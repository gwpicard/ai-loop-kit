import json
import os
from pathlib import Path
import unittest
from unittest import mock

from lite.tests.fake_claude import FakeClaudeGh
import tempfile

from lite.tests.helpers import copy_repo, make_repo, run_git
import common
import flow
import merge

AGENTS = "## Loop\nCheck command: test ! -f BAD\nTest command: seq 1 100; test ! -f FAIL && { test ! -f tests/test_new.py || test -f app.py; }\nLoop branch: loop/main\nMax rounds: 2\n"
MERGED = merge.Result(True, False, "merged as abc", "abc")
APPROVE = {"reply": "All good.\n\nVERDICT: APPROVE\nHEAD: {HEAD}\n\n1. none"}
CHANGES = {"reply": "VERDICT: CHANGES\nHEAD: {HEAD}\n\n1. Handle the empty case"}
WRITER = {"files": {"tests/test_new.py": "x\n"}, "reply": "Done.\nTESTS:\ntests/test_new.py"}


def roles(calls):
    return [c["role"] for c in calls]


class FlowTest(FakeClaudeGh):
    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        cls.template = cls._dir.name
        work, _ = make_repo(cls.template, {"AGENTS.md": AGENTS})
        run_git(["push", "origin", "main:loop/main"], work)

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def setUp(self):
        super().setUp()
        self.work, self.origin = copy_repo(self.template, self.tmp)
        self.issue_view()
        patch = mock.patch.object(merge, "merge", return_value=MERGED)
        self.merge = patch.start()
        self.addCleanup(patch.stop)
        pr = mock.patch.object(merge, "find_pr", return_value={"number": 9})
        pr.start()
        self.addCleanup(pr.stop)

    def issue_view(self, comments=(), listed=()):
        self.scenario([
            {"match": "issue view 7", "responses": [{"stdout": json.dumps({
                "title": "Add it", "body": "Do the thing.", "comments": list(comments)})}]},
            {"match": "issue comment", "responses": [{}]},
            {"match": "issue edit", "responses": [{}]},
            {"match": "issue create", "responses": [{}]}, {"match": "issue close", "responses": [{}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]}, {"match": "pr edit", "responses": [{}]},
            {"match": "issue list", "responses": [{"stdout": json.dumps(
                [{"title": t} for t in listed])}]}])

    def build(self, replies=()):
        return flow.build(7, self.work, replies)

    def build_scenario(self, **steps):
        base = {"test-writer": [WRITER], "builder": [{"files": {"app.py": "1\n"}}],
                "reviewer": [APPROVE]}
        base.update(steps)
        self.claude(base)

    def test_happy_path(self):
        self.build_scenario()
        r = self.build(["Use the env var."])
        self.assertEqual(r, flow.Result("merged", "merged as abc"))
        calls = self.claude_calls()
        self.assertEqual(roles(calls), ["test-writer", "builder", "simplify", "reviewer"])
        builder = calls[1]
        self.assertEqual(builder["env"]["LITE_LOCKED"], "tests/test_new.py")
        self.assertIn("Add it", builder["prompt"])
        self.assertIn("Do the thing.", builder["prompt"])
        self.assertIn("PLAN.md", builder["prompt"])
        self.assertIn("Use the env var.", builder["prompt"])
        self.assertIn("Work autonomously", builder["prompt"])
        self.assertIn("Test command: seq 1 100; test ! -f FAIL && { test ! -f tests/test_new.py || test -f app.py; }", builder["prompt"])
        self.assertIn("The builder's last report", calls[3]["prompt"])
        self.assertIn("git diff origin/loop/main...HEAD", calls[3]["prompt"].replace(
            "<loop branch>", "loop/main"))
        self.assertTrue(any(c[:2] == ["issue", "comment"] for c in self.calls()))
        self.merge.assert_called_once()
        self.assertEqual(self.merge.call_args[0][:2], (7, "issue/7"))
        pushed = common.git(["ls-remote", "--heads", self.origin, "issue/7"])
        self.assertIn("refs/heads/issue/7", pushed)
        self.assertNotIn(".lite-worktrees", common.git(["worktree", "list"], cwd=self.work))

    def test_changes_then_approve(self):
        self.build_scenario(reviewer=[CHANGES, APPROVE], builder=[
            {"files": {"app.py": "1\n"}}, {"files": {"app.py": "2\n"}}])
        self.assertEqual(self.build().status, "merged")
        calls = self.claude_calls()
        self.assertEqual(roles(calls), ["test-writer", "builder", "simplify", "reviewer",
                                        "builder", "simplify", "reviewer"])
        fix = calls[4]
        self.assertIn("--resume", fix["argv"])
        self.assertIn("Handle the empty case", fix["prompt"])
        self.assertNotIn("--resume", calls[6]["argv"])

    def test_failing_test_command_resumes_builder(self):
        self.build_scenario(builder=[{"files": {"app.py": "1\n", "FAIL": "x\n"}}, {"remove": ["FAIL"]}])
        self.assertEqual(self.build().status, "merged")
        calls = self.claude_calls()
        self.assertEqual(roles(calls), ["test-writer", "builder", "simplify", "builder",
                                        "simplify", "reviewer"])
        self.assertIn("--resume", calls[3]["argv"])
        tail = calls[3]["prompt"]
        self.assertIn("Test command failed", tail)
        self.assertIn(": 21\n", tail)
        self.assertIn("\n100", tail)
        self.assertNotIn("\n20\n", tail)

    def test_round_limit_parks(self):
        self.build_scenario(reviewer=[CHANGES])
        r = self.build()
        self.assertEqual(r.status, "parked", r.reason)
        self.assertIn("2 rounds", r.reason)
        self.assertEqual(roles(self.claude_calls()).count("reviewer"), 2)
        self.merge.assert_not_called()
        labels = [c for c in self.calls() if c[:2] == ["issue", "edit"]]
        self.assertTrue(any("needs-user" in c for c in labels))

    def test_merge_park_parks(self):
        self.merge.return_value = merge.Result(False, True, "protected path .github/", None)
        self.build_scenario()
        r = self.build()
        self.assertEqual(r.status, "parked", r.reason)
        self.assertIn("protected path", r.reason)
        self.assertEqual(roles(self.claude_calls()).count("reviewer"), 1)

    def test_refused_merge_counts_as_a_round(self):
        self.merge.side_effect = [merge.Result(False, False, "head moved", None), MERGED]
        self.build_scenario()
        self.assertEqual(self.build().status, "merged")
        calls = self.claude_calls()
        self.assertIn("head moved", calls[4]["prompt"])
        self.assertEqual(roles(calls).count("reviewer"), 2)

    def test_stop_line_from_a_session_parks(self):
        self.build_scenario(builder=[{"reply": "PARK: Need an API key | Add it as a secret"}])
        r = self.build()
        self.assertEqual((r.status, r.reason), ("parked", "Need an API key"))
        self.assertEqual(roles(self.claude_calls()), ["test-writer", "builder"])

    def test_session_crash_fails_and_cleans_up(self):
        self.build_scenario(builder=[{"crash": True}])
        r = self.build()
        self.assertEqual(r.status, "failed")
        self.assertIn("builder session", r.reason)
        self.assertIn("refs/heads/issue/7", common.git(["ls-remote", self.origin, "issue/7"]))
        self.assertNotIn(".lite-worktrees", common.git(["worktree", "list"], cwd=self.work))

    def test_reuses_an_existing_origin_branch(self):
        run_git(["push", "origin", "main:issue/7"], self.work)
        self.build_scenario()
        self.assertEqual(self.build().status, "merged")

    def test_rerun_skips_the_test_writer(self):
        run_git(["push", "origin", "main:issue/7"], self.work)
        self.issue_view([{"body": "TESTS:\ntests/test_new.py\n"}])
        self.build_scenario()
        self.assertEqual(self.build().status, "merged")
        calls = self.claude_calls()
        self.assertEqual(roles(calls), ["builder", "simplify", "reviewer"])
        self.assertEqual(calls[0]["env"]["LITE_LOCKED"], "tests/test_new.py")

    def test_a_worktree_left_by_a_crash_does_not_block(self):
        tree = os.path.join(self.tmp, ".lite-worktrees", "work-7")
        run_git(["worktree", "add", "-b", "issue/7", tree, "main"], self.work)
        self.build_scenario()
        self.assertEqual(self.build().status, "merged")

    def test_stop_line_tolerates_bold_and_backticks(self):
        self.build_scenario(builder=[{"reply": "Stuck.\n**`PARK: Need a key | Add a secret`**"}])
        r = self.build()
        self.assertEqual((r.status, r.reason), ("parked", "Need a key"))

    def spy_gh(self):
        sent, real = [], flow.gh

        def spy(args, input=None, retry=True):
            sent.append((args, input))
            return real(args, input=input, retry=retry)
        patch = mock.patch.object(flow, "gh", side_effect=spy)
        patch.start()
        self.addCleanup(patch.stop)
        return sent

    def test_tests_that_pass_on_the_base_resume_the_test_writer_once(self):
        passing = {"files": {"tests/test_ok.py": "x\n"}, "reply": "TESTS:\ntests/test_ok.py"}
        self.build_scenario(**{"test-writer": [passing, WRITER]})
        self.assertEqual(self.build().status, "merged")
        calls = self.claude_calls()
        self.assertEqual(roles(calls)[:3], ["test-writer", "test-writer", "builder"])
        self.assertIn("--resume", calls[1]["argv"])
        self.assertIn("pass before any code exists", calls[1]["prompt"])
        self.assertEqual(calls[2]["env"]["LITE_LOCKED"], "tests/test_new.py")
        self.assertNotIn("lite-merge", common.git(["worktree", "list"], cwd=self.work))

    def test_tests_that_still_pass_on_the_base_park_the_issue(self):
        passing = {"files": {"tests/test_ok.py": "x\n"}, "reply": "TESTS:\ntests/test_ok.py"}
        self.build_scenario(**{"test-writer": [passing]})
        r = self.build()
        self.assertEqual(r.status, "parked", r.reason)
        self.assertIn("pass before any code exists", r.reason)
        self.assertEqual(roles(self.claude_calls()), ["test-writer", "test-writer"])
        self.merge.assert_not_called()
        self.assertNotIn("lite-merge", common.git(["worktree", "list"], cwd=self.work))

    def writer_resumed_then(self, first, second):
        self.build_scenario(**{"test-writer": [first, second]})
        r = self.build()
        calls = self.claude_calls()
        return r, calls

    def test_no_tests_named_resumes_the_writer_once_then_parks(self):
        silent = {"files": {"tests/test_new.py": "x\n"}, "reply": "Done."}
        r, calls = self.writer_resumed_then(silent, silent)
        self.assertEqual(r.status, "parked", r.reason)
        self.assertEqual(roles(calls), ["test-writer", "test-writer"])
        self.assertIn("Name every test file", calls[1]["prompt"])
        self.assertIn("--resume", calls[1]["argv"])
        r, calls = self.writer_resumed_then(silent, WRITER)
        self.assertEqual(r.status, "merged", r.reason)
        self.assertEqual(roles(calls)[:3], ["test-writer", "test-writer", "builder"])

    def test_tests_that_are_missing_or_not_test_files_are_refused(self):
        for bad in ("tests/test_missing.py", "app.py"):
            named = {"files": {"app.py": "1\n"}, "reply": "TESTS:\n" + bad}
            r, calls = self.writer_resumed_then(named, named)
            self.assertEqual((r.status, roles(calls)), ("parked", ["test-writer"] * 2), bad)
        named = {"files": {"app.py": "1\n"}, "reply": "TESTS:\napp.py"}
        r, calls = self.writer_resumed_then(named, WRITER)
        self.assertEqual(r.status, "merged", r.reason)

    def test_a_crash_after_the_merge_still_posts_the_note(self):
        self.crashed_after_merge([])

    def test_an_existing_build_note_is_left_alone_on_a_rerun(self):
        sent = self.crashed_after_merge([{"body": "## Built\n\nThe original note.\n"}])
        names = [a[:2] for a, _ in sent]
        self.assertNotIn(["issue", "comment"], names)
        self.assertNotIn(["pr", "edit"], names)
        self.assertEqual(names.count(["issue", "create"]), 1)

    def test_follow_ups_of_none_create_nothing(self):
        sent = self.spy_gh()
        flow.after_merge(7, "", "FOLLOW-UPS:\nnone\n", "abc", [], None)
        self.assertFalse(any(a[:2] == ["issue", "create"] for a, _ in sent))

    def crashed_after_merge(self, comments):
        sent = self.spy_gh()
        merged = [{"number": 9, "mergeCommit": {"oid": "def456"}, "files": [{"path": "app.py"}]}]
        self.scenario([
            {"match": "issue view 7", "responses": [{"stdout": json.dumps(
                {"title": "t", "body": "b", "comments": comments, "state": "OPEN"})}]},
            {"match": "pr list", "responses": [{"stdout": json.dumps(merged)}]},
            {"match": "pr view 9", "responses": [{"stdout": json.dumps(
                {"comments": [{"body": "VERDICT: APPROVE\nHEAD: abc1234\n\nFOLLOW-UPS:\n- Do more\n"}]})}]},
            {"match": "issue list", "responses": [{"stdout": "[]"}]},
            {"match": "issue", "responses": [{}]}, {"match": "pr edit", "responses": [{}]}])
        self.assertEqual(self.build().status, "merged")
        self.assertEqual(self.claude_calls(), [])
        names = [a[:2] for a, _ in sent]
        self.assertEqual(names.count(["issue", "create"]), 1)
        self.assertEqual(names.count(["issue", "close"]), 1)
        if not comments:
            self.assertEqual(names.count(["issue", "comment"]), 1)
            self.assertEqual(names.count(["pr", "edit"]), 1)
            note = [i for a, i in sent if a[:2] == ["issue", "comment"]][0]
            self.assertIn("Merged as def456.", note)
            self.assertIn("- app.py", note)
        return sent

    def test_check_command_failure_resumes_the_builder(self):
        self.build_scenario(builder=[{"files": {"app.py": "1\n", "BAD": "x\n"}},
                                     {"remove": ["BAD"]}])
        self.assertEqual(self.build().status, "merged")
        calls = self.claude_calls()
        self.assertEqual(roles(calls)[3], "builder")
        self.assertIn("--resume", calls[3]["argv"])
        self.assertIn("Check command failed", calls[3]["prompt"])

    BUILT = {"files": {"app.py": "1\n"}, "reply": "Done.\n\nBUILT:\nAdded app.py.\n\nIt greets "
             "the user.\n\nDEVIATIONS:\nUsed a plain file."}

    def test_build_note_is_posted_once_and_goes_in_the_pull_request(self):
        sent = self.spy_gh()
        self.build_scenario(builder=[self.BUILT])
        self.assertEqual(self.build().status, "merged")
        notes = [i for a, i in sent if a[:2] == ["issue", "comment"] and i.startswith("## Built")]
        self.assertEqual(len(notes), 1)
        note = notes[0]
        for text in ("Added app.py.", "It greets the user.", "Deviations: Used a plain file.",
                     "Merged as abc.", "- app.py", "- tests/test_new.py", common.MARKER):
            self.assertIn(text, note)
        edits = [(a, i) for a, i in sent if a[:2] == ["pr", "edit"]]
        self.assertEqual([(a[2], i) for a, i in edits], [("9", note)])
        order = [a[:2] for a, _ in sent]
        self.assertLess(order.index(["issue", "comment"]), order.index(["pr", "edit"]))

    def test_post_once_skips_a_comment_the_issue_already_has(self):
        self.issue_view([{"body": "## Built\n\nx\n"}])
        flow.post_once(7, "## Built\n\nx\n")
        self.assertFalse(any(c[:2] == ["issue", "comment"] for c in self.calls()))

    def test_a_build_without_a_built_block_says_so(self):
        sent = self.spy_gh()
        self.build_scenario()
        self.build()
        note = [i for a, i in sent if a[:2] == ["issue", "comment"] and i.startswith("## Built")][0]
        self.assertIn("No BUILT block in the builder's report.", note)

    def test_follow_ups_become_inbox_issues_once(self):
        sent = self.spy_gh()
        self.issue_view(listed=["Tidy the parser"])
        review = APPROVE["reply"] + "\n\nFOLLOW-UPS:\n- Tidy the parser\n- Log skipped lines\n"
        self.build_scenario(reviewer=[{"reply": review}])
        self.assertEqual(self.build().status, "merged")
        created = [(a, i) for a, i in sent if a[:2] == ["issue", "create"]]
        self.assertEqual(len(created), 1)
        args, body = created[0]
        self.assertEqual(args[args.index("--title") + 1], "Log skipped lines")
        self.assertEqual(args[args.index("--label") + 1], "inbox")
        self.assertIn("Follow-up from #7.", body)
        self.assertIn(common.MARKER, body)

    def test_follow_ups_already_open_are_not_created_again(self):
        self.issue_view(listed=["Log skipped lines"])
        flow.after_merge(7, "", "FOLLOW-UPS:\n1. Log skipped lines\n", "abc", [], None)
        self.assertFalse(any(c[:2] == ["issue", "create"] for c in self.calls()))

    def test_follow_up_titles_match_ignoring_case_and_punctuation(self):
        self.issue_view(listed=["log skipped lines!"])
        flow.after_merge(7, "", "FOLLOW-UPS:\n1. Log   skipped, lines.\n", "abc", [], None)
        self.assertFalse(any(c[:2] == ["issue", "create"] for c in self.calls()))
        self.assertEqual(flow.same("Don't  Panic!"), flow.same("dont panic"))

    def test_the_note_has_one_merge_line_and_the_brief_asks_for_the_whole_issue(self):
        sent = self.spy_gh()
        self.build_scenario(builder=[self.BUILT])
        self.build()
        note = [i for a, i in sent if a[:2] == ["issue", "comment"] and i.startswith("## Built")][0]
        self.assertEqual(note.count("Merged"), 1)
        brief = Path(flow.BRIEFS, "builder.md").read_text(encoding="utf-8")
        for text in ("not only the last fix", "the loop adds one merge line"):
            self.assertIn(text, brief)

    def test_the_note_lists_what_the_sessions_left_behind(self):
        flow.session.SWEPT[7] = ["removed container abc", "new image def (kept)"]
        self.addCleanup(flow.session.SWEPT.clear)
        sent = self.spy_gh()
        flow.after_merge(7, "BUILT:\nx\nDEVIATIONS:\nnone", "", "abc", [], None)
        note = [i for a, i in sent if a[:2] == ["issue", "comment"]][0]
        self.assertIn("Left behind by sessions:\n- removed container abc\n- new image def (kept)\n", note)

    def failed_note(self, error):
        with mock.patch.object(flow, "after_merge", side_effect=error):
            self.build_scenario()
            self.assertEqual(self.build().status, "merged")
        with open(os.path.join(self.work, ".lite", "events.jsonl")) as f:
            self.assertEqual(f.read().count("note-failed"), 1)

    def test_a_failed_note_does_not_undo_the_merge(self):
        self.failed_note(common.GitHubError("down"))

    def test_any_error_in_the_note_is_logged_not_raised(self):
        self.failed_note(KeyError("title"))

    def test_parse_tests(self):
        self.assertEqual(flow.parse_block("a\nTESTS:\n- t/a.py\n`t/b.py`\n\nbye"),
                         ["t/a.py", "t/b.py"])
        self.assertEqual(flow.parse_block("no block"), [])


if __name__ == "__main__":
    unittest.main()
