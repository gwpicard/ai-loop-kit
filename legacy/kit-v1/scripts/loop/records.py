"""The checks that hold a project's records model, one rule at a time.

The records model gives every fact one home and a limit. This module checks
what a script can check. `kit/scripts/records-check.py` is the command line.

The rules, by name:

- `agents.missing`, `agents.lines`, `agents.section`: `AGENTS.md` exists, has at
  most 150 lines, and no `##` section holds more than 12 lines that are not blank.
- `claude.import`: `CLAUDE.md` holds the line `@AGENTS.md` and nothing else.
- `names`: a path, link, command or setting named in `README.md`, `AGENTS.md`,
  `docs/overview.md` or a listed concept file still exists (`document-claims.py`).
- `overview.missing`, `overview.lines`: `docs/overview.md` exists and has at most
  100 lines.
- `overview.area`: the overview's area table and the area map name the same areas.
- `overview.sensitive`: each flag is `yes` or `no`, and a sensitive area names its
  boundary.
- `docs.missing`, `docs.lines`: each area doc the table names exists and has at
  most 300 lines.
- `areas`: every tracked file is in an area, and every area matches a file
  (`loop/areas.py`).
- `changelog.missing`, `changelog.entry`: `CHANGELOG.md` exists, and holds an
  entry for each piece the caller says is closing.
- `repeat`: no paragraph of forty words or more appears in two documents
  (`document-bloat.py`).

The sensitive flag lives in the overview's table. The area map holds no prose,
so the flag cannot disagree with it in any other way than the area names.

A closed piece is named by the caller (`--closing`), since the records cannot
know which pieces a merge closes. An entry names its piece as `piece <number>`,
as a hash sign and the number, or as a link that ends in `/issues/<number>`.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from loop import areas
from loop.paths import Paths

AGENTS_LIMIT = 150
SECTION_LIMIT = 12
OVERVIEW_LIMIT = 100
DOC_LIMIT = 300

AGENTS = "AGENTS.md"
CLAUDE = "CLAUDE.md"
OVERVIEW = "docs/overview.md"
CHANGELOG = "CHANGELOG.md"
CLAUDE_IMPORT = "@AGENTS.md"
SCRIPTS = Path(__file__).resolve().parents[1]


class RecordsError(Exception):
    """A helper that could not run. Carries the next command."""

    def __init__(self, message: str, *, next_command: str) -> None:
        super().__init__(message)
        self.next_command = next_command


@dataclass(frozen=True)
class Fault:
    rule: str
    where: str
    message: str
    next_step: str

    def as_dict(self) -> dict[str, str]:
        return {
            "rule": self.rule,
            "where": self.where,
            "message": self.message,
            "next": self.next_step,
        }


@dataclass(frozen=True)
class AreaRow:
    area: str
    sensitive: str
    boundary: str
    doc: str
    line: int


def _read(root: Path, name: str) -> str | None:
    try:
        return (root / name).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


# --- AGENTS.md and CLAUDE.md ---------------------------------------------------


def agents_faults(text: str) -> list[Fault]:
    """Faults in the text of `AGENTS.md`: its length, and the length of each section."""
    found: list[Fault] = []
    lines = text.splitlines()
    if len(lines) > AGENTS_LIMIT:
        found.append(
            Fault(
                "agents.lines",
                f"{AGENTS}:{len(lines)}",
                f"{AGENTS} has {len(lines)} lines, above its limit of {AGENTS_LIMIT}",
                "move the detail to the file that owns it (the overview, an area doc, a check "
                "or a hook), then run records-check.py again",
            )
        )
    heading = "the start of the file"
    start = 1
    count = 0
    for number, line in enumerate([*lines, "## "], start=1):
        if line.startswith("## "):
            if count > SECTION_LIMIT:
                found.append(
                    Fault(
                        "agents.section",
                        f"{AGENTS}:{start}",
                        f"the section {heading!r} has {count} lines, above its limit of "
                        f"{SECTION_LIMIT}",
                        "split it, shorten it or move the detail to the file that owns it",
                    )
                )
            heading = line[3:].strip()
            start = number
            count = 0
        elif line.strip() and not line.startswith("# "):
            count += 1
    return found


def claude_faults(text: str | None) -> list[Fault]:
    wanted = (
        f"{CLAUDE} must hold the line {CLAUDE_IMPORT} and nothing else, so that "
        f"{AGENTS} is the one home of the rules"
    )
    fix = f"write {CLAUDE} as the single line {CLAUDE_IMPORT}"
    if text is None:
        return [Fault("claude.import", CLAUDE, f"{CLAUDE} is missing; {wanted}", fix)]
    content = [line.strip() for line in text.splitlines() if line.strip()]
    if content != [CLAUDE_IMPORT]:
        message = f"{CLAUDE} holds more than the import; {wanted}"
        return [Fault("claude.import", CLAUDE, message, fix)]
    return []


# --- the overview --------------------------------------------------------------


def _cells(line: str) -> list[str]:
    inner = line.strip().strip("|")
    return [cell.strip().strip("`").strip() for cell in inner.split("|")]


def overview_rows(text: str) -> list[AreaRow] | None:
    """The rows of the overview's area table, or None when it has no such table.

    The table's header row starts with `Area`, and carries `Sensitive`, `Boundary`
    and `Doc` columns.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        header = [cell.lower() for cell in _cells(line)]
        if not header or header[0] != "area":
            continue
        wanted = ("sensitive", "boundary", "doc")
        if any(name not in header for name in wanted):
            return None
        position = {name: header.index(name) for name in wanted}
        rows: list[AreaRow] = []
        for offset, row in enumerate(lines[index + 2 :], start=index + 3):
            if not row.lstrip().startswith("|"):
                break
            cells = _cells(row) + [""] * len(wanted) * 2
            rows.append(
                AreaRow(
                    cells[0],
                    cells[position["sensitive"]].lower(),
                    cells[position["boundary"]],
                    cells[position["doc"]],
                    offset,
                )
            )
        return rows
    return None


