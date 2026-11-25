"""The scheduling and PID publication tests must tolerate changing observations."""
import os
import signal
import unittest
from unittest import mock

from kit.tests import test_issue_kind as kinds
from kit.tests import test_pass_pid_publication as publication
from kit.tests.test_loop import setUpModule, tearDownModule  # noqa: F401
import loop


class SchedulingObservationsTest(kinds.KindSchedulingTest):
    def test_headroom_checks_keep_call_order_when_the_clock_goes_backwards(self):
        # Keep every worker event and its order, but reverse its clock readings.
        # The original test still has to prove the wait and both overlap checks.
        events = self.events

        def backwards_events():
            return [(number, what, -index)
                    for index, (number, what, _) in enumerate(events())]

        with mock.patch.object(self, "events", side_effect=backwards_events):
            kinds.KindSchedulingTest.test_parallel_work_obeys_load_and_memory_checks(self)


class PidObservationsTest(publication.PassPidPublicationTest):
    def test_publication_check_tolerates_a_leader_disappearing_between_snapshots(self):
        process_table = loop.process_table
        kill = os.kill
        leader = self.runtime / "leader-pid"
        killed = []
        snapshots = []

        def record_kill(pid, sig):
            result = kill(pid, sig)
            if sig == signal.SIGKILL and leader.exists():
                contents = leader.read_text()
                if contents.strip() == str(pid):
                    killed.append(pid)
            return result

        def changing_table():
            rows = process_table()
            if killed:
                pid = killed[-1]
                if not snapshots:
                    # One valid snapshot still shows the dying leader running.
                    rows[pid] = (os.getpid(), "S")
                else:
                    rows.pop(pid, None)
                snapshots.append(rows)
            return rows

        with mock.patch.object(os, "kill", side_effect=record_kill), \
                mock.patch.object(loop, "process_table", side_effect=changing_table):
            try:
                publication.PassPidPublicationTest.test_hook_cleanup_waits_for_the_leader_pid_contents(self)
            except KeyError as error:
                self.fail("the PID publication check mixed process-table snapshots: %s" % error)


def load_tests(loader, tests, pattern):
    # Inherit the real fixtures without collecting their other tests again.
    return unittest.TestSuite(
        cls(name)
        for cls in (SchedulingObservationsTest, PidObservationsTest)
        for name in sorted(cls.__dict__) if name.startswith("test_"))
