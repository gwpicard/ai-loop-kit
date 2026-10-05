#!/usr/bin/env sh
# builder-status-rehearsal.sh: drive the build loop with stand-in builders and
# read what each ending leaves behind.
#
# A ready piece is built with nobody there. Each attempt is a fresh builder the
# coordinating session starts on the run script's start request, and each
# attempt ends with one of five statuses. The gate script takes the route for
# each status, so the labels, the Kickback section and the pushed branch are
# only as true as the gate's routes. A loop that went past its limit, that
# routed a malformed result, or that wiped a failed attempt's work would look
# the same as one that works until a person read the piece. So every route is
# driven here against the replay harness's stand-in GitHub, in throwaway
# projects with a bare repository as their remote, and read back.
#
# The builder here is a stub: a new process given only the brief, which writes
# code, commits it and writes the result file. It proves the records and the
# routes, not that a model loses its context.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)

python3 - "$ROOT" <<'PY'
import fcntl
import json
import os
import subprocess
import sys

ROOT = sys.argv[1]
sys.path.insert(0, os.path.join(ROOT, ".agents", "tests", "lib"))
sys.dont_write_bytecode = True
import loop_project as lp  # noqa: E402

for path in (lp.RUN, os.path.join(lp.FOUNDATION, "gate.py"), lp.NOTE, lp.RECOVERY,
             os.path.join(ROOT, ".agents", "skills", "setup-ai-build-kit", "templates",
                          "loop-settings.json")):
    if not os.path.isfile(path):
        print("FAIL: missing %s" % path, file=sys.stderr)
        sys.exit(1)

lab = lp.Lab("builder-status")
expect = lab.expect
SETTINGS = os.path.join(ROOT, ".agents", "skills", "setup-ai-build-kit", "templates",
                        "loop-settings.json")


def setup(body=None, settings=True, number=12, loop_label="loop:build"):
    """A project with the piece made ready, its settings in place and a run of one claimed."""
    repo = lab.project()
    if settings:
        os.makedirs(os.path.join(repo, ".agents"), exist_ok=True)
        with open(SETTINGS) as handle:
            text = handle.read()
        with open(os.path.join(repo, ".agents", "loop-settings.json"), "w") as handle:
            handle.write(text)
    lab.ready_piece(repo, number, body, loop_label)
    code, out, err = lab.runpy(repo, "start", str(number))
    run = lab.run_name_of(out)
    return repo, run, code, out, err


def next_request(repo, run, number=12):
    code, out, err = lab.runpy(repo, "next", str(number), "--run", run)
    return lab.request_of(out), code, out, err


def end(repo, run, number=12):
    return lab.runpy(repo, "ended", str(number), "--run", run)


def notes(repo, number=12):
    folder = os.path.join(repo, ".agents", "pieces", str(number))
    if not os.path.isdir(folder):
        return []
    return sorted(n for n in os.listdir(folder) if n.startswith("attempt-") and n.endswith(".md"))


def body_of(number=12):
    return lab.find(number)["body"]


def tree_matches(repo, commit):
    return subprocess.run(["git", "-C", repo, "diff", "--quiet", commit, "HEAD"],
                          env=lab.env).returncode == 0


# --- the settings template ------------------------------------------------------

with open(SETTINGS) as handle:
    template = json.load(handle)
expect(template.get("attempts") == 3 and template.get("piece_budget_minutes") == 120,
       "the settings template holds three attempts and a 120-minute piece budget",
       repr(template))

# --- a run of one, its start request and the id written back ---------------------

repo, run, code, out, err = setup()
expect(code == 0 and run.startswith("solo-12-"),
       "/implement on one piece makes a run of one, named solo-<number>-<time>",
       out + err)
expect(lab.labels_of(12) == ["loop:build", "state:building", "type:feature"],
       "the run of one claims the piece through the gate", repr(lab.labels_of(12)))
record = lab.record(repo, run)
expect(record.get("run") == run and any(p.get("number") == 12 and p.get("status") == "building"
                                        for p in record.get("pieces", [])),
       "run.json names the run and holds the piece as building", repr(record))
request, code, out, err = next_request(repo, run)
expect(code == 0 and request is not None, "run.py writes a start request", out + err)
request = request or {}
expect(request.get("piece") == 12 and request.get("attempt") == 1
       and request.get("worktree") and request.get("brief") and request.get("result")
       == ".agents/runs/%s/results/12-attempt-1.json" % run,
       "the start request names the piece, the attempt, the worktree, the brief and the "
       "result file in .agents/runs/<run name>/results/", repr(request))
