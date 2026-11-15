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

AGENTS = "## Loop\nCheck command: test ! -f BAD\nTest command: seq 1 99; { test ! -f FAIL && { test ! -f tests/test_new.py || test -f app.py; }; } || { echo AssertionError; false; }\nLoop branch: loop/main\nMax rounds: 2\n"
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
        self.assertEqual(roles(calls), ["test-writer", "builder", "reviewer"])
        builder = calls[1]
        self.assertEqual(builder["env"]["LITE_LOCKED"], "tests/test_new.py")
        self.assertIn("Add it", builder["prompt"])
        self.assertIn("Do the thing.", builder["prompt"])
        self.assertIn("PLAN.md", builder["prompt"])
        self.assertIn("Use the env var.", builder["prompt"])
        self.assertIn("Work autonomously", builder["prompt"])
        self.assertIn("Test command: seq 1 99; { test ! -f FAIL && { test ! -f tests/test_new.py || test -f app.py; }; } || { echo AssertionError; false; }", builder["prompt"])
        self.assertIn("The builder's last report", calls[2]["prompt"])
        self.assertIn("git diff origin/loop/main...HEAD", calls[2]["prompt"].replace(
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
        self.assertEqual(roles(calls), ["test-writer", "builder", "reviewer",
                                        "builder", "reviewer"])
        fix = calls[3]
        self.assertIn("--resume", fix["argv"])
        self.assertIn("Handle the empty case", fix["prompt"])
        self.assertNotIn("--resume", calls[4]["argv"])

    def test_failing_test_command_resumes_builder(self):
        self.build_scenario(builder=[{"files": {"app.py": "1\n", "FAIL": "x\n"}}, {"remove": ["FAIL"]}])
        self.assertEqual(self.build().status, "merged")
        calls = self.claude_calls()
        self.assertEqual(roles(calls), ["test-writer", "builder", "builder", "reviewer"])
        self.assertIn("--resume", calls[2]["argv"])
        tail = calls[2]["prompt"]
        self.assertIn("Test command failed", tail)
        self.assertIn(": 21\n", tail)
        self.assertIn("\nAssertionError", tail)
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
        self.assertIn("head moved", calls[3]["prompt"])
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

    def push_commit(self, name, remote_branch, text):
        run_git(["checkout", "-q", "-b", name, "main"], self.work)
        with open(os.path.join(self.work, "app.py"), "w") as f:
            f.write(text)
        run_git(["add", "-A"], self.work)
        run_git(["commit", "-qm", name], self.work)
        run_git(["push", "origin", "%s:%s" % (name, remote_branch)], self.work)
        run_git(["checkout", "-q", "main"], self.work)

    def test_a_reused_branch_gains_what_the_loop_branch_gained(self):
        run_git(["push", "origin", "main:issue/7"], self.work)
        with open(os.path.join(self.work, "gained.txt"), "w") as f:
            f.write("x\n")
        run_git(["checkout", "-q", "-b", "later", "main"], self.work)
        run_git(["add", "-A"], self.work)
        run_git(["commit", "-qm", "gained on the loop branch"], self.work)
        run_git(["push", "origin", "later:loop/main"], self.work)
        self.issue_view([{"body": "TESTS:\ntests/test_new.py\n"}])
        self.build_scenario(builder=[{"files": {"other.py": "1\n"}}])
        self.assertEqual(self.build().status, "merged")
        files = common.git(["ls-tree", "-r", "--name-only", "issue/7"], cwd=self.origin).split()
        self.assertIn("gained.txt", files)
        self.assertIn("other.py", files)

    def conflicted(self, *steps):
        self.push_commit("mine", "issue/7", "branch\n")
        self.push_commit("theirs", "loop/main", "loop\n")
        self.issue_view([{"body": "TESTS:\ntests/test_new.py\n"}])
        self.build_scenario(builder=list(steps) + [{"files": {"other.py": "1\n"}}])
        return self.build()

    def test_the_builder_resolves_a_conflict_with_the_loop_branch(self):
        r = self.conflicted({"files": {"app.py": "both\n"}})
        self.assertEqual(r.status, "merged")
        first = self.claude_calls()[0]
        self.assertEqual(first["role"], "builder")
        self.assertIn("First task", first["prompt"])
        self.assertIn("conflicts in: app.py", first["prompt"])
        files = common.git(["show", "issue/7:app.py"], cwd=self.origin)
        self.assertEqual(files, "both")
        self.assertTrue(common.git(["log", "--merges", "--format=%s", "issue/7"], cwd=self.origin))

    def test_an_unfinished_merge_parks_and_names_the_paths(self):
        r = self.conflicted({"reply": "I could not."})
        self.assertEqual(r.status, "parked")
        self.assertIn("conflicts with loop/main in: app.py", r.reason)
        self.assertEqual(roles(self.claude_calls()), ["builder"])
        self.assertNotIn(".lite-worktrees", common.git(["worktree", "list"], cwd=self.work))

    def test_conflict_markers_left_in_a_committed_merge_park(self):
        r = self.conflicted({"files": {"app.py": "<<<<<<< HEAD\nbranch\n=======\nloop\n>>>>>>> origin/loop/main\n"}})
        self.assertEqual(r.status, "parked")
        self.assertEqual(roles(self.claude_calls()), ["builder"])

    def test_the_local_issue_branch_goes_after_a_merge_but_stays_when_parked(self):
        self.build_scenario(builder=[{"reply": "Stuck.\nPARK: Need a key | Add a secret"}])
        self.assertEqual(self.build().status, "parked")
        self.assertIn("issue/7", common.git(["branch", "--list", "issue/7"], cwd=self.work))
        self.build_scenario()
        self.assertEqual(self.build().status, "merged")
        self.assertEqual(common.git(["branch", "--list", "issue/7"], cwd=self.work), "")

    def test_rerun_skips_the_test_writer(self):
        run_git(["push", "origin", "main:issue/7"], self.work)
        self.issue_view([{"body": "TESTS:\ntests/test_new.py\n"}])
        self.build_scenario()
        self.assertEqual(self.build().status, "merged")
        calls = self.claude_calls()
        self.assertEqual(roles(calls), ["builder", "reviewer"])
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
        self.assertNotIn("lite-tree", common.git(["worktree", "list"], cwd=self.work))

    def test_tests_that_still_pass_on_the_base_park_the_issue(self):
        passing = {"files": {"tests/test_ok.py": "x\n"}, "reply": "TESTS:\ntests/test_ok.py"}
        self.build_scenario(**{"test-writer": [passing]})
        r = self.build()
        self.assertEqual(r.status, "parked", r.reason)
        self.assertIn("pass before any code exists", r.reason)
        self.assertEqual(roles(self.claude_calls()), ["test-writer", "test-writer"])
        self.merge.assert_not_called()
        self.assertNotIn("lite-tree", common.git(["worktree", "list"], cwd=self.work))

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
        self.assertEqual(roles(calls)[2], "builder")
        self.assertIn("--resume", calls[2]["argv"])
        self.assertIn("Check command failed", calls[2]["prompt"])

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

    def test_every_verdict_is_posted_on_the_issue(self):
        sent = self.spy_gh()
        self.build_scenario(reviewer=[{"reply": "VERDICT: CHANGES\nHEAD: {HEAD}\n1. fix it"}, APPROVE])
        self.assertEqual(self.build().status, "merged")
        posts = [i for a, i in sent if a[:2] == ["issue", "comment"] and i.startswith("## Review, round")]
        self.assertEqual([p.splitlines()[0] for p in posts], ["## Review, round 1", "## Review, round 2"])
        self.assertIn("VERDICT: CHANGES", posts[0])
        self.assertIn("1. fix it", posts[0])
        self.assertIn("VERDICT: APPROVE", posts[1])
        self.assertTrue(all(common.MARKER in p for p in posts))

    def test_review_rounds_continue_after_earlier_ones(self):
        sent = self.spy_gh()
        self.issue_view([{"body": "## Review, round 1\n\nVERDICT: CHANGES\nHEAD: x\n\n" + common.MARKER},
                         {"body": "## Review, round 4\n\nVERDICT: CHANGES\n"}])
        self.build_scenario(reviewer=[APPROVE])
        self.assertEqual(self.build().status, "merged")
        posts = [i for a, i in sent if a[:2] == ["issue", "comment"] and i.startswith("## Review, round")]
        self.assertEqual([p.splitlines()[0] for p in posts], ["## Review, round 5"])

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

    def test_the_built_text_is_kept_whole_and_the_loop_adds_one_merge_line(self):
        sent = self.spy_gh()
        built = dict(self.BUILT, reply="BUILT:\nAdded app.py. Merged the loop branch into the issue branch.\nDEVIATIONS:\nnone")
        self.build_scenario(builder=[built])
        self.build()
        note = [i for a, i in sent if a[:2] == ["issue", "comment"] and i.startswith("## Built")][0]
        self.assertEqual(note.count("Merged as"), 1)
        self.assertIn("Added app.py. Merged the loop branch into the issue branch.", note)
        brief = Path(flow.BRIEFS, "builder.md").read_text(encoding="utf-8")
        self.assertIn("quote commit hashes", brief)

    def test_the_builder_brief_leaves_a_locked_test_conflict_to_the_loop(self):
        brief = Path(flow.BRIEFS, "builder.md").read_text(encoding="utf-8")
        self.assertIn("conflict inside an existing test file cannot be resolved", brief)
        self.assertIn("the loop then parks", brief)

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

    def fast(self, **lines):
        """Rewrite the settings of the project the build reads; markers go to files in tmp."""
        text = "## Loop\nLoop branch: loop/main\nMax rounds: 3\n" + "".join(
            "%s: %s\n" % (k.replace("_", " "), v.replace("TMP", self.tmp)) for k, v in lines.items())
        with open(os.path.join(self.work, "AGENTS.md"), "w") as f:
            f.write(text)

    def runs(self, name):
        try:
            with open(os.path.join(self.tmp, name + ".log")) as f:
                return f.read().split("\n")[:-1]
        except OSError:
            return []

    FULL = "echo full >> TMP/full.log; test -f app.py || { echo AssertionError; false; }"
    FILES = "echo {files} >> TMP/files.log; test -f app.py || { echo AssertionError; false; }"
    PASSED = {"files": {"app.py": "1\n"}, "passed": True}

    def test_fails_first_runs_only_the_locked_files_with_the_test_files_command(self):
        self.fast(Test_command=self.FULL, Test_files_command=self.FILES)
        self.build_scenario(builder=[self.PASSED])
        self.assertEqual(self.build().status, "merged")
        self.assertEqual(self.runs("files"), ["tests/test_new.py"])
        self.assertEqual(self.runs("full"), [])

    def test_fails_first_falls_back_to_the_test_command(self):
        self.fast(Test_command=self.FULL)
        self.build_scenario(builder=[self.PASSED])
        self.assertEqual(self.build().status, "merged")
        self.assertEqual(self.runs("full"), ["full"])

    def test_tests_that_fail_by_a_syntax_error_are_not_failing_by_assertion(self):
        self.fast(Test_command="true", Test_files_command="echo 'SyntaxError: invalid syntax'; exit 1")
        self.build_scenario()
        r = self.build()
        self.assertEqual(r.status, "parked", r.reason)
        self.assertIn("by assertion", r.reason)
        self.assertEqual(roles(self.claude_calls()), ["test-writer", "test-writer"])

    def first_fails(self, command, body="Do the thing.", **more):
        self.fast(Test_command="true", Test_files_command=command, **more)
        common.git(["push", "origin", "--delete", "issue/7"], cwd=self.work, check=False)
        common.git(["branch", "-D", "issue/7"], cwd=self.work, check=False)
        self.claude({})
        self.scenario_body(body)
        self.build_scenario()
        r = self.build()
        return r, roles(self.claude_calls())

    def scenario_body(self, body):
        self.scenario([{"match": "issue view 7", "responses": [{"stdout": json.dumps(
            {"title": "Add it", "body": body, "comments": []})}]}, {"match": "issue", "responses": [{}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]}])

    def test_a_command_that_cannot_run_or_times_out_is_not_a_failing_test(self):
        for command in ("exit 127", "nosuchcommand_xyz {files}"):
            r, called = self.first_fails(command)
            self.assertEqual((r.status, called), ("parked", ["test-writer"] * 2), command)
            self.assertIn("could not run", r.reason)
        merge.TEST_TIMEOUT, old = 1, merge.TEST_TIMEOUT
        self.addCleanup(setattr, merge, "TEST_TIMEOUT", old)
        r, _ = self.first_fails("sleep 30")
        self.assertIn("timed out", r.reason)

    def test_a_prepare_failure_in_the_fails_first_checkout_is_not_proof(self):
        self.fast(Test_command="true", Test_files_command="echo AssertionError; false",
                  Prepare_command="test -f app.py || { echo no deps; exit 4; }")
        self.build_scenario()
        r = self.build()  # the worktree itself prepares first, so Prepare must already fail there
        self.assertEqual(r.status, "failed")
        self.assertIn("Prepare command failed", r.reason)

    def test_fails_first_needs_an_assertion_or_a_name_the_issue_introduces(self):
        r, called = self.first_fails("echo 'Traceback'; echo 'ValueError: boom'; false")
        self.assertEqual((r.status, called), ("parked", ["test-writer"] * 2))
        self.assertIn("do not fail by assertion", r.reason)
        for output in ("AssertionError: 1 != 2", "--- FAIL: TestX", "Expected: 1\nReceived: 2", "3 failed, 1 passed",
                       "FAIL: test_x (t.T)", "expected 1 got 2"):
            r, _ = self.first_fails("printf '%s\\n' '" + output.replace("\n", "' '") + "'; false")
            self.assertEqual(r.status, "merged", output)
        r, _ = self.first_fails("echo 'FAILED (errors=1)'; echo 'ERROR: test_x'; false")
        self.assertEqual(r.status, "parked")
        r, _ = self.first_fails("echo \"ModuleNotFoundError: No module named 'widgets'\"; false", body="Add the widgets module.")
        self.assertEqual(r.status, "merged")
        r, _ = self.first_fails("echo \"ModuleNotFoundError: No module named 'other'\"; false", body="Add the widgets module.")
        self.assertEqual(r.status, "parked")

    def test_the_full_command_runs_after_the_builder_only_when_the_stop_hook_did_not_pass_the_head(self):
        self.fast(Test_command=self.FULL, Test_files_command=self.FILES)
        self.build_scenario(builder=[{"files": {"app.py": "1\n"}}])
        self.assertEqual(self.build().status, "merged")
        self.assertEqual(self.runs("full"), ["full"])
        self.assertEqual(roles(self.claude_calls()), ["test-writer", "builder", "reviewer"])

    def fix_pass(self, extra):
        self.fast(Test_command=self.FULL, Test_files_command=self.FILES)
        self.build_scenario(reviewer=[CHANGES, APPROVE],
                            builder=[self.PASSED, dict({"files": {"app.py": "2\n"}}, **extra)])
        self.assertEqual(self.build().status, "merged")
        return self.runs("full")

    def test_a_fix_pass_the_hook_passed_is_not_run_again(self):
        self.assertEqual(self.fix_pass({"passed": True}), [])

    def test_a_fix_pass_the_hook_did_not_pass_runs_the_full_command(self):
        self.assertEqual(self.fix_pass({}), ["full"])

    def test_a_failure_found_by_the_flow_goes_back_to_the_builder_with_its_tail(self):
        self.fast(Test_command="echo full >> TMP/full.log; test -f app.py && test ! -f FAIL || { echo AssertionError; false; }")
        self.build_scenario(builder=[{"files": {"app.py": "1\n", "FAIL": "x\n"}}, {"remove": ["FAIL"]}])
        self.assertEqual(self.build().status, "merged")
        self.assertIn("Test command failed", self.claude_calls()[2]["prompt"])

    def test_the_reviewer_gets_the_latest_result_and_the_test_files_command(self):
        self.fast(Test_command=self.FULL, Test_files_command=self.FILES)
        self.build_scenario(builder=[self.PASSED])
        self.build()
        prompt = self.claude_calls()[-1]["prompt"]
        self.assertIn("Latest test result: passed on this commit.", prompt)
        self.assertIn("all passed", prompt)
        self.assertIn("Test files command: echo {files}", prompt)
        brief = Path(flow.BRIEFS, "reviewer.md").read_text(encoding="utf-8")
        self.assertIn("do not run the full Test command", brief)
        self.assertNotIn("Run the Test command and your own checks", brief)

    def test_the_reviewer_sees_the_tail_when_the_flow_ran_the_tests(self):
        self.fast(Test_command="echo full >> TMP/full.log; test -f app.py && echo ran-fine", Test_files_command=self.FILES)
        self.build_scenario(builder=[{"files": {"app.py": "1\n"}}])
        self.build()
        self.assertIn("Test command passed: ran-fine", self.claude_calls()[-1]["prompt"])

    def test_the_builder_is_told_to_test_the_files_it_touches_and_leave_the_full_run_to_the_hook(self):
        self.fast(Test_command=self.FULL, Test_files_command=self.FILES)
        self.build_scenario(builder=[self.PASSED])
        self.build()
        prompt = self.claude_calls()[1]["prompt"]
        self.assertIn("Test files command: echo {files}", prompt)
        brief = Path(flow.BRIEFS, "builder.md").read_text(encoding="utf-8")
        for text in ("Test files command", "Stop hook runs the full"):
            self.assertIn(text, brief)

    def test_simplify_is_not_a_brief_any_more(self):
        self.assertFalse(Path(flow.BRIEFS, "simplify.md").exists())

    def test_prepare_runs_in_the_new_worktree(self):
        self.fast(Test_command=self.FULL, Prepare_command='echo "$PWD" >> TMP/prep.log')
        self.build_scenario(builder=[self.PASSED])
        self.assertEqual(self.build().status, "merged")
        prepared = self.runs("prep")
        self.assertTrue(prepared[0].endswith(".lite-worktrees/work-7"), prepared)

    def test_a_failing_prepare_command_fails_the_build(self):
        self.fast(Test_command="true", Prepare_command="echo no deps; exit 4")
        self.build_scenario()
        r = self.build()
        self.assertEqual(r.status, "failed")
        self.assertIn("Prepare command failed", r.reason)
        self.assertEqual(self.claude_calls(), [])

    def test_a_folder_that_is_not_a_worktree_is_renamed_aside_never_deleted(self):
        tree = os.path.join(self.tmp, ".lite-worktrees", "work-7")
        os.makedirs(tree)
        with open(os.path.join(tree, "keep.txt"), "w") as f:
            f.write("mine\n")
        self.build_scenario()
        self.assertEqual(self.build().status, "merged")
        aside = [n for n in os.listdir(os.path.dirname(tree)) if n.startswith("work-7.stale-")]
        self.assertEqual(len(aside), 1)
        with open(os.path.join(os.path.dirname(tree), aside[0], "keep.txt")) as f:
            self.assertEqual(f.read(), "mine\n")

    def test_parse_tests(self):
        self.assertEqual(flow.parse_block("a\nTESTS:\n- t/a.py\n`t/b.py`\n\nbye"),
                         ["t/a.py", "t/b.py"])
        self.assertEqual(flow.parse_block("no block"), [])


if __name__ == "__main__":
    unittest.main()
