"""Decisions to confirm: the deviations the loop recorded, listed in the final pull request."""
import os
import unittest
from unittest import mock

from kit.tests import test_loop
from kit.tests.helpers import copy_repo, run_git
import loop
import merge

setUpModule, tearDownModule = test_loop.setUpModule, test_loop.tearDownModule

HEAD = "# Plan\n\n## Lessons\n\nnone\n\n## Deviations\n\nBuilders append here.\n"
OLD = "- Issue 1: kept the old name, the plan did not say.\n"
NEW = "- Issue 2: chose a flat list, the closest approach to the plan.\n"
NEWER = "- Issue 3: used the default port, the plan named none.\n"
TAIL = "\n## Surfaces\n\n- Something else\n"


class Decisions(test_loop.Base):
    commit, land = test_loop.GitTest.commit, test_loop.GitTest.land

    def setUp(self):
        super().setUp()
        self.work, self.origin = copy_repo(test_loop.TEMPLATE.name, self._tmp.name)
        mock.patch.object(merge, "run_tests", return_value=None).start()
        mock.patch.object(loop.pass_, "run_pass", return_value=({}, "")).start()

    def plan(self, text):
        """Put PLAN.md on main and the loop branch, as a project that already has one."""
        self.commit("main", "PLAN.md", text, "Plan")
        run_git(["push", "origin", "main:loop/main"], self.work)

    def drain_body(self, prs=()):
        self.world([], prs=prs)
        self.run_loop()
        found = [i for c, i in self.inputs if c.startswith(("pr create", "pr edit"))]
        self.assertTrue(found)
        return found[-1]

    def section(self, body):
        self.assertIn("## Decisions to confirm", body)
        return body.split("## Decisions to confirm")[1].split("\n## ")[0]

    def test_a_new_deviation_is_listed_unchanged(self):
        self.plan(HEAD + "\n" + OLD + TAIL)
        self.land()
        self.commit("loop/main", "PLAN.md", HEAD + "\n" + OLD + NEW + TAIL, "Issue 2")
        section = self.section(self.drain_body())
        self.assertIn(NEW.strip(), section)
        self.assertNotIn(OLD.strip(), section)
        self.assertNotIn("none", section)
        self.assertNotIn("Something else", section)

    def test_no_new_deviation_says_none(self):
        self.plan(HEAD + "\n" + OLD + TAIL)
        self.land()
        self.assertEqual(self.section(self.drain_body()).strip(), "none")

    def test_a_missing_plan_says_none_and_the_drain_carries_on(self):
        self.land()
        body = self.drain_body()
        self.assertEqual(self.section(body).strip(), "none")
        self.assertEqual(self.writes("needs-user"), [])

    def test_the_section_sits_between_hands_on_checks_and_the_landed_list_and_pass_report(self):
        self.plan(HEAD + TAIL)
        self.land()
        self.commit("loop/main", "PLAN.md", HEAD + "\n" + NEW + TAIL, "Issue 2")
        loop.pass_.run_pass.return_value = ({}, "## End-of-loop pass\n\nChecked.\n")
        body = self.drain_body()
        at = [body.index(s) for s in ("## Hands-on checks", "## Decisions to confirm", "Landed", "## End-of-loop pass")]
        self.assertNotIn(-1, at)
        self.assertEqual(at, sorted(at))

    def test_a_refresh_rebuilds_the_list_from_the_branches(self):
        self.plan(HEAD + TAIL)
        self.land()
        self.commit("loop/main", "PLAN.md", HEAD + "\n" + NEW + NEWER + TAIL, "Issue 3")
        old = "x\n\n## Decisions to confirm\n\n" + NEW + "\n## Hands-on checks\n\nnone\n"
        pr = {"number": 9, "url": "https://example/pull/9", "body": old}
        self.extra = [{"match": "pr view 9", **test_loop.out({"body": old})}]
        self.world([], prs=[pr])
        self.rules = self.extra + self.rules
        self.run_loop()
        body = [i for c, i in self.inputs if c.startswith("pr edit")][-1]
        section = self.section(body)
        self.assertIn(NEW.strip(), section)
        self.assertIn(NEWER.strip(), section)
        self.assertEqual(section.count(NEW.strip()), 1)


if __name__ == "__main__":
    unittest.main()
