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

import ast
import hashlib
import json
import os
import re
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402
import agents  # noqa: E402
import sandbox  # noqa: E402
import walkaway  # noqa: E402
from loopkit import (STATE_PREFIX, GitHub, Refused, branch_name,  # noqa: E402
                     changed_check_settings,
                     clean_quality_outputs, record_quality_outputs,
                     last_record, loop_settings, main_ref, prepare, record_prepare_outputs, record_text, rev,
                     records, repo_root, sh, untracked_paths)
from run_start import cleanup_interrupted_reviews, ready_pieces  # noqa: E402
from procs import (AttemptIdle, _ACTIVE_GROUPS, _untrack_process, acquire_lock,
                   cache_main_ref_for_piece as _cache_main_for_piece,
                   clear_main_ref_for_piece as _clear_main_piece_cache,
                   kill_active_processes, lock_path, process_alive,
                   process_group_alive, release_lock, track_process)

KIT = Path(__file__).resolve().parent.parent
ATTEMPT_TIMEOUT = 40 * 60
DEFAULT_IDLE_LIMIT = 10 * 60


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def record_attempt_timing(logfile: Path, started_at: datetime,
                          elapsed_seconds: float) -> None:
    timing = {
        "started_at": started_at.isoformat(timespec="milliseconds"),
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "elapsed_seconds": round(elapsed_seconds, 3),
    }
    with logfile.open("a") as output:
        output.write("\nAttempt timing: " + json.dumps(timing, sort_keys=True) + "\n")


def _run_metrics_path(root: Path, n: int) -> Path:
    return root / ".loop" / "run-metrics" / f"piece-{n}.json"


def _save_run_metrics(root: Path, n: int, started_at: datetime,
                      attempts: int) -> None:
    path = _run_metrics_path(root, n)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({
        "started_at": started_at.isoformat(),
        "attempts": attempts,
    }) + "\n")
    temporary.replace(path)


def _recovered_run_metrics(root: Path, n: int) -> tuple[int, float]:
    try:
        saved = json.loads(_run_metrics_path(root, n).read_text())
        started_at = datetime.fromisoformat(saved["started_at"])
        if started_at.tzinfo is None:
            return 0, 0
        attempts = max(0, int(saved["attempts"]))
        seconds = max(0.0, (datetime.now(timezone.utc) - started_at).total_seconds())
        return attempts, seconds
    except (OSError, ValueError, KeyError, TypeError):
        return 0, 0


def recover_building(gh: GitHub, root: Path) -> list[str]:
    """Return pieces left in building to shaping after a dead run."""
    recovered = []
    for issue in gh.issues_with_label(STATE_PREFIX + "building"):
        note = "the previous run ended while this piece was building"
        attempts, seconds = _recovered_run_metrics(root, issue["number"])
        recovered.append(f"piece {issue['number']}: " + gate.move(
            gh, root, issue["number"], "shaping", reason=note,
            reason_type="environment", attempts=attempts, seconds=seconds))
        _run_metrics_path(root, issue["number"]).unlink(missing_ok=True)
    return recovered


def _hand_back(gh: GitHub, root: Path, n: int, reason: str, reason_type: str,
               metrics: dict, cause: str = "") -> str:
    """Return a claimed piece with the run's actual attempt count and duration."""
    return gate.move(gh, root, n, "shaping", reason=reason, reason_type=reason_type,
                     cause=cause,
                     attempts=metrics["attempts"],
                     seconds=time.monotonic() - metrics["started"])


def latest_main_commit(folder: Path) -> Optional[str]:  # noqa: UP045
    """Refresh remote main before deciding whether a failed check is stale."""
    main = main_ref(folder)
    if "origin" in sh(["git", "remote"], folder).stdout.split():
        sh(["git", "fetch", "--quiet", "origin", "main"], folder, check=False)
        remote_main = rev(folder, "origin/main")
        if remote_main:
            return remote_main
    return rev(folder, main)


