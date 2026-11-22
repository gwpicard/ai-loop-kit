"""Check cadence recovery and commands that cannot select test files."""
import json
import unittest
from unittest import mock

import common
from kit.tests import test_merge_full_suite_cadence as cadence


class CadenceHistoryTest(unittest.TestCase):
    def setUp(self):
        self.fixture = cadence.FullSuiteCadenceTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def test_command_without_placeholder_runs_full_suite(self):
        f = self.fixture
        f.configure(**{"Test files command": "echo cannot select files"})
        f.candidate()
        result = f.merge_process()
        self.assertTrue(result["ok"], result["reason"])
        self.assertEqual(f.commands(), ["full " + f.sha, "check"])
        self.assertTrue(f.merged_events()[-1]["full_suite"])

    def test_missing_locked_test_list_runs_full_suite(self):
        f = self.fixture
        f.candidate({"tests/test_added.py": "candidate test\n"})
        scenario = f.scenario

        def without_locked_tests(rules):
            rules[0]["responses"][0]["stdout"] = json.dumps({"body": "Add a feature.", "comments": []})
            scenario(rules)

        with mock.patch.object(f, "scenario", side_effect=without_locked_tests):
            result = f.merge_process()
        self.assertTrue(result["ok"], result["reason"])
        self.assertEqual(f.commands(), ["full " + f.sha, "check"])
        self.assertTrue(f.merged_events()[-1]["full_suite"])

    def test_successful_drain_resets_the_persisted_count(self):
        f = self.fixture
        f.seed_three_merges()
        common.event("drain", f.work, phase="end", outcome="pass")
        f.candidate()
        result = f.merge_process()
        self.assertTrue(result["ok"], result["reason"])
        self.assertTrue(f.commands()[0].startswith("targeted "))
        self.assertFalse(f.merged_events()[-1]["full_suite"])

    def test_failed_drain_does_not_reset_the_persisted_count(self):
        f = self.fixture
        f.seed_three_merges()
        common.event("drain", f.work, phase="end", outcome="fail")
        f.candidate()
        result = f.merge_process()
        self.assertTrue(result["ok"], result["reason"])
        self.assertEqual(f.commands(), ["full " + f.sha, "check"])
