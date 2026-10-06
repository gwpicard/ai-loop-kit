#!/usr/bin/env python3
"""The command log: one JSON line for every call the agent runs, is refused or retries.

Lessons and investigations read this file. It is `commands.log` in the run's
folder, `.agents/runs/<run>/commands.log` in the project's main folder, and Git
ignores it.

Two things write it:

- `guard.py` calls `record()` for every decision: `pass`, `ask` or `refuse`.
- Claude Code runs this file as a PostToolUse and PostToolUseFailure hook, and
  `main()` writes `ran` or `failed`.

A line holds the time, the session, the event, the tool, the command (or the file
a file tool names), the reason for an ask or a refusal, the folder the session
ran in, the run's name and a retry count. The retry count is the number of earlier
lines in the same session with the same command and event, so a refused command
that comes back shows 1, then 2.

A call that carries a call ID is logged once for each event, even when the hook
runs twice for it at the same time, as it does when a session loads the plugin and
`--settings` both. A marker file in `claims/` next to the log settles the race. A call with no ID is always logged.

The run's name is the `AI_LOOP_KIT_RUN` variable. The session starter sets it.
Without it, or with a name `loop/paths.py` refuses, the line goes to the run named
`attended`.

Secrets are scrubbed before a line is written, and a long command is cut. The log
never stops a call: any fault here is swallowed, and `main()` always exits 0.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from loop import paths as loop_paths

RUN_ENV = "AI_LOOP_KIT_RUN"
DEFAULT_RUN = "attended"
MAX_TEXT = 2000
RETRY_WINDOW = 2000

SCRUBS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "[redacted]"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "[redacted]"),
    (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), "[redacted]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[redacted]"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "[redacted]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "[redacted]"),
    (re.compile(r"(?i)(authorization:\s*(?:bearer|token|basic)\s+)\S+"), r"\1[redacted]"),
    (
        re.compile(
            r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|KEY)[A-Z0-9_]*)"
            r"=(\"[^\"]*\"|'[^']*'|\S+)"
        ),
        r"\1=[redacted]",
    ),
]


def scrub(text: str) -> str:
    for pattern, replacement in SCRUBS:
        text = pattern.sub(replacement, text)
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT] + " [cut]"
    return text


def _main_folder(start: Path) -> Path | None:
    """The main folder of the project that holds `start`, a worktree included."""
    try:
        work = loop_paths.find_project_root(start)
    except loop_paths.PathError:
        return None
    dot_git = work / ".git"
    if dot_git.is_file():
        try:
            first = dot_git.read_text().splitlines()[0]
        except (OSError, IndexError):
            return work
        if first.startswith("gitdir:"):
            target = Path(first.split(":", 1)[1].strip())
            if not target.is_absolute():
                target = (work / target).resolve()
            # <main>/.git/worktrees/<name>
            if target.parent.name == "worktrees" and target.parent.parent.name == ".git":
                return target.parent.parent.parent
    return work


def run_name(env: Mapping[str, str], root: Path) -> str:
    name = env.get(RUN_ENV) or DEFAULT_RUN
    paths = loop_paths.Paths.for_project(root, data_base=root, kit_folder=root)
    try:
        paths.run_dir(name)
    except loop_paths.PathError:
        return DEFAULT_RUN
    return name


def _target(payload: Mapping[str, Any]) -> str:
    raw = payload.get("tool_input")
    tool_input: Mapping[str, Any] = raw if isinstance(raw, dict) else {}
    for key in ("command", "file_path", "notebook_path", "path", "pattern"):
        if isinstance(tool_input.get(key), str):
            return str(tool_input[key])
    return ""


def _retries(log: Path, session: str, command: str, event: str) -> int:
    try:
        lines = log.read_text(encoding="utf-8").splitlines()[-RETRY_WINDOW:]
    except OSError:
        return 0
    count = 0
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if (
            isinstance(row, dict)
            and row.get("session") == session
            and row.get("command") == command
            and row.get("event") == event
        ):
            count += 1
    return count


def _claim(log: Path, session: str, call_id: str, event: str) -> bool:
    """Claim this call and event. True for the first claimant, False for any later one.

    A builder session gets the hooks from `--settings`. If the plugin is loaded
    too, each hook runs twice for one call, and Claude Code runs them at the same
    time. Both runs carry the same call ID. A marker file made with O_CREAT and
    O_EXCL lets exactly one of them go on, with no read-then-write gap.
    """
    key = hashlib.sha256(f"{session}\0{call_id}\0{event}".encode()).hexdigest()[:32]
    folder = log.parent / "claims"
    folder.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(folder / key, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    os.close(fd)
    return True


def record(
    payload: Mapping[str, Any], event: str, reason: str, env: Mapping[str, str]
) -> None:
    """Append one line to the run's command log. Never raises."""
    try:
        cwd = str(payload.get("cwd") or os.getcwd())
        root = _main_folder(Path(cwd))
        if root is None:
            return
        name = run_name(env, root)
        paths = loop_paths.Paths.for_project(root, data_base=root, kit_folder=root)
        log = paths.command_log(name)
        session = str(payload.get("session_id") or "")
        command = scrub(_target(payload))
        call_id = str(payload.get("tool_use_id") or "")
        if call_id and not _claim(log, session, call_id, event):
            return
        row = {
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "session": session,
            "event": event,
            "tool": str(payload.get("tool_name") or ""),
            "command": command,
            "reason": scrub(reason),
            "cwd": cwd,
            "run": name,
            "retry": _retries(log, session, command, event),
        }
        if call_id:
            row["call"] = call_id
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        return


def main(stdin: TextIO, stderr: TextIO, env: Mapping[str, str] | None = None) -> int:
    """The PostToolUse and PostToolUseFailure hook. Always exits 0."""
    env = os.environ if env is None else env
    try:
        payload = json.loads(stdin.read())
    except ValueError:
        return 0
    if not isinstance(payload, dict) or not payload.get("tool_name"):
        return 0
    hook_event = str(payload.get("hook_event_name") or "")
    reason = ""
    if hook_event == "PostToolUseFailure":
        event, reason = "failed", str(payload.get("error") or "")
    elif hook_event == "PostToolUse":
        response = payload.get("tool_response")
        failed = isinstance(response, dict) and bool(response.get("is_error"))
        event = "failed" if failed else "ran"
        if isinstance(response, dict) and response.get("interrupted"):
            reason = "interrupted"
    else:
        event = hook_event.lower() or "seen"
    record(payload, event, reason, env)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin, sys.stderr))
