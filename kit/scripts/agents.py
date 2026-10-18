"""Launch non-interactive Claude Code or Codex sessions."""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Optional, Union

import sandbox
from loopkit import CHECK_FILES, command_env, loop_settings
from risk_checks import path_mentioned

KIT = Path(__file__).resolve().parent.parent
CLAUDE_MCP_ARGS = ["--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}']
CAPABILITIES = {
    "researcher": (("question",), {"web-search", "web-open"}, "dated Research lines"),
    "judge-writer": (("Intent", "Approach", "Contract", "Files"),
                     {"read", "write", "shell"}, "verdict"),
}


def selected(folder: Path, override: Optional[str] = None) -> str:
    """Return the requested backend, defaulting to Claude Code."""
    value = override if override is not None else loop_settings(folder).get("agent", "claude")
    if value not in {"claude", "codex"}:
        raise ValueError(f"unknown agent backend: {value}")
    return value


def _claude_args(folder: Path, prompt: str, role: str,
                 disallowed: list[str], settings_allowed: bool,
                 walk_away: bool, domains: Optional[list[str]]) -> list[str]:
    cli = os.environ.get("LOOP_CLAUDE", "claude")
    args = [cli, "-p", prompt, "--output-format", "stream-json", "--verbose"]
    if role == "researcher":
        return [*args, "--model", "sonnet", "--tools", "WebSearch,WebFetch",
                       "--allowedTools", "WebSearch,WebFetch", *CLAUDE_MCP_ARGS,
                       "--setting-sources", ""]
    if role == "critic":
        return [cli, "-p", prompt, "--output-format", "text", "--allowedTools", "Read"]
    if role == "judge-writer":
        args += ["--model", "sonnet"]
    args += ["--permission-mode", "acceptEdits", "--allowedTools",
             "Bash", "Read", "Edit", "Write", "MultiEdit", "Glob", "Grep",
             "--settings", json.dumps(sandbox.session_settings(folder, domains, walk_away))]
    if walk_away:
        args += CLAUDE_MCP_ARGS
    denied = [f"Edit({path})" for path in disallowed]
    if role == "builder" and not settings_allowed:
        denied += [f"Edit({path.replace('/*', '/**')})" for path in CHECK_FILES]
    if denied:
        args += ["--disallowedTools", *denied]
    return args


def start_session(backend: str, prompt: str, folder: Path, *, role: str,
                  disallowed: Optional[list[str]] = None, settings_allowed: bool = False,
                  protected_paths: Optional[list[str]] = None,
                  protected_exceptions: Optional[list[str]] = None,  # noqa: UP045
                  contract: Optional[dict[str, str]] = None,
                  walk_away: bool = False, domains: Optional[list[str]] = None,
                  cwd: Optional[Path] = None) -> subprocess.Popen:
    """Start one non-interactive agent process with the selected boundary."""
    backend = selected(folder, backend)
    if role == "researcher" and walk_away:
        raise ValueError(f"{backend} researcher requires web-search and web-open; "
                         "leave the piece in shaping")
    work = folder.resolve()
    if role == "builder" and contract is not None:
        contract_text = " ".join(contract.values())
        protected_paths = [path for path in (protected_paths or [])
                           if not path_mentioned(contract_text, path)]
    if backend == "claude":
        args = _claude_args(work, prompt, role, disallowed or [], settings_allowed,
                            walk_away, domains)
    else:
        cli = os.environ.get("LOOP_CODEX", "codex")
        # Ignoring config.toml alone still loads installed plugins and app MCP servers.
        args = [cli, "exec", "--json", "--disable", "plugins", "--disable", "apps"]
        writable = sandbox.codex_builder_paths(work) if role == "builder" else None
        if writable:
            prompt += ("\n\nCodex write boundary (permissions.ai-loop.filesystem):\n"
                       + "\n".join(str(path) for path in [work, *writable])
                       + "\nTMPDIR is the first path after the build folder above. "
                       "permissions.ai-loop.network.enabled=false. "
                       "If a refusal cannot be fixed within this boundary, write "
                       "environment on the first line of .loop/outcome, then the "
                       "refused path and the setting responsible. Do not retry "
                       "outside the sandbox.")
        if walk_away or writable:
            args += sandbox.codex_permission_args(work, writable, deny_secrets=walk_away)
            args += ["--config", 'approval_policy="never"']
        else:
            args += ["--sandbox", "read-only" if role == "researcher" else "workspace-write",
                     "--config", 'approval_policy="never"', "--config",
                     'sandbox_workspace_write.network_access=false', "--config",
                     "sandbox_workspace_write.writable_roots=[]", "--config",
                     "sandbox_workspace_write.exclude_slash_tmp=true", "--config",
                     "sandbox_workspace_write.exclude_tmpdir_env_var=true"]
        if role == "researcher":
            args += ["--disable", "shell_tool", "--config", 'web_search="live"']
        args += ["--cd", str(work), "--ignore-user-config", "--ephemeral", prompt]
    env = {**command_env(work, protected_paths=protected_paths, scrub_secrets=True,
                         protected_exceptions=protected_exceptions),
           "LOOP_BUILDER": "1" if role in {"builder", "reviewer"} else "0",
           "LOOP_REVIEWER": "1" if role in {"reviewer", "critic"} else "0"}
    if backend == "claude" and walk_away:
        env.update({"LOOP_WALK_AWAY": "1", "LOOP_BUILD_ROOT": str(work)})
    if backend == "codex" and writable:
        env["TMPDIR"] = str(writable[0])
    return subprocess.Popen(args, cwd=(cwd or folder).resolve(), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, env=env, start_new_session=True)


def event_text(output: Union[str, bytes], backend: str = "codex") -> str:
    """Return final agent text from Codex JSON events or raw session output."""
    if isinstance(output, bytes):
        output = output.decode(errors="replace")
    messages = [text.rstrip("\n") for event in json_events(output)
                if event.get("type") in {"assistant", "item.completed", "turn.completed"}
                and (text := log_line(json.dumps(event), backend))]
    return messages[-1] if messages else output if backend == "claude" else ""


def json_events(output: str):
    """Read dictionary events, ignoring plain diagnostics and malformed lines."""
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            yield event


def log_line(line: str, backend: str, result_event: dict | None = None) -> str:
    """Convert one JSONL event into readable text for the session log."""
    try:
        event = json.loads(line)
    except ValueError:
        return line + "\n"
    if not isinstance(event, dict):
        return ""
    if result_event is not None and event.get("type") in {"result", "turn.failed"}:
        result_event.update(event)
    if backend == "claude":
        if event.get("type") == "result" and (event.get("is_error") or event.get("error")):
            return f"Claude result error: {event.get('result') or event.get('error')}\n"
        message = event.get("message", {})
        if event.get("type") == "assistant" and isinstance(message, dict):
            return "".join(str(block.get("text", "")) + "\n"
                           for block in message.get("content", [])
                           if isinstance(block, dict) and block.get("type") == "text")
        return ""
    if event.get("type") == "turn.failed":
        return f"Codex turn failed: {event.get('error', '')}\n"
    item = event.get("item", {})
    text = item.get("text", "") if event.get("type") == "item.completed" and \
        isinstance(item, dict) and item.get("type") == "agent_message" \
        else event.get("last_agent_message", "")
    return text + "\n" if isinstance(text, str) and text else ""


def environment_evidence(logfile: Path) -> str:
    """Read observed tool failures, including shell refusals in successful batches."""
    events = logfile.with_suffix(".jsonl")
    outputs = []
    for event in json_events(events.read_text(errors="replace") if events.is_file() else ""):
        item = event.get("item", {})
        kind = item.get("type") if isinstance(item, dict) else ""
        if event.get("type") == "item.completed" and (
                (kind == "command_execution" and isinstance(item.get("exit_code"), int)) or
                (kind == "web_search" and (item.get("error") or item.get("status") == "failed"))):
            output = str(item.get("aggregated_output", item.get("error") or f"{kind} failed"))
            outputs.extend(text for text in output.splitlines() if item.get("exit_code", 1) or
                           re.fullmatch(r"zsh:[0-9]+: can't create temp file for here document: "
                                        r"operation not permitted", text))
        message = event.get("message", {})
        if event.get("type") == "user" and isinstance(message, dict):
            for block in message.get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_result" and \
                        block.get("is_error"):
                    content = block.get("content") or ""
                    text = ("\n".join(str(part.get("text", "")) for part in content
                                     if isinstance(part, dict))
                            if isinstance(content, list) else str(content))
                    outputs.append(text or "tool result failed")
    failures = [text.strip() for output in outputs for text in output.splitlines() if text.strip()]
    return ("Observed tool failure: " + "\n".join(failures[-3:]))[:500] if failures else ""
