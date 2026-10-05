#!/usr/bin/env python3
"""run.py: drive the build loop for a piece, one attempt at a time.

    python3 run.py start <number> [--run <name>]
    python3 run.py next <number> --run <name> [--worktree <folder>]
    python3 run.py started <number> --run <name> --agent <id>
    python3 run.py ended <number> --run <name>

Run it from the project's folder or a worktree of it. The run record is
.agents/runs/<run name>/run.json in the main folder, the first folder
`git worktree list` names, beside the gate's own status for each piece.

This script never starts a model session. For each attempt it writes a start
request into the run record, naming the piece, the attempt number, the
worktree, the brief and the result file the builder writes, and prints it on a
line that starts with `request:`. The coordinating session starts a fresh
builder for it with its own subagent tool, on the route the section-builder
skill's references/task-context-capabilities.md names, and writes the
builder's id back with `started`. When the builder ends, `ended` reads the
result and hands it to the gate, `.agents/tools/gate.py result`, which takes
the status's route.

start claims the piece through the gate in a run of its own, named
solo-<number>-<date>-<time>, or adds it to the run --run names. On a piece the
run record already holds as building it makes no new claim: it resumes, routes
any result that was saved but not routed, and keeps the attempt count, which
is the number of attempt notes in .agents/pieces/<number>/.

A failed attempt is a done whose checks fail when the gate runs them, or no
result once the builder is known to have ended. Its note is written by
attempt-note.py, its work is kept by recovery.py preserve, and the branch is
put back to the start commit's content: uncommitted work goes to
`git stash push --include-untracked`, and one commit reverts what the attempts
committed, so the branch keeps every attempt's history. The next attempt
starts from there, until the attempts or the piece's time budget in
.agents/loop-settings.json run out. Then the gate kicks the piece back.

environment_failed is retried once as an attempt that does not count. A second
one, or one on another piece straight after one on this, stops the piece in
state:building and pauses the run.

Exit codes: 0 when the next step is printed, 1 when something stops the piece
here, 2 when GitHub could not be reached, 3 when the run is paused.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import fcntl
import glob
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from typing import Any, NoReturn

HERE = os.path.dirname(os.path.abspath(__file__))
NOTE = os.path.join(HERE, "attempt-note.py")
RECOVERY = os.path.join(HERE, "recovery.py")
DEFAULTS = {"attempts": 3, "piece_budget_minutes": 120}
SETTINGS = ".agents/loop-settings.json"
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
STATUSES = ("done", "done_with_concerns", "needs_context", "blocked", "environment_failed")


def say(line: str) -> None:
    print(line, flush=True)


def stop(line: str, code: int = 1) -> NoReturn:
    say(line)
    sys.exit(code)


def git(folder: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", folder, *args], capture_output=True, text=True,
                          check=False)


def first_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "no message")


def now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def main_folder() -> str:
    done = git(os.getcwd(), "worktree", "list", "--porcelain")
    for line in done.stdout.splitlines():
        if line.startswith("worktree "):
            return line[len("worktree "):]
    stop("run.py: this folder is not inside a Git project, so there is no run to drive")


ROOT = ""


def at(path: str) -> str:
    return os.path.join(ROOT, *path.split("/"))


def gate_path() -> str:
    return at(".agents/tools/gate.py")


# --- the run record ----------------------------------------------------------

def record_path(run: str) -> str:
    return at(f".agents/runs/{run}/run.json")


def load(run: str) -> dict[str, Any]:
    try:
        with open(record_path(run), encoding="utf-8") as handle:
            record = json.load(handle)
    except FileNotFoundError:
        return {"run": run, "pieces": []}
    except (OSError, ValueError) as error:
        stop(f"run.py: the run record .agents/runs/{run}/run.json cannot be read ({error}), so "
             "nothing changed; move it aside and type /implement again")
    if not isinstance(record, dict) or not isinstance(record.get("pieces"), list):
        stop(f"run.py: .agents/runs/{run}/run.json holds no list of pieces, so nothing changed")
    return record


def save(run: str, record: dict[str, Any]) -> None:
    folder = os.path.dirname(record_path(run))
    os.makedirs(folder, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=folder, suffix=".tmp")
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        json.dump(record, out, indent=2)
        out.write("\n")
    os.replace(temporary, record_path(run))


def entry_of(record: dict[str, Any], number: int) -> dict[str, Any] | None:
    return next((p for p in record["pieces"] if isinstance(p, dict)
                 and p.get("number") == number), None)


def building_run(number: int) -> str:
    """The newest run whose record holds the piece as building, or none."""
    found = ""
    for path in sorted(glob.glob(at(".agents/runs/*/run.json")), key=os.path.getmtime):
        try:
            with open(path, encoding="utf-8") as handle:
                record = json.load(handle)
        except (OSError, ValueError):
            continue
        entry = entry_of(record, number) if isinstance(record, dict) and \
            isinstance(record.get("pieces"), list) else None
        if entry is not None and entry.get("status") == "building":
            found = os.path.basename(os.path.dirname(path))
    return found


@contextlib.contextmanager
def locked(run: str) -> Iterator[None]:
    """One session at a time drives a run. A second is told and changes nothing."""
    folder = os.path.dirname(record_path(run))
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "run.lock"), "a", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            stop(f"run.py: another session is working on run {run} now, so nothing changed; "
                 "type /implement again once it has finished")
        yield


# --- settings -------------------------------------------------------------------

def limits(run: str, record: dict[str, Any]) -> tuple[int, int]:
    """The attempts and the piece's time budget in minutes. A missing file means
    the defaults, said once in a run. A file that cannot be used starts nothing."""
    path = at(SETTINGS)
    if not os.path.exists(path):
        if not record.get("said_defaults"):
            say(f"There is no {SETTINGS}, so the defaults apply: {DEFAULTS['attempts']} "
                f"attempts and {DEFAULTS['piece_budget_minutes']} minutes for each piece.")
            record["said_defaults"] = True
            save(run, record)
        return DEFAULTS["attempts"], DEFAULTS["piece_budget_minutes"]
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as error:
        stop(f"{SETTINGS} is not valid JSON ({error}), so no attempt started. Put it right, "
             f"or delete it to use the defaults of {DEFAULTS['attempts']} attempts and "
             f"{DEFAULTS['piece_budget_minutes']} minutes.")
    if not isinstance(data, dict):
        stop(f"{SETTINGS} does not hold one set of settings, so no attempt started. Write "
             '{"attempts": 3, "piece_budget_minutes": 120}, or delete it to use the defaults.')
    values = []
    for key, default in DEFAULTS.items():
        value = data.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            stop(f"{SETTINGS}: {key} must be a whole number above 0, and it is {value!r}, so no "
                 f"attempt started. Write a whole number such as {default}, or delete the file "
                 "to use the defaults.")
        values.append(value)
    return values[0], values[1]


# --- the attempts -------------------------------------------------------------

def notes_used(number: int) -> int:
    """How many attempts have been made: the attempt notes already on disk."""
    return len(glob.glob(at(f".agents/pieces/{number}/attempt-*.md")))


def minutes_since(start: str) -> float:
    try:
        began = datetime.datetime.fromisoformat(start)
    except (TypeError, ValueError):
        return 0.0
    if began.tzinfo is None:
        began = began.astimezone()
    return (datetime.datetime.now().astimezone() - began).total_seconds() / 60


def run_gate(folder: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, gate_path(), *args], cwd=folder, capture_output=True,
                          text=True, check=False)


def echo(done: subprocess.CompletedProcess[str]) -> None:
    for line in (done.stdout + done.stderr).splitlines():
        if line.strip():
            say(line)


def load_gate() -> Any:
    spec = importlib.util.spec_from_file_location("gate", gate_path())
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    writes = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = writes
    return module


def read_piece(number: int, folder: str) -> dict[str, Any]:
    done = subprocess.run(["gh", "api", f"repos/{{owner}}/{{repo}}/issues/{number}"], cwd=folder,
                          capture_output=True, text=True, check=False)
    if done.returncode != 0:
        stop(f"GitHub could not be reached ({first_line(done.stderr)}), so no attempt started. "
             f"Type /implement {number} once it can be reached.", 2)
    try:
        issue = json.loads(done.stdout)
    except ValueError:
        stop(f"GitHub's answer for #{number} could not be read, so no attempt started.", 2)
    return issue if isinstance(issue, dict) else {}


def checks_of(body: str, module: str) -> list[str]:
    """The piece's acceptance checks, read as the gate reads them."""
    gate = load_gate()
    lint = gate.load_lint() if gate is not None else None
    if gate is None or lint is None:
        return []
    found = gate.acceptance_checks(body, module or "build", lint)
    return [p for p in found if " " not in p.strip()]


