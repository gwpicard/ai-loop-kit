#!/usr/bin/env python3
"""Keep unsuccessful work locally and check a separate base before continuation.

Only the coordinating session calls this helper, through the run script beside
it, run.py, once a failed attempt of the build loop is known to have ended. It
never pushes, claims, labels, merges or changes the failed checkout. Each
attempt is kept once, under .agents/recovery/<run name>-<number>/attempt-<n>/.
The installed folders a project can make again, such as node_modules/, are left
out and named in the manifest, and an env file is named there and never copied,
so a key never lands in the copy. The kit never deletes these folders. See the
section-builder skill's references/build-loop.md and the implement skill's
references/running-longer.md.
"""

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
from pathlib import Path


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.pending')
    with temp.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def git(source, *args):
    result = subprocess.run(['git', '-C', str(source), *args], capture_output=True, check=False)
    if result.returncode:
        raise ValueError('Git could not ' + args[0] + '; work is kept.')
    return result.stdout


def commit(source, ref):
    return git(source, 'rev-parse', '--verify', ref + '^{commit}').decode().strip()


def digest(data):
    return hashlib.sha256(data).hexdigest()


# Folders a project makes again from its own files, such as installed
# dependencies and build output. A copy of them is large and holds nothing a
# person wrote, so each is named in the manifest and left out.
LEFT_OUT = ('node_modules', '.venv', 'venv', '__pycache__', '.next', 'dist', 'build', 'coverage')


def is_env_file(name):
    return name == '.env' or name.startswith('.env.')


def inventory(source):
    """Include ignored work without following links or nesting other worktrees.

    An installed folder is named and left out. An env file is named by its name
    alone, never read, since it holds keys.
    """
    result = {}

    def unreadable(error):
        raise ValueError('A working folder could not be read; stop preservation.')

    for folder, dirs, files in os.walk(source, followlinks=False, onerror=unreadable):
        rel = Path(folder).relative_to(source)
        for d in sorted(dirs):
            if d in LEFT_OUT and not (Path(folder) / d).is_symlink():
                result[(rel / d).as_posix()] = {'kind':'left out'}
        dirs[:] = sorted(d for d in dirs if (rel / d).as_posix() not in
                         ('.git', '.agents/runs', '.agents/worktrees', '.agents/recovery')
                         and not (d in LEFT_OUT and not (Path(folder) / d).is_symlink()))
        for name in sorted(files + [d for d in dirs if (Path(folder) / d).is_symlink()]):
            path = Path(folder) / name
            key = path.relative_to(source).as_posix()
            if key == '.git':
                continue
            if is_env_file(name) and not path.is_symlink():
                result[key] = {'kind':'env'}
            elif path.is_symlink():
                result[key] = {'kind':'link', 'target':os.readlink(path)}
            elif path.is_file():
                result[key] = {'kind':'file', 'sha256':digest(path.read_bytes()),
                               'mode':path.stat().st_mode & 0o777}
            else:
                raise ValueError('A special file cannot be preserved; stop recovery.')
    return result


