"""Move 5: building to review. The gate judges the attempt.

The gate judges, never the builder. It reads the piece branch at its head, in
the design's order:

1. The fingerprint. The spec and the judge commit must be what the claim kept.
2. The frozen bar, byte for byte (`loop.bar`). A change is a failed attempt, logged
   as possible gaming. The checks after it would judge a changed bar, so none runs.
3. The visible judge, then the hidden held-out cases. A held-out result much worse
   than the visible one is logged as possible gaming.
4. The new-test lint (`loop.newtest_lint`).
5. The must-stay-the-same checks.
6. The diff stays inside the declared touches. The area map is read from the base
   commit of the piece with `git show`, never from the builder's tree.
7. A new dependency is planned in the spec and passes `dependency-check.py`.

Every fault of steps 3 to 7 is reported together. Metric targets, the hypothesis
list and mutation testing wait for later pieces (L5 and L7).

Two outcomes are not the same, and the gate keeps them apart:

- A failed attempt is the builder's. The gate writes an `attempt` entry in the piece
  record (`loop.attempt_log`) and refuses the move. The piece stays building, with the
  findings in the log for the next builder. At the limit (`attempt_limit` in the policy
  file, 3 by default) the refusal carries `send_back`, and `loop.moves` sends the piece
  back to shaping by move 6 with every attempt's findings.
- A refusal is the gate's own. A git error, a missing record, an unreadable file, a
  held-out store that is empty or changed, or a judge that could not run is refused
  with a `next:` line. No attempt is counted, and no check ever passes unless it ran.

A pass writes the attempt entry and the judge run, and the piece moves to review.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from loop import (
    areas,
    attempt_log,
    bar,
    fingerprint,
    heldout,
    judge,
    newtest_lint,
    policy,
    spec,
)
from loop.cli import ExitCode
from loop.gates import CheckContext, CheckResult, claim, passed, refused
from loop.gates import ready as ready_gate
from loop.paths import Paths

BASE = ready_gate.BASE
HELD_OUT_GAP = 0.5  # this share of hidden cases failing, with the visible judge green, is gaming
LOCKFILES = ("package-lock.json", "pnpm-lock.yaml", "uv.lock")
# Files that can add a dependency and that the dependency check cannot read.
UNREAD_MANIFEST = re.compile(
    r"^(requirements.*\.txt|yarn\.lock|poetry\.lock|Pipfile\.lock|Cargo\.lock|go\.sum)$")
HELD_PATH = re.compile(r"held-out-path:\s*(\S+)")
REASON_TEXT = 160  # characters of one finding in the reason for a move to shaping


@dataclass(frozen=True)
class Deps:
    """What the gate calls out to. Tests pass stand-ins."""

    run_judge: Callable[..., dict[str, Any]]
    dependency_check: Callable[[Sequence[str], Mapping[str, str]], tuple[int, str]]
    today: Callable[[], str]


class Refusal(Exception):
    """The gate's own fault: it could not tell, so it refuses and no attempt is counted."""

    def __init__(self, text: str, next_command: str) -> None:
        super().__init__(text)
        self.next_command = next_command


@dataclass
class Findings:
    items: list[dict[str, Any]] = field(default_factory=list)

    def add(self, check: str, text: str, *, gaming: bool = False) -> None:
        self.items.append(attempt_log.finding(check, text, gaming=gaming))

    def __bool__(self) -> bool:
        return bool(self.items)


# --- the policy and the record --------------------------------------------------------------


def _policy(paths: Paths) -> dict[str, Any]:
    if not paths.policy_file.exists():
        return policy.with_defaults({})
    return policy.load(paths.policy_file)


@dataclass(frozen=True)
class Facts:
    """What the gate reads before it judges, all from git and the piece record."""

    number: int
    branch: str
    head: str
    base: str
    judge_commit: str
    judge_files: list[str]
    scaffold: bool
    again: str
    since: str = ""  # where the attempt's own changes start: the base, or a stacking merge

    @property
    def start(self) -> str:
        """The commit the diff checks measure from. A stacked piece starts after its stack."""
        return self.since or self.base


# --- git --------------------------------------------------------------------------------------


