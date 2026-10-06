"""Move 4: ready to building. The claim gate.

The run re-checks the piece before a builder starts. Every check that can fail
on its own is reported, so one run names every fault. The cheap checks come
first. The judge runs on today's `main` only when all of them pass.

A fault of the spec or of the code under it sends the piece back to shaping, by
move 3, with the fault written as the reason (decision 9, until L9 brings the
fuller research refresh). The gate does that itself: a refusal that carries
`send_back` in its data makes `loop.moves` make move 3. A fault of the moment
leaves the piece ready: a blocker, a piece already building, an area in use, no
free slot, and a must-stay-the-same check that is red on `main`.

Sends back:
1. The fingerprint differs from the one ready took: the spec was edited by hand,
   or a judge file changed after the first commit.
2. The spec fails the lint, the needs list, the area map or the quick-path
   limits on today's `main`.
3. A research finding fails the quick check (`loop.research`).
4. A file the spec relies on changed on `main` since ready.
5. The judge no longer fails on an assertion that names a spec ID on `main`.

Leaves ready:
6. A must-stay-the-same check fails on `main`.
7. A blocker is not done and not built earlier in this run. The run passes the
   issue numbers of the pieces built earlier as `--option built_earlier=7,8`.
   With none, only done counts.
8. The piece is already building.
9. A running piece holds one of its areas.
10. No builder slot is free (`builder_cap` in the policy file, 3 by default).

On a pass, the gate keeps the fingerprint in the piece record, as ready does,
and adds a `claim-check` entry. Attempt judging (P16) reads that fingerprint.

The blocked-by links are read as the App. With an issue and no App, the claim is
refused: the gate never passes a check that did not run.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from loop import fingerprint, github, judge, lint, moves, needs, policy, research, spec, states
from loop.cli import ExitCode
from loop.gates import CheckContext, CheckResult, passed
from loop.gates import ready as ready_gate
from loop.paths import Paths

BASE = ready_gate.BASE
SHAPE = ready_gate.SHAPE
# Needs the claim leaves out. The judge and the lists were settled at ready, the
# acceptance of a sensitive area is read by `_sensitive`, and the research
# findings have their own quick check.
SKIPPED_NEEDS = ("judge_not_failing", "test_lists_differ", "sensitive_area", "research_gap")


@dataclass(frozen=True)
class Deps:
    """What the gate calls out to. Tests pass stand-ins."""

    run_judge: Callable[..., dict[str, Any]]
    blockers: Callable[[CheckContext], dict[int, str]]
    today: Callable[[], str]
    version_of: Callable[[Path, str, str], str | None]


class Faults:
    """The faults found so far. `back` marks the ones that send the piece back to shaping."""

    def __init__(self) -> None:
        self.texts: list[str] = []
        self.nexts: list[str] = []
        self.back: list[str] = []

    def add(self, text: str, next_command: str, *, back: bool) -> None:
        self.texts.append(text)
        self.nexts.append(next_command)
        if back:
            self.back.append(text)

    def adopt(self, found: ready_gate.Refusals, *, back: bool) -> None:
        for text, next_command in zip(found.texts, found.nexts, strict=True):
            self.add(text, next_command, back=back)

    def __bool__(self) -> bool:
        return bool(self.texts)

    def result(self) -> CheckResult:
        data: dict[str, Any] = {}
        if self.back:
            data["send_back"] = "The claim check found: " + "; ".join(self.back)
        return CheckResult(
            ok=False, failures=tuple(self.texts), next_command=self.nexts[0], data=data
        )


# --- the policy -------------------------------------------------------------------------


def _policy(paths: Paths) -> dict[str, Any]:
    """The policy file with its defaults. A missing file means the defaults."""
    if not paths.policy_file.exists():
        return policy.with_defaults({})
    return policy.load(paths.policy_file)


# --- the blocked-by links ---------------------------------------------------------------------


def github_blockers(ctx: CheckContext, hub: Any = None) -> dict[int, str]:
    """Each blocker of the piece's issue and its state (`done`, `building`, ...; "" for none).

    A piece with no issue yet has no link to read. A piece with an issue and no App is
    refused: the gate never passes a check that did not run.
    """
    if hub is None:
        hub = github.GitHub(ctx.paths)
    issue = ready_gate._issue_number(ctx.record)
    if issue is None:
        return {}
    if not hub.available:
        raise github.GitHubError(
            "the blocked-by links cannot be read without the gate's App, so the piece waits",
            next_command=f"{github.SETUP_NEXT}. The person's command: "
            + github.sync_command(ctx.paths.root),
            code=ExitCode.REFUSED,
        )
    try:
        linked = hub.api_json(f"repos/{{owner}}/{{repo}}/issues/{issue}/dependencies/blocked_by")
    except github.GitHubError as error:
        if error.not_found:
            raise github.GitHubError(
                f"GitHub has no blocked-by answer for issue {issue}",
                next_command=github.SETUP_NEXT,
                code=ExitCode.REFUSED,
            ) from error
        raise
    found: dict[int, str] = {}
    for item in linked:
        if not isinstance(item, dict):
            continue
        number = int(item["number"])
        try:
            labels = hub.read_issue(number)["labels"]
        except github.GitHubError as error:
            # No such issue, or a pull request: neither is a piece that is done.
            if error.not_found or error.code == ExitCode.REFUSED:
                found[number] = ""
                continue
            raise
        names = [states.state_of_label(name) for name in labels]
        found[number] = next((name for name in names if name), "")
    return found


def _built_earlier(options: Any, faults: Faults, number: int) -> set[int]:
    raw = str(options.get("built_earlier", "")).replace(",", " ").split()
    if not all(word.isdigit() for word in raw):
        faults.add(
            f"the option built_earlier must list issue numbers, such as 7,8; it holds "
            f"{options.get('built_earlier')!r}",
            f"gate.py move {number} building --option built_earlier=7,8",
            back=False,
        )
        return set()
    return {int(word) for word in raw}


# --- git ------------------------------------------------------------------------------------


def _git(root: Path, *args: str) -> tuple[int, str]:
    return ready_gate._git(root, *args)


def _overlay(root: Path, base: str, commit: str, files: Sequence[str]) -> str:
    """A commit that holds `base` with the judge files of `commit` laid over it.

    It is the tree the judge would see if the judge files were the first commit on today's
    `main`. No ref points at it and no working folder is touched.
    """
    folder = tempfile.mkdtemp(prefix="claim-")
    index = os.path.join(folder, "index")
    env = {**os.environ, "GIT_INDEX_FILE": index, "GIT_AUTHOR_NAME": "loop",
           "GIT_AUTHOR_EMAIL": "loop@example.invalid", "GIT_COMMITTER_NAME": "loop",
           "GIT_COMMITTER_EMAIL": "loop@example.invalid"}

    def run(*args: str) -> str:
        done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                              check=False, env=env)
        if done.returncode != 0:
            raise ready_gate.GitError(
                f"git {args[0]} failed while the claim built the tree for the judge "
                f"({done.stderr.strip()[:120]}), so the gate cannot run the judge on {base}"
            )
        return done.stdout.strip()

    try:
        run("read-tree", base)
        for path in files:
            entry = run("ls-tree", commit, "--", path)
            mode, _kind, rest = entry.split(None, 2)
            run("update-index", "--add", "--cacheinfo", f"{mode},{rest.split()[0]},{path}")
        tree = run("write-tree")
        return run("commit-tree", tree, "-p", base, "-m", "the judge files on today's main")
    finally:
        if os.path.exists(index):
            os.remove(index)
        os.rmdir(folder)


# --- the checks -------------------------------------------------------------------------------


def _recorded_fingerprint(record: Sequence[Any]) -> dict[str, Any] | None:
    found: dict[str, Any] | None = None
    for entry in record:
        if entry.get("kind") == "fingerprint":
            found = dict(entry["fingerprint"])
    return found


def _judge_changed(
    root: Path, number: int, recorded: dict[str, Any], faults: Faults
) -> list[str] | None:
    """Check that the judge files are as ready found them. Returns the files, or None."""
    branch = ready_gate.branch_name(number)
    commit = str(recorded.get("judge_commit", ""))
    code, _ = _git(root, "rev-parse", "--verify", "-q", f"refs/heads/{branch}")
    if code != 0:
        faults.add(
            f"the piece branch {branch} does not exist, so the judge files cannot be checked",
            f"gate.py branch {number}, restore the judge files as the first commit, then "
            + SHAPE.format(n=number),
            back=True,
        )
        return None
    _, listing = _git(root, "rev-list", "--reverse", "--first-parent", f"{BASE}..{branch}")
    first = listing.split()[0] if listing.split() else ""
    if first != commit:
        faults.add(
            f"the first commit on {branch} is now {first[:7] or 'missing'}, and ready took "
            f"the judge files from {commit[:7]}, so a judge file changed after ready",
            f"restore the judge files as the first commit on {branch}, or shape the piece "
            "again: " + SHAPE.format(n=number),
            back=True,
        )
        return None
    _, names = _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", commit)
    files = names.splitlines()
    later = []
    for path in files:
        _, hashes = _git(root, "log", "--format=%h", f"{commit}..{branch}", "--", path)
        if hashes:
            later.append(f"{path} (in {', '.join(hashes.split())})")
    if later:
        faults.add(
            "a judge file changed after ready: " + "; ".join(later),
            "restore the judge files as the first commit holds them, or shape the piece "
            "again: " + SHAPE.format(n=number),
            back=True,
        )
    return files


def _judge_tests(root: Path, commit: str, files: Sequence[str]) -> dict[str, str]:
    tests: dict[str, str] = {}
    for path in files:
        if not ready_gate.looks_like_test(path):
            continue
        _, text = _git(root, "show", f"{commit}:{path}")
        for name, body in lint.read_tests(text).items():
            tests[f"{path}::{name}"] = body
    return tests


def _lint_on_main(
    ctx: CheckContext, sp: Mapping[str, Any], tests: dict[str, str] | None, scaffold: bool,
    faults: Faults,
) -> None:
    number = ctx.number
    found = needs.needs_from_body(
        ctx.body,
        issue_type=ready_gate._issue_type(ctx.record),
        tests=tests,
        unresolved_dependencies=[],
    )
    for item in found:
        if item["kind"] not in SKIPPED_NEEDS:
            faults.add(f"the spec fails the lint on today's {BASE}: {item['text']}",
                       SHAPE.format(n=number), back=True)
    if not scaffold and not sp["must_stay_checks"]:
        faults.add("the spec's Must stay the same holds no Check: line, so nothing proves it",
                   SHAPE.format(n=number), back=True)
    held = ready_gate.Refusals()
    ready_gate._sensitive(sp, held, number)
    ready_gate._areas(sp, ctx.paths, held)
    ready_gate._quick(sp, tests, held)
    faults.adopt(held, back=True)


def _research(
    ctx: CheckContext, sp: Mapping[str, Any], deps: Deps, age_days: int, faults: Faults
) -> int:
    root = ctx.paths.root
    findings = [spec.parse_finding(item) for item in sp["research"]]
    problems = research.check(
        findings,
        today=deps.today(),
        age_days=age_days,
        file_fingerprint=lambda path: research.file_fingerprint(root, BASE, path),
        version_of=lambda name: deps.version_of(root, BASE, name),
    )
    for text in problems:
        faults.add(
            f"a research finding does not hold: {text}",
            "re-research that finding in /shape, write the new answer in the spec, then "
            + SHAPE.format(n=ctx.number),
            back=True,
        )
    return len(findings)


def _relied_on(ctx: CheckContext, faults: Faults) -> int:
    root = ctx.paths.root
    recorded: dict[str, Any] | None = None
    for entry in ctx.record:
        if entry.get("kind") == "relied-on":
            recorded = dict(entry.get("files", {}))
    if recorded is None:
        faults.add(
            "the piece record holds no relied-on entry (the ready gate writes one), so the "
            "relied-on files cannot be checked",
            "take the piece through the ready gate again: " + SHAPE.format(n=ctx.number),
            back=True,
        )
        return 0
    for path, old in recorded.items():
        now = research.file_fingerprint(root, BASE, path)
        if now is None:
            faults.add(f"the relied-on file {path} is no longer on {BASE}",
                       SHAPE.format(n=ctx.number), back=True)
        elif now != old:
            faults.add(f"the relied-on file {path} changed on {BASE} since ready",
                       SHAPE.format(n=ctx.number), back=True)
    return len(recorded)


def _others(ctx: CheckContext, sp: Mapping[str, Any], limit: int, faults: Faults) -> None:
    """Already building, an area in use, and a free slot, read from the piece records."""
    paths = ctx.paths
    number = ctx.number
    own = "shaping"
    for entry in ctx.record:
        if entry.get("kind") == "move":
            own = str(entry.get("to"))
    issue = ready_gate._issue_number(ctx.record)
    if own == "building":
        faults.add(f"piece {number} is already building, so a second claim is refused",
                   f"gate.py report {number}", back=False)
    folder = paths.pieces_dir
    numbers = sorted(int(p.name) for p in folder.iterdir()
                     if p.is_dir() and p.name.isdigit()) if folder.is_dir() else []
    mine = {t for t in sp["links"]["touches"] if t.lower() != "none"}
    building = 0
    for other in numbers:
        if other == number:
            continue
        try:
            piece = moves.read_piece(paths, other)
        except moves.MoveError as error:
            faults.add(f"the record of piece {other} cannot be read: {error}",
                       error.next_command, back=False)
            continue
        if piece is None or piece.state != "building":
            continue
        building += 1
        if issue is not None and piece.issue == issue:
            faults.add(f"issue {issue} is already building as piece {other}",
                       f"gate.py report {other}", back=False)
        try:
            theirs = {t for t in spec.parse(piece.body).links["touches"] if t.lower() != "none"}
        except spec.SpecError:
            faults.add(f"the areas of the running piece {other} cannot be read, so the gate "
                       "cannot tell whether they clash", f"gate.py report {other}", back=False)
            continue
        shared = sorted(mine & theirs)
        if shared:
            faults.add(
                f"the area {', '.join(shared)} is in use by piece {other}, which is building",
                f"wait until piece {other} leaves building, then gate.py move {number} building",
                back=False,
            )
    if own != "building" and building >= limit:
        faults.add(
            f"no builder slot is free: {building} pieces are building and the limit is {limit} "
            "(builder_cap in the policy file)",
            f"wait for a slot, then gate.py move {number} building. The piece stays ready",
            back=False,
        )


def _blockers(ctx: CheckContext, deps: Deps, faults: Faults) -> None:
    try:
        linked = deps.blockers(ctx)
    except github.GitHubError as error:
        faults.add(f"the blocked-by links cannot be read: {error.message}", error.next_command,
                   back=False)
        return
    earlier = _built_earlier(ctx.options, faults, ctx.number)
    for issue, state in sorted(linked.items()):
        if state != "done" and issue not in earlier:
            faults.add(
                f"issue {issue} blocks this piece, and it is {state or 'not a piece'}, not done "
                "and not built earlier in this run",
                f"wait for issue {issue} to be done, or have the run claim it first and pass "
                f"--option built_earlier={issue}",
                back=False,
            )


def _on_main(
    ctx: CheckContext, sp: Mapping[str, Any], deps: Deps, recorded: dict[str, Any],
    files: list[str] | None, limit_note: list[str], faults: Faults,
) -> str:
    """Run the judge and the must-stay-the-same checks on today's `main`. Returns the ref."""
    root, number = ctx.paths.root, ctx.number
    ref = BASE
    if files is not None:
        commit = str(recorded["judge_commit"])
        try:
            if _git(root, "rev-parse", f"{commit}^")[1] == _git(root, "rev-parse", BASE)[1]:
                ref = commit
            else:
                ref = _overlay(root, BASE, commit, files)
        except ready_gate.GitError as error:
            faults.add(str(error), error.next_command, back=False)
            return ref
        try:
            verdict = deps.run_judge(str(sp["judge"]["command"] or ""), root, ref)
        except judge.JudgeError as error:
            faults.add(f"the judge could not be run: {error}", error.next_command, back=False)
            return ref
        fault = ready_gate._judge_fault(verdict, list(sp["ids"]))
        if fault:
            faults.add(
                f"on today's {BASE}, {fault}",
                f"shape the piece again: {SHAPE.format(n=number)}", back=True,
            )
    else:
        limit_note.append("a scaffold piece has no judge files, so only its checks ran on main")
    for check in sp["must_stay_checks"]:
        try:
            outcome = deps.run_judge(check, root, BASE)
        except judge.JudgeError as error:
            faults.add(f"the check {check} could not be run: {error}", error.next_command,
                       back=False)
            continue
        if outcome["outcome"] != "passed":
            faults.add(
                f"the must-stay-the-same check `{check}` fails on today's {BASE} "
                f"({outcome['outcome']})",
                "the check is already red on main; fix main or the Check: line, then "
                f"gate.py move {number} building",
                back=False,
            )
    return ref


