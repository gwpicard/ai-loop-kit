#!/usr/bin/env python3
# contract: agent
# contract: changes-state
"""The review loop: a fresh reviewer reads the specs and the combined diff, piece by piece.

The engine (`loop.run.engine`) calls `run_hook` for the events of a run. This module answers
`built-all` and `run-end`. It runs after the integration loop (`loop.run.integrate`), which
makes the docs commit and runs the final combined check at `built-all`. Review begins only
when that check is green on the exact head of the combined branch. A final check that is red,
refused or older than the branch head means no review, and no review is never a clean one.

One round, for each combined branch (the run's, and the own branch of a piece that needs
individual review):

1. The fingerprint of each joined piece is taken again, as the claim does. A spec that changed
   after the gate froze it goes to shaping by move 9, and the round waits for the rebuilt branch.
2. A scratch copy of the combined head is made, and a fresh `claude -p` session starts in it
   (`loop.sessions`). It gets two data blocks: the specs and the diff of each piece's join. It
   gets no attempt log, no hand-off and no builder's account. Its command line carries no
   credential and its settings let it write one file, its findings file.
3. The findings file is checked against the schema. Each finding has a `kind`
   (`failing-check`, `wrong-spec` or `worth-knowing`), a `gap` (`missing`, `partial`,
   `contradicts` or `unrequested`), a `piece` and `evidence`. A failing check also brings the
   test (`check`: path, text and command) and a written `justification`.
4. Every finding becomes one of three things:
   - a failing check: the test is run once on the combined head and must fail. The loop, never
     the builder, commits it to the piece branch. The piece leaves the combined branch (a rebuild
     from main under a fresh name, by `Integrator.leave`) and goes back to building by move 8,
     with the test, its commit, its command and the justification as options. The gate writes a
     `review-test` entry, which joins the frozen bar (`loop.bar`, `loop.gates.rebuild`);
   - a wrong spec: the piece leaves the same way and goes to shaping by move 9;
   - a note worth knowing: it goes to the run record, for the pull request.
5. The policy key `review_rounds` (2 by default) caps the rounds. A finding left in the last
   round sends only that piece to shaping by move 9. The reason becomes an open question with
   the person only, so the gate sets `needs-you`. The combined branch is rebuilt without the
   piece, and the other pieces go ahead.

A failing-check finding whose test does not fail on the combined head is not proved. It becomes
a worth-knowing note and moves nothing. A test that could not run is a refusal. One piece gets
one new test in a round: when a piece has more than one failing check, the first valid test
joins the bar and the rest travel in the reason, for the builder and the next round.

What this module never does is let a check pass that did not run. A reviewer session that
fails, a findings file that is missing, unreadable or invalid, a spend cap that is used up, a
git error, a worktree that holds unsaved work or a final check that is not green is a refusal
(`ReviewRefusal`) and never a clean review. The refusal is recorded, and the engine writes it
to the run record as a problem. It never uses a revert, a reset or a force push, and it never
writes a label or a piece record: every state move goes through the gate.

The run record keeps `review.tracks[key]` (`rounds`, `status`, `reviewed`, `removed`) and
`review.verdicts[piece]` (`verdict`, `round`, `findings`, `notes`). The pull request reads the
verdicts, and opens only for a track whose status is `clean`. Worth-knowing items also go to
`integration.worth_knowing`, with `source` set to `review`.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import shlex
import sys
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

if __package__ in (None, ""):  # run by path: put the kit's scripts folder on the path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from loop import bar, cli, fingerprint, github, judge, sessions, spec
from loop.cli import ExitCode
from loop.paths import Paths
from loop.run import integrate
from loop.run import record as run_record
from loop.run.gateway import Gateway, Reply

KINDS = ("failing-check", "wrong-spec", "worth-knowing")
GAPS = ("missing", "partial", "contradicts", "unrequested")
FINDINGS_ENV = "AI_LOOP_KIT_FINDINGS_FILE"
DEFAULT_ROUNDS = 2
REASON_LIMIT = 900
# The one outcome that proves a finding: a failed assertion that names a spec ID, read from a
# runner whose report the gate reads (`judge.REPORT_RUNNERS`). Nothing else freezes a test.
FAILING = ("failed",)
FINDING_KEYS = {"kind", "gap", "piece", "evidence", "check", "justification"}
CHECK_KEYS = {"path", "text", "command"}
MAIN_TRACK = integrate.MAIN_TRACK

SessionStarter = Callable[[sessions.Session], sessions.Result]
Mover = Callable[[int, str, str, Mapping[str, str]], Reply]
JudgeRun = Callable[..., dict[str, Any]]


class ReviewRefusal(Exception):
    """The review could not tell, so it refuses and never passes. The message names the way on."""

    def __init__(self, message: str, next_command: str) -> None:
        super().__init__(message)
        self.next_command = next_command


# --- the findings schema --------------------------------------------------------------------


@dataclass(frozen=True)
class Check:
    path: str
    text: str
    command: str


@dataclass(frozen=True)
class Finding:
    kind: str
    gap: str
    piece: int
    evidence: str
    check: Check | None = None
    justification: str = ""


def _again(file_hint: str = "the findings file") -> str:
    return (f"fix {file_hint} to follow kit/briefs/reviewer.md, or run the review again: "
            "run.py --run <name>")


def _bad(message: str) -> ReviewRefusal:
    return ReviewRefusal(message, _again())


def _text(value: Any, what: str, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _bad(f"{where}: {what} must be text and not blank")
    return value.strip()


def _parse_check(raw: Any, where: str) -> Check:
    if not isinstance(raw, dict):
        raise _bad(f"{where}: check must be an object with path, text and command")
    extra = sorted(set(raw) - CHECK_KEYS)
    if extra:
        raise _bad(f"{where}: check holds {', '.join(extra)}, which it may not")
    path = _text(raw.get("path"), "check path", where)
    text = raw.get("text")
    command = _text(raw.get("command"), "check command", where)
    if not isinstance(text, str) or not text.strip():
        raise _bad(f"{where}: check text must be text and not blank")
    pure = PurePosixPath(path)
    if (pure.is_absolute() or ".." in pure.parts or any(c in path for c in "*?[]{}\\")
            or not bar.is_test(path) or bar.is_guarded(path) or bar.is_settings(path)
            or bar.is_snapshot(path)):
        raise _bad(f"{where}: the check path {path!r} is not one new test file inside the "
                   "project, in a place where tests live, so it cannot join the bar")
    try:
        words = shlex.split(command)
    except ValueError:
        words = []
    if path not in words:
        raise _bad(f"{where}: the check command does not name the test file {path} as a word, "
                   "so it would not run the test")
    return Check(path, text if text.endswith("\n") else text + "\n", command)


def parse_findings(text: str, pieces: Collection[int]) -> list[Finding]:
    """The findings in `text`, each checked. Anything that is not valid is a refusal.

    `pieces` are the pieces joined to the combined branch. A finding about another piece is
    not valid. An empty list is a valid, clean review: it must be written out, so a missing file
    is never taken for one.
    """
    try:
        data = json.loads(text)
    except ValueError as error:
        raise _bad(f"the findings file is not JSON ({error})") from error
    if not isinstance(data, dict):
        raise _bad("the findings file must be a JSON object")
    items = data.get("findings")
    if "findings" not in data:
        raise _bad("the findings file holds no findings key; a clean review is an empty list")
    if not isinstance(items, list):
        raise _bad("the findings key must hold a list")
    extra_top = sorted(set(data) - {"findings"})
    if extra_top:
        raise _bad(f"the findings file holds {', '.join(extra_top)}, which it may not")
    found: list[Finding] = []
    for index, raw in enumerate(items, start=1):
        where = f"finding {index}"
        if not isinstance(raw, dict):
            raise _bad(f"{where} must be an object")
        extra = sorted(set(raw) - FINDING_KEYS)
        if extra:
            raise _bad(f"{where} holds {', '.join(extra)}, which it may not")
        for key in ("kind", "gap", "piece", "evidence"):
            if key not in raw:
                raise _bad(f"{where} has no {key}")
        kind, gap, number = raw["kind"], raw["gap"], raw["piece"]
        if kind not in KINDS:
            raise _bad(f"{where}: kind must be one of {', '.join(KINDS)}, not {kind!r}")
        if gap not in GAPS:
            raise _bad(f"{where}: gap must be one of {', '.join(GAPS)}, not {gap!r}")
        if not isinstance(number, int) or isinstance(number, bool) or number not in pieces:
            raise _bad(f"{where}: piece {number!r} is not a piece joined to this branch "
                       f"({', '.join(str(p) for p in sorted(pieces))})")
        evidence = _text(raw["evidence"], "evidence", where)
        check: Check | None = None
        justification = ""
        if kind == "failing-check":
            for key in ("check", "justification"):
                if key not in raw:
                    raise _bad(f"{where}: a failing check needs its {key}")
            check = _parse_check(raw["check"], where)
            justification = _text(raw["justification"], "justification", where)
        elif "check" in raw or "justification" in raw:
            raise _bad(f"{where}: only a failing check may hold a check or a justification")
        found.append(Finding(kind, gap, number, evidence, check, justification))
    return found


# --- the reviewer's session -----------------------------------------------------------------


def findings_file(paths: Paths, run: str, key: str, number: int) -> Path:
    return paths.run_dir(run) / f"findings-{_label(key, number)}.json"


def _label(key: str, number: int) -> str:
    return f"review-{key}-r{number}"


def plan_session(
    paths: Paths, *, run: str, key: str, number: int, worktree: Path, pieces: Sequence[int],
    rounds: int, specs: str, diff: str, env: Mapping[str, str] | None,
    max_budget_usd: float | None,
) -> sessions.Session:
    """Plan the reviewer's session. Its brief holds the specs and the diff, each in a data block.

    The command line is the shared one: no account, no token, no resume. The environment is
    scrubbed of every GitHub credential by `sessions.plan`. The settings allow a read of the
    worktree and a write of the findings file, and nothing else.
    """
    target = findings_file(paths, run, key, number)
    template = (paths.kit_dir / "briefs" / "reviewer.md").read_text(encoding="utf-8")
    brief = sessions.render_brief(
        template,
        trusted={"PIECES": ", ".join(str(p) for p in pieces), "ROUND": str(number),
                 "ROUNDS": str(rounds), "FINDINGS_FILE": str(target)},
        outside={"spec": specs, "diff": diff})
    return sessions.plan(
        paths, run=run, label=_label(key, number), worktree=worktree, brief=brief,
        max_budget_usd=max_budget_usd, env=env,
        settings_template=paths.kit_dir / "templates" / "reviewer-settings.json",
        extra_values={"FINDINGS_FILE": str(target)}, extra_env={FINDINGS_ENV: str(target)})


# --- the loop -------------------------------------------------------------------------------


@dataclass
class TrackReport:
    status: str  # skipped, clean, closed, sent
    key: str = MAIN_TRACK
    round: int = 0
    message: str = ""
    sent: dict[int, str] = field(default_factory=dict)  # piece: building or shaping


@dataclass
class Plan:
    """What one round does with each piece, decided before anything moves."""

    building: dict[int, tuple[list[Finding], Finding]] = field(default_factory=dict)
    shaping: dict[int, list[Finding]] = field(default_factory=dict)
    notes: dict[int, list[Finding]] = field(default_factory=dict)
    demoted: list[tuple[Finding, str]] = field(default_factory=list)


class Reviewer:
    def __init__(
        self,
        paths: Paths,
        name: str,
        run: run_record.RunRecord,
        policy: Mapping[str, Any],
        loop: integrate.Integrator,
        *,
        start_session: SessionStarter | None = None,
        mover: Mover | None = None,
        judge_run: JudgeRun | None = None,
        restart: Callable[[int], None] | None = None,
        ask_round: Callable[[], None] | None = None,
        gate_lock: Any = None,
        env: Mapping[str, str] | None = None,
        rounds: int | None = None,
        hub: Any = None,
    ) -> None:
        self.paths = paths
        self.root = paths.root
        self.name = name
        self.record = run
        self.policy = policy
        self.loop = loop
        self.start_session: SessionStarter = start_session or sessions.start
        self.mover: Mover = mover or self._default_mover
        self.judge_run: JudgeRun = judge_run or self._default_judge
        self.restart = restart or (lambda number: None)
        self.ask_round = ask_round or (lambda: None)
        self.gate_lock = gate_lock if gate_lock is not None else contextlib.nullcontext()
        self.env = env
        self.rounds = rounds
        self.hub = hub if hub is not None else github.GitHub(paths)
        self._identity = integrate._identity(self.root)

    # --- defaults ---------------------------------------------------------------------------

    def _default_mover(self, number: int, target: str, reason: str,
                       options: Mapping[str, str]) -> Reply:
        return Gateway(self.paths).move(number, target, reason=reason, options=options)

    def _default_judge(self, command: str, root: Path, ref: str, **more: Any) -> dict[str, Any]:
        try:
            limit: int | None = int(self.policy["test_timeout_seconds"])
        except (KeyError, TypeError, ValueError):
            limit = None
        return judge.run(command, root, ref, time_limit=limit, **more)

    def cap(self) -> int:
        if self.rounds is not None:
            return self.rounds
        try:
            return int(self.policy.get("review_rounds", DEFAULT_ROUNDS))
        except (TypeError, ValueError):
            return DEFAULT_ROUNDS

    # --- the record -------------------------------------------------------------------------

    def _data(self) -> dict[str, Any]:
        found: dict[str, Any] = self.record.data.setdefault("review", {})
        found.setdefault("tracks", {})
        found.setdefault("verdicts", {})
        return found

    def _state(self, key: str) -> dict[str, Any]:
        with self.record.lock:
            tracks: dict[str, Any] = self._data()["tracks"]
            state: dict[str, Any] = tracks.setdefault(key, {"rounds": 0, "status": "new"})
            return state

    def _save(self) -> None:
        self.record.save()

    def _set(self, key: str, **fields: Any) -> None:
        with self.record.lock:
            self._state(key).update(fields)
            self._save()

    def _verdict(self, number: int, verdict: str, round_number: int,
                 findings: Sequence[str] = (), notes: Sequence[str] = ()) -> None:
        with self.record.lock:
            self._data()["verdicts"][str(number)] = {
                "verdict": verdict, "round": round_number, "findings": list(findings),
                "notes": list(notes)}
            self._save()

    def _refuse(self, key: str, message: str, next_command: str) -> ReviewRefusal:
        self._set(key, status="refused", reason=message)
        self.record.note(f"Review of {key} refused: {message}")
        return ReviewRefusal(message, next_command)

    # --- every track ------------------------------------------------------------------------

    def review_all(self) -> list[TrackReport]:
        """Review each combined branch that holds a piece. The first refusal is raised last."""
        reports: list[TrackReport] = []
        first: ReviewRefusal | None = None
        for key in self.loop.tracks():
            try:
                reports.append(self.review(key))
            except (ReviewRefusal, integrate.IntegrationRefusal) as error:
                if first is None:
                    first = (error if isinstance(error, ReviewRefusal) else ReviewRefusal(
                        str(error), error.next_command))
        if first is not None:
            raise first
        return reports

    # --- one track --------------------------------------------------------------------------

    def _head(self, branch: str) -> str:
        return integrate._must(self.root, f"read the head of {branch}", "rev-parse",
                               f"refs/heads/{branch}")

    def _green(self, key: str, branch: str, head: str) -> bool:
        final = self.record.data.get("integration", {}).get("final", {}).get(key)
        return bool(final) and final.get("status") == "green" and final.get("branch") == branch \
            and final.get("head") == head

    def review(self, key: str = MAIN_TRACK) -> TrackReport:
        """One round for one combined branch, when its final check is green on its head."""
        with self.loop._lock:
            pieces = self.loop.joined(key)
            if not pieces:
                return TrackReport("skipped", key, message=f"{key} holds no piece")
            branch = self.loop.combined(key)
            head = self._head(branch)
            state = self._state(key)
            if not self._green(key, branch, head):
                return TrackReport("skipped", key, state["rounds"],
                                   f"the final check of {branch} is not green on its head")
            if state.get("accept"):
                self._set(key, status="clean", reviewed=head, accept=False)
                self.record.note(f"Review of {branch}: piece(s) "
                                 f"{', '.join(str(n) for n in state.get('removed', []))} left "
                                 "after the last round, and the branch without them passed "
                                 "its checks, so it goes ahead")
                return TrackReport("closed", key, state["rounds"])
            if state.get("reviewed") == head:
                return TrackReport("skipped", key, state["rounds"], "already reviewed")
            number = int(state["rounds"]) + 1
            if number > self.cap():
                raise self._refuse(
                    key, f"{branch} changed after the last review round ({self.cap()} of "
                    f"{self.cap()}) and no round is left, so its head {head[:7]} was not "
                    "reviewed", "the person reads the diff, or raises review_rounds in the "
                    f"policy file, then run.py --run {self.name}")
            gone = self._fingerprints(key, pieces, number)
            if gone:
                self.ask_round()
                return TrackReport("sent", key, state["rounds"], sent={n: "shaping" for n in gone})
            return self._round(key, pieces, branch, head, number)

    # --- the fingerprints -------------------------------------------------------------------

    def _body(self, key: str, view: integrate.PieceView) -> str:
        """The issue body as it is now. With the App it is read from GitHub, as the gate reads it.

        The gate's record holds the last body the gate wrote, and an edit by hand reaches
        GitHub first. Without the App there is no other body to read.
        """
        if view.issue is None or not self.hub.available:
            return view.body
        try:
            return str(self.hub.read_issue(view.issue)["body"])
        except github.GitHubError as error:
            raise self._refuse(
                key, f"issue {view.issue} of piece {view.number} cannot be read ({error.message}), "
                "so review cannot confirm that its spec is the one the gate froze",
                error.next_command) from error

    def _fingerprints(self, key: str, pieces: Sequence[int], number: int) -> list[int]:
        """Take each piece's fingerprint again. A spec that changed goes to shaping (move 9)."""
        gone: list[int] = []
        for piece in pieces:
            view = self.loop.reader(piece)
            recorded = next((e["fingerprint"] for e in reversed(view.record)
                             if e.get("kind") == "fingerprint"), None)
            if not recorded:
                raise self._refuse(
                    key, f"the piece record of piece {piece} holds no fingerprint, so review "
                    "cannot confirm that the spec is the one the gate froze",
                    f"gate.py report {piece}")
            try:
                now = fingerprint.take(self._body(key, view),
                                       str(recorded.get("judge_commit", "")))
            except (spec.SpecError, fingerprint.FingerprintError) as error:
                reason = (f"Review would not read piece {piece}: its spec cannot be read now "
                          f"({error}), so the spec is not the one the gate froze. The piece "
                          "leaves the combined branch and goes back to shaping.")
            else:
                if now["fingerprint"] == recorded.get("fingerprint"):
                    continue
                reason = (f"Review would not read piece {piece}: the fingerprint of its spec "
                          f"changed since the gate froze it (it was "
                          f"{str(recorded.get('fingerprint'))[:12]}, it is now "
                          f"{now['fingerprint'][:12]}), so someone edited the spec and the gate "
                          "did not make the change. The piece leaves the combined branch and "
                          "goes back to shaping.")
            if self._leave_to_shaping(key, piece, reason, number, [])[0]:
                gone.append(piece)
            self._verdict(piece, "shaping", number, [reason])
        return gone

    # --- one round --------------------------------------------------------------------------

    def _budget(self) -> float | None:
        cap = (self.policy.get("billing") or {}).get("spend_cap_per_run_usd")
        if cap is None:
            return None
        left = float(cap) - self.record.spend_total()
        if left <= 1e-9:
            raise ReviewRefusal(
                f"the spend cap of the run is used up, so the reviewer cannot start "
                f"(${self.record.spend_total():.2f} of ${float(cap):.2f})",
                "raise the cap in the policy file, then run.py --run " + self.name)
        return round(left, 4)

    def _round(self, key: str, pieces: Sequence[int], branch: str, head: str,
               number: int) -> TrackReport:
        try:
            budget = self._budget()
        except ReviewRefusal as error:
            raise self._refuse(key, str(error), error.next_command) from error
        specs, diff = self._material(key, pieces, branch)
        text = self._read(key, pieces, head, number, specs, diff, budget)
        try:
            found = parse_findings(text, pieces)
        except ReviewRefusal as error:
            raise self._refuse(key, str(error), error.next_command) from error
        last = number >= self.cap()
        try:
            plan = self._decide(found, head, last)
            self._ready_to_commit(plan)
        except ReviewRefusal as error:
            raise self._refuse(key, str(error), error.next_command) from error
        self._set(key, rounds=number, status="open")
        return self._act(key, pieces, branch, head, number, last, plan)

    def _material(self, key: str, pieces: Sequence[int], branch: str) -> tuple[str, str]:
        """The specs and the diff of each piece's join: all the reviewer is shown."""
        joins = self._joins(branch)
        specs: list[str] = []
        diffs: list[str] = []
        for piece in pieces:
            view = self.loop.reader(piece)
            parsed = spec.parse(view.body)
            if not parsed.found:
                raise self._refuse(key, f"piece {piece} has no spec block, so the reviewer has "
                                   "no spec to read", f"gate.py report {piece}")
            specs.append(f"## Piece {piece}: {' '.join(view.title.split())}\n\n{parsed.block}")
            if piece not in joins:
                raise self._refuse(
                    key, f"no join commit of piece {piece} is on {branch}, so its diff cannot be "
                    "shown", f"python3 -m loop.run.integrate status --run {self.name}")
            commit, parent = joins[piece]
            changed = integrate._must(
                self.root, f"read the diff of piece {piece}", "diff", "--no-color",
                "--no-ext-diff", "--no-renames", parent, commit, "--")
            diffs.append(f"=== piece {piece} (join commit {commit[:7]}) ===\n"
                         f"{changed or 'This join changed no file.'}")
        return "\n\n".join(specs), "\n\n".join(diffs)

    def _joins(self, branch: str) -> dict[int, tuple[str, str]]:
        out = integrate._must(
            self.root, f"read the join commits of {branch}", "log", "--first-parent",
            "--format=%H%x1f%P%x1f%B%x1e", f"refs/heads/{branch}", f"^refs/heads/{integrate.MAIN}")
        found: dict[int, tuple[str, str]] = {}
        for row in out.split("\x1e"):
            fields = row.strip().split("\x1f")
            if len(fields) != 3:
                continue
            commit, parents, message = fields
            numbers = integrate.trailers(message)
            if len(numbers) == 1 and parents.split():
                found[numbers[0]] = (commit, parents.split()[0])
        return found

    def _read(self, key: str, pieces: Sequence[int], head: str, number: int, specs: str,
              diff: str, budget: float | None) -> str:
        """Run the session in a scratch copy of the head and return its findings text."""
        folder = self.paths.worktrees_dir / f"review-{self.name}-{key}-r{number}"
        target = findings_file(self.paths, self.name, key, number)
        with contextlib.suppress(OSError):
            moved = sessions._move_aside(target)
            if moved is not None:
                self.record.note(f"an earlier findings file was kept as {moved.name}")
        if folder.exists():
            integrate.remove_worktree(self.root, folder)
        with self.gate_lock:
            integrate._must(self.root, "made the reviewer's scratch copy", "worktree", "add",
                            "-q", "--detach", str(folder), head)
        try:
            try:
                session = plan_session(
                    self.paths, run=self.name, key=key, number=number, worktree=folder,
                    pieces=pieces, rounds=self.cap(), specs=specs, diff=diff, env=self.env,
                    max_budget_usd=budget)
                result = self.start_session(session)
            except (sessions.SessionError, OSError) as error:
                raise self._refuse(
                    key, f"the reviewer session could not start ({error})",
                    getattr(error, "next_command", "") or f"run.py --run {self.name}") from error
        finally:
            with self.gate_lock:
                note = integrate.remove_worktree(self.root, folder)
            if note:
                self.record.note(note)
        self._spend(pieces, result)
        if result.exit_code != 0:
            raise self._refuse(
                key, f"the reviewer session ended with exit code {result.exit_code}, so there "
                "is no review", f"look at {session.brief_file}, then run.py --run {self.name}")
        try:
            return target.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise self._refuse(
                key, f"the reviewer left no findings file ({target.name}), and a review that "
                "did not say it found nothing is not a clean one",
                f"run.py --run {self.name} to review again") from error
        except (OSError, UnicodeDecodeError) as error:
            raise self._refuse(key, f"the findings file cannot be read ({error})",
                               f"run.py --run {self.name}") from error

    def _spend(self, pieces: Sequence[int], result: sessions.Result) -> None:
        cost = (result.output or {}).get("total_cost_usd")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost >= 0:
            self.record.add_spend(min(pieces), float(cost))

    # --- deciding ---------------------------------------------------------------------------

    def _decide(self, found: Sequence[Finding], head: str, last: bool) -> Plan:
        """Sort the findings by piece. Every failing check is proved before anything moves."""
        plan = Plan()
        for item in found:
            if item.kind == "worth-knowing":
                plan.notes.setdefault(item.piece, []).append(item)
        stops: dict[int, list[Finding]] = {}
        for item in found:
            if item.kind != "worth-knowing":
                stops.setdefault(item.piece, []).append(item)
        for piece, items in sorted(stops.items()):
            wrong = any(f.kind == "wrong-spec" for f in items)
            if last or wrong:
                plan.shaping[piece] = items
                continue
            chosen: Finding | None = None
            for item in items:
                assert item.check is not None
                verdict, why = self._prove(item.check, head)
                if verdict == "proved":
                    chosen = item
                    break
                plan.demoted.append((item, why))
            if chosen is None:
                continue
            plan.building[piece] = (items, chosen)
        return plan

    def _prove(self, check: Check, head: str) -> tuple[str, str]:
        """Run the reviewer's test on the combined head.

        It is proved only when the runner is one whose report the gate reads and the test fails
        on an assertion that names a spec ID (FL- or EC-). A pass, a bare exit code from another
        runner, or a failure with no spec ID is not proved: the finding is refused with a note
        and no test is frozen. A test that cannot run is a refusal of the whole review.
        """
        try:
            verdict = self.judge_run(check.command, self.root, head,
                                     extra_files={check.path: check.text})
        except judge.JudgeError as error:
            raise ReviewRefusal(
                f"the reviewer's test {check.path} could not be run ({error}), so the finding "
                "is not proved", error.next_command) from error
        outcome = str(verdict.get("outcome"))
        runner = verdict.get("runner")
        if outcome == "passed":
            return "passed", "did not fail on the combined branch"
        if outcome in ("failed", "failed_no_id") and runner not in judge.REPORT_RUNNERS:
            return "unproved", (
                f"was run by {runner or 'a runner the gate does not know'}, which writes no "
                f"report the gate reads ({', '.join(judge.REPORT_RUNNERS)} do), so a failure "
                "cannot be told from a crash")
        if outcome == "failed_no_id":
            return "unproved", ("failed, but on no assertion that names a spec ID "
                                "(FL- or EC-), so it is not the right failure")
        if outcome in FAILING:
            return "proved", ""
        raise ReviewRefusal(
            f"the reviewer's test {check.path} did not fail on an assertion (it {outcome}), so "
            "it is not a failing check and the gate cannot tell whether the finding is true",
            f"read the test in the findings file, then run.py --run {self.name} to review again")

    def _ready_to_commit(self, plan: Plan) -> None:
        """Check that every piece worktree can take its test, before any piece moves."""
        for piece, (_items, chosen) in plan.building.items():
            assert chosen.check is not None
            self._folder(piece, chosen.check.path)

    def _folder(self, piece: int, path: str) -> Path:
        name = self.record.piece(piece).get("worktree")
        if not name:
            raise ReviewRefusal(
                f"the run record holds no worktree for piece {piece}, so the reviewer's test "
                "cannot be committed to its branch", f"gate.py branch {piece}, then run.py "
                f"--run {self.name}")
        folder = self.paths.worktrees_dir / str(name)
        code, branch, _ = integrate._git(folder, "rev-parse", "--abbrev-ref", "HEAD")
        if code != 0 or branch != f"piece-{piece}":
            raise ReviewRefusal(
                f"the folder {folder} does not hold the branch piece-{piece}, so the reviewer's "
                "test cannot be committed there", f"look at {folder}, then run.py --run "
                f"{self.name}")
        code, dirty, _ = integrate._git(folder, "status", "--porcelain", "--untracked-files=all")
        if code != 0 or dirty:
            first = dirty.splitlines()[0].strip() if dirty else "git failed"
            raise ReviewRefusal(
                f"the folder {folder} holds unsaved work ({first}), and review will not "
                "commit beside it", f"commit or keep that work, then run.py --run {self.name}")
        if (folder / path).exists():
            raise ReviewRefusal(
                f"the file {path} already exists on piece-{piece}, and review adds a new test "
                "and never overwrites one",
                f"read the findings file, then run.py --run {self.name}")
        return folder

    # --- acting -----------------------------------------------------------------------------

    def _act(self, key: str, pieces: Sequence[int], branch: str, head: str, number: int,
             last: bool, plan: Plan) -> TrackReport:
        report = TrackReport("clean", key, number)
        restarted = False  # a call that left the round sent another piece to be built again
        for demoted, why in plan.demoted:
            self.loop.worth_knowing(
                f"The reviewer's check for piece {demoted.piece} {why}, so the finding is not "
                f"proved and nothing was sent back: {demoted.evidence}", source="review",
                piece=demoted.piece, gap=demoted.gap, round=number)
        for piece in pieces:
            notes = [f.evidence for f in plan.notes.get(piece, [])]
            for item in plan.notes.get(piece, []):
                self.loop.worth_knowing(item.evidence, source="review", piece=piece,
                                        gap=item.gap, round=number)
            if piece in plan.shaping:
                items = plan.shaping[piece]
                reason = self._shaping_reason(piece, branch, items, number, last)
                moved, again = self._leave_to_shaping(key, piece, reason, number,
                                                      [f.evidence for f in items])
                restarted = restarted or bool(again)
                if moved:
                    report.sent[piece] = "shaping"
                    removed = [*self._state(key).get("removed", []), piece]
                    self._set(key, removed=removed)
                self._verdict(piece, "shaping", number, [f.evidence for f in items], notes)
            elif piece in plan.building:
                items, chosen = plan.building[piece]
                if self._send_to_building(key, piece, branch, items, chosen, number):
                    report.sent[piece] = "building"
                self._verdict(piece, "sent-back", number, [f.evidence for f in items], notes)
            else:
                self._verdict(piece, "clean", number, (), notes)
        if report.sent:
            report.status = "sent"
            # A branch that changed for any other reason than the removal was never read.
            self._set(key, status="open", accept=last and not restarted and any(
                v == "shaping" for v in report.sent.values()))
            self.ask_round()
        else:
            report.status = "clean"
            self._set(key, status="clean", reviewed=head)
        return report

    def _shaping_reason(self, piece: int, branch: str, items: Sequence[Finding], number: int,
                        last: bool) -> str:
        said = " ".join(f"({f.kind}, {f.gap}) {f.evidence}" for f in items)
        if last and not any(f.kind == "wrong-spec" for f in items):
            head = (f"A finding is still there for piece {piece} after {self.cap()} rounds of "
                    f"review, so no round is left. The piece leaves {branch} and goes to "
                    "shaping, and the person decides.")
        elif last:
            head = (f"Review round {number} of {self.cap()}: the fresh reviewer found that the "
                    f"spec of piece {piece} is wrong. The piece leaves {branch} and goes to "
                    "shaping, and the person decides.")
        else:
            head = (f"Review round {number} of {self.cap()}: the fresh reviewer found that the "
                    f"spec of piece {piece} is wrong. The piece leaves {branch} and goes back "
                    "to shaping.")
        return self._clip(f"{head} What it found: {said}")

    @staticmethod
    def _clip(text: str) -> str:
        return text if len(text) <= REASON_LIMIT else text[:REASON_LIMIT - 3].rstrip() + "..."

    def _leave_to_shaping(self, key: str, piece: int, reason: str, number: int,
                          findings: Sequence[str]) -> tuple[bool, list[int]]:
        """Take the piece out of the combined branch, then move 9.

        Returns whether the piece moved, and the pieces the rebuild replay sent back to be built
        again (`left.restarted`). Such a piece rejoins on a new head that no reviewer reads.
        """
        left = self.loop.leave(piece, reason)
        if left.status != "rebuilt":
            raise self._refuse(key, left.message, left.next_command)
        again = list(left.restarted)
        with self.gate_lock:
            reply = self.mover(piece, "shaping", reason, {})
        if not reply.ok:
            self._wait(piece, f"the gate refused to send piece {piece} to shaping: "
                       f"{reply.message}", reply.next_command or
                       f"gate.py move {piece} shaping --reason <the finding>")
            return False, again
        self.record.set_status(piece, run_record.SENT_BACK, reason=reason)
        self.record.add_decision(piece, "run", f"Sent piece {piece} to shaping after review "
                                 f"round {number}. {reason}")
        return True, again

    def _send_to_building(self, key: str, piece: int, branch: str, items: Sequence[Finding],
                          chosen: Finding, number: int) -> bool:
        check = chosen.check
        assert check is not None
        folder = self._folder(piece, check.path)
        commit = self._commit_test(folder, piece, check, chosen)
        also = [f.evidence for f in items if f is not chosen]
        reason = self._clip(
            f"Review round {number} of {self.cap()}: the fresh reviewer found a failing check in "
            f"piece {piece} ({chosen.gap}). {chosen.evidence} The reviewer's test {check.path} "
            f"fails on {branch}. It was committed to the piece branch by the review loop and "
            f"joins the frozen bar. Why it can be trusted: {chosen.justification}"
            + (f" Also found: {' '.join(also)}" if also else ""))
        left = self.loop.leave(piece, reason)
        if left.status != "rebuilt":
            raise self._refuse(key, left.message, left.next_command)
        options = {"review_test_path": check.path, "review_test_commit": commit,
                   "review_test_command": check.command,
                   "review_justification": chosen.justification}
        with self.gate_lock:
            reply = self.mover(piece, "building", reason, options)
        if not reply.ok:
            self._wait(piece, f"the gate refused to send piece {piece} back to building: "
                       f"{reply.message}", reply.next_command or
                       f"gate.py move {piece} building --reason <the finding>")
            return False
        landed = str(reply.data.get("to") or "building")
        finding_text = " ".join([chosen.evidence, *also])
        self.record.update(piece, review_finding=finding_text)
        if landed == "building":
            self.restart(piece)
        else:
            self.record.set_status(piece, run_record.SENT_BACK, reason=reason)
        self.record.add_decision(
            piece, "run", f"Sent piece {piece} back to {landed} after review round {number}. "
            f"The reviewer's test {check.path} joined the frozen bar. {reason}")
        return landed == "building"

    def _commit_test(self, folder: Path, piece: int, check: Check, chosen: Finding) -> str:
        """Commit the reviewer's test to the piece branch, in the piece's own folder.

        The loop does it, never the builder, so the file is the reviewer's, byte for byte. The
        commit has no hook, no signature and no attribution line.
        """
        target = folder / check.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(check.text, encoding="utf-8")
        config = [*self._identity, *integrate.QUIET]
        for args in (("add", "--", check.path),
                     ("commit", "--no-verify", "-q", "-m",
                      f"Add a check from review: {chosen.evidence[:60]}")):
            code, out, err = integrate._git(folder, *args, config=config)
            if code != 0:
                raise ReviewRefusal(
                    f"git {args[0]} failed in {folder} while review committed its test "
                    f"({(err or out)[:100]})", f"look at {folder}, then run.py --run {self.name}")
        return integrate._must(folder, "read the commit of the review test", "rev-parse", "HEAD")

    def _wait(self, piece: int, why: str, next_command: str) -> None:
        self.record.set_status(piece, run_record.WAITING_PERSON, reason=why, next=next_command)


