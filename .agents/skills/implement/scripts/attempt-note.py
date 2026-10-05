#!/usr/bin/env python3
"""attempt-note.py: write the note one attempt of the build loop leaves for the next.

    python3 attempt-note.py <number> <worktree> [--run <name>] [--attempt <n>]
                            [--status <status>]

Each attempt is a fresh builder, and the only thing it carries from the attempt
before is that attempt's note. So the note is built from the gate's evidence
record and from Git alone, never from a model's account: each check that failed
in the attempt, with its exit code and the last 40 lines of its output, read
from the file the record line names; the files the attempt touched; the commit
it ended on; and its status.

The attempt is the latest start request the run record holds for the piece, in
.agents/runs/<run name>/run.json in the main folder, unless --attempt names
another. Its start time picks the evidence lines that belong to it, and its
base commit gives the files it touched. The status is the one in the builder's
result file, or --status, or "no result" where the builder left none.

The note goes to .agents/pieces/<number>/attempt-<n>.md in the main folder,
with a short record beside it, attempt-<n>.json, that the gate reads when it
lists the attempts in a Kickback section. Running it again for the same
attempt writes the same note again.
"""

from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import subprocess
import sys
from typing import Any

LAST_LINES = 40
FOOTER = ("attempt-note.py wrote this note from the gate's evidence record and from Git. No "
          "model wrote or summarised it.")


def git(folder: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", folder, "-c", "core.quotePath=false", *args],
                          capture_output=True, text=True, check=False)


def stop(message: str) -> None:
    print(f"attempt-note.py: {message}", file=sys.stderr)
    sys.exit(2)


def main_folder(folder: str) -> str:
    done = git(folder, "worktree", "list", "--porcelain")
    for line in done.stdout.splitlines():
        if line.startswith("worktree "):
            return line[len("worktree "):]
    stop(f"{folder} is not inside a Git project")
    return ""


def load(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def find_request(root: str, number: int, run: str | None,
                 attempt: int | None) -> dict[str, Any]:
    """The start request for the attempt, from the run record that holds the piece."""
    if run:
        paths = [os.path.join(root, ".agents", "runs", run, "run.json")]
    else:
        paths = sorted(glob.glob(os.path.join(root, ".agents", "runs", "*", "run.json")),
                       key=os.path.getmtime, reverse=True)
    for path in paths:
        try:
            record = load(path)
        except (OSError, ValueError):
            continue
        for piece in record.get("pieces", []) if isinstance(record, dict) else []:
            if not isinstance(piece, dict) or piece.get("number") != number:
                continue
            requests = [r for r in piece.get("requests") or [] if isinstance(r, dict)]
            if attempt is not None:
                requests = [r for r in requests if r.get("attempt") == attempt]
            if requests:
                chosen: dict[str, Any] = requests[-1]
                return chosen
    stop(f"no run record under .agents/runs/ holds a start request for #{number}")
    return {}


def moment(text: str) -> datetime.datetime | None:
    try:
        when = datetime.datetime.fromisoformat(str(text))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.astimezone()
    return when


def failing_checks(root: str, number: int,
                   since: datetime.datetime) -> tuple[bool, list[dict[str, Any]]]:
    """Whether the attempt recorded any check, and the checks whose last run in
    it failed, in the order they first ran. A before run, a breakage, a note
    and a run from before the attempt are not checks of the attempt."""
    path = os.path.join(root, ".agents", "pieces", str(number), "evidence.jsonl")
    latest: dict[str, dict[str, Any]] = {}
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        lines = []
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("phase") != "after" or "command" not in entry:
            continue
        when = moment(entry.get("time", ""))
        if when is None or when < since:
            continue
        latest[str(entry["command"])] = entry
    return bool(latest), [e for e in latest.values() if e.get("exit") != 0 or e.get("late")]


def last_lines(root: str, name: str) -> str:
    try:
        with open(os.path.join(root, name), encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return "(the output file this run names is not on this computer)\n"
    kept = text.splitlines()[-LAST_LINES:]
    return "\n".join(kept) + "\n" if kept else "(it printed nothing)\n"


def touched(folder: str, base: str) -> list[str]:
    files = set(git(folder, "diff", "--name-only", base).stdout.split("\n"))
    files |= set(git(folder, "ls-files", "--others", "--exclude-standard").stdout.split("\n"))
    return sorted(f for f in files if f and not f.startswith(".agents/pieces/"))


def status_of(root: str, request: dict[str, Any], given: str | None) -> str:
    if given:
        return given
    try:
        data = load(os.path.join(root, str(request.get("result") or "-")))
    except (OSError, ValueError):
        return "no result"
    status = data.get("status") if isinstance(data, dict) else None
    return str(status) if status else "a result with no status"


def write_note(number: int, folder: str, run: str | None, attempt: int | None,
               given: str | None) -> str:
    root = main_folder(folder)
    request = find_request(root, number, run, attempt)
    number_of = int(request.get("attempt") or 0)
    if number_of < 1:
        stop(f"the start request for #{number} names no attempt number")
    since = moment(str(request.get("started_at") or "")) or \
        datetime.datetime.fromtimestamp(0, datetime.timezone.utc)
    base = str(request.get("base") or "")
    status = status_of(root, request, given)
    ended = git(folder, "rev-parse", "HEAD").stdout.strip() or "none"
    recorded, checks = failing_checks(root, number, since)

    text = [f"# Attempt {number_of} of #{number}", "", f"Status: {status}",
            f"Ended on commit: {ended}", "", "## Failing checks", ""]
    failing: list[dict[str, Any]] = []
    if not recorded:
        text += ["No check was recorded in this attempt.", ""]
    elif not checks:
        text += ["None of the checks recorded in this attempt failed.", ""]
    else:
        for entry in checks:
            code = "it ran past its time limit and was stopped" if entry.get("late") \
                else f"Exit code {entry.get('exit')}"
            failing.append({"command": entry["command"], "exit": entry.get("exit")})
            text += [f"### `{entry['command']}`", "",
                     f"{code}. The last {LAST_LINES} lines of its output:", "", "```text",
                     last_lines(root, str(entry.get("output") or "")).rstrip("\n"), "```", ""]
    text += ["## Files the attempt touched", ""]
    files = touched(folder, base) if base else []
    text += [f"- {name}" for name in files] if files else ["No file was changed."]
    text += ["", FOOTER, ""]

    pieces = os.path.join(root, ".agents", "pieces", str(number))
    os.makedirs(pieces, exist_ok=True)
    note = f".agents/pieces/{number}/attempt-{number_of}.md"
    with open(os.path.join(root, note), "w", encoding="utf-8") as handle:
        handle.write("\n".join(text))
    summary = {"attempt": number_of, "status": status, "failing": failing, "note": note,
               "commit": ended}
    with open(os.path.join(pieces, f"attempt-{number_of}.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")
    return note


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("number", type=int)
    parser.add_argument("worktree")
    parser.add_argument("--run")
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--status")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.worktree):
        stop(f"{args.worktree} is not a folder")
    note = write_note(args.number, os.path.abspath(args.worktree), args.run, args.attempt,
                      args.status)
    print(f"attempt-note.py wrote {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
