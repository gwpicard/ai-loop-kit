"""Measure commands started inside real session launches on macOS."""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import unittest

from kit.tests.helpers import FakeGh, make_repo, write_exe
import common
import session


KIT = Path(__file__).resolve().parents[1]

# Replace the external agent only. Session launch, command dispatch, hooks and
# the operating system's priority readings remain real.
AGENT = '''#!PYTHON
import json, os, pathlib, subprocess, sys
sys.stdin.read()
folder = pathlib.Path(os.environ['SESSION_PRIORITY_FOLDER'])
priority = subprocess.check_output(
    ['/bin/ps', '-o', 'pri=,nice=', '-p', str(os.getpid())], text=True)
(folder / 'agent.json').write_text(json.dumps([int(n) for n in priority.split()]))
result = subprocess.run(json.loads(os.environ['SESSION_PRIORITY_COMMAND']),
                        input=json.dumps({'session_id': 'priority-fixture'}),
                        capture_output=True, text=True, timeout=30)
(folder / 'command.json').write_text(json.dumps({
    'code': result.returncode, 'out': result.stdout, 'err': result.stderr}))
if 'exec' in sys.argv:
    pathlib.Path(sys.argv[sys.argv.index('-o') + 1]).write_text('done')
    print(json.dumps({'type': 'thread.started', 'thread_id': 'priority-fixture'}))
else:
    print(json.dumps({'result': 'done', 'session_id': 'priority-fixture'}))
'''


@unittest.skipUnless(sys.platform == 'darwin', 'Requires macOS process priorities')
class SessionCommandPriorityTest(FakeGh):
    def setUp(self):
        super().setUp()
        # Each fixture owns its check records, rather than reusing the enclosing
        # build's settings, timeout or successful-check cache.
        for name in list(os.environ):
            if name.startswith('LOOP_') and name != 'LOOP_TEST_EXE_CACHE':
                os.environ.pop(name)
        os.environ['LOOP_TMPDIR'] = self.tmp
        for agent in ('claude', 'codex'):
            write_exe(str(Path(self.tmp, 'bin', agent)), AGENT)

    def priority(self):
        return tuple(int(n) for n in subprocess.check_output(
            ['/bin/ps', '-o', 'pri=,nice=', '-p', str(os.getpid())], text=True).split())

    def launch(self, action, agent, targeted=False):
        folder = Path(self.tmp, '%s-%s-%s' % (action, agent, targeted))
        folder.mkdir()
        os.environ['SESSION_PRIORITY_FOLDER'] = str(folder)

        def probe(name):
            command = '/bin/ps -o pri= -p $$ > ' + shlex.quote(str(folder / name))
            return ': before; ' + command + '; : after' if targeted else command

        values = {'Test command': probe('test'), 'Check command': probe('check')}
        if targeted:
            values['Test files command'] = probe('test') + '; : {files}'
        work, _ = make_repo(str(folder), {
            'loop.json': json.dumps(values),
            'tests/test_one.py': '# Fixture selected by the session.\n',
            'tests/test spaced.py': '# Fixture with a quoted path.\n',
        })
        command = ([str(KIT / 'bin/loop'), 'check'] if action == 'check' else
                   [sys.executable, str(KIT / 'hooks/stop.py')])
        os.environ['SESSION_PRIORITY_COMMAND'] = json.dumps(command)
        before = self.priority()
        reply, _ = session.run(
            'builder', 'Run the configured command.', work, 'fixture', work, 1,
            agent=agent, start=common.git(['rev-parse', 'HEAD'], work),
            locked=('tests/test spaced.py', 'tests/test_one.py'))
        self.assertEqual(reply, 'done')
        result = json.loads((folder / 'command.json').read_text())
        self.assertEqual(result['code'], 0, result)
        self.assertEqual(result['err'], '', result)
        if action == 'check':
            self.assertIn('passed:', result['out'], result)
        else:
            self.assertEqual(result['out'].strip(), '', result)
        self.assertEqual(self.priority()[1], before[1],
                         'The supervisor must keep its niceness')
        return folder, before

    def assert_commands_outside_background(self, action):
        # The loop's supervisor runs normally. An enclosing background agent
        # would impose its policy even after session.run stops using taskpolicy.
        if self.priority()[0] <= 4:
            self.skipTest('Requires a supervisor outside the inherited background class')
        for agent in ('claude', 'codex'):
            for targeted in (False, True):
                with self.subTest(agent=agent, targeted=targeted):
                    folder, _ = self.launch(action, agent, targeted)
                    for name in ('test', 'check'):
                        with self.subTest(command=name):
                            self.assertTrue((folder / name).exists(),
                                            'The %s command must actually run' % name)
                            self.assertNotEqual(int((folder / name).read_text()), 4,
                                                '%s started %s in the background class'
                                                % (action, name))

    def test_loop_check_commands_run_outside_background_class(self):
        self.assert_commands_outside_background('check')

    def test_stop_hook_commands_run_outside_background_class(self):
        self.assert_commands_outside_background('stop')

    def test_agent_keeps_lower_priority_than_supervisor(self):
        for agent in ('claude', 'codex'):
            with self.subTest(agent=agent):
                folder, (supervisor_priority, supervisor_nice) = self.launch('check', agent)
                agent_priority, agent_nice = json.loads((folder / 'agent.json').read_text())
                self.assertTrue(
                    (agent_priority == 4 and supervisor_priority > 4)
                    or agent_nice > supervisor_nice,
                    'The agent must remain below the supervisor: agent=%s, supervisor=%s'
                    % ((agent_priority, agent_nice), (supervisor_priority, supervisor_nice)))


class SessionPriorityDocumentationTest(unittest.TestCase):
    def test_readme_explains_session_and_command_priorities_in_one_place(self):
        paragraphs = [' '.join(p.lower().replace('`', '').split())
                      for p in (KIT / 'README.md').read_text().split('\n\n')]
        matches = [p for p in paragraphs if 'agent sessions' in p and 'macos' in p
                   and 'loop check' in p and 'stop hook' in p]
        self.assertEqual(len(matches), 1,
                         'Explain agent, loop check and Stop hook priorities in one place')
        paragraph = matches[0]
        self.assertRegex(paragraph, r'niceness|nice\b')
        self.assertIn('background', paragraph)
        for step in ('supervisor', 'prepare', 'smoke', 'merge', 'drain'):
            self.assertIn(step, paragraph)
        sentences = re.split(r'(?<=[.!?])\s+', paragraph)
        self.assertTrue(any('test' in s and 'check' in s
                            and 'loop check' in s and 'stop hook' in s
                            and re.search(r'normal priority|outside[^.]*background', s)
                            for s in sentences),
                        'One sentence must state Test and Check priorities for both entry points')


if __name__ == '__main__':
    unittest.main()
