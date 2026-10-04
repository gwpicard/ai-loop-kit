#!/usr/bin/env sh
# plan-refresh.sh: print the project's open pieces into plan.local.md.
#
# Information flows one way. The issues are the record; this file is a printout
# of them and never a source. Nothing here reads a piece from plan.local.md, and
# nothing anywhere writes back to an issue from it. If the printout looks stale,
# print it again. The one line read back is the time it was written, so a
# refresh that cannot reach GitHub can say how old the list in hand is.
#
# The file is gitignored, so it is one person's view of a shared record and can
# never collide with anyone else's.
#
# Founding copies this file to .agents/tools/plan-refresh.sh in the project, and
# /maintain adds it to a project founded before it shipped with every
# installation. It lives in the setup-ai-build-kit skill because every route that
# installs the kit carries the skills and nothing else.
#
# Run from the project's root folder.

set -eu

OUT=${1:-plan.local.md}

command -v gh >/dev/null 2>&1 || {
  echo "plan-refresh: the GitHub CLI is not installed, so the plan cannot be refreshed" >&2
  exit 1
}
command -v python3 >/dev/null 2>&1 || {
  echo "plan-refresh: python3 is needed to read the issue list" >&2
  exit 1
}

# When GitHub is out of reach the last printout stays as it was, and this says
# when it was written, so the person still has a list and knows its age.
last_written() {
  written=$(sed -n 's/^Last refreshed: //p' "$OUT" 2>/dev/null | head -1)
  if [ -n "$written" ]; then
    echo "plan-refresh: $OUT is left as it was, written $written" >&2
  else
    echo "plan-refresh: there is no earlier printout to fall back on" >&2
  fi
}

# Keep diagnostics private until credentials have been masked. All GitHub calls
# use this wrapper, so a missing blocker answer cannot look like an empty list.
umask 077
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
trap 'exit 1' INT TERM

github_json() {
  if gh "$@" 2>"$scratch/github-error"; then
    return 0
  fi
  python3 - "$scratch/github-error" <<'PYERROR' >&2
import os, re, sys

error = open(sys.argv[1], errors="replace").read()
# Mask secret environment values as well as credentials in common gh errors
# and HTTP diagnostics. A failed lookup must never print a credential.
for key, value in sorted(os.environ.items(), key=lambda item: -len(item[1])):
    if value and re.search(r"token|password|secret|api_?key", key, re.I):
        error = error.replace(value, "[redacted]")
error = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)",
               "[redacted]", error)
error = re.sub(r"(?im)(authorization\s*:\s*)[^\r\n]+", r"\1[redacted]", error)
error = re.sub(r"(?i)(https?://)[^/\s@]+@", r"\1[redacted]@", error)
error = re.sub(r"(?i)((?:access_token|token|password|secret|api_?key)\s*[=:]\s*)[^\s&]+",
               r"\1[redacted]", error)
if error.strip():
    print("plan-refresh: GitHub CLI error:")
    print(error.rstrip())

text = error.lower()
if any(word in text for word in ("http 401", "bad credentials")):
    print("plan-refresh: gh could not authenticate; compare GH_TOKEN and GITHUB_TOKEN presence and gh auth status in this session and your terminal before signing in again. A sandbox may not read your stored login")
elif any(word in text for word in ("gh auth login", "not logged", "not signed")):
    print("plan-refresh: gh is not signed in, or its sign-in has expired; run gh auth login in your terminal, then refresh again")
elif any(word in text for word in ("no git remotes", "none of the git remotes", "no github remote")):
    print("plan-refresh: this project has no GitHub remote; ask the agent to connect it to the project's GitHub repository, then refresh again")
elif any(word in text for word in ("error connecting", "could not resolve host", "network", "connection refused", "timeout", "timed out", "dial tcp")):
    print("plan-refresh: could not reach GitHub; network access may be blocked or unavailable. Allow GitHub access in this session, then refresh again")
elif any(word in text for word in ("http 403", "http 404", "permission", "not accessible", "could not resolve to a repository")):
    print("plan-refresh: check that gh is signed in to an account with permission to access this repository, then refresh again")
else:
    print("plan-refresh: could not reach GitHub or read this repository; ask the agent to check GitHub access in this session, then refresh again")
PYERROR
  last_written
  return 1
}

