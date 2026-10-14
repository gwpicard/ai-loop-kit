#!/usr/bin/env python3
"""The gate: the only code that moves a piece from one state to another.

A piece is a GitHub issue with exactly one `state:` label. The gate allows
only the moves in MOVES, runs the checks for each one itself, and writes a
record on the issue for every move it makes.

    gate.py init                       make the labels, ignore .loop/
    gate.py capture --title T --body-file F
    gate.py check N                    run the ready checks, move nothing
    gate.py move N STATE [--reason R]  move a piece
    gate.py sync                       move merged pieces to done
    gate.py status                     list the pieces by state
    gate.py doctor                     check the project is ready for the loop
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loopkit import (NEEDS_YOU, STATE_PREFIX, STATES, GitHub, Refused,  # noqa: E402
                     REASON_TYPES,
                     bar_hash_at, bar_hash_in, branch_name, changed_check_settings,
                     conflict_markers, last_record, main_ref,
                     loop_settings, parse_spec, prepare, record_text, records, repo_root, rev,
                     run_judge, sh, spec_hash)

# (from, to): the move's name. Anything else is refused.
MOVES = {
    ("new", "shaping"): "capture",
    ("shaping", "ready"): "ready",
    ("ready", "shaping"): "pull-back",
    ("ready", "building"): "claim",
    ("building", "shaping"): "give-back",
    ("building", "approval"): "submit",
    ("approval", "done"): "merged",
    ("approval", "shaping"): "reject",
    ("dropped", "shaping"): "reopen",
}
for _s in ("shaping", "ready", "building", "approval"):
    MOVES[(_s, "dropped")] = "drop"

# Moves that need a reason, because they send work back or end it.
NEEDS_REASON = {"pull-back", "give-back", "reject", "drop", "reopen"}
NEEDS_TYPE = {"pull-back", "give-back", "reject", "reopen"}

# A judge that fails for one of these reasons fails for the wrong reason.
WRONG_REASON = re.compile(r"SyntaxError|IndentationError|ERROR collecting|"
                          r"command not found|No such file or directory")

# A line that reports a failing test: pytest, unittest, TAP and plain runners.
FAIL_LINE = re.compile(r"FAIL|ERROR|Error|not ok|_{3,}")

# The judge passes and the keep check fails only because of the judge files.
BAR_WRONG = "the bar is wrong: the keep check fails on the judge files themselves"

LABEL_COLOURS = {"shaping": "c5def5", "ready": "0e8a16", "building": "fbca04",
                 "approval": "5319e7", "done": "006b75", "dropped": "cccccc"}


def state_of(issue: dict) -> str:
    states = [lab[len(STATE_PREFIX):] for lab in issue["labels"] if lab.startswith(STATE_PREFIX)]
    if len(states) != 1:
        raise Refused(f"piece {issue['number']} has {len(states)} state labels: {states}",
                      "a person fixes the labels by hand, then runs the move again")
    if states[0] not in STATES:
        raise Refused(f"'{STATE_PREFIX}{states[0]}' is not a state")
    return states[0]


# ---------------------------------------------------------------- checks

def check_ready(root: Path, issue: dict) -> dict:
    """The ready gate. Returns the record to write. Refuses on any gap."""
    n = issue["number"]
    spec = parse_spec(issue["body"] or "")
    branch = branch_name(n)
    head = rev(root, branch)
    if head is None:
        raise Refused(f"there is no branch {branch}",
                      f"create {branch} from main and commit the judge files on it")
    bar = bar_hash_at(root, head, spec.files) if spec.files else ""
    main = main_ref(root)
    main_sha = rev(root, main)

    # Run the judge on today's main, with only the judge files added.
    tmp = Path(tempfile.mkdtemp(prefix=f"loop-ready-{n}-"))
    folder = tmp / "main"
    try:
        sh(["git", "worktree", "add", "--detach", "--quiet", str(folder), main], root)
        ok, poutput = (True, "") if spec.kind == "scaffold" else prepare(folder)
        if not ok:
            raise Refused("the Prepare command fails on a fresh copy of main:\n"
                          f"{poutput.strip()[-1500:]}",
                          "fix the Prepare command in AGENTS.md, then run gate.py doctor")
        if spec.keep:
            # What must stay the same is checked on main as it is today.
            kcode, koutput = run_judge(folder, spec.keep)
            if kcode != 0:
                raise Refused(f"the keep check already fails on main:\n{koutput.strip()[-1500:]}",
                              "fix main first, or correct the Keep: command")
        if spec.files:
            sh(["git", "checkout", head, "--", *spec.files], folder)
        code, output = run_judge(folder, spec.command)
    finally:
        sh(["git", "worktree", "remove", "--force", str(folder)], root, check=False)
        shutil.rmtree(tmp, ignore_errors=True)

    tail = output.strip()[-1500:]
    if spec.kind == "scaffold":
        # The first piece of an empty project: its judge is that the test
        # command runs, so there is nothing that must fail on main.
        pass
    elif code == 0:
        raise Refused("the judge already passes on main, so there is nothing to build",
                      "make the judge test what the Done when items ask for")
    elif WRONG_REASON.search(output):
        raise Refused("the judge fails on main for the wrong reason "
                      f"(a broken test, not a missing feature):\n{tail}",
                      "fix the judge so it fails on an assertion")
    else:
        # The ID may sit inside a test name, like test_D1_adds, so do not use \b.
        # Count an ID only on a line that reports a failure, so that a runner
        # which also prints passing tests (pytest -v) cannot fake a failure.
        fail_lines = "\n".join(line for line in output.splitlines() if FAIL_LINE.search(line))

        def named_in(text: str, i: str) -> bool:
            return re.search(rf"(?<![A-Za-z0-9]){i}(?![0-9])", text) is not None
        build = [i for i in spec.done_when if i not in spec.stays]
        named = [i for i in build if named_in(fail_lines, i)]
        if not named:
            raise Refused("the judge fails on main, but its output names no spec ID "
                          f"({', '.join(build)}):\n{tail}",
                          "put the spec ID in each test name, like test_D1_adds_a_habit")
        missing = [i for i in build if i not in named]
        if missing:
            raise Refused(f"no failing judge test names {', '.join(missing)}",
                          "give every Done when item at least one test, or mark an item that "
                          "already holds as '(stays)'")
        failing_stays = [i for i in spec.stays if named_in(fail_lines, i)]
        if failing_stays:
            raise Refused(f"{', '.join(failing_stays)} is marked (stays) but fails on main",
                          "a (stays) item already holds today; test only what it says")
    if spec.stays:
        judge_text = "".join(sh(["git", "show", f"{head}:{f}"], root).stdout for f in spec.files)
        untested = [i for i in spec.stays
                    if not re.search(rf"(?<![A-Za-z0-9]){i}(?![0-9])", judge_text)]
        if untested:
            raise Refused(f"no judge test names {', '.join(untested)}",
                          "give every (stays) item a test with its ID in the name")
    return {"move": "ready", "bar": bar, "files": spec.files, "command": spec.command,
            "kind": spec.kind, "keep": spec.keep, "stays": list(spec.stays),
            "settings": spec.settings,
            "commit": head, "main": main_sha,
            "spec": spec_hash(issue["body"] or "")}


def check_frozen(issue: dict, comments: list[str]) -> dict:
    """The spec may not change after ready. Returns the ready record."""
    ready = last_record(comments, "ready")
    if ready is None:
        raise Refused(f"piece {issue['number']} has no ready record",
                      "move it back to shaping and through the ready gate")
    if ready["spec"] != spec_hash(issue["body"] or ""):
        raise Refused("the spec changed after the piece became ready",
                      "pull the piece back to shaping and take it through ready again")
    return ready


def judge(folder: Path, ready: dict) -> tuple[bool, str]:
    """Run the frozen judge in a build folder. The bar must be unchanged."""
    if ready["files"] and bar_hash_in(folder, ready["files"]) != ready["bar"]:
        return False, "the judge files differ from the ones fixed at ready"
    markers = conflict_markers(folder)
    if markers:
        return False, f"merge conflict markers are left in: {', '.join(markers)}"
    git_dir = Path(sh(["git", "rev-parse", "--absolute-git-dir"], folder).stdout.strip())
    prepare_paths = git_dir / "info" / "ai-loop-kit-prepare-paths"
    if prepare_paths.is_file():
        roots = prepare_paths.read_text().splitlines()
        if roots:
            added = sh(["git", "diff", "--name-only", "--diff-filter=A",
                        f"{ready['commit']}..HEAD"], folder).stdout.splitlines()
            leaked = [path for path in added if any(
                path == root.rstrip("/") or path.startswith(root.rstrip("/") + "/")
                for root in roots)]
            if leaked:
                return False, ("the piece adds files under paths Prepare created: "
                               + ", ".join(leaked))
    if not ready.get("settings"):
        changed = changed_check_settings(folder)
        if changed:
            return False, ("the build changes the project's check settings: "
                           f"{', '.join(changed)}. Put them back. A piece may change them only "
                           "when its spec says 'Settings: may change'.")
    code, output = run_judge(folder, ready["command"])
    if code != 0:
        return False, output
    if ready.get("keep"):
        kcode, koutput = run_judge(folder, ready["keep"])
        if kcode != 0:
            if ready["files"] and keep_passes_without_judge(folder, ready):
                return False, f"{BAR_WRONG}. Without them it passes:\n{koutput}"
            return False, f"the judge passes, but the keep check now fails:\n{koutput}"
    return True, output


def keep_passes_without_judge(folder: Path, ready: dict) -> bool:
    """Run the keep check once with the judge files set aside. If it passes,
    the judge files break it, and no build can fix that."""
    aside = Path(tempfile.mkdtemp(prefix="loop-aside-"))
    moved = []
    try:
        for i, f in enumerate(ready["files"]):
            if (folder / f).is_file():
                shutil.move(str(folder / f), str(aside / str(i)))
                moved.append((aside / str(i), folder / f))
        code, _ = run_judge(folder, ready["keep"])
        return code == 0
    finally:
        for held, home in moved:
            shutil.move(str(held), str(home))
        shutil.rmtree(aside, ignore_errors=True)


# ---------------------------------------------------------------- moves

def move(gh: GitHub, root: Path, n: int, to: str, reason: str = "",
         reason_type: str = "", folder: Optional[Path] = None, pr: str = "") -> str:
    issue = gh.issue(n)
    frm = state_of(issue)
    name = MOVES.get((frm, to))
    if name is None:
        allowed = sorted(t for (f, t) in MOVES if f == frm)
        raise Refused(f"there is no move from {frm} to {to}",
                      f"from {frm} a piece can go to: {', '.join(allowed)}")
    if name in NEEDS_REASON and not reason:
        raise Refused(f"the {name} move needs a reason", "pass --reason")
    if name in NEEDS_TYPE and reason_type not in REASON_TYPES:
        raise Refused(f"the {name} move needs a typed reason", "pass --type and --reason")

    record: dict = {"move": name, "from": frm, "to": to}
    note = f"{frm} → {to} ({name})."
    comments = gh.comments(n)
    if name == "ready":
        record = {**check_ready(root, issue), "from": frm, "to": to}
        if record["kind"] == "scaffold":
            note += " Scaffold piece: the fails-on-main check does not apply."
        else:
            note += " The judge fails on main as it should, naming every spec ID to build."
            if record["stays"]:
                note += f" {', '.join(record['stays'])} already hold on main, as marked."
        if record["keep"]:
            note += f" The keep check `{record['keep']}` passes on main."
        note += f" Bar `{record['bar'][:12] or 'none'}` is fixed."
    elif name == "claim":
        check_frozen(issue, comments)
    elif name == "submit":
        ready = check_frozen(issue, comments)
        if folder is None or not pr:
            raise Refused("submit needs the build folder and the pull request",
                          "the run makes this move, not a person")
        passed, output = judge(folder, ready)
        if not passed:
            raise Refused(f"the judge does not pass:\n{output.strip()[-1500:]}")
        record["pr"] = pr
        record["commit"] = rev(folder, "HEAD")
        note += f" The gate ran the judge and it passed. Pull request: {pr}"
    elif name == "merged":
        found = gh.pr_for_branch(branch_name(n))
        if not found or found["state"] != "MERGED":
            raise Refused(f"the pull request for {branch_name(n)} is not merged",
                          "the person merges it on GitHub")
    if reason:
        record["reason"] = reason
        note += f" Reason: {reason}"
    if reason_type:
        record["type"] = reason_type

    add = [STATE_PREFIX + to]
    remove = [STATE_PREFIX + frm]
    if name in ("give-back", "reject"):
        add.append(NEEDS_YOU)
    elif NEEDS_YOU in issue["labels"] and to in ("ready", "dropped", "done"):
        remove.append(NEEDS_YOU)
    gh.comment(n, record_text(record, note))
    gh.set_labels(n, add, remove)
    if issue.get("state", "OPEN") == "OPEN":
        if to == "done":
            gh.close(n, "completed")
        elif to == "dropped":
            gh.close(n, "not planned")
    return note


def capture(gh: GitHub, title: str, body: str) -> int:
    n = gh.create_issue(title, body, [STATE_PREFIX + "shaping"])
    gh.comment(n, record_text({"move": "capture", "from": "new", "to": "shaping"},
                              "new → shaping (capture)."))
    return n


def sync(gh: GitHub, root: Path) -> list[str]:
    notes = []
    # The pull request's closing words close the issue when it merges, so a
    # merged piece may already be closed. Look at closed issues too.
    for item in gh.issues_with_label(STATE_PREFIX + "approval", closed_too=True):
        found = gh.pr_for_branch(branch_name(item["number"]))
        if found and found["state"] == "MERGED":
            notes.append(f"{item['number']}: " + move(gh, root, item["number"], "done"))
    return notes


def init(gh: GitHub, root: Path) -> None:
    for s in STATES:
        gh.ensure_label(STATE_PREFIX + s, LABEL_COLOURS[s], f"Loop state: {s}. Only the gate sets it.")
    gh.ensure_label(NEEDS_YOU, "d93f0b", "The piece waits for the person.")
    ignore_loop_folder(root)


# Files that tools make while tests run. A run must never commit them.
GENERATED = ["/.loop/", "__pycache__/", "*.pyc", ".pytest_cache/", ".mypy_cache/",
             ".ruff_cache/", "node_modules/", ".DS_Store", "*.egg-info/", ".coverage"]


def ignore_loop_folder(root: Path) -> None:
    """Ignore .loop/ and generated files through git's local exclude file. A
    builder never edits that file, and the project's own files stay as they are."""
    common = Path(sh(["git", "rev-parse", "--git-common-dir"], root).stdout.strip())
    exclude = (common if common.is_absolute() else root / common) / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    text = exclude.read_text() if exclude.exists() else ""
    have = text.splitlines()
    missing = [g for g in GENERATED if g not in have]
    if missing:
        exclude.write_text(text + ("" if text.endswith("\n") or not text else "\n")
                           + "\n".join(missing) + "\n")


