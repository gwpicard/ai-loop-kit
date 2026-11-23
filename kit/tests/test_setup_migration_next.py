"""Migration guidance reaches the person before the loop restarts."""
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

from kit.tests.helpers import FakeGh, make_repo, run_git
from kit.tests.test_setup import rule
import setup


class MigrationNextTest(FakeGh):
    def project(self, reverse=False, dirty=False):
        settings = ["Test command: true", "Loop branch: loop/restart",
                    "Builder model: sonnet", "Reviewer model: opus", "Defect rounds: 2"]
        agents = ["Read PLAN.md before building.", "- Keep decisions in `PLAN.md`."]
        claude = ["@AGENTS.md", "Consult PLAN.md for the rollout.",
                  "  Update `PLAN.md` after each piece."]
        if reverse:
            settings.reverse()
            agents.reverse()
            claude.reverse()
        standing = "# Project\n" + "\n".join(agents) + "\n"
        section = "## Loop\n" + "\n".join(settings) + "\n"
        original = standing + section if reverse else section + standing
        work, _ = make_repo(self.tmp, {
            "AGENTS.md": original,
            "CLAUDE.md": "\n".join(claude) + "\n",
            "PLAN.md": "# Plan\n\n## Decisions\nKeep exports local.\n",
            ".gitignore": "cache/\n",
        })
        work = Path(work)
        if dirty:
            # The migration must notice edits before it changes AGENTS.md itself.
            (work / "AGENTS.md").write_text(original.replace("Test command: true",
                                                            "Test command: echo migrated"))
            if reverse:
                run_git(["add", "AGENTS.md"], work)
        self.scenario([
            rule("label list", json.dumps([{"name": name} for name in setup.LABELS])),
            rule("issue list", '[{"number":7,"title":"Factory"}]'),
            rule("issue create", "https://github.com/o/r/issues/73\n"),
        ])
        references = {"AGENTS.md": agents,
                      "CLAUDE.md": [line for line in claude if "PLAN.md" in line]}
        return work, references

    def run_setup(self, work):
        result = subprocess.run([sys.executable, setup.__file__], cwd=work,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((work / "loop.json").is_file(), "Exercise an applied migration")
        self.assertNotIn("## Loop", (work / "AGENTS.md").read_text())
        return result.stdout

    def test_next_steps_name_the_inbox_and_order_the_remaining_work(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                work, _ = self.project(reverse)
                output = self.run_setup(work)
                lines = [line for line in output.splitlines() if line.startswith("next:")]
                patterns = (
                    r"(?i)(?:place|home|move|distribut).*PLAN\.md",
                    r"(?i)(?=.*loop\.json)(?=.*AGENTS\.md)(?=.*\.gitignore)"
                    r"(?=.*pull request).*commit",
                    r"(?i)(?:update|pull).*checkout|git pull",
                    r"(?i)merge.*\bmain\b.*loop/restart",
                )
                positions = []
                for pattern in patterns:
                    matches = [i for i, line in enumerate(lines) if re.search(pattern, line)]
                    self.assertTrue(matches, "Missing next step: " + pattern + "\n" + output)
                    positions.append(matches[0])
                self.assertTrue(all(a < b for a, b in zip(positions, positions[1:])), lines)
                self.assertRegex(lines[positions[0]], r"\b73\b",
                                 "Name the inbox issue created for this plan")
                self.assertRegex(lines[positions[2]].lower(), r"merg",
                                 "Update the checkout after the pull request merges")

    def test_each_standing_instruction_that_names_the_plan_is_quoted(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                work, references = self.project(reverse)
                output = self.run_setup(work)
                lines = [line for line in output.splitlines() if line.startswith("next:")]
                for name, instructions in references.items():
                    for instruction in instructions:
                        with self.subTest(file=name, instruction=instruction):
                            quoted = [line for line in lines if name in line and instruction in line]
                            self.assertEqual(len(quoted), 1,
                                             "Quote each original line in its own next step:\n" + output)
                self.assertEqual(len({line for line in lines
                                      if any(instruction in line
                                             for instructions in references.values()
                                             for instruction in instructions)}), 4)

    def test_warns_about_uncommitted_input_and_names_every_dropped_setting(self):
        for reverse in (False, True):
            with self.subTest(staged=reverse):
                work, _ = self.project(reverse, dirty=True)
                output = self.run_setup(work)
                self.assertEqual(json.loads((work / "loop.json").read_text())["Test command"],
                                 "echo migrated", "Migrate the person's uncommitted settings")
                with self.subTest(notice="uncommitted AGENTS.md"):
                    warnings = [line for line in output.splitlines()
                                if re.search(r"warn", line, re.I)]
                    self.assertTrue(any("AGENTS.md" in line and re.search(
                        r"uncommitted|local (?:changes|edits)|dirty", line, re.I)
                                        for line in warnings), output)
                for setting in ("Builder model", "Reviewer model", "Defect rounds"):
                    with self.subTest(dropped=setting):
                        notices = [line for line in output.splitlines()
                                   if setting in line and re.search(
                                       r"drop|remov|ignor|replac|convert|migrat", line, re.I)]
                        self.assertTrue(notices, "Name the dropped setting: " + setting + "\n" + output)


class MigrationSkillTest(unittest.TestCase):
    def test_skill_relays_next_lines_before_starting_the_loop(self):
        skill = Path(setup.__file__).resolve().parents[1] / "skills/setup/SKILL.md"
        text = " ".join(skill.read_text().split())
        with self.subTest(requirement="relay"):
            self.assertRegex(text.lower(),
                             r"(?:report|relay|show|present|repeat)[^.]*next:",
                             "Explicitly relay setup's next: lines to the person")
        with self.subTest(requirement="start condition"):
            self.assertRegex(text.lower(),
                             r"(?:do not|never|must not)[^.]*start[^.]*loop[^.]*until[^.]*"
                             r"(?:person|user)[^.]*(?:seen|shown|read)|"
                             r"(?:before|until)[^.]*(?:start|restart)[^.]*loop[^.]*"
                             r"(?:person|user)[^.]*(?:seen|shown|show|read)|"
                             r"(?:show|present|relay)[^.]*next:[^.]*"
                             r"(?:person|user)[^.]*before[^.]*(?:start|restart)[^.]*loop",
                             "Make seeing the next steps a condition of starting the loop")
