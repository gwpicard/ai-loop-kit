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
        self.base = Path(temporary.name).resolve()
        self.project = self.base / "person's project"
        self.project.mkdir()
        subprocess.run(["git", "init", "-q", str(self.project)], check=True,
                       capture_output=True)
        self.setup = setup_module()
        self.oid = "a" * 40
        self.origin = "https://example.test/private-project.git"
        self.private = "https://person:credential-must-not-leak@example.test/private"
        self.token = "synthetic-token-must-not-leak"

    def retry(self) -> str:
        return ('python3 -I "' + str(self.setup.HERE / "setup.py") + '" preflight --project '
                + shlex.quote(str(self.project.resolve())))

    def operation(self, stage: str, diagnostic: str, code: int = 128) -> Any:
        def run(folder: Path, arguments: list[str], timeout: int, **kwargs: Any) -> Any:
            del folder, timeout, kwargs
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


    def test_settings_exclusions_name_exact_isolated_nonexecuting_subcommands(self) -> None:
        merge = self.setup.load_module("exclusion_merge", self.setup.HERE / "merge-settings.py")
        kit = ROOT / "kit"
        result = self.setup.prepare_settings(self.project, kit, merge)
        sandbox = json.loads(result["text"])["sandbox"]
        setup = 'python3 -I "' + str(kit.resolve() / "scripts/setup.py") + '" '
        gate = 'python3 -I "' + str(kit.resolve() / "scripts/gate.py") + '" '
        expected = {setup + verb + " *" for verb in
                    ("preflight", "found", "first-piece", "github labels", "github issue")}
        expected.update(gate + verb + " *" for verb in
                        ("capture", "report", "spec", "answer", "comment", "drop",
                         "labels", "move-record"))
        self.assertEqual(set(sandbox["excludedCommands"]), expected)
        self.assertTrue(sandbox["enabled"])
        self.assertTrue(sandbox["failIfUnavailable"])
        self.assertFalse(sandbox["allowUnsandboxedCommands"])
        self.assertIn(str(kit.resolve()), sandbox["filesystem"]["denyWrite"])
        builder = json.loads((kit / "templates/builder-settings.json").read_text())
        self.assertFalse(builder["sandbox"].get("excludedCommands"))

    def first_piece_arguments(self, commit: str) -> Any:
        parser = self.setup.cli.make_parser("setup", "fixture", changes_state=True)
        self.setup.setup(parser)
        return parser.parse_args(["first-piece", "--project", str(self.project),
                                  "--development", "--kit-ref", commit,
                                  "--test-command", "true"])

    def test_first_piece_accepts_matching_development_selector(self) -> None:
        args = self.first_piece_arguments(self.oid)
        with patch.object(self.setup.versions, "prepare") as acquire, \
                patch.object(self.setup.versions, "load",
                          return_value={"mode": "development", "commit": self.oid}) as load, \
                patch.object(self.setup.versions, "verify") as verify, \
                patch.object(self.setup, "sync_scaffold_command") as scaffold, \
                patch.object(self.setup.bootstrap, "check"), \
                patch.object(self.setup, "run_gate", return_value={"piece": 1}) as gate:
            result = self.setup.step_first_piece(args)
        self.assertTrue(result["captured"])
        acquire.assert_not_called()
        load.assert_called_once()
        verify.assert_called_once()
        scaffold.assert_called_once()
        gate.assert_called_once()

    def test_first_piece_mismatched_or_invalid_selector_refuses_before_mutation(self) -> None:
        for commit in ("b" * 40, "main", "a" * 7):
            with self.subTest(commit=commit), \
                    patch.object(self.setup.versions, "prepare") as acquire, \
                    patch.object(self.setup.versions, "load", return_value={
                        "mode": "development", "commit": self.oid}), \
                    patch.object(self.setup.versions, "verify"), \
                    patch.object(self.setup, "sync_scaffold_command") as scaffold, \
                    patch.object(self.setup, "run_gate") as gate, \
                    self.assertRaises(cli.Failure):
                self.setup.step_first_piece(self.first_piece_arguments(commit))
            acquire.assert_not_called()
            scaffold.assert_not_called()
            gate.assert_not_called()



    def test_first_piece_default_release_route_keeps_existing_verified_selection(self) -> None:
        parser = self.setup.cli.make_parser("setup", "fixture", changes_state=True)
        self.setup.setup(parser)
        args = parser.parse_args(["first-piece", "--project", str(self.project),
                                  "--test-command", "true"])
        with patch.object(self.setup.versions, "prepare") as acquire, \
                patch.object(self.setup.versions, "load", return_value={
                    "version": "0.1.0", "tag": "v0.1.0", "commit": self.oid}) as load, \
                patch.object(self.setup.versions, "verify") as verify, \
                patch.object(self.setup, "sync_scaffold_command"), \
                patch.object(self.setup.bootstrap, "check"), \
                patch.object(self.setup, "run_gate", return_value={"piece": 1}):
            result = self.setup.step_first_piece(args)
        self.assertTrue(result["captured"])
        acquire.assert_not_called()
        load.assert_not_called()
        verify.assert_not_called()



    def test_move_record_alias_only_delegates_safe_targets(self) -> None:
        gate = self.setup.load_module("record_move_gate", self.setup.HERE / "gate.py")
        for target in ("shaping", "dropped", "approval"):
            output = io.StringIO()
            with self.subTest(target=target), patch.object(gate, "_paths"), \
                    patch.object(gate.github, "GitHub"), \
                    patch.object(gate.moves, "Gate") as constructor, \
                    contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                constructor.return_value.move.return_value = {"to": target}
                code = gate.main(["--json", "move-record", "3", target, "--reason", "fixture"])
                self.assertEqual(code, 0)
                constructor.return_value.move.assert_called_once_with(
                    3, target, reason="fixture", options={}, dry_run=False)
                self.assertEqual(json.loads(output.getvalue())["to"], target)

    def test_move_record_rejects_judge_targets_before_move_dispatch(self) -> None:
        import argparse

        gate = self.setup.load_module("invalid_record_move_gate", self.setup.HERE / "gate.py")
        for target in ("ready", "building", "review", "done"):
            args = argparse.Namespace(command="move-record", number=3, target=target,
                                      reason="fixture", option=[], dry_run=False)
            with self.subTest(target=target), patch.object(gate, "_paths"), \
                    patch.object(gate.github, "GitHub"), \
                    patch.object(gate.moves, "Gate") as constructor, \
                    self.assertRaises(cli.Failure):
                gate.handle(args)
            constructor.return_value.move.assert_not_called()
            with patch.object(gate, "handle") as handler, \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                code = gate.main(["--json", "move-record", "3", target])
            self.assertNotEqual(code, 0)
            handler.assert_not_called()


    def test_merge_settings_cli_and_setup_refuse_unsafe_roots_without_changes(self) -> None:
        import shutil

        merge = self.setup.load_module("literal_root_merge", self.setup.HERE / "merge-settings.py")
        for marker in ("*", "?", "[", '"', "$", "`", "\\", "\n"):
            with self.subTest(marker=repr(marker)), \
                    tempfile.TemporaryDirectory(dir=self.base) as folder:
                case = Path(folder)
                unsafe = case / ("plugin" + marker + "root")
                shutil.copytree(ROOT / "kit/templates", unsafe / "templates")
                target = case / "settings.json"
                target.write_text('{"person_rule":"keep"}\n')
                target.chmod(0o640)
                untouched = case / "unrelated.txt"
                untouched.write_text("person work\n")
                before = (target.read_bytes(), target.stat().st_mode, untouched.read_bytes())
                result = subprocess.run([
                    sys.executable, "-I", str(self.setup.HERE / "merge-settings.py"),
                    str(ROOT / "kit/templates/claude-settings.json"), str(target),
                    "--set", "KIT_DIR=" + str(unsafe),
                ], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                   timeout=10, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((target.read_bytes(), target.stat().st_mode,
                                  untouched.read_bytes()), before)
                with self.assertRaises(cli.Failure):
                    self.setup.prepare_settings(self.project, unsafe, merge)
                safe = case / "safe-plugin"
                shutil.copytree(ROOT / "kit/templates", safe / "templates")
                unsafe_alias = case / ("alias" + marker + "root")
                unsafe_alias.symlink_to(safe, target_is_directory=True)
                canonical_alias = case / "plain-plugin"
                canonical_alias.symlink_to(unsafe, target_is_directory=True)
                for selected in (unsafe_alias, canonical_alias):
                    with self.subTest(selected=selected.name):
                        result = subprocess.run([
                            sys.executable, "-I", str(self.setup.HERE / "merge-settings.py"),
                            str(ROOT / "kit/templates/claude-settings.json"), str(target),
                            "--set", "KIT_DIR=" + str(selected),
                        ], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=10, check=False)
                        self.assertNotEqual(result.returncode, 0)
                        self.assertEqual((target.read_bytes(), target.stat().st_mode,
                                          untouched.read_bytes()), before)
                        with self.assertRaises(cli.Failure):
                            self.setup.prepare_settings(self.project, selected, merge)
        plain = self.base / "person's plugin with spaces"
        shutil.copytree(ROOT / "kit/templates", plain / "templates")
        result = self.setup.prepare_settings(self.project, plain, merge)
        self.assertIn(str(plain.resolve()), result["text"])


if __name__ == "__main__":
    unittest.main()
