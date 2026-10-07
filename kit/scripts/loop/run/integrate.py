"""The integration loop: join each built piece to the run's combined branch, one trial at a time.

The engine (`loop.run.engine`) calls `run_hook` for the events of a run. This module answers
`start`, `piece-built` and `built-all`. It never writes a label or a piece record. The one
state move it makes, the culprit going back to building (move 8), goes through the gate.

How a join goes:

1. A scratch copy of the combined branch is made (`git worktree add --detach`). Main is taken
   in first, by a merge commit, when it moved. Then the piece branch is merged in with a merge
   commit that carries a `Piece: #n` trailer. A merge conflict is red, and no agent resolves it.
2. The scratch copy is removed. The trial commit is the thing every check runs on. The checks
   run on a temporary checkout of that commit (`loop.judge`): each joined piece's visible
   judge, its must-stay-the-same checks, and the check that every join commit stays inside the
   declared touches of its piece. Held-out cases are never part of a trial.
3. A red result runs the same check on the same commit once more. A result that differs marks
   the check flaky. A flaky check is a worth-knowing item and never a pass: the trial is thrown
   away, no piece is blamed, and the piece waits for the person.
4. Only on green does the combined branch move to the trial commit (`git update-ref`, with the
   old value given, so a branch that moved meanwhile is a refusal). On red the trial is thrown
   away, the branch never moves, and the piece just joined goes back to building by move 8,
   with the clash written as the reason. The run then carries on.

A piece that must leave after it joined is never reverted out. `leave` cuts a new combined
branch from main under a fresh name and replays the joins that stay, each as a trial. The old
branch is left as it was. Nothing here uses a rebase, a reset, a revert or a force push.

A resumed run reads the `Piece:` trailers on the combined branch to see which joins are done,
so a piece never joins twice. The run record keeps the branch names and the worth-knowing items.

At the end (`finish`), the docs commit is made on the combined branch (`loop.run.docs_commit`),
then the final combined check runs every joined piece's judges again, with the held-out cases
copied into the checkout only for that check (`loop.heldout`, the judge's `extra_files`). Git
never holds them. A green branch is pushed through the gate's push step (`loop.github.push`),
which scans for secrets first. Before the App exists the push waits for the person, with a
`next:` line.

What this module never does is let a check pass that did not run. A git error, a judge that
could not run, a record that cannot be read or a push that was refused is a refusal, never a
pass, and each names its next command.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loop import areas, github, judge, moves, spec
from loop.cli import ExitCode
from loop.paths import Paths
from loop.run import record as run_record
from loop.run.gateway import Reply

MAIN = "main"
TRAILER_PREFIX = "Piece: #"
TRAILER = re.compile(r"^Piece: #(\d+)[ \t]*$", re.MULTILINE)
REASON_LIMIT = 900
MAIN_TRACK = "main"
FINAL_ROUNDS = 5

QUIET = ("-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null")

JudgeRun = Callable[..., dict[str, Any]]
Mover = Callable[[int, str, str], Reply]
Push = Callable[[str], dict[str, Any]]
HeldRuns = Callable[["PieceView"], Sequence[tuple[str, Mapping[str, str]]]]
DocsCommit = Callable[..., Any]


def trailers(text: str) -> list[int]:
    """The piece numbers named by `Piece: #n` lines in a commit message, in order."""
    return [int(n) for n in TRAILER.findall(text)]


class IntegrationRefusal(Exception):
    """The loop could not tell, so it refuses and never passes. The message names the next step."""

    def __init__(self, message: str, next_command: str) -> None:
        super().__init__(message)
        self.next_command = next_command


@dataclass(frozen=True)
class PieceView:
    """What the loop reads of a piece from the gate's record."""

    number: int
    title: str
    state: str
    issue: int | None
    individual: bool
    issue_type: str
    spec: Mapping[str, Any]
    judge_files: tuple[str, ...] = ()
    record: Sequence[Mapping[str, Any]] = ()
    body: str = ""


@dataclass
class JoinResult:
    status: str  # joined, already, red, conflict, flaky, waiting, refused, rebuilt, green
    number: int = 0
    message: str = ""
    next_command: str = ""
    trial: str = ""
    head: str = ""
    branch: str = ""
    failures: list[dict[str, str]] = field(default_factory=list)
    restarted: list[int] = field(default_factory=list)
    info: dict[str, Any] = field(default_factory=dict)


@dataclass
class Failure:
    piece: int
    kind: str  # judge, must-stay, touches, held-out
    command: str
    text: str
    extra: Mapping[str, str] | None = None
    outcome: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"piece": str(self.piece), "kind": self.kind, "command": self.command,
                "text": self.text}


# --- git ------------------------------------------------------------------------------------


def _identity(root: Path) -> list[str]:
    """`-c` options that give a committer when Git has none, so a scratch merge can commit."""
    done = subprocess.run(["git", "-C", str(root), "var", "GIT_COMMITTER_IDENT"],
                          capture_output=True, text=True, check=False)
    if done.returncode == 0:
        return []
    return ["-c", "user.name=AI Loop Kit", "-c", "user.email=loop@localhost.invalid"]


def _git(folder: Path, *args: str, config: Sequence[str] = ()) -> tuple[int, str, str]:
    done = subprocess.run(["git", "-C", str(folder), *config, *args], capture_output=True,
                          text=True, check=False)
    return done.returncode, done.stdout.strip(), done.stderr.strip()


