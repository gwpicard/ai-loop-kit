"""Retries reuse approval only while the parked branch still has its reviewed head."""
import json
from pathlib import Path
import unittest
from unittest import mock

import common
import flow
import merge
from kit.tests.helpers import FakeGh


class RetryGoesToMergeTest(FakeGh):
    def setUp(self):
        super().setUp()
        self.work = Path(self.tmp, "project")
        self.origin = Path(self.tmp, "origin.git")
        self.git(["init", "--bare", "--template=", str(self.origin)], cwd=self.tmp)
        self.git(["init", "--template=", "-b", "loop/main", str(self.work)], cwd=self.tmp)
        self.git(["config", "user.name", "Test"])
        self.git(["config", "user.email", "test@example.com"])
        self.git(["remote", "add", "origin", str(self.origin)])
        Path(self.work, "loop.json").write_text(json.dumps({"Test command": "true"}))
        Path(self.work, "tests").mkdir()
        Path(self.work, "tests/test_saved.py").write_text("assert True\n")
        Path(self.work, "app.txt").write_text("original\n")
        self.git(["add", "."])
        self.git(["commit", "-qm", "Initial project"])
        self.git(["push", "origin", "loop/main"])
        self.base = self.git(["rev-parse", "HEAD"])
        self.git(["switch", "-c", "issue/7"])
        self.approved = self.commit("app.txt", "reviewed work\n")
        self.git(["push", "origin", "issue/7"])
        self.git(["switch", "loop/main"])
        self.review = self.approval(self.approved, 2)
        self.merge_park = self.park("The loop refused to merge: Test command timed out.")
        self.locked = {"body": "TESTS:\ntests/test_saved.py\n\nCommit: " + self.base
                       + "\n\n" + common.MARKER}
        self.reply = {"body": "Retry the merge, please."}

    def git(self, args, cwd=None, **kwargs):
        return common.git(args, cwd=str(cwd or self.work), **kwargs)

    def commit(self, path, content):
        Path(self.work, path).write_text(content)
        self.git(["add", path])
        self.git(["commit", "-qm", "Update " + path])
        return self.git(["rev-parse", "HEAD"])

    def approval(self, head, round_number):
        return ("## Review, round %s\n\nThe change meets the criteria.\n\n"
                "VERDICT: APPROVE\nHEAD: %s\n\nFOLLOW-UPS:\nnone\n\n%s\n"
                % (round_number, head, common.MARKER))

    def park(self, reason):
        return {"body": "## Needs you\n\n" + reason
                + "\n\nRecommended: Retry when ready.\n\nReply on this issue; "
                "the loop picks up your reply.\n\n" + common.MARKER + "\n"}

    def retry(self, comments):
        self.scenario([
            {"match": "issue view 7", "responses": [{"stdout": json.dumps({
                "title": "Retry approved work", "body": "Keep the approved change.",
                "comments": comments})}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "issue comment", "responses": [{}]},
            {"match": "issue edit", "responses": [{}]},
        ])
        self.sessions, self.merges = [], []

        def agent(role, prompt, tree, *args, **kwargs):
            self.sessions.append({"role": role, "prompt": prompt,
                                  "merging": bool(self.git(
                                      ["rev-parse", "-q", "--verify", "MERGE_HEAD"],
                                      cwd=tree, check=False))})
            return "PARK: Recording agent finished | End this fixture", "recording-session"

        def merge_gate(issue, branch, review, project):
            head = self.git(["rev-parse", branch])
            self.merges.append({"issue": issue, "branch": branch, "review": review,
                                "head": head, "remote": self.git(
                                    ["rev-parse", "refs/heads/" + branch], cwd=self.origin),
                                "parents": self.git(["rev-list", "--parents", "-n", "1", head]).split()[1:]})
            return merge.Result(True, False, "merged", head)

        with mock.patch.object(flow.session, "run", side_effect=agent), \
                mock.patch.object(merge, "merge", side_effect=merge_gate), \
                mock.patch.object(merge, "find_pr", return_value=None):
            return flow.build(7, str(self.work), replies=[self.reply["body"]])

    def assert_reused_review(self, result, head, review):
        self.assertEqual([s["role"] for s in self.sessions], [],
                         "A merge-only retry must start no agent sessions")
        self.assertEqual(result.status, "merged", result.reason)
        self.assertEqual(len(self.merges), 1, "The retry must reach the merge gate once")
        landed = self.merges[0]
        self.assertEqual((landed["issue"], landed["branch"]), (7, "issue/7"))
        self.assertEqual((landed["head"], landed["remote"]), (head, head))
        approved_text = review.split("\n\n", 1)[1].split(common.MARKER)[0].strip()
        self.assertIn(approved_text, landed["review"])
        self.assertEqual(merge.parse_verdict(landed["review"]), ("APPROVE", head))

    def test_unchanged_approved_head_retries_merge_without_any_session(self):
        older = {"body": self.approval(self.base, 1)}
        for layout in ("tests first", "tests between reviews"):
            with self.subTest(layout=layout):
                reviews = [older, {"body": self.review}]
                comments = ([self.locked] + reviews if layout == "tests first"
                            else [older, self.locked, reviews[-1]])
                result = self.retry(comments + [self.merge_park, self.reply])
                self.assert_reused_review(result, self.approved, self.review)

    def test_clean_catch_up_uses_pre_merge_approval_without_any_session(self):
        self.git(["switch", "loop/main"])
        loop_head = self.commit("gained.txt", "work merged while the issue was parked\n")
        self.git(["push", "origin", "loop/main"])
        result = self.retry([self.locked, {"body": self.review}, self.merge_park, self.reply])
        self.assertEqual([s["role"] for s in self.sessions], [],
                         "A clean catch-up must not start an agent session")
        self.assertEqual(len(self.merges), 1, "Catch-up must continue to the merge gate")
        caught_up = self.merges[0]["head"]
        self.assertNotEqual(caught_up, self.approved, "The fixture must create a catch-up commit")
        self.assertEqual(set(self.merges[0]["parents"]), {self.approved, loop_head})
        self.assertEqual(self.git(["show", caught_up + ":app.txt"]), "reviewed work")
        self.assertEqual(self.git(["show", caught_up + ":gained.txt"]),
                         "work merged while the issue was parked")
        self.assert_reused_review(result, caught_up, self.review.replace(self.approved, caught_up))

    def test_changed_head_or_other_last_park_still_runs_builder(self):
        for case in ("changed head", "latest approval differs", "other last park"):
            with self.subTest(case=case):
                head = self.approved
                if case == "changed head":
                    self.git(["switch", "issue/7"])
                    head = self.commit("later.txt", "work after approval\n")
                    self.git(["push", "origin", "issue/7"])
                    self.git(["switch", "loop/main"])
                reviews = [{"body": self.review}]
                if case == "latest approval differs":
                    reviews.append({"body": self.approval(self.base, 3)})
                parks = [self.merge_park]
                if case == "other last park":
                    parks.append(self.park("Choose which behaviour should ship?"))
                result = self.retry([self.locked] + reviews + parks + [self.reply])
                self.assertEqual([s["role"] for s in self.sessions], ["builder"], case)
                self.assertEqual(result.status, "parked", result.reason)
                self.assertEqual(self.merges, [], "The builder must run before another merge")
                self.assertEqual(self.git(["rev-parse", "refs/heads/issue/7"], cwd=self.origin), head)
                self.approved = head
                self.review = self.approval(head, 2)

    def test_conflicting_catch_up_still_enters_builder_conflicts_step(self):
        self.git(["switch", "loop/main"])
        self.commit("app.txt", "incompatible loop work\n")
        self.git(["push", "origin", "loop/main"])
        result = self.retry([self.locked, {"body": self.review}, self.merge_park, self.reply])
        self.assertEqual([s["role"] for s in self.sessions], ["builder"])
        self.assertTrue(self.sessions[0]["merging"], "Leave the merge open for the builder")
        self.assertIn("conflicts in: app.txt", self.sessions[0]["prompt"])
        events = [json.loads(line) for line in Path(self.work, ".loop/events.jsonl").read_text().splitlines()]
        starts = [e["step"] for e in events if e.get("kind") == "step" and e.get("phase") == "start"]
        self.assertEqual(starts, ["conflicts"])
        self.assertEqual(result.status, "parked", result.reason)
        self.assertEqual(self.merges, [], "A conflicting catch-up must not reuse approval to merge")


if __name__ == "__main__":
    unittest.main()
