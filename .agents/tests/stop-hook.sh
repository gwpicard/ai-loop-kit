#!/usr/bin/env sh
# stop-hook.sh: feed `gate.py stop-check` the input Claude Code gives a Stop
# hook, in throwaway worktrees, and read what it does.
#
# A builder that says it is done while an acceptance check still fails would
# hand the gate a failed attempt and lose the minutes it took. The founded
# Claude Code settings run the gate's stop-check when a session or a subagent
# stops. Where the builder's result says done and an acceptance check fails, it
# exits 2 with one line naming the check, so the builder carries on, once.
# Everywhere else it stays silent and lets the session stop: a result with
# another status, no result yet, a second stop, a folder that belongs to no
# piece, and this repository, whose own settings carry no such hook. It reads
# the run record on this computer and never asks GitHub.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)

python3 - "$ROOT" <<'PY'
import json
import os
import subprocess
import sys
import tempfile

ROOT = sys.argv[1]
sys.path.insert(0, os.path.join(ROOT, ".agents", "tests", "lib"))
sys.dont_write_bytecode = True
import loop_project as lp  # noqa: E402

TEMPLATE = os.path.join(lp.FOUNDATION, "claude-settings.json")
lab = lp.Lab("stop-hook")
expect = lab.expect


def hook_input(folder, active=False, event="Stop"):
    return json.dumps({"session_id": "s", "transcript_path": "/dev/null", "cwd": folder,
                       "hook_event_name": event, "stop_hook_active": active})


def stop_check(repo, folder, active=False, event="Stop"):
    calls = len(lab.calls())
    code, out, err = lab.run(folder, sys.executable,
                             os.path.join(repo, ".agents", "tools", "gate.py"), "stop-check",
                             stdin=hook_input(folder, active, event))
    return code, out, err, lab.calls()[calls:]


# A piece being built in its own worktree, with a start request written.
repo = lab.project()
lab.ready_piece(repo)
lab.git(repo, "checkout", "-q", "main")
worktree = os.path.join(repo, ".agents", "worktrees", "12-refunds")
lab.git(repo, "worktree", "add", "-q", worktree, "spec/12-refunds")
code, out, err = lab.runpy(repo, "start", "12")
run = lab.run_name_of(out)
code, out, err = lab.run(worktree, sys.executable, lp.RUN, "next", "12", "--run", run,
                         "--worktree", worktree)
request = lab.request_of(out) or {}
expect(bool(request), "a start request names the worktree", out + err)
result = os.path.join(repo, request.get("result", "missing.json"))

# The builder has not written a result yet.
code, out, err, calls = stop_check(repo, worktree)
expect(code == 0 and not out and not err, "with no result file yet, the session may stop",
       "%s %r %r" % (code, out, err))

# Done, while the acceptance check still fails.
lab.write(worktree, {"app/billing/refund.py": lp.REFUND_WRONG})
lab.git(worktree, "add", "-A")
lab.git(worktree, "commit", "-q", "-m", "wrong")
lab.write_result(repo, request, {"status": "done", "concerns": [], "needs": [],
                                 "could_not_check": []})
lab.set_faults({"offline": True})
code, out, err, calls = stop_check(repo, worktree)
lines = [line for line in err.splitlines() if line.strip()]
expect(code == 2 and len(lines) == 1 and "tests/test_refund.py" in lines[0] and not out,
       "done with a failing acceptance check exits 2 with one line naming the check",
       "%s %r %r" % (code, out, err))
expect(calls == [],
       "the stop check asks GitHub nothing", repr(calls))
evidence = os.path.join(repo, ".agents", "pieces", "12", "evidence.jsonl")
records = [json.loads(line) for line in open(evidence)] if os.path.isfile(evidence) else []
expect(any(r.get("source") == "stop-check" and r.get("exit") not in (0, None)
           for r in records),
       "the check ran through the gate's evidence record", repr(records[-2:]))

# The same, from a subagent's stop.
code, out, err, calls = stop_check(repo, worktree, event="SubagentStop")
expect(code == 2, "a subagent's stop is sent back the same way", err)

