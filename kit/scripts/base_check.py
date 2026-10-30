"""The base check: a piece made ready while a blocker was unfinished is checked on the base.

The run does this when every blocker is done, before it builds the piece. A refusal hands the
piece back to shaping with `needs-you`; the run carries on with the other pieces.
"""
from __future__ import annotations

from pathlib import Path

import gate
from errors import JudgeRefused, Refused
from loopkit import GitHub, last_record, record_text, refresh_main

ENVIRONMENT = ("prepare command", "regression check", "keep check")


def confirm(gh: GitHub, root: Path, n: int) -> None:
    """Run the full ready check on the current base for a piece whose check is pending.

    A piece already checked is left as it is. Raises Refused when the check refuses, or when
    the spec or the judge files changed since the contract was approved."""
    pending = last_record(gh.comments(n), "ready") or {}
    if pending.get("base_check") != "pending":
        return
    refresh_main(root)
    record = gate.check_ready(gh, root, gh.issue(n))
    for key, what in (("spec", "the spec"), ("exit_bar", "the judge files")):
        if record.get(key) != pending.get(key):
            raise Refused(f"{what} changed after approval", "make the piece ready again")
    note = (f"Base check done: pieces {', '.join(map(str, pending.get('blockers', [])))} are done "
            "and the ready check passes on the current base.")
    gh.comment(n, record_text({**record, "from": "ready", "to": "ready"}, note))
    gate.run_event(root, "base-check", n, "ready")


def hand_back(gh: GitHub, root: Path, n: int, error: Refused) -> str:
    """Move the piece to shaping with `needs-you` and the reason; return the run's line."""
    if isinstance(error, JudgeRefused):
        kind = error.reason_type
    elif any(word in error.reason.lower() for word in ENVIRONMENT):
        kind = "environment"
    else:
        kind = "spec-unclear"
    gate.move(gh, root, n, "shaping", reason=error.reason, reason_type=kind, needs_you=True)
    return f"piece {n}: back to shaping, base check refused: {error.reason}"
