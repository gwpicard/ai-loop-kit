"""A run with no flag walks away when it can, and a detached run outlives its caller."""
from __future__ import annotations

import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import KIT, SPEC, FakeGitHub

# isort: split
import procs
import run
import run_cli
import walkaway
from loopkit import record_text

ROOT = KIT.parent
PASS = [(True, "everything is fine", "")]
FAIL = [(True, "the first check", ""), (False, "Prepare is red on main", "fix the Prepare command")]


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


class ModeTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.gh = FakeGitHub()

    def ready(self, **record):
        n = self.gh.create_issue("A piece", SPEC, ["state:ready"])
        self.gh.comment(n, record_text({"move": "ready", **record}, "ready"))
        return n

    def build(self, gh, root, n, *args):
        self.lock_seen = run.lock_path(self.root).is_file()
        self.gh.set_labels(n, ["state:approval"], ["state:ready"])
        return f"piece {n}: pull request ready"

    def start(self, arguments, checks=PASS):
        stack = ExitStack()
        self.addCleanup(stack.close)
        for name, value in (("repo_root", self.root), ("GitHub", self.gh)):
            stack.enter_context(patch.object(run_cli, name, return_value=value))
        stack.enter_context(patch.object(run_cli, "refresh_main"))
        stack.enter_context(patch.object(run_cli.signal, "signal"))
        stack.enter_context(patch.object(run_cli.gate, "ignore_loop_folder"))
        stack.enter_context(patch.object(run_cli.gate, "sync"))
        self.doctor = stack.enter_context(patch.object(run_cli.gate, "doctor", return_value=checks))
        self.awake = MagicMock()
        stack.enter_context(patch.object(walkaway, "keep_awake", return_value=self.awake))
        self.post = stack.enter_context(patch.object(walkaway, "post_summary"))
        stack.enter_context(patch.object(run, "recover_building", return_value=[]))
        stack.enter_context(patch.object(run, "cleanup_interrupted_reviews", return_value=[]))
        stack.enter_context(patch.object(run, "ready_pieces", side_effect=lambda *a: sorted(
            n for n, i in self.gh.issues.items() if "state:ready" in i["labels"])))
        self.builder = stack.enter_context(patch.object(run, "build_piece", side_effect=self.build))
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = run.main(arguments)
        stack.close()
        return status, out.getvalue(), err.getvalue()

    def walk_away_flag(self):
        return self.builder.call_args.args[4]

    def test_D1_a_full_pass_runs_walk_away_and_writes_the_summary(self):
        n = self.ready()
        status, out, _ = self.start([])
        self.assertEqual(status, 0)
        self.assertEqual(self.doctor.call_args.kwargs["pieces"], [n])
        self.assertTrue(self.doctor.call_args.kwargs["walk_away"])
        self.assertIs(self.walk_away_flag(), True)
        self.awake.__enter__.assert_called_once()
        self.assertTrue((self.root / ".loop" / "summary.md").is_file())
        self.assertNotIn("Falling back", out)

    def test_D2_a_failed_check_names_itself_and_falls_back_to_attended(self):
        self.ready()
        status, out, _ = self.start([], FAIL)
        self.assertEqual(status, 0)
        self.assertIn("Prepare is red on main", out)
        self.assertIn("next: fix the Prepare command", out)
        self.assertNotIn("the first check", out)
        self.assertIn("Falling back to an attended run", out)
        self.assertIs(self.walk_away_flag(), False)
        self.awake.__enter__.assert_not_called()
        self.assertFalse((self.root / ".loop" / "summary.md").exists())

    def test_D2_a_line_is_printed_before_the_probe(self):
        self.ready()
        order = []
        with patch("builtins.print", side_effect=lambda *a, **k: order.append(" ".join(map(str, a)))):
            self.start([])
        self.assertTrue(order and "check" in order[0].lower(), order[:2])

    def test_D3_a_piece_that_needs_services_makes_the_run_attended(self):
        n = self.ready(risks={"needs_services": ["postgres", "redis"]})
        status, out, _ = self.start([])
        self.assertEqual(status, 0)
        self.doctor.assert_not_called()
        self.assertIn(f"piece {n}", out)
        self.assertIn("postgres", out)
        self.assertIn("redis", out)
        self.assertIs(self.walk_away_flag(), False)

    def test_D4_attended_skips_doctor_and_prints_no_fallback(self):
        self.ready()
        status, out, _ = self.start(["--attended"], FAIL)
        self.assertEqual(status, 0)
        self.doctor.assert_not_called()
        self.assertNotIn("Falling back", out)
        self.assertIs(self.walk_away_flag(), False)

    def test_D5_walk_away_still_refuses_when_a_check_fails(self):
        self.ready()
        status, _, err = self.start(["--walk-away"], FAIL)
        self.assertEqual(status, 2)
        self.assertIn("refused: walk-away pre-run check failed", err)
        self.builder.assert_not_called()

    def test_D6_codex_walk_away_says_it_is_a_preview_and_claude_does_not(self):
        self.ready(agent="codex")
        _, out, _ = self.start([])
        self.assertIs(self.walk_away_flag(), True)
        self.assertIn("Codex backend is a preview", out)
        self.setUp()
        self.ready(agent="claude")
        _, out, _ = self.start([])
        self.assertNotIn("preview", out.lower())
        self.setUp()
        self.ready(agent="claude")
        _, out, _ = self.start(["--agent", "codex"])
        self.assertIn("Codex backend is a preview", out)

    def test_D11_both_modes_keep_the_lock_the_status_and_the_final_line(self):
        for arguments, checks in (([], PASS), (["--attended"], PASS), ([], FAIL)):
            with self.subTest(arguments=arguments, ok=checks is PASS):
                self.setUp()
                self.ready()
                self.lock_seen = False
                status, out, _ = self.start(arguments, checks)
                self.assertTrue(self.lock_seen)
                self.assertEqual(status, 0)
                self.assertIn("Run finished.", out)
                self.assertFalse(run.lock_path(self.root).exists())
        self.setUp()
        n = self.ready()
        with patch.object(self, "build", side_effect=Exception("boom")):
            status, out, _ = self.start([])
        self.assertEqual((status, "Run finished." in out), (1, True), n)


