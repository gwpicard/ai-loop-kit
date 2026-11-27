"""Reopened issues rebuild after a revert; interrupted merges still recover."""
import json
from pathlib import Path
import shlex
import sys
import unittest
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git
import common
import flow
import merge


MERGED_AT = "2026-01-02T12:00:00Z"
REOPENED_AT = "2026-01-03T09:00:00Z"
REAL_GIT = common.git
REAL_SESSION = flow.session.run


class ReopenedAfterRevertTest(FakeClaudeGh):
    def setUp(self):
        super().setUp()
        command = shlex.quote(sys.executable) + " -m unittest discover -s tests"
        self.work, self.origin = make_repo(self.tmp, {
            "loop.json": json.dumps({"Test command": command, "Loop branch": "loop/main"}),
            "tests/test_base.py": "import unittest\n",
        })
        run_git(["switch", "-c", "issue/7"], self.work)
        Path(self.work, "feature.txt").write_text("previous implementation\n")
        run_git(["add", "feature.txt"], self.work)
        run_git(["commit", "-qm", "Previous implementation"], self.work)
        self.old_head = REAL_GIT(["rev-parse", "HEAD"], cwd=self.work)
        run_git(["push", "origin", "issue/7"], self.work)
        run_git(["switch", "-c", "loop/main", "main"], self.work)
        run_git(["merge", "--squash", "issue/7"], self.work)
        run_git(["commit", "-qm", "Merge previous implementation"], self.work)
        self.old_merge = REAL_GIT(["rev-parse", "HEAD"], cwd=self.work)
        run_git(["push", "origin", "loop/main"], self.work)
        run_git(["switch", "main"], self.work)
        self.old_pr = {"number": 9, "state": "MERGED", "headRefName": "issue/7",
                       "baseRefName": "loop/main", "headRefOid": self.old_head,
                       "mergedAt": MERGED_AT, "mergeCommit": {"oid": self.old_merge},
                       "files": [{"path": "feature.txt"}]}
        self.timeline = [{"event": "closed", "created_at": MERGED_AT}]
        self.comments = []
        self.issue_state = "OPEN"
        self.new_pr = None
        self.sent = []
        self.git_calls = []
        self.starts = []
        for module in (common, flow, merge):
            patch = mock.patch.object(module, "gh", side_effect=self.github)
            patch.start()
            self.addCleanup(patch.stop)
            patch = mock.patch.object(module, "git", side_effect=self.git)
            patch.start()
            self.addCleanup(patch.stop)

    def git(self, args, **kwargs):
        self.git_calls.append(list(args))
        return REAL_GIT(args, **kwargs)

    def github(self, args, **kwargs):
        """Keep PR history and issue state at the GitHub boundary."""
        self.sent.append((list(args), kwargs.get("input", "")))
        if args[0] == "api" and any("/issues/7/timeline" in a for a in args):
            return self.timeline if isinstance(self.timeline, str) else json.dumps(self.timeline)
        if args[:2] == ["issue", "view"]:
            return json.dumps({"title": "Restore the feature", "body": "Build the feature again.",
                               "state": self.issue_state, "comments": self.comments})
        if args[:2] == ["issue", "comment"]:
            self.comments.append({"body": kwargs["input"]})
            return ""
        if args[:2] == ["issue", "close"]:
            self.issue_state = "CLOSED"
            return ""
        if args[:2] == ["issue", "edit"] or args[:2] == ["pr", "edit"]:
            return ""
        if args[:2] == ["pr", "list"]:
            prs = [self.old_pr] + ([self.new_pr] if self.new_pr else [])
            for flag, field in (("--head", "headRefName"), ("--base", "baseRefName")):
                if flag in args:
                    prs = [p for p in prs if p[field] == args[args.index(flag) + 1]]
            state = args[args.index("--state") + 1] if "--state" in args else "open"
            return json.dumps([p for p in prs if state == "all" or p["state"].lower() == state])
        if args[:2] == ["pr", "view"]:
            pr = self.old_pr if str(args[2]) == "9" else self.new_pr
            return json.dumps(dict(pr, comments=[]))
        if args[:2] == ["pr", "create"]:
            branch = args[args.index("--head") + 1]
            base = args[args.index("--base") + 1]
            head = REAL_GIT(["rev-parse", "origin/" + branch], cwd=self.work)
            self.new_pr = {"number": 10, "state": "OPEN", "headRefName": branch,
                           "baseRefName": base, "headRefOid": head, "mergeCommit": None}
            return "https://example.test/pull/10"
        if args[:2] == ["pr", "comment"]:
            return ""
        if args[:2] == ["pr", "merge"]:
            self.assertIsNotNone(self.new_pr, "The rebuild must create a new pull request")
            self.assertEqual(str(args[2]), str(self.new_pr["number"]))
            self.assertEqual(args[args.index("--match-head-commit") + 1],
                             self.new_pr["headRefOid"])
            with common.scratch_tree(self.work, "origin/" + self.new_pr["baseRefName"]) as tree:
                run_git(["merge", "--squash", "origin/" + self.new_pr["headRefName"]], tree)
                run_git(["commit", "-qm", "Merge rebuilt feature"], tree)
                commit = REAL_GIT(["rev-parse", "HEAD"], cwd=tree)
                run_git(["push", "origin", "HEAD:" + self.new_pr["baseRefName"]], tree)
            self.new_pr.update(state="MERGED", mergeCommit={"oid": commit},
                               mergedAt="2026-01-04T12:00:00Z")
            return ""
        self.fail("Unexpected GitHub call: " + repr(args))

    def revert_and_reopen(self):
        run_git(["switch", "loop/main"], self.work)
        run_git(["revert", "--no-edit", self.old_merge], self.work)
        Path(self.work, "current.txt").write_text("work added after the revert\n")
        run_git(["add", "current.txt"], self.work)
        run_git(["commit", "-qm", "Advance the loop branch"], self.work)
        run_git(["push", "origin", "loop/main"], self.work)
        self.loop_head = REAL_GIT(["rev-parse", "HEAD"], cwd=self.work)
        run_git(["switch", "main"], self.work)
        self.timeline.append({"event": "reopened", "created_at": REOPENED_AT})

    def build(self):
        def session(*args, **kwargs):
            tree = args[2]
            self.starts.append({"role": args[0],
                                "head": REAL_GIT(["rev-parse", "HEAD"], cwd=tree),
                                "branch": REAL_GIT(["branch", "--show-current"], cwd=tree),
                                "feature": Path(tree, "feature.txt").exists(),
                                "current": Path(tree, "current.txt").exists()})
            return REAL_SESSION(*args, **kwargs)

        with mock.patch.object(flow.session, "run", side_effect=session):
            return flow.build(7, self.work)

    def built_notes(self):
        return [body for args, body in self.sent
                if args[:2] == ["issue", "comment"] and body.startswith("## Built")]

    def test_reopening_after_the_merge_does_not_close_or_note_the_old_merge(self):
        self.revert_and_reopen()
        events = list(self.timeline)
        for timeline in (events, json.dumps([{"event": "reopened", "created_at":
                                              "2026-01-01T09:00:00Z"}]) + "\n" + json.dumps(events)):
            with self.subTest(timeline=timeline):
                self.timeline = timeline
                self.sent.clear()
                self.starts.clear()
                self.comments.clear()
                self.issue_state = "OPEN"
                self.claude({"test-writer": [{"reply": "PARK: Which feature variant? | Keep the original."}]})
                result = self.build()
                self.assertEqual(self.issue_state, "OPEN",
                                 "An old merge must not close an issue reopened after it")
                self.assertFalse(self.built_notes(), "The reverted merge must not get a new build note")
                self.assertFalse(any(args[:2] == ["pr", "edit"] for args, _ in self.sent),
                                 "The reverted pull request must not be rewritten as a completed build")
                self.assertTrue(self.starts, "The reopened issue must reach a build session")
                self.assertEqual(result.status, "parked", result.reason)

    def test_rebuild_starts_at_current_loop_head_and_merges_a_new_pull_request(self):
        self.revert_and_reopen()
        self.comments = [{"body": "## Built\n\nPrevious implementation.\n\n" + common.MARKER}]
        self.claude({
            "test-writer": [{"files": {"tests/test_rebuilt.py":
                "from pathlib import Path\nimport unittest\n\n"
                "class FeatureTest(unittest.TestCase):\n"
                "    def test_feature(self):\n"
                "        self.assertTrue(Path('feature.txt').is_file())\n"},
                "reply": "TESTS:\ntests/test_rebuilt.py"}],
            "builder": [{"files": {"feature.txt": "rebuilt implementation\n"},
                         "reply": "BUILT:\nRestored the feature.\nDEVIATIONS:\nnone"}],
            "reviewer": [{"reply": "VERDICT: APPROVE\nHEAD: {HEAD}\n"}],
        })
        result = self.build()
        self.assertTrue(self.starts, "The old merged pull request must not bypass the rebuild")
        start = self.starts[0]
        self.assertEqual(start["head"], self.loop_head, "Rebuild from the current loop branch")
        self.assertNotEqual(start["branch"], "issue/7", "Keep the old merged branch history intact")
        self.assertFalse(start["feature"], "The reverted implementation must be absent at build start")
        self.assertTrue(start["current"], "The rebuild must include work added since the revert")
        self.assertEqual(result.status, "merged", result.reason)
        self.assertIsNotNone(self.new_pr, "Create a new pull request for the rebuild")
        self.assertEqual(self.new_pr["headRefName"], start["branch"])
        self.assertEqual((self.new_pr["baseRefName"], self.new_pr["state"]), ("loop/main", "MERGED"))
        remote_old = REAL_GIT(["ls-remote", "--heads", self.origin, "issue/7"], cwd=self.work)
        self.assertEqual(remote_old.split()[0], self.old_head, "Do not rewrite the old remote branch")
        new_head = self.new_pr["headRefOid"]
        self.assertIn(self.old_head, REAL_GIT(["rev-list", new_head + ".." + self.old_head], cwd=self.work),
                      "The new branch must not merge the old issue branch history back in")
        pushes = [args for args in self.git_calls if args[0] == "push"]
        self.assertTrue(pushes, "The real build path must push its new branch")
        for args in pushes:
            self.assertFalse(any(a in ("-f", "--force", "--force-with-lease", "--mirror", "--all")
                                 or a.startswith(("--force=", "--force-with-lease=", "+")) for a in args),
                             "The rebuild must merge without a force-push: " + repr(args))
        landed = REAL_GIT(["rev-parse", "refs/heads/loop/main"], cwd=self.origin)
        self.assertEqual(landed, self.new_pr["mergeCommit"]["oid"])
        self.assertEqual(REAL_GIT(["show", landed + ":feature.txt"], cwd=self.origin),
                         "rebuilt implementation")
        self.assertEqual(REAL_GIT(["show", landed + ":current.txt"], cwd=self.origin),
                         "work added after the revert")
        self.assertEqual(self.issue_state, "CLOSED")
        self.assertEqual(len(self.built_notes()), 1)
        self.assertIn(landed, self.built_notes()[0])

    def test_crash_after_merge_without_reopening_posts_the_note_and_closes(self):
        result = self.build()
        self.assertEqual(result.status, "merged", result.reason)
        self.assertFalse(self.starts, "Recover a completed merge without starting another build")
        self.assertEqual(self.issue_state, "CLOSED")
        self.assertEqual(len(self.built_notes()), 1)
        self.assertIn(self.old_merge, self.built_notes()[0])
        self.assertIsNone(self.new_pr)
        self.assertFalse(any(args[0] == "push" for args in self.git_calls))


if __name__ == "__main__":
    unittest.main()
