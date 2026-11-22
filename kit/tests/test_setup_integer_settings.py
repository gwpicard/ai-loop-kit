import json
from pathlib import Path
import subprocess
import sys
import unittest

from kit.tests.helpers import FakeGh, make_repo
import common
import setup


class IntegerSettingsMigrationTest(FakeGh):
    def test_setup_writes_whole_numbers_as_integers_and_preserves_fractions(self):
        for reverse, newline in ((False, "\n"), (True, "\r\n")):
            with self.subTest(reverse=reverse, newline=repr(newline)):
                parent = Path(self.tmp, "reversed" if reverse else "forward")
                parent.mkdir()
                lines = ["Test command: true", "Parallel: 2", "Idle hours: 1.5",
                         "Max rounds: 3", "Session minutes: 12.5"]
                if reverse:
                    lines.reverse()
                agents = newline.join(["# Project", "## Loop", *lines, ""])
                work, _ = make_repo(str(parent), {"AGENTS.md": agents})
                config = Path(work, "loop.json")
                config.write_text('{"Test command": "true", "Parallel": 2.0}', encoding="utf-8")
                self.assertEqual(common.read_settings(work)["Parallel"], 2)
                config.unlink()
                self.scenario([
                    {"match": match, "responses": [{"code": 0, "stdout": stdout}]}
                    for match, stdout in (("label list", "[]"), ("label create", ""),
                                          ("issue list", "[]"),
                                          ("issue create", "https://example/issues/7"),
                                          ("issue pin", ""))])
                result = subprocess.run([sys.executable, setup.__file__, work],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                text = config.read_text(encoding="utf-8")
                values = json.loads(text)
                self.assertEqual(values["Idle hours"], 1.5)
                self.assertEqual(values["Session minutes"], 12.5)
                self.assertEqual(common.read_settings(work)["Parallel"], 2)
                self.assertRegex(text, r'"Parallel":\s*2\s*[,}]')
                for key in ("Parallel", "Max rounds"):
                    self.assertIs(type(values[key]), int, key + " must be written as an integer")


if __name__ == "__main__":
    unittest.main()
