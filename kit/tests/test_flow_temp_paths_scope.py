"""Exercise the temporary-path oracle with cheap child-test probes."""
import collections
import json
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
NAMES = {
    "test_happy_path",
    "test_session_crash_fails_and_cleans_up",
    "test_an_unfinished_merge_parks_and_names_the_paths",
}

# Every interpreter, including those started by run.py, installs the probes.
# Keep the oracle's selection, assertions and subprocess handling intact.
PROBES = """
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

root = Path(os.environ['FLOW_SCOPE_ROOT'])
sys.path[:0] = [str(root), str(root / 'kit/scripts')]
from kit.tests.test_flow import FlowTest
import common

def record(event):
    with open(os.environ['FLOW_SCOPE_LOG'], 'a') as stream:
        stream.write(json.dumps(event) + '\\n')

common.git = lambda *args, **kwargs: 'removed'
FlowTest.setUpClass = classmethod(lambda cls: None)
FlowTest.tearDownClass = classmethod(lambda cls: None)
FlowTest.setUp = lambda self: None
FlowTest.tearDown = lambda self: None

def probe(self):
    record({'test': self._testMethodName, 'temp': os.environ.get('TMPDIR')})
    removed = common.git(['worktree', 'remove', 'probe'])
    # The leak oracle checks that failures originate in this source file.
    exec(compile("assert removed == 'removed', 'leaked worktree'",
                 str(root / 'kit/tests/test_flow.py'), 'exec'), {'removed': removed})

for name in dir(FlowTest):
    if name.startswith('test_'):
        setattr(FlowTest, name, probe)

real_run = subprocess.run
def run(*args, **kwargs):
    if any(frame.filename.endswith('/test_flow_temp_paths.py')
           for frame in traceback.extract_stack()):
        record({'timeout': kwargs.get('timeout')})
    return real_run(*args, **kwargs)
subprocess.run = run
"""


class FlowTempPathsScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory(prefix="flow-scope-") as folder:
            folder = Path(folder)
            (folder / "sitecustomize.py").write_text(textwrap.dedent(PROBES))
            journal = folder / "calls.jsonl"
            env = dict(os.environ, FLOW_SCOPE_ROOT=str(ROOT), FLOW_SCOPE_LOG=str(journal),
                       PYTHONPATH=str(folder) + os.pathsep + os.environ.get("PYTHONPATH", ""))
            cls.result = subprocess.run(
                [sys.executable, "kit/tests/run.py", "kit/tests/test_flow_temp_paths.py"],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=50)
            cls.events = [json.loads(line) for line in journal.read_text().splitlines()]

    def assert_oracle_passed(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout + self.result.stderr)

    def test_only_the_three_path_tests_run_in_both_layouts_and_detect_leaks(self):
        self.assert_oracle_passed()
        layouts = collections.defaultdict(collections.Counter)
        for event in self.events:
            if "test" in event:
                layouts[event["temp"]][event["test"]] += 1
        self.assertEqual(len(layouts), 2, layouts)
        for temp, counts in layouts.items():
            with self.subTest(temp=temp):
                self.assertEqual(set(counts), NAMES,
                                 "The temporary-path oracle ran unrelated flow tests")
                self.assertTrue(all(count in (1, 2) for count in counts.values()), counts)
        # A normal run in both layouts, then a deliberately leaked run.
        self.assertEqual(sum(sum(counts.values()) for counts in layouts.values()), 9)
        for temp in layouts:
            self.assertFalse(Path(temp).exists(), "The oracle left its temporary folder")

    def test_every_child_has_a_timeout_below_the_module_budget(self):
        self.assert_oracle_passed()
        limits = [event["timeout"] for event in self.events if "timeout" in event]
        self.assertGreaterEqual(len(limits), 3, self.events)
        for limit in limits:
            with self.subTest(timeout=limit):
                self.assertIsInstance(limit, (int, float))
                self.assertGreater(limit, 0)
                self.assertLess(limit, 60, "A child can outlive the module's 60-second budget")


class FlowTempPathsDurationTest(unittest.TestCase):
    def test_real_oracle_command_finishes_within_sixty_seconds(self):
        with tempfile.TemporaryDirectory(prefix="flow-duration-") as folder:
            folder = Path(folder)
            # Record descendant groups before they execute, preserving the
            # process isolation used by the real flow tests.
            (folder / "sitecustomize.py").write_text(textwrap.dedent("""
                import os
                import subprocess
                original_init = subprocess.Popen.__init__
                def initialise(self, *args, **kwargs):
                    if kwargs.get('start_new_session'):
                        original_setup = kwargs.get('preexec_fn')
                        def setup():
                            fd = os.open(os.environ['FLOW_DURATION_GROUPS'],
                                         os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                            os.write(fd, ('%d\\n' % os.getpid()).encode())
                            os.close(fd)
                            if original_setup:
                                original_setup()
                        kwargs['preexec_fn'] = setup
                    return original_init(self, *args, **kwargs)
                subprocess.Popen.__init__ = initialise
            """))
            groups = folder / "groups"
            env = dict(os.environ, TMPDIR=str(folder), TMP=str(folder), TEMP=str(folder),
                       FLOW_DURATION_GROUPS=str(groups),
                       PYTHONPATH=str(folder) + os.pathsep + os.environ.get("PYTHONPATH", ""))
            start = time.monotonic()
            process = subprocess.Popen(
                [sys.executable, "kit/tests/run.py", "kit/tests/test_flow_temp_paths.py"],
                cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, start_new_session=True)
            try:
                try:
                    stdout, stderr = process.communicate(timeout=60)
                except subprocess.TimeoutExpired:
                    self.fail("The real temporary-path oracle exceeded 60 seconds")
                elapsed = time.monotonic() - start
                self.assertEqual(process.returncode, 0, (stdout + stderr)[-10000:])
                self.assertLess(elapsed, 60)
            finally:
                pending = [process.pid]
                stopped = set()
                while pending:
                    for pgid in pending:
                        try:
                            os.killpg(pgid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        stopped.add(pgid)
                    pending = ([int(line) for line in groups.read_text().splitlines()
                                if int(line) not in stopped] if groups.exists() else [])
                process.communicate()


if __name__ == "__main__":
    unittest.main()
