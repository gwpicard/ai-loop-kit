"""Count commands when a builder stops after a successful loop check."""
from pathlib import Path
import unittest

from kit.tests import test_session_targeted_cap as sessions
from kit.tests.helpers import run_git


class StopAfterLoopCheckTest(unittest.TestCase):
    def assert_allowed(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")

    def test_stop_reuses_only_a_clean_loop_check_pass_at_the_current_commit(self):
        fixture = sessions.SessionFixture(self, importers=0)
        for change in ("commit", "tracked", "untracked"):
            with self.subTest(change=change):
                # Commit the preceding dirty example before recording another clean pass.
                run_git(["add", "-A"], fixture.work)
                run_git(["commit", "--allow-empty", "-m", "Prepare clean pass"], fixture.work)
                self.assert_allowed(fixture.check())
                before = fixture.merge.commands()
                if change == "commit":
                    run_git(["commit", "--allow-empty", "-m", "Advance checked head"], fixture.work)
                else:
                    name = "app.py" if change == "tracked" else "new_source.py"
                    (fixture.work / name).write_text("value = 3\n")
                result = fixture.stop("invalidated-" + change)
                self.assert_allowed(result)
                self.assertEqual(result.stdout, "")
                self.assertEqual(fixture.merge.commands()[len(before):], fixture.expected())
                if change != "commit":
                    self.assert_allowed(fixture.check())
                    before = fixture.merge.commands()
                    result = fixture.stop("dirty-check-" + change)
                    self.assert_allowed(result)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(fixture.merge.commands()[len(before):], fixture.expected(),
                                     "A loop check run with unsaved changes cannot authorise a later stop")

        run_git(["add", "-A"], fixture.work)
        run_git(["commit", "-m", "Save dirty examples"], fixture.work)
        self.assert_allowed(fixture.check())
        before = fixture.merge.commands()
        result = fixture.stop("clean-pass")
        self.assert_allowed(result)
        self.assertEqual(result.stdout, "")
        self.assertEqual(fixture.merge.commands(), before,
                         "Stop must reuse loop check's clean pass without running either command")

    def test_builder_brief_limits_sessions_to_targeted_tests_and_reserves_full_suite_for_merge(self):
        text = " ".join(Path(sessions.KIT, "briefs/builder.md").read_text().lower().split())
        self.assertRegex(text, r"session[^.]*only[^.]*targeted tests")
        self.assertRegex(text, r"merge runs the full suite")
        self.assertRegex(text, r"never park[^.]*longer test limit[^.]*wider test scope")


if __name__ == "__main__":
    unittest.main()
