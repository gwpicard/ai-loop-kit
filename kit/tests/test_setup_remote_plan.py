"""Setup preserves the plan held on the project's remote loop branch."""
import json
from pathlib import Path

from kit.tests import test_plan_retirement as migration
from kit.tests.helpers import FakeGh, run_git


class RemotePlan(FakeGh):
    project = migration.Migration.project
    command = migration.Migration.command
    bodies = migration.Migration.bodies

    def remote_plan(self, reverse=False, local_plan=True):
        self.project(reverse)
        branch = "loop/release" if reverse else "loop/main"
        Path(self.work, "loop.json").write_text(json.dumps({
            "Test command": "true", "Loop branch": branch}) + "\n")
        if not local_plan:
            Path(self.work, "PLAN.md").unlink()
            run_git(["add", "PLAN.md"], self.work)
            run_git(["commit", "-m", "Retire the checkout plan"], self.work)
        publisher = str(Path(self.work).parent / "publisher")
        run_git(["clone", self.origin, publisher], self.tmp)
        run_git(["checkout", "-b", branch], publisher)
        sections = (
            ("Decisions", "Keep the newest export decision from the loop."),
            ("Lessons", "Reject repeated record identifiers before export.\n"
                        "Retain the original record order."),
            ("Deviations", "Kept the existing export command.\n"
                           "Used the checked-in example records."),
            ("Loop notes", "Keep this section found only on the loop branch."),
        )
        if reverse:
            sections = tuple(reversed(sections))
        plan = "# Plan\n\n" + "\n".join(
            "## %s\n\n%s\n" % section for section in sections)
        Path(publisher, "PLAN.md").write_text(plan)
        run_git(["add", "PLAN.md"], publisher)
        run_git(["-c", "user.name=Test", "-c", "user.email=t@example.com",
                 "commit", "-m", "Record the loop plan"], publisher)
        run_git(["push", "origin", branch], publisher)
        # The checkout has not fetched the new branch. Setup must read origin.
        return branch, sections

    def plan_issue(self):
        created = [(args, body) for args, body in self.bodies()
                   if args[args.index("--title") + 1] == migration.TITLE]
        self.assertEqual(len(created), 1, "Setup must file one plan inbox issue")
        args, body = created[0]
        self.assertIn("inbox", args[args.index("--label") + 1].split(","))
        return body

    def test_inbox_uses_loop_sections_instead_of_the_checkout_plan(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                _, sections = self.remote_plan(reverse)
                before = Path(self.work, "PLAN.md").read_bytes()

                self.command()

                body = self.plan_issue()
                for heading, content in sections:
                    self.assertIn("## " + heading, body)
                    self.assertIn(content, body,
                                  "The inbox must preserve the loop branch's newest entries")
                self.assertNotIn("Keep exports local.", body)
                self.assertEqual(Path(self.work, "PLAN.md").read_bytes(), before)

    def test_preview_and_real_run_identify_the_plan_source_branch(self):
        for reverse in (False, True):
            for dry_run in (True, False):
                with self.subTest(reverse=reverse, dry_run=dry_run):
                    branch, _ = self.remote_plan(reverse)

                    text = self.command(dry_run=dry_run)

                    lines = [line for line in text.splitlines()
                             if "PLAN.md" in line and branch in line]
                    self.assertTrue(lines, "Setup must name PLAN.md and its source "
                                    "branch %s on the same line:\n%s" % (branch, text))
                    if dry_run:
                        self.assertEqual(self.bodies(), [])

    def test_inbox_is_filed_when_only_the_loop_branch_has_a_plan(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                _, sections = self.remote_plan(reverse, local_plan=False)

                self.command()

                body = self.plan_issue()
                for heading, content in sections:
                    self.assertIn("## " + heading, body)
                    self.assertIn(content, body)
                self.assertFalse(Path(self.work, "PLAN.md").exists(),
                                 "Reading the remote plan must not recreate the checkout file")
