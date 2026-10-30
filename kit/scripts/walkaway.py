"""Pre-run checks and run records for unattended builds."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

import agents
import answers
import holds
import sandbox
from loopkit import (JUDGE_TIMEOUT, STATE_PREFIX, Refused, base_merges, command_env,
                     last_record, loop_settings, main_ref, prepare, run_judge, secret_env_names, sh)

MIN_FREE_BYTES = 10 * 1024 ** 3
STALE_AFTER_SECONDS = 10 * 60
NO_TESTS_SKIP = "skipped: the base branch has no tests yet; the scaffold piece adds them"
NO_TESTS_STEP = "shape and ready a scaffold piece first"


def approved_domains(root: Path) -> list[str]:
    raw = loop_settings(root).get("sandbox domains", "")
    return sorted({part.strip() for part in raw.split(",") if part.strip()})


def _check(ok: bool, label: str, next_step: str = "") -> tuple[bool, str, str]:
    return ok, label, "" if ok else next_step


def codex_sandbox_test(root: Path, timeout: int = JUDGE_TIMEOUT) -> tuple[bool, str]:
    """Run Prepare, then the Test command inside the Codex builder sandbox, on fresh main.
    The sandbox probe proves what is refused; this proves the builder can still test."""
    settings = loop_settings(root)
    if not settings.get("test"):
        return True, "no Test command"
    folder = root.parent / f".loop-sandbox-test-{os.getpid()}"
    try:
        sh(["git", "worktree", "add", "--detach", "--quiet", str(folder), main_ref(root)], root)
    except Exception as error:
        return False, f"could not make a fresh main worktree: {str(error)[:200]}"
    try:
        prepared, output = prepare(folder, settings.get("prepare", ""), package_cache=True)
        if not prepared:
            return False, "Prepare failed: " + output[-300:].strip()
        writable = sandbox.codex_builder_paths(folder)
        env = {**command_env(folder, scrub_secrets=True, package_cache=True),
               "TMPDIR": str(writable[0])}
        args = [os.environ.get("LOOP_CODEX", "codex"), "sandbox",
                *sandbox.codex_permission_args(folder, writable), "sh", "-c", settings["test"]]
        result = subprocess.run(args, cwd=folder, env=env, capture_output=True, text=True,
                                timeout=timeout)
        return result.returncode == 0, (result.stdout + result.stderr)[-300:].strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"the sandboxed Test command could not finish: {error}"
    finally:
        sh(["git", "worktree", "remove", "--force", str(folder)], root, check=False)


def base_has_tests(root: Path) -> bool:
    from doctor import TEST_PATH
    files = sh(["git", "ls-tree", "-r", "--name-only", main_ref(root)], root).stdout.splitlines()
    return any(TEST_PATH.search(path.lower()) for path in files)


def empty_base_scaffold(gh, root: Path, pieces: list[int]) -> bool:
    """True when the base has no tests and the piece the run builds first is a ready scaffold."""
    if base_has_tests(root):
        return False
    first, _ = holds.pick(gh, list(pieces), holds.wanted(gh, pieces), {})
    return first is not None and (last_record(gh.comments(first), "ready") or {}
                                  ).get("kind") == "scaffold"


def preflight(gh, root: Path, *, baseline_checked: bool = False,
              agent: Optional[str] = None,
              pieces: Optional[list[int]] = None) -> list[tuple[bool, str, str]]:
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

        guard = root / "kit" / "hooks" / "guard.py"
        checks.append(_check(guard.is_file(), "the kit guard hook is available to sessions",
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
    try:
        merges = base_merges(root)
    except Refused as error:
        merges = False
        checks.append(_check(False, error.reason, error.next_step))
    waiting = 0 if merges else len(gh.issues_with_label(STATE_PREFIX + "approval"))
    checks.append(_check(waiting < waiting_limit,
                         f"approval queue is below its limit ({waiting}/{waiting_limit})",
                         "review or merge an approval pull request, then retry"))

    empty = pieces is not None and not base_has_tests(root)
    scaffold = empty and empty_base_scaffold(gh, root, pieces)
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
                checks.append(_check(test_code == 0 or scaffold, "Test passes on a fresh main worktree",
                                     NO_TESTS_STEP if empty else
                                     "fix the Test command before retrying the walk-away run"))
                if scaffold:
                    checks[-1] = (True, f"Test on a fresh main worktree: {NO_TESTS_SKIP}", "")
                if not prepared:
                    checks[-2] = (False, checks[-2][1] + ": " + poutput[-300:].strip(), checks[-2][2])
                if test_code and not scaffold:
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
    if scaffold and backend != "claude" and active:
        checks.append((True, f"the Test command inside the Codex builder sandbox: {NO_TESTS_SKIP}", ""))
    elif backend != "claude" and active:
        tested, output = codex_sandbox_test(root)
        checks.append(_check(tested, "the Test command passes inside the Codex builder sandbox"
                             + ("" if tested else f": {output}"),
                             NO_TESTS_STEP if empty else "fix the refused path or tool named above (an old uv can panic in "
                             "the sandbox: upgrade it), then run gate.py doctor --walk-away"))
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


BLOCKERS = ("back to shaping", "refused", "stopped by an error", "Run paused", "held until",
            "Not merged")


def piece_summary(root: Path, number: int, result: str, state: str,
                  since: Optional[datetime] = None) -> str:
    attempts, elapsed = _piece_timing(root, number, since)
    match = re.search(r"https://github\.com/\S+", result)
    pull_request = match.group(0).rstrip(".,)") if match else "none"
    return (f"piece {number}: state {state}; {attempts} attempt(s); "
            f"{int(elapsed // 60)}m {int(elapsed % 60)}s; pull request {pull_request}. "
            f"Result: {result}")


def builder_outcome(path: Path) -> tuple[str, str]:
    lines = path.read_text(errors="replace").splitlines()
    kind = lines[0].strip() if lines else ""
    body = [line.strip() for line in lines[1:] if line.strip()]
    if kind == "needs-answer":
        body = answers.split_recommendation(body)[0]
    if kind in ("needs-answer", "environment"):
        return kind, "\n".join(body)[:500]
    if kind != "spec-unclear":
        return kind, ""
    reason = next((line[7:].strip() for line in body if line.startswith("Reason:")), "")
    cite = next((line[9:].strip() for line in body if line.startswith("Citation:")), "")
    command_cited = re.fullmatch(r"Command: .+ \(exit [1-9][0-9]*\)", cite)
    file_cited = not cite.startswith("Command:") and re.fullmatch(r"`?.+:[1-9][0-9]*`?", cite)
    valid = command_cited or file_cited
    return kind, f"{reason[:500]}\nCitation: {cite}" if reason and valid else ""


def outcome_recommendation(path: Path) -> dict:
    """The path and reason a builder recommended with a question; empty when invalid."""
    body = [line.strip() for line in path.read_text(errors="replace").splitlines()[1:]]
    return answers.split_recommendation(body)[1]


def summary_text(results: list[str], started: datetime, finished: datetime) -> str:
    lines = ["# Walk-away run summary", "", f"Started: {started.isoformat()}",
             f"Finished: {finished.isoformat()}", "", "## Pieces", ""]
    lines.extend(f"- {result}" for result in results)
    merged = any(" merged into " in result for result in results)
    lines += ["", "## Decisions made by the run", "", "- The gate judged each attempt.",
              "- The run merged gated pieces into the base branch; the pull request into "
              "main waits for the person." if merged else
              "- Pull requests were left for the person to merge.", "", "## Blockers", ""]
    blockers = [result for result in results if any(marker in result for marker in BLOCKERS)]
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