saved = lab.record(repo, run)
piece = next(p for p in saved["pieces"] if p["number"] == 12)
expect(piece.get("requests") and piece["requests"][-1].get("handoff") == request.get("handoff"),
       "the start request is written into the run record", repr(piece))
expect(piece.get("start_commit") == lab.git(repo, "rev-parse", "HEAD"),
       "the run record keeps the branch tip at the first attempt as the start commit",
       repr(piece))
brief_path = os.path.join(repo, request.get("brief", "missing"))
brief = json.load(open(brief_path)) if os.path.isfile(brief_path) else {}
expect(brief.get("result") == request.get("result") and "transcript" not in brief
       and brief.get("baseline", {}).get("commit") == piece.get("start_commit"),
       "the brief names the same result file and the start commit, and carries no "
       "conversation", repr(brief))
expect("usage is not counted" in json.dumps(brief).lower(),
       "the brief says only time counts against the budget", json.dumps(brief))
code, out, err = lab.runpy(repo, "started", "12", "--run", run, "--agent", "agent-7f3")
saved = lab.record(repo, run)
piece = next(p for p in saved["pieces"] if p["number"] == 12)
expect(code == 0 and piece["requests"][-1].get("agent") == "agent-7f3",
       "the coordinating session writes the subagent's id back into the request",
       repr(piece["requests"][-1]))

# --- done: the gate runs the checks, and the piece goes on to review ---------------

lab.stub_builder(repo, request, {"app/billing/refund.py": lp.REFUND_DONE},
                 {"status": "done", "concerns": [], "needs": [], "could_not_check": []})
code, out, err = end(repo, run)
expect(code == 0 and lab.labels_of(12) == ["loop:build", "state:building", "type:feature"],
       "done leaves the labels alone: the piece goes on to checking", out + err)
evidence = os.path.join(repo, ".agents", "pieces", "12", "evidence.jsonl")
lines = [json.loads(line) for line in open(evidence)] if os.path.isfile(evidence) else []
expect(any(line.get("source") == "result" and line.get("exit") == 0
           and "tests/test_refund.py" in str(line.get("command")) for line in lines),
       "done runs the acceptance check through the gate's evidence record", repr(lines[-3:]))
expect("review" in (out + err).lower(), "done says the next step is the review", out + err)
expect(lab.model_calls() == [], "run.py started no model session", repr(lab.model_calls()))

# --- done_with_concerns: checking, and a builder_concerns reason ------------------

repo, run, code, out, err = setup()
request, code, out, err = next_request(repo, run)
lab.stub_builder(repo, request, {"app/billing/refund.py": lp.REFUND_DONE},
                 {"status": "done_with_concerns", "concerns": ["The rounding was guessed."],
                  "needs": [], "could_not_check": []})
code, out, err = end(repo, run)
forced = os.path.join(repo, ".agents", "pieces", "12", "forced.jsonl")
reasons = [json.loads(line) for line in open(forced)] if os.path.isfile(forced) else []
expect(code == 0 and any(r.get("reason") == "builder_concerns" and r.get("source")
                         == "gate.py result" and "rounding" in r.get("detail", "")
                         for r in reasons),
       "done_with_concerns writes a builder_concerns line to forced.jsonl", repr(reasons))
expect(lab.labels_of(12) == ["loop:build", "state:building", "type:feature"],
       "done_with_concerns goes on to checking with the labels unchanged")

# --- needs_context and blocked: a kickback to the sub-state the builder names -----

for status, kind, target in (("needs_context", "clarify", "shaping:clarify"),
                             ("blocked", "research", "shaping:research"),
                             ("needs_context", "spec", "shaping:spec")):
    repo, run, code, out, err = setup()
    request, code, out, err = next_request(repo, run)
    lab.stub_builder(repo, request, {"app/billing/partial.py": "PART = 1\n"},
                     {"status": status, "concerns": [], "could_not_check": [],
                      "needs": [{"kind": kind, "what": "Should a refund over the limit "
                                 "need a second person?"}]})
    tip = lab.git(repo, "rev-parse", "HEAD")
    code, out, err = end(repo, run)
    kickback = body_of()
    expect(code == 0 and lab.labels_of(12) == ["loop:build", target, "state:shaping",
                                                "type:feature"],
           "%s naming %s is a kickback to %s" % (status, kind, target), out + err)
    expect("## Kickback" in kickback and "What happened" in kickback
           and "What was tried" in kickback and "What is needed" in kickback
           and "second person" in kickback,
           "%s writes a Kickback section saying what happened, what was tried and what is "
           "needed" % status, kickback[-600:])
    expect(lab.remote_tip(repo, "spec/12-refunds") == tip,
           "%s pushes the branch and keeps it" % status, out + err)

