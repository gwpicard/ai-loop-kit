"""Warnings at the commands people use to set up and start the loop."""
import contextlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from unittest import mock

from kit.tests.helpers import FAKE_GH, FakeGh, make_repo, run_git, write_exe
import loop
import setup


KIT = Path(__file__).resolve().parents[1]
SETTING = "Automatically delete head branches"


def repository_api(args):
    return (args[:1] == ["api"] and any(
        re.fullmatch(r"/?repos/[^/]+/[^/]+", arg) for arg in args[1:]))


class DeleteBranchWarningTest(FakeGh):
    def setUp(self):
        super().setUp()
        self.work, _ = make_repo(self.tmp, {
            "loop.json": json.dumps({"Test command": "true", "Idle hours": 12}),
        })
        run_git(["push", "origin", "main:loop/main"], self.work)
        # Honour both a whole repository response and gh's field projection.
        probe = '''
import re
if sys.argv[1:2] == ["api"] and any(re.fullmatch(r"/?repos/[^/]+/[^/]+", a) for a in sys.argv[2:]):
    mode = os.environ["TEST_BRANCH_SETTING"]
    if mode == "unreadable":
        sys.stderr.write("repository setting unavailable\\n")
        sys.exit(1)
    value = mode == "on"
    if "--jq" in sys.argv or "-q" in sys.argv:
        print(json.dumps(value))
    else:
        print(json.dumps({"name": "project", "delete_branch_on_merge": value,
                          "private": True}))
    sys.exit(0)
'''
        write_exe(os.path.join(self.tmp, "bin", "gh"),
                  FAKE_GH.replace('rules = json.load(open(path))["rules"]',
                                  probe + '\nrules = json.load(open(path))["rules"]'))

    def world(self, mode):
        os.environ["TEST_BRANCH_SETTING"] = mode
        factory = {"number": 1, "title": "Factory", "body": "", "labels": []}
        answers = [
            ("label list", json.dumps([{"name": n} for n in setup.LABELS])),
            ("issue list --state closed", "[]"),
            ("issue list", json.dumps([factory])),
            ("pr list", "[]"),
            ("issue edit", ""),
        ]
        self.scenario([{"match": match, "responses": [{"stdout": text}]}
                       for match, text in answers])

    def setup_command(self):
        result = subprocess.run([sys.executable, str(KIT / "scripts/setup.py"), self.work],
                                cwd=self.work, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("preflight: the Test command passes", result.stdout)
        return result.stdout + result.stderr

    def loop_command(self, probe_timeout=False):
        output = io.StringIO()
        waits = []
        attempts = []
        real_run = subprocess.run

        def run(args, **kwargs):
            if probe_timeout and Path(args[0]).name == "gh" and repository_api(args[1:]):
                attempts.append(args)
                timeout = kwargs.get("timeout")
                self.assertIsNotNone(timeout, "the optional probe must have a short timeout")
                self.assertGreater(timeout, 0)
                self.assertLessEqual(timeout, 5, "the optional probe must not use the normal gh timeout")
                raise subprocess.TimeoutExpired(args, timeout)
            return real_run(args, **kwargs)

        def poll(stop, seconds):
            waits.append(seconds)
            if len(waits) == 2:
                Path(stop).touch()

        previous = os.getcwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(self.work)
        # Keep the command dispatch, preflight and supervisor real. No builds
        # are queued; synchronising and draining the batch are outside this test.
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output), \
                mock.patch.object(loop.sys, "platform", "linux"), \
                mock.patch.object(loop.os, "nice"), \
                mock.patch.object(loop, "sync_default", return_value=False), \
                mock.patch.object(loop, "drain"), \
                mock.patch.object(subprocess, "run", side_effect=run), \
                mock.patch.object(loop, "wait_stop", side_effect=poll):
            code = loop.main(["run"])
        text = output.getvalue()
        self.assertEqual(code, 0, text)
        self.assertEqual(len(waits), 2, text)
        self.assertNotIn("problem, will check again", text)
        self.assertIn("exiting: stop requested", text)
        if probe_timeout:
            self.assertEqual(len(attempts), 1, "a timed-out setting probe must not retry")
            self.assertNotIn(SETTING, text)
        return text

    def warning(self, text):
        lines = [line for line in text.splitlines() if SETTING in line]
        self.assertEqual(len(lines), 1, text)
        line = lines[0]
        self.assertIn("warning", line.lower())
        self.assertRegex(line, r"Settings.*General.*Pull Requests.*Automatically delete head branches")
        self.assertRegex(line.lower(), r"turn.*off|disable|uncheck|untick")
        # The supervisor prefixes log lines with a timestamp.
        return re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", line)

    def one_probe(self):
        probes = [args for args in self.calls() if repository_api(args)]
        self.assertEqual(len(probes), 1, self.calls())
        return probes[0]

    def test_setup_warns_once_with_the_setting_and_its_location(self):
        self.world("on")
        self.warning(self.setup_command())
        self.one_probe()

    def test_loop_warns_with_the_same_line_once_across_polling_cycles(self):
        self.world("on")
        actual = self.warning(self.loop_command())
        self.one_probe()
        self.world("on")
        self.assertEqual(actual, self.warning(self.setup_command()))
        self.one_probe()

    def test_slow_setting_probe_is_bounded_and_the_loop_still_starts(self):
        self.world("on")
        self.loop_command(probe_timeout=True)

    def test_off_or_unreadable_setting_is_silent_and_both_commands_continue(self):
        for mode in ("off", "unreadable"):
            for command in (self.setup_command, self.loop_command):
                with self.subTest(mode=mode, command=command.__name__):
                    self.world(mode)
                    text = command()
                    self.assertNotIn(SETTING, text)
                    self.assertNotIn("repository setting unavailable", text)
                    self.one_probe()

    def test_readme_explains_why_automatic_branch_deletion_should_be_off(self):
        text = (KIT / "README.md").read_text()
        paragraphs = [" ".join(p.split()) for p in text.split("\n\n")]
        relevant = [p for p in paragraphs if SETTING.lower() in p.lower()]
        self.assertTrue(relevant, "README must name the GitHub setting")
        paragraph = relevant[0].lower()
        self.assertRegex(paragraph, r"off|disable|uncheck|untick")
        self.assertIn("loop branch", paragraph)
        self.assertRegex(paragraph, r"delet\w*|remov\w*")
        self.assertRegex(paragraph, r"final|merg\w*")
