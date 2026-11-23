"""Build recovery preserves commits left on a parked issue branch."""
import json
from pathlib import Path
import unittest
from unittest import mock

import common
import flow
from kit.tests.helpers import FakeGh


class UnpushedCommitsTest(FakeGh):
    def setUp(self):
        super().setUp()
        self.work = Path(self.tmp, "project")
        self.origin = Path(self.tmp, "origin.git")
        self.git(["init", "--bare", "--template=", str(self.origin)], cwd=self.tmp)
        self.git(["init", "--template=", "-b", "loop/main", str(self.work)], cwd=self.tmp)
        self.git(["config", "user.name", "Test"])
        self.git(["config", "user.email", "test@example.com"])
        self.git(["remote", "add", "origin", str(self.origin)])
        Path(self.work, "loop.json").write_text(json.dumps({
            "Test command": "python3 tests/test_saved.py"}))
        Path(self.work, "tests").mkdir()
        Path(self.work, "tests/test_saved.py").write_text("assert False, 'Not built yet'\n")
        self.git(["add", "loop.json", "tests/test_saved.py"])
        self.git(["commit", "-qm", "Initial project"])
        self.git(["push", "origin", "loop/main"])
        self.base = self.git(["rev-parse", "HEAD"])
        self.scenario([
            {"match": "issue view 7", "responses": [{"stdout": json.dumps({
                "title": "Keep builder work", "body": "Preserve committed work.",
                "comments": [{"body": "TESTS:\ntests/test_saved.py"}]})}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "issue comment", "responses": [{}]},
            {"match": "issue edit", "responses": [{}]},
        ])

    def git(self, args, cwd=None, **kwargs):
        return common.git(args, cwd=str(cwd or self.work), **kwargs)

    def remote_head(self):
        return self.git(["rev-parse", "--verify", "refs/heads/issue/7"],
                        cwd=self.origin, check=False)

    def build(self, run):
        with mock.patch.object(flow.session, "run", side_effect=run):
            result = flow.build(7, str(self.work))
        self.assertEqual(result.status, "parked", result.reason)
        return result

    def parked_local_commit(self, remote):
        if remote:
            self.git(["push", "origin", "HEAD:issue/7"])
        saved = []

        def builder(role, prompt, tree, *args, **kwargs):
            if role == "test-writer":
                return "TESTS:\ntests/test_saved.py", "writer-session"
            self.assertEqual(role, "builder")
            Path(tree, "builder.txt").write_text("Keep this builder work.\n")
            self.git(["add", "builder.txt"], cwd=tree)
            self.git(["commit", "-qm", "Builder work before parking"], cwd=tree)
            saved.append(self.git(["rev-parse", "HEAD"], cwd=tree))
            return "PARK: Choose the next task? | Continue later", "parked-session"

        # Reproduce a park from a released runner that did not push on parking.
        # Only this fixture suppresses pushes; the resumed build uses real Git.
        real_git = common.git

        def old_runner(args, *positional, **kwargs):
            return "" if args[0] == "push" else real_git(args, *positional, **kwargs)

        with mock.patch.object(common, "git", side_effect=old_runner), \
                mock.patch.object(flow, "git", side_effect=old_runner):
            self.build(builder)
        self.assertEqual(len(saved), 1)
        self.assertEqual(self.git(["rev-parse", "issue/7"]), saved[0])
        self.assertEqual(self.remote_head(), self.base if remote else "")
        return saved[0]

    def observe_resume(self):
        observed = []

        def session(role, prompt, tree, *args, **kwargs):
            observed.append((self.git(["rev-parse", "HEAD"], cwd=tree), self.remote_head(),
                             Path(tree, "builder.txt").exists()))
            return "PARK: Choose the next task? | Continue later", "resumed-session"

        self.build(session)
        self.assertEqual(len(observed), 1)
        return observed[0]

    def advance_remote(self, parent):
        tree = self.git(["rev-parse", parent + "^{tree}"])
        commit = self.git(["commit-tree", tree, "-p", parent, "-m", "Remote work"])
        self.git(["push", "origin", commit + ":refs/heads/issue/7"])
        return commit

    def test_resume_keeps_and_pushes_local_commits_ahead_of_remote_before_session(self):
        saved = self.parked_local_commit(remote=True)
        self.assertEqual(self.observe_resume(), (saved, saved, True),
                         "The resumed session must see the local commit already on the remote")

    def test_resume_keeps_and_pushes_local_commits_without_remote_before_session(self):
        saved = self.parked_local_commit(remote=False)
        self.assertEqual(self.observe_resume(), (saved, saved, True),
                         "A missing remote branch must not discard the parked local commit")

    def test_divergence_backs_up_local_branch_and_logs_its_name(self):
        saved = self.parked_local_commit(remote=True)
        remote = self.advance_remote(self.base)
        observed = self.observe_resume()
        self.assertEqual(observed, (remote, remote, False))
        backups = self.git(["for-each-ref", "--format=%(refname:short)",
                            "refs/heads/issue/7-local-*"]).splitlines()
        self.assertEqual(len(backups), 1, "Divergence must retain one named backup branch")
        self.assertRegex(backups[0], r"^issue/7-local-\d[\dTtZz._:+-]*$")
        self.assertEqual(self.git(["rev-parse", backups[0]]), saved)
        log = Path(self.work, ".loop/loop.out")
        lines = log.read_text().splitlines() if log.exists() else []
        self.assertEqual(len([line for line in lines if backups[0] in line]), 1,
                         "loop.out must name the retained branch on one line")

    def test_equal_local_and_remote_still_start_from_remote(self):
        self.git(["branch", "issue/7", self.base])
        self.git(["push", "origin", "issue/7"])
        self.assertEqual(self.observe_resume(), (self.base, self.base, False))
        self.assertEqual(self.git(["branch", "--list", "issue/7-local-*"]), "")

    def test_local_branch_behind_remote_still_starts_from_remote(self):
        self.git(["branch", "issue/7", self.base])
        self.git(["push", "origin", "issue/7"])
        remote = self.advance_remote(self.base)
        self.assertEqual(self.observe_resume(), (remote, remote, False))
        self.assertEqual(self.git(["branch", "--list", "issue/7-local-*"]), "")

    def test_park_pushes_committed_work_before_posting_the_park(self):
        self.git(["push", "origin", "HEAD:issue/7"])
        saved, at_park = [], []
        real_park = common.park

        def builder(role, prompt, tree, *args, **kwargs):
            self.assertEqual(role, "builder")
            Path(tree, "builder.txt").write_text("Work committed before the park.\n")
            self.git(["add", "builder.txt"], cwd=tree)
            self.git(["commit", "-qm", "Builder work"], cwd=tree)
            saved.append(self.git(["rev-parse", "HEAD"], cwd=tree))
            return "PARK: Choose the next task? | Continue later", "parked-session"

        def park(*args, **kwargs):
            at_park.append(self.remote_head())
            return real_park(*args, **kwargs)

        with mock.patch.object(common, "park", side_effect=park):
            self.build(builder)
        self.assertEqual(len(saved), 1)
        self.assertEqual(at_park, saved, "Push committed work before publishing the park")
        self.assertEqual(self.remote_head(), saved[0])


if __name__ == "__main__":
    unittest.main()