def _git(root: Path, again: str, *args: str) -> str:
    code, text = ready_gate._git(root, *args)
    if code != 0:
        raise Refusal(
            f"git {args[0]} failed while the gate judged the attempt, so the gate cannot tell",
            f"check the project's git repository, then {again}",
        )
    return text


def _show(root: Path, again: str, ref: str, path: str) -> str:
    """The text of a file at a commit, exactly as stored (`_git` strips the ends of its text)."""
    done = subprocess.run(["git", "-C", str(root), "show", f"{ref}:{path}"], capture_output=True,
                          check=False)
    if done.returncode != 0:
        raise Refusal(
            f"git show failed for {path} at {ref[:7]} while the gate judged the attempt, so the "
            "gate cannot tell",
            f"check the project's git repository, then {again}",
        )
    return done.stdout.decode("utf-8", "replace")


def _facts(ctx: CheckContext, sp: Mapping[str, Any], recorded: Mapping[str, Any],
           head_ref: str | None = None) -> Facts:
    """What the gate reads. `head_ref` names another branch to judge in place of the piece's."""
    root, number = ctx.paths.root, ctx.number
    again = f"gate.py move {number} review"
    branch = head_ref or ready_gate.branch_name(number)
    code, _ = ready_gate._git(root, "rev-parse", "--verify", "-q", f"refs/heads/{branch}")
    if code != 0:
        raise Refusal(
            f"the piece branch {branch} does not exist, so there is no attempt to judge",
            f"gate.py branch {number}, build on it, then {again}",
        )
    head = _git(root, again, "rev-parse", f"refs/heads/{branch}")
    judge_commit = str(recorded.get("judge_commit", ""))
    scaffold = ready_gate._is_scaffold(sp)
    if not judge_commit:
        raise Refusal(
            "the fingerprint in the piece record names no judge commit, so the bar cannot be read",
            f"gate.py report {number}",
        )
    if scaffold:
        base, files = judge_commit, []
    else:
        base = _git(root, again, "rev-parse", f"{judge_commit}^")
        names = _git(root, again, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root",
                     judge_commit)
        files = names.splitlines()
    since = _stack_base(ctx, root, again, base, head, judge_commit)
    return Facts(number=number, branch=branch, head=head, base=base, judge_commit=judge_commit,
                 judge_files=files, scaffold=scaffold, again=again, since=since)


STACK_SUBJECT = "Stack on piece "


def _stack_base(ctx: CheckContext, root: Path, again: str, base: str, head: str,
                judge_commit: str) -> str:
    """The stacking merge a dependent was built on, from the option `stack_base`, or "".

    The run stacks a dependent on its dependency's branch with one merge commit whose subject
    starts `Stack on piece`. The diff checks measure from that merge, so the dependency's own
    changes are not charged to the dependent. The option is checked against the branch: it must
    be a merge commit on the first-parent line of the piece branch. Anything else is a
    refusal, so a wrong value can never widen what the piece may change. The merge must also be
    the first thing on the branch after the judge commit: every first-parent commit before it is
    the judge commit or an earlier stacking merge, so no change of the piece's own hides before
    it. Its second parent must be the tip of the branch of a dependency the run recorded, from
    the option `stacked_on` (piece numbers, comma separated).
    """
    wanted = str(ctx.options.get("stack_base", "")).strip()
    if not wanted:
        return ""
    code, found = ready_gate._git(root, "rev-parse", "--verify", "-q", f"{wanted}^{{commit}}")
    line = _git(root, again, "rev-list", "--first-parent", "--parents",
                f"{base}..{head}") if code == 0 else ""
    on_branch = {row.split()[0]: row.split()[1:] for row in line.splitlines() if row.strip()}
    if code != 0 or found not in on_branch or len(on_branch[found]) < 2:
        raise Refusal(
            f"the stack base {wanted[:12]} is not a stacking merge on the piece branch, so the "
            "gate cannot tell which changes are the dependency's",
            f"the run stacks a dependent again, then gate.py move {ctx.number} review",
        )
    subject = _git(root, again, "log", "-1", "--format=%s", found)
    if not subject.startswith(STACK_SUBJECT):
        raise Refusal(
            f"the commit {found[:7]} is a merge, but not a stacking merge (its subject does "
            f"not start with {STACK_SUBJECT.strip()!r}), so the gate will not measure from it",
            f"the run stacks a dependent again, then gate.py move {ctx.number} review",
        )
    _stack_is_clean(ctx, root, again, base, found, judge_commit)
    return found


