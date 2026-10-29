"""Settings and smoke probes for Claude Code's built-in Bash sandbox."""
from __future__ import annotations
if __name__ == "__main__":
    import kit_python
    kit_python.require()

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import agents

MIN_VERSION = (2, 1, 285)
PROBE_PATH = Path.home() / "sandbox-probe"


def version_tuple(value: str) -> tuple[int, int, int]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", value)
    return tuple(map(int, match.groups())) if match else (0, 0, 0)


def version_ok(value: str) -> bool:
    return version_tuple(value) >= MIN_VERSION


def settings_for(folder: Path, domains: Optional[list[str]] = None) -> dict:
    """Return strict per-session sandbox settings for one build worktree."""
    home = Path.home()
    credentials = ["~/.ssh", "~/.config/gh", "~/Library/Keychains"]
    caches = [home / ".npm", home / ".cache" / "pip"]
    temp = Path(tempfile.gettempdir())
    work = folder.resolve()
    env_paths = [path for path in work.glob(".env*") if path.name != ".env.example"]
    from loopkit import loop_settings
    secret_paths = loop_settings(work).get("secret paths", [])
    configured_paths = [Path(path) if Path(path).is_absolute() else work / path
                        for path in secret_paths]
    denied_paths = sorted({str(path.resolve()) for path in [*env_paths, *configured_paths]})
    return {
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "allowUnsandboxedCommands": False,
            "filesystem": {
                "allowWrite": [str(work), str(temp), *(str(path) for path in caches)],
                "allowRead": [str(work), str(temp), *(str(path) for path in caches)],
                "denyRead": [*(str(Path(path).expanduser()) for path in credentials),
                             *denied_paths],
            },
            "credentials": {
                "files": [{"path": path, "mode": "deny"} for path in credentials],
                "envVars": [{"name": name, "mode": "deny"}
                            for name in ("GITHUB_TOKEN", "GH_TOKEN", "NPM_TOKEN")],
            },
            "network": {"strictAllowlist": True, "allowedDomains": sorted(set(domains or []))},
        },
        "permissions": {
            "blockReadsOutsideWorkingDirectories": True,
            "deny": [
                *(f"Read({path}/**)" for path in credentials), "Bash(git push *)", "Bash(gh *)",
                *(f"Read({path})" for path in denied_paths),
            ],
        },
    }


def session_settings(folder: Path, domains: Optional[list[str]] = None,
                     walk_away: bool = True) -> dict:
    """Combine the existing guard with a walk-away file-tool boundary."""
    guard = Path(__file__).resolve().parents[1] / "hooks" / "guard.py"
    boundary = Path(__file__).resolve()
    launcher = Path(__file__).resolve().parents[1] / "bin" / "kit-python"
    # Through sh, so a lost executable bit does not matter, and any failure
    # exits 2: Claude Code lets a call through on every other exit code.
    hook = f'sh -c \'sh "$@" || exit 2\' kit-guard "{launcher}"'
    commands = [f'{hook} "{guard}"']
    if walk_away:
        commands.append(f'{hook} "{boundary}" guard')
    hooks = [{"matcher": "Bash|Edit|Write|MultiEdit|NotebookEdit", "hooks": [
        {"type": "command", "command": command} for command in commands]}]
    settings = settings_for(folder, domains) if walk_away else {}
    settings["hooks"] = {"PreToolUse": hooks}
    return settings


def codex_builder_paths(folder: Path) -> list[Path]:
    """Prepare temp space and find only the git paths needed for this checkout."""
    from loopkit import sh

    work = folder.resolve()
    temp = work / ".loop" / "tmp"
    if not temp.resolve().is_relative_to(work):
        raise ValueError(f"TMPDIR {temp} resolves outside the build folder "
                         "(permissions.ai-loop.filesystem)")
    temp.mkdir(parents=True, exist_ok=True)
    git_dir = Path(sh(["git", "rev-parse", "--absolute-git-dir"], work).stdout.strip())
    common = Path(sh(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                     work).stdout.strip())
    paths = [temp.resolve(), git_dir.resolve()]
    if common != git_dir:
        paths.append((common / "objects").resolve())
        ref = sh(["git", "symbolic-ref", "-q", "HEAD"], work, check=False).stdout.strip()
        if ref:
            paths.extend((common / name).resolve() for name in (ref, ref + ".lock", "logs/" + ref))
    return paths


