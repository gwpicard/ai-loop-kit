"""Startup checks sandbox capabilities without running project tests."""
import json
import os
from pathlib import Path
import shlex
import unittest

from kit.tests import test_codex_sandbox_start as start_tests
from kit.tests.fake_codex_check import FAKE
from kit.tests.helpers import write_exe


class ProbeContractTest(start_tests.SandboxStartTest):
    def fake_sandbox(self, body):
        write_exe(os.path.join(self.tmp, "bin/codex"), FAKE.replace(
            "argv = sys.argv[1:]\n", "argv = sys.argv[1:]\n" + body, 1))

    def test_probe_starts_the_program_and_checks_worktree_writes(self):
        # Observe the configured interpreter independently of the project script.
        observer = Path(self.tmp, "observer")
        observer.mkdir()
        Path(observer, "sitecustomize.py").write_text('''import json, os, sys
def record(event, args):
    if event == "open" and isinstance(args[0], str):
        path, mode, flags = args
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
            path = os.path.realpath(path)
            if path.startswith(os.path.realpath(os.getcwd()) + os.sep):
                with open(os.environ["WRITE_CALLS"], "a") as output:
                    output.write(json.dumps(path) + "\\n")
sys.addaudithook(record)
''')
        program = Path(self.tmp, "bin/probe-python")
        write_exe(str(program), '''#!PYTHON
import json, os, sys
with open(os.environ["PROGRAM_CALLS"], "a") as output:
    output.write(json.dumps({"sandbox": os.environ.get("INSIDE_TEST_SANDBOX"),
                             "cwd": os.getcwd()}) + "\\n")
os.environ["PYTHONPATH"] = os.environ["PROBE_OBSERVER"]
os.execv(sys.executable, [sys.executable] + sys.argv[1:])
''')
        os.environ["PROBE_OBSERVER"] = str(observer)
        os.environ["PROGRAM_CALLS"] = str(Path(self.tmp, "program-calls"))
        os.environ["WRITE_CALLS"] = str(Path(self.tmp, "write-calls"))
        settings_path = Path(self.work, "loop.json")
        settings = json.loads(settings_path.read_text())
        settings["Test files command"] = shlex.quote(str(program)) + " probe.py {files}"
        settings_path.write_text(json.dumps(settings))

        code, text, queues = self.start()
        self.assertEqual(code, 0, text)
        self.assertEqual(queues, 1, text)
        self.assertEqual(self.calls("PROBE_CALLS"), [],
                         "startup must not run the project test command")
        program_calls = self.calls("PROGRAM_CALLS")
        self.assertTrue(program_calls, "the configured test program must start")
        for call in program_calls:
            self.assertEqual(
                dict(call, cwd=os.path.realpath(call["cwd"])),
                {"sandbox": "1", "cwd": os.path.realpath(self.work)}, text)
        self.assertTrue(self.calls("WRITE_CALLS"),
                        "the probe must attempt a write inside the worktree")
        self.assertEqual(len(self.calls("SANDBOX_CALLS")), 1)
        self.assertEqual(self.codex_calls(), [], "the probe must not spend a model turn")

        self.fake_sandbox('''if argv[:1] == ["sandbox"]:
    print("sandbox: worktree write denied: Operation not permitted", file=sys.stderr)
    sys.exit(1)
''')
        code, text, queues = self.start()
        self.assertEqual(code, 1, text)
        self.assertEqual(queues, 0, text)
        self.assertIn("Codex sandbox refused the test command", text)

    def test_a_denied_project_operation_does_not_stop_startup(self):
        for diagnostic in (
                "PermissionError: [Errno 1] Operation not permitted: 'ps'",
                "project sandbox test\nPermissionError: [Errno 1] Operation not permitted: 'ps'"):
            with self.subTest(diagnostic=diagnostic):
                Path(self.work, "probe.py").write_text(
                    start_tests.PROBE + "\nprint(%r, file=sys.stderr)\nsys.exit(1)\n" % diagnostic)
                code, text, queues = self.start()
                self.assertEqual(code, 0, text)
                self.assertEqual(queues, 1, text)
                self.assertEqual(self.calls("PROBE_CALLS"), [],
                                 "even a test mentioning sandbox must not run during startup")

    def test_only_the_commands_output_can_identify_a_sandbox_refusal(self):
        for diagnostic, expected in (
                ("PermissionError: [Errno 1] Operation not permitted: 'ps'", 0),
                ("Operation not permitted: 'ps'\nproject command failed", 0),
                ("sandbox: Operation not permitted", 1)):
            with self.subTest(diagnostic=diagnostic):
                self.fake_sandbox('''if argv[:1] == ["sandbox"]:
    print(%r, file=sys.stderr)
    sys.exit(1)
''' % diagnostic)
                code, text, queues = self.start()
                self.assertEqual(code, expected, text)
                self.assertEqual(queues, 1 - expected, text)
                if expected:
                    self.assertIn("Codex sandbox refused the test command", text)


for _name in dir(ProbeContractTest):
    if _name.startswith("test_") and _name not in vars(ProbeContractTest):
        setattr(ProbeContractTest, _name, None)


if __name__ == "__main__":
    unittest.main()
