"""Move 9: review to shaping. A review finding shows the spec was wrong.

The gate's shared rules hold this move: the written reason, and for a move back
to shaping the anti-circle rule. The run, the review or the person supplies the
reason. A later piece that can check more replaces this module.
"""

from loop.gates import reason_only as check

__all__ = ["check"]
