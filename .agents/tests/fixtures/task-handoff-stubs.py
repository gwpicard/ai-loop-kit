"""Offline contract rehearsal, not an agent implementation or context measurement."""
import copy
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# The same bounded brief shown to installed builders supplies the fixture.
text = Path(sys.argv[1]).read_text()
found = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)
assert found is not None, "the task handoff shows no brief"
brief = json.loads(found.group(1))
required = {"task", "handoff", "requirements", "baseline", "records", "artifacts", "run",
            "authorisation", "resources", "result"}
assert required <= brief.keys()

# Each invocation is a new OS process with only the brief on stdin. It models
# the exposed-tool contract; no model is called and no client is installed.
stub = r'''
import json
from pathlib import Path
import sys
b = json.load(sys.stdin)
c = b['capability']
if c['fresh'] and c['write'] and not c['inherit'] and not c['resume_id']:
    route = 'fresh-builder'
elif c['reset'] and c['evidence'] and c['write']:
    route = 'supported-reset-resume'
else:
    print(json.dumps({'route': 'unavailable', 'resume': '/implement', 'waiting': True}))
    sys.exit(0)
assert 'transcript' not in b and 'merge_preapproved' not in b
assert Path.cwd() == Path(b['baseline']['directory']).resolve()
assert b['baseline']['commit'] == Path('HEAD').read_text()
assert Path(b['requirements']).read_text() == 'show notes'
assert b['authorisation']['scope'] == ['task']
for p in b['records']:
    assert Path(p).is_file()
prior = [Path(p).read_text() for p in b['artifacts']]
assert prior == ['earlier checked output']
for resource in b['resources'].values():
    if resource['owner'] != 'coordinator':
        assert resource['owner'] == b['task']
        assert resource['transfer'] == {'released_by': 'coordinator', 'acknowledged_by': b['task']}
# This builder has no resource transfer; it reports the missing observation.
result = {'handoff': b['handoff'], 'route': route, 'commit': 'built-ref', 'checks': [{'command': 'sample check', 'exit': 0}],
          'flags': [], 'unseen': ['browser retained by coordinator'],
          'evidence': b['artifacts'], 'resources': b['resources']}
Path(b['result']).write_text(json.dumps(result))
print(json.dumps({'result': b['result']}))
'''

with tempfile.TemporaryDirectory(prefix="task-handoff-") as temp:
    root = Path(temp)
    task = root / "task"
    task.mkdir()
    run = root / "run"
    run.mkdir()
    (run / "state.json").write_text('{"pieces":[{"state":"waiting","attempts":1}]}')
    (run / "progress.md").write_text('previous task checked\n')
    (root / "earlier").mkdir()
    (root / "earlier/result.md").write_text('earlier checked output')
    for record in brief['records']:
        p = root / record
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('relevant saved record')
    (task / "requirements.md").write_text('show notes')
    (task / "HEAD").write_text('checked-ref')
    current = copy.deepcopy(brief)
    current['baseline']['directory'] = str(task)
    current['requirements'] = str(task / 'requirements.md')
    current['records'] = [str(root / p) for p in brief['records']]
    current['artifacts'] = [str(root / p) for p in brief['artifacts']]
    current['result'] = str(task / 'result.json')
    current['run']['directory'] = str(run)
    current['resources']['server']['directory'] = str(task)
    current['capability'] = {'fresh': True, 'write': True, 'inherit': False,
                             'resume_id': None, 'reset': False, 'evidence': ''}
    original_state = {p.name: p.read_bytes() for p in run.iterdir()}

    def invoke(value):
        return subprocess.run([sys.executable, '-c', stub], input=json.dumps(value),
                              text=True, cwd=task, capture_output=True, check=False)

    first = invoke(current)
    assert first.returncode == 0, first.stderr
    result = json.loads(Path(current['result']).read_text())
    assert result['route'] == 'fresh-builder'
    assert result['handoff'] == current['handoff']
    stale = copy.deepcopy(result)
    stale['handoff'] = 'previous-attempt'
    assert stale['handoff'] != current['handoff']
    assert result['resources'] == current['resources']
    assert {p.name: p.read_bytes() for p in run.iterdir()} == original_state
    # A later invocation knows only saved sources; changing that source is seen.
    saved = Path(current['artifacts'][0])
    saved.write_text('changed artifact')
    assert invoke(current).returncode != 0
    saved.write_text('earlier checked output')
    assert invoke(current).returncode == 0
    # An acknowledged transfer may change ownership; one missing side may not.
    transferred = copy.deepcopy(current)
    for resource in transferred['resources'].values():
        resource['owner'] = transferred['task']
        resource['transfer'] = {'released_by': 'coordinator', 'acknowledged_by': transferred['task']}
    assert invoke(transferred).returncode == 0
    for missing in ('released_by', 'acknowledged_by'):
        unacknowledged = copy.deepcopy(transferred)
        del unacknowledged['resources']['browser']['transfer'][missing]
        assert invoke(unacknowledged).returncode != 0
    # Baseline mismatch and inherited transcript are refused by the stub.
    bad = copy.deepcopy(current)
    bad['baseline']['commit'] = 'stale-ref'
    assert invoke(bad).returncode != 0
    bad = copy.deepcopy(current)
    bad['transcript'] = 'prior conversation'
    assert invoke(bad).returncode != 0
    for change in ({'fresh': False}, {'write': False}, {'inherit': True}, {'resume_id': 'old-agent'}):
        bad = copy.deepcopy(current)
        bad['capability'].update(change)
        limited = json.loads(invoke(bad).stdout)
        assert limited == {'route': 'unavailable', 'resume': '/implement', 'waiting': True}
    supported = copy.deepcopy(current)
    supported['capability'].update(fresh=False, reset=True, evidence='exposed fresh re-entry')
    assert invoke(supported).returncode == 0
    assert json.loads(Path(current['result']).read_text())['route'] == 'supported-reset-resume'
    # Interrupt after a saved brief, before a result: there is no completion.
    Path(current['result']).unlink()
    (run / 'brief.json').write_text(json.dumps(current))
    failed = subprocess.run([sys.executable, '-c', 'raise SystemExit(7)'], cwd=task, check=False)
    assert failed.returncode == 7 and not Path(current['result']).exists()
    assert (run / 'state.json').read_bytes() == original_state['state.json']
    # Resume in another new process from the durable brief, attempts intact.
    assert invoke(json.loads((run / 'brief.json').read_text())).returncode == 0
    assert json.loads((run / 'state.json').read_text())['pieces'][0]['attempts'] == 1
    assert (run / 'progress.md').read_bytes() == original_state['progress.md']
print('task handoff stubs: routing, saved lookup, interruption and retained ownership passed')
print('Limits: stubs do not establish model eviction, live leases or baseline recovery correctness')
