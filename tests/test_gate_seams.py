"""Guard the gate's size and the setup and command-line seams."""
import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import Project, git

# isort: split
import gate
from loopkit import Refused


class GateSeamTest(unittest.TestCase):
    def test_state_gate_stays_under_800_lines(self):
        self.assertLess(len(Path(gate.__file__).read_text().splitlines()), 800)

    def test_doctor_quality_keeps_current_and_proposed_prepare_distinct(self):
        project = Project()
        self.addCleanup(project.close)
        gate.init(project.gh, project.root)
        project.loop_section("test -f prepared", prepare="touch prepared")
        agents = project.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Quality: test -f prepared\n")
        git(project.root, "add", "AGENTS.md")
        git(project.root, "commit", "--quiet", "-m", "Set Quality")
        git(project.root, "push", "--quiet", "origin", "main")
        for override, passed in ((None, True), ("", False)):
            with self.subTest(prepare=override):
                checks = gate.doctor(project.gh, project.root,
                                     extra_quality=["test -f tested"],
                                     proposed_prepare=override,
                                     proposed_test="test -f prepared && touch tested")
                quality = [item for item in checks if "Quality command" in item[1]]
                self.assertEqual([item[0] for item in quality], [True, passed], checks)
                self.assertIn("Proposed Quality", quality[1][1])
                if not passed:
                    self.assertIn("Test command failed before Quality", quality[1][2])

    def test_current_and_proposed_mutation_probes_report_unexercised(self):
        project = Project()
        self.addCleanup(project.close)
        gate.init(project.gh, project.root)
        command = "printf 'no changed Python functions found'"
        project.loop_section("true")
        agents = project.root / "AGENTS.md"
        agents.write_text(agents.read_text() + f"Quality: {command}\n")
        git(project.root, "add", "AGENTS.md")
        git(project.root, "commit", "--quiet", "-m", "Set mutation probe")
        git(project.root, "push", "--quiet", "origin", "main")
        checks = gate.doctor(project.gh, project.root, extra_quality=[command])
        quality = [item for item in checks if "Quality mutation" in item[1]]
        self.assertEqual(quality, [(True, "Quality mutation check could not be exercised "
                                   f"on main ({command})", "")] * 2)

    def test_cli_doctor_exit_codes_and_next_steps(self):
        for checks, expected in (([(True, "ready", "")], 0),
                                 ([(False, "Keep timed out", "increase Keep limit")], 2)):
            with self.subTest(checks=checks), \
                    patch("gate_cli.repo_root", return_value=Path.cwd()), \
                    patch("gate_cli.GitHub"), patch("gate.doctor", return_value=checks), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(gate.main(["doctor"]), expected)
                if expected:
                    self.assertIn("FAIL Keep timed out\n     next: increase Keep limit",
                                  output.getvalue())

    def test_cli_refusal_and_invalid_arguments_exit_two(self):
        with patch("gate_cli.repo_root", return_value=Path.cwd()), \
                patch("gate_cli.GitHub"), \
                patch("gate.request_stop", side_effect=Refused("no run", "start run.py")), \
                contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(gate.main(["stop"]), 2)
            self.assertEqual(output.getvalue(), "refused: no run\nnext: start run.py\n")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            gate.main(["move", "1", "unknown"])
        self.assertEqual(error.exception.code, 2)


class CachedQualityProbeTest(unittest.TestCase):
    def setUp(self):
        from run_fixtures import RunFixture
        RunFixture.setUp(self)

    def test_cached_failed_probe_for_same_command_and_main_is_reused(self):
        import json
        import os

        import run
        from loopkit import main_ref, rev

        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        command = "exit 4"
        agents.write_text(agents.read_text() + f"Quality: {command}\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Set failing Quality")
        git(self.p.root, "push", "--quiet", "origin", "main")
        number = self.p.piece()
        gate.move(self.p.gh, self.p.root, number, "ready")
        main = rev(self.p.root, main_ref(self.p.root))
        probe = gate.quality_probe_path(self.p.root, number, command, main)
        probe.parent.mkdir(exist_ok=True)
        probe.write_text(json.dumps({"checked": True, "failed": True,
                                    "command": command, "main": main}))
        with patch.dict(os.environ, {"FAKE_MODE": "good"}), \
                patch.object(gate, "quality_fails_on_main") as fresh_probe:
            result = run.build_piece(self.p.gh, self.p.root, number, 2)
        fresh_probe.assert_not_called()
        self.assertIn("back to shaping", result)
        self.assertIn("environment", "\n".join(self.p.gh.comments(number)))
        self.assertNotIn(number, self.p.gh.prs)
