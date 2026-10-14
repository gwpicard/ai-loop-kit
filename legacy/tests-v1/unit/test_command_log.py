"""Unit tests for the duplicate guard in kit/hooks/command-log.py.

A builder session started with `--settings` may also load the plugin, which wires
the same hooks. Each hook then runs twice for one call. The log must hold one line.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

_spec = importlib.util.spec_from_file_location(
    "command_log", ROOT / "kit" / "hooks" / "command-log.py"
)
assert _spec is not None and _spec.loader is not None
command_log = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(command_log)


class Duplicates(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp())
        self.project = self.base / "project"
        self.project.mkdir()
        subprocess.run(["git", "-C", str(self.project), "init", "-q", "-b", "main"], check=True)
        self.env = {"AI_LOOP_KIT_RUN": "night-1"}
        self.log = self.project / ".agents" / "runs" / "night-1" / "commands.log"

    def payload(self, **extra: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "session_id": "s1",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "cwd": str(self.project),
        }
        base.update(extra)
        return base

    def lines(self) -> list[dict[str, Any]]:
        return [json.loads(row) for row in self.log.read_text().splitlines()]

    def test_the_same_call_seen_twice_is_logged_once(self) -> None:
        payload = self.payload(tool_use_id="toolu_1")
        command_log.record(payload, "ran", "", self.env)
        command_log.record(payload, "ran", "", self.env)
        self.assertEqual(len(self.lines()), 1)

    def test_the_two_events_of_one_call_are_both_kept(self) -> None:
        payload = self.payload(tool_use_id="toolu_1")
        command_log.record(payload, "pass", "", self.env)
        command_log.record(payload, "ran", "", self.env)
        command_log.record(payload, "ran", "", self.env)
        self.assertEqual([row["event"] for row in self.lines()], ["pass", "ran"])

    def test_a_real_retry_with_a_new_call_id_is_kept_and_counted(self) -> None:
        command_log.record(self.payload(tool_use_id="toolu_1"), "ran", "", self.env)
        command_log.record(self.payload(tool_use_id="toolu_2"), "ran", "", self.env)
        self.assertEqual([row["retry"] for row in self.lines()], [0, 1])

    def test_a_call_with_no_id_is_never_dropped(self) -> None:
        command_log.record(self.payload(), "ran", "", self.env)
        command_log.record(self.payload(), "ran", "", self.env)
        self.assertEqual(len(self.lines()), 2)

    def test_two_hook_processes_at_once_log_each_call_once(self) -> None:
        hook = ROOT / "kit" / "hooks" / "command-log.py"
        env = {
            "PATH": "/usr/bin:/bin",
            "AI_LOOP_KIT_RUN": "night-1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        procs = []
        for index in range(20):
            body = json.dumps(
                self.payload(
                    tool_use_id=f"toolu_{index}",
                    hook_event_name="PostToolUse",
                    tool_response={},
                    tool_input={"command": f"echo {index}"},
                )
            )
            for _ in range(2):
                proc = subprocess.Popen(
                    [sys.executable, str(hook)],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                    text=True,
                )
                procs.append((proc, body))
        for proc, body in procs:
            assert proc.stdin is not None
            proc.stdin.write(body)
            proc.stdin.close()
        for proc, _ in procs:
            proc.wait()
        calls = [row["call"] for row in self.lines()]
        self.assertEqual(len(calls), 20)
        self.assertEqual(len(set(calls)), 20)


if __name__ == "__main__":
    unittest.main()