def codex_permission_args(folder: Path, writable: Optional[list[Path]] = None,  # noqa: UP045
                          deny_secrets: bool = True) -> list[str]:
    """Build a write boundary, with secret denials for walk-away sessions."""
    from loopkit import loop_settings

    work = folder.resolve()
    workspace_rules = {".": "write"}
    filesystem = {
        ":tmpdir": "write" if writable else "deny",
        ":slash_tmp": "deny",
        ":workspace_roots": workspace_rules,
        **{str(path): "write" for path in (writable or [])},
    }
    if deny_secrets:
        workspace_rules.update({".env*": "deny", ".env.example": "read"})
        filesystem.update({str(Path.home() / name): "deny" for name in (
            ".ssh", ".aws", ".config/gh", ".config/gcloud", "Library/Keychains")})
    for raw in loop_settings(work).get("secret paths", []) if deny_secrets else []:
        path = Path(raw)
        target = (path if path.is_absolute() else work / path).resolve()
        if target.is_relative_to(work):
            workspace_rules[target.relative_to(work).as_posix()] = "deny"
        else:
            filesystem[str(target)] = "deny"

    def toml_value(value):
        if isinstance(value, dict):
            return "{" + ",".join(f"{json.dumps(key)}={toml_value(item)}"
                                  for key, item in value.items()) + "}"
        return json.dumps(value)

    return ["--config", 'default_permissions="ai-loop"',
            "--config", 'permissions.ai-loop.extends=":workspace"',
            "--config", f"permissions.ai-loop.filesystem={toml_value(filesystem)}",
            "--config", "permissions.ai-loop.network.enabled=false"]


def guard_tool_input(tool: str, data: dict, folder: Path) -> Optional[str]:
    """Limit Claude file tools to the active build worktree."""
    if tool not in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
        return None
    raw = data.get("file_path") or data.get("notebook_path") or ""
    path = Path(str(raw))
    if not path.is_absolute():
        path = folder / path
    try:
        path.resolve().relative_to(folder.resolve())
    except (OSError, ValueError):
        return "walk-away file tools may only write inside the active build folder"
    return None


def guard_main(argv: Optional[list[str]] = None) -> int:
    """PreToolUse hook entry point for file-tool writes in walk-away sessions."""
    args = sys.argv[1:] if argv is None else argv
    if args != ["guard"]:
        return 2
    try:
        call = json.load(sys.stdin)
        folder = Path(os.environ["LOOP_BUILD_ROOT"])
    except (ValueError, KeyError, OSError):
        return 2
    reason = guard_tool_input(call.get("tool_name", ""), call.get("tool_input") or {}, folder)
    if reason:
        print(f"Refused by walk-away sandbox: {reason}", file=sys.stderr)
        return 2
    return 0


def walkaway_settings_files(root: Path) -> list[Path]:
    home = Path.home()
    candidates = [
        Path("/Library/Application Support/ClaudeCode/managed-settings.json"),
        home / ".claude" / "managed-settings.json",
        home / ".claude" / "settings.json",
        home / ".claude" / "settings.local.json",
        root / ".claude" / "settings.json",
        root / ".claude" / "settings.local.json",
    ]
    return list(dict.fromkeys(path for path in candidates if path.is_file()))


def excluded_commands(root: Path) -> list[str]:
    """Read loaded settings and report sandbox escape rules without echoing content."""
    found = []
    for path in walkaway_settings_files(root):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            found.append(f"{path}: unreadable settings")
            continue
        commands = data.get("sandbox", {}).get("excludedCommands", [])
        if commands:
            found.append(f"{path}: sandbox.excludedCommands is set")
    return found


def probe(folder: Path, domains: Optional[list[str]] = None,
          claude: str = "claude", timeout: int = 90) -> tuple[bool, str]:
    """Ask a real Claude session to try bounded, content-free boundary checks."""
    if PROBE_PATH.exists():
        return False, f"{PROBE_PATH} already exists; move it before the sandbox probe"
    prompt = (
        "Use Bash to run this shell script exactly. It prints no file contents: "
        "touch ~/sandbox-probe >/dev/null 2>&1; echo HOME_WRITE_EXIT:$?; "
        "for p in ~/.ssh ~/.config/gh ~/Library/Keychains; do "
        "ls \"$p\" >/dev/null 2>&1; echo READ_EXIT:$?; done; "
        "curl --noproxy '*' -Is --max-time 8 https://example.com >/dev/null 2>&1; "
        "echo NETWORK_EXIT:$?. Do not retry any command outside the sandbox."
    )
    args = [claude, "-p", prompt, "--output-format", "stream-json", "--verbose",
            "--permission-mode", "acceptEdits", "--tools", "Bash",
            "--settings", json.dumps(settings_for(folder, domains)), *agents.CLAUDE_MCP_ARGS]
    try:
        result = subprocess.run(args, cwd=folder, capture_output=True, text=True,
                                timeout=timeout, check=False,
                                env=agents.command_env(folder, scrub_secrets=True))
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"Claude sandbox probe could not run: {error}"
    if PROBE_PATH.exists():
        # Leave the probe artefact in place so a human can inspect it if the sandbox leaked.
        return False, "sandbox allowed a write outside the build folder; ~/sandbox-probe exists"
    output = result.stdout + result.stderr
    if "Not logged in" in output or "authentication_failed" in output:
        return False, "Claude sandbox probe could not authenticate; run /login and retry"
    if result.returncode:
        return False, f"Claude sandbox probe exited {result.returncode}: {output[-500:].strip()}"
    results = []
    for event in agents.json_events(output):
        if event.get("type") == "user":
            results.extend(event.get("message", {}).get("content", []))
    text = "\n".join(str(result.get("content", "")) for result in results
                      if isinstance(result, dict) and result.get("type") == "tool_result")
    statuses = re.findall(r"(?:HOME_WRITE_EXIT|READ_EXIT|NETWORK_EXIT):(\d+)", text)
    if len(statuses) != 5:
        return False, "Claude sandbox probe did not return all five shell exit statuses"
    if any(code == "0" for code in statuses):
        return False, "Claude sandbox allowed a forbidden write, credential read or unlisted network request"
    return True, "Claude sandbox blocked the home write, three credential reads and unlisted network request"


