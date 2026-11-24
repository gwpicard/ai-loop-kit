"""Final merge authority exercised through supervisor cycles with fake GitHub."""
import json
from pathlib import Path
from unittest import mock

import common
import loop
from kit.tests.helpers import finish_pass, make_repo, run_git
from kit.tests.test_loop import Base


class FinalMergeTest(Base):
    def setUp(self):
        super().setUp()
        self.work, _ = make_repo(self._tmp.name, {
            "loop.json": json.dumps({"Test command": "true", "Idle hours": 1}),
            "app.txt": "base\n"})
        run_git(["checkout", "-b", "loop/main"], self.work)
        Path(self.work, "app.txt").write_text("built\n")
        run_git(["commit", "-am", "Issue 7: build fixture"], self.work)
        run_git(["push", "origin", "loop/main"], self.work)
        self.head = common.git(["rev-parse", "HEAD"], cwd=self.work)
        self.merge_commit = "a" * 40
        self.comments = []
        self.check = "SUCCESS"
        self.conflicting = False
        self.merged = False
        self.pr_body = ""
        self.observed = []
        self.world([])
        mock.patch.object(loop, "start_pass", side_effect=finish_pass).start()
        mock.patch.object(loop.pass_, "run_pass", return_value=({}, "Pass completed.\n")).start()
        mock.patch.object(loop, "summary", return_value="").start()

    def configure(self, mode):
        path = Path(self.work, "loop.json")
        settings = json.loads(path.read_text())
        if mode is not None:
            settings["Final merge"] = mode
        path.write_text(json.dumps(settings))

    def fake_gh(self, args, input=None):
        result = super().fake_gh(args, input)
        checks = [{"name": "required", "state": self.check,
                   "status": "COMPLETED" if self.check != "PENDING" else "IN_PROGRESS",
                   "conclusion": self.check if self.check != "PENDING" else "",
                   "bucket": {"SUCCESS": "pass", "FAILURE": "fail", "PENDING": "pending"}[self.check]}]
        info = dict(number=9, url="https://example/pull/9", body=self.pr_body,
                    state="MERGED" if self.merged else "OPEN", headRefName="loop/main",
                    baseRefName="main", headRefOid=self.head,
                    mergeable="CONFLICTING" if self.conflicting else "MERGEABLE",
                    mergeStateStatus="DIRTY" if self.conflicting else "CLEAN",
                    statusCheckRollup=checks, comments=self.comments,
                    mergeCommit={"oid": self.merge_commit} if self.merged else None)
        if args[:2] == ["pr", "list"]:
            return 0, json.dumps([] if self.merged else [info]), ""
        if args[:2] == ["pr", "view"]:
            return 0, json.dumps(info), ""
        if args[:2] == ["pr", "checks"]:
            code = {"SUCCESS": 0, "FAILURE": 1, "PENDING": 8}[self.check]
            return code, json.dumps(checks), ""
        if args[:2] == ["pr", "edit"]:
            self.pr_body = input or ""
        if args[:2] == ["pr", "merge"]:
            self.merged = True
        if args[:1] == ["api"] and "comments" in " ".join(args):
            return 0, json.dumps([dict(c, user=c["author"]) for c in self.comments]), ""
        if args[:1] == ["api"] and "/pulls/" in " ".join(args):
            return 0, json.dumps(dict(info, merge_commit_sha=self.merge_commit if self.merged else None)), ""
        return result

    def request(self, body="merge", user="maintainer"):
        self.comments.append(dict(body=body, author={"login": user},
                                  createdAt="2026-11-23T12:00:00Z"))

    def drive(self, changes=()):
        changes = iter(changes)

        def poll(path, seconds):
            self.observed.append(len(self.writes("pr merge")))
            change = next(changes, None)
            if change is None:
                self.stop_after()
            else:
                change()

        with mock.patch.object(loop, "wait_stop", side_effect=poll):
            try:
                result = self.run_loop()
            except common.SettingsError as error:
                self.fail("The supervisor must accept Final merge: %s" % error)
        self.assertEqual(result, 0)
        errors = [str(call) for call in self.say.call_args_list if "problem, will check again" in str(call)]
        self.assertEqual(errors, [])

    def test_person_is_the_default_and_neither_person_mode_merges(self):
        self.assertEqual(common.read_settings(self.work).get("Final merge"), "person")
        self.request()
        self.drive([lambda: self.configure("person")])
        self.assertEqual(self.observed, [0, 0])

    def test_on_request_observes_a_new_comment_at_the_next_cycle(self):
        self.configure("on request")
        self.drive([self.request])
        self.assertEqual(self.observed, [0, 1])
        comments = "\n".join((body or "") + " " + command for command, body in self.inputs
                             if command.startswith("pr comment "))
        self.assertIn("maintainer", comments)
        self.assertIn(self.merge_commit, comments)

    def test_on_request_accepts_a_line_with_other_lines_in_either_order(self):
        self.configure("on request")
        self.drive([lambda: self.request("Checks reviewed.\nmerge\nThank you.")])
        self.assertEqual(self.observed, [0, 1])

    def test_on_request_ignores_prose_and_a_reader_then_accepts_a_writer(self):
        self.configure("on request")
        self.request("please merge")
        self.request("merge this")
        self.request("merge", "reader")
        original = self.fake_gh

        def permissions(args, input=None):
            if "/collaborators/reader/permission" in " ".join(args):
                self.calls.append(" ".join(args))
                return 0, '{"permission": "read"}', ""
            return original(args, input)

        with mock.patch.object(common, "_run_gh", side_effect=permissions):
            self.drive([lambda: self.request("Thank you.\nmerge")])
        self.assertEqual(self.observed, [0, 1])

    def test_when_green_waits_for_failing_and_pending_required_checks(self):
        self.configure("when green")
        self.check = "FAILURE"
        self.drive([lambda: setattr(self, "check", "PENDING"),
                    lambda: setattr(self, "check", "SUCCESS")])
        self.assertEqual(self.observed, [0, 0, 1])

    def test_on_request_waits_for_checks_without_another_request(self):
        self.configure("on request")
        self.request()
        self.check = "PENDING"
        self.drive([lambda: setattr(self, "check", "FAILURE"),
                    lambda: setattr(self, "check", "SUCCESS")])
        self.assertEqual(self.observed, [0, 0, 1])

    def test_on_request_waits_for_a_conflict_to_clear(self):
        self.configure("on request")
        self.request()
        self.conflicting = True
        self.drive([lambda: setattr(self, "conflicting", False)])
        self.assertEqual(self.observed, [0, 1])

    def test_when_green_requires_a_passing_drain(self):
        self.configure("when green")
        path = Path(self.work, "loop.json")
        settings = json.loads(path.read_text())
        settings["Test command"] = "false"
        path.write_text(json.dumps(settings))
        self.drive()
        self.assertEqual(self.observed, [0])
        events = Path(self.work, ".loop/events.jsonl").read_text()
        self.assertIn('"fail"', events)
        # A new invocation drains the same head successfully before merging it.
        settings["Test command"] = "true"
        path.write_text(json.dumps(settings))
        self.observed.clear()
        self.drive()
        self.assertEqual(self.observed, [1])