def _stack_is_clean(ctx: CheckContext, root: Path, again: str, base: str, merge: str,
                    judge_commit: str) -> None:
    """Refuse a stacking merge that follows a commit of the piece's own, or merges anything but
    the tip of a recorded dependency's branch."""
    wanted = [w.strip() for w in str(ctx.options.get("stacked_on", "")).split(",") if w.strip()]
    tips: dict[str, str] = {}
    for number in wanted:
        code, tip = ready_gate._git(root, "rev-parse", "--verify", "-q",
                                    f"refs/heads/piece-{number}^{{commit}}")
        if code == 0:
            tips[number] = tip
    second = _git(root, again, "rev-parse", f"{merge}^2")
    moved = [n for n in wanted if tips.get(n) != second] or wanted
    # Stacking again changes nothing for a dependency the piece already holds, so the piece
    # goes back to ready (move 7). The dependent is then built again on a fresh branch.
    fix = (f"gate.py move {ctx.number} ready --reason \"the dependency "
           f"{' and '.join('piece-' + n for n in moved) or 'piece'} moved after this piece was "
           "stacked on it\"")
    earlier = _git(root, again, "rev-list", "--first-parent", "--parents", f"{base}..{merge}^1")
    for row in earlier.splitlines():
        sha, *parents = row.split()
        if sha == judge_commit:
            continue
        subject = _git(root, again, "log", "-1", "--format=%s", sha)
        if len(parents) >= 2 and subject.startswith(STACK_SUBJECT):
            continue
        raise Refusal(
            f"the commit {sha[:7]} comes before the stacking merge on the piece branch and is "
            "neither the judge commit nor a stacking merge, so the gate will not measure from "
            "the merge: it could hide that commit's changes",
            fix)
    if second not in set(tips.values()):
        raise Refusal(
            f"the stacking merge {merge[:7]} does not merge the tip of the branch of a "
            "dependency the run recorded for this piece, so the gate will not measure from it",
            fix)


def _uncommitted(root: Path, facts: Facts) -> str | None:
    """A note when the worktree of the piece branch holds a tracked change nobody committed.

    It is a note and not a refusal. The judge runs in a temporary checkout of the commit, so
    the change plays no part, and a refusal would let a builder dodge the count of attempts.
    """
    listing = _git(root, facts.again, "worktree", "list", "--porcelain")
    folder: str | None = None
    for block in listing.split("\n\n"):
        lines = block.splitlines()
        if f"branch refs/heads/{facts.branch}" in lines:
            folder = next((ln[9:] for ln in lines if ln.startswith("worktree ")), None)
    if folder is None:
        return None
    code, text = ready_gate._git(Path(folder), "status", "--porcelain", "--untracked-files=no")
    if code != 0:
        raise Refusal(
            f"git status failed in the worktree {folder}, so the gate cannot tell whether the "
            "attempt is committed",
            f"check the worktree, then {facts.again}",
        )
    if not text:
        return None
    return (
        f"the worktree {folder} held changes nobody committed ({text.splitlines()[0].strip()}"
        f"{', and more' if len(text.splitlines()) > 1 else ''}); the gate judged the commit "
        f"{facts.head[:7]} and ignored them"
    )


# --- the checks ------------------------------------------------------------------------------


def _fingerprint(ctx: CheckContext, facts: Facts, recorded: Mapping[str, Any],
                 found: Findings) -> None:
    try:
        now = fingerprint.take(ctx.body, facts.judge_commit)
    except (spec.SpecError, fingerprint.FingerprintError) as error:
        raise Refusal(
            f"the spec cannot be read, so the fingerprint cannot be checked: {error}",
            getattr(error, "next_command", "") or f"gate.py report {ctx.number}",
        ) from error
    if now["fingerprint"] != recorded.get("fingerprint"):
        found.add(
            "fingerprint",
            f"the fingerprint changed since the claim (it was {str(recorded['fingerprint'])[:12]}"
            f", it is now {now['fingerprint'][:12]}), so the spec is not the one the claim kept",
        )


