"""Merge-only retries preserve build reports in the issue note and pull request."""
import json
from pathlib import Path
import unittest
from unittest import mock

import common
import flow
import merge
from kit.tests.helpers import FakeGh, make_repo, run_git


class RetryBuildReportTest(FakeGh):
    def setUp(self):
        super().setUp()
        self.work, _ = make_repo(self.tmp, {
            "loop.json": json.dumps({"Test command": "true"}),
            "app.txt": "original\n", "tests/test_saved.py": "assert True\n"})
        run_git(["push", "origin", "main:loop/main"], self.work)
        run_git(["switch", "-c", "issue/7"], self.work)
        Path(self.work, "app.txt").write_text("reviewed work\n")
        run_git(["add", "app.txt"], self.work)
        run_git(["commit", "-qm", "Reviewed work"], self.work)
        self.head = common.git(["rev-parse", "HEAD"], cwd=self.work)
        run_git(["push", "origin", "issue/7"], self.work)
        run_git(["switch", "main"], self.work)
        comments = [{"body": body} for body in (
            "TESTS:\ntests/test_saved.py\n\n" + common.MARKER,
            "## Review, round 1\n\nVERDICT: APPROVE\nHEAD: " + self.head + "\n\n" + common.MARKER,
            "## Needs you\n\nThe loop refused to merge: Test command timed out.\n\n" + common.MARKER)]
        self.scenario([
            {"match": "issue view 7", "responses": [{"stdout": json.dumps({
                "title": "Retry approved work", "body": "Keep the approved change.", "comments": comments})}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "issue comment", "responses": [{}]},
            {"match": "pr edit", "responses": [{}]},
        ])
        self.logs = Path(self.work, ".loop/logs")
        self.logs.mkdir(parents=True)

    def log(self, number, reply, agent="claude"):
        if agent == "claude":
            output = json.dumps({"type": "result", "is_error": False, "result": reply}, indent=2)
        else:
            output = "\n".join(json.dumps(event) for event in (
                {"type": "thread.started", "thread_id": "saved-thread"},
                {"type": "item.completed", "item": {"type": "agent_message", "text": reply}},
                {"type": "turn.completed", "usage": {}}))
        (self.logs / ("7-builder-%s.log" % number)).write_text(
            "--- %s session\n%s\n--- stderr\n\n" % (agent, output))

    def retry(self):
        sent, real_gh = [], flow.gh

        def gh(args, **kwargs):
            sent.append((args, kwargs.get("input", "")))
            return real_gh(args, **kwargs)

        with mock.patch.object(flow, "gh", side_effect=gh), \
                mock.patch.object(flow.session, "run", side_effect=AssertionError("Unexpected agent session")), \
                mock.patch.object(merge, "merge", return_value=merge.Result(True, False, "merged", self.head)), \
                mock.patch.object(merge, "find_pr", return_value={"number": 9}):
            result = flow.build(7, self.work, replies=["Retry the merge."])
        self.assertEqual(result.status, "merged", result.reason)
        notes = [text for args, text in sent if args[:2] == ["issue", "comment"] and text.startswith("## Built")]
        self.assertEqual(len(notes), 1)
        self.assertEqual([text for args, text in sent if args[:2] == ["pr", "edit"]], notes)
        self.assertIn("Retried the merge using the last approving review", notes[0])
        self.assertNotIn("No BUILT block", notes[0])
        return notes[0]

    def test_available_report_preserves_summary_and_deviations_for_both_agents(self):
        for number, agent in ((9, "claude"), (10, "codex")):
            with self.subTest(agent=agent):
                self.log(1, "BUILT:\nOutdated summary.\nDEVIATIONS:\nnone")
                summary = "Added the reviewed behaviour with %s.\nKept the existing interface." % agent
                self.log(number, "BUILT:\n%s\nDEVIATIONS:\nUsed the existing adapter." % summary, agent)
                note = self.retry()
                self.assertIn(summary, note)
                self.assertIn("Deviations: Used the existing adapter.", note)
                self.assertNotIn("Outdated summary", note)
                self.assertNotIn("unavailable", note)

    def test_missing_report_explicitly_marks_summary_and_deviations_unavailable(self):
        self.log(1, "PARK: Need a decision | Retry later")
        (self.logs / "7-builder-2.log").write_text("Interrupted session\n")
        note = self.retry()
        self.assertIn("The original builder summary is unavailable", note)
        self.assertIn("Deviations: Unknown: the original deviation status is unavailable", note)
        self.assertNotIn("Deviations: none", note)

    def test_missing_deviations_does_not_imply_none(self):
        self.log(1, "BUILT:\nAdded the reviewed behaviour.")
        note = self.retry()
        self.assertIn("Added the reviewed behaviour.", note)
        self.assertIn("Deviations: Unknown: the original deviation status is unavailable", note)
        self.assertNotIn("Deviations: none", note)

    def test_explicit_no_deviations_is_preserved(self):
        self.log(1, "BUILT:\nAdded the reviewed behaviour.\nDEVIATIONS:\nnone")
        note = self.retry()
        self.assertIn("Added the reviewed behaviour.", note)
        self.assertIn("Deviations: none", note)
        self.assertNotIn("Unknown", note)

    def test_available_deviations_survive_a_missing_summary(self):
        self.log(1, "DEVIATIONS:\nUsed the existing adapter.")
        note = self.retry()
        self.assertIn("The original builder summary is unavailable", note)
        self.assertIn("Deviations: Used the existing adapter.", note)


if __name__ == "__main__":
    unittest.main()
