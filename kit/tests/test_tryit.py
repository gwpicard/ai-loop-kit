"""Running the product: issue steps accompany the loop branch and its commit."""
import subprocess
import unittest

from kit.tests import test_handson

setUpModule, tearDownModule = test_handson.setUpModule, test_handson.tearDownModule


class Template(unittest.TestCase):
    def test_shaping_puts_run_steps_in_the_issue_and_general_guidance_in_the_readme(self):
        text = test_handson.read("skills", "shape", "SKILL.md")
        for phrase in ("Hands-on check", "run the product from the loop branch", "README.md"):
            self.assertIn(phrase, text)


class Showing(test_handson.Listing):
    def head(self):
        return subprocess.run(["git", "rev-parse", "--short", "origin/loop/main"], cwd=self.work,
                              check=True, capture_output=True, text=True).stdout.strip()

    def test_the_branch_and_commit_precede_the_issue_steps(self):
        self.land()
        self.issues(i2=test_handson.WITH)
        section = self.section(self.drain_body()).split("\n## ")[0]
        self.assertIn(self.head(), section)
        self.assertLess(section.index("loop/main"), section.index("Open the app"))

    def test_an_old_plan_is_ignored(self):
        self.land()
        self.commit("loop/main", "PLAN.md", "# Plan\n\n## Try it\n\nObsolete instructions.\n", "Old notes")
        self.issues(i2=test_handson.WITH)
        body = self.drain_body()
        self.assertNotIn("Obsolete instructions", body)
        self.assertNotIn("PLAN.md", self.section(body).split("\n## ")[0])
        self.assertIn("- [ ] Open the app. Expect the list to load.", body)

    def test_a_refresh_uses_the_new_commit_and_keeps_checked_steps(self):
        self.land()
        self.issues(i2=test_handson.WITH)
        old = self.head()
        first = self.drain_body()
        ticked = first.replace("- [ ] Open the app.", "- [x] Open the app.")
        pr = {"number": 9, "url": "https://example/pull/9", "body": ticked}
        self.commit("loop/main", "y.txt", "y\n", "Issue 2 again")
        self.extra += [{"match": "pr view 9", **test_handson.out({"body": ticked})}]
        section = self.section(self.drain_body(prs=[pr])).split("\n## ")[0]
        self.assertIn(self.head(), section)
        self.assertNotIn(old, section)
        self.assertIn("- [x] Open the app. Expect the list to load.", section)


if __name__ == "__main__":
    unittest.main()
