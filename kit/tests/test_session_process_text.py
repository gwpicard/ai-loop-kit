import contextlib
import os
from pathlib import Path
import signal
import subprocess
import time

from kit.tests.fake_codex import FakeCodexGh
from kit.tests.helpers import make_repo, write_exe
from kit.tests import test_loop_progress_records as progress
import session


PS = '''#!PYTHON
import json, os, subprocess, sys
from pathlib import Path
result = subprocess.run(['/bin/ps'] + sys.argv[1:], capture_output=True)
sys.stdout.buffer.write(result.stdout)
bad = 'command=' in ' '.join(sys.argv[1:])
if bad and os.environ.get('BAD_PS_BUILDER_ONCE'):
    path = Path(os.environ['FAKE_CLAUDE_SCENARIO'] + '.calls')
    calls = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    marker = Path(os.environ['BAD_PS_BUILDER_ONCE'])
    bad = bool(calls and calls[-1]['role'] == 'builder' and not marker.exists())
    if bad:
        marker.touch()
if bad:
    sys.stdout.buffer.write(b'0 0 unrelated-\\xff\\n')
sys.stderr.buffer.write(result.stderr)
sys.exit(result.returncode)
'''

AGENT = '''#!PYTHON
import json, os, subprocess, sys
from pathlib import Path
sys.stdin.read()
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                         start_new_session=True)
Path(os.environ['PS_CHILD']).write_text(str(child.pid))
with open(os.environ['LOOP_GROUPS'], 'a') as groups:
    groups.write('%d:%s\\n' % (child.pid, os.environ['LOOP_GROUP_TOKEN']))
print(json.dumps({'result': 'done', 'session_id': 'marked-hook'}))
'''


class SessionProcessTextTest(FakeCodexGh):
    run_factory = progress.ProgressRecordsTest.run_factory

    def setUp(self):
        super().setUp()
        write_exe(str(Path(self.tmp, 'bin/ps')), PS)

    def test_both_agents_complete_with_invalid_bytes_in_an_unrelated_command(self):
        work, _ = make_repo(self.tmp, {'loop.json': '{"Test command":"true"}'})
        self.claude({'builder': [{'reply': 'done', 'session_id': 'claude-text'}]})
        self.codex([{'reply': 'done', 'thread': 'codex-text'}])
        for agent in ('claude', 'codex'):
            with self.subTest(agent=agent):
                self.assertEqual(session.run('builder', 'Fixture', work, 'test', work, 7,
                                             agent=agent), ('done', agent + '-text'))
        self.assertEqual(len(self.claude_calls()), 1)
        self.assertEqual(len(self.codex_calls()), 1)

    def test_marked_hook_cleanup_survives_invalid_process_text(self):
        work, _ = make_repo(self.tmp, {'loop.json': '{"Test command":"true"}'})
        child_path = Path(self.tmp, 'child-pid')
        os.environ.update(PS_CHILD=str(child_path),
                          LOOP_PASS_GROUPS=str(Path(self.tmp, 'pass-groups')))
        write_exe(str(Path(self.tmp, 'bin/claude')), AGENT)

        def end_child():
            if child_path.exists():
                with contextlib.suppress(ProcessLookupError):
                    os.kill(int(child_path.read_text()), signal.SIGKILL)
        self.addCleanup(end_child)
        self.assertEqual(session.run('pass', 'Fixture', work, 'test', work, 7),
                         ('done', 'marked-hook'))
        pid = int(child_path.read_text())
        until = time.monotonic() + 5
        while True:
            state = subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'stat='],
                                   capture_output=True, text=True).stdout.strip()
            if not state or state.startswith('Z') or time.monotonic() >= until:
                break
            time.sleep(0.02)
        self.assertTrue(not state or state.startswith('Z'), 'the marked hook is still running')
        log = Path(work, '.loop/logs/7-pass-1.log').read_text()
        self.assertIn('left running, killed: ' + str(pid), log)
        self.assertNotIn('unrelated-', log)

    def test_invalid_process_text_does_not_add_a_builder_attempt(self):
        marker = Path(self.tmp, 'invalid-builder-scan')
        os.environ['BAD_PS_BUILDER_ONCE'] = str(marker)
        lines, events = self.run_factory(parked=True)
        self.assertTrue(marker.exists())
        self.assertFalse(any(e['kind'] == 'crashed' for e in events))
        progress.ProgressRecordsTest.assert_line(self, lines, 4, r'\bpark(?:ed)?\b')
