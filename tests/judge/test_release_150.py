import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Release150Test(unittest.TestCase):
    def test_plugin_version_is_150(self):
        plugin = json.loads((ROOT / "kit/.claude-plugin/plugin.json").read_text())
        self.assertEqual(plugin["version"], "1.5.0")

    def test_changelog_records_release_and_moved_previews(self):
        changelog = (ROOT / "CHANGELOG.md").read_text()
        release = changelog.split("## 1.4.0", 1)[0]
        self.assertIn("## 1.5.0", release)
        self.assertIn(".loop/", release)
        self.assertIn("1.6", release)
        self.assertIn("preview", release)

    def test_field_results_records_release_proof(self):
        results = (ROOT / "tests/field/RESULTS.md").read_text()
        rows = [line for line in results.splitlines() if line.startswith("|")]
        proof_rows = [line for line in rows if "1.5 release proof" in line]
        self.assertEqual(len(proof_rows), 1)
        self.assertIn("563e70e", proof_rows[0])
        self.assertIn("| 1 | 0 | 0 |", proof_rows[0])
        self.assertIn("22.8", proof_rows[0])

    def test_version_pins_are_updated(self):
        for name in ("tests/test_loop.py", "tests/test_run.py", "tests/run_fixtures.py"):
            source = (ROOT / name).read_text()
            self.assertIn('"1.5.0"', source)
            self.assertNotIn('"1.4.0"', source)

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
