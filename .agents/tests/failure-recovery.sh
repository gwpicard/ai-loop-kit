#!/usr/bin/env sh
# Run recovery in a disposable project and inspect the work it retained.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
python3 - "$ROOT" <<'PY'
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

root = Path(sys.argv[1])
helper = root / '.agents/skills/implement/scripts/recovery.py'
fixture = Path(tempfile.mkdtemp(prefix='kit-failure-recovery-'))

def run(*args, cwd=None, code=0):
    result = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert result.returncode == code, (args, result.returncode, result.stdout, result.stderr)
    return result.stdout.strip()

def git(project, *args):
    return run('git', '-C', project, *args)

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))

def load(path):
    return json.loads(path.read_text())

def call(state, command, *args, code=0):
    return run('python3', helper, command, '--state', state, '--piece', 1, *args, code=code)

def project(name, broken_base=False, parent=False, in_worktree=False):
    p = fixture / name
    p.mkdir()
    git(p, 'init', '-q', '-b', 'main')
    git(p, 'config', 'user.name', 'Fixture')
    git(p, 'config', 'user.email', 'fixture@example.invalid')
    (p / '.gitignore').write_text('.agents/runs/\n.agents/worktrees/\nprivate/\n')
    (p / 'shared.txt').write_text('broken' if broken_base else 'works')
    (p / 'dependent.txt').write_text('untouched')
    (p / 'check.py').write_text("from pathlib import Path\nassert Path('shared.txt').read_text() == 'works'\nassert not Path('failed.txt').exists()\n")
    git(p, 'add', '.')
    git(p, 'commit', '-qm', 'Working project')
    if parent:
        (p / 'successful.txt').write_text('earlier successful part')
        git(p, 'add', '.')
        git(p, 'commit', '-qm', 'Successful parent part')
    base = git(p, 'rev-parse', 'HEAD')
    main = p
    if in_worktree:
        p = main / '.agents/worktrees/failed'
        p.parent.mkdir(parents=True)
        git(main, 'worktree', 'add', '-qb', 'failed-piece', str(p), base)
    else:
        git(p, 'switch', '-qc', 'failed-piece')
    (p / 'failed.txt').write_text('failed committed work')
    git(p, 'add', '.')
    git(p, 'commit', '-qm', 'Unsuccessful work')
    failed_head = git(p, 'rev-parse', 'HEAD')
    (p / 'shared.txt').write_text('failed staged work')
    git(p, 'add', 'shared.txt')
    (p / 'shared.txt').write_text('failed unstaged work')
    (p / 'untracked.txt').write_text('new work')
    (p / 'private').mkdir()
    (p / 'private/ignored.txt').write_text('ignored evidence')
    os.symlink('ignored.txt', p / 'private/link')
    state = main / '.agents/runs/test/state.json'
    write(state, {'run':'test', 'merge_preapproved':False, 'pieces':[
        {'number':1,'state':'building','attempts':3,'branch':'failed-piece','worktree':str(p),'start_commit':base},
        {'number':2,'state':'waiting'}, {'number':3,'state':'waiting'},
        {'number':4,'state':'waiting'}, {'number':5,'state':'waiting'}]})
    evidence = state.parent / 'failed-checks.json'
    write(evidence, [{'command':'python3 check.py','exit_code':1}])
    return p, state, base, failed_head, evidence

def preserved(state, head):
    rec = load(state)['pieces'][0]['recovery']
    assert rec['stage'] == 'preserved'
    assert load(state)['pieces'][0]['state'] == 'building'
    assert git(Path(rec['source']), 'rev-parse', rec['retained_ref']) == head
    with tarfile.open(rec['archive']) as archive:
        assert archive.extractfile('failed.txt').read() == b'failed committed work'
        assert archive.extractfile('shared.txt').read() == b'failed unstaged work'
        assert archive.extractfile('untracked.txt').read() == b'new work'
        assert archive.extractfile('private/ignored.txt').read() == b'ignored evidence'
        assert archive.getmember('private/link').linkname == 'ignored.txt'
    assert 'failed staged work' in Path(rec['index_patch']).read_text()
    assert load(Path(rec['evidence']))[0]['exit_code'] == 1
    assert Path(rec['archive']).stat().st_mode & 0o077 == 0
    return rec

