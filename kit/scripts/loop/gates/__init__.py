"""The checks of each move, one module per move: `loop/gates/<name>.py`.

`loop/states.py` names the module for each move. `loop/moves.py` loads it and
calls its `check(ctx)`, which returns a `CheckResult`. A move whose module is
not installed yet is refused with a `next:` line, so a later piece adds its
module and changes no shared file.

The gate applies the shared rules itself, before any module runs: the table,
the reason on a move back, the anti-circle rule, the repeat counter, the two
reads and the label checks. A module holds only the checks of its own move.

A passing result may carry data the gate records:

- `fingerprint`: a fingerprint from `loop.fingerprint.take`, taken at ready;
- `body`: a new issue body, a change the gate itself makes to the spec;
- `must_look`: the must-look reasons the ready gate wrote, a list of text. The
  gate records them on the move, and a piece with one gets individual review;
- `entries`: more entries for the piece record, such as the judge runs and the
  test lists the check made. Each has a `kind` that the gate's own kinds do not use.

A refusal may carry `send_back`: the reason the gate gives to move 3, which sends the
piece back to shaping. Only the claim sets it, and `loop.moves` makes that move itself.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from loop.paths import Paths
from loop.states import Move


@dataclass(frozen=True)
class CheckContext:
    number: int
    move: Move
    origin: str
    target: str
    reason: str | None
    title: str
    body: str
    spec: Mapping[str, Any] | None  # None when the body holds a block the parser refuses
    record: Sequence[Mapping[str, Any]]
    paths: Paths
    options: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    failures: tuple[str, ...] = ()
    next_command: str = ""
    data: Mapping[str, Any] = field(default_factory=dict)


def passed(**data: Any) -> CheckResult:
    return CheckResult(ok=True, data=data)


def refused(failures: Sequence[str], next_command: str) -> CheckResult:
    return CheckResult(ok=False, failures=tuple(failures), next_command=next_command)


def reason_only(ctx: CheckContext) -> CheckResult:
    """The check of a move whose only condition is the shared rules (a written reason)."""
    return passed()
