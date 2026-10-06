"""The policy file: the rules the person writes before a run.

The file is `.agents/loop/policy.json` (`Paths.policy_file`). Agents read it and
cannot change it: the deny rules and the guard hook protect it. It is JSON, not
TOML, because Python 3.10 has no `tomllib`.

The policy has no pre-approval key. Pre-approving a merge is asked once for each
run (`--merge-pre-approved`), so it can never become a standing setting.

`validate` returns every problem, each named by its key (nested keys use a
dot, such as `billing.mode`). `load` reads a file, refuses it with every
problem, and returns the values with the defaults filled in.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "builder_cap": 3,
    "attempt_limit": 3,
    "review_rounds": 2,
    "question_cap": 5,
    "research_age_days": 30,
    "length_limits": {"chore": 80, "bug": 120, "feature": 250},
    "pull_request_size_limit": 800,
    "billing": {
        "mode": "subscription",
        "spend_cap_per_piece_usd": None,
        "spend_cap_per_run_usd": None,
    },
    "test_command": "",
    "test_timeout_seconds": 1800,
    "min_free_memory_mb": 2048,
    "min_free_disk_gb": 5,
}

# Whole numbers, with the range each may take.
_INTEGERS: dict[str, tuple[int, int]] = {
    "builder_cap": (1, 8),
    "attempt_limit": (1, 10),
    "review_rounds": (1, 5),
    "question_cap": (1, 20),
    "research_age_days": (1, 365),
    "pull_request_size_limit": (1, 100000),
    "test_timeout_seconds": (60, 14400),
    "min_free_memory_mb": (256, 1048576),
    "min_free_disk_gb": (1, 100000),
}
BILLING_MODES = ("subscription", "api_key")
SPEND_CAPS = ("spend_cap_per_piece_usd", "spend_cap_per_run_usd")
_APPROVAL_WORDS = ("approv", "merge")
NEEDS_CAP = "is needed: an API key must have a spend cap"


@dataclass(frozen=True)
class Problem:
    """One thing wrong with the policy. `key` is "" when the whole file is wrong."""

    key: str
    message: str


class PolicyError(ValueError):
    """The policy cannot be used. The message names each key at fault."""

    def __init__(self, problems: list[Problem]) -> None:
        self.problems = problems
        super().__init__(
            "; ".join(f"{p.key}: {p.message}" if p.key else p.message for p in problems)
        )


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _unknown(key: str, where: str, known: dict[str, Any]) -> Problem:
    name = f"{where}.{key}" if where else key
    if not where and any(word in key.lower() for word in _APPROVAL_WORDS):
        return Problem(
            name,
            "the policy has no pre-approval key. Pre-approval is asked once for each run: "
            "start the run with --merge-pre-approved",
        )
    return Problem(name, f"is not a policy key. The keys are: {', '.join(sorted(known))}")


def validate(data: Any) -> list[Problem]:
    """Every problem with the policy `data`. An empty list means it is valid."""
    if not isinstance(data, dict):
        return [Problem("", "the policy must be a JSON object")]
    problems: list[Problem] = []
    for key in data:
        if key not in DEFAULTS:
            problems.append(_unknown(key, "", DEFAULTS))
    for key, (low, high) in _INTEGERS.items():
        if key not in data:
            continue
        value = data[key]
        if not _is_integer(value):
            problems.append(Problem(key, f"must be a whole number, not {json.dumps(value)}"))
        elif not low <= value <= high:
            problems.append(Problem(key, f"must be between {low} and {high}, not {value}"))
    if "test_command" in data and not isinstance(data["test_command"], str):
        problems.append(Problem("test_command", "must be text, the command that tests the project"))
    problems += _validate_limits(data.get("length_limits", {}))
    problems += _validate_billing(data.get("billing", {}))
    return problems


def _validate_limits(limits: Any) -> list[Problem]:
    if not isinstance(limits, dict):
        return [Problem("length_limits", "must be an object with chore, bug and feature")]
    known = DEFAULTS["length_limits"]
    problems: list[Problem] = []
    for key, value in limits.items():
        name = f"length_limits.{key}"
        if key not in known:
            problems.append(_unknown(key, "length_limits", known))
        elif not _is_integer(value) or value < 1:
            problems.append(
                Problem(
                    name, f"must be a whole number of lines, 1 or more, not {json.dumps(value)}"
                )
            )
    return problems


def _validate_billing(billing: Any) -> list[Problem]:
    if not isinstance(billing, dict):
        return [Problem("billing", "must be an object with mode and the spend caps")]
    known = DEFAULTS["billing"]
    problems: list[Problem] = []
    for key in billing:
        if key not in known:
            problems.append(_unknown(key, "billing", known))
    mode = billing.get("mode", known["mode"])
    if mode not in BILLING_MODES:
        problems.append(
            Problem(
                "billing.mode", f"must be one of {', '.join(BILLING_MODES)}, not {json.dumps(mode)}"
            )
        )
    for key in SPEND_CAPS:
        value = billing.get(key)
        if value is not None and (not _is_number(value) or value <= 0):
            problems.append(
                Problem(
                    f"billing.{key}", f"must be a number above 0, or null, not {json.dumps(value)}"
                )
            )
    if mode == "api_key":
        for key in SPEND_CAPS:
            if billing.get(key) is None:
                problems.append(Problem(f"billing.{key}", NEEDS_CAP))
    return problems


def with_defaults(data: dict[str, Any]) -> dict[str, Any]:
    """`data` with every missing key filled from the defaults. Assumes `data` is valid."""
    merged: dict[str, Any] = {}
    for key, default in DEFAULTS.items():
        if isinstance(default, dict):
            given = data.get(key)
            merged[key] = {**default, **(given if isinstance(given, dict) else {})}
        else:
            merged[key] = data.get(key, default)
    return merged


def read(path: Path) -> Any:
    """The JSON in `path`. Raises `PolicyError` when it is missing or not JSON."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise PolicyError(
            [Problem("", f"cannot read the policy file {path} ({error.strerror})")]
        ) from error
    try:
        return json.loads(text)
    except ValueError as error:
        raise PolicyError([Problem("", f"{path} is not valid JSON ({error})")]) from error


def load(path: Path) -> dict[str, Any]:
    """Read, check and complete the policy at `path`. Raises `PolicyError`."""
    data = read(path)
    problems = validate(data)
    if problems:
        raise PolicyError(problems)
    return with_defaults(data)
