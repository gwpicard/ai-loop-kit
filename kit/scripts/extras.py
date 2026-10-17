"""Explicit boundary for the optional mutation tools and gauntlet critics."""
from __future__ import annotations

import importlib.util
import os
import re
import runpy
from functools import cache
from pathlib import Path

from errors import Refused

MUTATION_FILES = ("mutmut-check.py", "mutmut-changed.py", "mutmut_support.py")
MUTATION_COMMAND = re.compile(r"mutmut(?:-check|-changed|_support)\.py\b")


def extra_root(capability: str, files: tuple[str, ...]) -> Path:
    configured = os.environ.get("AI_LOOP_KIT_EXTRAS_ROOT")
    root = (Path(configured).expanduser() if configured
            else Path(__file__).resolve().parents[2] / "extras")
    if not all((root / name).is_file() for name in files):
        raise Refused(
            f"the {capability} extra is not installed",
            "run /plugin install ai-loop-kit-extras@ai-loop-kit, then "
            "/ai-loop-kit-extras:setup; export AI_LOOP_KIT_EXTRAS_ROOT to its plugin path "
            "in the shell that starts the gate or run")
    return root


def mutation_root() -> Path:
    return extra_root("mutation", tuple("quality/" + name for name in MUTATION_FILES))


def critics_root() -> Path:
    return extra_root("gauntlet critics", ("scripts/critic.py", "briefs/critic.md"))


@cache
def _load_critics(root: Path):
    spec = importlib.util.spec_from_file_location("loopkit_critics", root / "scripts/critic.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def critics():
    """Load the critic only when a requested check needs it."""
    return _load_critics(critics_root())


def require_extras(*configs: dict) -> None:
    """Refuse requested optional commands, including those in frozen records."""
    for config in configs:
        if config.get("kind") == "gauntlet" or config.get("type") in {"critics", "critic"}:
            critics_root()
        commands = [config.get(key, "") for key in
                    ("command", "capture", "measure", "keep", "test", "prepare")]
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
