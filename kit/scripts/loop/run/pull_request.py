#!/usr/bin/env python3
# contract: agent
# contract: changes-state
"""The pull request step and the merge decision of a run.

The engine (`loop.run.engine`) calls `run_hook` for the events of a run. This module answers
`built-all` and `run-end`. It runs after the integration loop and the review loop, so a branch
reaches it only when its final combined check is green and its review is clean.

What it does, for each combined branch (a track) that is clean on its head:

1. It splits the branch into parts of whole pieces when it is past the policy's
   `pull_request_size_limit` (lines changed). An isolated track, which holds a piece that needs
   individual review and every dependent of it, gives each piece its own part. Each part is a
   commit the loop tested: the join of its last piece, or the head of the branch for the last
   part. A part after the first is based on the branch of the part before it.
2. It writes the title and the body: each piece with its judge result, held-out result, review
   verdict and worth-knowing notes, and one `Closes` line for each piece. Text from agents and
   issues is made safe first (`loop.closing.neutralise`), and the gate scans the result again.
3. It pushes each branch through `loop.github.push` (the secret scan runs first), opens each pull
   request as the App, and asks the gate for move 10 for each piece, giving it the facts.

With no App nothing is pushed and nothing is opened. The body goes to a file in the run folder,
the run stops at this step with a `next:` line that names the exact push and pull request
commands for the person, and the pieces wait in review.

A pre-approved run (`run.py --merge-pre-approved`, kept in the run record for this run only)
then asks the gate for move 11 for each pull request, in order. The gate merges the exact tested
commit only when every condition holds, and a piece with a must-look reason, anywhere in the
run, makes every such merge wait for the person.

After the run, this module is also the door for the person and the agent:

    python3 -m loop.run.pull_request status  --run NAME
    python3 -m loop.run.pull_request merge   --run NAME --said "<the person's words>"
    python3 -m loop.run.pull_request reject  --run NAME --piece N [--piece N] --reason TEXT
    python3 -m loop.run.pull_request refresh --run NAME
    python3 -m loop.run.pull_request sweep   --run NAME

`reject` is move 13 for the named pieces, and move 12 for the others of the same branch. The
combined branch is rebuilt without the rejected pieces under a fresh name, and the old pull
request is closed. `refresh` is move 12 for every piece when `main` moved after the final
check: the branch is rebuilt on the new `main`. `sweep` reads the open pull requests: a merge by
the person, a closed pull request and the person's comments, each of which becomes the right
move. Then `run.py --run NAME` builds what went back, checks the branch again and opens the
pull request that replaces the old one.

Nothing here reverts, resets or force pushes. A check that did not run is a refusal, never a
pass.
"""

from __future__ import annotations

import argparse
import contextlib
import re
import shlex
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

if __package__ in (None, ""):  # run by path: put the kit's scripts folder on the path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from loop import cli, closing, github, moves, pulls
from loop.cli import ExitCode
from loop.gates import merge as merge_gate
from loop.paths import Paths
from loop.run import integrate
from loop.run import record as run_record
from loop.run.gateway import Gateway, Reply

MAIN = "main"
TITLE_LIMIT = 120
NOTE_LIMIT = 400
REASON_LIMIT = 900
TRUSTED = ("OWNER", "MEMBER", "COLLABORATOR")  # who may send a piece back by a comment

class Api(Protocol):
    """The pull request calls this step makes. `loop.pulls.Pulls` is the real one."""

    def create(self, *, base: str, head: str, title: str, body: str) -> tuple[int, str]: ...

    def view(self, ref: int | str) -> pulls.PullRequest: ...

    def close(self, number: int, comment: str) -> None: ...

    def set_base(self, number: int, base: str) -> None: ...


Mover = Callable[[int, str, str | None, Mapping[str, str]], Reply]
Push = Callable[[str], dict[str, Any]]


class PullRequestRefusal(Exception):
    """The step could not go on, so it refuses and never passes. The message names the next step."""

    def __init__(self, message: str, next_command: str) -> None:
        super().__init__(message)
        self.next_command = next_command


# --- the split --------------------------------------------------------------------------------


def plan_groups(
    sizes: Sequence[tuple[int, int]], limit: int, *, one_each: bool
) -> list[list[int]]:
    """Whole pieces, in the order they joined, grouped so no group passes `limit` lines.

    A piece larger than the limit is a group of its own. `one_each` gives every piece its own
    group, for a track whose pieces each need individual review.
    """
    groups: list[list[int]] = []
    held = 0
    for number, size in sizes:
        if one_each or not groups or held + size > limit:
            groups.append([number])
            held = size
        else:
            groups[-1].append(number)
            held += size
    return groups


# --- the words --------------------------------------------------------------------------------


@dataclass
class PieceFacts:
    number: int
    issue: int
    title: str
    judge: str
    held_out: bool
    review: str
    notes: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    must_look: list[str] = field(default_factory=list)
    size: int = 0


def _plain(text: str, limit: int = NOTE_LIMIT) -> str:
    """Text from an agent or an issue, made safe: one line, no reference, cut to a limit."""
    flat = " ".join(closing.neutralise(text).split())
    return flat if len(flat) <= limit else flat[: limit - 3].rstrip() + "..."


