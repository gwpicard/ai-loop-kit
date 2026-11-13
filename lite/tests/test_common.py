import json
import os
import tempfile
import time
import unittest
from unittest import mock

from lite.tests.helpers import FakeGh, make_repo
import common


def ok(stdout=""):
    return {"code": 0, "stdout": stdout}


def fail(stderr, code=1):
    return {"code": code, "stderr": stderr}


class SettingsTest(unittest.TestCase):
    def write(self, text):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = tmp.name
        with open(os.path.join(d, "AGENTS.md"), "w") as f:
            f.write(text)
        return d

    def test_defaults(self):
        s = common.read_settings(self.write("## Loop\nTest command: make test\n"))
        self.assertEqual(s["Test command"], "make test")
        self.assertEqual(s["Loop branch"], "loop/main")
        self.assertEqual(s["Builder model"], "sonnet")
        self.assertEqual(s["Reviewer model"], "sonnet")
        self.assertEqual(s["Protected paths"], [".github/", ".claude/", ".githooks/"])
        self.assertEqual(s["Idle hours"], 12)
        self.assertEqual(s["Max rounds"], 3)

    def test_values_and_backquotes(self):
        s = common.read_settings(self.write(
            "# Title\nTest command: other\n\n## Loop\n"
            "Test command: `sh tests/run.sh`\nLoop branch: `loop/x`\n"
            "Protected paths: `a/`, `b/`\nIdle hours: 2\nMax rounds: 5\n"
            "\n## Next\nLoop branch: wrong\n"))
        self.assertEqual(s["Test command"], "sh tests/run.sh")
        self.assertEqual(s["Loop branch"], "loop/x")
        self.assertEqual(s["Protected paths"], ["a/", "b/"])
        self.assertEqual(s["Idle hours"], 2)
        self.assertEqual(s["Max rounds"], 5)

    def test_test_command_required(self):
        with self.assertRaises(common.SettingsError):
            common.read_settings(self.write("## Loop\nLoop branch: x\n"))

    def test_missing_file(self):
        with self.assertRaises(common.SettingsError):
            common.read_settings(os.path.join(self.write("x"), "none"))


class GhTest(FakeGh):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(common, "sleep")
        self.sleep = p.start()
        self.addCleanup(p.stop)

    def test_success(self):
        self.scenario([{"match": "issue list", "responses": [ok("[]")]}])
        self.assertEqual(common.gh(["issue", "list"]), "[]")

    def test_retries_5xx_then_succeeds(self):
        self.scenario([{"match": "issue", "responses": [
            fail("HTTP 502: Bad Gateway"), fail("HTTP 503"), ok("fine")]}])
        self.assertEqual(common.gh(["issue", "list"]), "fine")
        self.assertEqual([c.args[0] for c in self.sleep.call_args_list], [5, 20])

    def test_gives_up_after_three_retries(self):
        self.scenario([{"match": "issue", "responses": [fail("HTTP 500")]}])
        with self.assertRaises(common.GitHubError):
            common.gh(["issue", "list"])
        self.assertEqual([c.args[0] for c in self.sleep.call_args_list], [5, 20, 60])
        self.assertEqual(len(self.calls()), 4)

    def test_retries_network_errors(self):
        self.scenario([{"match": "issue", "responses": [
            fail("dial tcp: i/o timeout"), ok("x")]}])
        self.assertEqual(common.gh(["issue", "list"]), "x")

    def test_other_failure_is_not_retried(self):
        self.scenario([{"match": "issue", "responses": [
            fail("HTTP 404: Not Found\nmore detail")]}])
        with self.assertRaises(common.GitHubError) as cm:
            common.gh(["issue", "view", "9"])
        self.assertEqual(len(self.calls()), 1)
        self.assertNotIn("\n", str(cm.exception))
        self.sleep.assert_not_called()

    def rate_scenario(self, reset, then):
        body = {"resources": {"core": {"remaining": 0, "reset": reset},
                              "search": {"remaining": 5, "reset": 1}}}
        self.scenario([
            {"match": "api rate_limit", "responses": [ok(json.dumps(body))]},
            {"match": "issue", "responses": [fail("HTTP 429: rate limit")] + then}])

    def test_rate_limit_waits_for_reset_and_retries_once(self):
        self.rate_scenario(int(time.time()) + 120, [ok("done")])
        self.assertEqual(common.gh(["issue", "list"]), "done")
        waited = self.sleep.call_args_list[0].args[0]
        self.assertTrue(100 <= waited <= 120, waited)

    def test_rate_limit_wait_is_capped(self):
        self.rate_scenario(int(time.time()) + 10 * 3600, [ok("done")])
        common.gh(["issue", "list"])
        self.sleep.assert_called_once_with(65 * 60)

    def test_rate_limit_retries_only_once(self):
        self.rate_scenario(int(time.time()) + 5, [fail("HTTP 403: rate limit")])
        with self.assertRaises(common.GitHubError):
            common.gh(["issue", "list"])
        self.assertEqual(self.sleep.call_count, 1)

    def test_403_without_exhausted_limit_fails_at_once(self):
        body = {"resources": {"core": {"remaining": 50, "reset": 1}}}
        self.scenario([
            {"match": "api rate_limit", "responses": [ok(json.dumps(body))]},
            {"match": "issue", "responses": [fail("HTTP 403: forbidden")]}])
        with self.assertRaises(common.GitHubError):
            common.gh(["issue", "list"])
        self.sleep.assert_not_called()


