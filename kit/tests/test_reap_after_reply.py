"""A build that died twice is parked; after the person's reply its next death gets the retry again."""
import os
import unittest
from unittest import mock

from kit.tests.test_loop import Base, issue, setUpModule, tearDownModule  # noqa: F401
import common
import loop


class DeadProcess:
    returncode = 3

    def poll(self):
        return 3


class ReapAfterReply(Base):
    def test_a_death_after_a_park_and_a_reply_is_a_first_death(self):
        self.world([issue(2, labels=("building",))])
        st = loop.new_state()
        for _ in range(2):
            st["building"][2] = ("10:00", DeadProcess())
            loop.reap(self.work, st)
        parked = len([i for c, i in self.inputs if i and "The build crashed twice" in i])
        self.assertEqual(parked, 1)
        # the person replied, the issue is ready again and builds, and the process dies once
        self.inputs.clear()
        st["building"][2] = ("11:00", DeadProcess())
        loop.reap(self.work, st)
        texts = [i or "" for _, i in self.inputs]
        self.assertFalse(any("crashed twice" in t for t in texts), "one death after a reply was parked as 'twice'")
        self.assertTrue(any("Trying once more" in t for t in texts))


if __name__ == "__main__":
    unittest.main()
