import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PublicDocsTest(unittest.TestCase):
    def test_readme_states_operational_limits(self):
        readme = (ROOT / "README.md").read_text()
        for detail in (
                "pytest", "unittest", "TAP", "macOS", "Linux", "3.9", "3.12",
                "Attended runs have no sandbox", "2.1.285", "caffeinate",
                "collaborators"):
            with self.subTest(detail=detail):
                self.assertTrue(detail in readme, f"README is missing {detail!r}")

    def test_upgrade_note_names_new_settings_and_spec_sections(self):
        note = ROOT / "docs" / "UPGRADE-1.2.md"
        self.assertTrue(note.is_file(), "the 1.2 upgrade note is missing")
        content = note.read_text()
        for detail in ("Sandbox domains:", "Keep limit:", "Secret paths:",
                       "## Exit", "## Risks"):
            with self.subTest(detail=detail):
                self.assertTrue(detail in content, f"upgrade note is missing {detail!r}")


if __name__ == "__main__":
    unittest.main()
