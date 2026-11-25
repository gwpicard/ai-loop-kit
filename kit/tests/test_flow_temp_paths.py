import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[2]
NAMES = ['test_happy_path',
         'test_session_crash_fails_and_cleans_up',
         'test_an_unfinished_merge_parks_and_names_the_paths']


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
                    result = subprocess.run(
                        [sys.executable, "-c", code],
                        cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
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
            result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
