"""The gate's table of states and moves, as data.

A piece is in one of seven states. It changes state only by one of fourteen
numbered moves, and the gate refuses any other. This module holds the table
and nothing else. `loop/moves.py` applies it.

Each move names its checks module, `loop/gates/<checks>.py`. A later piece adds
the module for its move and changes no shared file.

The design's transition table is the source. Moves back (3, 6, 7, 8, 9, 12,
13 and 14) need a written reason. The anti-circle rule applies only to moves
back to shaping (3, 6, 9, and 13 when it goes to shaping). Moves 7, 8 and 12
have a repeat counter instead: after 3 of the same move, the piece goes back to
shaping from where it stands.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

STATES = ("shaping", "ready", "building", "review", "approval", "done", "dropped")
NEW = "new"  # where move 1 starts: an idea that is not a piece yet
CLOSED = ("done", "dropped")

STATE_PREFIX = "state:"
NEEDS_YOU = "needs-you"
TYPE_PREFIX = "type:"
TYPES = ("feature", "bug", "chore")


@dataclass(frozen=True)
class Move:
    number: int
    origins: tuple[str, ...]
    targets: tuple[str, ...]
    checks: str  # the module loop/gates/<checks>.py
    summary: str

    @property
    def back(self) -> bool:
        return self.number in BACK_MOVES


MOVES: tuple[Move, ...] = (
    Move(1, (NEW,), ("shaping",), "capture", "capture by /shape, in the person's words"),
    Move(2, ("shaping",), ("ready",), "ready", "the ready gate"),
    Move(3, ("ready",), ("shaping",), "pull_back", "pulled back to shaping, with a reason"),
    Move(4, ("ready",), ("building",), "claim", "the claim gate and a free builder slot"),
    Move(5, ("building",), ("review",), "attempt", "the gate judges the attempt"),
    Move(6, ("building",), ("shaping",), "rethink", "the bar is wrong, or the attempts ran out"),
    Move(
        7,
        ("building", "approval"),
        ("ready",),
        "give_back",
        "given back with the spec untouched, never counted as an attempt",
    ),
    Move(8, ("review",), ("building",), "rebuild", "a trial join turned red, or a conflict"),
    Move(9, ("review",), ("shaping",), "respec", "a review finding shows the spec was wrong"),
    Move(10, ("review",), ("approval",), "review", "combined check green and a clean review"),
    Move(11, ("approval",), ("done",), "merge", "the merge of the exact tested commit"),
    Move(12, ("approval",), ("review",), "recheck", "the tested tree changed"),
    Move(
        13,
        ("approval",),
        ("building", "shaping"),
        "reject",
        "the person closed the pull request or commented a reason",
    ),
    Move(
        14,
        ("shaping", "ready", "dropped"),
        ("dropped", "shaping"),
        "drop",
        "dropped with a reason, or reopened into shaping with a reason",
    ),
)

BACK_MOVES = frozenset({3, 6, 7, 8, 9, 12, 13, 14})
ANTI_CIRCLE = frozenset({3, 6, 9, 13})
COUNTED = frozenset({7, 8, 12})
REPEAT_LIMIT = 3

# Move 14 joins three origins to two targets, but not every pair: dropped goes
# only to shaping, and shaping and ready go only to dropped.
_NOT_PAIRS = frozenset({("dropped", "dropped"), ("shaping", "shaping"), ("ready", "shaping")})


def _pairs() -> dict[tuple[str, str], Move]:
    table: dict[tuple[str, str], Move] = {}
    for move in MOVES:
        for origin in move.origins:
            for target in move.targets:
                if move.number == 14 and (origin, target) in _NOT_PAIRS:
                    continue
                if (origin, target) in table:
                    raise ValueError(f"{origin} to {target} is in the table twice")
                table[(origin, target)] = move
    return table


PAIRS = _pairs()


def find(origin: str, target: str) -> Move | None:
    """The move from `origin` to `target`, or None when the table has no such move."""
    return PAIRS.get((origin, target))


def by_number(number: int) -> Move:
    return next(move for move in MOVES if move.number == number)


def targets_from(origin: str) -> list[str]:
    """The states a piece in `origin` may move to, in table order."""
    return [target for (start, target) in PAIRS if start == origin]


def anti_circle(move: Move | None, target: str) -> bool:
    """True when the anti-circle rule holds for this move (a move back to shaping)."""
    return move is not None and move.number in ANTI_CIRCLE and target == "shaping"


def back_to_shaping(origin: str) -> Move:
    """The move back to shaping from `origin`, used when a counted move runs out."""
    move = find(origin, "shaping")
    if move is None or move.number not in ANTI_CIRCLE:
        raise ValueError(f"no move back to shaping starts from {origin}")
    return move


# --- labels -------------------------------------------------------------------------


def label(state: str) -> str:
    return STATE_PREFIX + state


def state_of_label(name: str) -> str | None:
    if name.startswith(STATE_PREFIX) and name[len(STATE_PREFIX) :] in STATES:
        return name[len(STATE_PREFIX) :]
    return None


def state_labels(names: Iterable[str]) -> list[str]:
    """Every `state:` label in `names`, known or not, in the order given."""
    return [name for name in names if name.startswith(STATE_PREFIX)]


LABELS: tuple[tuple[str, str, str], ...] = (
    ("state:shaping", "FBCA04", "Not buildable yet; the needs list says why"),
    ("state:ready", "0E8A16", "Spec complete, judge fails today, waits for a run"),
    ("state:building", "1D76DB", "Being built on its own piece branch"),
    ("state:review", "5319E7", "Joined to the run's branch and read by a fresh reviewer"),
    ("state:approval", "006B75", "Passed review; its pull request waits for the merge"),
    ("state:done", "0E8A16", "Merged to main"),
    ("state:dropped", "BFD4F2", "Closed on purpose, with a reason"),
    (NEEDS_YOU, "D93F0B", "Waits on the person; only the gate sets it"),
    ("type:feature", "A2EEEF", "A new behaviour"),
    ("type:bug", "D73A4A", "Something that does not work as it should"),
    ("type:chore", "C5DEF5", "Upkeep with no change in behaviour"),
)
