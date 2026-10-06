"""The attempt log: what the gate saw in each attempt, kept in the piece record.

The gate writes one `attempt` entry for each attempt it judges, through
`loop.evidence`. So the log is hash-chained and keyed like the rest of the piece
record, and no builder can write it: the deny rules cover `.agents/pieces/`, and
the key sits outside the project. The next builder's brief reads it with `render`.

An entry holds:

- `n`: the attempt number, counted since the piece last left shaping;
- `result`: `passed` or `failed`;
- `head` and `base`: the commits judged and the commit the piece was cut from;
- `at`: the date;
- `possible_gaming`: true when a finding is one the design logs as possible gaming;
- `findings`: one item for each fault, with a `check`, a `text` and a `gaming` flag.

A finding about a held-out case never holds the case, its text or its output. It
says how many hidden cases failed and no more, so the log leaks nothing the
builder may not read.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

KIND = "attempt"
MAX_TEXT = 400

# The checks, in the design's order. A finding names the check that found it.
CHECKS = (
    "fingerprint",
    "frozen-bar",
    "visible-judge",
    "held-out",
    "new-test-lint",
    "must-stay-the-same",
    "touches",
    "dependency",
)


def finding(check: str, text: str, *, gaming: bool = False) -> dict[str, Any]:
    """One fault. `gaming` marks the faults the design logs as possible gaming."""
    if check not in CHECKS:
        raise ValueError(f"{check!r} is not a check of the attempt gate")
    clipped = " ".join(text.split())
    if len(clipped) > MAX_TEXT:
        clipped = clipped[: MAX_TEXT - 3].rstrip() + "..."
    return {"check": check, "text": clipped, "gaming": bool(gaming)}


def entry(
    *,
    number: int,
    result: str,
    head: str,
    base: str,
    at: str,
    findings: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """The record entry of one attempt."""
    if result not in ("passed", "failed"):
        raise ValueError(f"{result!r} is not an attempt result")
    items = [dict(item) for item in findings]
    return {
        "kind": KIND,
        "n": number,
        "result": result,
        "head": head,
        "base": base,
        "at": at,
        "possible_gaming": any(item.get("gaming") for item in items),
        "findings": items,
    }


def attempts(record: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The attempts since the piece last left shaping, oldest first.

    This is the window `loop.moves` uses for its repeat counter: a move out of
    shaping starts a new count.
    """
    found: list[dict[str, Any]] = []
    for item in record:
        kind = item.get("kind")
        if kind == "move" and item.get("from") == "shaping":
            found = []
        elif kind == KIND:
            found.append(dict(item))
    return found


def used(record: Sequence[Mapping[str, Any]]) -> int:
    """How many attempts the piece has used since it last left shaping."""
    return len(attempts(record))


def failed(record: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in attempts(record) if item.get("result") == "failed"]


def render(record: Sequence[Mapping[str, Any]]) -> str:
    """The log as text for a builder's brief. It is outside text, so it goes in a data block."""
    items = attempts(record)
    if not items:
        return "No attempt has been judged yet."
    lines: list[str] = []
    for item in items:
        lines.append(
            f"Attempt {item['n']} ({item.get('at', '')}, commit {str(item.get('head', ''))[:7]}): "
            f"{item['result']}."
        )
        if item.get("possible_gaming"):
            lines.append("  The gate logged this attempt as possible gaming.")
        for found in item.get("findings", []):
            lines.append(f"  - {found['check']}: {found['text']}")
    return "\n".join(lines)