def _must(folder: Path, why: str, *args: str, config: Sequence[str] = ()) -> str:
    code, out, err = _git(folder, *args, config=config)
    if code != 0:
        first = (err or out).splitlines()[0] if (err or out) else f"exit code {code}"
        raise IntegrationRefusal(
            f"git {args[0]} failed while the loop {why} ({first}), so the loop cannot tell",
            f"check the project's git repository ({folder}), then run.py --run again")
    return out


def remove_worktree(root: Path, path: Path) -> str:
    """Take a scratch copy away. Returns "" or a note. It never forces and never deletes by hand.

    A copy that holds a tracked change is first put back to its commit with `checkout`. Files
    that are not tracked count as ignored, as `loop.judge` does it.
    """
    if _git(root, "worktree", "remove", str(path))[0] == 0:
        return ""
    if path.is_dir():
        _git(path, "checkout", "-q", "--", ".")
        everything = path.parent / "exclude-everything"
        everything.write_text("*\n", encoding="utf-8")
        code, _, err = _git(root, "worktree", "remove", str(path),
                            config=["-c", f"core.excludesFile={everything}"])
        if code == 0:
            with contextlib.suppress(OSError):
                everything.unlink()
            return ""
        return (f"the scratch copy {path} could not be removed ({err[:100]}); remove it with: "
                f"git worktree remove {path}")
    _git(root, "worktree", "prune")
    return ""