class TrustTest(FakeGh):
    def rules(self, actors, permission):
        return [
            {"match": "/timeline", "responses": [ok("".join(a + "\n" for a in actors))]},
            {"match": "/permission", "responses": [
                ok(json.dumps({"permission": permission}))]}]

    def test_write_and_admin_are_trusted(self):
        for perm in ("write", "admin"):
            self.scenario(self.rules(["alice"], perm))
            self.assertTrue(common.ready_is_trusted(7))

    def test_read_is_not_trusted(self):
        self.scenario(self.rules(["mallory"], "read"))
        self.assertFalse(common.ready_is_trusted(7))

    def test_no_ready_event_is_not_trusted(self):
        self.scenario(self.rules([], "admin"))
        self.assertFalse(common.ready_is_trusted(7))

    def test_last_actor_is_checked(self):
        self.scenario(self.rules(["alice", "bob"], "write"))
        common.ready_is_trusted(7)
        self.assertIn("collaborators/bob/permission", self.calls()[-1][1])


class LabelTest(FakeGh):
    def test_add_and_remove(self):
        self.scenario([{"match": "issue edit", "responses": [ok()]}])
        common.add_label(3, "ready")
        common.remove_label(3, "building")
        self.assertEqual(self.calls(), [
            ["issue", "edit", "3", "--add-label", "ready"],
            ["issue", "edit", "3", "--remove-label", "building"]])

    def test_label_names(self):
        self.assertEqual(common.label_names({"labels": [{"name": "a"}]}), ["a"])


class DependsOnTest(unittest.TestCase):
    def test_parses(self):
        self.assertEqual(common.depends_on("Intro\nDepends on: #4, #12 and #7\n"), [4, 12, 7])

    def test_none(self):
        self.assertEqual(common.depends_on("Nothing here #5"), [])
        self.assertEqual(common.depends_on(None), [])

    def test_case_and_several_lines(self):
        self.assertEqual(common.depends_on("depends on: #1\n  Depends on: #2"), [1, 2])


class GitEventTest(FakeGh):
    def test_git_helper(self):
        work, _ = make_repo(self.tmp)
        self.assertEqual(common.git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=work), "main")
        with self.assertRaises(common.GitError):
            common.git(["checkout", "nope"], cwd=work)
        self.assertEqual(common.git(["checkout", "nope"], cwd=work, check=False), "")

    def test_event_appends_lines(self):
        common.event("start", root=self.tmp, issue=3)
        common.event("stop", root=self.tmp)
        with open(os.path.join(self.tmp, ".lite", "events.jsonl")) as f:
            lines = f.read().splitlines()
        self.assertEqual([json.loads(l)["kind"] for l in lines], ["start", "stop"])
        self.assertEqual(json.loads(lines[0])["issue"], 3)


if __name__ == "__main__":
    unittest.main()
