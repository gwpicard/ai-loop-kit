"""Exercise the merge gate across process restarts, using real test commands."""
import json
from pathlib import Path
import shlex
import subprocess
import sys
from unittest import mock

from kit.tests.helpers import FakeGh, make_repo, run_git
import common
import loop
import pass_


SCRIPTS = str(Path(__file__).resolve().parents[1] / "scripts")


class FullSuiteCadenceTest(FakeGh):
    def setUp(self):
        super().setUp()
        self.trace = Path(self.tmp, "commands")
        target = shlex.quote(str(self.trace))
        record_files = (
            "import json, sys; "
            "open(sys.argv[1], 'a').write('targeted ' + json.dumps(sys.argv[2:]) + '\\n')"
        )
        self.settings = {
            "Test command": "echo full $(git rev-parse HEAD) >> %s; test ! -f FAIL" % target,
            "Test files command": "%s -c %s %s {files}" % (
                shlex.quote(sys.executable), shlex.quote(record_files), target),
            "Check command": "echo check >> " + target,
        }
        self.work, self.origin = make_repo(self.tmp, {
            "loop.json": json.dumps(self.settings),
            "tests/test_locked.py": "locked\n",
            "app.py": "initial\n",
        })
        run_git(["push", "origin", "HEAD:loop/main"], self.work)
        self.serial = 0

    def configure(self, **values):
        self.settings.update(values)
        Path(self.work, "loop.json").write_text(json.dumps(self.settings))
        run_git(["add", "loop.json"], self.work)
        run_git(["commit", "-m", "configure fixture"], self.work)
        run_git(["push", "origin", "HEAD:loop/main"], self.work)

    def candidate(self, files=None):
        self.serial += 1
        self.branch = "issue/" + str(self.serial)
        run_git(["fetch", "origin"], self.work)
        run_git(["checkout", "-b", self.branch, "origin/loop/main"], self.work)
        files = files or {"app.py": "change %s\n" % self.serial}
        for name, text in files.items():
            path = Path(self.work, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        run_git(["add", "-A"], self.work)
        run_git(["commit", "-m", "candidate"], self.work)
        self.sha = common.git(["rev-parse", "HEAD"], self.work)
        run_git(["push", "origin", self.branch], self.work)
        return self.sha

    def merge_process(self):
        pr = {"number": 7, "headRefOid": self.sha,
              "mergeCommit": {"oid": self.sha}}
        self.scenario([
            {"match": "issue view 1 --json body", "responses": [{"stdout": json.dumps({
                "body": "Add a feature.", "comments": [{
                    "body": "TESTS:\ntests/test_locked.py\n"}]})}]},
            {"match": "pr list", "responses": [
                {"stdout": json.dumps([dict(pr, state="OPEN")])},
                {"stdout": json.dumps([dict(pr, state="MERGED")])}]},
            {"match": "--json comments", "responses": [{"stdout": '{"comments": []}'}]},
            {"match": "pr comment", "responses": [{}]},
            {"match": "pr merge", "responses": [{}]},
            {"match": "issue close", "responses": [{}]},
            {"match": "issue edit", "responses": [{}]},
        ])
        # Every invocation starts a new interpreter, discarding all module state.
        code = (
            "import json, sys; sys.path.insert(0, sys.argv[1]); import merge; "
            "r = merge.merge(1, sys.argv[3], 'VERDICT: APPROVE\\nHEAD: ' + sys.argv[4], sys.argv[2]); "
            "print(json.dumps(r._asdict()))"
        )
        process = subprocess.run(
            [sys.executable, "-c", code, SCRIPTS, self.work, self.branch, self.sha],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout.splitlines()[-1])
        if result["ok"]:
            # The fake answers the API; advance the real fixture ref as GitHub would.
            run_git(["push", "origin", self.sha + ":loop/main"], self.work)
        return result

    def commands(self):
        return self.trace.read_text().splitlines() if self.trace.exists() else []

    def merged_events(self):
        path = Path(self.work, ".loop/events.jsonl")
        return [e for e in map(json.loads, path.read_text().splitlines())
                if e["kind"] == "merged"]

    def seed_three_merges(self):
        for _ in range(3):
            self.candidate()
            result = self.merge_process()
            self.assertTrue(result["ok"], result["reason"])
        self.trace.write_text("")

    def test_reads_the_default_and_a_configured_interval(self):
        for override, expected in (({}, 4), ({"Full suite every": 2}, 2)):
            with self.subTest(settings=override):
                Path(self.work, "loop.json").write_text(json.dumps(
                    dict(self.settings, **override)))
                try:
                    settings = common.read_settings(self.work)
                except common.SettingsError as error:
                    self.fail("Full suite every must be accepted: " + str(error))
                self.assertEqual(settings.get("Full suite every"), expected)

    def test_refuses_intervals_below_one_with_a_clear_message(self):
        for value in (0, -1, 0.5):
            with self.subTest(value=value):
                Path(self.work, "loop.json").write_text(json.dumps(
                    dict(self.settings, **{"Full suite every": value})))
                with self.assertRaises(common.SettingsError) as caught:
                    common.read_settings(self.work)
                message = str(caught.exception)
                self.assertIn("Full suite every", message)
                self.assertNotIn("unknown key", message)
                self.assertRegex(message.lower(), r"invalid|at least|>=|minimum")

    def test_targeted_merges_and_the_fourth_full_run_survive_restarts(self):
        for index in range(1, 9):
            with self.subTest(merge=index):
                names = (["tests/test_z%s.py" % index, "tests/test a%s.py" % index]
                         if index % 2 else
                         ["tests/test b%s.py" % index, "tests/test_a%s.py" % index])
                self.candidate(dict([(names[0], "first\n"), ("app.py", str(index)),
                                     (names[1], "second\n")]))
                before = len(self.commands())
                result = self.merge_process()
                self.assertTrue(result["ok"], result["reason"])
                due = index % 4 == 0
                expected = (["full " + self.sha] if due else
                            ["targeted " + json.dumps(sorted(names + ["tests/test_locked.py"]))])
                self.assertEqual(self.commands()[before:], expected + ["check"])
                event = self.merged_events()[-1]
                self.assertIs(event.get("full_suite"), due,
                              "each merged event must record whether the full suite ran")

    def test_no_files_command_runs_the_full_suite_on_every_merge(self):
        self.configure(**{"Test files command": ""})
        for _ in range(2):
            self.candidate()
            before = len(self.commands())
            result = self.merge_process()
            self.assertTrue(result["ok"], result["reason"])
            self.assertEqual(self.commands()[before:], ["full " + self.sha, "check"])

    def test_interval_one_keeps_a_full_run_on_every_merge(self):
        self.configure(**{"Full suite every": 1})
        for _ in range(2):
            self.candidate()
            before = len(self.commands())
            result = self.merge_process()
            self.assertTrue(result["ok"], result["reason"])
            self.assertEqual(self.commands()[before:], ["full " + self.sha, "check"])

    def test_due_failure_checks_a_passing_loop_head_once_and_returns_to_builder(self):
        self.seed_three_merges()
        base = common.git(["rev-parse", "origin/loop/main"], self.work)
        self.candidate({"FAIL": "candidate regression\n"})
        result = self.merge_process()
        self.assertFalse(result["ok"])
        self.assertFalse(result["park"], result["reason"])
        self.assertEqual([c for c in self.commands() if c.startswith("full ")],
                         ["full " + self.sha, "full " + base])
        self.assertFalse(any(c[:2] == ["pr", "merge"] for c in self.calls()))
        self.assertEqual(len(self.merged_events()), 3)

    def test_due_failure_already_on_loop_head_is_not_returned_to_builder(self):
        self.seed_three_merges()
        base = self.candidate({"FAIL": "earlier regression\n"})
        run_git(["push", "origin", base + ":loop/main"], self.work)
        self.candidate()
        result = self.merge_process()
        self.assertFalse(result["ok"])
        self.assertTrue(result["park"], "a loop-branch failure must not return to the builder")
        self.assertRegex(result["reason"].lower(), r"already.*loop branch")
        self.assertEqual([c for c in self.commands() if c.startswith("full ")],
                         ["full " + self.sha, "full " + base])
        self.assertFalse(any(c[:2] == ["pr", "merge"] for c in self.calls()))
        self.assertEqual(len(self.merged_events()), 3)

    def test_drain_runs_full_tests_before_the_pass_and_final_pull_request(self):
        self.candidate()
        run_git(["commit", "--allow-empty", "-m", "Issue fixture"], self.work)
        run_git(["push", "origin", "HEAD:loop/main"], self.work)
        run_git(["fetch", "origin"], self.work)
        head = common.git(["rev-parse", "origin/loop/main"], self.work)
        Path(self.work, ".loop").mkdir(exist_ok=True)
        self.scenario([
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "pr create", "responses": [{}]},
        ])

        def run_pass(*args):
            self.assertEqual(self.commands(), ["full " + head, "check"])
            self.assertFalse(any(c[:2] == ["pr", "create"] for c in self.calls()))
            return {}, "Pass complete."

        with mock.patch.object(pass_, "run_pass", side_effect=run_pass) as passed, \
                mock.patch.object(loop, "summary", return_value="Fixture summary"), \
                mock.patch.object(loop.report, "render", return_value="Fixture report"), \
                mock.patch.object(loop, "hands_on", return_value=""), \
                mock.patch.object(loop, "decisions", return_value=""):
            loop.drain(self.work, common.read_settings(self.work), loop.new_state())
        passed.assert_called_once()
        self.assertTrue(any(c[:2] == ["pr", "create"] for c in self.calls()))
        self.assertEqual(self.commands(), ["full " + head, "check"])
