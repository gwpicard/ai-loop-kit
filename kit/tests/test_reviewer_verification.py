"""The reviewer reports only verified findings, and a fix for a finding comes with a test."""
import os
import unittest

from kit.tests import helpers  # noqa: F401  (puts kit/scripts on the path)
import merge

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def brief(name):
    with open(os.path.join(ROOT, "kit", "briefs", name), encoding="utf-8") as f:
        return " ".join(f.read().lower().split())


class ReviewerBriefTest(unittest.TestCase):
    def test_each_fix_gives_location_scenario_and_fix(self):
        text = brief("reviewer.md")
        self.assertIn("file:line", text)
        self.assertIn("failure scenario", text)

    def test_uncertain_finding_is_an_unverified_follow_up(self):
        text = brief("reviewer.md")
        self.assertIn("unverified", text)
        self.assertRegex(text, r"(uncertain|unverified)[^.]*follow-up|follow-up[^.]*(uncertain|unverified)")
        self.assertRegex(text, r"never a fix|not a fix")
        self.assertRegex(text, r"no finding is better than a speculative")

    def test_tests_the_builder_added_must_be_able_to_fail(self):
        text = brief("reviewer.md")
        self.assertRegex(text, r"without the change")
        self.assertRegex(text, r"cannot fail[^.]*changes|changes[^.]*cannot fail")
        self.assertRegex(text, r"locked tests?[^.]*(shown to fail|fail first)|(shown to fail|fail first)[^.]*locked")

    def test_follows_the_code_path_for_wiring(self):
        text = brief("reviewer.md")
        self.assertIn("wiring", text)
        for word in ("registration", "menus", "routes", "configuration"):
            self.assertIn(word, text)

    def test_ends_prose_with_checked_and_sound_before_verdict(self):
        raw = open(os.path.join(ROOT, "kit", "briefs", "reviewer.md"), encoding="utf-8").read()
        self.assertIn("Checked and sound", raw)
        self.assertLess(raw.index("Checked and sound"), raw.index("VERDICT: APPROVE or CHANGES"))


class BuilderBriefTest(unittest.TestCase):
    def test_fix_for_a_finding_comes_with_a_reproducing_test(self):
        text = brief("builder.md")
        self.assertRegex(text, r"fix for a review finding")
        self.assertIn("real entry point", text)
        self.assertIn("unverified", text)
        self.assertIn("built block", text)


class VerdictParsingTest(unittest.TestCase):
    def test_checked_and_sound_list_keeps_the_verdict(self):
        reply = ("Review prose.\n\nChecked and sound:\n- routes registered\n- VERDICT: handled\n\n"
                 "VERDICT: CHANGES\nHEAD: abc1234\n1. a.py:3 fails when x; fix y\n\nFOLLOW-UPS:\nnone\n")
        self.assertEqual(merge.parse_verdict(reply), ("CHANGES", "abc1234"))
        approve = "Checked and sound:\n- all\n\nVERDICT: APPROVE\nHEAD: abc1234\n"
        self.assertEqual(merge.parse_verdict(approve), ("APPROVE", "abc1234"))


if __name__ == "__main__":
    unittest.main()