def waiting_limit_note(gh: GitHub, root: Path, ready: Optional[dict] = None) -> str:
    value = (ready or {}).get("waiting_limit", loop_settings(root).get("waiting limit", "3"))
    try:
        limit = max(1, int(value))
    except ValueError:
        limit = 3
    waiting = len(gh.issues_with_label(STATE_PREFIX + "approval"))
    if waiting >= limit:
        return (f"Run paused: {waiting} pieces wait in approval (limit {limit}). "
                "next: review or merge a pull request, then run again.")
    return ""


def idle_limit_seconds(folder: Path, frozen_value: Optional[str] = None) -> int:
    value = frozen_value if frozen_value is not None else loop_settings(folder).get("idle limit", "10")
    try:
        return max(1, int(value)) * 60
    except ValueError:
        return DEFAULT_IDLE_LIMIT


def stop_path(root: Path) -> Path:
    return root / ".loop" / "stop"


def stop_requested(root: Path) -> bool:
    return stop_path(root).is_file()


def _interrupt_handler(signum, frame) -> None:
    kill_active_processes()
    raise KeyboardInterrupt(f"signal {signum}")


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
    command = ready.get("command", "")
    kind_rules = ""
    if ready.get("kind") == "goal":
        command = "Measure: " + ready["measure"]
        kind_rules = ("Before changing code in every attempt, write one testable hypothesis to "
                      "`.loop/hypothesis`. The gate measures the result three times and uses "
                      "the median. Meet Target and Keep to pass.\n")
        files = "- (the measured value is the judge)"
    elif ready.get("kind") == "gauntlet":
        command = "Capture: " + ready["capture"]
        kind_rules = ("The gate captures your result and runs three fresh blind critics against "
                      "the named reference. Do not change the reference or criteria.\n")
        files = "- (the captured artefact is the judge)"
    earlier = last_failure or "This is the first attempt."
    if came_back:
        earlier = ("This piece was built before and came back for these reasons:\n"
                   f"{came_back}\nThe branch still holds that earlier build. Change it so the "
                   f"reasons no longer apply.\n\n{earlier}")
    for key, value in {"PIECE": str(n), "SPEC": body.strip(),
                       "APPROACH": ready.get("approach", "") or "No approach was supplied.",
                       "RESEARCH": research_brief(ready),
                       "COMMAND": command,
                       "FILES": files,
                       "DEPENDENTS": "\n".join(f"- `{f}`" for f in dependent_files(
                           folder or Path.cwd(), ready.get("approach", ""), [], ready.get("files"))) or "- (none found)",
                       "LAST_FAILURE": earlier}.items():
        text = text.replace("{{" + key + "}}", value)
    if kind_rules:
        text += "\n## Loop kind instructions\n\n" + kind_rules
    return text


def research_brief(ready: dict) -> str:
    """Format frozen findings and claim-time stale flags for the builder."""
    stale = set(ready.get("stale_research", []))
    lines = [f"- {item['id']}: {item['finding']} (source: {item['source']}, read: {item['read']})"
             + (" [possibly stale]" if item["id"] in stale else "")
             for item in ready.get("research", [])]
    return "\n".join(lines) or "- No outside facts were used."


def review_piece(root: Path, folder: Path, n: int, k: int, issue: dict, ready: dict,
                 walk_away: bool = False, domains: Optional[list[str]] = None) -> dict:
    import review
    return review.review_piece(root, folder, n, k, issue, ready, walk_away, domains)


