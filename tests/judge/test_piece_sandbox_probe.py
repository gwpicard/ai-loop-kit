"""The Claude sandbox probe names the real startup cause and tests only real paths."""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))

try:
    import sandbox
except ImportError as error:
    if error.name != "sandbox" and not str(error.name).startswith("sandbox."):
        raise
    sandbox = None

SSH, GH = "~/.ssh", "~/.config/gh"
BLOCKED = "HOME_WRITE_BLOCKED READ_BLOCKED ~/.ssh NETWORK_BLOCKED"
CAUSE = "kernel.apparmor_restrict_unprivileged_userns"


def tool_result(text):
    return json.dumps({"type": "user", "message": {"content": [{
        "type": "tool_result", "content": text}]}})


def require_interface(test):
    test.assertIsNotNone(sandbox, "sandbox must exist")
    test.assertTrue(hasattr(sandbox, "probe_read_paths"),
                    "sandbox.probe_read_paths must exist")


def run_probe(test, stdout, paths=(SSH,), stderr="", returncode=0, before=False, leak=False):
    """Run sandbox.probe against a fake Claude; return (ok, detail, prompt)."""
    require_interface(test)
    seen = {}

    def fake_run(args, **kwargs):
        seen["prompt"] = args[args.index("-p") + 1]
        if leak:
            sandbox.PROBE_PATH.write_text("")
        return type("Result", (), {"returncode": returncode,
                                   "stdout": stdout, "stderr": stderr})()

    with tempfile.TemporaryDirectory() as temp:
        marker = Path(temp) / "absent"
        if before:
            marker.write_text("")
        with patch.object(sandbox, "PROBE_PATH", marker), \
             patch.object(sandbox, "probe_read_paths", return_value=list(paths)), \
             patch.object(sandbox.subprocess, "run", side_effect=fake_run):
            ok, detail = sandbox.probe(Path(temp), ["pypi.org"])
    return ok, detail, seen.get("prompt", "")


