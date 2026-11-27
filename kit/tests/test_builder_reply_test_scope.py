"""Replies cannot widen the tests a builder session runs."""
import json
from pathlib import Path
import re
import unittest
from unittest import mock

import common
import flow
from kit.tests.helpers import FakeGh, make_repo, run_git


FULL_SUITE_REPLY = (
    "No. Don't accept the focused tests alone. " + chr(35) + str(300 + 65)
    + " raises Test minutes from 30 to 90; run the full suite again under the new limit."
)
SCOPE_RULE = r"\brepl(?:y|ies)\b[^.\n]*\bcannot widen\b[^.\n]*\btest(?:s)?\b"
STOP = "PARK: End of the prompt fixture | No action needed."


class BuilderReplyTestScopeTest(FakeGh):
    def setUp(self):
        super().setUp()
        self.work, _ = make_repo(self.tmp, {
            "loop.json": json.dumps({
                "Test command": "true", "Test files command": "true {files}",
                "Max rounds": 2,
            }),
            "tests/test_saved.py": "assert True\n",
            "app.txt": "base\n",
        })
        run_git(["push", "origin", "HEAD:loop/main"], self.work)
        self.base = common.git(["rev-parse", "HEAD"], cwd=self.work)
        self.commit_app("issue\n")
        run_git(["push", "origin", "HEAD:issue/7"], self.work)
        self.scenario([
            {"match": "issue view 7", "responses": [{"stdout": json.dumps({
                "title": "Keep builder tests targeted", "body": "Build the approved change.",
                "comments": [{"body": "TESTS:\ntests/test_saved.py\n"}],
            })}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "issue comment", "responses": [{}]},
            {"match": "issue edit", "responses": [{}]},
        ])

    def commit_app(self, text):
        Path(self.work, "app.txt").write_text(text)
        run_git(["add", "app.txt"], self.work)
        run_git(["commit", "-qm", "Update the fixture app"], self.work)

    def capture(self, replies, *, reach_review=False, fix=False):
        self.calls = []

        def session(role, prompt, tree, *args, **kwargs):
            self.calls.append({"role": role, "prompt": prompt, "resume": kwargs.get("resume")})
            if role == "builder" and (reach_review or fix) and len(self.calls) == 1:
                # No session id makes the fix round start with a fresh prompt.
                return "BUILT:\nKept the approved change.\nDEVIATIONS:\nnone", None
            if role == "reviewer" and fix:
                head = common.git(["rev-parse", "HEAD"], cwd=tree)
                return "VERDICT: CHANGES\nHEAD: " + head + "\n1. Handle empty input.", "review"
            return STOP, "captured"

        with mock.patch.object(flow.session, "run", side_effect=session):
            result = flow.build(7, self.work, replies=replies)
        self.assertEqual(result.status, "parked", result.reason)
        self.assertEqual(result.reason, "End of the prompt fixture")
        return self.calls

    def assert_scope_rule(self, text):
        text = " ".join(text.replace("`", "").split())
        self.assertRegex(text.lower(), SCOPE_RULE)
        self.assertIn("loop check", text)
        self.assertIn("DEVIATIONS", text)
        self.assertIn("full suite", text.lower())
        self.assertRegex(text.lower(), r"\bmerge runs (?:the full suite|it)\b")

    def assert_rule_after_replies(self, prompt, replies):
        block = "The person's replies to the last park:\n" + "\n---\n".join(replies) + "\n"
        self.assertEqual(prompt.count(block), 1)
        after = prompt.split(block, 1)[1]
        lines = [line.strip() for line in after.splitlines() if line.strip()]
        self.assertTrue(lines, "The builder prompt needs a test-scope rule after all replies")
        self.assert_scope_rule(lines[0])

    def test_first_builder_prompt_puts_the_rule_after_the_full_suite_reply(self):
        replies = [FULL_SUITE_REPLY]
        calls = self.capture(replies)
        self.assertEqual([call["role"] for call in calls], ["builder"])
        self.assert_rule_after_replies(calls[0]["prompt"], replies)

    def test_fresh_fix_prompt_puts_the_rule_after_every_reply(self):
        replies = [FULL_SUITE_REPLY, "Keep the approved behaviour."]
        calls = self.capture(replies, fix=True)
        self.assertEqual([call["role"] for call in calls], ["builder", "reviewer", "builder"])
        self.assertIsNone(calls[-1]["resume"])
        self.assertIn("Fix these", calls[-1]["prompt"])
        self.assert_rule_after_replies(calls[-1]["prompt"], replies)

    def test_conflicts_prompt_puts_the_rule_after_every_reply(self):
        run_git(["checkout", "-q", "-b", "loop-side", self.base], self.work)
        self.commit_app("loop\n")
        run_git(["push", "origin", "HEAD:loop/main"], self.work)
        replies = ["Keep both changes when resolving the conflict.", FULL_SUITE_REPLY]
        calls = self.capture(replies)
        self.assertEqual([call["role"] for call in calls], ["builder"])
        self.assertIn("conflicts in: app.txt", calls[0]["prompt"])
        self.assert_rule_after_replies(calls[0]["prompt"], replies)

    def test_builder_without_replies_has_no_added_scope_rule(self):
        prompt = self.capture([])[0]["prompt"]
        self.assertNotIn("The person's replies", prompt)
        issue_prompt = prompt.split("# Issue 7:", 1)[1]
        self.assertNotRegex(issue_prompt.lower(), SCOPE_RULE)

    def test_reviewer_with_replies_has_no_added_scope_rule(self):
        calls = self.capture([FULL_SUITE_REPLY], reach_review=True)
        self.assertEqual([call["role"] for call in calls], ["builder", "reviewer"])
        prompt = calls[-1]["prompt"]
        self.assertIn(FULL_SUITE_REPLY, prompt)
        self.assertNotRegex(prompt.lower(), SCOPE_RULE)

    def test_builder_brief_states_the_rule_next_to_the_test_scope_park_rule(self):
        text = Path(flow.BRIEFS, "builder.md").read_text()
        paragraphs = [" ".join(part.split()) for part in re.split(r"\n\s*\n", text)]
        anchor = "Never park to ask for a longer test limit or a wider test scope."
        index = next(i for i, paragraph in enumerate(paragraphs) if anchor in paragraph)
        self.assert_scope_rule(" ".join(paragraphs[max(0, index - 1):index + 2]))


if __name__ == "__main__":
    unittest.main()
