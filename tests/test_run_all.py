import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RunAllTests(unittest.TestCase):
    def test_runner_discovers_every_test_module(self):
        with tempfile.TemporaryDirectory() as temporary:
            bin_dir = Path(temporary) / "bin"
            bin_dir.mkdir()
            capture = Path(temporary) / "arguments"
            python = bin_dir / "python3"
            python.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" > "$RUN_ALL_CAPTURE"\n'
            )
            python.chmod(0o755)
            environment = os.environ.copy()
            environment["PATH"] = f"{bin_dir}{os.pathsep}{environment['PATH']}"
            environment["RUN_ALL_CAPTURE"] = str(capture)

            result = subprocess.run(
                ["sh", str(ROOT / "tests" / "run-all.sh")],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertTrue(capture.exists(), result.stderr)
            arguments = capture.read_text().strip().split()
            self.assertEqual(
                arguments,
                ["-m", "unittest", "discover", "-q", "-p", "test_*.py"],
                result.stdout + result.stderr,
            )


if __name__ == "__main__":
    unittest.main()
