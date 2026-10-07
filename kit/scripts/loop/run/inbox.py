#!/usr/bin/env python3
# contract: agent
# contract: changes-state
"""The inbox: the person's answers, read from GitHub comments and from the mailbox.

    inbox.py --run NAME [--project .] [--dry-run]

Inside a run, the engine calls `run_hook` and this module does three jobs.

1. On every tick, at most every `POLL_SECONDS`, it reads the new comments on the issue of each
   parked piece, and on the run's pull request (the number in the run record under
   `pull_request`). With no GitHub App it reads nothing from GitHub. Never the person's `gh`
   sign-in: every read goes through `loop.github`, as the App.
2. A new comment from the person (the owner, a member or a collaborator, never a bot) is an
   answer. The piece's text goes into the run record as data, and `resume_piece` puts the piece
   back to building. The builder reads the answer inside the marked data block of its brief. A
   comment on the pull request names its piece: `piece 4: blue`.
3. At the end of the run, a parked piece that has an answer is not resumed (no run is left to
   build it). The answer goes in through `gate.py answer`, which writes it under Decisions and
   takes a new fingerprint (`--parked`: a builder's question is not in the spec); the piece goes
   back to ready by move 7; and the person is told in a comment, as the App.
   This is also what the command line does, for an answer that comes after
   the run has ended.

The text of a comment is data. It is never run, never put in a command, and never written into a
spec by this module: only the gate writes an answer into the spec. A comment that cannot be read,
a read of GitHub that fails and a refusal by the gate are each a note in the run record with the
next command. None of them is a quiet pass, and a refused answer stays kept in the record, so the
next call tries it again.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

if __name__ == "__main__":
    HERE = Path(__file__).resolve().parent
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
    sys.path.insert(0, str(HERE.parents[1]))

from loop import cli, github, moves
from loop.paths import PathError, Paths, find_project_root
from loop.run import record, summary
from loop.run.gateway import Gateway

POLL_SECONDS = 15.0
POLL_ENV = "AI_LOOP_KIT_INBOX_POLL"
MAX_ANSWER = 4000
PEOPLE = ("OWNER", "MEMBER", "COLLABORATOR")
_NAMED = re.compile(r"(?is)^\s*(?:answer\s+)?(?:piece\s+|#)(\d+)\s*[:\-]\s*(.+)$")

make_hub: Callable[[Paths], github.GitHub] = lambda paths: github.GitHub(paths)  # noqa: E731
make_gateway: Callable[[Paths], Gateway] = lambda paths: Gateway(paths)  # noqa: E731

_LOCK = threading.RLock()
_SEEN: dict[tuple[str, str], dict[str, Any]] = {}


def _mine(context: Any) -> dict[str, Any]:
    with _LOCK:
        return _SEEN.setdefault((str(context.paths.root), context.name),
                                {"last": 0.0, "said": set(), "hub": None})


def forget(context: Any) -> None:
    with _LOCK:
        _SEEN.pop((str(context.paths.root), context.name), None)


def _say(context: Any, key: str, text: str) -> None:
    """A note, once for each key."""
    mine = _mine(context)
    with _LOCK:
        if key in mine["said"]:
            return
        mine["said"].add(key)
    context.record.note(text)


def _hub(context: Any) -> github.GitHub:
    mine = _mine(context)
    with _LOCK:
        if mine["hub"] is None:
            mine["hub"] = make_hub(context.paths)
        hub: github.GitHub = mine["hub"]
    return hub


def _stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# --- the answer of a person ------------------------------------------------------------


def deliver(context: Any, number: int, text: str, source: str, by: str = "") -> bool:
    """An answer for a parked piece: keep it in the record, and put the piece back to building.

    Returns True when the piece was parked and now goes on. Any other case is a note.
    """
    rec = context.record
    words = " ".join(str(text).split())[:MAX_ANSWER]
    if not words:
        rec.note(f"an answer for piece {number} from {source} was empty, so it is ignored")
        return False
    try:
        status = rec.status(number)
    except KeyError:
        rec.note(f"an answer from {source} names piece {number}, which is not in this run")
        return False
    if status != record.PARKED_PERSON:
        rec.note(f"an answer for piece {number} came from {source}, but the piece is "
                 f"{status} and waits for no answer, so the answer is not used")
        return False
    rec.update(number, answer={"text": words, "source": source, "by": by or source,
                               "at": _stamp()})
    rec.add_decision(
        number, "run",
        f"Went on with piece {number} on the person's answer ({source}). The answer goes into "
        "the spec through gate.py answer, which the person or the run after this one gives.")
    context.resume_piece(number)
    return True


# --- reading the comments --------------------------------------------------------------


def _comments(context: Any, hub: github.GitHub, issue: int) -> list[dict[str, Any]] | None:
    """The comments on an issue or pull request, or None when GitHub could not be read."""
    try:
        listed = hub.api_json(f"repos/{{owner}}/{{repo}}/issues/{issue}/comments")
    except github.GitHubError as error:
        _say(context, f"read:{issue}:{error.message}",
             f"the comments on issue {issue} cannot be read ({error.message}), so no answer is "
             "read "
             f"from there. next: {error.next_command}")
        return None
    if not isinstance(listed, list):
        _say(context, f"shape:{issue}", f"GitHub answered with something that is not a list of "
             f"comments for issue {issue}, so no answer is read from there")
        return None
    found: list[dict[str, Any]] = []
    for item in listed:
        try:
            found.append({"id": int(item["id"]), "body": str(item["body"]),
                          "login": str(item["user"]["login"]),
                          "who": str(item["author_association"]),
                          "at": str(item.get("created_at") or "")})
        except (KeyError, TypeError, ValueError):
            _say(context, f"bad:{issue}:{repr(item)[:60]}",
                 f"a comment on issue {issue} is malformed (no id, text, author or association), "
                 "so it is not read")
    return found


def _is_person(comment: dict[str, Any]) -> bool:
    return not str(comment["login"]).endswith("[bot]") and comment["who"] in PEOPLE


def _newer(comment: dict[str, Any], since: str, after: int) -> bool:
    """A comment made after the piece was parked: by its time, else by its number."""
    if comment["at"] and since:
        return bool(comment["at"] >= since)
    return bool(comment["id"] > after)


def _poll(context: Any) -> None:
    mine = _mine(context)
    now = time.monotonic()
    limit = float(os.environ.get(POLL_ENV) or POLL_SECONDS)
    with _LOCK:
        if mine["last"] and now - mine["last"] < limit:
            return
        mine["last"] = now
    hub = _hub(context)
    if not hub.available:
        return  # no App: nothing is read from GitHub
    rec = context.record
    for number in rec.with_status(record.PARKED_PERSON):
        issue = rec.piece(number).get("issue")
        if isinstance(issue, int):
            _read_piece(context, hub, number, issue)
    pull = _pull_request(rec)
    if pull is not None:
        _read_pull_request(context, hub, pull)


def _answers_of(context: Any, hub: github.GitHub, number: int, issue: int) -> list[
        dict[str, Any]]:
    rec = context.record
    held = rec.piece(number)
    listed = _comments(context, hub, issue)
    if listed is None:
        return []
    since = str(held.get("at") or "")
    if held.get("inbox_after") is None:
        # The first look at this piece: comments from before it was parked are not answers.
        rec.update(number, inbox_after=max((c["id"] for c in listed), default=0))
        if not any(c["at"] for c in listed):
            return []
    after = int(held.get("inbox_after") or 0)
    used = {int(i) for i in held.get("inbox_used", [])}
    return [c for c in listed
            if c["id"] not in used and _newer(c, since, after) and _is_person(c)]


def _read_piece(context: Any, hub: github.GitHub, number: int, issue: int) -> None:
    rec = context.record
    new = _answers_of(context, hub, number, issue)
    if not new:
        return
    text = "\n\n".join(c["body"] for c in new)
    rec.update(number, inbox_used=[*rec.piece(number).get("inbox_used", []),
                                   *[c["id"] for c in new]])
    deliver(context, number, text, f"a comment on issue {issue} by {new[-1]['login']}",
            by=new[-1]["login"])


def _pull_request(rec: record.RunRecord) -> int | None:
    held = rec.data.get("pull_request")
    if isinstance(held, dict):
        held = held.get("number")
    return held if isinstance(held, int) and not isinstance(held, bool) else None


def _read_pull_request(context: Any, hub: github.GitHub, pull: int) -> None:
    rec = context.record
    listed = _comments(context, hub, pull)
    if listed is None:
        return
    box = rec.data.setdefault("inbox", {})
    if "pull_after" not in box:
        box["pull_after"] = max((c["id"] for c in listed), default=0)
        box["pull_used"] = []
        rec.save()
        return
    used = {int(i) for i in box.get("pull_used", [])}
    for comment in listed:
        if comment["id"] in used or comment["id"] <= int(box["pull_after"]):
            continue
        if not _is_person(comment):
            continue
        box["pull_used"] = [*box.get("pull_used", []), comment["id"]]
        rec.save()
        named = _NAMED.match(comment["body"])
        if not named:
            _say(context, f"unnamed:{comment['id']}",
                 f"a comment on the pull request {pull} by {comment['login']} names no piece, so "
                 "it is not used as an answer. Start an answer with 'piece <number>:'")
            continue
        number = _piece_named(rec, int(named.group(1)))
        if number is None:
            _say(context, f"nopiece:{comment['id']}",
                 f"a comment on the pull request {pull} names piece {named.group(1)}, which is "
                 "not in this run")
            continue
        deliver(context, number, named.group(2), f"a comment on the pull request {pull} by "
                f"{comment['login']}", by=comment["login"])


def _piece_named(rec: record.RunRecord, wanted: int) -> int | None:
    for number in rec.numbers():
        if number == wanted:
            return number
    for number in rec.numbers():
        if rec.piece(number).get("issue") == wanted:
            return number
    return None


# --- after the run ---------------------------------------------------------------------


def after_run(context: Any, *, dry_run: bool = False) -> list[dict[str, Any]]:
    """Put the answers of parked pieces into the gate. Returns what was done for each piece."""
    rec = context.record
    gateway = make_gateway(context.paths)
    hub = _hub(context)
    done: list[dict[str, Any]] = []
    for number in rec.with_status(record.PARKED_PERSON):
        held = rec.piece(number)
        if not held.get("answer"):
            issue = held.get("issue")
            if hub.available and isinstance(issue, int):
                new = _answers_of(context, hub, number, issue)
                if new:
                    rec.update(number, answer={
                        "text": " ".join("\n\n".join(c["body"] for c in new).split())[:MAX_ANSWER],
                        "source": f"a comment on issue {issue} by {new[-1]['login']}",
                        "by": new[-1]["login"], "at": _stamp()},
                        inbox_used=[*held.get("inbox_used", []), *[c["id"] for c in new]])
        answer = rec.piece(number).get("answer")
        if not isinstance(answer, dict) or not answer.get("text"):
            continue
        done.append(_gate_answer(context, gateway, hub, number, answer, dry_run))
    return done


def _gate_answer(context: Any, gateway: Gateway, hub: github.GitHub, number: int,
                 answer: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    rec = context.record
    question = str(rec.piece(number).get("question") or "")
    said = {"piece": number, "source": answer.get("source", ""), "question": question}
    if dry_run:
        return {**said, "would": "gate.py answer, then move 7 to ready, then a comment"}
    if not question:
        rec.note(f"piece {number} has an answer but no recorded question, so the gate cannot be "
                 "asked to write it")
        return {**said, "result": "no-question"}
    by = f"{answer.get('by') or 'the person'} (written by the run from {answer.get('source')})"
    # The question is a builder's, parked in building, so the spec holds none: --parked.
    args = ["answer", str(number), "--question", question, "--answer", str(answer["text"]),
            "--by", by, "--parked"]
    with context.gate_lock:
        reply = gateway._call("gate.py", args)
        if not reply.ok:
            rec.note(f"the gate did not write the answer of piece {number}: {reply.message}. "
                     f"The answer is kept, and the piece stays parked. next: {reply.next_command}")
            rec.update(number, next=reply.next_command or f"gate.py answer {number} --question "
                       f"<it> --answer <yours> --by <you> --parked, then gate.py move {number} "
                       "ready")
            return {**said, "result": "answer-refused", "error": reply.message}
        back = gateway.move(number, "ready",
                            reason=f"the person answered the question after the run: {question}")
    if not back.ok:
        rec.note(f"the gate wrote the answer of piece {number} but refused move 7: "
                 f"{back.message}. next: {back.next_command}")
        rec.update(number, next=back.next_command or f"gate.py move {number} ready --reason <why>")
        return {**said, "result": "move-refused", "error": back.message}
    rec.set_status(number, record.RETURNED,
                   reason="the person answered the question; the gate wrote the answer into the "
                   "spec and move 7 put the piece back to ready")
    rec.add_decision(number, "run", f"Wrote the person's answer into the spec of piece {number} "
                     "through gate.py answer, and put the piece back to ready by move 7.")
    told = _tell(context, hub, number)
    return {**said, "result": "ready", "told": told}


def _tell(context: Any, hub: github.GitHub, number: int) -> bool:
    rec = context.record
    issue = rec.piece(number).get("issue")
    if not isinstance(issue, int):
        rec.note(f"piece {number} has no issue, so the person is not told by a comment")
        return False
    if not hub.available:
        rec.note(f"there is no GitHub App, so the person is not told about piece {number} by a "
                 "comment")
        return False
    login = str((rec.piece(number).get("answer") or {}).get("by") or "")
    mention = f"@{login} " if re.fullmatch(r"[A-Za-z0-9-]{1,39}", login) else ""
    try:
        hub.comment(issue, f"{mention}Your answer is in. The gate wrote it into the spec of this "
                    "piece, and the piece is back in ready.")
    except github.GitHubError as error:
        rec.note(f"the person could not be told about piece {number} ({error.message}). "
                 f"next: {error.next_command}")
        return False
    return True


# --- the hook --------------------------------------------------------------------------


def run_hook(context: Any, event: str, **data: Any) -> None:
    if event == "start":
        forget(context)
        if not _hub(context).available:
            _say(context, "no-app",
                 "there is no GitHub App, so no comment is read for this run. Answers come "
                 "through the mailbox ('answer <piece>: <text>') and gate.py answer")
        else:
            _poll(context)
    elif event == "tick":
        _poll(context)
    elif event == "run-end":
        mine = _mine(context)
        with _LOCK:
            mine["last"] = 0.0
        _poll(context)
        after_run(context)


# --- the command line ------------------------------------------------------------------


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run", required=True, help="the name of the run that ended")
    parser.add_argument("--project", default=".", help="a folder inside the project")


def handler(args: argparse.Namespace) -> dict[str, Any]:
    try:
        paths = Paths.for_project(find_project_root(Path(args.project)))
        paths.run_dir(args.run)
    except PathError as error:
        raise cli.Failure(str(error), next_command="cd into the project, then run inbox.py again",
                          code=cli.ExitCode.USAGE) from error
    try:
        rec = record.RunRecord.load(paths, args.run)
    except record.RecordError as error:
        raise cli.Failure(str(error), next_command=error.next_command,
                          code=cli.ExitCode.REFUSED) from error
    try:
        lock = record.acquire_lock(paths, args.run)
    except record.LockHeld as error:
        raise cli.Failure(
            f"{error}. A live run reads the comments itself.", next_command=error.next_command,
            code=cli.ExitCode.REFUSED) from error
    try:
        context = SimpleNamespace(paths=paths, name=args.run, record=rec,
                                  resume_piece=lambda number: None, gate_lock=threading.RLock())
        mailbox_answers(context, dry_run=args.dry_run)
        try:
            done = after_run(context, dry_run=args.dry_run)
        except moves.MoveError as error:
            raise cli.Failure(str(error), next_command=error.next_command) from error
        if not args.dry_run:
            summary.write(rec)
    finally:
        lock.release()
    waiting = [d for d in done if d.get("result") not in ("ready", None)]
    return {"run": args.run, "answers": done, "parked": rec.with_status(record.PARKED_PERSON),
            "next": (f"read the notes in the run record for piece {waiting[0]['piece']}"
                     if waiting else "read the summary in the run folder")}


def mailbox_answers(context: Any, *, dry_run: bool = False) -> None:
    """Answers the person wrote in the mailbox after the run: each line once, kept in the record."""
    rec = context.record
    path = context.paths.mailbox(context.name)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    except (OSError, UnicodeDecodeError) as error:
        rec.note(f"the mailbox {path} cannot be read ({type(error).__name__}), so its answers "
                 "are not used")
        return
    held = rec.data.setdefault("mailbox", {"events": [], "paused": False})
    kept: list[str] = held.setdefault("answers_used", [])
    for line in lines:
        found = re.match(r"(?i)^\s*answer\s+#?(\d+)\s*[:\-]?\s*(.+)$", line)
        if not found or line.strip() in kept:
            continue
        number = int(found.group(1))
        if str(number) not in rec.data["pieces"] or rec.status(number) != record.PARKED_PERSON:
            continue
        if dry_run:
            continue
        rec.update(number, answer={"text": " ".join(found.group(2).split())[:MAX_ANSWER],
                                   "source": "the mailbox", "by": "the person",
                                   "at": _stamp()})
        kept.append(line.strip())
        rec.save()


def main(argv: list[str]) -> int:
    return cli.run("inbox.py", "Put the answers of parked pieces into the gate, after a run.",
                   setup, handler, argv, changes_state=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
