# Intent: before a walk-away run, a sandboxed Claude builder is checked for running kit-python and reading the kit's helper.
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import Project, git

# isort: split
try:
    import sandbox
except ImportError as error:
    if error.name != "sandbox" and not str(error.name).startswith("sandbox."):
        raise
    sandbox = None

import gate
import walkaway


def tool_result(text):
    return json.dumps({"type": "user", "message": {"content": [{
        "type": "tool_result", "content": text}]}})


def run_builder_probe(test, stdout="", timeout=False, returncode=0):
    """Run sandbox.builder_probe against a fake Claude; return (ok, reason, settings text)."""
    test.assertIsNotNone(sandbox, "sandbox must exist")
    test.assertTrue(hasattr(sandbox, "builder_probe"), "sandbox.builder_probe must exist")
    seen = {}

    def fake_run(args, **kwargs):
        if "-p" not in args:  # git calls that build the session environment
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        seen["settings"] = args[args.index("--settings") + 1]
        if timeout:
            raise subprocess.TimeoutExpired(args, 90)
        return type("Result", (), {"returncode": returncode, "stdout": stdout, "stderr": ""})()

    with tempfile.TemporaryDirectory() as temp, \
         patch.object(sandbox.subprocess, "run", side_effect=fake_run):
        ok, reason = sandbox.builder_probe(Path(temp), ["pypi.org"])
    return ok, reason, seen.get("settings", "")


class BuilderProbeTest(unittest.TestCase):
    def test_D1_both_commands_allowed_returns_true(self):
        ok, _, _ = run_builder_probe(self, tool_result("KIT_PYTHON_ALLOWED\nKIT_HELPER_ALLOWED"))
        self.assertIs(ok, True)

    def test_D2_a_blocked_kit_python_returns_false_and_names_it(self):
        ok, reason, _ = run_builder_probe(self, tool_result("KIT_PYTHON_BLOCKED\nKIT_HELPER_ALLOWED"))
        self.assertIs(ok, False)
        self.assertIn("kit-python", reason)

    def test_D2_a_blocked_helper_returns_false_and_names_it(self):
        ok, reason, _ = run_builder_probe(self, tool_result("KIT_PYTHON_ALLOWED\nKIT_HELPER_BLOCKED"))
        self.assertIs(ok, False)
        self.assertIn("helper", reason)
        self.assertNotIn("kit-python", reason)

    def test_D2_both_blocked_names_both_commands(self):
        ok, reason, _ = run_builder_probe(self, tool_result("KIT_PYTHON_BLOCKED\nKIT_HELPER_BLOCKED"))
        self.assertIs(ok, False)
        self.assertIn("kit-python", reason)
        self.assertIn("helper", reason)

    def test_D3_output_without_the_lines_fails_with_a_short_reason(self):
        ok, reason, settings = run_builder_probe(self, tool_result("something unexpected"))
        self.assertIs(ok, False)
        self.assertLess(len(reason), 300)
        self.assertNotIn(settings, reason)

    def test_D3_only_one_command_reported_fails(self):
        ok, reason, _ = run_builder_probe(self, tool_result("KIT_PYTHON_ALLOWED"))
        self.assertIs(ok, False)
        self.assertLess(len(reason), 300)

    def test_D3_a_timeout_fails_with_a_short_reason_without_the_settings(self):
        ok, reason, settings = run_builder_probe(self, timeout=True)
        self.assertIs(ok, False)
        self.assertLess(len(reason), 300)
        self.assertTrue(settings)
        self.assertNotIn(settings, reason)
        self.assertNotIn('"sandbox"', reason)


class PreflightBuilderProbeTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Agent: claude\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Select claude")
        git(self.p.root, "push", "--quiet", "origin", "main")
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)

    def test_D4_a_blocked_builder_command_is_a_failed_preflight_check(self):
        self.assertTrue(hasattr(sandbox, "builder_probe"), "sandbox.builder_probe must exist")
        reason = "the builder could not run kit-python"
        with patch.object(sandbox, "probe", return_value=(True, "ok")), \
             patch.object(sandbox, "builder_probe", return_value=(False, reason)):
            checks = walkaway.preflight(self.p.gh, self.p.root, baseline_checked=True)
        failed = [label for ok, label, _ in checks if not ok and "builder" in label]
        self.assertTrue(failed, f"a builder check must fail: {checks}")
        self.assertIn("cannot run the kit's commands", failed[0])
        self.assertIn("kit-python", failed[0])


if __name__ == "__main__":
    unittest.main()
