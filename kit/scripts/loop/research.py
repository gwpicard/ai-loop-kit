"""The quick check of every research finding, and the files a piece relies on.

A finding rests on an in-project file with its fingerprint, or on an outside
page or package version (`loop.spec.parse_finding` reads the shape, and
`kit/spec-format.md` writes it down). At every claim the gate checks each one:

- An in-project finding: the file at `main` must still carry the fingerprint.
  The fingerprint is the SHA-256 of the file's bytes at `main`. A finding may
  write the first 7 or more hex digits of it. `stamp` prints it.
- An outside finding: it must be inside the age limit (`research_age_days` in
  the policy file). A package must also still have the version the finding
  names, as the project's own manifest says. A page has a date and no
  version the kit can read offline, so its age is its check.
- A finding that names no source, date or basis is a fault, and so is a date
  in the future.

Anything the quick check cannot confirm is a fault. The caller sends such a
piece back to shaping, because the fuller refresh arrives with L9.

The same fingerprint serves the "relied-on" files: the ready gate records the
files that the spec's `Relies on:` line names, and the claim reads them again.

Run `python3 -m loop.research stamp --path <file>` to print a file's fingerprint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from loop import cli
from loop.paths import PathError, find_project_root

PAGE = re.compile(r"^https?://", re.IGNORECASE)
CONSTRAINT = re.compile(r"^[\^~<>=!v\s]+")
WORD_EDGES = "()[]{}`'\"<>,;:"


def _git_bytes(root: Path, *args: str) -> tuple[int, bytes]:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    return done.returncode, done.stdout


def file_fingerprint(root: Path, ref: str, path: str) -> str | None:
    """The SHA-256 of `path` at `ref`, or None when the file is not there."""
    code, data = _git_bytes(root, "show", f"{ref}:{path}")
    if code != 0:
        return None
    return hashlib.sha256(data).hexdigest()


def tracked(root: Path, ref: str) -> set[str]:
    """The files of the project at `ref`. Raises `OSError` when git cannot list them."""
    code, data = _git_bytes(root, "ls-tree", "-r", "--name-only", ref)
    if code != 0:
        raise OSError(f"git could not list the files of {ref}")
    return set(data.decode("utf-8", "replace").splitlines())


def relied_on_files(relies_on: Sequence[str], files: set[str]) -> list[str]:
    """The files in the spec's `Relies on:` items. A word counts when it names a file of the
    project. A service or a route by name is not a file, so nothing can fingerprint it."""
    found: list[str] = []
    for item in relies_on:
        for word in item.split():
            candidate = word.strip(WORD_EDGES).rstrip(".")
            if candidate in files and candidate not in found:
                found.append(candidate)
    return found


def relied_on(relies_on: Sequence[str], root: Path, ref: str) -> dict[str, str]:
    """Each relied-on file of the project at `ref` with its fingerprint."""
    out: dict[str, str] = {}
    for path in relied_on_files(relies_on, tracked(root, ref)):
        found = file_fingerprint(root, ref, path)
        if found is not None:
            out[path] = found
    return out


def manifest_version(root: Path, ref: str, name: str) -> str | None:
    """The version of package `name` that the project's manifest names at `ref`, or None.

    Reads `package.json` (dependencies of every kind) and `requirements.txt` (`name==x`).
    """
    code, data = _git_bytes(root, "show", f"{ref}:package.json")
    if code == 0:
        try:
            loaded = json.loads(data.decode("utf-8"))
        except ValueError:
            loaded = {}
        if isinstance(loaded, dict):
            for group in ("dependencies", "devDependencies", "peerDependencies",
                          "optionalDependencies"):
                wanted = loaded.get(group)
                if isinstance(wanted, dict) and isinstance(wanted.get(name), str):
                    return CONSTRAINT.sub("", wanted[name]).strip() or None
    code, data = _git_bytes(root, "show", f"{ref}:requirements.txt")
    if code == 0:
        for line in data.decode("utf-8", "replace").splitlines():
            found = re.match(rf"^\s*{re.escape(name)}\s*==\s*([^\s;#]+)", line, re.IGNORECASE)
            if found:
                return found.group(1)
    return None


def _age(checked: str, today: str) -> int:
    return (date.fromisoformat(today) - date.fromisoformat(checked)).days


def check(
    findings: Sequence[Mapping[str, Any]],
    *,
    today: str,
    age_days: int,
    file_fingerprint: Callable[[str], str | None],
    version_of: Callable[[str], str | None],
) -> list[str]:
    """What the quick check cannot confirm, one text for each finding that fails."""
    problems: list[str] = []
    for found in findings:
        who = str(found.get("source") or found.get("text") or "")[:60]
        lacking = [name for name, key in (("a source", "source"), ("a date", "date"),
                                          ("what it rests on", "kind")) if not found.get(key)]
        if lacking:
            problems.append(f"the finding {who!r} has no {', no '.join(lacking)}")
            continue
        source, kind = str(found["source"]), found["kind"]
        if kind == "file":
            now = file_fingerprint(source)
            recorded = str(found["fingerprint"])
            if now is None:
                problems.append(f"the finding on {source} rests on a file that is no longer "
                                f"on main")
            elif not now.startswith(recorded):
                problems.append(f"the finding on {source} rests on fingerprint {recorded}, "
                                f"and the file is now {now[:12]}")
            continue
        age = _age(str(found["date"]), today)
        if age < 0:
            problems.append(f"the finding on {source} is dated in the future ({found['date']})")
        elif age > age_days:
            problems.append(f"the finding on {source} is {age} days old, past the limit of "
                            f"{age_days} days (written {found['date']})")
        elif not PAGE.match(source):
            now = version_of(source)
            if now is None:
                problems.append(f"the quick check cannot confirm the version of {source}: the "
                                "project's manifest does not name it")
            elif now != found["version"]:
                problems.append(f"the finding on {source} rests on version {found['version']}, "
                                f"and the project now has {now}")
    return problems


# --- command line ---------------------------------------------------------------------------


def _setup(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    sub = commands.add_parser("stamp", help="print the fingerprint of a file at a ref")
    sub.add_argument("--path", required=True, help="the file, as the project names it")
    sub.add_argument("--ref", default="main", help="the ref to read it at (default: main)")
    sub.add_argument("--root", help="the project folder (default: the one around here)")
    sub.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="print JSON")


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    try:
        root = Path(args.root) if args.root else find_project_root(Path.cwd())
    except PathError as error:
        raise cli.Failure(
            str(error), next_command="research stamp --help", code=cli.ExitCode.USAGE
        ) from error
    found = file_fingerprint(root, args.ref, args.path)
    if found is None:
        raise cli.Failure(
            f"{args.path} is not a file at {args.ref}",
            next_command=f"check the path with: git ls-tree -r --name-only {args.ref}",
            code=cli.ExitCode.REFUSED,
        )
    return {"path": args.path, "ref": args.ref, "fingerprint": found,
            "write": f"Rests on: fingerprint {found[:12]}"}


def main(argv: list[str]) -> int:
    return cli.run(
        "research",
        "Print the fingerprint a research finding writes for an in-project file.",
        _setup,
        _handle,
        argv,
    )


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
