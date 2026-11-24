import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from kit.tests.test_guard import GUARD


class CodexMissingModulesTest(unittest.TestCase):
    def test_missing_hook_modules_refuse_a_codex_call(self):
        with tempfile.TemporaryDirectory() as folder:
            hook = Path(folder) / "hooks" / "guard.py"
            hook.parent.mkdir()
            shutil.copyfile(GUARD, hook)
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith("LOOP_") and k != "PYTHONPATH"}
            env.update(LOOP_AGENT="codex", LOOP_ROLE="reviewer")
            payload = {"tool_name": "Bash", "cwd": folder,
                       "tool_input": {"command": "echo changed > README.md"}}
            result = subprocess.run(
                [sys.executable, str(hook)], input=json.dumps(payload),
                cwd=folder, env=env, capture_output=True, text=True)
            self.assertEqual(
                result.returncode, 2,
                "Codex must refuse when guard modules are missing; " + result.stderr)


if __name__ == "__main__":
    unittest.main()
