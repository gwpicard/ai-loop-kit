# Doctor and gate messages must describe what the kit actually knows.
from __future__ import annotations

import io
import json
import sys
import sysconfig
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import Project

# isort: split
import gate
import session
from loopkit import GitHub


def pytest_program() -> Path | None:
    """The pytest program installed for this Python, wherever pip put it."""
    folders = [Path(sys.executable).parent, Path(sysconfig.get_path("scripts"))]
    folders += [Path(sysconfig.get_path("scripts", scheme))
                for scheme in ("posix_user", "osx_framework_user")
                if scheme in sysconfig.get_scheme_names()]
    return next((folder / "pytest" for folder in folders
                 if (folder / "pytest").is_file()), None)


class HonestMessagesTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.p.loop_section("true")
        gate.init(self.p.gh, self.p.root)

    def doctor_output(self):
        with patch("gate_cli.repo_root", return_value=self.p.root), \
                patch("gate_cli.GitHub", return_value=self.p.gh), \
                redirect_stdout(io.StringIO()) as output:
            code = gate.main(["doctor"])
        return code, output.getvalue().splitlines()

    def add_empty_test_file(self):
        """A project with a test file that collects nothing has a real fault."""
        (self.p.root / "test_nothing.py").write_text("HELPER = 1\n")
        from helpers import git
        git(self.p.root, "add", "test_nothing.py")
        git(self.p.root, "commit", "--quiet", "-m", "Empty test file")

    def test_project_without_tests_gets_a_warning_and_the_scaffold_step(self):
        self.p.loop_section(f"{sys.executable} -m pytest")
        code, lines = self.doctor_output()
        self.assertEqual(code, 0, lines)
        self.assertTrue(any(line.startswith("warn") and "no tests yet" in line
                            for line in lines), lines)
        self.assertTrue(any("next:" in line and "scaffold piece" in line for line in lines),
                        lines)

    def test_project_without_tests_warns_for_unittest_on_new_python(self):
        command = f"{sys.executable} -c 'import sys; print(\"NO TESTS RAN\"); sys.exit(5)'"
        self.p.loop_section(command)
        code, lines = self.doctor_output()
        self.assertEqual(code, 0, lines)
        self.assertTrue(any(line.startswith("warn") and "no tests yet" in line
                            for line in lines), lines)

    def test_D1_empty_pytest_says_no_tests_were_collected(self):
        self.add_empty_test_file()
        self.p.loop_section(f"{sys.executable} -m pytest")
        code, lines = self.doctor_output()
        self.assertEqual(code, 2)
        self.assertTrue(any(line.startswith("FAIL") and "no tests were collected" in line
                            for line in lines), lines)
        self.assertTrue(any("next:" in line and "add tests" in line for line in lines), lines)

    def test_D1_empty_pytest_is_clear_with_a_distinct_keep(self):
        self.add_empty_test_file()
        self.p.loop_section(f"{sys.executable} -m pytest")
        import doctor
        original = doctor.loop_settings
        with patch.object(doctor, "loop_settings", side_effect=lambda folder: {
                **original(folder), "keep": "true"}):
            code, lines = self.doctor_output()
        self.assertEqual(code, 2)
        self.assertTrue(any(line.startswith("FAIL") and "no tests were collected" in line
                            for line in lines), lines)

    def test_D1_quiet_empty_pytest_says_no_tests_were_collected(self):
        program = pytest_program()
        commands = (f"{sys.executable} -m pytest -qq",
                    f'"{sys.executable}" -m pytest -qqq',
                    f"{program} -qq" if program else "")
        self.add_empty_test_file()
        for command in commands:
            with self.subTest(command=command):
                if not command:
                    self.skipTest("no pytest program is installed for this Python")
                self.p.loop_section(command)
                code, lines = self.doctor_output()
                self.assertEqual(code, 2)
                self.assertTrue(any(line.startswith("FAIL") and "no tests were collected" in line
                                    for line in lines), lines)
                self.assertTrue(any("next:" in line and "add tests" in line for line in lines),
                                lines)

    def test_custom_exit_five_keeps_its_configuration_failure(self):
        message = "configuration error: missing test database URL"
        command = f"{sys.executable} -c 'import sys; print(\"{message}\"); sys.exit(5)'"
        for prefix in ("", f"{sys.executable} -m pytest -qq; "):
            with self.subTest(prefix=prefix):
                self.p.loop_section(prefix + command)
                code, lines = self.doctor_output()
                self.assertEqual(code, 2)
                self.assertIn(message, "\n".join(lines))
                self.assertFalse(any("no tests were collected" in line for line in lines), lines)
                self.assertFalse(any("add tests" in line for line in lines), lines)
                self.assertTrue(any("next: fix the command or environment" in line
                                    for line in lines), lines)

    def test_D2_unknown_protection_has_an_unknown_mark_without_blocking(self):
        code, lines = self.doctor_output()
        protection = next(line for line in lines if "main branch protection:" in line)
        self.assertEqual(protection.split()[0], "unknown")
        self.assertIn("main branch protection: unknown", protection)
        self.assertEqual(code, 0)

    def test_known_protection_stays_non_blocking(self):
        for state in ("enabled", "disabled"):
            with self.subTest(state=state), patch.object(
                    self.p.gh, "main_protection", return_value=state, create=True):
                code, lines = self.doctor_output()
                self.assertIn(f"ok   main branch protection: {state}", lines)
                self.assertEqual(code, 0)

    def test_D3_leftover_worktree_has_a_warning_mark_without_blocking(self):
        leftover = self.p.root / ".loop/worktrees/old"
        leftover.mkdir(parents=True)
        saved = leftover / "notes.txt"
        saved.write_text("keep this work\n")
        code, lines = self.doctor_output()
        warning = next(line for line in lines if "warning: old in-project worktrees" in line)
        self.assertEqual(warning.split()[0], "warn")
        self.assertIn(str(leftover), warning)
        self.assertTrue(any("next:" in line and str(leftover) in line for line in lines))
        self.assertEqual(code, 0)
        self.assertEqual(saved.read_text(), "keep this work\n")

    def test_D4_list_contract_names_the_type_and_the_fix(self):
        source = self.p.root / "input.json"
        source.write_text(json.dumps({"Intent": "Keep habits", "Approach": "",
                                      "Contract": ["D1: keep it"], "Files": "judge.py"}))
        args = ["session.py", "--role", "judge-writer", "--input", str(source),
                "--output", str(self.p.root / "answer.txt"), "--folder", str(self.p.root)]
        with patch.object(sys, "argv", args), patch.object(session, "run_session") as launch, \
                redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit) as caught:
            session.main()
        self.assertEqual(caught.exception.code, 2)
        lines = error.getvalue().splitlines()
        self.assertIn("Contract must be a string", lines[0])
        self.assertTrue(lines[1].startswith("next:"), lines)
        self.assertIn("Contract", lines[1])
        self.assertIn("JSON string", lines[1])
        self.assertIn("\\n", lines[1])
        launch.assert_not_called()

    def test_D5_status_uses_current_labels_after_ready_without_search_lag(self):
        n = self.p.piece()
        stale = self.p.gh.issue(n)
        gate.move(self.p.gh, self.p.root, n, "ready")

        def transport(*args):
            self.assertEqual(args[:2], ("issue", "list"))
            # Label searches still have the old shaping state.
            items = ([stale] if args[args.index("--label") + 1] in stale["labels"] else []) \
                if "--label" in args else [self.p.gh.issue(n)]
            return json.dumps([{**item, "labels": [{"name": label} for label in item["labels"]]}
                               for item in items])

        gh = GitHub(self.p.root)
        with patch.object(gh, "_gh", side_effect=transport):
            lines = gate.status(gh).splitlines()
        self.assertIn(f"ready: {n} Add a habit", lines)
        self.assertIn("shaping: none", lines)

    def test_status_keeps_older_ready_pieces_among_unlabelled_issues(self):
        recent = [{"number": n, "title": "Unshaped", "labels": []} for n in range(2, 203)]
        ready = {"number": 1, "title": "Ready piece", "labels": [{"name": "state:ready"}]}

        def transport(*args):
            items = [ready] if "--label" in args else [*recent, ready]
            return json.dumps(items[:int(args[args.index("--limit") + 1])])

        gh = GitHub(self.p.root)
        with patch.object(gh, "_gh", side_effect=transport):
            lines = gate.status(gh).splitlines()
        self.assertIn("ready: 1 Ready piece", lines)


if __name__ == "__main__":
    unittest.main()
