"""Run the probe contract with direct and linked temporary folders."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ProbeTemporaryPathsTest(unittest.TestCase):
    def test_contract_passes_with_default_direct_and_linked_tmpdir(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as folder:
            direct = Path(folder).resolve()
            target = direct / "temporary folders"
            target.mkdir()
            linked = direct / "linked"
            linked.symlink_to(target, target_is_directory=True)
            nested = target / "nested"
            nested.mkdir()
            for temporary in (None, direct, linked, linked / "nested"):
                with self.subTest(TMPDIR=str(temporary)):
                    env = dict(os.environ)
                    env.pop("TMPDIR", None)
                    if temporary is not None:
                        env["TMPDIR"] = str(temporary)
                    result = subprocess.run(
                        [sys.executable, "kit/tests/run.py",
                         "kit/tests/test_codex_probe_contract.py"],
                        cwd=ROOT, env=env, text=True, capture_output=True,
                        timeout=120)
                    self.assertEqual(
                        result.returncode, 0,
                        "The probe contract must pass with TMPDIR=%s:\n%s%s"
                        % (temporary, result.stdout, result.stderr))


if __name__ == "__main__":
    unittest.main()
