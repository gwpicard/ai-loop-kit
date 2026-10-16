"""Pre-run checks and run records for unattended builds."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

import agents
import sandbox
from loopkit import (STATE_PREFIX, loop_settings, main_ref, prepare, run_judge,
                     secret_env_names, sh)

MIN_FREE_BYTES = 10 * 1024 ** 3
STALE_AFTER_SECONDS = 10 * 60


def approved_domains(root: Path) -> list[str]:
    raw = loop_settings(root).get("sandbox domains", "")
    return sorted({part.strip() for part in raw.split(",") if part.strip()})


def _check(ok: bool, label: str, next_step: str = "") -> tuple[bool, str, str]:
    return ok, label, "" if ok else next_step


def preflight(gh, root: Path, *, baseline_checked: bool = False,
              agent: Optional[str] = None) -> list[tuple[bool, str, str]]:
    """Return explicit checks. A failed check always has one next step."""
    checks = []
    try:
        backend = agents.selected(root, agent)
    except ValueError as error:
        return [_check(False, str(error), "set `Agent: claude` or `Agent: codex` in AGENTS.md")]
    if backend == "claude":
        claude = os.environ.get("LOOP_CLAUDE", "claude")
        version = subprocess.run([claude, "--version"], cwd=root, capture_output=True,
                                 text=True, check=False)
        version_text = version.stdout.strip() if version.returncode == 0 else ""
        checks.append(_check(version.returncode == 0 and sandbox.version_ok(version_text),
                             f"Claude Code {version_text or 'version unavailable'} supports strict sandbox mode",
                             "install Claude Code 2.1.285 or later and check that it is on PATH"))

        settings_errors = sandbox.excluded_commands(root)
        checks.append(_check(not settings_errors,
                             "loaded Claude settings do not exclude commands from the sandbox",
                             "remove sandbox.excludedCommands from the loaded settings and retry"))
        if settings_errors:
            checks[-1] = (False, checks[-1][1] + ": " + "; ".join(settings_errors), checks[-1][2])

        config = root / "kit" / "hooks" / "hooks.json"
        guard = root / "kit" / "hooks" / "guard.py"
        wired = config.is_file() and guard.is_file() and "guard.py" in config.read_text(errors="replace")
        wired = wired or guard.is_file()
        checks.append(_check(wired, "the kit guard hook is available to sessions",
                             "restore kit/hooks/guard.py and the run session hook"))

        bypass = any(os.environ.get(key) for key in
                     ("CLAUDE_CODE_BYPASS_PERMISSIONS", "CLAUDE_CODE_DANGEROUSLY_SKIP_PERMISSIONS"))
        checks.append(_check(not bypass, "the session permission mode is not bypass",
                             "remove the Claude Code bypass permission environment setting"))
        domains = approved_domains(root)
        checks.append(_check(bool(domains), "the project has confirmed sandbox network domains",
                             "agree package registry domains, then add `Sandbox domains: <comma-separated domains>` to AGENTS.md"))

    else:
        codex = os.environ.get("LOOP_CODEX", "codex")
        version = subprocess.run([codex, "--version"], cwd=root, capture_output=True,
                                 text=True, check=False)
        version_text = version.stdout.strip() if version.returncode == 0 else "version unavailable"
        checks.append(_check(version.returncode == 0,
                             f"Codex CLI {version_text} is available",
                             "install Codex CLI and check that it is on PATH"))

    removed_names = secret_env_names()
    listed_names = ", ".join(removed_names) if removed_names else "none found"
    report = ("secret-shaped environment variables removed from builder and reviewer "
              f"sessions: {listed_names}")
    checks.append((True, report, ""))

    free_bytes = shutil.disk_usage(root).free
    checks.append(_check(free_bytes >= MIN_FREE_BYTES,
                         f"free disk is at least 10 GB ({free_bytes // (1024 ** 3)} GB available)",
                         "free at least 10 GB of disk space before starting"))
    limit = loop_settings(root).get("waiting limit", "3")
    try:
        waiting_limit = max(1, int(limit))
    except ValueError:
        waiting_limit = 3
    waiting = len(gh.issues_with_label(STATE_PREFIX + "approval"))
    checks.append(_check(waiting < waiting_limit,
                         f"approval queue is below its limit ({waiting}/{waiting_limit})",
                         "review or merge an approval pull request, then retry"))

    if not baseline_checked:
        try:
            main = main_ref(root)
            folder = root.parent / f".loop-walkaway-main-{os.getpid()}"
            sh(["git", "worktree", "add", "--detach", "--quiet", str(folder), main], root)
            try:
                settings = loop_settings(folder)
                prepared, poutput = prepare(folder, settings.get("prepare", ""))
                test_code, test_output = run_judge(folder, settings.get("test", ""))
                checks.append(_check(prepared, "Prepare passes on a fresh main worktree",
                                     "fix the Prepare command before retrying the walk-away run"))
                checks.append(_check(test_code == 0, "Test passes on a fresh main worktree",
                                     "fix the Test command before retrying the walk-away run"))
                if not prepared:
                    checks[-2] = (False, checks[-2][1] + ": " + poutput[-300:].strip(), checks[-2][2])
                if test_code:
                    checks[-1] = (False, checks[-1][1] + ": " + test_output[-300:].strip(), checks[-1][2])
            finally:
                sh(["git", "worktree", "remove", "--force", str(folder)], root, check=False)
        except Exception as error:
            checks.append(_check(False, f"main baseline could not be checked: {str(error)[:200]}",
                                 "run gate.py doctor and resolve its failures"))
    else:
        checks.append((True, "Prepare and Test pass on a fresh main worktree", ""))

    if backend == "claude":
        active, detail = sandbox.probe(root, domains, claude=claude)
        probe_label = "Claude's active sandbox probe blocks home writes, secret reads and unlisted network"
    else:
        active, detail = sandbox.codex_probe(root)
        probe_label = "Codex's active sandbox probe blocks home writes, SSH reads and outside network"
    checks.append(_check(active, probe_label,
                         "resolve the active sandbox probe failure, then run gate.py doctor --walk-away"))
    if not active:
        checks[-1] = (False, checks[-1][1] + f": {detail}", checks[-1][2])
    return checks


def heartbeat_path(root: Path) -> Path:
    return root / ".loop" / "heartbeat"


def write_heartbeat(root: Path, piece: Optional[int] = None, attempt: Optional[int] = None,
                    state: str = "active") -> None:
    target = heartbeat_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"time": datetime.now(timezone.utc).isoformat(),
                                  "piece": piece, "attempt": attempt, "state": state},
                                 sort_keys=True) + "\n")


def heartbeat_status(root: Path) -> str:
    target = heartbeat_path(root)
    if not target.is_file():
        return ""
    try:
        data = json.loads(target.read_text())
        stamp = datetime.fromisoformat(data["time"])
        age = max(0, (datetime.now(timezone.utc) - stamp).total_seconds())
    except (OSError, ValueError, KeyError, TypeError):
        return "walk-away heartbeat is unreadable"
    state = "stale" if age > STALE_AFTER_SECONDS else "live"
    part = f", piece {data.get('piece')} attempt {data.get('attempt')}" if data.get("piece") else ""
    if data.get("state") == "finished":
        return f"last walk-away run finished ({int(age // 60)} minutes ago{part})"
    return f"walk-away run {state} ({int(age // 60)} minutes old{part})"


@contextmanager
def keep_awake(root: Path) -> Iterator[None]:
    proc = None
    if sys.platform == "darwin":
        try:
            proc = subprocess.Popen(["caffeinate", "-dimsu"], stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
        except OSError:
            proc = None
    stopped = threading.Event()
    write_heartbeat(root)

    def beat() -> None:
        while not stopped.wait(60):
            write_heartbeat(root)

    thread = threading.Thread(target=beat, name="walkaway-heartbeat", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=2)
        write_heartbeat(root, state="finished")
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def _piece_timing(root: Path, number: int, since: Optional[datetime] = None) -> tuple[int, float]:
    logs = root / ".loop" / "logs"
    files = sorted(logs.glob(f"piece-{number}-attempt-*.log")) if logs.is_dir() else []
    attempts, elapsed = 0, 0.0
    for path in files:
        try:
            content = path.read_text(errors="replace")
        except OSError:
            continue
        timings = re.findall(r"Attempt timing: (\{[^\n]+\})", content)
        for record in timings:
            try:
                data = json.loads(record)
                stamp = datetime.fromisoformat(data["started_at"])
                if since and stamp < since:
                    continue
                elapsed += float(data.get("elapsed_seconds", 0))
                attempts += 1
            except (ValueError, TypeError, KeyError):
                continue
    return attempts, elapsed


def piece_summary(root: Path, number: int, result: str, state: str,
                  since: Optional[datetime] = None) -> str:
    attempts, elapsed = _piece_timing(root, number, since)
    match = re.search(r"https://github\.com/\S+", result)
    pull_request = match.group(0).rstrip(".,)") if match else "none"
    return (f"piece {number}: state {state}; {attempts} attempt(s); "
            f"{int(elapsed // 60)}m {int(elapsed % 60)}s; pull request {pull_request}. "
            f"Result: {result}")


def summary_text(results: list[str], started: datetime, finished: datetime) -> str:
    lines = ["# Walk-away run summary", "", f"Started: {started.isoformat()}",
             f"Finished: {finished.isoformat()}", "", "## Pieces", ""]
    lines.extend(f"- {result}" for result in results)
    lines += ["", "## Decisions made by the run", "", "- The gate judged each attempt.",
              "- Pull requests were left for the person to merge.", "", "## Blockers", ""]
    blockers = [result for result in results if any(marker in result for marker in
                ("back to shaping", "refused", "stopped by an error", "Run paused"))]
    lines.extend(f"- {blocker}" for blocker in blockers)
    if not blockers:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def write_summary(root: Path, results: list[str], started: datetime,
                  finished: datetime) -> Path:
    path = root / ".loop" / "summary.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(summary_text(results, started, finished))
    return path


def post_summary(gh, summary: str, mention: bool = False) -> None:
    """Post to the stable tracking issue, mentioning the owner only on blockers."""
    rows = json.loads(gh._gh("issue", "list", "--state", "all", "--search",
                             'in:title "AI Loop Kit run log"', "--limit", "20",
                             "--json", "number,title"))
    tracking = next((row["number"] for row in rows
                     if row.get("title") == "AI Loop Kit run log"), None)
    if tracking is None:
        tracking = gh.create_issue("AI Loop Kit run log", "Walk-away run summaries.", [])
    if mention:
        user = gh._gh("api", "user", "--jq", ".login").strip()
        if user:
            summary = f"@{user}\n\n" + summary
    gh.comment(tracking, summary)
