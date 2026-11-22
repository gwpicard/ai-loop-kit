"""The plan's facts reach the places that use them without losing the old file."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest
from unittest import mock

from kit.tests import test_loop, test_pass, test_setup
from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import FAKE_GH, FakeGh, make_repo, run_git, write_exe
import common
import flow
import loop
import pass_
import setup


KIT = Path(__file__).resolve().parents[1]
TITLE = "Find a home for the contents of PLAN.md"
STOPS = (
    "spending money or changing billing",
    "credentials, secrets or access rights",
    "permissions, repository or service settings",
    "irreversible data changes",
    "anything that makes the project public",
    "a new dependency, or a change to a protected path",
    "any decision only the person can make",
)
SECTIONS = (
    ("Decisions", "Keep exports local."),
    ("Product rules", "Use British spelling."),
    ("Stops", "Ask before deleting an archive."),
    ("Surfaces", "- import records\n- export records"),
    ("Lessons", "Reject empty identifiers before saving."),
    ("Deviations", "Used the existing cache."),
    ("Try it", "Run the preview command."),
    ("Project notes", "Retain this uncommon section too."),
)


def old_plan(reverse=False):
    sections = tuple(reversed(SECTIONS)) if reverse else SECTIONS
    return "# Plan\n\n" + "\n".join("## %s\n\n%s\n" % s for s in sections) + "\n## Empty\n\n"


class Guidance(unittest.TestCase):
    def test_only_the_setup_migration_names_the_plan(self):
        found = []
        for folder in ("briefs", "scripts", "skills", "templates"):
            for path in (KIT / folder).rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts and path != KIT / "scripts/setup.py":
                    if "PLAN.md" in path.read_text(encoding="utf-8"):
                        found.append(str(path.relative_to(KIT)))
        self.assertEqual(found, [], "Only setup's migration may name PLAN.md")
        self.assertFalse((KIT / "templates/PLAN.md").exists())

    def test_preamble_holds_the_stop_list_and_the_product_choice_rule(self):
        text = " ".join((KIT / "briefs/preamble.md").read_text().split())
        for stop in STOPS:
            with self.subTest(stop=stop):
                self.assertIn(stop, text)
        self.assertIn("Park only for a choice that changes what the product does or looks like, "
                      "or what ships. Decide everything else yourself and record it under DEVIATIONS.", text)

    def test_the_plan_conflict_helper_is_removed(self):
        self.assertFalse(hasattr(flow, "keep_added_plan_lines"))

    def test_lessons_brief_requires_a_check_or_standing_instruction_and_no_append(self):
        text = " ".join((KIT / "briefs/pass-lessons.md").read_text().split())
        self.assertIn("inbox", text)
        self.assertIn("AGENTS.md", text)
        self.assertIn("check", text)
        self.assertRegex(text.lower(), r"(?:do not|never)[^.]*\b(?:append|write)\b|(?:append|write)[^.]*no file")


class Migration(FakeGh):
    def project(self, reverse=False):
        self.work, self.origin = make_repo(self.tmp, {
            "loop.json": '{"Test command": "true"}\n', "PLAN.md": old_plan(reverse),
            "AGENTS.md": "# Project\nKeep exports local.\n"})
        # Record stdin as well as arguments, so the real setup command can use body-file.
        script = FAKE_GH.replace('rules = json.load',
            'with open(path + ".bodies", "a") as f:\n'
            '    f.write(json.dumps({"args": sys.argv[1:], "body": sys.stdin.read()}) + "\\n")\n'
            'rules = json.load')
        write_exe(os.path.join(self.tmp, "bin", "gh"), script)
        Path(self.scenario_path + ".bodies").unlink(missing_ok=True)
        self.scenario([
            test_setup.rule("label list", json.dumps([{"name": n} for n in setup.LABELS])),
            test_setup.rule("issue list", '[{"number":7,"title":"Factory"}]'),
            test_setup.rule("issue create", "https://github.com/o/r/issues/42\n"),
        ])

    def command(self, dry_run=False):
        result = subprocess.run([sys.executable, setup.__file__] + (["--dry-run"] if dry_run else [])
                                + [self.work], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def bodies(self):
        path = Path(self.scenario_path + ".bodies")
        out = []
        for line in path.read_text().splitlines() if path.exists() else []:
            record = json.loads(line)
            args = record["args"]
            if args[:2] == ["issue", "create"]:
                body = args[args.index("--body") + 1] if "--body" in args else record["body"]
                out.append((args, body))
        return out

    def check_body(self, body):
        for heading, text in SECTIONS:
            self.assertIn(heading, body)
            self.assertIn(text, body)
        self.assertNotIn("## Empty", body)
        for heading, home in (("Decisions", "AGENTS.md"), ("Product rules", "AGENTS.md"),
                              ("Stops", "AGENTS.md"), ("Surfaces", "Red-team surfaces")):
            # Each proposal must accompany its section, rather than appear once in an introduction.
            start = body.index(heading)
            text_at = body.index(dict(SECTIONS)[heading], start)
            end = min([body.find(other, text_at + len(dict(SECTIONS)[heading]))
                       for other, _ in SECTIONS if body.find(other, text_at + len(dict(SECTIONS)[heading])) >= 0]
                      or [len(body)])
            self.assertIn(home, body[start:end])
        self.assertRegex(body, r"(?is)Lessons.*(?:check|AGENTS\.md).*(?:drop|discard)")
        self.assertRegex(body, r"(?is)Deviations.*(?:drop|discard).*git")

    def test_setup_files_one_inbox_issue_keeps_the_file_and_logs_the_issue(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                self.project(reverse)
                plan = Path(self.work, "PLAN.md").read_bytes()
                agents = Path(self.work, "AGENTS.md").read_bytes()
                self.command()
                created = self.bodies()
                self.assertEqual(len(created), 1, "Setup must file the plan's contents once")
                args, body = created[0]
                self.assertEqual(args[args.index("--title") + 1], TITLE)
                self.assertIn("inbox", args[args.index("--label") + 1].split(","))
                self.check_body(body)
                self.assertEqual(Path(self.work, "PLAN.md").read_bytes(), plan)
                self.assertEqual(Path(self.work, "AGENTS.md").read_bytes(), agents)
                log = Path(self.work, ".loop/migrations.log")
                self.assertIn("42", log.read_text())
                before = log.read_bytes()
                self.command()
                self.assertEqual(len(self.bodies()), 1)
                self.assertEqual(log.read_bytes(), before)

    def test_dry_run_summarises_without_filing_or_changing_files(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                self.project(reverse)
                before = test_setup.SetupTest.snapshot(self, Path(self.work))
                origin = test_setup.SetupTest.snapshot(self, Path(self.origin))
                text = self.command(dry_run=True)
                self.assertEqual(test_setup.SetupTest.snapshot(self, Path(self.work)), before)
                self.assertEqual(test_setup.SetupTest.snapshot(self, Path(self.origin)), origin)
                self.assertEqual(self.bodies(), [])
                self.assertIn(TITLE, text)
                for heading, content in SECTIONS:
                    self.assertIn(heading, text)
                    self.assertNotIn(content, text)
                self.assertNotIn("## Empty", text)

    def test_dry_run_skips_a_missing_or_logged_plan(self):
        for logged in (False, True):
            with self.subTest(logged=logged):
                self.project()
                if logged:
                    self.command()
                else:
                    Path(self.work, "PLAN.md").unlink()
                before = test_setup.SetupTest.snapshot(self, Path(self.work))
                self.assertNotIn(TITLE, self.command(dry_run=True))
                self.assertEqual(test_setup.SetupTest.snapshot(self, Path(self.work)), before)
                self.assertEqual(len(self.bodies()), int(logged))

    def test_setup_accepts_red_team_surfaces_as_a_json_list(self):
        for surfaces in ([], ["import records", "export records"]):
            with self.subTest(surfaces=surfaces):
                self.project()
                Path(self.work, "loop.json").write_text(json.dumps({
                    "Test command": "true", "Red-team surfaces": surfaces}))
                self.command(dry_run=True)


class Decisions(test_loop.Base):
    def test_final_pull_request_uses_all_recorded_deviations_since_the_default_branch(self):
        self.work, _ = make_repo(self._tmp.name, {
            "loop.json": '{"Test command":"true","Idle hours":0}',
            "PLAN.md": "# Plan\n## Deviations\n- Obsolete plan decision.\n"})
        Path(self.work, "old.txt").write_text("already shipped")
        run_git(["add", "old.txt"], self.work)
        run_git(["commit", "-m", "Issue 10"], self.work)
        run_git(["push", "origin", "HEAD:main"], self.work)
        run_git(["checkout", "-b", "loop/main"], self.work)
        for number in (11, 12, 13):
            Path(self.work, "change.txt").write_text(str(number))
            run_git(["add", "change.txt"], self.work)
            run_git(["commit", "-m", "Issue %d" % number], self.work)
        Path(self.work, "PLAN.md").write_text("# Plan\n## Deviations\n- Obsolete plan decision.\n- Ignore this added plan line.\n")
        run_git(["add", "PLAN.md"], self.work)
        run_git(["commit", "-m", "Record old plan notes"], self.work)
        run_git(["push", "origin", "loop/main"], self.work)
        self.world([])
        long_item = "Retained the existing export format " + "and its ordering " * 15 + "for compatibility."
        for number, deviations in ((11, "- Kept the cache.\n- " + long_item),
                                    (12, "none"), (13, "Used the existing parser.")):
            note = "## Built\n\nFinished.\n\nDeviations: %s\n\nMerged as abc.\n" % deviations
            self.rules.insert(0, {"match": "issue view %d " % number,
                                  **test_loop.out({"title": "Piece", "body": "", "comments": [{"body": note}]})})
        with mock.patch.object(loop.merge, "run_tests", return_value=None), \
                mock.patch.object(loop.pass_, "run_pass", return_value=({}, "")), \
                mock.patch.object(loop, "summary", return_value=""):
            self.run_loop()
        bodies = [body for command, body in self.inputs if command.startswith("pr create")]
        self.assertEqual(len(bodies), 1)
        section = bodies[0].split("## Decisions to confirm\n", 1)[1].split("\n## ", 1)[0]
        for number, item in ((11, "Kept the cache."), (11, long_item), (13, "Used the existing parser.")):
            self.assertIn(item, section)
            self.assertRegex(section, r"(?:#|Issue )%d\b" % number)
        self.assertNotIn("none", section.lower())
        self.assertNotIn("Obsolete plan decision", section)
        self.assertNotIn("Ignore this added plan line", section)
        self.assertNotRegex(section, r"(?:#|Issue )10\b")


class Pass(FakeClaudeGh):
    repo = test_pass.PassTest.repo
    gh = test_pass.PassTest.gh
    run_pass = test_pass.PassTest.run_pass
    bodies = test_pass.PassTest.bodies

    def test_red_team_uses_the_settings_list_instead_of_the_old_plan(self):
        for surfaces in (("import records", "export records"), ("export records", "import records")):
            with self.subTest(surfaces=surfaces):
                self.repo(test_pass.plan(surfaces=("obsolete surface",)))
                self.settings["Red-team surfaces"] = list(surfaces)
                self.claude({"pass": [test_pass.NONE]})
                result, _ = self.run_pass()
                self.assertEqual(result["errors"], [])
                prompts = [c["prompt"] for c in self.claude_calls() if "\nSurface: " in c["prompt"]]
                self.assertEqual([re.search(r"\nSurface: (.*)", p)[1] for p in prompts], list(surfaces))

    def test_empty_settings_list_proposes_surfaces_in_an_inbox_issue(self):
        self.repo(test_pass.plan(surfaces=("obsolete surface",)))
        self.settings["Red-team surfaces"] = []
        seen = self.bodies()
        self.claude({"pass": [{"reply": "FINDINGS:\nnone\n\nSURFACES:\nimport records\nexport records"},
                              test_pass.NONE]})
        result, _ = self.run_pass()
        self.assertEqual(result["errors"], [])
        created = [(args, body) for args, body in seen if args[:2] == ["issue", "create"]]
        self.assertEqual(len(created), 1)
        args, body = created[0]
        self.assertEqual(args[args.index("--label") + 1], "inbox")
        for text in ("Red-team surfaces", "import records", "export records"):
            self.assertIn(text, body)
        self.assertNotIn("PLAN.md", body)
        self.assertFalse(any("\nSurface: " in c["prompt"] for c in self.claude_calls()))

    def test_each_lesson_is_an_inbox_issue_with_its_preventive_check_or_instruction(self):
        self.repo(test_pass.plan(surfaces=()))
        self.settings["Red-team surfaces"] = []
        before = subprocess.run(["git", "rev-parse", "origin/loop/main"], cwd=self.work,
                                capture_output=True, text=True, check=True).stdout
        seen = self.bodies()
        lessons = (("Reject blank identifiers", "check tests/test_import.py rejects an empty identifier"),
                   ("Retain export ordering", "AGENTS.md line: preserve record order when exporting"))
        self.claude({"pass": [test_pass.NONE, test_pass.NONE,
                              {"reply": "LESSONS:\n" + "\n".join("%s | %s" % l for l in lessons)
                               + "\n\nGUARDRAILS:\nnone"}, test_pass.NONE]})
        result, _ = self.run_pass()
        self.assertEqual(result["errors"], [])
        created = [(args, body) for args, body in seen if args[:2] == ["issue", "create"]]
        self.assertEqual(len(created), len(lessons), "Each lesson needs its own inbox issue")
        for title, prevention in lessons:
            matches = [(args, body) for args, body in created if title in args[args.index("--title") + 1] or title in body]
            self.assertEqual(len(matches), 1)
            args, body = matches[0]
            self.assertIn(prevention, body)
            self.assertEqual(args[args.index("--label") + 1], "inbox")
            self.assertNotIn("PLAN.md", body)
        after = subprocess.run(["git", "rev-parse", "origin/loop/main"], cwd=self.work,
                               capture_output=True, text=True, check=True).stdout
        self.assertEqual(after, before)
        self.assertEqual(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                                       cwd=self.work, capture_output=True, text=True, check=True).stdout, "")


if __name__ == "__main__":
    unittest.main()
