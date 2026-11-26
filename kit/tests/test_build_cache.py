"""Project caches survive worktrees and stay exclusive to their running build."""
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git, write_exe
from kit.tests import test_flow
import common
import session


ROOT = Path(__file__).resolve().parents[2]
STOP = str(ROOT / "kit/hooks/stop.py")

# The configured commands record only the cache and the context needed to
# distinguish worktree, fails-first, targeted, revert and merge checks.
PROBE = r'''
import json
import os
from pathlib import Path
import sys
import time

kind, *files = sys.argv[1:]
cache = os.environ.get("LOOP_CACHE_DIR", "")
folder = Path(cache) if cache else None
exists = bool(folder and folder.is_dir())
marker = folder / "compiler-output" if exists else None
had_output = bool(marker and marker.exists())
if marker and kind in ("test", "files"):
    marker.write_text("keep compiler output\n")
step = Path(os.environ["CACHE_PROJECT"], ".loop/builds",
            os.environ.get("CACHE_ISSUE", "7") + ".step")
row = dict(kind=kind, files=files, cache=cache, exists=exists,
           had_output=had_output, cwd=str(Path.cwd()),
           step=step.read_text().strip() if step.exists() else "worktree")
with open(os.environ["CACHE_JOURNAL"], "a") as stream:
    stream.write(json.dumps(row) + "\n")
gate = os.environ.get("CACHE_COMMAND_GATE", "")
if gate and kind == os.environ.get("CACHE_GATE_KIND"):
    Path(gate + ".ready").touch()
    until = time.monotonic() + 180
    while not Path(gate).exists() and time.monotonic() < until:
        time.sleep(0.02)
    assert Path(gate).exists(), "test did not release the command"
if kind in ("test", "files"):
    assert not Path("tests/test_new.py").exists() or Path("app.py").exists(), "app is absent"
    assert not Path("tests/test_extra.py").exists() or Path("app.py").exists(), "app is absent"
    assert not Path("tests/test_candidate.py").exists(), "candidate rejects this input"
'''


# Run the real entry points in separate processes, as concurrent builds are.
# GitHub and agent replies are fixtures; commands and scratch trees are real.
DRIVER = r'''
import json
import os
from pathlib import Path
import sys
import time
from unittest import mock

sys.path[:0] = [sys.argv[1], str(Path(sys.argv[1], "kit/scripts"))]
import common
import flow
import loop
import merge
import pass_

mode, project, issue, output, gate = sys.argv[2:]
real_session = flow.session.run
def agent(*args, **kwargs):
    reply = real_session(*args, **kwargs)
    if gate and args[0] == "builder":
        Path(gate + ".ready").touch()
        until = time.monotonic() + 180
        while not Path(gate).exists() and time.monotonic() < until:
            time.sleep(0.02)
        assert Path(gate).exists(), "test did not release the build"
    return reply

with mock.patch.object(merge, "find_pr", return_value={
        "number": 9, "state": "MERGED", "mergeCommit": {"oid": "abc"}}), \
        mock.patch.object(flow.session, "run", side_effect=agent):
    if mode == "build":
        result = flow.build(int(issue), project)
        saved = dict(status=result.status, reason=result.reason)
    elif mode == "drain":
        state = loop.new_state()
        loop.drain(project, common.read_settings(project), state)
        saved = dict(status=state["last"])
    else:
        report, text = pass_.run_pass(project, common.read_settings(project), "origin/main")
        saved = dict(errors=report["errors"], smoke=report["smoke"],
                     confirmed=report["confirmed"], text=text)
Path(output).write_text(json.dumps(saved))
'''


