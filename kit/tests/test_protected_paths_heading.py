import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

from kit.tests.helpers import FakeGh, make_repo, run_git, write_exe
from kit.tests.fake_claude import FakeClaudeGh
import flow
import merge
import setup


ROOT = Path(__file__).resolve().parents[2]
OLD = "## Paths the builder may change"
NEW = "## Protected paths this issue may change"


class HeadingTest(unittest.TestCase):
    def test_issue_guidance_names_the_protected_paths_section(self):
        for name in ("kit/templates/issue.md", "kit/skills/shape/SKILL.md", "kit/README.md"):
            with self.subTest(path=name):
                text = (ROOT / name).read_text()
                self.assertTrue(NEW in text, name + " must name " + NEW)
                self.assertNotIn(OLD, text)

    def test_template_explains_the_scope_and_usual_value(self):
        text = (ROOT / "kit/templates/issue.md").read_text()
        section = re.search(r"^## (?:Protected paths this issue|Paths the builder) may change\n"
                            r"(.*?)(?=^## |\Z)", text, re.M | re.S).group(1)
        prose = " ".join(section.replace("`", "").split()).lower()
        self.assertRegex(prose, r"(?:any|every|all) other files?\b")
        self.assertRegex(prose, r"(?:usual|normally|default).*none|none.*(?:usual|normally|default)")

    def test_allowed_paths_reads_the_new_heading_and_stops_at_the_next_section(self):
        examples = (
            ("## Goal\n\nChange it.\n\n" + NEW + "\n\n- `./package.json`\n"
             "- tests/test_old.py\n\n## Notes\n\nprivate.txt\n",
             {"package.json", "tests/test_old.py"}),
            ("## Notes\r\n\r\n```\r\noutput\r\n```\r\n\r\n" + NEW +
             "\r\n\r\n1. loop.json\r\n2. tests/test_other.py\r\n",
             {"loop.json", "tests/test_other.py"}),
        )
        for body, expected in examples:
            with self.subTest(body=body):
                self.assertEqual(merge.allowed_paths(body), expected)

    def test_the_old_heading_grants_no_paths(self):
        for body in (OLD + "\n\npackage.json\n",
                     "## Goal\r\nChange it.\r\n\r\n" + OLD +
                     "\r\n\r\n- `tests/test_old.py`\r\n\r\n## Notes\r\nKeep this.\r\n"):
            with self.subTest(body=body):
                self.assertEqual(merge.allowed_paths(body), set())


MIGRATION_GH = '''#!PYTHON
import json, os, pathlib, sys
path = pathlib.Path(os.environ["MIGRATION_GH_STATE"])
state = json.loads(path.read_text())
args = sys.argv[1:]
state["calls"].append(args)
out = ""
if args[:2] == ["label", "list"]:
    out = json.dumps([{"name": name} for name in
                      ("inbox", "shaping", "ready", "building", "needs-user")])
elif args[:2] == ["issue", "list"]:
    issues = state["issues"]
    if "--state" in args and args[args.index("--state") + 1] == "open":
        issues = [i for i in issues if i["state"] == "OPEN"]
    if "--search" in args and "Factory in:title" in args:
        issues = [i for i in issues if i["title"] == "Factory"]
    out = json.dumps(issues)
elif args[:2] == ["issue", "view"]:
    out = json.dumps(next(i for i in state["issues"] if str(i["number"]) == args[2]))
elif args[:2] == ["issue", "edit"]:
    if "--body-file" in args:
        source = args[args.index("--body-file") + 1]
        if source == "-":
            body = sys.stdin.buffer.read().decode("utf-8")
        else:
            with open(source, encoding="utf-8", newline="") as f:
                body = f.read()
    elif "--body" in args:
        body = args[args.index("--body") + 1]
    else:
        raise AssertionError("issue edit must supply the renamed body")
    issue = next(i for i in state["issues"] if str(i["number"]) == args[2])
    issue["body"] = body
    state["edits"].append({"number": issue["number"], "body": body})
else:
    raise AssertionError("unexpected gh command: " + repr(args))
path.write_text(json.dumps(state))
sys.stdout.write(out)
'''


