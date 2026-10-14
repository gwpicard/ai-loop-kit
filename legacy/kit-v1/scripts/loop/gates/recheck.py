"""Move 12: approval to review. The tested tree changed.

Two things change it. `main` moved after the final combined check, so the combined branch must
be brought up to date and checked again. Or the person rejected a piece, so the combined branch
is rebuilt without it and the others go back to be read again. The gate asks for a written
reason, as for every move back, and it proves one of the two:

- `main` moved: Git shows commits on `main` that the tested commit lacks (after a fetch);
- a piece was rejected: `--option rejected=<piece>` names a piece of the same pull request that
  is no longer in approval.

A piece in approval whose tested tree did not change has no reason to go back, so the gate
refuses the move. A piece with no pull request in its record is refused too.
"""

from __future__ import annotations

from loop import moves
from loop.gates import CheckContext, CheckResult, passed, refused
from loop.gates import merge as merge_gate


def check(ctx: CheckContext) -> CheckResult:
    entry = merge_gate.latest_entry(ctx.record)
    if entry is None:
        return refused([f"piece {ctx.number} has no pull request in its record, so no tested "
                        "tree can have changed"], f"gate.py report {ctx.number}")
    try:
        opening = merge_gate.Opening.from_entry(entry)
        asked = str(ctx.options.get("rejected", "")).strip()
        if asked:
            other = int(asked)
            piece = moves.read_piece(ctx.paths, other)
            if other not in opening.stack or piece is None:
                return refused([f"piece {other} is not a piece of this pull request"],
                               f"gate.py report {ctx.number}")
            if other == ctx.number or piece.state not in ("building", "shaping", "ready"):
                return refused([f"piece {other} is {piece.state}, so it was not rejected"],
                               f"gate.py move {other} building --reason \"<why>\" first (move 13)")
            return passed(entries=[{"kind": "recheck", "because": "rejected", "piece": other,
                                    "pull_request": opening.number, "head": opening.head}])
        merge_gate.fetch_main(ctx.paths)
        behind = merge_gate.moved(ctx.paths.root, opening.head)
    except merge_gate.Unreadable as error:
        return refused([str(error)], error.next_command)
    except (ValueError, moves.MoveError) as error:
        return refused([str(error)], f"gate.py report {ctx.number}")
    if not behind:
        return refused(
            [f"main did not move, and no piece was rejected, so the tested commit "
             f"{opening.head[:7]} is still the tree that would merge"],
            f"the person merges pull request {opening.number}, or gate.py move {ctx.number} "
            "done after their yes")
    return passed(entries=[{"kind": "recheck", "because": "main-moved",
                            "pull_request": opening.number, "head": opening.head,
                            "commits": len(behind)}])