def _exists(root: Path, ref: str) -> bool:
    return _git(root, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")[0] == 0


def _ancestor(root: Path, older: str, newer: str) -> bool:
    return _git(root, "merge-base", "--is-ancestor", older, newer)[0] == 0


# --- touches --------------------------------------------------------------------------------


def _rules_at(root: Path, ref: str) -> list[areas.Rule]:
    if not _git(root, "ls-tree", ref, "--", areas.MAP_FILE)[1]:
        return []
    code, text, _ = _git(root, "show", f"{ref}:{areas.MAP_FILE}")
    if code != 0:
        raise IntegrationRefusal(f"the area map at {ref[:7]} cannot be read",
                                 "check the project's git repository, then run.py again")
    try:
        return areas.parse(text)
    except areas.AreaMapError as error:
        raise IntegrationRefusal(f"the area map at {ref[:7]} cannot be read: {error}",
                                 error.next_command) from error


def touches_faults(
    root: Path, parent: str, commit: str, *, allowed: Collection[str],
    new_areas: Collection[str], frozen: Collection[str],
) -> list[str]:
    """The files a join commit changed outside the declared touches of its piece.

    The same rule as the attempt gate's: the area map is read from the parent, so a piece
    cannot widen its touches by editing the map, except for a new area it names.
    """
    code, listing, _ = _git(root, "diff", "--no-renames", "--name-only", "-z", parent, commit,
                            "--")
    if code != 0:
        raise IntegrationRefusal(
            f"git diff failed while the loop checked the touches at {commit[:7]}",
            "check the project's git repository, then run.py again")
    # `_git` strips the ends of the text, which is safe for a list that ends in a NUL.
    paths = sorted(p for p in listing.split("\0") if p and p not in frozen)
    base_rules = _rules_at(root, parent)
    head_rules: list[areas.Rule] | None = None
    allowed_set = {a for a in allowed if a.lower() != "none"}
    new_set = set(new_areas)
    outside: list[str] = []
    for path in paths:
        area = areas.which(base_rules, path)
        if area == areas.EXEMPT or area in allowed_set:
            continue
        if new_set:
            if path == areas.MAP_FILE:
                continue
            if area == areas.UNCLAIMED:
                if head_rules is None:
                    head_rules = _rules_at(root, commit)
                if areas.area_of(head_rules, path) in allowed_set & new_set:
                    continue
        outside.append(f"{path} ({area})")
    return outside


# --- the integrator -------------------------------------------------------------------------


class Integrator:
    def __init__(
        self,
        paths: Paths,
        name: str,
        run: run_record.RunRecord,
        policy: Mapping[str, Any],
        *,
        reader: Callable[[int], PieceView] | None = None,
        judge_run: JudgeRun | None = None,
        mover: Mover | None = None,
        push: Push | None = None,
        restart: Callable[[int], None] | None = None,
        gate_lock: Any = None,
        dependencies: Mapping[int, Collection[int]] | None = None,
        held_runs: HeldRuns | None = None,
        docs_commit: DocsCommit | None = None,
    ) -> None:
        self.paths = paths
        self.root = paths.root
        self.name = name
        self.record = run
        self.policy = policy
        self.reader = reader or self._read
        self.judge_run: JudgeRun = judge_run or self._default_judge()
        self.mover = mover or self._default_mover
        self.push = push or self._default_push
        self.restart = restart or (lambda number: None)
        self.gate_lock = gate_lock if gate_lock is not None else contextlib.nullcontext()
        self.dependencies = {n: set(d) for n, d in (dependencies or {}).items()}
        self.held_runs: HeldRuns = held_runs or self._default_held
        self.docs_commit = docs_commit or self._default_docs
        self._lock = threading.RLock()
        self._identity = _identity(self.root)

    # --- defaults ---------------------------------------------------------------------------

    def _default_judge(self) -> JudgeRun:
        try:
            limit: int | None = int(self.policy["test_timeout_seconds"])
        except (KeyError, TypeError, ValueError):
            limit = None

        def run(command: str, root: Path, ref: str, **more: Any) -> dict[str, Any]:
            return judge.run(command, root, ref, time_limit=limit, **more)

        return run

    def _read(self, number: int) -> PieceView:
        try:
            piece = moves.read_piece(self.paths, number)
        except moves.MoveError as error:
            raise IntegrationRefusal(str(error), error.next_command) from error
        if piece is None:
            raise IntegrationRefusal(f"piece {number} is not in the gate's record",
                                     f"gate.py report {number}")
        try:
            parsed = spec.parse(piece.body).to_dict()
        except spec.SpecError as error:
            raise IntegrationRefusal(f"the spec of piece {number} cannot be read ({error})",
                                     f"gate.py report {number}") from error
        if not parsed["found"]:
            raise IntegrationRefusal(f"piece {number} has no spec block",
                                     f"gate.py report {number}")
        files: tuple[str, ...] = ()
        recorded = next((e["fingerprint"] for e in reversed(piece.record)
                         if e.get("kind") == "fingerprint"), None)
        if recorded and recorded.get("judge_commit") and "scaffold" not in str(
                parsed["judge"]["kind"] or "").lower():
            code, out, _ = _git(self.root, "diff-tree", "--no-commit-id", "--name-only", "-r",
                                "--root", str(recorded["judge_commit"]))
            if code == 0:
                files = tuple(out.splitlines())
        return PieceView(
            number=number, title=piece.title, state=piece.state, issue=piece.issue,
            individual=piece.individual_review, issue_type=piece.issue_type, spec=parsed,
            judge_files=files, record=tuple(piece.record), body=piece.body)

    def _default_mover(self, number: int, target: str, reason: str) -> Reply:
        from loop.run.gateway import Gateway

        return Gateway(self.paths).move(number, target, reason=reason)

    def _default_push(self, branch: str) -> dict[str, Any]:
        return github.push(self.paths, branch)

    def _default_held(self, view: PieceView) -> list[tuple[str, Mapping[str, str]]]:
        """Each hidden case as a judge command and the one file that holds the case.

        The cases are read from the gate's store, never from git, and are checked against the
        fingerprint in the spec, as the attempt gate does.
        """
        from loop.gates import CheckContext
        from loop.gates import attempt as attempt_gate
        from loop.gates import ready as ready_gate
        from loop.states import by_number

        sp = view.spec
        if ready_gate._is_scaffold(sp):
            return []
        ctx = CheckContext(number=view.number, move=by_number(5), origin="building",
                           target="review", reason=None, title=view.title, body=view.body,
                           spec=sp, record=view.record, paths=self.paths, options={})
        try:
            cases = attempt_gate._held_cases(ctx, sp)
            command = str(sp["judge"]["command"] or "")
            runs: list[tuple[str, Mapping[str, str]]] = []
            for path, text in cases.values():
                held = attempt_gate._held_command(command, list(view.judge_files), path,
                                                  view.number)
                runs.append((held, {path: text}))
        except attempt_gate.Refusal as error:
            raise IntegrationRefusal(str(error), error.next_command) from error
        return runs

    def _default_docs(self, **more: Any) -> Any:
        from loop.run import docs_commit

        return docs_commit.apply(**more)

    # --- the record -------------------------------------------------------------------------

    def _data(self) -> dict[str, Any]:
        found: dict[str, Any] = self.record.data.setdefault("integration", {})
        found.setdefault("tracks", {})
        found.setdefault("worth_knowing", [])
        return found

    def _save(self) -> None:
        self.record.save()

    def _track(self, key: str) -> dict[str, Any]:
        with self.record.lock:
            tracks: dict[str, Any] = self._data()["tracks"]
            if key not in tracks:
                tracks[key] = {"generation": 1, "branch": self._branch_name(key, 1),
                               "pending": []}
                self._save()
            found: dict[str, Any] = tracks[key]
            return found

    def _branch_name(self, key: str, generation: int) -> str:
        base = f"combined-{self.name}" + ("" if key == MAIN_TRACK else f"-{key}")
        return base if generation == 1 else f"{base}-r{generation}"

    def combined(self, key: str = MAIN_TRACK) -> str:
        """The name of the track's combined branch now."""
        return str(self._track(key)["branch"])

    def tracks(self) -> list[str]:
        return list(self._data()["tracks"])

    def joined(self, key: str = MAIN_TRACK) -> list[int]:
        """The pieces joined to the track's branch, read from its `Piece:` trailers."""
        branch = self.combined(key)
        if not _exists(self.root, f"refs/heads/{branch}"):
            return []
        code, out, _ = _git(self.root, "log", "--first-parent", "--reverse",
                            "--format=%B%x00", f"refs/heads/{branch}", f"^refs/heads/{MAIN}")
        if code != 0:
            raise IntegrationRefusal(
                f"git log failed while the loop read the joins on {branch}",
                "check the project's git repository, then run.py again")
        found: list[int] = []
        for message in out.split("\0"):
            for number in trailers(message):
                if number not in found:
                    found.append(number)
        return found

    def _all_joined(self) -> set[int]:
        done: set[int] = set()
        for key in self.tracks():
            done |= set(self.joined(key))
        return done

    def worth_knowing(self, text: str, **more: Any) -> None:
        with self.record.lock:
            self._data()["worth_knowing"].append({"text": text, **more})
            self._save()
        self.record.note(f"Worth knowing: {text}")

    # --- the tracks -------------------------------------------------------------------------

    def _isolated(self, number: int, seen: set[int] | None = None) -> bool:
        """An individual piece, and every dependent of one, follows its own branch."""
        seen = seen or set()
        if number in seen:
            return False
        seen.add(number)
        try:
            if self.reader(number).individual:
                return True
        except IntegrationRefusal:
            return False
        return any(self._isolated(d, seen) for d in sorted(self.dependencies.get(number, ())))

    def _track_key(self, number: int) -> str:
        """`main` for a piece in the run's combined branch, else the key of its own branch."""
        if not self._isolated(number):
            return MAIN_TRACK
        try:
            if self.reader(number).individual:
                return f"piece-{number}"
        except IntegrationRefusal:
            pass
        for dep in sorted(self.dependencies.get(number, ())):
            if self._isolated(dep):
                return self._track_key(dep)
        return f"piece-{number}"

    def start(self) -> None:
        """Make sure the main track's combined branch exists, cut from main."""
        with self._lock:
            self._ensure(MAIN_TRACK)

    def _ensure(self, key: str) -> str:
        track = self._track(key)
        branch = str(track["branch"])
        if not _exists(self.root, f"refs/heads/{branch}"):
            if not _exists(self.root, f"refs/heads/{MAIN}"):
                raise IntegrationRefusal(
                    f"there is no branch {MAIN}, so the combined branch cannot be cut",
                    "git branch --list, then run.py --run again")
            with self.gate_lock:
                _must(self.root, f"cut {branch} from {MAIN}", "branch", branch, MAIN)
            self.record.note(f"cut the combined branch {branch} from {MAIN}")
        return branch

    # --- joining ----------------------------------------------------------------------------

    def on_built(self, number: int) -> JoinResult:
        """A piece was built: join it, then every waiting piece whose dependencies joined."""
        result = self.join(number)
        self.drain()
        return result

    def drain(self) -> list[int]:
        """Join each built piece that waits, in run order, until none can join. Returns them."""
        done: list[int] = []
        with self._lock:
            for key in self.tracks():
                self._replay(key)
            progress = True
            while progress:
                progress = False
                joined_now = self._all_joined()
                for number in self.record.with_status(run_record.BUILT):
                    if number in joined_now:
                        continue
                    if self.dependencies.get(number, set()) - joined_now:
                        continue
                    if self.join(number).status == "joined":
                        done.append(number)
                        progress = True
                        break
        return done

    def join(self, number: int) -> JoinResult:
        """Join one piece to its track's combined branch as a trial."""
        with self._lock:
            try:
                return self._join(number)
            except IntegrationRefusal as error:
                self.record.update(number, integration_refused=str(error))
                return JoinResult("refused", number, str(error), error.next_command)

    def _join(self, number: int) -> JoinResult:
        view = self.reader(number)
        if view.state != "review":
            return JoinResult(
                "refused", number,
                f"piece {number} is {view.state} in the gate's record, not review, so it "
                "cannot join", f"gate.py report {number}")
        key = self._track_key(number)
        if number in self.joined(key):
            return JoinResult("already", number, f"piece {number} already joined",
                              branch=self.combined(key))
        unmet = sorted(self.dependencies.get(number, set()) - self._all_joined())
        if unmet:
            return JoinResult(
                "waiting", number,
                f"piece {number} waits for piece {', '.join(str(n) for n in unmet)} to join "
                "first", "the run joins it when its dependencies have joined")
        branch = self._ensure(key)
        head = _must(self.root, "read the combined branch", "rev-parse", f"refs/heads/{branch}")
        return self._trial(number, view, key, branch, head)

    def _scratch(self, head: str) -> Path:
        folder = self.paths.run_dir(self.name) / "trial"
        folder.mkdir(parents=True, exist_ok=True)
        path = Path(tempfile.mkdtemp(prefix="join-", dir=folder)) / "copy"
        with self.gate_lock:
            _must(self.root, "made the scratch copy", "worktree", "add", "-q", "--detach",
                  str(path), head)
        return path

    def _drop(self, path: Path) -> None:
        with self.gate_lock:
            note = remove_worktree(self.root, path)
        if note:
            self.record.note(note)
        with contextlib.suppress(OSError):
            path.parent.rmdir()

    def _merge(self, scratch: Path, ref: str, message: str) -> tuple[bool, list[str]]:
        code, _, _ = _git(
            scratch, "merge", "--no-ff", "--no-verify", "-q", "-m", message, ref,
            config=[*self._identity, *QUIET])
        if code == 0:
            return True, []
        _, listing, _ = _git(scratch, "diff", "--name-only", "--diff-filter=U")
        files = [f for f in listing.splitlines() if f]
        _git(scratch, "merge", "--abort")
        return False, files

    def _trial(self, number: int, view: PieceView, key: str, branch: str,
               head: str) -> JoinResult:
        scratch = self._scratch(head)
        try:
            current = head
            if not _ancestor(self.root, MAIN, head):
                ok, files = self._merge(scratch, MAIN, f"Merge {MAIN} into {branch}")
                if not ok:
                    raise IntegrationRefusal(
                        f"{MAIN} cannot be merged into {branch} (it conflicts in "
                        f"{', '.join(files) or 'some files'}), so no trial can be made",
                        f"look at {branch} and {MAIN}; the combined branch has to be rebuilt "
                        f"from {MAIN}: python3 -m loop.run.integrate leave --run {self.name} "
                        f"--piece <number> --reason <why>")
                current = _must(scratch, "read the scratch copy", "rev-parse", "HEAD")
            title = " ".join(view.title.split())[:60]
            ok, files = self._merge(scratch, f"refs/heads/piece-{number}",
                                    f"Join piece {number}: {title}\n\n{TRAILER_PREFIX}{number}")
            if not ok:
                partners = self._partners(files, current)
                reason = self._conflict_reason(number, branch, files, partners)
                return self._send_back(number, "conflict", reason, branch, head, "")
            trial = _must(scratch, "read the trial commit", "rev-parse", "HEAD")
        finally:
            self._drop(scratch)
        failures, flaky = self._check(trial, current, number, key, branch)
        for item in flaky:
            self._flaky(item, trial)
        if failures:
            reason = self._red_reason(number, branch, failures, self.joined(key))
            result = self._send_back(number, "red", reason, branch, head, trial)
            result.failures = [f.as_dict() for f in failures]
            return result
        if flaky:
            return self._wait_flaky(number, flaky, branch, head, trial)
        with self.gate_lock:
            code, _, err = _git(self.root, "update-ref", "-m", f"join piece {number}",
                                f"refs/heads/{branch}", trial, head)
        if code != 0:
            raise IntegrationRefusal(
                f"the combined branch {branch} moved while the trial ran ({err[:120]}), so the "
                "trial is thrown away", f"run.py --run {self.name} to join again")
        self.record.update(number, joined=trial, joined_to=branch)
        self.record.piece(number).pop("clash", None)
        self.record.note(f"joined piece {number} to {branch} at {trial[:7]}")
        self._save()
        return JoinResult("joined", number, f"piece {number} joined {branch}", trial=trial,
                          head=trial, branch=branch)

    # --- the checks of a trial --------------------------------------------------------------

    def _run(self, command: str, ref: str, extra: Mapping[str, str] | None = None
             ) -> dict[str, Any]:
        try:
            if extra:
                return self.judge_run(command, self.root, ref, extra_files=dict(extra))
            return self.judge_run(command, self.root, ref)
        except judge.JudgeError as error:
            raise IntegrationRefusal(f"a check could not be run ({error}), so the gate cannot "
                                     "tell", error.next_command) from error

    def _plan_checks(self, pieces: Sequence[int], *, held: bool) -> list[Failure]:
        """The checks of each piece as pending failures with a command, none yet run."""
        plans: list[Failure] = []
        for n in pieces:
            view = self.reader(n)
            sp = view.spec
            command = str(sp["judge"]["command"] or "").strip()
            if not command:
                raise IntegrationRefusal(
                    f"the spec of piece {n} holds no judge command, so the check cannot run",
                    f"gate.py report {n}")
            plans.append(Failure(n, "judge", command, f"piece {n} visible judge `{command}`"))
            for check in sp["must_stay_checks"]:
                plans.append(Failure(n, "must-stay", str(check),
                                     f"piece {n} must-stay-the-same check `{check}`"))
            if held:
                for held_command, extra in self.held_runs(view):
                    plans.append(Failure(n, "held-out", held_command,
                                         f"{self._hidden(n)}", extra))
        return plans

    @staticmethod
    def _hidden(number: int) -> str:
        return f"a hidden case of piece {number}"

    def _verdicts(self, plans: Sequence[Failure], ref: str) -> list[Failure]:
        red: list[Failure] = []
        for item in plans:
            verdict = self._run(item.command, ref, item.extra)
            if verdict.get("outcome") != "passed":
                red.append(Failure(item.piece, item.kind, item.command, item.text, item.extra,
                                   str(verdict.get("outcome"))))
        return red

    def _settle(self, red: list[Failure], ref: str) -> tuple[list[Failure], list[Failure]]:
        """Run each red check once more on the same commit. Returns (still red, flaky)."""
        real: list[Failure] = []
        flaky: list[Failure] = []
        for item in red:
            again = self._run(item.command, ref, item.extra)
            if again.get("outcome") == "passed":
                flaky.append(item)
            else:
                real.append(item)
        return real, flaky

    def _check(self, trial: str, parent: str, number: int, key: str, branch: str
               ) -> tuple[list[Failure], list[Failure]]:
        pieces = [*[n for n in self.joined(key) if n != number], number]
        red = self._touches_of_joins(trial, pieces, key)
        red += self._verdicts(self._plan_checks(pieces, held=False), trial)
        touches = [f for f in red if f.kind == "touches"]
        others = [f for f in red if f.kind != "touches"]
        real, flaky = self._settle(others, trial)
        return touches + real, flaky

    def _touches_of_joins(self, trial: str, pieces: Sequence[int], key: str) -> list[Failure]:
        """The files each join commit changed, against the touches of the piece it joined."""
        code, out, _ = _git(self.root, "log", "--first-parent", "--format=%H%x1f%P%x1f%B%x1e",
                            trial, f"^refs/heads/{MAIN}")
        if code != 0:
            raise IntegrationRefusal("git log failed while the loop read the join commits",
                                     "check the project's git repository, then run.py again")
        red: list[Failure] = []
        for row in out.split("\x1e"):
            fields = row.strip().split("\x1f")
            if len(fields) != 3:
                continue
            commit, parents, message = fields
            found = trailers(message)
            parent_list = parents.split()
            if len(found) != 1 or found[0] not in pieces or not parent_list:
                continue
            view = self.reader(found[0])
            sp = view.spec
            outside = touches_faults(
                self.root, parent_list[0], commit,
                allowed=list(sp["links"]["touches"]),
                new_areas=list(sp["changes"]["new_area"]), frozen=view.judge_files)
            if outside:
                shown = ", ".join(outside[:6])
                have = ", ".join(sp["links"]["touches"]) or "none"
                red.append(Failure(found[0], "touches", "touches",
                                   f"piece {found[0]} changed files outside its declared "
                                   f"touches ({have}): {shown}"))
        return red

    def _flaky(self, item: Failure, ref: str) -> None:
        text = (f"{item.text} was red once and passed on the second run of the same commit "
                f"{ref[:7]}, so it is flaky and was not counted as a pass")
        with self.record.lock:
            known = [w for w in self._data()["worth_knowing"] if w.get("check") == item.command
                     and w.get("piece") == item.piece and w.get("commit") == ref]
        if not known:
            self.worth_knowing(text, check=item.command, piece=item.piece, commit=ref)

    def _wait_flaky(self, number: int, flaky: Sequence[Failure], branch: str, head: str,
                    trial: str) -> JoinResult:
        names = "; ".join(f"`{f.command}`" for f in flaky)
        why = (f"a check that is flaky decided the trial of piece {number} ({names}): it was "
               "red once and green on the same commit, so the trial is thrown away and the "
               "piece is not blamed")
        nxt = (f"make the flaky check steady, then run.py --run {self.name} to join piece "
               f"{number} again")
        self.record.set_status(number, run_record.WAITING_PERSON, reason=why, next=nxt)
        return JoinResult("flaky", number, why, nxt, trial=trial, head=head, branch=branch,
                          failures=[f.as_dict() for f in flaky])

    # --- red --------------------------------------------------------------------------------

    def _partners(self, files: Sequence[str], head: str) -> list[int]:
        found: list[int] = []
        for path in files:
            code, out, _ = _git(self.root, "log", "--first-parent", "--format=%B%x00", head,
                                f"^refs/heads/{MAIN}", "--", path)
            if code != 0:
                continue
            for message in out.split("\0"):
                for number in trailers(message):
                    if number not in found:
                        found.append(number)
        return found

    @staticmethod
    def _numbers(numbers: Sequence[int]) -> str:
        return ", ".join(f"piece {n}" for n in numbers)

    def _clip(self, text: str) -> str:
        return text if len(text) <= REASON_LIMIT else text[:REASON_LIMIT - 3].rstrip() + "..."

    def _conflict_reason(self, number: int, branch: str, files: Sequence[str],
                         partners: Sequence[int]) -> str:
        names = ", ".join(files) or "some files"
        who = (f"Those files were last changed by {self._numbers(partners)}. "
               if partners else "")
        return self._clip(
            f"Piece {number} could not join {branch}: the merge conflicts in {names}. {who}"
            "No agent resolves a conflict across pieces, so the trial was thrown away, the "
            "combined branch did not move, and the piece goes back to building. Change the "
            "piece so it does not clash with the joined work, then it joins again.")

    def _red_reason(self, number: int, branch: str, failures: Sequence[Failure],
                    earlier: Sequence[int]) -> str:
        partners = sorted({f.piece for f in failures if f.piece != number})
        if not partners:
            partners = [n for n in earlier if n != number]
        clash = (f"It clashed with {self._numbers(partners)}. " if partners
                 else "No other piece had joined yet. ")
        red = "; ".join(f"{f.text} was red ({f.outcome})" if f.outcome and f.kind != "touches"
                        else f.text for f in failures)
        return self._clip(
            f"Piece {number} turned the trial join into {branch} red. The trial was thrown away "
            f"and the combined branch did not move. {clash}Red: {red}.")

    def _send_back(self, number: int, status: str, reason: str, branch: str, head: str,
                   trial: str) -> JoinResult:
        """The gate's move 8: the culprit goes back to building, with the clash as the reason."""
        with self.gate_lock:
            reply = self.mover(number, "building", reason)
        if not reply.ok:
            why = f"the gate refused to send piece {number} back to building: {reply.message}"
            nxt = reply.next_command or f"gate.py move {number} building --reason <the clash>"
            self.record.set_status(number, run_record.WAITING_PERSON, reason=why, next=nxt)
            return JoinResult("refused", number, why, nxt, trial=trial, head=head, branch=branch)
        landed = str(reply.data.get("to") or "building")
        self.record.update(number, clash=reason)
        if landed == "building":
            self.restart(number)
        else:
            self.record.set_status(number, run_record.SENT_BACK, reason=reason)
        self.record.add_decision(number, "run", f"Sent piece {number} back to {landed} after a "
                                 f"red trial join. {reason}")
        return JoinResult(status, number, reason, trial=trial, head=head, branch=branch,
                          restarted=[number] if landed == "building" else [])

    # --- a piece that leaves ----------------------------------------------------------------

    def leave(self, number: int, reason: str) -> JoinResult:
        """Rebuild the combined branch from main without `number`, under a fresh name.

        The old branch stays as it was. The joins that stay are replayed as trials, in their
        old order. The leaving piece's own move is the caller's: review or the person made it.
        """
        with self._lock:
            key = next((k for k in self.tracks() if number in self.joined(k)), None)
            if key is None:
                return JoinResult("refused", number,
                                  f"piece {number} is not joined to any combined branch",
                                  "python3 -m loop.run.integrate status --run " + self.name)
            keep = [n for n in self.joined(key) if n != number]
            with self.record.lock:
                track = self._track(key)
                old = str(track["branch"])
                track["generation"] = int(track["generation"]) + 1
                track["branch"] = self._branch_name(key, int(track["generation"]))
                track["pending"] = keep
                track.setdefault("retired", []).append(old)
                self._save()
            self.record.update(number, joined=None)
            self.record.note(f"piece {number} left {old} ({reason}); the combined branch is "
                             f"rebuilt from {MAIN} as {track['branch']}")
            self._ensure(key)
            restarted = self._replay(key)
            return JoinResult("rebuilt", number, reason, branch=self.combined(key),
                              restarted=restarted)

    def _replay(self, key: str) -> list[int]:
        """Join the pieces a rebuild still owes, in order. Returns the pieces sent back."""
        sent: list[int] = []
        track = self._track(key)
        for number in list(track.get("pending", [])):
            done = number in self.joined(key)
            if not done:
                result = self.join(number)
                if result.status in ("red", "conflict"):
                    sent.extend(result.restarted)
                elif result.status not in ("joined", "already"):
                    continue  # it waits; the pending list keeps it for the next drain
            with self.record.lock:
                if number in track["pending"]:
                    track["pending"].remove(number)
                self._save()
        return sent

    # --- the end of the run -----------------------------------------------------------------

    def final_check(self, key: str = MAIN_TRACK) -> JoinResult:
        """Run every joined piece's judges again, with the held-out cases, on the branch head."""
        with self._lock:
            branch = self.combined(key)
            pieces = self.joined(key)
            if not pieces:
                return JoinResult("green", 0, f"{branch} holds no piece", branch=branch)
            head = _must(self.root, "read the combined branch", "rev-parse",
                         f"refs/heads/{branch}")
            plans = self._plan_checks(pieces, held=True)
            counts = {"pieces": list(pieces), "held_out": sum(p.kind == "held-out" for p in plans),
                      "checks": len(plans)}
            red = self._verdicts(plans, head)
            real, flaky = self._settle(red, head)
            for item in flaky:
                self._flaky(item, head)
            if not real and flaky:
                names = "; ".join(f"`{f.command}`" for f in flaky)
                return JoinResult(
                    "flaky", 0, f"a flaky check decided the final check ({names}), so it is "
                    "not a pass", f"make the check steady, then run.py --run {self.name}",
                    branch=branch, head=head)
            if not real:
                return JoinResult("green", 0, f"the final combined check of {branch} is green",
                                  branch=branch, head=head, info=counts)
            culprits = sorted({f.piece for f in real})
            restarted: list[int] = []
            for number in culprits:
                mine = [f for f in real if f.piece == number]
                kinds = ", ".join(sorted({f.kind for f in mine}))
                hidden = [f for f in mine if f.kind == "held-out"]
                said = "; ".join(f.text if f.kind != "held-out" else
                                 f"{len([f for f in hidden])} hidden case(s) failed"
                                 for f in mine[:1]) or kinds
                reason = self._clip(
                    f"Piece {number} failed the final combined check of {branch} ({kinds}): "
                    f"{said}. The piece leaves the combined branch through a rebuild from "
                    f"{MAIN}, and goes back to building.")
                self.leave(number, reason)
                with self.gate_lock:
                    reply = self.mover(number, "building", reason)
                if not reply.ok:
                    why = ("the gate refused to send piece "
                           f"{number} back to building: {reply.message}")
                    self.record.set_status(
                        number, run_record.WAITING_PERSON, reason=why,
                        next=reply.next_command or f"gate.py move {number} building "
                        "--reason <the failure>")
                    continue
                self.record.update(number, clash=reason)
                if str(reply.data.get("to") or "building") == "building":
                    self.restart(number)
                    restarted.append(number)
                else:
                    self.record.set_status(number, run_record.SENT_BACK, reason=reason)
            return JoinResult("red", 0, f"the final combined check of {branch} was red",
                              branch=branch, head=head, restarted=restarted,
                              failures=[f.as_dict() for f in real])

    def _push(self, key: str, branch: str) -> dict[str, Any]:
        try:
            done = self.push(branch)
        except github.NoApp as error:
            return {"push": "waiting", "next": error.next_command, "message": error.message}
        except github.GitHubError as error:
            return {"push": "refused", "next": error.next_command, "message": error.message}
        return {"push": "pushed", "scanned": done.get("scanned"), "to": done.get("to", "")}

    def finish(self) -> dict[str, dict[str, Any]]:
        """For each track that holds a piece: the docs commit, the final check, the push."""
        report: dict[str, dict[str, Any]] = {}
        with self._lock:
            self.drain()
            for key in self.tracks():
                if not self.joined(key):
                    continue
                for _ in range(FINAL_ROUNDS):
                    entry = self._finish_one(key)
                    if entry["status"] != "red" or entry.get("restarted"):
                        break
                report[key] = entry
            with self.record.lock:
                self._data()["final"] = {k: {x: y for x, y in v.items() if x != "failures"}
                                         for k, v in report.items()}
                self._save()
        return report

    def _finish_one(self, key: str) -> dict[str, Any]:
        branch = self.combined(key)
        entry: dict[str, Any] = {"branch": branch}
        try:
            self._docs(key, branch)
            result = self.final_check(key)
        except IntegrationRefusal as error:
            entry.update(status="refused", message=str(error), next=error.next_command)
            return entry
        branch = self.combined(key)  # a rebuild may have changed it
        entry.update(branch=branch, status=result.status, message=result.message,
                     head=result.head, restarted=result.restarted, failures=result.failures,
                     checked=result.info)
        if result.status != "green":
            entry["next"] = result.next_command or (
                "the run joins the rebuilt pieces, then checks again")
            return entry
        entry.update(self._push(key, branch))
        if entry.get("push") in ("waiting", "refused"):
            first = self.joined(key)[0]
            self.record.update(first, github_next=str(entry.get("next", "")))
        return entry

    def _docs(self, key: str, branch: str) -> None:
        pieces = [self.reader(n) for n in self.joined(key)]
        self.docs_commit(root=self.root, paths=self.paths, branch=branch, pieces=pieces,
                         run=self.name, gate_lock=self.gate_lock, identity=self._identity)


# --- the hooks ------------------------------------------------------------------------------

_INTEGRATORS: dict[tuple[str, str], Integrator] = {}


def _dependencies(context: Any) -> dict[int, set[int]]:
    infos: Mapping[int, Any] = getattr(context, "infos", {}) or {}
    by_issue = {i.issue: i.number for i in infos.values() if getattr(i, "issue", None)}
    found: dict[int, set[int]] = {}
    for number, info in infos.items():
        found[number] = {by_issue[b] for b in getattr(info, "blockers", ())
                         if b in by_issue and by_issue[b] != number}
    return found


def integrator_for(context: Any) -> Integrator:
    key = (str(context.paths.root), str(context.name))
    made = _INTEGRATORS.get(key)
    if made is None:
        made = Integrator(
            context.paths, context.name, context.record, context.policy,
            restart=getattr(context, "restart_piece", None),
            gate_lock=getattr(context, "gate_lock", None),
            dependencies=_dependencies(context))
        _INTEGRATORS[key] = made
    return made


def run_hook(context: Any, event: str, **data: Any) -> None:
    """The engine's hook. `start` and `piece-built` join; `built-all` finishes the run."""
    if event not in ("start", "piece-built", "built-all"):
        return
    loop = integrator_for(context)
    if event == "start":
        loop.start()
        loop.drain()
    elif event == "piece-built":
        loop.on_built(int(data["piece"]))
    else:
        for entry in loop.finish().values():
            if entry["status"] == "refused":
                raise IntegrationRefusal(str(entry.get("message")), str(entry.get("next", "")))
            if entry.get("push") == "refused":
                raise IntegrationRefusal(str(entry.get("message")), str(entry.get("next", "")))


# --- a door for tests and the person ----------------------------------------------------------


def _paths_for(args: argparse.Namespace) -> Paths:
    from loop.paths import find_project_root

    return Paths.for_project(find_project_root(Path.cwd()))


def main(argv: list[str]) -> int:
    """`status`, `leave` and `final`, over a run record. The run script is not needed."""
    parser = argparse.ArgumentParser(prog="python3 -m loop.run.integrate",
                                     description="Look at or change a run's combined branch.")
    parser.add_argument("command", choices=("status", "leave", "final"))
    parser.add_argument("--run", required=True)
    parser.add_argument("--piece", type=int)
    parser.add_argument("--reason", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        paths = _paths_for(args)
        run = run_record.RunRecord.load(paths, args.run)
        from loop import policy as policy_module

        loaded = (policy_module.load(paths.policy_file) if paths.policy_file.exists()
                  else policy_module.with_defaults({}))
        loop = Integrator(paths, args.run, run, loaded)
        out: dict[str, Any]
        if args.command == "status":
            out = {"ok": True, "tracks": {k: {"branch": loop.combined(k),
                                               "joined": loop.joined(k)}
                                          for k in loop.tracks()}}
        elif args.command == "leave":
            if args.piece is None or not args.reason:
                print("leave needs --piece and --reason\nnext: python3 -m loop.run.integrate "
                      "leave --run NAME --piece N --reason WHY", file=sys.stderr)
                return int(ExitCode.USAGE)
            result = loop.leave(args.piece, args.reason)
            out = {"ok": result.status == "rebuilt", "status": result.status,
                   "branch": result.branch, "message": result.message}
        else:
            out = {"ok": True, "final": loop.finish()}
        print(json.dumps(out, sort_keys=True))
        return int(ExitCode.OK) if out.get("ok") else int(ExitCode.REFUSED)
    except (run_record.RecordError, IntegrationRefusal) as error:
        nxt = getattr(error, "next_command", "")
        print(f"{error}\nnext: {nxt}", file=sys.stderr)
        return int(ExitCode.REFUSED)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