def render_title(run: str, pieces: Sequence[PieceFacts], part: int, parts: int) -> str:
    names = ", ".join(_plain(p.title, 60) for p in pieces)
    tail = f" (part {part} of {parts})" if parts > 1 else ""
    head = f"Run {run}: "
    room = TITLE_LIMIT - len(head) - len(tail)
    names = names if len(names) <= room else names[: room - 3].rstrip() + "..."
    return f"{head}{names}{tail}"


def render_body(
    pieces: Sequence[PieceFacts],
    *,
    run: str,
    branch: str,
    head: str,
    checks: int,
    held_runs: int,
    part: int,
    parts: int,
    general: Sequence[str],
) -> str:
    lines = [f"## Run {run}", ""]
    where = f", part {part} of {parts}" if parts > 1 else ""
    lines.append(f"Branch `{branch}`{where}. Tested at `{head[:7]}`. The final combined check ran "
                 f"{checks} check(s), and {held_runs} hidden case(s) ran with them.")
    if parts > 1:
        lines.append(f"This pull request is part {part} of {parts}. Each part holds whole "
                     "pieces. A part is based on the part before it and merges after it. The "
                     "docs commit and the changelog entries of every piece come in the last "
                     "part.")
    lines += ["", "## Pieces", ""]
    for piece in pieces:
        lines.append(f"### Piece {piece.number}: {_plain(piece.title, 100)}")
        lines.append("")
        lines.append(f"- Judge: `{_plain(piece.judge, 160)}`, green at the final combined check "
                     f"of `{branch}`.")
        lines.append("- Held-out: the hidden cases ran at the final check and passed."
                     if piece.held_out else "- Held-out: none for this piece.")
        lines.append(f"- Review: {_plain(piece.review)}.")
        if piece.must_look:
            lines.append("- The person must look at this piece: "
                         + _plain("; ".join(piece.must_look)) + ".")
        for label, items in (("Added", piece.added), ("Changed", piece.changed),
                             ("Removed", piece.removed)):
            for item in items:
                lines.append(f"- {label}: {_plain(item)}")
        if piece.notes:
            lines.append("- Worth knowing:")
            lines += [f"  - {_plain(note)}" for note in piece.notes]
        lines += ["", f"Closes #{piece.issue}", ""]
    if general:
        lines += ["## Worth knowing for the whole run", ""]
        lines += [f"- {_plain(note)}" for note in general]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def push_and_open_commands(root: str, branches: Sequence[str], opens: Sequence[
        tuple[str, str, str, str]]) -> str:
    """The exact commands for the person when the gate has no App.

    `opens` holds (base, head, title, body file) for each pull request, in order.
    """
    push = f"git push origin {' '.join(shlex.quote(b) for b in branches)}"
    creates = [
        f"gh pr create --base {shlex.quote(base)} --head {shlex.quote(head)} "
        f"--title {shlex.quote(title)} --body-file {shlex.quote(body)}"
        for base, head, title, body in opens]
    return ("tell the person to run, in their own terminal: "
            f"cd {shlex.quote(root)} && {push} && " + " && ".join(creates))



# --- Git --------------------------------------------------------------------------------------


def _git(root: Path, *args: str) -> tuple[int, str]:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          check=False)
    return done.returncode, done.stdout.strip()


def _must(root: Path, why: str, *args: str) -> str:
    code, out = _git(root, *args)
    if code != 0:
        raise PullRequestRefusal(
            f"git could not {why}", "check the project's git repository, then run this again")
    return out


@dataclass
class Join:
    piece: int
    commit: str
    size: int


def joins(root: Path, branch: str) -> list[Join]:
    """Each piece's join on the branch, in order, with the lines the join changed."""
    out = _must(root, f"read the joins on {branch}", "log", "--first-parent", "--reverse",
                "--format=%H%x1f%P%x1f%B%x1e", f"refs/heads/{branch}", f"^refs/heads/{MAIN}")
    found: list[Join] = []
    for row in out.split("\x1e"):
        fields = row.strip().split("\x1f")
        if len(fields) != 3 or not fields[1].split():
            continue
        numbers = integrate.trailers(fields[2])
        if len(numbers) != 1:
            continue
        commit, parent = fields[0], fields[1].split()[0]
        stat = _must(root, f"measure the join {commit[:7]}", "diff", "--numstat", "--no-renames",
                     parent, commit)
        size = 0
        for line in stat.splitlines():
            added, _, rest = line.partition("\t")
            deleted = rest.partition("\t")[0]
            size += (int(added) if added.isdigit() else 1) + (int(deleted) if deleted.isdigit()
                                                              else 1)
        found.append(Join(numbers[0], commit, size))
    return found


@dataclass
class Part:
    index: int
    pieces: list[int]
    head: str
    branch: str
    base: str  # the branch the pull request is based on
    since: str  # where the commit range for the closing-word scan starts
    size: int


# --- the loop ---------------------------------------------------------------------------------


