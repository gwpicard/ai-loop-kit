import json
import os
import unittest
from unittest import mock

from lite.tests.fake_claude import FakeClaudeGh
from lite.tests.helpers import make_repo, run_git
import common
import flow
import merge

AGENTS = "## Loop\nTest command: test ! -f FAIL\nLoop branch: loop/main\nMax rounds: 2\n"
MERGED = merge.Result(True, False, "merged as abc", "abc")
APPROVE = {"reply": "All good.\n\nVERDICT: APPROVE\nHEAD: {HEAD}\n\n1. none"}
CHANGES = {"reply": "VERDICT: CHANGES\nHEAD: {HEAD}\n\n1. Handle the empty case"}
WRITER = {"files": {"tests/test_new.py": "x\n"}, "reply": "Done.\nTESTS:\ntests/test_new.py"}


def roles(calls):
    return [c["role"] for c in calls]


class FlowTest(FakeClaudeGh):
    def setUp(self):
        super().setUp()
        self.work, self.origin = make_repo(self.tmp, {"AGENTS.md": AGENTS})
        run_git(["push", "origin", "main:loop/main"], self.work)
        self.scenario([
            {"match": "issue view 7", "responses": [
                {"stdout": json.dumps({"title": "Add it", "body": "Do the thing."})}]},
            {"match": "issue comment", "responses": [{}]},
            {"match": "issue edit", "responses": [{}]}])
        patch = mock.patch.object(merge, "merge", return_value=MERGED)
        self.merge = patch.start()
        self.addCleanup(patch.stop)

    def build(self, replies=()):
        return flow.build(7, self.work, replies)

    def build_scenario(self, **steps):
        base = {"test-writer": [WRITER], "builder": [{"files": {"app.py": "1\n"}}],
                "reviewer": [APPROVE]}
        base.update(steps)
        self.claude(base)

    def test_happy_path(self):
        self.build_scenario()
        r = self.build(["Use the env var."])
        self.assertEqual(r, flow.Result("merged", "merged as abc"))
        calls = self.claude_calls()
        self.assertEqual(roles(calls), ["test-writer", "builder", "simplify", "reviewer"])
        builder = calls[1]
        self.assertEqual(builder["env"]["LITE_LOCKED"], "tests/test_new.py")
        self.assertIn("Add it", builder["prompt"])
        self.assertIn("Do the thing.", builder["prompt"])
        self.assertIn("PLAN.md", builder["prompt"])
        self.assertIn("Use the env var.", builder["prompt"])
        self.assertIn("Work autonomously", builder["prompt"])
        self.assertIn("The builder's last report", calls[3]["prompt"])
        self.assertIn("git diff origin/loop/main...HEAD", calls[3]["prompt"].replace(
            "<loop branch>", "loop/main"))
        self.assertTrue(any(c[:2] == ["issue", "comment"] for c in self.calls()))
        self.merge.assert_called_once()
        self.assertEqual(self.merge.call_args[0][:2], (7, "issue/7"))
        pushed = common.git(["ls-remote", "--heads", self.origin, "issue/7"])
        self.assertIn("refs/heads/issue/7", pushed)
        self.assertNotIn(".lite-worktrees", common.git(["worktree", "list"], cwd=self.work))

    def test_changes_then_approve(self):
        self.build_scenario(reviewer=[CHANGES, APPROVE], builder=[
            {"files": {"app.py": "1\n"}}, {"files": {"app.py": "2\n"}}])
        self.assertEqual(self.build().status, "merged")
        calls = self.claude_calls()
        self.assertEqual(roles(calls), ["test-writer", "builder", "simplify", "reviewer",
                                        "builder", "simplify", "reviewer"])
        fix = calls[4]
        self.assertIn("--resume", fix["argv"])
        self.assertIn("Handle the empty case", fix["prompt"])
        self.assertNotIn("--resume", calls[6]["argv"])

    def test_failing_test_command_resumes_builder(self):
        self.build_scenario(builder=[{"files": {"FAIL": "x\n"}}, {"remove": ["FAIL"]}])
        self.assertEqual(self.build().status, "merged")
        calls = self.claude_calls()
        self.assertEqual(roles(calls), ["test-writer", "builder", "simplify", "builder",
                                        "simplify", "reviewer"])
        self.assertIn("--resume", calls[3]["argv"])
        self.assertIn("Test command failed", calls[3]["prompt"])

    def test_round_limit_parks(self):
        self.build_scenario(reviewer=[CHANGES])
        r = self.build()
        self.assertEqual(r.status, "parked", r.reason)
        self.assertIn("2 rounds", r.reason)
        self.assertEqual(roles(self.claude_calls()).count("reviewer"), 2)
        self.merge.assert_not_called()
        labels = [c for c in self.calls() if c[:2] == ["issue", "edit"]]
        self.assertTrue(any("needs-user" in c for c in labels))

    def test_merge_park_parks(self):
        self.merge.return_value = merge.Result(False, True, "protected path .github/", None)
        self.build_scenario()
        r = self.build()
        self.assertEqual(r.status, "parked", r.reason)
        self.assertIn("protected path", r.reason)
        self.assertEqual(roles(self.claude_calls()).count("reviewer"), 1)

    def test_refused_merge_counts_as_a_round(self):
        self.merge.side_effect = [merge.Result(False, False, "head moved", None), MERGED]
        self.build_scenario()
        self.assertEqual(self.build().status, "merged")
        calls = self.claude_calls()
        self.assertIn("head moved", calls[4]["prompt"])
        self.assertEqual(roles(calls).count("reviewer"), 2)

    def test_stop_line_from_a_session_parks(self):
        self.build_scenario(builder=[{"reply": "PARK: Need an API key | Add it as a secret"}])
        r = self.build()
        self.assertEqual((r.status, r.reason), ("parked", "Need an API key"))
        self.assertEqual(roles(self.claude_calls()), ["test-writer", "builder"])

    def test_session_crash_fails_and_cleans_up(self):
        self.build_scenario(builder=[{"crash": True}])
        r = self.build()
        self.assertEqual(r.status, "failed")
        self.assertIn("builder session", r.reason)
        self.assertNotIn(".lite-worktrees", common.git(["worktree", "list"], cwd=self.work))

    def test_reuses_an_existing_origin_branch(self):
        run_git(["push", "origin", "main:issue/7"], self.work)
        self.build_scenario()
        self.assertEqual(self.build().status, "merged")

    def test_parse_tests(self):
        self.assertEqual(flow.parse_tests("a\nTESTS:\n- t/a.py\n`t/b.py`\n\nbye"),
                         ["t/a.py", "t/b.py"])
        self.assertEqual(flow.parse_tests("no block"), [])


if __name__ == "__main__":
    unittest.main()