def open_request(entry: dict[str, Any]) -> dict[str, Any] | None:
    requests = entry.get("requests") or []
    if requests and isinstance(requests[-1], dict) and not requests[-1].get("ended"):
        last: dict[str, Any] = requests[-1]
        return last
    return None


def pending_request(entry: dict[str, Any]) -> dict[str, Any] | None:
    """A request whose builder ended and whose result was never routed."""
    requests = entry.get("requests") or []
    if requests and isinstance(requests[-1], dict) and requests[-1].get("ended") \
            and not requests[-1].get("route"):
        last: dict[str, Any] = requests[-1]
        return last
    return None


def write_request(run: str, record: dict[str, Any], entry: dict[str, Any], number: int,
                  attempt: int, retry: bool, allowed: tuple[int, int]) -> None:
    folder = str(entry["worktree"])
    issue = read_piece(number, folder)
    body = str(issue.get("body") or "")
    labels = [label["name"] if isinstance(label, dict) else str(label)
              for label in issue.get("labels", [])]
    loops = [n.split(":", 1)[1] for n in labels if n.startswith("loop:")]
    module = loops[0] if len(loops) == 1 else ""
    checks = checks_of(body, module)
    handoff = f"{run}-{number}-attempt-{attempt}" + ("-retry" if retry else "")
    briefs = f".agents/runs/{run}/briefs"
    os.makedirs(at(briefs), exist_ok=True)
    requirements = f"{briefs}/{number}-requirements.md"
    with open(at(requirements), "w", encoding="utf-8") as handle:
        handle.write(body)
    head = git(folder, "rev-parse", "HEAD").stdout.strip()
    result = f".agents/runs/{run}/results/{number}-attempt-{attempt}.json"
    os.makedirs(os.path.dirname(at(result)), exist_ok=True)
    notes = sorted(glob.glob(at(f".agents/pieces/{number}/attempt-*.md")))
    left = max(0, int(allowed[1] - minutes_since(str(entry.get("first_started") or now()))))
    brief = {
        "task": f"#{number} {issue.get('title', '')}".strip(),
        "handoff": handoff,
        "requirements": requirements,
        "baseline": {"branch": entry.get("branch"), "commit": head, "directory": folder},
        "records": [name for name in ("AGENTS.md", "masterplan.md", "docs/working-rules.md")
                    if os.path.exists(os.path.join(folder, name))],
        "artifacts": [os.path.relpath(path, ROOT) for path in notes],
        "run": {"directory": f".agents/runs/{run}", "coordinator": "the session that ran run.py",
                "attempts": notes_used(number)},
        "authorisation": {"scope": [folder],
                          "steps": ("the repair steps of the section-builder skill's "
                                    "references/fix-loop.md, inside the attempts its "
                                    "references/build-loop.md describes" if module == "fix" else
                                    "the build steps of the section-builder skill's "
                                    "references/build-loop.md")
                                   + ", each check run through the gate, and commits on this "
                                     "branch; never claim, push, review, open a pull request "
                                     "or merge"},
        "resources": {},
        "result": result,
        "loop": {"module": module or "build", "attempt": attempt, "retry": retry,
                 "attempts_allowed": allowed[0], "budget_minutes": allowed[1],
                 "minutes_left": left, "checks": checks,
                 "budget": "Only time counts against the budget; usage is not counted.",
                 "end": "End the attempt with exactly one status in the result file: "
                        + ", ".join(STATUSES) + "."},
    }
    path = f"{briefs}/{number}-attempt-{attempt}" + ("-retry" if retry else "") + ".json"
    with open(at(path), "w", encoding="utf-8") as handle:
        json.dump(brief, handle, indent=2)
        handle.write("\n")
    request = {"piece": number, "attempt": attempt, "retry": retry, "handoff": handoff,
               "worktree": folder, "brief": path, "result": result, "started_at": now(),
               "base": head, "checks": checks, "agent": None, "ended": False, "route": None}
    entry.setdefault("requests", []).append(request)
    save(run, record)
    say(f"Attempt {attempt} of #{number}" + (", again after the environment failed" if retry
                                             else "") + " is ready for a fresh builder.")
    say("request: " + json.dumps(request))
    say("next: start a fresh builder for this request with your coding agent's own subagent "
        "tool, give it the brief and nothing of this conversation, then run: python3 "
        f"{os.path.relpath(__file__, os.getcwd())} started {number} --run {run} --agent <id>")


