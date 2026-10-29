"""Run-start recovery and GitHub's briefly delayed ready search."""
from __future__ import annotations

import hashlib
import os
import re
import time
from pathlib import Path
from typing import Callable, Optional

from loopkit import STATE_PREFIX, Refused, branch_name, main_ref, rev, sh

READY_RETRIES = 4
READY_RETRY_SECONDS = 5


def worktree_home(root: Path) -> Path:
    """Keep build folders outside the project and its test discovery."""
    base = os.environ.get("LOOP_WORKTREES") or str(
        Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
        / "ai-loop-kit" / "worktrees")
    key = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:8]
    return Path(base) / f"{root.name}-{key}"


def worktrees(root: Path) -> list[dict[str, str]]:
    output = sh(["git", "worktree", "list", "--porcelain", "-z"], root).stdout
    return [dict(line.partition(" ")[::2] for line in entry.split("\0"))
            for entry in output.strip("\0").split("\0\0") if entry]


def existing_worktree(root: Path, n: int) -> Path | None:
    """Find the build folder, refusing a checkout owned by someone else."""
    owned = (worktree_home(root) / f"piece-{n}", root / ".loop" / "worktrees" / f"piece-{n}")
    for entry in worktrees(root):
        if entry.get("branch") == f"refs/heads/{branch_name(n)}":
            path = Path(entry["worktree"])
            if path.resolve() not in {folder.resolve() for folder in owned}:
                raise Refused(f"{branch_name(n)} is already checked out at {path}",
                              "finish work there and switch that checkout to another branch")
            return path
    return None


def worktree_reason(root: Path, folder: Path, merged_into: str = "", made=None) -> str:
    """Return why cleanup must keep a folder. Ignored artefacts, and files `made` accepts as
    the kit's own (such as test caches), do not count."""
    entries = worktrees(root)
    entry = next((item for item in entries
                  if Path(item["worktree"]).resolve() == folder.resolve()), None)
    if not entry:
        return "not a registered worktree"
    if entry == entries[0] or folder.resolve() == root.resolve():
        return "the project checkout"
    if "locked" in entry:
        return "locked worktree: " + entry["locked"]
    status = sh(["git", "status", "--porcelain", "--untracked-files=all"], folder, check=False)
    if status.returncode:
        return status.stderr.strip() or "cannot check worktree status"
    if status.stdout.strip() and not (made and all(
            made(line[3:]) for line in status.stdout.splitlines())):
        return "uncommitted work"
    if sh(["git", "rev-parse", "--verify", "MERGE_HEAD"], folder, check=False).returncode == 0:
        return "unfinished merge"
    merged_into = merged_into or main_ref(root)
    if sh(["git", "merge-base", "--is-ancestor", "HEAD", merged_into],
          folder, check=False).returncode:
        return f"unmerged work (not merged into {merged_into})"
    return ""


def remove_worktree(root: Path, folder: Path, merged_into: str = "", made=None) -> bool:
    try:
        reason = worktree_reason(root, folder, merged_into, made)
        if not reason:
            result = sh(["git", "worktree", "remove", *(["--force"] if made else []), str(folder)],
                        root, check=False)
            if result.returncode == 0:
                return True
            reason = result.stderr.strip() or result.stdout.strip() or "git worktree remove failed"
    except (OSError, RuntimeError, Refused) as error:
        reason = str(error)
    print(f"kept worktree {folder}: {reason}", flush=True)
    return False


def _probe_file(path: Path) -> tuple:
    if path.is_symlink():
        return os.readlink(path), 0
    if path.is_file():
        return path.read_bytes(), path.stat().st_mode
    return None, -1 if path.exists() else 0


def capture_probe_files(folder: Path, names: list[str]) -> dict:
    return {"head": rev(folder, "HEAD"),
            "index": sh(["git", "write-tree"], folder).stdout.strip(),
            "files": {name: _probe_file(folder / name) for name in names}}


def restore_probe_files(folder: Path, before: dict, injected: dict) -> None:
    """Undo only injected files whose working and staged contents still match."""
    if rev(folder, "HEAD") != injected["head"]:
        return
    for name, expected in injected["files"].items():
        path = folder / name
        if _probe_file(path) != expected or sh(
                ["git", "diff", "--cached", "--quiet", injected["index"], "--", name],
                folder, check=False).returncode:
            continue
        if sh(["git", "diff", "--cached", "--quiet", before["index"], "--", name],
              folder, check=False).returncode:
            sh(["git", "restore", "--source=" + before["index"], "--staged", "--", name], folder)
        data, mode = before["files"][name]
        if path.is_symlink() or data is None or isinstance(data, str):
            path.unlink(missing_ok=True)
        if isinstance(data, str):
            path.symlink_to(data)
        elif data is not None:
            path.write_bytes(data)
            path.chmod(mode)


def release_worktree(root: Path, n: int) -> None:
    try:
        folder = existing_worktree(root, n)
    except (Refused, OSError, RuntimeError) as error:
        print(f"kept worktree for {branch_name(n)} in {root}: {error}", flush=True)
        return
    if folder:
        remove_worktree(root, folder, branch_name(n))


def cleanup_interrupted_reviews(root: Path, prefixes: tuple[str, ...] = ()) -> list[str]:
    """Remove review folders only when their work survives on the piece branch."""
    name = re.compile(r"review/(?:standards|contract)-(\d+)-\d+-[0-9a-f]{8}$")
    removed: list[str] = []
    kept: set[str] = set()
    for entry in worktrees(root):
        branch = entry.get("branch", "").removeprefix("refs/heads/")
        match = name.fullmatch(branch)
        if not match or (prefixes and not branch.startswith(prefixes)):
            continue
        base = branch_name(int(match[1]))
        base = base if rev(root, base) else ""
        folder = Path(entry["worktree"])
        if remove_worktree(root, folder, base):
            removed.append(f"worktree {folder}")
        else:
            kept.add(branch)
    branches = sh(["git", "branch", "--list", "review/*"], root).stdout
    for line in branches.splitlines():
        branch = line.strip().lstrip("*+ ")
        match = name.fullmatch(branch)
        if not match or branch in kept or (prefixes and not branch.startswith(prefixes)):
            continue
        base = branch_name(int(match[1]))
        base = base if rev(root, base) else main_ref(root)
        if sh(["git", "merge-base", "--is-ancestor", branch, base], root, check=False).returncode:
            print(f"kept branch {branch}: unmerged work (not merged into {base})", flush=True)
            continue
        result = sh(["git", "branch", "-D", branch], root, check=False)
        if result.returncode == 0:
            removed.append(f"branch {branch}")
        else:
            print(f"kept branch {branch}: {result.stderr.strip()}", flush=True)
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
