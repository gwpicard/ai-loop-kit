"""Setup requires a real remote main commit before questions or founding."""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit/scripts"))

from loop import cli  # noqa: E402


def setup_module() -> Any:
    spec = importlib.util.spec_from_file_location("preflight_setup", ROOT / "kit/scripts/setup.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SetupPreflightTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="setup-preflight-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.project = self.base / "person's project"
        self.remote = self.base / "origin.git"
        self.scratch = self.base / "verification"
        self.scratch.mkdir()
        self.config = self.base / "gitconfig"
        self.config.write_text("")
        self.real_git = shutil.which("git")
        assert self.real_git is not None
        environment = patch.dict(os.environ, {
            "GIT_CONFIG_GLOBAL": str(self.config), "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "Test Person", "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test Person", "GIT_COMMITTER_EMAIL": "test@example.com",
            "GIT_TERMINAL_PROMPT": "0", "TMPDIR": str(self.scratch),
        })
        environment.start()
        self.addCleanup(environment.stop)
        temporary_root = patch("tempfile.tempdir", str(self.scratch))
        temporary_root.start()
        self.addCleanup(temporary_root.stop)
        self.git(self.base, "init", "--bare", "-b", "main", str(self.remote))
        self.git(self.base, "init", "-b", "work", str(self.project))
        self.git(self.project, "remote", "add", "origin", str(self.remote))
        self.setup = setup_module()
        self.log = self.base / "transport.jsonl"

    def git(self, folder: Path, *args: str) -> str:
        done = subprocess.run([str(self.real_git), "-C", str(folder), *args],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=10, check=True)
        return done.stdout.strip()

    def snapshot(self) -> dict[str, tuple[bytes, int]]:
        return {str(item.relative_to(self.project)): (item.read_bytes(), item.stat().st_mode)
                for item in self.project.rglob("*") if item.is_file()}

    def seed_work(self) -> None:
        staged = self.project / "staged.txt"
        staged.write_text("staged version\n")
        self.git(self.project, "add", "staged.txt")
        staged.write_text("dirty version\n")
        untracked = self.project / "untracked.sh"
        untracked.write_text("#!/bin/sh\nprintf '%s' untouched\n")
        untracked.chmod(0o755)

    def publish_fixture_main(self) -> str:
        # This is the person's action against a local bare fixture, never a real remote.
        self.git(self.project, "commit", "--allow-empty", "--only", "-m", "Initial fixture")
        self.git(self.project, "push", "origin", "HEAD:refs/heads/main")
        return self.git(self.project, "rev-parse", "HEAD")

    def transport(self, mode: str) -> None:
        """Keep origin identity visible; rewrite only local test transport calls."""
        folder = self.base / "bin"
        folder.mkdir()
        wrapper = folder / "git"
        wrapper.write_text("#!" + sys.executable + "\n" + '''import json, os, subprocess, sys
from pathlib import Path
args = sys.argv[1:]
mode = os.environ['FIELD3_MODE']
query = 'ls-remote' in args
fetch = 'fetch' in args
if query or fetch or 'cat-file' in args or 'init' in args:
    with Path(os.environ['FIELD3_LOG']).open('a') as stream:
        stream.write(json.dumps({'args': args, 'pid': os.getpid()}) + '\\n')
if query:
    oid = os.environ['FIELD3_OID']
    if mode == 'query-error':
        print('private-url-must-not-leak', file=sys.stderr)
        raise SystemExit(128)
    if mode == 'malformed':
        print('not-an-object\\trefs/heads/main')
        raise SystemExit(0)
    if mode == 'duplicate':
        print((oid + '\\trefs/heads/main\\n') * 2, end='')
        raise SystemExit(0)
    if mode == 'wrong-ref':
        print(oid + '\\trefs/heads/other')
        raise SystemExit(0)
    if mode == 'extra-field':
        print(oid + '\\trefs/heads/main\\textra')
        raise SystemExit(0)
    if mode == 'noncommit':
        print(oid + '\\trefs/heads/main')
        raise SystemExit(0)
if fetch and mode == 'fetch-error':
    print('private-url-must-not-leak', file=sys.stderr)
    raise SystemExit(128)
if fetch and mode == 'wrong-fetch':
    raise SystemExit(0)
if query:
    args = [os.environ['FIELD3_REMOTE']
            if item in ('origin', os.environ['FIELD3_ADDRESS']) else item for item in args]
if fetch:
    args = [os.environ['FIELD3_REMOTE'] if item == os.environ['FIELD3_ADDRESS'] else item
            for item in args]
result = subprocess.run([os.environ['FIELD3_REAL_GIT'], *args], check=False)
raise SystemExit(result.returncode)
''')
        wrapper.chmod(0o755)
        variables = {"PATH": str(folder) + os.pathsep + os.environ["PATH"],
                     "FIELD3_MODE": mode, "FIELD3_LOG": str(self.log),
                     "FIELD3_REAL_GIT": str(self.real_git), "FIELD3_REMOTE": str(self.remote),
                     "FIELD3_ADDRESS": str(self.remote),
                     "FIELD3_OID": self.git(self.project, "rev-parse", "HEAD")}
        environment = patch.dict(os.environ, variables)
        environment.start()
        self.addCleanup(environment.stop)

    def refusal(self) -> cli.Failure:
        before = self.snapshot()
        with self.assertRaises(cli.Failure) as caught:
            self.setup.check_origin(self.project, False)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(self.scratch.iterdir()), [], "verification scratch must be cleaned")
        self.assertIn(caught.exception.code, (cli.ExitCode.REFUSED, cli.ExitCode.ENVIRONMENT))
        self.assertNotIn("private-url-must-not-leak", str(caught.exception))
        return caught.exception

    def test_found_empty_remote_stops_before_version_preparation(self) -> None:
        self.seed_work()
        before = self.snapshot()
        parser = argparse.ArgumentParser()
        self.setup.setup(parser)
        args = parser.parse_args(["found", "--project", str(self.project), "--dry-run",
                                  "--development", "--kit-ref", "a" * 40])
        with patch.object(self.setup, "check_tooling", return_value=False), \
                patch.object(self.setup.versions, "prepare",
                             side_effect=RuntimeError("version preparation reached")) as prepare:
            observed: Exception | None = None
            try:
                self.setup.step_found(args)
            except (cli.Failure, RuntimeError) as error:
                observed = error
        self.assertFalse(prepare.called, "FIELD3: absent main must stop before version preparation")
        self.assertIsInstance(observed, cli.Failure)
        self.assertEqual(self.snapshot(), before)

    def test_empty_remote_refuses_without_touching_person_work(self) -> None:
        self.seed_work()
        failure = self.refusal()
        self.assertIn("--allow-empty --only", failure.next_command)
        self.assertIn("HEAD:refs/heads/main", failure.next_command)
        self.assertIn("&&", failure.next_command)

    def test_missing_origin_has_runnable_person_prompt(self) -> None:
        self.git(self.project, "remote", "remove", "origin")
        failure = self.refusal()
        self.assertIn("IFS= read -r field_origin_address", failure.next_command)
        self.assertIn('test -n "$field_origin_address"', failure.next_command)
        self.assertIn('remote add -- origin "$field_origin_address"', failure.next_command)
        self.assertNotIn("<", failure.next_command)
        done = subprocess.run(["sh", "-c", failure.next_command], input="\n",
                              capture_output=True, text=True, timeout=5, check=False)
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(self.git(self.project, "remote"), "")
        done = subprocess.run(["sh", "-c", failure.next_command],
                              input=str(self.remote) + "\n", capture_output=True,
                              text=True, timeout=5, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.git(self.project, "remote", "get-url", "origin"), str(self.remote))

    def test_person_empty_commit_command_preserves_index_dirty_and_modes(self) -> None:
        self.seed_work()
        cached = self.git(self.project, "diff", "--cached", "--binary")
        work = {p.name: (p.read_bytes(), p.stat().st_mode)
                for p in self.project.iterdir() if p.is_file()}
        failure = self.refusal()
        done = subprocess.run(["sh", "-c", failure.next_command], stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=10, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.git(self.project, "ls-tree", "HEAD"), "")
        self.assertEqual(self.git(self.project, "diff", "--cached", "--binary"), cached)
        self.assertEqual({p.name: (p.read_bytes(), p.stat().st_mode)
                          for p in self.project.iterdir() if p.is_file()}, work)
        self.assertEqual(self.git(self.remote, "rev-parse", "main"),
                         self.git(self.project, "rev-parse", "HEAD"))

    def test_person_refusing_hook_prevents_push(self) -> None:
        hook = self.project / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        failure = self.refusal()
        done = subprocess.run(["sh", "-c", failure.next_command], stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=10, check=False)
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(self.git(self.remote, "for-each-ref", "refs/heads"), "")

    def test_person_failed_push_is_not_successful_initialisation(self) -> None:
        hook = self.remote / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        failure = self.refusal()
        done = subprocess.run(["sh", "-c", failure.next_command], stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=10, check=False)
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(self.git(self.remote, "for-each-ref", "refs/heads"), "")

    def test_existing_history_has_truthful_person_push_command(self) -> None:
        self.git(self.project, "commit", "--allow-empty", "--only", "-m", "Existing history")
        self.git(self.project, "push", "origin", "HEAD:refs/heads/other")
        other = self.git(self.remote, "rev-parse", "other")
        failure = self.refusal()
        self.assertIn("HEAD:refs/heads/main", failure.next_command)
        self.assertNotIn("--allow-empty", failure.next_command)
        self.assertEqual(self.git(self.remote, "rev-parse", "other"), other)

    def test_remote_commit_verified_without_project_writes(self) -> None:
        oid = self.publish_fixture_main()
        self.seed_work()
        before = self.snapshot()
        self.transport("normal")
        self.setup.check_origin(self.project, False)
        calls = [json.loads(line)["args"] for line in self.log.read_text().splitlines()]
        fetch = [args for args in calls if "fetch" in args]
        self.assertEqual(len(fetch), 1, "FIELD3: advertisement alone is not commit verification")
        self.assertIn(oid, fetch[0], "retrieve exact advertised object, not moving main")
        self.assertTrue(any("cat-file" in args and oid in args for args in calls))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_unknown_or_invalid_remote_never_suggests_main_push(self) -> None:
        self.publish_fixture_main()
        for mode in ("query-error", "malformed", "duplicate", "wrong-ref", "extra-field",
                     "fetch-error", "wrong-fetch"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(dir=self.base) as folder:
                # A distinct wrapper per case; keep the existing fixture commit and refs.
                previous = self.base
                self.base = Path(folder)
                try:
                    self.transport(mode)
                    failure = self.refusal()
                    self.assertIn("preflight", failure.next_command)
                    self.assertNotIn("push", failure.next_command)
                    self.assertNotIn("commit --", failure.next_command)
                finally:
                    self.base = previous

    def test_blob_advertisement_is_not_a_commit(self) -> None:
        self.publish_fixture_main()
        blob_file = self.base / "blob"
        blob_file.write_text("not a commit\n")
        blob = self.git(self.remote, "hash-object", "-w", str(blob_file))
        self.git(self.remote, "update-ref", "refs/tags/blob", blob)
        self.transport("noncommit")
        with patch.dict(os.environ, {"FIELD3_OID": blob}):
            failure = self.refusal()
        self.assertNotIn("push", failure.next_command)
        self.assertIn("preflight", failure.next_command)

    def test_query_and_fetch_timeouts_reap_owned_process_and_clean_scratch(self) -> None:
        self.publish_fixture_main()
        original = subprocess.Popen.communicate
        for command, required_timeout in (("ls-remote", 20), ("fetch", 30)):
            children: list[subprocess.Popen[Any]] = []
            def interrupted(child: subprocess.Popen[Any], *args: Any,
                            command: str = command, required_timeout: int = required_timeout,
                            children: list[subprocess.Popen[Any]] = children,
                            **kwargs: Any) -> Any:
                assert isinstance(child.args, (list, tuple))
                if command in child.args and child not in children:
                    children.append(child)
                    self.assertEqual(kwargs.get("timeout"), required_timeout)
                    raise subprocess.TimeoutExpired(child.args, required_timeout)
                return original(child, *args, **kwargs)
            with self.subTest(command=command), patch.object(subprocess.Popen, "communicate",
                                                             new=interrupted):
                failure = self.refusal()
            self.assertTrue(children, "FIELD3: required remote operation did not run")
            self.assertTrue(all(child.poll() is not None for child in children))
            self.assertIn("preflight", failure.next_command)
            self.assertNotIn("push", failure.next_command)

    def test_verification_uses_closed_stdin_and_bounded_inspection(self) -> None:
        self.publish_fixture_main()
        initialise = subprocess.Popen.__init__
        communicate = subprocess.Popen.communicate
        stages: list[str] = []
        inspected: list[str] = []
        def started(child: subprocess.Popen[Any], args: Any, *rest: Any,
                    **kwargs: Any) -> None:
            for name in ("ls-remote", "fetch", "init", "cat-file"):
                if name in args:
                    self.assertEqual(kwargs.get("stdin"), subprocess.DEVNULL)
                    stages.append(name)
            initialise(child, args, *rest, **kwargs)
        def waited(child: subprocess.Popen[Any], *args: Any, **kwargs: Any) -> Any:
            assert isinstance(child.args, (list, tuple))
            for name in ("init", "cat-file"):
                if name in child.args:
                    self.assertEqual(kwargs.get("timeout"), 5)
                    inspected.append(name)
            return communicate(child, *args, **kwargs)
        with patch.object(subprocess.Popen, "__init__", new=started), \
                patch.object(subprocess.Popen, "communicate", new=waited):
            self.setup.check_origin(self.project, False)
        self.assertEqual(set(stages), {"ls-remote", "fetch", "init", "cat-file"})
        self.assertEqual(set(inspected), {"init", "cat-file"})
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_fetch_url_cannot_become_an_option(self) -> None:
        self.publish_fixture_main()
        self.transport("normal")
        self.git(self.project, "remote", "set-url", "--", "origin", "-field3-origin")
        before = self.snapshot()
        with patch.object(self.setup, "origin_git", wraps=self.setup.origin_git) as verify, \
                self.assertRaises(cli.Failure):
            self.setup.check_origin(self.project, False)
        verify.assert_not_called()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.log.exists(), "unsupported origin reached the verifier")
        address = str(self.remote.resolve())
        self.git(self.project, "remote", "set-url", "origin", address)
        with patch.dict(os.environ, {"FIELD3_ADDRESS": address}):
            self.setup.check_origin(self.project, False)
        calls = [json.loads(line)["args"] for line in self.log.read_text().splitlines()]
        fetches = [args for args in calls if "fetch" in args]
        self.assertEqual(len(fetches), 1)
        self.assertIn("--", fetches[0])
        self.assertLess(fetches[0].index("--"), fetches[0].index(address))

    def test_preflight_cli_checks_before_acquisition(self) -> None:
        commit = self.publish_fixture_main()
        before = self.snapshot()
        output = io.StringIO()
        with patch.object(self.setup, "check_tooling", return_value=False), \
                patch.object(self.setup.versions, "prepare") as prepare, \
                contextlib.redirect_stdout(output), \
                contextlib.redirect_stderr(io.StringIO()):
            try:
                code = self.setup.main(["--json", "preflight", "--project", str(self.project)])
            except SystemExit as error:
                code = error.code
        self.assertEqual(code, 0, "FIELD3: opening preflight command must accept committed main")
        body = json.loads(output.getvalue())
        self.assertTrue(body["ok"])
        self.assertTrue(body["read_only"])
        self.assertEqual(body["origin_main"], "verified commit")
        self.assertEqual(body["project"], str(self.project.resolve()))
        self.assertEqual(body["main_commit"], commit)
        prepare.assert_not_called()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(self.scratch.iterdir()), [])

        alias = self.base / "project alias"
        alias.symlink_to(self.project, target_is_directory=True)
        output = io.StringIO()
        with patch.object(self.setup, "check_tooling", return_value=False), \
                patch.object(self.setup.versions, "prepare") as prepare, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code = self.setup.main(["--json", "preflight", "--project", str(alias)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["project"], str(self.project.resolve()))
        self.assertEqual(json.loads(output.getvalue())["main_commit"], commit)
        prepare.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_direct_found_rechecks_origin_after_successful_preflight(self) -> None:
        self.publish_fixture_main()
        self.seed_work()
        with patch.object(self.setup, "check_tooling", return_value=False):
            result = self.setup.step_preflight(argparse.Namespace(project=str(self.project)))
        self.assertEqual(result["origin_main"], "verified commit")
        empty = self.base / "different empty origin.git"
        self.git(self.base, "init", "--bare", "-b", "main", str(empty))
        self.git(self.project, "remote", "set-url", "origin", str(empty))
        # Pasted or stored output is data, never a way to skip the fresh check.
        (self.project / "preflight-result.json").write_text(json.dumps(result))
        before = self.snapshot()
        parser = argparse.ArgumentParser()
        self.setup.setup(parser)
        args = parser.parse_args(["found", "--project", str(self.project), "--dry-run",
                                  "--development", "--kit-ref", "a" * 40])
        with patch.object(self.setup, "check_tooling", return_value=False), \
                patch.object(self.setup.versions, "prepare") as prepare, \
                self.assertRaises(cli.Failure) as raised:
            self.setup.step_found(args)
        self.assertIn("origin has no main", str(raised.exception))
        prepare.assert_not_called()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_found_metadata_identifies_fresh_main_and_actual_write_mode(self) -> None:
        commit = self.publish_fixture_main()
        self.seed_work()
        kit = self.base / "installed-plugin"
        shutil.copytree(ROOT / "kit", kit,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "version.json"))
        spec = importlib.util.spec_from_file_location(
            "found_metadata_release_fixture", ROOT / "tests/lib/version-fixture.py")
        assert spec is not None and spec.loader is not None
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        parser = argparse.ArgumentParser()
        self.setup.setup(parser)
        with patch.dict(os.environ, {"AI_LOOP_KIT_DATA": str(self.base / "data")}):
            release = fixture.release(kit, self.project, publish=False)
            self.assertNotEqual(commit, release.commit,
                                "project main metadata must not use the kit release SHA")
            for dry_run in (True, False):
                arguments = ["found", "--project", str(self.project), "--kit-dir", str(kit),
                             "--language", "python", "--test-command", "true"]
                if dry_run:
                    arguments.append("--dry-run")
                args = parser.parse_args(arguments)
                before = self.snapshot()
                prepared = dataclasses.replace(release, dry_run=dry_run)
                with self.subTest(dry_run=dry_run), \
                        patch.object(self.setup, "check_tooling", return_value=False), \
                        patch.object(self.setup.versions, "prepare", return_value=prepared):
                    result = self.setup.step_found(args)
                    self.assertEqual(result["project"], str(self.project.resolve()))
                    self.assertEqual(result["main_commit"], commit)
                    self.assertEqual(result["origin_main"], "verified commit")
                    self.assertIs(result["read_only"], dry_run)
                    self.assertEqual(result["kit_revision"], release.commit)
                    if dry_run:
                        self.assertEqual(self.snapshot(), before)
                        self.assertFalse(release.path.exists())
                    else:
                        self.assertTrue((self.project / "AGENTS.md").exists())
                        self.assertTrue(release.path.exists())
                self.assertEqual(list(self.scratch.iterdir()), [])

    def test_own_origin_stops_before_remote_contact(self) -> None:
        with patch.object(self.setup, "git_out", return_value="https://example.test/kit.git"), \
                patch.object(self.setup.subprocess, "run") as run, \
                patch.object(self.setup.subprocess, "Popen") as popen, \
                self.assertRaises(cli.Failure):
            self.setup.check_origin(self.project, True)
        run.assert_not_called()
        popen.assert_not_called()


    def test_verifier_discards_caller_git_routing_and_local_configuration(self) -> None:
        injected = {
            "GIT_DIR": "/synthetic/project/.git",
            "GIT_WORK_TREE": "/synthetic/project",
            "GIT_COMMON_DIR": "/synthetic/common",
            "GIT_INDEX_FILE": "/synthetic/index",
            "GIT_OBJECT_DIRECTORY": "/synthetic/objects",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": "/synthetic/alternates",
            "GIT_CONFIG": "/synthetic/local-config",
            "GIT_CONFIG_PARAMETERS": "'credential.helper=synthetic-helper'",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.sshCommand",
            "GIT_CONFIG_VALUE_0": "synthetic-ssh",
            "GIT_CONFIG_KEY_9": "credential.helper",
            "GIT_CONFIG_VALUE_9": "synthetic-helper",
            "GIT_CONFIG_GLOBAL": "/synthetic/person-global",
            "GIT_CONFIG_SYSTEM": "/synthetic/trusted-system",
        }
        with patch.dict(os.environ, injected), \
                patch.object(self.setup.subprocess, "Popen") as start:
            start.return_value.communicate.return_value = ("", "")
            start.return_value.returncode = 0
            self.setup.origin_git(self.scratch, ["init", "--quiet"], 5)
        environment = start.call_args.kwargs["env"]
        for name in injected:
            if name in {"GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM"}:
                self.assertEqual(environment[name], injected[name])
            else:
                self.assertFalse(name in environment,
                                 "caller Git state reached clean verifier: " + name)
        self.assertEqual(environment["GIT_TERMINAL_PROMPT"], "0")

    def test_origin_query_does_not_use_project_credential_helper(self) -> None:
        self.publish_fixture_main()
        marker = self.base / "credential-helper-ran"
        helper = self.base / "credential-helper.py"
        helper.write_text("from pathlib import Path\nPath(" + repr(str(marker)) +
                          ").write_text('unexpected credential access')\n")
        configured = "!" + str(sys.executable) + " " + str(helper)
        self.git(self.project, "config", "credential.helper", configured)
        original = self.setup.origin_git
        query_folders: list[Path] = []

        def checked_origin(folder: Path, arguments: list[str], limit: int,
                           **kwargs: Any) -> subprocess.CompletedProcess[str]:
            if "ls-remote" in arguments:
                query_folders.append(folder.resolve())
                # A deterministic stand-in makes consulting project-local credentials visible.
                local_helper = (self.git(folder, "config", "--local", "--get-all",
                                         "credential.helper")
                                if folder.resolve() == self.project.resolve() else "")
                if local_helper:
                    subprocess.run([str(sys.executable), str(helper)],
                                   stdin=subprocess.DEVNULL, check=True, timeout=5)
            return cast(subprocess.CompletedProcess[str],
                        original(folder, arguments, limit, **kwargs))

        with patch.object(self.setup, "origin_git", side_effect=checked_origin):
            self.setup.check_origin(self.project, False)
        self.assertEqual(len(query_folders), 1)
        self.assertNotEqual(query_folders[0], self.project.resolve())
        self.assertFalse(marker.exists(), "project credential helper was consulted")
        self.assertEqual(list(self.scratch.iterdir()), [])


    def test_external_origin_helper_is_refused_before_its_sentinel(self) -> None:
        marker = self.base / "ext-helper-ran"
        helper = self.base / "remote-helper.sh"
        helper.write_text("#!/bin/sh\nprintf hit > '" + str(marker) + "'\nexit 1\n")
        helper.chmod(0o755)
        self.git(self.base, "config", "--global", "protocol.ext.allow", "always")
        self.git(self.project, "remote", "set-url", "origin", "ext::" + str(helper))
        before = self.snapshot()
        with self.assertRaises(cli.Failure):
            self.setup.check_origin(self.project, False)
        self.assertFalse(marker.exists(), "origin launched its external helper")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_custom_helper_and_trusted_url_rewrite_cannot_escape_finite_protocols(self) -> None:
        marker = self.base / "custom-helper-ran"
        executables = self.base / "git-exec"
        executables.mkdir()
        helper = executables / "git-remote-synthetic"
        helper.write_text("#!/bin/sh\nprintf hit > '" + str(marker) + "'\nexit 1\n")
        helper.chmod(0o755)
        self.git(self.base, "config", "--global", "protocol.synthetic.allow", "always")
        for rewritten in (False, True):
            with self.subTest(rewritten=rewritten):
                marker.unlink(missing_ok=True)
                address = "https://synthetic.invalid/project" if rewritten else "synthetic::project"
                self.git(self.project, "remote", "set-url", "origin", address)
                if rewritten:
                    self.git(self.base, "config", "--global", "url.synthetic::.insteadOf",
                             "https://synthetic.invalid/")
                with patch.dict(os.environ, {"GIT_EXEC_PATH": str(executables),
                                             "GIT_ALLOW_PROTOCOL": "synthetic"}), \
                        self.assertRaises(cli.Failure):
                    self.setup.check_origin(self.project, False)
                self.assertFalse(marker.exists(), "rewritten/custom origin launched helper")
                self.assertEqual(list(self.scratch.iterdir()), [])

    def test_local_source_uploadpack_configuration_does_not_execute_hook(self) -> None:
        commit = self.publish_fixture_main()
        marker = self.base / "uploadpack-hook-ran"
        helper = self.base / "pack-hook.sh"
        helper.write_text("#!/bin/sh\nprintf hit > '" + str(marker) + "'\nexit 1\n")
        helper.chmod(0o755)
        self.git(self.remote, "config", "uploadpack.packObjectsHook", str(helper))
        with patch.dict(os.environ, {"GIT_NO_LAZY_FETCH": "0"}):
            self.assertEqual(self.setup.check_origin(self.project, False), commit)
        self.assertFalse(marker.exists(), "local source upload-pack executed its hook")
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_verifier_pins_protocols_exec_path_and_no_lazy_fetch(self) -> None:
        with patch.dict(os.environ, {"GIT_EXEC_PATH": "/synthetic/exec",
                                     "GIT_ALLOW_PROTOCOL": "ext:synthetic",
                                     "GIT_NO_LAZY_FETCH": "0"}), \
                patch.object(self.setup.subprocess, "Popen") as start:
            start.return_value.communicate.return_value = ("", "")
            start.return_value.returncode = 0
            self.setup.origin_git(self.scratch, ["init", "--quiet"], 5)
        environment = start.call_args.kwargs["env"]
        self.assertFalse("GIT_EXEC_PATH" in environment, "exec-path injection reached verifier")
        self.assertEqual(environment["GIT_ALLOW_PROTOCOL"], "https:ssh:file")
        self.assertEqual(environment["GIT_PROTOCOL_FROM_USER"], "0")
        self.assertEqual(environment["GIT_NO_LAZY_FETCH"], "1")
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], str(self.config))

if __name__ == "__main__":
    unittest.main()