def refresh(state, base, direct_blocker=True, impact=True):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    issues = state.parent / 'current-issues.json'
    write(issues, {'observed_at':now,'issues':[
        {'number':1,'state':'open','labels':['state:shaping','shaping:research'],'blocked_by':[]},
        {'number':2,'state':'open','labels':['state:ready'],'blocked_by':[1] if direct_blocker else []},
        {'number':3,'state':'open','labels':['state:ready'],'blocked_by':[]},
        {'number':4,'state':'open','labels':['state:ready'],'blocked_by':[2]},
        {'number':5,'state':'open','labels':['state:ready'],'blocked_by':[]}]})
    reach = state.parent / 'current-impact.json'
    write(reach, {'observed_at':now, 'base_commit':base, 'tasks':{
        '2':{'independent':True,'reason':'separate area'},
        '3':{'independent':impact,'reason':'current code and checks read'},
        '4':{'independent':True,'reason':'separate area'},
        '5':{'independent':True,'reason':'other independent area'}}})
    return issues, reach

def eligible(state, task, issues, impact, code=0):
    return run('python3', helper, 'eligible', '--state',state,'--piece',1,
               '--candidate',task,'--issues',issues,'--impact',impact,code=code)

# Interrupt after preservation. Resume cannot claim anything until checks ran.
p, state, base, head, evidence = project('single')
# A current failed head is never accepted in place of the checked task boundary.
call(state, 'preserve', '--source',p,'--base',head,'--evidence',evidence,code=2)
assert 'recovery' not in load(state)['pieces'][0]
call(state, 'preserve', '--source',p,'--base',base,'--evidence',evidence)
rec = preserved(state, head)
issues, impact = refresh(state, base)
eligible(state,3,issues,impact,code=2)
call(state,'preserve','--source',p,'--base',base,'--evidence',evidence)
assert load(state)['pieces'][0]['recovery']['archive'] == rec['archive']
call(state,'baseline','--check','python3 check.py')
rec = load(state)['pieces'][0]['recovery']
assert rec['stage'] == 'checked' and rec['baseline_commit'] == base
assert rec['checks'][0]['exit_code'] == 0
assert load(state)['pieces'][0]['state'] == 'shaping'
assert 'unfinished' not in load(state)['pieces'][0]['reason'].lower()
baseline = Path(rec['baseline_worktree'])
assert git(baseline,'rev-parse','HEAD') == base
assert not (baseline/'failed.txt').exists()
assert (p/'failed.txt').exists() and (p/'private/ignored.txt').exists()
issues, impact = refresh(state, base)
eligible(state,2,issues,impact,code=2)
eligible(state,4,issues,impact,code=2)
eligible(state,3,issues,impact)
(baseline/'independent.txt').write_text('completed independent task')
run('python3','check.py',cwd=baseline)
git(baseline,'add','independent.txt')
git(baseline,'commit','-qm','Independent task complete')
assert (baseline/'dependent.txt').read_text() == 'untouched'
assert load(issues)['issues'][1]['labels'] == ['state:ready']
assert load(state)['pieces'][1]['state'] == 'waiting'
# The ordinary coordinator save marks only the independently built task to check.
data = load(state)
data['pieces'][2]['state'] = 'to check'
write(state,data)
data = load(issues)
data['issues'][2]['labels'] = ['state:in-review','review:person']
write(issues,data)
assert load(state)['pieces'][2]['state'] == 'to check'
assert load(issues)['issues'][2]['labels'] == ['state:in-review','review:person']
assert load(issues)['issues'][1]['labels'] == ['state:ready']
assert load(state)['pieces'][0]['state'] == 'shaping'
assert git(p,'rev-parse','HEAD') == head
# A changed checkout invalidates a prior green baseline, even for another task.
eligible(state,5,issues,impact,code=2)
advanced = git(baseline,'rev-parse','HEAD')
# A commit alone cannot move the checked base; its successful task must name it.
call(state,'baseline','--base',advanced,'--check','python3 check.py',code=2)
data = load(state)
data['pieces'][2]['checked_commit'] = advanced
write(state,data)
call(state,'baseline','--base',advanced,'--check','python3 check.py')
issues, impact = refresh(state,advanced)
eligible(state,5,issues,impact)
assert (baseline/'independent.txt').read_text() == 'completed independent task'
assert not (baseline/'failed.txt').exists()
assert load(state)['pieces'][1]['state'] == 'waiting'

