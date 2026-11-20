import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest import mock

from kit.tests.helpers import copy_repo, make_repo, run_git
import common
import flow
import loop
import merge
import pass_

AGENTS = "## Loop\nTest command: true\nLoop branch: loop/main\nIdle hours: 0\n"
FACTORY = {"number": 1, "title": "Factory", "body": ""}
TEMPLATE = None


def setUpModule():
    global TEMPLATE
    TEMPLATE = tempfile.TemporaryDirectory()
    work, _ = make_repo(TEMPLATE.name, {"AGENTS.md": AGENTS})
    run_git(["push", "origin", "main:loop/main"], work)


def tearDownModule():
    TEMPLATE.cleanup()


def out(value):
    return {"stdout": json.dumps(value)}


def issue(number, labels=("ready",), body=""):
    return {"number": number, "title": "Piece %d" % number, "body": body,
            "labels": [{"name": n} for n in labels]}


def comment(body, user="me"):
    return {"body": body, "author": {"login": user}}


class Base(unittest.TestCase):
    """The loop with gh answered in process, flow.build replaced and no real sleeps."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = os.path.join(self._tmp.name, "work")
        self.addCleanup(mock.patch.stopall)
        self.say = mock.patch.object(loop, "say", return_value=None).start()
        mock.patch.object(loop.time, "sleep").start()
        mock.patch.object(common, "_run_gh", self.fake_gh).start()
        self.rules, self.calls, self.inputs, self.built = [], [], [], []

    def fake_gh(self, args, input=None):
        text = " ".join(args)
        self.calls.append(text)
        self.inputs.append((text, input))
        for rule in self.rules:
            if rule["match"] in text:
                return 0, rule.get("stdout", ""), ""
        return 0, "", ""

    def world(self, open_issues, closed=(), comments=(), prs=(), board="", permission="write"):
        self.rules = [
            {"match": "--json comments", **out({"comments": list(comments)})},
            {"match": "issue list --state open", **out([dict(FACTORY, body=board)] + open_issues)},
            {"match": "issue list --state closed", **out([{"number": n} for n in closed])},
            {"match": "pr list", **out(list(prs))},
            {"match": "permission", **out({"permission": permission})}]

    def writes(self, word):
        return [c for c in self.calls if word in c]

    def board_inputs(self):
        return [i for c, i in self.inputs if c.startswith("issue edit 1 ")]

    def stop_after(self):
        """The fake world never changes, so end the run after a build."""
        os.makedirs(os.path.join(self.work, ".loop"), exist_ok=True)
        open(os.path.join(self.work, ".loop", "stop"), "w").close()

    def fake_build(self, results=None):
        def build(number, project, replies=()):
            self.built.append((number, list(replies)))
            self.stop_after()
            r = (results or {}).get(number)
            if isinstance(r, Exception):
                raise r
            return r or flow.Result("merged", "done")
        return mock.patch.object(flow, "build", side_effect=build)

    def run_loop(self, trusted=True):
        with mock.patch.object(common, "ready_is_trusted", return_value=trusted):
            return loop.run(self.work)


class LoopTest(Base):
    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.work, ".loop"))
        with open(os.path.join(self.work, "AGENTS.md"), "w") as f:
            f.write(AGENTS)
        mock.patch.object(loop, "sync_default").start()
        mock.patch.object(loop, "drain").start()

    def pid_file(self):
        return os.path.join(self.work, ".loop", "loop.pid")

    def test_dead_pid_lock_is_taken_over(self):
        self.world([])
        dead = subprocess.Popen(["true"])
        dead.wait()
        with open(self.pid_file(), "w") as f:
            f.write(str(dead.pid))
        self.assertEqual(self.run_loop(), 0)
        self.assertFalse(os.path.exists(self.pid_file()))

    def test_live_pid_refuses(self):
        self.world([])
        with open(self.pid_file(), "w") as f:
            f.write(str(os.getppid()))
        self.assertEqual(self.run_loop(), 1)
        self.assertIn("refused", self.say.call_args[0][0])
        self.assertIn("next:", self.say.call_args[0][0])
        self.assertTrue(os.path.exists(self.pid_file()))
        self.assertEqual(self.calls, [])

    def test_a_live_loop_of_kit_2_0_0_in_lite_refuses(self):
        self.world([])
        os.makedirs(os.path.join(self.work, ".lite"))
        with open(os.path.join(self.work, ".lite", "loop.pid"), "w") as f:
            f.write(str(os.getppid()))
        self.assertEqual(self.run_loop(), 1)
        self.assertIn("running from .lite/", self.say.call_args[0][0])
        self.assertFalse(os.path.exists(self.pid_file()))
        self.assertEqual(self.calls, [])

    def test_stop_file_exits(self):
        self.world([])
        with open(os.path.join(self.work, "AGENTS.md"), "w") as f:
            f.write(AGENTS.replace("Idle hours: 0", "Idle hours: 5"))
        old = os.getcwd()
        os.chdir(self.work)
        self.addCleanup(os.chdir, old)
        asked = []

        def ask_once(seconds):
            # time.sleep is patched for the whole process: on Linux subprocess.run polls with it
            # while clean_up runs git, so only the loop's first sleep may ask for the stop
            if not asked:
                asked.append(seconds)
                loop.main(["stop"])
        loop.time.sleep.side_effect = ask_once
        self.assertEqual(self.run_loop(), 0)
        self.assertIn("stop requested", self.say.call_args_list[-2][0][0])
        self.assertFalse(os.path.exists(os.path.join(self.work, ".loop", "stop")))

    def test_a_failing_clean_up_is_logged_and_leaves_no_lock(self):
        self.world([])
        with mock.patch.object(loop, "clean_up", side_effect=OSError("denied")):
            self.assertEqual(self.run_loop(), 0)
        self.assertIn("clean-up problem: denied", [c[0][0] for c in self.say.call_args_list])
        self.assertFalse(os.path.exists(self.pid_file()))

    def test_stale_stop_file_is_removed_at_start(self):
        self.world([issue(2)])
        self.stop_after()
        with self.fake_build():
            self.run_loop()
        self.assertEqual(len(self.built), 1)

    def test_picks_lowest_buildable_skipping_the_rest(self):
        self.world([issue(5), issue(3, body="Depends on: #9"), issue(4, ("inbox",)),
                    issue(6, body="Depends on: #2, #3"), issue(7, ("ready", "building"))],
                   closed=[2, 9])
        trusted = {3: True, 5: False}
        with mock.patch.object(common, "ready_is_trusted", side_effect=lambda n: trusted[n]):
            st = loop.new_state()
            loop.snapshot(st)
            self.assertEqual(loop.pick(st), 3)
            trusted[3] = False
            self.assertEqual(loop.pick(st), 3)  # trust is cached for the run
            st["trust"].clear()
            self.assertIsNone(loop.pick(st))
        self.world([issue(6, body="Depends on: #2, #3")], closed=[2])
        st = loop.new_state()
        loop.snapshot(st)
        with mock.patch.object(common, "ready_is_trusted", return_value=True):
            self.assertIsNone(loop.pick(st))

    def test_build_swaps_ready_for_building(self):
        self.world([issue(2)])
        with self.fake_build():
            self.run_loop()
        edits = self.writes("issue edit 2")
        self.assertEqual(edits[0], "issue edit 2 --add-label building")
        self.assertEqual(edits[1], "issue edit 2 --remove-label ready")

    def test_reply_requeues_a_parked_issue_and_reaches_the_build(self):
        self.world([issue(4, ("needs-user",))], comments=[
            comment("## Needs you\n\nWhich port?\n\nRecommended: 80\n\n" + common.MARKER),
            comment("Crashed, trying again.\n\n" + common.MARKER), comment("Use 8080.")])
        with self.fake_build():
            self.run_loop()
        edits = self.writes("issue edit 4")
        self.assertEqual(edits[:2], ["issue edit 4 --remove-label needs-user",
                                     "issue edit 4 --add-label ready"])
        self.assertEqual(self.built, [(4, ["Use 8080."])])

    PARK = "## Needs you\n\ntests/test_x.py fails the lint check. May I change tests/test_x.py?\n\nRecommended: yes, reformat it\n\n" + common.MARKER

    def agree(self, reply, park=PARK, body="Do it.\n", user="me", extra=()):
        self.world([issue(4, ("needs-user",), body=body)], comments=[comment(park)] + list(extra) + [comment(reply, user)])
        with self.fake_build():
            self.run_loop()
        return [i for c, i in self.inputs if c.startswith("issue edit 4 --body-file")]

    def test_a_yes_to_a_park_about_one_test_path_adds_that_path_to_the_issue(self):
        edits = self.agree("Yes, go ahead.")
        self.assertEqual(len(edits), 1)
        self.assertEqual(merge.allowed_paths(edits[0]), {"tests/test_x.py"})
        self.assertIn("Do it.", edits[0])
        self.assertEqual(self.built, [(4, ["Yes, go ahead."])])

    def test_the_path_joins_an_existing_paths_section(self):
        edits = self.agree("yes", body="Do it.\n\n## Paths the builder may change\n\nsrc/a.py\n\n## Notes\n\nx\n")
        self.assertEqual(merge.allowed_paths(edits[0]), {"src/a.py", "tests/test_x.py"})
        self.assertIn("## Notes", edits[0])
        edits = self.agree("yes", body="## Paths the builder may change\n\nnone\n")
        self.assertEqual(merge.allowed_paths(edits[-1]), {"tests/test_x.py"})

    def test_a_reply_that_does_not_clearly_agree_adds_nothing(self):
        for reply in ("No, leave it.", "Yes, but not that file.", "Which one do you mean?", "Maybe", "yes and also no"):
            with self.subTest(reply=reply):
                self.assertEqual(self.agree(reply), [])

    def test_the_loops_own_comment_or_a_stranger_never_grants_a_path(self):
        self.assertEqual(self.agree("Yes.\n\n" + common.MARKER, user="me"), [])
        self.world([issue(4, ("needs-user",))], comments=[comment(self.PARK), comment("yes", "stranger")], permission="read")
        self.run_loop()
        self.assertEqual([i for c, i in self.inputs if c.startswith("issue edit 4 --body-file")], [])

    def test_a_path_the_stops_list_covers_is_never_granted(self):
        for path in (".claude/tests/test_x.py", ".github/workflows/tests/test_a.py", "tests/package.json",
                     "tests/requirements.txt", "tests/settings.json"):
            with self.subTest(path=path):
                park = "## Needs you\n\nMay I change %s?\n\nRecommended: yes\n\n%s" % (path, common.MARKER)
                self.assertEqual(self.agree("yes", park=park), [])

    def test_a_needs_you_comment_without_the_loop_marker_is_no_park(self):
        park = self.PARK.replace("\n\n" + common.MARKER, "")
        self.assertNotIn(common.MARKER, park)
        self.assertEqual(self.agree("yes", park=park), [])
        self.assertEqual(self.writes("issue edit 4"), [])  # not even requeued

    def test_only_a_park_naming_exactly_one_test_path_and_asking_to_change_it_counts(self):
        for park in ("## Needs you\n\nWhich port?\n\nRecommended: 80",
                     "## Needs you\n\nMay I change tests/test_x.py and tests/test_y.py?\n\nRecommended: yes\n\n" + common.MARKER,
                     "## Needs you\n\nMay I change src/app.py?\n\nRecommended: yes\n\n" + common.MARKER,
                     "## Needs you\n\ntests/test_x.py is slow.\n\nRecommended: wait\n\n" + common.MARKER):
            with self.subTest(park=park):
                self.assertEqual(self.agree("yes", park=park), [])

    def test_no_reply_or_a_stranger_leaves_it_parked(self):
        park = comment("## Needs you\n\nWhich port?\n\nRecommended: 80\n\n" + common.MARKER)
        for extra, permission in (([], "write"), ([comment("do it", "stranger")], "read")):
            self.world([issue(4, ("needs-user",))], comments=[park] + extra,
                       permission=permission)
            self.run_loop()
            self.assertEqual(self.writes("issue edit 4"), [])

    def test_crash_is_retried_once_then_succeeds(self):
        self.world([issue(2)])
        tries = []

        def build(number, project, replies=()):
            tries.append(number)
            self.stop_after()
            if len(tries) == 1:
                raise RuntimeError("boom")
            return flow.Result("merged", "ok")
        with mock.patch.object(flow, "build", side_effect=build):
            self.run_loop()
        self.assertEqual(tries, [2, 2])
        self.assertEqual(len(self.writes("issue comment 2")), 1)
        self.assertEqual(self.writes("needs-user"), [])

    def test_second_crash_parks(self):
        self.world([issue(2)])
        with self.fake_build({2: RuntimeError("boom")}):
            self.run_loop()
        self.assertEqual(len(self.built), 2)
        self.assertEqual(len(self.writes("--add-label needs-user")), 1)
        self.assertEqual(len(self.writes("issue comment 2")), 2)

    def test_failed_result_counts_as_a_crash(self):
        self.world([issue(2)])
        with self.fake_build({2: flow.Result("failed", "no worktree")}):
            self.run_loop()
        self.assertEqual(len(self.built), 2)
        self.assertEqual(len(self.writes("--add-label needs-user")), 1)

    def test_github_trouble_is_not_a_crash_and_building_is_restored(self):
        self.world([issue(2)])
        with self.fake_build({2: common.GitHubError("gh issue view failed: HTTP 502")}):
            self.run_loop()
        self.assertEqual(len(self.built), 1)
        self.assertEqual(self.writes("issue comment"), [])
        self.assertEqual(self.writes("needs-user"), [])
        loop.time.sleep.assert_any_call(loop.POLL)
        self.world([issue(2, ("building",))])  # the next cycle, or a killed run
        self.calls.clear()
        with self.fake_build():
            self.run_loop()
        self.assertEqual(self.writes("issue edit 2")[:2], ["issue edit 2 --add-label ready",
                                                           "issue edit 2 --remove-label building"])

    def test_any_exception_in_a_cycle_is_one_line_and_the_loop_goes_on(self):
        self.rules = [{"match": "issue list", "stdout": "not json"}]
        loop.time.sleep.side_effect = lambda s: self.stop_after()
        self.assertEqual(self.run_loop(), 0)
        problem = [c[0][0] for c in self.say.call_args_list if c[0][0].startswith("problem")]
        self.assertEqual(len(problem), 1)
        self.assertNotIn("\n", problem[0])

    def test_every_comment_the_loop_posts_carries_the_marker(self):
        self.world([issue(2)])
        with self.fake_build({2: RuntimeError("boom")}):
            self.run_loop()
        posted = [i for c, i in self.inputs if c.startswith("issue comment")]
        self.assertEqual(len(posted), 2)  # the retry note and the park comment
        self.assertTrue(all(common.MARKER in body for body in posted))
        self.inputs.clear()
        flow.post_once(2, "TESTS:\ntests/test_a.py\n\n" + common.MARKER + "\n")
        body = [i for c, i in self.inputs if c.startswith("issue comment")][0]
        self.assertIn(common.MARKER, body)
        self.assertEqual(merge.locked_paths([{"body": body}]), ["tests/test_a.py"])

    def test_idle_exit_says_why(self):
        self.world([])
        self.assertEqual(self.run_loop(), 0)
        said = [c[0][0] for c in self.say.call_args_list]
        self.assertIn("exiting: nothing built for 0 hours", said)
        with open(os.path.join(self.work, ".loop", "events.jsonl")) as f:
            exits = [e for e in map(json.loads, f) if e["kind"] == "exit"]
        self.assertEqual([e["reason"] for e in exits], ["nothing built for 0 hours"])
        self.assertTrue(said[-1].startswith("left behind: "))

    def test_board_body_renders_every_section(self):
        body = loop.board_body([("Building now", ["#7, reviewing, since 10:00"]),
                                ("Needs you", ["- #4 Port: Which port?"]), ("Empty", [])],
                               "built #7", "10:02")
        for text in ("## Building now", "#7, reviewing, since 10:00", "- #4 Port: Which port?",
                     "## Empty\n\nNothing.", "Last event: built #7", "Next check: 10:02"):
            self.assertIn(text, body)

    def test_board_sections_come_from_the_issue_list(self):
        self.world([issue(8), issue(9, body="Depends on: #8"), issue(4, ("needs-user",)),
                    issue(10, ("inbox",)), issue(11, ("shaping",))], comments=[
            comment("## Needs you\n\nWhich port?\n\nRecommended: 80\n\n" + common.MARKER)])
        st = loop.new_state()
        loop.snapshot(st)
        loop.answer(st)
        os.makedirs(os.path.join(self.work, ".loop", "builds"))
        with open(os.path.join(self.work, ".loop", "builds", "7.step"), "w") as f:
            f.write("reviewing")
        st.update(building={7: ("10:00", None)}, pr="https://example/pull/1",
                  conflict="clash in x.txt")
        loop.write_board(self.work, st)
        body = self.board_inputs()[-1]
        for text in ("#7, reviewing, since 10:00", "- #4 Piece 4: Which port? (reply on the issue)",
                     "https://example/pull/1", "clash in x.txt"):
            self.assertIn(text, body)

    def test_board_is_not_rewritten_when_unchanged(self):
        self.world([])
        st = loop.new_state()
        loop.snapshot(st)
        loop.write_board(self.work, st)
        self.assertEqual(len(self.board_inputs()), 1)
        self.world([], board=self.board_inputs()[0])
        loop.snapshot(st)
        loop.write_board(self.work, st)
        self.assertEqual(len(self.board_inputs()), 1)

    def test_missing_factory_prints_refused_and_continues(self):
        self.rules = [{"match": "issue list --state open", **out([])},
                      {"match": "issue list --state closed", **out([])}]
        st = loop.new_state()
        loop.snapshot(st)
        loop.write_board(self.work, st)
        self.assertIn("refused", self.say.call_args[0][0])
        self.assertIn("setup", self.say.call_args[0][0])
        self.assertEqual(self.writes("issue edit"), [])


class GitTest(Base):
    """Drain and the default branch sync, with one real repository copied per test."""

    def setUp(self):
        super().setUp()
        self.work, self.origin = copy_repo(TEMPLATE.name, self._tmp.name)
        mock.patch.object(pass_, "run_pass", return_value=({}, "")).start()  # no real sessions

    def test_loop_exit_cleans_up_and_names_what_is_left(self):
        parent = os.path.dirname(self.work)
        empty = os.path.join(parent, ".loop-worktrees")
        os.makedirs(empty)
        gone = os.path.join(parent, "gone-tree")
        for args in (["branch", "issue/5"], ["branch", "issue/6"], ["branch", "issue/x"],
                     ["worktree", "add", "-q", "--detach", gone], ["worktree", "add", "-q", "--detach", parent + "/kept"]):
            run_git(args, self.work)
        shutil.rmtree(gone)  # a worktree whose folder was deleted: prune drops it
        logs = os.path.join(self.work, ".loop", "logs")
        os.makedirs(logs)
        for name, days in (("7-builder-1.log", 15), ("8-reviewer-1.log", 13), ("piece-3-attempt-1.log", 15)):
            path = os.path.join(logs, name)
            open(path, "w").close()
            os.utime(path, (time.time() - days * 86400,) * 2)
        loop.clean_up(self.work, {5})
        self.assertEqual(sorted(os.listdir(logs)), ["8-reviewer-1.log", "piece-3-attempt-1.log"])  # a 1.x log is not ours
        self.assertFalse(os.path.exists(empty))
        line = self.say.call_args[0][0]
        self.assertRegex(line, r"^left behind: worktrees: \S*/kept; branches of closed issues: issue/5$")
        loop.clean_up(self.work, set())
        self.assertIn("branches of closed issues: none", self.say.call_args[0][0])

    def commit(self, branch, name, text, message):
        run_git(["checkout", "-q", branch], self.work)
        with open(os.path.join(self.work, name), "w") as f:
            f.write(text)
        run_git(["add", "-A"], self.work)
        run_git(["commit", "-m", message], self.work)
        run_git(["push", "origin", "%s:%s" % (branch, branch)], self.work)

    def land(self):
        run_git(["checkout", "-q", "-b", "loop/main", "origin/loop/main"], self.work)
        self.commit("loop/main", "x.txt", "x\n", "Issue 2")

    def test_drain_creates_the_pull_request_once_then_refreshes(self):
        self.land()
        self.world([])
        self.run_loop()
        create = self.writes("pr create")
        self.assertEqual(len(create), 1)
        self.assertIn("--base main --head loop/main", create[0])
        self.assertEqual(self.writes("pr edit"), [])
        self.world([], prs=[{"number": 9, "url": "https://example/pull/9"}])
        self.run_loop()
        self.assertEqual(len(self.writes("pr create")), 1)
        self.assertEqual(len(self.writes("pr edit 9")), 1)

    def test_default_branch_ahead_is_merged_into_the_loop_branch(self):
        self.commit("main", "y.txt", "y\n", "later")
        self.world([])
        st = loop.new_state()
        self.assertTrue(loop.sync_default(self.work, "loop/main", st))  # the loop is then dirty
        self.assertFalse(loop.sync_default(self.work, "loop/main", st))
        self.run_loop()
        tip = subprocess.run(["git", "ls-tree", "--name-only", "loop/main"], cwd=self.origin,
                             capture_output=True, text=True).stdout
        self.assertIn("y.txt", tip)

    def test_conflict_is_shown_and_parks_nothing(self):
        self.land()
        self.commit("main", "x.txt", "other\n", "clash")
        self.world([])
        self.assertFalse(loop.sync_default(self.work, "loop/main", loop.new_state()))
        self.run_loop()
        self.assertEqual(self.writes("needs-user"), [])
        self.assertIn("## Needs you\n\nMerging main into loop/main", self.board_inputs()[0])


    def pass_world(self):
        os.makedirs(os.path.join(self.work, ".loop"), exist_ok=True)
        self.land()
        self.world([])
        self.tests = mock.patch.object(merge, "run_tests", return_value=None).start()
        return mock.patch.object(pass_, "run_pass", return_value=(
            {"confirmed": [1], "issues": ["#5 a (inbox)", "#6 b (ready)"]}, "## End-of-loop pass (1 sessions)\n"))

    def test_drain_runs_the_pass_only_after_new_merges_and_reports_in_the_body(self):
        with self.pass_world() as run_pass:
            self.run_loop()
            self.world([], prs=[{"number": 9, "url": "https://example/pull/9"}])
            self.run_loop()
            self.assertEqual(run_pass.call_count, 1)
            self.assertIn("## End-of-loop pass", [i for c, i in self.inputs if c.startswith("pr edit 9")][0])
            self.assertEqual(run_pass.call_args[0][2], "origin/main")
            create = [i for c, i in self.inputs if c.startswith("pr create")]
            self.assertIn("## End-of-loop pass", create[0])
            self.commit("loop/main", "z.txt", "z\n", "Issue 3")
            self.run_loop()
            self.assertEqual(run_pass.call_count, 2)
            self.assertRegex(run_pass.call_args[0][2], "^[0-9a-f]{40}$")

    def test_the_defect_round_count_survives_between_passes_and_reaches_the_pass(self):
        with self.pass_world() as run_pass:
            run_pass.return_value = ({"rounds": 1, "issues": []}, "## End-of-loop pass\n")
            self.run_loop()
            self.assertEqual(run_pass.call_args[1]["rounds"], 0)
            self.commit("loop/main", "z.txt", "z\n", "Issue 3")
            self.run_loop()
            self.assertEqual(run_pass.call_args[1]["rounds"], 1)

    def test_a_corrupt_pass_file_counts_as_capped_and_a_missing_one_as_zero(self):
        with self.pass_world() as run_pass:
            run_pass.return_value = ({"rounds": 1, "issues": []}, "## End-of-loop pass\n")
            self.run_loop()
            self.assertEqual(run_pass.call_args[1]["rounds"], 0)  # no file yet
            for text in ("{not json", "[]", '{"rounds": "two"}'):
                with open(os.path.join(self.work, ".loop", "pass.json"), "w") as f:
                    f.write(text)
                self.commit("loop/main", "z%d.txt" % len(text), "z\n", "Issue 3")
                self.run_loop()
                self.assertIsNone(run_pass.call_args[1]["rounds"], text)
                self.assertIsInstance(json.load(open(os.path.join(self.work, ".loop", "pass.json")))["rounds"], int)

    def test_board_says_when_the_defect_rounds_limit_was_reached(self):
        with self.pass_world() as run_pass:
            run_pass.return_value = ({"rounds": 2, "capped": True, "confirmed": [1], "issues": []}, "## End-of-loop pass\n")
            self.run_loop()
        st = loop.new_state()
        st["pr"] = "https://example/pull/9"
        loop.snapshot(st)
        loop.write_board(self.work, st)
        self.assertIn("defect rounds limit reached, defects filed as inbox", self.board_inputs()[-1])

    def test_a_pass_that_raises_does_not_block_the_pull_request(self):
        with self.pass_world() as run_pass:
            run_pass.side_effect = RuntimeError("boom")
            self.run_loop()
        create = [i for c, i in self.inputs if c.startswith("pr create")]
        self.assertEqual(len(create), 1)
        self.assertIn("The pass did not run: RuntimeError: boom", create[0])

    def test_no_pass_when_the_tests_fail(self):
        with self.pass_world() as run_pass:
            self.tests.return_value = "the Test command failed"
            self.run_loop()
            run_pass.assert_not_called()
        self.assertEqual(len(self.writes("pr create")), 1)

    def test_a_pass_with_errors_is_retried_at_the_next_drain(self):
        with self.pass_world() as run_pass:
            run_pass.return_value = ({"errors": ["a session failed"]}, "## End-of-loop pass\n\nProblems\n")
            self.run_loop()
            self.run_loop()
            self.assertEqual(run_pass.call_count, 2)
            run_pass.return_value = ({}, "## End-of-loop pass\n")
            self.run_loop()
            self.run_loop()
            self.assertEqual(run_pass.call_count, 3)


class StartCheckTest(Base):
    """`loop run` refuses at start when the project is not set up, and takes no lock."""

    LABELS = ["inbox", "shaping", "ready", "building", "needs-user"]

    def start(self, labels=None, issues=None, remote=True):
        if remote:
            self.work, _ = copy_repo(TEMPLATE.name, self._tmp.name)
        else:
            os.makedirs(self.work)
            run_git(["init", "-q", "-b", "main"], self.work)
            with open(os.path.join(self.work, "AGENTS.md"), "w") as f:
                f.write(AGENTS)
        self.rules = [{"match": "label list", **out([{"name": n} for n in (labels or self.LABELS)])},
                      {"match": "issue list", **out([FACTORY] if issues is None else issues)}]
        with mock.patch.object(loop.os, "getcwd", return_value=self.work), \
                mock.patch.object(loop, "run", return_value=0) as run:
            return loop.main(["run"]), run

    def refused(self, code, run, reason):
        self.assertEqual((code, run.called), (1, False))
        text = self.say.call_args[0][0]
        self.assertIn("refused: " + reason, text)
        self.assertIn("next: run ", text)
        self.assertIn("setup.py", text)
        self.assertFalse(os.path.exists(os.path.join(self.work, ".loop", "loop.pid")))

    def test_no_remote_refuses_at_start(self):
        code, run = self.start(remote=False)
        self.refused(code, run, "this folder has no origin remote")

    def test_a_missing_label_refuses_at_start(self):
        code, run = self.start(labels=["inbox", "ready"])
        self.refused(code, run, "the loop labels are missing")

    def test_a_missing_factory_issue_refuses_at_start(self):
        code, run = self.start(issues=[])
        self.refused(code, run, "there is no Factory issue")

    def test_a_missing_loop_branch_refuses_at_start(self):
        self.work, _ = copy_repo(TEMPLATE.name, self._tmp.name)
        run_git(["push", "origin", "--delete", "loop/main"], self.work)
        with mock.patch.object(loop.os, "getcwd", return_value=self.work), mock.patch.object(loop, "run") as run:
            code = loop.main(["run"])
        self.refused(code, run, "the loop branch loop/main is not on origin")

    def test_a_set_up_project_starts(self):
        code, run = self.start()
        self.assertEqual((code, run.called), (0, True))
