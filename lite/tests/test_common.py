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

    def test_no_retry_on_5xx_when_retry_is_false(self):
        self.scenario([{"match": "issue", "responses": [
            fail("HTTP 502: Bad Gateway"), ok("late")]}])
        with self.assertRaises(common.GitHubError):
            common.gh(["issue", "comment", "3"], retry=False)
        self.assertEqual(len(self.calls()), 1)
        self.sleep.assert_not_called()

    def test_timeout_is_transient(self):
        self.scenario([{"match": "issue", "responses": [
            {"sleep": 3, "stdout": "slow"}, ok("quick")]}])
        with mock.patch.object(common, "TIMEOUT", 0.5):
            self.assertEqual(common.gh(["issue", "list"]), "quick")
        self.sleep.assert_called_once_with(5)

    def test_timeout_gives_up_with_one_line(self):
        self.scenario([{"match": "issue", "responses": [{"sleep": 3}]}])
        with mock.patch.object(common, "TIMEOUT", 1.0):
            with self.assertRaises(common.GitHubError) as cm:
                common.gh(["issue", "list"])
        self.assertIn("timed out", str(cm.exception))
        self.assertEqual(len(self.calls()), 4)

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


def ev(kind, login, label="ready"):
    actor = {"login": login} if login else None
    return {"event": kind, "label": {"name": label}, "actor": actor}


class TrustTest(FakeGh):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(common, "sleep")
        p.start()
        self.addCleanup(p.stop)

    def check(self, events, permission="write", pages=1):
        rules = [{"match": "/timeline", "responses": [
            ok("".join(json.dumps(events) for _ in range(pages)))]}]
        if isinstance(permission, dict):
            rules.append({"match": "/permission", "responses": [permission]})
        else:
            rules.append({"match": "/permission", "responses": [
                ok(json.dumps({"permission": permission}))]})
        self.scenario(rules)
        return common.ready_is_trusted(7)

    def test_write_and_admin_are_trusted(self):
        for perm in ("write", "admin"):
            self.assertTrue(self.check([ev("labeled", "alice")], perm))

    def test_read_is_not_trusted(self):
        self.assertFalse(self.check([ev("labeled", "mallory")], "read"))

    def test_no_ready_event_is_not_trusted(self):
        self.assertFalse(self.check([ev("labeled", "alice", "bug")], "admin"))
        self.assertFalse(self.check([], "admin"))

    def test_last_actor_is_checked(self):
        self.check([ev("labeled", "alice"), ev("labeled", "bob")])
        self.assertIn("collaborators/bob/permission", self.calls()[-1][1])

    def test_unlabel_then_relabel_by_stranger_is_untrusted(self):
        events = [ev("labeled", "alice"), ev("unlabeled", "alice"),
                  ev("labeled", "mallory")]
        self.assertFalse(self.check(events, "read"))
        self.assertIn("collaborators/mallory/permission", self.calls()[-1][1])

    def test_removed_label_is_untrusted(self):
        self.assertFalse(self.check([ev("labeled", "alice"), ev("unlabeled", "alice")]))

    def test_null_actor_is_untrusted_without_a_lookup(self):
        self.assertFalse(self.check([ev("labeled", None)], "admin"))
        self.assertTrue(all("permission" not in c[1] for c in self.calls()))

    def test_bot_actor_with_failed_lookup_is_untrusted(self):
        failure = fail("HTTP 404: x[bot] is not a user")
        self.assertFalse(self.check([ev("labeled", "x[bot]")], failure))

    def test_paginated_output_is_read(self):
        self.assertTrue(self.check([ev("labeled", "alice")], "admin", pages=2))


class LabelTest(FakeGh):
    def test_add_and_remove(self):
        self.scenario([{"match": "issue edit", "responses": [ok()]}])
        common.add_label(3, "ready")
        common.remove_label(3, "building")
        self.assertEqual(self.calls(), [
            ["issue", "edit", "3", "--add-label", "ready"],
            ["issue", "edit", "3", "--remove-label", "building"]])


def h(n):
    return "#" + str(n)  # built, so no hash-digits text is tracked


class DependsOnTest(unittest.TestCase):
    def test_parses(self):
        self.assertEqual(common.depends_on("Intro\nDepends on: %s, %s and %s\n" % (h(4), h(12), h(7))), [4, 12, 7])

    def test_none(self):
        self.assertEqual(common.depends_on("Nothing here " + h(5)), [])
        self.assertEqual(common.depends_on(None), [])

    def test_case_and_several_lines(self):
        self.assertEqual(common.depends_on("depends on: %s\n  Depends on: %s" % (h(1), h(2))), [1, 2])


class GitEventTest(FakeGh):
    def test_git_helper(self):
        work, _ = make_repo(self.tmp)
        self.assertEqual(common.git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=work), "main")
        with self.assertRaises(common.GitError):
            common.git(["checkout", "nope"], cwd=work)
        self.assertEqual(common.git(["checkout", "nope"], cwd=work, check=False), "")
        with mock.patch.object(common, "TIMEOUT", 0.001):
            with self.assertRaises(common.GitError) as cm:
                common.git(["status"], cwd=work)
        self.assertIn("timed out", str(cm.exception))

    def test_event_appends_lines(self):
        common.event("start", root=self.tmp, issue=3)
        common.event("stop", root=self.tmp)
        with open(os.path.join(self.tmp, ".lite", "events.jsonl")) as f:
            lines = f.read().splitlines()
        self.assertEqual([json.loads(l)["kind"] for l in lines], ["start", "stop"])
        self.assertEqual(json.loads(lines[0])["issue"], 3)


if __name__ == "__main__":
    unittest.main()
