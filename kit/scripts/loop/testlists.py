"""The two fresh test lists of the ready gate.

Two sessions that carry none of the shaping conversation each list the tests
they would write for a piece. This module plans and runs both, through
`loop.sessions`, so the rules of every session hold here too: the brief goes by
file, the environment holds no GitHub credential, and the spec reaches a session
only inside a marked data block. It then reads each list as the set of spec IDs
that its tests cover. The lists are compared by those IDs, never by test name.

The ready gate calls `run_two` itself, inside the move. An agent never supplies
a list, because an agent's word is not evidence. `kit/scripts/test-lists.py` is
the command line over the same code.

A session hands back with `done`, and its summary holds one line for each test.
A session that leaves no hand-off, or any other outcome, gives no list.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from loop import sessions, spec
from loop.paths import Paths

LABELS = ("a", "b")
BASE = "main"
Start = Callable[..., sessions.Result]


class ListError(Exception):
    """A list that cannot be had. Carries the next command."""

    def __init__(self, message: str, *, next_command: str) -> None:
        super().__init__(message)
        self.next_command = next_command


def run_name(number: int) -> str:
    return f"ready-{number}"


def compare(first: Sequence[str], second: Sequence[str]) -> list[str]:
    """The IDs that one list covers and the other does not."""
    return sorted(set(first) ^ set(second))


def ids_from_summary(summary: str, allowed: Sequence[str]) -> list[str]:
    """The spec IDs a session's summary names, sorted and once each."""
    return sorted({item for item in spec.ID.findall(summary) if item in set(allowed)})


def template_path(paths: Paths) -> Path:
    return paths.kit_dir / "briefs" / "test-list.md"


def worktree_name(number: int, label: str) -> str:
    return f"p{number}-list-{label}"


def open_worktree(paths: Paths, name: str, branch: str) -> Path:
    """Open the session's worktree through `worktree.sh`, the only thing that opens one."""
    script = paths.kit_dir / "scripts" / "worktree.sh"
    done = subprocess.run(
        ["sh", str(script), "open", name, branch, BASE],
        cwd=paths.root,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        said = (done.stderr or done.stdout).strip().splitlines()[:1]
        raise ListError(
            f"the worktree {name} could not be opened ({said[0] if said else 'no reason given'})",
            next_command=f"sh {script} leftovers, then run the same command again",
        )
    return paths.worktrees_dir / name


def run_two(
    paths: Paths,
    *,
    number: int,
    block: str,
    ids: Sequence[str],
    opener: Callable[[str], Path] | None = None,
    start: Start = sessions.start,
    env: Mapping[str, str] | None = None,
    max_budget_usd: float | None = None,
) -> dict[str, Any]:
    """Run the two sessions. Returns `lists` (the IDs each covers) and the session labels."""
    try:
        template = template_path(paths).read_text(encoding="utf-8")
    except OSError as error:
        raise ListError(
            f"the brief {template_path(paths)} cannot be read ({error.strerror})",
            next_command="reinstall the kit, then run the command again",
        ) from error
    brief = sessions.render_brief(
        template,
        trusted={"PIECE": str(number), "HANDOFF_COMMAND": sessions.handoff_command(paths.kit_dir)},
        outside={"spec": block},
    )
    lists: list[list[str]] = []
    labels: list[str] = []
    for letter in LABELS:
        name = worktree_name(number, letter)
        folder = (
            opener(name)
            if opener is not None
            else open_worktree(paths, name, f"list-{number}-{letter}")
        )
        label = f"p{number}-list-{letter}"
        session = sessions.plan(
            paths,
            run=run_name(number),
            label=label,
            worktree=folder,
            brief=brief,
            max_budget_usd=max_budget_usd,
            env=env,
        )
        result = start(session)
        handoff = result.handoff
        if handoff is None or handoff.get("outcome") != "done":
            why = result.handoff_error or "the session left no hand-off, or did not hand back done"
            raise ListError(
                f"test-list session {letter} gave no list ({why})",
                next_command="run the ready move again; if it repeats, tell the person",
            )
        found = ids_from_summary(str(handoff.get("summary", "")), ids)
        if not found:
            raise ListError(
                f"the list of session {letter} names no spec ID",
                next_command="run the ready move again; if it repeats, tell the person",
            )
        lists.append(found)
        labels.append(label)
    return {"lists": lists, "labels": labels, "differ": compare(lists[0], lists[1])}
