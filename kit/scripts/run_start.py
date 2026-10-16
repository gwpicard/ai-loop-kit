"""Run-start recovery and GitHub's briefly delayed ready search."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from loopkit import STATE_PREFIX, sh

READY_RETRIES = 4
READY_RETRY_SECONDS = 5


def _run_metrics_path(root: Path, n: int) -> Path:
    return root / ".loop" / "run-metrics" / f"piece-{n}.json"


def _save_run_metrics(root: Path, n: int, started_at: datetime, attempts: int) -> None:
    path = _run_metrics_path(root, n)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"started_at": started_at.isoformat(),
                                     "attempts": attempts}) + "\n")
    temporary.replace(path)


def _recovered_run_metrics(root: Path, n: int) -> tuple[int, float]:
    try:
        saved = json.loads(_run_metrics_path(root, n).read_text())
        started_at = datetime.fromisoformat(saved["started_at"])
        if started_at.tzinfo is None:
            return 0, 0
        attempts = max(0, int(saved["attempts"]))
        seconds = max(0.0, (datetime.now(timezone.utc) - started_at).total_seconds())
        return attempts, seconds
    except (OSError, ValueError, KeyError, TypeError):
        return 0, 0


def cleanup_interrupted_reviews(root: Path) -> list[str]:
    """Remove abandoned worktrees and branches made by the review step."""
    name = re.compile(r"review/(?:standards|contract)-\d+-\d+-[0-9a-f]{8}$")
    entries = sh(["git", "worktree", "list", "--porcelain"], root).stdout.splitlines()
    worktrees: list[tuple[str, str]] = []
    path = ""
    for line in entries:
        if line.startswith("worktree "):
            path = line[9:]
        elif line.startswith("branch refs/heads/"):
            branch = line[len("branch refs/heads/"):]
            if name.fullmatch(branch):
                worktrees.append((path, branch))

    removed: list[str] = []
    known: set[str] = set()
    for folder, branch in worktrees:
        result = sh(["git", "worktree", "remove", "--force", folder], root, check=False)
        if result.returncode == 0:
            removed.append(f"worktree {folder}")
        result = sh(["git", "branch", "-D", branch], root, check=False)
        if result.returncode == 0:
            removed.append(f"branch {branch}")
        known.add(branch)

    branches = sh(["git", "branch", "--list", "review/*"], root, check=False).stdout
    for line in branches.splitlines():
        branch = line.strip().lstrip("* ")
        if branch not in known and name.fullmatch(branch):
            result = sh(["git", "branch", "-D", branch], root, check=False)
            if result.returncode == 0:
                removed.append(f"branch {branch}")
    return removed


def ready_pieces(gh, log: Optional[Callable[[str], None]] = None) -> list[int]:
    """Retry GitHub's ready-label search briefly when its index lags a move."""
    for attempt in range(READY_RETRIES + 1):
        pieces = sorted(i["number"] for i in gh.issues_with_label(STATE_PREFIX + "ready"))
        if pieces or attempt == READY_RETRIES:
            return pieces
        message = (f"ready label search is empty; retrying in {READY_RETRY_SECONDS} seconds "
                   f"({attempt + 1}/{READY_RETRIES})")
        if log:
            log(message)
        else:
            print(message, flush=True)
        time.sleep(READY_RETRY_SECONDS)
    return []
