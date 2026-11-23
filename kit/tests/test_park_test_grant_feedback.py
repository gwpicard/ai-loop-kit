"""Park replies report whether they granted permission to change tests."""
import os
from pathlib import Path
import re
import unittest
from unittest import mock

import common
import loop
import merge
from kit.tests.helpers import write_settings
from kit.tests.test_loop import AGENTS, Base, comment, issue


class ParkTestGrantFeedback(Base):
    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.work, ".loop"))
        write_settings(os.path.join(self.work, "loop.json"), AGENTS)
        mock.patch.object(common, "restore_loop_branch").start()
        mock.patch.object(loop, "sync_default").start()
        mock.patch.object(loop, "drain").start()

    def issue_comments(self):
        return [body for command, body in self.inputs
                if command.startswith("issue comment 4 ")]

    def read_replies(self, question, replies, body):
        self.calls.clear()
        self.inputs.clear()
        self.built.clear()
        park = "## Needs you\n\n%s\n\nRecommended: yes\n\n%s" % (question, common.MARKER)
        self.world([issue(4, ("needs-user",), body=body)],
                   comments=[comment(park)] + [comment(reply) for reply in replies])
        with self.fake_build():
            self.assertEqual(self.run_loop(), 0)
        return [text for command, text in self.inputs
                if command.startswith("issue edit 4 --body-file")]

    def test_a_grant_posts_one_comment_naming_only_the_paths_added(self):
        body = "## Protected paths this issue may change\n\ntests/test_existing.py\n"
        for question in (
                "May I change tests/test_z.py, tests/test_existing.py and tests/test_a.py?",
                "May I change `tests/test_a.py`, `.claude/tests/test_secret.py`, "
                "`tests/test_z.py` and `tests/test_existing.py`?"):
            with self.subTest(question=question):
                edits = self.read_replies(question, ["Yes. Change it only where needed.", "Yes."], body)
                self.assertTrue(edits, "The plain last reply should grant the test paths")
                self.assertEqual(merge.allowed_paths(edits[-1]),
                                 {"tests/test_existing.py", "tests/test_a.py", "tests/test_z.py"})
                self.assertEqual(self.built, [(4, ["Yes. Change it only where needed.", "Yes."])])
                comments = self.issue_comments()
                self.assertEqual(len(comments), 1, "Report the grant once, rather than once per path")
                text = comments[0]
                self.assertIn("tests/test_a.py", text)
                self.assertIn("tests/test_z.py", text)
                self.assertNotIn("tests/test_existing.py", text)
                self.assertNotIn(".claude/tests/test_secret.py", text)
                self.assertIn("Protected paths this issue may change", text)
                self.assertRegex(text.lower(), r"\b(add(?:ed)?|grant(?:ed)?)\b")

    def test_a_conditional_yes_reports_no_grant_and_still_requeues_with_the_replies(self):
        body = "## Protected paths this issue may change\n\nnone\n"
        examples = (
            ("May I change tests/test_a.py and tests/test_z.py?", "Yes. Change it only where needed.", "only"),
            ("May I change `tests/test_z.py` and `tests/test_a.py`?", "Okay, but keep the assertion.", "but"),
        )
        for question, reply, doubt in examples:
            with self.subTest(reply=reply):
                edits = self.read_replies(question, ["Yes.", reply], body)
                self.assertEqual(edits, [], "The conditional last reply must grant no path")
                self.assertEqual(self.built, [(4, ["Yes.", reply])])
                self.assertIn("issue edit 4 --remove-label needs-user", self.calls)
                self.assertIn("issue edit 4 --add-label ready", self.calls)
                comments = self.issue_comments()
                self.assertEqual(len(comments), 1, "Explain why the conditional yes granted nothing")
                text = comments[0]
                for path in ("tests/test_a.py", "tests/test_z.py"):
                    self.assertIn(path, text)
                self.assertRegex(text.lower(), r"(not granted|no .*grant|did not .*grant|cannot .*grant)")
                self.assertRegex(text.lower(), r"(doubt|conditional|ambiguous|\b%s\b)" % doubt)
                self.assertIn("Yes.", text)
                self.assertRegex(text.lower(), r"\b(last|latest|final)\b.*\breply\b")

    def test_a_park_about_tests_without_a_path_warns_that_yes_cannot_grant_one(self):
        for question in ("May I change the failing test?", "May I update the fixture?",
                         "May I change the lock?"):
            with self.subTest(question=question):
                self.inputs.clear()
                common.park(4, question, "Change tests/test_recommended.py.", project=self.work)
                comments = self.issue_comments()
                self.assertEqual(len(comments), 1)
                text = comments[0]
                extra = text.replace(question, "").replace("Change tests/test_recommended.py.", "")
                lines = [line.lower() for line in extra.splitlines()]
                self.assertTrue(any(
                    re.search(r"(no .*path|path.*(?:not|without|missing))", line)
                    and "yes" in line
                    and re.search(r"(cannot|can't|will not|won't|does not).*grant", line)
                    for line in lines), "The park needs one line explaining that no named path means no grant")


class ParkTestPathBrief(unittest.TestCase):
    def test_the_preamble_requires_the_test_path_in_the_park_question(self):
        text = " ".join((Path(loop.flow.BRIEFS) / "preamble.md").read_text().split())
        self.assertRegex(text.lower(),
                         r"park[^.]*test[^.]*\b(must|always)\b[^.]*\bpath\b[^.]*\bquestion\b")


if __name__ == "__main__":
    unittest.main()
