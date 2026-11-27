"""Park replies grant one recommended test path and explain unsuccessful grants."""
import json
import os
import unittest
from unittest import mock

import common
import loop
import merge
from kit.tests.helpers import write_settings
from kit.tests.test_loop import AGENTS, Base, comment, issue


MARCDOWN_PARK = (
    "## Needs you\n\n"
    "Can the test lock allow the requested assertion update?\n\n"
    "Recommended: Allow changing `RevealTests.swift:330` to expect `start + 3`.\n\n"
    "Reply on this issue; the loop picks up your reply.\n\n"
    "<!-- lite-loop -->"
)
BODY = "## Protected paths this issue may change\n\nnone\n"


def park(question, recommendation):
    return ("## Needs you\n\n%s\n\nRecommended: %s\n\n"
            "Reply on this issue; the loop picks up your reply.\n\n%s\n"
            % (question, recommendation, common.MARKER))


class ParkRecommendedGrant(Base):
    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.work, ".loop"))
        write_settings(os.path.join(self.work, "loop.json"), AGENTS)
        mock.patch.object(common, "restore_loop_branch").start()
        mock.patch.object(loop, "sync_default").start()
        mock.patch.object(loop, "drain").start()
        mock.patch.object(loop.setup, "missing", return_value=None).start()
        which = loop.shutil.which
        mock.patch.object(loop.shutil, "which", side_effect=lambda name, *a, **kw:
                          None if name == "caffeinate" else which(name, *a, **kw)).start()

    def run_command(self):
        previous = os.getcwd()
        try:
            os.chdir(self.work)
            with mock.patch.object(common, "ready_is_trusted", return_value=True):
                self.assertEqual(loop.main(["run"]), 0)
        finally:
            os.chdir(previous)

    def read_reply(self, parked, reply="yes, as recommended", body=BODY, twice=False):
        self.calls.clear()
        self.inputs.clear()
        self.built.clear()
        comments = [comment(parked), comment(reply)]
        self.world([issue(4, ("needs-user",), body=body)], comments=comments)
        posted = []

        def github(args, input=None):
            result = self.fake_gh(args, input)
            if args[:3] == ["issue", "comment", "4"]:
                posted.append(input)
                comments.append(comment(input))
            if args[:3] == ["issue", "view", "4"] and "comments" in args:
                return 0, json.dumps({"comments": comments}), ""
            return result

        with mock.patch.object(common, "_run_gh", side_effect=github), self.fake_build():
            self.run_command()
            first = list(posted)
            if twice:
                # Replay a stale needs-user listing with the feedback already visible.
                self.run_command()
        edits = [text for command, text in self.inputs
                 if command.startswith("issue edit 4 --body-file")]
        return edits, first, posted

    def assert_no_grant_feedback(self, comments):
        self.assertEqual(len(comments), 1, "Explain the unsuccessful grant once")
        text = comments[0].lower()
        self.assertRegex(text, r"(nothing was granted|not granted|no .*grant|did not .*grant|cannot .*grant)")
        self.assertRegex(text, r"\brepl(?:y|ies)\b")
        self.assertRegex(text, r"\b(name|specify|state|include|list|reply with)\b[^.\n]*\bpaths?\b")
        self.assertIn(common.MARKER, comments[0])

    def test_agreement_grants_one_recommended_path_and_reports_its_source(self):
        examples = (
            (MARCDOWN_PARK, "RevealTests.swift"),
            (park("May I change the failing test?",
                  "Change Tests/MarcdownCoreTests/RevealTests.swift."),
             "Tests/MarcdownCoreTests/RevealTests.swift"),
        )
        for parked, path in examples:
            with self.subTest(park=parked):
                edits, comments, _ = self.read_reply(parked)
                self.assertEqual(len(edits), 1, "Agreement must grant the single recommended path")
                self.assertEqual(merge.allowed_paths(edits[0]), {path})
                self.assertEqual(len(comments), 1)
                self.assertIn(path, comments[0])
                self.assertRegex(comments[0].lower(), r"\brecommend(?:ation|ed)\b")
                self.assertEqual(self.built, [(4, ["yes, as recommended"])])

    def test_several_recommended_paths_require_a_reply_naming_the_paths(self):
        for recommendation in (
                "Change tests/test_a.py and tests/test_z.py.",
                "Change `tests/test_z.py`, then `tests/test_a.py`."):
            with self.subTest(recommendation=recommendation):
                edits, comments, _ = self.read_reply(
                    park("May I change the failing tests?", recommendation))
                self.assertEqual(edits, [], "Agreement cannot select among several recommended paths")
                self.assert_no_grant_feedback(comments)
                self.assertEqual(self.built, [(4, ["yes, as recommended"])])

    def test_doubt_words_prevent_a_recommended_grant(self):
        for reply in ("Yes, but keep the assertion.", "Okay, only change its layout.",
                      "Yes, unless the test is still needed.", "Yes, maybe."):
            with self.subTest(reply=reply):
                edits, _, _ = self.read_reply(MARCDOWN_PARK, reply)
                self.assertEqual(edits, [], "A doubt word must prevent the recommended grant")
                self.assertEqual(self.built, [(4, [reply])])

    def test_agreement_without_a_grant_posts_one_notice_across_two_passes(self):
        examples = (
            (park("May I change the failing test?", "Update the assertion."), BODY),
            (park("May I change the test lock?", "Change tests/package.json."), BODY),
            (park("May I change tests/test_a.py?", "Change that assertion."),
             "## Protected paths this issue may change\n\ntests/test_a.py\n"),
        )
        for parked, body in examples:
            with self.subTest(park=parked):
                edits, first, all_comments = self.read_reply(parked, body=body, twice=True)
                self.assertEqual(edits, [], "An unsuccessful grant must leave the issue body alone")
                self.assert_no_grant_feedback(first)
                self.assertEqual(all_comments, first, "A second pass must not duplicate the notice")
                self.assertEqual(self.built, [(4, ["yes, as recommended"])] * 2)

    def test_a_question_path_takes_precedence_over_the_recommendation(self):
        for question, recommendation, paths in (
                ("May I change tests/test_a.py?", "Also change tests/test_z.py.",
                 {"tests/test_a.py"}),
                ("May I change `tests/test_z.py` and `tests/test_a.py`?",
                 "Change `tests/test_other.py` and `tests/test_a.py`.",
                 {"tests/test_a.py", "tests/test_z.py"})):
            with self.subTest(question=question):
                edits, comments, _ = self.read_reply(park(question, recommendation))
                self.assertTrue(edits, "Agreement must still grant the paths named in the question")
                self.assertEqual(merge.allowed_paths(edits[-1]), paths)
                self.assertEqual(len(comments), 1)
                for path in paths:
                    self.assertIn(path, comments[0])
                self.assertNotIn("tests/test_other.py", comments[0])
                self.assertEqual(self.built, [(4, ["yes, as recommended"])])


if __name__ == "__main__":
    unittest.main()