# --- a result the gate refuses as malformed ---------------------------------------

repo, run, code, out, err = setup()
request, code, out, err = next_request(repo, run)
results = os.path.join(repo, ".agents", "runs", run, "results")
os.makedirs(results, exist_ok=True)
bad = {"missing.json": None,
       "not-json.json": "{status: done",
       "no-status.json": {"concerns": []},
       "unknown.json": {"status": "finished"},
       "no-sub-state.json": {"status": "needs_context", "needs": []},
       "wrong-sub-state.json": {"status": "blocked", "needs": [{"kind": "prototype",
                                                                 "what": "a look"}]},
       "bad-causes.json": {"status": "done", "causes": [{"cause": "a", "outcome": "maybe"}]}}
for name, value in bad.items():
    path = os.path.join(results, name)
    if value is not None:
        with open(path, "w") as handle:
            handle.write(value if isinstance(value, str) else json.dumps(value))
    code, out, err = lab.gate(repo, "result", "12", path)
    expect(code == 5 and "refused" in err and "next:" in err
           and lab.labels_of(12) == ["loop:build", "state:building", "type:feature"],
           "gate.py result refuses %s and moves nothing" % name, "%s %s %s" % (code, out, err))

# --- three failed attempts, then the stop ----------------------------------------

repo, run, code, out, err = setup()
start = lab.git(repo, "rev-parse", "HEAD")
for attempt in (1, 2, 3):
    request, code, out, err = next_request(repo, run) if attempt == 1 else (request, 0, "", "")
    expect(request is not None and request.get("attempt") == attempt,
           "attempt %d has its own start request" % attempt, repr(request))
    request = request or {}
    lab.stub_builder(repo, request, {"app/billing/refund.py": lp.REFUND_WRONG,
                                     "app/billing/scratch_%d.py" % attempt: "X = 1\n"},
                     {"status": "done", "concerns": [], "needs": [], "could_not_check": []})
    # Something left unsaved, which the next attempt must not inherit.
    lab.write(repo, {"app/billing/unsaved.py": "Y = %d\n" % attempt})
    commits_before = int(lab.git(repo, "rev-list", "--count", "HEAD"))
    code, out, err = end(repo, run)
    if attempt < 3:
        expect(code == 0 and tree_matches(repo, start),
               "after failed attempt %d the branch holds the start commit's content again"
               % attempt, out + err)
        expect(int(lab.git(repo, "rev-list", "--count", "HEAD")) == commits_before + 1,
               "the restoring commit is added on top, so the attempt's history is kept")
        expect(not os.path.exists(os.path.join(repo, "app/billing/unsaved.py")),
               "unsaved work is put away before the next attempt")
        request = lab.request_of(out)
    keep = os.path.join(repo, ".agents", "recovery", "%s-12" % run, "attempt-%d" % attempt)
    expect(os.path.isdir(keep), "attempt %d's work is kept under .agents/recovery/" % attempt,
           repr(os.listdir(os.path.dirname(keep)) if os.path.isdir(os.path.dirname(keep))
                else "none"))
expect(notes(repo) == ["attempt-1.md", "attempt-2.md", "attempt-3.md"],
       "each failed attempt has a note written by the script", repr(notes(repo)))
expect(lab.labels_of(12) == ["loop:build", "shaping:research", "state:shaping", "type:feature"],
       "after three failed attempts the piece is kicked back to research", out + err)
kickback = body_of()
expect(all(("Attempt %d" % n) in kickback and (".agents/pieces/12/attempt-%d.md" % n)
           in kickback for n in (1, 2, 3)) and "exit 1" in kickback,
       "the Kickback lists each attempt by number, status, failing check, exit code and note",
       kickback[-900:])
expect("AssertionError" not in kickback and "assert module" not in kickback,
       "no check output goes to GitHub", kickback[-900:])
