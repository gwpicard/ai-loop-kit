"""Setup reports the standing-instruction word budget through its command."""
import json
from pathlib import Path
import re
import subprocess
import sys

from kit.tests.helpers import FakeGh, make_repo
from kit.tests.test_setup import rule
import setup


class StandingInstructionBudgetTest(FakeGh):
    def project(self, agents, claude):
        work, _ = make_repo(self.tmp, {
            "loop.json": '{"Test command": "true"}\n',
            "AGENTS.md": agents,
            "CLAUDE.md": claude,
            "docs/AGENTS.md": "nested " * 2000,
        })
        self.scenario([
            rule("label list", json.dumps([{"name": n} for n in setup.LABELS])),
            rule("issue list", '[{"number":7,"title":"Factory"}]'),
        ])
        return Path(work)

    def run_setup(self, work, dry_run=False):
        args = [sys.executable, setup.__file__]
        if dry_run:
            args.append("--dry-run")
        result = subprocess.run(args, cwd=work, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def assert_warning(self, text, agents, claude):
        self.assertRegex(text.lower(), r"warn(?:ing)?\b", text)
        self.assertRegex(text, r"\b1,?500\b", text)
        for name, count in (("AGENTS.md", agents), ("CLAUDE.md", claude)):
            number = r"\b" + format(count, ",").replace(",", ",?") + r"\b"
            self.assertRegex(text, r"(?s)(?:" + re.escape(name) + r".*?" + number
                             + "|" + number + r".*?" + re.escape(name) + ")", text)

    def instruction_bytes(self, work):
        return {name: (work / name).read_bytes() for name in ("AGENTS.md", "CLAUDE.md")}

    def test_warns_on_combined_total_with_varied_whitespace_and_import_position(self):
        examples = (
            ("guide " * 1000, "@AGENTS.md\n" + "rule " * 501, 1000, 501),
            ("guide\t" * 602, "rule\r\n" * 899 + " \t@AGENTS.md \t\r\n", 602, 899),
        )
        for agents, claude, agents_count, claude_count in examples:
            with self.subTest(agents=agents_count, claude=claude_count):
                work = self.project(agents, claude)
                text = self.run_setup(work)
                self.assert_warning(text, agents_count, claude_count)

    def test_dry_run_and_setup_give_the_same_warning_and_preserve_both_files(self):
        work = self.project("guide\t" * 1001, "rule\n" * 503 + "@AGENTS.md\n")
        before = self.instruction_bytes(work)
        preview = self.run_setup(work, dry_run=True)
        self.assertEqual(self.instruction_bytes(work), before)
        applied = self.run_setup(work)
        self.assertEqual(self.instruction_bytes(work), before)
        self.assert_warning(preview, 1001, 503)
        self.assert_warning(applied, 1001, 503)
        relevant = lambda text: [line for line in text.splitlines() if re.search(
            r"warn|budget|AGENTS\.md|CLAUDE\.md|\b1,?500\b", line, re.I)]
        self.assertEqual(relevant(preview), relevant(applied))

    def test_only_a_standalone_import_is_excluded_at_the_budget_boundary(self):
        for dry_run in (False, True):
            for count in (499, 500):
                with self.subTest(dry_run=dry_run, claude=count):
                    work = self.project("guide " * 1000, "rule " * count + "\n@AGENTS.md\n")
                    before = self.instruction_bytes(work)
                    text = self.run_setup(work, dry_run=dry_run)
                    self.assertNotRegex(text.lower(), r"warn|budget|\b1,?500\b|agents\.md|claude\.md")
                    self.assertEqual(self.instruction_bytes(work), before)
        for claude in ("@AGENTS.md " + "rule " * 500, "rule " * 500 + "@AGENTS.md"):
            with self.subTest(inline=claude.startswith("@")):
                work = self.project("guide " * 1000, claude)
                self.assert_warning(self.run_setup(work), 1000, 501)
