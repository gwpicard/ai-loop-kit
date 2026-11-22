import json
import os
import subprocess
import sys
import tempfile
import unittest

from kit.tests.helpers import make_repo
from kit.tests.test_guard import GUARD


class MissingBuilderBaselineTest(unittest.TestCase):
    def test_unreadable_start_commit_does_not_unlock_existing_tests(self):
        with tempfile.TemporaryDirectory() as folder:
            work, _ = make_repo(folder, {"tests/test_app.py": "assert True\n"})
            start = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=work, text=True).strip()
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith("LOOP_")}
            env.update(LOOP_AGENT="codex", LOOP_ROLE="builder")
            payload = {
                "tool_name": "apply_patch", "cwd": work,
                "tool_input": "*** Begin Patch\n*** Update File: tests/test_app.py\n"
                              "@@\n-assert True\n+assert False\n*** End Patch\n"}
            for baseline in (start, "f" * 40):
                with self.subTest(baseline=baseline):
                    env["LOOP_START"] = baseline
                    result = subprocess.run(
                        [sys.executable, GUARD], input=json.dumps(payload),
                        env=env, capture_output=True, text=True)
                    self.assertEqual(
                        result.returncode, 2,
                        "An unreadable baseline must not unlock a tracked test; "
                        + result.stderr)


if __name__ == "__main__":
    unittest.main()
