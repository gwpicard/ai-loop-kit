#!/usr/bin/env python3
"""Review sessions, verdicts and finding filters for the run."""
from __future__ import annotations

import json
import os
import re
import selectors
import signal
import subprocess
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

import agents
import gate
import sandbox
from loopkit import (CHECK_FILES, Refused, main_ref, prepare,
                     record_prepare_outputs, rev, sh, untracked_paths)
from procs import AttemptIdle, _untrack_process, track_process
from run import commit_leftovers, idle_limit_seconds

KIT = Path(__file__).resolve().parent.parent
ATTEMPT_TIMEOUT = 40 * 60
BASELINE_SMELLS = (
    "Mysterious Name", "Duplicated Code", "Feature Envy", "Data Clumps",
    "Primitive Obsession", "Repeated Switches", "Shotgun Surgery", "Divergent Change",
    "Speculative Generality", "Message Chains", "Middle Man", "Refused Bequest",
)


def _diff_hunks(diff: str) -> dict[str, list[tuple[int, int]]]:
    hunks: dict[str, list[tuple[int, int]]] = {}
    path = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            hunks.setdefault(path, [])
        elif path and line.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                start, count = int(match.group(1)), int(match.group(2) or "1")
                hunks[path].append((start, start + max(count, 1) - 1))
    return hunks


def _valid_hunk(citation: str, hunks: dict[str, list[tuple[int, int]]]) -> bool:
    match = re.search(r"([^\s|]+):(\d+)(?:-(\d+))?", citation)
    if not match:
        return False
    path, start = match.group(1), int(match.group(2))
    end = int(match.group(3) or start)
    return any(start <= hi and end >= lo for lo, hi in hunks.get(path, []))


