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
import json
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "quality"))
from loopkit import (CAUSES, NEEDS_YOU, STATE_PREFIX, STATES, GitHub, Refused,  # noqa: E402
                     REASON_TYPES,
                     bar_hash_at, bar_hash_in, branch_name, changed_check_settings,
                     bar_file_list, conflict_markers, last_record, main_ref,
                     clean_quality_outputs, keep_limit_seconds, loop_settings,
                     parse_spec, prepare,
                     record_quality_outputs, record_text, records, repo_root, rev,
                     run_judge, sh, skipped_tests, spec_hash)
from proposed_quality import apply as apply_proposed_quality  # noqa: E402
import critic  # noqa: E402
import measure  # noqa: E402
from testlint import lint_files  # noqa: E402
from research import stale_findings  # noqa: E402

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


def _kind_ready_judge(folder: Path, spec) -> tuple[bool, str, dict]:
    """Run the goal or gauntlet baseline while checking a piece for ready."""
    if spec.kind == "goal":
        output, record = measure.ready(folder, spec.measure, spec.target)
        return True, output, record
    if spec.kind == "gauntlet":
        output, record = critic.ready(folder, spec.capture, spec.reference, list(spec.criteria))
        return True, output, record
    return False, "", {}


def _kind_attempt_judge(folder: Path, ready: dict) -> tuple[int, str]:
    """Run the measurement or blind critic for one completed attempt."""
    if ready.get("kind") == "goal":
        return measure.judge_attempt(folder, ready)
    if ready.get("kind") == "gauntlet":
        return critic.judge_attempt(folder, ready)
    return -1, ""


def check_times(output: str) -> list[float]:
    """Extract elapsed seconds from Keep checks recorded in command output."""
    return [float(value) for value in re.findall(
        r"Keep took: (\d+(?:\.\d+)?) seconds", output)]


def run_keep(folder: Path, command: str, timeout: int,
             protected_paths: Optional[list[str]] = None) -> tuple[int, str]:
    """Run Keep with its limit and report the elapsed seconds."""
    started = time.monotonic()
    code, output = run_judge(folder, command, timeout=timeout,
                             protected_paths=protected_paths)
    elapsed = time.monotonic() - started
    return code, f"{output.rstrip()}\nKeep took: {elapsed:.3f} seconds".lstrip()


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
    bar_files = bar_file_list(root, head, spec.files)
    bar = bar_hash_at(root, head, spec.files, bar_files) if spec.files else ""
    main = main_ref(root)
    main_sha = rev(root, main)
    settings = loop_settings(root)
    keep_limit = keep_limit_seconds(settings)
    keep_command = spec.keep or settings.get("keep", "")
    keep_output = ""

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
        if keep_command:
            # What must stay the same is checked on main as it is today.
            kcode, koutput = run_keep(folder, keep_command, timeout=keep_limit)
            keep_output = koutput
            if kcode != 0:
                raise Refused(f"the keep check already fails on main:\n{koutput.strip()[-1500:]}",
                              "fix main first, or correct the Keep: command")
        if bar_files:
            sh(["git", "checkout", head, "--", *bar_files], folder)
        lint = lint_files([folder / f for f in spec.files], folder,
                          " ".join(spec.done_when.values()))
        if lint:
            raise Refused("the judge has quality problems:\n" + "\n".join(lint),
                          "fix the judge files, then run gate.py check again")
        kind_record = {}
        if spec.kind in ("goal", "gauntlet"):
            _, output, kind_record = _kind_ready_judge(folder, spec)
            code = 1
        else:
            code, output = run_judge(folder, spec.command)
    finally:
        sh(["git", "worktree", "remove", "--force", str(folder)], root, check=False)
        shutil.rmtree(tmp, ignore_errors=True)

    tail = output.strip()[-1500:]
    if spec.kind in ("goal", "gauntlet"):
        pass
    elif spec.kind == "scaffold":
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
    agent = loop_settings(root).get("agent", "claude")
    if agent not in {"claude", "codex"}:
        raise Refused(f"Agent must be claude or codex, not {agent!r}",
                      "set `Agent: claude` or `Agent: codex` in the loop section of AGENTS.md")
    return {"move": "ready", "bar": bar, "bar_files": bar_files,
            "contract": spec.done_when, "intent": spec.intent, "approach": spec.approach,
            "files": spec.files, "command": spec.command,
            "kind": spec.kind, "keep": keep_command,
            "keep_limit": settings.get("keep limit", "15"),
            "check_seconds": check_times(keep_output + "\n" + output),
            **kind_record,
            "test": loop_settings(root).get("test", ""),
            "prepare": loop_settings(root).get("prepare", ""),
            "quality": loop_settings(root).get("quality", []),
            "standards": loop_settings(root).get("standards", ""),
            "idle_limit": loop_settings(root).get("idle limit", "10"),
            "waiting_limit": loop_settings(root).get("waiting limit", "3"),
            "agent": agent,
            "stays": list(spec.stays),
            "research": list(spec.research),
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
                        bar_hash_at(root, head, ready["files"],
                                    ready.get("bar_files", ready["files"]))
                        != ready["bar"]):
        raise Refused("the judge bar changed after the piece became ready",
                      "move the piece back to shaping and run the ready gate again")


