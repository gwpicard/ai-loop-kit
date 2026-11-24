"""Delegated merges through the supervisor and the person's merge command."""
import contextlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import unittest
from unittest import mock

import common
import loop
import pass_
from kit.tests.helpers import FakeGh, finish_pass, make_repo, run_git, write_exe


KIT = Path(__file__).resolve().parents[1]
MERGE_OID = "a" * 40

# This fake never contacts GitHub. It records comment bodies as well as arguments.
GH = '''#!PYTHON
import json, os, sys
from pathlib import Path
p = Path(os.environ["DELEGATED_GH"])
s = json.loads(p.read_text())
a = sys.argv[1:]
body = sys.stdin.read() if "--body-file" in a and a[a.index("--body-file") + 1] == "-" else ""
with open(str(p) + ".calls", "a") as f:
    f.write(json.dumps({"args": a, "body": body}) + "\\n")
def emit(value):
    print(json.dumps(value))
    sys.exit(0)
if a[:2] == ["pr", "merge"]:
    s["merged"] = True
    p.write_text(json.dumps(s))
    sys.exit(0)
pr = dict(s["pr"], comments=s["comments"],
          state="MERGED" if s.get("merged") else "OPEN",
          mergeCommit={"oid": s["merge_oid"]} if s.get("merged") else None)
if a[:2] == ["pr", "view"]:
    emit(pr)
if a[:2] == ["pr", "list"]:
    emit([] if s.get("merged") else [pr])
if a[:2] == ["pr", "checks"]:
    print(json.dumps(s["checks"]))
    sys.exit(0 if all(c["bucket"] == "pass" for c in s["checks"]) else 1)
if a[:2] in (["pr", "comment"], ["pr", "edit"], ["issue", "edit"]):
    sys.exit(0)
if a[:2] == ["label", "list"]:
    emit([{"name": n} for n in ("inbox", "shaping", "ready", "building", "needs-user")])
if a[:2] == ["issue", "list"]:
    emit([] if "closed" in a else [{"number": 1, "title": "Factory", "body": "", "labels": []}])
if a and a[0] == "api":
    if "permission" in " ".join(a):
        emit({"permission": s["permission"]})
    if "comments" in " ".join(a):
        emit(s["comments"])
    if "--jq" in a and "delete_branch_on_merge" in a[a.index("--jq") + 1]:
        print("false")
        sys.exit(0)
    emit({"default_branch": "main", "delete_branch_on_merge": False})
if a[:2] == ["repo", "view"]:
    emit({"defaultBranchRef": {"name": "main"}, "nameWithOwner": "test/project"})
sys.exit("unhandled fake gh call: " + " ".join(a))
'''


