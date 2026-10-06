"""The run loop: claim pieces as slots free up, build each attempt by attempt, route outcomes.

The engine is plain code, not an agent. It starts every builder as a separate `claude -p`
session (`loop.sessions`), reads the hand-off it left, and asks the gate (`gate.py`) to judge. It
never writes a label or a piece record: every state move goes through the gate. It keeps the run
record (`loop.run.record`), which says what is done, so a run killed and started again resumes
without redoing a finished piece.

What the engine never does is let a check pass that did not run. A git error, a record that
cannot be read, a session that could not start, or a gate that refused without judging is a
refusal or a park, and each names its next command.

Threads: one worker thread per building piece runs the sessions. The main thread claims pieces,
reaps workers, writes the heartbeat and calls the hooks. Every call to the gate and to git goes
through one lock, so two threads never move the repository at once.
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.util
import json
import os
import re
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loop import attempt_log, bar, github, moves, sessions, spec
from loop.gates import CheckContext
from loop.gates import attempt as attempt_gate
from loop.paths import Paths
from loop.run import attempts, plan, record, summary
from loop.run.gateway import Gateway
from loop.states import by_number

OPTIONAL_MODULES = ("watch", "inbox", "integrate", "review", "pull_request")
EVENTS = ("start", "tick", "session-ended", "piece-built", "built-all", "run-end")
NO_HYPOTHESIS = "This piece has no hypothesis list. Build what the spec asks for."
HEARTBEAT_SECONDS = 1.0


class EngineRefusal(Exception):
    """The run cannot go on. The message names the next command."""

    def __init__(self, message: str, next_command: str) -> None:
        super().__init__(message)
        self.next_command = next_command


@dataclass
class Outcome:
    status: str  # finished, stopped or parked
    code: int  # 0 finished; 3 stopped or parked; 1 a problem was recorded
    next_command: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class HookContext:
    """What a hook module gets: the run's paths, name, record and policy."""

    paths: Paths
    name: str
    record: record.RunRecord
    policy: Mapping[str, Any]
    resume_piece: Callable[[int], None]


def slug(title: str) -> str:
    words = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return words[:28].strip("-") or "piece"


# --- reading the pieces -------------------------------------------------------------


def read_infos(paths: Paths, numbers: Sequence[int], hub: github.GitHub) -> list[plan.PieceInfo]:
    """The plan's view of each piece: its areas and, with the App, its blockers."""
    infos: list[plan.PieceInfo] = []
    for number in numbers:
        piece = moves.read_piece(paths, number)
        if piece is None:
            raise EngineRefusal(f"piece {number} is not in the gate's record",
                                "gate.py report")
        try:
            parsed = spec.parse(piece.body).to_dict()
        except spec.SpecError as error:
            raise EngineRefusal(f"the spec of piece {number} cannot be read ({error})",
                                f"gate.py report {number}") from error
        if not parsed["found"]:
            raise EngineRefusal(f"piece {number} has no spec block", f"gate.py report {number}")
        areas = frozenset(t for t in parsed["links"]["touches"] if t.lower() != "none")
        blockers: set[int] = set()
        if piece.issue is not None and hub.available:
            try:
                linked = hub.api_json(
                    f"repos/{{owner}}/{{repo}}/issues/{piece.issue}/dependencies/blocked_by")
            except github.GitHubError as error:
                raise EngineRefusal(
                    f"the blocked-by links of piece {number} cannot be read ({error.message}), "
                    "so the order cannot be planned", error.next_command) from error
            blockers = {int(i["number"]) for i in linked if isinstance(i, dict) and "number" in i}
        infos.append(plan.PieceInfo(number=number, title=piece.title, issue=piece.issue,
                                    areas=areas, blockers=frozenset(blockers)))
    return infos


# --- the engine ---------------------------------------------------------------------


