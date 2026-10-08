"""Check that the first scaffold inherits its selected hosted command from Git.

The workflow is the hosted command's home. The piece's judge supplies the
selected command; a working-file change alone cannot prepare its branch.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from loop.cli import ExitCode, Failure

WORKFLOW = ".github/workflows/checks.yml"
POLICY = ".agents/loop/policy.json"
ENTRY = "          SCAFFOLD_TEST_COMMAND: "
NEXT = (
    "ask the person to commit the foundation or scaffold-command preparation on a new branch, "
    "review and merge its pull request themselves, then fetch and update local main and try again; "
    "do not push to main or discard an existing piece branch"
)


def refusal(message: str) -> Failure:
    return Failure(message, next_command=NEXT, code=ExitCode.REFUSED)


def entry(text: str) -> str | None:
    values = [line[len(ENTRY):] for line in text.splitlines() if line.startswith(ENTRY)]
    if not values:
        return None
    if len(values) != 1:
        raise refusal("checks.yml must hold one generated scaffold command entry")
    try:
        value: object = json.loads(values[0])
    except ValueError as error:
        raise refusal("checks.yml's generated scaffold command cannot be read") from error
    if not isinstance(value, str):
        raise refusal("checks.yml's generated scaffold command must be text")
    return value


def committed(root: Path, ref: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{ref}:{path}"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout if result.returncode == 0 else None


def check(root: Path, selected: str, *, ref: str = "main", use_working_marker: bool = True) -> None:
    """Refuse a generated bootstrap whose committed command differs from the judge.

    A real committed policy command supersedes bootstrap. A custom workflow
    without the generated entry remains the person's responsibility.
    """
    workflow = committed(root, ref, WORKFLOW)
    actual = entry(workflow) if workflow is not None else None
    local = root / WORKFLOW
    working = (
        entry(local.read_text("utf-8")) if use_working_marker and local.is_file() else None
    )
    main_workflow = committed(root, "main", WORKFLOW) if not use_working_marker else None
    main_marker = entry(main_workflow) if main_workflow is not None else None
    if actual is None and working is None and main_marker is None:
        return
    raw_policy = committed(root, ref, POLICY)
    if raw_policy is not None:
        try:
            data = json.loads(raw_policy)
            command = data.get("test_command", "") if isinstance(data, dict) else None
        except ValueError as error:
            raise refusal(f"the policy on {ref} cannot be read") from error
        if not isinstance(command, str):
            raise refusal(f"the policy test_command on {ref} must be text")
        if command.strip():
            return
    if actual is None or actual != selected:
        raise refusal(
            f"the selected scaffold command is not prepared in committed {ref}; "
            "a working workflow edit cannot reach the scaffold branch"
        )