# Restore pointers from the durable local record even when state lost its field.
data = load(state)
del data['pieces'][0]['recovery']
write(state,data)
call(state,'preserve','--source',p,'--base',base,'--evidence',evidence)
assert load(state)['pieces'][0]['recovery']['failed_commit'] == head

# Earlier successful parts survive; the unsuccessful part never reaches them.
p, state, base, head, evidence = project('parent', parent=True, in_worktree=True)
call(state,'preserve','--source',p,'--base',base,'--evidence',evidence,'--final-state','shaping')
preserved(state,head)
call(state,'baseline','--check','python3 check.py')
rec = load(state)['pieces'][0]['recovery']
baseline = Path(rec['baseline_worktree'])
assert (baseline/'successful.txt').read_text() == 'earlier successful part'
assert not (baseline/'failed.txt').exists()
assert load(state)['pieces'][0]['state'] == 'shaping'
assert git(p,'rev-parse','HEAD') == head
issues, impact = refresh(state,base,impact=False)
eligible(state,3,issues,impact,code=2)
issues, impact = refresh(state,base)
eligible(state,3,issues,impact)
# Stale observations and absent blocker records fail closed.
data = load(issues)
data['observed_at'] = '2000-01-01T00:00:00+00:00'
write(issues,data)
eligible(state,3,issues,impact,code=2)
issues, impact = refresh(state,base)
data = load(issues)
data['issues'][2]['blocked_by'] = [99]
write(issues,data)
eligible(state,3,issues,impact,code=2)
issues, impact = refresh(state,base)
# An ignored edit after checks invalidates the checked copy.
(baseline/'private').mkdir()
(baseline/'private/new.txt').write_text('new ignored input')
eligible(state,3,issues,impact,code=2)
# Preserve the changed copy and verify it again rather than deleting the input.
call(state,'baseline','--check','python3 check.py')
issues, impact = refresh(state,base)
eligible(state,3,issues,impact)
# Retention prevents cleanup even after the run state has become final.
worktrees = root / '.agents/skills/implement/scripts/worktree.sh'
assert 'Kept' in run('sh',worktrees,'remove',baseline,cwd=p,code=1)
assert baseline.exists()
assert 'Kept' in run('sh',worktrees,'remove',p,cwd=p,code=1)
assert p.exists() and (p/'failed.txt').exists()
# A partially checked recovery is still unfinished until the checks rerun.
data = load(state)
data['pieces'][0]['recovery']['stage'] = 'checking'
data['pieces'][0]['state'] = 'building'
write(state,data)
eligible(state,3,issues,impact,code=2)
call(state,'baseline','--check','python3 check.py')
issues, impact = refresh(state,base)
# Re-reading current blockers catches a newly introduced transitive dependency.
data = load(issues)
data['issues'][2]['blocked_by'] = [4]
write(issues,data)
eligible(state,3,issues,impact,code=2)

# A shared-base check failure blocks every candidate relying on this base.
p, state, base, head, evidence = project('shared-failure',broken_base=True)
call(state,'preserve','--source',p,'--base',base,'--evidence',evidence)
call(state,'baseline','--check','python3 check.py',code=2)
rec = load(state)['pieces'][0]['recovery']
assert rec['stage'] == 'blocked' and rec['checks'][0]['exit_code'] != 0
issues,impact = refresh(state,base)
eligible(state,3,issues,impact,code=2)
assert not (Path(rec['baseline_worktree'])/'independent.txt').exists()
assert load(state)['pieces'][1]['state'] == 'waiting'
# No check and a verification gap cannot be presented as passing.
call(state,'baseline',code=2)
call(state,'baseline','--check','true','--gap','Smoke check unavailable',code=2)
assert load(state)['pieces'][0]['recovery']['stage'] == 'blocked'
assert load(state)['pieces'][0]['recovery']['gaps'] == ['Smoke check unavailable']