# --- the hooks ------------------------------------------------------------------------------

_REVIEWERS: dict[tuple[str, str, str], Reviewer] = {}


def reviewer_for(context: Any) -> Reviewer:
    key = (str(context.paths.root), str(context.name), str(id(context.record)))
    made = _REVIEWERS.get(key)
    if made is None:
        made = Reviewer(
            context.paths, context.name, context.record, context.policy,
            integrate.integrator_for(context),
            start_session=getattr(context, "start_session", None),
            restart=getattr(context, "restart_piece", None),
            ask_round=getattr(context, "another_round", None),
            gate_lock=getattr(context, "gate_lock", None))
        _REVIEWERS[key] = made
    return made


def run_hook(context: Any, event: str, **data: Any) -> None:
    """The engine's hook. `built-all` reviews; `run-end` notes a review that did not finish."""
    if event == "built-all":
        reviewer_for(context).review_all()
    elif event == "run-end":
        tracks = context.record.data.get("review", {}).get("tracks", {})
        for key, state in tracks.items():
            if state.get("status") in ("open", "refused"):
                context.record.note(
                    f"Review of {key} did not finish ({state.get('status')}): a piece left "
                    "the combined branch or a review was refused, and the branch was not "
                    "reviewed again, so no pull request opens for it")


# --- a door for the person and the tools ----------------------------------------------------


