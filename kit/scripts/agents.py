"""Launch non-interactive Claude Code or Codex sessions."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Optional, Union

from loopkit import CHECK_FILES, command_env

KIT = Path(__file__).resolve().parent.parent


def selected(folder: Path, override: Optional[str] = None) -> str:
    """Return the requested backend, defaulting to Claude Code."""
    value = override
    if value is None:
        from loopkit import loop_settings
        value = loop_settings(folder).get("agent", "claude")
    if value not in {"claude", "codex"}:
        raise ValueError(f"unknown agent backend: {value}")
    return value


def _claude_settings(folder: Path, role: str, walk_away: bool,
                     domains: Optional[list[str]]) -> str:
    if walk_away:
        import sandbox
        return json.dumps(sandbox.session_settings(folder, domains), separators=(",", ":"))
    if role == "critic":
        return "{}"
    guard = f'python3 "{KIT / "hooks" / "guard.py"}"'
    return json.dumps({"hooks": {"PreToolUse": [{
        "matcher": "Bash|Edit|Write|MultiEdit|NotebookEdit",
        "hooks": [{"type": "command", "command": guard}],
    }]}})


def _claude_args(folder: Path, prompt: str, role: str,
                 disallowed: list[str], settings_allowed: bool,
                 walk_away: bool, domains: Optional[list[str]]) -> list[str]:
    cli = os.environ.get("LOOP_CLAUDE", "claude")
    args = [cli, "-p", prompt, "--output-format", "stream-json", "--verbose"]
    if role == "critic":
        args = [cli, "-p", prompt, "--output-format", "text", "--allowedTools", "Read"]
    else:
        args += ["--permission-mode", "acceptEdits", "--allowedTools",
                 "Bash", "Read", "Edit", "Write", "MultiEdit", "Glob", "Grep",
                 "--settings", _claude_settings(folder, role, walk_away, domains)]
        if walk_away:
            args += ["--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}']
        denied = [f"Edit({path})" for path in disallowed]
        if role == "builder" and not settings_allowed:
            denied += [f"Edit({path.replace('/*', '/**')})" for path in CHECK_FILES]
        if denied:
            args += ["--disallowedTools", *denied]
    return args


def start_session(backend: str, prompt: str, folder: Path, *, role: str,
                  disallowed: Optional[list[str]] = None,
                  settings_allowed: bool = False,
                  protected_paths: Optional[list[str]] = None,
                  walk_away: bool = False,
                  domains: Optional[list[str]] = None,
                  cwd: Optional[Path] = None) -> subprocess.Popen:
    """Start one non-interactive agent process with the selected boundary."""
    backend = selected(folder, backend)
    work = folder.resolve()
    working = (cwd or folder).resolve()
    if backend == "claude":
        args = _claude_args(work, prompt, role, disallowed or [], settings_allowed,
                            walk_away, domains)
        env = {**command_env(work, protected_paths=protected_paths),
               "LOOP_BUILDER": "1" if role in {"builder", "reviewer"} else "0",
               "LOOP_REVIEWER": "1" if role in {"reviewer", "critic"} else "0"}
        if walk_away:
            env.update({"LOOP_WALK_AWAY": "1", "LOOP_BUILD_ROOT": str(work)})
    else:
        cli = os.environ.get("LOOP_CODEX", "codex")
        args = [cli, "exec", "--json", "--sandbox", "workspace-write",
                "--ask-for-approval", "never", "--cd", str(work),
                "--ignore-user-config", "--ephemeral", "--config",
                "sandbox_workspace_write.network_access=false", "--config",
                "sandbox_workspace_write.writable_roots=[]", "--config",
                "sandbox_workspace_write.exclude_slash_tmp=true", "--config",
                "sandbox_workspace_write.exclude_tmpdir_env_var=true", prompt]
        env = {**command_env(work, protected_paths=protected_paths),
               "LOOP_BUILDER": "1" if role in {"builder", "reviewer"} else "0",
               "LOOP_REVIEWER": "1" if role in {"reviewer", "critic"} else "0"}
        env.pop("GH_TOKEN", None)
        env.pop("GITHUB_TOKEN", None)
    return subprocess.Popen(args, cwd=working, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, env=env, start_new_session=True)


def event_text(output: Union[str, bytes], backend: str = "codex") -> str:
    """Return final agent text from Codex JSON events or raw session output."""
    if isinstance(output, bytes):
        output = output.decode(errors="replace")
    if backend != "codex":
        return output
    messages = []
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        item = event.get("item")
        if event.get("type") == "item.completed" and isinstance(item, dict) \
                and item.get("type") == "agent_message" and isinstance(item.get("text"), str):
            messages.append(item["text"])
        elif event.get("type") == "turn.completed" and isinstance(event.get("last_agent_message"), str):
            messages.append(event["last_agent_message"])
    return messages[-1] if messages else ""


def log_line(line: str, backend: str) -> str:
    """Convert one JSONL event into readable text for the session log."""
    if backend == "claude":
        try:
            event = json.loads(line)
        except ValueError:
            return line + "\n"
        if not isinstance(event, dict):
            return ""
        if event.get("type") == "result" and (event.get("is_error") or event.get("error")):
            return f"Claude result error: {event.get('result') or event.get('error')}\n"
        message = event.get("message", {})
        if event.get("type") == "assistant" and isinstance(message, dict):
            return "".join(str(block.get("text", "")) + "\n"
                           for block in message.get("content", [])
                           if isinstance(block, dict) and block.get("type") == "text")
        return ""
    try:
        event = json.loads(line)
    except ValueError:
        return line + "\n"
    if not isinstance(event, dict):
        return ""
    item = event.get("item")
    if event.get("type") == "item.completed" and isinstance(item, dict):
        if item.get("type") == "agent_message":
            return str(item.get("text", "")) + "\n"
    if event.get("type") == "turn.failed":
        return f"Codex turn failed: {event.get('error', '')}\n"
    return ""
