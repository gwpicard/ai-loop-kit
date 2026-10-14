"""The plan of a run: the order of the pieces, the slots, and who may start now.

Pure functions. They read no file and start nothing. The run loop gives them the pieces it read
from the gate's record.

- Dependencies come first. A piece waits for the pieces whose issue numbers are in its
  `blockers`, when those pieces are in the same run. A blocker outside the run must already be
  done, and the claim gate checks that.
- Serial chains are shown first, the longest first, then the single pieces.
- Two pieces that touch one area never run at once. The claim gate refuses the second anyway,
  so the plan does not ask it to.
- Slots are sized from free memory and capped by the policy's `builder_cap`.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

SLOT_MEMORY_MB = 1024  # memory one more builder needs above the floor


class PlanError(Exception):
    """A plan that cannot be made. The message names the pieces."""

    def __init__(self, message: str, next_command: str) -> None:
        super().__init__(message)
        self.next_command = next_command


@dataclass(frozen=True)
class PieceInfo:
    number: int
    title: str = ""
    issue: int | None = None
    areas: frozenset[str] = field(default_factory=frozenset)
    blockers: frozenset[int] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Plan:
    chains: tuple[tuple[int, ...], ...]
    singles: tuple[int, ...]
    order: tuple[int, ...]
    waves: tuple[tuple[int, ...], ...]
    slots: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "slots": self.slots,
            "chains": [list(c) for c in self.chains],
            "singles": list(self.singles),
            "order": list(self.order),
            "waves": [list(w) for w in self.waves],
        }


def slots(
    free_memory_mb: int | None, *, floor_mb: int, cap: int, per_slot_mb: int = SLOT_MEMORY_MB
) -> int:
    """How many builders may run at once. One at the floor, one more for each `per_slot_mb`.

    Unknown free memory gives one slot, since the plan never claims more than it can see room
    for. The result is never below 1 and never above `cap`.
    """
    if free_memory_mb is None:
        return 1
    room = max(0, free_memory_mb - floor_mb) // per_slot_mb
    return max(1, min(cap, 1 + room))


def _blockers_in_run(pieces: Sequence[PieceInfo]) -> dict[int, set[int]]:
    """For each piece, the numbers of the pieces in this run that must be built first."""
    by_issue = {p.issue: p.number for p in pieces if p.issue is not None}
    found: dict[int, set[int]] = {}
    for p in pieces:
        found[p.number] = {
            by_issue[b] for b in p.blockers if b in by_issue and by_issue[b] != p.number
        }
    return found


def _topological(numbers: Iterable[int], needs: dict[int, set[int]]) -> list[int]:
    """The numbers with every blocker before the piece it blocks. Ties go by number."""
    left = sorted(numbers)
    done: list[int] = []
    placed: set[int] = set()
    while left:
        ready = [n for n in left if needs[n] <= placed]
        if not ready:
            raise PlanError(
                "these pieces wait for one another, so none can go first: "
                + ", ".join(str(n) for n in left),
                "remove one blocked-by link between them on GitHub, then run.py --plan again",
            )
        pick = ready[0]
        done.append(pick)
        placed.add(pick)
        left.remove(pick)
    return done


def _components(numbers: Sequence[int], needs: dict[int, set[int]]) -> list[list[int]]:
    """Groups of pieces joined by blocked-by links, each sorted by number."""
    parent = {n: n for n in numbers}

    def find(n: int) -> int:
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    for n, blockers in needs.items():
        for b in blockers:
            parent[find(n)] = find(b)
    groups: dict[int, list[int]] = {}
    for n in sorted(numbers):
        groups.setdefault(find(n), []).append(n)
    return list(groups.values())


def make_plan(pieces: Iterable[PieceInfo], *, slots: int) -> Plan:
    """The order, the chains and the waves for `pieces`. Refuses a cycle."""
    listed = sorted(pieces, key=lambda p: p.number)
    numbers = [p.number for p in listed]
    needs = _blockers_in_run(listed)
    chains: list[tuple[int, ...]] = []
    singles: list[int] = []
    for group in _components(numbers, needs):
        if len(group) == 1:
            singles.append(group[0])
        else:
            chains.append(tuple(_topological(group, {n: needs[n] & set(group) for n in group})))
    chains.sort(key=lambda c: (-len(c), c[0]))
    singles.sort()
    order = tuple(n for chain in chains for n in chain) + tuple(singles)
    by_number = {p.number: p for p in listed}
    waves: list[tuple[int, ...]] = []
    placed: set[int] = set()
    left = list(order)
    while left:
        wave: list[int] = []
        taken: set[str] = set()
        for n in left:
            if len(wave) >= max(1, slots):
                break
            if not needs[n] <= placed:
                continue
            if by_number[n].areas & taken:
                continue
            wave.append(n)
            taken |= by_number[n].areas
        placed.update(wave)
        left = [n for n in left if n not in wave]
        waves.append(tuple(wave))
    return Plan(tuple(chains), tuple(singles), order, tuple(waves), max(1, slots))


def runnable(
    pieces: Iterable[PieceInfo],
    *,
    order: Sequence[int],
    pending: Collection[int],
    built: Collection[int],
    occupied: Collection[int],
    free_slots: int,
) -> list[int]:
    """The pending pieces that may start now, in plan order, at most `free_slots`.

    A piece may start when every blocker in the run is built, and none of its areas is held by
    an occupied piece (running, or parked inside building) or by a piece chosen before it.
    """
    listed = {p.number: p for p in pieces}
    needs = _blockers_in_run(list(listed.values()))
    held: set[str] = set()
    for n in occupied:
        if n in listed:
            held |= listed[n].areas
    chosen: list[int] = []
    for n in order:
        if len(chosen) >= free_slots:
            break
        if n not in pending or n not in listed:
            continue
        if not needs[n] <= set(built):
            continue
        if listed[n].areas & held:
            continue
        chosen.append(n)
        held |= listed[n].areas
    return chosen
