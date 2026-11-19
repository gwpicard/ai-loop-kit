"""A PLAN.md conflict where both sides only added lines is resolved by the loop."""
import json
import os
import tempfile
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import copy_repo, make_repo, run_git
import common
import flow
import merge

AGENTS = "## Loop\nTest command: true\nLoop branch: loop/main\nMax rounds: 2\n"
BASE_PLAN = "# Plan\n\n## Deviations\n\n- base line\n"
APPROVE = {"reply": "All good.\n\nVERDICT: APPROVE\nHEAD: {HEAD}\n\n1. none"}
MERGED = merge.Result(True, False, "merged as abc", "abc")
SETTINGS = {"Loop branch": "loop/main"}


class PlanAdditionsConflict(FakeClaudeGh):
    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        cls.template = cls._dir.name
        work, _ = make_repo(cls.template, {"AGENTS.md": AGENTS, "PLAN.md": BASE_PLAN, "other.txt": "base\n"})
        run_git(["push", "origin", "main:loop/main"], work)

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def setUp(self):
        super().setUp()
        self.work, self.origin = copy_repo(self.template, self.tmp)
        self.scenario([
            {"match": "issue view 7", "responses": [{"stdout": json.dumps({
                "title": "Add it", "body": "Do it.", "comments": [{"body": "TESTS:\ntests/test_new.py\n"}]})}]},
            {"match": "issue comment", "responses": [{}]}, {"match": "issue edit", "responses": [{}]},
            {"match": "issue create", "responses": [{}]}, {"match": "issue close", "responses": [{}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]}, {"match": "pr edit", "responses": [{}]},
            {"match": "issue list", "responses": [{"stdout": "[]"}]}])
        for name, value in (("find_pr", {"number": 9}),):
            p = mock.patch.object(merge, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def push_side(self, branch, files):
        run_git(["checkout", "-q", "-b", "side-" + branch.replace("/", "-"), "main"], self.work)
        for name, text in files.items():
            with open(os.path.join(self.work, name), "w") as f:
                f.write(text)
        run_git(["add", "-A"], self.work)
        run_git(["commit", "-qm", "side " + branch], self.work)
        run_git(["push", "origin", "HEAD:" + branch], self.work)
        run_git(["checkout", "-q", "main"], self.work)

    def sides(self, mine, theirs):
        self.push_side("issue/7", mine)
        self.push_side("loop/main", theirs)

    def additions(self):
        self.sides({"PLAN.md": BASE_PLAN + "- builder line\n"}, {"PLAN.md": BASE_PLAN + "- loop line\n"})

    def reworded(self):
        self.sides({"PLAN.md": BASE_PLAN.replace("base line", "builder rewording")},
                   {"PLAN.md": BASE_PLAN + "- loop line\n"})

    def two_files(self):
        self.sides({"PLAN.md": BASE_PLAN + "- builder line\n", "other.txt": "mine\n"},
                   {"PLAN.md": BASE_PLAN + "- loop line\n", "other.txt": "theirs\n"})

    # the start of a build on a reused branch

    def build(self, *steps):
        self.claude({"builder": list(steps) + [{"files": {"extra.py": "1\n"}}], "reviewer": [APPROVE]})
        with mock.patch.object(merge, "merge", return_value=MERGED):
            return flow.build(7, self.work)

    def builder_prompts(self):
        return [c["prompt"] for c in self.claude_calls() if c["role"] == "builder"]

    def test_build_keeps_both_added_lines_without_a_builder_session(self):
        self.additions()
        r = self.build()
        self.assertEqual(r.status, "merged", r.reason)
        self.assertFalse(any("First task" in p or "conflicts in" in p for p in self.builder_prompts()))
        plan = common.git(["show", "issue/7:PLAN.md"], cwd=self.origin)
        self.assertEqual(plan.splitlines()[-3:], ["- base line", "- loop line", "- builder line"])
        self.assertTrue(common.git(["log", "--merges", "--format=%s", "issue/7"], cwd=self.origin))

    def test_build_sends_a_reworded_line_to_the_builder(self):
        self.reworded()
        r = self.build({"files": {"PLAN.md": BASE_PLAN + "- resolved\n"}})
        self.assertEqual(r.status, "merged", r.reason)
        first = self.builder_prompts()[0]
        self.assertIn("First task", first)
        self.assertIn("conflicts in: PLAN.md", first)

    def test_build_sends_plan_and_another_file_to_the_builder(self):
        self.two_files()
        r = self.build({"files": {"PLAN.md": BASE_PLAN + "- resolved\n", "other.txt": "both\n"}})
        self.assertEqual(r.status, "merged", r.reason)
        first = self.builder_prompts()[0]
        self.assertIn("First task", first)
        self.assertIn("PLAN.md", first)
        self.assertIn("other.txt", first)

    # land

    def tree(self):
        path = os.path.join(self.tmp, "tree")
        run_git(["fetch", "-q", "origin"], self.work)
        run_git(["worktree", "add", "-q", "-B", "issue/7", path, "origin/issue/7"], self.work)
        return path

    def land(self, t):
        old = common.git(["rev-parse", "HEAD"], cwd=t)
        review = "VERDICT: APPROVE\nHEAD: %s\n" % old
        with mock.patch.object(merge, "merge", return_value=MERGED) as m:
            return flow.land(7, "issue/7", review, self.work, t, SETTINGS), m

    def test_land_keeps_both_added_lines_pushes_and_updates_the_head(self):
        self.additions()
        t = self.tree()
        landed, m = self.land(t)
        self.assertEqual(landed.conflicts, [])
        m.assert_called_once()
        with open(os.path.join(t, "PLAN.md")) as f:
            self.assertEqual(f.read().splitlines()[-3:], ["- base line", "- loop line", "- builder line"])
        head = common.git(["rev-parse", "HEAD"], cwd=t)
        self.assertEqual(landed.head, head)
        self.assertEqual(common.git(["rev-parse", "issue/7"], cwd=self.origin), head)
        self.assertIn("HEAD: " + head, landed.review)
        self.assertEqual(len(common.git(["log", "-1", "--format=%P"], cwd=t).split()), 2)

    def test_land_leaves_a_reworded_line_to_the_builder(self):
        self.reworded()
        landed, m = self.land(self.tree())
        self.assertEqual(landed.conflicts, ["PLAN.md"])
        m.assert_not_called()

    def test_land_leaves_plan_and_another_file_to_the_builder(self):
        self.two_files()
        landed, m = self.land(self.tree())
        self.assertEqual(sorted(landed.conflicts), ["PLAN.md", "other.txt"])
        m.assert_not_called()
