"""One time limit for every call that waits on the network, so a dropped
connection ends the step with a named error instead of hanging the run."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

NETWORK_TIMEOUT = 120


class StepTimeout(RuntimeError):
    """A network call ran past NETWORK_TIMEOUT seconds."""


def step_timeout(label: str) -> StepTimeout:
    return StepTimeout(f"{label} ran past {NETWORK_TIMEOUT} seconds")


def run_limited(args: list[str], cwd: Path, label: str,
                stdin: Optional[str] = None) -> subprocess.CompletedProcess:
    """Run a command under the limit. `label` names the step in the error."""
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True, input=stdin,
                              check=False, timeout=NETWORK_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise step_timeout(label) from None