def overview_faults(
    text: str | None, rules: list[areas.Rule] | None, tracked: set[str], root: Path
) -> list[Fault]:
    """Faults in the overview and in the area docs its table names."""
    if text is None:
        return [
            Fault(
                "overview.missing",
                OVERVIEW,
                f"{OVERVIEW} is missing",
                "copy kit/templates/overview.md to docs/overview.md and fill it in",
            )
        ]
    found: list[Fault] = []
    count = len(text.splitlines())
    if count > OVERVIEW_LIMIT:
        found.append(
            Fault(
                "overview.lines",
                OVERVIEW,
                f"{OVERVIEW} has {count} lines, above its limit of {OVERVIEW_LIMIT}",
                "move the detail to the area doc that owns it",
            )
        )
    rows = overview_rows(text)
    if rows is None:
        found.append(
            Fault(
                "overview.area",
                OVERVIEW,
                f"{OVERVIEW} has no area table (header: Area, Purpose, Sensitive, Boundary, Doc)",
                "add the table as kit/templates/overview.md shows",
            )
        )
        return found
    named = {row.area for row in rows}
    if rules is not None:
        mapped = areas.names(rules)
        for row in rows:
            if row.area not in mapped:
                found.append(
                    Fault(
                        "overview.area",
                        f"{OVERVIEW}:{row.line}",
                        f"the overview names the area {row.area}, and {areas.MAP_FILE} has no "
                        "such area",
                        f"add the area to {areas.MAP_FILE}, or take it from the table",
                    )
                )
        for name in mapped:
            if name not in named:
                found.append(
                    Fault(
                        "overview.area",
                        OVERVIEW,
                        f"{areas.MAP_FILE} has the area {name}, and the overview does not name it",
                        "add a row for it to the area table",
                    )
                )
    for row in rows:
        where = f"{OVERVIEW}:{row.line}"
        if row.sensitive not in ("yes", "no"):
            found.append(
                Fault(
                    "overview.sensitive",
                    where,
                    f"the sensitive flag of {row.area} is {row.sensitive!r}; write yes or no",
                    "correct the flag",
                )
            )
        elif row.sensitive == "yes" and not row.boundary:
            found.append(
                Fault(
                    "overview.sensitive",
                    where,
                    f"{row.area} is sensitive and names no boundary",
                    "write where the area ends in the Boundary column",
                )
            )
        found += _doc_faults(row, where, tracked, root)
    return found


