"""Refusals shared by parsing and execution, without runtime imports."""


class Refused(Exception):
    """A gate refusal: what is wrong, and the next step that fixes it."""

    def __init__(self, reason: str, next_step: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.next_step = next_step


class JudgeRefused(Refused):
    """A refusal about the judge itself. `reason_type` says who must act: `bar-wrong` when the
    judge needs repair, `spec-unclear` when the judge already passes and the spec is at fault."""

    def __init__(self, reason: str, next_step: str = "", reason_type: str = "bar-wrong") -> None:
        super().__init__(reason, next_step)
        self.reason_type = reason_type
