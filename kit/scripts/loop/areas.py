"""The project's area map, read in one place.

The map is the file `docs/area-map` (`Paths.area_map`). It is written in the
style of a CODEOWNERS file: one rule on each line, a pattern and then an area
name, and the last rule that matches a path wins. A line that starts with `#`
is a comment, and blank lines are ignored. The map holds no prose.

A pattern follows the rules of a CODEOWNERS file:

- `*` stands for any characters except `/`, `**` for any characters at all,
  and `?` for one character except `/`;
- a leading `/` fixes the pattern to the project root. So does a `/` in the
  middle. Otherwise the pattern matches at any depth;
- a trailing `/` names a folder and everything below it. A pattern with no
  trailing `/` matches a file, or a folder and everything below it.

An area name is one word of letters, digits, `.`, `_` and `-`.

Every tracked file belongs to an area, and every area matches at least one
tracked file. Three kinds of path belong to no area and are never reported: a
file at the project root, anything under a hidden top-level folder, and
anything under `changes/`.

`kit/scripts/area-map.py` is the command line over this module. The ready gate
reads the area names here.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from loop.paths import Paths

MAP_FILE = "docs/area-map"
TEMPLATE_HINT = "copy kit/templates/area-map to docs/area-map, then add one line for each area"
UNCLAIMED = "unclaimed"
EXEMPT = "exempt"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class AreaMapError(Exception):
    """A map that cannot be read, or a project that cannot be listed. Carries the next command."""

    def __init__(self, message: str, *, next_command: str) -> None:
        super().__init__(message)
        self.next_command = next_command


@dataclass(frozen=True)
class Rule:
    pattern: str
    area: str
    line: int
    regex: re.Pattern[str]


def _translate(pattern: str) -> re.Pattern[str]:
    folder = pattern.endswith("/")
    body = pattern.rstrip("/")
    anchored = body.startswith("/") or "/" in body
    body = body.lstrip("/")
    out: list[str] = []
    index = 0
    while index < len(body):
        if body.startswith("**/", index):
            out.append("(?:.*/)?")
            index += 3
        elif body.startswith("**", index):
            out.append(".*")
            index += 2
        elif body[index] == "*":
            out.append("[^/]*")
            index += 1
        elif body[index] == "?":
            out.append("[^/]")
            index += 1
        else:
            out.append(re.escape(body[index]))
            index += 1
    start = "^" if anchored else "^(?:.*/)?"
    end = "/.*$" if folder else "(?:/.*)?$"
    return re.compile(start + "".join(out) + end)


def parse(text: str) -> list[Rule]:
    """Every rule in the map, in file order. Raises `AreaMapError`."""
    rules: list[Rule] = []
    for number, raw in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        words = line.split()
        where = f"{MAP_FILE} line {number}"
        if len(words) != 2:
            raise AreaMapError(
                f"{where}: write each rule as `<pattern> <area>`, with the area as one word",
                next_command=f"correct line {number} of {MAP_FILE}, then run the command again",
            )
        pattern, area = words
        if not _NAME.match(area):
            raise AreaMapError(
                f"{where}: {area!r} is not an area name; use letters, digits, '.', '_' and '-'",
                next_command=f"correct line {number} of {MAP_FILE}, then run the command again",
            )
        rules.append(Rule(pattern, area, number, _translate(pattern)))
    return rules


def load(paths: Paths) -> list[Rule]:
    """The rules of the project's map. Raises `AreaMapError` when the file is missing."""
    try:
        text = paths.area_map.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise AreaMapError(
            f"{MAP_FILE} is missing", next_command=TEMPLATE_HINT
        ) from error
    except OSError as error:
        raise AreaMapError(
            f"{MAP_FILE} cannot be read ({error.strerror})",
            next_command=f"check the permissions of {MAP_FILE}, then run the command again",
        ) from error
    return parse(text)


def load_or_empty(paths: Paths) -> list[Rule]:
    """Like `load`, and an empty list when the project has no map yet."""
    if not paths.area_map.exists():
        return []
    return load(paths)


def names(rules: list[Rule]) -> list[str]:
    """Each area name once, in the order of its first rule."""
    found: list[str] = []
    for rule in rules:
        if rule.area not in found:
            found.append(rule.area)
    return found


def clean(path: str) -> str:
    path = path.strip()
    while path.startswith("./"):
        path = path[2:]
    return path.strip("/")


def area_of(rules: list[Rule], path: str) -> str | None:
    """The area of the last rule that matches `path`, or None."""
    wanted = clean(path)
    for rule in reversed(rules):
        if rule.regex.match(wanted):
            return rule.area
    return None


def is_exempt(path: str) -> bool:
    """True for a root file, a path under a hidden top-level folder, and `changes/`."""
    wanted = clean(path)
    if "/" not in wanted:
        return True
    top = wanted.split("/", 1)[0]
    return top.startswith(".") or top == "changes"


def which(rules: list[Rule], path: str) -> str:
    """The area of `path`, `exempt`, or `unclaimed`."""
    found = area_of(rules, path)
    if found is not None:
        return found
    return EXEMPT if is_exempt(path) else UNCLAIMED


def tracked_files(root: Path) -> list[str]:
    """The files Git tracks in the project, through `git ls-files`."""
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise AreaMapError(
            f"git cannot be run ({error.strerror})", next_command="install Git, then run it again"
        ) from error
    if done.returncode != 0:
        raise AreaMapError(
            f"{root} is not a Git project",
            next_command="run the command from the project folder, or run git init first",
        )
    return [item for item in done.stdout.decode("utf-8", "replace").split("\0") if item]


def problems(rules: list[Rule], files: list[str]) -> list[str]:
    """What is untrue about the map, one sentence for each fault."""
    found: list[str] = []
    used: set[str] = set()
    first_line: dict[str, int] = {}
    for rule in rules:
        first_line.setdefault(rule.area, rule.line)
    unclaimed: list[str] = []
    for path in files:
        area = area_of(rules, path)
        if area is not None:
            used.add(area)
        elif not is_exempt(path):
            unclaimed.append(path)
    shown = ", ".join(unclaimed[:5])
    if len(unclaimed) > 5:
        shown += f" and {len(unclaimed) - 5} more"
    if unclaimed:
        found.append(
            f"{len(unclaimed)} tracked file(s) belong to no area: {shown}. "
            f"Add a rule for them to {MAP_FILE}."
        )
    found += [
        f"{MAP_FILE} line {first_line[area]}: the area {area} matches no tracked file. "
        "Correct its pattern, or remove the rule."
        for area in names(rules)
        if area not in used
    ]
    return found
