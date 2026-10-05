#!/usr/bin/env sh
# attempt-note-rehearsal.sh: run the implement skill's scripts/attempt-note.py
# on a throwaway attempt and compare the note with a stored one.
#
# Each attempt of the build loop is a fresh builder, and the only thing it
# carries from the attempt before is that attempt's note. A note a model wrote
# could leave out the failure that mattered or describe one that never
# happened, and the next builder would trust it. So the note is built by a
# script from the gate's evidence record and from Git alone: each check that
# failed in the attempt, with its exit code and the last 40 lines of its
# output read from the file the record names, the files the attempt touched,
# the commit it ended on and its status. A check that failed and then passed,
# a run from before the attempt, a before run and a breakage are not failures
# of the attempt, so none of them reaches the note.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)

python3 - "$ROOT" <<'PY'
import importlib.util
import json
import os
import sys

ROOT = sys.argv[1]
sys.path.insert(0, os.path.join(ROOT, ".agents", "tests", "lib"))
sys.dont_write_bytecode = True
import loop_project as lp  # noqa: E402

EXPECTED = os.path.join(ROOT, ".agents", "tests", "fixtures", "attempt-note.md")
for path in (lp.NOTE, EXPECTED):
    if not os.path.isfile(path):
        print("FAIL: missing %s" % path, file=sys.stderr)
        sys.exit(1)

lab = lp.Lab("attempt-note")
expect = lab.expect
repo = lab.project()
RUN = "solo-12-20261005-100000"
CHECK = "python3 -m pytest -q -p no:cacheprovider tests/test_refund.py"
OTHER = "python3 -m pytest -q -p no:cacheprovider tests/test_orders.py"
FLAKY = "python3 -m pytest -q -p no:cacheprovider tests/test_flaky.py"
STARTED = "2026-10-05T10:00:00+00:00"

# The attempt: two files committed, one changed and one new left unsaved.
base = lab.git(repo, "rev-parse", "HEAD")
lab.commit(repo, {"app/billing/refund.py": lp.REFUND_WRONG,
                  "app/billing/scratch.py": "X = 1\n"}, "attempt 1")
lab.write(repo, {"app/billing/__init__.py": "# changed\n",
                 "app/billing/untracked.py": "Y = 2\n"})
ended = lab.git(repo, "rev-parse", "HEAD")


def write_run(requests):
    folder = os.path.join(repo, ".agents", "runs", RUN)
    os.makedirs(os.path.join(folder, "results"), exist_ok=True)
    record = {"run": RUN, "pieces": [{"number": 12, "status": "building",
                                       "branch": "spec/12-refunds", "worktree": repo,
                                       "start_commit": base, "first_started": STARTED,
                                       "requests": requests}]}
    with open(os.path.join(folder, "run.json"), "w") as handle:
        json.dump(record, handle)


def request(attempt, started, at):
    return {"piece": 12, "attempt": attempt, "retry": False, "worktree": repo,
            "handoff": "%s-12-attempt-%d" % (RUN, attempt), "started_at": started,
            "base": at, "result": ".agents/runs/%s/results/12-attempt-%d.json" % (RUN, attempt),
            "brief": ".agents/runs/%s/briefs/12-attempt-%d.json" % (RUN, attempt),
            "checks": ["tests/test_refund.py"], "agent": None, "ended": True, "route": None}


write_run([request(1, STARTED, base)])
with open(os.path.join(repo, ".agents", "runs", RUN, "results", "12-attempt-1.json"), "w") as h:
    json.dump({"status": "done", "concerns": [], "needs": [], "could_not_check": []}, h)

# The evidence record, written by the gate's own writer, so each line chains.
spec = importlib.util.spec_from_file_location("gate", os.path.join(repo, ".agents", "tools",
                                                                    "gate.py"))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
here = os.getcwd()
os.chdir(repo)
long_output = "".join("output line %d\n" % n for n in range(1, 51))


def run_line(command, code, time, phase="after", output="ok\n"):
    return {"command": command, "exit": code, "commit": ended, "clean": True, "time": time,
            "phase": phase, "source": "evidence", "output": gate.keep_output(12, output)}


gate.write_record(12, [
    run_line(CHECK, 1, "2026-10-05T09:59:00+00:00", output="from before the attempt\n"),
    run_line(CHECK, 1, "2026-10-05T10:01:00+00:00", phase="before",
             output="the before run\n"),
    run_line(FLAKY, 1, "2026-10-05T10:02:00+00:00", output="flaky failed\n"),
    run_line(FLAKY, 0, "2026-10-05T10:03:00+00:00"),
    run_line(OTHER, 0, "2026-10-05T10:04:00+00:00"),
    run_line(CHECK, 1, "2026-10-05T10:05:00+00:00", output=long_output),
    run_line(CHECK, 0, "2026-10-05T10:06:00+00:00", phase="breakage",
             output="a breakage\n"),
    {"note": "the type check and the linter are not run here", "commit": ended,
     "time": "2026-10-05T10:07:00+00:00", "phase": "after", "source": "move"},
])
os.chdir(here)

code, out, err = lab.run(repo, sys.executable, lp.NOTE, "12", repo)
note_path = os.path.join(repo, ".agents", "pieces", "12", "attempt-1.md")
expect(code == 0 and os.path.isfile(note_path), "attempt-note.py writes attempt-1.md",
       out + err)
written = open(note_path).read() if os.path.isfile(note_path) else ""
expected = open(EXPECTED).read()
expect(written.replace(ended, "<commit>").replace("#" + "12", "#<number>") == expected,
       "the note matches the stored one, byte for byte apart from the commit",
       "\n--- written ---\n" + written)
expect("output line 11\n" in written and "output line 10\n" not in written
       and "output line 50" in written,
       "a failing check carries the last 40 lines of its output, read from its output file")
expect("from before the attempt" not in written and "the before run" not in written
       and "flaky failed" not in written and "a breakage" not in written,
       "runs before the attempt, before runs, breakages and a check that passed later are "
       "left out")
sidecar = os.path.join(repo, ".agents", "pieces", "12", "attempt-1.json")
summary = json.load(open(sidecar)) if os.path.isfile(sidecar) else {}
expect(summary.get("attempt") == 1 and summary.get("status") == "done"
       and summary.get("failing") == [{"command": CHECK, "exit": 1}]
       and summary.get("note") == ".agents/pieces/12/attempt-1.md",
       "a short record beside the note names the attempt, its status and its failing checks",
       repr(summary))

# A second attempt with no evidence lines, and no result file.
lab.git(repo, "add", "-A")
lab.git(repo, "commit", "-q", "-m", "keep")
second_base = lab.git(repo, "rev-parse", "HEAD")
write_run([request(1, STARTED, base), request(2, "2026-10-05T11:00:00+00:00", second_base)])
code, out, err = lab.run(repo, sys.executable, lp.NOTE, "12", repo)
second = os.path.join(repo, ".agents", "pieces", "12", "attempt-2.md")
text = open(second).read() if os.path.isfile(second) else ""
expect(code == 0 and "No check was recorded in this attempt." in text
       and "Status: no result" in text and "No file was changed" in text,
       "an attempt with no evidence lines and no result says so", out + err + text)
expect(open(note_path).read() == written, "the first note is left as it was")
expect(lab.model_calls() == [], "no model was asked to write or summarise a note")
lab.finish("attempt-note-rehearsal.sh")
PY