class DelegatedMergeTest(FakeGh):
    def setUp(self):
        super().setUp()
        self.work, self.origin = make_repo(self.tmp, {
            "loop.json": json.dumps({"Test command": "true", "Idle hours": 12}),
            "app.txt": "base\n",
        })
        run_git(["push", "origin", "main:loop/main"], self.work)
        run_git(["checkout", "-b", "loop/main"], self.work)
        Path(self.work, "app.txt").write_text("batch\n")
        run_git(["commit", "-am", "Issue batch"], self.work)
        run_git(["push", "origin", "loop/main"], self.work)
        self.head = common.git(["rev-parse", "HEAD"], cwd=self.work)
        self.state_path = Path(self.tmp, "delegated.json")
        os.environ["DELEGATED_GH"] = str(self.state_path)
        write_exe(Path(self.tmp, "bin", "gh"), GH)
        self.reset()

    def reset(self, *, check="SUCCESS", comments=(), permission="write",
              conflict=False, base="main", head="loop/main"):
        bucket = {"SUCCESS": "pass", "FAILURE": "fail", "PENDING": "pending"}[check]
        checks = [{"name": "required-tests", "state": check, "bucket": bucket,
                   "link": "https://example.invalid/check", "workflow": "CI"}]
        self.state = {
            "pr": {"number": 7, "url": "https://example.invalid/pull/7",
                   "title": "Batch", "body": "", "baseRefName": base,
                   "headRefName": head, "headRefOid": self.head,
                   "mergeable": "CONFLICTING" if conflict else "MERGEABLE",
                   "mergeStateStatus": "DIRTY" if conflict else "CLEAN",
                   "isDraft": False, "statusCheckRollup": [
                       {"__typename": "CheckRun", "name": "required-tests",
                        "status": "IN_PROGRESS" if check == "PENDING" else "COMPLETED",
                        "conclusion": "" if check == "PENDING" else check}]},
            "checks": checks, "comments": list(comments), "permission": permission,
            "merge_oid": MERGE_OID,
        }
        self.save()
        Path(str(self.state_path) + ".calls").unlink(missing_ok=True)

    def save(self):
        self.state_path.write_text(json.dumps(self.state))

    def recorded(self, verb):
        path = Path(str(self.state_path) + ".calls")
        rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        return [r for r in rows if r["args"][:len(verb)] == verb]

    def comment(self, body, user="alex"):
        return {"body": body, "author": {"login": user},
                "user": {"login": user}, "createdAt": "2026-11-23T09:00:00Z"}

    def supervise(self, policy, *, after_first=None, drain_failure=None):
        # Validate the new setting separately, so policy tests reach the cycle
        # before the settings reader has learnt its new key.
        settings = dict(common.read_settings(self.work), **{"Final merge": policy})
        output = io.StringIO()
        polls = []

        def wait(stop, seconds):
            polls.append(seconds)
            if len(polls) == 1 and after_first:
                self.assertEqual(self.recorded(["pr", "merge"]), [])
                after_first()
            if len(polls) >= 3:
                Path(stop).touch()

        with contextlib.ExitStack() as stack:
            previous = os.getcwd()
            os.chdir(self.work)
            stack.callback(os.chdir, previous)
            stack.enter_context(contextlib.redirect_stdout(output))
            stack.enter_context(contextlib.redirect_stderr(output))
            stack.enter_context(mock.patch.object(common, "read_settings", return_value=settings))
            stack.enter_context(mock.patch.object(loop.sys, "platform", "linux"))
            stack.enter_context(mock.patch.object(loop.os, "nice"))
            stack.enter_context(mock.patch.object(loop, "wait_stop", side_effect=wait))
            stack.enter_context(mock.patch.object(loop, "start_pass", side_effect=finish_pass))
            stack.enter_context(mock.patch.object(loop, "summary", return_value=""))
            stack.enter_context(mock.patch.object(pass_, "run_pass", return_value=({}, "Pass completed.\n")))
            if drain_failure:
                stack.enter_context(mock.patch.object(loop.merge, "run_tests", return_value=drain_failure))
            code = loop.main(["run"])
        self.assertEqual(code, 0, output.getvalue())
        self.assertNotIn("problem, will check again", output.getvalue())

    def assert_merged_once(self):
        calls = self.recorded(["pr", "merge"])
        self.assertEqual(len(calls), 1, "the delegated merge must run exactly once")
        args = calls[0]["args"]
        self.assertIn("7", args)
        self.assertNotIn("--delete-branch", args)
        self.assertNotIn("--admin", args)
        self.assertNotIn("--auto", args)
        return args

    def test_setting_defaults_to_person_and_accepts_only_the_three_values(self):
        with self.subTest(default=True):
            self.assertEqual(common.read_settings(self.work).get("Final merge"), "person")
        path = Path(self.work, "loop.json")
        for value in ("person", "on request", "when green"):
            with self.subTest(value=value):
                path.write_text(json.dumps({"Test command": "true", "Final merge": value}))
                try:
                    actual = common.read_settings(self.work)
                except common.SettingsError as error:
                    self.fail("valid Final merge setting refused: %s" % error)
                self.assertEqual(actual["Final merge"], value)
        for value in ("always", "", True, 1, None):
            with self.subTest(invalid=value):
                path.write_text(json.dumps({"Test command": "true", "Final merge": value}))
                with self.assertRaises(common.SettingsError):
                    common.read_settings(self.work)

    def test_person_keeps_the_merge_manual_but_when_green_delegates_it(self):
        self.reset(comments=[self.comment("merge")])
        self.supervise("person")
        self.assertEqual(self.recorded(["pr", "merge"]), [])
        self.reset()
        self.supervise("when green")
        self.assert_merged_once()

    def test_on_request_reads_a_new_comment_on_the_next_cycle_and_records_the_requester(self):
        for body in ("merge", "Please land this.\nmerge\nThank you."):
            with self.subTest(body=body):
                self.reset()

                def request():
                    self.state["comments"] = [self.comment(body)]
                    self.save()

                self.supervise("on request", after_first=request)
                self.assert_merged_once()
                posted = "\n".join(r["body"] + " ".join(r["args"])
                                   for r in self.recorded(["pr", "comment"]))
                self.assertIn("alex", posted)
                self.assertIn(MERGE_OID, posted)

    def test_on_request_requires_write_access_and_a_standalone_merge_line(self):
        for body, permission in (("merge please", "write"), ("do not merge", "write"),
                                 ("merge", "read"), ("merge", "write")):
            with self.subTest(body=body, permission=permission):
                self.reset(comments=[self.comment(body)], permission=permission)
                self.supervise("on request")
                if body == "merge" and permission == "write":
                    self.assert_merged_once()
                else:
                    self.assertEqual(self.recorded(["pr", "merge"]), [])

    def test_final_merge_waits_for_failing_or_pending_required_checks_to_pass(self):
        for policy in ("on request", "when green"):
            for check in ("FAILURE", "PENDING"):
                with self.subTest(policy=policy, check=check):
                    self.reset(check=check, comments=[self.comment("merge")])

                    def green():
                        self.state["checks"][0].update(state="SUCCESS", bucket="pass")
                        self.state["pr"]["statusCheckRollup"][0].update(
                            status="COMPLETED", conclusion="SUCCESS")
                        self.save()

                    self.supervise(policy, after_first=green)
                    self.assert_merged_once()

    def test_final_merge_waits_for_conflicts_to_clear(self):
        for policy in ("on request", "when green"):
            with self.subTest(policy=policy):
                self.reset(conflict=True, comments=[self.comment("merge")])

                def resolve():
                    self.state["pr"].update(mergeable="MERGEABLE", mergeStateStatus="CLEAN")
                    self.save()

                self.supervise(policy, after_first=resolve)
                self.assert_merged_once()

    def test_when_green_requires_a_passing_drain(self):
        self.supervise("when green", drain_failure="the Test command failed")
        self.assertEqual(self.recorded(["pr", "merge"]), [])
        self.reset()
        self.supervise("when green")
        self.assert_merged_once()

    def command(self):
        return subprocess.run([str(KIT / "bin/loop"), "merge", "7"], cwd=self.work,
                              text=True, capture_output=True, timeout=30)

    def test_merge_command_refuses_failed_or_pending_checks_then_merges_green(self):
        for check in ("FAILURE", "PENDING", "SUCCESS"):
            with self.subTest(check=check):
                self.reset(check=check)
                result = self.command()
                text = result.stdout + result.stderr
                self.assertNotIn("usage:", text, "loop merge must be a recognised command")
                if check != "SUCCESS":
                    self.assertNotEqual(result.returncode, 0, text)
                    self.assertEqual(self.recorded(["pr", "merge"]), [])
                    self.assertRegex(text.lower(), r"check|pending|fail")
                else:
                    self.assertEqual(result.returncode, 0, text)
                    self.assert_merged_once()
                    events = Path(self.work, ".loop/events.jsonl")
                    self.assertTrue(events.exists(), "the request must leave an event")
                    requests = [json.loads(line) for line in events.read_text().splitlines()
                                if json.loads(line).get("kind") == "merged-by-request"]
                    self.assertEqual(len(requests), 1)
                    self.assertIn("7", [str(v) for v in requests[0].values()])

    def test_merge_command_uses_squash_and_project_sign_off_settings(self):
        for signed in (False, True):
            with self.subTest(signed=signed):
                self.reset()
                Path(self.work, "loop.json").write_text(json.dumps({
                    "Test command": "true", "Sign-off": signed}))
                result = self.command()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                args = self.assert_merged_once()
                self.assertIn("--squash", args)
                self.assertIn("--body", args)
                body = args[args.index("--body") + 1]
                trailer = "Signed-off-by: Test <t@example.com>"
                self.assertEqual(trailer in body, signed)

    def test_loop_branch_merge_tests_the_combined_result_with_the_full_test_command(self):
        run_git(["checkout", "-b", "fix/requested", "main"], self.work)
        Path(self.work, "fix.txt").write_text("fix\n")
        run_git(["add", "fix.txt"], self.work)
        run_git(["commit", "-m", "Requested fix"], self.work)
        run_git(["push", "origin", "fix/requested"], self.work)
        self.head = common.git(["rev-parse", "HEAD"], cwd=self.work)
        for passing in (False, True):
            with self.subTest(passing=passing):
                self.reset(base="loop/main", head="fix/requested")
                marker = Path(self.tmp, "full-test-%s" % passing)
                probe = Path(self.tmp, "probe.py")
                probe.write_text(
                    "from pathlib import Path\n"
                    "assert Path('app.txt').read_text() == 'batch\\n', 'missing loop branch change'\n"
                    "assert Path('fix.txt').read_text() == 'fix\\n', 'missing requested fix'\n"
                    "Path(%r).write_text('ran')\n" % str(marker)
                    + "raise SystemExit(%d)\n" % (0 if passing else 1))
                Path(self.work, "loop.json").write_text(json.dumps({
                    "Test command": "%s %s" % (shlex.quote(sys.executable), shlex.quote(str(probe))),
                    "Test files command": "false {files}",
                }))
                result = self.command()
                self.assertTrue(marker.exists(), "run the full Test command on the merged result: "
                                + result.stdout + result.stderr)
                if passing:
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assert_merged_once()
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(self.recorded(["pr", "merge"]), [])


class DelegatedMergeTextTest(unittest.TestCase):
    def test_skill_accepts_a_persons_merge_instruction_without_another_confirmation(self):
        text = " ".join((KIT / "skills/loop/SKILL.md").read_text().lower().split())
        self.assertTrue("loop merge" in text, "the skill must describe loop merge")
        self.assertRegex(text, r"without (?:asking|confirmation)|do not ask again|no further confirmation")
        for boundary in (r"never.{0,180}releases", r"never.{0,180}release branch",
                         r"never.{0,180}force.push", r"never.{0,180}delet.{0,30}branch"):
            self.assertRegex(text, boundary)

    def test_readme_documents_the_policy_command_and_person_default(self):
        text = " ".join((KIT / "README.md").read_text().split())
        self.assertTrue("Final merge" in text, "the README must document Final merge")
        for value in ("person", "on request", "when green", "loop merge"):
            self.assertIn(value, text)
        self.assertRegex(text.lower(), r"person.{0,100}default|default.{0,100}person")
