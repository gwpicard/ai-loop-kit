import contextlib
import io
import json
import subprocess
import sys
from unittest import mock
import pathlib

from kit.tests.helpers import FakeGh, make_repo
import setup
import common


def rule(match, stdout="", code=0, stderr=""):
    return {"match": match, "responses": [{"stdout": stdout, "stderr": stderr, "code": code}]}


def run(project, dry_run=False):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = setup.setup(project, dry_run=True) if dry_run else setup.setup(project)
    return code, buf.getvalue()


class SetupTest(FakeGh):
    def repo(self, agents="## Loop\nTest command: true\n"):
        files = {"AGENTS.md": agents} if agents else {"README.md": "x\n"}
        self.work, self.origin = make_repo(self.tmp, files)

    def fresh(self):
        self.scenario([rule("label list", "[]"), rule("label create"), rule("issue list", "[]"),
                       rule("issue create", "https://github.com/o/r/issues/7\n"),
                       rule("issue pin")])

    def done(self, test="true"):
        self.scenario([rule("label list", '[{"name":"%s"}]' % '"},{"name":"'.join(setup.LABELS)),
                       rule("issue list", '[{"number":7,"title":"Factory"}]')])

    def writes(self):
        return [c for c in self.calls() if c[:2] in (["label", "create"], ["issue", "create"],
                                                      ["issue", "pin"])]

    def test_first_run_creates_everything(self):
        self.repo()
        self.fresh()
        code, text = run(self.work)
        self.assertEqual(code, 0, text)
        self.assertEqual(len([c for c in self.writes() if c[:2] == ["label", "create"]]), 5)
        self.assertIn(["issue", "pin", "7"], self.calls())
        self.assertIn(".loop/", pathlib.Path(self.work, ".gitignore").read_text())
        self.assertIn("preflight: the Test command passes", text)
        self.assertIn("protect main", text)
        self.assertIn("refs/heads/loop/main", __import__("subprocess").run(
            ["git", "ls-remote", self.origin], capture_output=True, text=True).stdout)

    def test_second_run_changes_nothing(self):
        self.repo()
        self.fresh()
        run(self.work)
        self.done()
        before = pathlib.Path(self.work, ".gitignore").read_text()
        code, text = run(self.work)
        self.assertEqual(code, 0, text)
        self.assertEqual(self.writes(), [])
        self.assertIn("summary: 0 change(s)", text)
        self.assertEqual(pathlib.Path(self.work, ".gitignore").read_text(), before)

    def test_optional_commands_are_reported_not_required(self):
        self.repo("## Loop\nTest command: true\nCheck command: true\nSmoke command: echo ok\n")
        self.fresh()
        code, text = run(self.work)
        self.assertEqual(code, 0, text)
        self.assertIn("optional: Check command: true; Smoke command: echo ok; Session minutes: 45; Parallel: 1", text)

    def test_no_optional_commands_is_said_plainly(self):
        self.repo()
        self.fresh()
        self.assertIn("no Check or Smoke command set", run(self.work)[1])

    def test_missing_section_is_refused(self):
        self.repo(agents="# Project\n")
        self.fresh()
        code, text = run(self.work)
        self.assertEqual(code, 1)
        self.assertIn("refused:", text)
        self.assertIn("Test command:", text)
        self.assertEqual(self.calls(), [])

    def test_failing_preflight_is_reported(self):
        self.repo("## Loop\nTest command: false\n")
        self.fresh()
        code, text = run(self.work)
        self.assertEqual(code, 1)
        self.assertIn("preflight: the Test command failed", text)
        self.assertIn("preflight failed", text)

    def old_project(self):
        self.repo("# Project\nDefect rounds: outside\n## Loop\nTest command: true\nDefect rounds: 2\n## Other\nDefect rounds: keep\n")
        pathlib.Path(self.work, "PLAN.md").write_text("# Plan\n## Standing approvals\nPass defects are approved.\n")

    def snapshot(self, folder):
        return {str(p.relative_to(folder)): p.read_bytes() for p in pathlib.Path(folder).rglob("*") if p.is_file()}

    def test_upgrade_removes_only_the_loop_setting_and_keeps_the_plan(self):
        self.old_project()
        self.fresh()
        plan = pathlib.Path(self.work, "PLAN.md").read_bytes()
        code, text = run(self.work)
        self.assertEqual(code, 0, text)
        agents = pathlib.Path(self.work, "AGENTS.md").read_text()
        self.assertNotIn("Defect rounds: 2", agents)
        self.assertIn("Defect rounds: outside", agents)
        self.assertIn("Defect rounds: keep", agents)
        self.assertEqual(pathlib.Path(self.work, "PLAN.md").read_bytes(), plan)
        self.assertIn("Find a home for the contents of PLAN.md", text)
        self.assertIn("Pass defects are approved.", text)
        log = pathlib.Path(self.work, ".loop", "migrations.log")
        records = [json.loads(line) for line in log.read_text().splitlines()]
        removed = next(r for r in records if "removed Defect rounds" in r["change"])
        self.assertIn("Defect rounds: 2\n", removed["undo"])
        self.assertIn("AGENTS.md", removed["undo"])
        for record in records:
            self.assertEqual(record["kit"], common.kit_version())
            self.assertRegex(record["time"], r"^\d{4}-\d{2}-\d{2}T")
            self.assertTrue(record["undo"])
        self.done()
        before = log.read_bytes()
        agents = pathlib.Path(self.work, "AGENTS.md").read_bytes()
        code, text = run(self.work)
        self.assertEqual(code, 0, text)
        self.assertIn("summary: 0 change(s)", text)
        self.assertEqual(log.read_bytes(), before)
        self.assertEqual(pathlib.Path(self.work, "AGENTS.md").read_bytes(), agents)

    def test_dry_run_previews_all_changes_without_writes_or_preflight(self):
        self.old_project()
        self.fresh()
        for name in (".loop/logs/old.log", ".loop/v1/heartbeat", ".loop/pass.json", ".loop/loop.out.lite",
                     ".loop/events.jsonl", ".loop/summary.json", ".loop/pass/review.md",
                     ".loop/pauses", ".loop/passed-session", ".loop/stop-session",
                     ".loop/session-active", ".loop/history-7.md"):
            path = pathlib.Path(self.work, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name)
        before, origin = self.snapshot(self.work), self.snapshot(self.origin)
        result = subprocess.run([sys.executable, setup.__file__, "--dry-run", self.work],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(self.work), before)
        self.assertEqual(self.snapshot(self.origin), origin)
        self.assertEqual(self.writes(), [])
        self.assertIn("preflight skipped", result.stdout)
        code, text = run(self.work)
        self.assertEqual(code, 0, text)
        preview = [line.removeprefix("would change: ") for line in result.stdout.splitlines() if line.startswith("would change: ")]
        applied = [line.removeprefix("change: ") for line in text.splitlines() if line.startswith("change: ")]
        self.assertEqual(preview, applied)
        self.assertTrue(any("Factory" in line for line in preview))
        self.assertTrue(any("loop branch" in line for line in preview))
        records = [json.loads(line) for line in pathlib.Path(self.work, ".loop", "migrations.log").read_text().splitlines()]
        self.assertEqual([r["change"] for r in records], applied)
        self.assertIn("heartbeat", pathlib.Path(self.work, ".loop/v1/heartbeat").read_text())

    def test_dry_run_does_not_run_preflight_in_process(self):
        self.repo()
        self.fresh()
        with mock.patch.object(setup.merge, "run_tests", side_effect=AssertionError("preflight ran")):
            self.assertEqual(run(self.work, dry_run=True)[0], 0)
        self.assertFalse(pathlib.Path(self.work, ".loop").exists())

    def test_setup_refuses_each_kit_1_marker_before_migrating_settings(self):
        self.old_project()
        for name in ("run.lock", "heartbeat", "dashboard.html", "dashboard.json", "preferences.json",
                     "summary.md", "why.md", "hypothesis", "outcome", "cache", "capture", "run-metrics"):
            with self.subTest(name=name):
                path = pathlib.Path(self.work, ".loop", name)
                path.parent.mkdir(exist_ok=True)
                path.write_text("legacy content\n")
                before = self.snapshot(self.work)
                result = subprocess.run([sys.executable, setup.__file__, self.work],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("install kit 2.2.0, run its setup, then update to this version", result.stdout)
                self.assertEqual(self.snapshot(self.work), before)
                path.unlink()