class BuildCacheTest(FakeClaudeGh):
    def setUp(self):
        super().setUp()
        os.environ.pop("LOOP_CACHE_DIR", None)
        # Fake agents leave no background children to discover with ps.
        write_exe(str(Path(self.tmp, "bin/ps")), "#!PYTHON\n")
        # Priority is unrelated to the cache contract and unavailable in some sandboxes.
        write_exe(str(Path(self.tmp, "bin/taskpolicy")),
                  "#!PYTHON\nimport os, sys\nos.execvp(sys.argv[2], sys.argv[2:])\n")
        self.children = []
        self.addCleanup(self.stop_children)

    def fixture(self, layout="project", review_fix=False):
        parent = Path(self.tmp, layout)
        parent.mkdir(parents=True)
        probe = parent / "cache_probe.py"
        probe.write_text(PROBE)
        command = shlex.join([sys.executable, str(probe)])
        self.work, _ = make_repo(str(parent), {"loop.json": json.dumps({
            "Loop branch": "loop/main", "Max rounds": 2,
            "Test command": command + " test",
            "Test files command": command + " files {files}",
            "Prepare command": command + " prepare",
            "Check command": command + " check",
            "Smoke command": command + " smoke",
            "Red-team surfaces": ["the input command"]})})
        run_git(["push", "origin", "main:loop/main"], self.work)
        self.scenario([
            {"match": "issue view", "responses": [{"stdout": json.dumps({
                "title": "Add an app", "body": "Build the app.", "comments": []})}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "issue list", "responses": [{"stdout": "[]"}]},
            {"match": "", "responses": [{}]}])
        self.claude({
            "test-writer": [test_flow.WRITER],
            "builder": ([
                {"files": {"app.py": "1\n", "tests/test_extra.py": "extra\n"}, "stop_hook": STOP},
                {"files": {"app.py": "2\n"}}] if review_fix else [{"files": {"app.py": "1\n"}}]),
            "reviewer": [test_flow.CHANGES, test_flow.APPROVE] if review_fix else [test_flow.APPROVE],
            "pass": [
                {"reply": "FINDINGS:\nnone"}, {"reply": "FINDINGS:\nnone"},
                {"files": {".loop/pass/tests/test_candidate.py": "candidate\n"},
                 "reply": "FINDINGS:\nReject the input | The input is rejected | .loop/pass/tests/test_candidate.py"},
                {"reply": "CONFIRMED:\nReject the input\n\nHELD:\nnone\n\nREJECTED:\nnone"},
                {"reply": "LESSONS:\nnone\n\nGUARDRAILS:\nnone\n\nSIMPLIFY:\nnone"}]})

    def start(self, token, issue=7, mode="build", hold=False, hold_command=""):
        folder = Path(self.tmp, "run-" + token)
        folder.mkdir()
        # Each process has its own fake-tool state, while all use one project.
        for name, source in (("gh.json", self.scenario_path), ("claude.json", self.claude_path)):
            (folder / name).write_text(Path(source).read_text())
        gate = folder / "release"
        env = {k: v for k, v in os.environ.items() if k not in {
            "LOOP_CACHE_DIR", "LOOP_BUILD_SETTINGS", "LOOP_ROLE", "LOOP_PROJECT", "LOOP_AGENT"}}
        env.update(FAKE_GH_SCENARIO=str(folder / "gh.json"),
                   FAKE_CLAUDE_SCENARIO=str(folder / "claude.json"),
                   CACHE_PROJECT=self.work, CACHE_ISSUE=str(issue),
                   CACHE_JOURNAL=str(folder / "commands.jsonl"))
        if hold_command:
            env.update(CACHE_COMMAND_GATE=str(gate), CACHE_GATE_KIND=hold_command)
        log = (folder / "output.log").open("w")
        try:
            proc = subprocess.Popen(
                [sys.executable, "-c", DRIVER, str(ROOT), mode, self.work,
                 str(issue), str(folder / "result.json"), str(gate) if hold else ""],
                env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        finally:
            log.close()
        child = (proc, folder)
        self.children.append(child)
        return child

    def stop_children(self):
        for proc, folder in self.children:
            (folder / "release").touch()
        for proc, folder in self.children:
            try:
                proc.wait(timeout=120)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)

    def wait_ready(self, child):
        proc, folder = child
        until = time.monotonic() + 90
        while not (folder / "release.ready").exists() and proc.poll() is None and time.monotonic() < until:
            time.sleep(0.02)
        result = folder / "result.json"
        self.assertTrue((folder / "release.ready").exists(),
                        "the fixture did not reach its gate:\n" + (folder / "output.log").read_text()
                        + (result.read_text() if result.exists() else ""))

    def finish(self, child):
        proc, folder = child
        (folder / "release").touch()
        proc.wait(timeout=120)
        self.assertEqual(proc.returncode, 0, (folder / "output.log").read_text())
        saved = json.loads((folder / "result.json").read_text())
        if "reason" in saved:
            self.assertEqual(saved["status"], "merged", saved["reason"] + "\n" + (folder / "output.log").read_text())
        return saved

    def rows(self, child):
        path = child[1] / "commands.jsonl"
        self.assertTrue(path.exists(), "configured commands must run")
        return [json.loads(line) for line in path.read_text().splitlines()]

    def cache(self, rows):
        self.assertTrue(rows)
        paths = {row["cache"] for row in rows}
        self.assertNotIn("", paths, "every configured command must receive LOOP_CACHE_DIR")
        self.assertEqual(len(paths), 1, "one operation must keep the same cache across its trees")
        self.assertTrue(all(row["exists"] for row in rows), "create the cache before running commands")
        path = Path(next(iter(paths))).resolve()
        parent = Path(self.work).parent / ".loop-cache" / Path(self.work).name
        self.assertTrue(path.is_relative_to(parent.resolve()), (path, parent))
        self.assertNotEqual(path, parent.resolve(), "each build needs a folder within the project cache")
        return path

    def test_build_commands_share_one_cache_across_worktree_and_scratch_trees(self):
        for index, layout in enumerate(("project", "nested projects/project group")):
            with self.subTest(layout=layout):
                self.fixture(layout, review_fix=True)
                child = self.start("layout-%s" % index)
                self.assertEqual(self.finish(child)["status"], "merged")
                rows = self.rows(child)
                worktree = Path(self.work).parent / ".loop-worktrees" / (Path(self.work).name + "-7")
                local = [r for r in rows if Path(r["cwd"]).resolve() == worktree.resolve()]
                self.assertEqual({r["kind"] for r in local}, {"prepare", "files", "check"})
                for step, kinds in (("fails-first", {"prepare", "files"}),
                                    ("tests", {"prepare", "files", "check"}),
                                    ("merge", {"prepare", "test", "check"})):
                    selected = [r for r in rows if r["step"].startswith(step) and r not in local]
                    self.assertTrue(kinds <= {r["kind"] for r in selected}, (step, rows))
                reverted = [r for r in rows if r["files"] == ["tests/test_extra.py"]]
                self.assertTrue(reverted, "the builder's extra test must exercise the revert check")
                self.assertTrue(all(Path(r["cwd"]).resolve() != worktree.resolve() for r in reverted))
                self.cache(rows)
                calls = [json.loads(line) for line in (child[1] / "claude.json.calls").read_text().splitlines()]
                for call in calls:
                    self.assertEqual(call["env"].get("LOOP_CACHE_DIR"), rows[0]["cache"])

    def test_cache_output_survives_cleanup_and_is_reused_by_the_next_build(self):
        self.fixture()
        first = self.start("first")
        self.assertEqual(self.finish(first)["status"], "merged")
        first_rows = self.rows(first)
        for row in first_rows:
            self.assertFalse(Path(row["cwd"]).exists(), "build and scratch worktrees must be removed")
        second = self.start("second", issue=8)
        self.assertEqual(self.finish(second)["status"], "merged")
        second_rows = self.rows(second)
        cache = self.cache(first_rows)
        self.assertEqual((cache / "compiler-output").read_text(), "keep compiler output\n")
        self.assertEqual(self.cache(second_rows), cache)
        self.assertTrue(second_rows[0]["had_output"], "the next build must see the previous compiler output")

    def test_concurrent_builds_keep_distinct_caches_and_reuse_an_exited_holders_folder(self):
        self.fixture()
        first = self.start("holder", hold=True)
        self.wait_ready(first)
        second = self.start("rival", issue=8, hold=True)
        self.wait_ready(second)
        first_rows, second_rows = self.rows(first), self.rows(second)
        # At this gate the agent and command children have exited. Kill the
        # holder without cleanup to prove that a stale owner cannot retain it.
        first[0].kill()
        first[0].wait(timeout=5)
        third = self.start("replacement", issue=9)
        self.assertEqual(self.finish(third)["status"], "merged")
        self.assertIsNone(second[0].poll())
        self.assertEqual(self.finish(second)["status"], "merged")
        one, two = self.cache(first_rows), self.cache(second_rows)
        self.assertNotEqual(one, two, "a cache stays exclusive even between commands")
        self.assertEqual(self.cache(self.rows(third)), one, "reuse the exited holder's cache while the rival is live")

    def test_drain_and_pass_commands_hold_a_project_cache_until_they_finish(self):
        for index, (mode, command) in enumerate((("drain", "test"), ("pass", "smoke"))):
            with self.subTest(mode=mode):
                self.fixture("batch-" + mode)
                batch = self.start(mode, mode=mode, hold_command=command)
                self.wait_ready(batch)
                rival = self.start("batch-rival-%s" % index, hold=True)
                self.wait_ready(rival)
                held_rows, rival_rows = self.rows(batch), self.rows(rival)
                result = self.finish(batch)
                rows = self.rows(batch)
                if mode == "drain":
                    self.assertEqual(result["status"], "drained: tests pass")
                    self.assertEqual({r["kind"] for r in rows}, {"prepare", "test", "check"})
                else:
                    self.assertEqual(result["errors"], [])
                    self.assertEqual(result["smoke"], "passed")
                    self.assertEqual(len(result["confirmed"]), 1, result)
                    self.assertEqual({r["kind"] for r in rows}, {"prepare", "smoke", "files", "check"})
                    calls = [json.loads(line) for line in (batch[1] / "claude.json.calls").read_text().splitlines()]
                    self.assertTrue(calls)
                self.assertEqual(self.finish(rival)["status"], "merged")
                batch_cache = self.cache(held_rows)
                self.assertNotEqual(batch_cache, self.cache(rival_rows))
                self.assertEqual(self.cache(rows), batch_cache)
                if mode == "pass":
                    self.assertTrue(all(c["env"].get("LOOP_CACHE_DIR") == rows[0]["cache"] for c in calls))

    def test_codex_sandbox_arguments_allow_the_build_cache(self):
        self.fixture()
        for name in ("cache", "cache with spaces"):
            with self.subTest(folder=name):
                cache = Path(self.work).parent / ".loop-cache" / Path(self.work).name / name
                cache.mkdir(parents=True)
                args = session.codex_sandbox_config(
                    self.work, {"LOOP_CACHE_DIR": str(cache)}, common.read_settings(self.work))
                prefix = "sandbox_workspace_write.writable_roots="
                roots = [json.loads(args[i + 1][len(prefix):]) for i, value in enumerate(args[:-1])
                         if value == "-c" and args[i + 1].startswith(prefix)]
                self.assertEqual(len(roots), 1, args)
                self.assertIn(str(cache.resolve()), roots[0])

    def test_readme_explains_cache_location_lifetime_reset_and_xcode_fallback_together(self):
        readme = (ROOT / "kit/README.md").read_text()
        sections = re.split(r"(?m)^#{1,3} ", readme)
        passages = [s for s in sections if "LOOP_CACHE_DIR" in s]
        self.assertEqual(len(passages), 1, "keep the cache guidance in one place")
        passage = " ".join(passages[0].split()).replace("`", "")
        for pattern in (r"\.loop-cache[/\\]<project>", r"\.loop-worktrees", r"\bparent\b",
                        r"(?i)(?:never|does not|doesn't) (?:delet|remov)", r"(?i)delet.*reset",
                        r"Xcode", r"LOOP_CACHE_DIR(?:\)|(?::-[^}]*)?\})?/DerivedData",
                        r"\.build\}?/DerivedData",
                        r"(?i)unset|not set|fallback|empty"):
            self.assertRegex(passage, pattern)
