"""The dashboard keeps a piece from local events when GitHub cannot return it."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import FakeGitHub

# isort: split
import dashboard_server


class NoIssue(FakeGitHub):
    """GitHub lists the labelled issues but cannot return one piece."""

    def issue(self, n):
        raise RuntimeError("gh issue view failed: timed out")


class LostPieceTest(unittest.TestCase):
    def test_a_piece_github_cannot_return_is_shown_from_local_events(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / ".loop").mkdir()
            (root / ".loop" / "events.jsonl").write_text(
                json.dumps({"event": "claim", "piece": 7, "state": "building",
                            "time": "2026-10-30T10:00:00Z"}) + "\n")
            view = dashboard_server.snapshot(root, NoIssue())
        self.assertEqual([(p["number"], p["lane"], p["stage"]) for p in view["pieces"]],
                         [(7, "in-run", "building")])
        self.assertIn("Piece 7: could not check GitHub. Showing local events.", view["notices"])


if __name__ == "__main__":
    unittest.main()
