"""Move 3: ready to shaping. The person pulled it back, the fingerprint
changed, or the claim's research check found a finding it cannot confirm.

The gate's shared rules hold this move: the written reason, and for a move back
to shaping the anti-circle rule. The run, the review or the person supplies the
reason. A later piece that can check more replaces this module.
"""

from loop.gates import reason_only as check

__all__ = ["check"]