def ready_fixture(name):
    p,state,base,head,evidence = project(name)
    call(state,'preserve','--source',p,'--base',base,'--evidence',evidence)
    call(state,'baseline','--check','python3 check.py')
    return p,state,base,head,evidence

def linked_input():
    p,state,base,head,evidence = project('changed-link')
    # Harmless fixture input stands in for an ignored credential file.
    (p/'.gitignore').write_text((p/'.gitignore').read_text() + '.env\n')
    git(p,'add','.gitignore')
    git(p,'commit','-qm','Ignore local input')
    base = git(p,'rev-parse','HEAD')
    data = load(state)
    data['pieces'][0]['start_commit'] = base
    write(state,data)
    (p/'.env').write_text('fixture input')
    call(state,'preserve','--source',p,'--base',base,'--evidence',evidence)
    check = "python3 -c \"from pathlib import Path; assert Path('.env').read_text() == 'fixture input'\""
    call(state,'baseline','--check',check)
    rec = load(state)['pieces'][0]['recovery']
    assert (Path(rec['baseline_worktree'])/'.env').is_symlink()
    issues,impact = refresh(state,base)
    eligible(state,3,issues,impact)
    (p/'.env').write_text('changed fixture input')
    eligible(state,3,issues,impact,code=2)
    call(state,'baseline','--check',"python3 -c \"from pathlib import Path; Path('.env').write_text('input changed by check')\"",code=2)
    rec = load(state)['pieces'][0]['recovery']
    assert rec['stage'] == 'blocked' and rec['gaps'] == ['Linked inputs changed during the baseline checks.']
    assert 'input changed by check' not in json.dumps(rec['baseline_links'])

def failed_prefix():
    p,state,base,head,evidence = project('failed-prefix')
    (p/'second.txt').write_text('second failed commit')
    git(p,'add','second.txt')
    git(p,'commit','-qm','More unsuccessful work')
    call(state,'preserve','--source',p,'--base',base,'--evidence',evidence)
    candidate = fixture/'prefix-candidate'
    git(p,'worktree','add','-qb','candidate',str(candidate),head)
    (candidate/'successful.txt').write_text('independent success')
    git(candidate,'add','successful.txt')
    git(candidate,'commit','-qm','Independent success')
    chosen = git(candidate,'rev-parse','HEAD')
    data = load(state)
    data['pieces'][2].update(state='to check',checked_commit=chosen)
    write(state,data)
    call(state,'baseline','--base',chosen,'--check','true',code=2)
    assert (candidate/'failed.txt').exists() and not (candidate/'second.txt').exists()

def split_record():
    p,state,base,head,evidence = ready_fixture('split-record')
    script = state.parent/'interrupt.py'
    script.write_text("""import importlib.util, os, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('recovery',sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
original = m.os.replace
def replace(source,target):
    if Path(target).name == 'state.json':
        os._exit(79)
    return original(source,target)
m.os.replace = replace
sys.argv = [sys.argv[1], 'baseline', '--state',sys.argv[2], '--piece','1','--check','false']
m.main()
""")
    run('python3',script,helper,state,code=79)
    rec = load(state)['pieces'][0]['recovery']
    record = Path(rec['archive']).parent/'recovery.json'
    assert rec['stage'] == 'checked' and load(record)['stage'] == 'checking'
    issues,impact = refresh(state,base)
    eligible(state,3,issues,impact,code=2)
    assert load(record)['stage'] == 'checking'
    call(state,'baseline','--check','false',code=2)
    assert load(state)['pieces'][0]['recovery']['stage'] == 'blocked'
    assert load(state)['pieces'][0]['recovery']['checks'][0]['exit_code'] != 0
    assert (p/'failed.txt').exists()

