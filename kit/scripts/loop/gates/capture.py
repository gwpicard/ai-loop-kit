"""Move 1: capture by /shape, in the person's words. The design names no other check.

The gate holds a title, so the piece can be found again.
"""

from __future__ import annotations

from loop.gates import CheckContext, CheckResult, passed, refused


def check(ctx: CheckContext) -> CheckResult:
    if not ctx.title.strip():
        return refused(
            ["a piece needs a title, in the person's words"],
            'gate.py capture --title "<the idea in a few words>" --body-file <file>',
        )
    return passed()
