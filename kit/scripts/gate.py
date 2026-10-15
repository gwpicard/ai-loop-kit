#!/usr/bin/env python3
"""The gate: the only code that moves a piece from one state to another.

A piece is a GitHub issue with exactly one `state:` label. The gate allows
only the moves in MOVES, runs the checks for each one itself, and writes a
record on the issue for every move it makes.

    gate.py init                       make the labels, ignore .loop/
    gate.py capture --title T --body-file F
    gate.py check N                    run the ready checks, move nothing
    gate.py move N STATE [--reason R] [--type T]
    gate.py spec N --body-file F       replace a shaping piece's spec
    gate.py sync                       move merged pieces to done
    gate.py status                     list the pieces by state
    gate.py doctor                     check the project is ready for the loop
    gate.py report                     count typed hand-backs
    gate.py stop                       stop a live run after its current attempt
"""
from __future__ import annotations

import argparse
import hashlib
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
                     bar_file_list, conflict_markers, last_record, main_ref,
                     clean_quality_outputs, loop_settings, prepare,
                     record_quality_outputs, record_text, records, repo_root, rev,
                     run_judge, sh, skipped_tests, spec_hash)
from testlint import lint_files  # noqa: E402
import measure  # noqa: E402
from measure import run_measure, target_met  # noqa: E402
import critic  # noqa: E402

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
NEEDS_TYPE = {"pull-back", "give-back", "reject", "reopen", "stopped"}

# A judge that fails for one of these reasons fails for the wrong reason.
WRONG_REASON = re.compile(r"^\s*(?:E\s+)?(?:SyntaxError|IndentationError|"
                          r"ModuleNotFoundError|ImportError|FileNotFoundError):|"
                          r"^ERROR collecting(?:\s|$)", re.MULTILINE)

# A line that reports a failing test: pytest, unittest, TAP and plain runners.
FAIL_LINE = re.compile(r"FAIL|ERROR|Error|not ok|_{3,}")

# The judge passes and the keep check fails only because of the judge files.
BAR_WRONG = "the bar is wrong: the keep check fails on the judge files themselves"


def _package_spec(body: str):
    """Named hook for the P3 parser, kept beside the gate entry points."""
    return measure.parse_spec(body)


def _capture(folder: Path, command: str) -> Path:
    """Named hook for the gauntlet capture step."""
    return critic.capture(folder, command)