def put_back(folder: str, number: int, attempt: int, start: str, run: str) -> None:
    """Put the branch back to the start commit's content, keeping its history."""
    if git(folder, "status", "--porcelain").stdout.strip():
        stashed = git(folder, "stash", "push", "--include-untracked", "-m",
                      f"attempt {attempt} of #{number}, kept in .agents/recovery/{run}-{number}/")
        if stashed.returncode != 0:
            stop(f"The unsaved work of attempt {attempt} could not be put away "
                 f"({first_line(stashed.stderr)}), so the next attempt does not start. It is "
                 "kept in its folder and in .agents/recovery/.")
    if git(folder, "diff", "--quiet", start, "HEAD").returncode == 0:
        return
    for commit in git(folder, "rev-list", "--first-parent", f"{start}..HEAD").stdout.split():
        parents = git(folder, "rev-list", "--parents", "-n", "1", commit).stdout.split()
        args = ["revert", "--no-commit"] + (["-m", "1"] if len(parents) > 2 else []) + [commit]
        reverted = git(folder, *args)
        if reverted.returncode != 0:
            stop(f"Attempt {attempt}'s commits could not be reverted "
                 f"({first_line(reverted.stderr)}), so the next attempt does not start. Its "
                 "work is kept in .agents/recovery/, and the folder is left as it is.")
    if git(folder, "diff", "--cached", "--quiet").returncode != 0:
        made = git(folder, "commit", "-q", "-m",
                   f"Put #{number} back to its start for the next attempt",
                   "-m", f"Attempt {attempt} failed. Its work is kept on this computer in "
                         f".agents/recovery/{run}-{number}/attempt-{attempt}/.")
        if made.returncode != 0:
            stop(f"The restoring commit could not be made ({first_line(made.stderr)}), so the "
                 "next attempt does not start.")
    if git(folder, "diff", "--quiet", start, "HEAD").returncode != 0:
        stop(f"After attempt {attempt} the branch does not hold the start commit's content, so "
             "the next attempt does not start.")


