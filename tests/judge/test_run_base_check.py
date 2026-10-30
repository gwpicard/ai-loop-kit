"""The run checks a pending piece against the base when its blockers are done."""
from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import SPEC, Project, git

# isort: split

import base_check
import gate
import holds
import run
import run_cli
from errors import JudgeRefused
from loopkit import Refused, last_record, record_text

ROOT = Path(__file__).resolve().parents[2]
RISKS = """
## Risks
Protected paths: none
New dependency: none
Shared files: none
Needs services: none
Open choices: none
Depends on: {depends}
"""
BODY = """## Intent
Use the helper.

Out of scope:
- Anything else.

## Contract
- D1: the helper answers.

## Exit
### Tests
Command: `python3 judge_dep.py`
Files:
- judge_dep.py
"""
# Fails by assertion naming D1 until helper.txt exists on the base.
JUDGE = '''import os, sys
if os.path.exists("helper.txt"):
    print("ok test_D1_helper")
    sys.exit(0)
print("FAIL test_D1_helper AssertionError helper missing {tag}")
sys.exit(1)
'''


class RunBaseCheckTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.gh = self.p.gh
        self.p.loop_section("true")
        self.blocker = self.fake_ready()
        self.built: list[int] = []
        self.on_build = {}

    def fake_ready(self, depends=()):
        n = self.gh.create_issue("A piece", SPEC, ["state:ready"])
        self.gh.comment(n, record_text({"move": "ready", "risks": {"depends_on": list(depends)},
                                        "waiting_limit": "9"}, "ready"))
        return n

    def pending_piece(self, depends=None, tag="one"):
        body = BODY + RISKS.format(depends=self.blocker if depends is None else depends)
        n = gate.capture(self.gh, "Dependent", body)
        git(self.p.root, "switch", "--quiet", "-c", f"piece/{n}", "main")
        (self.p.root / "judge_dep.py").write_text(JUDGE.format(tag=tag))
        git(self.p.root, "add", "judge_dep.py")
        git(self.p.root, "commit", "--quiet", "-m", "Judge")
        git(self.p.root, "switch", "--quiet", "main")
        gate.move(self.gh, self.p.root, n, "ready")
        self.assertEqual(last_record(self.gh.comments(n), "ready")["base_check"], "pending")
        return n

    def land_helper(self):
        """The blocker's work reaches main."""
        (self.p.root / "helper.txt").write_text("here\n")
        git(self.p.root, "add", "helper.txt")
        git(self.p.root, "commit", "--quiet", "-m", "Helper")
        git(self.p.root, "push", "--quiet", "origin", "main")

    def ready_pieces(self):
        return sorted(n for n, i in self.gh.issues.items() if "state:ready" in i["labels"])

    def build(self, gh, root, n, *args):
        self.built.append(n)
        self.gh.set_labels(n, ["state:approval"], ["state:ready"])
        self.on_build.get(n, lambda: None)()
        return f"piece {n}: pull request ready"

    def run_all(self):
        out = io.StringIO()
        with patch.object(run_cli, "repo_root", return_value=self.p.root), \
                patch.object(run_cli, "GitHub", return_value=self.gh), \
                patch.object(run_cli.signal, "signal"), \
                patch.object(run, "ready_pieces", side_effect=lambda *a: self.ready_pieces()), \
                patch.object(run, "build_piece", side_effect=self.build), \
                redirect_stdout(out):
            status = run.main([])
        return status, out.getvalue()

    def finish_blocker(self):
        self.on_build[self.blocker] = lambda: self.gh.set_labels(
            self.blocker, ["state:done"], ["state:approval"])

    def ready_records(self, n):
        return [r for r in (json.loads(c.split("loop-gate ", 1)[1].split(" -->", 1)[0])
                            for _, c in self.gh.notes[n] if "loop-gate " in c)
                if r.get("move") == "ready"]

    def events(self):
        path = self.p.root / ".loop" / "events.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    def test_D1_a_done_blocker_runs_the_ready_check_and_builds_in_the_same_run(self):
        n = self.pending_piece()
        before = len(self.ready_records(n))
        seen = {}

        def at_build():
            record = last_record(self.gh.comments(n), "ready")
            seen.update(base_check=record.get("base_check"), blockers=record.get("blockers"))
        self.on_build[n] = at_build
        self.finish_blocker()
        status, out = self.run_all()
        self.assertEqual((status, self.built), (0, [self.blocker, n]))
        self.assertEqual(len(self.ready_records(n)), before + 1)
        self.assertEqual(seen, {"base_check": None, "blockers": None})
        self.assertIn(("base-check", n, "ready"),
                      [(e["event"], e["piece"], e["state"]) for e in self.events()])

    def test_D1_confirm_changes_no_label_and_does_nothing_for_a_checked_piece(self):
        n = self.pending_piece()
        self.gh.set_labels(self.blocker, ["state:done"], ["state:ready"])
        labels = list(self.gh.issue(n)["labels"])
        base_check.confirm(self.gh, self.p.root, n)
        self.assertEqual(self.gh.issue(n)["labels"], labels)
        count = len(self.ready_records(n))
        with patch.object(gate, "check_ready", side_effect=AssertionError("ran again")):
            base_check.confirm(self.gh, self.p.root, n)
        self.assertEqual(len(self.ready_records(n)), count)

    def test_D2_a_refused_check_hands_the_piece_back_and_the_run_continues(self):
        n = self.pending_piece()
        other = self.fake_ready()
        self.on_build[self.blocker] = lambda: (
            self.gh.set_labels(self.blocker, ["state:done"], ["state:approval"]),
            self.land_helper())  # the helper lands, so the judge passes on main
        status, out = self.run_all()
        self.assertEqual((status, self.built), (1, [self.blocker, other]))
        issue = self.gh.issue(n)
        self.assertEqual(gate.state_of(issue), "shaping")
        self.assertIn("needs-you", issue["labels"])
        record = last_record(self.gh.comments(n), "pull-back")
        self.assertEqual(record["type"], "spec-unclear")
        self.assertIn("already passes on main", record["reason"])
        self.assertIn(f"piece {n}: back to shaping, base check refused: "
                      "the judge already passes on main", out)

    def test_D3_a_changed_judge_file_hands_the_piece_back_unbuilt(self):
        n = self.pending_piece()
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "judge_dep.py").write_text(JUDGE.format(tag="two"))
        git(self.p.root, "commit", "--quiet", "-am", "Change the judge")
        git(self.p.root, "switch", "--quiet", "main")
        self.gh.set_labels(self.blocker, ["state:done"], ["state:ready"])
        status, out = self.run_all()
        self.assertEqual(self.built, [])
        self.assertEqual(gate.state_of(self.gh.issue(n)), "shaping")
        self.assertIn("needs-you", self.gh.issue(n)["labels"])
        self.assertIn(f"piece {n}: back to shaping, base check refused: ", out)
        self.assertIn("judge", last_record(self.gh.comments(n), "pull-back")["reason"])

    def test_D4_a_piece_that_depends_on_a_handed_back_piece_stays_held(self):
        n = self.pending_piece()
        after = self.fake_ready([n])
        self.gh.set_labels(self.blocker, ["state:done"], ["state:ready"])
        self.land_helper()
        status, out = self.run_all()
        self.assertEqual(self.built, [])
        self.assertIn(f"piece {after}: held until piece {n} is done", out)
        self.assertEqual(gate.state_of(self.gh.issue(after)), "ready")

    def test_D5_stays_a_blocker_in_approval_holds_the_piece_without_a_check(self):
        n = self.pending_piece()
        self.gh.set_labels(self.blocker, ["state:approval"], ["state:ready"])
        count = len(self.gh.notes[n])
        with patch.object(gate, "check_ready", side_effect=AssertionError("ran")):
            status, out = self.run_all()
        self.assertEqual(self.built, [])
        self.assertIn(f"piece {n}: {holds.MARK} piece {self.blocker} is done", out)
        self.assertEqual(len(self.gh.notes[n]), count)

    def test_D2_the_type_follows_the_refusal(self):
        cases = ((JudgeRefused("the judge is wrong", "", "bar-wrong"), "bar-wrong"),
                 (Refused("the Prepare command fails on a fresh copy of main"), "environment"),
                 (Refused("the regression check on main fails"), "environment"),
                 (Refused("the keep check already fails on main"), "environment"),
                 (Refused("the spec changed after approval"), "spec-unclear"))
        for error, expected in cases:
            with self.subTest(expected=expected, reason=error.reason):
                n = self.fake_ready()
                line = base_check.hand_back(self.gh, self.p.root, n, error)
                self.assertEqual(last_record(self.gh.comments(n), "pull-back")["type"], expected)
                self.assertEqual(line, f"piece {n}: back to shaping, base check refused: "
                                       f"{error.reason}")

    def test_D6_the_size_budget_covers_the_measured_python(self):
        import test_size_inventory
        test_size_inventory.SizeInventoryTest(
            "test_kit_python_budgets_and_install_size").debug()


if __name__ == "__main__":
    unittest.main()