def hidden_tracked():
    for flag in ('--assume-unchanged','--skip-worktree'):
        p,state,base,head,evidence = ready_fixture('hidden-' + flag[2:])
        check = "git update-index " + flag + " shared.txt && printf 'hidden edit' > shared.txt"
        call(state,'baseline','--check','python3 check.py','--check',check,code=2)
        rec = load(state)['pieces'][0]['recovery']
        baseline = Path(rec['baseline_worktree'])
        assert git(baseline,'status','--porcelain') == ''
        assert (baseline/'shared.txt').read_text() == 'hidden edit'
        assert git(baseline,'show',base+':shared.txt') == 'works'
        issues,impact = refresh(state,base)
        eligible(state,3,issues,impact,code=2)

    for point in ('before','after'):
        p,state,base,head,evidence = ready_fixture('suppressed-' + point)
        rec = load(state)['pieces'][0]['recovery']
        baseline = Path(rec['baseline_worktree'])
        git(baseline,'update-index','--skip-worktree','shared.txt')
        (baseline/'shared.txt').write_text('hidden after success')
        assert git(baseline,'status','--porcelain') == ''
        if point == 'before':
            call(state,'baseline','--check','true',code=2)
        issues,impact = refresh(state,base)
        eligible(state,3,issues,impact,code=2)
        assert (baseline/'shared.txt').read_text() == 'hidden after success'

def linked_directory():
    p,state,base,head,evidence = project('linked-directory')
    (p/'.ai-build-kit-maintenance').write_text('worktree-links|private/assets\nconfidential|private/confidential\n')
    (p/'private/assets').mkdir()
    (p/'private/assets/font').write_text('fixture font')
    git(p,'add','.ai-build-kit-maintenance')
    git(p,'commit','-qm','Record linked build inputs')
    base = git(p,'rev-parse','HEAD')
    data = load(state)
    data['pieces'][0]['start_commit'] = base
    write(state,data)
    call(state,'preserve','--source',p,'--base',base,'--evidence',evidence)
    check = "python3 -c \"from pathlib import Path; assert Path('private/assets/font').read_text() == 'fixture font'\""
    call(state,'baseline','--check',check)
    rec = load(state)['pieces'][0]['recovery']
    baseline = Path(rec['baseline_worktree'])
    # A whole authorised folder link must include nested contents too.
    os.symlink(p/'private/assets',baseline/'private/folder')
    data = (p/'.ai-build-kit-maintenance').read_text()
    (p/'.ai-build-kit-maintenance').write_text(data.replace('private/assets','private/assets ; private/folder'))
    os.symlink('assets',p/'private/folder')
    call(state,'baseline','--check',check)
    issues,impact = refresh(state,base)
    eligible(state,3,issues,impact)
    (p/'private/assets/font').write_text('changed fixture font')
    eligible(state,3,issues,impact,code=2)
    call(state,'baseline','--check','true')
    rec = load(state)['pieces'][0]['recovery']
    assert 'private/folder' in rec['baseline_links']
    # Contents never enter command output or the private hash record.
    record = Path(rec['archive']).parent/'recovery.json'
    assert 'changed fixture font' not in record.read_text()
    assert record.stat().st_mode & 0o077 == 0
    outside = fixture/'outside-input'
    outside.write_text('outside fixture')
    os.symlink(outside,baseline/'private/unknown')
    call(state,'baseline','--check','true',code=2)
    rec = load(state)['pieces'][0]['recovery']
    assert rec['stage'] == 'blocked'
    assert rec['gaps'] == ['Linked baseline inputs could not be safely verified.']
    assert (baseline/'private/unknown').is_symlink()

