"""Issue kinds through the supervisor, its board and the shaping guidance."""
import os
from pathlib import Path
import re
import unittest

from kit.tests import test_parallel, test_board_activity
from kit.tests.helpers import write_settings
from kit.tests.test_loop import AGENTS, issue, setUpModule, tearDownModule  # noqa: F401
import common


KIT = Path(__file__).resolve().parents[1]


class KindContractTest(unittest.TestCase):
    def test_kind_helper_reads_the_line_and_defaults_to_build(self):
        kind = getattr(common, "issue_kind", None)
        self.assertTrue(callable(kind), "common.issue_kind must read the kind from an issue body")
        for body, expected in (
                ("Kind: parallel\n\n## Goal\nResearch\n", "parallel"),
                ("## Goal\nResearch\n\nKind: parallel\n", "parallel"),
                ("Kind: build\n\n## Goal\nImplement\n", "build"),
                ("## Goal\nImplement\n\nKind: build\n", "build"),
                ("", "build"),
                ("## Goal\nImplement\n", "build"),
                ("Kind: research\n\n## Goal\nResearch\n", "build"),
                ("## Goal\nResearch\n\nKind: unknown\n", "build")):
            with self.subTest(body=body):
                self.assertEqual(kind(body), expected)

    def test_issue_template_describes_both_kinds(self):
        body = (KIT / "templates/issue.md").read_text()
        self.assertIn("Kind: build", body)
        self.assertIn("Kind: parallel", body)

    def test_shape_skill_describes_both_kinds(self):
        body = (KIT / "skills/shape/SKILL.md").read_text()
        self.assertIn("Kind: build", body)
        self.assertIn("Kind: parallel", body)


class KindSchedulingTest(test_parallel.ParallelTest):
    def wait_for_workers(self, first, second):
        # Keep both workers alive until each has recorded its start.
        rendezvous = '''
if number in {%d, %d}:
    until = time.monotonic() + 15
    while True:
        with open(os.path.join(project, ".loop", "fake.log")) as stream:
            started = {int(line.split()[0]) for line in stream if line.split()[1] == "start"}
        if {%d, %d} <= started:
            break
        if time.monotonic() >= until:
            raise AssertionError("parallel workers did not both start")
        time.sleep(0.01)
''' % (first, second, first, second)
        Path(self.script).write_text(test_parallel.FAKE_WORKER.replace(
            'time.sleep(cfg.get("sleep", 0.5))', rendezvous))

    def test_one_extra_parallel_slot_skips_a_waiting_build(self):
        write_settings(os.path.join(self.work, "loop.json"), AGENTS + "Parallel: 1\n")
        self.world_of(issue(2, body="Kind: build"), issue(3),
                      issue(4, body="Kind: parallel"), issue(5, body="Kind: parallel"))
        self.run_it()
        self.assertEqual(self.merged(), {2, 3, 4, 5})
        self.assertLess(self.at(4, "start"), self.at(2, "end"),
                        "parallel work must start beside the occupied build slot")
        self.assertLess(self.at(2, "start"), self.at(4, "end"))
        self.assertGreaterEqual(self.at(5, "start"), self.at(4, "end"),
                                "only one parallel issue may run at a time")
        self.assertGreaterEqual(self.at(3, "start"), self.at(2, "end"))

    def test_a_waiting_parallel_issue_does_not_hold_up_a_build(self):
        write_settings(os.path.join(self.work, "loop.json"), AGENTS + "Parallel: 1\n")
        self.world_of(issue(2, body="Kind: parallel"), issue(3, body="Kind: parallel"),
                      issue(4, body="Kind: build"), issue(5, body="Kind: unrecognised"))
        self.run_it()
        self.assertEqual(self.merged(), {2, 3, 4, 5})
        self.assertLess(self.at(4, "start"), self.at(2, "end"),
                        "a parallel issue must leave the build slot available")
        self.assertLess(self.at(2, "start"), self.at(4, "end"))
        self.assertGreaterEqual(self.at(3, "start"), self.at(2, "end"))
        self.assertGreaterEqual(self.at(5, "start"), self.at(4, "end"))

    def test_parallel_work_waits_for_dependencies_then_runs_beside_a_build(self):
        write_settings(os.path.join(self.work, "loop.json"), AGENTS + "Parallel: 1\n")
        self.world_of(issue(2), issue(3, body="Kind: parallel\nDepends on: #2"),
                      issue(4, body="Depends on: #2\nKind: build"))
        self.wait_for_workers(3, 4)
        self.run_it()
        self.assertEqual(self.merged(), {2, 3, 4})
        order = [(number, what) for number, what, _ in self.events()]
        self.assertGreater(order.index((3, "start")), order.index((2, "end")))
        self.assertGreater(order.index((4, "start")), order.index((2, "end")))
        self.assertLess(order.index((4, "start")), order.index((3, "end")),
                        "the unblocked parallel issue must leave room for a build")
        self.assertLess(order.index((3, "start")), order.index((4, "end")))

    def test_parallel_work_obeys_load_and_memory_checks(self):
        for first, reason in ((2, "load average 9.0 is not below the 8 CPUs"),
                              (5, "memory pressure is critical")):
            with self.subTest(reason=reason):
                write_settings(os.path.join(self.work, "loop.json"), AGENTS + "Parallel: 1\n")
                self.world_of(issue(first), issue(first + 1, body="Kind: parallel"),
                              issue(first + 2, body="Depends on: #%d" % first))
                self.wait_for_workers(first + 1, first + 2)
                self.headroom.side_effect = lambda: (
                    reason if first not in self.merged()
                    or (first, "end") not in [(n, what) for n, what, _ in self.events()]
                    else None)
                self.run_it()
                order = [(number, what) for number, what, _ in self.events()]
                self.assertGreater(order.index((first + 1, "start")), order.index((first, "end")),
                                        "parallel work must wait while the machine is busy")
                self.assertLess(order.index((first + 2, "start")), order.index((first + 1, "end")),
                                "parallel work must use the extra slot once headroom returns")
                self.assertLess(order.index((first + 1, "start")), order.index((first + 2, "end")))


class KindBoardTest(test_board_activity.BoardActivityTest):
    def test_building_rows_mark_only_parallel_issues(self):
        for bodies in (("Kind: parallel\n\n## Goal\nResearch", "Kind: build", ""),
                       ("Kind: unknown", "## Goal\nResearch\n\nKind: parallel", "")):
            with self.subTest(bodies=bodies):
                self.st["building"] = {n: ("10:00", None) for n in (2, 3, 4)}
                self.st["issues"] = [
                    {"number": n, "title": "Piece", "body": body, "labels": {"building"}}
                    for n, body in zip((2, 3, 4), bodies)]
                building = self.board().split("## Building now", 1)[1].split("## Needs you", 1)[0]
                for n, body in zip((2, 3, 4), bodies):
                    row = next(line for line in building.splitlines() if re.search(r"#%d\b" % n, line))
                    self.assertEqual("(parallel)" in row, "Kind: parallel" in body, row)


def load_tests(loader, tests, pattern):
    # Reuse the fixtures without rerunning tests owned by their original modules.
    return unittest.TestSuite(
        cls(name)
        for cls in (KindContractTest, KindSchedulingTest, KindBoardTest)
        for name in sorted(cls.__dict__) if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
