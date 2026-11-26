"""Loop commands and sessions receive a visible cache beside their project."""
import json
import os
from pathlib import Path
import re
import shlex
import sys
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git, write_exe
from kit.tests import test_build_cache, test_flow
import flow
import loop
import merge
import setup


ROOT = Path(__file__).resolve().parents[2]


class VisibleBuildCacheTest(FakeClaudeGh):
    def setUp(self):
        super().setUp()
        os.environ.pop("LOOP_CACHE_DIR", None)
        write_exe(str(Path(self.tmp, "bin/ps")), "#!PYTHON\n")
        write_exe(str(Path(self.tmp, "bin/taskpolicy")),
                  "#!PYTHON\nimport os, sys\nos.execvp(sys.argv[2], sys.argv[2:])\n")

    def project(self, layout, name="work"):
        parent = Path(self.tmp, layout)
        parent.mkdir(parents=True)
        probe = parent / "probe.py"
        probe.write_text(test_build_cache.PROBE)
        command = shlex.join([sys.executable, str(probe)])
        work, _ = make_repo(str(parent), {"loop.json": json.dumps({
            "Test command": command + " test",
            "Test files command": command + " files {files}",
            "Prepare command": command + " prepare",
            "Check command": command + " check",
            "Loop branch": "loop/main"})})
        if name != "work":
            renamed = parent / name
            Path(work).rename(renamed)
            work = str(renamed)
        run_git(["push", "origin", "main:loop/main"], work)
        self.scenario([
            {"match": "issue view", "responses": [{"stdout": json.dumps({
                "title": "Add the application", "body": "", "comments": []})}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "issue list", "responses": [{"stdout": "[]"}]},
            {"match": "", "responses": [{}]}])
        return Path(work)

    def run_command(self, project, issue):
        self.claude({"test-writer": [test_flow.WRITER],
                     "builder": [{"files": {"app.py": "application = True\n"}}],
                     "reviewer": [test_flow.APPROVE]})
        journal = project.parent / ("commands-%s.jsonl" % issue)
        results = []

        def build_once(work, settings, state):
            # Keep the command dispatcher and build real. Only the scheduler
            # runs synchronously, so this test needs no background worker.
            results.append(flow.build(issue, work))
            Path(work, ".loop/stop").touch()

        previous = os.getcwd()
        try:
            os.chdir(project)
            with mock.patch.dict(os.environ, CACHE_PROJECT=str(project),
                                 CACHE_ISSUE=str(issue), CACHE_JOURNAL=str(journal)), \
                    mock.patch.object(loop.sys, "platform", "linux"), \
                    mock.patch.object(setup, "missing", return_value=None), \
                    mock.patch.object(loop, "snapshot"), \
                    mock.patch.object(loop, "write_board"), \
                    mock.patch.object(loop, "start_builds", side_effect=build_once), \
                    mock.patch.object(loop, "wait_stop"), \
                    mock.patch.object(merge, "find_pr", return_value={
                        "number": 9, "state": "MERGED", "mergeCommit": {"oid": "abc"}}):
                code = loop.main(["run"])
        finally:
            os.chdir(previous)
        self.assertEqual(code, 0)
        self.assertEqual(len(results), 1, "loop run must reach the build")
        self.assertEqual(results[0].status, "merged", results[0].reason)
        self.assertTrue(journal.is_file(), "the configured commands must run")
        rows = [json.loads(line) for line in journal.read_text().splitlines()]
        calls = self.claude_calls()
        self.assertEqual({row["kind"] for row in rows}, {"prepare", "files", "test", "check"})
        self.assertEqual([call["role"] for call in calls],
                         ["test-writer", "builder", "reviewer"])
        return rows, calls

    def test_loop_run_passes_an_existing_visible_sibling_cache_to_commands_and_sessions(self):
        for layout, name in (("plain", "work"), ("nested projects/project group", "notes app")):
            with self.subTest(layout=layout, project=name):
                project = self.project(layout, name)
                rows, calls = self.run_command(project, 7)
                values = [row["cache"] for row in rows]
                values += [call["env"].get("LOOP_CACHE_DIR", "") for call in calls]
                self.assertNotIn("", values, "every command and session needs LOOP_CACHE_DIR")
                self.assertEqual(len(set(values)), 1, "the build must keep the same cache")
                self.assertTrue(all(row["exists"] for row in rows))
                cache = Path(values[0])
                self.assertTrue(cache.is_absolute())
                self.assertTrue(cache.is_dir(), "the cache must survive worktree cleanup")
                self.assertEqual(cache.stat().st_dev, project.stat().st_dev)
                self.assertFalse(cache.is_relative_to(project))
                self.assertIn(project.name, cache.relative_to(project.parent).parts)
                # The enclosing runner may have a hidden parent. Check both
                # spellings of every component the kit adds beside the project.
                for path, parent in ((cache, project.parent),
                                     (cache.resolve(), project.parent.resolve())):
                    parts = path.relative_to(parent).parts
                    self.assertFalse(any(part.startswith(".") for part in parts),
                                     "LOOP_CACHE_DIR contains a hidden component: %s" % path)

    def test_old_cache_is_untouched_and_loop_out_reports_manual_removal_once(self):
        project = self.project("old cache project")
        old = project.parent / ".loop-cache" / project.name
        (old / "1/nested").mkdir(parents=True)
        (old / "1/compiler-output").write_bytes(b"previous compiler output\n")
        (old / "1/nested/object").write_bytes(b"\x00\x01old object\xff")
        (old / "1.lock").touch()

        def snapshot():
            return {str(path.relative_to(old)): (
                path.stat().st_ino, path.stat().st_mode, path.stat().st_mtime_ns,
                path.read_bytes() if path.is_file() else None)
                for path in [old, *old.rglob("*")]}

        before = snapshot()
        first, _ = self.run_command(project, 7)
        after_first = snapshot() if old.exists() else {}
        second, _ = self.run_command(project, 8)
        log = project / ".loop/loop.out"
        lines = log.read_text().splitlines() if log.exists() else []
        notices = [line for line in lines if str(old) in line
                   and re.search(r"remov|delet", line, re.I)]
        with self.subTest(contract="one manual removal notice across restarts"):
            self.assertEqual(len(notices), 1, lines)
            self.assertRegex(notices[0], r"(?i)by hand|manually|manual removal")
        with self.subTest(contract="old cache remains untouched"):
            self.assertEqual(after_first, before)
            self.assertEqual(snapshot() if old.exists() else {}, before)
        with self.subTest(contract="start and reuse a separate cache"):
            cache = Path(first[0]["cache"])
            self.assertFalse(cache.resolve().is_relative_to(old.resolve()))
            self.assertFalse(first[0]["had_output"], "do not copy or reuse the old cache")
            self.assertEqual(second[0]["cache"], str(cache))
            self.assertTrue(second[0]["had_output"], "reuse output from the new cache")

    def test_readme_names_a_visible_cache_location_beside_the_project(self):
        readme = (ROOT / "kit/README.md").read_text()
        passage = next((paragraph for paragraph in readme.split("\n\n")
                        if "LOOP_CACHE_DIR" in paragraph and "<project>" in paragraph), "")
        location = re.search(r"<parent>/([^`\s]*<project>)/?", passage)
        self.assertIsNotNone(location, "name the per-project cache location in the reference")
        self.assertFalse(any(part.startswith(".") for part in location[1].split("/")),
                         "the documented cache location must have no hidden component")
