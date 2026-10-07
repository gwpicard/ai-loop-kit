"""Move 11: approval to done. The merge of the exact tested commit.

Only two things end in `done`: the person merged the pull request on GitHub, or the agent merged
it for the person (told to, or pre-approved before this run). The gate holds both.

- A pull request that is already merged passes only when GitHub merged the tested commit, the one
  the final combined check and the review read. Another head is a refusal that names the check
  on `main`.
- A pull request that is open is merged by the gate itself, as the App, with
  `gh pr merge --match-head-commit <tested commit>`, and only when every condition holds. The
  merge is the `act` of the move, so a dry run never merges.
- The person's words name the merge (`--option merge=agent --option said="<their words>"`), or
  the run was pre-approved: the run record says so, `run.py --merge-pre-approved` wrote it, and
  every pre-approval condition holds. A pre-approved merge waits for any piece with a must-look
  reason, anywhere in the run.

Conditions that hold every merge: the pull request's head is the tested commit; the final
combined check was green on the head of the branch the pull request holds; the review is clean;
`main` did not move after the final check (else move 12); a stacked pull request merges after its
base; every doc a piece names was changed (the stack's last pull request carries the docs
commit); no closing word stands anywhere but on a `Closes` line; the pull request's checks passed
(no checks is never a pass); no piece holds an irreversible data change, which is always the
person's merge.

A read that fails (GitHub, Git, the run record) is a refusal, never a pass.

This module also holds what moves 10 and 12 share: the record's `pull-request` entry, the run
record, and the tests of the tested tree (`moved`, `doc_faults`).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from loop import attempt_log, closing, github, moves, pulls, spec
from loop.gates import CheckContext, CheckResult, passed, refused
from loop.paths import Paths

KIND = "pull-request"
MERGED_KIND = "merged"
MAIN = "main"
MODES = ("agent", "pre-approved")
NAMES_THE_MERGE = re.compile(r"\bmerge\b", re.IGNORECASE)


class Unreadable(Exception):
    """A read the gate depends on failed, so it cannot tell and refuses."""

    def __init__(self, message: str, next_command: str = "") -> None:
        super().__init__(message)
        self.next_command = next_command or (
            "check the project's git repository and the run record, then run this again")


# --- Git ---------------------------------------------------------------------------------------


def _git(root: Path, *args: str) -> tuple[int, str]:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          check=False)
    return done.returncode, done.stdout.strip()


def _must(root: Path, why: str, *args: str) -> str:
    code, out = _git(root, *args)
    if code != 0:
        raise Unreadable(f"git could not {why}")
    return out


def _exists(root: Path, ref: str) -> bool:
    return _git(root, "rev-parse", "--verify", "-q", ref)[0] == 0


def main_refs(root: Path) -> list[str]:
    """The refs that say where `main` is: the local branch and the last fetched remote one."""
    return [r for r in (f"refs/heads/{MAIN}", f"refs/remotes/origin/{MAIN}") if _exists(root, r)]


def moved(root: Path, head: str, refs: Sequence[str] | None = None) -> list[str]:
    """The commits on `main` that the tested `head` does not hold.

    A merge commit that only brings in commits `head` already holds is not a move: it is how an
    earlier pull request of the same stack reached `main`. Anything else is work nobody tested
    together with `head`. An empty list means `main` did not move.
    """
    _must(root, f"read {head}", "rev-parse", "--verify", f"{head}^{{commit}}")
    found: list[str] = []
    for ref in refs if refs is not None else main_refs(root):
        out = _must(root, f"list the commits {ref} has beyond {head}", "rev-list", "--parents",
                    f"{head}..{ref}")
        for line in out.splitlines():
            parts = line.split()
            commit, parents = parts[0], parts[1:]
            if commit in found:
                continue
            own = len(parents) >= 2 and all(
                _git(root, "merge-base", "--is-ancestor", p, head)[0] == 0 for p in parents[1:])
            if not own:
                found.append(commit)
    return found


def main_lags(root: Path) -> bool:
    """True when the last fetched `origin/main` holds commits the local `main` lacks."""
    if not (_exists(root, f"refs/heads/{MAIN}") and _exists(root, f"refs/remotes/origin/{MAIN}")):
        return False
    out = _must(root, "compare main with origin/main", "rev-list", "--count",
                f"refs/heads/{MAIN}..refs/remotes/origin/{MAIN}")
    return out != "0"


def fetch_main(paths: Paths) -> None:
    """Bring `origin/main` up to date. A fetch that fails is an unreadable `main`."""
    try:
        github.fetch(paths, MAIN)
    except github.GitHubError as error:
        raise Unreadable(f"origin/{MAIN} could not be read ({error.message}), so it is not "
                         "known whether main moved", error.next_command) from error


def changed_files(root: Path, head: str) -> set[str]:
    """The files `head` changes against `main`, from where the two branches parted."""
    base = f"refs/heads/{MAIN}" if _exists(root, f"refs/heads/{MAIN}") else f"origin/{MAIN}"
    out = _must(root, f"list what {head} changes", "diff", "--no-renames", "--name-only", "-z",
                f"{base}...{head}")
    return {p for p in out.split("\0") if p}


def doc_faults(root: Path, head: str, specs: Mapping[int, Mapping[str, Any]]) -> list[str]:
    """Each doc a piece names (`Docs:` under its changes) that the branch did not change."""
    names: list[tuple[int, str]] = []
    faults: list[str] = []
    for number, parsed in sorted(specs.items()):
        for doc in parsed["changes"]["docs"]:
            pure = PurePosixPath(str(doc).strip())
            if pure.is_absolute() or ".." in pure.parts or not pure.parts:
                faults.append(f"piece {number} names {doc!r}, a path outside the project")
            else:
                names.append((number, str(pure)))
    if not names:
        return faults
    changed = changed_files(root, head)
    for number, doc in names:
        if doc not in changed:
            faults.append(f"piece {number} names the doc {doc}, and the pull request did not "
                          "change it")
    return faults


# --- the records ------------------------------------------------------------------------------


def latest_entry(record: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """The piece's last `pull-request` entry, or None when no pull request was opened."""
    found = [dict(e) for e in record if e.get("kind") == KIND]
    return found[-1] if found else None


