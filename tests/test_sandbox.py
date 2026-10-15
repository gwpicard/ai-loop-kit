"""Checks for the strict session sandbox and unattended run record."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kit" / "scripts"))

import sandbox
import walkaway
import review
import run


class SandboxTest(unittest.TestCase):
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
