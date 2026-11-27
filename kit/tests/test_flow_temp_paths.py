import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
NAMES = ['test_happy_path',
         'test_session_crash_fails_and_cleans_up',
         'test_an_unfinished_merge_parks_and_names_the_paths']


def run_flow(code, env, folder):
    with tempfile.NamedTemporaryFile(dir=folder) as journal, \
            tempfile.TemporaryFile(mode="w+") as stdout, \
            tempfile.TemporaryFile(mode="w+") as stderr:
        def record_group():
            fd = os.open(journal.name, os.O_WRONLY | os.O_APPEND)
            os.write(fd, ('%d\n' % os.getpid()).encode())
            os.close(fd)

        # Record separate groups before their commands can start, including
        # commands whose parent interpreter is killed by the timeout.
        prefix = textwrap.dedent("""
            import os
            import subprocess
            original_popen = subprocess.Popen
            def popen(*args, **kwargs):
                if kwargs.get('start_new_session'):
                    original_setup = kwargs.get('preexec_fn')
                    def setup():
                        fd = os.open(%r, os.O_WRONLY | os.O_APPEND)
                        os.write(fd, ('%%d\\n' %% os.getpid()).encode())
                        os.close(fd)
                        if original_setup:
                            original_setup()
                    kwargs['preexec_fn'] = setup
                return original_popen(*args, **kwargs)
            subprocess.Popen = popen
        """) % journal.name
        try:
            result = subprocess.run(
                [sys.executable, "-c", prefix + code], cwd=ROOT, env=env,
                stdout=stdout, stderr=stderr, text=True, timeout=30,
                start_new_session=True, preexec_fn=record_group)
        finally:
            stopped = set()
            deadline = time.monotonic() + 5
            while True:
                groups = {int(line) for line in Path(journal.name).read_text().splitlines()}
                for pgid in groups - stopped:
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    stopped.add(pgid)
                processes = subprocess.run(
                    ['ps', '-A', '-o', 'pgid=,stat='], capture_output=True,
                    text=True, errors="replace", check=True, timeout=5).stdout.splitlines()
                alive = {int(parts[0]) for line in processes if (parts := line.split())
                         and not parts[1].startswith('Z')} & groups
                if not alive and {int(line) for line in Path(journal.name).read_text().splitlines()} == stopped:
                    break
                if time.monotonic() >= deadline:
                    raise AssertionError('Flow process groups did not stop: %r' % alive)
                time.sleep(0.01)
        stdout.seek(0)
        stderr.seek(0)
        result.stdout, result.stderr = stdout.read(), stderr.read()
        return result


