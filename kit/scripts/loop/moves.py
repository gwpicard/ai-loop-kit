"""The gate's moves: the only way a piece changes state.

`Gate` applies the table in `loop/states.py` and the shared rules of the design:

- A move not in the table is refused, with the legal targets on the `next:` line.
- Every move back carries a written reason, posted on the issue.
- The anti-circle rule, on moves back to shaping only: the reason must be new to
  the piece, and the gate writes it into the spec as a new open question.
- Moves 7, 8 and 12 have a repeat counter. It counts only the moves since the
  piece last left shaping. After 3 of the same move, the next one sends the
  piece back to shaping from where it stands, with its history. The gate's own
  reason names the count in all, so the anti-circle rule never refuses it.
- Every move reads the piece twice: once to check, once just before writing.
- A change the gate makes to the spec takes a new fingerprint.
- An issue with two `state:` labels is refused. A label that differs from the
  gate's own piece record was changed by hand: the gate reports it and never
  undoes it.

Each move then calls its checks module, `loop/gates/<name>.py`. A move whose
module is not installed yet is refused with a `next:` line.

The piece record, `.agents/pieces/<n>/`, is the gate's truth for state. Only the
gate writes it, through `loop.evidence`. Each entry has a `kind`: `capture`,
`move`, `body`, `needs`, `fingerprint`, `answer`, `queue`, `synced`, `branch`, and,
from the ready gate, `judge-run`, `test-lists` and `relied-on`, from the claim gate,
`claim-check`, and from the attempt gate, `attempt`. A move into ready carries the `must_look`
reasons the ready gate wrote.

A check that refuses with `send_back` in its data (the claim gate does) makes the gate send
the piece back to shaping with that text as the reason: by move 3 from the claim, and by
move 6 from the attempt gate, which first writes the failed attempt to the record. A dry run
only reports it.

With the GitHub App the gate writes the labels, the body and the comments as
the App, then the record. A failed GitHub write leaves the record unchanged.
Without the App, the gate makes the move in the record alone and queues each
GitHub write there. Its `next:` line names `gate.py sync`, which only the person
runs. Once the App exists, the gate sends a piece's queue as the App before its
next move.

The gate writes the computed needs below the spec, under `NEEDS_HEADING`, and
the fingerprint marker after them. Everything from that heading to the end of
the body is the gate's own, and it rewrites it each time.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from loop import evidence, fingerprint, github, needs, spec, states
from loop.cli import ExitCode
from loop.gates import CheckContext, CheckResult
from loop.paths import Paths

NEEDS_HEADING = "## Needs (written by the gate; do not edit)"
NO_FINGERPRINT = "<!-- loop:fingerprint none yet; taken at ready -->"
_FINGERPRINT_LINE = re.compile(r"^\s*<!-- loop:fingerprint .*-->\s*$")

CheckFunction = Callable[[CheckContext], CheckResult]
Loader = Callable[[str], CheckFunction | None]


class MoveError(Exception):
    """A refusal or a failure. Carries the exit code and the next command."""

    def __init__(
        self,
        message: str,
        *,
        next_command: str,
        code: ExitCode = ExitCode.REFUSED,
        data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.next_command = next_command
        self.code = code
        self.data = data or {}


class Hub(Protocol):
    """GitHub as the gate uses it: `loop.github.GitHub`, or a stand-in in tests."""

    @property
    def available(self) -> bool: ...

    def read_issue(self, number: int) -> dict[str, Any]: ...

    def read_again(self, number: int, first: Mapping[str, Any]) -> dict[str, Any]: ...

    def create_issue(self, title: str, body: str, labels: Sequence[str]) -> int: ...

    def edit_labels(self, number: int, *, add: Sequence[str], remove: Sequence[str]) -> None: ...

    def set_body(self, number: int, body: str) -> None: ...

    def comment(self, number: int, body: str) -> None: ...

    def close(self, number: int, reason: str) -> None: ...

    def reopen(self, number: int) -> None: ...

    def list_labels(self) -> list[str]: ...

    def create_label(self, name: str, colour: str, description: str) -> None: ...


def load_checks(name: str) -> CheckFunction | None:
    """The `check` function of `loop/gates/<name>.py`, or None when it is not installed."""
    module_name = f"loop.gates.{name}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name == module_name:
            return None
        raise
    found: CheckFunction | None = getattr(module, "check", None)
    return found


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.casefold()).split())


@dataclass
class Piece:
    """A piece as the gate's record holds it."""

    number: int
    title: str = ""
    issue_type: str = "feature"
    issue: int | None = None
    state: str = states.NEW
    body: str = ""
    needs: list[dict[str, Any]] = field(default_factory=list)
    needs_you: bool = False
    fingerprint_data: dict[str, Any] | None = None
    must_look: list[str] = field(default_factory=list)  # the reasons the ready gate wrote
    queue: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[int, int] = field(default_factory=dict)  # since it last left shaping
    totals: dict[int, int] = field(default_factory=dict)  # moves asked for, in all
    history: list[dict[str, Any]] = field(default_factory=list)
    recent: list[dict[str, Any]] = field(default_factory=list)  # since it last left shaping
    entries: int = 0
    next_id: int = 1
    record: list[dict[str, Any]] = field(default_factory=list)

    @property
    def fingerprint(self) -> str | None:
        if self.fingerprint_data is None:
            return None
        return str(self.fingerprint_data.get("fingerprint"))

    @property
    def individual_review(self) -> bool:
        """True when the ready gate wrote a must-look reason: the piece gets its own review."""
        return bool(self.must_look)

    @property
    def reasons(self) -> list[str]:
        return [str(m["reason"]) for m in self.history if m.get("reason")]

    @property
    def changed_outside(self) -> bool:
        """True when the body in the record no longer matches the recorded fingerprint."""
        return _fingerprint_moved(self.body, self.fingerprint_data)

    def labels(self) -> list[str]:
        """The labels the record says the issue carries."""
        found = [states.label(self.state), states.TYPE_PREFIX + self.issue_type]
        if self.needs_you:
            found.append(states.NEEDS_YOU)
        return found


def _fingerprint_moved(body: str, data: Mapping[str, Any] | None) -> bool:
    if not data:
        return False
    try:
        now = fingerprint.take(body, str(data.get("judge_commit", "")))
    except (spec.SpecError, fingerprint.FingerprintError):
        return True
    return now["fingerprint"] != data.get("fingerprint")


