"""The docs commit: the project's records, brought up to date before the final combined check.

After the last join, this makes one more commit on the combined branch. It works in a scratch
copy of the branch and moves the branch only when the result is good. For each joined piece, in
join order, it:

1. adds a new area the piece names (`New area:` in its Changes field) to the area map, and a
   row for each area in the map that the overview lacks, with an area doc to match;
2. applies the piece's `Added:`, `Changed:` and `Removed:` lines to the area docs of the areas
   it touches. An added or changed line becomes a requirement line with a link to the piece. A
   removed line takes out the requirement line that says the same;
3. writes one changelog entry from the piece's behaviour change into `changes/`, then folds the
   files into `CHANGELOG.md` with `fold-changes.py` (a second commit), under the day, in the
   section Added, Changed, Removed, Fixed or Security.

`records-check.py`'s checks (`loop.records`) must pass on the result, with a changelog entry for
every joined piece. If they do not, the branch does not move, and the refusal names each fault.

The commit is idempotent. A piece whose lines are in the area doc, and whose entry is in the
changelog, adds nothing, and a run with nothing to add makes no commit.
"""

from __future__ import annotations

import contextlib
import re
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loop import areas, github, records
from loop.paths import Paths
from loop.run.integrate import (
    MAIN,
    QUIET,
    IntegrationRefusal,
    PieceView,
    _git,
    _must,
    remove_worktree,
    trailers,
)

CHANGES = "changes"
SECTIONS = ("Added", "Changed", "Removed", "Fixed", "Security")


@dataclass
class DocsResult:
    committed: bool
    head: str = ""
    notes: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


def _clean(text: str) -> str:
    return " ".join(text.split())


def _sentence(text: str) -> str:
    text = _clean(text)
    return text if not text or text[-1] in ".!?" else text + "."


def section_of(view: PieceView) -> str:
    changes = view.spec["changes"]
    if changes.get("security"):
        return "Security"
    if view.issue_type == "bug":
        return "Fixed"
    for name in ("added", "changed", "removed"):
        if changes.get(name):
            return name.capitalize()
    return "Changed"


def entry_text(view: PieceView, link: str) -> str:
    """One changelog entry for a piece, from its behaviour change."""
    changes = view.spec["changes"]
    parts = [_sentence(t) for name in ("added", "changed") for t in changes.get(name, [])
             if _clean(t)]
    parts += [f"Removed: {_sentence(t)}" for t in changes.get("removed", []) if _clean(t)]
    text = " ".join(parts) or _sentence(view.title) or f"Piece {view.number}."
    return f"{text} ({link})"


def _link(root: Path, view: PieceView) -> str:
    label = f"piece {view.number}"
    if view.issue is None:
        return label
    code, url, _ = _git(root, "config", "--get", "remote.origin.url")
    base = github.github_address(url) if code == 0 and url else None
    if base is None:
        return label
    return f"[{label}]({base.removesuffix('.git')}/issues/{view.issue})"


# --- the area map and the overview ------------------------------------------------------------


def _join_commit(root: Path, head: str, number: int) -> tuple[str, str] | None:
    """The join commit of a piece and its first parent, read from the `Piece:` trailers."""
    code, out, _ = _git(root, "log", "--first-parent", "--format=%H%x1f%P%x1f%B%x1e", head,
                        f"^refs/heads/{MAIN}")
    if code != 0:
        return None
    for row in out.split("\x1e"):
        fields = row.strip().split("\x1f")
        if len(fields) == 3 and trailers(fields[2]) == [number] and fields[1].split():
            return fields[0], fields[1].split()[0]
    return None


def _unclaimed(root: Path, head: str, number: int, rules: list[areas.Rule]) -> list[str]:
    found = _join_commit(root, head, number)
    if found is None:
        return []
    commit, parent = found
    code, out, _ = _git(root, "diff", "--no-renames", "--name-only", "-z", parent, commit, "--")
    if code != 0:
        return []
    return sorted(p for p in out.split("\0")
                  if p and areas.area_of(rules, p) is None and not areas.is_exempt(p))


def _patterns(root: Path, head: str, files: Sequence[str], rules: list[areas.Rule],
              area: str) -> list[str]:
    """Rules for `files`: a folder where all its files are unclaimed, else one rule a file."""
    _, listing, _ = _git(root, "ls-tree", "-r", "--name-only", head)
    tracked = [p for p in listing.splitlines() if p]
    rules_out: list[str] = []
    done: set[str] = set()
    for path in files:
        folder = path.rsplit("/", 1)[0] if "/" in path else ""
        if folder and folder not in done:
            inside = [p for p in tracked if p.startswith(folder + "/")]
            if all(areas.area_of(rules, p) is None or areas.area_of(rules, p) == area
                   for p in inside):
                rules_out.append(f"{folder}/ {area}")
                done.add(folder)
                continue
        if folder in done:
            continue
        rules_out.append(f"/{path} {area}")
    return rules_out