def _bar(ctx: CheckContext, facts: Facts, found: Findings) -> None:
    root = ctx.paths.root
    if not facts.scaffold:
        listing = _git(root, facts.again, "rev-list", "--reverse", "--first-parent",
                       f"{facts.base}..{facts.head}")
        first = listing.split()[0] if listing.split() else ""
        if first != facts.judge_commit:
            found.add(
                "frozen-bar",
                f"the first commit on {facts.branch} is {first[:7] or 'missing'}, and the judge "
                f"files were frozen in {facts.judge_commit[:7]}, so the judge commit was changed",
                gaming=True,
            )
    try:
        listed = bar.changes(
            root, facts.start, facts.head,
            judge_commit=None if facts.scaffold else facts.judge_commit,
            judge_files=facts.judge_files,
        )
    except bar.BarError as error:
        raise Refusal(str(error), error.next_command) from error
    for change in listed:
        found.add("frozen-bar", change.text(), gaming=True)


def _visible(ctx: CheckContext, sp: Mapping[str, Any], facts: Facts, deps: Deps,
             found: Findings, runs: list[dict[str, Any]]) -> bool:
    command = str(sp["judge"]["command"] or "")
    if not command.strip():
        raise Refusal("the spec's Judge field holds no Command:, so the judge cannot run",
                      f"write the Command: line in /shape, then gate.py move {ctx.number} shaping")
    try:
        verdict = deps.run_judge(command, ctx.paths.root, facts.head)
    except judge.JudgeError as error:
        raise Refusal(f"the judge could not be run: {error}", error.next_command) from error
    runs.append(verdict)
    if verdict["outcome"] == "passed":
        return True
    ids = ", ".join(verdict.get("failing_ids") or [])
    runner = verdict.get("runner") or "an unknown runner"
    named = (f" naming {ids}" if ids else
             f" ({runner} writes no report that names a spec ID, so the failure is not proven)")
    why = {"failed": "failed on an assertion" + named,
           "failed_no_id": "failed on an assertion that names no spec ID",
           "timeout": "ran past its time limit and was stopped"}.get(
        str(verdict["outcome"]),
        f"errored instead of passing ({verdict.get('kind') or verdict.get('note') or 'no reason'})",
    )
    found.add("visible-judge", f"the visible judge {why}")
    return False


def _held_command(command: str, judge_files: Sequence[str], held_path: str, number: int) -> str:
    try:
        words = shlex.split(command)
    except ValueError as error:
        raise Refusal(f"the judge command could not be read ({error})",
                      f"fix the Command: line in /shape, then gate.py move {number} shaping") \
            from error
    kept: list[str] = []
    swapped = False
    for word in words:
        if word in judge_files:
            if not swapped:
                kept.append(held_path)
                swapped = True
            continue
        kept.append(word)
    if not swapped:
        raise Refusal(
            "the Judge's Command: names no judge file, so the gate cannot run a held-out case "
            "in its place",
            "name the judge files in the Command: line in /shape, for example "
            f"`pytest tests/test_x.py`, then gate.py move {number} shaping",
        )
    return shlex.join(kept)


