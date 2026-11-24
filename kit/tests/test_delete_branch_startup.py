"""The optional branch warning must respect the loop's GitHub boundary."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
from unittest import mock

from kit.tests.helpers import FakeGh, make_repo, run_git
from kit.tests.test_delete_branch_warning import repository_api, SETTING
import common
import loop
import setup


class DeleteBranchStartupTest(FakeGh):
    def setUp(self):
        super().setUp()
        self.work, _ = make_repo(self.tmp, {
            "loop.json": json.dumps({"Test command": "true", "Idle hours": 12}),
        })
        run_git(["push", "origin", "main:loop/main"], self.work)
        self.answers = [
            ("label list", json.dumps([{"name": name} for name in setup.LABELS])),
            ("issue list --state closed", "[]"),
            ("issue list", json.dumps([
                {"number": 1, "title": "Factory", "body": "", "labels": []},
            ])),
            ("pr list", "[]"),
            ("issue edit", ""),
        ]
        self.scenario([{"match": match, "responses": [{"stdout": text}]}
                       for match, text in self.answers])
        previous = os.getcwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(self.work)

    def start_and_stop(self):
        output = io.StringIO()
        polls = []

        def wait(stop, seconds):
            polls.append(seconds)
            if len(polls) == 2:
                Path(stop).touch()

        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output), \
                mock.patch.object(loop.sys, "platform", "linux"), \
                mock.patch.object(loop.os, "nice"), \
                mock.patch.object(loop, "sync_default", return_value=False), \
                mock.patch.object(loop, "drain"), \
                mock.patch.object(loop, "wait_stop", side_effect=wait):
            try:
                code = loop.main(["run"])
            except Exception as error:
                self.fail("the optional warning stopped loop run: %s: %s" %
                          (type(error).__name__, error))
        text = output.getvalue()
        self.assertEqual(code, 0, text)
        self.assertEqual(len(polls), 2, text)
        self.assertIn("exiting: stop requested", text)
        self.assertNotIn("problem, will check again", text)
        self.assertNotIn(SETTING, text)
        self.assertNotIn("unexpected setting failure", text)
        self.assertFalse(Path(self.work, ".loop/loop.pid").exists())

    def test_unexpected_wrapper_exception_is_silent_and_loop_run_starts(self):
        real_gh = common.gh
        probes = []

        def gh(args, *positional, **keywords):
            if repository_api(args):
                probes.append(args)
                raise RuntimeError("unexpected setting failure")
            return real_gh(args, *positional, **keywords)

        with mock.patch.object(common, "gh", side_effect=gh):
            self.start_and_stop()
        self.assertEqual(len(probes), 1, "read the setting through common.gh once")

    def test_in_process_fake_gh_needs_no_setting_subprocess(self):
        calls = []
        real_run = subprocess.run
        direct_probes = []

        def fake_gh(args, input=None):
            calls.append(args)
            text = " ".join(args)
            for match, answer in self.answers:
                if match in text:
                    return 0, answer, ""
            return 0, "", ""

        def run(args, **keywords):
            if Path(args[0]).name == "gh" and repository_api(args[1:]):
                direct_probes.append(args)
                raise AttributeError("unexpected setting failure")
            return real_run(args, **keywords)

        # Start-up gh calls use this in-process fake, as the polling tests do.
        with mock.patch.object(common, "_run_gh", side_effect=fake_gh), \
                mock.patch.object(subprocess, "run", side_effect=run):
            self.start_and_stop()
        self.assertEqual(direct_probes, [], "the setting probe bypassed the fake gh")
        self.assertTrue(any(args[:2] == ["issue", "list"] for args in calls),
                        "the supervisor must reach its normal polling cycle")