def write_boundaries():
    for boundary in ('record-before','record-after','state-before','state-after','checked-before-state'):
        p,state,base,head,evidence = ready_fixture('interruption-' + boundary)
        old = load(state)['pieces'][0]['recovery']
        script = state.parent/'interrupt.py'
        script.write_text("""import importlib.util, json, os, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('recovery',sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
original = m.os.replace
boundary = sys.argv[3]
def replace(source,target):
    name = Path(target).name
    stage = json.loads(Path(source).read_text())
    if name == 'state.json': stage = stage['pieces'][0]['recovery']
    final = stage.get('stage') == 'checked'
    if (boundary == 'record-before' and name == 'recovery.json') or (
            boundary == 'state-before' and name == 'state.json') or (
            boundary == 'checked-before-state' and name == 'state.json' and final):
        os._exit(79)
    original(source,target)
    if (boundary == 'record-after' and name == 'recovery.json') or (
            boundary == 'state-after' and name == 'state.json'):
        os._exit(79)
m.os.replace = replace
sys.argv = [sys.argv[1], 'baseline', '--state',sys.argv[2], '--piece','1','--check','true']
m.main()
""")
        run('python3',script,helper,state,boundary,code=79)
        issues,impact = refresh(state,base)
        eligible(state,3,issues,impact,code=2)
        # The resume route uses the same reconciliation, without claiming work.
        call(state,'reconcile')
        rec = load(state)['pieces'][0]['recovery']
        assert rec['stage'] == 'checking'
        assert load(Path(rec['archive']).parent/'recovery.json') == rec
        assert load(state)['pieces'][0]['state'] == 'building'
        assert rec['generation'] > old['generation']
        call(state,'baseline','--check','python3 check.py')
        issues,impact = refresh(state,base)
        eligible(state,3,issues,impact)
        assert (p/'failed.txt').exists()

        # A stale writer cannot put an earlier checked generation back.
        stale_script = state.parent/'stale.py'
        write(state.parent/'old.json',old)
        stale_script.write_text("""import importlib.util, json, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('recovery',sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
state = m.read(sys.argv[2]); old = m.read(Path(sys.argv[2]).parent/'old.json')
try: m.attach(sys.argv[2],state,state['pieces'][0],old)
except ValueError: sys.exit(2)
""")
        before = load(state)
        run('python3',stale_script,helper,state,code=2)
        assert load(state) == before

def left_out():
    # A failed attempt that installed dependencies and holds a key in .env. The
    # copy keeps the work, never the installed folders, and an env file by its
    # name alone.
    p,state,base,head,evidence = project('left-out')
    (p/'.gitignore').write_text((p/'.gitignore').read_text() +
                                'node_modules/\n.venv/\nvenv/\n__pycache__/\n.next/\ndist/\n'
                                'build/\ncoverage/\n.env\n.env.local\n')
    for folder in ('node_modules/pkg', '.venv/lib', 'venv/lib', 'app/__pycache__', '.next/cache',
                   'dist', 'build', 'coverage'):
        (p/folder).mkdir(parents=True, exist_ok=True)
        (p/folder/'kept-out.txt').write_text('installed, not work')
    (p/'.env').write_text('SECRET=fixture-secret-value\n')
    (p/'.env.local').write_text('OTHER=fixture-other-value\n')
    call(state,'preserve','--source',p,'--base',base,'--evidence',evidence)
    rec = load(state)['pieces'][0]['recovery']
    with tarfile.open(rec['archive']) as archive:
        names = archive.getnames()
        for member in archive.getmembers():
            if member.isfile():
                data = archive.extractfile(member).read()
                assert b'fixture-secret-value' not in data and b'fixture-other-value' not in data
    for folder in ('node_modules', '.venv', 'venv', 'app/__pycache__', '.next', 'dist', 'build',
                   'coverage'):
        assert not any(n == folder or n.startswith(folder + '/') for n in names), (folder, names)
    assert '.env' not in names and '.env.local' not in names, names
    assert 'failed.txt' in names and 'untracked.txt' in names, names
    manifest = load(Path(rec['manifest']))
    for folder in ('node_modules', '.venv', 'venv', 'app/__pycache__', '.next', 'dist', 'build',
                   'coverage'):
        assert manifest.get(folder, {}).get('kind') == 'left out', (folder, manifest)
    assert manifest.get('.env', {}).get('kind') == 'env', manifest
    assert manifest.get('.env.local', {}).get('kind') == 'env', manifest
    for record in (Path(rec['manifest']), Path(rec['archive']).parent/'recovery.json', state):
        text = record.read_text()
        assert 'fixture-secret-value' not in text and 'fixture-other-value' not in text
    # Nothing is deleted: the installed folders and the key stay where they were.
    assert (p/'node_modules/pkg/kept-out.txt').exists() and (p/'.env').exists()