class FlowTempPathsTest(unittest.TestCase):
    def test_flow_passes_under_build_temp_paths_and_still_detects_leaked_worktrees(self):
        code = textwrap.dedent("""
            import sys
            import unittest
            sys.path.insert(0, 'kit/scripts')
            from kit.tests.test_flow import FlowTest

            names = %r
            suite = unittest.TestSuite(FlowTest(name) for name in names)
            result = unittest.TextTestRunner().run(suite)
            failed = len(result.failures) + len(result.errors)
            print('%%d failed,' %% failed)
            sys.exit(not result.wasSuccessful())
        """) % NAMES
        with tempfile.TemporaryDirectory() as folder:
            for parts in ((".loop-worktrees", "build-temp"),
                          ("loop-build-example", ".loop-worktrees", "nested")):
                temp = Path(folder).joinpath(*parts)
                temp.mkdir(parents=True)
                env = dict(os.environ, TMPDIR=str(temp), TMP=str(temp), TEMP=str(temp))
                with self.subTest(temp=temp):
                    result = run_flow(code, env, folder)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("0 failed,", result.stdout)

            # Suppress only the final removal, leaving real git worktrees for
            # the three existing tests to detect. No source files are changed.
            code = textwrap.dedent("""
                import sys
                import unittest
                from unittest import mock
                sys.path.insert(0, 'kit/scripts')
                from kit.tests.test_flow import FlowTest
                import common

                names = %r
                real_git = common.git
                skipped = []
                def leave_worktree(args, *pos, **kwargs):
                    if args[:2] == ['worktree', 'remove']:
                        skipped.append(args[-1])
                        return ''
                    return real_git(args, *pos, **kwargs)

                suite = unittest.TestSuite(FlowTest(name) for name in names)
                with mock.patch.object(common, 'git', side_effect=leave_worktree):
                    result = unittest.TestResult()
                    suite.run(result)
                assert result.testsRun == len(names), result.testsRun
                assert not result.errors, result.errors
                assert {test._testMethodName for test, _ in result.failures} == set(names), result.failures
                assert len(skipped) == len(names), skipped
                for test, traceback in result.failures:
                    assert 'kit/tests/test_flow.py' in traceback, traceback
                    assert 'AssertionError' in traceback, traceback
            """) % NAMES
            result = run_flow(code, env, folder)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class FlowTempPathsCleanupTest(unittest.TestCase):
    def test_timeouts_stop_commands_before_removing_temporary_folders(self):
        if os.environ.get('FLOW_CLEANUP_PROBE'):
            return
        with tempfile.TemporaryDirectory(prefix='flow-cleanup-') as folder:
            folder = Path(folder)
            (folder / 'sitecustomize.py').write_text(textwrap.dedent("""
                import os
                from pathlib import Path
                import shlex
                import subprocess
                import sys
                sys.path[:0] = [%r, %r]
                from kit.tests.test_flow import FlowTest
                import common

                FlowTest.setUpClass = classmethod(lambda cls: None)
                FlowTest.tearDownClass = classmethod(lambda cls: None)
                FlowTest.setUp = lambda self: None
                FlowTest.tearDown = lambda self: None
                common.git = lambda *args, **kwargs: 'removed'

                def probe(self):
                    temp = os.environ['TMPDIR']
                    with open(os.environ['FLOW_CLEANUP_LOG'], 'a') as stream:
                        stream.write(temp + '\\n')
                    if os.environ.get('FLOW_CLEANUP_SLOW'):
                        command = 'echo $$ > %%s; sleep 3; mkdir -p %%s; touch %%s; sleep 30'
                        command %%= tuple(shlex.quote(path) for path in
                                         (os.environ['FLOW_CLEANUP_STARTED'], temp,
                                          os.environ['FLOW_CLEANUP_MARKER']))
                        common.run_shell(command, %r, 60)
                    removed = common.git(['worktree', 'remove', 'probe'])
                    exec(compile("assert removed == 'removed'", 'kit/tests/test_flow.py', 'exec'),
                         {'removed': removed})

                for name in %r:
                    setattr(FlowTest, name, probe)

                original_run = subprocess.run
                calls = 0
                def run(*args, **kwargs):
                    global calls
                    if kwargs.get('preexec_fn') and kwargs.get('start_new_session'):
                        calls += 1
                        if calls == int(os.environ['FLOW_CLEANUP_CHILD']):
                            kwargs['timeout'] = 2
                            kwargs['env'] = dict(kwargs['env'], FLOW_CLEANUP_SLOW='1')
                    return original_run(*args, **kwargs)
                subprocess.run = run
            """) % (str(ROOT), str(ROOT / 'kit/scripts'), str(ROOT), NAMES))
            for child in (1, 3):
                with self.subTest(child=child):
                    log, started, marker = (folder / ('%s-%d' % (name, child))
                                            for name in ('paths', 'started', 'survived'))
                    env = dict(os.environ, FLOW_CLEANUP_PROBE='1', FLOW_CLEANUP_CHILD=str(child),
                               FLOW_CLEANUP_LOG=str(log), FLOW_CLEANUP_STARTED=str(started),
                               FLOW_CLEANUP_MARKER=str(marker), PYTHONPATH=str(folder))
                    try:
                        result = subprocess.run(
                            [sys.executable, 'kit/tests/run.py', 'kit/tests/test_flow_temp_paths.py'],
                            cwd=ROOT, env=env, capture_output=True, text=True, timeout=15)
                        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertIn('TimeoutExpired', result.stdout + result.stderr)
                        self.assertTrue(started.exists(), 'The slow command did not start')
                        time.sleep(1.1)
                        self.assertFalse(marker.exists(), 'A descendant survived the timeout')
                        for temp in log.read_text().splitlines():
                            self.assertFalse(Path(temp).exists(), temp)
                    finally:
                        if started.exists():
                            try:
                                os.killpg(int(started.read_text()), signal.SIGKILL)
                            except ProcessLookupError:
                                pass


if __name__ == "__main__":
    unittest.main()
