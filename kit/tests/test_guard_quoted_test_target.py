import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from kit.tests.helpers import HERE, make_repo

GUARD = Path(HERE).parent / "hooks" / "guard.py"


class GuardQuotedTestTargetTest(unittest.TestCase):
    def test_quoted_redirection_cannot_overwrite_a_locked_test(self):
        with tempfile.TemporaryDirectory() as folder:
            path = "tests/test spaced.py"
            work, _ = make_repo(folder, {path: "original\n"})
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith("LOOP_")}
            env.update(LOOP_AGENT="codex", LOOP_ROLE="builder",
                       LOOP_LOCKED=path)
            for quote in ("'", '"'):
                with self.subTest(quote=quote):
                    command = "printf changed > " + quote + path + quote
                    result = subprocess.run(
                        [sys.executable, str(GUARD)],
                        input=json.dumps({"tool_name": "Bash", "cwd": work,
                                          "tool_input": {"command": command}}),
                        capture_output=True, text=True, env=env)
                    # The real shell confirms which file this spelling writes.
                    subprocess.run(["/bin/sh", "-c", command], cwd=work,
                                   check=True, capture_output=True, text=True)
                    self.assertEqual((Path(work) / path).read_text(), "changed")
                    self.assertEqual(result.returncode, 2,
                                     "The quoted target is a locked test: "
                                     + result.stderr)
                    self.assertIn("rule: test-lock", result.stderr)


if __name__ == "__main__":
    unittest.main()
