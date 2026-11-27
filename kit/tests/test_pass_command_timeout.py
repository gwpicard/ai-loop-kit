"""Pass command timeouts reach both reports, and reap records how the pass ended."""
import contextlib
import json
import os
import re
import shlex
import signal
import sys
import time
from pathlib import Path
from unittest import mock

from kit.tests.test_pass_background import BackgroundPassFixture
import loop


class PassCommandTimeoutTest(BackgroundPassFixture):
    def setUp(self):
        super().setUp()
        self.contexts = contextlib.ExitStack()
        self.addCleanup(self.contexts.close)
        # The supervisor's stdout is redirected to loop.out by its launcher.
        self.output = self.contexts.enter_context((self.runtime / "loop.out").open("a"))
        self.contexts.enter_context(contextlib.redirect_stdout(self.output))

    def short_command_limit(self):
        launcher = Path(self.tmp, "short pass worker")
        launcher.mkdir()
        (launcher / "pass_worker.py").write_text(
            "import runpy, sys\n"
            "sys.path.insert(0, %r)\n"
            "import merge\n"
            "merge.TEST_TIMEOUT = 1\n"
            "runpy.run_path(%r, run_name='__main__')\n"
            % (loop.HERE, str(Path(loop.HERE, "pass_worker.py"))))
        # Change only the budget in the child; run the real worker and shell command.
        self.contexts.enter_context(mock.patch.object(loop, "HERE", str(launcher)))

    def launch(self):
        before = len(self.workers)
        done = self.begin_drain()
        self.assertTrue(done.wait(10), "drain did not return after launching the pass")
        self.assertEqual(self.errors, [])
        self.assertEqual(len(self.workers), before + 1)
        return self.workers[-1]

    def collect_worker(self, worker):
        worker.wait(timeout=20)
        self.inputs.clear()
        self.collect(lambda: "pass" not in self.st)
        self.assertTrue(self.bodies(), "reap did not refresh the final pull request")
        saved = json.loads((self.runtime / "pass.json").read_text())
        return saved, self.bodies()[-1].split("## End-of-loop pass", 1)[-1]

    def end_lines(self):
        self.output.flush()
        return [line for line in (self.runtime / "loop.out").read_text().splitlines()
                if "end-of-loop pass finished" in line or "end-of-loop pass failed: " in line]

    def assert_timeout(self, text, name, command, observed):
        self.assertIn(name, text)
        self.assertIn(command, text)
        self.assertRegex(text.lower(), r"\b(timed out|timeout)\b")
        self.assertRegex(text.lower(), r"\blimit\s*[:=]?\s*1(?:\.0+)?\s*(seconds?|s)\b")
        elapsed = re.search(r"\belapsed\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:seconds?|s)\b",
                            text, re.I)
        self.assertIsNotNone(elapsed, "the report omits the elapsed seconds: " + text)
        self.assertGreaterEqual(float(elapsed[1]), 1)
        self.assertLessEqual(float(elapsed[1]), observed + 1)
        self.assertNotIn("exit code -9 and no result", text)

    def test_command_timeout_names_the_command_limit_and_elapsed_in_both_reports(self):
        self.short_command_limit()
        smoke = self.settings["Smoke command"]
        candidate = "tests/test_pass_probe.py"
        test = "if test -f %s; then %s; fi" % (
            candidate, shlex.join([sys.executable, candidate]))
        # Prepare, Test and Check also run at drain; hold them only in the pass.
        guarded = 'if [ -n "$LOOP_PASS_WORKER" ]; then %s; fi' % smoke
        cases = [
            ("Smoke", smoke, {"Smoke command": smoke}),
            ("Smoke", ": 'before the smoke command'; " + smoke,
             {"Smoke command": ": 'before the smoke command'; " + smoke}),
            ("Prepare", guarded, {"Prepare command": guarded}),
            ("Test files", smoke + " " + candidate,
             {"Test files command": smoke + " {files}"}),
            ("Test", guarded, {"Test command": guarded}),
            ("Check", guarded, {"Check command": guarded}),
        ]
        for name, command, settings in cases:
            with self.subTest(name=name, command=command):
                self.settings.update({"Smoke command": "true", "Prepare command": "",
                                      "Test command": test, "Test files command": "",
                                      "Check command": "", "Red-team surfaces": ["the CLI"]})
                self.settings.update(settings)
                self.claude({"pass": [
                    {"reply": "FINDINGS:\nnone"},
                    {"reply": "FINDINGS:\nnone"},
                    {"files": {".loop/pass/" + candidate: "assert False, 'pass probe'\n"},
                     "reply": "FINDINGS:\nPass probe | a reproducible failure | .loop/pass/" + candidate},
                ]})
                starts = len(self.starts())
                began = time.monotonic()
                saved, body = self.collect_worker(self.launch())
                observed = time.monotonic() - began
                self.assertEqual(len(self.starts()), starts + 1,
                                 "the worker did not run the delayed command")
                for text in (saved["text"], body):
                    with self.subTest(report=text):
                        self.assert_timeout(text, name, command, observed)

    def test_a_worker_without_a_result_keeps_the_original_failure_text(self):
        for code in (7, -signal.SIGKILL):
            with self.subTest(exit_code=code):
                self.worker_crash = code == 7
                starts = len(self.starts())
                worker = self.launch()
                if code < 0:
                    self.wait_for(lambda: len(self.starts()) > starts,
                                  "the pass did not reach its Smoke command")
                    os.killpg(worker.pid, signal.SIGKILL)
                saved, body = self.collect_worker(worker)
                expected = ("## End-of-loop pass\n\nCommit: `%s`.\n\n"
                            "The pass failed: worker ended with exit code %s and no result.\n"
                            % (self.head, code))
                self.assertEqual(worker.returncode, code)
                self.assertEqual(saved["text"], expected)
                self.assertIn(expected.split("\n", 1)[1], body)

    def test_reap_logs_one_finished_line_with_the_session_count(self):
        self.gate.touch()
        saved, _ = self.collect_worker(self.launch())
        self.assertIn("## End-of-loop pass (4 sessions)", saved["text"])
        loop.reap(self.work, self.st)
        loop.reap(self.work, self.st)
        lines = self.end_lines()
        self.assertEqual(len(lines), 1, "expected one pass completion line in loop.out")
        self.assertRegex(lines[0], r"end-of-loop pass finished\b.*\b4 sessions\b")

    def test_reap_logs_one_failed_line_with_the_reason(self):
        self.worker_crash = True
        saved, _ = self.collect_worker(self.launch())
        reason = "worker ended with exit code 7 and no result"
        self.assertIn(reason, saved["text"])
        loop.reap(self.work, self.st)
        loop.reap(self.work, self.st)
        lines = self.end_lines()
        self.assertEqual(len(lines), 1, "expected one pass completion line in loop.out")
        self.assertIn("end-of-loop pass failed: " + reason, lines[0])
