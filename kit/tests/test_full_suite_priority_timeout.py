"""Judge full suites through merge and drain, with real child commands."""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sys
import time
from unittest import mock

from kit.tests.helpers import FakeGh, make_repo, run_git, write_exe
import common
import loop
import merge
import session


KIT = Path(__file__).resolve().parents[1]

# Model inherited task classes without changing the host's scheduling policy.
# Both command wrappers and changes to an existing pid are observable.
POLICY = '''#!PYTHON
import os, pathlib, sys
args = sys.argv[1:]
priority = 'background' if '-b' in args else 'normal'
if args[1:2] == ['-p']:
    pid = args[args.index('-p') + 1]
    pathlib.Path(os.environ['PRIORITY_STATE'], pid).write_text(priority)
else:
    command = args[1:]
    if command and command[0] == '--':
        command = command[1:]
    pathlib.Path(os.environ['PRIORITY_STATE'], str(os.getpid())).write_text(priority)
    os.execvp(command[0], command)
'''

PROBE = '''#!PYTHON
import json, os, pathlib, subprocess, sys
pid = os.getpid()
priority = 'normal'
while pid > 1:
    marker = pathlib.Path(os.environ['PRIORITY_STATE'], str(pid))
    if marker.exists():
        priority = marker.read_text()
        break
    pid = int(subprocess.check_output(['/bin/ps', '-o', 'ppid=', '-p', str(pid)], text=True))
is_agent = '-p' in sys.argv
role = os.environ.get('LOOP_ROLE', '') if is_agent else sys.argv[1]
with open(os.environ['PRIORITY_TRACE'], 'a') as output:
    output.write(json.dumps([role, priority]) + '\\n')
if is_agent:
    sys.stdin.read()
    print(json.dumps({'result': 'done', 'session_id': 'priority-fixture'}))
'''


