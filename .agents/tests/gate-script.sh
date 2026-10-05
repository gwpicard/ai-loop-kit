#!/usr/bin/env sh
# gate-script.sh: drive the gate script a founded project receives against the
# replay harness's stand-in GitHub, and read the labels back after every call.
#
# The gate is the one way a piece changes state. Every check on a move lives in
# it, so a board can be trusted only as far as the gate refuses what it should.
# A gate that let one bad move through would look the same as one that works,
# until somebody built a piece nobody had shaped. So each row of its transition
# table is driven twice, once where the condition holds and once where it
# fails, and the table is read out of the script itself: a row added there and
# not driven here fails this check.
#
# It also drives the label set, capture, drop, tidy and the report, the run
# record the gate writes beside the labels, and the cases that are not the
# normal one: GitHub out of reach, an account that cannot create labels, two
# sessions moving one piece, a piece a person gave two states, and bad input.
#
# The move to state:ready also asks the ready-gate lint beside the gate. The
# lint is rehearsed on its own in ready-lint-rehearsal.sh, so most moves here
# run a copy of the gate with a stand-in lint beside it, whose answer each case
# sets, and one runs the real gate beside the real lint.
#
# Nothing here reaches the network. The stand-in keeps its state in a file in
# a throwaway folder.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
GATE="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation/gate.py"
FAKE="$ROOT/.agents/tests/replay/fake-github"

if [ ! -f "$GATE" ]; then
  echo "FAIL: the setup skill carries no gate script at templates/foundation/gate.py" >&2
  exit 1
fi

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT INT TERM

python3 - "$GATE" "$FAKE" "$WORK" <<'PY'
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

GATE, FAKE, WORK = sys.argv[1], sys.argv[2], sys.argv[3]
PROJECT = os.path.join(WORK, "project")
STATE = os.path.join(WORK, "gh-state.json")
LOG = os.path.join(WORK, "gh.log")

os.makedirs(PROJECT)
subprocess.run(["git", "init", "-q", PROJECT], check=True)
subprocess.run(["git", "-C", PROJECT, "-c", "user.name=R", "-c", "user.email=r@example.invalid",
                "commit", "-q", "--allow-empty", "-m", "first"], check=True)
# The move to review runs the bar guard on the pull request's branch against
# its base, so both are on this computer. The branch changes nothing.
subprocess.run(["git", "-C", PROJECT, "checkout", "-q", "-B", "main"], check=True)
subprocess.run(["git", "-C", PROJECT, "branch", "refunds"], check=True)

ENV = dict(os.environ)
ENV["PATH"] = FAKE + os.pathsep + ENV["PATH"]
ENV["FAKE_GH_STATE"] = STATE
ENV["FAKE_GH_LOG"] = LOG

# The gate runs from a copy with a stand-in lint beside it. The stand-in prints
# what the case wrote into its answer file, exits with its code, and notes each
# call, so a case can see whether the gate asked it at all.
TOOLS = os.path.join(WORK, "tools")
os.makedirs(TOOLS)
RUN_GATE = os.path.join(TOOLS, "gate.py")
shutil.copy(GATE, RUN_GATE)
# The bar guard and the test guard it wraps sit beside the gate, as founding
# places them.
SCRIPTS = os.path.join(os.path.dirname(GATE), "..", "..", "..", "section-builder", "scripts")
for name in ("bar-guard.sh", "test-guard.sh"):
    shutil.copy(os.path.join(SCRIPTS, name), os.path.join(TOOLS, name))
STUB = os.path.join(TOOLS, "ready-lint.py")
LINT_ANSWER = os.path.join(WORK, "lint-answer.json")
LINT_CALLS = os.path.join(WORK, "lint-calls")
with open(STUB, "w") as handle:
    handle.write("import json, os, sys\n"
                 "with open(os.environ['LINT_ANSWER']) as handle:\n"
                 "    answer = json.load(handle)\n"
                 "with open(os.environ['LINT_CALLS'], 'a') as handle:\n"
                 "    handle.write(' '.join(sys.argv[1:]) + '\\n')\n"
                 "sys.stdout.write(answer['out'])\n"
                 "sys.exit(answer['code'])\n")
ENV["LINT_ANSWER"] = LINT_ANSWER
ENV["LINT_CALLS"] = LINT_CALLS


def lint_says(code, out):
    with open(LINT_ANSWER, "w") as handle:
        json.dump({"code": code, "out": out}, handle)
    if os.path.exists(LINT_CALLS):
        os.remove(LINT_CALLS)


def lint_calls():
    if not os.path.exists(LINT_CALLS):
        return []
    with open(LINT_CALLS) as handle:
        return [line.strip() for line in handle if line.strip()]


lint_says(0, "Ready-gate lint: no gaps on Piece 10.\n")

failures = []


def fail(message):
    failures.append(message)
    print("FAIL: " + message, file=sys.stderr)


def ok(message):
    print("ok: " + message)


def expect(condition, message, detail=""):
    if condition:
        ok(message)
    else:
        fail(message + ((" -- " + detail) if detail else ""))


# --- the stand-in's state ---------------------------------------------------

def issue(number, labels=(), body="", title=None, state="open", assignees=(),
          blocked_by=(), sub_issues=(), **extra):
    made = {"number": number, "title": title or "Piece %d" % number, "body": body,
            "state": state, "labels": list(labels), "assignees": list(assignees),
            "blocked_by": list(blocked_by), "sub_issues": list(sub_issues)}
    made.update(extra)
    return made


def fresh(issues, **extra):
    state = {"repo": "rehearsal/project", "next": 900, "issues": issues}
    state.update(extra)
    with open(STATE, "w") as handle:
        json.dump(state, handle)
    if os.path.exists(LOG):
        os.remove(LOG)


def load():
    with open(STATE) as handle:
        return json.load(handle)


def find(number):
    for item in load()["issues"]:
        if item["number"] == number:
            return item
    return None


def labels_of(number):
    return sorted(find(number)["labels"])


def calls():
    if not os.path.exists(LOG):
        return []
    with open(LOG) as handle:
        return [line.split("\t", 1)[1].strip() for line in handle
                if line.startswith("CALL\t")]


def gate(*args, stdin=None, script=None):
    done = subprocess.run([sys.executable, script or RUN_GATE, *args], cwd=PROJECT, env=ENV,
                          capture_output=True, text=True, input=stdin)
    return done.returncode, done.stdout, done.stderr


