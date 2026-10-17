"""Fake-Claude rehearsals for the v1 field failure paths."""
from __future__ import annotations

import os
import json
import signal
import subprocess
import sys
import textwrap
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from helpers import KIT, git, pump_events
from test_audit import audit
import run_fixtures as run_test_fixture

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kit" / "scripts"))
import gate
import review
import run
import session
from loopkit import main_ref, rev


class ScenarioTest(unittest.TestCase):
    def setUp(self):
        run_test_fixture.RunFixture.setUp(self)

    def build(self, mode: str, attempts: int = 2):
        return run_test_fixture.RunFixture.build(self, mode, attempts)

    def test_hostile_builder_passes_judge_but_cannot_change_loop_settings(self):
        n, result = self.build("settings-cheat", attempts=1)
        self.assertEqual(self.p.gh.prs, {})
        comment = "\n".join(self.p.gh.comments(n))
        self.assertIn("the loop settings changed in AGENTS.md", comment)

    def test_hostile_builder_changes_are_each_refused(self):
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Quality: true\nStandards: STANDARDS.md\n")
        (self.p.root / "STANDARDS.md").write_text("Use clear names.\n")
        (self.p.root / "test_existing.py").write_text("def test_original(): pass\n")
        (self.p.root / "conftest.py").write_text("value = 1\n")
        git(self.p.root, "add", "AGENTS.md", "STANDARDS.md", "test_existing.py", "conftest.py")
        git(self.p.root, "commit", "--quiet", "-m", "Add loop settings and test support")
        git(self.p.root, "push", "--quiet", "origin", "main")
        expected = {
            "hostile-quality-delete": "the build changed frozen files: AGENTS.md",
            "hostile-test-rename": "existing test files not named in the Contract or Files",
            "hostile-conftest": "the build changed frozen files: conftest.py",
            "hostile-standards": "the build changed frozen files: STANDARDS.md",
        }
        for mode, reason in expected.items():
            with self.subTest(mode=mode):
                n, _ = self.build(mode, attempts=1)
                self.assertNotIn(n, self.p.gh.prs)
                self.assertIn(reason, "\n".join(self.p.gh.comments(n)))

    def test_idle_events_keep_a_session_alive_and_silence_stops_it(self):
        events = [json.dumps({"type": "assistant", "message": {
            "content": [{"type": "text", "text": "working"}]}}) for _ in range(20)]
        status, output = pump_events(session, events, idle_seconds=1, clock_step=.25)
        self.assertEqual(status, "")
        self.assertEqual(output.count("working"), 20)
        silent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3)"],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  start_new_session=True)
        with (self.p.root / "silent.log").open("w") as output:
            status = session._pump_session(silent, output, 1, hard_seconds=5)
        self.assertEqual(status, "idle")

    def test_builder_streaming_logs_events_and_passes(self):
        with patch.object(run, "idle_limit_seconds", return_value=30):
            n, result = self.build("stream-good", attempts=1)
        self.assertIn("pull request ready", result)
        log = self.p.root / ".loop" / "logs" / f"piece-{n}-attempt-1.log"
        self.assertIn("still working", log.read_text())

    def test_attempt_log_records_start_finish_and_elapsed_time(self):
        n, result = self.build("good", attempts=1)
        self.assertIn("pull request ready", result)
        log = self.p.root / ".loop" / "logs" / f"piece-{n}-attempt-1.log"
        line = next((line for line in log.read_text().splitlines()
                     if line.startswith("Attempt timing: ")), None)
        self.assertIsNotNone(line)
        timing = json.loads(line.removeprefix("Attempt timing: "))
        started = datetime.fromisoformat(timing["started_at"])
        finished = datetime.fromisoformat(timing["finished_at"])
        self.assertEqual(started.utcoffset().total_seconds(), 0)
        self.assertEqual(finished.utcoffset().total_seconds(), 0)
        self.assertLessEqual(started, finished)
        self.assertAlmostEqual((finished - started).total_seconds(),
                               timing["elapsed_seconds"], delta=2)

    def test_real_run_sigterm_stops_a_child_during_review(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        state = self.p.tmp.name + "/github.json"
        Path(state).write_text(json.dumps({
            "issues": self.p.gh.issues,
            "notes": {str(key): value for key, value in self.p.gh.notes.items()},
        }))
        inject = Path(self.p.tmp.name) / "inject"
        inject.mkdir()
        (inject / "sitecustomize.py").write_text(textwrap.dedent("""\
            import json
            import os
            import sys
            from pathlib import Path
            sys.path.insert(0, os.environ["LOOP_TEST_HELPERS"])
            from helpers import FakeGitHub
            import loopkit
            class ChildGitHub(FakeGitHub):
                def __init__(self, root):
                    super().__init__()
                    state = json.loads(Path(os.environ["LOOP_GH_STATE"]).read_text())
                    self.issues = {int(k): v for k, v in state["issues"].items()}
                    self.notes = {int(k): [tuple(note) for note in v]
                                  for k, v in state["notes"].items()}
                def set_labels(self, n, add, remove):
                    super().set_labels(n, add, remove)
                    Path(os.environ["LOOP_GH_STATE"]).write_text(json.dumps({
                        "issues": self.issues, "notes": self.notes,
                    }))
            loopkit.GitHub = ChildGitHub
            """))
        child_pid_file = Path(self.p.tmp.name) / "review-child.pid"
        fake = Path(self.p.tmp.name) / "review-claude"
        fake.write_text(textwrap.dedent("""\
            #!/usr/bin/env python3
            import os, pathlib, subprocess, sys, time
            prompt = " ".join(sys.argv)
            if os.environ.get("LOOP_REVIEWER") == "1":
                if "Standards reviewer brief" in prompt:
                    child_code = (
                        "import time; time.sleep(60)"
                    )
                    child = subprocess.Popen([sys.executable, "-c", child_code])
                    pathlib.Path(os.environ["CHILD_PID_FILE"]).write_text(str(child.pid))
                    while child.poll() is None:
                        time.sleep(.05)
                    print('<verdict>{"findings":[],"follow_ups":[],"changes":"none"}</verdict>')
                else:
                    print('<verdict>{"findings":[]}</verdict>')
            else:
                pathlib.Path("habits.py").write_text(
                    'def add(items, name):\\n    return items if name in items else items + [name]\\n')
                subprocess.run(["git", "add", "habits.py"], check=True)
                subprocess.run(["git", "commit", "--quiet", "-m", "Build"], check=True)
                print("built")
            """))
        fake.chmod(0o755)
        env = dict(os.environ)
        env.update({
            "LOOP_CLAUDE": str(fake),
            "LOOP_TEST_HELPERS": str(Path(__file__).resolve().parent),
            "LOOP_GH_STATE": state,
            "PYTHONPATH": os.pathsep.join((str(inject), str(KIT / "scripts"))),
            "CHILD_PID_FILE": str(child_pid_file),
        })
        process = subprocess.Popen([sys.executable, str(KIT / "scripts" / "run.py"), str(n)],
                                   cwd=self.p.root, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, start_new_session=True)
        def cleanup_run():
            if process.poll() is None:
                process.kill()
            process.wait()
            if process.stdout:
                process.stdout.close()
        self.addCleanup(cleanup_run)
        deadline = time.monotonic() + 20
        while not child_pid_file.is_file() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.05)
        self.assertTrue(child_pid_file.is_file(), process.stdout.read() if process.poll() is not None else "review child did not start")
        child_pid = int(child_pid_file.read_text())
        group = os.getpgid(child_pid)
        evidence = self.p.root / ".loop" / "logs" / "reviewer-processes"
        self.assertIn(str(group), evidence.read_text().splitlines())
        live_checks = audit.audit_cleanup(self.p.root)
        self.assertIn((False, f"reviewer process group {group} is alive"), live_checks)
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=10)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(.05)
        else:
            os.kill(child_pid, signal.SIGKILL)
            self.fail("review child survived SIGTERM to the real run process")

        restarted = subprocess.run(
            [sys.executable, str(KIT / "scripts" / "run.py"), str(n)],
            cwd=self.p.root, env=env, capture_output=True, text=True, timeout=20, check=False)
        self.assertEqual(restarted.returncode, 1, restarted.stdout + restarted.stderr)
        self.assertIn("refused: there is no move from shaping to building", restarted.stdout)
        checks = audit.audit_cleanup(self.p.root)
        self.assertTrue(all(passed for passed, _ in checks), checks)
        self.assertIn((True, f"reviewer process group {group} has exited"), checks)
        self.assertIn((True, "no review worktrees or branches remain"), checks)
        saved = json.loads(Path(state).read_text())
        piece = {**saved["issues"][str(n)],
                 "comments": [text for _, text in saved["notes"][str(n)]]}
        broken, score = audit.audit_piece(piece, None, self.p.root)
        self.assertEqual(broken, [])
        self.assertEqual((score["state"], score["attempts"], score["sent_back"]),
                         ("shaping", 1, 1))

    def test_bar_wrong_stops_on_attempt_one(self):
        n, result = self.build("bar-wrong", attempts=3)
        self.assertIn("back to shaping", result)
        from loopkit import records
        handbacks = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "give-back"]
        self.assertEqual(handbacks[-1]["type"], "bar-wrong")
        attempts = [line for line in self.p.gh.comments(n)
                    if line.startswith("**Run:** attempt")]
        self.assertEqual(len(attempts), 1)

    def test_quality_failure_retries_and_passes_on_second_attempt(self):
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() +
            "Quality: if [ ! -f .loop/quality-once ]; then touch .loop/quality-once; exit 1; fi; exit 0\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Add retrying quality check")
        git(self.p.root, "push", "--quiet", "origin", "main")
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        with patch.object(gate, "quality_fails_on_main", return_value=False) as main_check:
            result = run.build_piece(self.p.gh, self.p.root, n, 2)
        self.assertIn("pull request ready", result)
        self.assertTrue(any("failed a Quality check; retrying" in c for c in self.p.gh.comments(n)))
        quality_command = next(line.removeprefix("Quality: ")
                               for line in agents.read_text().splitlines()
                               if line.startswith("Quality: "))
        main_commit = rev(self.p.root, main_ref(self.p.root))
        main_check.assert_called_once_with(self.p.folder(n), quality_command, "true", [])
        probe = gate.quality_probe_path(self.p.root, n, quality_command, main_commit)
        self.assertTrue(probe.is_file())
        self.assertEqual(json.loads(probe.read_text())["main"], main_commit)

    def test_node_review_fix_survives_the_recheck(self):
        source = self.p.root / "src" / "app.js"
        source.parent.mkdir()
        source.write_text("export const value = 1;\n")
        git(self.p.root, "add", "src/app.js")
        git(self.p.root, "commit", "--quiet", "-m", "Add node fixture")
        git(self.p.root, "push", "--quiet", "origin", "main")
        os.environ["FAKE_MODE"] = "good"
        os.environ["FAKE_REVIEW_MODE"] = "node-standard-fix"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("pull request ready", result)
        self.assertIn("// reviewed", git(self.p.root, "show", f"piece/{n}:src/app.js"))

    def test_kill_during_review_cleans_folder_and_branches(self):
        os.environ["FAKE_MODE"] = "good"
        os.environ["FAKE_REVIEW_MODE"] = "review-idle"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        with patch.object(review, "idle_limit_seconds", return_value=1):
            result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("back to shaping", result)
        branches = git(self.p.root, "branch", "--list", "review/*")
        self.assertEqual(branches, "")
        self.assertTrue(self.p.folder(n).exists())
        self.assertIn("habits.py", git(self.p.folder(n), "ls-files"))
        self.assertFalse(run._ACTIVE_GROUPS)

    def test_run_start_removes_and_reports_abandoned_review_worktrees(self):
        branch = "review/standards-21-2-abcdef12"
        folder = self.p.root.parent / "abandoned-review"
        git(self.p.root, "worktree", "add", "--quiet", "-b", branch,
            str(folder), "main")
        removed = run.cleanup_interrupted_reviews(self.p.root)
        self.assertEqual(removed, [f"worktree {folder.resolve()}", f"branch {branch}"])
        self.assertNotIn(branch, git(self.p.root, "branch", "--list", "review/*"))
        self.assertFalse(folder.exists())

    def test_main_merge_that_changes_the_bar_returns_before_attempt_one(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        (self.p.root / "conftest.py").write_text("value = 1\n")
        git(self.p.root, "add", "conftest.py")
        git(self.p.root, "commit", "--quiet", "-m", "Change project test bar")
        git(self.p.root, "push", "--quiet", "origin", "main")
        result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("back to shaping", result)
        self.assertFalse(any(c.startswith("**Run:** attempt 1 of")
                             for c in self.p.gh.comments(n)))


if __name__ == "__main__":
    unittest.main()