def regular_bytes(path):
    """Read a regular file without opening a final link or waiting on a pipe."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('A baseline input is not a regular file; verification is incomplete.')
        data = stream.read()
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('A baseline input changed while it was read; check it again.')
    return data


def tracked_matches(path, chosen):
    """Compare actual bytes and kinds with the tree, regardless of index flags."""
    for entry in git(path, 'ls-tree', '-rz', chosen).split(b'\0'):
        if not entry:
            continue
        header, name = entry.split(b'\t', 1)
        mode, kind, oid = header.split()
        relative = Path(os.fsdecode(name))
        working = path / relative
        if any((path / parent).is_symlink() for parent in relative.parents):
            return False
        expected = git(path, 'cat-file', 'blob', oid.decode()) if kind == b'blob' else None
        if mode == b'120000':
            if not working.is_symlink() or os.fsencode(os.readlink(working)) != expected:
                return False
        elif mode in (b'100644', b'100755'):
            if working.is_symlink() or not working.is_file():
                return False
            if regular_bytes(working) != expected:
                return False
            if bool(working.stat().st_mode & 0o111) != (mode == b'100755'):
                return False
        else:
            raise ValueError('A tracked input cannot be compared with its commit; verification is incomplete.')
    return True


def linked_inputs(path, main):
    """Fingerprint established inputs separately from the no-dereference archive."""
    record = main / '.ai-build-kit-maintenance'
    lines = record.read_text().splitlines() if record.exists() else []
    listed = []
    confidential = []
    for line in lines:
        if line.startswith('worktree-links|'):
            listed = [Path(p.strip().removeprefix('./').rstrip('/'))
                      for p in line.split('|', 1)[1].split(' ; ') if p.strip()]
        if line.startswith('confidential|'):
            confidential.append(Path(line.split('|', 1)[1].strip().removeprefix('./').rstrip('/')))
    result = {}

    def fingerprint(target, allowed, seen):
        real = target.resolve(strict=True)
        if not real.is_relative_to(allowed) or any(
                real.is_relative_to((main / c).resolve()) for c in confidential):
            raise ValueError('A linked input has no safe established target; verification is incomplete.')
        if real in seen:
            raise ValueError('A linked input loops; verification is incomplete.')
        if real.is_dir():
            value = {p.name:fingerprint(p, allowed, seen | {real})
                     for p in sorted(real.iterdir())}
        else:
            value = {'sha256':digest(regular_bytes(real)), 'mode':real.stat().st_mode & 0o777}
        if target.resolve(strict=True) != real:
            raise ValueError('A linked input changed while it was read; check it again.')
        return {'target':str(real), 'input':value}

    for name, item in inventory(path).items():
        if item['kind'] != 'link':
            continue
        link = path / name
        real = link.resolve(strict=True)
        if real.is_relative_to(path):
            allowed = path
        else:
            relative = Path(name)
            env = len(relative.parts) == 1 and (name == '.env' or name.startswith('.env.'))
            authorised = env or any(relative == p or relative.is_relative_to(p) for p in listed
                                   if not p.is_absolute() and '..' not in p.parts)
            ignored = subprocess.run(['git','-C',str(path),'check-ignore','-q','--',name],
                                     capture_output=True, check=False).returncode == 0
            if (not authorised or not ignored or not real.is_relative_to(main) or
                    real != (main / name).resolve(strict=True)):
                raise ValueError('A linked input has no safe established target; verification is incomplete.')
            allowed = real if real.is_dir() else main
        result[name] = fingerprint(link, allowed, set())
    return result


def baseline_inputs(args, state, piece, rec, path, main):
    try:
        return linked_inputs(path, main)
    except (OSError, ValueError, RuntimeError):
        message = 'Linked baseline inputs could not be safely verified.'
        rec['gaps'].append(message)
        rec['stage'] = 'blocked'
        attach(args.state, state, piece, rec)
        raise ValueError(message) from None


def verify(source, rec):
    if commit(source, rec['retained_ref']) != rec['failed_commit']:
        raise ValueError('The retained commit does not match; stop recovery.')
    manifest = {name:item for name, item in read(rec['manifest']).items()
                if item.get('kind') in ('file', 'link')}
    with tarfile.open(rec['archive'], 'r') as archive:
        members = {member.name:member for member in archive.getmembers()}
        if set(members) != set(manifest):
            raise ValueError('The retained files do not match their record.')
        for name, expected in manifest.items():
            member = members[name]
            if expected['kind'] == 'link':
                valid = member.issym() and member.linkname == expected['target']
            else:
                valid = (member.isfile() and member.mode == expected['mode'] and
                         digest(archive.extractfile(member).read()) == expected['sha256'])
            if not valid:
                raise ValueError('A retained file could not be verified.')
    for name in ('index_patch', 'evidence'):
        if digest(Path(rec[name]).read_bytes()) != rec[name + '_sha256']:
            raise ValueError('Retained evidence could not be verified.')


def attach(state_path, state, piece, rec):
    record = Path(rec['archive']).parent / 'recovery.json'
    generation = rec.get('generation', 0)
    if record.exists() and read(record).get('generation', 0) != generation:
        raise ValueError('Recovery advanced since it was read; reconcile before continuing.')
    rec['generation'] = generation + 1
    save(record, rec)
    piece['recovery'] = rec
    # Pending recovery must still be found by older waiting/building readers.
    piece['state'] = 'building' if rec['stage'] in ('preserved', 'checking') else rec['final_state']
    if piece['state'] == 'building':
        piece['reason'] = 'Recovery unfinished; no task may use this base yet.'
    else:
        piece['reason'] = rec.get('failure_reason', 'Unsuccessful work retained for review.')
        if rec['stage'] == 'blocked':
            piece['reason'] += ' The shared baseline has not passed all checks.'
    save(state_path, state)


def reconcile(args, state, piece):
    """The durable record owns the generation; disagreement is unfinished work."""
    state_path = Path(args.state).resolve()
    main = state_path.parents[3]
    name = state.get('run', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', name) or not state_path.is_relative_to(main / '.agents/runs'):
        raise ValueError('Run state has no safe recovery location.')
    saved = piece.get('recovery')
    attempt = getattr(args, 'attempt', None) or (saved or {}).get('attempt')
    folder = recovery_folder(main, name, piece['number'], attempt)
    record = folder / 'recovery.json'
    if folder.is_symlink() or folder.parent.is_symlink() or record.is_symlink():
        raise ValueError('A recovery record must not be a link.')
    if not record.exists():
        if saved or record.with_name('recovery.json.pending').exists():
            raise ValueError('Recovery has no complete durable record; keep its files and stop.')
        return
    rec = read(record)
    if rec['piece'] != piece['number'] or Path(rec['archive']).parent != folder:
        raise ValueError('The durable recovery record identifies other work; stop.')
    pending = (record.with_name('recovery.json.pending').exists() or
               state_path.with_name(state_path.name + '.pending').exists())
    if rec != saved or pending:
        # Even a checked write interrupted before run state is saved must recheck.
        if rec['stage'] == 'checked' or pending:
            rec['stage'] = 'checking'
            rec.setdefault('gaps', []).append('Recovery records were interrupted; rerun baseline checks.')
            rec.pop('eligibility', None)
        verify(Path(rec['source']), rec)
        attach(args.state, state, piece, rec)


def recovery_folder(main, name, number, attempt):
    """Where a piece's kept work goes: one folder for the piece in this run,
    and inside it one for each attempt of the build loop."""
    folder = main / '.agents/recovery' / (name + '-' + str(number))
    return folder / ('attempt-' + str(attempt)) if attempt else folder


def preserve(args, state, piece):
    source = Path(args.source).resolve()
    main = Path(git(source, 'worktree', 'list', '--porcelain').decode().splitlines()[0][9:])
    state_path = Path(args.state).resolve()
    if not state_path.is_relative_to(main / '.agents/runs'):
        raise ValueError('Run state must stay in the main project runs folder.')
    name = state.get('run', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
        raise ValueError('The run name is not safe for a recovery folder.')
    base = commit(source, args.base)
    if not piece.get('start_commit') or base != commit(source,piece['start_commit']):
        raise ValueError('The base is not the recorded checked task boundary; stop recovery.')
    folder = recovery_folder(main, name, args.piece, args.attempt)
    store = main / '.agents/recovery'
    if any(p.is_symlink() for p in (folder, folder.parent, store)):
        raise ValueError('A recovery folder must not be a link.')
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    (store / '.gitignore').write_text('*\n')
    if subprocess.run(['git','-C',str(main),'check-ignore','-q',str(folder)], check=False).returncode:
        raise ValueError('Recovery storage is not ignored by Git.')
    record = folder / 'recovery.json'
    if record.exists():
        reconcile(args, state, piece)
        rec = piece['recovery']
        if rec['source'] != str(source) or rec['requested_base'] != base:
            raise ValueError('This recovery already identifies different work; stop.')
        verify(source, rec)
        attach(state_path, state, piece, rec)
        return
    head = commit(source, 'HEAD')
    # A parent base must already be an ancestor, never guessed from main.
    git(source, 'merge-base', '--is-ancestor', base, head)
    ref = 'refs/ai-build-kit/recovery/' + name + '/' + str(args.piece)
    if args.attempt:
        ref += '/attempt-' + str(args.attempt)
    existing = subprocess.run(['git','-C',str(source),'rev-parse','--verify',ref],
                              capture_output=True, check=False)
    if existing.returncode == 0:
        if existing.stdout.decode().strip() != head:
            raise ValueError('A previous recovery points at other work; stop.')
    else:
        git(source, 'update-ref', ref, head, '0' * len(head))
    before = inventory(source)
    index = git(source, 'diff', '--cached', '--binary', 'HEAD')
    evidence = Path(args.evidence).read_bytes()
    if not evidence:
        raise ValueError('Failed check evidence is empty; keep the checkout and stop.')
    archive_path = folder / 'files.tar'
    temp = folder / 'files.tar.pending'
    with tarfile.open(temp, 'w', dereference=False) as archive:
        for name, item in before.items():
            if item['kind'] not in ('file', 'link'):
                continue
            archive.inodes.clear()  # Keep each hard-linked file recoverable on its own.
            archive.add(source / name, arcname=name, recursive=False)
    os.replace(temp, archive_path)
    save(folder / 'manifest.json', before)
    (folder / 'index.patch').write_bytes(index)
    (folder / 'checks-before-recovery').write_bytes(evidence)
    rec = {'piece':args.piece, 'stage':'preserved', 'source':str(source),
           'retained_ref':ref, 'failed_commit':head, 'requested_base':base,
           'archive':str(archive_path), 'manifest':str(folder / 'manifest.json'),
           'index_patch':str(folder / 'index.patch'), 'index_patch_sha256':digest(index),
           'evidence':str(folder / 'checks-before-recovery'), 'evidence_sha256':digest(evidence),
           'attempt':args.attempt,
           'left_out':sorted(n for n, item in before.items() if item['kind'] == 'left out'),
           'env_files':sorted(n for n, item in before.items() if item['kind'] == 'env'),
           'final_state':args.final_state, 'failure_reason':piece.get('reason') or
           'Unsuccessful work retained for review.', 'preserved_at':now(), 'checks':[], 'gaps':[]}
    verify(source, rec)
    if (inventory(source) != before or commit(source, 'HEAD') != head or
            git(source, 'diff', '--cached', '--binary', 'HEAD') != index):
        raise ValueError('The failed checkout changed during preservation; stop.')
    attach(state_path, state, piece, rec)


def baseline(args, state, piece):
    reconcile(args, state, piece)
    rec = piece.get('recovery')
    if not rec:
        raise ValueError('Preserve work before checking a baseline.')
    source = Path(rec['source'])
    verify(source, rec)
    chosen = commit(source,args.base) if args.base else rec.get('baseline_commit',rec['requested_base'])
    if chosen != rec['requested_base']:
        successful = [item for item in state['pieces'] if item.get('checked_commit') == chosen
                      and item['number'] != args.piece and
                      (item.get('state') in ('to check','merged') or
                       (item.get('state') == 'building' and
                        item.get('reason') == "waiting for the parent's pull request"))]
        if not successful:
            raise ValueError('A later baseline has no successfully checked task checkpoint.')
        git(source,'merge-base','--is-ancestor',rec['requested_base'],chosen)
        failed_commits = git(source, 'rev-list', rec['requested_base'] + '..' +
                            rec['failed_commit']).decode().splitlines()
        for failed_commit in failed_commits:
            contains_failure = subprocess.run(['git','-C',str(source),'merge-base',
                                                '--is-ancestor',failed_commit,chosen],
                                               capture_output=True, check=False)
            if contains_failure.returncode != 1:
                raise ValueError('A later baseline may contain the failed task; stop recovery.')
    if not args.check:
        raise ValueError('No existing project checks were supplied; the base is unchecked.')
    main = Path(git(source,'worktree','list','--porcelain').decode().splitlines()[0][9:])
    path = main / '.agents/worktrees' / ('recovery-' + state['run'] + '-' + str(args.piece))
    rec['baseline_worktree'] = str(path)
    rec['baseline_commit'] = chosen
    rec['stage'] = 'checking'
    rec['checks'] = []
    rec['gaps'] = args.gap or []
    attach(args.state,state,piece,rec)
    if path.is_symlink():
        raise ValueError('The baseline path is a link; stop recovery.')
    branch = 'recovery/' + state['run'] + '-' + str(args.piece)
    worktrees = Path(__file__).with_name('worktree.sh')
    opened = subprocess.run(['sh',str(worktrees),'open','--resume',path.name,branch,
                             chosen], cwd=main, capture_output=True, check=False)
    if opened.returncode:
        raise ValueError('The baseline worktree could not be opened; the failed work is kept.')
    if (commit(path,'HEAD') != chosen or
            git(path,'status','--porcelain').strip() or not tracked_matches(path, chosen)):
        raise ValueError('The baseline differs from its identified commit; stop recovery.')
    before_links = baseline_inputs(args, state, piece, rec, path, main)
    for command in args.check:
        result = subprocess.run(command, shell=True, cwd=path,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        rec['checks'].append({'command':command,'exit_code':result.returncode})
        attach(args.state,state,piece,rec)
    clean = (commit(path,'HEAD') == chosen and not git(path,'status','--porcelain').strip()
             and tracked_matches(path, chosen))
    after_links = baseline_inputs(args, state, piece, rec, path, main)
    if before_links != after_links:
        rec['gaps'].append('Linked inputs changed during the baseline checks.')
    if not clean:
        rec['gaps'].append('The checks changed the baseline checkout.')
    rec['stage'] = 'checked' if clean and not rec['gaps'] and all(
        item['exit_code'] == 0 for item in rec['checks']) else 'blocked'
    rec['checked_at'] = now()
    # Keep the file inventory with the commit the checks actually saw.
    rec['baseline_files'] = inventory(path)
    rec['baseline_links'] = after_links
    attach(args.state,state,piece,rec)
    if rec['stage'] != 'checked':
        raise ValueError('The shared baseline is not verified; stop work that relies on it.')


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('Evidence needs an explicit observation time zone.')
    return parsed


def eligible(args, state, piece):
    reconcile(args, state, piece)
    rec = piece.get('recovery', {})
    if rec.get('stage') != 'checked':
        raise ValueError('Recovery has no checked baseline; do not claim the next task.')
    verify(Path(rec['source']),rec)
    path = Path(rec['baseline_worktree'])
    main = Path(git(path,'worktree','list','--porcelain').decode().splitlines()[0][9:])
    if (commit(path,'HEAD') != rec['baseline_commit'] or
            git(path,'status','--porcelain').strip() or not tracked_matches(path,rec['baseline_commit']) or
            inventory(path) != rec['baseline_files'] or
            linked_inputs(path,main) != rec.get('baseline_links')):
        raise ValueError('The baseline changed after its checks; check it again before continuation.')
    issues, impact = read(args.issues), read(args.impact)
    for evidence in (issues, impact):
        observed = timestamp(evidence['observed_at'])
        if observed < timestamp(rec['checked_at']) or observed > timestamp(now()):
            raise ValueError('Refresh issue blockers and code impact after checking the baseline.')
    if impact['base_commit'] != rec['baseline_commit']:
        raise ValueError('Code impact was read against a different baseline.')
    items = {item['number']:item for item in issues['issues']}
    candidate = items[args.candidate]
    if candidate['state'] != 'open' or 'state:ready' not in candidate['labels']:
        raise ValueError('The next task is no longer ready and open.')
    reach = impact['tasks'].get(str(args.candidate), {})
    if reach.get('independent') is not True or not reach.get('reason'):
        raise ValueError('Current code impact does not establish safe continuation.')
    by_number = {item['number']:item for item in state['pieces']}
    seen = set()

    def visit(number):
        if number in seen:
            raise ValueError('Dependency cycle or unreadable blocker; do not continue.')
        seen.add(number)
        item = items[number]
        if number == args.piece:
            raise ValueError('This task depends on the unsuccessful task.')
        for blocker in item['blocked_by']:
            other = items[blocker]
            if other['state'] == 'closed':
                continue
            visit(blocker)
            saved = by_number.get(blocker, {})
            if saved.get('state') not in ('to check','merged') or saved.get('recovery'):
                raise ValueError('An open prerequisite has not completed its build.')
        seen.remove(number)

    visit(args.candidate)
    piece['recovery']['eligibility'] = {'candidate':args.candidate,'observed_at':now(),
                                       'issues':str(Path(args.issues).resolve()),
                                       'impact':str(Path(args.impact).resolve()),
                                       'reason':reach['reason']}
    attach(args.state,state,piece,rec)
    print('The next task may use the checked baseline; its normal readiness and claim steps still apply.')


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['preserve','baseline','eligible','reconcile'])
    parser.add_argument('--state',required=True)
    parser.add_argument('--piece',required=True,type=int)
    parser.add_argument('--source')
    parser.add_argument('--base')
    parser.add_argument('--evidence')
    parser.add_argument('--final-state', choices=['shaping'],default='shaping')
    parser.add_argument('--attempt',type=int)
    parser.add_argument('--check',action='append')
    parser.add_argument('--gap',action='append')
    parser.add_argument('--candidate',type=int)
    parser.add_argument('--issues')
    parser.add_argument('--impact')
    args = parser.parse_args()
    required = {'preserve':['source','base','evidence'], 'baseline':[],
                'eligible':['candidate','issues','impact'], 'reconcile':[]}[args.command]
    if any(getattr(args,key) is None for key in required):
        parser.error('Missing inputs for ' + args.command)
    try:
        # A single coordinator owns recovery, but a stale concurrent call still fails closed.
        with Path(args.state).with_name('recovery.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = read(args.state)
            piece = next(item for item in state['pieces'] if item['number'] == args.piece)
            globals()[args.command](args,state,piece)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    except (OSError, KeyError, StopIteration, RuntimeError, tarfile.TarError):
        # Paths and project command output can contain confidential material.
        print('Recovery could not establish safe continuation; keep its files and inspect the local record.',file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