def read_piece(paths: Paths, number: int) -> Piece | None:
    """The piece in the gate's record, or None when the gate never captured it."""
    try:
        record = evidence.read(paths, number)
    except evidence.EvidenceError as error:
        raise MoveError(str(error), next_command=error.next_command) from error
    if not record or record[0].get("kind") != "capture":
        return None
    piece = Piece(number=number, record=record, entries=len(record))
    queued: dict[int, dict[str, Any]] = {}
    for entry in record:
        kind = entry.get("kind")
        if kind == "capture":
            piece.title = str(entry.get("title", ""))
            piece.issue_type = str(entry.get("type", "feature"))
            piece.issue = entry.get("issue")
            piece.state = "shaping"
        elif kind == "move":
            if entry.get("from") == "shaping":
                piece.counts = {}
                piece.recent = []
            piece.state = str(entry["to"])
            if entry.get("from") == "shaping" and entry.get("to") == "ready":
                piece.must_look = [str(r) for r in entry.get("must_look", [])]
            moved = int(entry["move"])
            asked = int(entry.get("asked") or moved)
            piece.counts[moved] = piece.counts.get(moved, 0) + 1
            piece.totals[asked] = piece.totals.get(asked, 0) + 1
            piece.history.append(entry)
            piece.recent.append(entry)
        elif kind == "body":
            piece.body = str(entry["text"])
        elif kind == "needs":
            piece.needs = list(entry.get("needs", []))
            piece.needs_you = bool(entry.get("needs_you"))
        elif kind == "fingerprint":
            piece.fingerprint_data = dict(entry["fingerprint"])
        elif kind == "queue":
            queued[int(entry["id"])] = dict(entry["op"], id=int(entry["id"]))
            piece.next_id = max(piece.next_id, int(entry["id"]) + 1)
        elif kind == "synced":
            queued.pop(int(entry["id"]), None)
            if entry.get("issue"):
                piece.issue = int(entry["issue"])
    piece.queue = [queued[key] for key in sorted(queued)]
    return piece