def read_run(paths: Paths, name: str) -> dict[str, Any]:
    path = paths.run_record(name)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Unreadable(f"the run record {path} cannot be read ({error})",
                         f"run.py --run {name} to make it again") from error
    if not isinstance(data, dict):
        raise Unreadable(f"the run record {path} is not a record")
    return data


def piece_specs(paths: Paths, numbers: Sequence[int]) -> dict[int, dict[str, Any]]:
    found: dict[int, dict[str, Any]] = {}
    for number in numbers:
        try:
            piece = moves.read_piece(paths, number)
        except moves.MoveError as error:
            raise Unreadable(str(error), error.next_command) from error
        if piece is None:
            raise Unreadable(f"piece {number} is not in the gate's record", "gate.py report")
        try:
            parsed = spec.parse(piece.body).to_dict()
        except spec.SpecError as error:
            raise Unreadable(f"the spec of piece {number} cannot be read ({error})",
                             f"gate.py report {number}") from error
        if not parsed["found"]:
            raise Unreadable(f"piece {number} has no spec block", f"gate.py report {number}")
        found[number] = parsed
    return found


def issues_of(paths: Paths, numbers: Sequence[int]) -> dict[int, int]:
    found: dict[int, int] = {}
    for number in numbers:
        try:
            piece = moves.read_piece(paths, number)
        except moves.MoveError as error:
            raise Unreadable(str(error), error.next_command) from error
        if piece is None or piece.issue is None:
            raise Unreadable(f"piece {number} has no issue, so no Closes line can name it",
                             "gate.py sync, then run this again")
        found[number] = piece.issue
    return found


# --- what a pull request holds ----------------------------------------------------------------

OPENING_OPTIONS = ("run", "track", "part", "parts", "pull_request", "branch", "head", "base",
                   "since", "stack_head", "base_pr", "pieces", "stack")


