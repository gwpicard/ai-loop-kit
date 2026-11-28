"""Resource waits and disk retries share the Stop hook's session deadline."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import common
from kit.tests.helpers import HERE, make_repo


spec = importlib.util.spec_from_file_location("resource_stop", Path(HERE, "../hooks/stop.py"))
stop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stop)


class StopResourceDeadlineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work, _ = make_repo(self.tmp.name, {
            ".gitignore": ".loop/\n",
            "loop.json": json.dumps({"Test command": "echo test", "Check command": "echo check"}),
        })
        self.now, self.began, self.budget = 1000.0, 1000.0, 0.25
        self.launches, self.limits, self.sleeps = [], [], []

    def hook(self, resource="", command="echo test", advance=None, recovery=0.4):
        settings = common.read_settings(self.work)
        settings["Test command"] = command
        popen, wait = common.subprocess.Popen, common.wait_limited

        def launch(*args, **kwargs):
            if kwargs.get("shell"):
                self.launches.append(self.now - self.began)
            return popen(*args, **kwargs)

        def limited(callback, limit, project, deadline=None):
            self.limits.append(limit)
            return wait(callback, limit, project, deadline=deadline)

        def nap(seconds):
            self.sleeps.append(seconds)
            self.now += seconds if advance is None else advance

        def pressure(**kwargs):
            held = resource == "memory" or resource == "check-memory" and self.launches
            return 4 if held and self.now - self.began < recovery else 1

        def disk(path):
            low = resource == "disk" and self.now - self.began < recovery
            return mock.Mock(free=0 if low else common.MIN_DISK_FREE)

        env = dict(LOOP_ROLE="builder", LOOP_PROJECT=self.work, LOOP_START="", LOOP_LOCKED="",
                   LOOP_SESSION_BEGAN=str(self.began), LOOP_SESSION_LIMIT=str(self.budget),
                   LOOP_GROUPS="", LOOP_TMPDIR=self.tmp.name)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(common, "build_settings", return_value=settings), \
                mock.patch.object(common.time, "time", side_effect=lambda: self.now), \
                mock.patch.object(common, "sleep", side_effect=nap), \
                mock.patch.object(common, "pressure_level", side_effect=pressure), \
                mock.patch.object(common, "build_count", return_value=2), \
                mock.patch.object(common.shutil, "disk_usage", side_effect=disk), \
                mock.patch.object(common.subprocess, "Popen", side_effect=launch), \
                mock.patch.object(common, "wait_limited", side_effect=limited), \
                mock.patch.object(common, "say"), \
                mock.patch.object(stop.os, "getcwd", return_value=self.work), \
                mock.patch.object(stop.sys, "stdin", io.StringIO('{"session_id":"resources"}')), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(stop.main(), 0)
        self.assertEqual((out.getvalue(), err.getvalue()), ("", ""))

    def assert_no_pass(self):
        self.assertFalse(Path(self.work, ".loop/passed-resources").exists())

    def test_memory_wait_expires_without_launching_or_recording_a_pass(self):
        self.hook("memory")
        self.assertEqual(self.launches, [])
        self.assertAlmostEqual(self.now - self.began, self.budget)
        self.assertLessEqual(max(self.sleeps), self.budget)
        self.assert_no_pass()

    def test_disk_wait_expires_without_launching_or_recording_a_pass(self):
        self.hook("disk")
        self.assertEqual(self.launches, [])
        self.assertAlmostEqual(self.now - self.began, self.budget)
        self.assertLessEqual(max(self.sleeps), self.budget)
        self.assert_no_pass()

    def test_check_resource_wait_expires_without_launching_or_recording_a_pass(self):
        self.hook("check-memory")
        self.assertEqual(self.launches, [0])
        self.assertAlmostEqual(self.now - self.began, self.budget)
        self.assert_no_pass()

    def test_launch_budget_is_recalculated_after_memory_recovers(self):
        self.hook("memory", advance=0.1, recovery=0.1)
        self.assertEqual(len(self.launches), 2)
        self.assertTrue(all(abs(when - 0.1) < 0.0001 for when in self.launches))
        self.assertTrue(all(0 < limit <= 0.1501 for limit in self.limits), self.limits)

    def test_disk_full_retry_expires_without_relaunching_or_recording_a_pass(self):
        self.hook(command="echo 'No space left on device'; exit 1")
        self.assertEqual(self.launches, [0])
        self.assertAlmostEqual(self.now - self.began, self.budget)
        self.assertLessEqual(max(self.sleeps), self.budget)
        self.assert_no_pass()

    def test_retry_budget_is_recalculated_after_disk_recovers(self):
        self.hook(command="if test -f retried; then echo ok; else touch retried; "
                          "echo 'No space left on device'; exit 1; fi", advance=0.1)
        self.assertEqual(len(self.launches), 3)
        self.assertAlmostEqual(self.launches[0], 0)
        self.assertTrue(all(abs(when - 0.1) < 0.0001 for when in self.launches[1:]))
        self.assertTrue(all(0 < limit <= 0.1501 for limit in self.limits[1:]), self.limits)