repo_json=$(github_json repo view --json nameWithOwner) || exit 1
repo=$(printf '%s' "$repo_json" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin).get("nameWithOwner",""))' \
  2>/dev/null || true)
[ -n "$repo" ] || {
  echo "plan-refresh: GitHub returned no repository name; ask the agent to check the project's GitHub repository, then refresh again" >&2
  last_written
  exit 1
}

# Nothing here uses gh's built-in --jq. The filtering happens in python instead,
# so the only thing gh has to do is return JSON. That keeps one query language
# out of the script, and it is what lets the test harness stand in for gh.
#
# One call for the whole backlog. The list payload carries
# issue_dependencies_summary, so blocked_by tells us whether anything open is
# holding a piece up without asking per issue. Only the pieces that are blocked
# need a second call, to name what is holding them.
#
# The REST issues endpoint returns pull requests too, so they are filtered out.
listing=$(github_json api "repos/$repo/issues?state=open&per_page=100" --paginate) || exit 1

# A blocker is named by its title rather than its number. Its number rides
# along only so the printout can tell whether the blocker is in the plan a run
# would follow. A number is a thing the reader has to go and look up, and the commands that read this file have to
# say "deposits cannot start until card payments is set up" rather than
# "blocked by #9". Carrying the title here means neither of them has to match a
# number back to a line somewhere else in the file and hope it is still there.
blockers_for() {
  answer=$(github_json api "repos/$repo/issues/$1/dependencies/blocked_by") || return 1
  printf '%s' "$answer" | python3 -c '
import json, sys
items = json.load(sys.stdin)
if not isinstance(items, list):
    raise SystemExit(1)
print(json.dumps([[i.get("number"), i["title"]] for i in items
                  if i.get("state") == "open"]))
' 2>/dev/null || {
    echo "plan-refresh: GitHub returned an unreadable blocker list; refresh again before choosing work" >&2
    last_written
    return 1
  }
}

