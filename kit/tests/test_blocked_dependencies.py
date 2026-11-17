import os
import re
import unittest
from unittest import mock

from kit.tests import test_loop
from kit.tests.helpers import copy_repo
from kit.tests.test_loop import Base, comment, issue, out, setUpModule, tearDownModule  # noqa: F401
import common
import loop


def pr(number, base="develop", closes=(), state="OPEN"):
    return {"number": number, "baseRefName": base, "state": state,
            "closingIssuesReferences": [{"number": n} for n in closes]}


class BlockedDependencyTest(Base):
    """Dependencies the loop will never build are listed under Needs you."""

    def setUp(self):
        super().setUp()
        self.work, self.origin = copy_repo(test_loop.TEMPLATE.name, self._tmp.name)

    def world(self, open_issues, closed=(), comments=(), prs=(), **kw):
        super().world(open_issues, closed=closed, comments=comments, **kw)

        def listing(args, input=None):
            text = " ".join(args)
            self.calls.append(text)
            wanted = {"open": ("OPEN",), "merged": ("MERGED",), "closed": ("CLOSED",),
                      "all": ("OPEN", "MERGED", "CLOSED")}
            state = args[args.index("--state") + 1] if "--state" in args else "open"
            return 0, out([p for p in prs if p["state"] in wanted[state]])["stdout"], ""
        self.rules.insert(0, {"match": "pr list", "listing": listing})

    def fake_gh(self, args, input=None):
        text = " ".join(args)
        for rule in self.rules:
            if rule["match"] in text and "listing" in rule:
                return rule["listing"](args, input)
        return super().fake_gh(args, input)

    def board(self, open_issues, **kw):
        self.world(open_issues, **kw)
        st = loop.new_state()
        loop.snapshot(st)
        loop.answer(st)
        loop.write_board(self.work, st)
        return self.board_inputs()[-1], st

    def needs_you(self, body):
        return re.search(r"## Needs you\n(.*?)(?=\n## )", body, re.S).group(1)

    def rows(self, body, number):
        return [l for l in self.needs_you(body).splitlines() if l.startswith("- #%d " % number)]

    def test_a_dependency_with_an_open_pull_request_asks_for_the_merge_once(self):
        body, _ = self.board([issue(5, ("ready",), "Depends on: #9"),
                              issue(6, ("ready",), "Depends on: #9"),
                              issue(9, ("blocked",))],
                             prs=[pr(30, "develop", closes=[9])])
        rows = self.rows(body, 9)
        self.assertEqual(len(rows), 1)
        self.assertIn("#%d" % 30, rows[0])
        self.assertIn("develop", rows[0])
        self.assertIn("merge", rows[0])
        self.assertRegex(rows[0], r"\b2\b")

    def test_a_dependency_in_the_inbox_asks_to_shape_or_label_it(self):
        body, _ = self.board([issue(5, ("ready",), "Depends on: #9"), issue(9, ("inbox",))])
        rows = self.rows(body, 9)
        self.assertEqual(len(rows), 1)
        self.assertIn("shape", rows[0])
        self.assertIn("ready", rows[0])
        self.assertRegex(rows[0], r"\b1\b")

    def test_a_dependency_that_exists_nowhere_asks_to_check_the_depends_on_line(self):
        body, _ = self.board([issue(5, ("ready",), "Depends on: #%d" % 99)])
        rows = self.rows(body, 99)
        self.assertEqual(len(rows), 1)
        self.assertIn("check the `Depends on` line", rows[0])

    def test_dependencies_the_loop_builds_or_already_lists_get_no_new_row(self):
        body, _ = self.board([issue(5, ("ready",), "Depends on: #7, #8, #4"),
                              issue(7, ("ready",)), issue(8, ("building",)),
                              issue(4, ("needs-user",))], comments=[
            comment("## Needs you\n\nWhich port?\n\nRecommended: 80\n\n" + common.MARKER)])
        self.assertEqual(self.rows(body, 7), [])
        self.assertEqual(self.rows(body, 8), [])
        rows = self.rows(body, 4)
        self.assertEqual(rows, ["- #4 Piece 4: Which port? (reply on the issue)"])

    def test_a_closed_dependency_gets_no_row(self):
        body, _ = self.board([issue(5, ("ready",), "Depends on: #3")], closed=[3])
        self.assertEqual(self.rows(body, 3), [])

    def test_the_new_rows_cost_at_most_one_extra_gh_call(self):
        self.board([issue(5, ("ready",), "Depends on: #9, #%d" % 99), issue(9, ("inbox",))])
        self.assertLessEqual(len([c for c in self.calls if "pr list" in c]), 1)
        self.assertEqual(len([c for c in self.calls if c.startswith("issue list")]), 2)

    def test_a_merged_pull_request_on_a_depends_on_line_counts_as_done(self):
        self.world([issue(5, ("ready",), "Depends on: #%d" % 40)],
                   prs=[pr(40, "main", state="MERGED")])
        st = loop.new_state()
        loop.snapshot(st)
        with mock.patch.object(common, "ready_is_trusted", return_value=True):
            self.assertEqual(loop.pick(st), 5)
        loop.write_board(self.work, st)
        self.assertEqual(self.rows(self.board_inputs()[-1], 40), [])

    def test_an_open_pull_request_does_not_count_as_done(self):
        self.world([issue(5, ("ready",), "Depends on: #%d" % 40)], prs=[pr(40, "main")])
        st = loop.new_state()
        loop.snapshot(st)
        with mock.patch.object(common, "ready_is_trusted", return_value=True):
            self.assertIsNone(loop.pick(st))


if __name__ == "__main__":
    unittest.main()
