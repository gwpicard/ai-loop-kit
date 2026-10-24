"""Depends on: the run builds a piece only when every piece it names is done."""
from __future__ import annotations

from helpers import SPEC, FakeGitHub, Project, git

# isort: split

import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import gate
import holds
import loop_pr
import run
import run_cli
import walkaway
from loopkit import Refused, parse_spec, record_text

RISKS = """
## Risks
Protected paths: none
New dependency: none
Shared files: none
Needs services: none
Open choices: none
"""


class DependsOnSpecTest(unittest.TestCase):
    def test_specs_without_the_line_parse_as_before(self):
        self.assertNotIn("depends_on", parse_spec(SPEC + RISKS).risks)

    def test_the_line_reads_piece_numbers(self):
        self.assertEqual(parse_spec(SPEC + RISKS + "Depends on: 12, 15\n").risks["depends_on"],
                         (12, 15))
        self.assertNotIn("depends_on", parse_spec(SPEC + RISKS + "Depends on: none\n").risks)

    def test_bad_values_are_refused(self):
        hashed = "#" + "12"
        for value, words in (("abc", "piece numbers only"), (hashed, "piece numbers only"),
                             ("0", "piece numbers only"), ("1.5", "piece numbers only"),
                             ("12 15", "piece numbers only"), ("12, 12", "names a piece twice")):
            with self.subTest(value=value):
                with self.assertRaises(Refused) as refusal:
                    parse_spec(SPEC + RISKS + f"Depends on: {value}\n")
                self.assertIn(words, refusal.exception.reason)
        with self.assertRaises(Refused) as refusal:
            parse_spec(SPEC + RISKS + "Depends on: 3\nDepends on: 4\n")
        self.assertIn("used twice", refusal.exception.reason)


class ReadyCheckTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.p.loop_section("printf baseline")

    def piece(self, depends=""):
        """A real piece: capture, judge commit, then the ready gate."""
        spec = SPEC + RISKS + (f"Depends on: {depends}\n" if depends else "")
        n = gate.capture(self.p.gh, "A piece", spec)
        git(self.p.root, "switch", "--quiet", "-c", f"piece/{n}", "main")
        from helpers import JUDGE
        (self.p.root / "judge_add.py").write_text(JUDGE)
        git(self.p.root, "add", "judge_add.py")
        git(self.p.root, "commit", "--quiet", "-m", "Judge")
        git(self.p.root, "switch", "--quiet", "main")
        return n

    def test_ready_freezes_the_dependencies(self):
        first = self.piece()
        second = self.piece(str(first))
        gate.move(self.p.gh, self.p.root, second, "ready")
        record = gate.last_record(self.p.gh.comments(second), "ready")
        self.assertEqual(record["risks"]["depends_on"], [first])

    def test_a_dependency_still_in_shaping_is_allowed(self):
        first = self.piece()
        second = self.piece(str(first))
        gate.move(self.p.gh, self.p.root, second, "ready")
        self.assertEqual(gate.state_of(self.p.gh.issue(first)), "shaping")

    def test_ready_refuses_self_missing_and_dropped_dependencies(self):
        dropped = self.piece()
        self.p.gh.set_labels(dropped, ["state:dropped"], ["state:shaping"])
        for depends, words in (("{n}", "depends on itself"), ("99", "which is missing"),
                               (str(dropped), "which is dropped")):
            with self.subTest(depends=depends):
                n = len(self.p.gh.issues) + 1
                self.piece(depends.format(n=n))
                with self.assertRaises(Refused) as refusal:
                    gate.move(self.p.gh, self.p.root, n, "ready")
                self.assertIn(words, refusal.exception.reason)

    def test_no_line_makes_no_github_call(self):
        gh = Mock()
        holds.check(gh, 1, ())
        self.assertEqual(holds.pick(gh, [3, 1], {3: [], 1: []}, {}), (3, {}))
        self.assertEqual(gh.mock_calls, [])


class WavesTest(unittest.TestCase):
    def test_waves_layer_by_dependency(self):
        wants = {1: [], 2: [1], 3: [1, 2], 4: [99], 5: [6], 6: [5]}
        self.assertEqual(holds.waves([1, 2, 3, 4, 5, 6], wants), {1: 1, 2: 2, 3: 3, 4: 1})


