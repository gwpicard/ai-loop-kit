import contextlib
import io
import json
import os
import unittest

import tempfile

from lite.tests.helpers import FakeGh, copy_repo, make_repo, run_git
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
    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        cls.template = cls._dir.name
        work, _ = make_repo(cls.template, {
            "AGENTS.md": AGENTS, "app.py": "x = 1\n",
            "tests/test_old.py": "old\n", "tests/test_locked.py": "tests\n"})
        run_git(["push", "origin", "main:loop/main"], work)

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def setUp(self):
        super().setUp()
        self.work, self.origin = copy_repo(self.template, self.tmp)

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

    def rules(self, sha=None, lists=(), issue=ISSUE, extra=()):
        """lists: what each successive `pr list` returns, as (state) or None."""
        seq = [ok(json.dumps([] if st is None else [
            {"number": 7, "state": st, "headRefOid": oid or sha,
             "mergeCommit": {"oid": "abc123"} if st == "MERGED" else None}]))
            for st, oid in [x if isinstance(x, tuple) else (x, None)
                            for x in lists]] or [ok("[]")]
        self.scenario(list(extra) + [
            rule("issue view 1 --json body", ok(json.dumps(issue))),
            rule("issue view 1 --json state", ok('{"state": "CLOSED"}')),
            rule("pr list", *seq),
            rule("pr create", ok("https://example/pull/7")),
            rule("pr comment", ok()),
            rule("pr merge", ok()),
            rule("--json comments", ok('{"comments": []}')),
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
        self.rules(sha, [None, "OPEN", "MERGED"])
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
        self.assert_parked(sha, "existing test file changed")

    def test_existing_test_deleted(self):
        sha = self.branch({}, remove=["tests/test_old.py"])
        self.assert_parked(sha, "existing test file changed")

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
        self.rules(sha, [None, "OPEN", "MERGED"], issue=issue)
        r = self.run_merge(sha)
        self.assertTrue(r.ok, r.reason)

    def test_pr_exists_no_second_create(self):
        sha = self.good()
        self.rules(sha, ["OPEN", "MERGED"])
        r = self.run_merge(sha)
        self.assertTrue(r.ok, r.reason)
        self.assertNotIn("pr create", self.names())

    def test_merge_fails_but_merged(self):
        sha = self.good()
        self.rules(sha, ["OPEN", "MERGED"], extra=[rule("pr merge", fail("HTTP 502"))])
        r = self.run_merge(sha)
        self.assertTrue(r.ok, r.reason)
        self.assertEqual(self.names().count("pr merge"), 1)

    def test_merge_fails_not_merged(self):
        sha = self.good()
        self.rules(sha, ["OPEN"], extra=[rule("pr merge", fail("not mergeable"))])
        r = self.run_merge(sha)
        self.assertFalse(r.ok)
        self.assertFalse(r.park)
        self.assertNotIn("issue close", self.names())

    def test_comment_already_posted_is_not_repeated(self):
        sha = self.good()
        text = verdict(sha)
        self.rules(sha, ["OPEN", "MERGED"], extra=[rule(
            "--json comments", ok(json.dumps({"comments": [{"body": text}]})))])
        r = self.run_merge(sha, text)
        self.assertTrue(r.ok, r.reason)
        self.assertNotIn("pr comment", self.names())

    def test_comment_fails_refuses_before_merge(self):
        sha = self.good()
        self.rules(sha, ["OPEN"], extra=[rule("pr comment", fail("HTTP 502"))])
        r = self.run_merge(sha)
        self.assertFalse(r.ok)
        self.assertNotIn("pr merge", self.names())

    def test_stale_merged_pr_not_trusted(self):
        sha = self.good()
        self.rules(sha, [("MERGED", "f" * 40), "OPEN", "MERGED"])
        r = self.run_merge(sha)
        self.assertTrue(r.ok, r.reason)
        self.assertIn("pr create", self.names())

    def test_rerun_after_branch_deleted(self):
        sha = self.good()
        run_git(["update-ref", "-d", "refs/heads/issue/1"], self.origin)
        self.rules(sha, ["MERGED"])
        r = self.run_merge(sha)
        self.assertTrue(r.ok, r.reason)
        self.assertNotIn("pr merge", self.names())

    def test_non_ascii_path_cannot_evade(self):
        sha = self.branch({"\u00e9t\u00e9/package.json": "{}\n"})
        self.assert_parked(sha, "lockfile")

    def test_case_variants_are_stops(self):
        sha = self.branch({".Claude/x": "x\n"})
        self.assert_parked(sha, ".claude")
        self.assertTrue(merge.is_test_file("Tests/x.py"))
        self.assertTrue(merge.is_test_file("TEST_a.PY"))

    def test_case_variant_settings_file(self):
        sha = self.branch({"config/Settings.json": "{}\n"})
        self.assert_parked(sha, "settings file")

    def test_type_change_of_test_file(self):
        run_git(["checkout", "-b", "issue/1", "main"], self.work)
        os.remove(os.path.join(self.work, "tests/test_old.py"))
        os.symlink("../app.py", os.path.join(self.work, "tests/test_old.py"))
        run_git(["add", "-A"], self.work)
        run_git(["commit", "-m", "link"], self.work)
        run_git(["push", "origin", "issue/1"], self.work)
        sha = common.git(["rev-parse", "HEAD"], cwd=self.work)
        run_git(["checkout", "main"], self.work)
        self.assert_parked(sha, "existing test file")

    def test_locked_paths_union_of_blocks(self):
        comments = [{"body": "TESTS:\na.py\n"}, {"body": "x\nTESTS:\nb.py\n"}]
        self.assertEqual(merge.locked_paths(comments), ["a.py", "b.py"])

    def test_timeout_kills_process_group(self):
        sha = self.good()
        with open(os.path.join(self.work, "AGENTS.md"), "w") as f:
            f.write("## Loop\nTest command: sleep 30\n")
        self.rules(sha)
        old, merge.TEST_TIMEOUT = merge.TEST_TIMEOUT, 1
        self.addCleanup(setattr, merge, "TEST_TIMEOUT", old)
        r = self.run_merge(sha)
        self.assertFalse(r.ok)
        self.assertIn("timed out", r.reason)

    def test_unexpected_error_is_a_refusal(self):
        sha = self.good()
        self.scenario([rule("issue view", ok("not json"))])
        r = self.run_merge(sha)
        self.assertFalse(r.ok)
        self.assertFalse(r.park)

    def test_cli_never_shows_traceback(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(merge.main(["x"]), 1)


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
