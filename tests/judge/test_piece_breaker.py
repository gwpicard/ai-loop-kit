"""A failing final suite on the base names the piece that broke it and hands that piece back."""
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
from helpers import FakeGitHub, Project, git

# isort: split

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

# broken.txt is the failure: the command prints its content and exits 1 while it exists.
TEST = "if [ -e broken.txt ]; then cat broken.txt; exit 1; fi"


class MergedGitHub(FakeGitHub):
    """The fake GitHub, with merge commits on pull requests and issue reopening."""

    def reopen(self, n: int) -> None:
        self.issues[n]["state"] = "OPEN"

    def merged(self, n: int, base: str, commit: str) -> None:
        self.prs[f"piece/{n}"] = {"url": f"https://example.invalid/pull/{n}", "state": "MERGED",
                                  "title": f"Piece {n}", "base": base,
                                  "mergeCommit": {"oid": commit}}


class BreakerTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.gh = MergedGitHub()
        self.p.gh = self.gh
        self.env = patch.dict(os.environ)
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop("AI_LOOP_KIT_TIER", None)
        self.p.loop_section(TEST)
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Base branch: trip\nBase merges: run\n")
        git(self.p.root, "commit", "--quiet", "-am", "Settings")
        git(self.p.root, "push", "--quiet", "origin", "main")
        git(self.p.root, "branch", "trip", "main")
        git(self.p.root, "push", "--quiet", "-u", "origin", "trip")

    def done_issue(self):
        n = self.gh.create_issue("A piece", "body", [STATE_PREFIX + "done"])
        self.gh.comment(n, record_text({"move": "ready", "risks": {"depends_on": []}}, "ready"))
        return n

    def land(self, n, name="file.txt", content="x\n"):
        git(self.p.root, "switch", "--quiet", "-c", f"piece/{n}", "trip")
        (self.p.root / name).write_text(content)
        git(self.p.root, "add", name)
        git(self.p.root, "commit", "--quiet", "-m", f"Piece {n}")
        git(self.p.root, "switch", "--quiet", "trip")
        git(self.p.root, "merge", "--quiet", "--no-ff", "-m", f"Merge piece {n}", f"piece/{n}")
        git(self.p.root, "push", "--quiet", "origin", "trip")
        commit = git(self.p.root, "rev-parse", "HEAD").strip()
        git(self.p.root, "switch", "--quiet", "main")
        self.gh.merged(n, "trip", commit)

    def land_many(self, count, culprit, content="BROKEN\n"):
        """Land `count` pieces; the one at index `culprit` adds broken.txt. Returns their numbers."""
        numbers = [self.done_issue() for _ in range(count)]
        for index, n in enumerate(numbers):
            if index == culprit:
                self.land(n, "broken.txt", content)
            else:
                self.land(n, f"piece{n}.txt")
        return numbers

    def counted_check(self, numbers):
        self.assertTrue(suite is not None and hasattr(suite, "final_check"),
                        "suite.final_check must exist")
        real = suite.full_suite
        calls = []

        def counting(*args, **kwargs):
            calls.append(args[1])
            return real(*args, **kwargs)

        with patch.object(suite, "full_suite", side_effect=counting), \
                redirect_stdout(io.StringIO()):
            line = suite.final_check(self.gh, self.p.root, "trip", numbers)
        return line, calls

    def test_D3_names_the_first_piece_whose_merge_fails_and_stays_within_the_run_budget(self):
        for count in (1, 2, 3, 5):
            for culprit in range(count):
                with self.subTest(pieces=count, culprit=culprit):
                    self.tearDown_state()
                    numbers = self.land_many(count, culprit)
                    line, calls = self.counted_check(numbers)
                    self.assertEqual(
                        line, f"piece {numbers[culprit]}: back to shaping, "
                              "broke the full suite on trip")
                    budget = {1: 1, 2: 2, 3: 3, 5: 4}[count]
                    self.assertLessEqual(len(calls), budget)

    def tearDown_state(self):
        """Reset the base to main between sub-cases."""
        self.gh.prs.clear()
        self.gh.issues.clear()
        self.gh.notes.clear()
        git(self.p.root, "push", "--quiet", "--force", "origin", "main:trip")
        git(self.p.root, "branch", "--quiet", "-f", "trip", "main")
        for line in git(self.p.root, "branch", "--list", "piece/*", "--format=%(refname:short)").split():
            git(self.p.root, "branch", "--quiet", "-D", line)

    def test_D3_two_pieces_that_break_it_only_together_blame_the_later_one(self):
        first, second = self.done_issue(), self.done_issue()
        # Neither file breaks the suite alone; the pair does (the command checks both).
        agents = self.p.root / "AGENTS.md"
        git(self.p.root, "switch", "--quiet", "trip")
        text = agents.read_text().replace(
            TEST, "if [ -e a.txt ] && [ -e b.txt ]; then echo PAIR; exit 1; fi")
        agents.write_text(text)
        git(self.p.root, "commit", "--quiet", "-am", "Pair test")
        git(self.p.root, "push", "--quiet", "origin", "trip")
        git(self.p.root, "switch", "--quiet", "main")
        self.land(first, "a.txt")
        self.land(second, "b.txt")
        line, _ = self.counted_check([first, second])
        self.assertEqual(line, f"piece {second}: back to shaping, broke the full suite on trip")

    def test_D4_the_culprit_goes_back_to_shaping_with_needs_you_reopened_and_the_output(self):
        numbers = [self.done_issue(), self.done_issue(), self.done_issue()]
        self.land(numbers[0], "one.txt")
        self.land(numbers[1], "broken.txt", "EARLY" + "x" * 3500 + "LATE-END\n")
        self.land(numbers[2], "three.txt")
        culprit = numbers[1]
        self.gh.issues[culprit]["state"] = "CLOSED"
        line, _ = self.counted_check(numbers)
        self.assertEqual(line, f"piece {culprit}: back to shaping, broke the full suite on trip")
        labels = self.gh.issue(culprit)["labels"]
        self.assertIn(STATE_PREFIX + "shaping", labels)
        self.assertNotIn(STATE_PREFIX + "done", labels)
        self.assertIn("needs-you", labels)
        self.assertEqual(self.gh.issue(culprit)["state"], "OPEN")
        text = "\n".join(self.gh.comments(culprit))
        self.assertIn("LATE-END", text)
        self.assertIn("x" * 2500, text)
        self.assertNotIn("x" * 3001, text)
        self.assertNotIn("EARLY", text)
        self.assertIn(TEST, text)
        for other in (numbers[0], numbers[2]):
            self.assertIn(STATE_PREFIX + "done", self.gh.issue(other)["labels"])

    def test_D4_the_run_exits_non_zero_and_marks_the_final_pull_request_incomplete(self):
        pieces = [self.gh.create_issue("A piece", "b", [STATE_PREFIX + "ready"]) for _ in range(2)]
        for n in pieces:
            self.gh.comment(n, record_text({"move": "ready", "risks": {"depends_on": []}}, "ready"))

        def build(gh, root, n, *args):
            self.land(n, "broken.txt" if n == pieces[0] else f"piece{n}.txt", "BROKEN\n")
            gh.set_labels(n, [STATE_PREFIX + "done"], [STATE_PREFIX + "ready"])
            return f"piece {n}: pull request ready"

        out = io.StringIO()
        with patch.object(run_cli, "repo_root", return_value=self.p.root), \
                patch.object(run_cli, "GitHub", return_value=self.gh), \
                patch.object(run_cli.signal, "signal"), \
                patch.object(run_cli, "choose_mode", return_value=True), \
                patch.object(walkaway, "keep_awake", return_value=nullcontext()), \
                patch.object(walkaway, "write_summary", side_effect=RuntimeError("skip")), \
                patch.object(run, "build_piece", side_effect=build), \
                redirect_stdout(out):
            status = run.main([str(n) for n in pieces])
        line = f"piece {pieces[0]}: back to shaping, broke the full suite on trip"
        self.assertEqual(status, 1)
        self.assertIn(line, out.getvalue())
        final = self.gh.prs["trip"]
        self.assertEqual(final["base"], "main")
        self.assertIn("incomplete", final["title"])
        self.assertIn("## Held in this run\n- " + line, final["body"])

    def test_D5_a_failing_tip_with_no_failing_merge_moves_nothing(self):
        numbers = [self.done_issue(), self.done_issue()]
        self.land(numbers[0], "one.txt")
        self.land(numbers[1], "two.txt")
        # A commit that is no piece's merge breaks the tip.
        git(self.p.root, "switch", "--quiet", "trip")
        (self.p.root / "broken.txt").write_text("BROKEN\n")
        git(self.p.root, "add", "broken.txt")
        git(self.p.root, "commit", "--quiet", "-m", "Direct commit")
        git(self.p.root, "push", "--quiet", "origin", "trip")
        git(self.p.root, "switch", "--quiet", "main")
        before = {n: self.gh.issue(n)["labels"] for n in numbers}
        comments = [len(self.gh.comments(n)) for n in numbers]
        line, _ = self.counted_check(numbers)
        self.assertEqual(line, "Full suite failed on trip; no single piece found; "
                               "final pull request held until it passes")
        self.assertEqual({n: self.gh.issue(n)["labels"] for n in numbers}, before)
        self.assertEqual([len(self.gh.comments(n)) for n in numbers], comments)

    def test_D5_the_run_still_opens_the_final_pull_request_marked_incomplete(self):
        pieces = [self.gh.create_issue("A piece", "b", [STATE_PREFIX + "ready"]) for _ in range(2)]
        for n in pieces:
            self.gh.comment(n, record_text({"move": "ready", "risks": {"depends_on": []}}, "ready"))

        def build(gh, root, n, *args):
            self.land(n, f"piece{n}.txt")
            if n == pieces[-1]:
                git(root, "switch", "--quiet", "trip")
                (root / "broken.txt").write_text("BROKEN\n")
                git(root, "add", "broken.txt")
                git(root, "commit", "--quiet", "-m", "Direct commit")
                git(root, "push", "--quiet", "origin", "trip")
                git(root, "switch", "--quiet", "main")
            gh.set_labels(n, [STATE_PREFIX + "done"], [STATE_PREFIX + "ready"])
            return f"piece {n}: pull request ready"

        out = io.StringIO()
        with patch.object(run_cli, "repo_root", return_value=self.p.root), \
                patch.object(run_cli, "GitHub", return_value=self.gh), \
                patch.object(run_cli.signal, "signal"), \
                patch.object(run_cli, "choose_mode", return_value=True), \
                patch.object(walkaway, "keep_awake", return_value=nullcontext()), \
                patch.object(walkaway, "write_summary", side_effect=RuntimeError("skip")), \
                patch.object(run, "build_piece", side_effect=build), \
                redirect_stdout(out):
            status = run.main([str(n) for n in pieces])
        self.assertEqual(status, 1)
        self.assertIn("no single piece found", out.getvalue())
        final = self.gh.prs["trip"]
        self.assertEqual(final["base"], "main")
        self.assertIn("incomplete", final["title"])
        for n in pieces:
            self.assertIn(STATE_PREFIX + "done", self.gh.issue(n)["labels"])


if __name__ == "__main__":
    unittest.main()