expect(".agents/recovery/%s-12" % run in kickback and "rm -r" in kickback,
       "the Kickback names the kept attempts' folder and the command that deletes it",
       kickback[-900:])
stashes = lab.git(repo, "stash", "list")
expect(len([s for s in stashes.splitlines() if s.strip()]) >= 2,
       "uncommitted work was put away with git stash, never thrown away", stashes)
with open(lp.RUN) as handle:
    driver = handle.read()
expect(not any(refused in driver for refused in ("reset --hard", "\"reset\", \"--hard\"",
                                                  "checkout .", "restore .",
                                                  "\"checkout\", \".\"", "\"restore\", \".\"",
                                                  "--force", "\"-f\"")),
       "the loop driver never resets, checks out or restores the tree, and never forces a push")

# --- the limit decided from needs: spec when a check cannot be met as written -------

repo, run, code, out, err = setup(settings=False)
os.makedirs(os.path.join(repo, ".agents"), exist_ok=True)
with open(os.path.join(repo, ".agents", "loop-settings.json"), "w") as handle:
    json.dump({"attempts": 1, "piece_budget_minutes": 120}, handle)
request, code, out, err = next_request(repo, run)
lab.stub_builder(repo, request, {"app/billing/refund.py": lp.REFUND_WRONG},
                 {"status": "done", "concerns": [], "could_not_check": [],
                  "needs": [{"kind": "spec", "check": "tests/test_refund.py",
                             "what": "The check wants 10 where the masterplan says 9."}]})
code, out, err = end(repo, run)
expect(lab.labels_of(12) == ["loop:build", "shaping:spec", "state:shaping", "type:feature"],
       "at the limit, a needs entry of kind spec naming an acceptance check sends the piece "
       "to spec", out + err)
repo, run, code, out, err = setup(settings=False)
os.makedirs(os.path.join(repo, ".agents"), exist_ok=True)
with open(os.path.join(repo, ".agents", "loop-settings.json"), "w") as handle:
    json.dump({"attempts": 1, "piece_budget_minutes": 120}, handle)
request, code, out, err = next_request(repo, run)
lab.stub_builder(repo, request, {"app/billing/refund.py": lp.REFUND_WRONG},
                 {"status": "done", "concerns": [], "could_not_check": [],
                  "needs": [{"kind": "spec", "check": "tests/test_other.py",
                             "what": "Some other check."}]})
code, out, err = end(repo, run)
expect(lab.labels_of(12) == ["loop:build", "shaping:research", "state:shaping", "type:feature"],
       "a spec need naming no acceptance check of the piece still goes to research",
       out + err)

# --- the time budget ---------------------------------------------------------------

repo, run, code, out, err = setup()
request, code, out, err = next_request(repo, run)
saved = lab.record(repo, run)
for item in saved["pieces"]:
    if item["number"] == 12:
        item["first_started"] = "2000-01-01T00:00:00+00:00"
with open(os.path.join(repo, ".agents", "runs", run, "run.json"), "w") as handle:
    json.dump(saved, handle)
lab.stub_builder(repo, request, {"app/billing/refund.py": lp.REFUND_WRONG},
                 {"status": "done", "concerns": [], "needs": [], "could_not_check": []})
code, out, err = end(repo, run)
expect(lab.labels_of(12) == ["loop:build", "shaping:research", "state:shaping", "type:feature"]
       and notes(repo) == ["attempt-1.md"],
       "past the piece's time budget the loop stops after one attempt", out + err)

# --- a merge commit on the branch, and an attempt that committed nothing ----------

repo, run, code, out, err = setup()
start = lab.git(repo, "rev-parse", "HEAD")
request, code, out, err = next_request(repo, run)
lab.git(repo, "checkout", "-q", "-b", "side", "main")
lab.commit(repo, {"docs/side.md": "side\n"}, "side work")
lab.git(repo, "checkout", "-q", "spec/12-refunds")
lab.stub_builder(repo, request, {"app/billing/refund.py": lp.REFUND_WRONG},
                 {"status": "done", "concerns": [], "needs": [], "could_not_check": []})
lab.git(repo, "merge", "-q", "--no-edit", "side")
code, out, err = end(repo, run)
expect(code == 0 and tree_matches(repo, start),
       "an attempt holding a merge commit is put back to the start commit's content",
       out + err)
