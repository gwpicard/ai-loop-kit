"""Exit checks used by the ready gate and run loop."""
from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import critic
import gate
import loopkit
import measure
import run
from helpers import KIT, SPEC, Project, git
from loopkit import Refused, parse_spec


class LoopKindSpecTest(unittest.TestCase):
    def test_exit_section_parses_tests_measure_and_combined_checks(self):
        body = SPEC.replace(
            "## Judge\nCommand: `python3 judge_add.py`\nFiles:\n- judge_add.py\n",
            "## Exit\n### Tests\nCommand: `python3 judge_add.py`\nFiles:\n- judge_add.py\n")
        tests = parse_spec(body)
        self.assertEqual([check["type"] for check in tests.checks], ["tests"])

        measure_body = SPEC.replace(
            "## Judge\nCommand: `python3 judge_add.py`\nFiles:\n- judge_add.py\n",
            "## Exit\n### Measure\nCommand: `python3 bench.py`\nTarget: `< 10`\n"
            "Files:\n- bench.py\n")
        measured = parse_spec(measure_body)
        self.assertEqual(measured.checks[0]["type"], "measure")
        self.assertEqual(measured.checks[0]["target"], "< 10")

        combined = parse_spec(body.replace(
            "## Exit\n### Tests", "## Exit\n### Measure\nCommand: `python3 bench.py`\n"
            "Target: `< 10`\nFiles:\n- bench.py\n\n### Tests"))
        self.assertEqual([check["type"] for check in combined.checks],
                         ["measure", "tests"])

    def test_exit_checks_require_files_and_old_kind_remains_one_check(self):
        body = SPEC.replace(
            "## Judge\nCommand: `python3 judge_add.py`\nFiles:\n- judge_add.py\n",
            "## Exit\n### Tests\nCommand: `python3 judge_add.py`\n")
        with self.assertRaisesRegex(Refused, "Files"):
            parse_spec(body)
        legacy = parse_spec(SPEC)
        self.assertEqual(len(legacy.checks), 1)
        self.assertEqual(legacy.checks[0]["type"], "tests")

    def test_fix_playbook_reaches_builder_without_changing_the_check(self):
        spec = parse_spec(SPEC + "Playbook: fix\n")
        self.assertEqual(spec.playbook, "fix")
        brief = run.brief(7, SPEC, {
            "checks": list(spec.checks), "files": spec.files, "playbook": spec.playbook,
        }, "")
        self.assertIn("reproduce the reported bug", brief)

    def test_goal_spec_and_builder_brief_keep_research_together(self):
        body = SPEC.replace("Command: `python3 judge_add.py`\nFiles:\n- judge_add.py\n",
                            "Kind: goal\nMeasure: `python3 bench.py`\nTarget: `< 200`\n"
                            "Files:\n- bench.py\n")
        body += ("\n## Research\n- R1: The API supports batching "
                 "(source: https://example.test/api, read: 2026-10-15)\n")
        spec = parse_spec(body)
        self.assertEqual(spec.kind, "goal")
        self.assertEqual(spec.measure, "python3 bench.py")
        self.assertEqual(spec.research[0]["id"], "R1")
        brief = run.brief(7, body, {
            "kind": "goal", "measure": spec.measure, "target": spec.target, "files": [],
            "checks": list(spec.checks), "research": list(spec.research),
        }, "")
        self.assertIn("Measure: python3 bench.py", brief)
        self.assertIn("R1: The API supports batching", brief)

    def test_goal_spec_reads_measure_and_target_and_exit_files(self):
        body = SPEC.replace("Command: `python3 judge_add.py`\nFiles:\n- judge_add.py\n",
                            "Kind: goal\n"
                            "Measure: `python3 bench.py`\nTarget: `< 200`\n"
                            "Files:\n- bench.py\n")
        spec = parse_spec(body)
        self.assertEqual(spec.kind, "goal")
        self.assertEqual(spec.measure, "python3 bench.py")
        self.assertEqual(spec.target, "< 200")
        self.assertEqual(spec.files, ["bench.py"])

    def test_goal_ready_refuses_missing_exit_files(self):
        project = Project()
        self.addCleanup(project.close)
        body = SPEC.replace("Command: `python3 judge_add.py`\nFiles:\n- judge_add.py\n",
                            "Kind: goal\nMeasure: `python3 bench.py`\nTarget: `< 200`\n")
        number = project.piece(spec=body)
        with self.assertRaisesRegex(Refused, "goal judges need.*Files"):
            gate.move(project.gh, project.root, number, "ready")

    def test_gauntlet_spec_reads_capture_reference_and_criteria(self):
        body = SPEC.replace("Command: `python3 judge_add.py`\nFiles:\n- judge_add.py\n",
                            "Kind: gauntlet\n"
                            "Capture: `python3 render.py`\nReference: `docs/example.png`\n"
                            "Criteria:\n- Readable labels\n- Clear hierarchy\n"
                            "Files:\n- render.py\n- docs/example.png\n")
        spec = parse_spec(body)
        self.assertEqual(spec.kind, "gauntlet")
        self.assertEqual(spec.capture, "python3 render.py")
        self.assertEqual(spec.reference, "docs/example.png")
        self.assertEqual(spec.criteria, ("Readable labels", "Clear hierarchy"))
        self.assertEqual(spec.files, ["render.py", "docs/example.png"])

    def test_editing_goal_measure_script_fails_attempt_with_bar_changed(self):
        project = Project()
        self.addCleanup(project.close)
        body = SPEC.replace(
            "Command: `python3 judge_add.py`\nFiles:\n- judge_add.py\n",
            "Kind: goal\nMeasure: `python3 bench.py`\nTarget: `< 10`\nFiles:\n- bench.py\n")
        number = project.piece(spec=body)
        git(project.root, "switch", "--quiet", f"piece/{number}")
        (project.root / "bench.py").write_text("print(100)\n")
        git(project.root, "add", "bench.py")
        git(project.root, "commit", "--quiet", "-m", "Add goal measure")
        git(project.root, "switch", "--quiet", "main")

        gate.move(project.gh, project.root, number, "ready")
        ready = gate.last_record(project.gh.comments(number), "ready")
        self.assertIn("bench.py", ready["bar_files"])

        git(project.root, "switch", "--quiet", f"piece/{number}")
        (project.root / "bench.py").write_text("print(1)\n")
        passed, reason = gate.judge(project.root, ready)
        self.assertFalse(passed)
        self.assertIn("the build changed frozen files: bench.py", reason)


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

    def test_measure_attempt_runs_with_frozen_protected_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            loop_dir = folder / ".loop"
            loop_dir.mkdir()
            (loop_dir / "hypothesis").write_text("cache repeated work")
            protected_paths = ["src/private"]
            ready = {"measure": "bench", "target": "< 10"}
            with patch.object(measure, "run_judge", return_value=(0, "9")) as run:
                code, _ = measure.judge_attempt(
                    folder, ready, protected_paths=protected_paths)
        self.assertEqual(code, 0)
        self.assertEqual(run.call_count, 3)
        self.assertTrue(all(call.kwargs["protected_paths"] == protected_paths
                            for call in run.call_args_list))

    def test_measure_refuses_a_non_numeric_last_line(self):
        with self.assertRaises(Refused):
            measure.parse_value("elapsed: unknown\n")


