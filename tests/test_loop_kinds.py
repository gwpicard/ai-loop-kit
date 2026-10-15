"""Goal and gauntlet judges used by the ready gate and run loop."""
from __future__ import annotations

import unittest
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from helpers import KIT, SPEC
from loopkit import Refused, parse_spec
import critic
import gate
import measure
import run


class LoopKindSpecTest(unittest.TestCase):
    def test_goal_spec_and_builder_brief_keep_research_together(self):
        body = SPEC.replace("Command: `python3 judge_add.py`\nFiles:\n- judge_add.py\n",
                            "Kind: goal\nMeasure: `python3 bench.py`\nTarget: `< 200`\n")
        body += ("\n## Research\n- R1: The API supports batching "
                 "(source: https://example.test/api, read: 2026-10-15)\n")
        spec = parse_spec(body)
        self.assertEqual(spec.kind, "goal")
        self.assertEqual(spec.measure, "python3 bench.py")
        self.assertEqual(spec.research[0]["id"], "R1")
        brief = run.brief(7, body, {
            "kind": "goal", "measure": spec.measure, "target": spec.target,
            "research": list(spec.research),
        }, "")
        self.assertIn("Measure: python3 bench.py", brief)
        self.assertIn("R1: The API supports batching", brief)

    def test_goal_spec_reads_measure_and_target_without_test_files(self):
        body = SPEC.replace("Command: `python3 judge_add.py`\nFiles:\n- judge_add.py\n",
                            "Kind: goal\n"
                            "Measure: `python3 bench.py`\nTarget: `< 200`\n")
        spec = parse_spec(body)
        self.assertEqual(spec.kind, "goal")
        self.assertEqual(spec.measure, "python3 bench.py")
        self.assertEqual(spec.target, "< 200")
        self.assertEqual(spec.files, [])

    def test_gauntlet_spec_reads_capture_reference_and_criteria(self):
        body = SPEC.replace("Command: `python3 judge_add.py`\nFiles:\n- judge_add.py\n",
                            "Kind: gauntlet\n"
                            "Capture: `python3 render.py`\nReference: `docs/example.png`\n"
                            "Criteria:\n- Readable labels\n- Clear hierarchy\n")
        spec = parse_spec(body)
        self.assertEqual(spec.kind, "gauntlet")
        self.assertEqual(spec.capture, "python3 render.py")
        self.assertEqual(spec.reference, "docs/example.png")
        self.assertEqual(spec.criteria, ("Readable labels", "Clear hierarchy"))


class MeasureTest(unittest.TestCase):
    def test_target_parses_numeric_comparisons(self):
        target = measure.parse_target(">= 0.9")
        self.assertTrue(target.accepts(0.9))
        self.assertFalse(target.accepts(0.89))

    def test_measure_uses_median_of_three_last_line_values(self):
        values = iter([(0, "10\n"), (0, "30\n"), (0, "20\n")])
        result = measure.measure_values("bench", runner=lambda command: next(values))
        self.assertEqual(result, [10.0, 30.0, 20.0])
        self.assertEqual(measure.median(result), 20.0)

    def test_measure_refuses_a_non_numeric_last_line(self):
        with self.assertRaises(Refused):
            measure.parse_value("elapsed: unknown\n")


