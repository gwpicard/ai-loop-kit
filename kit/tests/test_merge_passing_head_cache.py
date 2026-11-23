"""A saved passing loop-head result avoids repeating the baseline full run."""
import unittest
from pathlib import Path

from kit.tests import test_merge_full_suite_cadence as cadence
from kit.tests.helpers import run_git


class PassingHeadCacheTest(unittest.TestCase):
    def test_retry_reuses_the_passing_baseline_across_processes(self):
        f = cadence.FullSuiteCadenceTest()
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.addCleanup(f.tearDown)
        f.seed_three_merges()
        f.candidate({"FAIL": "candidate regression\n"})
        first = f.merge_process()
        self.assertFalse(first["ok"])
        self.assertFalse(first["park"])
        self.assertEqual(len([c for c in f.commands() if c.startswith("full ")]), 2)
        f.trace.write_text("")
        second = f.merge_process()
        self.assertFalse(second["ok"])
        self.assertFalse(second["park"])
        self.assertEqual(f.commands(), ["full " + f.sha])

    def test_wait_is_written_once_to_loop_output_without_a_targeted_command(self):
        f = cadence.FullSuiteCadenceTest()
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.addCleanup(f.tearDown)
        f.configure(**{"Full suite every": 1, "Test files command": ""})
        base = f.candidate({"FAIL": "loop regression\n"})
        run_git(["push", "origin", base + ":loop/main"], f.work)
        f.candidate()
        self.assertTrue(f.merge_process()["park"])
        f.trace.write_text("")
        result = f.merge_process()
        self.assertFalse(result["ok"])
        self.assertFalse(result["park"])
        self.assertEqual(f.commands(), ["check"])
        lines = Path(f.work, ".loop/loop.out").read_text().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn(base[:10], lines[0])
        self.assertIn("waiting", lines[0])
