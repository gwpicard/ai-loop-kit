"""Real build sessions receive a share of the machine's test workers."""
import os
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests import test_settings_build_retention


class BuildTestWorkersTest(FakeClaudeGh):
    def check_budget(self, parallel):
        # The existing supervisor fixture runs a worker and all three fake agent roles.
        with mock.patch.dict(os.environ, {"LOOP_TEST_WORKERS": "97"}):
            test_settings_build_retention.BuildRetentionTest.check_build(self, "loop.json", parallel)
        calls = self.claude_calls()
        self.assertTrue(calls, "the build must reach an agent session")
        expected = str(max(1, (os.cpu_count() or 1) // parallel))
        for call in calls:
            with self.subTest(role=call["role"], parallel=parallel):
                self.assertEqual(call["env"].get("LOOP_TEST_WORKERS"), expected)

    def test_builds_share_processors_using_the_parallel_setting(self):
        self.check_budget(3)

    def test_each_build_gets_at_least_one_test_worker(self):
        self.check_budget((os.cpu_count() or 1) + 1)
