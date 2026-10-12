"""Attended setup reports network refusals without disclosing Git diagnostics."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit/scripts"))

from loop import cli  # noqa: E402


def setup_module() -> Any:
    spec = importlib.util.spec_from_file_location("sandbox_setup", ROOT / "kit/scripts/setup.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SetupSandboxTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="setup-sandbox-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.project = self.base / "person's project"
        self.project.mkdir()
        self.setup = setup_module()
        self.oid = "a" * 40
        self.origin = "https://example.test/private-project.git"
        self.private = "https://person:credential-must-not-leak@example.test/private"
        self.token = "synthetic-token-must-not-leak"

    def retry(self) -> str:
        return ("!python3 " + shlex.quote(str(self.setup.HERE / "setup.py"))
                + " preflight --project " + shlex.quote(str(self.project.resolve())) + " --json")

    def operation(self, stage: str, diagnostic: str, code: int = 128) -> Any:
        def run(folder: Path, arguments: list[str], timeout: int) -> Any:
            del folder, timeout
            command = arguments[0]
            if command == stage:
                return subprocess.CompletedProcess(arguments, code, "", diagnostic)
            output = self.oid + "\trefs/heads/main\n" if command == "ls-remote" else ""
            if command == "cat-file":
                output = "commit\n"
            return subprocess.CompletedProcess(arguments, 0, output, "")
        return run

    def refusal(self, stage: str, diagnostic: str, code: int = 128) -> cli.Failure:
        with patch.object(self.setup, "git_out", return_value=self.origin), \
                patch.object(self.setup, "origin_git", side_effect=self.operation(
                    stage, diagnostic, code)), self.assertRaises(cli.Failure) as raised:
            self.setup.check_origin(self.project, False)
        return raised.exception

    def unknown(self, failure: cli.Failure) -> None:
        text = str(failure).lower()
        self.assertNotIn("origin has no main", text)
        self.assertNotIn("sandbox network denial", text)
        self.assertNotIn("sandbox blocked", text)
        self.assertNotIn("push", failure.next_command)
        self.assertNotIn("commit --", failure.next_command)
        self.assertIn("preflight", failure.next_command)

    def test_origin_git_retains_captured_stderr(self) -> None:
        child = Mock(returncode=128)
        child.communicate.return_value = ("distinct stdout", "distinct private stderr")
        output, error = io.StringIO(), io.StringIO()
        with patch.object(self.setup.subprocess, "Popen", return_value=child) as popen, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            result = self.setup.origin_git(self.project, ["ls-remote", "origin"], 20)
        self.assertEqual(result.stdout, "distinct stdout")
        self.assertEqual(result.stderr, "distinct private stderr")
        self.assertEqual((output.getvalue(), error.getvalue()), ("", ""))
        self.assertEqual(popen.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        child.communicate.assert_called_once_with(timeout=20)

    def test_query_sandbox_network_denial_has_safe_person_retry(self) -> None:
        for marker in ("blocked-by-sandbox-runtime: network request denied",
                       "Sandbox: deny network-outbound"):
            with self.subTest(marker=marker):
                failure = self.refusal("ls-remote", marker + " " + self.private)
                self.assertIn("sandbox", str(failure).lower())
                self.assertIn("network", str(failure).lower())
                self.assertEqual(failure.next_command, self.retry())
                self.assertNotIn(self.private, str(failure))

    def test_fetch_sandbox_network_denial_has_safe_person_retry(self) -> None:
        for marker in ("blocked-by-sandbox-runtime: network request denied",
                       "Sandbox: deny network-outbound"):
            with self.subTest(marker=marker):
                failure = self.refusal("fetch", marker + " " + self.token)
                self.assertIn("sandbox", str(failure).lower())
                self.assertIn("network", str(failure).lower())
                self.assertEqual(failure.next_command, self.retry())
                self.assertNotIn(self.token, str(failure))
        self.assertEqual(sorted(item.name for item in self.base.iterdir()), [self.project.name])

    def test_generic_transport_errors_are_unknown(self) -> None:
        for stage in ("ls-remote", "fetch"):
            for diagnostic in ("Could not resolve host: example.test", "Connection refused",
                               "HTTP 403 Forbidden", "Authentication failed",
                               "Operation timed out"):
                with self.subTest(stage=stage, diagnostic=diagnostic):
                    self.unknown(self.refusal(stage, diagnostic + " " + self.private))

    def test_timeout_is_unknown_and_reaps_owned_process(self) -> None:
        child = Mock(pid=123456, returncode=-9)
        child.communicate.side_effect = [subprocess.TimeoutExpired("git", 20), ("", "")]
        with patch.object(self.setup.subprocess, "Popen", return_value=child), \
                patch.object(self.setup.os, "killpg") as kill, \
                self.assertRaises(cli.Failure) as raised:
            self.setup.origin_git(self.project, ["ls-remote", "origin"], 20)
        self.unknown(raised.exception)
        kill.assert_called_once_with(child.pid, self.setup.signal.SIGKILL)
        self.assertEqual(child.communicate.call_count, 2)
        self.assertEqual(child.communicate.call_args.kwargs["timeout"], 5)

    def test_exit_two_with_stderr_is_not_absent_main(self) -> None:
        for diagnostic in ("Sandbox: deny network-outbound", "Authentication failed",
                           "Could not resolve host: example.test"):
            with self.subTest(diagnostic=diagnostic):
                failure = self.refusal("ls-remote", diagnostic, 2)
                self.assertNotIn("origin has no main", str(failure).lower())
                self.assertNotIn("push", failure.next_command)
                self.assertNotIn("commit --", failure.next_command)
                self.assertIn("preflight", failure.next_command)

    def test_non_network_sandbox_text_is_not_network_denial(self) -> None:
        for diagnostic in ("Could not open sandbox-notes.txt", "Sandbox: deny file-read-data",
                           "HTTP 403 Forbidden", "URL https://example.test/deny-network-outbound"):
            with self.subTest(diagnostic=diagnostic):
                self.unknown(self.refusal("ls-remote", diagnostic))

    def test_preflight_cli_redacts_sensitive_diagnostics(self) -> None:
        for stage in ("ls-remote", "fetch"):
            for marker in ("Sandbox: deny network-outbound", "HTTP 403 Forbidden"):
                diagnostic = marker + " " + self.private + "?token=" + self.token
                output, error = io.StringIO(), io.StringIO()
                with self.subTest(stage=stage, marker=marker), \
                        patch.object(self.setup, "project_root", return_value=self.project), \
                        patch.object(self.setup, "check_tooling", return_value=False), \
                        patch.object(self.setup, "git_out", return_value=self.origin), \
                        patch.object(self.setup, "origin_git", side_effect=self.operation(
                            stage, diagnostic)), contextlib.redirect_stdout(output), \
                        contextlib.redirect_stderr(error):
                    code = self.setup.main(["--json", "preflight", "--project", str(self.project)])
                body = json.loads(output.getvalue())
                self.assertFalse(body["ok"])
                self.assertNotEqual(code, 0)
                emitted = output.getvalue() + error.getvalue()
                self.assertNotIn(self.private, emitted)
                self.assertNotIn(self.token, emitted)
                self.assertNotIn(diagnostic, emitted)
                self.assertNotIn("push", body["next"])

    def test_unknown_connection_hint_is_safe_and_conditional(self) -> None:
        diagnostic = "Failed to connect to github.com port 443: Couldn't connect to server"
        failure = self.refusal("ls-remote", diagnostic)
        self.unknown(failure)
        self.assertIn("sandbox", str(failure).lower())
        self.assertRegex(str(failure).lower(), r"\b(?:may|might|possible)\b")
        self.assertNotIn(diagnostic, str(failure))


if __name__ == "__main__":
    unittest.main()