class Opening:
    """The facts of one pull request, as move 10 records them and move 11 reads them back.

    A track's combined branch goes to `main` as one pull request, or as a stack of them when it
    is too big or when its pieces need individual review. Part `n` of `parts` holds whole
    pieces. Its head is a commit the loop tested: the join of its last piece, or, for the last
    part, the head of the branch after the docs commit and the final combined check.
    """

    def __init__(self, data: Mapping[str, Any]) -> None:
        try:
            self.run = str(data["run"])
            self.track = str(data["track"])
            self.part = int(data["part"])
            self.parts = int(data["parts"])
            self.number = int(data["pull_request"])
            self.branch = str(data["branch"])
            self.head = str(data["head"])
            self.base = str(data["base"])
            self.since = str(data["since"])
            self.stack_head = str(data["stack_head"])
            self.base_pr = int(data["base_pr"]) if str(data.get("base_pr", "")).strip() else None
            self.pieces = _numbers(data["pieces"])
            self.stack = _numbers(data["stack"])
        except (KeyError, ValueError, TypeError) as error:
            raise Unreadable(f"the pull request facts are not whole ({error})") from error
        if not (1 <= self.part <= self.parts) or not set(self.pieces) <= set(self.stack):
            raise Unreadable("the pull request facts do not agree with each other")

    @classmethod
    def from_options(cls, options: Mapping[str, str]) -> Opening:
        missing = [name for name in OPENING_OPTIONS if name not in options]
        if missing:
            raise Unreadable(f"move 10 needs the options {', '.join(missing)}",
                             "the run's pull request step gives them: python3 -m "
                             "loop.run.pull_request open --run <name>")
        return cls(options)

    @classmethod
    def from_entry(cls, entry: Mapping[str, Any]) -> Opening:
        return cls(entry)

    def as_entry(self) -> dict[str, Any]:
        return {"kind": KIND, "run": self.run, "track": self.track, "part": self.part,
                "parts": self.parts, "pull_request": self.number, "branch": self.branch,
                "head": self.head, "base": self.base, "since": self.since,
                "stack_head": self.stack_head,
                "base_pr": self.base_pr if self.base_pr is not None else "",
                "pieces": self.pieces, "stack": self.stack}

    @property
    def last(self) -> bool:
        return self.part == self.parts


def _numbers(value: Any) -> list[int]:
    if isinstance(value, str):
        value = [w for w in re.split(r"[ ,]+", value.strip()) if w]
    return sorted({int(v) for v in value})


def offline_faults(paths: Paths, opening: Opening, *, title: str, body: str) -> list[str]:
    """Every fault a pull request has that Git and the run record can show, with no GitHub call."""
    root = paths.root
    faults: list[str] = []
    run = read_run(paths, opening.run)
    final = (run.get("integration", {}).get("final", {}) or {}).get(opening.track) or {}
    if final.get("status") != "green" or final.get("head") != opening.stack_head:
        faults.append(f"the final combined check of {opening.track} was not green on "
                      f"{opening.stack_head[:7]}, the head this pull request is cut from")
    review = (run.get("review", {}).get("tracks", {}) or {}).get(opening.track) or {}
    if review.get("status") != "clean" or review.get("reviewed") != opening.stack_head:
        faults.append(f"the review of {opening.track} was not clean on {opening.stack_head[:7]}")
    verdicts = run.get("review", {}).get("verdicts", {}) or {}
    for number in opening.pieces:
        if (verdicts.get(str(number)) or {}).get("verdict") != "clean":
            faults.append(f"the review verdict of piece {number} is not clean")
    for ref in (opening.head, opening.stack_head):
        _must(root, f"read {ref}", "rev-parse", "--verify", f"{ref}^{{commit}}")
    if _git(root, "merge-base", "--is-ancestor", opening.head, opening.stack_head)[0] != 0:
        faults.append("the tested commit is not part of the branch the final check read")
    code, tip = _git(root, "rev-parse", "--verify", "-q", f"refs/heads/{opening.branch}")
    if code != 0 or tip != opening.head:
        faults.append(f"the branch {opening.branch} does not point at the tested commit "
                      f"{opening.head[:7]}")
    joined = _joined(root, opening.head)
    absent = [n for n in opening.pieces if n not in joined]
    if absent:
        faults.append(f"piece {', '.join(str(n) for n in absent)} is not joined in the tested "
                      "commit")
    specs = piece_specs(paths, opening.stack)
    faults += doc_faults(root, opening.stack_head, specs)
    issues = issues_of(paths, opening.pieces)
    try:
        commits = closing.commits_between(str(root), opening.since, opening.head)
        entries = closing.changelog_entries(str(root), opening.since, opening.head)
    except closing.ReadError as error:
        raise Unreadable(f"{error}, so no closing word was scanned") from error
    faults += [f"{f.where}: {f.message}" for f in closing.scan(
        title=title, body=body, commits=commits, changelog=entries,
        pieces=sorted(issues.values()))]
    return faults


