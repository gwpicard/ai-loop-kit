import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTES = ROOT / "docs/release-notes/v1.7.0.md"


class Release170Test(unittest.TestCase):
    def test_plugin_version_is_170(self):
        plugin = json.loads((ROOT / "kit/.claude-plugin/plugin.json").read_text())
        self.assertEqual(plugin["version"], "1.7.0")

    def test_changelog_links_the_release_notes(self):
        changelog = (ROOT / "CHANGELOG.md").read_text()
        release = changelog.split("## 1.6.1", 1)[0]
        self.assertIn("## 1.7.0", release)
        self.assertIn("docs/release-notes/v1.7.0.md", release)

    def test_release_notes_have_the_standard_sections(self):
        notes = NOTES.read_text()
        for heading in ("## Updating", "## What changes",
                        "## What we tested, and what is not proven yet"):
            self.assertIn(heading, notes)
        # Every action an existing user must take is given word for word.
        for line in ("claude plugin update ai-loop-kit@ai-loop-kit",
                     "/reload-plugins"):
            self.assertIn(line, notes)
        self.assertNotIn("\u2014", notes)  # no em dashes
        self.assertNotIn("PLACEHOLDER", notes)

    def test_version_pins_are_updated(self):
        for name in ("tests/test_loop.py", "tests/test_run.py", "tests/run_fixtures.py"):
            source = (ROOT / name).read_text()
            self.assertIn('"1.7.0"', source)
            self.assertNotIn('"1.6.1"', source)

    def test_tracked_files_have_no_issue_or_pull_request_numbers(self):
        pattern = "(^|[^A-Za-z0-9$}])" + chr(35) + "[0-9]{2,4}([^0-9]|$)"
        result = subprocess.run(
            ["git", "grep", "-nE", pattern],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1, result.stdout)


if __name__ == "__main__":
    unittest.main()
