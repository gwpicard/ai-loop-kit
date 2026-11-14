import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from lite.tests.helpers import copy_repo, make_repo, run_git
import common
import flow
import loop
import merge

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
        os.makedirs(os.path.join(self.work, ".lite"), exist_ok=True)
        open(os.path.join(self.work, ".lite", "stop"), "w").close()

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
        os.makedirs(os.path.join(self.work, ".lite"))
        with open(os.path.join(self.work, "AGENTS.md"), "w") as f:
            f.write(AGENTS)
        mock.patch.object(loop, "sync_default").start()
        mock.patch.object(loop, "drain").start()

    def pid_file(self):
        return os.path.join(self.work, ".lite", "loop.pid")

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

    def test_stop_file_exits(self):
        self.world([])
        with open(os.path.join(self.work, "AGENTS.md"), "w") as f:
            f.write(AGENTS.replace("Idle hours: 0", "Idle hours: 5"))
        old = os.getcwd()
        os.chdir(self.work)
        self.addCleanup(os.chdir, old)
        loop.time.sleep.side_effect = lambda s: loop.main(["stop"])
        self.assertEqual(self.run_loop(), 0)
        self.assertIn("stop requested", self.say.call_args_list[-1][0][0])
        self.assertFalse(os.path.exists(os.path.join(self.work, ".lite", "stop")))

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
            comment("## Needs you\n\nWhich port?\n\nRecommended: 80"),
            comment("Crashed, trying again.\n\n" + common.MARKER), comment("Use 8080.")])
        with self.fake_build():
            self.run_loop()
        edits = self.writes("issue edit 4")
        self.assertEqual(edits[:2], ["issue edit 4 --remove-label needs-user",
                                     "issue edit 4 --add-label ready"])
        self.assertEqual(self.built, [(4, ["Use 8080."])])

    def test_no_reply_or_a_stranger_leaves_it_parked(self):
        park = comment("## Needs you\n\nWhich port?\n\nRecommended: 80")
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

    def test_untrusted_ready_issue_is_marked_on_the_board(self):
        self.world([issue(5)])
        st = loop.new_state()
        loop.snapshot(st)
        with mock.patch.object(common, "ready_is_trusted", return_value=False) as check:
            self.assertIsNone(loop.pick(st))
            self.assertIsNone(loop.pick(st))
        self.assertEqual(check.call_count, 1)
        loop.write_board(self.work, st)
        self.assertIn("not built: labelled by a non-collaborator", self.board_inputs()[-1])

    def test_every_comment_the_loop_posts_carries_the_marker(self):
        self.world([issue(2)])
        with self.fake_build({2: RuntimeError("boom")}):
            self.run_loop()
        posted = [i for c, i in self.inputs if c.startswith("issue comment")]
        self.assertEqual(len(posted), 2)  # the retry note and the park comment
        self.assertTrue(all(common.MARKER in body for body in posted))
        self.inputs.clear()
        flow.post_tests(2, ["tests/test_a.py"])
        body = [i for c, i in self.inputs if c.startswith("issue comment")][0]
        self.assertIn(common.MARKER, body)
        self.assertEqual(merge.locked_paths([{"body": body}]), ["tests/test_a.py"])

    def test_idle_exit_says_why(self):
        self.world([])
        self.assertEqual(self.run_loop(), 0)
        self.assertIn("exiting: nothing built for 0 hours", self.say.call_args_list[-1][0][0])

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
            comment("## Needs you\n\nWhich port?\n\nRecommended: 80")])
        st = loop.new_state()
        loop.snapshot(st)
        loop.answer(st)
        st.update(building=(7, "reviewing", "10:00"), pr="https://example/pull/1",
                  conflict="clash in x.txt")
        loop.write_board(self.work, st)
        body = self.board_inputs()[-1]
        for text in ("#7, reviewing, since 10:00", "- #4 Piece 4: Which port? (reply on the issue)",
                     "- #8 Piece 8: waits on nothing", "- #9 Piece 9: waits on #8",
                     "- #%d Piece %d: inbox" % (10, 10), "- #%d Piece %d: shaping" % (11, 11), "https://example/pull/1",
                     "clash in x.txt"):
            self.assertIn(text, body)

    def test_the_building_issue_is_not_in_the_queue(self):
        self.world([issue(2), issue(3)])
        st = loop.new_state()
        loop.snapshot(st)
        st["building"] = (2, "builder", "10:00")
        loop.write_board(self.work, st)
        body = self.board_inputs()[-1]
        self.assertEqual(body.count("Piece 2"), 0)
        self.assertIn("Piece 3: waits on nothing", body)

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

    def test_landed_section_lists_merges_made_since_the_last_fetch(self):
        self.land()
        run_git(["update-ref", "refs/remotes/origin/loop/main", "origin/main"], self.work)  # stale
        self.world([])
        st = loop.new_state()
        loop.snapshot(st)
        loop.write_board(self.work, st)
        self.assertIn("- Issue 2", self.board_inputs()[-1])

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
        self.assertIn("## Conflict\n\nMerging main into loop/main", self.board_inputs()[0])
