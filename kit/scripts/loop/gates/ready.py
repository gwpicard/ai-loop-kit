"""Move 2: shaping to ready. The ready gate.

The checks run in the order of the design: the machine lint first, then the two
fresh test lists, then the judge files committed and seen failing, then the
fingerprint. Every check that can fail on its own is reported, so one run names
every fault. The gate runs every judge and every session itself and trusts no
agent's word.

1. Pieces the core cannot hold yet are refused alone, with a `next:` line that
   names the later piece: a measurement judge or a spec marked "route open"
   (L7), and a reference judge (L8).
2. In a project with no test runner, only a quick-path scaffold piece passes,
   and its judge is that the test command runs. Any other piece is refused.
3. The lint and the needs list (`loop.needs`) hold nothing; every sensitive
   area carries its acceptance; every area the spec touches is in the area map
   or named under `New area:`; the blocked-by links point at real pieces and
   form no cycle; a quick-path piece keeps its limits; the held-out cases are in
   the gate-only store and the spec holds their fingerprint.
4. The judge files are the first commit on the piece branch, alone, and later
   commits leave them alone.
5. Two fresh sessions list the tests they would write. The lists must cover the
   same spec IDs. The sessions run only once everything above passes.
6. The judge runs on `main` with the judge files in place. It must fail on an
   assertion that names a spec ID. Each `Check:` line under Must stay the same
   must pass on `main`.
7. The gate writes `Fails today:` into the spec's Judge field, takes the
   fingerprint, and hands both to the move with the must-look reasons.

The must-look reasons are exactly five, and only this module writes them:
a sensitive area, a `Not reversible:` mark, a `New dependency:` mark, a
`Security:` mark (all under Changes to current behaviour), and a `must-look`
line the person writes in Decisions. Any one gives the piece individual review.

Tests drive `run` with stand-ins for the judge, the sessions and GitHub. `check`
runs it with the real ones.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from loop import (
    areas,
    fingerprint,
    github,
    heldout,
    judge,
    lint,
    needs,
    policy,
    research,
    sessions,
    spec,
    states,
    testlists,
)
from loop.cli import ExitCode
from loop.gates import CheckContext, CheckResult, passed, refused
from loop.paths import Paths

BASE = "main"

SENSITIVE = "a sensitive area"
IRREVERSIBLE = "an irreversible data change"
NEW_DEPENDENCY = "a new dependency"
SECURITY = "a security change"
PERSON = "the person's mark"
REASONS = (SENSITIVE, IRREVERSIBLE, NEW_DEPENDENCY, SECURITY, PERSON)

TEST_DIRS = frozenset(
    {"test", "tests", "__tests__", "spec", "specs", "e2e", "fixtures", "testdata", "cypress"}
)
TEST_NAME = re.compile(
    r"(^test_|_test\.|\.test\.|\.spec\.|_spec\.|^conftest\.py$|^tests?\.\w+$|^Test[A-Z]\w*\.)"
)
RUNNER_FILES = frozenset({"pytest.ini", "tox.ini", "conftest.py", "go.mod", "Cargo.toml"})
RUNNER_CONFIG = re.compile(r"^(vitest|jest)\.config\.\w+$")
PERSON_MARK = re.compile(r"^\s*must[\s-]*look\b", re.IGNORECASE)
HEX64 = re.compile(r"\b[0-9a-f]{64}\b")
SHAPE = "gate.py spec {n} --body-file <file>, then gate.py move {n} ready"


def branch_name(number: int) -> str:
    """The piece branch, as `gate.py branch` makes it."""
    return f"piece-{number}"


@dataclass(frozen=True)
class Deps:
    """What the gate calls out to. Tests pass stand-ins."""

    run_judge: Callable[..., dict[str, Any]]
    run_lists: Callable[[Paths, int, str, list[str]], dict[str, Any]]
    blockers: Callable[[CheckContext], list[str]]
    today: Callable[[], str]


class Refusals:
    """The faults found so far. One run reports all of them, with the first next step."""

    def __init__(self) -> None:
        self.texts: list[str] = []
        self.nexts: list[str] = []

    def add(self, text: str, next_command: str) -> None:
        self.texts.append(text)
        self.nexts.append(next_command)

    def __bool__(self) -> bool:
        return bool(self.texts)

    def result(self) -> CheckResult:
        return refused(self.texts, self.nexts[0])


# --- git ------------------------------------------------------------------------------


def _git(root: Path, *args: str) -> tuple[int, str]:
    done = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    return done.returncode, done.stdout.strip()


class GitError(Exception):
    """A git step the gate depends on failed, so the gate cannot tell and refuses."""

    def __init__(self, message: str, next_command: str = "") -> None:
        super().__init__(message)
        self.next_command = next_command or "check the project's git repository, then run the "\
            "ready move again"


def looks_like_test(path: str) -> bool:
    parts = path.split("/")
    if any(part.lower() in TEST_DIRS for part in parts[:-1]):
        return True
    return bool(TEST_NAME.search(parts[-1]))


def has_test_runner(root: Path, ref: str, test_command: str = "") -> bool:
    """True when the project at `ref` holds a test runner, a test file or a test command."""
    if test_command.strip():
        return True
    code, listing = _git(root, "ls-tree", "-r", "--name-only", ref)
    if code != 0:
        raise GitError(f"git could not list the files of {ref}, so the gate cannot tell whether "
                       "the project has a test runner")
    for path in listing.splitlines():
        name = path.rsplit("/", 1)[-1]
        if name in RUNNER_FILES or RUNNER_CONFIG.match(name) or looks_like_test(path):
            return True
    for name, needle in (("package.json", None), ("pyproject.toml", "pytest"),
                         ("setup.cfg", "pytest")):
        if name not in listing.splitlines():
            continue
        _, text = _git(root, "show", f"{ref}:{name}")
        if needle is None:
            try:
                script = str(json.loads(text).get("scripts", {}).get("test", ""))
            except (ValueError, AttributeError):
                continue
            if script and "no test specified" not in script:
                return True
        elif needle in text:
            return True
    return False


# --- small readers ------------------------------------------------------------------------


def _issue_type(record: Sequence[Mapping[str, Any]]) -> str:
    for entry in record:
        if entry.get("kind") == "capture":
            found = str(entry.get("type") or "")
            if found in states.TYPES:
                return found
    return "feature"


def _issue_number(record: Sequence[Mapping[str, Any]]) -> int | None:
    found: int | None = None
    for entry in record:
        if entry.get("kind") in ("capture", "synced") and entry.get("issue"):
            found = int(entry["issue"])
    return found


def _policy_limit(paths: Paths) -> tuple[int | None, str]:
    """The judge time limit and the test command of the project's policy, when it has one."""
    try:
        loaded = policy.load(paths.policy_file)
    except policy.PolicyError:
        return None, ""
    return int(loaded["test_timeout_seconds"]), str(loaded.get("test_command") or "")