request = lab.request_of(out) or {}
lab.write(repo, {"app/billing/refund.py": lp.REFUND_WRONG})
lab.write_result(repo, request, {"status": "done", "concerns": [], "needs": [],
                                 "could_not_check": []})
count = int(lab.git(repo, "rev-list", "--count", "HEAD"))
code, out, err = end(repo, run)
expect(tree_matches(repo, start) and int(lab.git(repo, "rev-list", "--count", "HEAD")) == count,
       "an attempt that committed nothing is put away with no empty restoring commit",
       out + err)

# --- environment_failed: one retry that does not count, then a pause --------------

repo, run, code, out, err = setup()
request, code, out, err = next_request(repo, run)
lab.write_result(repo, request, {"status": "environment_failed",
                                 "concerns": ["The test database would not start."],
                                 "needs": [], "could_not_check": []})
code, out, err = end(repo, run)
retry = lab.request_of(out)
expect(code == 0 and retry is not None and retry.get("attempt") == 1 and retry.get("retry")
       and retry.get("handoff") != request.get("handoff"),
       "environment_failed is retried once as a fresh attempt with the same number",
       out + err)
expect(notes(repo) == [] and lab.labels_of(12) == ["loop:build", "state:building",
                                                    "type:feature"],
       "the environment failure does not count as an attempt and is never a kickback")
lab.write_result(repo, retry or {}, {"status": "environment_failed",
                                     "concerns": ["The test database would not start."],
                                     "needs": [], "could_not_check": []})
code, out, err = end(repo, run)
saved = lab.record(repo, run)
expect(code == 3 and lab.labels_of(12) == ["loop:build", "state:building", "type:feature"]
       and saved.get("stopped") and "/implement 12" in (out + err),
       "a second environment failure stops the piece in building, pauses the run and tells "
       "the person to type /implement 12", out + err)
calls_before = len(lab.calls())
code, out, err = lab.runpy(repo, "start", "12")
claims = [c for c in lab.calls()[calls_before:] if "--add-label" in c
          and "state:building" in c]
expect(code == 0 and lab.run_name_of(out) == run and claims == [],
       "/implement on the stopped piece resumes its run through run.py with no new claim",
       out + err)
request, code, out, err = next_request(repo, run)
expect(request is not None and request.get("attempt") == 1 and not request.get("retry"),
       "the resumed run reads the same attempt count from the notes on disk", out + err)

# Two environment failures in a row on different pieces pause the run at once.
repo = lab.project()
with open(SETTINGS) as handle:
    text = handle.read()
os.makedirs(os.path.join(repo, ".agents"), exist_ok=True)
with open(os.path.join(repo, ".agents", "loop-settings.json"), "w") as handle:
    handle.write(text)
lab.fresh([lab.issue(12, ["state:shaping", "shaping:check", "type:feature", "loop:build"],
                     lp.piece_body()),
           lab.issue(14, ["state:shaping", "shaping:check", "type:feature", "loop:build"],
                     lp.piece_body())])
lab.gate(repo, "move", "12", "ready")
lab.gate(repo, "move", "14", "ready")
code, out, err = lab.runpy(repo, "start", "12")
run = lab.run_name_of(out)
code, out, err = lab.runpy(repo, "start", "14", "--run", run)
first, _, _, _ = next_request(repo, run, 12)
lab.write_result(repo, first or {}, {"status": "environment_failed", "needs": [],
                                     "concerns": ["No disk space."], "could_not_check": []})
end(repo, run, 12)
second, _, _, _ = next_request(repo, run, 14)
lab.write_result(repo, second or {}, {"status": "environment_failed", "needs": [],
                                      "concerns": ["No disk space."], "could_not_check": []})
code, out, err = end(repo, run, 14)
expect(code == 3 and lab.request_of(out) is None and lab.record(repo, run).get("stopped"),
       "environment_failed twice in a row on different pieces pauses the run at once",
       out + err)

# --- the settings file -------------------------------------------------------------

repo, run, code, out, err = setup(settings=False)
request, code, out, err = next_request(repo, run)
said = out + err
request2, code2, out2, err2 = next_request(repo, run)
expect(request is not None and "3 attempts" in said and "120 minutes" in said
       and "3 attempts" not in out2 + err2,
       "with no .agents/loop-settings.json the defaults apply, said once", said + out2)
