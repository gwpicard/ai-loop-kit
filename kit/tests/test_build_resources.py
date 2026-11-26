"""Build temp files stay beside worktrees and events record machine resources."""
import json
import os
from pathlib import Path
import shlex
import sys
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git, settings_json
from kit.tests import test_flow as fixtures
import common
import flow
import merge


class BuildResourcesTest(FakeClaudeGh):
    def fixture(self, parent, command=""):
        os.makedirs(parent, exist_ok=True)
        settings = fixtures.AGENTS.replace("seq 1 99;", command + "seq 1 99;")
        self.work, _ = make_repo(parent, {"loop.json": settings_json(settings)})
        run_git(["push", "origin", "main:loop/main"], self.work)
        self.scenario([
            {"match": "issue view 7", "responses": [{"stdout": json.dumps({
                "title": "Add it", "body": "Do the thing.", "comments": []})}]},
            {"match": "issue comment", "responses": [{}]},
            {"match": "issue edit", "responses": [{}]},
            {"match": "issue close", "responses": [{}]},
            {"match": "issue list", "responses": [{"stdout": "[]"}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "pr edit", "responses": [{}]}])

    def scenario_build(self, parked=False):
        self.claude({
            "test-writer": [fixtures.WRITER],
            "builder": ([{"reply": "PARK: Need credentials | Supply them."}] if parked else
                        [{"files": {"app.py": "1\n"}}, {"files": {"app.py": "2\n"}}]),
            "reviewer": [fixtures.CHANGES, fixtures.APPROVE]})

    def test_build_commands_and_sessions_use_temp_beside_worktrees_then_remove_it(self):
        for name in ("project", "nested projects/project group"):
            with self.subTest(layout=name):
                parent = Path(self.tmp, name)
                output = Path(self.tmp, "command-temp.jsonl")
                if output.exists():
                    output.unlink()
                script = ("import json, os, tempfile; "
                          "p = tempfile.mkdtemp(); "
                          "print(json.dumps([tempfile.gettempdir(), p, os.environ['TMPDIR']]))")
                command = "%s -c %s >> %s; " % (
                    shlex.quote(sys.executable), shlex.quote(script), shlex.quote(str(output)))
                self.fixture(str(parent), command)
                self.scenario_build()
                with mock.patch.object(merge, "merge", return_value=fixtures.MERGED):
                    result = flow.build(7, self.work)
                self.assertEqual(result.status, "merged", result.reason)
                commands = [json.loads(line) for line in output.read_text().splitlines()]
                self.assertTrue(commands, "the build must run the configured command")
                calls = self.claude_calls()
                self.assertTrue(calls)
                temp = Path(calls[0]["env"]["TMPDIR"])
                for call in calls:
                    self.assertEqual(Path(call["env"]["TMPDIR"]), temp)
                for printed, created, inherited in commands:
                    self.assertEqual(Path(printed).resolve(), temp.resolve())
                    self.assertEqual(Path(created).parent.resolve(), temp.resolve())
                    self.assertEqual(Path(inherited), temp)
                    self.assertFalse(Path(created).exists())
                self.assertFalse(temp.exists())
                self.assertEqual(temp.parent.resolve(), Path(self.work).parent.joinpath("loop-tmp").resolve())

    def test_every_step_and_terminal_event_records_load_and_pressure(self):
        pr = {"number": 9, "state": "MERGED", "mergeCommit": {"oid": "abc"}}
        for pressure in (2, None):
            for status in ("merged", "parked"):
                with self.subTest(pressure=pressure, status=status):
                    self.fixture(os.path.join(self.tmp, "events-%s-%s" % (pressure, status)))
                    path = Path(self.work, ".loop/events.jsonl")
                    self.scenario_build(parked=status == "parked")
                    with mock.patch.object(common.os, "getloadavg", return_value=(1.25, 8.5, 9.75)), \
                            mock.patch.object(common, "pressure_level", return_value=pressure), \
                            mock.patch.object(merge, "find_pr", return_value=pr):
                        result = flow.build(7, self.work)
                    self.assertEqual(result.status, status, result.reason)
                    events = [json.loads(line) for line in path.read_text().splitlines()]
                    measured = [e for e in events if e["kind"] in ("step", "merged", "parked")]
                    self.assertEqual({e["kind"] for e in measured}, {"step", status})
                    self.assertEqual({e["phase"] for e in measured if e["kind"] == "step"}, {"start", "end"})
                    if status == "parked":
                        self.assertTrue(any(e.get("step") == "builder" and e.get("outcome") == "parked"
                                            for e in measured), "exercise a park from the builder session")
                    missing = [(e["kind"], e.get("step"), e.get("phase")) for e in measured
                               if not {"load", "pressure"} <= e.keys()]
                    self.assertEqual(missing, [], "every event must carry load and pressure, including null pressure")
                    for event in measured:
                        self.assertEqual(event["load"], 1.25, event)
                        self.assertEqual(event["pressure"], pressure, event)

    def test_spotlight_exclusion_covers_build_temp_and_worktree_folders(self):
        readme = Path(__file__).resolve().parents[1].joinpath("README.md").read_text()
        paragraphs = [" ".join(p.split()) for p in readme.split("\n\n")]
        guidance = [p for p in paragraphs if "Spotlight" in p and "Search Privacy" in p]
        self.assertTrue(guidance, "the reference must explain the Spotlight exclusion")
        paragraph = " ".join(guidance)
        self.assertIn(".loop-worktrees", paragraph)
        self.assertIn("loop-tmp/loop-build-*", paragraph)
        self.assertRegex(paragraph.lower(), r"\btemp(?:orary)?\b",
                         "explain that build temporary files live within the excluded parent folder")
