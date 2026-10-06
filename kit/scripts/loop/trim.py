"""The trim pass: the last step of a piece's build loop (design: "The trim pass").

A fresh session may only remove or fold code the piece added, in one commit on a scratch
branch. It never touches a test. This module holds the rules and the whole pass:

- `check` judges the trim commit by four rules. It touches no test, no judge file and no
  other file of the frozen bar (the list comes from `loop.bar`). It changes only lines the
  piece added, read against the piece's base commit. It adds no file. It adds no net lines;
  "net" is the lines added minus the lines removed in the trim commit;
- `tool_reports` runs the unused-code and duplicated-code tools the project already has, and
  `findings_text` shapes the reports for the trim brief. It never installs a tool;
- `run_pass` makes the scratch branch and its worktree, runs the session (`loop.sessions`, so
  the brief holds outside text only in data blocks and the settings deny a write to every test),
  runs `check`, runs the attempt checks again on the scratch head (`attempt.rerun`, which
  counts no attempt), and only then moves the piece branch to the scratch head by a
  fast-forward. On a failure it throws the trim away: the scratch branch is left, the piece
  branch is unchanged, and the piece goes on untrimmed.

Nothing here runs `git reset`, `git revert`, a forced update or a recursive delete. A git
error or an unreadable file is a refusal (`TrimError`), never a pass. Once the piece branch
has moved, a later failure cannot throw the trim away; it goes back through the normal routes.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loop import bar, sessions
from loop.gates import CheckContext, attempt, claim
from loop.paths import PathError

REPORT_LIMIT = 6000  # characters of one tool's report kept for the brief
TOOL_SECONDS = 120
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
NONE_TEXT = (
    "The project has no tool for unused code or duplicated code (no vulture, knip or jscpd "
    "is installed or set up), so there is no report. Read the code the piece added instead."
)


class TrimError(Exception):
    """A refusal: the trim pass could not tell. It never counts as a pass."""

    def __init__(self, message: str, next_command: str) -> None:
        super().__init__(message)
        self.next_command = next_command


@dataclass(frozen=True)
class Violation:
    rule: str
    path: str
    text: str

    def line(self) -> str:
        where = f" {self.path} ({self.text})" if self.path else f" {self.text}"
        return f"{self.rule}:{where}"

    def as_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "path": self.path, "text": self.text}


@dataclass
class Verdict:
    violations: list[Violation] = field(default_factory=list)
    commits: int = 0
    net: int = 0
    files: list[str] = field(default_factory=list)


# --- git ----------------------------------------------------------------------------------


def _git(root: Path, *args: str, ok: Sequence[int] = (0,)) -> tuple[int, str]:
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "-c", "core.quotePath=false", *args],
            capture_output=True, check=False,
        )
    except OSError as error:
        raise TrimError(f"git could not be started ({error.strerror})",
                        "install git, then run the trim pass again") from error
    if done.returncode not in ok:
        first = next((ln for ln in done.stderr.decode("utf-8", "replace").splitlines()
                      if ln.strip()), "no message")
        raise TrimError(
            f"git {args[0]} failed ({first.strip()[:120]}), so the trim pass cannot tell",
            "check the project's git repository, then run the trim pass again",
        )
    return done.returncode, done.stdout.decode("utf-8", "replace")


def _commit(root: Path, ref: str) -> str:
    return _git(root, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")[1].strip()


def _exists_at(root: Path, ref: str, path: str) -> bool:
    return bool(_git(root, "ls-tree", ref, "--", path)[1].strip())


def _hunks(root: Path, old: str, new: str, path: str) -> list[tuple[int, int, int, int]]:
    """The hunks of one file between two commits: (old start, old count, new start, new count)."""
    text = _git(root, "diff", "--no-renames", "--no-color", "--no-ext-diff", "-U0", old, new,
                "--", path)[1]
    found: list[tuple[int, int, int, int]] = []
    for line in text.splitlines():
        match = HUNK.match(line)
        if match:
            a, b, c, d = match.groups()
            found.append((int(a), 1 if b is None else int(b), int(c), 1 if d is None else int(d)))
    return found


def _added_lines(root: Path, base: str, piece: str, path: str) -> set[int] | None:
    """The line numbers (in the piece head) the piece added to `path`. None means all of them."""
    if not _exists_at(root, base, path):
        return None
    lines: set[int] = set()
    for _a, _b, start, count in _hunks(root, base, piece, path):
        lines.update(range(start, start + count))
    return lines


# --- the rules ----------------------------------------------------------------------------


def _is_barred(path: str, listed: set[str]) -> bool:
    return (path in listed or bar.is_test(path) or bar.is_snapshot(path)
            or bar.is_settings(path) or bar.is_guarded(path))


def check(root: Path, base: str, piece_head: str, trim_head: str, *,
          judge_files: Sequence[str] = ()) -> Verdict:
    """Judge the trim commit(s) from `piece_head` to `trim_head`. A git fault raises `TrimError`."""
    base, piece, trim = _commit(root, base), _commit(root, piece_head), _commit(root, trim_head)
    verdict = Verdict()
    listed_commits = _git(root, "rev-list", f"{piece}..{trim}")[1].split()
    verdict.commits = len(listed_commits)
    descends = _git(root, "merge-base", "--is-ancestor", piece, trim, ok=(0, 1))[0] == 0
    if not descends:
        verdict.violations.append(Violation(
            "own-commit", "", "the scratch branch does not hold the piece's head, so it is not "
            "a trim of this piece"))
        return verdict
    if verdict.commits == 0:
        return verdict
    if verdict.commits > 1:
        verdict.violations.append(Violation(
            "own-commit", "", f"the trim is {verdict.commits} commits, and it must be one"))
    try:
        listed = set(bar.paths(root, piece, list(judge_files)))
        barred_changes = bar.changes(root, piece, trim, judge_commit=None,
                                     judge_files=list(judge_files))
    except bar.BarError as error:
        raise TrimError(str(error), error.next_command) from error
    raw = _git(root, "diff", "--no-renames", "--name-status", "-z", piece, trim, "--")[1]
    parts = raw.split("\0")
    changed = [(parts[i], parts[i + 1]) for i in range(0, len(parts) - 1, 2)]
    counts: dict[str, tuple[str, str]] = {}
    numstat = _git(root, "diff", "--no-renames", "--numstat", "-z", piece, trim, "--")[1]
    for item in numstat.split("\0"):
        fields = item.split("\t", 2)
        if len(fields) == 3:
            counts[fields[2]] = (fields[0], fields[1])
    flagged: set[str] = set()
    for status, path in changed:
        verdict.files.append(path)
        if _is_barred(path, listed):
            flagged.add(path)
            verdict.violations.append(Violation(
                "touches-test", path, "a trim never touches a test, a fixture, a judge file or "
                "a setting of the frozen bar"))
            continue
        if status[:1] == "A":
            verdict.violations.append(Violation(
                "new-file", path, "a trim only removes or folds, so it adds no file"))
            continue
        if status[:1] not in ("M", "D"):
            verdict.violations.append(Violation(
                "not-piece-code", path,
                f"the change has status {status}, which a trim may not make"))
            continue
        added, removed = counts.get(path, ("0", "0"))
        if added == "-" or removed == "-":
            verdict.violations.append(Violation(
                "binary", path, "the file is binary, so the trim pass cannot tell what changed"))
            continue
        verdict.net += int(added) - int(removed)
        owned = _added_lines(root, base, piece, path)
        for old_start, old_count, _start, _count in _hunks(root, piece, trim, path):
            if old_count == 0:
                if owned is not None and not owned:
                    verdict.violations.append(Violation(
                        "not-piece-code", path, "the trim adds a line to a file the piece did "
                        "not change"))
                continue
            lines = range(old_start, old_start + old_count)
            if owned is not None and not all(n in owned for n in lines):
                outside = [n for n in lines if n not in owned]
                verdict.violations.append(Violation(
                    "not-piece-code", path, f"the trim changes line {outside[0]}"
                    + (f" and {len(outside) - 1} more" if len(outside) > 1 else "")
                    + ", which the piece did not add"))
        if status[:1] == "D" and owned is not None and not owned:
            verdict.violations.append(Violation(
                "not-piece-code", path, "the trim deletes a file the piece did not add"))
    for change in barred_changes:
        if change.path not in flagged:
            verdict.violations.append(Violation(change.kind, change.path, change.detail))
    if verdict.net > 0:
        verdict.violations.append(Violation(
            "adds-lines", "", f"the trim adds {verdict.net} net lines, and a trim may only "
            "remove or fold"))
    return verdict


# --- the project's own tools ---------------------------------------------------------------


@dataclass(frozen=True)
class Report:
    tool: str
    kind: str  # unused-code or duplicated-code
    ran: bool
    text: str


TOOLS = (
    ("vulture", "unused-code", ".py"),
    ("knip", "unused-code", None),
    ("jscpd", "duplicated-code", "any"),
)
CONFIG = {
    "knip": ("knip.json", "knip.jsonc", ".knip.json", ".knip.jsonc"),
    "jscpd": (".jscpd.json",),
}


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _executable(tool: str, folders: Sequence[Path], env: Mapping[str, str]) -> str | None:
    for folder in folders:
        local = folder / "node_modules" / ".bin" / tool
        if local.is_file() and os.access(local, os.X_OK):
            return str(local)
    return shutil.which(tool, path=env.get("PATH", os.defpath))


def _configured(tool: str, folders: Sequence[Path]) -> bool:
    for folder in folders:
        if any((folder / name).is_file() for name in CONFIG.get(tool, ())):
            return True
        if tool == "vulture" and "[tool.vulture]" in _read(folder / "pyproject.toml"):
            return True
        package = _read(folder / "package.json")
        if tool != "vulture" and f'"{tool}"' in package:
            return True
    return False


def find_tools(
    root: Path, worktree: Path, env: Mapping[str, str]
) -> list[tuple[str, str, str | None]]:
    """Each tool the project has, as (tool, kind, program). The program is None when the tool is
    set up but not installed. A tool the project does not have is not listed."""
    folders = [worktree] if worktree == root else [worktree, root]
    found: list[tuple[str, str, str | None]] = []
    for tool, kind, _scope in TOOLS:
        program = _executable(tool, folders, env)
        if program or _configured(tool, folders):
            found.append((tool, kind, program))
    return found


def tool_reports(
    root: Path, worktree: Path, changed: Sequence[str], *,
    env: Mapping[str, str] | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> list[Report]:
    """Run each tool the project already has and keep its report. Nothing is installed.

    A tool that cannot run is reported as not run, with the reason, and never as clean.
    """
    environment = dict(os.environ if env is None else env)
    present = [p for p in changed if (worktree / p).is_file()]
    reports: list[Report] = []
    for tool, kind, program in find_tools(root, worktree, environment):
        if program is None:
            reports.append(Report(tool, kind, False, f"{tool} is set up in this project but is "
                                  "not installed, so it did not run"))
            continue
        scope = next(s for t, _k, s in TOOLS if t == tool)
        files = [p for p in present if scope == "any" or (scope and p.endswith(scope))]
        if scope is not None and not files:
            continue
        argv = [program, *files] if tool == "vulture" else (
            [program, "--reporters", "console", *files] if tool == "jscpd" else [program])
        try:
            done = runner(argv, cwd=str(worktree), env=environment, capture_output=True,
                          text=True, check=False, timeout=TOOL_SECONDS)
        except (OSError, subprocess.SubprocessError) as error:
            reports.append(Report(tool, kind, False, f"{tool} did not run ({error})"))
            continue
        if done.returncode in (126, 127):
            reports.append(Report(tool, kind, False, f"{tool} did not run (exit "
                                  f"{done.returncode}: {(done.stderr or '').strip()[:200]})"))
            continue
        text = (done.stdout or "").strip() or (done.stderr or "").strip() or "it reported nothing"
        reports.append(Report(tool, kind, True, text[:REPORT_LIMIT]))
    return reports


def findings_text(reports: Sequence[Report]) -> str:
    """The reports as the trim brief holds them, inside one data block."""
    if not reports:
        return NONE_TEXT
    return "\n\n".join(f"{r.tool} ({r.kind}):\n{r.text}" for r in reports)


# --- the pass -----------------------------------------------------------------------------


def _scratch(root: Path, branch: str, folders: Path, number: int) -> tuple[str, Path, str]:
    """A scratch branch name and worktree folder that nothing uses yet."""
    for count in range(1, 1000):
        suffix = "" if count == 1 else f"-{count}"
        name = f"{branch}-trim{suffix}"
        folder = folders / f"{number}-trim{suffix}"
        taken = _git(root, "show-ref", "--verify", "-q", f"refs/heads/{name}", ok=(0, 1))[0] == 0
        if not taken and not folder.exists():
            return name, folder, suffix
    raise TrimError(f"too many scratch branches sit beside {branch}",
                    "look at the piece's -trim branches, and keep the ones you need")


def _holder(root: Path, branch: str) -> Path | None:
    """The worktree that has `branch` checked out, if any."""
    listing = _git(root, "worktree", "list", "--porcelain")[1]
    for block in listing.split("\n\n"):
        lines = block.splitlines()
        if f"branch refs/heads/{branch}" in lines:
            return Path(next((ln[9:] for ln in lines if ln.startswith("worktree ")), "."))
    return None


def _advance(root: Path, branch: str, old: str, new: str) -> None:
    """Move the piece branch from `old` to `new` by a fast-forward only."""
    holder = _holder(root, branch)
    if holder is not None:
        code, _ = _git(holder, "merge", "--ff-only", "--quiet", new, ok=(0, 1))
        if code != 0:
            raise TrimError(f"the worktree {holder} would not fast-forward {branch}",
                            "save or commit the changes in that worktree, then run the trim "
                            "pass again")
        return
    _git(root, "update-ref", "-m", "trim pass: fast-forward", f"refs/heads/{branch}", new, old)


def _result(outcome: str, **more: Any) -> dict[str, Any]:
    return {"outcome": outcome, **more}


def run_pass(
    ctx: CheckContext, deps: attempt.Deps, *, run: str,
    runner: sessions.Runner = subprocess.run,
    env: Mapping[str, str] | None = None,
    max_budget_usd: float | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the trim pass on a piece that passed the attempt gate.

    Returns the outcome: `trimmed`, `nothing-to-trim` or `untrimmed` (with the reasons). A
    refusal of the pass itself raises `TrimError`.
    """
    paths, root, number = ctx.paths, ctx.paths.root, ctx.number
    recorded = claim._recorded_fingerprint(ctx.record)
    if ctx.spec is None or not ctx.spec["found"] or recorded is None:
        raise TrimError("the piece has no spec or no recorded fingerprint, so the trim pass "
                        "cannot tell what the piece added", f"gate.py report {number}")
    try:
        facts = attempt._facts(ctx, ctx.spec, recorded)
    except attempt.Refusal as error:
        raise TrimError(str(error), error.next_command) from error
    scratch, folder, suffix = _scratch(root, facts.branch, paths.worktrees_dir, number)
    environment = dict(os.environ if env is None else env)
    tools = find_tools(root, root, environment)
    common: dict[str, Any] = {
        "piece": number, "piece_branch": facts.branch, "piece_head": facts.head,
        "base": facts.base, "scratch_branch": scratch,
        "tools": [{"tool": t, "kind": k, "installed": p is not None} for t, k, p in tools],
    }
    if dry_run:
        return _result("dry-run", **common)
    try:
        stat = _git(root, "diff", "--stat", "--no-color", facts.base, facts.head, "--")[1]
        names = _git(root, "diff", "--no-renames", "--name-only", "-z", facts.base, facts.head,
                     "--")[1].split("\0")
        _git(root, "worktree", "add", "-q", "-b", scratch, str(folder), facts.head)
        reports = tool_reports(root, folder, [n for n in names if n], env=environment)
        template = (paths.kit_dir / "briefs" / "trim.md").read_text(encoding="utf-8")
        brief = sessions.render_brief(
            template,
            trusted={"PIECE": str(number),
                     "HANDOFF_COMMAND": sessions.handoff_command(paths.kit_dir)},
            outside={"spec": ctx.body, "diff": stat or "The piece changed no file.",
                     "findings": findings_text(reports)})
        barred = bar.paths(root, facts.head, facts.judge_files)
        session = sessions.plan(
            paths, run=run, label=f"p{number}-trim{suffix}", worktree=folder, brief=brief,
            max_budget_usd=max_budget_usd, env=environment, bar_paths=barred)
        done = sessions.start(session, runner=runner)
    except (bar.BarError, sessions.SessionError, PathError, OSError) as error:
        hint = "check the project's trim brief, then run the trim pass again"
        raise TrimError(str(error), getattr(error, "next_command", "") or hint) from error
    common.update(brief_file=str(session.brief_file), settings_file=str(session.settings_file),
                  reports=[r.tool for r in reports])
    reasons: list[str] = []
    if done.exit_code != 0:
        reasons.append(f"the trim session ended with exit code {done.exit_code}")
    elif done.handoff is None:
        reasons.append("the trim session left no hand-off" + (
            f" ({done.handoff_error})" if done.handoff_error else ""))
    elif done.handoff["outcome"] != "done":
        field_name = sessions.HANDOFF_FIELD[done.handoff["outcome"]]
        reasons.append(f"the trim session handed back {done.handoff['outcome']}: "
                       f"{done.handoff[field_name]}")
    if reasons:
        return _result("untrimmed", reasons=reasons, **common)
    scratch_head = _commit(root, f"refs/heads/{scratch}")
    common["scratch_head"] = scratch_head
    verdict = check(root, facts.base, facts.head, scratch_head, judge_files=facts.judge_files)
    common.update(net_lines=verdict.net, files=verdict.files)
    if verdict.commits == 0 and not verdict.violations:
        return _result("nothing-to-trim", reasons=[], **common)
    if verdict.violations:
        return _result("untrimmed", reasons=[v.line() for v in verdict.violations], **common)
    again = attempt.rerun(ctx, deps, scratch)
    if not again.ok:
        return _result("untrimmed", reasons=[*again.failures, f"next: {again.next_command}"],
                       **common)
    if _commit(root, f"refs/heads/{facts.branch}") != facts.head:
        return _result("untrimmed", reasons=[
            f"the piece branch {facts.branch} moved while the trim ran, so the trim is not a "
            "fast-forward of it"], **common)
    _advance(root, facts.branch, facts.head, scratch_head)
    return _result("trimmed", reasons=[], **common)