def _setup(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    status = commands.add_parser("status", help="show each combined branch's review")
    status.add_argument("--run", required=True, help="the run's name")
    status.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="print JSON")
    status.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS,
                        help="accepted, and ignored: this command changes nothing")
    check = commands.add_parser(
        "check-findings", help="check a findings file against the schema (changes nothing)")
    check.add_argument("--file", required=True, help="the findings file")
    check.add_argument("--pieces", required=True, help="the joined pieces, such as 1,2,3")
    check.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                       help="print JSON")
    check.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS,
                       help="accepted, and ignored: this command changes nothing")


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    from loop.paths import PathError, find_project_root

    try:
        if args.command == "check-findings":
            try:
                pieces = [int(p) for p in re.split(r"[ ,]+", args.pieces.strip()) if p]
            except ValueError as error:
                raise cli.Failure(f"--pieces must be numbers ({error})",
                                  next_command="review --help", code=ExitCode.USAGE) from error
            try:
                text = Path(args.file).read_text(encoding="utf-8")
            except OSError as error:
                raise cli.Failure(f"{args.file} cannot be read ({error.strerror})",
                                  next_command="review --help", code=ExitCode.ENVIRONMENT
                                  ) from error
            found = parse_findings(text, pieces)
            return {"findings": len(found), "kinds": sorted({f.kind for f in found})}
        paths = Paths.for_project(find_project_root(Path.cwd()))
        run = run_record.RunRecord.load(paths, args.run)
        shown: dict[str, Any] = run.data.get("review", {"tracks": {}, "verdicts": {}})
        return {"review": shown}
    except ReviewRefusal as error:
        raise cli.Failure(str(error), next_command=error.next_command,
                          code=ExitCode.REFUSED) from error
    except (PathError, run_record.RecordError) as error:
        raise cli.Failure(str(error), next_command=getattr(error, "next_command", "")
                          or "python3 -m loop.run.review --help",
                          code=ExitCode.ENVIRONMENT) from error


def main(argv: list[str]) -> int:
    return cli.run(
        "review", "Look at a run's review, or check a findings file: status, check-findings.",
        _setup, _handle, argv, changes_state=True)


if __name__ == "__main__":
    # Run under its real name, so the exceptions the modules share are one class.
    from loop.run.review import main as _main

    sys.exit(_main(sys.argv[1:]))