def claim_stale_research(ready: dict) -> list[str]:
    """Name findings that are more than 30 days old at claim time."""
    return stale_findings(ready.get("research", []))


def judge(folder: Path, ready: dict) -> tuple[bool, str]:
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
    kind_code, kind_output = _kind_attempt_judge(folder, ready)
    if kind_code >= 0:
        code, output = kind_code, kind_output
    else:
        code, output = run_judge(folder, ready["command"], protected_paths=protected_paths)
    if kind_code < 0 and skipped_tests(output):
        return False, f"the judge reported skipped tests:\n{output.strip()[-1500:]}"
    if code != 0:
        return False, output
    if ready.get("keep"):
        keep_timeout = keep_limit_seconds({"keep limit": ready.get("keep_limit", "15")})
        kcode, koutput = run_keep(folder, ready["keep"], timeout=keep_timeout,
                                  protected_paths=protected_paths)
        if skipped_tests(koutput):
            return False, f"the keep check reported skipped tests:\n{koutput.strip()[-1500:]}"
        if kcode != 0:
            retry_code, retry_output = run_keep(
                folder, ready["keep"], timeout=keep_timeout,
                protected_paths=protected_paths)
            if retry_code == 0 and not skipped_tests(retry_output):
                failed_names = failing_test_names(koutput)
                names = ", ".join(failed_names) if failed_names else "see failed Keep output"
                output += (f"\n\nKeep: {ready['keep']}\nExit: {kcode}\n{koutput.strip()}"
                           f"\n\nKeep retry: {ready['keep']}\nExit: {retry_code}\n"
                           f"{retry_output.strip()}\nCause: keep-flaky\n"
                           f"Failing Keep tests: {names}")
            elif ready["files"] and keep_passes_without_judge(folder, ready):
                return False, (f"{BAR_WRONG}. Keep retry also failed:\n"
                               f"{retry_output}\nWithout judge files it passes:\n{koutput}")
            else:
                failure = f"the judge passes, but the keep check now fails:\n{koutput}"
                if kind_code >= 0:
                    failure += f"\n\n{output}"
                return False, failure
        else:
            output += f"\n\nKeep: {ready['keep']}\nExit: {kcode}\n{koutput.strip()}"
    quality_results = []
    for command in ready.get("quality", []):
        qcode, qoutput = run_judge(folder, command, protected_paths=protected_paths)
        quality_results.append(f"Quality: {command}\nExit: {qcode}\n{qoutput.strip()}")
        if qcode != 0:
            failure = "a Quality command failed:\n" + "\n\n".join(quality_results)
            if kind_code >= 0:
                failure += f"\n\n{output}"
            return False, failure
    if quality_results:
        output += "\n\n" + "\n\n".join(quality_results)
    return True, output


