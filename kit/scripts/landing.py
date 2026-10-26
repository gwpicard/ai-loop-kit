"""With `Base merges: run`, the run merges a gated piece into the base branch itself.

It never merges into main, and it leaves a piece for the person when a merge
could do harm before anyone reads it. A failure here never stops the run.
"""
from __future__ import annotations

from pathlib import Path

import gate
from loopkit import GitHub, Refused, base_branch, base_merges, branch_name, rev, sh

# Files that act as soon as they land: workflows run with the repository's
# secrets, hooks run on every commit, and AGENTS.md changes the loop's rules.
RUNS_CODE = (".github/", ".githooks/")
RUNS_CODE_FILES = ("AGENTS.md",)


def runs_code(paths: list[str]) -> list[str]:
    return [p for p in paths if p.startswith(RUNS_CODE) or p in RUNS_CODE_FILES]


def land(gh: GitHub, root: Path, folder: Path, n: int, result: str, review: dict) -> str:
    """Merge the piece's pull request into the base, then mark it done."""
    try:
        if not base_merges(root):
            return result
        base = base_branch(root)
    except Refused as error:
        return f"{result} Not merged: {error.reason}"
    url = (gh.pr_for_branch(branch_name(n)) or {}).get("url", "")
    if review.get("contract_findings"):
        return (f"{result} Not merged: the contract review left findings. "
                "next: read them in the pull request, then merge it or reshape the piece")
    head = rev(folder, "HEAD") or ""
    sh(["git", "fetch", "--quiet", "origin", base], folder, check=False)
    changed = sh(["git", "diff", "--name-only", f"origin/{base}...HEAD"], folder).stdout.split()
    risky = runs_code(changed)
    if risky:
        why = (f"It changes {', '.join(risky)}. Workflows and hooks run code, with the "
               "repository's secrets, as soon as they land; AGENTS.md changes the loop's own "
               f"rules. So the run did not merge it into {base}. Read those files in the pull "
               "request, then merge it on GitHub and run gate.py sync, which marks it done and "
               "updates the final pull request. Pieces that depend on it wait until then.")
        gh.comment(n, f"**Run:** not merged into `{base}`. {why}")
        return f"{result} Not merged: {why}"
    if sh(["git", "merge-base", "--is-ancestor", f"origin/{base}", head], folder,
          check=False).returncode:
        return (f"{result} Not merged: {base} moved after the gate passed. "
                "next: merge it on GitHub after a look, or run the piece again")
    try:
        gh.merge_pr(url, base, head)
    except Exception as error:  # a conflict, a moved branch, or GitHub said no
        if (gh.pr_for_branch(branch_name(n)) or {}).get("state") != "MERGED":
            return f"{result} Not merged: {error}"
    sh(["git", "fetch", "--quiet", "origin", base], folder, check=False)
    try:
        gate.move(gh, root, n, "done")
    except Exception as error:
        return (f"piece {n}: merged into {base}, but the gate could not mark it done: "
                f"{error}. next: run gate.py sync")
    return f"piece {n}: merged into {base}: {url}"
