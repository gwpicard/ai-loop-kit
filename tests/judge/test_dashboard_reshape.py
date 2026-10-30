"""A handed-back piece shows its reason and a copyable shaping command on the dashboard."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import Project, git
from judge.test_dashboard_server import Base, Served, hand_back, issue

# isort: split
import dashboard_server
import gate
import run
from loopkit import record_text

KIT = Path(__file__).resolve().parents[2] / "kit"
SCRIPTS = KIT / "scripts"
PAGE = (SCRIPTS / "dashboard_page" / "app.js").read_text()


class ReshapeBase(Base):
    def handed_back(self, title="A piece", reason="the spec is unclear"):
        n = issue(self.gh, "shaping", title)
        hand_back(self.gh, n, reason)
        self.event("run-start", reason="started")
        self.event("give-back", n, "shaping", 1, "stopped")
        return n


class SnapshotTest(ReshapeBase):
    def test_D1_a_handed_back_piece_carries_type_reason_and_command(self):
        n = self.handed_back()
        hand_back(self.gh, n, "the real reason", move="reject")
        found = self.piece(n)
        self.assertEqual(found["stage"], "handed-back")
        self.assertEqual((found["handback_type"], found["handback_reason"]),
                         ("stopped", "the real reason"))
        self.assertEqual(found["reshape_command"], f'claude "/ai-loop-kit:shape {n}"')

    def test_D1_a_piece_that_is_not_handed_back_has_no_command(self):
        n = issue(self.gh, "shaping")
        found = self.piece(n)
        for key in ("handback_type", "reshape_command", "worktree_note"):
            self.assertNotIn(key, found)

    def test_D2_a_title_with_shell_characters_never_reaches_the_command(self):
        title = '$(touch /tmp/x); "rm" `id` \'q\' & |'
        n = self.handed_back(title)
        found = self.piece(n)
        self.assertEqual(found["title"], title)
        self.assertEqual(found["reshape_command"], f'claude "/ai-loop-kit:shape {n}"')
        for char in "$;`&|'":
            self.assertNotIn(char, found["reshape_command"])

    def test_D7_a_handed_back_piece_with_an_open_question_keeps_both(self):
        n = self.handed_back()
        self.gh.set_labels(n, ["needs-you"], [])
        self.gh.comment(n, record_text({"move": "give-back", "cause": "needs-answer",
                                        "reason": "Which store?", "date": "2026-10-30"}, "back"))
        found = self.piece(n)
        self.assertIs(found["question"]["answered"], False)
        self.assertEqual(found["reshape_command"], f'claude "/ai-loop-kit:shape {n}"')

    def test_D7_a_handed_back_piece_without_a_question_has_no_question(self):
        n = self.handed_back()
        found = self.piece(n)
        self.assertNotIn("question", found)
        self.assertIn("reshape_command", found)


class PageTest(Served):
    def test_D3_the_page_shows_the_reason_and_a_copy_button(self):
        self.assertIn("piece.handback_reason", PAGE)
        self.assertIn("navigator.clipboard.writeText(piece.reshape_command)", PAGE)
        self.assertIn('"Copy"', PAGE)

    def test_D3_no_endpoint_starts_a_process_or_terminal_for_shaping(self):
        self.assertEqual(dashboard_server.POSTS, ("/api/run", "/api/preferences", "/api/answer"))
        self.assertNotIn("subprocess", (SCRIPTS / "dashboard_server.py").read_text())
        n = issue(self.gh, "shaping")
        self.serve()
        status, _, _ = self.request(f"/api/shape/{n}", method="POST")
        self.assertIn(status, (403, 404, 405))

    def test_D7_the_answer_box_comes_before_the_command(self):
        card = PAGE[PAGE.index("function card"):PAGE.index("function reshapeRow")]
        self.assertLess(card.index("questionForm(piece)"), card.index("reshapeRow(piece)"))


class FolderTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.p.loop_section("true")
        self.n = self.p.piece()
        self.folder = run.worktree(self.p.root, self.n)
        self.p.gh.issues[self.n]["labels"] = ["state:building"]

    def hand_back(self):
        gate.move(self.p.gh, self.p.root, self.n, "shaping", reason="the spec is unclear",
                  reason_type="spec-unclear")
        self.p.root.joinpath(".loop").mkdir(exist_ok=True)
        (self.p.root / ".loop" / "events.jsonl").write_text(
            '{"event": "give-back", "piece": %d, "state": "shaping"}\n' % self.n)

    def found(self):
        view = dashboard_server.snapshot(self.p.root, self.p.gh)
        return next(p for p in view["pieces"] if p["number"] == self.n)

    def test_D4_a_kept_folder_gives_a_note_with_the_folder_and_the_next_step(self):
        (self.folder / "unsaved.txt").write_text("keep this\n")
        self.hand_back()
        note = self.found()["worktree_note"]
        self.assertIn(str(self.folder), note)
        self.assertIn("next:", note)
        self.assertIn("gate.py doctor", note)

    def test_D4_a_released_folder_gives_no_note(self):
        self.hand_back()
        self.assertFalse(self.folder.exists())
        self.assertIsNone(self.found()["worktree_note"])

    def test_D6_a_released_clean_folder_lets_the_checkout_switch_to_the_piece_branch(self):
        self.hand_back()
        self.assertFalse(self.folder.exists())
        git(self.p.root, "switch", "--quiet", f"piece/{self.n}")


if __name__ == "__main__":
    unittest.main()
