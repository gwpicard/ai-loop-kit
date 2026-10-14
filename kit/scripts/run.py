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
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402
from loopkit import (STATE_PREFIX, GitHub, Refused, branch_name, command_env,  # noqa: E402
                     last_record, main_ref, prepare, records, repo_root, sh)

KIT = Path(__file__).resolve().parent.parent
ATTEMPT_TIMEOUT = 40 * 60


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def came_back_reason(comments: list[str]) -> str:
    """Every reason the piece came back for after a build, oldest first."""
    built, reasons = False, []
    for r in records(comments):
        if r.get("move") == "claim":
            built = True
        elif built and r.get("move") in ("reject", "pull-back", "give-back", "rebuild"):
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


def build_once(folder: Path, prompt: str, files: list[str], logfile: Path) -> None:
    claude = os.environ.get("LOOP_CLAUDE", "claude")
    # Claude Code applies Edit(path) deny rules to every file-editing tool.
    denied = [f"Edit({f})" for f in files]
    args = [claude, "-p", prompt, "--permission-mode", "acceptEdits",
            "--allowedTools", "Bash", "Read", "Edit", "Write", "MultiEdit", "Glob", "Grep",
            "--settings", builder_settings()]
    if denied:
        args += ["--disallowedTools", *denied]
    env = {**command_env(folder), "LOOP_BUILDER": "1"}
    with logfile.open("w") as out:
        try:
            subprocess.run(args, cwd=folder, stdout=out, stderr=subprocess.STDOUT,
                           env=env, timeout=ATTEMPT_TIMEOUT)
        except subprocess.TimeoutExpired:
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


def worktree(root: Path, n: int) -> Path:
    folder = root / ".loop" / "worktrees" / f"piece-{n}"
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
        return build_claimed(gh, root, n, issue, attempts)
    except Exception as e:  # never leave a piece in building
        reason = f"the run stopped with an error: {str(e).strip()[:300]}"
        if gate.state_of(gh.issue(n)) == "building":
            gate.move(gh, root, n, "shaping", reason=reason)
        return f"piece {n}: back to shaping, {reason}"


def build_claimed(gh: GitHub, root: Path, n: int, issue: dict, attempts: int) -> str:
    ready = last_record(gh.comments(n), "ready")
    assert ready is not None  # the claim move checked it
    folder = worktree(root, n)

    # Bring the piece up to date with main, so the pull request merges cleanly.
    main = main_ref(root)
    if sh(["git", "merge", "--no-edit", "--quiet", main], folder, check=False).returncode != 0:
        sh(["git", "merge", "--abort"], folder, check=False)
        reason = f"{branch_name(n)} does not merge cleanly with {main}"
        gate.move(gh, root, n, "shaping", reason=reason)
        return f"piece {n}: back to shaping, {reason}"

    ok, poutput = prepare(folder)
    if not ok:
        reason = "the Prepare command failed in the build folder; run gate.py doctor"
        gh.comment(n, f"**Run:** Prepare failed.\n\n```\n{poutput.strip()[-1500:]}\n```")
        gate.move(gh, root, n, "shaping", reason=reason)
        return f"piece {n}: back to shaping, {reason}"

    logs = root / ".loop" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    last_failure = ""
    came_back = came_back_reason(gh.comments(n))
    for k in range(1, attempts + 1):
        logfile = logs / f"piece-{n}-attempt-{k}.log"
        log(f"piece {n}: attempt {k} of {attempts} (log: {logfile.relative_to(root)})")
        build_once(folder, brief(n, issue["body"], ready, last_failure, came_back), ready["files"], logfile)
        commit_leftovers(folder, n, k)
        passed, output = gate.judge(folder, ready)
        if passed:
            log(f"piece {n}: the gate ran the judge and it passed")
            return open_pull_request(gh, root, folder, n, issue, k, output)
        if output.startswith(gate.BAR_WRONG):
            # No build can fix this, and more attempts invite loosening a check.
            gh.comment(n, f"**Run:** attempt {k} of {attempts}: the judge passes, but the keep "
                          "check fails on the judge files themselves. The run stops here.\n\n"
                          f"```\n{output.strip()[-1500:]}\n```")
            reason = "the keep check fails on the judge files themselves; fix the judge"
            gate.move(gh, root, n, "shaping", reason=reason)
            return f"piece {n}: back to shaping, {reason}"
        if "differ from the ones fixed at ready" in output:
            restore_bar(folder, ready)
            last_failure = ("The last attempt changed the judge files. They were put back. "
                            "Make the judge pass without changing it.")
        else:
            last_failure = f"Attempt {k} failed. The judge said:\n{output.strip()[-3000:]}"
        log(f"piece {n}: attempt {k} failed")
        said = builder_words(logfile)
        gh.comment(n, f"**Run:** attempt {k} of {attempts} failed.\n\n"
                      f"The builder said:\n\n<<<\n{said}\n>>>\n\n"
                      f"The judge said:\n\n```\n{output.strip()[-1500:]}\n```")
    reason = f"the judge still fails after {attempts} attempts; see the comments above"
    gate.move(gh, root, n, "shaping", reason=reason)
    return f"piece {n}: back to shaping, needs you"


def open_pull_request(gh: GitHub, root: Path, folder: Path, n: int, issue: dict,
                      k: int, output: str) -> str:
    sh(["git", "push", "--quiet", "-u", "origin", branch_name(n)], folder)
    body = (f"Builds piece #{n}: {issue['title']}\n\nCloses #{n}\n\n"
            f"The gate ran the frozen judge itself after attempt {k}, and it passed.\n\n"
            f"<details><summary>Judge output</summary>\n\n```\n{output.strip()[-3000:]}\n```\n</details>\n")
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

    gate.ignore_loop_folder(root)
    gate.sync(gh, root)
    pieces = args.pieces or sorted(i["number"] for i in gh.issues_with_label(STATE_PREFIX + "ready"))
    if not pieces:
        print("Nothing is ready. Shape a piece first.")
        return 0
    results = []
    for n in pieces:
        try:
            results.append(build_piece(gh, root, n, args.attempts))
        except Refused as r:
            results.append(f"piece {n}: refused: {r.reason}" + (f" (next: {r.next_step})" if r.next_step else ""))
        except Exception as e:  # keep going with the other pieces
            results.append(f"piece {n}: stopped by an error: {e}")
    print("\nRun finished.")
    print("\n".join(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
