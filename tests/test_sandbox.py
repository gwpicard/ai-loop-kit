"""Checks for the strict session sandbox and unattended run record."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from helpers import git

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kit" / "scripts"))

import agents
import loopkit
import review
import run
import sandbox
import walkaway


class SandboxTest(unittest.TestCase):
    def test_walkaway_review_session_accepts_a_completed_session(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "build"
            folder.mkdir()
            logfile = root / "review.log"
            event = json.dumps({"type": "result", "is_error": False, "result": "ok"})
            process = subprocess.Popen(
                [sys.executable, "-c", f"print({event!r})"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
            with patch.object(review.agents, "start_session", return_value=process):
                status = review._review_session(folder, "brief", logfile, [], 5,
                                               walk_away=True, domains=["pypi.org"])

        self.assertEqual(status, "")

    def test_review_keeps_research_when_walkaway_controls_are_forwarded(self):
        body = ("## Research\n- R1: The API supports batching "
                "(source: https://example.test/api, read: 2026-10-15)\n")
        issue = {"body": body}
        with patch.object(review, "review_piece", return_value={}) as reviewer:
            run.review_piece(Path("/repo"), Path("/repo/build"), 4, 1,
                             issue, {"research": []}, True, ["pypi.org"])
        reviewer.assert_called_once_with(Path("/repo"), Path("/repo/build"), 4, 1,
                                         issue, {"research": []}, True, ["pypi.org"])
        self.assertIn("R1: The API supports batching", review.contract_research(body))

    def test_version_gate_requires_221285(self):
        self.assertTrue(sandbox.version_ok("2.1.289 (Claude Code)"))
        self.assertFalse(sandbox.version_ok("2.1.284"))
        self.assertFalse(sandbox.version_ok("unknown"))

    def test_settings_are_session_scoped_and_restrict_domains_and_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = sandbox.settings_for(root, ["pypi.org"])
        sandbox_settings = settings["sandbox"]
        self.assertTrue(sandbox_settings["enabled"])
        self.assertTrue(sandbox_settings["failIfUnavailable"])
        self.assertFalse(sandbox_settings["allowUnsandboxedCommands"])
        self.assertEqual(sandbox_settings["network"]["allowedDomains"], ["pypi.org"])
        self.assertTrue(sandbox_settings["network"]["strictAllowlist"])
        self.assertEqual({entry["name"] for entry in
                          sandbox_settings["credentials"]["envVars"]},
                         {"GITHUB_TOKEN", "GH_TOKEN", "NPM_TOKEN"})
        self.assertTrue(settings["permissions"]["blockReadsOutsideWorkingDirectories"])

    def test_settings_deny_project_env_files_and_configured_secret_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".env").touch()
            (root / ".env.local").touch()
            (root / ".env.example").touch()
            (root / "private").mkdir()
            (root / "AGENTS.md").write_text(
                "## The loop\nSecret paths: private/keys.json\n")
            settings = sandbox.settings_for(root)
        denied = settings["sandbox"]["filesystem"]["denyRead"]
        self.assertIn(str((root / ".env").resolve()), denied)
        self.assertIn(str((root / ".env.local").resolve()), denied)
        self.assertNotIn(str((root / ".env.example").resolve()), denied)
        self.assertIn(str((root / "private" / "keys.json").resolve()), denied)

    def test_codex_walkaway_session_applies_secret_path_denials(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            git(root, "init", "--quiet")
            (root / "AGENTS.md").write_text(
                "## The loop\nSecret paths: private/keys.json\n")
            with patch.object(loopkit, "project_root", return_value=root), \
                 patch.dict("os.environ", {"PATH": "/usr/bin"}, clear=True), \
                 patch.object(agents.subprocess, "Popen") as popen:
                agents.start_session("codex", "brief", root, role="builder",
                                     walk_away=True)

        args = popen.call_args.args[0]
        self.assertNotIn("--sandbox", args)
        configs = [args[index + 1] for index, value in enumerate(args[:-1])
                   if value == "--config"]
        profile = " ".join(configs)
        self.assertIn('default_permissions="ai-loop"', profile)
        self.assertIn('permissions.ai-loop.extends=":workspace"', profile)
        self.assertIn('".env*"="deny"', profile)
        self.assertIn('".env.example"="read"', profile)
        self.assertIn('"private/keys.json"="deny"', profile)
        self.assertIn("permissions.ai-loop.network.enabled=false", profile)

    def test_builder_environment_drops_secret_shaped_variables(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(loopkit, "project_root", return_value=root), \
                 patch.dict("os.environ", {
                     "PATH": "/usr/bin", "OPENAI_API_KEY": "hidden",
                     "APP_SECRET": "hidden", "DATABASE_URL": "hidden",
                     "PUBLIC_ENDPOINT": "https://example.test",
                     "GIT_CONFIG_KEY_0": "core.autocrlf",
                 }, clear=True), \
                 patch.object(agents.subprocess, "Popen") as popen:
                agents.start_session("codex", "brief", root, role="builder")
                builder_env = popen.call_args.kwargs["env"]
                agents.start_session("codex", "brief", root, role="reviewer")
                reviewer_env = popen.call_args.kwargs["env"]
        for env in (builder_env, reviewer_env):
            self.assertNotIn("OPENAI_API_KEY", env)
            self.assertNotIn("APP_SECRET", env)
            self.assertNotIn("DATABASE_URL", env)
            self.assertEqual(env["PUBLIC_ENDPOINT"], "https://example.test")
            self.assertEqual(env["GIT_CONFIG_KEY_0"], "core.autocrlf")

    def test_preflight_reports_secret_variable_names_without_values(self):
        class GitHub:
            @staticmethod
            def issues_with_label(label):
                return []

        with tempfile.TemporaryDirectory() as temp, \
             patch.dict("os.environ", {
                 "OPENAI_API_KEY": "hidden-value", "DATABASE_URL": "hidden-value",
             }, clear=True), \
             patch.object(walkaway.agents, "selected", return_value="codex"), \
             patch.object(walkaway.subprocess, "run", return_value=type(
                 "Result", (), {"returncode": 0, "stdout": "codex 1", "stderr": ""})()), \
             patch.object(walkaway.shutil, "disk_usage", return_value=type(
                 "Usage", (), {"free": 11 * 1024 ** 3})()), \
             patch.object(sandbox, "codex_probe", return_value=(True, "ok")):
            checks = walkaway.preflight(GitHub(), Path(temp), baseline_checked=True)
        report = next(label for ok, label, _ in checks if "secret-shaped" in label)
        self.assertIn("OPENAI_API_KEY", report)
        self.assertIn("DATABASE_URL", report)
        self.assertNotIn("hidden-value", report)

    def test_file_tool_hook_rejects_paths_outside_build_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inside = root / "src" / "main.py"
            outside = root.parent / "secret.txt"
            self.assertIsNone(sandbox.guard_tool_input("Write", {"file_path": str(inside)}, root))
            self.assertIn("inside the active build folder", sandbox.guard_tool_input(
                "Edit", {"file_path": str(outside)}, root))
            self.assertIsNone(sandbox.guard_tool_input("Bash", {}, root))

    def test_usage_limit_reset_falls_back_to_thirty_minutes(self):
        self.assertTrue(sandbox.usage_limit_event({
            "is_error": True, "result": "API rate limit reached"}))
        self.assertFalse(sandbox.usage_limit_event({"is_error": False, "result": "ok"}))
        self.assertEqual(sandbox.reset_wait_seconds({}), 1800)
        now = datetime.now(timezone.utc)
        later = now.timestamp() + 75
        self.assertLessEqual(sandbox.reset_wait_seconds({"reset_at": later}, now), 75)

    def test_probe_requires_all_five_blocked_shell_statuses(self):
        with tempfile.TemporaryDirectory() as temp:
            response = "\n".join([
                json.dumps({"type": "user", "message": {"content": [{
                    "type": "tool_result", "content":
                    "HOME_WRITE_EXIT:1 READ_EXIT:1 READ_EXIT:1 READ_EXIT:1 NETWORK_EXIT:6"} ]}}),
                json.dumps({"type": "result", "is_error": False}),
            ])
            process = type("Result", (), {"returncode": 0, "stdout": response, "stderr": ""})()
            with patch.object(sandbox, "PROBE_PATH", Path(temp) / "absent"), \
                 patch.object(sandbox.subprocess, "run", return_value=process):
                ok, reason = sandbox.probe(Path(temp), ["pypi.org"])
        self.assertTrue(ok)
        self.assertIn("blocked", reason)

    def test_probe_fails_when_any_boundary_check_succeeds(self):
        with tempfile.TemporaryDirectory() as temp:
            response = json.dumps({"type": "user", "message": {"content": [{
                "type": "tool_result", "content":
                "HOME_WRITE_EXIT:1 READ_EXIT:0 READ_EXIT:1 READ_EXIT:1 NETWORK_EXIT:6"}]}})
            process = type("Result", (), {"returncode": 0, "stdout": response, "stderr": ""})()
            with patch.object(sandbox, "PROBE_PATH", Path(temp) / "absent"), \
                 patch.object(sandbox.subprocess, "run", return_value=process):
                ok, _ = sandbox.probe(Path(temp))
        self.assertFalse(ok)

    def test_walkaway_summary_names_blockers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            started = datetime.now(timezone.utc)
            path = walkaway.write_summary(root, ["piece 4: back to shaping, needs you"],
                                          started, started)
            body = path.read_text()
        self.assertIn("## Decisions made by the run", body)
        self.assertIn("## Blockers", body)
        self.assertIn("piece 4", body)

    def test_walkaway_summary_shows_the_builder_question(self):
        started = datetime.now(timezone.utc)
        question = "Should this limiter use shared storage?"
        body = walkaway.summary_text(
            [f"piece 4: back to shaping, needs-answer: {question}"], started, started)
        self.assertIn(question, body)

    def test_piece_summary_includes_state_timing_and_pull_request(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            started = datetime.now(timezone.utc)
            log = root / ".loop" / "logs" / "piece-4-attempt-1.log"
            log.parent.mkdir(parents=True)
            log.write_text("Attempt timing: " + json.dumps({
                "started_at": started.isoformat(), "elapsed_seconds": 95,
            }) + "\n")
            summary = walkaway.piece_summary(
                root, 4, "piece 4: pull request ready for you: https://github.com/a/b/pull/7",
                "approval", started)
        self.assertIn("state approval", summary)
        self.assertIn("1 attempt(s); 1m 35s", summary)
        self.assertIn("https://github.com/a/b/pull/7", summary)

    def test_stale_heartbeat_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stamp = datetime.fromtimestamp(0, timezone.utc).isoformat()
            path = walkaway.heartbeat_path(root)
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"time": stamp, "piece": 9, "attempt": 2}))
            status = walkaway.heartbeat_status(root)
        self.assertIn("stale", status)
        self.assertIn("piece 9 attempt 2", status)


if __name__ == "__main__":
    unittest.main()
