"""Checks for goal and gauntlet judge helpers."""
from __future__ import annotations

import unittest
import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kit" / "scripts"))
import critic
from critic import parse_verdict, score_verdicts
from measure import median_value, parse_measurement, parse_target, target_met
import gate
from loopkit import Refused
from helpers import Project
from unittest.mock import patch


class MeasureTest(unittest.TestCase):
    def test_target_accepts_supported_operators_and_numbers(self):
        self.assertEqual(parse_target("< 200"), ("<", 200.0))
        self.assertEqual(parse_target(">= 0.9"), (">=", 0.9))
        self.assertTrue(target_met(0.95, ">= 0.9"))
        self.assertFalse(target_met(200, "< 200"))

    def test_rejects_bad_targets_and_non_numeric_last_lines(self):
        with self.assertRaises(ValueError):
            parse_target("about 200")
        with self.assertRaises(ValueError):
            parse_measurement("elapsed\nNaN")

    def test_reads_only_a_finite_number_from_the_last_nonempty_line(self):
        self.assertEqual(parse_measurement("elapsed\n\n  12.5  \n"), 12.5)

    def test_uses_the_median_of_three_values(self):
        self.assertEqual(median_value([10, 90, 20]), 20)
        with self.assertRaises(ValueError):
            median_value([10, 20])


