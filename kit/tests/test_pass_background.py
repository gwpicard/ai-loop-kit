"""The drain starts one pass worker; polling and reap own its lifetime."""
import json
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git, write_exe
import common
import loop
import pass_


class BackgroundPassFixture(FakeClaudeGh):
    """Hold a real pass at its smoke command, with fake Claude and GitHub."""

    def setUp(self):
        super().setUp()
        # These fakes leave no session children for process inspection to find.
        write_exe(os.path.join(self.tmp, "bin", "ps"), "#!PYTHON\n")
        self.work, _ = make_repo(self.tmp, {"loop.json": json.dumps({
            "Test command": "true", "Parallel": 1, "Idle hours": 1})})
        self.runtime = Path(self.work, ".loop")
        self.runtime.mkdir()
        self.gate = self.runtime / "release-smoke"
        self.smokes = self.runtime / "smoke-starts"
        script = self.runtime / "slow_smoke.py"
        script.write_text(
            "import json, os, pathlib, subprocess, time\n"
            "root = pathlib.Path(%r)\n"
            "head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()\n"
            "with (root / 'smoke-starts').open('a') as f:\n"
            "    f.write(json.dumps({'head': head, 'pid': os.getpid()}) + '\\n')\n"
            "until = time.monotonic() + 15\n"
            "while not (root / 'release-smoke').exists() and time.monotonic() < until:\n"
            "    time.sleep(0.02)\n"
            "(root / 'smoke-ended').touch()\n" % str(self.runtime))
        self.settings = common.read_settings(self.work)
        self.settings["Smoke command"] = shlex.join([sys.executable, str(script)])
        Path(self.work, "loop.json").write_text(json.dumps(dict(
            {k: v for k, v in self.settings.items() if k not in common.ROLES},
            **{k: " ".join(self.settings[k]) for k in common.ROLES})))
        run_git(["checkout", "-b", "loop/main"], self.work)
        self.head = self.land("first")
        self.scenario([
            {"match": "issue view", "responses": [{"stdout": json.dumps({
                "title": "Built piece", "body": "", "comments": []})}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "issue list", "responses": [{"stdout": "[]"}]},
            {"match": "", "responses": [{}]}])
        self.claude({"pass": [{"reply": "FINDINGS:\nnone\n\nLESSONS:\nnone\n\n"
                                 "GUARDRAILS:\nnone\n\nSIMPLIFY:\nnone"}]})
        self.st = loop.new_state()
        self.inputs, self.threads, self.errors, self.processes, self.workers = [], [], [], [], []
        self.worker_crash = False
        self.delay_worker = False
        self.launch_gate = self.runtime / "release-worker"
        real_popen = subprocess.Popen

        def popen(args, *rest, **kwargs):
            worker = (isinstance(args, (list, tuple)) and len(args) > 1
                      and Path(str(args[1])).parent.resolve() == Path(loop.HERE).resolve()
                      and Path(str(args[1])).name != "worker.py")
            if worker and self.worker_crash:
                args = [sys.executable, "-c", "import os; os._exit(7)"]
            elif worker and self.delay_worker:
                args = [sys.executable, "-c", (
                    "import os, pathlib, sys, time\n"
                    "gate = pathlib.Path(sys.argv[1])\n"
                    "until = time.monotonic() + 15\n"
                    "while not gate.exists() and time.monotonic() < until:\n"
                    "    time.sleep(0.02)\n"
                    "os.execv(sys.argv[2], sys.argv[2:])\n"), str(self.launch_gate)] + list(args)
            proc = real_popen(args, *rest, **kwargs)
            self.processes.append((proc, kwargs.get("start_new_session", False)))
            if worker:
                self.workers.append(proc)
            return proc

        self.addCleanup(mock.patch.stopall)
        mock.patch.object(common, "_run_gh", side_effect=self.github).start()
        mock.patch.object(subprocess, "Popen", side_effect=popen).start()
        mock.patch.object(loop, "summary", return_value="").start()
        self.parent_pass = mock.patch.object(pass_, "run_pass", wraps=pass_.run_pass).start()
        self.addCleanup(self.finish)

    def github(self, args, input=None):
        self.inputs.append((args, input))
        if args[:2] == ["pr", "list"]:
            if args[-1] == "comments":
                return 0, "[]", ""
            return 0, json.dumps([{"number": 9, "url": "https://example.test/pull/9"}]), ""
        if args[:2] == ["pr", "view"]:
            return 0, '{"body": ""}', ""
        if args[:2] == ["issue", "view"]:
            return 0, json.dumps({"title": "Built piece", "body": "", "comments": []}), ""
        if args[:2] == ["issue", "list"]:
            return 0, "[]", ""
        return 0, "", ""

    def land(self, text):
        Path(self.work, "piece.txt").write_text(text + "\n")
        run_git(["add", "piece.txt", "loop.json"], self.work)
        run_git(["commit", "-m", "Issue 3"], self.work)
        run_git(["push", "origin", "loop/main"], self.work)
        return common.git(["rev-parse", "HEAD"], cwd=self.work)

    def wait_for(self, predicate, message, seconds=6):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            if predicate():
                return
            time.sleep(0.02)
        self.fail(message)

    def starts(self):
        return [json.loads(line) for line in self.smokes.read_text().splitlines()] if self.smokes.exists() else []

    def begin_drain(self):
        done = threading.Event()

        def drain():
            try:
                loop.drain(self.work, self.settings, self.st)
            except Exception as error:
                self.errors.append(error)
            finally:
                done.set()

        thread = threading.Thread(target=drain)
        self.threads.append(thread)
        thread.start()
        return done

    def bodies(self):
        return [body for args, body in self.inputs if args[:2] in (["pr", "edit"], ["pr", "create"])]

    def collect(self, predicate):
        def reaped():
            loop.reap(self.work, self.st)
            return predicate()
        self.wait_for(reaped, "reap did not collect the finished pass and refresh the pull request")

    def finish(self):
        self.gate.touch()
        self.launch_gate.touch()
        for thread in self.threads:
            thread.join(timeout=20)
        for proc, grouped in list(self.processes):
            if proc.poll() is None:
                try:
                    if grouped:
                        os.killpg(proc.pid, signal.SIGKILL)
                    else:
                        proc.kill()
                except ProcessLookupError:
                    pass
            proc.wait(timeout=5)


class BackgroundPassTest(BackgroundPassFixture):
    def test_drain_returns_while_the_pass_runs_in_another_process(self):
        done = self.begin_drain()
        self.wait_for(self.starts, "the pass never reached its smoke command")
        self.assertTrue(done.wait(2), "drain waited for the pass instead of returning to polling")
        self.assertEqual(self.errors, [])
        self.assertEqual(self.parent_pass.call_count, 0, "the supervisor ran the pass inline")
        self.assertEqual(len(self.workers), 1, "the pass needs its own entry beside worker.py")
        self.assertIsNone(self.workers[0].poll())
        self.assertFalse(self.gate.exists())

    def test_a_second_drain_does_not_start_a_second_pass(self):
        first = self.begin_drain()
        self.wait_for(self.starts, "the first pass did not start")
        self.land("newer")
        second = self.begin_drain()
        self.assertTrue(second.wait(2), "the second drain started or waited for a pass")
        self.assertEqual(len(self.starts()), 1, "two passes ran at once")
        self.assertEqual(len(self.workers), 1)
        self.assertTrue(first.is_set())

    def test_reap_publishes_the_report_without_another_drain(self):
        done = self.begin_drain()
        self.wait_for(self.starts, "the pass did not start")
        self.gate.touch()
        self.assertTrue(done.wait(6))
        self.assertEqual(self.errors, [])
        # Wait for the worker's result, then require reap to publish it.
        for worker in self.workers:
            worker.wait(timeout=6)
        self.inputs.clear()
        self.collect(lambda: any("## End-of-loop pass" in body for body in self.bodies()))
        self.assertEqual(loop.last_pass(self.work)["head"], self.head)
        self.assertTrue(self.claude_calls(), "the worker did not run the pass sessions")
        count = len(self.bodies())
        loop.reap(self.work, self.st)
        self.assertEqual(len(self.bodies()), count, "reap collected the same result twice")

    def test_an_old_pass_keeps_its_commit_and_the_next_drain_covers_the_new_head(self):
        done = self.begin_drain()
        self.wait_for(self.starts, "the pass did not start")
        newer = self.land("second")
        self.gate.touch()
        self.assertTrue(done.wait(6))
        self.collect(lambda: loop.last_pass(self.work).get("head") == self.head)
        report = self.bodies()[-1].split("## End-of-loop pass", 1)[-1]
        self.assertIn(self.head[:7], report, "the pass report does not identify the commit it checked")
        self.assertNotIn(newer[:7], report)
        loop.drain(self.work, self.settings, self.st)
        self.collect(lambda: loop.last_pass(self.work).get("head") == newer)
        self.assertEqual([row["head"] for row in self.starts()], [self.head, newer])
        self.assertIn(newer[:7], self.bodies()[-1])

    def test_the_worker_uses_the_launch_commit_when_the_branch_moves_before_it_starts(self):
        self.delay_worker = True
        done = self.begin_drain()
        self.assertTrue(done.wait(2), "drain waited instead of handing a fixed commit to its worker")
        self.assertEqual(len(self.workers), 1)
        self.land("moved before the worker started")
        self.launch_gate.touch()
        self.wait_for(self.starts, "the delayed pass did not start")
        self.assertEqual(self.starts()[0]["head"], self.head,
                         "the worker followed the moving branch instead of its launch commit")
        self.gate.touch()
        self.collect(lambda: loop.last_pass(self.work).get("head") == self.head)

    def test_a_killed_pass_reports_an_error_when_reaped(self):
        done = self.begin_drain()
        self.wait_for(self.starts, "the pass did not start")
        self.assertTrue(done.wait(2), "the inline pass cannot be killed independently of the supervisor")
        self.assertEqual(len(self.workers), 1, "expected one independent pass worker")
        proc = self.workers[0]
        proc.kill()
        proc.wait(timeout=5)
        self.inputs.clear()
        self.collect(lambda: any("## End-of-loop pass" in body for body in self.bodies()))
        self.assertRegex(self.bodies()[-1].lower(), r"(?s)end-of-loop pass.*(error|failed|did not run|crash|killed)")
        self.assertEqual(self.st["deaths"], {}, "a pass failure consumed a build's crash attempt")
        self.assertEqual(self.errors, [])

    def test_a_crashed_worker_reports_an_error_without_stopping_the_loop(self):
        self.worker_crash = True
        self.gate.touch()
        loop.drain(self.work, self.settings, self.st)
        self.assertEqual(len(self.workers), 1, "the pass was not launched as an independent worker")
        self.workers[0].wait(timeout=5)
        self.inputs.clear()
        self.collect(lambda: any("## End-of-loop pass" in body for body in self.bodies()))
        self.assertRegex(self.bodies()[-1].lower(), r"(?s)end-of-loop pass.*(error|failed|did not run|crash)")
        self.assertEqual(self.st["deaths"], {})
        self.assertEqual(self.errors, [])
