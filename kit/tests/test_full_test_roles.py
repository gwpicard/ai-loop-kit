from pathlib import Path

from kit.tests.test_guard import GuardCase


class TestFullTestRoles(GuardCase):
    def test_full_test_refusal_and_fallback_cover_every_session_role(self):
        roles = ("builder", "reviewer", "test-writer", "pass")
        commands = ("make test", "  make test  ", "true && make test",
                    "false || make test", "make test; true", "make test | cat",
                    "true\nmake test")
        for role in roles:
            for command in commands:
                with self.subTest(role=role, command=command, files=""):
                    self.allowed(self.bash(command, role=role, test="make test"))
            with self.subTest(role=role, targeted=True):
                self.allowed(self.bash("make unit tests/test_app.py", role=role,
                                       test="make test", files="make unit {files}"))
            for command in commands:
                with self.subTest(role=role, command=command, files="make unit {files}"):
                    result = self.bash(command, role=role, test="make test",
                                       files="make unit {files}")
                    self.refused(result, "make unit {files}")
                    self.assertIn("rule: full-test", result.stderr.splitlines())

    def test_both_test_writing_briefs_name_the_test_files_command(self):
        briefs = Path(__file__).resolve().parents[1] / "briefs"
        for name in ("test-writer", "pass-redteam"):
            with self.subTest(brief=name):
                text = (briefs / (name + ".md")).read_text(encoding="utf-8")
                self.assertIn("Test files command", text)
