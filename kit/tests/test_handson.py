"""Hands-on checks: written at shaping, listed unticked in the final pull request."""
import json
import os
import unittest
from unittest import mock

from kit.tests import test_loop
from kit.tests.test_loop import out
from kit.tests.helpers import copy_repo
import loop
import merge

setUpModule, tearDownModule = test_loop.setUpModule, test_loop.tearDownModule

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
STEPS = "1. Open the app. Expect the list to load.\n2. Press Save. Expect a saved message."
WITH = "## Goal\n\nx\n\n## Hands-on check\n\n%s\n\n## Depends on\n\nDepends on: none\n" % STEPS
WITHOUT = "## Goal\n\nx\n\n## Depends on\n\nDepends on: none\n"


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as f:
        return f.read()


class TemplateAndSkill(unittest.TestCase):
    def test_the_issue_template_has_an_optional_hands_on_section(self):
        text = read("templates", "issue.md")
        self.assertIn("## Hands-on check", text)
        section = text.split("## Hands-on check")[1].split("\n## ")[0].lower()
        self.assertIn("optional", section)
        self.assertIn("expect", section)

    def test_the_shape_skill_asks_for_hands_on_steps(self):
        self.assertIn("hands-on", read("skills", "shape", "SKILL.md").lower())


class Listing(test_loop.Base):
    commit, land = test_loop.GitTest.commit, test_loop.GitTest.land

    def setUp(self):
        super().setUp()
        self.work, self.origin = copy_repo(test_loop.TEMPLATE.name, self._tmp.name)
        self.tests = mock.patch.object(merge, "run_tests", return_value=None).start()
        mock.patch.object(loop.pass_, "run_pass", return_value=({}, "")).start()

    def issues(self, **bodies):
        extra = []
        for n, body in bodies.items():
            n = int(n[1:])
            data = {"number": n, "title": "Piece %d" % n, "body": body}
            extra.append({"match": "issue view %d" % n, **out(data)})
        self.extra = extra

    def section(self, body):
        self.assertIn("## Hands-on checks", body)
        return body.split("## Hands-on checks")[1]

    def drain_body(self, prs=()):
        self.world([], prs=prs)
        self.rules = self.extra + self.rules
        self.run_loop()
        found = [i for c, i in self.inputs if c.startswith(("pr create", "pr edit"))]
        self.assertTrue(found)
        return found[-1]

    def test_the_body_lists_each_issue_with_unticked_steps(self):
        self.land()
        self.issues(i2=WITH)
        body = self.drain_body()
        self.assertIn("## Hands-on checks", body)
        section = self.section(body)
        self.assertIn("2", section)
        self.assertIn("Piece 2", section)
        self.assertIn("- [ ] Open the app. Expect the list to load.", section)
        self.assertIn("- [ ] Press Save. Expect a saved message.", section)
        self.assertNotIn("- [x]", section)

    def test_an_issue_without_the_section_is_left_out(self):
        self.land()
        self.commit("loop/main", "y.txt", "y\n", "Issue 3")
        self.issues(i2=WITH, i3=WITHOUT)
        section = self.section(self.drain_body())
        self.assertIn("Piece 2", section)
        self.assertNotIn("Piece 3", section)

    def test_the_section_says_none_when_no_issue_has_steps(self):
        self.land()
        self.issues(i2=WITHOUT)
        section = self.section(self.drain_body())
        self.assertIn("none", section.split("\n## ")[0])
        self.assertNotIn("- [ ]", section.split("\n## ")[0])

    def test_a_refresh_keeps_every_ticked_box(self):
        self.land()
        self.issues(i2=WITH)
        ticked = "## Hands-on checks\n\n#2 Piece 2\n\n- [x] Open the app. Expect the list to load.\n- [ ] Press Save. Expect a saved message.\n"
        pr = {"number": 9, "url": "https://example/pull/9", "body": "Built by the loop.\n\n" + ticked}
        self.world([], prs=[pr])
        self.extra += [{"match": "pr view 9", **out({"body": pr["body"]})}]
        body = self.drain_body(prs=[pr])
        section = self.section(body)
        self.assertIn("- [x] Open the app. Expect the list to load.", section)
        self.assertIn("- [ ] Press Save. Expect a saved message.", section)
        self.assertEqual(section.count("Open the app"), 1)

    def test_a_new_hands_on_check_is_added_unticked_on_refresh(self):
        self.land()
        self.issues(i2=WITH)
        pr = {"number": 9, "url": "https://example/pull/9", "body": "x\n\n## Hands-on checks\n\nnone\n"}
        self.extra += [{"match": "pr view 9", **out({"body": pr["body"]})}]
        section = self.drain_body(prs=[pr]).split("## Hands-on checks")[1]
        self.assertIn("- [ ] Open the app. Expect the list to load.", section)

    def test_a_hands_on_check_never_parks_the_loop(self):
        self.land()
        self.issues(i2=WITH)
        self.drain_body()
        self.assertEqual(self.writes("needs-user"), [])
        self.assertEqual(self.writes("issue comment"), [])


if __name__ == "__main__":
    unittest.main()
