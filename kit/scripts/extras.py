"""Explicit boundary for the optional mutation tools."""
from __future__ import annotations

import os
import re
import runpy
from pathlib import Path

from errors import Refused

MUTATION_FILES = ("mutmut-check.py", "mutmut-changed.py", "mutmut_support.py")
MUTATION_COMMAND = re.compile(r"mutmut(?:-check|-changed|_support)\.py\b")


def mutation_root() -> Path:
    configured = os.environ.get("AI_LOOP_KIT_EXTRAS_ROOT")
    root = (Path(configured).expanduser() if configured
            else Path(__file__).resolve().parents[2] / "extras")
    if not all((root / "quality" / name).is_file() for name in MUTATION_FILES):
        raise Refused(
            "the mutation extra is not installed",
            "run /plugin install ai-loop-kit-extras@ai-loop-kit, then "
            "/ai-loop-kit-extras:setup; export AI_LOOP_KIT_EXTRAS_ROOT to its plugin path "
            "in the shell that starts the gate or run")
    return root


def require_extras(*configs: dict) -> None:
    """Refuse requested optional commands, including those in frozen records."""
    for config in configs:
        commands = [config.get(key, "") for key in
                    ("command", "capture", "keep", "test", "prepare")]
        commands.extend(config.get("quality", []))
        if any(MUTATION_COMMAND.search(command) for command in commands):
            mutation_root()
        require_extras(*config.get("checks", []))


def run_mutation(name: str) -> None:
    """Keep existing Quality command paths working with the extra installed."""
    try:
        path = mutation_root() / "quality" / name
    except Refused as error:
        raise SystemExit(f"refused: {error.reason}\nnext: {error.next_step}") from error
    runpy.run_path(str(path), run_name="__main__")
