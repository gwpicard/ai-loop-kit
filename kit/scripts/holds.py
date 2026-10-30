"""Order and holds: the run builds a piece only when every piece it depends on is done.

A hold is worked out on each pick from the issues themselves and never stored.
"""
from __future__ import annotations

from loopkit import STATE_PREFIX, GitHub, Refused, last_record

MARK = "held until"


def state(gh: GitHub, n: int) -> str:
    """A piece's state from its own issue, not from the lagging label search."""
    try:
        labels = [label for label in gh.issue(n)["labels"] if label.startswith(STATE_PREFIX)]
    except Exception:  # a missing issue, or GitHub could not answer
        return "missing"
    return labels[0][len(STATE_PREFIX):] if len(labels) == 1 else "unreadable"


def check(gh: GitHub, n: int, depends: tuple[int, ...]) -> None:
    """At ready, refuse a piece that names itself or a piece that is missing or dropped."""
    for d in depends:
        if d == n:
            raise Refused(f"piece {n} depends on itself", "take its own number out of Depends on")
        found = state(gh, d)
        if found in ("missing", "unreadable", "dropped"):
            raise Refused(f"piece {n} depends on piece {d}, which is {found}",
                          "fix the Depends on line, or reopen that piece")


def unfinished(gh: GitHub, depends: tuple[int, ...]) -> list[int]:
    """The pieces in Depends on that are not done. Ready is then pending its base check."""
    return [d for d in depends if state(gh, d) != "done"]


def require_checked(ready: dict) -> None:
    """A claim needs the base check: a pending ready record has not had it yet."""
    if ready.get("base_check") == "pending":
        blockers = ", ".join(str(d) for d in ready.get("blockers", []))
        raise Refused(f"the base check has not run; it runs when pieces {blockers} are done",
                      "the run does the base check when the blockers are done; build them first")


def wanted(gh: GitHub, pieces: list[int]) -> dict[int, list[int] | None]:
    """What each piece waits for, frozen in its ready record. None: the record could not
    be read, so the piece is held rather than built too early."""
    wants: dict[int, list[int] | None] = {}
    for n in pieces:
        try:
            ready = last_record(gh.comments(n), "ready") or {}
            wants[n] = [int(d) for d in ready.get("risks", {}).get("depends_on", [])]
        except Exception:
            wants[n] = None
    return wants


def waves(pieces: list[int], wants: dict[int, list[int] | None]) -> dict[int, int]:
    """Wave 1 needs no piece in the list; wave k needs one in wave k - 1. A cycle has none."""
    out: dict[int, int] = {}
    while True:
        more = {n: 1 + max([out[d] for d in (wants.get(n) or []) if d in pieces] or [0])
                for n in pieces if n not in out
                and all(d in out or d not in pieces for d in (wants.get(n) or []))}
        if not more:
            return out
        out.update(more)


def pick(gh: GitHub, pending: list[int], wants: dict[int, list[int] | None],
         tried: dict[int, str]) -> tuple[int | None, dict[int, str]]:
    """The first pending piece whose dependencies are all done. When none is, say why
    each piece waits."""
    seen: dict[int, str] = {}
    waiting: dict[int, list[int]] = {}
    for n in pending:
        if wants.get(n, []) is None:
            waiting[n] = []
            continue
        for d in wants.get(n) or []:
            if d not in seen:
                seen[d] = state(gh, d)
        waiting[n] = [d for d in wants.get(n) or [] if seen[d] != "done"]
        if not waiting[n]:
            return n, {}
    return None, {n: _line(n, deps, seen, tried, waiting) for n, deps in waiting.items()}


def _line(n: int, deps: list[int], seen: dict[int, str], tried: dict[int, str],
          waiting: dict[int, list[int]]) -> str:
    if not deps:
        return (f"piece {n}: {MARK} its ready record can be read. "
                "next: check the piece on GitHub, then run again")
    d = deps[0]
    if d in waiting:
        why, step = "it waits on a piece that is also held", f"see the line for piece {d}"
    elif d in tried:
        why = "this run: " + tried[d].split(": ", 1)[-1][:120]
        step = f"fix piece {d}, then run again"
    elif seen[d] == "approval":
        why, step = "it is in approval", "merge its pull request, run gate.py sync, then run again"
    elif seen[d] in ("shaping", "dropped"):
        why = f"it is in {seen[d]}"
        step = (f"finish or drop piece {d}; if this piece no longer needs it, take it out of "
                "Depends on and make this piece ready again")
    else:
        why, step = f"it is in {seen[d]}", f"build piece {d} first, then run again"
    return f"piece {n}: {MARK} piece {d} is done ({why}). next: {step}"
