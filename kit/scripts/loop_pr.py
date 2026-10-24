"""The pull request from the base branch into main: one review for every piece on it."""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path

import holds
from loopkit import CHECK_FILES, GitHub, base_branch, loop_settings, rev, sh

BODY_LIMIT = 60000  # GitHub refuses a body above 65,536 characters
HELD = ("back to shaping", "refused", "stopped by an error", "held until")


def touched(root: Path, commit: str, protected: list[str]) -> list[str]:
    """The check settings and protected paths that one merged piece changed."""
    names = sh(["git", "diff", "--name-only", f"{commit}^1", commit], root, check=False).stdout
    return [name for name in names.split()
            if any(fnmatch.fnmatch(name if "/" in p else name.rsplit("/", 1)[-1], p)
                   for p in CHECK_FILES)
            or name.rsplit("/", 1)[-1] in ("package.json", "pyproject.toml")
            or any(name == p.rstrip("/") or name.startswith(p.rstrip("/") + "/")
                   for p in protected)]


def in_main(root: Path, commit: str) -> bool:
    return sh(["git", "merge-base", "--is-ancestor", commit, "origin/main"], root,
              check=False).returncode == 0


def final_pull_request(gh: GitHub, root: Path, results: list[str]) -> str:
    """Open or refresh the pull request from the base into main. The run never merges it."""
    if not rev(root, "HEAD") or base_branch(root) == "main":
        return ""
    base = base_branch(root)
    sh(["git", "fetch", "--quiet", "origin", "main", base], root, check=False)
    ahead = sh(["git", "rev-list", "--count", f"origin/main..origin/{base}"], root, check=False)
    if ahead.returncode or ahead.stdout.strip() == "0":
        return ""
    protected = loop_settings(root).get("protected paths", [])
    pieces = [pr for pr in gh.pull_requests(base, "merged")
              if re.fullmatch(r"piece/\d+", pr["headRefName"])]
    lines = [f"This pull request brings `{base}` into `main`. Each piece below was built, "
             f"gated and merged into `{base}` in its own pull request, which keeps its "
             "evidence. The run never merges into `main`.", "", f"## Pieces on `{base}`"]
    entries = []
    for pr in sorted(pieces, key=lambda item: item.get("mergedAt") or ""):
        commit = (pr.get("mergeCommit") or {}).get("oid", "")
        if not commit or in_main(root, commit):
            continue
        risky = touched(root, commit, protected)
        entries.append((int(pr["headRefName"].split("/")[1]),
                        f"- {pr['headRefName']}: {pr['title']} ({pr['url']})"
                        + (f". Changes check settings or protected paths: {', '.join(risky)}"
                           if risky else "")))
    numbers = [n for n, _ in entries]
    wave = holds.waves(numbers, holds.wanted(gh, numbers)) if numbers else {}
    for k in sorted({wave.get(n, 1) for n in numbers}):  # headings only when pieces wait
        lines += ([f"### Wave {k}"] if max(wave.values(), default=1) > 1 else [])
        lines += [line for n, line in entries if wave.get(n, 1) == k]
    waiting = [f"- {pr['headRefName']}: {pr['title']} ({pr['url']})"
               for pr in gh.pull_requests(base, "open")
               if re.fullmatch(r"piece/\d+", pr["headRefName"])]
    held = [f"- {line}" for line in results if any(marker in line for marker in HELD)]
    if waiting:
        lines += ["", f"## Waiting to merge into `{base}`", *waiting]
    if held:
        lines += ["", "## Held in this run", *held]
    body = "\n".join(lines) + "\n"
    if len(body) > BODY_LIMIT:
        body = body[:BODY_LIMIT] + "\n\nThe list is cut here. Each piece pull request has the rest.\n"
    title = f"Bring {base} into main"
    if waiting or held:
        title += f" (incomplete: {len(waiting) + len(held)} not on {base})"
    existing = gh.pull_requests("main", "open", head=base)
    if existing:
        gh.edit_pr(existing[0]["url"], title, body, base="main")
        return f"Final pull request (updated): {existing[0]['url']}"
    return f"Final pull request: {gh.create_pr(base, title, body, base='main')}"
