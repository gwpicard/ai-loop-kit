"""Try it: the final pull request shows the build and the plan's steps for running it."""
import subprocess
import unittest

from kit.tests import test_handson

setUpModule, tearDownModule = test_handson.setUpModule, test_handson.tearDownModule

STEPS = "1. Run `make app`.\n2. Open the window. Expect an empty list."
COMMENT = "<!-- The steps a person follows to run the product, and the result to expect. -->"


def plan(try_it):
    return "# Plan\n\n## Goal\n\nx\n\n## Try it\n\n%s\n\n## Lessons\n\nnone\n" % try_it


class Template(unittest.TestCase):
    def test_the_plan_template_has_a_try_it_section_with_guidance_in_a_comment(self):
        text = test_handson.read("templates", "PLAN.md")
        self.assertIn("\n## Try it", text)
        section = text.split("\n## Try it")[1].split("\n## ")[0]
        self.assertIn("<!--", section)
        self.assertIn("-->", section)
        self.assertIn("empty", section.lower())
        self.assertIn("nothing to run", section.lower())

    def test_the_shape_skill_names_try_it(self):
        text = test_handson.read("skills", "shape", "SKILL.md")
        self.assertIn("## Try it", text)


class Showing(test_handson.Listing):
    def head(self):
        out = subprocess.run(["git", "rev-parse", "--short", "origin/loop/main"], cwd=self.work,
                             check=True, capture_output=True, text=True)
        return out.stdout.strip()

    def hands_on(self, try_it=None, **kw):
        self.land()
        if try_it is not None:
            self.commit("loop/main", "PLAN.md", plan(try_it), "Plan")
        self.issues(**(kw or {"i2": test_handson.WITH}))
        return self.section(self.drain_body()).split("\n## ")[0]

    def test_the_steps_open_the_section_with_the_branch_and_commit(self):
        section = self.hands_on(STEPS)
        self.assertIn("loop/main", section)
        self.assertIn(self.head(), section)
        self.assertIn("Run `make app`.", section)
        self.assertLess(section.index("loop/main"), section.index("Run `make app`."))
        self.assertLess(section.index("Run `make app`."), section.index("Piece 2"))
        self.assertIn("- [ ] Open the app. Expect the list to load.", section)
        self.assertNotIn("## Try it", section)

    def test_a_missing_section_gives_one_notice_and_the_drain_carries_on(self):
        self.land()
        self.commit("loop/main", "PLAN.md", "# Plan\n\n## Goal\n\nx\n", "Plan")
        self.issues(i2=test_handson.WITH)
        section = self.section(self.drain_body()).split("\n## ")[0]
        self.assertIn("## Try it", section)
        self.assertIn("PLAN.md", section)
        self.assertIn("- [ ] Press Save. Expect a saved message.", section)
        self.assertEqual(len([l for l in section.splitlines() if "## Try it" in l]), 1)

    def test_a_missing_plan_gives_the_notice(self):
        section = self.hands_on()
        self.assertIn("## Try it", section)
        self.assertIn("- [ ] Open the app. Expect the list to load.", section)

    def test_a_section_holding_only_the_template_comment_gives_the_notice(self):
        section = self.hands_on("\n%s\n\n" % COMMENT)
        self.assertIn("## Try it", section)
        self.assertNotIn("<!--", section)
        self.assertIn("- [ ] Open the app. Expect the list to load.", section)

    def test_none_shows_no_branch_line_steps_or_notice(self):
        section = self.hands_on("none")
        self.assertNotIn("## Try it", section)
        self.assertNotIn(self.head(), section)
        self.assertIn("- [ ] Open the app. Expect the list to load.", section)

    def test_no_notice_and_no_branch_line_when_no_issue_has_hands_on_steps(self):
        section = self.hands_on(STEPS, i2=test_handson.WITHOUT)
        self.assertNotIn("## Try it", section)
        self.assertNotIn(self.head(), section)
        self.assertNotIn("make app", section)
        self.assertIn("none", section)

    def test_a_refresh_shows_the_new_commit_and_keeps_the_ticked_box(self):
        self.land()
        self.commit("loop/main", "PLAN.md", plan(STEPS), "Plan")
        self.issues(i2=test_handson.WITH)
        old = self.head()
        first = self.drain_body()
        self.assertIn(old, first)
        ticked = first.replace("- [ ] Open the app.", "- [x] Open the app.")
        pr = {"number": 9, "url": "https://example/pull/9", "body": ticked}
        self.commit("loop/main", "y.txt", "y\n", "Issue 2 again")
        new = self.head()
        self.assertNotEqual(old, new)
        self.extra += [{"match": "pr view 9", **test_handson.out({"body": ticked})}]
        section = self.section(self.drain_body(prs=[pr])).split("\n## ")[0]
        self.assertIn(new, section)
        self.assertNotIn(old, section)
        self.assertIn("- [x] Open the app. Expect the list to load.", section)
        self.assertIn("- [ ] Press Save. Expect a saved message.", section)

    def test_a_ticked_looking_line_in_the_steps_is_not_a_ticked_check(self):
        steps = "1. Run `make app`.\n- [x] Press Save. Expect a saved message."
        self.land()
        self.commit("loop/main", "PLAN.md", plan(steps), "Plan")
        self.issues(i2=test_handson.WITH)
        pr = {"number": 9, "url": "https://example/pull/9", "body": "x\n\n## Hands-on checks\n\n#2 Piece 2\n\n- [ ] Open the app. Expect the list to load.\n"}
        self.extra += [{"match": "pr view 9", **test_handson.out({"body": pr["body"]})}]
        body = self.drain_body(prs=[pr])
        section = self.section(body).split("\n## ")[0]
        self.assertIn("- [ ] Open the app. Expect the list to load.", section)
        # a second refresh, reading the body just built, still ticks nothing
        self.extra = [e for e in self.extra if e["match"] != "pr view 9"]
        self.extra += [{"match": "pr view 9", **test_handson.out({"body": body})}]
        again = self.section(self.drain_body(prs=[pr])).split("\n## ")[0]
        self.assertIn("- [ ] Open the app. Expect the list to load.", again)
        self.assertIn("- [ ] Press Save. Expect a saved message.", again)
        self.assertNotIn("- [x] Open", again)


if __name__ == "__main__":
    unittest.main()
