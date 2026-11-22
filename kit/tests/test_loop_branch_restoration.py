"""Exercise branch recovery through supervisor cycles and the issue merge gate."""
import contextlib
import json
import os
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest import mock

from kit.tests.helpers import make_repo, run_git
import common
import loop
import merge


class BranchRestorationTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.folder.cleanup)
        self.work, self.origin = make_repo(self.folder.name, {
            "loop.json": json.dumps({"Test command": "true", "Idle hours": 12}),
            "app.txt": "initial\n",
        })
        self.base = common.git(["rev-parse", "HEAD"], cwd=self.work)
        run_git(["checkout", "-b", "loop/main"], self.work)
        Path(self.work, "unmerged.txt").write_text("work absent from the default branch\n")
        run_git(["add", "unmerged.txt"], self.work)
        run_git(["commit", "-m", "unmerged loop work"], self.work)
        self.old_head = common.git(["rev-parse", "HEAD"], cwd=self.work)
        run_git(["push", "origin", "HEAD:loop/main"], self.work)
        run_git(["checkout", "main"], self.work)
        self.runtime = Path(self.work, ".loop")
        self.runtime.mkdir(exist_ok=True)
        self.push_log = Path(self.folder.name, "pushes")
        hook = Path(self.origin, "hooks", "update")
        hook.parent.mkdir(exist_ok=True)
        hook.write_text('#!/bin/sh\nprintf "%s %s %s\\n" "$1" "$2" "$3" >> '
                        + shlex.quote(str(self.push_log)) + "\n")
        hook.chmod(0o755)

    def remote_head(self):
        rows = common.git(["ls-remote", "--heads", "origin", "refs/heads/loop/main"],
                          cwd=self.work)
        return rows.split()[0] if rows else None

    def delete_remote_branch(self):
        # Delete on the bare remote, as GitHub does, leaving the client's ref intact.
        run_git(["update-ref", "-d", "refs/heads/loop/main"], self.origin)
        self.assertIsNone(self.remote_head())
        self.assertEqual(common.git(["rev-parse", "origin/loop/main"], cwd=self.work),
                         self.old_head)

    def pushes(self):
        return self.push_log.read_text().splitlines() if self.push_log.exists() else []

    def restored_events(self):
        path = self.runtime / "events.jsonl"
        return [row for row in map(json.loads, path.read_text().splitlines())
                if row["kind"] == "loop-branch-restored"] if path.exists() else []

    def assert_restoration_report(self, source, count=1):
        lines = [line for line in (self.runtime / "loop.out").read_text().splitlines()
                 if "restor" in line.lower() and "loop/main" in line]
        self.assertEqual(len(lines), count, lines)
        for line in lines:
            self.assertIn(source, line)
        self.assertEqual(len(self.restored_events()), count)

    def run_cycles(self, cycles=1, delete_between=False):
        heads, waits = [], []

        def start(project, settings, state):
            heads.append(self.remote_head())

        def wait(path, seconds):
            waits.append(seconds)
            if len(waits) >= cycles:
                Path(path).touch()
            elif delete_between:
                run_git(["update-ref", "-d", "refs/heads/loop/main"], self.origin)

        # Keep Git and sync real; replace queue, board, pass and polling services.
        with mock.patch.object(loop, "snapshot"), \
                mock.patch.object(loop, "start_builds", side_effect=start), \
                mock.patch.object(loop, "write_board"), \
                mock.patch.object(loop, "drain"), \
                mock.patch.object(loop, "clean_up"), \
                mock.patch.object(loop, "wait_stop", side_effect=wait), \
                (self.runtime / "loop.out").open("w") as output, \
                contextlib.redirect_stdout(output):
            self.assertEqual(loop.run(self.work), 0)
        return heads

    def test_each_cycle_restores_the_last_known_head_before_starting_work(self):
        self.delete_remote_branch()
        heads = self.run_cycles(cycles=2, delete_between=True)
        self.assertEqual(heads, [self.old_head, self.old_head],
                         "each cycle must restore the remote before starting work")
        self.assertEqual(self.remote_head(), self.old_head)
        self.assertEqual([row.split()[2] for row in self.pushes()], [self.old_head] * 2)
        self.assert_restoration_report("origin/loop/main", count=2)

    def test_cycle_falls_back_to_default_without_a_remote_tracking_ref(self):
        self.delete_remote_branch()
        run_git(["update-ref", "-d", "refs/remotes/origin/loop/main"], self.work)
        heads = self.run_cycles()
        self.assertEqual(heads, [self.base], "restore from the default branch before work")
        self.assertEqual(self.remote_head(), self.base)
        self.assertEqual([row.split()[2] for row in self.pushes()], [self.base])
        self.assert_restoration_report("origin/main")

    def test_existing_branch_is_not_pushed_or_reported(self):
        self.assertEqual(self.run_cycles(cycles=2), [self.old_head] * 2)
        self.assertEqual(self.pushes(), [])
        self.assertEqual(self.restored_events(), [])
        lines = (self.runtime / "loop.out").read_text().splitlines()
        self.assertFalse([line for line in lines if "loop/main" in line], lines)

    def test_issue_merge_restores_before_creating_the_pull_request(self):
        for remembered in (True, False):
            with self.subTest(remembered=remembered):
                self.check_merge_restoration(remembered)

    def check_merge_restoration(self, remembered):
        expected = self.old_head if remembered else self.base
        branch = "issue/remembered" if remembered else "issue/fallback"
        run_git(["checkout", "-b", branch, expected], self.work)
        Path(self.work, "app.txt").write_text("candidate %s\n" % remembered)
        run_git(["add", "app.txt"], self.work)
        run_git(["commit", "-m", "candidate work"], self.work)
        sha = common.git(["rev-parse", "HEAD"], cwd=self.work)
        run_git(["push", "origin", "HEAD:" + branch], self.work)
        run_git(["checkout", "main"], self.work)
        self.delete_remote_branch()
        if not remembered:
            run_git(["update-ref", "-d", "refs/remotes/origin/loop/main"], self.work)
        self.push_log.write_text("")
        events_before = len(self.restored_events())
        created, merged, heads_at_create = [], [], []

        def github(args, input=None):
            if args[:2] == ["issue", "view"]:
                return 0, json.dumps({"body": "Change app text.", "comments": []}), ""
            if args[:2] == ["pr", "list"]:
                prs = [{"number": 7, "state": "MERGED" if merged else "OPEN",
                        "headRefOid": sha, "mergeCommit": {"oid": sha}}] if created else []
                return 0, json.dumps(prs), ""
            if args[:2] == ["pr", "create"]:
                heads_at_create.append(self.remote_head())
                if heads_at_create[-1] is None:
                    return 1, "", "the base branch does not exist"
                created.append(True)
                return 0, "https://example.test/pull/7", ""
            if args[:2] == ["pr", "merge"]:
                merged.append(True)
                return 0, "", ""
            if args[:2] == ["pr", "view"]:
                return 0, '{"comments": []}', ""
            if args[:2] in (["pr", "comment"], ["issue", "close"], ["issue", "edit"]):
                return 0, "", ""
            raise AssertionError("unexpected GitHub call: %r" % args)

        with mock.patch.object(common, "_run_gh", side_effect=github), \
                (self.runtime / "loop.out").open("w") as output, \
                contextlib.redirect_stdout(output):
            result = merge.merge(1, branch, "VERDICT: APPROVE\nHEAD: " + sha,
                                 self.work)
        self.assertTrue(result.ok, result.reason)
        self.assertFalse(result.park, result.reason)
        self.assertEqual(heads_at_create, [expected])
        self.assertEqual(self.remote_head(), expected)
        self.assertEqual([row.split()[2] for row in self.pushes()], [expected])
        self.assertEqual(len(self.restored_events()), events_before + 1)