def _joined(root: Path, head: str) -> set[int]:
    out = _must(root, "list the joins", "log", "--first-parent", "--format=%B%x00", head,
                f"^refs/heads/{MAIN}")
    found: set[int] = set()
    for message in out.split("\0"):
        found.update(int(n) for n in re.findall(r"^Piece: #(\d+)[ \t]*$", message, re.MULTILINE))
    return found


def online_faults(pr: pulls.PullRequest, opening: Opening, *, merging: bool = False) -> list[str]:
    faults: list[str] = []
    if pr.state != "OPEN":
        faults.append(f"the pull request is {pr.state.lower()}, not open")
    if pr.head_oid != opening.head:
        faults.append(f"the pull request holds {pr.head_oid[:7]}, not the tested commit "
                      f"{opening.head[:7]}")
    if pr.head_branch != opening.branch:
        faults.append(f"the pull request is cut from {pr.head_branch}, not {opening.branch}")
    # A stacked pull request may already be retargeted to main when its base has merged.
    allowed = {opening.base, MAIN} if merging and opening.base_pr is not None else {opening.base}
    if pr.base not in allowed:
        faults.append(f"the pull request is based on {pr.base}, not {opening.base}")
    return faults


def make_pulls(paths: Paths) -> pulls.Pulls:
    return pulls.Pulls(github.GitHub(paths))


def _unreadable(error: Unreadable) -> CheckResult:
    return refused([str(error)], error.next_command)


def _github(error: github.GitHubError) -> CheckResult:
    return refused([error.message], error.next_command)


# --- move 11 ----------------------------------------------------------------------------------


def merge_faults(paths: Paths, opening: Opening, pr: pulls.PullRequest,
                 api: pulls.Pulls) -> list[str]:
    faults: list[str] = []
    fetch_main(paths)
    behind = moved(paths.root, opening.head)
    if behind:
        faults.append(f"main moved after the final check: it holds {len(behind)} commit(s) the "
                      "tested commit lacks. Nothing merges until the branch is brought up to "
                      "date and checked again (move 12)")
    if opening.base_pr is not None:
        base = api.view(opening.base_pr)
        if base.state != "MERGED":
            faults.append(f"it is stacked on pull request {opening.base_pr}, which is "
                          f"{base.state.lower()}. A stacked pull request never merges before "
                          "its base")
        elif pr.base != MAIN:
            faults.append(f"its base {pr.base} is merged, so it must be retargeted to {MAIN} first")
    ok, why = api.checks(opening.number)
    if not ok:
        faults.append(f"the checks on the pull request are not green: {why}")
    for number, parsed in piece_specs(paths, opening.pieces).items():
        if parsed["changes"]["not_reversible"]:
            faults.append(f"piece {number} holds an irreversible data change, which is always "
                          "the person's merge, after a backup")
    return faults


def pre_approval_faults(paths: Paths, opening: Opening) -> list[str]:
    faults: list[str] = []
    run = read_run(paths, opening.run)
    if not run.get("merge_pre_approved"):
        return [f"the run {opening.run} was not pre-approved. Only run.py --merge-pre-approved "
                "starts a run that may merge for the person"]
    for number in _numbers(run.get("order", [])):
        try:
            piece = moves.read_piece(paths, number)
        except moves.MoveError as error:
            raise Unreadable(str(error), error.next_command) from error
        if piece is not None and piece.must_look:
            faults.append(f"piece {number} has a must-look reason ({'; '.join(piece.must_look)}), "
                          "so the person merges")
    for number in opening.pieces:
        piece = moves.read_piece(paths, number)
        attempts = attempt_log.attempts(piece.record) if piece is not None else []
        if not attempts or attempts[-1].get("result") != "passed":
            faults.append(f"the last attempt of piece {number} is not a pass")
        elif attempts[-1].get("possible_gaming"):
            faults.append(f"the last attempt of piece {number} is logged as possible gaming")
    return faults