def build_once(folder: Path, prompt: str, files: list[str], logfile: Path,
               settings: bool = False, idle_seconds: int = DEFAULT_IDLE_LIMIT,
               protected_paths: Optional[list[str]] = None,
               contract: Optional[dict[str, str]] = None,
               walk_away: bool = False, domains: Optional[list[str]] = None,
               result_event: Optional[dict] = None,
               append_log: bool = False, backend: str = "claude") -> str:
    with logfile.open("a" if append_log else "w") as out:
        proc = agents.start_session(
            backend, prompt, folder, role="builder", disallowed=files,
            settings_allowed=settings, protected_paths=protected_paths,
            contract=contract,
            walk_away=walk_away, domains=domains)
        track_process(proc)
        from review import _pump_session
        status = _pump_session(proc, out, idle_seconds, activity_path=folder,
                               result_event=result_event, backend=backend)
        if walk_away and result_event is not None and sandbox.usage_limit_event(result_event):
            return "usage-limit"
        return status


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
    files = ready.get("bar_files", ready["files"])
    if files:
        sh(["git", "checkout", ready["commit"], "--", *files], folder)
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


def build_piece(gh: GitHub, root: Path, n: int, attempts: int,
                walk_away: bool = False, agent_override: Optional[str] = None) -> str:
    _cache_main_for_piece()
    try:
        return _build_piece(gh, root, n, attempts, walk_away, agent_override)
    finally:
        _clear_main_piece_cache()


def _build_piece(gh: GitHub, root: Path, n: int, attempts: int,
                 walk_away: bool = False, agent_override: Optional[str] = None) -> str:
    started_at = datetime.now(timezone.utc)
    metrics = {"started": time.monotonic(), "started_at": started_at, "attempts": 0}
    issue = gh.issue(n)
    log(f"piece {n}: {issue['title']}")
    check_pushed_branch(root, n)
    _save_run_metrics(root, n, started_at, metrics["attempts"])
    gate.move(gh, root, n, "building")
    try:
        result = build_claimed(gh, root, n, issue, attempts, walk_away, agent_override,
                               metrics)
    except AttemptIdle as e:
        reason = str(e)
        if gate.state_of(gh.issue(n)) == "building":
            _hand_back(gh, root, n, reason, "builder-failed", metrics)
        result = f"piece {n}: back to shaping, {reason}"
    except Exception as e:  # never leave a piece in building
        reason = f"the run stopped with an error: {str(e).strip()[:300]}"
        if gate.state_of(gh.issue(n)) == "building":
            _hand_back(gh, root, n, reason, "environment", metrics)
        result = f"piece {n}: back to shaping, {reason}"
    state = gate.state_of(gh.issue(n))
    if state == "shaping":
        release_worktree(root, n)
    if state != "building":
        _run_metrics_path(root, n).unlink(missing_ok=True)
    return result