class FullSuitePriorityTimeoutTest(FakeGh):
    def setUp(self):
        super().setUp()
        self.trace = Path(self.tmp, 'priority.jsonl')
        state = Path(self.tmp, 'priority-state')
        state.mkdir()
        os.environ.update(PRIORITY_STATE=str(state), PRIORITY_TRACE=str(self.trace))
        bindir = Path(self.tmp, 'bin')
        for name, script in (('taskpolicy', POLICY), ('priority-probe', PROBE), ('claude', PROBE)):
            write_exe(str(bindir / name), script)
        self.values = {
            'Test command': 'priority-probe full; priority-probe full-last',
            'Prepare command': 'priority-probe prepare',
            'Check command': 'priority-probe check',
        }
        self.work, _ = make_repo(self.tmp, {'loop.json': json.dumps(self.values), 'app.py': 'old\n'})
        run_git(['push', 'origin', 'HEAD:loop/main'], self.work)
        run_git(['checkout', '-b', 'candidate'], self.work)
        Path(self.work, 'app.py').write_text('new\n')
        run_git(['add', 'app.py'], self.work)
        run_git(['commit', '-m', 'Candidate change'], self.work)
        self.sha = common.git(['rev-parse', 'HEAD'], self.work)
        run_git(['push', 'origin', 'candidate'], self.work)
        self.scenario([
            {'match': 'issue view', 'responses': [{'stdout': '{"body":"A change","comments":[]}'}]},
            {'match': 'pr list', 'responses': [{'stdout': json.dumps([{
                'number': 7, 'state': 'MERGED', 'headRefOid': self.sha,
                'mergeCommit': {'oid': self.sha}}])}]},
            {'match': 'pr view', 'responses': [{'stdout': '{"body":""}'}]},
            *[{'match': command, 'responses': [{}]} for command in (
                'issue close', 'issue edit', 'pr edit')],
        ])

    def merge_candidate(self):
        return merge.merge(1, 'candidate', 'VERDICT: APPROVE\nHEAD: ' + self.sha, self.work)

    def from_background_loop(self, action):
        # Run the real loop dispatcher; replace only preflight and queue work.
        which = shutil.which

        def supervisor(project):
            session.run('builder', 'Fixture', self.work, 'sonnet', project, 1)
            action()
            session.run('reviewer', 'Fixture', self.work, 'sonnet', project, 1)
            return 0

        with mock.patch.object(loop.sys, 'platform', 'darwin'), \
                mock.patch.object(common, 'kit_version_refusal', return_value=None), \
                mock.patch.object(common, 'record_kit_version'), \
                mock.patch.object(loop.setup, 'tidy', return_value=([], None)), \
                mock.patch.object(loop.setup, 'missing', return_value=None), \
                mock.patch.object(loop.shutil, 'which', side_effect=lambda name: None if name == 'caffeinate' else which(name)), \
                mock.patch.object(loop, 'run', side_effect=supervisor), \
                mock.patch.object(loop, 'say') as say, \
                mock.patch.object(loop.os, 'getcwd', return_value=self.work):
            self.assertEqual(loop.main(['run']), 0, say.call_args_list)
        records = [json.loads(line) for line in self.trace.read_text().splitlines()]
        full = [priority for name, priority in records if name.startswith('full')]
        self.assertEqual(full, ['normal', 'normal'], records)
        self.assertEqual([priority for name, priority in records
                          if name in ('builder', 'reviewer')], ['background', 'background'], records)
        self.assertEqual([priority for name, priority in records
                          if name in ('prepare', 'check')], ['normal', 'normal'], records)
        self.assertEqual(len(list(Path(os.environ['PRIORITY_STATE']).iterdir())), 2,
                         'Only the two sessions may call taskpolicy')

    def test_merge_background_sessions_leave_commands_at_normal_priority(self):
        def action():
            result = self.merge_candidate()
            self.assertTrue(result.ok, result.reason)
        self.from_background_loop(action)

    def test_drain_background_sessions_leave_commands_at_normal_priority(self):
        def action():
            state = loop.new_state()
            with mock.patch.object(loop.report, 'render', return_value='Fixture report'), \
                    mock.patch.object(loop, 'hands_on', return_value=''), \
                    mock.patch.object(loop, 'decisions', return_value=''):
                loop.drain(self.work, common.read_settings(self.work), state)
            self.assertEqual(state['last'], 'drained: tests pass')
        self.from_background_loop(action)

    def timeout_refusal(self, command):
        Path(self.work, 'loop.json').write_text(json.dumps({'Test command': command}))
        began = time.monotonic()
        with mock.patch.object(merge, 'TEST_TIMEOUT', 1):
            result = self.merge_candidate()
        self.assertFalse(result.ok, result)
        self.assertEqual(result.rule, 'test-command', result.reason)
        self.assertIn('timed out', result.reason)
        self.assertLess(time.monotonic() - began, 15, 'The timed-out child must be stopped')
        self.assertFalse(any(call[:2] == ['pr', 'merge'] for call in self.calls()))
        return result.reason

    def test_timeout_refusal_names_limit_elapsed_time_and_its_control(self):
        reason = self.timeout_refusal('%s -c %s' % (
            shlex.quote(sys.executable), shlex.quote('import time; time.sleep(30)')))
        self.assertRegex(reason.lower(), r'(?:limit|timeout)[^\n]*\b1(?:\.0+)?\s*(?:s\b|seconds?\b)')
        self.assertRegex(reason.lower(), r'elapsed[^\n]*\d+(?:\.\d+)?\s*(?:s\b|seconds?\b)|\d+(?:\.\d+)?\s*(?:s\b|seconds?\b)[^\n]*elapsed')
        self.assertIn('Test minutes', reason, 'Name the setting for the merge time limit')

    def test_timeout_refusal_keeps_a_bounded_tail_of_real_output(self):
        for stream, prefix in (('stdout', 'case-a'), ('stderr', 'case-b')):
            with self.subTest(stream=stream):
                script = (
                    'import sys, time; '
                    "[print('%s-%%03d' %% n, file=sys.%s, flush=True) for n in range(200)]; "
                    'time.sleep(30)'
                ) % (prefix, stream)
                reason = self.timeout_refusal('%s -c %s' % (
                    shlex.quote(sys.executable), shlex.quote(script)))
                for number in (197, 198, 199):
                    self.assertIn('%s-%03d' % (prefix, number), reason)
                self.assertNotIn(prefix + '-000', reason)
                lines = re.findall(re.escape(prefix) + r'-\d{3}', reason)
                self.assertLessEqual(len(set(lines)), 60, 'Keep at most 60 distinct output lines')

    def test_readme_explains_which_steps_keep_background_priority_and_why(self):
        text = ' '.join((KIT / 'README.md').read_text().lower().replace('`', '').split())
        requirements = (
            (r'(?:builds|agent sessions)[^.]*background|background[^.]*(?:builds|agent sessions)',
             'Say which work keeps background priority'),
            (r'(?:full suite|full test command)[^.]*normal priority|normal priority[^.]*(?:full suite|full test command)',
             'Say that the full suite runs at normal priority'),
            (r'(?:full suite|full test command)[^.]*(?:efficiency cores|time limit|timeout|slow|short|once per merge)',
             'Explain why the full suite needs normal priority'),
        )
        for pattern, message in requirements:
            self.assertIsNotNone(re.search(pattern, text), message)