def _last_verdict(output: str, reviewer: str) -> dict:
    matches = re.findall(r"<verdict>\s*(.*?)\s*</verdict>", output, flags=re.I | re.S)
    if not matches:
        raise ValueError("missing <verdict> block")
    payload = matches[-1].strip()
    fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", payload, flags=re.I)
    if fenced:
        payload = fenced.group(1).strip()
    try:
        data = json.loads(payload)
    except ValueError as error:
        raise ValueError(f"bad verdict JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValueError("verdict must be a JSON object")
    if reviewer == "standards":
        if not isinstance(data.get("findings"), list) or not isinstance(data.get("follow_ups"), list) \
                or not isinstance(data.get("changes"), str):
            raise ValueError("standards verdict needs findings, follow_ups and changes")
        for finding in data["findings"]:
            if not isinstance(finding, dict) or any(not isinstance(finding.get(key), str)
                                                    for key in ("rule", "hunk", "finding")):
                raise ValueError("each standards finding needs rule, hunk and finding strings")
        if any(not isinstance(item, str) for item in data["follow_ups"]):
            raise ValueError("standards follow_ups must be strings")
    elif reviewer == "contract":
        if not isinstance(data.get("findings"), list):
            raise ValueError("contract verdict needs a findings list")
        for finding in data["findings"]:
            if not isinstance(finding, dict) or any(not isinstance(finding.get(key), str)
                                                    for key in ("citation", "hunk", "finding")):
                raise ValueError("each contract finding needs citation, hunk and finding strings")
    elif reviewer == "judge-writer":
        if not isinstance(data.get("judge_files"), list) or not all(
                isinstance(item, str) for item in data["judge_files"]):
            raise ValueError("judge-writer verdict needs judge_files")
        if data.get("tests_per_id") is not True or not isinstance(data.get("notes"), str):
            raise ValueError("judge-writer verdict needs tests_per_id true and notes")
    return data


def _logged_verdict(logfile: Path, reviewer: str) -> dict:
    output = logfile.read_text(errors="replace") if logfile.exists() else ""
    try:
        return _last_verdict(output, reviewer)
    except ValueError as error:
        with logfile.open("a") as out:
            out.write(f"\nInvalid {reviewer} verdict: {error}\nRaw tail:\n{output[-2000:]}\n")
        raise Refused(f"{reviewer} returned an invalid verdict: {error}",
                      f"read {logfile} and correct the review output")


def parse_standards_findings(output: str, standards: str, diff: str) -> list[str]:
    """Keep only findings that cite a rule or smell and a changed hunk."""
    hunks = _diff_hunks(diff)
    allowed = {name.strip().casefold() for name in BASELINE_SMELLS}
    allowed.update(("unrelated special-case branches", "pass-through wrappers",
                    "logic in the owning layer", "reuse existing helpers"))
    standard_rules = {line.strip().casefold() for line in standards.splitlines()
                      if line.strip()}
    verdict = _last_verdict(output, "standards")
    findings = []
    for finding in verdict["findings"]:
        rule, hunk, description = (finding["rule"].strip(), finding["hunk"].strip(),
                                   finding["finding"].strip())
        if not rule or rule.casefold() not in allowed and rule.casefold() not in standard_rules:
            continue
        if _valid_hunk(hunk, hunks):
            findings.append(f"{rule} at {hunk}: {description}")
    return findings


def parse_contract_findings(output: str, body: str, diff: str) -> list[str]:
    """Keep contract findings that cite an approved line and a changed hunk."""
    data = _last_verdict(output, "contract")
    ids = set(re.findall(r"\b(D\d+)\b", body))
    out_of_scope = []
    in_scope = False
    for line in body.splitlines():
        if line.strip().lower().startswith("out of scope:"):
            in_scope = True
        elif line.startswith("## "):
            in_scope = False
        elif in_scope and re.match(r"^\s*[-*]\s+\S", line):
            out_of_scope.append(line.strip()[1:].strip())
    findings = []
    hunks = _diff_hunks(diff)
    for finding in data.get("findings", []):
        citation = str(finding.get("citation", ""))
        hunk = str(finding.get("hunk", ""))
        detail = str(finding.get("finding", "")).strip()
        cited_id = re.search(r"\b(D\d+)\b", citation)
        cites_scope = any(item and item in citation for item in out_of_scope)
        if not detail or not _valid_hunk(hunk, hunks):
            continue
        if not (cited_id and cited_id.group(1) in ids) and not cites_scope:
            continue
        findings.append(f"{citation} at {hunk}: {detail}")
    return findings


def _review_prompt(name: str, values: dict[str, str]) -> str:
    prompt = (KIT / "briefs" / name).read_text()
    for key, value in values.items():
        prompt = prompt.replace("{{" + key + "}}", value)
    return prompt


def _pump_session(proc: subprocess.Popen, out, idle_seconds: int,
                  hard_seconds: int = ATTEMPT_TIMEOUT,
                  activity_path: Optional[Path] = None,
                  result_event: Optional[dict] = None,
                  backend: str = "claude",
                  clock: Optional[Callable[[], float]] = None) -> str:
    """Copy output to a log and stop a silent or overlong process group."""
    now_seconds = clock if clock is not None else time.monotonic
    assert proc.stdout is not None
    stream = proc.stdout
    os.set_blocking(stream.fileno(), False)
    selector = selectors.DefaultSelector()
    selector.register(stream, selectors.EVENT_READ)
    started = last_output = now_seconds()
    last_stamp = _folder_activity_stamp(activity_path) if activity_path else 0.0
    next_activity_check = started + 2
    pending = ""
    eof = False
    reason = ""
    parent_exit_deadline: Optional[float] = None
    orphaned_child = False
    while not eof or proc.poll() is None:
        now = now_seconds()
        if proc.poll() is not None and not eof:
            if parent_exit_deadline is None:
                parent_exit_deadline = now + 3
            elif now >= parent_exit_deadline:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                orphaned_child = True
                break
        if activity_path and now >= next_activity_check:
            stamp = _folder_activity_stamp(activity_path)
            next_activity_check = now + 2
            if stamp > last_stamp:
                last_stamp = stamp
                last_output = now
        if proc.poll() is None and not reason:
            if now - started >= hard_seconds:
                reason = "hard"
            elif now - last_output >= idle_seconds:
                reason = "idle"
            if reason:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        timeout = 0.1
        if proc.poll() is None and not reason:
            timeout = min(timeout, max(0.0, min(hard_seconds - (now - started),
                                                idle_seconds - (now - last_output))))
        elif parent_exit_deadline is not None and not eof:
            timeout = min(timeout, max(0.0, parent_exit_deadline - now))
        events = selector.select(timeout)
        for key, _ in events:
            try:
                chunk = os.read(key.fd, 4096)
            except BlockingIOError:
                continue
            if not chunk:
                eof = True
                selector.unregister(stream)
                continue
            pending += chunk.decode(errors="replace")
            lines = pending.split("\n")
            pending = lines.pop()
            for line in lines:
                if result_event is not None:
                    try:
                        event = json.loads(line)
                    except ValueError:
                        event = None
                    if isinstance(event, dict) and event.get("type") == "result":
                        result_event.update(event)
                out.write(agents.log_line(line, backend))
            out.flush()
            last_output = now_seconds()
    if pending:
        out.write(agents.log_line(pending, backend))
    proc.wait()
    _untrack_process(proc)
    selector.close()
    stream.close()
    if reason:
        out.write("\nAttempt stopped after idle limit with no output.\n" if reason == "idle"
                  else f"\nThe attempt ran past {hard_seconds // 60} minutes and was stopped.\n")
    if orphaned_child:
        out.write("\nStopped a child process that kept the session pipe open after its parent exited.\n")
    return reason


def _folder_activity_stamp(folder: Optional[Path]) -> float:
    """Newest useful modification time under the build folder."""
    if folder is None:
        return 0.0
    newest = folder.stat().st_mtime if folder.exists() else 0.0
    for current, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in {
            ".git", ".venv", "node_modules", "dist", "build", "__pycache__"}]
        for name in (*dirs, *files):
            try:
                newest = max(newest, (Path(current) / name).stat().st_mtime)
            except OSError:
                continue
    return newest