class Engine:
    def __init__(
        self,
        paths: Paths,
        name: str,
        run: record.RunRecord,
        policy: Mapping[str, Any],
        infos: Sequence[plan.PieceInfo],
        *,
        slot_count: int,
        gateway: Gateway | None = None,
        hub: github.GitHub | None = None,
        env: Mapping[str, str] | None = None,
        tick_seconds: float = 0.25,
        start_session: Callable[[sessions.Session], sessions.Result] | None = None,
    ) -> None:
        self.paths = paths
        self.name = name
        self.record = run
        self.policy = policy
        self.infos = {i.number: i for i in infos}
        self.slot_count = max(1, slot_count)
        self.plan = plan.make_plan(infos, slots=self.slot_count)
        self.gateway = gateway or Gateway(paths)
        self.hub = hub or github.GitHub(paths)
        self.env = dict(os.environ if env is None else env)
        self.tick_seconds = tick_seconds
        self.limit = int(policy["attempt_limit"])
        billing = policy["billing"]
        self.cap_piece: float | None = billing.get("spend_cap_per_piece_usd")
        self.cap_run: float | None = billing.get("spend_cap_per_run_usd")
        self._start = start_session or self._start_session
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.gate_lock = threading.RLock()
        self.workers: dict[int, threading.Thread] = {}
        self.resume_queue: list[int] = []
        self.refused: dict[int, str] = {}  # pending pieces the claim refused, until something moves
        self.run_parked = ""  # why the run is parked at a spend cap, or ""
        self.failed = False  # a hook or a worker raised: the run ends with a failure
        self._procs: set[subprocess.Popen[str]] = set()
        self._proc_lock = threading.Lock()
        self._last_beat = 0.0
        self._template: Path | None = None
        self._hooks_cache: dict[str, Any] = {}

    # --- hooks -----------------------------------------------------------------------

    def _modules(self) -> list[Any]:
        found: list[Any] = []
        for name in OPTIONAL_MODULES:
            if name in self._hooks_cache:
                module = self._hooks_cache[name]
            else:
                module = None
                if importlib.util.find_spec(f"loop.run.{name}") is not None:
                    module = importlib.import_module(f"loop.run.{name}")
                self._hooks_cache[name] = module
            if module is not None and hasattr(module, "run_hook"):
                found.append(module)
        return found

    def context(self) -> HookContext:
        return HookContext(self.paths, self.name, self.record, self.policy, self.resume_piece)

    def hook(self, event: str, **data: Any) -> None:
        if event not in EVENTS:
            raise ValueError(f"{event!r} is not a run event")
        try:
            modules = self._modules()
        except (ImportError, ValueError) as error:
            self._problem(f"an optional run module cannot be loaded ({error})")
            return
        for module in modules:
            try:
                module.run_hook(self.context(), event, **data)
            except Exception as error:
                self._problem(f"{module.__name__} failed at {event}: "
                              f"{type(error).__name__}: {error}")

    def _problem(self, text: str) -> None:
        self.failed = True
        self.record.problem(text)

    def resume_piece(self, number: int) -> None:
        """A hook (the inbox, P22) asks for a parked piece to go on."""
        with self.gate_lock:
            if self.record.status(number) == record.PARKED_PERSON:
                self.record.set_status(number, record.BUILDING)
                self.resume_queue.append(number)
                self.wake.set()

    # --- reading the gate ------------------------------------------------------------

    def _read(self, number: int) -> moves.Piece:
        try:
            piece = moves.read_piece(self.paths, number)
        except moves.MoveError as error:
            raise EngineRefusal(str(error), error.next_command) from error
        if piece is None:
            raise EngineRefusal(f"piece {number} is not in the gate's record", "gate.py report")
        return piece

    # --- the loop --------------------------------------------------------------------

    def run(self) -> Outcome:
        self._reset_waiting()
        self._write_template()
        self.hook("start")
        self._reconcile_all()
        try:
            while True:
                self._tick()
                self._reap()
                if not self.stop.is_set():
                    self._check_run_cap()
                    if not self.run_parked:
                        self._launch()
                if not self.workers:
                    break
                self.wake.wait(self.tick_seconds)
                self.wake.clear()
        finally:
            for thread in list(self.workers.values()):
                thread.join()
        return self._finish()

    def _tick(self) -> None:
        now = time.monotonic()
        if now - self._last_beat >= HEARTBEAT_SECONDS:
            record.beat(self.paths, self.name)
            self._last_beat = now
        self.hook("tick")

    def _reap(self) -> None:
        done = [n for n, thread in self.workers.items() if not thread.is_alive()]
        for number in done:
            self.workers.pop(number).join()
            self.refused.clear()  # a slot or an area may be free now

    def _reset_waiting(self) -> None:
        """A run started again tries the pieces that only waited, from the start."""
        for number in self.record.with_status(record.WAITING, record.WAITING_PERSON,
                                              record.STOPPED):
            self.record.set_status(number, record.PENDING)

    def _check_run_cap(self) -> None:
        if self.run_parked:
            return
        reached = self.record.cap_reached(per_piece=None, per_run=self.cap_run, piece=-1) \
            if self.cap_run is not None else None
        if reached:
            self._park_run(reached)

    def _park_run(self, why: str) -> None:
        if not self.run_parked:
            self.run_parked = why
            self.record.note(f"the run is parked: {why}")
            self.record.add_decision(None, "run", f"Parked the run, since {why}.")

    # --- launching -------------------------------------------------------------------

    def _occupied(self) -> list[int]:
        held = set(self.workers) | set(self.resume_queue)
        held |= set(self.record.with_status(record.PARKED_PERSON, record.PARKED_SPEND))
        return sorted(held)

    def _launch(self) -> None:
        free = self.slot_count - len(self.workers)
        while free > 0 and self.resume_queue:
            self._start_worker(self.resume_queue.pop(0))
            free -= 1
        if free <= 0:
            return
        pending = [n for n in self.record.with_status(record.PENDING) if n not in self.refused]
        built = self.record.with_status(record.BUILT)
        chosen = plan.runnable(self.infos.values(), order=self.plan.order, pending=pending,
                               built=built, occupied=self._occupied(), free_slots=free)
        for number in chosen:
            if self.stop.is_set() or self.run_parked:
                return
            if self._claim(number):
                self._start_worker(number)
                free -= 1

    def _claim(self, number: int) -> bool:
        try:
            piece = self._read(number)
        except EngineRefusal as error:
            self._wait_person(number, str(error), error.next_command)
            return False
        if piece.issue is not None and not self.hub.available:
            self._wait_person(
                number,
                "the piece has an issue, and reading its blocked-by links is a GitHub step: "
                "the gate's App is not set up yet",
                github.sync_command(self.paths.root))
            return False
        earlier = sorted(
            i for n in self.record.with_status(record.BUILT)
            if (i := self.infos[n].issue) is not None)
        options = {"built_earlier": ",".join(str(i) for i in earlier)} if earlier else None
        with self.gate_lock:
            reply = self.gateway.move(number, "building", options=options)
        if reply.ok:
            if reply.data.get("github") == "queued":
                self.record.update(number, github_next=str(reply.data.get("next", "")))
            self.record.set_status(number, record.BUILDING)
            if options:
                self.record.add_decision(
                    number, "run",
                    f"Claimed piece {number} with built_earlier={options['built_earlier']}: "
                    "those pieces were built earlier in this run.")
            return True
        if reply.data.get("sent_back"):
            self.record.set_status(number, record.SENT_BACK, reason=reply.message,
                                   next=reply.next_command)
            self.wake.set()
            return False
        if reply.code == 4 or reply.code not in (3,):
            self._wait_person(number, reply.message, reply.next_command)
            return False
        # A refusal that keeps the piece ready: no slot, an area in use, a blocker. Wait.
        self.refused[number] = reply.message
        self.record.update(number, reason=reply.message, next=reply.next_command)
        return False

    def _wait_person(self, number: int, why: str, next_command: str) -> None:
        self.record.set_status(number, record.WAITING_PERSON, reason=why, next=next_command)

    def _start_worker(self, number: int) -> None:
        thread = threading.Thread(target=self._worker, args=(number,),
                                  name=f"piece-{number}", daemon=False)
        self.workers[number] = thread
        thread.start()

    # --- reconcile (resume) ----------------------------------------------------------

    def _reconcile_all(self) -> None:
        for number in self.record.resumable():
            self._reconcile(number)

    def _reconcile(self, number: int) -> None:
        """Where the gate's record is ahead of the run record, the gate wins."""
        status = self.record.status(number)
        try:
            state = self._read(number).state
        except EngineRefusal as error:
            self._wait_person(number, str(error), error.next_command)
            return
        if state == "building":
            if status == record.PENDING:
                self.record.set_status(number, record.BUILDING)
            self.resume_queue.append(number)
            self.record.note(f"piece {number} was building when the run started again, "
                             "so its builder goes on")
        elif state == "review":
            self.record.set_status(number, record.BUILDING)
            self.resume_queue.append(number)  # the worker sees the state and finishes it
        elif state == "ready":
            if status in (record.BUILDING, record.PARKED_SPEND):
                self.record.set_status(number, record.PENDING)
        else:
            self.record.set_status(number, record.SENT_BACK,
                                   reason=f"the gate says the piece is {state}")

    # --- the worker ------------------------------------------------------------------

    def _worker(self, number: int) -> None:
        try:
            self._build(number)
        except EngineRefusal as error:
            self._wait_person(number, str(error), error.next_command)
        except Exception as error:  # a fault in the run itself: park, never pass
            self._problem(f"piece {number}: {type(error).__name__}: {error}")
            self._wait_person(number, f"the run hit a fault: {type(error).__name__}: {error}",
                              f"read the problem in {self.paths.run_record(self.name)}, "
                              f"then run.py --run {self.name}")
        finally:
            self.wake.set()

    def _worktree(self, number: int) -> Path:
        info = self.infos[number]
        held = self.record.piece(number)
        name = str(held.get("worktree") or f"{number}-{slug(info.title)}")
        branch = f"piece-{number}"
        folder = self.paths.worktrees_dir / name
        with self.gate_lock:
            if not held.get("branch"):
                reply = self.gateway.branch(number)
                if not reply.ok:
                    raise EngineRefusal(f"the piece branch could not be made: {reply.message}",
                                        reply.next_command or f"gate.py branch {number}")
            code, text = self.gateway.open_worktree(name, branch, "main",
                                                    resume=folder.exists())
        if code != 0:
            raise EngineRefusal(f"the worktree could not be opened: {text}",
                                f"look at {folder}, then run.py --run {self.name}")
        self.record.update(number, branch=branch, worktree=name)
        return folder

    def _build(self, number: int) -> None:
        piece = self._read(number)
        if piece.state == "review":
            self._finish_piece(number)
            return
        folder = self._worktree(number)
        while True:
            if self.stop.is_set():
                self._stopped(number)
                return
            piece = self._read(number)
            used = attempt_log.used(piece.record)
            self.record.update(number, attempts=used)
            if piece.state != "building":
                raise EngineRefusal(
                    f"piece {number} is {piece.state} in the gate's record, not building",
                    f"gate.py report {number}")
            if used >= self.limit:
                raise EngineRefusal(
                    f"piece {number} has used {used} of {self.limit} attempts and is still "
                    "building, so the gate did not send it back",
                    f"gate.py move {number} shaping --reason \"<the attempts ran out>\"")
            budget = self._budget(number)
            if budget == "parked":
                return
            result = self._session(number, folder, piece, budget)
            if result is None:
                return
            self.hook("session-ended", piece=number, result=result)
            if self.stop.is_set():
                self._stopped(number)
                return
            route = attempts.route_handoff(result.handoff, result.exit_code)
            if result.handoff_error:
                self.record.note(f"piece {number}: the hand-off could not be read "
                                 f"({result.handoff_error})")
            if result.handoff is not None and result.handoff["outcome"] == "done":
                for text in result.handoff.get("decisions", []):
                    self.record.add_decision(number, "builder", text)
                self.record.update(number, summary=str(result.handoff["summary"]))
            if self._act(number, route) != "again":
                return

    def _budget(self, number: int) -> float | None | str:
        """The cost cap for the next session, None for no cap, or "parked"."""
        if self.run_parked:
            self.record.set_status(number, record.PARKED_SPEND, reason=self.run_parked,
                                   next=self._cap_next())
            return "parked"
        reached = self.record.cap_reached(per_piece=self.cap_piece, per_run=self.cap_run,
                                          piece=number)
        if reached:
            self._park_run(reached)
            self.record.set_status(number, record.PARKED_SPEND, reason=reached,
                                   next=self._cap_next())
            return "parked"
        left: list[float] = []
        if self.cap_piece is not None:
            left.append(self.cap_piece - self.record.spend_piece(number))
        if self.cap_run is not None:
            left.append(self.cap_run - self.record.spend_total())
        return min(left) if left else None

    def _cap_next(self) -> str:
        return (f"raise billing.spend_cap_per_piece_usd or billing.spend_cap_per_run_usd in "
                f"{self.paths.policy_file}, then run.py --run {self.name} to go on")

    # --- the session -----------------------------------------------------------------

    def _write_template(self) -> None:
        template = self.paths.kit_dir / "templates" / "builder-settings.json"
        allow = self.paths.agents_dir / "loop" / "network-allowlist.json"
        if not allow.is_file():
            self.record.note("there is no network allowlist file, so builders keep the "
                             "template's package registry hosts only")
            self._template = template
            return
        try:
            hosts = json.loads(allow.read_text(encoding="utf-8"))["allowedDomains"]
            if not isinstance(hosts, list) or not all(isinstance(h, str) for h in hosts):
                raise ValueError("allowedDomains must be a list of host names")
            data = json.loads(template.read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise EngineRefusal(
                f"the network allowlist {allow} cannot be used ({error})",
                "run /setup again to write it, then run.py again") from error
        data["sandbox"]["network"]["allowedDomains"] = hosts
        target = self.paths.run_dir(self.name) / "settings-template.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._template = target

    def _bar_paths(self, number: int, piece: moves.Piece) -> list[str]:
        try:
            parsed = spec.parse(piece.body).to_dict()
            recorded = next(
                (e["fingerprint"] for e in reversed(piece.record)
                 if e.get("kind") == "fingerprint"), None)
            if recorded is None:
                raise EngineRefusal("the piece record holds no fingerprint, so the frozen bar "
                                    "cannot be listed", f"gate.py report {number}")
            ctx = CheckContext(number=number, move=by_number(5), origin="building",
                               target="review", reason=None, title=piece.title, body=piece.body,
                               spec=parsed, record=piece.record, paths=self.paths, options={})
            facts = attempt_gate._facts(ctx, parsed, recorded)
            return bar.paths(self.paths.root, facts.base, facts.judge_files)
        except (spec.SpecError, attempt_gate.Refusal, bar.BarError) as error:
            raise EngineRefusal(
                f"the frozen bar of piece {number} cannot be listed ({error})",
                getattr(error, "next_command", "") or f"gate.py report {number}") from error

    def _session(self, number: int, folder: Path, piece: moves.Piece,
                 budget: float | None | str) -> sessions.Result | None:
        count = int(self.record.piece(number).get("sessions", 0)) + 1
        self.record.update(number, sessions=count)
        brief_template = (self.paths.kit_dir / "briefs" / "builder.md").read_text(encoding="utf-8")
        try:
            brief = sessions.render_brief(
                brief_template,
                trusted={"PIECE": str(number),
                         "HANDOFF_COMMAND": sessions.handoff_command(self.paths.kit_dir)},
                outside={"spec": piece.body, "attempt_log": attempt_log.render(piece.record),
                         "hypothesis": NO_HYPOTHESIS})
            barred = self._bar_paths(number, piece)
            session = sessions.plan(
                self.paths, run=self.name, label=f"p{number}-a{count}", worktree=folder,
                brief=brief, max_budget_usd=budget if isinstance(budget, float) else None,
                env=self.env, settings_template=self._template, bar_paths=barred)
        except sessions.SessionError as error:
            self._act(number, attempts.Route(
                "give-back", 7, "ready",
                reason=f"the builder session could not be planned: {error}"))
            return None
        began = time.time()
        try:
            result = self._start(session)
        except sessions.SessionError as error:
            self._act(number, attempts.Route(
                "give-back", 7, "ready",
                reason=f"the builder session could not start: {error}"))
            return None
        windows = list(self.record.piece(number).get("windows", []))
        windows.append([began, time.time()])
        self.record.update(number, windows=windows)
        self._spend(number, result)
        return result

    def _start_session(self, session: sessions.Session) -> sessions.Result:
        return sessions.start(session, runner=self._run_tracked)

    def _run_tracked(self, argv: Sequence[str], **options: Any) -> subprocess.CompletedProcess[str]:
        """Run a session so that a stop signal can end it. The child has a group of its own."""
        proc = subprocess.Popen(
            list(argv), cwd=options["cwd"], env=options["env"], stdin=options["stdin"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        with self._proc_lock:
            self._procs.add(proc)
            if self.stop.is_set():
                self._end(proc)
        try:
            out, err = proc.communicate()
        finally:
            with self._proc_lock:
                self._procs.discard(proc)
        return subprocess.CompletedProcess(list(argv), proc.returncode, out, err)

    @staticmethod
    def _end(proc: subprocess.Popen[str]) -> None:
        with contextlib.suppress(OSError):
            os.killpg(proc.pid, signal.SIGTERM)

    def request_stop(self) -> None:
        """A stop signal: no new session starts, and a running one is ended."""
        self.stop.set()
        with self._proc_lock:
            for proc in list(self._procs):
                self._end(proc)
        self.wake.set()

    def _spend(self, number: int, result: sessions.Result) -> None:
        output = result.output or {}
        cost = output.get("total_cost_usd")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost >= 0:
            self.record.add_spend(number, float(cost))
        usage = output.get("usage")
        if isinstance(usage, dict):
            self.record.add_tokens(number, {k: v for k, v in usage.items()
                                            if isinstance(v, int) and not isinstance(v, bool)})

    # --- acting on a route -----------------------------------------------------------

    def _act(self, number: int, route: attempts.Route) -> str:
        """Make the route's move through the gate. Returns "again" to start the next attempt."""
        if route.action == "judge":
            return self._judge(number, route)
        if route.action == "park-person":
            self.record.set_status(
                number, record.PARKED_PERSON, question=route.reason,
                next=f"answer the question: gate.py answer {number} --question <it> --answer "
                "<yours> --by <you>, then gate.py move "
                f"{number} ready (an answer in this run resumes the piece)")
            return "done"
        target = route.target or ""
        with self.gate_lock:
            reply = self.gateway.move(number, target, reason=route.reason)
        if not reply.ok:
            self._wait_person(number, f"the gate refused move {route.move}: {reply.message}",
                              reply.next_command)
            return "done"
        if route.action == "send-back":
            self.record.set_status(number, record.SENT_BACK, reason=route.reason)
            if "no real improvement" in route.reason.lower():
                self.record.add_decision(number, "run",
                                         "Stopped the attempts early: no real improvement. "
                                         "Sent the piece back to shaping by move 6.")
        else:
            self.record.set_status(number, record.RETURNED, reason=route.reason)
            self.record.add_decision(number, "run", f"Gave the piece back to ready: {route.reason}")
        return "done"

    def _judge(self, number: int, route: attempts.Route) -> str:
        before = attempt_log.used(self._read(number).record)
        if route.reason:
            self.record.note(f"piece {number}: {route.reason}")
        with self.gate_lock:
            reply = self.gateway.move(number, "review")
        after = self._read(number)
        judged = attempts.Judged(
            passed=reply.ok, sent_back=bool(reply.data.get("sent_back")),
            counted=attempt_log.used(after.record) > before,
            attempts=attempt_log.attempts(after.record), limit=self.limit,
            next_command=reply.next_command, message=reply.message)
        self.record.update(number, attempts=attempt_log.used(after.record))
        step = attempts.route_judged(judged)
        if step.action == "built":
            self._finish_piece(number)
            return "done"
        if step.action == "sent-back":
            self.record.set_status(number, record.SENT_BACK, reason=step.reason or reply.message,
                                   next=reply.next_command)
            return "done"
        if step.action == "wait-person":
            self._wait_person(number, step.reason, step.next_command)
            return "done"
        if step.action == "send-back":
            return self._act(number, step)
        return "again"

    def _finish_piece(self, number: int) -> None:
        """After move 5: the trim pass, which never fails the piece, then built."""
        if not self.record.piece(number).get("trimmed"):
            reply = self.gateway.trim(number, self.name, self._budget_for_trim(number))
            outcome = str(reply.data.get("outcome", f"exit code {reply.code}"))
            if not reply.ok:
                self.record.note(f"piece {number}: the trim pass went on untrimmed "
                                 f"({outcome}: {reply.message})")
            self.record.update(number, trimmed=True, trim=outcome)
        self.record.set_status(number, record.BUILT)
        self.hook("piece-built", piece=number)

    def _budget_for_trim(self, number: int) -> float | None:
        left: list[float] = []
        if self.cap_piece is not None:
            left.append(self.cap_piece - self.record.spend_piece(number))
        if self.cap_run is not None:
            left.append(self.cap_run - self.record.spend_total())
        positive = [x for x in left if x > 0]
        return min(positive) if positive else None

    def _stopped(self, number: int) -> None:
        """A stop signal: the building piece goes back to ready, and its branch is kept."""
        reason = (f"the run {self.name} was stopped by a signal, so piece {number} goes back to "
                  f"ready. Its branch piece-{number} and its worktree are kept")
        with self.gate_lock:
            reply = self.gateway.move(number, "ready", reason=reason)
        if reply.ok:
            self.record.set_status(number, record.STOPPED, reason=reason)
        else:
            self._wait_person(number, f"the stop could not give the piece back: {reply.message}",
                              reply.next_command)

    # --- the end ---------------------------------------------------------------------

    def _finish(self) -> Outcome:
        for number in self.record.with_status(record.PENDING):
            why = self.refused.get(number) or self._unmet(number)
            self.record.set_status(number, record.WAITING, reason=why)
        if not self.stop.is_set() and not self.run_parked:
            self.hook("built-all", built=self.record.with_status(record.BUILT))
        if self.stop.is_set():
            status, code = record.RUN_STOPPED, 3
            next_command = f"run.py --run {self.name} to go on from the run record"
        elif self.run_parked:
            status, code = record.RUN_PARKED, 3
            next_command = self._cap_next()
        else:
            status, code = record.FINISHED, 0
            next_command = self._finished_next()
        self.hook("run-end", status=status)
        if self.failed:
            code = 1
        self.record.set_run_status(status, ended=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        written = summary.write(self.record)
        return Outcome(status, code, next_command, {"summary": str(written)})

    def _unmet(self, number: int) -> str:
        needs = [b for b in self.infos[number].blockers]
        by_issue = {i.issue: i.number for i in self.infos.values() if i.issue is not None}
        for blocker in needs:
            other = by_issue.get(blocker)
            if other is not None and self.record.status(other) != record.BUILT:
                return (f"it waits for piece {other}, which is "
                        f"{self.record.status(other)}, not built")
        return "no slot or area came free for it before the run ended"

    def _finished_next(self) -> str:
        waiting = [n for n in self.record.numbers() if self.record.status(n) in (
            record.WAITING_PERSON, record.PARKED_PERSON)]
        queued = [n for n in self.record.numbers() if self.record.piece(n).get("github_next")]
        if waiting:
            first = self.record.piece(waiting[0])
            return str(first.get("next") or f"read the summary: piece {waiting[0]} waits for you")
        if queued:
            return str(self.record.piece(queued[0])["github_next"])
        return "read the morning summary in the run folder"
