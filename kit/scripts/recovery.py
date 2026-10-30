"""Finish a piece whose submit was recorded before the run died."""
from __future__ import annotations

from pathlib import Path

import gate
from loopkit import STATE_PREFIX, GitHub, Refused, branch_name, records, rev, sh

NOTE = ("The run stopped after the gate recorded the submit, so the next run finished the "
        "move. The review was not repeated and its findings were not kept.")


def _judge_output(root: Path, n: int, attempts: int) -> str:
    """The judge output the submit saved in its log, or a line saying it was lost."""
    try:
        text = (root / ".loop" / "logs" / f"piece-{n}-attempt-{attempts}.log").read_text()
    except OSError:
        return "The judge output was not kept after the crash."
    return text.rpartition("Submit judge output:\n")[2].strip() or "The judge output was empty."


def finish_submit(gh: GitHub, root: Path, n: int) -> bool:
    """Move a building piece to approval when its newest record is a submit of the pushed head.

    Returns false, leaving the piece as it is, when the submit does not match the head of
    piece/<n> or the branch cannot be fetched. Posts no second submit record.
    """
    import pr  # pr imports run, which imports this module
    import run
    issue = gh.issue(n)
    if STATE_PREFIX + "building" not in issue["labels"]:
        return False
    found = records(gh.comments(n))
    submit = found[-1] if found else {}
    if submit.get("move") != "submit" or not submit.get("commit"):
        return False
    if sh(["git", "fetch", "--quiet", "origin", branch_name(n)], root, check=False).returncode:
        return False
    head = sh(["git", "rev-parse", "FETCH_HEAD"], root, check=False).stdout.strip()
    if head != submit["commit"]:
        return False
    try:
        folder = run.worktree(root, n)
    except Refused:
        return False
    if rev(folder, "HEAD") != head:
        return False
    attempts = int(submit.get("attempts") or 0)
    judged = _judge_output(root, n, attempts)
    gh.set_labels(n, [STATE_PREFIX + "approval"], [STATE_PREFIX + "building"])
    gate.run_event(root, "submit", n, "approval", attempts, "submit")
    existing = gh.pr_for_branch(branch_name(n))
    url = existing["url"] if existing and existing["state"] == "OPEN" else ""
    pr.finish_pull_request(gh, root, folder, n, issue, attempts, judged,
                           {"reviewer_note": NOTE}, url, judged)
    return True
