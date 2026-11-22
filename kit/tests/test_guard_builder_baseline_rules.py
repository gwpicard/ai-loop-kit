import json
import os
import subprocess
import sys
import tempfile
import unittest

from kit.tests.helpers import make_repo
from kit.tests.test_guard import GUARD


class BuilderBaselineRulesTest(unittest.TestCase):
    def check_test_lock(self, agent, tools):
        with tempfile.TemporaryDirectory() as folder:
            work, _ = make_repo(folder, {
                "tests/test_app.py": "assert True\n",
                "tests/nested/test_other.py": "assert True\n"})
            start = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=work, text=True).strip()
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith("LOOP_")}
            env.update(LOOP_AGENT=agent, LOOP_ROLE="builder")
            for baseline in (start, "f" * 40):
                env["LOOP_START"] = baseline
                for path in ("tests/test_app.py", os.path.join(work, "tests/nested/test_other.py")):
                    for tool in tools:
                        with self.subTest(baseline=baseline, path=path, tool=tool):
                            if tool == "apply_patch":
                                inp = {"command": "*** Begin Patch\n*** Update File: %s\n"
                                       "@@\n-assert True\n+assert False\n*** End Patch\n" % path}
                            elif tool == "Write":
                                inp = {"file_path": path, "content": "assert False\n"}
                            else:
                                inp = {"file_path": path, "old_string": "True",
                                       "new_string": "False"}
                            result = subprocess.run(
                                [sys.executable, GUARD], env=env, capture_output=True,
                                text=True, input=json.dumps({"tool_name": tool,
                                                             "tool_input": inp, "cwd": work}))
                            self.assertEqual(result.returncode, 2, result.stderr)
                            self.assertIn("rule: test-lock\n", result.stderr)

    def test_codex_refuses_with_the_test_lock_rule(self):
        self.check_test_lock("codex", ("apply_patch",))

    def test_claude_write_and_edit_keep_existing_tests_locked(self):
        self.check_test_lock("claude", ("Write", "Edit"))


if __name__ == "__main__":
    unittest.main()