def codex_probe(folder: Path, timeout: int = 120) -> tuple[bool, str]:
    """Check Codex's workspace-write boundary before an unattended run."""
    if PROBE_PATH.exists():
        return False, f"{PROBE_PATH} already exists; move it before the sandbox probe"
    ssh_path = Path.home() / ".ssh"
    if not ssh_path.is_dir() or not os.access(ssh_path, os.R_OK):
        return False, "~/.ssh is unavailable for the sandbox read probe"
    if shutil.which("curl") is None:
        return False, "curl is unavailable for the sandbox network probe"
    prompt = (
        "Use the shell to run each check once and report the exit codes in a final line exactly "
        "as <probe>{\"write\":N,\"ssh_read\":N,\"network\":N}</probe>. Do not retry. "
        "First run `touch ~/sandbox-probe >/dev/null 2>&1; echo $?`; then run "
        "`ls ~/.ssh >/dev/null 2>&1; echo $?`; then run "
        "`curl --noproxy '*' -Is --max-time 8 https://example.com >/dev/null 2>&1; echo $?`. "
        "Do not print file contents."
    )
    for attempt in range(2):
        label = "Codex sandbox" + (" (retried once after an unreadable answer)" if attempt else "")
        try:
            proc = agents.start_session("codex", prompt, folder, role="probe", walk_away=True)
            output, _ = proc.communicate(timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            return False, f"{label} probe could not run: {error}"
        if PROBE_PATH.exists():
            return False, f"{label} allowed a home write; ~/sandbox-probe exists"
        if proc.returncode:
            detail = output.decode(errors="replace")[-500:].strip()
            return False, f"{label} probe exited {proc.returncode}: {detail}"
        text = agents.event_text(output)
        match = re.search(r"<probe>\s*(\{.*?\})\s*</probe>", text, re.I | re.S)
        try:
            results = json.loads(match.group(1)) if match else {}
            statuses = [int(results[key]) for key in ("write", "ssh_read", "network")]
        except (ValueError, KeyError, TypeError):
            if attempt:
                reason = ("returned invalid shell exit codes" if match else
                          "did not return all three shell exit codes")
                return False, f"{label} probe {reason}"
            continue
        failed = [name for name, code in zip(
            ("write (~/sandbox-probe)", "read (~/.ssh)", "network"), statuses) if code == 0]
        if failed:
            return False, f"{label} allowed: " + ", ".join(failed)
        return True, f"{label} blocked the home write, SSH read and outside network request"


def usage_limit_event(event: dict) -> bool:
    """Recognise rate and usage limits from Claude's streamed result event."""
    if not event:
        return False
    text = " ".join(str(event.get(key, "")) for key in ("result", "error", "subtype"))
    return bool(event.get("is_error") and re.search(r"rate.?limit|usage.?limit|overloaded", text, re.I))


def reset_wait_seconds(event: dict, now: Optional[datetime] = None) -> int:
    """Use the reset time Claude reports, or the plan's 30 minute fallback."""
    values = [event.get(key) for key in ("reset_at", "resetAt", "resets_at", "resetsAt")]
    details = event.get("rate_limit") or event.get("rateLimit") or event.get("usageLimits")
    if isinstance(details, dict):
        values += [details.get(key) for key in ("reset_at", "resetAt", "resets_at", "resetsAt")]
    for value in values:
        if isinstance(value, (int, float)):
            timestamp = value / 1000 if value > 10_000_000_000 else value
            return max(0, int(timestamp - (now or datetime.now(timezone.utc)).timestamp()))
        if isinstance(value, str):
            try:
                stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return max(0, int((stamp - (now or datetime.now(timezone.utc))).total_seconds()))
            except ValueError:
                continue
    return 30 * 60


if __name__ == "__main__":
    sys.exit(guard_main())