def _reference_path(root: Path, reference: str) -> str:
    """Named hook for checking a gauntlet reference."""
    return critic.reference_path(root, reference)

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
    spec, kind_fields = _package_spec(issue["body"] or "")
    branch = branch_name(n)
    head = rev(root, branch)
    if head is None:
        raise Refused(f"there is no branch {branch}",
                      f"create {branch} from main and commit the judge files on it")
    bar_files = bar_file_list(root, head, spec.files)
    bar = bar_hash_at(root, head, spec.files) if spec.files else ""
    main = main_ref(root)
    main_sha = rev(root, main)

    # Run the judge on today's main, with only the judge files added.
    tmp = Path(tempfile.mkdtemp(prefix=f"loop-ready-{n}-"))
    folder = tmp / "main"
    kind_evidence = {}
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
        if bar_files:
            sh(["git", "checkout", head, "--", *bar_files], folder)
        if spec.kind not in ("goal", "gauntlet"):
            lint = lint_files([folder / f for f in spec.files], folder,
                              " ".join(spec.done_when.values()))
            if lint:
                raise Refused("the judge has quality problems:\n" + "\n".join(lint),
                              "fix the judge files, then run gate.py check again")
            code, output = run_judge(folder, spec.command)
        else:
            code, output = 0, ""
        if spec.kind == "goal":
            try:
                baseline, report = run_measure(kind_fields["measure"], folder)
            except ValueError as error:
                raise Refused(f"Measure failed on main:\n{error}",
                              "fix Measure: so it prints one finite number on its last line")
            if target_met(baseline, kind_fields["target"]):
                raise Refused(f"Measure already meets Target on main: {baseline:g}",
                              "write a goal whose target is not met on today's main")
            kind_evidence = {"measure": kind_fields["measure"], "target": kind_fields["target"],
                             "main_value": baseline, "main_measure": report}
        elif spec.kind == "gauntlet":
            capture = _capture(folder, kind_fields["capture"])
            reference = _reference_path(root, kind_fields["reference"])
            try:
                passed, report = critic.judge(capture, reference, kind_fields["criteria"], folder)
            except (ValueError, OSError) as error:
                raise Refused(f"critics failed on main:\n{error}",
                              "fix Capture, Reference or the critic verdict format")
            if passed:
                raise Refused("main already wins the gauntlet against Reference",
                              "write criteria that describe a change still to make")
            kind_evidence = {"capture": kind_fields["capture"], "reference": reference,
                             "criteria": kind_fields["criteria"], "main_critics": report}
    finally:
        sh(["git", "worktree", "remove", "--force", str(folder)], root, check=False)
        shutil.rmtree(tmp, ignore_errors=True)

    tail = output.strip()[-1500:]
    if spec.kind in ("scaffold", "goal", "gauntlet"):
        # The first piece of an empty project: its judge is that the test
        # command runs, so there is nothing that must fail on main.
        pass
    elif code == 0:
        raise Refused("the judge already passes on main, so there is nothing to build",
                      "make the judge test what the Done when items ask for")
    elif (code == 127 and "command not found" in output) or WRONG_REASON.search(output):
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
    return {"move": "ready", "bar": bar, "bar_files": bar_files,
            "contract": spec.done_when, "intent": spec.intent, "approach": spec.approach,
            "files": spec.files, "command": spec.command,
            "kind": spec.kind, **kind_evidence,
            "keep": spec.keep or loop_settings(root).get("keep", ""),
            "test": loop_settings(root).get("test", ""),
            "prepare": loop_settings(root).get("prepare", ""),
            "quality": loop_settings(root).get("quality", []),
            "standards": loop_settings(root).get("standards", ""),
            "idle_limit": loop_settings(root).get("idle limit", "10"),
            "waiting_limit": loop_settings(root).get("waiting limit", "3"),
            "stays": list(spec.stays),
            "settings": spec.settings,
            "protected_paths": loop_settings(root).get("protected paths", []),
            "large_files": list(spec.large_files),
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


def check_claim_bar(root: Path, n: int, ready: dict) -> None:
    """Claim is valid only while the judge bar still matches ready."""
    head = rev(root, branch_name(n))
    if head is None or (ready["files"] and
                        bar_hash_at(root, head, ready.get("bar_files", ready["files"]))
                        != ready["bar"]):
        raise Refused("the judge bar changed after the piece became ready",
                      "move the piece back to shaping and run the ready gate again")


def judge(folder: Path, ready: dict, attempt: Optional[int] = None,
          attempt_started: Optional[float] = None) -> tuple[bool, str]:
    """Run the frozen judge in a build folder. The bar must be unchanged."""
    if ready["files"] and bar_hash_in(folder, ready.get("bar_files", ready["files"])) != ready["bar"]:
        settings_changed = sh(["git", "diff", "--no-renames", "--name-only",
                               f"{ready['commit']}..HEAD"], folder).stdout.splitlines()
        if "AGENTS.md" in settings_changed:
            return False, "the loop settings changed in AGENTS.md"
        return False, "the judge files differ from the ones fixed at ready"
    changed_tests = changed_existing_tests(folder, ready)
    if changed_tests:
        return False, ("the build changes existing test files not named in the Contract or Files: "
                       + ", ".join(changed_tests))
    main = main_ref(folder)
    changed_paths = sh(["git", "diff", "--no-renames", "--name-only",
                        f"{main}...HEAD"], folder).stdout.splitlines()
    contract_text = " ".join(ready.get("contract", {}).values()) + " " + \
        " ".join(ready.get("files", []))
    protected = [p for p in changed_paths for target in ready.get("protected_paths", [])
                 if (p == target.rstrip("/") or p.startswith(target.rstrip("/") + "/"))
                 and target not in contract_text]
    if protected:
        return False, "the build changes protected paths not named in the Contract: " + \
            ", ".join(sorted(set(protected)))
    oversized = []
    for path in changed_paths:
        target = folder / path
        if path in ready.get("large_files", []) or not target.is_file():
            continue
        before = sh(["git", "show", f"{main}:{path}"], folder, check=False).stdout
        before_lines = len(before.splitlines())
        after_lines = len(target.read_text(errors="replace").splitlines())
        if before_lines < 1000 <= after_lines:
            oversized.append(path)
    if oversized:
        return False, ("the build takes a file from under 1,000 lines to 1,000 or more: "
                       + ", ".join(oversized) + ". Add 'Large file: <path>' to the Judge section.")
    secret_files = [p for p in changed_paths if Path(p).name == ".env" or
                    Path(p).name.startswith(".env.") and Path(p).name not in
                    {".env.example", ".env.sample", ".env.template"}]
    diff_text = sh(["git", "diff", "--no-ext-diff", f"{main}...HEAD"], folder).stdout
    secret_patterns = [r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                       r"\bAKIA[0-9A-Z]{16}\b", r"\bghp_[A-Za-z0-9]{20,}\b",
                       r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", r"\bsk-[A-Za-z0-9_-]{20,}\b"]
    if secret_files or any(re.search(pattern, diff_text) for pattern in secret_patterns):
        return False, "the diff contains a secret-shaped value or .env file"
    markers = conflict_markers(folder)
    if markers:
        return False, f"merge conflict markers are left in: {', '.join(markers)}"
    git_dir = Path(sh(["git", "rev-parse", "--absolute-git-dir"], folder).stdout.strip())
    prepare_paths = git_dir / "info" / "ai-loop-kit-prepare-paths"
    if prepare_paths.is_file():
        roots = prepare_paths.read_text().splitlines()
        if roots:
            added = sh(["git", "diff", "--no-renames", "--name-only", "--diff-filter=A",
                        f"{ready['commit']}..HEAD"], folder).stdout.splitlines()
            leaked = [path for path in added if any(
                path == root.rstrip("/") or path.startswith(root.rstrip("/") + "/")
                for root in roots)]
            if leaked:
                return False, ("the piece adds files under paths Prepare created: "
                               + ", ".join(leaked))
    if not ready.get("settings"):
        changed = changed_check_settings(folder, (ready.get("standards", ""),)
                                        if ready.get("standards") else ())
        if changed:
            if "AGENTS.md" in changed:
                return False, "the loop settings changed in AGENTS.md"
            return False, ("the build changes the project's check settings: "
                           f"{', '.join(changed)}. Put them back. A piece may change them only "
                           "when its spec says 'Settings: may change'.")
    protected_paths = ready.get("protected_paths", [])
    kind = ready.get("kind", "feature")
    if kind in ("goal", "gauntlet"):
        code, output = 0, ""
    else:
        code, output = run_judge(folder, ready["command"], protected_paths=protected_paths)
    if skipped_tests(output):
        return False, f"the judge reported skipped tests:\n{output.strip()[-1500:]}"
    if code != 0:
        return False, output
    kind_passed = None
    kind_output = ""
    if kind == "goal":
        hypothesis_path = folder / ".loop" / "hypothesis"
        try:
            hypothesis = hypothesis_path.read_text().strip()
        except OSError:
            hypothesis = ""
        lines = [line.strip() for line in hypothesis.splitlines() if line.strip()]
        expected = f"Attempt {attempt}:" if attempt else ""
        selected = next((line for line in reversed(lines)
                         if not expected or line.lower().startswith(expected.lower())), "")
        hypothesis_first = bool(selected)
        if attempt_started is not None and hypothesis_first:
            try:
                hypothesis_time = hypothesis_path.stat().st_mtime
                hypothesis_first = hypothesis_time >= attempt_started
                changed = sh(["git", "diff", "--no-renames", "--name-only",
                              f"{ready['commit']}..HEAD"], folder).stdout.splitlines()
                for name in changed:
                    if name.startswith(".loop/") or not (folder / name).is_file():
                        continue
                    changed_time = (folder / name).stat().st_mtime
                    if changed_time >= attempt_started and changed_time < hypothesis_time:
                        hypothesis_first = False
                        break
            except OSError:
                hypothesis_first = False
        try:
            value, report = run_measure(ready["measure"], folder)
            target = ready["target"]
            kind_passed = target_met(value, target) and hypothesis_first
            hypothesis_note = f"Hypothesis: {selected}" if hypothesis_first else \
                "Hypothesis missing or late: write 'Attempt N: ...' before changing code"
            kind_output = (f"Goal baseline on main: {ready['main_value']:g}\n"
                           f"Goal after attempt: {value:g}\nTarget: {target}\n"
                           f"{hypothesis_note}\n{report}")
        except ValueError as error:
            kind_passed = False
            kind_output = f"Measure failed after the attempt:\n{error}"
    elif kind == "gauntlet":
        try:
            captured = _capture(folder, ready["capture"])
            kind_passed, report = critic.judge(captured, ready["reference"],
                                               ready["criteria"], folder)
            kind_output = (f"Gauntlet baseline on main:\n{ready.get('main_critics', '')}\n"
                           f"Gauntlet after attempt:\n{report}")
        except (Refused, ValueError, OSError) as error:
            kind_passed = False
            kind_output = f"Gauntlet judge failed:\n{error}"
    if ready.get("keep"):
        kcode, koutput = run_judge(folder, ready["keep"], protected_paths=protected_paths)
        if skipped_tests(koutput):
            result = f"the keep check reported skipped tests:\n{koutput.strip()[-1500:]}"
            return False, result + (("\n\n" + kind_output) if kind_output else "")
        if kcode != 0:
            if ready["files"] and keep_passes_without_judge(folder, ready):
                result = f"{BAR_WRONG}. Without them it passes:\n{koutput}"
                return False, result + (("\n\n" + kind_output) if kind_output else "")
            result = f"the judge passes, but the keep check now fails:\n{koutput}"
            return False, result + (("\n\n" + kind_output) if kind_output else "")
        output += f"\n\nKeep: {ready['keep']}\nExit: {kcode}\n{koutput.strip()}"
    quality_results = []
    for command in ready.get("quality", []):
        qcode, qoutput = run_judge(folder, command, protected_paths=protected_paths)
        quality_results.append(f"Quality: {command}\nExit: {qcode}\n{qoutput.strip()}")
        if qcode != 0:
            result = "a Quality command failed:\n" + "\n\n".join(quality_results)
            return False, result + (("\n\n" + kind_output) if kind_output else "")
    if quality_results:
        output += "\n\n" + "\n\n".join(quality_results)
    if kind_output:
        return bool(kind_passed), (output + "\n\n" if output else "") + kind_output
    return True, output


def changed_existing_tests(folder: Path, ready: dict) -> list[str]:
    """Find edits to existing tests, fixtures or conftest files outside scope."""
    base = sh(["git", "merge-base", "HEAD", main_ref(folder)], folder).stdout.strip()
    changed = sh(["git", "diff", "--no-renames", "--name-only", base], folder).stdout.splitlines()
    contract_text = "\n".join(str(v) for v in ready.get("contract", {}).values())
    allowed = list(ready.get("files", []))
    return sorted(name for name in changed if _is_test_support(name) and
                  _exists_at(folder, base, name) and
                  not any(name == p or name.startswith(p.rstrip("/") + "/") for p in allowed) and
                  name not in contract_text)


def _exists_at(folder: Path, ref: str, name: str) -> bool:
    return sh(["git", "cat-file", "-e", f"{ref}:{name}"], folder, check=False).returncode == 0


def _is_test_support(name: str) -> bool:
    path = Path(name)
    parts = {p.lower() for p in path.parts}
    base = path.name.lower()
    return (base == "conftest.py" or "fixture" in base or "fixtures" in parts or
            "test" in parts or "tests" in parts or "__tests__" in parts or
            base.startswith("test_") or base.endswith("_test.py") or
            ".test." in base or ".spec." in base)


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
        code, _ = run_judge(folder, ready["keep"],
                            protected_paths=ready.get("protected_paths", []))
        return code == 0
    finally:
        for held, home in moved:
            shutil.move(str(held), str(home))
        shutil.rmtree(aside, ignore_errors=True)


def quality_fails_on_main(folder: Path, command: str, test_command: str = "",
                          protected_paths: Optional[list[str]] = None) -> bool:
    """Check a failed Quality command in a fresh main worktree."""
    root = repo_root(folder)
    main = main_ref(folder)
    ok, _ = quality_on_fresh_main(root, main, command, test_command, protected_paths)
    return not ok


def quality_probe_path(root: Path, piece: int, command: str, main_commit: str) -> Path:
    key = hashlib.sha256((command + "\0" + main_commit).encode()).hexdigest()[:16]
    return root / ".loop" / f"main-quality-{piece}-{key}.json"


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
        elif record["kind"] == "goal":
            note += (f" Goal baseline is {record['main_value']:g}; target is "
                     f"{record['target']}, which main does not meet.")
        elif record["kind"] == "gauntlet":
            note += " Main does not win the gauntlet against the reference."
        else:
            note += " The judge fails on main as it should, naming every spec ID to build."
            if record["stays"]:
                note += f" {', '.join(record['stays'])} already hold on main, as marked."
        if record["keep"]:
            note += f" The keep check `{record['keep']}` passes on main."
        note += f" Bar `{record['bar'][:12] or 'none'}` is fixed."
    elif name == "claim":
        ready = check_frozen(issue, comments)
        check_claim_bar(root, n, ready)
    elif name == "submit":
        ready = check_frozen(issue, comments)
        if folder is None:
            raise Refused("submit needs the build folder",
                          "the run makes this move, not a person")
        passed, output = judge(folder, ready)
        if not passed:
            raise Refused(f"the judge does not pass:\n{output.strip()[-1500:]}")
        if pr:
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


def quality_on_fresh_main(root: Path, main: str, command: str,
                          test_command: str = "",
                          protected_paths: Optional[list[str]] = None) -> tuple[bool, str]:
    """Run Test, then one Quality command in its own prepared copy of main."""
    tmp = Path(tempfile.mkdtemp(prefix="loop-doctor-quality-"))
    folder = tmp / "main"
    try:
        sh(["git", "worktree", "add", "--detach", "--quiet", str(folder), main], root)
        ok, output = prepare(folder, protected_paths=protected_paths)
        if not ok:
            return False, "Prepare failed:\n" + output.strip()[-800:]
        if test_command:
            code, test_output = run_judge(folder, test_command,
                                          protected_paths=protected_paths)
            if code:
                return False, "Test command failed before Quality:\n" + test_output.strip()[-800:]
        code, output = run_judge(folder, command, protected_paths=protected_paths)
        clean_quality_outputs(folder, record_quality_outputs(folder))
        return code == 0, output
    finally:
        sh(["git", "worktree", "remove", "--force", str(folder)], root, check=False)
        try:
            tmp.rmdir()
        except OSError:
            pass


# Files that tools make while tests run. A run must never commit them.
GENERATED = ["/.loop/", "__pycache__/", "*.pyc", ".pytest_cache/", ".mypy_cache/",
             ".ruff_cache/", "node_modules/", ".DS_Store", "*.egg-info/", ".coverage",
             ".coverage.*", "mutants/", ".stryker-tmp/", "coverage.json", "coverage.xml",
             "coverage.lcov"]


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


def doctor(gh: GitHub, root: Path, extra_quality: Optional[list[str]] = None) -> list[tuple[bool, str, str]]:
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
    protection = gh.main_protection() if hasattr(gh, "main_protection") else "unknown"
    checks.append((True, f"main branch protection: {protection}", ""))
    have = set(gh.labels())
    add(all(STATE_PREFIX + s in have for s in STATES), "the state labels exist", "run: gate.py init")

    old_worktrees = root / ".loop" / "worktrees"
    if old_worktrees.is_dir() and any(old_worktrees.iterdir()):
        folders = ", ".join(
            (child.relative_to(root).as_posix() for child in sorted(old_worktrees.iterdir())))
        checks.append((True, f"warning: old in-project worktrees can break project tests: {folders}",
                       f"The person may remove these folders after checking them: {folders}."))

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
        for command in [*settings.get("quality", []), *(extra_quality or [])]:
            qok, qoutput = quality_on_fresh_main(root, main, command, settings["test"])
            if ("no changed Python functions found" in qoutput or
                    "no mutmut source paths configured" in qoutput):
                add(True, f"Quality mutation check could not be exercised on main ({command})", "")
            else:
                add(qok, f"Quality command passes on a fresh copy of main ({command})",
                    f"Quality check failed: {command}\n{qoutput.strip()[-800:]}")
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
                if (record.get("move") not in NEEDS_TYPE and record.get("move") != "judge-gap") or \
                        kind not in REASON_TYPES:
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
    _package_spec(body)
    gh.edit_body(n, body)


def request_stop(root: Path) -> str:
    """Ask a live run to stop at its next boundary."""
    loop = root / ".loop"
    if not (loop / "run.lock").is_file():
        raise Refused("there is no run to stop", "start run.py first")
    loop.mkdir(parents=True, exist_ok=True)
    (loop / "stop").write_text("stop after the current attempt\n")
    return "the run will stop after the current attempt"


def build_parser() -> argparse.ArgumentParser:
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
    d = sub.add_parser("doctor")
    d.add_argument("--quality-command", action="append", default=[],
                   help="also dry-run this proposed Quality command on fresh main")
    sub.add_parser("report")
    sub.add_parser("stop")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

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
            checks = doctor(gh, root, args.quality_command)
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