def lines(text):
    return [line for line in text.splitlines() if line.strip()]


def passed_one_line(result, what):
    code, out, err = result
    if code == 0 and len(lines(out)) == 1 and not lines(err):
        return True
    fail("%s: expected a pass printing one line, got exit %s, out=%r err=%r"
         % (what, code, out, err))
    return False


def refused_with_next(result, what):
    code, out, err = result
    said = lines(out) + lines(err)
    if code != 0 and any(line.startswith("next:") for line in said) and len(said) >= 2:
        return True
    fail("%s: expected a refusal with a next: line, got exit %s, out=%r err=%r"
         % (what, code, out, err))
    return False


def run_file(name):
    return os.path.join(PROJECT, ".agents", "runs", name, "run.json")


def write_run(name, pieces):
    path = run_file(name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        json.dump({"pieces": [{"number": n, "status": s} for n, s in pieces]}, handle)


def run_status(name, number):
    path = run_file(name)
    if not os.path.exists(path):
        return None
    with open(path) as handle:
        record = json.load(handle)
    for piece in record.get("pieces", []):
        if piece.get("number") == number:
            return piece.get("status")
    return None


# The family labels a position carries.
def family(position):
    if position.startswith("shaping:"):
        return ["state:shaping", position]
    if position == "state:in-review":
        return ["state:in-review", "review:person"]
    return [position]


def kit_family(labels):
    return sorted(l for l in labels if l.split(":", 1)[0] in ("state", "shaping", "review"))


# --- the transition table, read from the gate itself ------------------------

spec = importlib.util.spec_from_file_location("gate", GATE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
TABLE = [(row[0], row[1]) for row in module.TRANSITIONS]
expect(len(TABLE) == len(set(TABLE)), "the gate's transition table names each move once")

# --- one fixture per row, where the condition holds and where it fails ------

QUESTION = "## Open question\nShould a refund go back to the card it came from?\n"
TWO_QUESTIONS = "## Open question\nWhich card? And by when?\n"
DECIDED = "## Decided\n- A refund goes back to the card it came from.\n"
RESEARCH = ("## Research\n- The payment service refunds within five days. "
            "Source: https://example.com/refunds\n")
RESEARCH_NO_SOURCE = "## Research\n- The payment service refunds within five days.\n"
READY = ("## Readiness\n2026-10-04, checked by a session that did not shape it: Ready\n"
         "- NOTE 3: the builder should know the totals are rounded.\n")
READY_WITH_BLOCKING = ("## Readiness\n2026-10-04, checked by a session that did not shape it: Ready\n"
                       "- BLOCKING 5: nobody said what a refund shows.\n")
NOT_READY = ("## Readiness\n2026-10-04, checked by a session that did not shape it: Not ready\n"
             "- BLOCKING 5: nobody said what a refund shows.\n")
KICKBACK = ("## Kickback\nThe check for the refund total cannot be met as written. "
            "Tried twice. Needs a decision on rounding.\n")
ANSWER = {"research": RESEARCH, "clarify": DECIDED, "prototype": DECIDED}
LOOP_GUESS = "## Loop\nLoop module: build (guess, a new screen)\n"
LOOP = "## Loop\nLoop module: build\nAcceptance branch: spec/10-refunds\n"
REACH = "## Reach\nBoundary: billing\nReaches: none\n"
LINT_NOT_READY = ("## Readiness\n2026-10-05, ready-gate lint: Not ready\n"
                  "- BLOCKING lint: Reach names no test for billing\n")


def entered_with(before, sub, now):
    """A body that held `before` when the piece entered `sub`, and holds `now` today.

    The gate fingerprints a sub-state's sections on the way in. Spec's way out
    reads Loop and Reach, and its Open question, and check's reads Readiness, so
    a case builds the marker from what the piece held on entry.
    """
    marker = module.with_marker(before, sub).rstrip("\n").splitlines()[-1]
    return (now.rstrip("\n") + "\n\n" if now.strip() else "") + marker + "\n"


def case(origin, target):
    """(fixture issues, gate arguments, extra state, setup) for a pass and a fail."""
    n = 10
    sub = target.split(":", 1)[1]
    move = ["move", str(n), sub]
    typed = ["type:feature"]
    if origin == "shaping:raw":
        needs_question = sub in ("research", "clarify", "prototype")
        good = issue(n, family(origin) + typed, QUESTION if needs_question else "")
        bad = issue(n, family(origin), QUESTION if needs_question else "")
        return [good], [bad], move, move, {}
    if origin in ("shaping:research", "shaping:clarify", "shaping:prototype"):
        answer = ANSWER[origin.split(":")[1]]
        good = issue(n, family(origin) + typed, answer)
        bad = issue(n, family(origin) + typed, "")
        return [good], [bad], move, move, {}
    if origin == "shaping:spec" and sub == "check":
        # Loop and Reach written since the piece entered spec, or the same
        # contract it already carried then.
        good = issue(n, family(origin) + typed, entered_with(LOOP_GUESS, "spec", LOOP + REACH))
        bad = issue(n, family(origin) + typed, entered_with(LOOP + REACH, "spec", LOOP + REACH))
        return [good], [bad], move, move, {}
    if origin == "shaping:spec":
        # A new question, or the one the piece already carried into spec.
        return ([issue(n, family(origin) + typed, entered_with("", "spec", QUESTION))],
                [issue(n, family(origin) + typed, entered_with(QUESTION, "spec", QUESTION))],
                move, move, {})
    if origin == "shaping:check" and target == "state:ready":
        return ([issue(n, family(origin) + typed + ["loop:build"], READY)],
                [issue(n, family(origin) + typed + ["loop:build"], READY_WITH_BLOCKING)],
                move, move, {})
    if origin == "shaping:check":
        # A Not ready written since the piece entered check, or the one it
        # already carried then.
        return ([issue(n, family(origin) + typed, entered_with("", "check", NOT_READY))],
                [issue(n, family(origin) + typed, entered_with(NOT_READY, "check", NOT_READY))],
                move, move, {})
    if origin == "state:ready" and target == "state:building":
        return ([issue(n, family(origin) + typed)], [issue(n, family(origin) + typed)],
                move + ["--assignee", "@me"], move, {})
    if origin == "state:building" and target == "state:in-review":
        prs = [{"number": 1, "title": "Refunds", "body": "Closes #%d" % n,
                "head": "refunds", "base": "main", "state": "OPEN"}]
        other = [{"number": 1, "title": "Refunds", "body": "Part of #%d" % n,
                  "head": "refunds", "base": "main", "state": "OPEN"}]
        return ([issue(n, family(origin) + typed, assignees=["me"])],
                [issue(n, family(origin) + typed, assignees=["me"])], move, move,
                {"good": {"pull_requests": prs}, "bad": {"pull_requests": other}})
    if target.startswith("shaping:") and origin in ("state:building", "state:in-review"):
        return ([issue(n, family(origin) + typed, KICKBACK)],
                [issue(n, family(origin) + typed, "")], move, move, {})
    if origin == "state:in-review" and target == "state:building":
        return ([issue(n, family(origin) + typed)], [issue(n, family(origin) + typed)],
                move + ["--reason", "the refund total is off by a penny"], move, {})
    if origin == "state:ready" and target.startswith("shaping:"):
        return ([issue(n, family(origin) + typed)],
                [issue(n, family(origin) + typed, assignees=["someone"])], move, move, {})
    if target == "state:ready" and origin == "state:building":
        return ([issue(n, family(origin) + typed, assignees=["me"])],
                [issue(n, family(origin) + typed, assignees=["me"])],
                move + ["--run", "evening"], move + ["--run", "evening"],
                {"good_run": [(n, "building")], "bad_run": [(n, "queued")]})
    if target == "state:ready" and origin == "state:in-review":
        blocker = issue(20, family("shaping:clarify") + typed, KICKBACK)
        return ([issue(n, family(origin) + typed, assignees=["me"], blocked_by=[20]), blocker],
                [issue(n, family(origin) + typed, assignees=["me"]), blocker],
                move + ["--withdrawn-by", "20"], move + ["--withdrawn-by", "20"], {})
    return None


driven = set()
for origin, target in TABLE:
    built = case(origin, target)
    if built is None:
        fail("no fixture drives %s -> %s" % (origin, target))
        continue
    good_issues, bad_issues, good_args, bad_args, extra = built
    for kind, issues, args in (("good", good_issues, good_args), ("bad", bad_issues, bad_args)):
        fresh(issues, **extra.get(kind, {}))
        if os.path.exists(run_file("evening")):
            os.remove(run_file("evening"))
        if extra.get(kind + "_run"):
            write_run("evening", extra[kind + "_run"])
        before = labels_of(10)
        result = gate(*args)
        after = labels_of(10)
        what = "%s -> %s where the condition %s" % (origin, target,
                                                    "holds" if kind == "good" else "fails")
        if kind == "good":
            edits = [c for c in calls() if c.startswith("issue edit 10")]
            if (passed_one_line(result, what) and kit_family(after) == sorted(family(target))
                    and len(edits) == 1):
                driven.add((origin, target, kind))
                ok(what + ": moved, in one label write")
            else:
                fail("%s: labels after are %s, writes %s" % (what, after, edits))
        else:
            if refused_with_next(result, what) and after == before:
                driven.add((origin, target, kind))
                ok(what + ": refused, labels unchanged")
            else:
                fail("%s: labels went from %s to %s" % (what, before, after))

missing = [(o, t, k) for o, t in TABLE for k in ("good", "bad") if (o, t, k) not in driven]
expect(not missing, "every row of the gate's table was driven where it holds and where it fails",
       str(missing))

# The rows the slice names are all in the table.
named = [("shaping:raw", "shaping:clarify"), ("shaping:raw", "shaping:spec"),
         ("shaping:clarify", "shaping:spec"), ("shaping:research", "shaping:clarify"),
         ("shaping:spec", "shaping:check"), ("shaping:spec", "shaping:research"),
         ("shaping:check", "state:ready"), ("shaping:check", "shaping:spec"),
         ("state:ready", "state:building"), ("state:building", "state:in-review"),
         ("state:building", "shaping:clarify"), ("state:in-review", "shaping:spec"),
         ("state:in-review", "state:building"), ("state:ready", "shaping:clarify"),
         ("state:building", "state:ready"), ("state:in-review", "state:ready")]
expect(all(row in TABLE for row in named), "the table holds every move the slice names",
       str([row for row in named if row not in TABLE]))

# --- the conditions in more detail ------------------------------------------

# Two questions under Open question are not one.
fresh([issue(11, ["state:shaping", "shaping:raw", "type:bug"], TWO_QUESTIONS)])
result = gate("move", "11", "clarify")
expect(refused_with_next(result, "two open questions") and labels_of(11) ==
       ["shaping:raw", "state:shaping", "type:bug"],
       "an Open question section holding two questions is refused")

# Two type labels are not one.
fresh([issue(11, ["state:shaping", "shaping:raw", "type:bug", "type:chore"])])
result = gate("move", "11", "spec")
expect(refused_with_next(result, "two types"), "a piece with two type labels cannot leave raw")

# Research claims each need a source.
fresh([issue(11, ["state:shaping", "shaping:research", "type:feature"], RESEARCH_NO_SOURCE)])
result = gate("move", "11", "spec")
expect(refused_with_next(result, "research with no source")
       and labels_of(11) == ["shaping:research", "state:shaping", "type:feature"],
       "research with a claim that names no source is refused")

# The marker: written on the way in, last line, read on the way out.
MARKER = re.compile(r"^<!-- loop:gate sub-state=([a-z-]+) since=(\d{4}-\d{2}-\d{2}) "
                    r"answer=([0-9a-f]+)(?: question=([0-9a-f]+))? -->$")
fresh([issue(12, ["state:shaping", "shaping:raw", "type:feature"], QUESTION + "\n" + DECIDED)])
result = gate("move", "12", "clarify")
body = find(12)["body"]
last = body.rstrip("\n").splitlines()[-1]
match = MARKER.match(last)
expect(passed_one_line(result, "raw -> clarify with a Decided already there") and match
       and match.group(1) == "clarify",
       "a move into a sub-state writes the marker as the body's last line", repr(last))
expect(body.startswith(QUESTION), "the rest of the body is kept as it was")
result = gate("move", "12", "spec")
expect(refused_with_next(result, "an unchanged Decided")
       and labels_of(12) == ["shaping:clarify", "state:shaping", "type:feature"],
       "an answer section that has not changed since the piece entered is refused")
fixture = load()
fixture["issues"][0]["body"] = body.replace(
    DECIDED, DECIDED + "- The refund shows on the next statement.\n")
with open(STATE, "w") as handle:
    json.dump(fixture, handle)
result = gate("move", "12", "spec")
expect(passed_one_line(result, "a changed Decided") and
       labels_of(12) == ["shaping:spec", "state:shaping", "type:feature"],
       "once the answer changes, the piece moves on")
markers = [l for l in find(12)["body"].splitlines() if l.startswith("<!-- loop:gate")]
expect(len(markers) == 1 and MARKER.match(markers[0]).group(1) == "spec",
       "the marker is rewritten, never added twice", str(markers))

# Spec's marker carries a second fingerprint, of its Open question, so a
# question already asked and answered cannot send the piece back round.
fresh([issue(18, ["state:shaping", "shaping:clarify", "type:feature"],
             QUESTION + "\n" + DECIDED)])
result = gate("move", "18", "spec")
markers = [l for l in find(18)["body"].splitlines() if l.startswith("<!-- loop:gate")]
match = MARKER.match(markers[0]) if len(markers) == 1 else None
expect(passed_one_line(result, "clarify -> spec with its question still written") and match
       and match.group(1) == "spec" and match.group(4),
       "a move into spec writes a fingerprint of the Open question beside the answer",
       str(markers))
result = gate("move", "18", "clarify")
expect(refused_with_next(result, "spec -> clarify on the question already answered")
       and labels_of(18) == ["shaping:spec", "state:shaping", "type:feature"],
       "a question already asked and answered, still on the piece, cannot leave spec")
fixture = load()
fixture["issues"][0]["body"] = find(18)["body"].replace(
    "Should a refund go back to the card it came from?",
    "Should a refund over the limit need a second person?")
with open(STATE, "w") as handle:
    json.dump(fixture, handle)
result = gate("move", "18", "clarify")
expect(passed_one_line(result, "spec -> clarify on a new question")
       and labels_of(18) == ["shaping:clarify", "state:shaping", "type:feature"],
       "a new question sends the piece back from spec")

# Leaving spec for check needs both Loop and Reach, not one of them.
fresh([issue(18, ["state:shaping", "shaping:spec", "type:feature"],
             entered_with(LOOP_GUESS, "spec", LOOP))])
result = gate("move", "18", "check")
expect(refused_with_next(result, "spec -> check with no Reach")
       and labels_of(18) == ["shaping:spec", "state:shaping", "type:feature"],
       "a contract with no Reach section cannot leave spec")

# After a check was found passing on origin/main, spec names the earlier branch
# on a Kept branch line in ## Loop. That line alone is not a rewritten
# contract, so it never lets the piece leave spec, and it never stops a piece
# whose contract did change.
KEPT = "Kept branch: spec/10-refunds\n"
fresh([issue(18, ["state:shaping", "shaping:spec", "type:feature"],
             entered_with(LOOP + REACH, "spec", LOOP + KEPT + REACH))])
result = gate("move", "18", "check")
expect(refused_with_next(result, "spec -> check with only a Kept branch line added")
       and labels_of(18) == ["shaping:spec", "state:shaping", "type:feature"],
       "a Kept branch line added to ## Loop is not a rewritten contract")
LOOP_AGAIN = LOOP.replace("spec/10-refunds", "spec/10-refunds-2")
fresh([issue(18, ["state:shaping", "shaping:spec", "type:feature"],
             entered_with(LOOP + REACH, "spec", LOOP_AGAIN + KEPT + REACH))])
result = gate("move", "18", "check")
expect(passed_one_line(result, "spec -> check with a new acceptance branch and a kept one")
       and labels_of(18) == ["shaping:check", "state:shaping", "type:feature"],
       "a new acceptance branch with the earlier one kept in ## Loop leaves spec")

# A piece may keep more than one earlier spec branch, each on its own Kept
# branch line. A second one added with no new acceptance branch is still no
# rewritten contract.
KEPT_TWO = KEPT + "Kept branch: spec/10-refunds-first\n"
fresh([issue(18, ["state:shaping", "shaping:spec", "type:feature"],
             entered_with(LOOP_AGAIN + KEPT + REACH, "spec", LOOP_AGAIN + KEPT_TWO + REACH))])
result = gate("move", "18", "check")
expect(refused_with_next(result, "spec -> check with only a second Kept branch line added")
       and labels_of(18) == ["shaping:spec", "state:shaping", "type:feature"],
       "a second Kept branch line with no new acceptance branch is not a rewritten contract")

# The check's way back: a lint-written section counts as the checker's does,
# and a Ready section never sends a piece back.
fresh([issue(18, ["state:shaping", "shaping:check", "type:feature"],
             entered_with("", "check", LINT_NOT_READY))])
result = gate("move", "18", "spec")
expect(passed_one_line(result, "check -> spec with a lint-written Not ready")
       and labels_of(18) == ["shaping:spec", "state:shaping", "type:feature"],
       "a Readiness section the lint's refusal wrote sends the piece from check to spec")
fresh([issue(18, ["state:shaping", "shaping:check", "type:feature"],
             entered_with("", "check", READY))])
result = gate("move", "18", "spec")
expect(refused_with_next(result, "check -> spec with a Ready section")
       and labels_of(18) == ["shaping:check", "state:shaping", "type:feature"],
       "a Readiness section saying Ready never sends a piece back from check")

# No marker at all reads as an empty answer section at entry, and the next move writes one.
fresh([issue(13, ["state:shaping", "shaping:clarify", "type:feature"], "")])
result = gate("move", "13", "spec")
expect(refused_with_next(result, "no marker, no answer"),
       "with no marker and no answer, leaving clarify is refused")
fresh([issue(13, ["state:shaping", "shaping:clarify", "type:feature"], DECIDED)])
result = gate("move", "13", "spec")
markers = [l for l in find(13)["body"].splitlines() if l.startswith("<!-- loop:gate")]
expect(passed_one_line(result, "no marker, an answer") and len(markers) == 1,
       "with no marker, an answer counts as changed, and the next move writes the marker")

# A claim: --run alone, a blocker closed, a blocker earlier in the run, a blocker open.
fresh([issue(14, ["state:ready", "type:feature"], blocked_by=[15]),
       issue(15, ["type:feature"], state="closed")])
result = gate("move", "14", "building", "--assignee", "@me")
expect(passed_one_line(result, "claim with a closed blocker") and
       find(14)["assignees"] == ["@me"], "a claim with its blocker closed moves and assigns")
fresh([issue(14, ["state:ready", "type:feature"], blocked_by=[15]),
       issue(15, ["state:ready", "type:feature"])])
result = gate("move", "14", "building", "--assignee", "@me")
expect(refused_with_next(result, "claim with an open blocker") and
       find(14)["assignees"] == [] and labels_of(14) == ["state:ready", "type:feature"],
       "a claim with an open blocker is refused and leaves nobody assigned")
fresh([issue(14, ["state:ready", "type:feature"], blocked_by=[15]),
       issue(15, ["state:ready", "type:feature"])])
if os.path.exists(run_file("night")):
    os.remove(run_file("night"))
first = gate("move", "15", "building", "--run", "night")
second = gate("move", "14", "building", "--run", "night")
with open(run_file("night")) as handle:
    order = [p["number"] for p in json.load(handle)["pieces"]]
expect(passed_one_line(first, "claim of the blocker") and
       passed_one_line(second, "claim after its blocker in the same run") and order == [15, 14],
       "a blocker claimed earlier in the same run lets the piece on top be claimed", str(order))

# A claim of a piece whose reach touches a sensitive area with no acceptance on
# the record is refused. The gate reads the area map and the masterplan's
# sensitive areas on main, as the ready-gate lint does, so the rule holds even
# if a skill's words drift and a build is asked to start anyway. The same piece
# is claimed once the masterplan records the person's acceptance.
CARE = os.path.join(WORK, "care")
CARE_TOOLS = os.path.join(WORK, "care-tools")
os.makedirs(CARE_TOOLS)
shutil.copy(GATE, os.path.join(CARE_TOOLS, "gate.py"))
shutil.copy(os.path.join(os.path.dirname(GATE), "area-map.py"), CARE_TOOLS)
shutil.copy(STUB, CARE_TOOLS)
CARE_MAP = ("# Working rules\n\n## Areas\n\n- refunds: app/refunds.py\n  sensitive: money\n"
            "- shop: app/shop\n")


def care_project(stands):
    if os.path.isdir(CARE):
        shutil.rmtree(CARE)
    os.makedirs(os.path.join(CARE, "docs"))
    subprocess.run(["git", "init", "-q", "-b", "main", CARE], check=True)
    with open(os.path.join(CARE, "masterplan.md"), "w") as handle:
        handle.write("# Masterplan\n\n## Build path\n\nPath: Build with care\n"
                     "Sensitive areas:\n  money: the refund button; caution: the shop's "
                     "bookkeeper looks before it goes live; " + stands + "\n"
                     "Accepted: none\n\n## What it does, and for whom\n\nRefunds.\n")
    with open(os.path.join(CARE, "docs", "working-rules.md"), "w") as handle:
        handle.write(CARE_MAP)
    subprocess.run(["git", "-C", CARE, "add", "-A"], check=True)
    subprocess.run(["git", "-C", CARE, "-c", "user.name=R", "-c", "user.email=r@example.invalid",
                    "commit", "-q", "-m", "records"], check=True)


def care_gate(*args):
    done = subprocess.run([sys.executable, os.path.join(CARE_TOOLS, "gate.py"), *args], cwd=CARE,
                          env=ENV, capture_output=True, text=True)
    return done.returncode, done.stdout, done.stderr


for reach, what in (("Boundary: refunds\nReaches: none\n", "Boundary"),
                    ("Boundary: shop\nReaches: refunds: guarded by tests/test_refunds.py\n",
                     "Reaches line")):
    care_project("waiting")
    fresh([issue(19, ["state:ready", "type:feature", "loop:build"], "## Reach\n" + reach)])
    result = care_gate("move", "19", "building", "--assignee", "@me")
    said = result[1] + result[2]
    expect(refused_with_next(result, "claim in a sensitive area named by %s" % what)
           and labels_of(19) == ["loop:build", "state:ready", "type:feature"]
           and find(19)["assignees"] == [] and "money" in said,
           "a claim of a piece whose %s touches a sensitive area with no acceptance is refused, "
           "naming the area" % what, said)
care_project("accepted 2026-10-02")
fresh([issue(19, ["state:ready", "type:feature", "loop:build"],
             "## Reach\nBoundary: refunds\nReaches: none\n")])
result = care_gate("move", "19", "building", "--assignee", "@me")
expect(passed_one_line(result, "claim in a sensitive area with an acceptance")
       and labels_of(19) == ["loop:build", "state:building", "type:feature"],
       "the same claim moves once the masterplan records the acceptance")
care_project("waiting")
fresh([issue(19, ["state:ready", "type:feature", "loop:build"],
             "## Reach\nBoundary: shop\nReaches: none\n")])
result = care_gate("move", "19", "building", "--assignee", "@me")
expect(passed_one_line(result, "claim outside the sensitive area"),
       "a piece outside every sensitive area is claimed as before")

# Pull back defaults to clarify.
fresh([issue(16, ["state:ready", "type:feature"])])
result = gate("move", "16", "shaping")
expect(passed_one_line(result, "pull back") and
       labels_of(16) == ["shaping:clarify", "state:shaping", "type:feature"],
       "a ready piece pulled back with no sub-state named lands in clarify")
fresh([issue(16, ["state:ready", "type:feature"])])
result = gate("move", "16", "state:shaping")
expect(passed_one_line(result, "pull back with the prefix") and
       labels_of(16) == ["shaping:clarify", "state:shaping", "type:feature"],
       "the prefixed name state:shaping is accepted too")
fresh([issue(16, ["state:building", "type:feature"], KICKBACK)])
result = gate("move", "16", "shaping")
expect(refused_with_next(result, "a kickback naming no sub-state"),
       "a kickback must name clarify, research or spec")
fresh([issue(16, ["state:building", "type:feature"], KICKBACK)])
result = gate("move", "16", "prototype")
expect(refused_with_next(result, "a kickback to prototype"),
       "a kickback to prototype is not a move the gate makes")

# Give back: the assignee goes, the run says withdrawn, and a checking piece counts.
fresh([issue(17, ["state:building", "type:feature"], assignees=["me"])])
write_run("evening", [(17, "checking")])
result = gate("move", "17", "ready", "--run", "evening")
expect(passed_one_line(result, "give back a checking piece") and find(17)["assignees"] == []
       and run_status("evening", 17) == "withdrawn",
       "a run gives back a piece it was checking: assignee off, status withdrawn")

# In review back to building posts the reason as one comment.
fresh([issue(18, ["state:in-review", "review:person", "type:feature"])])
result = gate("move", "18", "building", "--reason", "the refund total is off by a penny")
comments = [c["body"] if isinstance(c, dict) else c for c in find(18).get("comments", [])]
expect(passed_one_line(result, "back to building") and len(comments) == 1 and
       "off by a penny" in comments[0], "a return to building posts the reason as one comment")
fresh([issue(18, ["state:in-review", "review:person", "type:feature"])],
      faults={"refuse_comment": True})
code, out, err = gate("move", "18", "building", "--reason", "the refund total is off by a penny")
expect(code == 0 and len(lines(out)) == 1 and "comment" in out and "not" in out and
       labels_of(18) == ["state:building", "type:feature"],
       "a comment that cannot be posted leaves the move standing and says so in its one line",
       repr(out + err))

# --- the ready gate ------------------------------------------------------------

# A move to ready needs a Readiness section saying Ready, a loop: label, and the
# ready-gate lint passing. The lint is asked last, since it runs checks.
READY_PIECE = ["state:shaping", "shaping:check", "type:feature", "loop:build"]
fresh([issue(10, READY_PIECE, READY)])
lint_says(0, "Ready-gate lint: no gaps on Piece 10.\n")
result = gate("move", "10", "ready")
expect(passed_one_line(result, "ready with the lint passing") and labels_of(10) ==
       ["loop:build", "state:ready", "type:feature"] and lint_calls() == ["10"],
       "a move to ready asks the lint once, about that piece, and moves on its pass",
       str(lint_calls()))

fresh([issue(10, ["state:shaping", "shaping:check", "type:feature"], READY)])
lint_says(0, "Ready-gate lint: no gaps on Piece 10.\n")
code, out, err = gate("move", "10", "ready")
expect(refused_with_next((code, out, err), "ready with no loop label") and "loop:" in out + err
       and labels_of(10) == ["shaping:check", "state:shaping", "type:feature"],
       "a piece with no loop: label is refused at the ready gate", repr(out + err))

GAPS = ("Ready-gate lint: 2 gap(s) on Piece 10:\n"
        "- the piece has no ## Reach section; next: write it in /shape\n"
        "- tests/test_refund.py passes on today's code; next: rewrite the check in /shape\n")
fresh([issue(10, READY_PIECE, READY)])
lint_says(1, GAPS)
code, out, err = gate("move", "10", "ready")
expect(refused_with_next((code, out, err), "ready with lint gaps") and
       "has no ## Reach section" in out + err and "passes on today's code" in out + err and
       labels_of(10) == ["loop:build", "shaping:check", "state:shaping", "type:feature"],
       "the lint's gaps refuse the move, and the refusal prints them", repr(out + err))

fresh([issue(10, READY_PIECE, READY)])
lint_says(2, "Ready-gate lint: GitHub did not answer, so nothing was checked.\n")
code, out, err = gate("move", "10", "ready")
expect(code != 0 and "GitHub did not answer" in out + err and
       labels_of(10) == ["loop:build", "shaping:check", "state:shaping", "type:feature"],
       "a lint that could not run counts as a refusal", repr(out + err))

os.rename(STUB, STUB + ".away")
fresh([issue(10, READY_PIECE, READY)])
code, out, err = gate("move", "10", "ready")
os.rename(STUB + ".away", STUB)
expect(refused_with_next((code, out, err), "ready with no lint beside the gate") and
       "ready-lint.py" in out + err and
       labels_of(10) == ["loop:build", "shaping:check", "state:shaping", "type:feature"],
       "with no lint beside the gate, the move to ready is refused and names it", repr(out + err))

fresh([issue(10, READY_PIECE, READY_WITH_BLOCKING)])
lint_says(0, "Ready-gate lint: no gaps on Piece 10.\n")
gate("move", "10", "ready")
expect(not lint_calls(), "a Readiness section that is not Ready is refused before the lint runs")

# The real gate beside the real lint: an older piece carrying Touches: and no
# Loop or Reach is refused, and the lint's own gap reaches the person.
TOUCHES = ("## So that\nA refund.\n\n## Done when\n### Works\n- A refund. Check: a test\n\n"
           "Touches: refunds\n\n" + READY)
fresh([issue(10, READY_PIECE, TOUCHES)])
code, out, err = gate("move", "10", "ready", script=GATE)
expect(refused_with_next((code, out, err), "the real lint on a Touches piece") and
       "## Loop" in out + err and
       labels_of(10) == ["loop:build", "shaping:check", "state:shaping", "type:feature"],
       "the real lint beside the real gate refuses a piece with no ## Loop", repr(out + err))

# --- capture -----------------------------------------------------------------

words = os.path.join(WORK, "words.md")
with open(words, "w") as handle:
    handle.write("Let people pay a deposit when they book.\n")
fresh([])
result = gate("capture", "--title", "Deposits", "--body-file", words)
made = find(900)
expect(passed_one_line(result, "capture a new piece") and made is not None and
       labels_of(900) == ["shaping:raw", "state:shaping"] and
       made["body"].startswith("Let people pay a deposit when they book.") and
       made["title"] == "Deposits",
       "capture opens an issue in shaping:raw with the person's words as its body")

fresh([issue(30, ["visual"], "Opened from the form.", title="Form issue"),
       issue(31, [], "Typed by hand.", title="Hand issue"),
       issue(32, [], "Dropped once, then reopened.", title="Reopened issue",
             state_reason="reopened"),
       issue(33, ["state:ready", "type:feature"], "Already in the model.")])
for number, kind in ((30, "a form-opened issue"), (31, "an issue opened by hand"),
                     (32, "a dropped piece someone reopened")):
    before = find(number)
    result = gate("capture", str(number))
    after = find(number)
    expect(passed_one_line(result, "capture " + kind) and
           kit_family(after["labels"]) == ["shaping:raw", "state:shaping"] and
           after["title"] == before["title"] and after["body"].startswith(before["body"]),
           "capture takes in %s and keeps its title and body" % kind)
code, out, err = gate("capture", "33")
expect(refused_with_next((code, out, err), "capture of a piece with a state") and
       "state:ready" in out + err and labels_of(33) == ["state:ready", "type:feature"],
       "capture refuses an issue that already has a state, and names it")

# --- parents -----------------------------------------------------------------

fresh([issue(40, [], "A big piece.", sub_issues=[41, 42]),
       issue(41, ["state:shaping", "shaping:raw"]),
       issue(42, ["state:ready", "type:feature"]),
       issue(43, ["state:ready", "type:feature"], sub_issues=[44]),
       issue(44, ["state:shaping", "shaping:raw"])])
code, out, err = gate("capture", "40")
expect(refused_with_next((code, out, err), "capture of a parent") and "parts" in out + err and
       labels_of(40) == [], "capture refuses a parent and says its parts carry the states")
code, out, err = gate("move", "43", "building", "--assignee", "@me")
expect(refused_with_next((code, out, err), "move of a parent") and "parts" in out + err and
       labels_of(43) == ["state:ready", "type:feature"],
       "move refuses a parent and says its parts carry the states")

# --- drop and tidy -----------------------------------------------------------

fresh([issue(50, ["state:shaping", "shaping:raw", "type:feature", "visual"])])
result = gate("drop", "50", "--reason", "Nobody needs this any more.")
dropped = find(50)
comments = [c["body"] if isinstance(c, dict) else c for c in dropped.get("comments", [])]
expect(passed_one_line(result, "drop") and dropped["state"] == "closed" and
       dropped.get("state_reason") == "not_planned" and kit_family(dropped["labels"]) == [] and
       "visual" in dropped["labels"] and any("Nobody needs this" in c for c in comments),
       "drop closes as not planned, writes the reason and takes the state labels off")
fresh([issue(50, ["state:ready"])])
result = gate("drop", "50")
expect(refused_with_next(result, "drop with no reason") and find(50)["state"] == "open",
       "drop with no reason is refused")

fresh([issue(51, ["state:in-review", "review:person", "type:bug"], state="closed"),
       issue(52, ["state:shaping", "shaping:spec"], state="closed"),
       issue(53, ["state:ready", "type:feature"])])
result = gate("tidy")
expect(passed_one_line(result, "tidy") and labels_of(51) == ["type:bug"] and
       labels_of(52) == [] and labels_of(53) == ["state:ready", "type:feature"],
       "tidy takes state, sub-state and review labels off closed issues only")

# --- report ------------------------------------------------------------------

fresh([issue(60, ["state:shaping", "shaping:raw"]),
       issue(61, ["state:in-review", "review:person", "type:bug"]),
       issue(62, [], "A parent.", sub_issues=[60, 61])])
code, out, err = gate("report")
expect(code == 0 and len(lines(out)) == 1 and not lines(err),
       "report prints one line when every open piece is in order, and a parent with none passes",
       repr(out + err))

OLD = ["idea", "shaping", "ready", "building", "to check", "parked", "blocked", "broken",
       "needs-clarification", "needs-prototype", "needs-research"]
reported = [issue(70, [], "No state at all."),
            issue(71, ["state:ready", "state:building", "type:feature"]),
            issue(72, ["state:ready", "shaping:spec", "type:feature"]),
            issue(73, ["state:shaping", "shaping:clarify", "shaping:spec"]),
            issue(74, ["state:building", "review:person"]),
            issue(75, ["state:shaping", "shaping:clarify"], sub_issues=[60]),
            issue(60, ["state:shaping", "shaping:raw"]),
            issue(76, [], "A parent with two open parts.", sub_issues=[77, 78]),
            issue(77, ["state:shaping", "shaping:raw"]),
            issue(78, ["state:ready", "type:chore"])]
for offset, old in enumerate(OLD):
    reported.append(issue(80 + offset, ["state:shaping", "shaping:raw", old]))
fresh(reported)
before = {item["number"]: sorted(item["labels"]) for item in load()["issues"]}
code, out, err = gate("report")
named_numbers = set(int(n) for n in re.findall(r"#(\d+)", out))
expect(code == 0 and {70, 71, 72, 73, 74, 75}.issubset(named_numbers),
       "report names a piece with no state, two states, a sub-label beside the wrong state, "
       "two sub-labels, and a parent carrying a state", repr(out))
expect(not ({76, 77, 78, 60} & named_numbers),
       "report never names a parent with no state, or pieces in order", repr(out))
for offset, old in enumerate(OLD):
    line = [l for l in out.splitlines() if "#%d" % (80 + offset) in l]
    expect(line and old in line[0], "report names the AI Build Kit label %r" % old, repr(line))
after = {item["number"]: sorted(item["labels"]) for item in load()["issues"]}
expect(before == after and not [c for c in calls() if c.startswith("issue edit")],
       "report changes nothing: a label a person set is reported, never reverted")

# --- labels ------------------------------------------------------------------

KIT = {"state:shaping": "0E8A16", "state:ready": "0E8A16", "state:building": "0E8A16",
       "state:in-review": "0E8A16", "shaping:raw": "FBCA04", "shaping:research": "FBCA04",
       "shaping:clarify": "FBCA04", "shaping:prototype": "FBCA04", "shaping:spec": "FBCA04",
       "shaping:check": "FBCA04", "review:auto": "5319E7", "review:person": "5319E7",
       "type:feature": "1D76DB", "type:bug": "1D76DB", "type:chore": "1D76DB",
       "loop:fix": "C5DEF5", "loop:build": "C5DEF5", "loop:goal": "C5DEF5",
       "loop:gauntlet": "C5DEF5", "visual": "EDEDED", "how it works": "EDEDED",
       "data": "EDEDED", "accounts and permissions": "EDEDED", "finance": "EDEDED",
       "external service": "EDEDED", "background automation": "EDEDED"}
expect(len(KIT) == 26, "the expected set is 26 labels")


def kit_labels_now():
    return {l["name"]: l["color"].upper() for l in load().get("labels", []) if l["name"] in KIT}


fresh([])
first = gate("labels")
after_first = kit_labels_now()
created_first = [c for c in calls() if c.startswith("label create")]
second = gate("labels")
after_second = kit_labels_now()
created_second = [c for c in calls() if c.startswith("label create")][len(created_first):]
expect(passed_one_line(first, "labels, first run") and after_first == KIT,
       "one run creates all 26 labels, each in its family's colour",
       str(set(KIT.items()) ^ set(after_first.items())))
expect(passed_one_line(second, "labels, second run") and after_second == KIT and
       not created_second, "a second run creates nothing and the same 26 are there")
expect(len(created_first) == 26, "the first run created each label once", str(len(created_first)))

fresh([], labels=[{"name": "visual", "color": "123456", "description": "mine"}])
gate("labels")
kept = [l for l in load()["labels"] if l["name"] == "visual"]
expect(kept and kept[0]["color"] == "123456",
       "a kit label that already exists in another colour is left as it is")

fresh([], faults={"refuse_label_create": ["state:ready", "loop:goal"]})
code, out, err = gate("labels")
now = kit_labels_now()
expect(code == 0 and "state:ready" in out + err and "loop:goal" in out + err and
       len(now) == 24, "an account that cannot create a label is told which, and the rest are made",
       repr(out + err))

# --- the run record ------------------------------------------------------------

pairs = [("state:ready", "building", ["--assignee", "@me"], "building"),
         ("state:in-review", "building", ["--reason", "a defect"], "building"),
         ("state:building", "in-review", [], "integrated"),
         ("state:building", "clarify", [], "kicked back"),
         ("state:in-review", "ready", [], "withdrawn")]
for origin, target, more, status in pairs:
    fresh([issue(90, family(origin) + ["type:feature"], KICKBACK)],
          pull_requests=[{"number": 3, "title": "x", "body": "Closes #%d" % 90, "head": "refunds",
                          "base": "main", "state": "OPEN"}])
    write_run("pairing", [(90, "building")])
    state_json = os.path.join(PROJECT, ".agents", "runs", "pairing", "state.json")
    with open(state_json, "w") as handle:
        handle.write('{"kept": "as it was"}\n')
    result = gate("move", "90", target, "--run", "pairing", *more)
    with open(state_json) as handle:
        untouched = handle.read() == '{"kept": "as it was"}\n'
    expect(passed_one_line(result, "%s -> %s in a run" % (origin, target)) and
           run_status("pairing", 90) == status and untouched,
           "%s -> %s writes %r into run.json and leaves state.json alone" % (origin, target, status),
           str(run_status("pairing", 90)))

fresh([issue(91, ["state:ready", "type:feature"])])
write_run("queued-run", [(91, "queued")])
result = gate("move", "91", "building", "--run", "queued-run")
with open(run_file("queued-run")) as handle:
    pieces = json.load(handle)["pieces"]
expect(passed_one_line(result, "claim of a queued piece") and pieces == [
    {"number": 91, "status": "building"}], "a queued piece is read and its status moves on")

fresh([issue(92, ["state:ready", "type:feature"])], faults={"refuse_label_write": True})
if os.path.exists(run_file("refused")):
    os.remove(run_file("refused"))
code, out, err = gate("move", "92", "building", "--run", "refused")
expect(code != 0 and not os.path.exists(run_file("refused")) and
       labels_of(92) == ["state:ready", "type:feature"],
       "a label write GitHub refuses leaves the run record as it was", repr(out + err))

broken = run_file("broken")
os.makedirs(os.path.dirname(broken), exist_ok=True)
with open(broken, "w") as handle:
    handle.write("{not json")
fresh([issue(93, ["state:ready", "type:feature"])])
result = gate("move", "93", "building", "--run", "broken")
with open(broken) as handle:
    still = handle.read() == "{not json"
expect(refused_with_next(result, "a run record that is not JSON") and still and
       labels_of(93) == ["state:ready", "type:feature"],
       "a run record that is not valid JSON is refused and never overwritten")

# --- not the normal case -------------------------------------------------------

fresh([issue(100, ["state:shaping", "shaping:raw", "type:feature"])], faults={"offline": True})
before = load()
code, out, err = gate("move", "100", "spec")
expect(code != 0 and len(lines(out) + lines(err)) == 1 and load() == before,
       "with GitHub out of reach the gate changes nothing and says so in one line",
       repr(out + err))
for args in (("labels",), ("report",), ("tidy",), ("capture", "100")):
    code, out, err = gate(*args)
    expect(code != 0 and len(lines(out) + lines(err)) == 1,
           "gate.py %s out of reach: one line and a non-zero exit" % args[0], repr(out + err))

fresh([issue(101, ["state:shaping", "shaping:clarify", "type:feature"], DECIDED)],
      faults={"race": {"number": 101, "on_read": 2,
                       "add": ["shaping:spec"], "remove": ["shaping:clarify"]}})
code, out, err = gate("move", "101", "spec")
expect(refused_with_next((code, out, err), "a move raced by another session") and
       labels_of(101) == ["shaping:spec", "state:shaping", "type:feature"] and
       not [c for c in calls() if c.startswith("issue edit")],
       "a piece that changed between the read and the write is refused, and nothing is written",
       repr(out + err))

fresh([issue(102, ["state:ready", "state:building", "type:feature"])])
code, out, err = gate("move", "102", "in-review")
expect(refused_with_next((code, out, err), "two states") and "state:ready" in out + err and
       "state:building" in out + err, "move refuses a piece with two states and names both")

fresh([issue(103, ["state:shaping", "shaping:raw", "type:feature"]),
       issue(104, ["state:shaping", "shaping:raw"], state="closed")])
for args, what in ((("move", "103", "sideways"), "an unknown target"),
                   (("move", "999", "spec"), "an issue that does not exist"),
                   (("move", "104", "spec"), "a closed issue"),
                   (("move", "ten", "spec"), "a number that is not a number"),
                   (("capture", "999"), "capture of an issue that does not exist"),
                   (("drop", "104", "--reason", "x"), "drop of a closed issue"),
                   (("fly",), "an unknown command")):
    expect(refused_with_next(gate(*args), what), "%s is refused with a next: line" % what)

# --- done ---------------------------------------------------------------------

if failures:
    print("gate-script.sh: %d check(s) failed" % len(failures), file=sys.stderr)
    sys.exit(1)
print("gate-script.sh: all checks passed")
PY
