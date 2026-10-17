"""Check the mutmut setup used by the changed-function quality command."""
from __future__ import annotations

import configparser
import re
from pathlib import Path


def source_paths(cwd: Path) -> list[str]:
    """Read mutmut source paths from its supported project config files."""
    pyproject = cwd / "pyproject.toml"
    if pyproject.is_file():
        try:
            import tomllib
        except ImportError:  # Python 3.9 and 3.10
            text = pyproject.read_text(errors="replace")
            section = re.search(r"(?ms)^\[tool\.mutmut\]\s*$(.*?)(?=^\[|\Z)", text)
            match = re.search(r"(?m)^\s*source_paths\s*=\s*(\[[^\]]*\])", section[1]) if section else None
            if match:
                import ast
                values = ast.literal_eval(match[1])
            else:
                values = []
        else:
            try:
                values = tomllib.loads(pyproject.read_text()).get("tool", {}).get(
                    "mutmut", {}).get("source_paths", [])
            except (OSError, ValueError):
                values = []
        configured = [value for value in values if isinstance(value, str) and value.strip()]
        if configured:
            return configured

    setup_cfg = cwd / "setup.cfg"
    config = configparser.ConfigParser()
    try:
        config.read(setup_cfg)
        value = config.get("mutmut", "source_paths", fallback="")
    except (OSError, configparser.Error):
        value = ""
    return [item.strip() for item in re.split(r"[\s,]+", value) if item.strip()]


def version_at_least(output: str, minimum: tuple[int, int] = (3, 8)) -> bool:
    """Return whether a mutmut version string meets the minimum version."""
    match = re.search(r"\b(?:version\s+)?(\d+)\.(\d+)(?:\.\d+)?\b", output)
    return bool(match and tuple(map(int, match.groups())) >= minimum)


def validation_error(cwd: Path, version_output: str) -> str:
    """Return the first setup gap that would make mutation results unreliable."""
    if not version_at_least(version_output):
        return "mutmut 3.8 or later is required; install or update mutmut"
    if not source_paths(cwd):
        return "no mutmut source paths configured"
    return ""
