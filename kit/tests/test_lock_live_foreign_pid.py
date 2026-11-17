"""A loop.pid naming a live process the user may not signal still means a loop is running."""
import os
import unittest

import loop
from kit.tests.test_loop import Base, setUpModule, tearDownModule  # noqa: F401


class LockForeignPid(Base):
    def test_a_live_pid_owned_by_someone_else_refuses(self):
        os.makedirs(os.path.join(self.work, ".lite"))
        with open(os.path.join(self.work, ".lite", "loop.pid"), "w") as f:
            f.write("1")  # launchd/init: alive, but os.kill(1, 0) raises PermissionError for a normal user
        if os.geteuid() == 0:
            self.skipTest("root may signal pid 1")
        self.assertTrue(str(loop.take_lock(self.work)).startswith("refused"))


if __name__ == "__main__":
    unittest.main()