def per_attempt():
    # Each attempt is kept on its own, at most once, inside the piece's folder.
    p,state,base,head,evidence = project('per-attempt')
    call(state,'preserve','--source',p,'--base',base,'--evidence',evidence,'--attempt','1')
    first = load(state)['pieces'][0]['recovery']
    git(p,'add','-A')
    git(p,'commit','-qm','Second attempt')
    (p/'second.txt').write_text('second attempt')
    second_head = git(p,'rev-parse','HEAD')
    call(state,'preserve','--source',p,'--base',base,'--evidence',evidence,'--attempt','2')
    second = load(state)['pieces'][0]['recovery']
    folder = p/'.agents/recovery/test-1'
    assert Path(first['archive']).parent == folder/'attempt-1', first['archive']
    assert Path(second['archive']).parent == folder/'attempt-2', second['archive']
    assert Path(first['archive']).exists()
    assert git(p,'rev-parse',first['retained_ref']) == head
    assert git(p,'rev-parse',second['retained_ref']) == second_head
    with tarfile.open(second['archive']) as archive:
        assert archive.extractfile('second.txt').read() == b'second attempt'
    call(state,'preserve','--source',p,'--base',base,'--evidence',evidence,'--attempt','2')
    assert load(state)['pieces'][0]['recovery']['archive'] == second['archive']
    assert sorted(x.name for x in folder.iterdir()) == ['attempt-1', 'attempt-2']

def no_result():
    # A builder whose session died leaves no result file. Its attempt is not
    # counted while it may still be running, and once it is known to have
    # ended it counts as a failed attempt, with its work kept.
    sys.path.insert(0, str(root/'.agents/tests/lib'))
    sys.dont_write_bytecode = True
    import loop_project as lp
    lab = lp.Lab('no-result')
    repo = lab.project()
    os.makedirs(os.path.join(repo, '.agents'), exist_ok=True)
    with open(os.path.join(repo, '.agents', 'loop-settings.json'), 'w') as handle:
        json.dump({'attempts': 3, 'piece_budget_minutes': 120}, handle)
    lab.ready_piece(repo)
    code, out, err = lab.runpy(repo, 'start', '12')
    name = lab.run_name_of(out)
    code, out, err = lab.runpy(repo, 'next', '12', '--run', name)
    request = lab.request_of(out)
    assert request, out + err
    start = lab.git(repo, 'rev-parse', 'HEAD')
    lab.stub_builder(repo, request, {'app/billing/kept.py': 'K = 1\n'}, None)
    lab.write(repo, {'app/billing/loose.py': 'L = 1\n'})
    code, out, err = lab.runpy(repo, 'next', '12', '--run', name)
    again = lab.request_of(out) or {}
    assert again.get('handoff') == request['handoff'], out + err
    pieces = Path(repo)/'.agents/pieces/12'
    assert not pieces.exists() or not list(pieces.glob('attempt-*.md')), 'counted too soon'
    assert (Path(repo)/'app/billing/loose.py').exists()
    code, out, err = lab.runpy(repo, 'ended', '12', '--run', name)
    note = pieces/'attempt-1.md'
    assert code == 0 and note.exists() and 'Status: no result' in note.read_text(), out + err
    archive = Path(repo)/'.agents/recovery'/(name + '-12')/'attempt-1'/'files.tar'
    with tarfile.open(archive) as kept:
        assert kept.extractfile('app/billing/kept.py').read() == b'K = 1\n'
        assert kept.extractfile('app/billing/loose.py').read() == b'L = 1\n'
    assert lab.git(repo, 'diff', start, 'HEAD') == '', 'the next attempt does not start clean'
    following = lab.request_of(out) or {}
    assert following.get('attempt') == 2, out + err
    lab.finish('no-result probe')

# Independent projects let every regression report before the test stops.
failures=[]
for probe in (linked_input,failed_prefix,split_record,hidden_tracked,linked_directory,write_boundaries,
              left_out,per_attempt,no_result):
    try:
        probe()
        print('Passed:',probe.__name__)
    except AssertionError as error:
        failures.append(probe.__name__)
        print('Failed:',probe.__name__,error)
assert not failures, failures

print('Failure recovery passed: retained files and commits, checked independent work, blocked dependants, successful parent parts, shared failure and interrupted recovery.')
print('Disposable artifacts:', fixture)
PY