class RunHoldsTest(unittest.TestCase):
    """The run loop with build_piece replaced by a scripted outcome."""

    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.p.loop_section("printf baseline")
        self.gh = self.p.gh
        self.outcomes = {}

    def ready(self, depends=()):
        n = self.gh.create_issue("A piece", SPEC, ["state:ready"])
        self.gh.comment(n, record_text({"move": "ready", "risks": {"depends_on": list(depends)},
                                        "waiting_limit": "9"}, "ready"))
        return n

    def build(self, gh, root, n, *args):
        outcome = self.outcomes.get(n, "approval")
        if outcome == "refused":
            raise Refused("the judge bar changed", "shape again")
        self.gh.set_labels(n, [f"state:{outcome}"], ["state:ready"])
        return f"piece {n}: " + ("pull request ready" if outcome == "approval"
                                 else "back to shaping, the builder gave up")

    def run_all(self, pieces=None):
        out = io.StringIO()
        with patch.object(run_cli, "repo_root", return_value=self.p.root), \
                patch.object(run_cli, "GitHub", return_value=self.gh), \
                patch.object(run_cli.signal, "signal"), \
                patch.object(run, "ready_pieces", return_value=sorted(
                    n for n, i in self.gh.issues.items() if "state:ready" in i["labels"])), \
                patch.object(run, "build_piece", side_effect=self.build) as builder, \
                redirect_stdout(out):
            status = run.main([str(n) for n in pieces or []])
        return status, out.getvalue(), [c.args[2] for c in builder.call_args_list]

    def test_without_the_line_order_and_output_are_unchanged(self):
        a, b = self.ready(), self.ready()
        with patch.object(holds, "state") as state:
            status, out, built = self.run_all()
        self.assertEqual((status, built), (0, [a, b]))
        self.assertNotIn("held", out)
        state.assert_not_called()

    def test_a_dependent_waits_while_its_dependency_is_in_approval(self):
        a = self.ready()
        b = self.ready([a])
        c = self.ready()
        comments = len(self.gh.notes[b])
        status, out, built = self.run_all()
        self.assertEqual((status, built), (0, [a, c]))
        self.assertIn(f"piece {b}: held until piece {a} is done (this run: pull request ready). "
                      f"next: fix piece {a}, then run again", out)
        self.assertEqual(len(self.gh.notes[b]), comments)
        self.assertEqual(gate.state_of(self.gh.issue(b)), "ready")

    def test_a_hand_back_holds_dependents_transitively_and_others_continue(self):
        a = self.ready()
        b = self.ready([a])
        c = self.ready([b])
        d = self.ready()
        self.outcomes[a] = "shaping"
        status, out, built = self.run_all()
        self.assertEqual((status, built), (1, [a, d]))
        self.assertIn(f"piece {b}: held until piece {a} is done (this run: back to shaping", out)
        self.assertIn(f"piece {c}: held until piece {b} is done "
                      "(it waits on a piece that is also held)", out)

    def test_a_refused_dependency_holds_its_dependent(self):
        a = self.ready()
        b = self.ready([a])
        self.outcomes[a] = "refused"
        status, out, built = self.run_all()
        self.assertEqual(built, [a])
        self.assertIn(f"piece {b}: held until piece {a} is done (this run: refused", out)

    def test_a_done_dependency_does_not_block(self):
        a = self.gh.create_issue("Done", SPEC, ["state:done"])
        b = self.ready([a])
        _, out, built = self.run_all()
        self.assertEqual(built, [b])
        self.assertNotIn("held", out)

    def test_dependencies_outside_the_run_hold_with_a_next_step(self):
        approval = self.gh.create_issue("Waiting", SPEC, ["state:approval"])
        shaping = self.gh.create_issue("Shaping", SPEC, ["state:shaping"])
        one, two, three = self.ready([approval]), self.ready([shaping]), self.ready([99])
        status, out, built = self.run_all()
        self.assertEqual((status, built), (0, []))
        self.assertIn(f"piece {one}: held until piece {approval} is done (it is in approval). "
                      "next: merge its pull request, run gate.py sync, then run again", out)
        self.assertIn(f"piece {two}: held until piece {shaping} is done (it is in shaping)", out)
        self.assertIn(f"piece {three}: held until piece 99 is done (it is in missing)", out)

    def test_state_comes_from_the_issue_not_the_label_search(self):
        a = self.gh.create_issue("Was waiting", SPEC, ["state:approval"])
        b = self.ready([a])
        self.gh.set_labels(a, ["state:done"], ["state:approval"])
        with patch.object(self.gh, "issues_with_label", return_value=[]):
            _, _, built = self.run_all()
        self.assertEqual(built, [b])

    def test_explicit_pieces_follow_the_holds(self):
        a = self.ready()
        b = self.ready([a])
        _, out, built = self.run_all([b])
        self.assertEqual(built, [])
        self.assertIn(f"piece {b}: held until piece {a} is done (it is in ready). "
                      f"next: build piece {a} first", out)

    def test_an_unreadable_ready_record_holds_the_piece(self):
        a = self.ready()
        original = self.gh.comments
        with patch.object(self.gh, "comments",
                          side_effect=lambda n: (_ for _ in ()).throw(RuntimeError("down"))
                          if n == a else original(n)):
            wants = holds.wanted(self.gh, [a])
        self.assertIsNone(wants[a])
        n, held = holds.pick(self.gh, [a], wants, {})
        self.assertIsNone(n)
        self.assertIn("held until its ready record can be read", held[a])

    def test_a_cycle_leaves_both_pieces_held(self):
        n, held = holds.pick(FakeGitHub(), [1, 2], {1: [2], 2: [1]}, {})
        self.assertIsNone(n)
        self.assertIn("also held", held[1])
        self.assertIn("also held", held[2])

    def test_a_second_run_gives_the_same_answer_and_writes_nothing(self):
        a = self.gh.create_issue("Waiting", SPEC, ["state:approval"])
        b = self.ready([a])
        _, first, _ = self.run_all()
        notes = len(self.gh.notes[b])
        _, second, _ = self.run_all()
        self.assertEqual(len(self.gh.notes[b]), notes)
        line = f"piece {b}: held until piece {a} is done"
        self.assertIn(line, first)
        self.assertIn(line, second)


class ReportTest(unittest.TestCase):
    def test_held_lines_are_blockers_in_the_summary_and_the_final_pull_request(self):
        line = "piece 4: held until piece 3 is done (it is in approval). next: merge"
        now = datetime.now(timezone.utc)
        self.assertIn(f"## Blockers\n\n- {line}", walkaway.summary_text([line], now, now))
        self.assertIn(holds.MARK, loop_pr.HELD)
        self.assertIn(holds.MARK, walkaway.BLOCKERS)


if __name__ == "__main__":
    unittest.main()
