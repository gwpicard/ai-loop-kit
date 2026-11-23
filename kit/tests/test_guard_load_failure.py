import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


GUARD = Path(__file__).resolve().parents[1] / "hooks" / "guard.py"


class GuardLoadFailureTest(unittest.TestCase):
    def test_missing_modules_allow_the_call_with_the_exact_warning(self):
        for missing in ("common", "merge"):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                hook = root / "hooks" / "guard.py"
                hook.parent.mkdir()
                shutil.copyfile(GUARD, hook)
                scripts = root / "scripts"
                scripts.mkdir()
                if missing == "merge":
                    (scripts / "common.py").write_text("")
                for agent in ("claude", "codex"):
                    with self.subTest(missing=missing, agent=agent):
                        env = {k: v for k, v in os.environ.items()
                               if not k.startswith("LOOP_")}
                        env.update(LOOP_AGENT=agent, LOOP_ROLE="builder")
                        result = subprocess.run(
                            [sys.executable, "-I", str(hook)],
                            input=json.dumps({
                                "tool_name": "Bash", "cwd": folder,
                                "tool_input": {"command": "printf hello"}}),
                            capture_output=True, text=True, env=env,
                            timeout=10)
                        self.assertEqual(
                            (result.returncode, result.stdout, result.stderr),
                            (0, "", "guard: cannot load, allowing the call: "
                             "No module named '%s'\n" % missing))

    def test_docstring_does_not_claim_missing_modules_refuse_all_calls(self):
        docstring = ast.get_docstring(ast.parse(GUARD.read_text()))
        self.assertIsNotNone(docstring)
        self.assertNotIn("missing guard modules refuse all calls",
                         " ".join(docstring.lower().split()))


if __name__ == "__main__":
    unittest.main()