def _is_scaffold(sp: Mapping[str, Any]) -> bool:
    return "scaffold" in str(sp["judge"]["kind"] or "").lower()


# --- the later pieces -----------------------------------------------------------------------


def _later(sp: Mapping[str, Any]) -> CheckResult | None:
    judge_part = sp["judge"]
    kind = str(judge_part["kind"] or "").lower()
    if sp["route_open"]:
        return refused(
            ['the spec marks the route open ("route open"), and the core does not hold the '
             "hypothesis list and the held-out twin yet (they arrive with L7)"],
            "wait for L7 (build-plan.md), or settle the route in /shape and remove the "
            "Route: open line",
        )
    if "metric" in kind or "measure" in kind:
        return refused(
            ["a measurement judge needs the hypothesis list and the held-out twin, which the "
             "core does not hold yet (they arrive with L7)"],
            "wait for L7 (build-plan.md), or give the piece a judge that is acceptance tests",
        )
    if "reference" in kind:
        return refused(
            ["a reference judge needs the blind comparison, which the core does not hold yet "
             "(it arrives with L8)"],
            "wait for L8 (build-plan.md), or give the piece a judge that is acceptance tests",
        )
    return None


# --- the checks ----------------------------------------------------------------------------


def _short(text: str, limit: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _sensitive(sp: Mapping[str, Any], out: Refusals, number: int) -> None:
    for item in sp["sensitive_areas"]:
        accepted = (
            re.search(r"\bAccepted:", item) and needs.QUOTE.search(item) and needs.DATE.search(item)
        )
        if not accepted:
            out.add(
                "a sensitive area has no recorded acceptance (the word Accepted:, the person's "
                f"words in quotes and a date): {_short(item)}",
                f"ask the person for their words and a date, then {SHAPE.format(n=number)}",
            )


def _areas(sp: Mapping[str, Any], paths: Paths, out: Refusals) -> None:
    try:
        rules = areas.load_or_empty(paths)
    except areas.AreaMapError as error:
        out.add(f"the area map cannot be read: {error}", error.next_command)
        return
    known = set(areas.names(rules))
    new = set(sp["changes"]["new_area"])
    touches = [t for t in sp["links"]["touches"] if t.lower() != "none"]
    missing = [t for t in touches if t not in known and t not in new]
    if missing:
        have = ", ".join(sorted(known)) or "none yet"
        out.add(
            f"the spec touches {', '.join(missing)}, which {areas.MAP_FILE} does not hold "
            f"(it holds: {have})",
            f"add a rule for each to {areas.MAP_FILE}, or name each under New area: in the "
            "spec's Changes to current behaviour",
        )


def _quick(sp: Mapping[str, Any], tests: Mapping[str, str] | None, out: Refusals) -> None:
    if sp["path"] != "quick":
        return
    step = "remove the Path: quick line and shape the full path, or cut the piece smaller"
    touches = [t for t in sp["links"]["touches"] if t.lower() != "none"]
    if len(touches) > 1:
        out.add(f"a quick-path piece names {len(touches)} areas, and the limit is one", step)
    if sp["sensitive_areas"]:
        out.add("a quick-path piece holds a sensitive area, and the limit is none", step)
    if sp["changes"]["new_dependency"]:
        out.add("a quick-path piece adds a new dependency, and the limit is none", step)
    if tests is not None and len(tests) != 1:
        out.add(
            f"the judge of a quick-path piece is {len(tests)} tests, and the limit is a single "
            "test",
            step,
        )


def _held_out(sp: Mapping[str, Any], paths: Paths, number: int, out: Refusals) -> None:
    store = f"python3 -m loop.heldout store --piece {number} --case ID=FILE"
    try:
        found = heldout.fingerprint(paths, number)
    except heldout.HeldOutError as error:
        out.add(f"the held-out cases are missing from the store: {error}", error.next_command)
        return
    line = sp["judge"]["held_out"] or ""
    written = HEX64.findall(line.lower())
    if not written:
        out.add(
            "the spec's Judge field has no Held-out cases: line with the fingerprint of the "
            "stored cases",
            f"write Held-out cases: fingerprint {found} in the Judge field, then "
            f"{SHAPE.format(n=number)}",
        )
    elif found not in written:
        out.add(
            "the fingerprint in the spec's Held-out cases line differs from the fingerprint of "
            "the stored cases",
            f"if the stored cases are right, write fingerprint {found} in the Judge field; "
            f"otherwise run {store} --replace",
        )


@dataclass
class JudgeFiles:
    first: str
    files: list[str]
    tests: dict[str, str]


def _judge_files(
    root: Path, number: int, command: str, out: Refusals
) -> JudgeFiles | None:
    branch = branch_name(number)
    code, _ = _git(root, "rev-parse", "--verify", "-q", f"refs/heads/{branch}")
    if code != 0:
        out.add(f"the piece branch {branch} does not exist", f"gate.py branch {number}")
        return None
    _, listing = _git(root, "rev-list", "--reverse", "--first-parent", f"{BASE}..{branch}")
    commits = listing.split()
    if not commits:
        out.add(
            f"{branch} has no commit beyond {BASE}; the judge files must be its first commit",
            f"commit the judge files to {branch} as its first commit, then "
            f"gate.py move {number} ready",
        )
        return None
    first = commits[0]
    _, parent = _git(root, "rev-parse", f"{first}^")
    _, today = _git(root, "rev-parse", BASE)
    if parent != today:
        out.add(
            f"the piece branch was cut from an older {BASE} ({parent[:7]}, and {BASE} is at "
            f"{today[:7]}), so the judge would not be tried on today's {BASE}",
            f"git rebase {BASE} {branch} (the judge files stay the first commit), then "
            f"gate.py move {number} ready",
        )
        return None
    _, names = _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", first)
    files = names.splitlines()
    try:
        words = shlex.split(command)
    except ValueError:
        words = []
    other = [f for f in files if not looks_like_test(f) and f not in words]
    if other:
        out.add(
            f"the first commit on {branch} holds files that are not judge files: "
            f"{', '.join(other)}; the judge files must be the first commit, alone",
            f"move the judge files to a first commit on {branch} cut from {BASE}, with nothing "
            "else in it",
        )
        return None
    later: list[str] = []
    for path in files:
        _, hashes = _git(root, "log", "--format=%h", f"{first}..{branch}", "--", path)
        if hashes:
            later.append(f"{path} (in {', '.join(hashes.split())})")
    if later:
        out.add(
            "a judge file changed after the first commit: " + "; ".join(later),
            f"restore the judge files as the first commit holds them, then "
            f"gate.py move {number} ready",
        )
    tests: dict[str, str] = {}
    for path in files:
        if not looks_like_test(path):
            continue
        _, text = _git(root, "show", f"{first}:{path}")
        for name, body in lint.read_tests(text).items():
            tests[f"{path}::{name}"] = body
    return JudgeFiles(first=first, files=files, tests=tests)


def _judge_fault(result: Mapping[str, Any], ids: Sequence[str]) -> str | None:
    """What is wrong with a judge run on main, or None when it failed on an assertion."""
    outcome = result["outcome"]
    if outcome == "passed":
        return ("the judge passes on main with the judge files in place, so the behaviour "
                "already exists or the tests prove nothing")
    if outcome == "failed":
        if result.get("runner") not in judge.REPORT_RUNNERS or not result.get("failing_ids"):
            return (
                f"the judge failed, but the {result.get('runner') or 'unknown'} runner writes no "
                "report that names a spec ID, so a failure on an assertion is not proven"
            )
        unknown = [i for i in result["failing_ids"] if i not in ids]
        if unknown:
            return "the judge fails on " + ", ".join(unknown) + ", and the spec holds no such ID"
        return None
    if outcome == "failed_no_id":
        return ("the judge failed on an assertion that names no spec ID (FL- or EC-), so it is "
                "not the right failure")
    if outcome == "timeout":
        return "the judge ran past its time limit and was stopped"
    why = result.get("kind") or result.get("note") or "no reason was given"
    return f"the judge errored instead of failing on its assertion ({why})"


def _must_look(sp: Mapping[str, Any]) -> list[str]:
    found: list[str] = []
    changes = sp["changes"]
    if sp["sensitive_areas"]:
        found.append(SENSITIVE)
    if changes["not_reversible"]:
        found.append(IRREVERSIBLE)
    if changes["new_dependency"]:
        found.append(NEW_DEPENDENCY)
    if changes["security"]:
        found.append(SECURITY)
    if any(PERSON_MARK.match(item) for item in sp["decisions"]):
        found.append(PERSON)
    return found


# --- the blocked-by links ---------------------------------------------------------------------

Fetch = Callable[[int], "dict[str, Any] | None"]


def dependency_problems(start: int, fetch: Fetch) -> list[str]:
    """What is wrong with the blocked-by links of issue `start`, followed all the way down.

    `fetch(n)` gives `{"labels": [...], "blocked_by": [numbers]}` for issue `n`,
    or None when no such issue exists.
    """
    problems: list[str] = []
    cache: dict[int, dict[str, Any] | None] = {}
    done: set[int] = set()

    def get(number: int) -> dict[str, Any] | None:
        if number not in cache:
            cache[number] = fetch(number)
        return cache[number]

    def note(text: str) -> None:
        if text not in problems:
            problems.append(text)

    def visit(number: int, trail: list[int]) -> None:
        info = get(number)
        if info is None:
            return
        for blocker in info["blocked_by"]:
            if blocker in trail:
                loop = [*trail[trail.index(blocker) :], blocker]
                note("blocked-by cycle: " + " -> ".join(str(n) for n in loop))
                continue
            found = get(blocker)
            if found is None:
                note(f"issue {blocker} does not exist (issue {number} is blocked by it)")
                continue
            labels = list(found["labels"])
            if not states.state_labels(labels):
                note(f"issue {blocker} is not a piece (issue {number} is blocked by it)")
            elif states.label("dropped") in labels:
                note(f"piece {blocker} is dropped, so it never finishes (issue {number} is "
                     "blocked by it)")
            if blocker not in done:
                visit(blocker, [*trail, blocker])
        done.add(number)

    if get(start) is None:
        note(f"issue {start} does not exist")
        return problems
    visit(start, [start])
    return problems


def _github_blockers(ctx: CheckContext, hub: Any = None) -> list[str]:
    """The blocked-by problems, read as the App.

    A piece with no issue yet has no link to read. A piece with an issue and no App is
    refused: the gate never passes a check it did not run.
    """
    if hub is None:
        hub = github.GitHub(ctx.paths)
    issue = _issue_number(ctx.record)
    if issue is None:
        return []
    if not hub.available:
        raise github.GitHubError(
            "the blocked-by links cannot be read without the gate's App, so the piece waits",
            next_command=f"{github.SETUP_NEXT}. The person's command: "
            + github.sync_command(ctx.paths.root),
            code=ExitCode.REFUSED,
        )

    def fetch(number: int) -> dict[str, Any] | None:
        try:
            info = hub.read_issue(number)
        except github.GitHubError as error:
            if error.not_found:
                return None
            if error.code == ExitCode.REFUSED:  # a pull request
                return {"labels": [], "blocked_by": []}
            raise
        try:
            linked = hub.api_json(
                f"repos/{{owner}}/{{repo}}/issues/{number}/dependencies/blocked_by"
            )
        except github.GitHubError as error:
            if error.not_found:
                raise github.GitHubError(
                    f"GitHub has no blocked-by answer for issue {number}",
                    next_command=github.SETUP_NEXT,
                    code=ExitCode.REFUSED,
                ) from error
            raise
        numbers = [int(item["number"]) for item in linked if isinstance(item, dict)]
        return {"labels": info["labels"], "blocked_by": numbers}

    return dependency_problems(issue, fetch)


def default_deps(paths: Paths) -> Deps:
    limit, _ = _policy_limit(paths)

    def run_judge(command: str, root: Path, ref: str) -> dict[str, Any]:
        return judge.run(command, root, ref, time_limit=limit)

    def run_lists(paths: Paths, number: int, block: str, ids: list[str]) -> dict[str, Any]:
        return testlists.run_two(paths, number=number, block=block, ids=ids)

    return Deps(
        run_judge=run_judge,
        run_lists=run_lists,
        blockers=_github_blockers,
        today=lambda: date.today().isoformat(),
    )


# --- the gate ---------------------------------------------------------------------------------


def run(ctx: CheckContext, deps: Deps) -> CheckResult:
    """The checks of move 2, with the given stand-ins."""
    sp = ctx.spec
    if sp is None or not sp["found"]:
        return refused(
            ["the spec block cannot be read, or the piece has none, so the gate cannot check it"],
            f"write the spec as kit/spec-format.md says, then {SHAPE.format(n=ctx.number)}",
        )
    later = _later(sp)
    if later is not None:
        return later
    paths, root, number = ctx.paths, ctx.paths.root, ctx.number
    _, test_command = _policy_limit(paths)
    scaffold = False
    try:
        runner = has_test_runner(root, BASE, test_command)
    except GitError as error:
        return refused([str(error)], error.next_command)
    if not runner:
        if not _is_scaffold(sp):
            return refused(
                ["the project has no test runner, so only a quick-path scaffold piece may become "
                 "ready"],
                "shape the scaffold piece first: Path: quick, a Judge whose Kind is scaffold "
                "and whose Command is the test command, and the test runner as its change",
            )
        if sp["path"] != "quick":
            return refused(
                ["a scaffold piece takes the quick path, and this spec does not say Path: quick"],
                f"add the line Path: quick to the spec block, then {SHAPE.format(n=number)}",
            )
        scaffold = True
    out = Refusals()
    notes: list[str] = []
    ids: list[str] = list(sp["ids"])
    command = str(sp["judge"]["command"] or "")

    # 1. The machine lint, and what the spec alone can tell.
    files: JudgeFiles | None = None
    if not scaffold:
        files = _judge_files(root, number, command, out)
    try:
        problems = deps.blockers(ctx)
    except github.GitHubError as error:
        out.add(f"the blocked-by links cannot be read: {error.message}", error.next_command)
        problems = []
    found = needs.needs_from_body(
        ctx.body,
        issue_type=_issue_type(ctx.record),
        tests=files.tests if files is not None else None,
        unresolved_dependencies=problems,
    )
    skipped = ("judge_not_failing", "test_lists_differ", "sensitive_area")
    for item in found:
        if item["kind"] not in skipped:
            out.add(item["text"], SHAPE.format(n=number))
    if not scaffold and not sp["must_stay_checks"]:
        out.add(
            "the spec's Must stay the same holds no Check: line, so nothing proves it",
            "add a Check: <command> line under Must stay the same, then "
            + SHAPE.format(n=number),
        )
    _sensitive(sp, out, number)
    _areas(sp, paths, out)
    _quick(sp, files.tests if files is not None else None, out)
    if not scaffold:
        _held_out(sp, paths, number, out)
    if out:
        return out.result()

    # 2. The two fresh test lists.
    entries: list[dict[str, Any]] = []
    if scaffold:
        notes.append("a scaffold piece in a project with no test runner skips the test lists")
    else:
        try:
            made = deps.run_lists(paths, number, spec.parse(ctx.body).block, ids)
        except (testlists.ListError, sessions.SessionError) as error:
            return refused(
                [f"the two test lists could not be made: {error}"], error.next_command
            )
        lists = [list(item) for item in made["lists"]]
        entries.append(
            {"kind": "test-lists", "lists": lists, "labels": list(made.get("labels", []))}
        )
        differ = testlists.compare(lists[0], lists[1])
        if differ:
            text = "the two fresh test lists differ by spec ID: " + ", ".join(differ)
            if len(differ) >= 2 and len(differ) * 2 >= len(ids):
                text += ". So many differ that the piece should be split into smaller pieces"
            return refused(
                [text],
                "settle each ID in the spec so a reader writes the same tests, or split the "
                f"piece, then {SHAPE.format(n=number)}",
            )

    # 3. The judge files, seen failing on main.
    results: list[dict[str, Any]] = []
    if scaffold:
        judge_commit = _git(root, "rev-parse", BASE)[1]
        fails = (f"no test runner on {BASE}; the judge is that the test command runs; "
                 f"{BASE} at {judge_commit[:7]}; {deps.today()} (written by the gate)")
    else:
        assert files is not None
        try:
            main_run = deps.run_judge(command, root, files.first)
        except judge.JudgeError as error:
            return refused([f"the judge could not be run: {error}"], error.next_command)
        results.append(main_run)
        fault = _judge_fault(main_run, ids)
        if fault:
            return refused(
                [fault],
                f"fix the judge files in the first commit on {branch_name(number)} so that "
                f"they fail on an assertion naming the spec ID, then gate.py move {number} ready",
            )
        judge_commit = files.first
        main_at = _git(root, "rev-parse", BASE)[1][:7]
        failing = list(main_run["failing_ids"])
        quiet = [i for i in ids if i not in failing and i in sp["judge"]["proves"]]
        if quiet:
            notes.append("these IDs already pass on main: " + ", ".join(quiet))
        fails = (f"{len(main_run['failures'])} test(s) fail on their assertion, naming "
                 f"{', '.join(failing)}; {BASE} at {main_at}; {deps.today()} "
                 "(written by the gate)")
        for check in sp["must_stay_checks"]:
            try:
                verdict = deps.run_judge(check, root, BASE)
            except judge.JudgeError as error:
                return refused([f"the check {check} could not be run: {error}"],
                               error.next_command)
            results.append(verdict)
            if verdict["outcome"] != "passed":
                return refused(
                    [f"the must-stay-the-same check `{check}` does not pass on {BASE} "
                     f"({verdict['outcome']})"],
                    "the check is already red on main; fix main or remove the Check: line "
                    f"from Must stay the same, then gate.py move {number} ready",
                )

    # 4. The line and the fingerprint the gate writes.
    try:
        body = spec.set_judge_line(ctx.body, "Fails today", fails)
        taken = fingerprint.take(body, judge_commit)
    except (spec.SpecError, fingerprint.FingerprintError) as error:
        return refused([str(error)], getattr(error, "next_command", SHAPE.format(n=number)))
    entries += [judge.evidence_entry(item, fingerprint=taken["fingerprint"]) for item in results]
    try:
        relied = research.relied_on(sp["links"]["relies_on"], root, BASE)
    except OSError as error:
        return refused([str(error)],
                       "check the project's git repository, then " + SHAPE.format(n=number))
    entries.append(
        {"kind": "relied-on", "files": relied, "main": _git(root, "rev-parse", BASE)[1]}
    )
    return passed(
        body=body,
        fingerprint=taken,
        must_look=_must_look(sp),
        entries=entries,
        notes=notes,
    )


def check(ctx: CheckContext) -> CheckResult:
    return run(ctx, default_deps(ctx.paths))