def _write_claude_log_line(out, line: str) -> None:
    """Keep stream-json transport out of the human-readable session log."""
    out.write(agents.log_line(line, "claude"))


def _review_session(folder: Path, prompt: str, logfile: Path, disallowed: list[str],
                    idle_seconds: int, protected_paths: Optional[list[str]] = None,
                    walk_away: bool = False, domains: Optional[list[str]] = None,
                    backend: str = "claude") -> str:
    for retry in range(2 if walk_away else 1):
        result_event = {}
        with logfile.open("w" if retry == 0 else "a") as out:
            proc = agents.start_session(
                backend, prompt, folder, role="reviewer", disallowed=disallowed,
                protected_paths=protected_paths, walk_away=walk_away, domains=domains)
            track_process(proc)
            with (logfile.parent / "reviewer-processes").open("a") as evidence:
                evidence.write(f"{proc.pid}\n")
            status = _pump_session(proc, out, idle_seconds, activity_path=folder,
                                   result_event=result_event, backend=backend)
        if not walk_away or not sandbox.usage_limit_event(result_event):
            return status
        if retry:
            return "usage-limit"
        wait_seconds = sandbox.reset_wait_seconds(result_event)
        with logfile.open("a") as out:
            out.write(f"\nUsage limit; waiting {wait_seconds} seconds before one retry.\n")
        time.sleep(wait_seconds)
    return "usage-limit"


def _cleanup_review_worktrees(root: Path, n: int, k: int) -> None:
    prefixes = (f"review/standards-{n}-{k}-", f"review/contract-{n}-{k}-")
    output = sh(["git", "worktree", "list", "--porcelain"], root).stdout.splitlines()
    path = ""
    to_remove = []
    for line in output:
        if line.startswith("worktree "):
            path = line[9:]
        elif line.startswith("branch refs/heads/"):
            branch = line[len("branch refs/heads/"):]
            if branch.startswith(prefixes):
                to_remove.append((path, branch))
    for path, branch in to_remove:
        sh(["git", "worktree", "remove", "--force", path], root, check=False)
        sh(["git", "branch", "-D", branch], root, check=False)


def review_piece(root: Path, folder: Path, n: int, k: int, issue: dict,
                 ready: dict, walk_away: bool = False,
                 domains: Optional[list[str]] = None) -> dict:
    try:
        return _review_piece(root, folder, n, k, issue, ready, walk_away, domains)
    finally:
        _cleanup_review_worktrees(root, n, k)


def contract_research(body: str) -> str:
    """Return the approved Research section for the contract reviewer."""
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower() == "## research":
            section = [line]
            for rest in lines[index + 1:]:
                if rest.startswith("## "):
                    break
                section.append(rest)
            return "\n".join(section)
    return "No outside findings."


