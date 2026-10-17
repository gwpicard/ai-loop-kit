"""Refusals shared by parsing and execution, without runtime imports."""


class Refused(Exception):
    """A gate refusal: what is wrong, and the next step that fixes it."""

    def __init__(self, reason: str, next_step: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.next_step = next_step
