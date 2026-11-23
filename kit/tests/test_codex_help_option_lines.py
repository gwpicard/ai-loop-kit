"""Help prose cannot supply a missing Codex option."""
import os
from pathlib import Path
import subprocess
import unittest

from kit.tests.fake_codex_check import FAKE, FakeCodexCheck
from kit.tests.helpers import make_repo, settings_json, write_exe

KIT = Path(__file__).resolve().parents[1]


class HelpOptionLinesTest(FakeCodexCheck):
    def test_start_refuses_a_model_flag_mentioned_only_in_prose(self):
        self.work, _ = make_repo(self.tmp, {"loop.json": settings_json(
            "## Loop\nTest command: true\nReviewer: codex gpt-6\n")})
        os.environ["FAKE_CODEX_NO_FLAG"] = "-m"
        for prose in ("Use -m to choose a model.",
                      "      --help  Show help; use -m to choose a model.",
                      "          Use -m to choose a model.",
                      "Usage: codex exec [-m MODEL] [OPTIONS]"):
            with self.subTest(prose=prose):
                fake = FAKE.replace('    sys.exit(0)\n',
                                    '    print(%r)\n    sys.exit(0)\n' % prose)
                write_exe(os.path.join(self.tmp, "bin/codex"), fake)
                result = subprocess.run([str(KIT / "bin/loop"), "run"], cwd=self.work,
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("has no -m flag", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