def _doc_faults(row: AreaRow, where: str, tracked: set[str], root: Path) -> list[Fault]:
    if not row.doc or row.doc not in tracked:
        named = f"names {row.doc}, which is not tracked" if row.doc else "names no area doc"
        return [
            Fault(
                "docs.missing",
                where,
                f"the row for {row.area} {named}",
                "write the area doc and track it, or correct the Doc column",
            )
        ]
    text = _read(root, row.doc)
    count = len((text or "").splitlines())
    if count > DOC_LIMIT:
        return [
            Fault(
                "docs.lines",
                row.doc,
                f"{row.doc} has {count} lines, above its limit of {DOC_LIMIT}",
                "split the area, and give each part a row in the overview",
            )
        ]
    return []


# --- the changelog -------------------------------------------------------------


def changelog_faults(text: str | None, closing: Sequence[int]) -> list[Fault]:
    if text is None:
        return [
            Fault(
                "changelog.missing",
                CHANGELOG,
                f"{CHANGELOG} is missing",
                "copy kit/templates/CHANGELOG.md to CHANGELOG.md",
            )
        ]
    found: list[Fault] = []
    for number in closing:
        pattern = rf"(?i)(?:\bpiece\s+#?|#|/issues/){number}(?!\d)"
        if not re.search(pattern, text):
            found.append(
                Fault(
                    "changelog.entry",
                    CHANGELOG,
                    f"piece {number} is closing and {CHANGELOG} has no entry for it",
                    f"add its entry under Added, Changed, Removed, Fixed or Security, "
                    f"with the link (piece {number})",
                )
            )
    return found


# --- the two helpers -----------------------------------------------------------


def _helper(scripts: Path, name: str, root: Path, *args: str) -> list[list[str]]:
    script = scripts / name
    if not script.is_file():
        raise RecordsError(
            f"{script} is missing", next_command="restore the kit's scripts folder, then run again"
        )
    done = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise RecordsError(
            f"{name} failed: {done.stderr.strip()[:200]}",
            next_command=f"python3 {script} {' '.join(args)}".strip(),
        )
    return [row.split("\t") for row in done.stdout.split("\n") if row]


def names_faults(scripts: Path, root: Path) -> list[Fault]:
    found: list[Fault] = []
    for row in _helper(scripts, "document-claims.py", root):
        if len(row) == 3:
            where, kind, name = row
            found.append(
                Fault(
                    "names",
                    where,
                    f"it names the {kind} {name}, which does not exist",
                    "correct the name, or take the line out",
                )
            )
    return found


def repeat_faults(scripts: Path, root: Path) -> list[Fault]:
    found: list[Fault] = []
    for row in _helper(scripts, "document-bloat.py", root, "--repeated"):
        if len(row) == 3 and row[0] == "repeated":
            found.append(
                Fault(
                    "repeat",
                    row[1],
                    f"the same paragraph as {row[2]}",
                    "keep it in one home and point at it from the other",
                )
            )
    return found


# --- the whole check -----------------------------------------------------------


def check(
    root: Path, *, closing: Sequence[int] = (), scripts: Path | None = None
) -> list[Fault]:
    """Every fault in the project's records at `root`. Raises `RecordsError`."""
    helpers = scripts or SCRIPTS
    paths = Paths.for_project(root, data_base=root, kit_folder=root)
    found: list[Fault] = []

    agents = _read(root, AGENTS)
    if agents is None:
        found.append(
            Fault(
                "agents.missing",
                AGENTS,
                f"{AGENTS} is missing",
                "copy kit/templates/AGENTS.md to AGENTS.md and fill it in",
            )
        )
    else:
        found += agents_faults(agents)
    found += claude_faults(_read(root, CLAUDE))

    try:
        tracked_list = areas.tracked_files(root)
    except areas.AreaMapError as error:
        raise RecordsError(str(error), next_command=error.next_command) from error
    rules: list[areas.Rule] | None
    try:
        rules = areas.load(paths)
    except areas.AreaMapError as error:
        rules = None
        found.append(Fault("areas", areas.MAP_FILE, str(error), error.next_command))
    if rules is not None:
        found += [
            Fault("areas", areas.MAP_FILE, problem, f"correct {areas.MAP_FILE}")
            for problem in areas.problems(rules, tracked_list)
        ]

    found += overview_faults(_read(root, OVERVIEW), rules, set(tracked_list), root)
    found += changelog_faults(_read(root, CHANGELOG), closing)
    found += names_faults(helpers, root)
    found += repeat_faults(helpers, root)
    return found
