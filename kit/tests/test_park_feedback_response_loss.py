"""A lost response must not duplicate park reply feedback."""
import json
import os
from unittest import mock

import common
import loop
import merge
from kit.tests.helpers import write_settings
from kit.tests.test_loop import AGENTS, Base, comment, issue


class ParkFeedbackResponseLoss(Base):
    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.work, ".loop"))
        write_settings(os.path.join(self.work, "loop.json"), AGENTS)
        mock.patch.object(common, "restore_loop_branch").start()
        mock.patch.object(loop, "sync_default").start()
        mock.patch.object(loop, "drain").start()

    def lost_response(self, reply, granted):
        body = "## Protected paths this issue may change\n\nnone\n"
        park = ("## Needs you\n\nMay I change tests/test_a.py?\n\n"
                "Recommended: yes\n\n" + common.MARKER)
        comments = [comment(park), comment(reply)]
        self.world([issue(4, ("needs-user",), body=body)], comments=comments)
        posted = []
        reads_after_loss = []

        def github(args, input=None):
            result = self.fake_gh(args, input)
            if args[:3] == ["issue", "comment", "4"]:
                posted.append(input)
                if len(posted) == 1:
                    return 124, "", "gh timed out after creating the comment"
            if args[:3] == ["issue", "view", "4"] and "comments" in args:
                if posted:
                    reads_after_loss.append(True)
                return 0, json.dumps({"comments": comments + [comment(text) for text in posted]}), ""
            return result

        with mock.patch.object(common, "_run_gh", side_effect=github), self.fake_build():
            self.assertEqual(self.run_loop(), 0)
        self.assertEqual(len(posted), 1, "A lost response must not repeat a successful post")
        self.assertTrue(reads_after_loss, "Read back the comment after losing its response")
        self.assertIn("tests/test_a.py", posted[0])
        self.assertIn(common.MARKER, posted[0])
        edits = [text for command, text in self.inputs
                 if command.startswith("issue edit 4 --body-file")]
        self.assertEqual(merge.allowed_paths(edits[-1]) if edits else set(),
                         {"tests/test_a.py"} if granted else set())
        self.assertIn("issue edit 4 --add-label ready", self.calls)
        self.assertEqual(self.built, [(4, [reply])])

    def test_a_lost_grant_feedback_response_is_read_back_without_reposting(self):
        self.lost_response("Yes.", granted=True)

    def test_a_lost_conditional_feedback_response_is_read_back_without_reposting(self):
        self.lost_response("Yes, but keep the assertion.", granted=False)