for text, key in (("{attempts: 3", "not valid JSON"),
                  (json.dumps({"attempts": 0, "piece_budget_minutes": 120}), "attempts"),
                  (json.dumps({"attempts": 3, "piece_budget_minutes": "two hours"}),
                   "piece_budget_minutes"),
                  (json.dumps({"attempts": 2.5, "piece_budget_minutes": 120}), "attempts")):
    repo, run, code, out, err = setup(settings=False)
    with open(os.path.join(repo, ".agents", "loop-settings.json"), "w") as handle:
        handle.write(text)
    request, code, out, err = next_request(repo, run)
    said = out + err
    expect(code == 1 and request is None and ".agents/loop-settings.json" in said and key in said
           and not os.path.isdir(os.path.join(repo, ".agents", "runs", run, "briefs")),
           "a settings file with %s starts no attempt and names the file and %s"
           % (text[:24], key), said)

# --- GitHub out of reach at the result, then a resumed run routes it --------------

repo, run, code, out, err = setup()
request, code, out, err = next_request(repo, run)
lab.stub_builder(repo, request, {"app/billing/partial.py": "PART = 1\n"},
                 {"status": "needs_context", "concerns": [], "could_not_check": [],
                  "needs": [{"kind": "clarify", "what": "Which currency?"}]})
lab.set_faults({"offline": True})
code, out, err = end(repo, run)
expect(code == 2 and os.path.isfile(os.path.join(repo, request["result"]))
       and "/implement 12" in (out + err),
       "with GitHub out of reach the result file is kept and the person told", out + err)
lab.set_faults({})
expect(lab.labels_of(12) == ["loop:build", "state:building", "type:feature"],
       "the piece stays in building")
code, out, err = lab.runpy(repo, "start", "12")
expect(code == 0 and lab.labels_of(12) == ["loop:build", "shaping:clarify", "state:shaping",
                                            "type:feature"],
       "a resumed run routes the saved result first", out + err)

# --- two resumes of one run at the same time ---------------------------------------

repo, run, code, out, err = setup()
lock_path = os.path.join(repo, ".agents", "runs", run, "run.lock")
with open(lock_path, "a") as lock:
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    before = json.dumps(lab.record(repo, run), sort_keys=True)
    code, out, err = lab.runpy(repo, "start", "12")
    expect(code == 1 and "another session" in (out + err)
           and json.dumps(lab.record(repo, run), sort_keys=True) == before,
           "a second resume while the run is locked changes nothing", out + err)

# --- switching the loop module -----------------------------------------------------

FIX_BODY = lp.piece_body(loop="Loop module: build\nAcceptance branch: spec/12-refunds\n"
                              "Reproduction: tests/test_refund.py")
repo, run, code, out, err = setup(body=FIX_BODY)
before_body = body_of()
code, out, err = lab.gate(repo, "check-contract", "12")
code, out, err = lab.gate(repo, "switch-module", "12", "fix")
lines = [json.loads(line) for line in open(os.path.join(repo, ".agents", "pieces", "12",
                                                         "evidence.jsonl"))] \
    if os.path.isfile(os.path.join(repo, ".agents", "pieces", "12", "evidence.jsonl")) else []
expect(code == 0 and lab.labels_of(12) == ["loop:fix", "state:building", "type:feature"]
       and body_of() == before_body,
       "switch-module changes the loop: label and leaves the contract body alone", out + err)
expect(any(line.get("phase") == "switch" for line in lines),
       "the switch is written as a line in the evidence record", repr(lines))
code, out, err = lab.gate(repo, "check-contract", "12")
expect(code == 0 and "unchanged" in out, "check-contract still passes after the switch",
       out + err)
for target, why in (("goal", "a module with no bar in the contract"),
                    ("fix", "the module the piece already has")):
    code, out, err = lab.gate(repo, "switch-module", "12", target)
    expect(code == 1 and "next:" in err and lab.labels_of(12) == ["loop:fix", "state:building",
                                                                   "type:feature"],
           "switch-module refuses %s" % why, out + err)
repo, run, code, out, err = setup()
code, out, err = lab.gate(repo, "switch-module", "12", "fix")
expect(code == 1 and lab.labels_of(12) == ["loop:build", "state:building", "type:feature"],
       "switch-module refuses fix for a contract with no reproduction", out + err)

expect(lab.model_calls() == [], "no model session was started anywhere",
       repr(lab.model_calls()))
lab.finish("builder-status-rehearsal.sh")
PY
