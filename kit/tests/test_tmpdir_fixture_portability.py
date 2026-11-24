"""Keep the temporary-folder repair mechanical and exercise its command oracles."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
# Digests of the original files with only the five required substitutions.
REPAIRED = {
    "test_loop_crash_board.py":
        "3eb63edf614be41ea7f06a5816e2a066113519e094ccdc5f57946d1c3a0581ce",
    "test_loop_outage.py":
        "52f0b73409a9c5732a38bf1d8bc2d31818418c22483dc87bb9c6e9cb07bee3b4",
    "test_loop_repeated_exception.py":
        "b1c71081768d4f4942c1ba39e1c5cc511be17bfb900ac2787032474e32e06039",
    "test_runner_hung_process.py":
        "6a0de2170c8a010ca9b6c39dae3e608ae5504cf7e6d70d880fa76a762e901279",
}


class TmpdirFixturePortabilityTest(unittest.TestCase):
    def test_only_the_five_tmpdir_reads_change(self):
        for name, digest in REPAIRED.items():
            with self.subTest(module=name):
                source = (ROOT / "kit/tests" / name).read_bytes()
                self.assertEqual(
                    hashlib.sha256(source).hexdigest(), digest,
                    name + " must change only the required reads to tempfile.gettempdir()")

    def test_house_rules_pass(self):
        result = subprocess.run(
            ["sh", "tests/house-rules.sh"], cwd=ROOT,
            capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_four_modules_pass_with_and_without_tmpdir(self):
        with tempfile.TemporaryDirectory(prefix="fixture-portability-") as folder:
            for present in (True, False):
                with self.subTest(tmpdir_present=present):
                    env = dict(os.environ, TMP=folder, TEMP=folder)
                    if present:
                        env["TMPDIR"] = folder
                    else:
                        env.pop("TMPDIR", None)
                    result = subprocess.run(
                        [sys.executable, "kit/tests/run.py"]
                        + ["kit/tests/" + name for name in REPAIRED],
                        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
