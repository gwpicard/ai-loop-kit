"""Retain drain diagnostics through the loop command, with or without a final pull request."""
import json
from pathlib import Path
import shlex
import subprocess
import sys

from kit.tests.helpers import FakeGh, make_repo, run_git


KIT = Path(__file__).resolve().parents[1]
LOG = ".loop/logs/drain.log"
COMMAND = """import json
from pathlib import Path
import sys

source, phase = Path(sys.argv[1]), sys.argv[2]
data = json.loads(source.read_text())[phase]
with source.with_suffix('.calls').open('a') as calls:
    calls.write(phase + '\\n')
sys.stdout.write(data['stdout'])
sys.stdout.flush()
sys.stderr.write(data['stderr'])
sys.stderr.flush()
sys.exit(data['code'])
"""


class DrainFailureOutputTest(FakeGh):
    def setUp(self):
        super().setUp()
        self.source = Path(self.tmp, "command-output.json")
        command = "%s commands.py %s " % (shlex.quote(sys.executable), shlex.quote(str(self.source)))
        self.work, _ = make_repo(self.tmp, {
            "loop.json": json.dumps({
                "Prepare command": command + "Prepare",
                "Test command": command + "Test",
                "Check command": command + "Check",
                "Idle hours": 0,
            }),
            "commands.py": COMMAND,
        })
        run_git(["push", "origin", "HEAD:loop/main"], self.work)
        self.runtime = Path(self.work, ".loop")
        self.runtime.mkdir()

    def drive(self, failures=(), attempt="current", passing=False, pull_request=False):
        data = {phase: dict(stdout="%s %s stdout\n" % (attempt, phase),
                            stderr="%s %s stderr\n" % (attempt, phase), code=0)
                for phase in ("Prepare", "Test", "Check")}
        data["Test"]["stdout"] += "\n".join(failures) + "\n" + "ordinary progress\n" * 80
        data["Test"]["code"] = 0 if passing else 1
        self.source.write_text(json.dumps(data))
        self.source.with_suffix(".calls").write_text("")
        factory = dict(number=1, title="Factory", body="", labels=[])
        prs = [dict(number=9, url="https://example.test/pull/9")] if pull_request else []
        self.scenario([
            {"match": "label list", "responses": [{"stdout": json.dumps([
                dict(name=name) for name in ("inbox", "shaping", "ready", "building", "needs-user")])}]},
            {"match": "issue list --state open", "responses": [{"stdout": json.dumps([factory])}]},
            {"match": "issue list --state closed", "responses": [{"stdout": "[]"}]},
            {"match": "issue edit", "responses": [{}]},
            {"match": "pr list --head", "responses": [{"stdout": json.dumps(prs)}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "pr view", "responses": [{"stdout": json.dumps(dict(body=""))}]},
            {"match": "pr edit", "responses": [{}]},
            {"match": "api repos/{owner}/{repo} --jq .delete_branch_on_merge",
             "responses": [{"stdout": "false"}]},
        ])
        output = self.runtime / "loop.out"
        with output.open("w") as stream:
            result = subprocess.run([str(KIT / "bin/loop"), "run"], cwd=self.work,
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=30)
        text = output.read_text()
        self.assertEqual(result.returncode, 0, text)
        self.assertNotIn("problem, will check again", text)
        self.assertEqual(self.source.with_suffix(".calls").read_text().splitlines(),
                         ["Prepare", "Test", "Check"] if passing else ["Prepare", "Test"])
        events = [json.loads(line) for line in (self.runtime / "events.jsonl").read_text().splitlines()]
        ends = [event for event in events if event["kind"] == "drain" and event.get("phase") == "end"]
        self.assertTrue(ends, text)
        self.assertEqual(ends[-1]["outcome"], "pass" if passing else "fail", ends[-1])
        return text, ends[-1]

    def assert_diagnostics(self, text, event, failures):
        lines = [line for line in text.splitlines() if LOG in line]
        with self.subTest(destination="loop.out"):
            self.assertEqual(len(lines), 1, text)
            self.assertRegex(lines[0], r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ")
        for destination, report in (("loop.out", "\n".join(lines)), ("drain event", event.get("reason", ""))):
            with self.subTest(destination=destination):
                self.assertIn(LOG, report)
                for failure in failures[:20]:
                    self.assertIn(failure, report)
                for failure in failures[20:]:
                    self.assertNotIn(failure, report)
                self.assertNotIn("ordinary progress", report)

    def test_each_drain_replaces_the_full_command_log_including_a_failed_test(self):
        path = Path(self.work, LOG)
        path.parent.mkdir(parents=True)
        path.write_text("stale output\n")
        for attempt, passing in (("first", True), ("second", False)):
            with self.subTest(attempt=attempt):
                self.drive(["FAIL: test_store (tests.Storage)"] if not passing else [],
                           attempt=attempt, passing=passing)
                self.assertTrue(path.is_file(), "save the drain output at " + LOG)
                saved = path.read_text()
                for phase in (("Prepare", "Test", "Check") if passing else ("Prepare", "Test")):
                    self.assertIn("%s %s stdout\n" % (attempt, phase), saved)
                    self.assertIn("%s %s stderr\n" % (attempt, phase), saved)
                self.assertEqual(saved.count("ordinary progress\n"), 80)
                self.assertNotIn("stale output", saved)
                if not passing:
                    self.assertIn("FAIL: test_store (tests.Storage)", saved)
                    self.assertNotIn("first ", saved)

    def test_failed_drain_reports_twenty_failure_lines_and_an_event_with_a_final_pull_request(self):
        failures = ["FAIL: test_case_%03d (tests.Many)" % index for index in range(25)]
        for ordered in (failures, list(reversed(failures))):
            with self.subTest(first=ordered[0]):
                text, event = self.drive(ordered[:2] + ordered, pull_request=True)
                self.assertTrue(any(call[:2] == ["pr", "edit"] for call in self.calls()))
                self.assert_diagnostics(text, event, ordered)

    def test_failed_drain_reports_the_reason_when_no_final_pull_request_exists(self):
        examples = (
            ["FAIL: test_store (tests.Storage)", "ERROR: test_load (tests.Storage)", "FAIL test_storage 12 tests"],
            ["FAIL test_network 8 tests", "ERROR: test_connect (tests.Network)", "FAIL: test_disconnect (tests.Network)"],
        )
        for failures in examples:
            with self.subTest(first=failures[0]):
                text, event = self.drive(failures)
                self.assertFalse(any(call[:2] in (["pr", "create"], ["pr", "edit"])
                                     for call in self.calls()), "no commits await a final pull request")
                self.assert_diagnostics(text, event, failures)