def _review_piece(root: Path, folder: Path, n: int, k: int, issue: dict,
                  ready: dict, walk_away: bool = False,
                  domains: Optional[list[str]] = None) -> dict:
    """Run one standards review and one contract review in fresh sessions."""
    main = main_ref(folder)
    diff = sh(["git", "diff", "--no-ext-diff", "--no-color", f"{main}...HEAD"], folder).stdout
    standards_path = ready.get("standards", "")
    standards = (folder / standards_path).read_text(errors="replace") if standards_path else ""
    standards_context = standards or "No project standards file is named. Use the built-in baseline."
    standards_folder = folder.parent / f"review-standards-{n}-{k}-{uuid.uuid4().hex[:8]}"
    standards_branch = f"review/standards-{n}-{k}-{uuid.uuid4().hex[:8]}"
    judged = rev(folder, "HEAD")
    sh(["git", "worktree", "add", "--quiet", "-b", standards_branch,
        str(standards_folder), judged], root)
    before = untracked_paths(standards_folder)
    before_dirs = {child.name for child in standards_folder.iterdir() if child.is_dir()}
    prepared, prepare_output = prepare(standards_folder, ready.get("prepare", ""),
                                      ready.get("protected_paths", []))
    if not prepared:
        raise Refused(f"Prepare failed in the standards review folder:\n{prepare_output[-1200:]}")
    record_prepare_outputs(standards_folder, before, before_dirs)
    logs = root / ".loop" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    standards_log = logs / f"piece-{n}-standards-review.log"
    denied = list(ready.get("files", [])) + ["tests/**", "**/test_*", "**/*_test.py",
               "**/*.test.*", "**/*.spec.*", "**/conftest.py"]
    denied += CHECK_FILES
    denied += ready.get("protected_paths", [])
    standards_status = _review_session(standards_folder, _review_prompt("standards-reviewer.md", {
        "STANDARDS": standards_context, "DIFF": diff}), standards_log, denied,
        idle_limit_seconds(folder, ready.get("idle_limit")), ready.get("protected_paths", []),
        walk_away, domains, ready.get("agent", "claude"))
    if standards_status == "idle":
        raise AttemptIdle(f"standards reviewer idle for {idle_limit_seconds(folder, ready.get('idle_limit')) // 60} minutes; "
                          f"see {standards_log}")
    commit_leftovers(standards_folder, n, k)
    standard_output = standards_log.read_text(errors="replace")
    standards_verdict = _logged_verdict(standards_log, "standards")
    standard_findings = parse_standards_findings(standard_output, standards_context, diff)
    standard_head = rev(standards_folder, "HEAD")
    reviewer_note = "Standards review ran once."
    if standard_head != judged:
        passed, output = gate.judge(standards_folder, ready)
        if passed:
            sh(["git", "merge", "--ff-only", "--quiet", standards_branch], folder)
            passed, output = gate.judge(folder, ready)
        if passed:
            commits = sh(["git", "log", "--oneline", f"{judged}..HEAD"], folder).stdout.strip()
            reviewer_note += " Reviewer fixes kept:\n" + (commits or "none")
        else:
            reviewer_note += " Reviewer fixes were dropped because a submit check failed:\n" + output[-1200:]
    follow_ups = standards_verdict["follow_ups"]

    final_diff = sh(["git", "diff", "--no-ext-diff", "--no-color", f"{main}...HEAD"], folder).stdout
    contract_parts = []
    body = issue["body"] or ""
    for section in ("Intent", "Approach", "Contract", "Done when"):
        lines = body.splitlines()
        for index, line in enumerate(lines):
            if line.strip().lower() == f"## {section}".lower():
                part = [line]
                for rest in lines[index + 1:]:
                    if rest.startswith("## "):
                        break
                    part.append(rest)
                contract_parts.extend(part)
                break
    contract = "\n".join(contract_parts)
    contract_folder = folder.parent / f"review-contract-{n}-{k}-{uuid.uuid4().hex[:8]}"
    contract_branch = f"review/contract-{n}-{k}-{uuid.uuid4().hex[:8]}"
    sh(["git", "worktree", "add", "--quiet", "-b", contract_branch,
        str(contract_folder), rev(folder, "HEAD")], root)
    before = untracked_paths(contract_folder)
    before_dirs = {child.name for child in contract_folder.iterdir() if child.is_dir()}
    prepared, prepare_output = prepare(contract_folder, ready.get("prepare", ""),
                                       ready.get("protected_paths", []))
    if not prepared:
        raise Refused(f"Prepare failed in the contract review folder:\n{prepare_output[-1200:]}")
    record_prepare_outputs(contract_folder, before, before_dirs)
    contract_log = logs / f"piece-{n}-contract-review.log"
    contract_status = _review_session(contract_folder, _review_prompt("contract-reviewer.md", {
        "CONTRACT": contract, "RESEARCH": contract_research(body),
        "DIFF": final_diff}), contract_log, denied,
        idle_limit_seconds(folder, ready.get("idle_limit")), ready.get("protected_paths", []),
        walk_away, domains, ready.get("agent", "claude"))
    if contract_status == "idle":
        raise AttemptIdle(f"contract reviewer idle for {idle_limit_seconds(folder, ready.get('idle_limit')) // 60} minutes; "
                          f"see {contract_log}")
    contract_output = contract_log.read_text(errors="replace")
    _logged_verdict(contract_log, "contract")
    contract_findings = parse_contract_findings(contract_output, issue["body"], final_diff)
    # Contract reviewers are read-only. Their branch is never merged.
    return {"standards_findings": standard_findings,
            "contract_findings": contract_findings,
            "follow_ups": follow_ups, "reviewer_note": reviewer_note}