def build_claimed(gh: GitHub, root: Path, n: int, issue: dict, attempts: int,
                  walk_away: bool = False, agent_override: Optional[str] = None,
                  metrics: Optional[dict] = None) -> str:  # noqa: UP045
    metrics = metrics or {"started": time.monotonic(),
                          "started_at": datetime.now(timezone.utc), "attempts": 0}
    ready = last_record(gh.comments(n), "ready")
    assert ready is not None  # the claim move checked it
    ready = {**ready, "agent": agents.selected(root, agent_override or ready.get("agent"))}
    claim = last_record(gh.comments(n), "claim") or {}
    ready = {**ready, "stale_research": claim.get("stale_research", [])}
    folder = worktree(root, n)
    dirty = dirty_folder_reason(folder)
    if dirty:
        status = sh(["git", "status", "--porcelain", "--untracked-files=all"], folder).stdout.strip()
        gh.comment(n, f"**Run:** {dirty}\n\n```\n{status[-1200:]}\n```")
        _hand_back(gh, root, n, dirty, "environment", metrics)
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
            _hand_back(gh, root, n, reason, "conflict", metrics)
            return f"piece {n}: back to shaping, {reason}"
        log(f"piece {n}: main changed; the builder resolves conflicts in {', '.join(conflicts)}")
        merge_note = ("Main changed since this piece was built. This folder holds an unfinished "
                      f"merge of main, with conflicts in: {', '.join(conflicts)}. First resolve "
                      "them: keep what main added and what this piece adds. Remove every "
                      "conflict marker and commit the merge. Then make the judge pass.")

    frozen_bar = ready.get("bar_files", ready.get("files", []))
    current_bar = gate.bar_file_list(folder, "HEAD", ready.get("files", []))
    added_bar = sorted(set(current_bar) - set(frozen_bar))
    if frozen_bar and (added_bar or gate.bar_hash_in(folder, frozen_bar) != ready["bar"]):
        changed_bar = sh(["git", "diff", "--no-renames", "--name-only",
                          f"{ready['commit']}..HEAD", "--", *sorted(set(frozen_bar) | set(added_bar))],
                         folder).stdout.splitlines()
        reason = "main changed the frozen judge bar: " + ", ".join(changed_bar or added_bar or frozen_bar)
        _hand_back(gh, root, n, reason, "bar-wrong", metrics)
        return f"piece {n}: back to shaping, {reason}"

    before = untracked_paths(folder)
    before_dirs = {child.name for child in folder.iterdir() if child.is_dir()}
    ok, poutput = prepare(folder, ready.get("prepare", ""), ready.get("protected_paths", []))
    if not ok:
        reason = "the Prepare command failed in the build folder; run gate.py doctor"
        gh.comment(n, f"**Run:** Prepare failed.\n\n```\n{poutput.strip()[-1500:]}\n```")
        _hand_back(gh, root, n, reason, "environment", metrics)
        return f"piece {n}: back to shaping, {reason}"
    record_prepare_outputs(folder, before, before_dirs)

    logs = root / ".loop" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    last_failure = merge_note
    came_back = came_back_reason(gh.comments(n))
    main_quality_results: dict[tuple[str, str], bool] = {}
    kind_history: list[str] = []
    for k in range(1, attempts + 1):
        if stop_requested(root):
            reason = (last_failure if last_failure.startswith("Attempt ")
                      else "the person asked the run to stop")
            _hand_back(gh, root, n, reason, "stopped", metrics)
            return f"piece {n}: back to shaping, {reason}"
        logfile = logs / f"piece-{n}-attempt-{k}.log"
        dirty_reason = dirty_folder_reason(folder)
        if dirty_reason:
            status = sh(["git", "status", "--porcelain", "--untracked-files=all"], folder).stdout.strip()
            reason = dirty_reason
            gh.comment(n, f"**Run:** {reason}\n\n``\n{status[-1200:]}\n```")
            _hand_back(gh, root, n, reason, "environment", metrics)
            return f"piece {n}: back to shaping, {reason}"
        started = time.monotonic()
        started_at = datetime.now(timezone.utc)
        (folder / ".loop" / "outcome").unlink(missing_ok=True)
        if ready.get("kind") == "goal":
            (folder / ".loop" / "hypothesis").unlink(missing_ok=True)
        log(f"piece {n}: attempt {k} of {attempts} (log: {logfile.relative_to(root)})")
        domains = walkaway.approved_domains(root) if walk_away else None
        if walk_away:
            walkaway.write_heartbeat(root, n, k)
        result_event = {}
        prompt = brief(n, issue["body"], ready, last_failure, came_back, folder)
        metrics["attempts"] = k
        _save_run_metrics(root, n, metrics["started_at"], k)
        idle_status = build_once(folder, prompt, ready["files"], logfile,
                                 ready.get("settings", False),
                                 idle_limit_seconds(folder, ready.get("idle_limit")),
                                 ready.get("protected_paths", []), ready.get("contract", {}),
                                 walk_away, domains,
                                 result_event, backend=ready["agent"])
        if idle_status == "usage-limit":
            wait_seconds = sandbox.reset_wait_seconds(result_event)
            log(f"piece {n}: usage limit; waiting {wait_seconds} seconds before one retry")
            time.sleep(wait_seconds)
            result_event = {}
            idle_status = build_once(folder, prompt, ready["files"], logfile,
                                     ready.get("settings", False),
                                     idle_limit_seconds(folder, ready.get("idle_limit")),
                                     ready.get("protected_paths", []), ready.get("contract", {}),
                                     walk_away, domains,
                                     result_event, append_log=True, backend=ready["agent"])
            if idle_status == "usage-limit":
                reason = "Claude Code remained rate limited after one reset wait; retry this walk-away run"
                gh.comment(n, f"**Run:** {reason}")
                _hand_back(gh, root, n, reason, "environment", metrics)
                return f"piece {n}: back to shaping, {reason}"
        if idle_status == "idle":
            record_attempt_timing(logfile, started_at, time.monotonic() - started)
            reason = f"builder attempt idle for {idle_limit_seconds(folder, ready.get('idle_limit')) // 60} minutes; see {logfile}"
            gh.comment(n, f"**Run:** {reason}")
            _hand_back(gh, root, n, reason, "builder-failed", metrics)
            return f"piece {n}: back to shaping, {reason}"
        outcome = folder / ".loop" / "outcome"
        if outcome.is_file():
            lines = outcome.read_text(errors="replace").splitlines()
            if lines and lines[0].strip() == "bar-wrong" and "\n".join(lines[1:]).strip():
                reason = "\n".join(lines[1:]).strip()[:500]
                record_attempt_timing(logfile, started_at, time.monotonic() - started)
                log(f"piece {n}: attempt {k} took {time.monotonic() - started:.1f}s; "
                    f"log: {logfile.relative_to(root)}")
                gh.comment(n, f"**Run:** attempt {k} reports bar-wrong: {reason}")
                _hand_back(gh, root, n, reason, "bar-wrong", metrics)
                return f"piece {n}: back to shaping, {reason}"
        commit_leftovers(folder, n, k)
        clean_quality_outputs(folder, record_quality_outputs(folder))
        try:
            attempt_ready = {**ready, "attempt": k}
            passed, output = gate.judge(folder, attempt_ready)
        finally:
            clean_quality_outputs(folder, record_quality_outputs(folder))
            record_attempt_timing(logfile, started_at, time.monotonic() - started)
        if ready.get("kind") in ("goal", "gauntlet"):
            kind_history.append(f"Attempt {k}: {output.strip()}")
            baseline = (f"Main measurement: {ready['main_measurements']}; median "
                        f"{ready['main_median']}\n" if ready.get("kind") == "goal" else
                        f"Main gauntlet: {ready['main_verdicts']}\n")
            output += "\n\n" + baseline + "Attempt history:\n" + "\n".join(kind_history)
        wrong_reason = re.search(
            r"\b(?:SyntaxError|IndentationError|ModuleNotFoundError|ImportError|"
            r"FileNotFoundError)\b|ERROR collecting|\bcommand not found\b",
            output, re.IGNORECASE)
        if not passed and wrong_reason:
            main_moved = latest_main_commit(folder) != ready.get("main")
            cause = "stale-after-main" if main_moved else "import-error"
            reason = "the judge or Keep check failed for the wrong reason"
            gh.comment(n, f"**Run:** attempt {k} of {attempts} failed for the wrong reason; "
                          "the run stops here.\n\n"
                          f"```\n{output.strip()[-1500:]}\n```")
            _hand_back(gh, root, n, reason, "environment", metrics, cause=cause)
            return f"piece {n}: back to shaping, {reason}"
        failed_quality = re.search(r"Quality: (.+)\nExit: ([1-9][0-9]*)", output)
        if not passed and failed_quality:
            command = failed_quality.group(1)
            main_commit = rev(folder, main_ref(folder)) or ""
            cache_key = (command, main_commit)
            if cache_key not in main_quality_results:
                quality_probe = gate.quality_probe_path(root, n, command, main_commit)
                try:
                    saved_probe = json.loads(quality_probe.read_text())
                    if (saved_probe.get("checked") is True
                            and saved_probe.get("command") == command
                            and saved_probe.get("main") == main_commit):
                        main_quality_results[cache_key] = saved_probe.get("failed") is True
                except (OSError, ValueError, AttributeError):
                    pass
                if cache_key not in main_quality_results:
                    main_quality_results[cache_key] = gate.quality_fails_on_main(
                        folder, command, ready.get("test", ""),
                        ready.get("protected_paths", []))
                    quality_probe.write_text(json.dumps({
                        "checked": True,
                        "failed": main_quality_results[cache_key],
                        "command": command,
                        "main": main_commit,
                    }, sort_keys=True) + "\n")
            main_quality_failed = main_quality_results[cache_key]
            if main_quality_failed:
                reason = f"Quality check also fails on main: {command}"
                gh.comment(n, f"**Run:** {reason}.\n\n```\n{output.strip()[-1500:]}\n```")
                _hand_back(gh, root, n, reason, "environment", metrics)
                return f"piece {n}: back to shaping, {reason}"
            last_failure = (f"Attempt {k} failed Quality command `{command}`. Fix this in the next "
                            f"attempt.\n\n{output.strip()[-2500:]}")
            gh.comment(n, f"**Run:** attempt {k} failed a Quality check; retrying.\n\n"
                          f"```\n{output.strip()[-1500:]}\n```")
            continue
        if passed:
            log(f"piece {n}: attempt {k} took {time.monotonic() - started:.1f}s; "
                f"log: {logfile.relative_to(root)}")
            log(f"piece {n}: the gate ran the judge and it passed")
            review = review_piece(root, folder, n, k, issue, ready, walk_away,
                                  walkaway.approved_domains(root) if walk_away else None)
            if review["contract_findings"]:
                reason = "; ".join(review["contract_findings"])
                gh.comment(n, record_text({"move": "judge-gap", "type": "judge-gap",
                                          "reason": reason},
                                          "Contract review found a judge gap: " + reason))
            return open_pull_request(gh, root, folder, n, issue, k, output, review,
                                    time.monotonic() - metrics["started"])
        if output.startswith(gate.BAR_WRONG):
            # No build can fix this, and more attempts invite loosening a check.
            gh.comment(n, f"**Run:** attempt {k} of {attempts}: the judge passes, but the keep "
                          "check fails on the judge files themselves. The run stops here.\n\n"
                          f"```\n{output.strip()[-1500:]}\n```")
            reason = "the keep check fails on the judge files themselves; fix the judge"
            _hand_back(gh, root, n, reason, "bar-wrong", metrics)
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
            reason = last_failure if last_failure.startswith("Attempt ") else \
                "the person asked the run to stop"
            _hand_back(gh, root, n, reason, "stopped", metrics)
            return f"piece {n}: back to shaping, {reason}"
    reason = f"the judge still fails after {attempts} attempts; see the comments above"
    _hand_back(gh, root, n, reason, "builder-failed", metrics)
    return f"piece {n}: back to shaping, needs you"


def pull_request_facts(folder: Path, ready: dict, output: str) -> tuple[str, str]:
    import pr
    return pr.pull_request_facts(folder, ready, output)


def open_pull_request(gh: GitHub, root: Path, folder: Path, n: int, issue: dict,
                      k: int, output: str, review: Optional[dict] = None,
                      seconds: float = 0) -> str:
    import pr
    return pr.open_pull_request(gh, root, folder, n, issue, k, output, review, seconds)


def main(argv: Optional[list[str]] = None) -> int:
    """Run the command-line orchestration from its focused module."""
    from run_cli import main as cli_main
    return cli_main(argv, sys.modules[__name__])

if __name__ == "__main__":
    sys.exit(main())