def doctor(gh: GitHub, root: Path) -> list[tuple[bool, str, str]]:
    """Setup's checks, in code. Each is (passed, what, next step)."""
    checks: list[tuple[bool, str, str]] = []

    def add(ok: bool, what: str, fix: str) -> bool:
        checks.append((ok, what, "" if ok else fix))
        return ok

    origin = sh(["git", "remote", "get-url", "origin"], root, check=False).stdout.strip()
    if not add(bool(origin), "the project has an origin",
               "create the GitHub repository and add it as origin"):
        return checks
    if not add(gh.signed_in(), "gh is signed in", "run: gh auth login"):
        return checks
    try:
        main = main_ref(root)
        add(main == "origin/main", "main has a commit on origin", "push a first commit to main")
    except Refused as r:
        add(False, "main has a commit on origin", r.next_step)
        return checks
    have = set(gh.labels())
    add(all(STATE_PREFIX + s in have for s in STATES), "the state labels exist", "run: gate.py init")

    tmp = Path(tempfile.mkdtemp(prefix="loop-doctor-"))
    folder = tmp / "main"
    try:
        sh(["git", "worktree", "add", "--detach", "--quiet", str(folder), main], root)
        settings = loop_settings(folder)
        if not add("test" in settings, "AGENTS.md on main names the Test command",
                   "merge setup's AGENTS.md section, with a 'Test command:' line"):
            return checks
        if "prepare" in settings:
            ok, output = prepare(folder)
            if not add(ok, f"Prepare passes on a fresh copy of main ({settings['prepare']})",
                       "fix the Prepare command:\n" + output.strip()[-800:]):
                return checks
        code, output = run_judge(folder, settings["test"])
        add(code == 0, f"the tests pass on a fresh copy of main ({settings['test']})",
            "every piece's keep check needs a green main. Fix the tests or the environment, "
            "or add a Prepare command:\n" + output.strip()[-800:])
    finally:
        sh(["git", "worktree", "remove", "--force", str(folder)], root, check=False)
        shutil.rmtree(tmp, ignore_errors=True)
    return checks


