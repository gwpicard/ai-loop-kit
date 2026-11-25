"""A completed worker releases dependants before the next GitHub snapshot."""
import unittest
from unittest import mock

from kit.tests import test_parallel as parallel
import loop


class CompletedDependencyTest(unittest.TestCase):
    def test_merge_after_snapshot_releases_dependant_in_the_same_cycle(self):
        fixture = parallel.ParallelTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.world_of(parallel.issue(2), parallel.issue(3, body="Depends on: #2"))
        snapshot = loop.snapshot
        waited = []

        def before_worker_finishes(state):
            snapshot(state)
            if 2 in state["building"]:
                # Model a closed-issue listing taken just before the worker merges.
                state["closed"].discard(2)
                state["building"][2][1].wait(timeout=10)
                waited.append(2)

        with mock.patch.object(loop, "snapshot", side_effect=before_worker_finishes):
            fixture.run_it()
        self.assertEqual(waited, [2])
        self.assertEqual(fixture.merged(), {2, 3})
        self.assertGreaterEqual(fixture.at(3, "start"), fixture.at(2, "end"))
