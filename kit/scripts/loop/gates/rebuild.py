"""Move 8: review to building. A trial join turned red, so the trial was thrown away and the
combined branch never moved. Or a merge conflict. Or a review finding became a failing check.

The gate's shared rules hold this move: the written reason, and the repeat counter, which
sends the piece back to shaping after three of the same move. The integration loop
(`loop/run/integrate.py`) supplies the reason: the failure, and the piece it clashed with.
A later piece that can check more replaces this module.
"""

from loop.gates import reason_only as check

__all__ = ["check"]