class SandboxProbeTest(unittest.TestCase):
    def test_D1_a_short_result_reports_the_session_text(self):
        ok, detail, _ = run_probe(self, tool_result("bwrap says something odd"),
                                  paths=[SSH, GH])
        self.assertFalse(ok)
        self.assertIn("returned", detail)
        self.assertIn("bwrap says something odd", detail)

    def test_D1_the_text_is_trimmed_to_its_last_500_characters(self):
        ok, detail, _ = run_probe(self, tool_result("HEAD" + "x" * 800 + "TAIL"))
        self.assertFalse(ok)
        self.assertIn("TAIL", detail)
        self.assertNotIn("HEAD", detail)

    def test_D1_without_a_tool_result_the_final_message_is_reported(self):
        stdout = json.dumps({"type": "result", "is_error": False,
                             "result": "I could not run the shell here"})
        ok, detail, _ = run_probe(self, stdout)
        self.assertFalse(ok)
        self.assertIn("I could not run the shell here", detail)

    def test_D2_each_startup_error_names_the_user_namespace_cause(self):
        for needle in ("apply-seccomp", "setgroups", "uid_map", "userns"):
            with self.subTest(needle=needle):
                ok, detail, _ = run_probe(self, tool_result(f"bwrap: {needle} failed: denied"))
                self.assertFalse(ok)
                self.assertIn(CAUSE, detail)
                self.assertIn("security decision", detail)

    def test_D2_stderr_is_searched_too(self):
        ok, detail, _ = run_probe(self, "", stderr="write /proc/self/uid_map: EPERM")
        self.assertFalse(ok)
        self.assertIn(CAUSE, detail)

    def test_D2_the_detail_does_not_suggest_loosening_the_restriction(self):
        ok, detail, _ = run_probe(self, tool_result("apply-seccomp: operation not permitted"))
        self.assertFalse(ok)
        lowered = detail.lower()
        for word in ("sysctl", "=0", "= 0", "disable", "loosen", "turn off"):
            self.assertNotIn(word, lowered)

    def test_D3_the_prompt_has_one_marked_line_per_check_and_no_shell_expansion(self):
        _, _, prompt = run_probe(self, tool_result(BLOCKED))
        lines = [line.strip() for line in prompt.splitlines() if "_ALLOWED" in line]
        self.assertEqual(len(lines), 3)
        self.assertEqual([line.split("echo ")[1].split("_")[0] for line in lines],
                         ["HOME", "READ", "NETWORK"])
        for line in lines:
            self.assertRegex(line, r"_BLOCKED(?: \S+)?$")
            self.assertNotIn("$", line)
            self.assertIsNone(re.search(r"\b(for|while)\b", line))
        self.assertNotIn("$", prompt)
        self.assertIn("READ_ALLOWED ~/.ssh", prompt)

    def test_D4_only_existing_paths_are_tested_and_named(self):
        ok, detail, prompt = run_probe(self, tool_result(BLOCKED))
        self.assertTrue(ok, detail)
        self.assertIn("~/.ssh", detail)
        self.assertNotIn(".config/gh", prompt)
        self.assertNotIn("Keychains", prompt)

    def test_D4_two_paths_make_four_expected_results(self):
        text = ("HOME_WRITE_BLOCKED READ_BLOCKED ~/.ssh READ_BLOCKED ~/.config/gh "
                "NETWORK_BLOCKED")
        ok, detail, _ = run_probe(self, tool_result(text), paths=[SSH, GH])
        self.assertTrue(ok, detail)
        self.assertIn("~/.config/gh", detail)
        ok, _, _ = run_probe(self, tool_result(BLOCKED), paths=[SSH, GH])
        self.assertFalse(ok)

    def test_D4_probe_read_paths_lists_only_credential_paths_that_exist(self):
        require_interface(self)
        with tempfile.TemporaryDirectory() as home:
            (Path(home) / "Library" / "Keychains").mkdir(parents=True)
            (Path(home) / ".ssh").mkdir()
            with patch.dict(os.environ, {"HOME": home}):
                self.assertEqual(sandbox.probe_read_paths(),
                                 ["~/.ssh", "~/Library/Keychains"])

    def test_D4_probe_read_paths_is_empty_when_none_exist(self):
        require_interface(self)
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"HOME": home}):
            self.assertEqual(sandbox.probe_read_paths(), [])

    def test_D5_with_no_credential_path_the_other_checks_still_run(self):
        ok, detail, prompt = run_probe(
            self, tool_result("HOME_WRITE_BLOCKED NETWORK_BLOCKED"), paths=[])
        self.assertTrue(ok, detail)
        self.assertIn("no credential path", detail.lower())
        self.assertNotIn("READ_ALLOWED", prompt)
        self.assertIn("HOME_WRITE_ALLOWED", prompt)
        self.assertIn("NETWORK_ALLOWED", prompt)

    def test_D5_a_read_result_is_not_expected_when_no_path_exists(self):
        ok, _, _ = run_probe(self, tool_result(BLOCKED), paths=[])
        self.assertFalse(ok)

    def test_D6_every_check_blocked_passes_and_any_allowed_fails(self):
        self.assertTrue(run_probe(self, tool_result(BLOCKED))[0])
        for marker in ("HOME_WRITE", "READ", "NETWORK"):
            with self.subTest(marker=marker):
                text = BLOCKED.replace(f"{marker}_BLOCKED", f"{marker}_ALLOWED")
                ok, detail, _ = run_probe(self, tool_result(text))
                self.assertFalse(ok)
                self.assertIn("allowed", detail.lower())

    def test_D6_results_joined_by_newlines_spaces_or_tabs_all_parse(self):
        for joiner in ("\n", " ", "\t"):
            with self.subTest(joiner=repr(joiner)):
                text = joiner.join(["HOME_WRITE_BLOCKED", "READ_BLOCKED ~/.ssh",
                                    "NETWORK_BLOCKED"])
                self.assertTrue(run_probe(self, tool_result(text))[0])

    def test_D6_a_nonzero_exit_with_a_startup_error_names_the_cause(self):
        ok, detail, _ = run_probe(self, tool_result("bwrap: setgroups denied"), returncode=1)
        self.assertFalse(ok)
        self.assertIn(CAUSE, detail)

    def test_D6_a_nonzero_exit_with_a_startup_error_on_stderr_names_the_cause(self):
        ok, detail, _ = run_probe(self, "", stderr="uid_map write failed", returncode=1)
        self.assertFalse(ok)
        self.assertIn(CAUSE, detail)

    def test_D6_any_other_nonzero_exit_keeps_its_message(self):
        ok, detail, _ = run_probe(self, "", stderr="boom happened", returncode=3)
        self.assertFalse(ok)
        self.assertIn("exited 3", detail)
        self.assertIn("boom happened", detail)
        self.assertNotIn("apparmor", detail)

    def test_D6_a_leftover_probe_file_keeps_its_message(self):
        ok, detail, _ = run_probe(self, "", before=True)
        self.assertFalse(ok)
        self.assertIn("already exists", detail)

    def test_D6_a_leaked_write_keeps_its_message(self):
        ok, detail, _ = run_probe(self, tool_result(BLOCKED), leak=True)
        self.assertFalse(ok)
        self.assertIn("allowed a write outside the build folder", detail)

    def test_D6_a_login_failure_keeps_its_message(self):
        ok, detail, _ = run_probe(self, "Not logged in", returncode=1)
        self.assertFalse(ok)
        self.assertIn("could not authenticate", detail)


if __name__ == "__main__":
    unittest.main()