# Names of the blockers, gathered before the printout is written so a failure
# part-way through leaves the previous printout intact rather than a half one.
blocked_numbers=$(printf '%s' "$listing" | python3 -c '
import json, sys
for i in json.load(sys.stdin):
    if i.get("pull_request") or i.get("state", "open") != "open":
        continue
    if (i.get("issue_dependencies_summary") or {}).get("blocked_by", 0) > 0:
        print(i["number"])
')

blocker_map=""
for n in $blocked_numbers; do
  blocker_map="$blocker_map$n	$(blockers_for "$n")
"
done

# The listing goes via a file rather than a pipe. This script reaches python on
# stdin, so anything piped in as well would be read as part of the script and
# leave sys.stdin empty by the time the program runs.
listing_file="$scratch/issues.json"
printf '%s' "$listing" > "$listing_file"

# The gate script sits beside this file, in .agents/tools in a project and in
# the setup skill's templates/foundation before founding copies it. Needs
# attention is what its report would print, so the printout asks it rather than
# working the same findings out a second time.
gate_path="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/gate.py"

python3 - "$OUT" "$listing_file" "$blocker_map" "$gate_path" <<'PY'
import importlib.util, json, re, subprocess, sys

out, listing_file, blocker_raw, gate_path = sys.argv[1:5]
# A closed issue is done. The listing asks for open issues only, but the check
# is made here too, so a closed issue still carrying a label can never print as
# work waiting to be done.
issues = [i for i in json.load(open(listing_file))
          if not i.get("pull_request") and i.get("state", "open") == "open"]

# The gate's own report check, loaded from the file beside this one. Nothing is
# written next to it: Python is told not to leave a compiled copy behind.
gate = None
try:
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("gate", gate_path)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    gate.findings_for, gate.missing_hook
except Exception:
    gate = None

# For each held-up piece, its open blockers as (number, title) pairs, and the
# titles joined for the line that names them.
blocked_by, blockers = {}, {}
for line in blocker_raw.splitlines():
    if "\t" in line:
        number, found = line.split("\t", 1)
        try:
            pairs = [(n, t) for n, t in json.loads(found)]
        except Exception:
            pairs = []
        blocked_by[int(number)] = pairs
        blockers[int(number)] = ", ".join(t for _, t in pairs)

stamp = subprocess.run(["date", "+%d %b, %H:%M"], capture_output=True,
                       text=True).stdout.strip()

def labels(issue):
    return {l["name"] for l in issue.get("labels", [])}

# A piece made of parts. GitHub's sub-issue summary rides along in the list
# payload, the way the blocked-by summary does, so a parent is known without a
# second call. total is how many parts; completed is how many have closed. A
# parent is an issue with at least one open part, as the gate counts it.
def sub_summary(issue):
    s = issue.get("sub_issues_summary") or {}
    return s.get("total", 0), s.get("completed", 0)

def is_parent(issue):
    total, completed = sub_summary(issue)
    return total - completed > 0

# An issue with no "## Done when" has never been sized. A parent carries no Done
# when of its own, because its parts carry the checkable conditions.
def still_a_note(issue):
    if sub_summary(issue)[0] > 0:
        return False
    return "## Done when" not in (issue.get("body") or "")

SUB_STATES = ["raw", "research", "clarify", "prototype", "spec", "check"]
REVIEWS = [("review:person", "In review, waiting for you"),
           ("review:auto", "In review, automatic")]

# The one column a piece sits in, read from its labels: a shaping sub-state,
# ready, building, or one of the two kinds of review. None when the labels do
# not say, which the gate's report then names.
def column(issue):
    names = labels(issue)
    states = [n for n in names if n.startswith("state:")]
    subs = [n for n in names if n.startswith("shaping:")]
    reviews = [n for n in names if n.startswith("review:")]
    if len(states) != 1:
        return None
    if states[0] == "state:shaping":
        if len(subs) == 1 and subs[0][len("shaping:"):] in SUB_STATES:
            return "Shaping: " + subs[0][len("shaping:"):]
        return None
    if states[0] == "state:in-review":
        if len(reviews) == 1:
            return dict(REVIEWS).get(reviews[0])
        return None
    return {"state:ready": "ready", "state:building": "Building"}.get(states[0])

import re

# The lines of a piece's body outside code blocks, stripped. A line inside a
# block fenced with ``` or ~~~ is an example, never the piece's own line.
def body_lines(issue):
    fence, kept = None, []
    for raw in (issue.get("body") or "").splitlines():
        line = raw.strip()
        mark = line[:3]
        if mark in ("```", "~~~"):
            fence = None if fence == mark else (fence or mark)
            continue
        if fence is None:
            kept.append(line)
    return kept

def heading(line, name):
    return re.match(r"^#{2,3}\s*%s\s*$" % name, line, re.I) is not None

# A piece that carries a later state without the steps before it, because a
# person can put a label on by hand. Never shaped, so it has no Done when, or,
# for a piece being built or reviewed, never passed the readiness check, so it
# has no Readiness section. Either way it looks exactly like a piece that went
# the proper way, so the printout says what is missing. A parent never gets
# either note. Where both are missing, the first is the whole story. The Done
# when test is the one still_a_note() uses, word for word, so the two never
# disagree about a piece. The Readiness test is the heading match
# verdict_marks() uses, which ignores case and code blocks.
WORDS = {"ready": "ready", "Building": "building",
         "In review, waiting for you": "in review", "In review, automatic": "in review"}

def skipped_step(issue):
    place = column(issue)
    if place not in WORDS or is_parent(issue):
        return ""
    if still_a_note(issue):
        return "(%s with no Done when, so never shaped)" % WORDS[place]
    if place != "ready" and not any(heading(line, "readiness") for line in body_lines(issue)):
        return "(%s with no Readiness check)" % WORDS[place]
    return ""

# What the gate's report says about a piece, or "" when it says nothing.
def findings(issue):
    if gate is None:
        return ""
    found = gate.findings_for(issue)
    return "(%s)" % "; ".join(found) if found else ""

# The board. A piece the gate's report names prints once, under Needs
# attention, because its labels give no column to trust. A piece that skipped a
# step prints there and in its column too, since somebody really is building or
# reviewing it, except a ready one, which is never offered to build. A parent
# the report does not name prints under Made of parts.
general = []
if gate is None:
    general.append("the gate script %s is missing or unreadable, so the labels were "
                   "not checked; run /maintain, which puts it back" % gate_path)
else:
    hook = gate.missing_hook()
    if hook:
        general.append(hook)

needs_attention, parents = [], []
columns = {name: [] for name in
           ["Shaping: " + s for s in SUB_STATES] + ["ready", "Building"]
           + [name for _, name in REVIEWS]}
held_up = []
for issue in sorted(issues, key=lambda i: i["number"]):
    found = findings(issue)
    if found:
        needs_attention.append((issue, found))
        continue
    if is_parent(issue):
        parents.append(issue)
        continue
    place = column(issue)
    if place is None:
        # Only reached with no gate to ask, which already said so above.
        needs_attention.append((issue, "(labels the printout cannot place)"))
        continue
    note = skipped_step(issue)
    if note:
        needs_attention.append((issue, note))
        if place == "ready":
            continue
    if place == "ready" and blockers.get(issue["number"]):
        held_up.append(issue)
    else:
        columns[place].append(issue)

lines = ["Plan (local view, refreshed from GitHub, do not edit)",
         "Last refreshed: %s" % stamp, ""]

# `(ready)` marks only a ready piece that has been sized. The commands that read
# this file name a piece to build only when it carries that mark. `(bug)` marks
# a repair in whichever column it sits.
def state_note(issue):
    marks = []
    if "type:bug" in labels(issue):
        marks.append("(bug)")
    if column(issue) == "ready" and not still_a_note(issue):
        marks.append("(ready)")
    return " ".join(marks)

# A piece held up by another names it, whichever column it sits in.
def held_note(issue):
    names = blockers.get(issue["number"])
    return "(needs %s)" % names if names else ""

# Under Needs attention the line names what is wrong and nothing else. A
# `(ready)` mark there would read as a piece to build.
def render(heading, group, note, marked=True, extra=()):
    if not group and not extra:
        return
    lines.append(heading)
    for text in extra:
        lines.append("  %s" % text)
    for issue in group:
        who = ", ".join(a["login"] for a in issue.get("assignees", []))
        mark = state_note(issue) if marked else ""
        suffix = " ".join(p for p in (note(issue), mark) if p)
        head = "  #%-4s %s" % (issue["number"], issue["title"])
        if who:
            head += "   (%s)" % who
        if suffix:
            head += "   %s" % suffix
        lines.append(head)
        lines.append("       %s" % issue["html_url"])
    lines.append("")

# The areas a piece changes, from its Touches line: one bare line,
# `Touches: <area>, <area>`, or the line under a `## Touches` or `### Touches`
# heading, as on a piece opened with the GitHub form. Backticks and a closing
# full stop are trimmed in any order, and names are compared without regard to
# capitals. None means the piece has no Touches line, so nothing says what it
# changes.
def touches(issue):
    under_heading = False
    for line in body_lines(issue):
        if line.lower().startswith("touches:"):
            text = line[len("touches:"):]
        elif heading(line, "touches"):
            under_heading = True
            continue
        elif under_heading and line:
            if line.startswith("#"):
                return None
            text = line
        else:
            continue
        areas = [re.sub(r"^[\s`]+|[\s`.]+$", "", a).lower()
                 for a in text.split(",")]
        areas = [a for a in areas if a and a != "_no response_"]
        return areas or None
    return None

# What the printout can read on a ready piece that decides what a run can do
# with it. The masterplan's sensitive areas are not on the piece, so /queue
# checks those itself. The marks, in the order a reader weighs them:
#   (needs you)        a `## Waiting on you` step other than `try it`
#   (not ready)        its `## Readiness` section's first line says Not ready
#   (not yet checked)  it has no `## Readiness` section
#   (try it)           a `Waiting on you: try it` line
def verdict_marks(issue):
    body = body_lines(issue)
    marks = []
    for n, line in enumerate(body):
        if heading(line, "waiting on you"):
            step = next((l for l in body[n + 1:] if l), "")
            if step and not step.startswith("#") \
                    and step.lower().rstrip(".") != "try it":
                marks.append("needs you")
            break
    readiness = None
    for n, line in enumerate(body):
        if heading(line, "readiness"):
            readiness = next((l for l in body[n + 1:] if l), "")
            break
    if readiness is None or readiness.startswith("#") or not readiness:
        marks.append("not yet checked")
    elif re.search(r"\bnot ready\b", readiness, re.I):
        marks.append("not ready")
    elif not re.search(r"\bready\b", readiness, re.I):
        marks.append("not yet checked")
    if any(re.match(r"^waiting on you:\s*try it\.?$", l, re.I) for l in body):
        marks.append("try it")
    return marks

# A run cannot take a piece that needs the person or is not ready.
def run_cannot_take(issue):
    return bool({"needs you", "not ready"} & set(verdict_marks(issue)))

# The plan a run would follow: every piece under To build, and every held-up
# piece whose open blockers are all in the plan, found again and again until
# nothing more joins. A piece whose chain reaches a blocker outside the plan
# waits its turn.
by_number = {i["number"]: i for i in issues}
in_plan = {i["number"] for i in columns["ready"]}
joined = True
while joined:
    joined = False
    for issue in held_up:
        n = issue["number"]
        pairs = blocked_by.get(n, [])
        if n not in in_plan and pairs and all(b in in_plan for b, _ in pairs):
            in_plan.add(n)
            joined = True

# A piece in the plan that stacks on a piece the run cannot take waits for it,
# and says why: the base's own reason, or what the base itself waits for.
def waits_for(issue, seen=()):
    n = issue["number"]
    for b, title in blocked_by.get(n, []):
        base = by_number.get(b)
        if base is None or b in seen:
            continue
        if run_cannot_take(base):
            why = ("needs you" if "needs you" in verdict_marks(base)
                   else "is not ready")
            return "waits for %s, which %s" % (title, why)
        deeper = waits_for(base, seen + (n,))
        if deeper:
            return "waits for %s, which %s" % (title, deeper)
    return ""

def marks_text(issue):
    return " ".join("(%s)" % m for m in verdict_marks(issue))

def to_build_note(issue):
    return marks_text(issue)

def held_up_note(issue):
    parts = [held_note(issue)]
    if issue["number"] in in_plan:
        parts.append("(in the plan)")
        wait = waits_for(issue)
        if wait:
            parts.append("(%s)" % wait)
    parts.append(marks_text(issue))
    return " ".join(p for p in parts if p)

# Which pieces free to build can go together. Two pieces share a group only
# when no area on their Touches lines matches, so the pieces of one group
# can be built at the same time in any order. Two pieces that pass alone can
# still fail together, so each still merges one at a time, brought up to date
# with main and checked again first. Pieces are placed in number
# order, each in the first group it clashes with nothing in. A piece with no
# Touches line goes alone, because nothing says what it would change.
def go_together(group):
    placed = []
    for issue in group:
        areas = touches(issue)
        if areas is not None:
            for members in placed:
                if members[0][1] is None:
                    continue
                if not any(set(areas) & set(a) for _, a in members):
                    members.append((issue, areas))
                    break
            else:
                placed.append([(issue, areas)])
        else:
            placed.append([(issue, None)])
    return placed

def render_groups(group):
    if not group:
        return
    lines.append("Go together")
    for n, members in enumerate(go_together(group), 1):
        lines.append("  Group %d" % n)
        for issue, areas in members:
            note = ("(touches %s)" % ", ".join(areas) if areas is not None
                    else "(Touches unknown, so it goes alone)")
            lines.append("    #%-4s %s   %s" % (issue["number"], issue["title"], note))
    lines.append("")

notes_by_number = {i["number"]: n for i, n in needs_attention}
render("Needs attention", [i for i, _ in needs_attention],
       lambda i: notes_by_number[i["number"]], marked=False, extra=general)
for name in SUB_STATES:
    render("Shaping: " + name, columns["Shaping: " + name], held_note)
render("To build", columns["ready"], to_build_note)
render_groups(columns["ready"])
render("Held up", held_up, held_up_note)
render("Building", columns["Building"], held_note)
for _, name in REVIEWS:
    render(name, columns[name], held_note)
render("Made of parts", parents,
       lambda i: "(%d of %d parts done, build the parts)" % (sub_summary(i)[1], sub_summary(i)[0]))

notes = [i for i in issues if still_a_note(i)]
if notes:
    if len(notes) == 1:
        lines.append("1 entry is still a note rather than a piece, "
                     "so it needs a few questions before building.")
    else:
        lines.append("%d entries are still notes rather than pieces, "
                     "so they need a few questions before building." % len(notes))
    lines.append("")

if not issues:
    lines.append("Nothing open. The list has run dry.")
    lines.append("")

open(out, "w").write("\n".join(lines) + "\n")
print("plan-refresh: wrote %s from %d open pieces" % (out, len(issues)))
PY
