"""A killed pass worker must not leave its smoke command writing runtime files."""
import os
import signal
import time

from kit.tests.test_pass_background import BackgroundPassFixture


class PassWorkerLifetimeTest(BackgroundPassFixture):
    def test_killing_the_pass_group_also_ends_the_smoke_command(self):
        done = self.begin_drain()
        self.wait_for(self.starts, "the smoke command did not start")
        self.assertTrue(done.wait(2))
        worker = self.workers[0]
        smoke = self.starts()[0]["pid"]
        self.assertEqual(os.getpgid(smoke), worker.pid,
                         "the smoke command escaped the pass worker's process group")
        os.killpg(worker.pid, signal.SIGKILL)
        worker.wait(timeout=5)
        self.gate.touch()
        # A surviving smoke command checks this gate every 20 ms and writes here.
        until = time.monotonic() + 0.3
        while time.monotonic() < until:
            self.assertFalse((self.runtime / "smoke-ended").exists())
            time.sleep(0.02)