def _at_a_terminal() -> bool:
    """True when standard input and standard output are both a terminal: a person typing."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def find_piece(paths: Paths, number: int) -> Piece | None:
    """The piece by its local number, or by the issue number `sync` gave it.

    Refuses a number that is both one piece's local number and another's issue.
    """
    own = read_piece(paths, number)
    folder = paths.pieces_dir
    others = sorted(int(p.name) for p in folder.iterdir()
                    if p.is_dir() and p.name.isdigit() and int(p.name) != number
                    ) if folder.is_dir() else []
    holders = [found for found in (read_piece(paths, n) for n in others)
               if found is not None and found.issue == number]
    if own is not None and holders and own.issue != number:
        raise MoveError(
            f"{number} is the local number of piece {number} and the issue number of piece "
            f"{holders[0].number}, so the gate cannot tell which is meant",
            next_command=f"gate.py report --json, then use the piece number "
            f"({number} or {holders[0].number})",
        )
    if own is not None:
        return own
    return holders[0] if holders else None


def _dropped_questions(before: str, after: str) -> list[str]:
    """The open questions in `before` that `after` no longer holds."""
    try:
        old = spec.parse(before).open_questions
    except spec.SpecError:
        return []
    try:
        kept = {_norm(q) for q in spec.parse(after).open_questions}
    except spec.SpecError:
        kept = set()
    return [q for q in old if _norm(q) not in kept]


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


AGENT = "the agent"  # the only name an agent session may record an answer under


def queue_digest(pieces: Sequence[Piece]) -> str:
    """A short digest of every queued write, so sync sends only what the dry run showed."""
    queued = [[p.number, p.issue, p.queue] for p in pieces]
    text = json.dumps(queued, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _shown(op: Mapping[str, Any]) -> dict[str, Any]:
    """A queued write as the person reads it before sync: everything but the hash."""
    return {key: value for key, value in op.items() if key != "base"}


def _listing(pieces: Sequence[Piece]) -> str:
    """Every queued write in full, in plain words, for the person to read before sync."""
    lines: list[str] = []
    for piece in pieces:
        where = f"issue {piece.issue}" if piece.issue is not None else "no issue yet"
        lines.append(f"Piece {piece.number} ({where}), {len(piece.queue)} write(s) waiting:")
        for index, op in enumerate(piece.queue, start=1):
            kind = op["op"]
            if kind == "issue":
                lines.append(f"  {index}. open an issue titled {op['title']!r}, labels "
                             f"{', '.join(op['labels']) or 'none'}, with this body:")
                lines.extend(f"     | {line}" for line in str(op["body"]).splitlines())
            elif kind == "body":
                lines.append(f"  {index}. replace the issue body with:")
                lines.extend(f"     | {line}" for line in str(op["text"]).splitlines())
            elif kind == "comment":
                lines.append(f"  {index}. post this comment in your name:")
                lines.extend(f"     | {line}" for line in str(op["text"]).splitlines())
            elif kind == "labels":
                lines.append(f"  {index}. labels: add {', '.join(op['add']) or 'none'}; "
                             f"remove {', '.join(op['remove']) or 'none'}")
            elif kind == "close":
                lines.append(f"  {index}. close the issue as {op['reason']}")
            elif kind == "reopen":
                lines.append(f"  {index}. reopen the issue")
    return "\n".join(lines)


class HandChange(Exception):
    """A label or a body on GitHub that differs from what the gate expects."""


class RunMergeAuthority:
    """Proof, held inside one process, that the process is the run script of a named run.

    `run.py` takes the run's lock, a file that holds its own process number. The merge of a
    pre-approved run is asked for inside that same process, by handing the gate this object. No
    command line, option or environment variable can make one: it is a Python object, and it
    holds only while this process still owns the run's lock.
    """

    def __init__(self, paths: Paths, run: str) -> None:
        self.paths = paths
        self.run = run

    def held(self) -> bool:
        """True while the run's lock file holds this very process's number."""
        try:
            held = self.paths.lock_file(self.run).read_text(encoding="utf-8").split()
        except (OSError, ValueError):
            return False
        return bool(held) and held[0] == str(os.getpid())


class Gate:
    """The only mover. See the module note."""

    def __init__(
        self,
        paths: Paths,
        hub: Hub,
        *,
        loader: Loader = load_checks,
        today: Callable[[], str] | None = None,
        env: Mapping[str, str] | None = None,
        terminal: Callable[[], bool] | None = None,
        run_authority: RunMergeAuthority | None = None,
    ) -> None:
        self.paths = paths
        self.run_authority = run_authority
        self.terminal = terminal or _at_a_terminal
        self.hub = hub
        self.loader = loader
        self.today = today or (lambda: date.today().isoformat())
        self.env: Mapping[str, str] = {} if env is None else env

    # --- reading -------------------------------------------------------------------

    def piece(self, number: int) -> Piece:
        """The piece by its local number or by its synced issue number."""
        found = find_piece(self.paths, number)
        if found is None:
            raise MoveError(
                f"piece {number} is not in the gate's record",
                next_command='gate.py capture --title "<title>" --body-file <file>, '
                f"or gate.py capture {number} for an issue that exists",
            )
        return found

    def numbers(self) -> list[int]:
        folder = self.paths.pieces_dir
        if not folder.is_dir():
            return []
        return sorted(int(p.name) for p in folder.iterdir() if p.is_dir() and p.name.isdigit())

    def fingerprint_changed(self, number: int) -> bool:
        """True when the spec now differs from the fingerprint the gate last took.

        Only an edit the gate did not make shows here, since every gate-made
        change takes a new fingerprint. With the App the body is read from GitHub.
        """
        piece = self.piece(number)
        body = piece.body
        if self.hub.available and piece.issue is not None:
            body = self.hub.read_issue(piece.issue)["body"]
        return _fingerprint_moved(body, piece.fingerprint_data)

    def _issue_now(self, piece: Piece) -> dict[str, Any] | None:
        """The first read of the issue, checked against the record. None with no App."""
        if not self.hub.available or piece.issue is None:
            return None
        try:
            issue = self.hub.read_issue(piece.issue)
        except github.GitHubError as error:
            raise MoveError(error.message, next_command=error.next_command,
                            code=error.code) from error
        found = states.state_labels(issue["labels"])
        if len(found) > 1:
            raise MoveError(
                f"issue {piece.issue} carries two state: labels ({', '.join(found)}), and a "
                "piece is in exactly one state",
                next_command="tell the person: remove the state label that is wrong; the "
                "gate does not choose for them",
            )
        expected = states.label(piece.state)
        flag = states.NEEDS_YOU in issue["labels"]
        if found != [expected] or flag != piece.needs_you:
            raise MoveError(
                f"the labels of issue {piece.issue} were changed by hand: they say "
                f"{', '.join(found) or 'no state'}"
                f"{' with needs-you' if flag else ''}, and the gate's record says "
                f"{expected}{' with needs-you' if piece.needs_you else ''}. The person "
                "outranks the gate, so it leaves the labels as they are",
                next_command="tell the person what gate.py report shows; if they want the "
                f"record's state back, they set the label {expected} themselves",
            )
        return issue

    def _sync_if_able(self, piece: Piece, dry_run: bool) -> Piece:
        """With the App, send a piece's queue as the App before anything else."""
        if not piece.queue or not self.hub.available or dry_run:
            return piece
        try:
            self._flush(piece, self.hub)
        except HandChange as change:
            raise MoveError(
                str(change), next_command="tell the person what gate.py report shows"
            ) from change
        except github.GitHubError as error:
            raise MoveError(error.message, next_command=error.next_command,
                            code=error.code) from error
        return self.piece(piece.number)

    # --- the body --------------------------------------------------------------------

    def _needs(self, body: str, state: str, issue_type: str) -> list[dict[str, Any]]:
        if state in states.CLOSED:
            return []
        try:
            return needs.needs_from_body(body, issue_type=issue_type)
        except spec.SpecError as error:
            return [
                needs.need("spec_error", f"The spec block cannot be read: {error}",
                           "the agent", False)
            ]

    def _write_below(
        self, body: str, found: Sequence[Mapping[str, Any]], print_: str | None
    ) -> str:
        """The body with the gate's needs list and fingerprint marker rewritten."""
        try:
            head, tail = spec.split_after_block(body)
        except spec.SpecError:
            head, tail = "", body
        kept: list[str] = []
        for line in tail.splitlines():
            if line.strip() == NEEDS_HEADING:
                break
            if not _FINGERPRINT_LINE.match(line):
                kept.append(line)
        rest = "\n".join(kept).strip("\n")
        lines = [f"- {n['text']}" for n in found] or ["- None. The piece needs nothing more."]
        marker = f"<!-- loop:fingerprint {print_} -->" if print_ else NO_FINGERPRINT
        parts = [part for part in (head.rstrip("\n"), rest) if part]
        parts.append(NEEDS_HEADING + "\n" + "\n".join(lines))
        parts.append(marker)
        return "\n\n".join(parts) + "\n"

    # --- writing ---------------------------------------------------------------------

    def _queue(self, piece: Piece, ops: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        entries = []
        for offset, op in enumerate(ops):
            entries.append({"kind": "queue", "id": piece.next_id + offset, "op": dict(op)})
        return entries

    def _apply(self, hub: Hub, issue: int, op: Mapping[str, Any], *, check: bool) -> None:
        kind = op["op"]
        if kind == "labels":
            if check:
                now = states.state_labels(hub.read_issue(issue)["labels"])
                if sorted(now) != sorted(op.get("expect", [])):
                    raise HandChange(
                        f"the labels of issue {issue} were changed by hand (they say "
                        f"{', '.join(now) or 'no state'}, and the gate expected "
                        f"{', '.join(op.get('expect', [])) or 'no state'}); the gate leaves "
                        "them as they are"
                    )
            hub.edit_labels(issue, add=list(op["add"]), remove=list(op["remove"]))
        elif kind == "body":
            if check and op.get("base"):
                now_body = hub.read_issue(issue)["body"]
                if _sha(now_body) != op["base"]:
                    raise HandChange(
                        f"the body of issue {issue} was edited on GitHub since the gate last "
                        "wrote it; the gate does not overwrite it"
                    )
            hub.set_body(issue, str(op["text"]))
        elif kind == "comment":
            hub.comment(issue, str(op["text"]))
        elif kind == "close":
            hub.close(issue, str(op["reason"]))
        elif kind == "reopen":
            hub.reopen(issue)

    def _flush(self, piece: Piece, hub: Hub) -> int:
        """Send a piece's queue. Each op sent is marked in the record at once."""
        sent = 0
        issue = piece.issue
        for op in piece.queue:
            if op["op"] == "issue":
                issue = hub.create_issue(str(op["title"]), str(op["body"]), list(op["labels"]))
                evidence.append(
                    self.paths, piece.number, [{"kind": "synced", "id": op["id"], "issue": issue}]
                )
            else:
                if issue is None:
                    raise HandChange(f"piece {piece.number} has no issue yet")
                self._apply(hub, issue, op, check=True)
                evidence.append(self.paths, piece.number, [{"kind": "synced", "id": op["id"]}])
            sent += 1
        return sent

    def _waiting(self) -> dict[str, Any]:
        return {"github": "queued", "waiting": True,
                "next": github.sync_command(self.paths.root)}

    def _commit(
        self,
        piece: Piece,
        issue_read: Mapping[str, Any] | None,
        ops: Sequence[Mapping[str, Any]],
        entries: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Read twice, then write GitHub (or queue) and the record in one step."""
        if issue_read is not None and piece.issue is not None:
            try:
                self.hub.read_again(piece.issue, issue_read)
            except github.ReadTwiceError as error:
                raise MoveError(error.message, next_command=error.next_command) from error
        again = read_piece(self.paths, piece.number)
        if again is None or again.entries != piece.entries:
            raise MoveError(
                f"piece {piece.number} moved between the gate's two reads of its record, so "
                "another session changed it",
                next_command="run gate.py report, then the same command again",
            )
        if self.hub.available and piece.issue is not None:
            try:
                for op in ops:
                    self._apply(self.hub, piece.issue, op, check=False)
            except github.GitHubError as error:
                raise MoveError(
                    f"{error.message}; the gate's record is unchanged",
                    next_command=error.next_command,
                    code=ExitCode.ENVIRONMENT,
                ) from error
            evidence.append(self.paths, piece.number, entries)
            return {"github": "written"}
        evidence.append(self.paths, piece.number, entries + self._queue(piece, ops))
        return self._waiting() if ops else {"github": "none"}

    def _ops(
        self,
        piece: Piece,
        old_labels: Sequence[str],
        new_labels: Sequence[str],
        old_body: str,
        new_body: str,
        comment: str | None = None,
        extra: Sequence[Mapping[str, Any]] = (),
    ) -> list[dict[str, Any]]:
        ops: list[dict[str, Any]] = []
        if new_body != old_body:
            ops.append({"op": "body", "text": new_body, "base": _sha(old_body)})
        if comment:
            ops.append({"op": "comment", "text": comment})
        ops.extend(dict(op) for op in extra)
        managed = [n for n in old_labels if n.startswith(states.STATE_PREFIX)
                   or n == states.NEEDS_YOU]
        remove = [n for n in managed if n not in new_labels]
        add = [n for n in new_labels if n not in old_labels]
        if add or remove:
            ops.append({"op": "labels", "add": add, "remove": remove,
                        "expect": states.state_labels(old_labels)})
        return ops

    # --- the commands ----------------------------------------------------------------

    def capture(
        self,
        *,
        title: str,
        body: str | None,
        issue_type: str = "feature",
        number: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Move 1: a new piece in shaping. With `number`, an issue that exists."""
        if issue_type not in states.TYPES:
            raise MoveError(f"{issue_type!r} is not a type", code=ExitCode.USAGE,
                            next_command="use --type feature, bug or chore")
        existing: dict[str, Any] | None = None
        if number is not None:
            if read_piece(self.paths, number) is not None:
                raise MoveError(f"piece {number} is captured already",
                                next_command=f"gate.py report {number}")
            if self.hub.available:
                try:
                    existing = self.hub.read_issue(number)
                except github.GitHubError as error:
                    raise MoveError(error.message, next_command=error.next_command,
                                    code=error.code) from error
                if states.state_labels(existing["labels"]):
                    raise MoveError(
                        f"issue {number} already carries a state label",
                        next_command="tell the person: the gate captures only an issue "
                        "with no state label",
                    )
                title = title or existing["title"]
                body = existing["body"] if body is None else body
            elif body is None:
                raise MoveError(
                    "with no App the gate cannot read the issue, so it needs the body",
                    next_command=f"gate.py capture {number} --title <title> --body-file <file>",
                )
        body = body or ""
        local = number if number is not None else (max(self.numbers(), default=0) + 1)
        move = states.by_number(1)
        self._check(move, local, states.NEW, "shaping", None, title, body, [], {})
        found = self._needs(body, "shaping", issue_type)
        needs_you = needs.needs_you(found)
        final = self._write_below(body, found, None)
        labels = [states.label("shaping"), states.TYPE_PREFIX + issue_type]
        if needs_you:
            labels.append(states.NEEDS_YOU)
        summary: dict[str, Any] = {"state": "shaping", "needs_you": needs_you, "move": 1,
                                   "needs": len(found)}
        if dry_run:
            return {"piece": local, **summary}
        entries_after: list[dict[str, Any]] = [
            {"kind": "body", "text": final, "sha": _sha(final), "why": "capture"},
            {"kind": "needs", "needs": found, "needs_you": needs_you},
        ]
        if self.hub.available:
            try:
                if existing is not None and number is not None:
                    issue = number
                    if final != existing["body"]:
                        self.hub.set_body(issue, final)
                    self.hub.edit_labels(issue, add=labels, remove=[])
                else:
                    issue = self.hub.create_issue(title, final, labels)
            except github.GitHubError as error:
                raise MoveError(f"{error.message}; the gate's record is unchanged",
                                next_command=error.next_command,
                                code=ExitCode.ENVIRONMENT) from error
            if read_piece(self.paths, issue) is not None:
                raise MoveError(
                    f"GitHub gave the new issue the number {issue}, which a local piece holds",
                    next_command="tell the person: a piece captured before the App has the "
                    "same number; run gate.py sync first",
                    code=ExitCode.ENVIRONMENT,
                )
            capture = {"kind": "capture", "title": title, "type": issue_type, "issue": issue,
                       "at": self.today()}
            evidence.append(self.paths, issue, [capture, *entries_after])
            return {"piece": issue, "issue": issue, "github": "written", **summary}
        capture = {"kind": "capture", "title": title, "type": issue_type, "issue": number,
                   "at": self.today()}
        if number is None:
            ops: list[dict[str, Any]] = [
                {"op": "issue", "title": title, "body": final, "labels": labels}
            ]
        else:
            ops = [{"op": "body", "text": final, "base": None},
                   {"op": "labels", "add": labels, "remove": [], "expect": []}]
        queue = [{"kind": "queue", "id": index + 1, "op": op} for index, op in enumerate(ops)]
        evidence.append(self.paths, local, [capture, *entries_after, *queue])
        return {"piece": local, "issue": number, **summary, **self._waiting()}

    def merge_authority(self) -> str:
        """Who is asking: "run" (the run script's own process), "person" or "" (an agent).

        An agent session holds neither. The run script hands the gate a `RunMergeAuthority`
        object, which holds only in the process that owns the run's lock. A person is a call
        with no agent-session marker, made with standard input and output on a terminal, as
        `sync` checks it. A pipe, a script and a hook have no terminal.
        """
        if self.run_authority is not None and self.run_authority.held():
            return "run"
        if not github.in_agent_session(self.env) and self.terminal():
            return "person"
        return ""

    def record_manual_main_check(
        self, number: int, *, pull_request: int, merge_commit: str,
        main_moved: bool, green: bool,
    ) -> None:
        """Record project checks for the person's already merged tree."""
        if self.merge_authority() != "person":
            raise MoveError("only a person at a terminal can record manual merge checks",
                            next_command="record the manual merge in your terminal")
        piece = self.piece(number)
        evidence.append(self.paths, piece.number, [{
            "kind": "main-check", "pull_request": pull_request,
            "merge_commit": merge_commit, "main_moved": main_moved,
            "tested_commit_merged": True, "result": "green" if green else "red",
        }])

    def _check(
        self,
        move: states.Move,
        number: int,
        origin: str,
        target: str,
        reason: str | None,
        title: str,
        body: str,
        record: Sequence[Mapping[str, Any]],
        options: Mapping[str, str],
    ) -> CheckResult:
        check = self.loader(move.checks)
        if check is None:
            raise MoveError(
                f"the checks for move {move.number} ({origin} to {target}), "
                f"loop/gates/{move.checks}.py, are not installed yet",
                next_command=f"wait for the later piece that adds loop/gates/{move.checks}.py "
                "(docs/design/v1/build-plan.md); the piece stays where it is",
            )
        try:
            parsed: dict[str, Any] | None = spec.parse(body).to_dict()
        except spec.SpecError:
            parsed = None
        ctx = CheckContext(number=number, move=move, origin=origin, target=target,
                           reason=reason, title=title, body=body, spec=parsed,
                           record=record, paths=self.paths, options=dict(options),
                           authority=self.merge_authority(),
                           person_github=(self.merge_authority() == "person" and
                                          bool(getattr(self.hub, "as_person", False))))
        result = check(ctx)
        if not result.ok:
            raise MoveError(
                "; ".join(result.failures) or f"the checks of move {move.number} failed",
                next_command=result.next_command or f"gate.py report {number}",
                data=dict(result.data),
            )
        return result

    def move(
        self,
        number: int,
        target: str,
        *,
        reason: str | None = None,
        options: Mapping[str, str] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Move a piece to `target` by the one move the table allows, or refuse."""
        if target not in states.STATES:
            raise MoveError(
                f"{target!r} is not a state. The states are: {', '.join(states.STATES)}",
                next_command="gate.py move <number> <state>",
                code=ExitCode.USAGE,
            )
        piece = self._sync_if_able(self.piece(number), dry_run)
        number = piece.number
        issue = self._issue_now(piece)
        body = issue["body"] if issue is not None else piece.body
        origin = piece.state
        move = states.find(origin, target)
        if move is None:
            legal = states.targets_from(origin)
            raise MoveError(
                f"no move takes a piece from {origin} to {target}, so the gate refuses it",
                next_command=(f"gate.py move {number} <{' | '.join(legal)}>" if legal
                              else f"piece {number} is {origin}; no move leaves it"),
            )
        reason = (reason or "").strip() or None
        if move.back and reason is None:
            raise MoveError(
                f"move {move.number} ({origin} to {target}) is a move back, and every move "
                "back carries a written reason",
                next_command=f'gate.py move {number} {target} --reason "<why>"',
            )
        asked = move.number
        repeats = piece.counts.get(move.number, 0)
        if move.number in states.COUNTED and repeats >= states.REPEAT_LIMIT:
            earlier = [str(m.get("reason")) for m in piece.recent if m["move"] == move.number]
            in_all = piece.totals.get(asked, 0) + 1
            move = states.back_to_shaping(origin)
            target = "shaping"
            reason = (
                f"Move {asked} was asked for the {_ordinal(repeats + 1)} time since the piece "
                f"last left shaping (the {_ordinal(in_all)} time in all), so the piece goes "
                f"back to shaping with its history: {'; '.join([*earlier, str(reason)])}"
            )
        if states.anti_circle(move, target):
            seen = {_norm(r) for r in piece.reasons}
            if _norm(str(reason)) in seen:
                raise MoveError(
                    f"the reason {reason!r} is already on piece {number}; a move back to "
                    "shaping must add a new need, so the piece does not go round in a circle",
                    next_command=f'gate.py move {number} shaping --reason "<what is new>"',
                )
        try:
            result = self._check(move, number, origin, target, reason, piece.title, body,
                                 piece.record, options or {})
        except MoveError as error:
            if move.number == 5 and error.data.get("attempt") and not dry_run:
                raise self._failed_attempt(piece, error) from error
            if error.data.get("send_back") and move.number == 4 and not dry_run:
                raise self._sent_back(number, error) from error
            if error.data.get("send_back") and dry_run:
                back = "move 6" if move.number == 5 else "move 3"
                error.message += f" (a real run sends the piece back to shaping by {back})"
            raise
        new_body = str(result.data.get("body") or body)
        if states.anti_circle(move, target):
            new_body = self._add_need(new_body, move.number, str(reason))
        found = self._needs(new_body, target, piece.issue_type)
        needs_you = target not in states.CLOSED and needs.needs_you(found)
        fp_entry = self._fingerprint_entry(piece, result, body, new_body, move.number)
        print_ = (fp_entry["fingerprint"]["fingerprint"] if fp_entry else piece.fingerprint)
        final = self._write_below(new_body, found, print_)
        summary: dict[str, Any] = {"piece": number, "move": move.number, "asked": asked,
                                   "from": origin, "to": target, "needs_you": needs_you}
        if result.data.get("must_look"):
            summary["must_look"] = list(result.data["must_look"])
        if dry_run:
            return summary
        self._act(result)
        if issue is not None and result.data.get("act") is not None:
            issue = self._read_after_act(piece, issue)
        old_labels = issue["labels"] if issue is not None else piece.labels()
        new_labels = [states.label(target), *(
            [states.NEEDS_YOU] if needs_you else [])]
        extra: list[dict[str, Any]] = []
        if target == "done":
            extra.append({"op": "close", "reason": "completed"})
        elif target == "dropped":
            extra.append({"op": "close", "reason": "not planned"})
        elif origin in states.CLOSED:
            extra.append({"op": "reopen"})
        comment = (f"Move {move.number}, {origin} to {target}. Reason: {reason}"
                   if reason else None)
        keep = [n for n in old_labels if not n.startswith(states.STATE_PREFIX)
                and n != states.NEEDS_YOU]
        ops = self._ops(piece, old_labels, [*keep, *new_labels], body, final, comment, extra)
        entries: list[dict[str, Any]] = [
            {"kind": "move", "move": move.number, "asked": asked, "from": origin, "to": target,
             "reason": reason, "at": self.today()},
        ]
        must_look = [str(r) for r in result.data.get("must_look", [])]
        if must_look:
            entries[0]["must_look"] = must_look
        if final != piece.body:
            why = "gate-made change" if final != body else "read from GitHub"
            entries.append({"kind": "body", "text": final, "sha": _sha(final), "why": why})
        entries.append({"kind": "needs", "needs": found, "needs_you": needs_you})
        if fp_entry:
            entries.append(fp_entry)
        entries.extend(dict(extra_entry) for extra_entry in result.data.get("entries", []))
        written = self._commit(piece, issue, ops, entries)
        if fp_entry:
            summary["fingerprint"] = fp_entry["fingerprint"]["fingerprint"]
        return {**summary, **written}

    def _read_after_act(self, piece: Piece, before: dict[str, Any]) -> dict[str, Any]:
        """The issue again, after an action that may have changed it.

        A merge closes the issues its `Closes` lines name, so the issue's state is allowed to
        differ from the first read. Its labels and its body are not. The read made after the
        action is the one the second read, just before the write, is compared with.
        """
        assert piece.issue is not None
        try:
            now = self.hub.read_issue(piece.issue)
        except github.GitHubError as error:
            raise MoveError(error.message, next_command=error.next_command,
                            code=error.code) from error
        if sorted(now["labels"]) != sorted(before["labels"]) or now["body"] != before["body"]:
            raise MoveError(
                f"issue {piece.issue} changed while the action of the move ran, so another "
                "session or the person changed it",
                next_command="run gate.py report, then the same command again",
            )
        return now

    @staticmethod
    def _act(result: CheckResult) -> None:
        """Run the action a check handed over, once, on a real move and never on a dry run.

        The merge is the one such action: the check proves every condition holds, and the gate
        merges only then. It runs before the record is written. A failed action leaves the piece
        where it was. A merge that went through while the record failed is made right by asking
        the same move again, which finds the pull request merged.
        """
        act = result.data.get("act")
        if act is None:
            return
        try:
            act()
        except github.GitHubError as error:
            raise MoveError(error.message, next_command=error.next_command,
                            code=error.code) from error

    def _failed_attempt(self, piece: Piece, error: MoveError) -> MoveError:
        """The refusal of an attempt the gate judged and failed (move 5).

        The check puts the attempt's entry in `attempt` in the data of its refusal. The gate
        writes it to the piece record, and the piece stays building, so the next builder's brief
        reads it. When the check also asks to `send_back` (no attempt is left), the piece goes
        back to shaping by move 6, with the same machinery as any move. A dry run never gets here.
        """
        again = read_piece(self.paths, piece.number)
        if again is None or again.entries != piece.entries:
            return MoveError(
                f"piece {piece.number} moved between the gate's two reads of its record, so "
                "another session changed it, and the attempt was not logged",
                next_command="run gate.py report, then the same command again",
            )
        evidence.append(self.paths, piece.number, [dict(error.data["attempt"])])
        if error.data.get("send_back"):
            return self._sent_back(piece.number, error)
        error.message += ". The attempt is logged in the piece record, and the piece stays building"
        return error

    def _sent_back(self, number: int, error: MoveError) -> MoveError:
        """The refusal of a check whose fault sends the piece back to shaping.

        A claim that fails sends it by move 3, and an attempt with none left by move 6. A check
        asks for it with `send_back` (the reason) in the data of its refusal. The move is made
        here, by the same machinery as any move, so the reason is posted, the anti-circle rule
        applies and the spec gets the need. A dry run never gets here.
        """
        reason = str(error.data["send_back"])
        try:
            done = self.move(number, "shaping", reason=reason)
        except MoveError as inner:
            return MoveError(
                f"{error.message}. The gate tried to send the piece back to shaping and could "
                f"not: {inner.message}",
                next_command=inner.next_command, code=error.code,
            )
        return MoveError(
            f"{error.message}. The piece was sent back to shaping by move {done['move']}, with "
            "the reason written on it and a new open question in the spec",
            next_command=f"settle the open question in /shape, then gate.py move {number} ready",
            code=error.code, data={"sent_back": True},
        )

    def _add_need(self, body: str, move_number: int, reason: str) -> str:
        item = (f"{reason} Why it matters: move {move_number} sent the piece back to "
                "shaping for it. Who: the person or the agent. (Written by the gate, "
                f"{self.today()}.)")
        try:
            return spec.add_list_item(body, "open_questions", item)
        except spec.SpecError:
            return body

    def _fingerprint_entry(
        self, piece: Piece, result: CheckResult, old_body: str, new_body: str, why_move: int
    ) -> dict[str, Any] | None:
        given = result.data.get("fingerprint")
        if given:
            return {"kind": "fingerprint", "fingerprint": dict(given),
                    "why": f"move {why_move}", "at": self.today()}
        if piece.fingerprint_data and new_body != old_body:
            return self._retake(piece, new_body)
        return None

    def _retake(self, piece: Piece, body: str) -> dict[str, Any] | None:
        if not piece.fingerprint_data:
            return None
        try:
            taken = fingerprint.take(body, str(piece.fingerprint_data.get("judge_commit", "")))
        except (spec.SpecError, fingerprint.FingerprintError):
            return None
        return {"kind": "fingerprint", "fingerprint": taken, "why": "gate-made change",
                "at": self.today()}

    def answer(
        self,
        number: int,
        *,
        question: str,
        answer: str,
        by: str,
        parked: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Write a (late) answer under Decisions, drop the question and take a new fingerprint.

        `parked` is for a builder's question, which waits in building and never in the spec:
        when no open question matches, the gate writes only the Decision line. It is refused in
        any other state.

        `by` names who answered. An agent session cannot record the person: the
        person records their own answer, in their own terminal.
        """
        if not answer.strip() or not question.strip() or not by.strip():
            raise MoveError("an answer needs the question, the answer and who answered",
                            next_command=f'gate.py answer {number} --question "<q>" '
                            '--answer "<a>" --by "<who answered>"', code=ExitCode.USAGE)
        agent = github.in_agent_session(self.env)
        if agent and " ".join(by.split()).casefold() != AGENT:
            raise MoveError(
                f"an agent session records an answer only --by {AGENT!r}, not {by.strip()!r}; "
                "any other name is the person's to record, in their own terminal",
                next_command="tell the person to run it themselves, in their own terminal: "
                f"{github.gate_command(self.paths.root)} answer {number} --question "
                f'"<q>" --answer "<a>" --by "<their name>"; or record it --by "{AGENT}"',
            )
        by = by.strip()
        piece = self._sync_if_able(self.piece(number), dry_run)
        number = piece.number
        issue = self._issue_now(piece)
        body = issue["body"] if issue is not None else piece.body
        try:
            open_questions = spec.parse(body).open_questions
        except spec.SpecError as error:
            raise MoveError(str(error), next_command=error.next_command) from error
        wanted = _norm(question)
        match = next((q for q in open_questions if wanted and wanted in _norm(q)), None)
        if parked and piece.state != "building":
            raise MoveError(
                f"piece {number} is {piece.state}; --parked answers a builder's question, which "
                "waits only in building",
                next_command=f"gate.py answer {number} --question <it> --answer <yours> --by "
                "<you> (without --parked) for a question the spec holds",
            )
        if match is None and not parked:
            raise MoveError(
                f"the spec of piece {number} holds no open question like {question!r}",
                next_command=f"gate.py report {number} --json, then use one of its questions; "
                f"for a builder's question parked in building, add --parked",
            )
        if match is None:
            match = question.strip()
            new_body = body
        else:
            new_body = spec.remove_list_item(body, "open_questions", match)
        decision = (f"{question.strip()} Answer: {answer.strip()} Decided by {by}, "
                    f"{self.today()}; written by the gate.")
        new_body = spec.add_list_item(new_body, "decisions", decision)
        found = self._needs(new_body, piece.state, piece.issue_type)
        needs_you = piece.state not in states.CLOSED and needs.needs_you(found)
        fp_entry = self._retake(piece, new_body)
        print_ = fp_entry["fingerprint"]["fingerprint"] if fp_entry else piece.fingerprint
        final = self._write_below(new_body, found, print_)
        summary: dict[str, Any] = {"piece": number, "question": match, "decision": decision,
                                   "needs_you": needs_you}
        if fp_entry:
            summary["fingerprint"] = fp_entry["fingerprint"]["fingerprint"]
        if dry_run:
            return summary
        old_labels = issue["labels"] if issue is not None else piece.labels()
        keep = [n for n in old_labels if n != states.NEEDS_YOU]
        new_labels = [*keep, *([states.NEEDS_YOU] if needs_you else [])]
        ops = self._ops(piece, old_labels, new_labels, body, final)
        entries: list[dict[str, Any]] = [
            {"kind": "answer", "question": match, "answer": answer.strip(), "by": by,
             "recorded_in": "an agent session" if agent else "a terminal", "at": self.today()},
            {"kind": "body", "text": final, "sha": _sha(final), "why": "gate-made change"},
            {"kind": "needs", "needs": found, "needs_you": needs_you},
        ]
        if fp_entry:
            entries.append(fp_entry)
        return {**summary, **self._commit(piece, issue, ops, entries)}

    def set_spec(self, number: int, body: str, *, dry_run: bool = False) -> dict[str, Any]:
        """Hand the gate a new spec for a piece in shaping. It rewrites the needs."""
        piece = self._sync_if_able(self.piece(number), dry_run)
        number = piece.number
        if piece.state != "shaping":
            raise MoveError(
                f"piece {number} is {piece.state}; its spec changes only in shaping",
                next_command=f'gate.py move {number} shaping --reason "<why>"',
            )
        issue = self._issue_now(piece)
        current = issue["body"] if issue is not None else piece.body
        dropped = _dropped_questions(current, body)
        if dropped:
            raise MoveError(
                f"the new spec of piece {number} drops the open question {dropped[0]!r}; only "
                "gate.py answer closes a question, and it writes the answer under Decisions",
                next_command=f'gate.py answer {number} --question "<the question>" '
                '--answer "<the answer>" --by "<who answered>", then gate.py spec again with '
                "every open question kept",
            )
        found = self._needs(body, "shaping", piece.issue_type)
        needs_you = needs.needs_you(found)
        final = self._write_below(body, found, piece.fingerprint)
        summary: dict[str, Any] = {"piece": number, "needs": len(found), "needs_you": needs_you}
        if dry_run:
            return summary
        old_labels = issue["labels"] if issue is not None else piece.labels()
        keep = [n for n in old_labels if n != states.NEEDS_YOU]
        ops = self._ops(piece, old_labels, [*keep, *([states.NEEDS_YOU] if needs_you else [])],
                        current, final)
        entries: list[dict[str, Any]] = [
            {"kind": "body", "text": final, "sha": _sha(final), "why": "spec handed to the gate"},
            {"kind": "needs", "needs": found, "needs_you": needs_you},
        ]
        return {**summary, **self._commit(piece, issue, ops, entries)}

    def comment(self, number: int, text: str, *, dry_run: bool = False) -> dict[str, Any]:
        """Post a comment on the piece's issue as the App, or queue it."""
        if not text.strip():
            raise MoveError("the comment is empty", code=ExitCode.USAGE,
                            next_command=f"gate.py comment {number} --body-file <file>")
        piece = self._sync_if_able(self.piece(number), dry_run)
        number = piece.number
        if dry_run:
            return {"piece": number, "comment": text}
        issue = self._issue_now(piece)
        ops = [{"op": "comment", "text": text}]
        return {"piece": number, **self._commit(piece, issue, ops, [])}

    def create_labels(self, *, dry_run: bool = False) -> dict[str, Any]:
        """Create the gate's labels that the repository lacks. The old labels stay."""
        if not self.hub.available:
            raise MoveError(
                "the gate's GitHub App is not set up yet, so the gate does not act on GitHub",
                next_command=github.sync_command(self.paths.root)
                + " (sync creates the labels too)",
            )
        try:
            present = set(self.hub.list_labels())
            missing = [row for row in states.LABELS if row[0] not in present]
            if not dry_run:
                for name, colour, text in missing:
                    self.hub.create_label(name, colour, text)
        except github.GitHubError as error:
            raise MoveError(error.message, next_command=error.next_command,
                            code=error.code) from error
        return {"created": [row[0] for row in missing],
                "present": sorted(present & {row[0] for row in states.LABELS})}

    def sync(
        self, person: Hub, *, dry_run: bool = False, confirm: str | None = None
    ) -> dict[str, Any]:
        """Send every queued GitHub write with the person's own sign-in. The person runs it.

        The dry run prints a digest of the queue. A real sync needs that digest
        in `confirm`, and refuses when the queue has changed since, so it sends
        only the writes the person read.
        """
        if github.in_agent_session(self.env):
            raise MoveError(
                "gate.py sync acts with the person's own sign-in, so only the person runs it, "
                "never an agent session",
                next_command=github.sync_command(self.paths.root),
            )
        done: list[dict[str, Any]] = []
        refusals: list[dict[str, Any]] = []
        pending = [p for p in (read_piece(self.paths, n) for n in self.numbers())
                   if p is not None and p.queue]
        digest = queue_digest(pending)
        if dry_run:
            return {
                "pieces": [{"piece": p.number, "issue": p.issue, "queued": len(p.queue),
                            "writes": [_shown(op) for op in p.queue]} for p in pending],
                "refused": [],
                "digest": digest,
                "listing": _listing(pending) or "Nothing is waiting.",
                "next": "read every write above. Each is posted in your own name. If you want "
                f"them all, run: {github.gate_command(self.paths.root)} sync --confirm {digest}",
            }
        if confirm is None:
            raise MoveError(
                "gate.py sync sends only the writes the person read, so it needs --confirm with "
                "the digest that gate.py sync --dry-run printed",
                next_command=github.sync_command(self.paths.root),
            )
        if confirm.strip().casefold() != digest:
            raise MoveError(
                "the queue changed after the dry run that printed this digest, so sync sends "
                "nothing; read the queue again",
                next_command=github.sync_command(self.paths.root),
            )
        if not self.terminal():
            raise MoveError(
                "gate.py sync posts in the person's name, so it runs only with a person at a "
                "terminal: its standard input and output must both be a terminal",
                next_command=github.sync_command(self.paths.root),
            )
        try:
            if pending:
                present = set(person.list_labels())
                for name, colour, text in states.LABELS:
                    if name not in present:
                        person.create_label(name, colour, text)
            for piece in pending:
                try:
                    sent = self._flush(piece, person)
                    done.append({"piece": piece.number, "sent": sent})
                except HandChange as change:
                    refusals.append({"piece": piece.number, "why": str(change)})
                    done.append({"piece": piece.number, "sent": None})
        except github.GitHubError as error:
            raise MoveError(error.message, next_command=error.next_command,
                            code=error.code) from error
        return {"pieces": done, "refused": refusals}

    # --- the report ------------------------------------------------------------------

    def report(self, *, brief: bool = False, number: int | None = None) -> dict[str, Any]:
        """Where each piece is, what needs the person, what waits, what was changed by hand."""
        rows: list[dict[str, Any]] = []
        problems: list[dict[str, Any]] = []
        hand: list[dict[str, Any]] = []
        if number is not None:
            wanted = find_piece(self.paths, number)
            number = wanted.number if wanted is not None else number
        chosen = [number] if number is not None else self.numbers()
        compare = self.hub.available and not brief
        for n in chosen:
            try:
                piece = read_piece(self.paths, n)
            except MoveError as error:
                problems.append({"piece": n, "error": error.message})
                continue
            if piece is None:
                continue
            row: dict[str, Any] = {"piece": n, "issue": piece.issue, "state": piece.state,
                                   "needs_you": piece.needs_you, "waiting_for_sync":
                                   bool(piece.queue), "must_look": piece.must_look}
            if not brief:
                row.update({"title": piece.title, "type": piece.issue_type,
                            "needs": piece.needs, "fingerprint": piece.fingerprint,
                            "queued": len(piece.queue),
                            "moves": [m["move"] for m in piece.history]})
            if number is not None:
                try:
                    row["open_questions"] = spec.parse(piece.body).open_questions
                except spec.SpecError:
                    row["open_questions"] = []
            rows.append(row)
            if compare and piece.issue is not None and not piece.queue:
                try:
                    labels = self.hub.read_issue(piece.issue)["labels"]
                except github.GitHubError as error:
                    problems.append({"piece": n, "error": error.message})
                    continue
                found = states.state_labels(labels)
                flag = states.NEEDS_YOU in labels
                if found != [states.label(piece.state)] or flag != piece.needs_you:
                    hand.append({"piece": n, "issue": piece.issue, "record": piece.state,
                                 "labels": found, "needs_you_record": piece.needs_you,
                                 "needs_you_label": flag})
        waiting = [r["piece"] for r in rows if r["waiting_for_sync"]]
        person = [r["piece"] for r in rows if r["needs_you"]]
        if waiting:
            next_line = github.sync_command(self.paths.root)
        elif hand:
            next_line = "tell the person which labels were changed by hand; the gate leaves them"
        elif problems:
            next_line = "stop and tell the person about the record that cannot be read"
        elif person:
            next_line = f"/shape: piece {person[0]} has a question only the person can answer"
        elif rows:
            next_line = "/run for the ready pieces, or /shape to capture or shape one"
        else:
            next_line = "/shape to capture the first idea"
        out: dict[str, Any] = {"app": self.hub.available, "pieces": rows,
                               "waiting_for_sync": waiting, "needs_you": person,
                               "problems": problems, "next": next_line}
        if not brief:
            out["hand_changed"] = hand
            out["labels_compared"] = compare
        return out