# --- the gate ---------------------------------------------------------------------------------


def _back(failure: str, ctx: CheckContext, next_command: str = "") -> CheckResult:
    faults = Faults()
    faults.add(failure, next_command or SHAPE.format(n=ctx.number), back=True)
    return faults.result()


def run(ctx: CheckContext, deps: Deps) -> CheckResult:
    """The checks of move 4, with the given stand-ins."""
    root = ctx.paths.root
    sp = ctx.spec
    if sp is None or not sp["found"]:
        return _back("the spec block cannot be read, or the piece has none, so the claim cannot "
                     "confirm that nothing changed since ready", ctx)
    try:
        loaded = _policy(ctx.paths)
    except policy.PolicyError as error:
        return CheckResult(
            ok=False,
            failures=(f"the policy file cannot be read, so the claim cannot size the slots or "
                      f"the age limit: {error}",),
            next_command=f"fix {ctx.paths.policy_file}, then gate.py move {ctx.number} building",
        )
    recorded = _recorded_fingerprint(ctx.record)
    if recorded is None:
        return _back("the piece record holds no fingerprint, so the claim cannot confirm that "
                     "nothing changed since ready", ctx)
    faults = Faults()
    scaffold = ready_gate._is_scaffold(sp)

    # 1. The fingerprint, and the judge files.
    try:
        now = fingerprint.take(ctx.body, str(recorded.get("judge_commit", "")))
    except (spec.SpecError, fingerprint.FingerprintError) as error:
        return _back(f"the spec cannot be read: {error}", ctx,
                     getattr(error, "next_command", ""))
    if now["fingerprint"] != recorded.get("fingerprint"):
        faults.add(
            f"the spec's fingerprint changed since ready (it was "
            f"{str(recorded['fingerprint'])[:12]}, it is now {now['fingerprint'][:12]}), so "
            "someone edited the spec and the gate did not make the change",
            SHAPE.format(n=ctx.number),
            back=True,
        )
    files: list[str] | None = None
    if not scaffold:
        files = _judge_changed(root, ctx.number, recorded, faults)
    tests = (_judge_tests(root, str(recorded["judge_commit"]), files)
             if files is not None else None)

    # 2. What the spec and the code under it say on today's main.
    _lint_on_main(ctx, sp, tests, scaffold, faults)
    count = _research(ctx, sp, deps, int(loaded["research_age_days"]), faults)
    relied = _relied_on(ctx, faults)

    # 3. The other pieces and the blockers.
    _others(ctx, sp, int(loaded["builder_cap"]), faults)
    _blockers(ctx, deps, faults)
    if faults:
        return faults.result()

    # 4. The judge and the must-stay-the-same checks, on today's main.
    notes: list[str] = []
    ref = _on_main(ctx, sp, deps, recorded, files, notes, faults)
    if faults:
        return faults.result()
    main_at = _git(root, "rev-parse", BASE)[1]
    return passed(
        fingerprint=now,
        entries=[{"kind": "claim-check", "at": deps.today(), "main": main_at, "judge_ref": ref,
                  "findings": count, "relied_on": relied}],
        notes=notes,
    )


def default_deps(paths: Paths) -> Deps:
    try:
        limit: int | None = int(_policy(paths)["test_timeout_seconds"])
    except policy.PolicyError:
        limit = None

    def run_judge(command: str, root: Path, ref: str) -> dict[str, Any]:
        return judge.run(command, root, ref, time_limit=limit)

    return Deps(
        run_judge=run_judge,
        blockers=github_blockers,
        today=lambda: date.today().isoformat(),
        version_of=research.manifest_version,
    )


def check(ctx: CheckContext) -> CheckResult:
    return run(ctx, default_deps(ctx.paths))
