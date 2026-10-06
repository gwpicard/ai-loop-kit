"""Where each outcome of an attempt goes.

A builder ends with one of five hand-offs, and the gate judges the attempt. Every result has
one route: the gate judges (move 5), the piece goes back to shaping (move 6), back to ready
(move 7), or it stays where it is. This module decides the route and nothing else. The run loop
makes the move through the gate, and never writes a label or a record itself.

The run keeps no count of attempts. The gate's attempt log in the piece record is the count
(`loop.attempt_log`), and `Judged.attempts` is read from it. A gave-up attempt, a stuck attempt
and a bar change all count, and the way each reaches the count is the gate's judging of the
branch: the gate fails what the builder did not finish.

"No real improvement" is decided here, from the judge results in that log: two failed attempts
in a row that name no fewer failing spec IDs and no fewer other faults.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from loop import sessions

# The design's outcomes table, column "Counts as an attempt".
OUTCOME_COUNTS: dict[str, bool] = {
    "gate-passes": False,
    "gate-fails": True,
    "attempts-out": True,
    "no-real-improvement": True,
    "bar-is-wrong": False,
    "needs-the-person": False,
    "blocked-by-environment": False,
    "usage-limit": False,
    "stuck": True,
    "gave-up": True,
    "bar-changed": True,
    "held-out-gap": True,
}

_IDS = re.compile(r"naming ((?:[A-Z]{2,}-\d+(?:, )?)+)")


def counts_as_attempt(outcome: str) -> bool:
    """Whether an outcome counts as an attempt. An unknown outcome raises KeyError."""
    return OUTCOME_COUNTS[outcome]


@dataclass(frozen=True)
class Route:
    """The one route of a result.

    `action` is one of: judge, send-back, give-back, park-person, built, next-attempt,
    sent-back, wait-person. `move` is the gate's move number, or None when the piece stays.
    """

    action: str
    move: int | None = None
    target: str | None = None
    reason: str = ""
    counts: bool = False
    next_command: str = ""


def route_handoff(handoff: Mapping[str, Any] | None, exit_code: int) -> Route:
    """The route of a builder session's hand-off. `None` means the session left none."""
    if handoff is None:
        if exit_code == 0:
            return Route(
                "judge", 5,
                reason="the session ended with no hand-off, so the gate judges the branch as it is",
            )
        return Route(
            "give-back", 7, "ready",
            reason=f"the builder session failed with exit code {exit_code} and left no hand-off, "
            "so the piece goes back to ready and no attempt is counted",
        )
    outcome = handoff.get("outcome")
    if outcome not in sessions.OUTCOMES:
        raise ValueError(f"{outcome!r} is not a hand-off outcome")
    detail = str(handoff.get(sessions.HANDOFF_FIELD[str(outcome)], "")).strip()
    if outcome == "done":
        return Route("judge", 5)
    if outcome == "gave-up":
        return Route("judge", 5, reason=f"the builder gave up: {detail}")
    if outcome == "bar-is-wrong":
        return Route("send-back", 6, "shaping", reason=f"The builder says the bar is wrong: {detail}")
    if outcome == "needs-the-person":
        return Route("park-person", None, reason=detail)
    return Route(
        "give-back", 7, "ready",
        reason=f"The builder is blocked by its environment: {detail}",
    )


@dataclass(frozen=True)
class Judged:
    """What the gate said to move 5, and the attempt log after it."""

    passed: bool
    sent_back: bool  # the gate itself made move 6 (no attempt was left)
    counted: bool  # the gate logged a new attempt
    attempts: Sequence[Mapping[str, Any]]  # the attempt log since the piece left shaping
    limit: int
    next_command: str = ""
    message: str = ""


def failing_ids(attempt: Mapping[str, Any]) -> set[str]:
    """The spec IDs the visible judge named in a failed attempt."""
    found: set[str] = set()
    for item in attempt.get("findings", []):
        if item.get("check") != "visible-judge":
            continue
        match = _IDS.search(str(item.get("text", "")))
        if match:
            found |= {part.strip() for part in match.group(1).split(",") if part.strip()}
    return found


def _other_findings(attempt: Mapping[str, Any]) -> int:
    return sum(1 for item in attempt.get("findings", []) if item.get("check") != "visible-judge")


def improved(previous: Mapping[str, Any], latest: Mapping[str, Any]) -> bool:
    """Whether `latest` is a real improvement on `previous`, by their judge results.

    An attempt logged as possible gaming is never one. Otherwise it is one when it names fewer
    failing spec IDs, or the same number of them and fewer other faults.
    """
    if latest.get("possible_gaming"):
        return False
    before, after = len(failing_ids(previous)), len(failing_ids(latest))
    if after != before:
        return after < before
    return _other_findings(latest) < _other_findings(previous)


def _said(attempt: Mapping[str, Any]) -> str:
    items = "; ".join(
        f"{f['check']}: {str(f['text'])[:160]}" for f in attempt.get("findings", [])
    )
    return f"attempt {attempt['n']} ({items or 'no finding'})"


def no_real_improvement(attempts: Sequence[Mapping[str, Any]], limit: int) -> str | None:
    """The reason to stop early, or None. Needs two failed attempts and one attempt left."""
    failed = [a for a in attempts if a.get("result") == "failed"]
    if len(failed) < 2 or len(failed) >= limit:
        return None
    if improved(failed[-2], failed[-1]):
        return None
    return (
        f"There was no real improvement: attempt {failed[-1]['n']} fared no better than "
        f"attempt {failed[-2]['n']}, so the piece goes back to shaping before the attempts run "
        "out. " + " | ".join(_said(a) for a in failed)
    )


def route_judged(judged: Judged) -> Route:
    """The route after the gate judged an attempt (move 5)."""
    if judged.passed:
        return Route("built", 5)
    if judged.sent_back:
        return Route("sent-back", 6, "shaping", reason=judged.message, counts=True)
    if not judged.counted:
        return Route(
            "wait-person", None,
            reason=judged.message or "the gate refused to judge the attempt and counted nothing",
            next_command=judged.next_command,
        )
    reason = no_real_improvement(judged.attempts, judged.limit)
    if reason is not None:
        return Route("send-back", 6, "shaping", reason=reason, counts=True)
    return Route("next-attempt", None, counts=True)
