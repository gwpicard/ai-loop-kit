import json
import os
import subprocess
import sys
import tempfile
import unittest

from kit.tests.helpers import make_repo, settings_json
from kit.tests.test_guard import GUARD
from kit.tests.test_stop import STOP


class BuilderBaselineFallbackTest(unittest.TestCase):
    def test_valid_baseline_allows_a_new_codex_test(self):
        with tempfile.TemporaryDirectory() as folder:
            work, _ = make_repo(folder, {"tests/test_old.py": "assert True\n"})
            start = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=work, text=True).strip()
            env = {k: v for k, v in os.environ.items() if not k.startswith("LOOP_")}
            env.update(LOOP_AGENT="codex", LOOP_ROLE="builder", LOOP_START=start)
            result = subprocess.run(
                [sys.executable, GUARD], env=env, capture_output=True, text=True,
                input=json.dumps({"tool_name": "apply_patch", "cwd": work,
                                  "tool_input": "*** Begin Patch\n*** Add File: tests/test_new.py\n"
                                                "+assert True\n*** End Patch\n"}))
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_stop_blocks_when_the_builder_baseline_is_unreadable(self):
        with tempfile.TemporaryDirectory() as folder:
            work, _ = make_repo(folder, {"loop.json": settings_json(
                "## Loop\nTest command: true\nTest files command: true {files}\n")})
            env = {k: v for k, v in os.environ.items() if not k.startswith("LOOP_")}
            env.update(LOOP_ROLE="builder", LOOP_PROJECT=work, LOOP_START="f" * 40)
            result = subprocess.run(
                [sys.executable, STOP], cwd=work, env=env, capture_output=True,
                text=True, input=json.dumps({"session_id": "baseline"}))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("internal error", result.stderr)
            reply = json.loads(result.stdout)
            self.assertEqual(reply["decision"], "block")
            self.assertIn("Cannot select test files", reply["reason"])
            self.assertFalse(os.path.exists(os.path.join(work, ".loop", "passed-baseline")))
