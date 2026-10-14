#!/usr/bin/env python3
"""The run: build each ready piece, let the gate judge it, open a pull request.

    run.py              build every ready piece, oldest first
    run.py 12 14        build these pieces only
    run.py --attempts 2

Each attempt is a fresh `claude -p` session in the piece's own worktree. The
gate runs the judge after every attempt. A pass opens a pull request for the
person to merge. Three failures send the piece back to shaping with the reason.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import selectors
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402
from loopkit import (CHECK_FILES, STATE_PREFIX, GitHub, Refused, branch_name,  # noqa: E402
                     changed_check_settings, command_env,
                     last_record, loop_settings, main_ref, prepare, record_prepare_outputs, record_text, rev,
                     records, repo_root, sh, untracked_paths)

KIT = Path(__file__).resolve().parent.parent
ATTEMPT_TIMEOUT = 40 * 60
DEFAULT_IDLE_LIMIT = 10 * 60


class AttemptIdle(Exception):
    pass


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def lock_path(root: Path) -> Path:
    return root / ".loop" / "run.lock"


def process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def acquire_lock(root: Path) -> Path:
    """Create the run lock, taking over only when its recorded process is dead."""
    path = lock_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps({"pid": os.getpid(), "started_at": time.time()}) + "\n"
    for _ in range(2):
        try:
            with path.open("x") as f:
                f.write(data)
            return path
        except FileExistsError:
            try:
                current = json.loads(path.read_text())
                pid = int(current["pid"])
            except (ValueError, KeyError, TypeError, OSError):
                pid = 0
            if pid and process_alive(pid):
                raise Refused(f"another run is live (pid {pid})", "wait for it to finish")
            path.unlink(missing_ok=True)
    raise Refused("could not take the run lock", "check .loop/run.lock and try again")


def release_lock(path: Path) -> None:
    path.unlink(missing_ok=True)


def recover_building(gh: GitHub, root: Path) -> list[str]:
    """Return pieces left in building to shaping after a dead run."""
    recovered = []
    for issue in gh.issues_with_label(STATE_PREFIX + "building"):
        note = "the previous run ended while this piece was building"
        recovered.append(f"piece {issue['number']}: " + gate.move(
            gh, root, issue["number"], "shaping", reason=note,
            reason_type="environment"))
    return recovered


def waiting_limit_note(gh: GitHub, root: Path) -> str:
    value = loop_settings(root).get("waiting limit", "3")
    try:
        limit = max(1, int(value))
    except ValueError:
        limit = 3
    waiting = len(gh.issues_with_label(STATE_PREFIX + "approval"))
    if waiting >= limit:
        return (f"Run paused: {waiting} pieces wait in approval (limit {limit}). "
                "next: review or merge a pull request, then run again.")
    return ""


def idle_limit_seconds(folder: Path) -> int:
    value = loop_settings(folder).get("idle limit", "10")
    try:
        return max(1, int(value)) * 60
    except ValueError:
        return DEFAULT_IDLE_LIMIT


def stop_path(root: Path) -> Path:
    return root / ".loop" / "stop"


def stop_requested(root: Path) -> bool:
    return stop_path(root).is_file()


def clear_stop(root: Path) -> None:
    stop_path(root).unlink(missing_ok=True)


def came_back_reason(comments: list[str]) -> str:
    """Every reason the piece came back for after a build, oldest first."""
    built, reasons = False, []
    for r in records(comments):
        if r.get("move") == "claim":
            built = True
        elif built and r.get("move") in ("reject", "pull-back", "give-back"):
            reasons.append(f"- {r.get('reason', '')}")
    return "\n".join(reasons)


def dependent_files(folder: Path, approach: str, changed: list[str],
                    exclude: Optional[list[str]] = None) -> list[str]:
    """List project source files that import a path or module named by the piece."""
    names = set()
    for path in changed:
        names.add(Path(path).stem)
    paths = re.findall(r"(?<![\w.-])([\w./-]+\.(?:py|js|jsx|ts|tsx|mjs|cjs))\b", approach)
    for path in paths:
        names.add(Path(path).stem)
    if not names:
        return []
    ignored = {".git", ".venv", "venv", "node_modules", "dist", "build", ".loop"}
    excluded = set(exclude or [])
    found = []
    for path in folder.rglob("*"):
        relative = path.relative_to(folder).as_posix()
        if not path.is_file() or ignored.intersection(path.parts) or relative in excluded:
            continue
        if any(part.lower() in {"test", "tests", "__tests__"} for part in path.parts) or \
                path.name.startswith("test_"):
            continue
        if path.suffix not in {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
            continue
        try:
            source = path.read_text(errors="replace")
        except OSError:
            continue
        depends = False
        if path.suffix == ".py":
            try:
                tree = ast.parse(source)
                imported = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported.update(alias.name.split(".")[0] for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported.add(node.module.split(".")[0])
                depends = bool(imported & names)
            except SyntaxError:
                depends = any(re.search(rf"\b{re.escape(name)}\b", source) for name in names)
        else:
            depends = bool(re.search(r"\b(?:import|require)\b", source)) and any(
                re.search(rf"(?:[/.'\"]|\b){re.escape(name)}(?:[/.'\"]|\b)", source)
                for name in names)
        if depends:
            found.append(path.relative_to(folder).as_posix())
    return sorted(set(found))


def brief(n: int, body: str, ready: dict, last_failure: str, came_back: str = "",
          folder: Optional[Path] = None) -> str:
    text = (KIT / "briefs" / "builder.md").read_text()
    files = "\n".join(f"- `{f}`" for f in ready["files"]) or "- (none: the command is the judge)"
    earlier = last_failure or "This is the first attempt."
    if came_back:
        earlier = ("This piece was built before and came back for these reasons:\n"
                   f"{came_back}\nThe branch still holds that earlier build. Change it so the "
                   f"reasons no longer apply.\n\n{earlier}")
    for key, value in {"PIECE": str(n), "SPEC": body.strip(),
                       "APPROACH": ready.get("approach", "") or "No approach was supplied.",
                       "COMMAND": ready["command"],
                       "FILES": files,
                       "DEPENDENTS": "\n".join(f"- `{f}`" for f in dependent_files(
                           folder or Path.cwd(), ready.get("approach", ""), [], ready.get("files"))) or "- (none found)",
                       "LAST_FAILURE": earlier}.items():
        text = text.replace("{{" + key + "}}", value)
    return text


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
    allowed = [name.lower() for name in BASELINE_SMELLS]
    allowed += ["unrelated special-case branches", "pass-through wrappers",
                "logic in the owning layer", "reuse existing helpers"]
    verdict = _last_verdict(output, "standards")
    findings = []
    for finding in verdict["findings"]:
        rule, hunk, description = (finding["rule"].strip(), finding["hunk"].strip(),
                                   finding["finding"].strip())
        if not any(rule.lower() == label for label in allowed) and rule.lower() not in standards.lower():
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
                  hard_seconds: int = ATTEMPT_TIMEOUT) -> str:
    """Copy output to a log and stop a silent or overlong process group."""
    assert proc.stdout is not None
    stream = proc.stdout
    os.set_blocking(stream.fileno(), False)
    selector = selectors.DefaultSelector()
    selector.register(stream, selectors.EVENT_READ)
    started = last_output = time.monotonic()
    eof = False
    reason = ""
    while not eof or proc.poll() is None:
        now = time.monotonic()
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
            out.write(chunk.decode(errors="replace"))
            out.flush()
            last_output = time.monotonic()
    proc.wait()
    selector.close()
    stream.close()
    if reason:
        out.write("\nAttempt stopped after idle limit with no output.\n" if reason == "idle"
                  else f"\nThe attempt ran past {hard_seconds // 60} minutes and was stopped.\n")
    return reason


def _review_session(folder: Path, prompt: str, logfile: Path, disallowed: list[str],
                    idle_seconds: int) -> str:
    claude = os.environ.get("LOOP_CLAUDE", "claude")
    guard = f'python3 "{KIT / "hooks" / "guard.py"}"'
    settings = json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash|Edit|Write|MultiEdit|NotebookEdit",
        "hooks": [{"type": "command", "command": guard}]}]}})
    args = [claude, "-p", prompt, "--permission-mode", "acceptEdits", "--allowedTools",
            "Bash", "Read", "Edit", "Write", "MultiEdit", "Glob", "Grep",
            "--settings", settings]
    if disallowed:
        args += ["--disallowedTools", *[f"Edit({path})" for path in disallowed]]
    env = {**command_env(folder), "LOOP_BUILDER": "1", "LOOP_REVIEWER": "1"}
    with logfile.open("w") as out:
        proc = subprocess.Popen(args, cwd=folder, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                env=env, start_new_session=True)
        return _pump_session(proc, out, idle_seconds)


def review_piece(root: Path, folder: Path, n: int, k: int, issue: dict,
                 ready: dict) -> dict:
    """Run one standards review and one contract review in fresh sessions."""
    settings = loop_settings(folder)
    main = main_ref(folder)
    diff = sh(["git", "diff", "--no-ext-diff", "--no-color", f"{main}...HEAD"], folder).stdout
    standards_path = settings.get("standards", "")
    standards = (folder / standards_path).read_text(errors="replace") if standards_path else ""
    standards_context = standards or "No project standards file is named. Use the built-in baseline."
    standards_folder = folder.parent / f"review-standards-{n}-{k}-{uuid.uuid4().hex[:8]}"
    standards_branch = f"review/standards-{n}-{k}-{uuid.uuid4().hex[:8]}"
    judged = rev(folder, "HEAD")
    sh(["git", "worktree", "add", "--quiet", "-b", standards_branch,
        str(standards_folder), judged], root)
    logs = root / ".loop" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    standards_log = logs / f"piece-{n}-standards-review.log"
    denied = list(ready.get("files", [])) + ["tests/**", "**/test_*", "**/*_test.py",
               "**/*.test.*", "**/*.spec.*", "**/conftest.py"]
    denied += CHECK_FILES
    denied += settings.get("protected paths", [])
    standards_status = _review_session(standards_folder, _review_prompt("standards-reviewer.md", {
        "STANDARDS": standards_context, "DIFF": diff}), standards_log, denied,
        idle_limit_seconds(folder))
    if standards_status == "idle":
        raise AttemptIdle(f"standards reviewer idle for {idle_limit_seconds(folder) // 60} minutes; "
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
    contract_log = logs / f"piece-{n}-contract-review.log"
    contract_status = _review_session(contract_folder, _review_prompt("contract-reviewer.md", {
        "CONTRACT": contract, "DIFF": final_diff}), contract_log, denied,
        idle_limit_seconds(folder))
    if contract_status == "idle":
        raise AttemptIdle(f"contract reviewer idle for {idle_limit_seconds(folder) // 60} minutes; "
                          f"see {contract_log}")
    contract_output = contract_log.read_text(errors="replace")
    _logged_verdict(contract_log, "contract")
    contract_findings = parse_contract_findings(contract_output, issue["body"], final_diff)
    # Contract reviewers are read-only. Their branch is never merged.
    return {"standards_findings": standard_findings,
            "contract_findings": contract_findings,
            "follow_ups": follow_ups, "reviewer_note": reviewer_note}


def builder_settings() -> str:
    """Wire the guard into the builder session, whether or not the plugin loads."""
    guard = f'python3 "{KIT / "hooks" / "guard.py"}"'
    return json.dumps({"hooks": {"PreToolUse": [{
        "matcher": "Bash|Edit|Write|MultiEdit|NotebookEdit",
        "hooks": [{"type": "command", "command": guard}]}]}})


def build_once(folder: Path, prompt: str, files: list[str], logfile: Path,
               settings: bool = False, idle_seconds: int = DEFAULT_IDLE_LIMIT) -> str:
    claude = os.environ.get("LOOP_CLAUDE", "claude")
    # Claude Code applies Edit(path) deny rules to every file-editing tool.
    # The gate checks the same files again, since Bash can still write them.
    denied = [f"Edit({f})" for f in files]
    if not settings:
        denied += [f"Edit({p.replace('/*', '/**')})" for p in CHECK_FILES]
    args = [claude, "-p", prompt, "--permission-mode", "acceptEdits",
            "--allowedTools", "Bash", "Read", "Edit", "Write", "MultiEdit", "Glob", "Grep",
            "--settings", builder_settings()]
    if denied:
        args += ["--disallowedTools", *denied]
    env = {**command_env(folder), "LOOP_BUILDER": "1"}
    with logfile.open("w") as out:
        proc = subprocess.Popen(args, cwd=folder, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                env=env, start_new_session=True)
        return _pump_session(proc, out, idle_seconds)


def builder_words(logfile: Path) -> str:
    """The end of what the builder said. It often names why the judge cannot pass."""
    text = logfile.read_text(errors="replace").strip() if logfile.exists() else ""
    lines = [line for line in text.splitlines() if not line.startswith("Permission deny rule")]
    return "\n".join(lines).strip()[-1500:] or "(nothing)"


def commit_leftovers(folder: Path, n: int, k: int) -> None:
    if sh(["git", "status", "--porcelain"], folder).stdout.strip():
        sh(["git", "add", "-A"], folder)
        sh(["git", "commit", "--quiet", "-m", f"Attempt {k} for piece {n}"], folder)


def restore_bar(folder: Path, ready: dict) -> None:
    if ready["files"]:
        sh(["git", "checkout", ready["commit"], "--", *ready["files"]], folder)
        commit_leftovers(folder, 0, 0)


def worktree_home(root: Path) -> Path:
    """Build folders live outside the project, so its own tools (lint, test
    discovery) never see them."""
    base = os.environ.get("LOOP_WORKTREES") or str(
        Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "ai-loop-kit" / "worktrees")
    key = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:8]
    return Path(base) / f"{root.name}-{key}"


def existing_worktree(root: Path, n: int) -> Optional[Path]:
    """The folder git already has checked out on the piece branch, if any."""
    path = None
    for line in sh(["git", "worktree", "list", "--porcelain"], root).stdout.splitlines():
        if line.startswith("worktree "):
            path = Path(line[len("worktree "):])
        elif line == f"branch refs/heads/{branch_name(n)}" and path and path != root:
            return path
    return None


def release_worktree(root: Path, n: int) -> None:
    """Remove a piece's build folder when the piece goes back to shaping, so
    shaping can switch to its branch. Git refuses if the folder holds changes."""
    folder = existing_worktree(root, n)
    if folder:
        sh(["git", "worktree", "remove", str(folder)], root, check=False)


def dirty_folder_reason(folder: Path) -> str:
    dirty = sh(["git", "status", "--porcelain", "--untracked-files=all"], folder).stdout.strip()
    if not dirty:
        return ""
    merge_head = sh(["git", "rev-parse", "--verify", "MERGE_HEAD"], folder, check=False)
    merge_states = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
    if merge_head.returncode == 0 and all(line[:2] in merge_states for line in dirty.splitlines()):
        return ""
    return ("build folder has uncommitted changes the run did not make. "
            "next: inspect the folder and commit or move those changes before running again")


def worktree(root: Path, n: int) -> Path:
    folder = existing_worktree(root, n) or worktree_home(root) / f"piece-{n}"
    if not folder.exists():
        folder.parent.mkdir(parents=True, exist_ok=True)
        res = sh(["git", "worktree", "add", "--quiet", str(folder), branch_name(n)], root, check=False)
        if res.returncode != 0:
            raise Refused(f"cannot open a worktree on {branch_name(n)}: {res.stderr.strip()}",
                          f"switch any checkout of {branch_name(n)} back to main")
    return folder


def check_pushed_branch(root: Path, n: int) -> None:
    """A pushed piece branch is never rewritten. Refuse before the claim if
    GitHub holds commits that the local branch lacks."""
    branch = branch_name(n)
    if sh(["git", "fetch", "--quiet", "origin", branch], root, check=False).returncode != 0:
        return  # not pushed yet
    remote = sh(["git", "rev-parse", "FETCH_HEAD"], root).stdout.strip()
    if sh(["git", "merge-base", "--is-ancestor", remote, branch], root, check=False).returncode:
        raise Refused(f"origin/{branch} holds commits that the local {branch} lacks, and a "
                      "pushed branch is never rewritten",
                      f"run `git switch {branch} && git merge origin/{branch}`, keep the new "
                      "judge files, commit, run gate.py check, then run again")


def build_piece(gh: GitHub, root: Path, n: int, attempts: int) -> str:
    issue = gh.issue(n)
    log(f"piece {n}: {issue['title']}")
    check_pushed_branch(root, n)
    gate.move(gh, root, n, "building")
    try:
        result = build_claimed(gh, root, n, issue, attempts)
    except AttemptIdle as e:
        reason = str(e)
        if gate.state_of(gh.issue(n)) == "building":
            gate.move(gh, root, n, "shaping", reason=reason, reason_type="builder-failed")
        result = f"piece {n}: back to shaping, {reason}"
    except Exception as e:  # never leave a piece in building
        reason = f"the run stopped with an error: {str(e).strip()[:300]}"
        if gate.state_of(gh.issue(n)) == "building":
            gate.move(gh, root, n, "shaping", reason=reason, reason_type="environment")
        result = f"piece {n}: back to shaping, {reason}"
    if gate.state_of(gh.issue(n)) == "shaping":
        release_worktree(root, n)
    return result


def build_claimed(gh: GitHub, root: Path, n: int, issue: dict, attempts: int) -> str:
    ready = last_record(gh.comments(n), "ready")
    assert ready is not None  # the claim move checked it
    folder = worktree(root, n)
    dirty = dirty_folder_reason(folder)
    if dirty:
        status = sh(["git", "status", "--porcelain", "--untracked-files=all"], folder).stdout.strip()
        gh.comment(n, f"**Run:** {dirty}\n\n```\n{status[-1200:]}\n```")
        gate.move(gh, root, n, "shaping", reason=dirty, reason_type="environment")
        return f"piece {n}: back to shaping, {dirty}"

    # Bring the piece up to date with main, so the pull request merges cleanly.
    # A conflict is left for the builder to resolve; the gate's keep check then
    # proves that what main gained still works.
    main = main_ref(root)
    merge_note = ""
    if sh(["git", "merge", "--no-edit", "--quiet", main], folder, check=False).returncode != 0:
        conflicts = sh(["git", "diff", "--name-only", "--diff-filter=U"], folder).stdout.split()
        if not conflicts:
            sh(["git", "merge", "--abort"], folder, check=False)
            reason = f"{branch_name(n)} does not merge with {main}"
            gate.move(gh, root, n, "shaping", reason=reason, reason_type="conflict")
            return f"piece {n}: back to shaping, {reason}"
        log(f"piece {n}: main changed; the builder resolves conflicts in {', '.join(conflicts)}")
        merge_note = ("Main changed since this piece was built. This folder holds an unfinished "
                      f"merge of main, with conflicts in: {', '.join(conflicts)}. First resolve "
                      "them: keep what main added and what this piece adds. Remove every "
                      "conflict marker and commit the merge. Then make the judge pass.")

    before = untracked_paths(folder)
    before_dirs = {child.name for child in folder.iterdir() if child.is_dir()}
    ok, poutput = prepare(folder)
    if not ok:
        reason = "the Prepare command failed in the build folder; run gate.py doctor"
        gh.comment(n, f"**Run:** Prepare failed.\n\n```\n{poutput.strip()[-1500:]}\n```")
        gate.move(gh, root, n, "shaping", reason=reason, reason_type="environment")
        return f"piece {n}: back to shaping, {reason}"
    record_prepare_outputs(folder, before, before_dirs)

    logs = root / ".loop" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    last_failure = merge_note
    came_back = came_back_reason(gh.comments(n))
    for k in range(1, attempts + 1):
        if stop_requested(root):
            reason = "the person asked the run to stop"
            gate.move(gh, root, n, "shaping", reason=reason, reason_type="bar-wrong")
            return f"piece {n}: back to shaping, {reason}"
        logfile = logs / f"piece-{n}-attempt-{k}.log"
        dirty_reason = dirty_folder_reason(folder)
        if dirty_reason:
            status = sh(["git", "status", "--porcelain", "--untracked-files=all"], folder).stdout.strip()
            reason = dirty_reason
            gh.comment(n, f"**Run:** {reason}\n\n``\n{status[-1200:]}\n```")
            gate.move(gh, root, n, "shaping", reason=reason, reason_type="environment")
            return f"piece {n}: back to shaping, {reason}"
        started = time.monotonic()
        log(f"piece {n}: attempt {k} of {attempts} (log: {logfile.relative_to(root)})")
        idle_status = build_once(folder, brief(n, issue["body"], ready, last_failure, came_back, folder),
                                 ready["files"], logfile, ready.get("settings", False),
                                 idle_limit_seconds(folder))
        if idle_status == "idle":
            reason = f"builder attempt idle for {idle_limit_seconds(folder) // 60} minutes; see {logfile}"
            gh.comment(n, f"**Run:** {reason}")
            gate.move(gh, root, n, "shaping", reason=reason, reason_type="builder-failed")
            return f"piece {n}: back to shaping, {reason}"
        outcome = folder / ".loop" / "outcome"
        if outcome.is_file():
            lines = outcome.read_text(errors="replace").splitlines()
            if lines and lines[0].strip() == "bar-wrong" and "\n".join(lines[1:]).strip():
                reason = "\n".join(lines[1:]).strip()[:500]
                log(f"piece {n}: attempt {k} took {time.monotonic() - started:.1f}s; "
                    f"log: {logfile.relative_to(root)}")
                gh.comment(n, f"**Run:** attempt {k} reports bar-wrong: {reason}")
                gate.move(gh, root, n, "shaping", reason=reason, reason_type="bar-wrong")
                return f"piece {n}: back to shaping, {reason}"
        commit_leftovers(folder, n, k)
        passed, output = gate.judge(folder, ready)
        if passed:
            log(f"piece {n}: attempt {k} took {time.monotonic() - started:.1f}s; "
                f"log: {logfile.relative_to(root)}")
            log(f"piece {n}: the gate ran the judge and it passed")
            review = review_piece(root, folder, n, k, issue, ready)
            if review["contract_findings"]:
                reason = "; ".join(review["contract_findings"])
                gh.comment(n, record_text({"move": "judge-gap", "type": "judge-gap",
                                          "reason": reason},
                                          "Contract review found a judge gap: " + reason))
            return open_pull_request(gh, root, folder, n, issue, k, output, review)
        if output.startswith(gate.BAR_WRONG):
            # No build can fix this, and more attempts invite loosening a check.
            gh.comment(n, f"**Run:** attempt {k} of {attempts}: the judge passes, but the keep "
                          "check fails on the judge files themselves. The run stops here.\n\n"
                          f"```\n{output.strip()[-1500:]}\n```")
            reason = "the keep check fails on the judge files themselves; fix the judge"
            gate.move(gh, root, n, "shaping", reason=reason, reason_type="bar-wrong")
            return f"piece {n}: back to shaping, {reason}"
        if "differ from the ones fixed at ready" in output:
            restore_bar(folder, ready)
            last_failure = ("The last attempt changed the judge files. They were put back. "
                            "Make the judge pass without changing it.")
        else:
            last_failure = f"Attempt {k} failed. The judge said:\n{output.strip()[-3000:]}"
        log(f"piece {n}: attempt {k} failed")
        log(f"piece {n}: attempt {k} took {time.monotonic() - started:.1f}s; "
            f"log: {logfile.relative_to(root)}")
        said = builder_words(logfile)
        gh.comment(n, f"**Run:** attempt {k} of {attempts} failed.\n\n"
                      f"The builder said:\n\n<<<\n{said}\n>>>\n\n"
                      f"The judge said:\n\n```\n{output.strip()[-1500:]}\n```")
        if stop_requested(root):
            reason = "the person asked the run to stop"
            gate.move(gh, root, n, "shaping", reason=reason, reason_type="bar-wrong")
            return f"piece {n}: back to shaping, {reason}"
    reason = f"the judge still fails after {attempts} attempts; see the comments above"
    gate.move(gh, root, n, "shaping", reason=reason, reason_type="builder-failed")
    return f"piece {n}: back to shaping, needs you"


def pull_request_facts(folder: Path, ready: dict, output: str) -> tuple[str, str]:
    main = main_ref(folder)
    paths = sh(["git", "diff", "--name-only", f"{main}...HEAD"], folder).stdout.splitlines()
    grouped: dict[str, list[str]] = {}
    for path in paths:
        area = Path(path).parts[0] if len(Path(path).parts) > 1 else "root"
        grouped.setdefault(area, []).append(path)
    areas = "\n".join(f"- **{area}:** " + ", ".join(f"`{p}`" for p in sorted(files))
                      for area, files in sorted(grouped.items())) or "- No tracked files changed."
    added = sh(["git", "diff", "--name-only", "--diff-filter=A", f"{main}...HEAD"],
               folder).stdout.splitlines()
    tests = [p for p in added if "test" in p.lower() or Path(p).name.startswith("test_")
             or p in ready.get("files", [])]
    tests_text = ", ".join(f"`{p}`" for p in tests) if tests else "none added"
    manifests = [p for p in paths if Path(p).name in
                 {"package.json", "pyproject.toml", "requirements.txt", "requirements-dev.txt"}
                 or Path(p).name.startswith("requirements") and p.endswith(".txt")]
    dependencies = []
    for manifest in manifests:
        diff = sh(["git", "diff", "--no-ext-diff", "--unified=0", f"{main}...HEAD", "--", manifest],
                  folder).stdout
        additions = [line[1:].strip() for line in diff.splitlines()
                     if line.startswith("+") and not line.startswith("+++")]
        dependencies.append(f"`{manifest}`: " + (", ".join(additions) if additions else "changed"))
    dependency_text = "; ".join(dependencies) if dependencies else "none"
    settings = loop_settings(folder)
    protected = settings.get("protected paths", [])
    risk = []
    if any(any(path == p.rstrip("/") or path.startswith(p.rstrip("/") + "/") for p in protected)
           for path in paths):
        risk.append("protected paths touched")
    if any(re.search(r"(^|/)(migrations?|alembic)(/|$)", p, re.I) for p in paths):
        risk.append("migration files touched")
    if any(re.search(r"(^|/)(config|\.github)(/|$)|(^|/)[^/]*config[^/]*$", p, re.I)
           or p.startswith(".github/") for p in paths):
        risk.append("configuration or CI files touched")
    changed_settings = changed_check_settings(folder)
    if changed_settings:
        risk.append("check settings touched: " + ", ".join(changed_settings))
    importers = dependent_files(folder, ready.get("approach", ""), paths, ready.get("files"))
    risk.append(f"{len(importers)} project file(s) import a named or changed module")
    large = []
    for path in paths:
        candidate = folder / path
        if candidate.is_file():
            count = len(candidate.read_text(errors="replace").splitlines())
            if count > 1000:
                large.append(f"`{path}` ({count} lines)")
    if large:
        risk.append("files over 1,000 lines: " + ", ".join(large))
    migration_count = sum(bool(re.search(r"(^|/)(migrations?|alembic)(/|$)", p, re.I)) for p in paths)
    revert = f"Revert {len(paths)} changed file(s)" + (
        f" and account for {migration_count} migration file(s)" if migration_count else "") + "."
    risk_text = "\n".join(f"- {line}" for line in risk) if risk else "- No flagged paths."
    risk_text += "\n- Importers: " + (", ".join(f"`{p}`" for p in importers) if importers else "none found")
    why_path = folder / ".loop" / "why.md"
    why = why_path.read_text(errors="replace").strip() if why_path.is_file() else "Why: not supplied.\n\nWhat could go wrong: not supplied."
    evidence = (f"- Judge, Keep and Quality output:\n\n```text\n{output.strip()[-5000:]}\n```\n"
                f"- Bar hash: `{ready['bar']}`\n- Judged commit: `{rev(folder, 'HEAD')}`\n"
                f"- Tests added: {tests_text}\n- New dependencies: {dependency_text}\n- {revert}")
    facts = ("## What changed\n\n" + areas + "\n\n## Risk\n\n" + risk_text +
             "\n\n## Why and what could go wrong\n\n" + why + "\n")
    return facts, evidence


def open_pull_request(gh: GitHub, root: Path, folder: Path, n: int, issue: dict,
                      k: int, output: str, review: Optional[dict] = None) -> str:
    sh(["git", "push", "--quiet", "-u", "origin", branch_name(n)], folder)
    facts, evidence = pull_request_facts(folder, last_record(gh.comments(n), "ready") or {}, output)
    body = (f"Builds piece #{n}: {issue['title']}\n\nCloses #{n}\n\n"
            f"The gate ran the frozen judge itself after attempt {k}, and it passed.\n\n"
            f"{facts}\n## Evidence\n\n{evidence}\n")
    review = review or {}
    if review.get("contract_findings"):
        body = ("## Contract review findings\n\n" + "\n".join(
            f"- {finding}" for finding in review["contract_findings"]) + "\n\n" + body)
    if review.get("reviewer_note"):
        body += f"\n## Review\n\n{review['reviewer_note']}\n"
    if review.get("standards_findings"):
        body += "\nStandards findings:\n" + "\n".join(
            f"- {finding}" for finding in review["standards_findings"]) + "\n"
    if review.get("follow_ups"):
        body += "\n## Follow-up pieces\n\n" + "\n".join(
            f"- {finding}" for finding in review["follow_ups"]) + "\n"
    changed = changed_check_settings(folder)
    if changed:
        body += ("\n**Check settings changed** (the spec allows it). Read these first:\n"
                 + "".join(f"- `{c}`\n" for c in changed))
    existing = gh.pr_for_branch(branch_name(n))
    url = existing["url"] if existing and existing["state"] == "OPEN" else \
        gh.create_pr(branch_name(n), issue["title"], body)
    gate.move(gh, root, n, "approval", folder=folder, pr=url)
    return f"piece {n}: pull request ready for you: {url}"


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="run.py", description=__doc__.split("\n\n")[0])
    p.add_argument("pieces", nargs="*", type=int)
    p.add_argument("--attempts", type=int, default=3)
    args = p.parse_args(argv)
    root = repo_root(Path.cwd())
    gh = GitHub(root)
    try:
        lock = acquire_lock(root)
    except Refused as r:
        print(f"refused: {r.reason}", file=sys.stderr)
        print(f"next: {r.next_step}", file=sys.stderr)
        return 2
    results = []
    try:
        gate.ignore_loop_folder(root)
        results.extend(recover_building(gh, root))
        gate.sync(gh, root)
        pieces = args.pieces or sorted(i["number"] for i in gh.issues_with_label(STATE_PREFIX + "ready"))
        if not pieces:
            print("Nothing is ready. Shape a piece first.")
            return 0
        for n in pieces:
            if stop_requested(root):
                log("stop requested; ending before the next piece")
                break
            waiting = waiting_limit_note(gh, root)
            if waiting:
                print(waiting)
                results.append(waiting)
                break
            try:
                results.append(build_piece(gh, root, n, args.attempts))
            except Refused as r:
                results.append(f"piece {n}: refused: {r.reason}" + (f" (next: {r.next_step})" if r.next_step else ""))
            except Exception as e:  # keep going with the other pieces
                results.append(f"piece {n}: stopped by an error: {e}")
        print("\nRun finished.")
        print("\n".join(results))
        return 0
    finally:
        if stop_requested(root):
            clear_stop(root)
        release_lock(lock)


if __name__ == "__main__":
    sys.exit(main())
