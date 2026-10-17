"""Full-bundle gauntlet critics and their gate integration."""
from __future__ import annotations

import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock
from unittest.mock import patch

from helpers import KIT, SPEC, Project, git

# isort: split
import gate
import loopkit
import measure
import test_agents
from loopkit import Refused

from extras import critics, critics_root

critic = critics()


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


class CriticGateTest(unittest.TestCase):
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


class CriticMessagesTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)

    def test_combined_ready_reports_tests_and_critics(self):
        body = SPEC.replace("## Judge", "## Exit\n### Tests") + (
            "\n### Critics\nCapture: `python3 render.py`\nReference: reference.txt\n"
            "Criteria:\n- Readable\nFiles:\n- render.py\n- reference.txt\n")
        n = self.p.piece(spec=body)
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "render.py").write_text(
            "import os\nfrom pathlib import Path\n"
            "(Path(os.environ['LOOP_CAPTURE_DIR']) / 'result.txt').write_text('main')\n")
        (self.p.root / "reference.txt").write_text("reference\n")
        git(self.p.root, "add", "render.py", "reference.txt")
        git(self.p.root, "commit", "--quiet", "-m", "Add critics check")
        git(self.p.root, "switch", "--quiet", "main")
        with patch.object(critic, "judge", return_value=[{"winner": "reference"}] * 3):
            note = gate.move(self.p.gh, self.p.root, n, "ready")
        self.assertIn("naming every spec ID", note)
        self.assertIn("Critics on main: 0/3 wins; fewer than the required 2", note)


class CriticBackendTest(unittest.TestCase):
    def test_codex_critic_parses_tagged_final_message(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            git(root, "init", "--quiet")
            (root / ".loop").mkdir()
            (root / "ours.txt").write_text("ours")
            (root / "reference.txt").write_text("reference")
            fake = test_agents.AgentSessionTest.fake_codex(self, root)
            verdict = ('<verdict>{"winner":"A","reasons":{"Readable labels":'
                       '{"winner":"A","reason":"clear"}}}</verdict>')
            with mock.patch.dict(os.environ, {"LOOP_CODEX": str(fake),
                                              "FAKE_MESSAGE": verdict}, clear=True):
                results = critic.judge(root, ["ours.txt"], "reference.txt",
                                       ["Readable labels"], agent="codex")
            self.assertEqual(len(results), 3)
            self.assertTrue(all(item["winner"] in {"ours", "reference"} for item in results))


class CriticPackageTest(unittest.TestCase):
    def test_critic_code_and_brief_belong_to_the_extra(self):
        self.assertTrue((critics_root() / "scripts/critic.py").is_file())
        self.assertTrue((critics_root() / "briefs/critic.md").is_file())
        self.assertFalse((KIT / "scripts/critic.py").exists())
        self.assertFalse((KIT / "briefs/critic.md").exists())


if __name__ == "__main__":
    unittest.main()
