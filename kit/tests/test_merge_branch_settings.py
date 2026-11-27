"""Merge gates refresh settings even when a build began before a settings change."""
import json
from pathlib import Path
import unittest
from unittest import mock

from kit.tests import test_loop_branch_settings
from kit.tests.helpers import run_git
import common
import loop
import merge


class MergeBranchSettingsTest(unittest.TestCase):
    def setUp(self):
        self.batch = test_loop_branch_settings.LoopBranchSettingsTest()
        self.batch.setUp()
        self.addCleanup(self.batch.doCleanups)
        self.batch.project()

    def run_batch(self, pieces):
        reap = loop.reap

        def finish_stopped_fixture(project, state, *args, **kwargs):
            reap(project, state, *args, **kwargs)
            if Path(project, ".loop/stop").exists():
                state["building"].clear()

        with mock.patch.object(loop, "reap", side_effect=finish_stopped_fixture):
            return self.batch.run_batch(pieces)

    def test_merge_refreshes_a_builds_older_settings_snapshot(self):
        batch = self.batch
        snapshot = common.read_settings(batch.work)
        gate = merge.merge

        def stale_merge(*args, **kwargs):
            with common.settings_environment(snapshot):
                return gate(*args, **kwargs)

        branch = dict(batch.checkout, **{"Check command": batch.marker_command("checks-ran")})
        with mock.patch.object(merge, "merge", side_effect=stale_merge):
            self.run_batch([{"loop.json": json.dumps(branch)}, {}])
        self.assertEqual(batch.marker("checks-ran"), ["piece-8", "piece-8"])

    def test_supervisor_fetches_settings_after_a_remote_merge(self):
        batch = self.batch
        github = batch.github
        remote = common.git(["remote", "get-url", "origin"], cwd=batch.work)

        def remote_merge(args, input=None, **kwargs):
            if args[:2] != ["pr", "merge"]:
                return github(args, input=input, **kwargs)
            pr = batch.prs[int(args[2])]
            sha = pr["headRefOid"]
            self.assertEqual(args[args.index("--match-head-commit") + 1], sha)
            # Pushing to the URL leaves the checkout's origin ref stale, as GitHub does.
            run_git(["push", remote, sha + ":" + pr["baseRefName"]], batch.work)
            pr.update(state="MERGED", mergeCommit={"oid": sha})
            return 0, "", ""

        batch.github = remote_merge
        branch = dict(batch.checkout, **{"Max rounds": 2,
                                        "Check command": batch.marker_command("checks-ran")})
        self.run_batch([{"loop.json": json.dumps(branch)}, {}])
        self.assertEqual(batch.received[1]["Max rounds"], 2)
        self.assertEqual(batch.marker("checks-ran"), ["piece-8", "piece-8"])

    def test_empty_and_malformed_branch_files_fall_back_to_checkout(self):
        for content in ("", "{"):
            with self.subTest(content=content):
                batch = self.batch
                batch.project()
                valid = json.dumps(dict(batch.checkout, **{"Max rounds": 2}))
                text = self.run_batch([{"loop.json": valid}, {"loop.json": content}, {}, {}])
                for settings in batch.received[2:]:
                    self.assertEqual(settings["Max rounds"], batch.checkout["Max rounds"])
                errors = [line for line in text.splitlines() if "cannot read settings" in line]
                self.assertEqual(len(errors), 1, text)