class CriticTest(unittest.TestCase):
    def test_verdict_requires_winner_and_a_reason_for_each_criterion(self):
        output = ('<verdict>{"winner":"A","reasons":{"Readable labels":'
                  '{"winner":"A","reason":"A is clearer"}}}</verdict>')
        result = critic.parse_verdict(output, ["Readable labels"])
        self.assertEqual(result["winner"], "A")
        with self.assertRaises(ValueError):
            critic.parse_verdict('<verdict>{"winner":"A","reasons":{}}</verdict>',
                                 ["Readable labels"])

    def test_three_sessions_get_a_randomised_pair_and_return_three_verdicts(self):
        prompts = []
        verdict = ('<verdict>{"winner":"A","reasons":{"Readable labels":'
                   '{"winner":"A","reason":"clear"}}}</verdict>')
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / ".loop").mkdir()
            (folder / "ours.png").write_text("ours")
            (folder / "reference.png").write_text("ref")
            results = critic.judge(folder, ["ours.png"], "reference.png",
                                   ["Readable labels"],
                                   template="{{ARTEFACT_A}} {{ARTEFACT_B}}",
                                   session=lambda prompt: prompts.append(prompt) or verdict)
        self.assertEqual(len(results), 3)
        self.assertEqual(len(prompts), 3)
        self.assertTrue(all("loop-critic-" in prompt and "/A/" in prompt and "/B/" in prompt
                            for prompt in prompts))

    def test_url_reference_is_downloaded_before_blind_order_is_assigned(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            with patch.object(critic.urllib.request, "urlopen",
                              return_value=BytesIO(b"reference bytes")):
                staged = Path(critic._stage_reference(folder, "https://example.invalid/ref.png"))
            self.assertTrue(staged.is_file())
            self.assertEqual(staged.suffix, ".png")
            self.assertEqual(staged.read_bytes(), b"reference bytes")


class PackageFilesTest(unittest.TestCase):
    def test_new_modules_and_critic_brief_are_present(self):
        self.assertTrue((KIT / "scripts" / "measure.py").is_file())
        self.assertTrue((KIT / "scripts" / "critic.py").is_file())
        self.assertTrue((KIT / "briefs" / "critic.md").is_file())


class GateHooksTest(unittest.TestCase):
    def test_goal_ready_records_main_measurements_and_requires_a_miss(self):
        spec = parse_spec(SPEC.replace(
            "Command: `python3 judge_add.py`\nFiles:\n- judge_add.py\n",
            "Kind: goal\nMeasure: `bench`\nTarget: `< 10`\n"))
        with patch.object(measure, "measure_values", return_value=[10, 12, 11]):
            _, output, record = gate._kind_ready_judge(Path.cwd(), spec)
        self.assertIn("median 11", output)
        self.assertEqual(record["main_median"], 11)
        with patch.object(measure, "measure_values", return_value=[1, 1, 1]):
            with self.assertRaises(Refused):
                gate._kind_ready_judge(Path.cwd(), spec)

    def test_goal_attempt_requires_a_fresh_hypothesis(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / ".loop").mkdir()
            ready = {"kind": "goal", "measure": "bench", "target": "< 10"}
            with patch.object(measure, "measure_values", return_value=[1, 1, 1]):
                code, output = gate._kind_attempt_judge(folder, ready)
            self.assertNotEqual(code, 0)
            self.assertIn("hypothesis", output)
            (folder / ".loop" / "hypothesis").write_text("cache repeated work")
            with patch.object(measure, "measure_values", return_value=[9, 8, 9]):
                code, output = gate._kind_attempt_judge(folder, ready)
            self.assertEqual(code, 0)
            self.assertIn("Hypothesis: cache repeated work", output)

    def test_gauntlet_attempt_passes_only_with_two_wins(self):
        ready = {"kind": "gauntlet", "capture": "render", "reference": "reference.png",
                 "criteria": ["Readable labels"], "attempt": 2}
        with patch.object(critic, "capture", return_value=["ours.png"]), \
                patch.object(critic, "judge", return_value=[
                    {"winner": "ours"}, {"winner": "ours"}, {"winner": "reference"}]):
            code, output = gate._kind_attempt_judge(Path.cwd(), ready)
        self.assertEqual(code, 0)
        self.assertIn("2/3", output)
        with patch.object(critic, "capture", return_value=["ours.png"]), \
                patch.object(critic, "judge", return_value=[
                    {"winner": "ours"}, {"winner": "reference"}, {"winner": "reference"}]):
            code, _ = gate._kind_attempt_judge(Path.cwd(), ready)
        self.assertEqual(code, 1)


class RunBriefTest(unittest.TestCase):
    def test_goal_brief_requires_hypothesis_before_code_changes(self):
        brief = run.brief(7, "## Contract\n- D1: target met", {
            "kind": "goal", "measure": "python3 bench.py", "files": [],
            "approach": "", "command": "", "contract": {}}, "")
        self.assertIn("Before changing code in every attempt", brief)
        self.assertIn(".loop/hypothesis", brief)
        self.assertIn("Measure: python3 bench.py", brief)


if __name__ == "__main__":
    unittest.main()