class CriticTest(unittest.TestCase):
    def test_parses_tagged_verdict_and_checks_every_criterion(self):
        text = ('<verdict>{"criteria":[{"criterion":"clarity","winner":"A",'
                '"why":"The label is clear."}],"winner":"A"}</verdict>')
        verdict = parse_verdict(text, ["clarity"])
        self.assertEqual(verdict["winner"], "A")
        with self.assertRaises(ValueError):
            parse_verdict(text, ["clarity", "contrast"])

    def test_counts_only_a_two_of_three_majority_as_a_win(self):
        self.assertTrue(score_verdicts(["A", "B", "A"], ["A", "B", "A"]))
        self.assertFalse(score_verdicts(["A", "B", "tie"], ["A", "A", "A"]))

    def test_runs_three_fresh_sessions_and_records_the_blind_order(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            capture = folder / "ours.txt"
            reference = folder / "reference.txt"
            capture.write_text("ours\n")
            reference.write_text("reference\n")
            results = []
            for winner in ("A", "B", "B"):
                verdict = {"winner": winner, "criteria": [
                    {"criterion": "clarity", "winner": winner, "why": "clearer"}]}
                results.append(type("Result", (), {
                    "returncode": 0,
                    "stdout": "<verdict>" + json.dumps(verdict) + "</verdict>",
                    "stderr": ""})())
            with patch("critic.subprocess.run", side_effect=results) as invoke:
                passed, evidence = critic.judge(capture, str(reference), ["clarity"], folder,
                                                orders=[True, False, True])
            self.assertTrue(passed)
            self.assertEqual(invoke.call_count, 3)
            self.assertEqual([call.args[0][-2:] for call in invoke.call_args_list],
                             [["--tools", ""]] * 3)
            self.assertEqual(json.loads(evidence)["critics"][1]["ours"], "B")


class SpecTest(unittest.TestCase):
    def test_goal_spec_names_a_measure_and_a_fixed_target_without_test_files(self):
        body = ("## Intent\nSpeed up the command.\n\nOut of scope:\n- Changing its output.\n\n"
                "## Contract\n- D1: The command runs faster than 200 ms.\n\n"
                "## Judge\nKind: goal\nMeasure: `python bench.py`\nTarget: < 200\n")
        spec, fields = gate._package_spec(body)
        self.assertEqual(spec.kind, "goal")
        self.assertEqual(fields["measure"], "python bench.py")
        self.assertEqual(fields["target"], "< 200")

    def test_gauntlet_spec_needs_criteria_and_keeps_them_in_order(self):
        body = ("## Intent\nImprove the page.\n\nOut of scope:\n- Changing its content.\n\n"
                "## Contract\n- D1: The page reads more clearly.\n\n"
                "## Judge\nKind: gauntlet\nCapture: `python capture.py`\n"
                "Reference: refs/page.txt\nCriteria:\n- clarity\n- order\n")
        spec, fields = gate._package_spec(body)
        self.assertEqual(spec.kind, "gauntlet")
        self.assertEqual(fields["criteria"], ["clarity", "order"])

    def test_goal_spec_refuses_an_invalid_target_at_parse_time(self):
        body = ("## Intent\nSpeed up the command.\n\nOut of scope:\n- Changing output.\n\n"
                "## Contract\n- D1: It is faster.\n\n## Judge\nKind: goal\n"
                "Measure: `python bench.py`\nTarget: soon\n")
        with self.assertRaises(Refused):
            gate._package_spec(body)


class GoalGateTest(unittest.TestCase):
    def setUp(self):
        self.project = Project()
        self.addCleanup(self.project.close)

    def test_ready_records_main_median_and_refuses_a_met_target(self):
        body = ("## Intent\nSpeed up the command.\n\nOut of scope:\n- Changing output.\n\n"
                "## Contract\n- D1: It runs under 200 ms.\n\n## Judge\nKind: goal\n"
                "Measure: `python3 -c 'print(250)'`\nTarget: < 200\n")
        n = self.project.piece(spec=body)
        gate.move(self.project.gh, self.project.root, n, "ready")
        record = gate.last_record(self.project.gh.comments(n), "ready")
        self.assertEqual(record["kind"], "goal")
        self.assertEqual(record["main_value"], 250)

        met_body = body.replace("print(250)", "print(150)")
        n2 = self.project.piece(spec=met_body)
        with self.assertRaises(Refused) as refused:
            gate.check_ready(self.project.root, self.project.gh.issue(n2))
        self.assertIn("already meets Target", refused.exception.reason)

    def test_attempt_requires_named_hypothesis_and_records_after_value(self):
        folder = self.project.root
        ready = {"kind": "goal", "files": [], "measure": "python3 -c 'print(100)'",
                 "target": "< 200", "main_value": 250, "command": "true"}
        passed, output = gate.judge(folder, ready, attempt=1)
        self.assertFalse(passed)
        self.assertIn("Hypothesis missing", output)
        hypothesis = folder / ".loop" / "hypothesis"
        hypothesis.parent.mkdir(exist_ok=True)
        hypothesis.write_text("Attempt 1: remove the extra sort\n")
        passed, output = gate.judge(folder, ready, attempt=1)
        self.assertTrue(passed)
        self.assertIn("Goal baseline on main: 250", output)
        self.assertIn("Goal after attempt: 100", output)
        self.assertIn("remove the extra sort", output)


class GauntletGateTest(unittest.TestCase):
    def setUp(self):
        self.project = Project()
        self.addCleanup(self.project.close)

    def test_ready_runs_three_critic_contract_and_records_reference(self):
        reference = self.project.root / "reference.txt"
        reference.write_text("reference page\n")
        from helpers import git
        git(self.project.root, "add", "reference.txt")
        git(self.project.root, "commit", "--quiet", "-m", "Add reference")
        git(self.project.root, "push", "--quiet", "origin", "main")
        body = ("## Intent\nImprove the page.\n\nOut of scope:\n- Changing the product.\n\n"
                "## Contract\n- D1: The page is easier to scan.\n\n## Judge\nKind: gauntlet\n"
                "Capture: `python3 -c \"from pathlib import Path; Path('.loop/capture/page.txt').write_text('ours')\"`\n"
                "Reference: reference.txt\nCriteria:\n- clarity\n- order\n")
        n = self.project.piece(spec=body)
        with patch.object(gate.critic, "judge", return_value=(False, "main loses")) as critics:
            gate.move(self.project.gh, self.project.root, n, "ready")
        record = gate.last_record(self.project.gh.comments(n), "ready")
        self.assertEqual(record["kind"], "gauntlet")
        self.assertEqual(record["reference"], str(reference.resolve()))
        self.assertIn("main loses", record["main_critics"])
        self.assertEqual(critics.call_args.args[2], ["clarity", "order"])

    def test_attempt_runs_the_capture_and_returns_critic_verdicts(self):
        reference = self.project.root / "reference.txt"
        reference.write_text("reference page\n")
        command = ("python3 -c \"from pathlib import Path; "
                   "Path('.loop/capture/page.txt').write_text('ours')\"")
        ready = {"kind": "gauntlet", "files": [], "capture": command,
                 "reference": str(reference), "criteria": ["clarity"], "main_critics": "main loses",
                 "command": command}
        with patch.object(gate.critic, "judge", return_value=(True, "two critics prefer ours")) as judge:
            passed, output = gate.judge(self.project.root, ready, attempt=1)
        self.assertTrue(passed)
        self.assertIn("Gauntlet after attempt", output)
        self.assertIn("two critics prefer ours", output)
        self.assertTrue(judge.called)


if __name__ == "__main__":
    unittest.main()