def check(ctx: CheckContext) -> CheckResult:
    entry = latest_entry(ctx.record)
    if entry is None:
        return refused(
            [f"piece {ctx.number} has no pull request in its record, so there is nothing to merge"],
            "python3 -m loop.run.pull_request open --run <name>")
    try:
        opening = Opening.from_entry(entry)
        api = make_pulls(ctx.paths)
        pr = api.view(opening.number)
        if pr.state == "MERGED":
            if pr.head_oid != opening.head:
                return refused(
                    [f"pull request {opening.number} merged {pr.head_oid[:7]}, not the tested "
                     f"commit {opening.head[:7]}. Main now holds work nobody tested"],
                    "gate.py check-main, then the project's checks on main")
            return passed(entries=[_merged(opening, pr, "person")])
        if pr.state == "CLOSED":
            return refused(
                [f"pull request {opening.number} was closed without a merge"],
                f'gate.py move {ctx.number} building --reason "<what the person said>" (move 13)')
        mode = str(ctx.options.get("merge", "")).strip()
        faults = online_faults(pr, opening, merging=True) + offline_faults(
            ctx.paths, opening, title=pr.title, body=pr.body)
        if mode not in MODES:
            faults.append("the pull request waits for the person's merge on GitHub. The agent "
                          "merges only when the person says so, or the run was pre-approved")
            return refused(faults, "the person merges pull request "
                           f"{opening.number} on GitHub, or says yes to the merge, and then "
                           f'gate.py move {ctx.number} done --option merge=agent --option '
                           'said="<their words>"')
        faults += merge_faults(ctx.paths, opening, pr, api)
        if mode == "agent":
            said = str(ctx.options.get("said", ""))
            if not NAMES_THE_MERGE.search(said):
                faults.append("the person's words do not name the merge. A yes to the agent "
                              "must say merge; \"put it live\" is not that yes")
        else:
            faults += pre_approval_faults(ctx.paths, opening)
        if faults:
            return refused(faults, f"fix what the gate names, then gate.py move {ctx.number} "
                           "done again; a tested commit that is not current goes back by "
                           f"gate.py move {ctx.number} review --reason \"<why>\" (move 12)")

        def act() -> None:
            api.merge(opening.number, head_commit=opening.head)

        return passed(act=act, entries=[_merged(opening, pr, mode)])
    except Unreadable as error:
        return _unreadable(error)
    except github.GitHubError as error:
        return _github(error)


def _merged(opening: Opening, pr: pulls.PullRequest, by: str) -> dict[str, Any]:
    return {"kind": MERGED_KIND, "pull_request": opening.number, "head": opening.head,
            "merge_commit": pr.merge_commit, "by": by, "run": opening.run}





# --- check-main: a merge the person made --------------------------------------------------------


def run_going(paths: Paths) -> str:
    """The name of a run whose lock holds a live process, or "" when no run is going."""
    try:
        names = sorted(p.name for p in paths.runs_dir.iterdir() if p.is_dir())
    except OSError:
        return ""
    for name in names:
        try:
            held = paths.lock_file(name).read_text(encoding="utf-8").split()
        except OSError:
            continue
        if not held or not held[0].isdigit():
            continue
        try:
            os.kill(int(held[0]), 0)
        except ProcessLookupError:
            continue
        except PermissionError:
            return name
        return name
    return ""


def approval_pieces(paths: Paths) -> dict[int, dict[str, Any]]:
    """Each piece in approval that has a pull request in its record, with that entry."""
    found: dict[int, dict[str, Any]] = {}
    try:
        names = sorted(p.name for p in paths.pieces_dir.iterdir() if p.name.isdigit())
    except OSError:
        return found
    for name in names:
        try:
            piece = moves.read_piece(paths, int(name))
        except moves.MoveError as error:
            raise Unreadable(str(error), error.next_command) from error
        entry = latest_entry(piece.record) if piece is not None else None
        if piece is not None and piece.state == "approval" and entry is not None:
            found[int(name)] = entry
    return found


