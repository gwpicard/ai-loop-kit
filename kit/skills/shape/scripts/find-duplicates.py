#!/usr/bin/env python3
# contract: agent
# contract: changes-state
"""find-duplicates.py: look for a piece with the same words, and pass new words to it.

Commands:
  find-duplicates.py search --text <the idea in the person's words>
  find-duplicates.py comment <number> --text <the new words>

`search` compares the idea with every open and closed issue, and with the gate's
own record of pieces. It warns about a dropped piece and shows the reason it was
dropped, so a rejected idea is not rebuilt by accident. It changes nothing.

GitHub is read only through loop/github.py, as the gate's App. With no App it
reads nothing on GitHub and says so with a `next:` line. It never uses the
person's own sign-in. The gate's record is still searched, since it is a local
folder.

`comment` asks the gate to post the new words on the duplicate as a kit comment
(`gate.py comment`). The gate signs it as the App. With no App the gate queues it,
and its `next:` line names `gate.py sync`, which only the person runs.

A match is a piece that shares at least two words with the idea, and at least
the share set by `--threshold` of the shorter text. The words are compared in
lower case, with the plainest words and a trailing "s" dropped.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from loop import github, moves, states  # noqa: E402
from loop.cli import ExitCode, Failure, run  # noqa: E402
from loop.paths import PathError, Paths, find_project_root  # noqa: E402

PROG = "find-duplicates.py"
GATE = SCRIPTS / "gate.py"
PAGE = 100
MAX_PAGES = 5
MIN_SHARED = 2
BODY_CHARS = 500
STOP_WORDS = frozenset(
    re.findall(
        r"\w+",
        "a an and are as at be but by can for from has have how i if in into is it its let "
        "make me my no not of on or our so that the their them then there they this to us was "
        "we what when which who will with would you your should could just want need new add "
        "get use people user users please",
    )
)
WORD = re.compile(r"[a-z0-9]+")


def words(text: str) -> set[str]:
    """The words that carry meaning in `text`: lower case, no filler, no trailing s."""
    found: set[str] = set()
    for raw in WORD.findall(text.lower()):
        word = raw[:-1] if len(raw) > 3 and raw.endswith("s") and not raw.endswith("ss") else raw
        if len(word) > 1 and word not in STOP_WORDS:
            found.add(word)
    return found


def score(idea: set[str], other: set[str]) -> tuple[float, list[str]]:
    """The share of the shorter text that the two have in common, and the shared words."""
    shared = sorted(idea & other)
    if len(shared) < MIN_SHARED or not idea or not other:
        return 0.0, shared
    return len(shared) / min(len(idea), len(other)), shared


def _label_names(issue: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in issue.get("labels") or []:
        names.append(str(item["name"] if isinstance(item, dict) else item))
    return names


def _drop_reason(hub: github.GitHub, number: int) -> str | None:
    """The reason the gate wrote when it dropped the issue, from its last comment."""
    found = hub.api_json(f"repos/{{owner}}/{{repo}}/issues/{number}/comments")
    if not isinstance(found, list):
        return None
    for comment in reversed(found):
        body = str(comment.get("body", "")) if isinstance(comment, dict) else ""
        match = re.search(r"Reason:\s*(.+)", body)
        if match and "dropped" in body.lower():
            return match.group(1).strip()
    return None


def _github_issues(hub: github.GitHub) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        batch = hub.api_json(
            f"repos/{{owner}}/{{repo}}/issues?state=all&per_page={PAGE}&page={page}"
        )
        if not isinstance(batch, list):
            break
        issues += [i for i in batch if isinstance(i, dict) and not i.get("pull_request")]
        if len(batch) < PAGE:
            break
    return issues


def _match(
    idea: set[str], title: str, body: str, threshold: float
) -> tuple[float, list[str]] | None:
    value, shared = score(idea, words(f"{title} {body[:BODY_CHARS]}"))
    return (value, shared) if value >= threshold else None


def _search_github(
    hub: github.GitHub, idea: set[str], threshold: float
) -> tuple[list[dict[str, Any]], set[int]]:
    matches: list[dict[str, Any]] = []
    seen: set[int] = set()
    for issue in _github_issues(hub):
        number = int(issue["number"])
        seen.add(number)
        found = _match(idea, str(issue.get("title", "")), str(issue.get("body") or ""), threshold)
        if found is None:
            continue
        labels = _label_names(issue)
        dropped = states.label("dropped") in labels
        closed = str(issue.get("state", "")).lower() == "closed"
        matches.append(
            {
                "number": number,
                "source": "github",
                "title": str(issue.get("title", "")),
                "state": "closed" if closed else "open",
                "labels": labels,
                "dropped": dropped,
                "reason": _drop_reason(hub, number) if dropped else None,
                "score": round(found[0], 2),
                "shared": found[1],
            }
        )
    return matches, seen


def _search_record(
    paths: Paths, idea: set[str], threshold: float, skip: set[int]
) -> list[dict[str, Any]]:
    folder = paths.pieces_dir
    if not folder.is_dir():
        return []
    matches: list[dict[str, Any]] = []
    for item in sorted(folder.iterdir()):
        if not (item.is_dir() and item.name.isdigit()):
            continue
        piece = moves.read_piece(paths, int(item.name))
        if piece is None or (piece.issue is not None and piece.issue in skip):
            continue
        found = _match(idea, piece.title, piece.body, threshold)
        if found is None:
            continue
        reasons = piece.reasons
        matches.append(
            {
                "number": piece.number,
                "source": "record",
                "title": piece.title,
                "state": "closed" if piece.state in states.CLOSED else "open",
                "labels": piece.labels(),
                "dropped": piece.state == "dropped",
                "reason": reasons[-1] if piece.state == "dropped" and reasons else None,
                "score": round(found[0], 2),
                "shared": found[1],
            }
        )
    return matches


def _paths() -> Paths:
    try:
        return Paths.for_project(find_project_root(Path.cwd()))
    except PathError as error:
        raise Failure(
            str(error),
            next_command="cd <the project>, then run the same command again",
            code=ExitCode.ENVIRONMENT,
        ) from error


def search(args: argparse.Namespace) -> dict[str, Any]:
    idea = words(args.text)
    if len(idea) < MIN_SHARED:
        raise Failure(
            "the idea has too few words to compare",
            next_command=f'{PROG} search --text "<the idea in the person\'s own words>"',
            code=ExitCode.USAGE,
        )
    paths = _paths()
    hub = github.GitHub(paths)
    matches: list[dict[str, Any]] = []
    seen: set[int] = set()
    out: dict[str, Any] = {"query": args.text, "github_read": False, "next": None}
    if hub.available:
        try:
            matches, seen = _search_github(hub, idea, args.threshold)
            out["github_read"] = True
        except github.GitHubError as error:
            raise Failure(
                error.message, next_command=error.next_command, code=error.code
            ) from error
    else:
        out["next"] = github.SETUP_NEXT
        sys.stderr.write(
            "note: the gate's GitHub App is not set up, so GitHub was not read. "
            "Only the gate's own record was searched.\n"
            f"next: {github.SETUP_NEXT}\n"
        )
    matches += _search_record(paths, idea, args.threshold, seen)
    matches.sort(key=lambda m: (-float(m["score"]), int(m["number"])))
    warnings = [
        f"piece {m['number']} was dropped"
        + (f" ({m['reason']})" if m["reason"] else "")
        + ": ask the person before the idea is built again"
        for m in matches
        if m["dropped"]
    ]
    out["matches"] = matches
    out["warnings"] = warnings
    return out


def _code(value: int) -> ExitCode:
    return ExitCode(value) if value in {int(c) for c in ExitCode} else ExitCode.FAILURE


def comment(args: argparse.Namespace) -> dict[str, Any]:
    text = f"New words on this idea, from a later sitting:\n\n{args.text.strip()}"
    command = [sys.executable, str(GATE), "comment", str(args.number), "--text", text, "--json"]
    if getattr(args, "dry_run", False):
        command.append("--dry-run")
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    try:
        body = json.loads(done.stdout or "{}")
    except ValueError:
        body = {}
    if done.returncode != 0:
        raise Failure(
            str(body.get("error") or done.stderr.strip() or "the gate refused the comment"),
            next_command=str(body.get("next") or f"python3 {GATE} comment --help"),
            code=_code(done.returncode),
        )
    return {"piece": args.number, "via": "gate.py comment", **body}


def setup(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    find = commands.add_parser(
        "search", help="find open, closed and dropped pieces with the same words"
    )
    find.add_argument("--text", required=True, help="the idea, in the person's own words")
    find.add_argument(
        "--threshold",
        type=float,
        default=0.6,
        help="the share of the shorter text that must match (default 0.6)",
    )
    find.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print JSON on standard output (the default when it is not a terminal)",
    )
    post = commands.add_parser(
        "comment", help="post the new words on a duplicate, through the gate"
    )
    post.add_argument("number", type=int, help="the duplicate's number")
    post.add_argument("--text", required=True, help="the new words")
    post.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print JSON on standard output (the default when it is not a terminal)",
    )
    post.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="say what would change, and change nothing",
    )


def handle(args: argparse.Namespace) -> dict[str, Any]:
    return search(args) if args.command == "search" else comment(args)


def main(argv: list[str]) -> int:
    return run(
        PROG,
        "Find a piece with the same words, and pass new words to it.",
        setup,
        handle,
        argv,
        changes_state=True,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
