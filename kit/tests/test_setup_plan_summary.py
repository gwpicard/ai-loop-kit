"""Setup previews the plan migration without printing its contents."""
from pathlib import Path
import re

from kit.tests import test_plan_retirement as migration
from kit.tests.helpers import FakeGh


class PlanSummary(FakeGh):
    project = migration.Migration.project
    command = migration.Migration.command
    bodies = migration.Migration.bodies

    def test_dry_run_summarises_each_non_empty_section(self):
        introduction = "Keep the original migration context.\nRetain the rollout notes too."
        homes = {
            "Introduction": ("README.md", "docs/"),
            "Decisions": ("AGENTS.md",),
            "Product rules": ("AGENTS.md",),
            "Stops": ("AGENTS.md",),
            "Surfaces": ("Red-team surfaces", "loop.json"),
            "Lessons": ("check", "AGENTS.md"),
            "Deviations": ("drop", "git"),
            "Try it": ("README.md",),
            "Project notes": ("README.md", "docs/"),
        }
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                self.project(reverse)
                plan = migration.old_plan(reverse).replace(
                    "# Plan\n", "# Plan\n\n" + introduction + "\n", 1)
                Path(self.work, "PLAN.md").write_text(plan)
                snapshot = migration.test_setup.SetupTest.snapshot
                before = snapshot(self, Path(self.work))
                origin = snapshot(self, Path(self.origin))

                text = self.command(dry_run=True)

                self.assertEqual(snapshot(self, Path(self.work)), before)
                self.assertEqual(snapshot(self, Path(self.origin)), origin)
                self.assertEqual(self.bodies(), [])
                self.assertIn(migration.TITLE, text)
                self.assertNotIn("Empty", text)
                for heading, content in (("Introduction", introduction),) + migration.SECTIONS:
                    for line in content.splitlines():
                        self.assertNotIn(line, text, "Dry runs must omit section text")
                    lines = [line for line in text.splitlines()
                             if re.search(r"\b" + re.escape(heading) + r"\b", line)]
                    self.assertEqual(len(lines), 1, "Each section needs one summary line: " + heading)
                    self.assertRegex(lines[0], r"\b%d\s+lines?\b" % len(content.splitlines()))
                    for home in homes[heading]:
                        self.assertIn(home.lower(), lines[0].lower())
