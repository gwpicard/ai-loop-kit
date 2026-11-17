"""A board write that fails right after a claim must not strand the issue as building for the rest of the run."""
import unittest
from unittest import mock

import common
import loop
from kit.tests.test_loop import LoopTest as _LoopTest, issue, setUpModule, tearDownModule  # noqa: F401


class BoardFailureAfterClaim(_LoopTest):
    def test_issue_is_built_after_a_failed_board_write(self):
        self.world([issue(2)])
        real, calls, sleeps = loop.write_board, [], []

        def flaky(project, st):
            calls.append(1)
            if len(calls) == 1:
                raise common.GitHubError("the board edit failed: HTTP 502")
            return real(project, st)

        def sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) > 20:
                raise RuntimeError("the loop is stuck waiting for a build that never started")
        loop.time.sleep.side_effect = sleep
        with mock.patch.object(loop, "write_board", side_effect=flaky), self.fake_build():
            try:
                self.run_loop()
            except RuntimeError:
                pass
        self.assertEqual([n for n, _ in self.built], [2])


if __name__ == "__main__":
    unittest.main()
