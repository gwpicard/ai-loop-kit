import json
import os
from pathlib import Path
import shlex
import sys
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git
import common
import flow
import merge
import pass_


TEMP_NAMES = ("TMPDIR", "TMP", "TEMP", "LOOP_TMPDIR")
PROBE = '''import json
import os
from pathlib import Path
import sys
import tempfile

names = ("TMPDIR", "TMP", "TEMP", "LOOP_TMPDIR")
env = {name: os.environ.get(name) for name in names}
with tempfile.NamedTemporaryFile(dir=env["TMPDIR"]) as temporary:
    record = {"command": sys.argv[1], "env": env, "cwd": os.getcwd(),
              "temporary": temporary.name,
              "device": os.stat(temporary.name).st_dev}
    with open(sys.argv[2], "a") as journal:
        journal.write(json.dumps(record) + "\\n")
'''
FAKE_TEST = '''from pathlib import Path
import unittest

class BuildTest(unittest.TestCase):
    def test_application_exists(self):
        self.assertTrue(Path("app.py").is_file())
'''


class VisibleBuildTempTest(FakeClaudeGh):
    def project(self, parent, name="work"):
        parent.mkdir(parents=True)
        journal = parent / "commands.jsonl"
        python = shlex.quote(sys.executable)

        def command(label):
            return "%s probe.py %s %s" % (python, label, shlex.quote(str(journal)))

        settings = {"Loop branch": "loop/main", "Max rounds": 1,
                    "Test command": command("Test") + " && " + python
                    + " -m unittest discover -s tests",
                    "Prepare command": command("Prepare"),
                    "Check command": command("Check"),
                    "Smoke command": command("Smoke")}
        work, _ = make_repo(str(parent), {"loop.json": json.dumps(settings),
                                          "probe.py": PROBE})
        if name != "work":
            renamed = parent / name
            Path(work).rename(renamed)
            work = str(renamed)
        run_git(["push", "origin", "main:loop/main"], work)
        self.scenario([
            {"match": "issue view", "responses": [{"stdout": json.dumps({
                "title": "Add the application", "body": "", "comments": []})}]},
            {"match": "issue comment", "responses": [{}]},
            {"match": "issue edit", "responses": [{}]},
            {"match": "issue close", "responses": [{}]},
            {"match": "issue create", "responses": [{}]},
            {"match": "issue list", "responses": [{"stdout": "[]"}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]}])
        return work, journal

    def assert_visible_temp(self, parent, work, records, calls):
        environments = [(record["command"], record["env"]) for record in records]
        environments += [(call["role"], call["env"]) for call in calls]
        self.assertTrue(environments)
        temp = Path(environments[0][1]["TMPDIR"])
        for source, env in environments:
            self.assertEqual({name: env.get(name) for name in TEMP_NAMES},
                             dict.fromkeys(TEMP_NAMES, str(temp)), source)
        self.assertIn(Path(work).parent, (temp.parent, temp.parent.parent))
        self.assertFalse(temp.is_relative_to(Path(work)))
        self.assertFalse(temp.exists(), "The build left its temporary folder behind")
        for record in records:
            self.assertEqual(record["device"], os.stat(work).st_dev)
            self.assertEqual(Path(record["temporary"]).parent, temp)
            self.assertFalse(Path(record["temporary"]).exists())
        # The enclosing test run may itself be in a hidden folder.
        # Check every component the kit adds below the project parent.
        for path, root in ((temp, parent), (temp.resolve(), parent.resolve())):
            relative = path.relative_to(root)
            self.assertFalse(any(part.startswith(".") for part in relative.parts),
                             "Sessions and commands received hidden temporary path: %s" % path)

    def test_build_sessions_and_commands_receive_visible_sibling_temp_and_clean_up(self):
        for layout, name in (("plain", "work"), ("parent with spaces", "notes app")):
            with self.subTest(layout=layout):
                parent = Path(self.tmp, layout)
                work, journal = self.project(parent, name)
                self.claude({
                    "test-writer": [{"files": {"tests/test_new.py": FAKE_TEST},
                                     "reply": "TESTS:\ntests/test_new.py"}],
                    "builder": [{"files": {"app.py": "application = True\n"}}],
                    "reviewer": [{"reply": "VERDICT: APPROVE\nHEAD: {HEAD}"}]})
                with mock.patch.object(merge, "merge", return_value=merge.Result(
                        True, False, "merged", "abc")):
                    result = flow.build(7, work)
                self.assertEqual(result.status, "merged", result.reason)
                records = [json.loads(line) for line in journal.read_text().splitlines()]
                self.assertEqual({r["command"] for r in records}, {"Prepare", "Test", "Check"})
                calls = self.claude_calls()
                self.assertEqual([c["role"] for c in calls], ["test-writer", "builder", "reviewer"])
                tree = parent / ".loop-worktrees" / (name + "-7")
                self.assertEqual({Path(c["cwd"]).resolve() for c in calls}, {tree.resolve()})
                self.assertFalse(tree.exists())
                self.assert_visible_temp(parent, work, records, calls)

    def test_smoke_and_pass_sessions_receive_visible_temp_and_clean_up_after_failure(self):
        parent = Path(self.tmp, "smoke project")
        work, journal = self.project(parent)
        settings = common.read_settings(work)
        settings["Smoke command"] += " && exit 3"
        self.claude({"pass": [{"reply": "FINDINGS:\nnone"}]})
        with common.build_environment(work):
            report, _ = pass_.run_pass(work, settings, "origin/main")
        self.assertEqual(report["errors"], [])
        self.assertIn("Smoke command failed", report["smoke"])
        records = [json.loads(line) for line in journal.read_text().splitlines()]
        self.assertEqual([r["command"] for r in records], ["Prepare", "Smoke"])
        calls = self.claude_calls()
        self.assertTrue(calls)
        self.assertEqual({c["role"] for c in calls}, {"pass"})
        self.assert_visible_temp(parent, work, records, calls)