class PullRequests:
    def __init__(
        self,
        paths: Paths,
        name: str,
        run: run_record.RunRecord,
        policy: Mapping[str, Any],
        loop: Any,
        *,
        api: Api | None = None,
        mover: Mover | None = None,
        push: Push | None = None,
        app: bool | None = None,
        gate_lock: Any = None,
    ) -> None:
        self.paths = paths
        self.root = paths.root
        self.name = name
        self.record = run
        self.policy = policy
        self.loop = loop
        self.hub = github.GitHub(paths)
        self.app = self.hub.available if app is None else app
        self.api: Api = api if api is not None else pulls.Pulls(self.hub)
        self.mover: Mover = mover or self._default_mover
        self.push: Push = push or self._default_push
        self.gate_lock = gate_lock if gate_lock is not None else contextlib.nullcontext()

    # --- defaults ---------------------------------------------------------------------------

    def _default_mover(self, number: int, target: str, reason: str | None,
                       options: Mapping[str, str]) -> Reply:
        return Gateway(self.paths).move(number, target, reason=reason, options=options)

    def _default_push(self, branch: str) -> dict[str, Any]:
        return github.push(self.paths, branch)

    # --- the record -------------------------------------------------------------------------

    def _all(self) -> dict[str, dict[str, Any]]:
        found: dict[str, dict[str, Any]] = self.record.data.setdefault("pull_requests", {})
        return found

    def _set(self, key: str, **fields: Any) -> None:
        with self.record.lock:
            self._all().setdefault(key, {}).update(fields)
            self.record.save()

    def entries(self, track: str | None = None) -> list[dict[str, Any]]:
        """The pull requests of the run, in part order. Each carries its key."""
        found = [{"key": k, **v} for k, v in self._all().items()
                 if track is None or v.get("track") == track]
        return sorted(found, key=lambda e: (str(e.get("track")), int(e.get("part", 1))))

    def _review(self, key: str) -> dict[str, Any]:
        tracks: dict[str, Any] = self.record.data.get("review", {}).get("tracks", {})
        found: dict[str, Any] = tracks.get(key) or {}
        return found

    def _final(self, key: str) -> dict[str, Any]:
        final: dict[str, Any] = self.record.data.get("integration", {}).get("final", {})
        found: dict[str, Any] = final.get(key) or {}
        return found

    # --- the pieces' facts ------------------------------------------------------------------

    def _facts(self, view: integrate.PieceView, size: int) -> PieceFacts:
        verdict = (self.record.data.get("review", {}).get("verdicts", {}) or {}).get(
            str(view.number)) or {}
        notes: list[str] = []
        for item in self.record.data.get("integration", {}).get("worth_knowing", []):
            if item.get("piece") == view.number:
                notes.append(str(item.get("text", "")))
        notes += [str(n) for n in verdict.get("notes", [])]
        for decision in self.record.data.get("decisions", []):
            if decision.get("piece") == view.number:
                notes.append(f"Decided alone by {decision.get('by')}: {decision.get('text')}")
        for entry in view.record:
            if entry.get("kind") == "review-test":
                notes.append(f"A new test from review, {entry.get('path')}: "
                             f"{entry.get('justification')}")
        changes = view.spec["changes"]
        try:
            piece = moves.read_piece(self.paths, view.number)
        except moves.MoveError as error:
            raise PullRequestRefusal(str(error), error.next_command) from error
        reasons = list(piece.must_look) if piece is not None else []
        if view.issue is None:
            raise PullRequestRefusal(
                f"piece {view.number} has no issue yet, so no Closes line can name it",
                github.sync_command(self.root))
        rounds = verdict.get("round")
        return PieceFacts(
            number=view.number, issue=int(view.issue), title=view.title,
            judge=str(view.spec["judge"]["command"] or ""),
            held_out=bool(view.spec["judge"]["held_out"]),
            review=f"{verdict.get('verdict', 'not recorded')}"
            + (f" in round {rounds}" if rounds else ""),
            notes=notes, added=list(changes["added"]), changed=list(changes["changed"]),
            removed=list(changes["removed"]), must_look=reasons, size=size)

    def _general(self, shown: Sequence[int]) -> list[str]:
        notes: list[str] = []
        for item in self.record.data.get("integration", {}).get("worth_knowing", []):
            piece = item.get("piece")
            if piece is None or piece not in shown:
                notes.append(str(item.get("text", "")))
        return notes

    # --- the parts --------------------------------------------------------------------------

    def parts(self, key: str, branch: str, head: str) -> list[Part]:
        found = joins(self.root, branch)
        if not found:
            raise PullRequestRefusal(f"{branch} holds no join, so there is nothing to open",
                                     f"python3 -m loop.run.integrate status --run {self.name}")
        limit = int(self.policy.get("pull_request_size_limit", 800))
        groups = plan_groups([(j.piece, j.size) for j in found], limit,
                             one_each=key != integrate.MAIN_TRACK)
        by_piece = {j.piece: j for j in found}
        parts: list[Part] = []
        since, base = MAIN, MAIN
        for index, group in enumerate(groups, start=1):
            last = index == len(groups)
            tip = head if last else by_piece[group[-1]].commit
            name = branch if last else f"{branch}-part-{index}"
            parts.append(Part(index, list(group), tip, name, base, since,
                              sum(by_piece[n].size for n in group)))
            since, base = tip, name
        return parts

    def _branch_for(self, part: Part) -> None:
        """Make the part's branch at its commit. An existing branch must already be there."""
        code, tip = _git(self.root, "rev-parse", "--verify", "-q", f"refs/heads/{part.branch}")
        if code == 0:
            if tip != part.head:
                raise PullRequestRefusal(
                    f"the branch {part.branch} exists and is not at {part.head[:7]}, and the "
                    "gate never moves a branch by force",
                    f"git -C {shlex.quote(str(self.root))} branch --list {part.branch}")
            return
        with self.gate_lock:
            _must(self.root, f"make the branch {part.branch}", "branch", part.branch, part.head)

    # --- opening ----------------------------------------------------------------------------

    def open_all(self) -> list[dict[str, Any]]:
        """Open the pull requests of every track that is clean on its head."""
        reports: list[dict[str, Any]] = []
        first: PullRequestRefusal | None = None
        for key in self.loop.tracks():
            try:
                reports.append(self.open_track(key))
            except PullRequestRefusal as error:
                self.record.note(f"No pull request for {key}: {error}")
                first = first or error
            except (integrate.IntegrationRefusal, merge_gate.Unreadable) as error:
                self.record.note(f"No pull request for {key}: {error}")
                first = first or PullRequestRefusal(str(error), error.next_command)
        if first is not None:
            raise first
        return reports

    def _skip(self, key: str, message: str) -> dict[str, Any]:
        return {"track": key, "status": "skipped", "message": message}

    def open_track(self, key: str) -> dict[str, Any]:
        lock = getattr(self.loop, "_lock", None) or contextlib.nullcontext()
        with lock:
            pieces = list(self.loop.joined(key))
            if not pieces:
                return self._skip(key, f"{key} holds no piece")
            branch = str(self.loop.combined(key))
            head = _must(self.root, f"read {branch}", "rev-parse", f"refs/heads/{branch}")
            review, final = self._review(key), self._final(key)
            if review.get("status") != "clean" or review.get("reviewed") != head:
                return self._skip(key, f"the review of {branch} is not clean on {head[:7]}, so "
                                  "no pull request opens for it")
            if final.get("status") != "green" or final.get("head") != head:
                return self._skip(key, f"the final combined check of {branch} is not green on "
                                  f"{head[:7]}, so no pull request opens for it")
            current = self.entries(key)
            if current and all(e.get("stack_head") == head
                               and e.get("state") in ("open", "waiting", "merged")
                               for e in current):
                return {"track": key, "status": "already", "message":
                        f"the pull request for {branch} at {head[:7]} is already recorded",
                        "pull_requests": [e["key"] for e in current]}
            return self._open(key, pieces, branch, head, final)

    def _open(self, key: str, pieces: list[int], branch: str, head: str,
              final: Mapping[str, Any]) -> dict[str, Any]:
        parts = self.parts(key, branch, head)
        views = {n: self.loop.reader(n) for n in pieces}
        sizes = {j.piece: j.size for j in joins(self.root, branch)}
        facts = {n: self._facts(views[n], sizes.get(n, 0)) for n in pieces}
        checked = final.get("checked") or {}
        made: list[dict[str, Any]] = []
        for part in parts:
            self._branch_for(part)
            body = render_body(
                [facts[n] for n in part.pieces], run=self.name, branch=part.branch,
                head=part.head, checks=int(checked.get("checks", 0)),
                held_runs=int(checked.get("held_out", 0)), part=part.index, parts=len(parts),
                general=self._general(pieces) if part.index == len(parts) else [])
            title = render_title(self.name, [facts[n] for n in part.pieces], part.index,
                                 len(parts))
            made.append({"part": part, "body": body, "title": title,
                         "key": key if len(parts) == 1 else f"{key}-part-{part.index}"})
        for item in made:
            part = item["part"]
            faults = merge_gate.offline_faults(
                self.paths, merge_gate.Opening(self._data(key, part, len(parts), 0, None, head,
                                                          pieces, branch)),
                title=item["title"], body=item["body"])
            if faults:
                raise PullRequestRefusal(
                    f"the pull request of {part.branch} was not opened: " + "; ".join(faults[:3]),
                    "fix what is named, then run.py --run " + self.name)
        if not self.app:
            return self._wait_for_person(key, made, pieces, head)
        for item in made:
            try:
                self.push(item["part"].branch)
            except github.GitHubError as error:
                raise PullRequestRefusal(error.message, error.next_command) from error
        opened: list[tuple[dict[str, Any], int, str]] = []
        base_pr: int | None = None
        try:
            for item in made:
                part = item["part"]
                number, url = self.api.create(base=part.base, head=part.branch,
                                              title=item["title"], body=item["body"])
                opened.append((item, number, url))
                self._set(item["key"], **self._data(key, part, len(parts), number, base_pr, head,
                                                    pieces, branch), state="open", url=url,
                          title=item["title"])
                base_pr = number
        except github.GitHubError as error:
            self._close_all(opened, f"The run could not finish opening this stack: "
                            f"{error.message}")
            raise PullRequestRefusal(error.message, error.next_command) from error
        for item, number, _ in opened:
            part = item["part"]
            stored = self._all()[item["key"]]
            for piece in part.pieces:
                reply = self.mover(piece, "approval", None, {
                    k: str(v) for k, v in stored.items() if k in merge_gate.OPENING_OPTIONS})
                if not reply.ok:
                    self._close_all(opened, f"The gate refused move 10 for piece {piece}: "
                                    f"{reply.message}")
                    raise PullRequestRefusal(
                        f"the gate refused move 10 for piece {piece}: {reply.message}",
                        reply.next_command or f"gate.py report {piece}")
                self.record.update(piece, pull_request=number, pr_key=item["key"])
        self._replace_old(key, head, [n for _, n, _ in opened])
        self.record.note(f"Opened {len(opened)} pull request(s) for {branch}: "
                         + ", ".join(url for *_, url in opened))
        return {"track": key, "status": "opened", "message": f"opened for {branch}",
                "pull_requests": [{"number": n, "url": u, "key": i["key"]}
                                  for i, n, u in opened]}

    def _data(self, key: str, part: Part, parts: int, number: int, base_pr: int | None,
              stack_head: str, stack: Sequence[int], branch: str) -> dict[str, Any]:
        return {"run": self.name, "track": key, "part": part.index, "parts": parts,
                "pull_request": number, "branch": part.branch, "head": part.head,
                "base": part.base, "since": part.since, "stack_head": stack_head,
                "base_pr": base_pr if base_pr is not None else "",
                "pieces": ",".join(str(n) for n in part.pieces),
                "stack": ",".join(str(n) for n in stack), "stack_branch": branch}

    def _close_all(self, opened: Sequence[tuple[dict[str, Any], int, str]], why: str) -> None:
        for item, number, _ in reversed(opened):
            try:
                self.api.close(number, why)
                self._set(item["key"], state="closed")
            except github.GitHubError as error:
                self.record.note(f"pull request {number} could not be closed: {error.message}")

    def _replace_old(self, key: str, head: str, new: Sequence[int]) -> None:
        for entry in self.entries(key):
            if entry.get("stack_head") == head or entry.get("state") != "open" \
                    or entry.get("pull_request") in new:
                continue
            try:
                self.api.close(int(entry["pull_request"]),
                               f"Replaced by pull request {new[-1]}, which holds the branch as "
                               "it was tested again.")
                self._set(str(entry["key"]), state="replaced")
            except github.GitHubError as error:
                self.record.note(f"the old pull request {entry['pull_request']} could not be "
                                 f"closed: {error.message}")

    def _wait_for_person(self, key: str, made: Sequence[dict[str, Any]], pieces: list[int],
                         head: str) -> dict[str, Any]:
        """No App: write the bodies, push nothing, and name the commands for the person."""
        folder = self.paths.run_dir(self.name)
        folder.mkdir(parents=True, exist_ok=True)
        opens: list[tuple[str, str, str, str]] = []
        for item in made:
            part = item["part"]
            target = folder / f"pull-request-{item['key']}.md"
            target.write_text(item["body"], encoding="utf-8")
            opens.append((part.base, part.branch, item["title"], str(target)))
        command = push_and_open_commands(str(self.root), [i["part"].branch for i in made], opens)
        for item in made:
            part = item["part"]
            self._set(item["key"], **self._data(key, part, len(made), 0, None, head, pieces,
                                                str(self.loop.combined(key))),
                      state="waiting", next=command,
                      body_file=str(folder / f"pull-request-{item['key']}.md"))
        self.record.update(pieces[0], github_next=command)
        self.record.note("The pull request step waits for the person: the gate's App is not set "
                         f"up, so nothing was pushed or opened. next: {command}")
        return {"track": key, "status": "waiting", "next": command,
                "message": "no App: nothing was pushed or opened"}

    # --- merging ----------------------------------------------------------------------------

    def merge(self, *, mode: str, said: str = "") -> list[dict[str, Any]]:
        """Ask the gate for move 11 for each open pull request, in order.

        The gate merges the exact tested commit only when every condition holds. A pull request
        that waits stops the rest of its own stack, never another track.
        """
        if mode not in merge_gate.MODES:
            raise PullRequestRefusal(f"{mode!r} is not a way to merge", "merge --help")
        reports: list[dict[str, Any]] = []
        stuck: set[str] = set()
        for entry in self.entries():
            if entry.get("state") != "open":
                continue
            track = str(entry["track"])
            if track in stuck:
                reports.append({"key": entry["key"], "status": "waits",
                                "why": "an earlier pull request of this stack waits"})
                continue
            report = self._merge_one(entry, mode, said)
            reports.append(report)
            if report["status"] != "merged":
                stuck.add(track)
        return reports

    def _merge_one(self, entry: Mapping[str, Any], mode: str, said: str) -> dict[str, Any]:
        key, pieces = str(entry["key"]), [int(n) for n in str(entry["pieces"]).split(",")]
        number = int(entry["pull_request"])
        base_pr = str(entry.get("base_pr") or "")
        if base_pr:
            try:
                if entry.get("base") != MAIN and self.api.view(int(base_pr)).state == "MERGED":
                    self.api.set_base(number, MAIN)
            except github.GitHubError as error:
                return {"key": key, "status": "waits", "why": error.message}
        reply = self.mover(pieces[0], "done", None, {"merge": mode, "said": said,
                                                      "run": self.name})
        if not reply.ok:
            self._set(key, waits=reply.message, next=reply.next_command)
            self.record.note(f"The merge of pull request {number} waits: {reply.message}")
            return {"key": key, "status": "waits", "why": reply.message,
                    "next": reply.next_command}
        for piece in pieces[1:]:
            again = self.mover(piece, "done", None, {})
            if not again.ok:
                self.record.note(f"piece {piece} did not reach done after the merge of pull "
                                 f"request {number}: {again.message}")
        self._set(key, state="merged", waits="")
        self.record.note(f"Pull request {number} merged by the gate ({mode}), on the tested "
                         f"commit {str(entry['head'])[:7]}.")
        return {"key": key, "status": "merged", "pull_request": number, "mode": mode}

    # --- sending pieces back ----------------------------------------------------------------

    def _pieces_of(self, entry: Mapping[str, Any], field_name: str = "pieces") -> list[int]:
        return [int(n) for n in str(entry[field_name]).split(",") if n.strip()]

    def _reset_review(self, key: str) -> None:
        with self.record.lock:
            tracks = self.record.data.setdefault("review", {}).setdefault("tracks", {})
            tracks[key] = {"rounds": 0, "status": "new"}
            self.record.save()

    def _close_open(self, key: str, why: str) -> list[int]:
        """Close each open pull request of the track: its tested tree is no longer the one."""
        closed: list[int] = []
        for entry in self.entries(key):
            if entry.get("state") != "open":
                continue
            number = int(entry["pull_request"])
            try:
                self.api.close(number, why)
            except github.GitHubError as error:
                raise PullRequestRefusal(
                    f"pull request {number} could not be closed ({error.message}), and a pull "
                    "request that is no longer the tested tree must not stay open",
                    error.next_command) from error
            self._set(str(entry["key"]), state="closed", closed_by="the run")
            closed.append(number)
        return closed

    def reject(self, numbers: Sequence[int], reason: str, *, to: str = "building"
               ) -> dict[str, Any]:
        """Move 13 for the named pieces, move 12 for the others of their branch, then a rebuild.

        The combined branch is rebuilt without the named pieces under a fresh name, and the old
        pull request is closed. A new pull request replaces it when the run goes on.
        """
        if to not in ("building", "shaping"):
            raise PullRequestRefusal(f"a rejected piece goes to building or shaping, not {to}",
                                     "reject --help")
        text = " ".join(reason.split())[:REASON_LIMIT]
        if not text:
            raise PullRequestRefusal("a piece goes back with a written reason",
                                     "give --reason with the person's words")
        wanted = sorted(set(numbers))
        tracks: dict[str, list[dict[str, Any]]] = {}
        for entry in self.entries():
            if entry.get("state") == "open" and set(wanted) & set(self._pieces_of(entry, "stack")):
                tracks.setdefault(str(entry["track"]), []).append(entry)
        lost = [n for n in wanted if not any(n in self._pieces_of(e, "stack")
                                             for es in tracks.values() for e in es)]
        if lost or not wanted:
            raise PullRequestRefusal(
                f"piece {', '.join(str(n) for n in lost)} is not in an open pull request of "
                f"the run {self.name}",
                f"python3 -m loop.run.pull_request status --run {self.name}")
        for number in wanted:
            reply = self.mover(number, to, text, {})
            if not reply.ok:
                raise PullRequestRefusal(
                    f"the gate refused move 13 for piece {number}: {reply.message}",
                    reply.next_command or f"gate.py report {number}")
        rest: list[int] = []
        for entries in tracks.values():
            for entry in entries:
                rest += [n for n in self._pieces_of(entry) if n not in wanted and n not in rest]
        for number in rest:
            reply = self.mover(number, "review",
                               f"Piece {wanted[0]} was sent back, so the combined branch is "
                               f"rebuilt without it and checked again. {text}"[:REASON_LIMIT],
                               {"rejected": str(wanted[0])})
            if not reply.ok:
                raise PullRequestRefusal(
                    f"the gate refused move 12 for piece {number}: {reply.message}",
                    reply.next_command or f"gate.py report {number}")
        for key in tracks:
            self._close_open(key, f"Closed: {text} A new pull request replaces this one once "
                             "the branch is rebuilt and checked again.")
        for number in wanted:
            self.loop.leave(number, text)
            self.record.update(number, rejected=text, joined=None)
            self.record.set_status(number, run_record.BUILDING if to == "building"
                                   else run_record.SENT_BACK, reason=text)
        for key in tracks:
            self._reset_review(key)
        self.record.note(f"Sent back piece {', '.join(str(n) for n in wanted)} to {to}; "
                         f"the others of the branch go back to review: {text}")
        return {"sent_back": wanted, "to": to, "back_to_review": rest,
                "next": f"run.py --run {self.name}, to build what went back and open the "
                        "pull request that replaces the old one"}

    def refresh(self, reason: str) -> dict[str, Any]:
        """Move 12 for every piece of a branch that `main` moved past, then a rebuild on `main`."""
        try:
            merge_gate.fetch_main(self.paths)
            if merge_gate.main_lags(self.root):
                raise PullRequestRefusal(
                    "origin/main holds commits the local main lacks, and the branch is cut from "
                    "the local main",
                    f"git -C {shlex.quote(str(self.root))} merge --ff-only origin/main, in "
                    "the main folder, then run this again")
            behind: dict[str, list[str]] = {}
            for entry in self.entries():
                if entry.get("state") == "open":
                    found = merge_gate.moved(self.root, str(entry["head"]))
                    if found:
                        behind[str(entry["track"])] = found
        except merge_gate.Unreadable as error:
            raise PullRequestRefusal(str(error), error.next_command) from error
        if not behind:
            raise PullRequestRefusal("main did not move past any open pull request, so the "
                                     "tested tree is unchanged",
                                     f"python3 -m loop.run.pull_request status --run {self.name}")
        text = " ".join(reason.split())[:REASON_LIMIT] or (
            "main moved after the final combined check, so the branch is brought up to date and "
            "checked again")
        sent: list[int] = []
        for key in behind:
            for entry in self.entries(key):
                if entry.get("state") != "open":
                    continue
                for number in self._pieces_of(entry):
                    reply = self.mover(number, "review", text, {})
                    if not reply.ok:
                        raise PullRequestRefusal(
                            f"the gate refused move 12 for piece {number}: {reply.message}",
                            reply.next_command or f"gate.py report {number}")
                    sent.append(number)
        for key in behind:
            self._close_open(key, f"Closed: {text} A new pull request replaces this one.")
            self.loop.refresh(key, text)
            self._reset_review(key)
        self.record.note(f"Main moved: pieces {', '.join(str(n) for n in sent)} went back to "
                         "review, and the branch is rebuilt on main")
        return {"back_to_review": sent, "tracks": sorted(behind),
                "next": f"run.py --run {self.name}, to check the rebuilt branch again and open "
                        "the pull request that replaces the old one"}

    # --- reading what the person did --------------------------------------------------------

    def _named(self, text: str, entry: Mapping[str, Any]) -> list[int]:
        """The pieces of the pull request that a comment names, by piece or issue number."""
        pieces = self._pieces_of(entry)
        issues: dict[int, int] = {}
        for number in pieces:
            view = self.loop.reader(number)
            if view.issue is not None:
                issues[int(view.issue)] = number
        found: set[int] = set()
        for word in re.findall(r"(?:\bpieces?\s+#?|#)(\d+(?:\s*(?:,|and|&)\s*#?\d+)*)", text,
                               re.IGNORECASE):
            for token in re.findall(r"\d+", word):
                wanted = int(token)
                if wanted in pieces:
                    found.add(wanted)
                elif wanted in issues:
                    found.add(issues[wanted])
        return sorted(found)

    def sweep(self) -> dict[str, Any]:
        """Read each open pull request: a merge, a closing or a comment becomes the right move."""
        out: dict[str, Any] = {"merged": [], "closed": [], "comments": [], "skipped": ""}
        if not self.app:
            out["skipped"] = "skipped: the gate's App is not set up, so GitHub cannot be read"
            return out
        done: set[int] = set()
        for entry in self.entries():
            if entry.get("state") != "open" or int(entry["pull_request"]) in done:
                continue
            number = int(entry["pull_request"])
            done.add(number)
            try:
                pr = self.api.view(number)
            except github.GitHubError as error:
                raise PullRequestRefusal(error.message, error.next_command) from error
            pieces = self._pieces_of(entry)
            if pr.state == "MERGED":
                for piece in pieces:
                    reply = self.mover(piece, "done", None, {})
                    if not reply.ok:
                        out["merged"].append({"pull_request": number, "piece": piece,
                                              "settled": False, "why": reply.message})
                        continue
                    out["merged"].append({"pull_request": number, "piece": piece,
                                          "settled": True})
                self._set(str(entry["key"]), state="merged")
                continue
            if pr.state == "CLOSED":
                self.reject(pieces, f"The person closed pull request {number}.")
                out["closed"].append({"pull_request": number, "pieces": pieces})
                continue
            seen = int(entry.get("seen_comment") or 0)
            fresh = [c for c in pr.comments if c.id > seen and c.association in TRUSTED]
            top = max((c.id for c in pr.comments), default=seen)
            self._set(str(entry["key"]), seen_comment=top)
            for comment in sorted(fresh, key=lambda c: c.id):
                named = self._named(comment.body, entry) or pieces
                self.reject(named, comment.body)
                out["comments"].append({"pull_request": number, "comment": comment.id,
                                        "pieces": named})
                break
        out["next"] = f"run.py --run {self.name}" if out["closed"] or out["comments"] else (
            "gate.py check-main, to settle the merge and check main" if out["merged"] else "")
        return out

    def status(self) -> dict[str, Any]:
        shown = []
        for entry in self.entries():
            item = {k: entry.get(k) for k in ("key", "track", "part", "pull_request", "url",
                                              "branch", "head", "state", "waits", "next")}
            item["pieces"] = self._pieces_of(entry) if entry.get("pieces") else []
            shown.append(item)
        return {"run": self.name, "pull_requests": shown,
                "merge_pre_approved": bool(self.record.data.get("merge_pre_approved"))}


