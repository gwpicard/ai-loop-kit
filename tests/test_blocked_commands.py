import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCKED = ROOT / ".agents" / "guard" / "blocked-commands.md"


class BlockedCommandsTests(unittest.TestCase):
    def test_document_matches_the_thin_kit(self):
        document = BLOCKED.read_text()

        self.assertNotIn("fix loop's announced reset step", document)
        self.assertNotIn("python3 -m loop.run.pull_request merge", document)
        self.assertNotIn("shipped, mirrors this list", document)
        self.assertIn("kit/hooks/guard.py", document)
        self.assertIn("LOOP_BUILDER=1", document)
        self.assertIn("git clean", document)
        self.assertIn("find", document)


if __name__ == "__main__":
    unittest.main()