def status(gh: GitHub) -> str:
    lines = []
    for s in STATES[:4]:
        items = gh.issues_with_label(STATE_PREFIX + s)
        lines.append(f"{s}: " + (", ".join(
            f"{i['number']}{' (needs you)' if NEEDS_YOU in i['labels'] else ''} {i['title']}"
            for i in items) or "none"))
    return "\n".join(lines)


def report(gh: GitHub) -> str:
    """Count hand-backs by typed reason and by piece from trusted records."""
    counts: dict[str, int] = {}
    pieces: dict[int, list[str]] = {}
    seen: dict[int, set[str]] = {}
    for state in STATES:
        for issue in gh.issues_with_label(STATE_PREFIX + state, closed_too=True):
            n = issue["number"]
            if n in seen:
                continue
            seen[n] = set()
            for record in records(gh.comments(n)):
                kind = record.get("type")
                if record.get("move") not in NEEDS_TYPE or kind not in REASON_TYPES:
                    continue
                key = f"{kind}: {record.get('reason', '')}"
                counts[kind] = counts.get(kind, 0) + 1
                pieces.setdefault(n, []).append(key)
    lines = [f"{kind}: {counts.get(kind, 0)}" for kind in REASON_TYPES]
    lines.append("by piece:")
    lines += [f"{n}: " + "; ".join(items) for n, items in sorted(pieces.items())]
    if not pieces:
        lines.append("none")
    return "\n".join(lines)


