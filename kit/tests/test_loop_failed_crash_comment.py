"""A failed crash comment on the first attempt must not leave the issue claimed and the loop waiting for ever."""
import unittest
from unittest import mock

import common
import flow
import loop
from kit.tests.test_loop import LoopTest as _LoopTest, issue, setUpModule, tearDownModule  # noqa: F401


class FailedCrashComment(_LoopTest):
    def test_loop_ends_and_issue_is_not_stranded(self):
        self.world([issue(2)])
        sleeps = []

        def sleep(seconds):
            # On Linux subprocess.run polls with time.sleep; the loop's own waits are 1 s or more.
            if seconds >= 1:
                sleeps.append(seconds)
            if len(sleeps) > 20:
                raise RuntimeError("the loop waits for a build that is not running")
        loop.time.sleep.side_effect = sleep
        real = loop.gh

        def fail_comment(args, **kw):
            if args[:2] == ["issue", "comment"]:
                raise common.GitHubError("HTTP 502")
            return real(args, **kw)
        build = {2: flow.Result("failed", "boom")}
        with mock.patch.object(loop, "gh", side_effect=fail_comment), self.fake_build(build):
            try:
                self.assertEqual(self.run_loop(), 0)
            except RuntimeError as e:
                self.fail(str(e))


if __name__ == "__main__":
    unittest.main()
