"""Regressions from the gauntlet field round."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import critic
import gate
import run
from helpers import SPEC, Project, git
from loopkit import Refused


def verdict(*criteria: str) -> str:
    reasons = {item: {"winner": "A", "reason": "A has clearer labels"}
               for item in criteria}
    return "<verdict>" + json.dumps({"winner": "A", "reasons": reasons}) + "</verdict>"


class CriticFailureTest(unittest.TestCase):
    def test_terminal_punctuation_does_not_change_the_criterion(self):
        for expected, returned in (("Readable labels.", "Readable labels"),
                                   ("Readable labels", "Readable labels."),
                                   ("Readable labels!", "Readable labels?")):
            with self.subTest(expected=expected, returned=returned):
                try:
                    result = critic.parse_verdict(verdict(returned), [expected])
                except ValueError as error:
                    self.fail(str(error))
                self.assertEqual(result["winner"], "A")
                self.assertEqual(list(result["reasons"]), [expected])

    def test_missing_and_extra_criterion_keys_are_named(self):
        with self.assertRaises(ValueError) as caught:
            critic.parse_verdict(verdict("Clear hierarchy", "Colour"),
                                 ["Readable labels.", "Clear hierarchy"])
        self.assertIn("missing: ['Readable labels.']", str(caught.exception))
        self.assertIn("extra: ['Colour']", str(caught.exception))

    def test_punctuation_cannot_hide_a_duplicate_criterion(self):
        with self.assertRaisesRegex(ValueError, "ambiguous criterion keys"):
            critic.parse_verdict(verdict("Readable labels", "Readable labels."),
                                 ["Readable labels"])

    def test_invalid_attempt_keeps_the_whole_critic_answer(self):
        for response in ("explanation before malformed <verdict>{bad}</verdict>",
                         "no tagged verdict at all", verdict("Colour")):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                (folder / "ours.txt").write_text("ours")
                (folder / "reference.txt").write_text("reference")
                process = Mock(returncode=0)
                process.communicate.return_value = (response.encode(), None)
                ready = {"capture": "render", "reference": "reference.txt",
                         "criteria": ["Readable labels."], "attempt": 2}
                with patch.object(critic, "capture", return_value=["ours.txt"]), \
                        patch.object(critic.agents, "start_session", return_value=process):
                    code, output = critic.judge_attempt(folder, ready)
                self.assertEqual(code, 1)
                self.assertIn(response, output)
                self.assertIn("critic returned an invalid verdict", output)

    def test_invalid_answer_survives_release_of_the_build_folder(self):
        project = Project()
        self.addCleanup(project.close)
        body = SPEC.replace(
            "Command: `python3 judge_add.py`\nFiles:\n- judge_add.py\n",
            "Kind: gauntlet\nCapture: `python3 render.py`\nReference: `reference.txt`\n"
            "Criteria:\n- Readable labels.\nFiles:\n- render.py\n- reference.txt\n")
        number = project.piece(spec=body)
        git(project.root, "switch", "--quiet", f"piece/{number}")
        (project.root / "render.py").write_text(
            "import os\nfrom pathlib import Path\n"
            "(Path(os.environ['LOOP_CAPTURE_DIR']) / 'sample.txt').write_text('ours')\n")
        (project.root / "reference.txt").write_text("reference")
        git(project.root, "add", "render.py", "reference.txt")
        git(project.root, "commit", "--quiet", "-m", "Capture artefact")
        git(project.root, "switch", "--quiet", "main")
        with patch.object(critic, "judge", return_value=[{"winner": "reference"}] * 3):
            gate.move(project.gh, project.root, number, "ready")

        response = "START OF CRITIC ANSWER\n" + "detail\n" * 800 + verdict("Colour")
        process = Mock(returncode=0)
        process.communicate.return_value = (response.encode(), None)
        with patch.object(run, "build_once", return_value=""), \
                patch.object(critic.agents, "start_session", return_value=process):
            result = run.build_piece(project.gh, project.root, number, 1)

        self.assertIn("back to shaping", result)
        self.assertFalse(project.folder(number).exists())
        logfile = project.root / ".loop" / "logs" / f"piece-{number}-attempt-1.log"
        self.assertIn(response, logfile.read_text())
        self.assertIn("missing: ['Readable labels.']", logfile.read_text())
        self.assertIn("extra: ['Colour']", logfile.read_text())


class PieceCheckoutTest(unittest.TestCase):
    def test_checked_out_piece_is_reported_before_claim_or_build(self):
        for location in ("another worktree", "the current checkout"):
            with self.subTest(location=location):
                project = Project()
                self.addCleanup(project.close)
                number = project.piece()
                gate.move(project.gh, project.root, number, "ready")
                if location == "another worktree":
                    folder = Path(project.tmp.name) / "another checkout"
                    git(project.root, "worktree", "add", "--quiet", str(folder),
                        f"piece/{number}")
                else:
                    folder = project.root
                    git(folder, "switch", "--quiet", f"piece/{number}")
                before = git(folder, "rev-parse", "HEAD")
                with patch.object(run, "build_once") as builder, \
                        self.assertRaises(Refused) as caught:
                    run.build_piece(project.gh, project.root, number, 1)
                self.assertIn(f"piece/{number} is already checked out", str(caught.exception))
                self.assertIn(str(folder), str(caught.exception))
                self.assertEqual(gate.state_of(project.gh.issue(number)), "ready")
                self.assertEqual(git(folder, "rev-parse", "HEAD"), before)
                self.assertTrue(folder.is_dir())
                builder.assert_not_called()