# A second stop in the same attempt lets the session stop.
code, out, err, calls = stop_check(repo, worktree, active=True)
expect(code == 0 and not out and not err,
       "with stop_hook_active set, the builder is not sent back a second time",
       "%s %r %r" % (code, out, err))

# Any other status lets the session stop.
for status in ("needs_context", "blocked", "environment_failed", "done_with_concerns"):
    lab.write_result(repo, request, {"status": status, "concerns": [], "could_not_check": [],
                                     "needs": [{"kind": "clarify", "what": "Which one?"}]})
    code, out, err, calls = stop_check(repo, worktree)
    expect(code == 0 and not out and not err, "a result of %s lets the session stop" % status,
           "%s %r %r" % (code, out, err))

# Done, with the check passing.
lab.write(worktree, {"app/billing/refund.py": lp.REFUND_DONE})
lab.git(worktree, "add", "-A")
lab.git(worktree, "commit", "-q", "-m", "right")
lab.write_result(repo, request, {"status": "done", "concerns": [], "needs": [],
                                 "could_not_check": []})
code, out, err, calls = stop_check(repo, worktree)
expect(code == 0 and not out and not err, "done with every acceptance check passing stops",
       "%s %r %r" % (code, out, err))

# A folder whose branch belongs to no piece being built.
code, out, err, calls = stop_check(repo, repo)
expect(code == 0 and not out and not err, "in the main folder on main it does nothing",
       "%s %r %r" % (code, out, err))
outside = tempfile.mkdtemp(prefix="stop-hook-outside-")
code, out, err, calls = stop_check(repo, outside)
expect(code == 0 and not out and not err, "outside any Git project it does nothing",
       "%s %r %r" % (code, out, err))
os.rmdir(outside)
code, out, err = lab.run(ROOT, sys.executable, os.path.join(lp.FOUNDATION, "gate.py"),
                         "stop-check", stdin=hook_input(ROOT))
expect(code == 0 and not out and not err, "in this repository it does nothing",
       "%s %r %r" % (code, out, err))
lab.set_faults({})

# The founded settings run it on both stops, with room for the checks' limit.
with open(TEMPLATE) as handle:
    settings = json.load(handle)
hooks = settings.get("hooks", {})
for event in ("Stop", "SubagentStop"):
    entries = [h for group in hooks.get(event, []) for h in group.get("hooks", [])]
    expect(len(entries) == 1 and "gate.py" in entries[0].get("command", "")
           and "stop-check" in entries[0].get("command", "")
           and int(entries[0].get("timeout", 0)) > 600,
           "the settings template runs gate.py stop-check on %s with a timeout above ten "
           "minutes" % event, repr(entries))
    if entries:
        lab.write(worktree, {"app/billing/refund.py": lp.REFUND_WRONG + "# %s\n" % event})
        lab.git(worktree, "add", "-A")
        lab.git(worktree, "commit", "-q", "-m", "wrong again")
        env = dict(lab.env, CLAUDE_PROJECT_DIR=repo)
        done = subprocess.run(["sh", "-c", entries[0]["command"]], cwd=worktree, env=env,
                              input=hook_input(worktree, event=event), capture_output=True,
                              text=True)
        expect(done.returncode == 2, "the %s command as written passes the exit code on" % event,
               "%s %r" % (done.returncode, done.stderr))
        done = subprocess.run(["sh", "-c", entries[0]["command"]], cwd=worktree,
                              env=dict(lab.env, CLAUDE_PROJECT_DIR=outside),
                              input=hook_input(worktree, event=event), capture_output=True,
                              text=True)
        expect(done.returncode == 0 and not done.stdout and not done.stderr,
               "with no gate in the project the %s command does nothing" % event,
               "%s %r" % (done.returncode, done.stderr))

# This repository's own settings carry neither hook.
with open(os.path.join(ROOT, ".claude", "settings.json")) as handle:
    own = json.load(handle)
expect(not any(event in own.get("hooks", {}) for event in ("Stop", "SubagentStop")),
       "this repository's own settings carry no Stop or SubagentStop hook")
lab.finish("stop-hook.sh")
PY
