#!/usr/bin/env python3
"""Stop hook for loop sessions. A builder that stops while the Test or Check
command fails, or a test writer that stops without a new test file, is told
to continue. Blocks are limited and counted in .lite/stop-<session>. Any
error allows the stop."""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import common
import merge

LIMITS = {"builder": 3, "test-writer": 2}


def count_block(project, session_id, limit):
    """Record one more block. False when the limit is already spent."""
    path = os.path.join(project, ".lite", "stop-" + session_id)
    try:
        with open(path) as f:
            n = int(f.read())
    except (OSError, ValueError):
        n = 0
    if n >= limit:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(str(n + 1))
    return True


def problem(role, cwd, project):
    """Why the session may not stop yet, or None."""
    if role == "builder":
        settings = common.read_settings(project)
        for name in ("Test", "Check"):
            command = settings[name + " command"]
            p = subprocess.run(command, shell=True, cwd=cwd, text=True, timeout=merge.TEST_TIMEOUT,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT) if command else None
            if p and p.returncode != 0:
                return "The %s command fails. Fix it, commit, then finish. Last 60 lines:\n%s" % (
                    name, "\n".join(p.stdout.strip().splitlines()[-60:]))
    start = os.environ.get("LITE_START")
    if role == "test-writer" and start:
        added = common.git(["diff", "--name-only", "--diff-filter=A", start + "..HEAD"], cwd=cwd)
        if not any(merge.is_test_file(p) for p in added.splitlines()):
            return "No new test file is committed. Write the failing tests and commit them."
    return None


def main():
    try:
        role, project = os.environ.get("LITE_ROLE"), os.environ["LITE_PROJECT"]
        session_id = json.load(sys.stdin)["session_id"]
        if role in LIMITS:
            why = problem(role, os.getcwd(), project)
            if why and count_block(project, session_id, LIMITS[role]):
                print(json.dumps({"decision": "block", "reason": why}))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