class WordingTest(unittest.TestCase):
    def read(self, path):
        return (ROOT / path).read_text()

    def test_D7_walk_away_is_no_longer_called_a_preview_for_claude(self):
        readme = self.read("README.md")
        walk = readme.split("## Walk away", 1)[1].split("\n## ", 1)[0]
        self.assertNotIn("planned", walk)
        for sentence in walk.replace("\n", " ").split(". "):
            if "preview" in sentence.lower():
                self.assertIn("Codex", sentence)
        self.assertNotIn("have not yet been validated", readme)
        self.assertIn("experimental", readme.lower())
        design = self.read("docs/DESIGN.md")
        self.assertNotIn("Planned for 1.7: walking away by default", design)
        guidance = self.read("kit/skills/run/references/walk-away.md")
        for line in guidance.splitlines():
            if "preview" in line.lower():
                self.assertIn("Codex", line)
        skill = self.read("kit/skills/run/SKILL.md")
        self.assertIn("--attended", skill)
        self.assertIn("--detach", skill)


class DetachTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.pids = []
        self.addCleanup(self.reap)

    def reap(self):
        for pid in self.pids:
            try:
                os.killpg(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

    def sleeper(self, mark="child.pgid"):
        code = f"import os,time;open({str(self.root / mark)!r},'w').write(str(os.getpgid(0)));time.sleep(60)"
        return [sys.executable, "-c", code]

    def wait_for(self, path):
        for _ in range(200):
            if path.is_file() and path.read_text():
                return
            time.sleep(0.05)
        self.fail(f"{path.name} never appeared")

    def test_lock_holder_reads_without_taking_the_lock(self):
        self.assertIsNone(procs.lock_holder(self.root))
        lock = procs.lock_path(self.root)
        lock.parent.mkdir(parents=True)
        lock.write_text(json.dumps({"pid": os.getpid(), "children": []}))
        self.assertEqual(procs.lock_holder(self.root), os.getpid())
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        lock.write_text(json.dumps({"pid": dead.pid, "children": []}))
        self.assertIsNone(procs.lock_holder(self.root))
        lock.write_text("not json")
        self.assertIsNone(procs.lock_holder(self.root))
        self.assertEqual(lock.read_text(), "not json")

    def test_D8_the_run_starts_in_a_new_session_with_a_log_and_returns(self):
        out = io.StringIO()
        started = time.monotonic()
        with redirect_stdout(out):
            pid, log = run_cli.start_detached(self.root, [], command=self.sleeper())
        self.pids.append(pid)
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(log.parent, self.root / ".loop" / "logs")
        self.assertRegex(log.name, r"^run-\d{8}T\d{6}Z\.log$")
        self.wait_for(self.root / "child.pgid")
        self.assertNotEqual(int((self.root / "child.pgid").read_text()), os.getpgid(0))
        self.assertTrue(alive(pid))

    def test_D8_main_detach_prints_pid_and_log_and_returns_zero(self):
        popen = MagicMock()
        popen.return_value.pid = 4242
        out = io.StringIO()
        with patch.object(run_cli, "repo_root", return_value=self.root), \
                patch.object(run_cli.subprocess, "Popen", popen), redirect_stdout(out):
            status = run.main(["--detach", "--attended", "7"])
        self.assertEqual(status, 0)
        command = popen.call_args.args[0]
        self.assertEqual(Path(command[1]).name, "run.py")
        self.assertEqual(command[2:], ["--attended", "7"])
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertIn("4242", out.getvalue())
        self.assertIn(str(self.root / ".loop" / "logs" / "run-"), out.getvalue())

    def test_D9_the_run_survives_sigterm_and_sighup_to_the_callers_group(self):
        script = textwrap.dedent(f"""
            import sys
            sys.path.insert(0, {str(ROOT / "kit" / "scripts")!r})
            import run_cli
            from pathlib import Path
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()):
                pid, log = run_cli.start_detached(Path({str(self.root)!r}), [],
                                                  command={self.sleeper()!r})
            print(pid, flush=True)
            import time; time.sleep(60)
        """)
        for number in (signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=number.name):
                (self.root / "child.pgid").unlink(missing_ok=True)
                caller = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE,
                                          text=True, start_new_session=True)
                self.pids.append(caller.pid)
                pid = int(caller.stdout.readline())
                self.pids.append(pid)
                self.wait_for(self.root / "child.pgid")
                os.killpg(caller.pid, number)
                caller.wait(timeout=10)
                time.sleep(0.3)
                self.assertTrue(alive(pid), "the detached run ended with its caller")
                os.killpg(pid, signal.SIGKILL)

    def test_D10_a_live_lock_refuses_before_anything_starts(self):
        lock = procs.lock_path(self.root)
        lock.parent.mkdir(parents=True)
        lock.write_text(json.dumps({"pid": os.getpid(), "children": []}))
        err = io.StringIO()
        with patch.object(run_cli, "repo_root", return_value=self.root), \
                patch.object(run_cli.subprocess, "Popen") as popen, redirect_stderr(err):
            status = run.main(["--detach"])
        self.assertEqual(status, 2)
        popen.assert_not_called()
        self.assertIn(str(os.getpid()), err.getvalue())
        self.assertFalse((self.root / ".loop" / "logs").exists())


if __name__ == "__main__":
    unittest.main()
