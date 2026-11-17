"""The failed crash comment test must not count subprocess polling, which on Linux calls time.sleep with short waits."""
import subprocess
import unittest
from unittest import mock

import loop
from kit.tests.test_loop_failed_crash_comment import FailedCrashComment as _Base, setUpModule, tearDownModule  # noqa: F401


class FailedCrashCommentWithPolling(_Base):
    def setUp(self):
        super().setUp()
        real_run = subprocess.run

        def run_polling(*args, **kw):
            for _ in range(30):
                loop.time.sleep(0.01)
            return real_run(*args, **kw)
        patcher = mock.patch.object(subprocess, "run", run_polling)
        patcher.start()
        self.addCleanup(patcher.stop)


if __name__ == "__main__":
    unittest.main()
