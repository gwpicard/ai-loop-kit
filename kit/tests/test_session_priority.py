"""Only agent processes and their children inherit the session priority."""
import json
import os
from pathlib import Path
import shutil
from unittest import mock

from kit.tests.fake_codex import FakeCodexGh
from kit.tests.helpers import make_repo, write_exe
import session


POLICY = '''#!PYTHON
import json, os, sys
with open(os.environ['SESSION_PRIORITY_TRACE'], 'a') as f:
    f.write(json.dumps(sys.argv[1:3]) + '\\n')
os.environ['SESSION_BACKGROUND'] = 'yes'
os.execvp(sys.argv[2], sys.argv[2:])
'''

AGENT = '''#!PYTHON
import json, os, subprocess, sys
sys.stdin.read()
child = subprocess.check_output([sys.executable, '-c',
    "import os; print(os.environ.get('SESSION_BACKGROUND', 'no'), os.nice(0))"], text=True).strip()
with open(os.environ['SESSION_PRIORITY_TRACE'], 'a') as f:
    f.write(json.dumps([os.environ['LOOP_ROLE'], child]) + '\\n')
if 'exec' in sys.argv:
    open(sys.argv[sys.argv.index('-o') + 1], 'w').write('done')
    print(json.dumps({'type': 'thread.started', 'thread_id': 'fixture'}))
else:
    print(json.dumps({'result': 'done', 'session_id': 'fixture'}))
'''


class SessionPriorityTest(FakeCodexGh):
    def setUp(self):
        super().setUp()
        self.work, _ = make_repo(self.tmp, {'loop.json': '{"Test command":"true"}'})
        self.trace = Path(self.tmp, 'priority.jsonl')
        os.environ['SESSION_PRIORITY_TRACE'] = str(self.trace)
        for name, script in (('taskpolicy', POLICY), ('claude', AGENT), ('codex', AGENT)):
            write_exe(str(Path(self.tmp, 'bin', name)), script)

    def run_agent(self, agent, role='builder', issue=1):
        reply, _ = session.run(role, 'Fixture', self.work, 'fixture', self.work, issue, agent=agent)
        self.assertEqual(reply, 'done')

    def records(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()]

    def test_mac_raises_niceness_for_both_agents_for_all_roles_and_summary(self):
        before = os.nice(0)
        with mock.patch.object(session.sys, 'platform', 'darwin'):
            for agent in ('claude', 'codex'):
                for role, issue in [('builder', 1), ('test-writer', 1), ('reviewer', 1),
                                    ('pass', 1), ('pass', 'summary')]:
                    self.run_agent(agent, role, issue)
        records = self.records()
        self.assertEqual(len(records), 10, 'Sessions must not call taskpolicy')
        self.assertEqual([role for role, _ in records],
                         ['builder', 'test-writer', 'reviewer', 'pass', 'pass'] * 2)
        self.assertTrue(all(value == 'no %d' % min(19, before + 10)
                            for _, value in records), records)
        self.assertEqual(os.nice(0), before, 'The supervisor must keep its priority')

    def test_niceness_does_not_need_taskpolicy_on_any_system(self):
        before = os.nice(0)
        which = shutil.which
        for platform in ('darwin', 'linux'):
            with self.subTest(platform=platform), mock.patch.object(session.sys, 'platform', platform), \
                    mock.patch.object(session.shutil, 'which', side_effect=lambda name: None if name == 'taskpolicy' else which(name)):
                for agent in ('claude', 'codex'):
                    self.run_agent(agent)
                    self.assertEqual(self.records()[-1], ['builder', 'no %d' % min(19, before + 10)])
                    self.assertEqual(os.nice(0), before)