# --- the hooks --------------------------------------------------------------------------------

_LOOPS: dict[tuple[str, str, str], PullRequests] = {}


def pull_requests_for(context: Any) -> PullRequests:
    key = (str(context.paths.root), str(context.name), str(id(context.record)))
    made = _LOOPS.get(key)
    if made is None:
        made = PullRequests(
            context.paths, context.name, context.record, context.policy,
            integrate.integrator_for(context), gate_lock=getattr(context, "gate_lock", None))
        _LOOPS[key] = made
    return made


def run_hook(context: Any, event: str, **data: Any) -> None:
    """The engine's hook. `built-all` opens the pull requests, and merges when pre-approved."""
    if event == "built-all":
        loop = pull_requests_for(context)
        loop.open_all()
        if context.record.data.get("merge_pre_approved"):
            loop.merge(mode="pre-approved")
    elif event == "run-end":
        tracks = context.record.data.get("review", {}).get("tracks", {})
        opened = {e.get("track") for e in pull_requests_for(context).entries()}
        for key, state in tracks.items():
            if state.get("status") == "clean" and key not in opened:
                context.record.note(f"No pull request is open for {key}, though its review is "
                                    "clean: read the notes above for the reason")


# --- a door for the person and the agent ------------------------------------------------------


def _setup(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    for name, text, changes in (
        ("status", "show each pull request of the run", False),
        ("open", "open the pull requests of every clean branch (changes state)", True),
        ("merge", "ask the gate for move 11 for each open pull request (changes state)", True),
        ("reject", "send pieces back by move 13, and rebuild the rest (changes state)", True),
        ("refresh", "main moved: move 12 for the pieces, and a rebuild (changes state)", True),
        ("sweep", "read the open pull requests: a merge, a closing, a comment (changes state)",
         True),
    ):
        sub = commands.add_parser(name, help=text)
        sub.add_argument("--run", required=True, help="the run's name")
        sub.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                         help="print JSON")
        if changes:
            sub.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS,
                             help="say what would run, and change nothing")
        if name == "merge":
            sub.add_argument("--said", default="", help="the person's words that name the merge")
            sub.add_argument("--pre-approved", action="store_true",
                             help="merge as the run's pre-approval allows (the run record must "
                             "say it was pre-approved)")
        if name == "reject":
            sub.add_argument("--piece", type=int, action="append", default=[], metavar="N",
                             help="a piece to send back (repeat)")
            sub.add_argument("--reason", required=True, help="the person's words")
            sub.add_argument("--to", choices=("building", "shaping"), default="building")
        if name == "refresh":
            sub.add_argument("--reason", default="", help="why (default: main moved)")


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    from loop import policy as policy_module
    from loop.paths import PathError, find_project_root

    try:
        paths = Paths.for_project(find_project_root(Path.cwd()))
        run = run_record.RunRecord.load(paths, args.run)
        loaded = (policy_module.load(paths.policy_file) if paths.policy_file.exists()
                  else policy_module.with_defaults({}))
        loop = integrate.Integrator(paths, args.run, run, loaded)
        made = PullRequests(paths, args.run, run, loaded, loop)
        dry = bool(getattr(args, "dry_run", False))
        if args.command == "status":
            return made.status()
        if dry:
            return {**made.status(), "would": args.command}
        if args.command == "open":
            return {"opened": made.open_all()}
        if args.command == "merge":
            mode = "pre-approved" if args.pre_approved else "agent"
            return {"merged": made.merge(mode=mode, said=args.said)}
        if args.command == "reject":
            return made.reject(args.piece, args.reason, to=args.to)
        if args.command == "refresh":
            return made.refresh(args.reason)
        return made.sweep()
    except (PathError, run_record.RecordError) as error:
        raise cli.Failure(str(error), next_command=getattr(error, "next_command", "")
                          or "python3 -m loop.run.pull_request --help",
                          code=ExitCode.ENVIRONMENT) from error
    except (PullRequestRefusal, integrate.IntegrationRefusal) as error:
        raise cli.Failure(str(error), next_command=error.next_command,
                          code=ExitCode.REFUSED) from error
    except github.GitHubError as error:
        raise cli.Failure(error.message, next_command=error.next_command,
                          code=ExitCode.REFUSED) from error


def main(argv: list[str]) -> int:
    return cli.run(
        "pull_request",
        "The pull request step and the merge decision: status, open, merge, reject, refresh, "
        "sweep.", _setup, _handle, argv, changes_state=True)


if __name__ == "__main__":
    # Run under its real name, so the exceptions the modules share are one class.
    from loop.run.pull_request import main as _main

    sys.exit(_main(sys.argv[1:]))