class CriticTest(unittest.TestCase):
    def test_successful_empty_capture_names_the_missing_sample(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            with patch.object(critic, "run_judge", return_value=(0, "")):
                with self.assertRaisesRegex(Refused, "empty sample"):
                    critic.capture(folder, "true", "main")

    def test_capture_runs_with_frozen_protected_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            protected_paths = ["src/private"]

            def run(folder, command, protected_paths=None):
                target = Path(critic.shlex.split(command)[0].split("=", 1)[1])
                (target / "sample.png").write_bytes(b"sample")
                return 0, "captured"

            with patch.object(critic, "run_judge", side_effect=run) as runner:
                files = critic.capture(folder, "render", "attempt", protected_paths)

        self.assertEqual(len(files), 1)
        self.assertEqual(runner.call_args.kwargs["protected_paths"], protected_paths)

    def test_critic_attempt_passes_frozen_paths_to_capture_and_judge(self):
        ready = {"capture": "render", "reference": "reference.png",
                 "criteria": ["Readable labels"], "attempt": 2}
        protected_paths = ["src/private"]
        wins = [{"winner": "ours"}, {"winner": "ours"}, {"winner": "reference"}]
        with patch.object(critic, "capture", return_value=["ours.png"]) as capture, \
                patch.object(critic, "judge", return_value=wins) as judge:
            code, _ = critic.judge_attempt(Path.cwd(), ready,
                                           protected_paths=protected_paths)
        self.assertEqual(code, 0)
        capture.assert_called_once_with(Path.cwd(), "render", "attempt-2",
                                        protected_paths=protected_paths)
        judge.assert_called_once_with(Path.cwd(), ["ours.png"], "reference.png",
                                      ["Readable labels"], agent=None,
                                      protected_paths=protected_paths)

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
    def test_tests_only_measure_only_and_combined_exit_checks_at_ready(self):
        test_check = {"type": "tests", "command": "judge", "files": ["judge.py"]}
        measure_check = {"type": "measure", "command": "bench", "target": "< 10",
                         "files": ["bench.py"]}
        with patch.object(loopkit, "run_judge", return_value=(1, "FAIL test_D1_feature")):
            records, _ = loopkit.exit_ready(Path.cwd(), (test_check,), {"D1": "feature"}, ())
        self.assertEqual([record["type"] for record in records], ["tests"])
        with patch.object(measure, "ready", return_value=("median 11", {"main_median": 11})):
            records, _ = loopkit.exit_ready(Path.cwd(), (measure_check,), {"D1": "feature"}, ())
        self.assertEqual(records[0]["main_median"], 11)
        failed_both = "FAIL test_D1_feature\nFAIL test_D2_target"
        with patch.object(loopkit, "run_judge", return_value=(1, failed_both)), \
                patch.object(measure, "ready", return_value=("median 11", {"main_median": 11})):
            records, _ = loopkit.exit_ready(Path.cwd(), (test_check, measure_check),
                                             {"D1": "feature", "D2": "target"}, ())
        self.assertEqual([record["type"] for record in records], ["tests", "measure"])

    def test_combined_exit_requires_tests_to_cover_every_build_contract_id(self):
        test_check = {"type": "tests", "command": "judge"}
        measure_check = {"type": "measure", "command": "bench", "target": "< 10"}
        with patch.object(loopkit, "run_judge", return_value=(1, "FAIL test_D1_feature")), \
                patch.object(measure, "ready", return_value=("median 11", {"main_median": 11})), \
                self.assertRaisesRegex(Refused, "no failing judge test names D2"):
            loopkit.exit_ready(Path.cwd(), (test_check, measure_check),
                               {"D1": "feature", "D2": "target"}, ())

    def test_tests_only_measure_only_and_combined_exit_checks_at_submit(self):
        test_check = {"type": "tests", "command": "judge"}
        measure_check = {"type": "measure", "command": "bench"}
        protected_paths = ["src/private"]
        with patch.object(loopkit, "run_judge", return_value=(0, "passed")) as run:
            code, _ = loopkit.exit_attempt(Path.cwd(), [test_check], protected_paths)
        self.assertEqual(code, 0)
        run.assert_called_once_with(Path.cwd(), "judge", protected_paths=protected_paths)
        with patch.object(measure, "judge_attempt", return_value=(0, "target met")):
            code, _ = loopkit.exit_attempt(Path.cwd(), [measure_check])
        self.assertEqual(code, 0)
        with patch.object(loopkit, "run_judge", return_value=(0, "passed")), \
                patch.object(measure, "judge_attempt", return_value=(0, "target met")):
            code, output = loopkit.exit_attempt(Path.cwd(), [test_check, measure_check])
        self.assertEqual(code, 0)
        self.assertIn("Tests exit check", output)
        self.assertIn("Measure exit check", output)

    def test_exit_attempt_passes_frozen_paths_to_measure_and_critic_adapters(self):
        measure_check = {"type": "measure", "command": "bench"}
        critic_check = {"type": "critic", "capture": "render", "reference": "reference.png",
                        "criteria": ["Readable labels"]}
        protected_paths = ["src/private"]
        with patch.object(measure, "judge_attempt", return_value=(0, "met")) as measure_attempt, \
                patch.object(critic, "judge_attempt", return_value=(0, "won")) as critic_attempt:
            code, _ = loopkit.exit_attempt(Path.cwd(), [measure_check, critic_check],
                                            protected_paths)
        self.assertEqual(code, 0)
        measure_attempt.assert_called_once_with(
            Path.cwd(), measure_check, protected_paths=protected_paths)
        critic_attempt.assert_called_once_with(
            Path.cwd(), critic_check, protected_paths=protected_paths)

    def test_goal_ready_records_main_measurements_and_requires_a_miss(self):
        spec = parse_spec(SPEC.replace(
            "Command: `python3 judge_add.py`\nFiles:\n- judge_add.py\n",
            "Kind: goal\nMeasure: `bench`\nTarget: `< 10`\nFiles:\n- bench.py\n"))
        with patch.object(measure, "measure_values", return_value=[10, 12, 11]):
            records, output = loopkit.exit_ready(Path.cwd(), spec.checks,
                                                  spec.done_when, spec.stays)
        self.assertIn("median 11", output)
        self.assertEqual(records[0]["main_median"], 11)
        with patch.object(measure, "measure_values", return_value=[1, 1, 1]):
            with self.assertRaises(Refused):
                loopkit.exit_ready(Path.cwd(), spec.checks, spec.done_when, spec.stays)

    def test_goal_attempt_requires_a_fresh_hypothesis(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / ".loop").mkdir()
            ready = [{"type": "measure", "measure": "bench", "target": "< 10"}]
            with patch.object(measure, "measure_values", return_value=[1, 1, 1]):
                code, output = loopkit.exit_attempt(folder, ready)
            self.assertNotEqual(code, 0)
            self.assertIn("hypothesis", output)
            (folder / ".loop" / "hypothesis").write_text("cache repeated work")
            with patch.object(measure, "measure_values", return_value=[9, 8, 9]):
                code, output = loopkit.exit_attempt(folder, ready)
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
            "approach": "", "command": "", "contract": {},
            "checks": [{"type": "measure", "command": "python3 bench.py", "target": "< 10"}]}, "")
        self.assertIn("Before changing code", brief)
        self.assertIn(".loop/hypothesis", brief)
        self.assertIn("Measure: python3 bench.py", brief)


if __name__ == "__main__":
    unittest.main()
