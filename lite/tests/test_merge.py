import json
import os
import unittest

from lite.tests.helpers import FakeGh, make_repo, run_git
import common
import merge

AGENTS = "## Loop\nTest command: test ! -f FAIL\nLoop branch: loop/main\n"
ISSUE = {"body": "Add a feature.", "comments": []}


def ok(stdout=""):
    return {"code": 0, "stdout": stdout}


def fail(stderr="boom"):
    return {"code": 1, "stderr": stderr}


def rule(match, *responses):
    return {"match": match, "responses": list(responses)}


def verdict(sha, word="APPROVE"):
    return "Looks fine.\n\nVERDICT: %s\nHEAD: %s\n\n1. nothing\n" % (word, sha)


class MergeTest(FakeGh):
    def setUp(self):
        super().setUp()
        self.work, self.origin = make_repo(self.tmp, {
            "AGENTS.md": AGENTS, "app.py": "x = 1\n",
            "tests/test_old.py": "old\n", "tests/test_locked.py": "tests\n"})
        run_git(["push", "origin", "main:loop/main"], self.work)

    def branch(self, files, remove=()):
        run_git(["checkout", "-b", "issue/1", "main"], self.work)
        for name, text in files.items():
            path = os.path.join(self.work, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(text)
        for name in remove:
            run_git(["rm", name], self.work)
        run_git(["add", "-A"], self.work)
        run_git(["commit", "-m", "work"], self.work)
        run_git(["push", "origin", "issue/1"], self.work)
        sha = common.git(["rev-parse", "HEAD"], cwd=self.work)
        run_git(["checkout", "main"], self.work)
        return sha

    def rules(self, issue=ISSUE, listing="[]", extra=()):
        self.scenario(list(extra) + [
            rule("issue view 1 --json body", ok(json.dumps(issue))),
            rule("pr list", ok(listing)),
            rule("pr create", ok("https://example/pull/7")),
            rule("pr comment", ok()),
            rule("pr merge", ok()),
            rule("--json state,mergeCommit",
                 ok('{"state": "MERGED", "mergeCommit": {"oid": "abc123"}}')),
            rule("issue close", ok()),
        ])

    def run_merge(self, sha, text=None):
        return merge.merge(1, "issue/1", text or verdict(sha), self.work)

    def names(self):
        return [" ".join(c[:2]) for c in self.calls()]

    def good(self):
        return self.branch({"app.py": "x = 2\n", "tests/test_new.py": "new\n"})

    def test_happy_path(self):
        sha = self.good()
        self.rules(listing="[]")
        # after create, the list shows the open pull request
        self.rules(extra=[rule("pr list", ok("[]"),
                               ok('[{"number": 7, "state": "OPEN"}]'))])
        r = self.run_merge(sha)
        self.assertTrue(r.ok, r.reason)
        self.assertEqual(r.commit, "abc123")
        calls = self.calls()
        merge_call = [c for c in calls if c[:2] == ["pr", "merge"]][0]
        self.assertIn("--match-head-commit", merge_call)
        self.assertIn(sha, merge_call)
        self.assertIn("--delete-branch", merge_call)
        comment = [c for c in calls if c[:2] == ["pr", "comment"]]
        self.assertEqual(len(comment), 1)
        close = [c for c in calls if c[:2] == ["issue", "close"]][0]
        self.assertIn("abc123", " ".join(close))
        with open(os.path.join(self.work, ".lite", "events.jsonl")) as f:
            events = f.read()
        self.assertIn('"merged"', events)
        self.assertEqual(common.git(["worktree", "list"], cwd=self.work).count("\n"), 0)

    def test_changes_verdict(self):
        sha = self.good()
        self.rules()
        r = self.run_merge(sha, verdict(sha, "CHANGES"))
        self.assertFalse(r.ok)
        self.assertFalse(r.park)
        self.assertIn("CHANGES", r.reason)
        self.assertEqual(self.calls(), [])

    def test_head_mismatch(self):
        sha = self.good()
        self.rules()
        r = self.run_merge(sha, verdict("0" * 40))
        self.assertFalse(r.ok)
        self.assertFalse(r.park)
        self.assertIn("not the reviewed commit", r.reason)

    def test_failing_tests(self):
        sha = self.branch({"FAIL": "x\n"})
        self.rules()
        r = self.run_merge(sha)
        self.assertFalse(r.ok)
        self.assertFalse(r.park)
        self.assertIn("Test command failed", r.reason)

    def assert_parked(self, sha, text, issue=ISSUE):
        self.rules(issue=issue)
        r = self.run_merge(sha)
        self.assertFalse(r.ok)
        self.assertTrue(r.park)
        self.assertIn(text, r.reason)
        self.assertNotIn("pr create", self.names())

    def test_protected_path(self):
        sha = self.branch({".githooks/pre-commit": "x\n"})
        self.assert_parked(sha, ".githooks/pre-commit")

    def test_workflow(self):
        sha = self.branch({".github/workflows/ci.yml": "x\n"})
        self.assert_parked(sha, "workflow")

    def test_lockfile(self):
        sha = self.branch({"sub/package.json": "{}\n"})
        self.assert_parked(sha, "lockfile")

    def test_settings_file(self):
        sha = self.branch({"config/settings.json": "{}\n"})
        self.assert_parked(sha, "settings file")

    def test_existing_test_modified(self):
        sha = self.branch({"tests/test_old.py": "changed\n"})
        self.assert_parked(sha, "existing test file modified")

    def test_existing_test_deleted(self):
        sha = self.branch({}, remove=["tests/test_old.py"])
        self.assert_parked(sha, "existing test file deleted")

    def test_locked_test_deleted(self):
        run_git(["checkout", "-b", "issue/1", "main"], self.work)
        with open(os.path.join(self.work, "tests/test_fresh.py"), "w") as f:
            f.write("fresh\n")
        run_git(["add", "-A"], self.work)
        run_git(["commit", "-m", "tests"], self.work)
        run_git(["rm", "tests/test_fresh.py"], self.work)
        run_git(["commit", "-m", "builder removed it"], self.work)
        with open(os.path.join(self.work, "tests/test_fresh.py"), "w") as f:
            f.write("fresh\n")
        run_git(["add", "-A"], self.work)
        run_git(["commit", "-m", "back"], self.work)
        with open(os.path.join(self.work, "tests/test_fresh.py"), "w") as f:
            f.write("weakened\n")
        run_git(["commit", "-am", "weaken"], self.work)
        run_git(["push", "origin", "issue/1"], self.work)
        sha = common.git(["rev-parse", "HEAD"], cwd=self.work)
        run_git(["checkout", "main"], self.work)
        issue = {"body": "x", "comments": [
            {"body": "Tests written.\n\nTESTS:\ntests/test_fresh.py\n"}]}
        self.assert_parked(sha, "locked test modified", issue)

    def test_locked_test_removed_at_head(self):
        run_git(["checkout", "-b", "issue/1", "main"], self.work)
        with open(os.path.join(self.work, "tests/test_fresh.py"), "w") as f:
            f.write("fresh\n")
        run_git(["add", "-A"], self.work)
        run_git(["commit", "-m", "tests"], self.work)
        run_git(["rm", "tests/test_fresh.py"], self.work)
        run_git(["commit", "-m", "gone"], self.work)
        run_git(["push", "origin", "issue/1"], self.work)
        sha = common.git(["rev-parse", "HEAD"], cwd=self.work)
        run_git(["checkout", "main"], self.work)
        issue = {"body": "x", "comments": [
            {"body": "TESTS:\n- `tests/test_fresh.py`\n"}]}
        self.assert_parked(sha, "locked test deleted", issue)

    def test_named_path_allowed(self):
        sha = self.branch({".github/workflows/ci.yml": "x\n",
                           "tests/test_old.py": "changed\n"})
        issue = {"body": "Change .github/workflows/ci.yml and tests/test_old.py",
                 "comments": []}
        self.rules(issue=issue, extra=[rule("pr list", ok("[]"),
                   ok('[{"number": 7, "state": "OPEN"}]'))])
        r = self.run_merge(sha)
        self.assertTrue(r.ok, r.reason)

    def test_pr_exists_no_second_create(self):
        sha = self.good()
        self.rules(listing='[{"number": 7, "state": "OPEN"}]')
        r = self.run_merge(sha)
        self.assertTrue(r.ok, r.reason)
        self.assertNotIn("pr create", self.names())

    def test_merge_fails_but_merged(self):
        sha = self.good()
        self.rules(listing='[{"number": 7, "state": "OPEN"}]',
                   extra=[rule("pr merge", fail("HTTP 502"))])
        r = self.run_merge(sha)
        self.assertTrue(r.ok, r.reason)
        self.assertEqual(self.names().count("pr merge"), 1)

    def test_merge_fails_not_merged(self):
        sha = self.good()
        self.rules(listing='[{"number": 7, "state": "OPEN"}]', extra=[
            rule("pr merge", fail("not mergeable")),
            rule("--json state,mergeCommit", ok('{"state": "OPEN"}'))])
        r = self.run_merge(sha)
        self.assertFalse(r.ok)
        self.assertFalse(r.park)
        self.assertNotIn("issue close", self.names())

    def test_comment_fails_then_exists(self):
        sha = self.good()
        text = verdict(sha)
        self.rules(listing='[{"number": 7, "state": "OPEN"}]', extra=[
            rule("pr comment", fail("HTTP 502")),
            rule("--json comments", ok(json.dumps(
                {"comments": [{"body": text}]})))])
        r = self.run_merge(sha, text)
        self.assertTrue(r.ok, r.reason)
        self.assertEqual(self.names().count("pr comment"), 1)

    def test_comment_fails_and_missing(self):
        sha = self.good()
        self.rules(listing='[{"number": 7, "state": "OPEN"}]', extra=[
            rule("pr comment", fail("HTTP 502")),
            rule("--json comments", ok('{"comments": []}'))])
        r = self.run_merge(sha)
        self.assertFalse(r.ok)
        self.assertNotIn("pr merge", self.names())


class ParkTest(FakeGh):
    def test_park(self):
        self.scenario([rule("issue", ok())])
        common.park(5, "Which one?", "The first.")
        calls = self.calls()
        self.assertEqual(calls[0][:5], ["issue", "edit", "5", "--add-label", "needs-user"])
        self.assertEqual(calls[1][-2:], ["--remove-label", "building"])
        self.assertEqual(calls[2][:2], ["issue", "comment"])


if __name__ == "__main__":
    unittest.main()
