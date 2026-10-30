"""An empty run says "Nothing is ready" at once unless a piece was moved recently."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))

import run_start


def write_events(root: Path, *events: tuple[str, int]) -> None:
    now = datetime.now(timezone.utc)
    folder = root / ".loop"
    folder.mkdir(exist_ok=True)
    lines = [json.dumps({"time": (now - timedelta(seconds=age)).isoformat(),
                         "piece": 12, "event": name}) for name, age in events]
    (folder / "events.jsonl").write_text("\n".join(lines) + "\n")


class EmptyRunNoWaitTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.addCleanup(self.folder.cleanup)

    def search(self, results):
        gh = Mock()
        gh.issues_with_label.side_effect = results
        with patch.object(run_start.time, "sleep") as sleep:
            found = run_start.ready_pieces(gh, root=self.root)
        return found, sleep, gh

    def test_D1_no_ready_event_means_one_search_and_no_sleep(self):
        found, sleep, gh = self.search([[], [{"number": 12}]])
        self.assertEqual(found, [])
        self.assertEqual(gh.issues_with_label.call_count, 1)
        sleep.assert_not_called()

    def test_D2_a_recent_ready_event_retries_until_the_piece_appears(self):
        write_events(self.root, ("ready", 30))
        found, sleep, gh = self.search([[], [{"number": 12}]])
        self.assertEqual(found, [12])
        self.assertEqual(sleep.call_count, 1)

    def test_D3_an_old_ready_event_does_not_sleep(self):
        write_events(self.root, ("ready", 20 * 60))
        found, sleep, _ = self.search([[], [{"number": 12}]])
        self.assertEqual(found, [])
        sleep.assert_not_called()

    def test_D4_a_missing_or_half_written_event_file_counts_as_no_recent_move(self):
        self.assertFalse(run_start.recent_ready(self.root))
        folder = self.root / ".loop"
        folder.mkdir()
        (folder / "events.jsonl").write_text('{"event": "ready", "time": "2026-')
        self.assertFalse(run_start.recent_ready(self.root))
        (folder / "events.jsonl").write_text('{"event": "ready"}\nnot json\n[1]\n')
        self.assertFalse(run_start.recent_ready(self.root))
        found, sleep, _ = self.search([[], [{"number": 12}]])
        self.assertEqual(found, [])
        sleep.assert_not_called()

    def test_D7_a_recent_requeue_event_retries_like_a_ready_move(self):
        write_events(self.root, ("requeue", 30))
        found, sleep, _ = self.search([[], [{"number": 12}]])
        self.assertEqual(found, [12])
        self.assertEqual(sleep.call_count, 1)

    def test_D5_no_project_folder_keeps_the_retry(self):
        gh = Mock()
        gh.issues_with_label.side_effect = [[], [], [{"number": 12}]]
        with patch.object(run_start.time, "sleep") as sleep:
            self.assertEqual(run_start.ready_pieces(gh), [12])
        self.assertEqual(sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