def failing_test_names(output: str) -> list[str]:
    """Extract reported failing test names from common test runner output."""
    names = []
    for line in output.splitlines():
        match = re.search(r"\b(?:FAILED?|ERROR)\s*:?\s*(.+)$|\bnot ok\s+\d+\s+-\s*(.+)$",
                          line, re.IGNORECASE)
        if match:
            name = (match.group(1) or match.group(2)).strip()
            if name and name not in names:
                names.append(name)
    return names


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
        code, _ = run_keep(folder, ready["keep"],
                           timeout=keep_limit_seconds(
                               {"keep limit": ready.get("keep_limit", "15")}),
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

def _cause(name: str, reason: str, reason_type: str) -> str:
    text = reason.lower()
    if name == "reject":
        cause = "person-rejected"
    elif name == "pull-back":
        cause = "person-request"
    elif "prepare" in text:
        cause = "prepare-failed"
    elif "rate limit" in text or "usage limit" in text:
        cause = "usage-limit"
    elif "idle" in text:
        cause = "idle"
    elif "stale" in text or "main changed" in text:
        cause = "stale-after-main"
    elif "importerror" in text or "module not found" in text or "import error" in text:
        cause = "import-error"
    elif "flaky" in text:
        cause = "keep-flaky"
    elif "conflict" in text or "does not merge" in text:
        cause = "conflict"
    elif "judge gap" in text:
        cause = "judge-gap"
    elif reason_type == "stopped" or "person asked the run to stop" in text:
        cause = "stopped"
    elif "bar" in text or reason_type == "bar-wrong":
        cause = "bar-wrong"
    elif "quality" in text:
        cause = "quality-failed"
    elif "judge" in text:
        cause = "judge-failed"
    elif "dirty" in text or "uncommitted" in text:
        cause = "dirty-worktree"
    elif reason_type == "builder-failed":
        cause = "builder-failed"
    else:
        cause = "other"
    return cause if cause in CAUSES else "other"


def _kit_version() -> str:
    manifest = Path(__file__).resolve().parents[1] / ".claude-plugin" / "plugin.json"
    try:
        return str(json.loads(manifest.read_text()).get("version") or "unknown")
    except (OSError, ValueError, AttributeError):
        return "unknown"


def move(gh: GitHub, root: Path, n: int, to: str, reason: str = "",
         reason_type: str = "", folder: Optional[Path] = None, pr: str = "",
         cause: str = "", attempts: Optional[int] = None,
         seconds: Optional[float] = None) -> str:
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
        ready = check_frozen(issue, comments)
        check_claim_bar(root, n, ready)
        stale = claim_stale_research(ready)
        if stale:
            record["stale_research"] = stale
            note += f" Research findings {', '.join(stale)} are possibly stale; check them before building."
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
        record["check_seconds"] = check_times(output)
        record["commit"] = rev(folder, "HEAD")
        record["attempts"] = max(0, int(attempts or 0))
        record["seconds"] = round(max(0.0, float(seconds or 0)), 3)
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
    if name in ("give-back", "reject", "pull-back"):
        previous_submit = last_record(comments, "submit") or {}
        attempt_count = attempts if attempts is not None else previous_submit.get("attempts", 0)
        elapsed = seconds if seconds is not None else previous_submit.get("seconds", 0)
        record.update({
            "cause": cause if cause in CAUSES else _cause(name, reason, reason_type),
            "attempts": max(0, int(attempt_count)),
            "seconds": round(max(0.0, float(elapsed)), 3),
            "kit": _kit_version(),
            "date": datetime.now(timezone.utc).date().isoformat(),
        })

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
                          protected_paths: Optional[list[str]] = None,
                          prepare_command: Optional[str] = None,
                          proposed_quality: str = "") -> tuple[bool, str]:
    """Run Test, then one Quality command in its own prepared copy of main."""
    tmp = Path(tempfile.mkdtemp(prefix="loop-doctor-quality-"))
    folder = tmp / "main"
    try:
        sh(["git", "worktree", "add", "--detach", "--quiet", str(folder), main], root)
        if proposed_quality:
            apply_proposed_quality(folder / "AGENTS.md", proposed_quality,
                                   prepare_command, test_command)
            settings = loop_settings(folder)
            command = settings.get("quality", [command])[-1]
            test_command = settings.get("test", "")
        ok, output = prepare(folder, command=prepare_command,
                             protected_paths=protected_paths)
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


