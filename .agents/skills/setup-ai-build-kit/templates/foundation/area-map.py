#!/usr/bin/env python3
"""area-map.py: read the project's area map and say whether it is true.

Every folder of the project belongs to a named area. The map is the
`## Areas` section of docs/working-rules.md, one line for each area:

  - <name>: <path>, <path>
    sensitive: <name of a line under Sensitive areas: in masterplan.md>
    boundary: <the one boundary the area must not cross>

An area whose folder does not exist yet is written `- <name>: none yet`.

Usage:
  area-map.py check           the map claims every tracked folder, and is true
  area-map.py which <path>... the area each path belongs to, one line each
  area-map.py areas           every area, with its sensitive name or -

`which` prints `<path><TAB><area>` for each path, in the order given, where the
area is a name, `unclaimed`, or `exempt` for a path in a hidden top-level
folder, a file at the project root, or a path under `changes/`. `areas` prints
`<area><TAB><sensitive name or ->` in file order. Both exit 0 whenever the map
can be read. `check` prints one line and exits 0 when the map is true, and
otherwise prints one line for each problem and exits 1. A map that cannot be
read, a missing file and a folder outside Git exit 1 with one line, for every
action. The script reads the project through Git and writes nothing.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import NamedTuple

MAP_FILE = "docs/working-rules.md"
MASTERPLAN = "masterplan.md"
FOUNDING_STEP = ("founding writes it in the setup-ai-build-kit skill's step 7, "
                 "Write the masterplan")
CLAIM = "Say which area it belongs to in the Areas section of docs/working-rules.md."
NO_GIT = ("area-map.py needs a Git repository; run it from the project folder after founding "
          "has saved its first checkpoint, or after git init.")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


class MapError(Exception):
    """The map cannot be read, said in one line."""


class Area(NamedTuple):
    name: str
    line: int
    paths: list[tuple[str, int]]
    sensitive: tuple[str, int] | None
    boundary: str | None


def blank_comments(text: str) -> str:
    """The text with each HTML comment emptied, keeping its line breaks."""
    return COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def clean_path(path: str) -> str:
    path = path.strip().strip("`").strip()
    while path.startswith("./"):
        path = path[2:]
    return path.rstrip("/")


def read_map(text: str) -> list[Area]:
    """Every area in the Areas section, in file order. Raises MapError."""
    lines = blank_comments(text.replace("\r\n", "\n")).split("\n")
    start = next((i for i, line in enumerate(lines) if line.strip() == "## Areas"), None)
    if start is None:
        raise MapError(f"{MAP_FILE} has no ## Areas section; {FOUNDING_STEP}.")
    areas: list[Area] = []
    names: dict[str, int] = {}
    for index in range(start + 1, len(lines)):
        line = lines[index]
        number = index + 1
        where = f"{MAP_FILE} line {number}"
        if re.match(r"^#{1,2}\s", line):
            break
        if not line.strip():
            continue
        if line[0] in " \t":
            if not areas:
                raise MapError(f"{where}: an indented line sits under no area.")
            key, colon, value = line.strip().partition(":")
            key = key.strip().lower()
            area = areas[-1]
            if not colon or key not in ("sensitive", "boundary"):
                raise MapError(f"{where}: a line under an area is either `sensitive: <name>` "
                               "or `boundary: <rule>`.")
            if not value.strip():
                raise MapError(f"{where}: the {key}: line names nothing.")
            if key == "sensitive":
                if area.sensitive is not None:
                    raise MapError(f"{where}: a second sensitive: line under {area.name}; an "
                                   "area has at most one.")
                areas[-1] = area._replace(sensitive=(value.strip(), number))
            else:
                if area.boundary is not None:
                    raise MapError(f"{where}: a second boundary: line under {area.name}; an "
                                   "area has at most one.")
                areas[-1] = area._replace(boundary=value.strip())
            continue
        if not line.startswith("- "):
            raise MapError(f"{where}: is not an area line; write each area as "
                           "`- <name>: <path>, <path>`.")
        name, colon, rest = line[2:].partition(":")
        name = name.strip()
        if not colon:
            raise MapError(f"{where}: the area line has no colon; write each area as "
                           "`- <name>: <path>, <path>`.")
        if ":" in rest:
            raise MapError(f"{where}: the line holds a second colon; an area name holds no "
                           "comma and no colon.")
        if not name:
            raise MapError(f"{where}: the area has no name before the colon.")
        if "," in name:
            raise MapError(f'{where}: the area name "{name}" holds a comma; an area name '
                           "holds no comma and no colon.")
        if name.lower() in names:
            raise MapError(f"{where}: the area {name} is named twice, first on line "
                           f"{names[name.lower()]}.")
        names[name.lower()] = number
        paths: list[tuple[str, int]] = []
        if rest.strip().lower() != "none yet":
            paths = [(clean_path(p), number) for p in rest.split(",") if clean_path(p)]
            if not paths:
                raise MapError(f"{where}: {name} names no path; write `none yet` while its "
                               "folder does not exist.")
        areas.append(Area(name, number, paths, None, None))
    return areas


def sensitive_lines(text: str) -> list[tuple[str, int, str]]:
    """The lines under `Sensitive areas:` in the masterplan: name, line, whole line.

    `Sensitive areas: none`, written on the line itself, and a masterplan with
    no such line both give none.
    """
    lines = blank_comments(text.replace("\r\n", "\n")).split("\n")
    found: list[tuple[str, int, str]] = []
    for index, line in enumerate(lines):
        if not line.startswith("Sensitive areas:"):
            continue
        if line[len("Sensitive areas:"):].strip():
            return []
        for below in range(index + 1, len(lines)):
            text_below = lines[below]
            if not text_below.strip():
                continue
            if text_below[0] not in " \t":
                break
            name = text_below.strip().split(":", 1)[0].strip()
            if name:
                found.append((name, below + 1, text_below.strip()))
        return found
    return []


# --- the project ------------------------------------------------------------------

def project_root() -> str:
    try:
        done = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                              text=True, check=False)
    except OSError:
        raise MapError(NO_GIT)
    if done.returncode != 0 or not done.stdout.strip():
        raise MapError(NO_GIT)
    return done.stdout.strip()


def read_file(root: str, name: str) -> str | None:
    try:
        with open(os.path.join(root, name), encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def load(root: str) -> list[Area]:
    text = read_file(root, MAP_FILE)
    if text is None:
        raise MapError(f"{MAP_FILE} is missing; {FOUNDING_STEP}.")
    return read_map(text)


def tracked_files(root: str) -> list[str]:
    done = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True,
                          check=False)
    if done.returncode != 0:
        raise MapError(NO_GIT)
    return [p for p in done.stdout.decode("utf-8", "replace").split("\0") if p]


def is_exempt(path: str, folders: set[str], root: str) -> bool:
    top = path.split("/", 1)[0]
    if top.startswith(".") or top == "changes":
        return True
    if "/" not in path:
        return path not in folders and not os.path.isdir(os.path.join(root, path))
    return False


def area_of(path: str, areas: list[Area]) -> str | None:
    """The name of the most specific area whose listed path holds this one."""
    best: tuple[int, str] | None = None
    for area in areas:
        for listed, _ in area.paths:
            holds = path == listed or path.startswith(listed + "/")
            if holds and (best is None or len(listed) > best[0]):
                best = (len(listed), area.name)
    return best[1] if best else None


# --- the actions --------------------------------------------------------------------

def which(root: str, areas: list[Area], given: list[str]) -> int:
    folders = folders_of(tracked_files(root))
    for path in given:
        clean = clean_path(path)
        name = area_of(clean, areas)
        if name is None:
            name = "exempt" if is_exempt(clean, folders, root) else "unclaimed"
        print(f"{path}\t{name}")
    return 0


def areas_action(areas: list[Area]) -> int:
    for area in areas:
        print(f"{area.name}\t{area.sensitive[0] if area.sensitive else '-'}")
    return 0


def folders_of(files: list[str]) -> set[str]:
    folders: set[str] = set()
    for path in files:
        parts = path.split("/")
        for n in range(1, len(parts)):
            folders.add("/".join(parts[:n]))
    return folders


def check(root: str, areas: list[Area]) -> int:
    problems: list[str] = []
    files = tracked_files(root)
    folders = folders_of(files)
    known = set(files) | folders

    owner: dict[str, tuple[str, int]] = {}
    for area in areas:
        for listed, number in area.paths:
            where = f"{MAP_FILE} line {number}"
            if listed in owner:
                first, line = owner[listed]
                problems.append(f"{where}: {listed} is listed under {area.name} and under "
                                f"{first} (line {line}). A path belongs to one area.")
                continue
            owner[listed] = (area.name, number)
            if listed not in known and not os.path.exists(os.path.join(root, listed)):
                problems.append(f"{where}: {listed} is listed under {area.name} but does not "
                                "exist. Say where it moved, or write `none yet` while it is "
                                "still to come.")

    plan_text = read_file(root, MASTERPLAN) or ""
    named = {name.lower(): (name, number) for name, number, _ in sensitive_lines(plan_text)}
    pointed: set[str] = set()
    for area in areas:
        if area.sensitive is None:
            continue
        name, number = area.sensitive
        pointed.add(name.lower())
        if name.lower() not in named:
            problems.append(f"{MAP_FILE} line {number}: sensitive: {name} names no line under "
                            f"Sensitive areas: in {MASTERPLAN}. Name a sensitive area the "
                            "masterplan's build path lists.")
    for key, (name, number) in named.items():
        if key not in pointed:
            problems.append(f"{MASTERPLAN} line {number}: the sensitive area {name} has no "
                            f"area pointing at it. Add `sensitive: {name}` under its area in "
                            f"{MAP_FILE}.")

    held_paths = set(owner)

    def held(path: str) -> bool:
        parts = path.split("/")
        return any("/".join(parts[:n]) in held_paths for n in range(1, len(parts) + 1))

    children: dict[str, set[str]] = {}
    for path in files:
        parts = path.split("/")
        for n in range(1, len(parts)):
            children.setdefault("/".join(parts[:n]), set()).add("/".join(parts[:n + 1]))
    claimed_cache: dict[str, bool] = {}

    def claimed(path: str) -> bool:
        if path not in claimed_cache:
            if held(path):
                claimed_cache[path] = True
            elif path in children:
                claimed_cache[path] = all(claimed(child) for child in children[path])
            else:
                claimed_cache[path] = False
        return claimed_cache[path]

    def report(path: str) -> None:
        if claimed(path):
            return
        inside = [p for p in held_paths if p.startswith(path + "/")]
        if path in children and inside:
            for child in sorted(children[path]):
                report(child)
            return
        kind = "folder" if path in children else "file"
        problems.append(f"{path} is a {kind} no area claims. {CLAIM}")

    for top in sorted(p for p in folders if "/" not in p):
        if top.startswith(".") or top == "changes":
            continue
        report(top)

    if problems:
        for problem in problems:
            print(problem)
        return 1
    count = len(areas)
    print(f"The area map in {MAP_FILE} claims every folder: {count} "
          f"area{'' if count == 1 else 's'}.")
    return 0


USAGE = "usage: area-map.py check | which <path>... | areas"


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print((__doc__ or "").strip())
        return 0 if argv else 2
    action = argv[0]
    if action not in ("check", "which", "areas") or (action == "which" and len(argv) < 2) \
            or (action != "which" and len(argv) != 1):
        print(USAGE, file=sys.stderr)
        return 2
    try:
        root = project_root()
        areas = load(root)
        if action == "which":
            return which(root, areas, argv[1:])
        if action == "areas":
            return areas_action(areas)
        return check(root, areas)
    except MapError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