def _held_cases(ctx: CheckContext, sp: Mapping[str, Any]) -> dict[str, tuple[str, str]]:
    """Each stored case as (path, text). The store is read here and nowhere else."""
    number = ctx.number
    store = f"python3 -m loop.heldout store --piece {number} --case ID=FILE"
    try:
        cases = heldout.read(ctx.paths, number)
        stored = heldout.fingerprint(ctx.paths, number) if cases else ""
    except (heldout.HeldOutError, OSError, UnicodeDecodeError) as error:
        raise Refusal(f"the held-out cases cannot be read: {error}", store) from error
    if not cases:
        raise Refusal(
            f"piece {number} has no held-out cases in the gate's store, so the gate cannot run "
            "them and will not pass the attempt without them",
            store,
        )
    written = ready_gate.HEX64.findall(str(sp["judge"]["held_out"] or "").lower())
    if stored not in written:
        raise Refusal(
            "the stored held-out cases differ from the fingerprint in the spec's Held-out cases "
            "line, so they were changed after ready",
            f"if the stored cases are right, take the piece through shaping again: "
            f"gate.py move {number} shaping --reason \"the held-out cases changed\"",
        )
    parsed: dict[str, tuple[str, str]] = {}
    bad: list[str] = []
    for name, text in cases.items():
        found = next((m.group(1) for line in text.splitlines()[:5]
                      if (m := HELD_PATH.search(line))), None)
        pure = PurePosixPath(found) if found else None
        if pure is None or pure.is_absolute() or ".." in pure.parts:
            bad.append(name)
            continue
        parsed[name] = (str(pure), text)
    if bad:
        raise Refusal(
            "a held-out case holds no usable `held-out-path: <relative path>` line in its first "
            f"five lines: {', '.join(sorted(bad))}",
            f"store the case again with the line: {store} --replace, then update the spec's "
            "Held-out cases fingerprint",
        )
    return parsed


def _held_out(ctx: CheckContext, sp: Mapping[str, Any], facts: Facts, deps: Deps,
              found: Findings) -> None:
    cases = _held_cases(ctx, sp)
    command = str(sp["judge"]["command"] or "")
    failed = 0
    for path, text in cases.values():
        try:
            # The case is written into the judge's temporary checkout, never into git.
            verdict = deps.run_judge(
                _held_command(command, facts.judge_files, path, ctx.number),
                ctx.paths.root, facts.head, extra_files={path: text},
            )
        except judge.JudgeError as error:
            raise Refusal(f"a held-out case could not be run: {error}",
                          error.next_command) from error
        if verdict["outcome"] != "passed":
            failed += 1
    if failed:
        gap = failed / len(cases) >= HELD_OUT_GAP
        found.add(
            "held-out",
            f"{failed} of {len(cases)} hidden cases failed while the visible judge passed"
            + (", a gap so wide that the attempt is logged as possible gaming: the code may be "
               "written for the visible tests" if gap else ""),
            gaming=gap,
        )


def _lint(ctx: CheckContext, facts: Facts, found: Findings) -> list[str]:
    """The new-test lint over the lines the attempt added. Returns the report-only notes."""
    root = ctx.paths.root
    frozen = set(facts.judge_files)
    flags = ("--unified=0", "--no-color", "--no-ext-diff", "--no-renames")
    diff = _git(root, facts.again, "diff", *flags, facts.start, facts.head, "--")
    status = _git(root, facts.again, "diff", "--name-status", "--no-renames", facts.start,
                  facts.head, "--")
    changes = [(line.split("\t")[0], line.split("\t")[-1])
               for line in status.splitlines() if "\t" in line]
    wanted = {path: change for path, change in newtest_lint.parse_diff(diff).items()
              if path not in frozen}
    items = newtest_lint.lint_changes([(s, p) for s, p in changes if p not in frozen])
    own = newtest_lint.detect_own_modules(root)
    for path, change in sorted(wanted.items()):
        if newtest_lint.language_of(path) is None:
            continue
        text = _show(root, facts.again, facts.head, path)
        items.extend(newtest_lint.lint_text(path, text, added=change.added,
                                            touched=change.touched, own_modules=own))
    for item in newtest_lint.refusals(items):
        found.add("new-test-lint",
                  f"{item['rule']} in {item['file']}:{item['line']}: {item['message']}")
    return [f"{item['rule']} in {item['file']}:{item['line']}: {item['message']}"
            for item in newtest_lint.reports(items)]


def _must_stay(ctx: CheckContext, sp: Mapping[str, Any], facts: Facts, deps: Deps,
               found: Findings, runs: list[dict[str, Any]]) -> None:
    for check in sp["must_stay_checks"]:
        try:
            verdict = deps.run_judge(check, ctx.paths.root, facts.head)
        except judge.JudgeError as error:
            raise Refusal(f"the check {check} could not be run: {error}",
                          error.next_command) from error
        runs.append(verdict)
        if verdict["outcome"] != "passed":
            found.add("must-stay-the-same",
                      f"the must-stay-the-same check `{check}` is red ({verdict['outcome']})")