def doctor(gh: GitHub, root: Path, extra_quality: Optional[list[str]] = None,
           proposed_prepare: Optional[str] = None,
           proposed_test: Optional[str] = None,
           walk_away: bool = False,
           agent: Optional[str] = None) -> list[tuple[bool, str, str]]:
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
        try:
            keep_timeout = keep_limit_seconds(settings)
        except Refused as refusal:
            add(False, "AGENTS.md has a valid Keep limit", refusal.next_step)
            return checks
        if not add("test" in settings, "AGENTS.md on main names the Test command",
                   "merge setup's AGENTS.md section, with a 'Test command:' line"):
            return checks
        if "prepare" in settings:
            ok, output = prepare(folder)
            if not add(ok, f"Prepare passes on a fresh copy of main ({settings['prepare']})",
                       "fix the Prepare command:\n" + output.strip()[-800:]):
                return checks
        keep_command = settings.get("keep", settings["test"])
        if keep_command == settings["test"]:
            code, output = run_keep(folder, keep_command, timeout=keep_timeout)
            check_name = f"the tests pass on a fresh copy of main ({settings['test']})"
        else:
            code, output = run_judge(folder, settings["test"])
            add(code == 0, f"the tests pass on a fresh copy of main ({settings['test']})",
                "fix the Test command or the environment, or add a Prepare command:\n"
                + output.strip()[-800:])
            code, output = run_keep(folder, keep_command, timeout=keep_timeout)
            check_name = f"Keep passes on a fresh copy of main ({keep_command})"
        duration = next((line for line in output.splitlines()
                         if line.startswith("Keep took: ")), "")
        if duration:
            check_name += f" ({duration.removeprefix('Keep took: ')})"
        if code == 124:
            fix = ("increase Keep limit in AGENTS.md or make the Keep command finish sooner:\n"
                   + output.strip()[-800:])
        else:
            fix = ("fix the Keep command or the environment, or add a Prepare command:\n"
                   + output.strip()[-800:])
        add(code == 0, check_name, fix)
        for command in settings.get("quality", []):
            qok, qoutput = quality_on_fresh_main(
                root, main, command, settings["test"],
                prepare_command=settings.get("prepare", ""))
            if "no changed Python functions found" in qoutput:
                add(True, f"Quality mutation check could not be exercised on main ({command})", "")
            else:
                add(qok, f"Quality command passes on a fresh copy of main ({command})",
                    f"Quality check failed: {command}\n{qoutput.strip()[-800:]}")
        for command in extra_quality or []:
            qprepare = (proposed_prepare if proposed_prepare is not None
                        else settings.get("prepare", ""))
            qtest = proposed_test if proposed_test is not None else settings["test"]
            qok, qoutput = quality_on_fresh_main(
                root, main, command, qtest, prepare_command=qprepare,
                proposed_quality=command)
            if "no changed Python functions found" in qoutput:
                add(True, f"Quality mutation check could not be exercised on main ({command})", "")
            else:
                add(qok, f"Proposed Quality command passes on a fresh copy of main ({command})",
                    f"Quality check failed: {command}\n{qoutput.strip()[-800:]}")
    finally:
        sh(["git", "worktree", "remove", "--force", str(folder)], root, check=False)
        shutil.rmtree(tmp, ignore_errors=True)
    if walk_away and all(ok for ok, _, _ in checks):
        import walkaway
        checks.extend(walkaway.preflight(gh, root, baseline_checked=True, agent=agent))
    return checks


def status(gh: GitHub, root: Optional[Path] = None) -> str:
    lines = []
    for s in STATES[:4]:
        items = gh.issues_with_label(STATE_PREFIX + s)
        lines.append(f"{s}: " + (", ".join(
            f"{i['number']}{' (needs you)' if NEEDS_YOU in i['labels'] else ''} {i['title']}"
            for i in items) or "none"))
    if root is not None:
        import walkaway
        heartbeat = walkaway.heartbeat_status(root)
        if heartbeat:
            lines.append(heartbeat)
    return "\n".join(lines)


def report(gh: GitHub) -> str:
    """Count hand-backs by type and cause, and report first-attempt outcomes."""
    counts: dict[str, int] = {}
    cause_counts: dict[str, int] = {}
    pieces: dict[int, list[str]] = {}
    seen: dict[int, set[str]] = {}
    started, first_pass = set(), set()
    for state in STATES:
        for issue in gh.issues_with_label(STATE_PREFIX + state, closed_too=True):
            n = issue["number"]
            if n in seen:
                continue
            seen[n] = set()
            issue_records = records(gh.comments(n))
            claimed = False
            first_build_outcome = False
            for record in issue_records:
                if record.get("move") == "claim":
                    started.add(n)
                    claimed = True
                elif claimed and not first_build_outcome and record.get("move") in (
                        "give-back", "submit"):
                    first_build_outcome = True
                    if record.get("move") == "submit" and record.get("attempts") == 1:
                        first_pass.add(n)
                kind = record.get("type")
                if (record.get("move") not in NEEDS_TYPE and record.get("move") != "judge-gap") or \
                        kind not in REASON_TYPES:
                    continue
                key = f"{kind}: {record.get('reason', '')}"
                counts[kind] = counts.get(kind, 0) + 1
                cause_key = f"{kind} / {record.get('cause', 'other')}"
                cause_counts[cause_key] = cause_counts.get(cause_key, 0) + 1
                pieces.setdefault(n, []).append(key)
    lines = [f"{kind}: {counts.get(kind, 0)}" for kind in REASON_TYPES]
    lines.append("by type and cause:")
    lines += [f"{key}: {value}" for key, value in sorted(cause_counts.items())]
    denominator = len(started)
    percentage = round(len(first_pass) * 100 / denominator) if denominator else 0
    lines.append(f"pieces started: {denominator}")
    lines.append(f"passed on the first attempt: {len(first_pass)} / {denominator} ({percentage}%)")
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
    d.add_argument("--prepare-command",
                   help="use this proposed Prepare command for doctor dry-runs")
    d.add_argument("--test-command",
                   help="use this proposed Test command for doctor dry-runs")
    d.add_argument("--walk-away", action="store_true",
                   help="also check the active sandbox and unattended-run prerequisites")
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
            print(status(gh, root))
        elif args.cmd == "doctor":
            checks = doctor(gh, root, args.quality_command,
                            args.prepare_command, args.test_command, args.walk_away)
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