def check_main(
    paths: Paths,
    *,
    settle: Callable[[int], Mapping[str, Any]],
    run_tests: Callable[[str], Mapping[str, Any]],
    test_command: str,
    app: bool,
    dry_run: bool,
    record: Callable[[int, dict[str, Any]], object] = lambda number, entry: None,
) -> dict[str, Any]:
    """Find the merges the person made, and check `main` when `main` had moved before them.

    A person can merge on GitHub at any time, and a free private repository cannot stop them.
    If `main` had moved after the final combined check, the merged tree is one nobody tested, so
    the project's own check runs on the merge commit. A piece whose pull request merged on the
    tested commit goes to done by move 11. Nothing here merges anything.
    """
    out: dict[str, Any] = {"merges": [], "waiting": [], "unreadable": [], "skipped": "",
                           "next": ""}
    going = run_going(paths)
    if going:
        out["skipped"] = f"skipped: a run is going ({going}), and it settles its own merges"
        return out
    try:
        waiting = approval_pieces(paths)
    except Unreadable as error:
        out["unreadable"].append({"pull_request": 0, "pieces": [], "why": str(error)})
        out["next"] = error.next_command
        return out
    if not waiting:
        return out
    if not app:
        out["skipped"] = ("skipped: the gate's App is not set up, so a merge on GitHub cannot "
                          "be read")
        return out
    api = make_pulls(paths)
    groups: dict[int, list[int]] = {}
    for number, entry in waiting.items():
        groups.setdefault(int(entry["pull_request"]), []).append(number)
    for number, pieces in sorted(groups.items()):
        item: dict[str, Any] = {"pull_request": number, "pieces": sorted(pieces)}
        try:
            pr = api.view(number)
            if pr.state == "OPEN":
                out["waiting"].append({**item, "why": "open: waits for the merge"})
                continue
            if pr.state == "CLOSED":
                out["waiting"].append({**item, "why": "closed without a merge: move 13 is needed"})
                continue
            fetch_main(paths)
            opening = Opening.from_entry(waiting[pieces[0]])
            first = _must(paths.root, f"read the merge commit {pr.merge_commit[:7]}", "rev-parse",
                          "--verify", f"{pr.merge_commit}^1") if pr.merge_commit else ""
            behind = moved(paths.root, opening.head, [first]) if first else []
        except github.GitHubError as error:
            out["unreadable"].append({**item, "why": error.message})
            continue
        except Unreadable as error:
            out["unreadable"].append({**item, "why": str(error)})
            continue
        same = pr.head_oid == opening.head
        item.update(merge_commit=pr.merge_commit, main_moved=bool(behind), settled=False,
                    tested_commit_merged=same)
        if not pr.merge_commit:
            item["why"] = "GitHub gave no merge commit, so main cannot be checked"
        if same and not dry_run:
            try:
                for piece in sorted(pieces):
                    settle(piece)
                item["settled"] = True
            except moves.MoveError as error:
                item["why"] = error.message
        elif same:
            item["why"] = "dry run: the pieces would go to done by move 11"
        else:
            item["why"] = (f"merged {pr.head_oid[:7]}, not the tested commit {opening.head[:7]}: "
                           "main holds work nobody tested")
        needed = bool(behind) or not same
        item["main_check"] = _main_check(paths, pr.merge_commit, needed, test_command,
                                         run_tests, dry_run, item)
        if item["main_check"] in ("green", "red") and not dry_run:
            for piece in sorted(pieces):
                record(piece, {
                    "kind": "main-check", "pull_request": number, "result": item["main_check"],
                    "merge_commit": pr.merge_commit, "main_moved": bool(behind),
                    "tested_commit_merged": same})
        out["merges"].append(item)
    red = [m for m in out["merges"] if m.get("main_check") == "red"]
    odd = [m for m in out["merges"] if not m.get("tested_commit_merged")]
    if red:
        out["next"] = (f"main is red after the person's merge of pull request "
                       f"{red[0]['pull_request']}: tell the person, then capture a bug piece "
                       'with gate.py capture --title "<what broke>". Never revert or force '
                       "push; a fix goes in through a pull request")
    elif odd:
        out["next"] = (f"pull request {odd[0]['pull_request']} merged a commit nobody tested: "
                       "tell the person, and read the project's checks on main")
    elif out["unreadable"]:
        out["next"] = "check the GitHub App and the network, then run gate.py check-main again"
    return out


def _main_check(paths: Paths, ref: str, needed: bool, command: str,
                run_tests: Callable[[str], Mapping[str, Any]], dry_run: bool,
                item: dict[str, Any]) -> str:
    if not needed:
        return "not needed"
    if not ref:
        return "not run"
    if not command.strip():
        item["why"] = (str(item.get("why", "")) + " skipped: the policy has no test_command, "
                       "so main was not checked").strip()
        return "not run"
    if dry_run:
        return "not run"
    result = run_tests(ref)
    return "green" if result.get("exit_code") == 0 and not result.get("timed_out") else "red"
