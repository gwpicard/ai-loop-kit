"""Prove a written judge on the base before the judge writer finishes.

The proof is the ready check itself, so a judge that fails here for the wrong reason is
repaired by the writer, not found later by the shaper.
"""
from __future__ import annotations

from pathlib import Path

import holds
from loopkit import GitHub, parse_spec, refresh_main, repo_root, sh

SKIPPED = "base proof skipped: pieces {} are not done; the base check runs when they are"


def prove(folder: Path, data: dict) -> str:
    """Run the ready check on the committed judge; return the line to print.

    `data` is the writer's input. Raises `JudgeRefused` when the judge needs repair and
    `Refused` for any other refusal. A piece with unfinished blockers has no base to fail on
    yet, so its proof is skipped.
    """
    import gate  # lazily: the gate imports the launcher's neighbours
    root = repo_root(folder)
    number = int(sh(["git", "branch", "--show-current"], root).stdout.strip().split("/")[-1])
    gh = GitHub(root)
    issue = gh.issue(number)
    blockers = holds.unfinished(gh, parse_spec(issue["body"] or "").risks.get("depends_on", ()))
    if blockers:
        return SKIPPED.format(", ".join(map(str, blockers)))
    refresh_main(root)
    gate.check_ready(gh, root, issue)
    return "base proof passed: the judge fails on the base for the right reason"


def retry_prompt(prompt: str, refusal) -> str:
    """The writer's prompt with the ready check's refusal added."""
    return (prompt + "\n\nYour judge was committed, then refused on the base:\n"
            f"{refusal.reason}\nnext: {refusal.next_step}\n"
            "Fix the judge files, then finish with the verdict as before.")