def _area_rules(root: Path, again: str, ref: str) -> list[areas.Rule]:
    """The area map as `ref` holds it, read with `git show`. No map means no rules."""
    if not _git(root, again, "ls-tree", ref, "--", areas.MAP_FILE):
        return []
    try:
        return areas.parse(_git(root, again, "show", f"{ref}:{areas.MAP_FILE}"))
    except areas.AreaMapError as error:
        raise Refusal(f"the area map at {ref[:7]} cannot be read: {error}",
                      error.next_command) from error


def _touches(ctx: CheckContext, sp: Mapping[str, Any], facts: Facts, found: Findings) -> None:
    root = ctx.paths.root
    allowed = {t for t in sp["links"]["touches"] if t.lower() != "none"}
    new_areas = set(sp["changes"]["new_area"])
    frozen = set(facts.judge_files)
    base_rules = _area_rules(root, facts.again, facts.start)
    head_rules: list[areas.Rule] | None = None
    names = _git(root, facts.again, "diff", "--no-renames", "--name-only", "-z", facts.start,
                 facts.head, "--")
    outside: list[str] = []
    for path in sorted(p for p in names.split("\0") if p and p not in frozen):
        area = areas.which(base_rules, path)
        if area == areas.EXEMPT or area in allowed:
            continue
        if new_areas:
            if path == areas.MAP_FILE:
                continue
            if area == areas.UNCLAIMED:
                if head_rules is None:
                    head_rules = _area_rules(root, facts.again, facts.head)
                if areas.area_of(head_rules, path) in allowed & new_areas:
                    continue
        outside.append(f"{path} ({area})")
    if outside:
        shown = ", ".join(outside[:8]) + (f" and {len(outside) - 8} more" if len(outside) > 8
                                          else "")
        have = ", ".join(sorted(allowed)) or "none"
        found.add("touches", f"the diff leaves the declared touches ({have}): {shown}")


def _dependencies(ctx: CheckContext, sp: Mapping[str, Any], facts: Facts, deps: Deps,
                  found: Findings) -> list[str]:
    """The dependency check. Returns a note for each changed file it cannot read."""
    root = ctx.paths.root
    status = _git(root, facts.again, "diff", "--name-status", "--no-renames", "-z", facts.start,
                  facts.head, "--").split("\0")
    changed = [status[i + 1] for i in range(0, len(status) - 1, 2)
               if status[i][:1] in ("A", "M") and Path(status[i + 1]).name in LOCKFILES]
    unread = [status[i + 1] for i in range(0, len(status) - 1, 2)
              if status[i][:1] in ("A", "M") and UNREAD_MANIFEST.match(Path(status[i + 1]).name)]
    notes = [f"the dependency check does not read {path}, so a package added there was not "
             "checked" for path in unread]
    planned = bool(sp["changes"]["new_dependency"])
    script = ctx.paths.kit_dir / "scripts" / "dependency-check.py"
    env = {**os.environ, "PYTHONPATH": str(ctx.paths.kit_dir / "scripts")}
    for path in changed:
        folder = tempfile.mkdtemp(prefix="attempt-deps-")
        after = Path(folder) / "after" / Path(path).name
        before = Path(folder) / "before" / Path(path).name
        try:
            after.parent.mkdir()
            before.parent.mkdir()
            after.write_text(_show(root, facts.again, facts.head, path), encoding="utf-8")
            old = (_show(root, facts.again, facts.start, path)
                   if _git(root, facts.again, "ls-tree", facts.start, "--", path) else "")
            before.write_text(old, encoding="utf-8")
            argv = [sys.executable, str(script), "--lockfile", str(after), "--before",
                    str(before), "--json"]
            for option in ("registry", "now"):
                if ctx.options.get(option):
                    argv += [f"--{option}", str(ctx.options[option])]
            # The lockfile against itself first: no new package, so no registry call. Exit 4
            # here, or 1 or 3, means the builder's own lockfile cannot be read: a failed attempt.
            alone = [*argv[:5], str(after), *argv[6:]]
            self_code, _self_out = deps.dependency_check(alone, env)
            code, out = self_code, ""
            if self_code == 0:
                code, out = deps.dependency_check(argv, env)
            elif self_code not in (1, 3, int(ExitCode.ENVIRONMENT)):
                raise Refusal(
                    f"dependency-check.py gave exit {self_code} for {path} read against itself, "
                    "so the new packages are not proven safe",
                    f"run dependency-check.py --lockfile {path} --base-ref {BASE} --help, fix "
                    f"what it names, then gate.py move {ctx.number} review",
                )
        finally:
            for item in (after, before):
                if item.exists():
                    item.unlink()
            for item in (after.parent, before.parent):
                if item.is_dir():
                    item.rmdir()
            os.rmdir(folder)
        if self_code != 0:
            found.add("dependency", f"{path} cannot be read by the dependency check, so the "
                      "lockfile is broken and its packages are not proven safe")
            continue
        _read_dependency_answer(ctx, path, code, out, planned, found)
    return notes


