"""Probe sandbox capabilities before starting the queue."""
import contextlib
import io
import json
import os
from pathlib import Path
import shlex
import sys
import unittest
from unittest import mock

from kit.tests.fake_codex_check import FAKE, FakeCodexCheck
from kit.tests.helpers import make_repo, run_git, write_exe
import loop

SANDBOX = '''if argv[:1] == ["sandbox"]:
    with open(os.environ["SANDBOX_CALLS"], "a") as output:
        output.write(json.dumps({"argv": argv, "cwd": os.getcwd()}) + "\\n")
    command = argv[argv.index("--") + 1:]
    env = dict(os.environ, INSIDE_TEST_SANDBOX="1")
    sys.exit(subprocess.run(command, env=env).returncode)
'''

PROBE = '''import json, os, sys
with open(os.environ["PROBE_CALLS"], "a") as output:
    output.write(json.dumps({"sandbox": os.environ.get("INSIDE_TEST_SANDBOX"),
                             "files": sys.argv[1:]}) + "\\n")
'''


class SandboxStartTest(FakeCodexCheck):
    def setUp(self):
        super().setUp()
        write_exe(os.path.join(self.tmp, "bin/codex"), FAKE.replace(
            "argv = sys.argv[1:]\n", "argv = sys.argv[1:]\n" + SANDBOX, 1))
        os.environ["SANDBOX_CALLS"] = str(Path(self.tmp, "sandbox-calls"))
        os.environ["PROBE_CALLS"] = str(Path(self.tmp, "probe-calls"))
        settings = {"Test command": "false", "Test files command": "%s probe.py {files}" % sys.executable,
                    "Builder": "codex gpt-6", "Test writer": "codex gpt-6", "Reviewer": "codex gpt-6"}
        self.work, _ = make_repo(self.tmp, {"loop.json": json.dumps(settings), "probe.py": PROBE,
                                           "tests/test_sample.py": "pass\n"})
        run_git(["push", "origin", "main:loop/main"], self.work)
        self.scenario([
            {"match": "issue list --state closed", "responses": [{"stdout": "[]"}]},
            {"match": "issue list", "responses": [{"stdout": json.dumps([
                {"number": 1, "title": "Factory", "body": "", "labels": []},
            ])}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "issue edit", "responses": [{}]},
        ])
        before = os.getcwd()
        self.addCleanup(os.chdir, before)
        os.chdir(self.work)

    def start(self):
        output = io.StringIO()
        # Stop after one poll, without starting a worker or running the batch pass.
        def stop(path, seconds):
            Path(path).touch()

        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output), \
                mock.patch.object(loop.sys, "platform", "linux"), \
                mock.patch.object(loop.os, "nice"), \
                mock.patch.object(loop.setup, "missing", return_value=None), \
                mock.patch.object(loop, "sync_default", return_value=False), \
                mock.patch.object(loop, "drain"), \
                mock.patch.object(loop, "wait_stop", side_effect=stop), \
                mock.patch.object(loop, "start_builds") as queue:
            code = loop.main(["run"])
        return code, output.getvalue(), queue.call_count

    def calls(self, variable):
        path = Path(os.environ[variable])
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_start_probes_once_without_running_project_tests(self):
        code, text, queues = self.start()
        self.assertEqual(code, 0, text)
        self.assertEqual(len(self.calls("SANDBOX_CALLS")), 1,
                         "loop run must probe Codex's sandbox once, even with several Codex roles")
        self.assertEqual(self.calls("PROBE_CALLS"), [], text)
        self.assertEqual(queues, 1)
        self.assertEqual(self.codex_calls(), [], "the probe must not spend a model turn")

    def test_a_sandbox_refusal_stops_startup_before_the_queue(self):
        refusal = '''if argv[:1] == ["sandbox"]:
    with open(os.environ["SANDBOX_CALLS"], "a") as output:
        output.write(json.dumps({"argv": argv, "cwd": os.getcwd()}) + "\\n")
    print("sandbox: unable to make temporary file: Operation not permitted", file=sys.stderr)
    sys.exit(1)
'''
        write_exe(os.path.join(self.tmp, "bin/codex"), FAKE.replace(
            "argv = sys.argv[1:]\n", "argv = sys.argv[1:]\n" + refusal, 1))
        code, text, queues = self.start()
        self.assertEqual(code, 1, "sandbox refusal must stop startup: " + text)
        self.assertIn("sandbox", text.lower())
        self.assertIn("Operation not permitted", text)
        self.assertEqual(queues, 0, text)
        self.assertNotIn("issue", text.lower())
        self.assertEqual(len(self.calls("SANDBOX_CALLS")), 1)

    def test_a_program_that_cannot_start_stops_the_queue(self):
        path = Path(self.work, "loop.json")
        settings = json.loads(path.read_text())
        settings["Test files command"] = "./missing-test-program {files}"
        path.write_text(json.dumps(settings))
        code, text, queues = self.start()
        self.assertEqual(code, 1, text)
        self.assertEqual(queues, 0, text)
        self.assertIn("Codex sandbox refused the test command", text)

    def test_script_runner_body_is_never_executed(self):
        for shebang, body in (("#!/bin/sh -e", "printf ran > tests-ran\n"),
                              ("#!PYTHON", "open('tests-ran', 'w').close()\n")):
            for targeted in (True, False):
                with self.subTest(shebang=shebang, targeted=targeted):
                    marker = Path(self.work, "tests-ran")
                    runner = Path(self.work, "run-tests")
                    write_exe(str(runner), shebang + "\n" + body)
                    path = Path(self.work, "loop.json")
                    settings = json.loads(path.read_text())
                    settings["Test command"] = "./run-tests"
                    settings["Test files command"] = "./run-tests {files}" if targeted else ""
                    path.write_text(json.dumps(settings))
                    code, text, queues = self.start()
                    self.assertEqual(code, 0, text)
                    self.assertEqual(queues, 1, text)
                    self.assertFalse(marker.exists(), "startup ran the script runner's test body")

    def test_leading_environment_assignments_reach_the_probe_program(self):
        program = Path(self.tmp, "bin/assigned-python")
        write_exe(str(program), '''#!PYTHON
import os, sys
assert os.environ["PYTHONDONTWRITEBYTECODE"] == "1"
assert os.environ["PROBE_VALUE"] == os.environ["PROBE_EXPECTED"]
with open(os.environ["ASSIGNED_CALLS"], "a") as output:
    output.write(os.environ.get("INSIDE_TEST_SANDBOX", "") + "\\n")
os.execv(sys.executable, [sys.executable] + sys.argv[1:])
''')
        os.environ["ASSIGNED_CALLS"] = str(Path(self.tmp, "assigned-calls"))
        os.environ["PROBE_EXPECTED"] = "a value with spaces"
        path = Path(self.work, "loop.json")
        settings = json.loads(path.read_text())
        settings["Test files command"] = (
            'PYTHONDONTWRITEBYTECODE=1 PROBE_VALUE="$PROBE_EXPECTED" '
            + shlex.quote(str(program)) + " probe.py {files}")
        path.write_text(json.dumps(settings))
        code, text, queues = self.start()
        self.assertEqual(code, 0, text)
        self.assertEqual(queues, 1, text)
        self.assertEqual(Path(os.environ["ASSIGNED_CALLS"]).read_text(), "1\n")
        self.assertEqual(self.calls("PROBE_CALLS"), [], text)

    def test_a_worktree_write_refusal_stops_the_queue(self):
        program = Path(self.tmp, "bin/refusing-python")
        write_exe(str(program), '''#!PYTHON
import sys
if sys.argv[1:] == ["--version"]:
    print("Python 3.13")
else:
    print("sandbox: worktree write denied: Operation not permitted", file=sys.stderr)
    sys.exit(1)
''')
        path = Path(self.work, "loop.json")
        settings = json.loads(path.read_text())
        settings["Test files command"] = str(program) + " probe.py {files}"
        path.write_text(json.dumps(settings))
        code, text, queues = self.start()
        self.assertEqual(code, 1, text)
        self.assertEqual(queues, 0, text)
        self.assertIn("Codex sandbox refused the test command", text)


if __name__ == "__main__":
    unittest.main()