def note(number: int, folder: str, run: str, attempt: int, status: str | None) -> str:
    args = [sys.executable, NOTE, str(number), folder, "--run", run, "--attempt", str(attempt)]
    if status:
        args += ["--status", status]
    done = subprocess.run(args, cwd=folder, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        stop(f"The note for attempt {attempt} could not be written ({first_line(done.stderr)}), "
             "so the next attempt does not start.")
    return at(f".agents/pieces/{number}/attempt-{attempt}.md")


def failed_attempt(run: str, number: int, request: dict[str, Any], status: str | None) -> None:
    """Note the failed attempt, keep its work, put the branch back, then start
    the next attempt or, at the limit, hand the piece to the gate's kickback."""
    record = load(run)
    entry = entry_of(record, number) or {}
    folder = str(entry.get("worktree") or os.getcwd())
    attempt = int(request["attempt"])
    note_path = note(number, folder, run, attempt, status)
    kept = subprocess.run([sys.executable, RECOVERY, "preserve", "--state", record_path(run),
                           "--piece", str(number), "--source", folder, "--base",
                           str(entry.get("start_commit")), "--evidence", note_path,
                           "--attempt", str(attempt)],
                          cwd=folder, capture_output=True, text=True, check=False)
    if kept.returncode != 0:
        stop(f"Attempt {attempt}'s work could not be kept ({first_line(kept.stderr)}), so the "
             "next attempt does not start, and the folder is left exactly as it is.")
    put_back(folder, number, attempt, str(entry.get("start_commit")), run)
    record = load(run)
    entry = entry_of(record, number) or {}
    entry["requests"][-1]["route"] = "failed"
    record["environment_failures"] = []
    save(run, record)
    say(f"Attempt {attempt} of #{number} failed. Its note is {os.path.relpath(note_path, ROOT)}, "
        f"and its work is kept in .agents/recovery/{run}-{number}/attempt-{attempt}/.")
    allowed = limits(run, record)
    used = notes_used(number)
    spent = minutes_since(str(entry.get("first_started") or now()))
    reason = ""
    if used >= allowed[0]:
        reason = f"the limit of {allowed[0]} attempts"
    elif spent >= allowed[1]:
        reason = f"the piece's time budget of {allowed[1]} minutes"
    if reason:
        done = run_gate(folder, "result", str(number), at(str(request["result"])), "--at-limit",
                        "--reason", reason)
        echo(done)
        if done.returncode == 2:
            stop(f"GitHub could not be reached, so #{number} stays in state:building. Type "
                 f"/implement {number} once it can be reached.", 2)
        if done.returncode != 0:
            stop(f"The gate did not send #{number} back, so it stays in state:building.")
        record = load(run)
        entry = entry_of(record, number) or {}
        entry["requests"][-1]["route"] = "kickback"
        save(run, record)
        return
    write_request(run, record, entry, number, used + 1, False, allowed)


def environment(run: str, number: int, request: dict[str, Any]) -> None:
    record = load(run)
    entry = entry_of(record, number) or {}
    streak = [n for n in record.get("environment_failures") or [] if isinstance(n, int)]
    entry["requests"][-1]["route"] = "environment"
    told = (f"It stays in state:building, with its run record, result files and attempt notes "
            f"kept. Put the computer right, then type /implement {number}.")
    if streak and streak[-1] != number:
        record["stopped"] = {"piece": number, "at": now(),
                             "reason": f"the environment failed on #{streak[-1]}, then on "
                                       f"#{number}"}
        save(run, record)
        stop(f"#{number}: the environment failed straight after it failed on #{streak[-1]}, so "
             f"the run pauses now rather than try a third. {told}", 3)
    if request.get("retry"):
        record["stopped"] = {"piece": number, "at": now(),
                             "reason": f"the environment failed twice on #{number}"}
        save(run, record)
        stop(f"#{number} stopped: the environment failed twice. {told}", 3)
    record["environment_failures"] = streak + [number]
    result = at(str(request["result"]))
    if os.path.exists(result):
        os.replace(result, result[:-len(".json")] + "-environment.json")
    save(run, record)
    write_request(run, record, entry, number, int(request["attempt"]), True,
                  limits(run, record))


def route(run: str, number: int, request: dict[str, Any]) -> None:
    """Hand the builder's result to the gate, which takes its status's route."""
    record = load(run)
    entry = entry_of(record, number) or {}
    folder = str(entry.get("worktree") or os.getcwd())
    path = at(str(request["result"]))
    attempt = int(request["attempt"])
    if not os.path.exists(path):
        say(f"The builder of attempt {attempt} ended and left no result, so the attempt counts "
            "as failed.")
        failed_attempt(run, number, request, "no result")
        return
    status = None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        status = data.get("status") if isinstance(data, dict) else None
        if isinstance(data, dict) and data.get("handoff") not in (None, request.get("handoff")):
            say(f"The result at {request['result']} belongs to another start request, so attempt "
                f"{attempt} counts as failed.")
            failed_attempt(run, number, request, "a result from another start request")
            return
    except (OSError, ValueError):
        status = None
    if status in ("needs_context", "blocked"):
        note(number, folder, run, attempt, None)
    done = run_gate(folder, "result", str(number), path)
    echo(done)
    if done.returncode == 2:
        stop(f"GitHub could not be reached, so #{number} stays in state:building and its result "
             f"is kept at {request['result']}. Type /implement {number} once it can be "
             "reached.", 2)
    if done.returncode == 4:
        environment(run, number, request)
        return
    if done.returncode in (3, 5):
        failed_attempt(run, number, request, None if done.returncode == 3
                       else "a result the gate could not route")
        return
    if done.returncode != 0:
        stop(f"The gate refused the result, so #{number} stays where it is.")
    record = load(run)
    entry = entry_of(record, number) or {}
    went = "kickback" if "route: kickback" in done.stdout else "review"
    entry["requests"][-1]["route"] = went
    record["environment_failures"] = []
    save(run, record)
    if went == "review":
        note(number, folder, run, attempt, None)
        say(f"next: #{number} goes on to the review, section-builder's step 7, in {folder}.")
    else:
        say(f"next: #{number} is back in shaping for /shape. The run takes its next piece.")


# --- the commands -------------------------------------------------------------

def command_start(number: int, run: str | None) -> None:
    resumed = building_run(number) if not run else ""
    name = run or resumed or \
        f"solo-{number}-{datetime.datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}"
    if not NAME.fullmatch(name):
        stop(f"run.py: '{name}' is not a run name: use letters, numbers, dots and dashes")
    folder = os.path.dirname(record_path(name))
    made = not os.path.isdir(folder)
    with locked(name):
        record = load(name)
        entry = entry_of(record, number)
        if entry is not None and entry.get("status") == "building":
            record.pop("stopped", None)
            record["environment_failures"] = []
            save(name, record)
            say(f"run {name}: resumed #{number} with no new claim; {notes_used(number)} "
                "attempt(s) made so far.")
            pending = pending_request(entry)
            if pending is not None:
                say("Its last result was saved but never routed, so it is routed first.")
                route(name, number, pending)
                return
            say(f"next: python3 {os.path.relpath(__file__, os.getcwd())} next {number} --run "
                f"{name}")
            return
        claim = run_gate(os.getcwd(), "move", str(number), "building", "--run", name,
                         "--assignee", "@me")
        echo(claim)
        if claim.returncode != 0:
            if made:
                for leftover in ("run.lock",):
                    with contextlib.suppress(OSError):
                        os.remove(os.path.join(folder, leftover))
                with contextlib.suppress(OSError):
                    os.rmdir(folder)
            stop(f"#{number} was not claimed, so nothing was built.",
                 2 if claim.returncode == 2 else 1)
        record = load(name)
        record["run"] = name
        record.setdefault("created", now())
        save(name, record)
        say(f"run {name}: claimed #{number} through the gate.")
        say(f"next: show the acceptance checks failing, then run: python3 "
            f"{os.path.relpath(__file__, os.getcwd())} next {number} --run {name}")


def command_next(number: int, run: str, worktree: str | None) -> None:
    with locked(run):
        record = load(run)
        entry = entry_of(record, number)
        if entry is None or entry.get("status") != "building":
            stop(f"run.py: run {run} holds no #{number} being built; type /implement "
                 f"{number} to claim it")
        if record.get("stopped"):
            stop(f"run {run} is paused: {record['stopped'].get('reason')}. Type /implement "
                 f"{record['stopped'].get('piece')} once it is put right.", 3)
        pending = pending_request(entry)
        if pending is not None:
            route(run, number, pending)
            return
        current = open_request(entry)
        if current is not None:
            say(f"Attempt {current['attempt']} of #{number} is still with its builder; its "
                "start request again:")
            say("request: " + json.dumps(current))
            return
        allowed = limits(run, record)
        if not entry.get("worktree"):
            folder = os.path.abspath(worktree) if worktree else \
                git(os.getcwd(), "rev-parse", "--show-toplevel").stdout.strip()
            entry["worktree"] = folder
            entry["branch"] = git(folder, "branch", "--show-current").stdout.strip()
            entry["start_commit"] = git(folder, "rev-parse", "HEAD").stdout.strip()
            entry["first_started"] = now()
        used = notes_used(number)
        spent = minutes_since(str(entry.get("first_started")))
        if used >= allowed[0] or spent >= allowed[1]:
            requests = entry.get("requests") or [{"result": ""}]
            done = run_gate(str(entry["worktree"]), "result", str(number),
                            at(str(requests[-1].get("result") or "-")), "--at-limit",
                            "--reason", f"the limit of {allowed[0]} attempts"
                            if used >= allowed[0] else
                            f"the piece's time budget of {allowed[1]} minutes")
            echo(done)
            sys.exit(0 if done.returncode == 0 else done.returncode)
        write_request(run, record, entry, number, used + 1, False, allowed)


def command_started(number: int, run: str, agent: str) -> None:
    with locked(run):
        record = load(run)
        entry = entry_of(record, number)
        current = open_request(entry) if entry is not None else None
        if current is None:
            stop(f"run.py: run {run} holds no start request for #{number} waiting for a builder")
        current["agent"] = agent
        save(run, record)
        say(f"Attempt {current['attempt']} of #{number} is with builder {agent}. When it ends, "
            f"run: python3 {os.path.relpath(__file__, os.getcwd())} ended {number} --run {run}")


def command_ended(number: int, run: str) -> None:
    with locked(run):
        record = load(run)
        entry = entry_of(record, number)
        if entry is None:
            stop(f"run.py: run {run} holds no #{number}")
        current = open_request(entry) or pending_request(entry)
        if current is None:
            stop(f"run.py: #{number} has no attempt waiting to be routed")
        current["ended"] = True
        save(run, record)
        route(run, number, current)


def main(argv: list[str]) -> int:
    global ROOT
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["start", "next", "started", "ended"])
    parser.add_argument("number", type=int)
    parser.add_argument("--run")
    parser.add_argument("--worktree")
    parser.add_argument("--agent")
    args = parser.parse_args(argv)
    ROOT = main_folder()
    if not os.path.isfile(gate_path()):
        stop("run.py: the gate script is missing at .agents/tools/gate.py; run /maintain, which "
             "puts it back")
    if args.command != "start" and not args.run:
        stop(f"run.py: {args.command} needs --run <name>, the name start printed")
    if args.command == "start":
        command_start(args.number, args.run)
    elif args.command == "next":
        command_next(args.number, str(args.run), args.worktree)
    elif args.command == "started":
        if not args.agent:
            stop("run.py: started needs --agent <id>, the builder's id")
        command_started(args.number, str(args.run), str(args.agent))
    else:
        command_ended(args.number, str(args.run))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
