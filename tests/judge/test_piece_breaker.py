# Intent: a failing final suite on the base names the piece that broke it and hands that piece back.
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import FakeGitHub, Project, git

# isort: split

import gate
import loop_pr
from loopkit import last_record

try:
    import suite
except ImportError as error:
    if error.name != "suite":
        raise
    suite = None

BASE = "loop/1.8"
# Passes while broken.txt is absent. The failing run prints a head, a long middle and a tail.
BROKEN_ALONE = ("if [ -e broken.txt ]; then echo HEAD-MARKER; seq 1 2000; "
                "echo TAIL-MARKER; exit 1; fi; echo suite-ok")
BROKEN_TOGETHER = ("if [ -e a.txt ] && [ -e b.txt ]; then echo HEAD-MARKER; seq 1 2000; "
                   "echo TAIL-MARKER; exit 1; fi; echo suite-ok")


class ReopeningGitHub(FakeGitHub):
    def reopen(self, n: int) -> None:
        if self.issues[n]["state"] == "OPEN":
            raise RuntimeError("already open")  # be stricter than gh
        self.issues[n]["state"] = "OPEN"


class PieceBreakerTest(unittest.TestCase):
    def build(self, command: str, pieces: list[str]) -> list[int]:
        """Merge one fake piece per file name onto the base; a name of "" adds a harmless file."""
        self.p = Project()
        self.addCleanup(self.p.close)
        self.gh = self.p.gh = ReopeningGitHub()
        root = self.p.root
        (root / "AGENTS.md").write_text(
            f"# AGENTS.md\n\n## The loop\nTest command: `{command}`\n"
            f"Base branch: {BASE}\nBase merges: run\nKeep limit: 60\n")
        git(root, "add", "AGENTS.md")
        git(root, "commit", "--quiet", "-m", "Loop section")
        git(root, "push", "--quiet", "origin", "main")
        git(root, "switch", "--quiet", "-c", BASE, "main")
        numbers = []
        for index, name in enumerate(pieces, 1):
            n = self.gh.create_issue(f"Piece {index}", "body", ["state:done"])
            self.gh.issues[n]["state"] = "CLOSED"
            git(root, "switch", "--quiet", "-c", f"piece/{n}", BASE)
            (root / (name or f"harmless-{n}.txt")).write_text("x\n")
            git(root, "add", "-A")
            git(root, "commit", "--quiet", "-m", f"Piece {n}")
            git(root, "switch", "--quiet", BASE)
            git(root, "merge", "--no-ff", "--quiet", "-m", f"Merge piece {n}", f"piece/{n}")
            self.gh.prs[f"piece/{n}"] = {
                "url": f"https://example.invalid/pull/{n}", "state": "MERGED", "base": BASE,
                "title": f"Piece {n}", "mergedAt": f"2026-11-03T10:0{index}:00Z",
                "mergeCommit": {"oid": git(root, "rev-parse", "HEAD")}}
            numbers.append(n)
        git(root, "push", "--quiet", "origin", BASE)
        git(root, "switch", "--quiet", "main")
        return numbers

    def check(self, numbers: list[int]) -> tuple[str, int]:
        """Run final_check, counting the suite runs through the real full_suite."""
        calls = []
        real = suite.full_suite

        def counting(*args, **kwargs):
            calls.append(args[1])
            return real(*args, **kwargs)
        with patch.object(suite, "full_suite", side_effect=counting):
            out = suite.final_check(self.gh, self.p.root, BASE, numbers)
        return out, len(calls)

    def assert_interface(self):
        self.assertTrue(suite is not None and hasattr(suite, "final_check")
                        and hasattr(suite, "full_suite"), "suite.final_check must exist")

    def test_D3_names_the_first_piece_whose_merge_fails_within_the_run_bound(self):
        self.assert_interface()
        for count, culprit in [(1, 0), (2, 0), (2, 1), (3, 0), (3, 1), (3, 2),
                               (5, 2), (8, 0), (8, 5), (8, 7)]:
            with self.subTest(pieces=count, culprit=culprit):
                names = ["" for _ in range(count)]
                names[culprit] = "broken.txt"
                numbers = self.build(BROKEN_ALONE, names)
                out, runs = self.check(numbers)
                self.assertIn(f"piece {numbers[culprit]}: back to shaping, "
                              f"broke the full suite on {BASE}", out)
                self.assertLessEqual(runs, math.ceil(math.log2(count)) + 1)

    def test_D3_two_pieces_that_break_the_suite_only_together_blame_the_later_one(self):
        self.assert_interface()
        numbers = self.build(BROKEN_TOGETHER, ["a.txt", "", "b.txt", ""])
        out, runs = self.check(numbers)
        self.assertIn(f"piece {numbers[2]}: back to shaping, broke the full suite on {BASE}", out)
        self.assertEqual(gate.state_of(self.gh.issue(numbers[0])), "done")
        self.assertLessEqual(runs, 3)

    def test_D4_the_named_piece_goes_back_to_shaping_with_the_output_and_is_reopened(self):
        self.assert_interface()
        numbers = self.build(BROKEN_ALONE, ["", "broken.txt", ""])
        out, _ = self.check(numbers)
        bad = numbers[1]
        self.assertIn(f"piece {bad}: back to shaping, broke the full suite on {BASE}", out)
        issue = self.gh.issue(bad)
        self.assertEqual(gate.state_of(issue), "shaping")
        self.assertIn("needs-you", issue["labels"])
        self.assertEqual(issue["state"], "OPEN")
        record = last_record(self.gh.comments(bad), "suite-fail")
        self.assertIsNotNone(record)
        self.assertEqual(record["type"], "builder-failed")
        self.assertIn(f"broke the full suite on {BASE}: {BROKEN_ALONE}", record["reason"])
        text = "\n".join(self.gh.comments(bad))
        self.assertIn("TAIL-MARKER", text)
        self.assertIn("2000\nTAIL-MARKER", text)
        self.assertNotIn("HEAD-MARKER", text)  # only the last 3,000 characters
        self.assertIn(BROKEN_ALONE, text)
        for other in (numbers[0], numbers[2]):
            self.assertEqual(gate.state_of(self.gh.issue(other)), "done")
            self.assertEqual(self.gh.issue(other)["state"], "CLOSED")

    def test_D4_an_issue_that_is_still_open_is_not_reopened_again(self):
        self.assert_interface()
        numbers = self.build(BROKEN_ALONE, ["broken.txt", ""])
        self.gh.issues[numbers[0]]["state"] = "OPEN"
        out, _ = self.check(numbers)  # the strict fake raises if reopen is called on an open issue
        self.assertIn(f"piece {numbers[0]}: back to shaping", out)
        self.assertEqual(self.gh.issue(numbers[0])["state"], "OPEN")

    def test_D5_no_failing_merge_names_no_piece_and_the_final_pull_request_is_incomplete(self):
        self.assert_interface()
        numbers = self.build(BROKEN_ALONE, ["", ""])
        # The tip fails for a reason no piece merge introduced: a commit on the base
        # that is not a piece merge, so every probed merge passes.
        root = self.p.root
        git(root, "switch", "--quiet", BASE)
        (root / "broken.txt").write_text("direct\n")
        git(root, "add", "-A")
        git(root, "commit", "--quiet", "-m", "Direct commit on the base")
        git(root, "push", "--quiet", "origin", BASE)
        git(root, "switch", "--quiet", "main")
        labels = {n: list(self.gh.issue(n)["labels"]) for n in numbers}
        out, _ = self.check(numbers)
        self.assertIn(f"Full suite failed on {BASE}; no single piece found; "
                      "final pull request held until it passes", out)
        for n in numbers:
            self.assertEqual(self.gh.issue(n)["labels"], labels[n])
            self.assertEqual(self.gh.issue(n)["state"], "CLOSED")
            self.assertEqual(self.gh.comments(n), [])
        loop_pr.final_pull_request(self.gh, root, [out])
        opened = self.gh.prs[BASE]
        self.assertEqual(opened["base"], "main")
        self.assertIn("incomplete", opened["title"])
        self.assertIn("no single piece found", opened["body"])


if __name__ == "__main__":
    unittest.main()
