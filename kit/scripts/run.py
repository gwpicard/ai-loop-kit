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
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402
from loopkit import (CHECK_FILES, STATE_PREFIX, GitHub, Refused, branch_name,  # noqa: E402
                     changed_check_settings, command_env,
                     last_record, main_ref, prepare, record_prepare_outputs, record_text,
                     records, repo_root, sh, untracked_paths)

KIT = Path(__file__).resolve().parent.parent
ATTEMPT_TIMEOUT = 40 * 60


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


def brief(n: int, body: str, ready: dict, last_failure: str, came_back: str = "") -> str:
    text = (KIT / "briefs" / "builder.md").read_text()
    files = "\n".join(f"- `{f}`" for f in ready["files"]) or "- (none: the command is the judge)"
    earlier = last_failure or "This is the first attempt."
    if came_back:
        earlier = ("This piece was built before and came back for these reasons:\n"
                   f"{came_back}\nThe branch still holds that earlier build. Change it so the "
                   f"reasons no longer apply.\n\n{earlier}")
    for key, value in {"PIECE": str(n), "SPEC": body.strip(), "COMMAND": ready["command"],
                       "FILES": files, "LAST_FAILURE": earlier}.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def builder_settings() -> str:
    """Wire the guard into the builder session, whether or not the plugin loads."""
    guard = f'python3 "{KIT / "hooks" / "guard.py"}"'
    return json.dumps({"hooks": {"PreToolUse": [{
        "matcher": "Bash|Edit|Write|MultiEdit|NotebookEdit",
        "hooks": [{"type": "command", "command": guard}]}]}})


def build_once(folder: Path, prompt: str, files: list[str], logfile: Path,
               settings: bool = False) -> None:
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
        proc = None
        try:
            proc = subprocess.Popen(args, cwd=folder, stdout=out, stderr=subprocess.STDOUT,
                                    env=env, start_new_session=True)
            proc.wait(timeout=ATTEMPT_TIMEOUT)
        except subprocess.TimeoutExpired:
            if proc is not None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
            out.write(f"\nThe attempt ran past {ATTEMPT_TIMEOUT // 60} minutes and was stopped.\n")


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
        started = time.monotonic()
        log(f"piece {n}: attempt {k} of {attempts} (log: {logfile.relative_to(root)})")
        build_once(folder, brief(n, issue["body"], ready, last_failure, came_back),
                   ready["files"], logfile, ready.get("settings", False))
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
            return open_pull_request(gh, root, folder, n, issue, k, output)
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


def open_pull_request(gh: GitHub, root: Path, folder: Path, n: int, issue: dict,
                      k: int, output: str) -> str:
    sh(["git", "push", "--quiet", "-u", "origin", branch_name(n)], folder)
    body = (f"Builds piece #{n}: {issue['title']}\n\nCloses #{n}\n\n"
            f"The gate ran the frozen judge itself after attempt {k}, and it passed.\n\n"
            f"<details><summary>Judge output</summary>\n\n```\n{output.strip()[-3000:]}\n```\n</details>\n")
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
