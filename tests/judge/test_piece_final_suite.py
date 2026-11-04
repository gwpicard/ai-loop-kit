"""A tiered walk-away run checks the full suite once on the base before the final pull request."""
from __future__ import annotations

import io
import os
import sys
import unittest
from contextlib import nullcontext, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import GOOD_CODE, FakeGitHub, Project, git

# isort: split

import gate
import pr
import run
import run_cli
import walkaway
from loopkit import STATE_PREFIX, record_text

try:
    import suite
except ImportError as error:
    if error.name != "suite" and not str(error.name).startswith("suite."):
        raise
    suite = None

ROOT = Path(__file__).resolve().parents[2]
TEST = "test ! -e broken.txt"
SENTENCE = "A field run lost old behaviour when only the judge ran"


class MergedGitHub(FakeGitHub):
    """The fake GitHub, with the merge commit that the real list of pull requests carries."""

    def reopen(self, n: int) -> None:
        self.issues[n]["state"] = "OPEN"

    def merged(self, n: int, base: str, commit: str) -> None:
        self.prs[f"piece/{n}"] = {"url": f"https://example.invalid/pull/{n}", "state": "MERGED",
                                  "title": f"Piece {n}", "base": base,
                                  "mergeCommit": {"oid": commit}}


class FinalSuiteTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.gh = MergedGitHub()
        self.p.gh = self.gh
        self.env = patch.dict(os.environ)
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop("AI_LOOP_KIT_TIER", None)
        self.seen: list = []

    def settings(self, base="trip", merges="run"):
        self.p.loop_section(TEST)
        extra = (f"Base branch: {base}\n" if base else "") + (f"Base merges: {merges}\n" if merges else "")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + extra)
        git(self.p.root, "commit", "--quiet", "-am", "Settings")
        git(self.p.root, "push", "--quiet", "origin", "main")
        if base:
            git(self.p.root, "branch", base, "main")
            git(self.p.root, "push", "--quiet", "-u", "origin", base)

    def land(self, n, name, base="trip"):
        """Merge a piece branch into the base with a merge commit and record its pull request."""
        git(self.p.root, "switch", "--quiet", "-c", f"piece/{n}", base)
        (self.p.root / name).write_text("x\n")
        git(self.p.root, "add", name)
        git(self.p.root, "commit", "--quiet", "-m", f"Piece {n}")
        git(self.p.root, "switch", "--quiet", base)
        git(self.p.root, "merge", "--quiet", "--no-ff", "-m", f"Merge piece {n}", f"piece/{n}")
        git(self.p.root, "push", "--quiet", "origin", base)
        commit = git(self.p.root, "rev-parse", "HEAD").strip()
        git(self.p.root, "switch", "--quiet", "main")
        self.gh.merged(n, base, commit)

    def ready_issue(self):
        n = self.gh.create_issue("A piece", "body", [STATE_PREFIX + "ready"])
        self.gh.comment(n, record_text({"move": "ready", "risks": {"depends_on": []}}, "ready"))
        return n

    def run_pieces(self, pieces, walk_away, merge_into=None):
        def build(gh, root, n, *args):
            self.seen.append(os.environ.get("AI_LOOP_KIT_TIER"))
            if merge_into:
                self.land(n, f"piece{n}.txt", merge_into)
            gh.set_labels(n, [STATE_PREFIX + "done"], [STATE_PREFIX + "ready"])
            return f"piece {n}: pull request ready"

        out = io.StringIO()
        with patch.object(run_cli, "repo_root", return_value=self.p.root), \
                patch.object(run_cli, "GitHub", return_value=self.gh), \
                patch.object(run_cli.signal, "signal"), \
                patch.object(run_cli, "choose_mode", return_value=walk_away), \
                patch.object(walkaway, "keep_awake", return_value=nullcontext()), \
                patch.object(walkaway, "write_summary", side_effect=RuntimeError("skip")), \
                patch.object(run, "build_piece", side_effect=build), \
                redirect_stdout(out):
            status = run.main([str(n) for n in pieces])
        return status, out.getvalue()

    def test_D1_a_walk_away_run_onto_a_base_sets_the_tier_and_clears_it(self):
        self.settings()
        pieces = [self.ready_issue(), self.ready_issue()]
        status, _ = self.run_pieces(pieces, True, merge_into="trip")
        self.assertEqual(self.seen, ["narrow", "narrow"])
        self.assertNotIn("AI_LOOP_KIT_TIER", os.environ)

    def test_D1_an_attended_run_sets_nothing(self):
        self.settings()
        self.run_pieces([self.ready_issue()], False)
        self.assertEqual(self.seen, [None])

    def test_D1_a_base_of_main_sets_nothing(self):
        self.settings(base="", merges="run")
        self.run_pieces([self.ready_issue()], True)
        self.assertEqual(self.seen, [None])

    def test_D1_base_merges_person_sets_nothing(self):
        self.settings(merges="person")
        self.run_pieces([self.ready_issue()], True)
        self.assertEqual(self.seen, [None])

    def test_D2_a_green_base_passes_the_full_suite(self):
        self.settings()
        self.land(21, "one.txt")
        self.land(22, "two.txt")
        self.assertTrue(suite is not None and hasattr(suite, "final_check"),
                        "suite.final_check must exist")
        line = suite.final_check(self.gh, self.p.root, "trip", [21, 22])
        self.assertEqual(line, "Full suite passed on trip (2 pieces)")

    def test_D2_the_run_reports_the_pass_and_opens_the_final_pull_request(self):
        self.settings()
        pieces = [self.ready_issue(), self.ready_issue()]
        status, out = self.run_pieces(pieces, True, merge_into="trip")
        self.assertEqual(status, 0)
        self.assertIn("Full suite passed on trip (2 pieces)", out)
        final = self.gh.prs["trip"]
        self.assertEqual((final["base"], final["title"]), ("main", "Bring trip into main"))

    def done_issue(self):
        n = self.ready_issue()
        self.gh.set_labels(n, [STATE_PREFIX + "done"], [STATE_PREFIX + "ready"])
        return n

    def test_D7_a_broken_base_fails_the_full_suite_and_names_the_piece(self):
        self.settings()
        first, second = self.done_issue(), self.done_issue()
        self.land(first, "one.txt")
        self.land(second, "broken.txt")
        self.assertTrue(suite is not None and hasattr(suite, "final_check"),
                        "suite.final_check must exist")
        line = suite.final_check(self.gh, self.p.root, "trip", [first, second])
        self.assertEqual(line, f"piece {second}: back to shaping, broke the full suite on trip")

    def test_D7_a_failed_suite_exits_non_zero_and_still_opens_a_marked_final_pull_request(self):
        self.settings()
        pieces = [self.ready_issue(), self.ready_issue()]
        original = self.land

        def land(n, name, base="trip"):
            original(n, "broken.txt" if n == pieces[1] else name, base)

        with patch.object(self, "land", side_effect=land):
            status, out = self.run_pieces(pieces, True, merge_into="trip")
        line = f"piece {pieces[1]}: back to shaping, broke the full suite on trip"
        self.assertEqual(status, 1)
        self.assertIn(line, out)
        final = self.gh.prs["trip"]
        self.assertEqual(final["base"], "main")
        self.assertIn("(incomplete: 1 not on trip)", final["title"])
        self.assertIn("## Held in this run\n- " + line, final["body"])

    def test_D8_a_tiered_submit_names_the_narrow_check_in_the_pull_request(self):
        body = self.submitted_body(tiered=True)
        self.assertIn("- Narrow check: `printf baseline`; exit 0; commit `", body)
        self.assertIn("The full Test command runs on the base before the final pull request.", body)
        self.assertNotIn("- Regression:", body)

    def test_D8_an_untiered_submit_keeps_the_regression_line(self):
        body = self.submitted_body(tiered=False)
        self.assertIn("- Regression: `printf baseline`; exit 0; commit `", body)
        self.assertNotIn("Narrow check", body)

    def submitted_body(self, tiered):
        n = self.p.piece()
        gate.move(self.gh, self.p.root, n, "ready")
        gate.move(self.gh, self.p.root, n, "building")
        folder = run.worktree(self.p.root, n)
        (folder / "habits.py").write_text(GOOD_CODE)
        git(folder, "add", "habits.py")
        git(folder, "commit", "--quiet", "-m", "Build habits")
        with patch.dict(os.environ, {"AI_LOOP_KIT_TIER": "narrow"} if tiered else {}):
            pr.open_pull_request(self.gh, self.p.root, folder, n, self.gh.issue(n), 1, "ok")
        return self.gh.prs[f"piece/{n}"]["body"]

    def test_D6_the_design_keeps_the_lesson_and_names_the_final_suite(self):
        lines = (ROOT / "docs" / "DESIGN.md").read_text().splitlines()
        row = [line for line in lines if SENTENCE in line]
        self.assertEqual(len(row), 1, "the lesson sentence must appear once, word for word")
        self.assertIn("final suite", row[0])


if __name__ == "__main__":
    unittest.main()
