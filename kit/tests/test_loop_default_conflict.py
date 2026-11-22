"""Default-branch conflicts reported through the running supervisor."""
import contextlib
import io
import json
import re
from pathlib import Path
from unittest import mock

import common
import flow
import loop
from kit.tests.helpers import make_repo, run_git, settings_json
from kit.tests.test_loop import Base, issue


class DefaultConflictTest(Base):
    files = ("z.txt", "folder/a file.txt")
    extra = "middle.txt"
    failure = r"(?i)conflict|did not|cannot|could not|fail|does not"

    def setUp(self):
        self.pr_body = None
        super().setUp()
        settings = "## Loop\nTest command: true\nLoop branch: loop/main\nIdle hours: 1\n"
        contents = {name: "base\n" for name in (*self.files, self.extra)}
        self.work, self.origin = make_repo(
            self._tmp.name, dict(contents, **{"loop.json": settings_json(settings)}))
        run_git(["push", "origin", "main:loop/main"], self.work)
        run_git(["checkout", "-b", "loop/main"], self.work)
        self.commit("loop/main", {name: "loop\n" for name in contents})
        self.commit("main", {name: "default\n" for name in self.files})
        self.world([])
        self.say.side_effect = common.say
        self.log = io.StringIO()
        self.observed = []
        # These tests exercise supervision and Git, without agent sessions.
        mock.patch.object(loop.pass_, "run_pass", return_value=({}, "")).start()
        mock.patch.object(loop.session, "run", side_effect=AssertionError("unexpected agent session")).start()

    def fake_gh(self, args, input=None):
        result = super().fake_gh(args, input)
        if args[:2] == ["pr", "list"] and "--head" in args:
            return 0, json.dumps([{"number": 9, "url": "https://example/pull/9"}]
                                 if self.pr_body is not None else []), ""
        if args[:2] == ["pr", "view"]:
            return 0, json.dumps({"body": self.pr_body or ""}), ""
        if args[:2] in (["pr", "create"], ["pr", "edit"]):
            self.pr_body = input
        return result

    def commit(self, branch, files):
        run_git(["checkout", "-q", branch], self.work)
        run_git(["fetch", "--no-prune", "origin"], self.work)
        run_git(["merge", "--ff-only", "origin/" + branch], self.work)
        for name, text in files.items():
            Path(self.work, name).write_text(text)
        run_git(["add", "--", *files], self.work)
        run_git(["commit", "-qm", "Update fixture"], self.work)
        run_git(["push", "origin", branch], self.work)

    def change_conflicts(self):
        self.commit("main", {self.extra: "default\n"})

    def resolve_conflicts(self):
        self.commit("main", {name: "loop\n" for name in (*self.files, self.extra)})

    def conflict_again(self):
        self.commit("main", {self.files[0]: "another default\n"})
        self.commit("loop/main", {self.files[0]: "another loop\n"})

    def drive(self, changes):
        """Observe each idle poll, then change the world for the next one."""
        changes = iter(changes)

        def poll(path, seconds):
            event_path = Path(self.work, ".loop/events.jsonl")
            self.observed.append(dict(
                log=self.log.getvalue(), body=self.pr_body,
                board=self.board_inputs()[-1],
                events=[json.loads(line) for line in event_path.read_text().splitlines()]
                if event_path.exists() else []))
            change = next(changes, None)
            if change is None:
                self.stop_after()
            else:
                change()

        with mock.patch.object(loop, "wait_stop", side_effect=poll), contextlib.redirect_stdout(self.log):
            result = self.run_loop()
        self.assertEqual(result, 0)
        self.assertNotIn("problem, will check again", self.log.getvalue())

    def test_loop_out_reports_changed_files_once_and_rearms_after_success(self):
        self.drive([lambda: None, self.change_conflicts, lambda: None,
                    self.resolve_conflicts, self.conflict_again, lambda: None])
        expected = [1, 1, 2, 2, 2, 3, 3]
        attempts = [1, 1, 1, 1, 1, 2, 2]
        for index, seen in enumerate(self.observed):
            with self.subTest(poll=index):
                lines = [line for line in seen["log"].splitlines()
                         if self.files[0] in line and re.search(self.failure, line)]
                self.assertEqual(len(lines), expected[index], seen["log"])
                self.assertIn(self.files[1], lines[0])
                self.assertNotIn(self.extra, lines[0])
                if index >= 2:
                    self.assertIn(self.extra, lines[1])
                if index >= 5:
                    self.assertNotIn(self.files[1], lines[-1])
                    self.assertNotIn(self.extra, lines[-1])
                self.assertEqual(seen["log"].count("merging origin/main into loop/main"),
                                 attempts[index], seen["log"])

    def test_final_pull_request_tracks_conflict_changes_and_recovery(self):
        self.drive([lambda: None, self.change_conflicts, self.resolve_conflicts,
                    self.conflict_again])
        for index in (0, 1, 2, 4):
            with self.subTest(poll=index):
                # Churn statistics also name files, but are not a conflict warning.
                body = re.sub(r"```.*?```", "", self.observed[index]["body"] or "", flags=re.S)
                self.assertTrue([line for line in body.splitlines()
                                 if "main" in line and re.search(self.failure, line)], body)
                self.assertIn("main", body)
                self.assertIn("loop/main", body)
                self.assertIn(self.files[0], body)
                if index < 4:
                    self.assertIn(self.files[1], body)
                if index == 2:
                    self.assertIn(self.extra, body)
                if index == 4:
                    self.assertNotIn(self.files[1], body)
                    self.assertNotIn(self.extra, body)
        cleared = self.observed[3]["body"] or ""
        self.assertNotIn(self.files[0], cleared)
        self.assertNotIn(self.files[1], cleared)
        self.assertNotIn(self.extra, cleared)
        self.assertFalse([line for line in cleared.splitlines()
                          if "main" in line and re.search(self.failure, line)], cleared)
        self.assertEqual(len(self.writes("pr create")), 1)
        self.assertTrue(self.writes("pr edit"))

    def test_failure_event_and_board_survive_a_ready_piece_building(self):
        def ready():
            self.world([issue(7)])

        def build(number, project, replies=()):
            self.built.append(number)
            # The fake builder lands an independent piece on the still-conflicting branch.
            self.commit("loop/main", {"piece.txt": "built\n"})
            self.world([], closed=[number])
            return flow.Result("merged", "done")

        with mock.patch.object(flow, "build", side_effect=build):
            self.drive([ready, self.resolve_conflicts])
        self.assertEqual(self.built, [7])
        self.assertIn("#7 merged: done", self.observed[1]["board"])
        self.assertEqual(common.git(["show", "origin/loop/main:piece.txt"], cwd=self.work), "built")
        self.assertFalse(self.writes("needs-user"))
        for index in (0, 1):
            seen = self.observed[index]
            with self.subTest(poll=index, surface="board"):
                self.assertRegex(seen["board"], self.failure)
                for name in self.files:
                    self.assertIn(name, seen["board"])
            with self.subTest(poll=index, surface="event"):
                failures = [event for event in seen["events"]
                            if all(name in json.dumps(event) for name in self.files)]
                self.assertTrue(failures, "No event records the conflicting files: %r" % seen["events"])
                self.assertRegex(json.dumps(failures), self.failure)
        for name in self.files:
            self.assertNotIn(name, self.observed[2]["board"])
