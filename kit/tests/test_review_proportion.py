"""A review blocks only on what matters; later rounds do not open new ground."""
import json
import os
import tempfile
import unittest
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import copy_repo, make_repo, run_git, settings_json
import flow
import merge

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AGENTS = ("## Loop\nCheck command: test ! -f BAD\nTest command: seq 1 99; { test ! -f tests/test_new.py || test -f app.py; }"
          " || { echo AssertionError; false; }\nLoop branch: loop/main\nMax rounds: 3\n")
MERGED = merge.Result(True, False, "merged as abc", "abc")
WRITER = {"files": {"tests/test_new.py": "x\n"}, "reply": "Done.\nTESTS:\ntests/test_new.py"}


def brief():
    with open(os.path.join(ROOT, "kit", "briefs", "reviewer.md"), encoding="utf-8") as f:
        return " ".join(f.read().lower().split())


class ReviewerBriefTest(unittest.TestCase):
    def test_blocking_findings_are_the_four_kinds(self):
        text = brief()
        self.assertIn("blocking", text)
        for words in ("acceptance criterion not met", "project rule", "lost", "existing behaviour"):
            self.assertIn(words, text)
        self.assertRegex(text, r"changes only for blocking")
        self.assertRegex(text, r"every other verified finding[^.]*follow-ups")

    def test_entry_point_and_layout_test_findings_are_follow_ups(self):
        text = brief()
        self.assertNotRegex(text, r"return changes for a test that calls internal code")
        self.assertRegex(text, r"(entry point|layout)[^.]*follow-up|follow-up[^.]*(entry point|layout)")

    def test_a_test_that_cannot_fail_is_a_follow_up(self):
        text = brief()
        self.assertNotRegex(text, r"a test that cannot fail is a changes item")
        self.assertRegex(text, r"cannot fail[^.]*follow-ups|follow-ups[^.]*cannot fail")
        self.assertRegex(text, r"cannot fail[^.]*changes|changes[^.]*cannot fail")
        self.assertIn("without the change", text)
        self.assertIn("fail first", text)

    def test_a_round_after_changes_blocks_only_on_earlier_fixes(self):
        text = brief()
        self.assertRegex(text, r"still missing")
        self.assertRegex(text, r"broke")
        self.assertRegex(text, r"new finding[^.]*follow-up")


class ReviewRoundsTest(FakeClaudeGh):
    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        cls.template = cls._dir.name
        work, _ = make_repo(cls.template, {"loop.json": settings_json(AGENTS)})
        run_git(["push", "origin", "main:loop/main"], work)

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def setUp(self):
        super().setUp()
        self.work, self.origin = copy_repo(self.template, self.tmp)
        self.scenario([
            {"match": "issue view 7", "responses": [{"stdout": json.dumps(
                {"title": "Add it", "body": "Do the thing.", "comments": []})}]},
            {"match": "issue comment", "responses": [{}]}, {"match": "issue edit", "responses": [{}]},
            {"match": "issue create", "responses": [{}]}, {"match": "issue close", "responses": [{}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]}, {"match": "pr edit", "responses": [{}]},
            {"match": "issue list", "responses": [{"stdout": "[]"}]}])
        for name, value in (("merge", MERGED), ("find_pr", {"number": 9})):
            patch = mock.patch.object(merge, name, return_value=value)
            patch.start()
            self.addCleanup(patch.stop)

    def run_build(self, reviews):
        sent, real = [], flow.gh

        def spy(args, input=None, retry=True):
            sent.append((args, input))
            return real(args, input=input, retry=retry)
        patch = mock.patch.object(flow, "gh", side_effect=spy)
        patch.start()
        self.addCleanup(patch.stop)
        self.claude({"test-writer": [WRITER],
                     "builder": [{"files": {"app.py": "1\n"}}, {"files": {"app.py": "2\n"}}],
                     "reviewer": [{"reply": r} for r in reviews]})
        self.assertEqual(flow.build(7, self.work, ()).status, "merged")
        return sent

    def test_the_review_after_changes_gets_the_numbered_fixes(self):
        self.run_build(["VERDICT: CHANGES\nHEAD: {HEAD}\n1. probe-fix-alpha",
                        "VERDICT: APPROVE\nHEAD: {HEAD}\n\n1. none"])
        prompts = [c["prompt"] for c in self.claude_calls() if c["role"] == "reviewer"]
        self.assertEqual(len(prompts), 2)
        self.assertNotIn("probe-fix-alpha", prompts[0])
        self.assertIn("probe-fix-alpha", prompts[1])

    def test_follow_ups_of_every_round_become_inbox_issues(self):
        sent = self.run_build([
            "VERDICT: CHANGES\nHEAD: {HEAD}\n1. fix it\n\nFOLLOW-UPS:\n- Probe follow-up number one\n",
            "VERDICT: APPROVE\nHEAD: {HEAD}\n\nFOLLOW-UPS:\n- Probe follow-up number two\n"])
        titles = [a[a.index("--title") + 1] for a, _ in sent
                  if a[:2] == ["issue", "create"] and "inbox" in a]
        self.assertEqual(sorted(titles), ["Probe follow-up number one", "Probe follow-up number two"])


if __name__ == "__main__":
    unittest.main()
