"""Cache comparisons accept temporary folders reached through a link."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULES = ("kit/tests/test_visible_build_cache.py",
           "kit/tests/test_cache_location_contract.py")
RUNNER = """import runpy
import sys
import unittest

unittest.defaultTestLoader.testNamePatterns = [
    "*test_loop_run_passes_an_existing_visible_sibling_cache_to_commands_and_sessions",
    "*test_loop_run_overrides_an_inherited_hidden_cache_for_every_command_and_session",
]
sys.argv[0] = "kit/tests/run.py"
runpy.run_path(sys.argv[0], run_name="__main__")
"""


class CacheComparisonPortabilityTest(unittest.TestCase):
    def run_comparisons(self, unset_tmpdir):
        with tempfile.TemporaryDirectory(prefix="cache-comparison-") as folder:
            parent = Path(folder)
            target = parent / "temporary folders"
            target.mkdir()
            linked = parent / "linked temporary folders"
            linked.symlink_to(target, target_is_directory=True)
            self.assertNotEqual(str(linked), str(linked.resolve()))
            # TMP keeps the unset-TMPDIR case inside the enclosing build too.
            env = dict(os.environ, TMPDIR=str(linked), TMP=str(linked), TEMP=str(linked))
            # Select the two contracts through the runner's unittest loader.
            command = [sys.executable, "-c", RUNNER, *MODULES]
            if unset_tmpdir:
                command = ["env", "-u", "TMPDIR", *command]
            process = subprocess.Popen(command, cwd=ROOT, env=env, text=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            try:
                output, _ = process.communicate(timeout=180)
            finally:
                if process.poll() is None:
                    # The runner handles TERM by stopping its test process groups.
                    process.terminate()
                    process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, output)

    def test_cache_comparisons_pass_with_tmpdir_unset(self):
        self.run_comparisons(unset_tmpdir=True)

    def test_cache_comparisons_pass_with_tmpdir_set_to_a_linked_folder(self):
        self.run_comparisons(unset_tmpdir=False)