def _read(folder: Path, name: str) -> str | None:
    try:
        return (folder / name).read_text(encoding="utf-8")
    except OSError:
        return None


def _map_and_overview(scratch: Path, head: str, pieces: Sequence[PieceView],
                      notes: list[str], files: set[str]) -> None:
    text = _read(scratch, areas.MAP_FILE)
    rules = areas.parse(text) if text is not None else []
    new_lines: list[str] = []
    who: dict[str, PieceView] = {}
    for view in pieces:
        for area in view.spec["changes"]["new_area"]:
            who.setdefault(area, view)
            if area in areas.names(rules):
                continue
            unclaimed = _unclaimed(scratch, head, view.number, rules)
            if not unclaimed:
                notes.append(f"piece {view.number} names the new area {area}, and no file it "
                             "changed is outside the area map, so no rule was added")
                continue
            added = _patterns(scratch, head, unclaimed, rules, area)
            new_lines += added
            rules = areas.parse((text or "") + "\n" + "\n".join(new_lines) + "\n")
    if new_lines:
        body = (text or "").rstrip("\n")
        (scratch / areas.MAP_FILE).write_text(
            (body + "\n" if body else "") + "\n".join(new_lines) + "\n", encoding="utf-8")
        files.add(areas.MAP_FILE)
    overview = _read(scratch, records.OVERVIEW)
    if overview is None:
        raise IntegrationRefusal(
            f"{records.OVERVIEW} is missing, so the area table cannot be brought up to date",
            "copy kit/templates/overview.md to docs/overview.md and fill it in")
    rows = records.overview_rows(overview)
    if rows is None:
        raise IntegrationRefusal(
            f"{records.OVERVIEW} has no area table", "add the table as "
            "kit/templates/overview.md shows")
    named = {row.area for row in rows}
    lines = overview.split("\n")
    at = rows[-1].line if rows else len(lines)
    fresh: list[str] = []
    for area in areas.names(rules):
        if area in named:
            continue
        owner = who.get(area)
        purpose = _clean(owner.title) if owner is not None else f"The {area} area"
        doc = f"docs/{area}.md"
        fresh.append(f"| {area} | {purpose} | no | | `{doc}` |")
        target = scratch / doc
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"# {area}\n\n", encoding="utf-8")
            files.add(doc)
    if fresh:
        lines[at:at] = fresh
        (scratch / records.OVERVIEW).write_text("\n".join(lines), encoding="utf-8")
        files.add(records.OVERVIEW)


# --- the area docs ----------------------------------------------------------------------------


def _doc_of(scratch: Path, area: str) -> str | None:
    overview = _read(scratch, records.OVERVIEW)
    rows = records.overview_rows(overview) if overview is not None else None
    for row in rows or []:
        if row.area == area and row.doc:
            return row.doc
    return None


def _bare(line: str) -> str:
    line = re.sub(r"\s*\((?:\[)?piece \d+[^)]*\)?\)?\s*$", "", line.strip())
    line = line[2:] if line.startswith("- ") else line
    return _clean(line).rstrip(".").lower()


def _behaviour(scratch: Path, pieces: Sequence[PieceView], notes: list[str],
               files: set[str]) -> None:
    for view in pieces:
        changes = view.spec["changes"]
        touched = [a for a in view.spec["links"]["touches"] if a.lower() != "none"]
        edits = [("add", t) for name in ("added", "changed") for t in changes.get(name, [])
                 if _clean(t)]
        edits += [("remove", t) for t in changes.get("removed", []) if _clean(t)]
        if not edits:
            continue
        if not touched:
            notes.append(f"piece {view.number} touches no area, so its lines reach the "
                         "changelog only")
            continue
        for area in touched:
            doc = _doc_of(scratch, area)
            if doc is None:
                raise IntegrationRefusal(
                    f"piece {view.number} touches the area {area}, and the overview has no row "
                    "with a doc for it", f"add the area {area} to {records.OVERVIEW}, then run "
                    "the docs commit again")
            text = _read(scratch, doc)
            if text is None:
                text = f"# {area}\n\n"
            lines = text.split("\n")
            for kind, wanted in edits:
                key = _bare(wanted)
                if kind == "add":
                    if any(_bare(line) == key for line in lines if line.startswith("- ")):
                        continue
                    while lines and not lines[-1].strip():
                        lines.pop()
                    lines += [f"- {_sentence(wanted)} (piece {view.number})", ""]
                else:
                    kept = [line for line in lines
                            if not (line.startswith("- ") and _bare(line) == key)]
                    if len(kept) == len(lines):
                        notes.append(f"piece {view.number} removes \"{_clean(wanted)}\", and "
                                     f"{doc} holds no line that says it")
                    lines = kept
            new = "\n".join(lines)
            if not new.endswith("\n"):
                new += "\n"
            if new != text:
                (scratch / doc).parent.mkdir(parents=True, exist_ok=True)
                (scratch / doc).write_text(new, encoding="utf-8")
                files.add(doc)