class SetupHeadingTest(FakeGh):
    def setUp(self):
        super().setUp()
        self.work, _ = make_repo(self.tmp, {
            "loop.json": json.dumps({"Test command": "true"}),
            ".gitignore": ".loop/\nloop.local.json\n",
        })
        run_git(["push", "origin", "HEAD:loop/main"], self.work)
        self.state_path = Path(self.tmp, "migration-gh.json")
        self.old_bodies = {
            31: "## Goal\n\nKeep café text.\n\n" + OLD + "\n\nnone\n\n## Notes\n\nKeep this.\n",
            42: OLD + "\r\n\r\n- `tests/test_old.py`\r\n\r\n## Goal\r\n\r\nKeep order.\r\n",
        }
        self.issues = [dict(number=n, title="A piece", body=b, state="OPEN")
                       for n, b in self.old_bodies.items()] + [
            dict(number=7, title="Factory", body="Board", state="OPEN"),
            dict(number=53, title="Already renamed", body=NEW + "\n\nnone\n", state="OPEN"),
            dict(number=64, title="No section", body="Leave this alone.\n", state="OPEN"),
            dict(number=75, title="Closed", body=OLD + "\n\nloop.json\n", state="CLOSED"),
        ]
        self.state_path.write_text(json.dumps(dict(issues=self.issues, edits=[], calls=[])))
        os.environ["MIGRATION_GH_STATE"] = str(self.state_path)
        write_exe(Path(self.tmp, "bin", "gh"), MIGRATION_GH)

    def state(self):
        return json.loads(self.state_path.read_text())

    def command(self, *flags):
        result = subprocess.run([sys.executable, str(Path(setup.__file__).resolve()),
                                 *flags, self.work], cwd=self.work,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_setup_renames_open_issues_preserves_bodies_and_records_undo(self):
        output = self.command()
        state = self.state()
        self.assertEqual({e["number"] for e in state["edits"]}, set(self.old_bodies), output)
        self.assertEqual(len(state["edits"]), len(self.old_bodies))
        for issue in self.issues:
            actual = next(i for i in state["issues"] if i["number"] == issue["number"])
            expected = issue["body"].replace(OLD, NEW) if issue["number"] in self.old_bodies else issue["body"]
            self.assertEqual(actual["body"], expected)
        folder = Path(self.work, ".loop/migrations")
        backups = {str(p.relative_to(self.work)): p.read_bytes()
                   for p in folder.rglob("*") if p.is_file()}
        records = [json.loads(line) for line in
                   Path(self.work, ".loop/migrations.log").read_text().splitlines()]
        for number, body in self.old_bodies.items():
            with self.subTest(issue=number):
                self.assertIn(str(number), output)
                saved = [name for name, data in backups.items() if data == body.encode("utf-8")]
                self.assertTrue(saved, "the original issue body must be saved under .loop/migrations/")
                record = next((r for r in records if str(number) in r["change"]), None)
                self.assertIsNotNone(record, "each issue rename needs a migration record")
                self.assertRegex(record["change"].lower(), r"renam|protected paths this issue may change")
                self.assertIn(str(number), record["undo"])
                self.assertIn("gh issue edit", record["undo"])
                self.assertIn("--body-file", record["undo"])
                self.assertTrue(any(name in record["undo"] for name in saved), record["undo"])

    def test_dry_run_lists_matching_issues_without_edits_or_local_writes(self):
        before = {str(p.relative_to(self.work)): p.read_bytes()
                  for p in Path(self.work).rglob("*") if p.is_file()}
        output = self.command("--dry-run")
        for number in self.old_bodies:
            self.assertIn(str(number), output, "dry-run must list each issue to rename")
        self.assertEqual(self.state()["edits"], [])
        self.assertEqual(self.state()["issues"], self.issues)
        after = {str(p.relative_to(self.work)): p.read_bytes()
                 for p in Path(self.work).rglob("*") if p.is_file()}
        self.assertEqual(after, before)

    def test_second_setup_does_not_edit_again_or_overwrite_the_saved_bodies(self):
        output = self.command()
        first = self.state()
        self.assertEqual(len(first["edits"]), len(self.old_bodies), output)
        folder = Path(self.work, ".loop")
        before = {str(p.relative_to(folder)): p.read_bytes()
                  for p in folder.rglob("*") if p.is_file() and "logs" not in p.parts}
        self.command()
        self.assertEqual(self.state()["edits"], first["edits"])
        after = {str(p.relative_to(folder)): p.read_bytes()
                 for p in folder.rglob("*") if p.is_file() and "logs" not in p.parts}
        self.assertEqual(after, before)


class FlowHeadingTest(FakeClaudeGh):
    def test_build_uses_the_new_section_for_builder_permissions(self):
        work, _ = make_repo(self.tmp, {"loop.json": json.dumps({
            "Test command": "echo AssertionError; false"})})
        run_git(["push", "origin", "HEAD:loop/main"], work)
        info = dict(title="Change a test", comments=[], body=NEW + "\n\ntests/test_new.py\n")
        self.scenario([
            {"match": "issue view", "responses": [{"stdout": json.dumps(info)}]},
            {"match": "issue comment", "responses": [{}]},
            {"match": "issue edit", "responses": [{}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
        ])
        self.claude({
            "test-writer": [{"files": {"tests/test_new.py": "new\n"},
                             "reply": "TESTS:\ntests/test_new.py"}],
            "builder": [{"reply": "PARK: Stop after recording permissions | Inspect the test."}],
        })
        result = flow.build(7, work)
        self.assertEqual(result.status, "parked", result.reason)
        builder = next(c for c in self.claude_calls() if c["role"] == "builder")
        self.assertEqual(builder["env"]["LOOP_ALLOWED"], "tests/test_new.py")
        self.assertEqual(builder["env"]["LOOP_LOCKED"], "")


if __name__ == "__main__":
    unittest.main()