def _read_dependency_answer(ctx: CheckContext, path: str, code: int, out: str, planned: bool,
                            found: Findings) -> None:
    try:
        body = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
    except ValueError:
        body = {}
    again = f"gate.py move {ctx.number} review"
    if code == 0 and isinstance(body, dict) and "added" in body:
        added = [f"{p['name']} {p['version']}" for p in body["added"]]
        if added and not planned:
            found.add(
                "dependency",
                f"{path} gained {', '.join(added[:6])}, and the spec holds no `New dependency:` "
                "mark, so the dependency was not planned",
            )
        return
    if code == int(ExitCode.REFUSED):
        text = str(body.get("error", "a new package was refused")) if isinstance(body, dict) \
            else "a new package was refused"
        found.add("dependency", f"{path}: {text}")
        return
    raise Refusal(
        f"dependency-check.py gave exit {code} for {path} and no answer the gate can read, so "
        "the new packages are not proven safe",
        f"run dependency-check.py --lockfile {path} --base-ref {BASE} --help, fix what it names, "
        f"then {again}",
    )


# --- the result ------------------------------------------------------------------------------


def _reason(record: Sequence[Mapping[str, Any]], current: Mapping[str, Any], limit: int) -> str:
    """The reason for move 6: every failed attempt, with its findings."""
    parts: list[str] = []
    for item in [*attempt_log.failed(record), current]:
        said = "; ".join(
            f"{f['check']}: {str(f['text'])[:REASON_TEXT]}" for f in item["findings"]
        )
        parts.append(f"attempt {item['n']} at {str(item['head'])[:7]} ({said})")
    return (f"The attempts ran out: {current['n']} of {limit} failed, so the piece goes back to "
            "shaping with every attempt's findings. " + " | ".join(parts))


def _failed(
    ctx: CheckContext, facts: Facts, found: Findings, limit: int, today: str,
    notes: Sequence[str] = (),
) -> CheckResult:
    number = attempt_log.used(ctx.record) + 1
    item = attempt_log.entry(number=number, result="failed", head=facts.head, base=facts.base,
                             at=today, findings=found.items)
    lines = [f"attempt {number} of {limit} failed"
             + (" and is logged as possible gaming" if item["possible_gaming"] else "")]
    lines += [f"{f['check']}: {f['text']}" for f in found.items]
    lines += [f"note: {note}" for note in notes]
    data: dict[str, Any] = {"attempt": item}
    if number >= limit:
        data["send_back"] = _reason(ctx.record, item, limit)
        nxt = (f"no attempt is left: the gate sends the piece back to shaping by move 6. "
               f"Settle the findings in /shape, then gate.py move {ctx.number} ready")
    else:
        nxt = (f"start attempt {number + 1} of {limit}: the builder's brief carries the attempt "
               f"log, then gate.py move {ctx.number} review")
    return CheckResult(ok=False, failures=tuple(lines), next_command=nxt, data=data)