# --- the changelog ----------------------------------------------------------------------------


def _write_entries(scratch: Path, pieces: Sequence[PieceView], files: set[str]) -> None:
    changelog = _read(scratch, records.CHANGELOG) or ""
    for view in pieces:
        if re.search(rf"(?i)\bpiece\s+{view.number}(?!\d)", changelog):
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", view.title.lower()).strip("-")[:30].strip("-")
        name = f"{CHANGES}/{view.number}-{slug or 'piece'}.md"
        target = scratch / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"Section: {section_of(view)}\n"
                          f"{entry_text(view, _link(scratch, view))}\n", encoding="utf-8")
        files.add(name)


def _fold(scratch: Path, paths: Paths) -> str:
    script = paths.kit_dir / "scripts" / "fold-changes.py"
    done = subprocess.run([sys.executable, str(script), "--main", MAIN], cwd=scratch,
                          capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise IntegrationRefusal(
            f"fold-changes.py failed ({(done.stderr or done.stdout).strip()[:200]}), so the "
            "changelog was not written", f"python3 {script} --main {MAIN}, in a copy of the "
            "combined branch")
    return done.stdout


# --- the commit -------------------------------------------------------------------------------


def _commit(scratch: Path, identity: Sequence[str], message: str) -> bool:
    _must(scratch, "staged the docs", "add", "-A")
    if _git(scratch, "diff", "--cached", "--quiet")[0] == 0:
        return False
    _must(scratch, "made the docs commit", "commit", "-q", "--no-verify", "-m", message,
          config=[*identity, *QUIET])
    return True


def apply(*, root: Path, paths: Paths, branch: str, pieces: Sequence[PieceView], run: str,
          gate_lock: Any, identity: Sequence[str]) -> DocsResult:
    """Make the docs commit on `branch`, or make none. A refusal moves nothing."""
    ref = f"refs/heads/{branch}"
    head = _must(root, "read the combined branch", "rev-parse", ref)
    folder = paths.run_dir(run) / "docs"
    folder.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="docs-", dir=folder)) / "copy"
    with gate_lock:
        _must(root, "made the scratch copy", "worktree", "add", "-q", "--detach", str(scratch),
              head)
    result = DocsResult(False, head)
    try:
        files: set[str] = set()
        _map_and_overview(scratch, head, pieces, result.notes, files)
        _behaviour(scratch, pieces, result.notes, files)
        _write_entries(scratch, pieces, files)
        wrote = _commit(scratch, identity, f"Update the docs and the changelog for run {run}")
        if (scratch / CHANGES).is_dir() and _git(scratch, "ls-tree", "--name-only", "HEAD",
                                                 f"{CHANGES}/")[1]:
            _fold(scratch, paths)
            folded = _commit(scratch, identity, "Fold the changelog")
            wrote = wrote or folded
        if not wrote:
            return result
        faults = records.check(scratch, closing=[v.number for v in pieces],
                               scripts=paths.kit_dir / "scripts")
        if faults:
            shown = "; ".join(f"{f.where}: {f.message}" for f in faults[:5])
            more = f" and {len(faults) - 5} more" if len(faults) > 5 else ""
            raise IntegrationRefusal(
                f"the records are not right after the docs commit, so the branch does not "
                f"move: {shown}{more}",
                faults[0].next_step + f", then run.py --run {run}")
        new = _must(scratch, "read the docs commit", "rev-parse", "HEAD")
        with gate_lock:
            code, _, err = _git(root, "update-ref", "-m", f"docs commit for run {run}", ref,
                                new, head)
        if code != 0:
            raise IntegrationRefusal(
                f"the combined branch {branch} moved while the docs commit was made "
                f"({err[:120]})", f"run.py --run {run} to make the docs commit again")
        result.committed = True
        result.head = new
        result.files = sorted(files)
        return result
    except records.RecordsError as error:
        raise IntegrationRefusal(str(error), error.next_command) from error
    finally:
        with gate_lock:
            note = remove_worktree(root, scratch)
        if note:
            result.notes.append(note)
        with contextlib.suppress(OSError):
            scratch.parent.rmdir()


__all__ = ["DocsResult", "apply", "entry_text", "section_of"]
