#!/usr/bin/env python3
"""Stop hook for loop sessions. A builder that stops while the Test or Check
command fails, or a test writer that stops without a new test file, is told
to continue. Blocks are limited and counted in .lite/stop-<session>. Any
error allows the stop."""
import json
import os
import signal
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import common
import merge

# Blocks are counted per session id: a builder resumed for fix rounds keeps its
# id, so the limit of 3 is shared across all its rounds, not reset each round.
LIMITS = {"builder": 3, "test-writer": 2}
TIMEOUT = 600  # per command, well under the hook's own 1800 seconds


def run(command, cwd):
    """Run a shell command. Return (exit code, output); the code is None on timeout."""
    p = subprocess.Popen(command, shell=True, cwd=cwd, text=True, start_new_session=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        out, _ = p.communicate(timeout=TIMEOUT)
        return p.returncode, out
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        return None, ""


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
            code, out = run(command, cwd) if command else (0, "")
            if code is None:
                return "The %s command timed out after %d seconds. Make it finish." % (name, TIMEOUT)
            if code:
                return "The %s command fails. Fix it, commit, then finish. Last 60 lines:\n%s" % (
                    name, "\n".join(out.strip().splitlines()[-60:]))
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
