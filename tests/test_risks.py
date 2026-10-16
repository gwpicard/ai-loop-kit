"""Risk lines parsed from a piece and enforced by the gate."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kit" / "scripts"))
import gate
import run
from helpers import GOOD_CODE, SPEC, Project, git
from loopkit import Refused, parse_spec


class RiskSpecTest(unittest.TestCase):
    def test_reads_risks_and_refuses_unanswered_open_choices(self):
        body = (SPEC + "\n## Risks\n"
                "Protected paths: src/auth.py, src/billing.py\n"
                "New dependency: requests: retry API\n"
                "Shared files: src/app.py\n"
                "Needs services: postgres\n"
                "Open choices: none\n")
        spec = parse_spec(body)
        self.assertEqual(spec.risks["protected_paths"], ("src/auth.py", "src/billing.py"))
        self.assertEqual(spec.risks["new_dependencies"], ("requests: retry API",))
        self.assertEqual(spec.risks["shared_files"], ("src/app.py",))
        self.assertEqual(spec.risks["needs_services"], ("postgres",))
        self.assertEqual(spec.risks["open_choices"], ())
        with self.assertRaises(Refused) as refusal:
            parse_spec(body.replace("Open choices: none", "Open choices: which database?"))
        self.assertIn("Open choices", refusal.exception.reason)

    def test_new_dependencies_need_a_reason(self):
        body = (SPEC + "\n## Risks\nProtected paths: none\n"
                "New dependency: requests\nShared files: none\n"
                "Needs services: none\nOpen choices: none\n")
        with self.assertRaises(Refused) as refusal:
            parse_spec(body)
        self.assertIn("name and reason", refusal.exception.reason)


class RiskGateTest(unittest.TestCase):
    def setUp(self):
        self.project = Project()
        self.addCleanup(self.project.close)

    def ready(self, number):
        gate.move(self.project.gh, self.project.root, number, "ready")

    def test_ready_records_risks_and_warns_about_shared_files(self):
        risks = ("\n## Risks\nProtected paths: none\nNew dependency: none\n"
                 "Shared files: src/app.py\nNeeds services: none\nOpen choices: none\n")
        first = self.project.piece(spec=SPEC + risks)
        self.ready(first)
        second = self.project.piece(spec=SPEC + risks)
        self.ready(second)
        record = gate.last_record(self.project.gh.comments(second), "ready")
        self.assertEqual(record["risks"]["shared_files"], ["src/app.py"])
        self.assertEqual(record["shared_conflicts"],
                         [{"issue": first, "files": ["src/app.py"]}])
        self.assertIn("shared files src/app.py", self.project.gh.comments(second)[-1])

    def test_submit_refuses_an_unnamed_new_dependency(self):
        number = self.project.piece()
        self.ready(number)
        folder = run.worktree(self.project.root, number)
        (folder / "package.json").write_text('{"dependencies":{"left-pad":"^1.0.0"}}\n')
        git(folder, "add", "package.json")
        git(folder, "commit", "--quiet", "-m", "Add a dependency")
        passed, output = gate.judge(folder, gate.last_record(
            self.project.gh.comments(number), "ready"))
        self.assertFalse(passed)
        self.assertIn("unnamed dependencies: left-pad", output)

    def test_pyproject_dependencies_are_checked_at_submit(self):
        number = self.project.piece()
        self.ready(number)
        folder = run.worktree(self.project.root, number)
        (folder / "pyproject.toml").write_text(
            '[project]\ndependencies = [\n    "requests>=2",\n]\n')
        git(folder, "add", "pyproject.toml")
        git(folder, "commit", "--quiet", "-m", "Add a Python dependency")
        passed, output = gate.judge(folder, gate.last_record(
            self.project.gh.comments(number), "ready"))
        self.assertFalse(passed)
        self.assertIn("unnamed dependencies: requests", output)

    def test_poetry_group_dependencies_are_checked_at_submit(self):
        number = self.project.piece()
        self.ready(number)
        folder = run.worktree(self.project.root, number)
        (folder / "habits.py").write_text(GOOD_CODE)
        (folder / "pyproject.toml").write_text(
            '[tool.poetry.group.dev.dependencies]\nrequests = "^2"\n')
        git(folder, "add", "habits.py", "pyproject.toml")
        git(folder, "commit", "--quiet", "-m", "Add a Poetry group dependency")
        passed, output = gate.judge(folder, gate.last_record(
            self.project.gh.comments(number), "ready"))
        self.assertFalse(passed)
        self.assertIn("unnamed dependencies: requests", output)

    def test_risk_path_authorises_a_configured_protected_path(self):
        self.project.loop_section("true")
        agents_file = self.project.root / "AGENTS.md"
        agents_file.write_text(agents_file.read_text() + "Protected paths: secrets\n")
        git(self.project.root, "add", "AGENTS.md")
        git(self.project.root, "commit", "--quiet", "-m", "Protect secrets")
        git(self.project.root, "push", "--quiet", "origin", "main")
        risks = ("\n## Risks\nProtected paths: secrets\nNew dependency: none\n"
                 "Shared files: none\nNeeds services: none\nOpen choices: none\n")
        number = self.project.piece(spec=SPEC + risks)
        self.ready(number)
        folder = run.worktree(self.project.root, number)
        (folder / "habits.py").write_text(GOOD_CODE)
        (folder / "secrets").mkdir()
        (folder / "secrets" / "settings.py").write_text("setting = True\n")
        git(folder, "add", "habits.py", "secrets/settings.py")
        git(folder, "commit", "--quiet", "-m", "Change named protected path")
        passed, output = gate.judge(folder, gate.last_record(
            self.project.gh.comments(number), "ready"))
        self.assertTrue(passed, output)

    def test_walk_away_refuses_pieces_that_need_services(self):
        risks = ("\n## Risks\nProtected paths: none\nNew dependency: none\n"
                 "Shared files: none\nNeeds services: postgres\nOpen choices: none\n")
        number = self.project.piece(spec=SPEC + risks)
        self.ready(number)
        with self.assertRaises(Refused) as refusal:
            run.build_piece(self.project.gh, self.project.root, number,
                            attempts=1, walk_away=True)
        self.assertIn("needs services: postgres", refusal.exception.reason)
        self.assertIn("state:ready", self.project.gh.issue(number)["labels"])