def replace_spec(gh: GitHub, n: int, body: str) -> None:
    """Replace a piece's spec only while it is in shaping."""
    issue = gh.issue(n)
    if state_of(issue) != "shaping":
        raise Refused("the spec can only change while a piece is shaping",
                      "move the piece back to shaping, then edit its spec")
    parse_spec(body)
    gh.edit_body(n, body)


def request_stop(root: Path) -> str:
    """Ask a live run to stop at its next boundary."""
    loop = root / ".loop"
    if not (loop / "run.lock").is_file():
        raise Refused("there is no run to stop", "start run.py first")
    loop.mkdir(parents=True, exist_ok=True)
    (loop / "stop").write_text("stop after the current attempt\n")
    return "the run will stop after the current attempt"


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="gate.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    c = sub.add_parser("capture")
    c.add_argument("--title", required=True)
    c.add_argument("--body-file", required=True)
    ck = sub.add_parser("check")
    ck.add_argument("n", type=int)
    m = sub.add_parser("move")
    m.add_argument("n", type=int)
    m.add_argument("to", choices=STATES)
    m.add_argument("--reason", default="")
    m.add_argument("--type", dest="reason_type", choices=REASON_TYPES, default="")
    s = sub.add_parser("spec")
    s.add_argument("n", type=int)
    s.add_argument("--body-file", required=True)
    sub.add_parser("sync")
    sub.add_parser("status")
    sub.add_parser("doctor")
    sub.add_parser("report")
    sub.add_parser("stop")
    args = p.parse_args(argv)

    root = repo_root(Path.cwd())
    gh = GitHub(root)
    try:
        if args.cmd == "init":
            init(gh, root)
            print("ok: labels made, .loop/ ignored locally")
        elif args.cmd == "capture":
            n = capture(gh, args.title, Path(args.body_file).read_text())
            print(f"ok: captured piece {n} in shaping")
        elif args.cmd == "check":
            issue = gh.issue(args.n)
            rec = check_ready(root, issue)
            print(f"ok: piece {args.n} would pass the ready gate (bar {rec['bar'][:12]})")
        elif args.cmd == "move":
            print("ok: " + move(gh, root, args.n, args.to, args.reason,
                                  args.reason_type))
        elif args.cmd == "spec":
            replace_spec(gh, args.n, Path(args.body_file).read_text())
            print(f"ok: piece {args.n} spec replaced")
        elif args.cmd == "sync":
            print("\n".join(sync(gh, root)) or "ok: nothing merged since the last sync")
        elif args.cmd == "status":
            print(status(gh))
        elif args.cmd == "doctor":
            checks = doctor(gh, root)
            for ok, what, fix in checks:
                print(f"{'ok  ' if ok else 'FAIL'} {what}")
                if fix:
                    print(f"     next: {fix}")
            if not all(ok for ok, _, _ in checks):
                return 2
        elif args.cmd == "report":
            print(report(gh))
        elif args.cmd == "stop":
            print("ok: " + request_stop(root))
    except Refused as r:
        print(f"refused: {r.reason}", file=sys.stderr)
        if r.next_step:
            print(f"next: {r.next_step}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
