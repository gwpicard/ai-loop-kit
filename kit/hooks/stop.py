#!/usr/bin/env python3
"""Stop hook for loop sessions. A builder that stops while the Test or Check
command fails, or a test writer that stops without a new test file, is told
to continue. Blocks are limited and counted in .loop/stop-<session>. Any
error allows the stop."""
import json
import os
import sys

try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
    import common
    import merge
except Exception as e:
    sys.stderr.write("stop: cannot load, allowing the stop: %s\n" % e)
    sys.exit(0)

# Blocks are counted per session id: a builder resumed for fix rounds keeps its
# id, so the limit of 3 is shared across all its rounds, not reset each round.
LIMITS = {"builder": 3, "test-writer": 2}
TIMEOUT = 600  # least time per command; it grows with the session limit


def run(command, cwd, timeout=None):
    """Run a shell command. Return (exit code, output); the code is None on timeout. The command
    keeps a group of its own, listed in LOOP_GROUPS, so the loop ends it with the session."""
    return common.run_shell(command, cwd, timeout or TIMEOUT, record=os.environ.get("LOOP_GROUPS"),
                            patience=600)  # the hook has its own limit; do not wait it out


def passed_path(project, session_id):
    return os.path.join(project, ".loop", "passed-" + session_id)


def unchanged_since_pass(project, session_id, cwd):
    """True when HEAD is the commit that last passed for this session and the tree is clean."""
    try:
        return (common.read_passed(project, session_id)[0] == common.git(["rev-parse", "HEAD"], cwd=cwd).strip()
                and not common.git(["status", "--porcelain", "--", ".", ":!.loop"], cwd=cwd).strip())
    except OSError:
        return False


def count_block(project, session_id, limit):
    """Record one more block. False when the limit is already spent."""
    path = os.path.join(project, ".loop", "stop-" + session_id)
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


def problem(role, cwd, project, session_id=""):
    """Why the session may not stop yet, or None."""
    if role == "builder":
        settings = common.read_settings(project)
        if session_id and unchanged_since_pass(project, session_id, cwd):
            return None
        timeout = max(TIMEOUT, settings["Session minutes"] * 20)  # a third of the session limit
        tails = []
        for name in ("Test", "Check"):
            command = settings[name + " command"]
            code, out = run(command, cwd, timeout) if command else (0, "")
            if code is None:
                return "The %s command timed out after %d seconds. Make it finish." % (name, timeout)
            if code:
                return "The %s command fails. Fix it, commit, then finish. Last 60 lines:\n%s" % (
                    name, "\n".join(out.strip().splitlines()[-60:]))
            if command:
                tails.append("%s command passed: %s" % (name, (out.strip().splitlines() or ["no output"])[-1]))
        if session_id and not common.git(["status", "--porcelain", "--", ".", ":!.loop"], cwd=cwd).strip():
            os.makedirs(os.path.dirname(passed_path(project, session_id)), exist_ok=True)
            with open(passed_path(project, session_id), "w") as f:
                f.write("\n".join([common.git(["rev-parse", "HEAD"], cwd=cwd).strip()] + tails) + "\n")
    start = os.environ.get("LOOP_START")
    if role == "test-writer" and start:
        added = common.git(["diff", "--name-only", "--diff-filter=A", start + "..HEAD"], cwd=cwd)
        if not any(merge.is_test_file(p) for p in added.splitlines()):
            return "No new test file is committed. Write the failing tests and commit them."
    return None


def main():
    try:
        role, project = os.environ.get("LOOP_ROLE"), os.environ["LOOP_PROJECT"]
        session_id = json.load(sys.stdin)["session_id"]
        if role in LIMITS:
            why = problem(role, os.getcwd(), project, session_id)
            if why and count_block(project, session_id, LIMITS[role]):
                print(json.dumps({"decision": "block", "reason": why}))
    except Exception as e:
        sys.stderr.write("stop: internal error, allowing the stop: %s\n" % e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