def run(ctx: CheckContext, deps: Deps, head_ref: str | None = None) -> CheckResult:
    """The checks of move 5, with the given stand-ins.

    `head_ref` is for `rerun`: a branch to judge in place of the piece branch.
    """
    sp = ctx.spec
    number = ctx.number
    root = ctx.paths.root
    if sp is None or not sp["found"]:
        return refused(
            ["the spec block cannot be read, or the piece has none, so the gate cannot judge "
             "the attempt against it"],
            f"gate.py report {number}",
        )
    try:
        loaded = _policy(ctx.paths)
    except policy.PolicyError as error:
        return refused(
            [f"the policy file cannot be read, so the gate cannot tell how many attempts are "
             f"left: {error}"],
            f"fix {ctx.paths.policy_file}, then gate.py move {number} review",
        )
    recorded = claim._recorded_fingerprint(ctx.record)
    if recorded is None or not any(e.get("kind") == "claim-check" for e in ctx.record):
        return refused(
            ["the piece record holds no fingerprint or no claim check, so the gate cannot tell "
             "that the piece was claimed with the bar it is judged against"],
            f"gate.py report {number}; the piece goes through move 4 first",
        )
    found = Findings()
    runs: list[dict[str, Any]] = []
    notes: list[str] = []
    try:
        facts = _facts(ctx, sp, recorded, head_ref)
        unsaved = _uncommitted(root, facts)
        if unsaved:
            notes.append(unsaved)
        _fingerprint(ctx, facts, recorded, found)
        if not found:
            _bar(ctx, facts, found)
        if not found:
            if _visible(ctx, sp, facts, deps, found, runs) and not facts.scaffold:
                _held_out(ctx, sp, facts, deps, found)
            notes += _lint(ctx, facts, found)
            _must_stay(ctx, sp, facts, deps, found, runs)
            _touches(ctx, sp, facts, found)
            notes += _dependencies(ctx, sp, facts, deps, found)
    except Refusal as error:
        if not found:
            return refused([str(error)], error.next_command)
        notes.append(f"the gate also refused: {error}")
    if found:
        return _failed(ctx, facts, found, int(loaded["attempt_limit"]), deps.today(), notes)
    item = attempt_log.entry(number=attempt_log.used(ctx.record) + 1, result="passed",
                             head=facts.head, base=facts.base, at=deps.today())
    entries = [item, *(judge.evidence_entry(r, fingerprint=str(recorded["fingerprint"]))
                       for r in runs)]
    return passed(entries=entries, notes=notes)


def rerun(ctx: CheckContext, deps: Deps, head_ref: str) -> CheckResult:
    """The checks of move 5 on the head of another branch, with no attempt counted.

    The trim pass (P19) calls this straight after a trim, on the scratch branch. It is the
    same judging as `run`, but the result holds no attempt entry, no judge-run entry and no
    `send_back`, so nothing is logged and no piece moves. A failure or a refusal is the trim's
    to lose: the scratch branch is left, and the piece goes on untrimmed.
    """
    result = run(ctx, deps, head_ref)
    if result.ok:
        return passed(notes=list(result.data.get("notes", [])))
    if "attempt" not in result.data:
        return result
    failures = tuple(result.failures[1:])  # the first line counts an attempt that is not one
    return CheckResult(
        ok=False,
        failures=failures,
        next_command=(f"the trim is thrown away: the scratch branch {head_ref} is left, and "
                      "the piece goes on untrimmed"),
        data={},
    )


# --- the real stand-ins --------------------------------------------------------------------


def _run_dependency_check(argv: Sequence[str], env: Mapping[str, str]) -> tuple[int, str]:
    try:
        done = subprocess.run(list(argv), capture_output=True, text=True, check=False,
                              env=dict(env))
    except OSError as error:
        raise Refusal(f"dependency-check.py could not be started ({error.strerror})",
                      "install python3, then run the move again") from error
    return done.returncode, done.stdout


def default_deps(paths: Paths) -> Deps:
    try:
        limit: int | None = int(_policy(paths)["test_timeout_seconds"])
    except policy.PolicyError:
        limit = None

    def run_judge(command: str, root: Path, ref: str, **more: Any) -> dict[str, Any]:
        return judge.run(command, root, ref, time_limit=limit, **more)

    return Deps(run_judge=run_judge, dependency_check=_run_dependency_check,
                today=lambda: date.today().isoformat())


def check(ctx: CheckContext) -> CheckResult:
    return run(ctx, default_deps(ctx.paths))
