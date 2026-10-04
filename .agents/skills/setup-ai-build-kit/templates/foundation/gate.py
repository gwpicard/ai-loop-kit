#!/usr/bin/env python3
"""gate.py: the one way a piece changes state.

Each open piece carries one state label, and a state that has sub-labels
carries one of those. This script is the only thing that moves them. It reads
the piece, checks the condition for the move, writes the new labels and takes
the old ones off in one call, and refuses when the condition fails. A refusal
says what failed and the next thing to do, as a command.

A person can still change a label on GitHub. The person outranks the gate, so
`report` names what it finds and never puts it back.

Commands:
  gate.py labels
  gate.py capture --title <title> --body-file <file>
  gate.py capture <number>
  gate.py move <number> <target> [--run <name>] [--assignee <login>]
                                 [--reason <text>] [--withdrawn-by <number>]
  gate.py drop <number> --reason <text>
  gate.py tidy
  gate.py report

A target is a sub-state (raw, research, clarify, prototype, spec, check) or a
state (shaping, ready, building, in-review), with or without its prefix.

It talks to GitHub through the GitHub command-line tool already signed in on
this computer, and writes a run's piece status into
.agents/runs/<name>/run.json in the project's main folder.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, NoReturn, Optional, Sequence, Tuple

# --- the label set -------------------------------------------------------

STATES = ["state:shaping", "state:ready", "state:building", "state:in-review"]
SUB_STATES = ["raw", "research", "clarify", "prototype", "spec", "check"]
SHAPING = ["shaping:" + name for name in SUB_STATES]
REVIEW = ["review:auto", "review:person"]
TYPES = ["type:feature", "type:bug", "type:chore"]
LOOPS = ["loop:fix", "loop:build", "loop:goal", "loop:gauntlet"]
SUBJECTS = ["visual", "how it works", "data", "accounts and permissions", "finance",
            "external service", "background automation"]

COLOURS = {"state": "0E8A16", "shaping": "FBCA04", "review": "5319E7",
           "type": "1D76DB", "loop": "C5DEF5", "subject": "EDEDED"}

DESCRIPTIONS = {
    "state:shaping": "Not ready to build yet",
    "state:ready": "Passed the ready gate; can be built with nobody there",
    "state:building": "A run is building it",
    "state:in-review": "Built, every check green, not yet on main",
    "shaping:raw": "Captured in the person's words, not looked at yet",
    "shaping:research": "Waiting on a fact from outside",
    "shaping:clarify": "Waiting on a decision only the person makes",
    "shaping:prototype": "Waiting on a decision the person has to see first",
    "shaping:spec": "No question left; the contract is being written",
    "shaping:check": "Waiting on the readiness check",
    "review:auto": "Waiting on the automatic review",
    "review:person": "Waiting on the person's review",
    "type:feature": "Something new the tool does",
    "type:bug": "The tool does not do what it promised",
    "type:chore": "Upkeep nobody would notice in the tool",
    "loop:fix": "Built in the fix loop",
    "loop:build": "Built in the build loop",
    "loop:goal": "Built in a loop towards a number",
    "loop:gauntlet": "Built until a blind critic prefers it",
}

# The labels of AI Build Kit's model. The report names them and moves nothing.
OLD_MODEL = ["idea", "shaping", "ready", "building", "to check", "parked", "blocked",
             "broken", "needs-clarification", "needs-prototype", "needs-research"]

# The labels only this script writes on an open piece.
FAMILIES = ("state:", "shaping:", "review:")

ASKING = ["shaping:research", "shaping:clarify", "shaping:prototype"]

# --- the transition table ------------------------------------------------
#
# One row for each move the gate makes: where the piece is, where it goes, and
# the name of the condition checked. The rehearsal reads this list too, so a
# row added here and not tried there fails the rehearsal.

TRANSITIONS: List[Tuple[str, str, str]] = []
for _target in ASKING:
    TRANSITIONS.append(("shaping:raw", _target, "triaged with a question"))
TRANSITIONS.append(("shaping:raw", "shaping:spec", "triaged"))
for _origin in ASKING:
    for _target in ASKING + ["shaping:spec"]:
        if _target != _origin:
            TRANSITIONS.append((_origin, _target, "answered"))
TRANSITIONS.append(("shaping:spec", "shaping:check", "none"))
for _target in ASKING:
    TRANSITIONS.append(("shaping:spec", _target, "new question"))
TRANSITIONS.append(("shaping:check", "state:ready", "readiness says ready"))
for _target in ["shaping:spec"] + ASKING:
    TRANSITIONS.append(("shaping:check", _target, "readiness says not ready"))
TRANSITIONS.append(("state:ready", "state:building", "claim"))
TRANSITIONS.append(("state:building", "state:in-review", "pull request"))
for _origin in ("state:building", "state:in-review"):
    for _target in ("shaping:clarify", "shaping:research", "shaping:spec"):
        TRANSITIONS.append((_origin, _target, "kickback"))
TRANSITIONS.append(("state:in-review", "state:building", "defect"))
for _target in ("shaping:clarify", "shaping:research", "shaping:prototype", "shaping:spec"):
    TRANSITIONS.append(("state:ready", _target, "pulled back"))
TRANSITIONS.append(("state:building", "state:ready", "given back"))
TRANSITIONS.append(("state:in-review", "state:ready", "given back"))

# The run status each move writes when a run is named.
RUN_STATUS = {"state:building": "building", "state:in-review": "integrated",
              "state:ready": "withdrawn", "state:shaping": "kicked back"}

# The section that records a sub-state's answer.
ANSWER_SECTION = {"research": "Research", "clarify": "Decided", "prototype": "Decided"}

MARKER = re.compile(r"^<!-- loop:gate sub-state=([a-z-]+) since=(\S+) answer=([0-9a-f]*) -->\s*$")


# --- how the gate speaks -------------------------------------------------

class Refused(Exception):
    """A condition failed. Carries what failed and the next allowed action."""

    def __init__(self, what: str, next_step: str) -> None:
        super().__init__(what)
        self.what = what
        self.next_step = next_step


class Unreachable(Exception):
    """GitHub did not answer, or answered with an error the gate cannot act on.

    The message is the whole line the person sees. detail is GitHub's own first
    line, kept so a caller can say what it was doing when the call failed.
    """

    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.detail = detail or message


def say(line: str) -> None:
    print(line)


def refuse(what: str, next_step: str) -> NoReturn:
    raise Refused(what, next_step)


# --- talking to GitHub ---------------------------------------------------

def gh(args: Sequence[str], stdin: Optional[str] = None) -> str:
    try:
        done = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True)
    except OSError as error:
        raise Unreachable("the GitHub command-line tool could not be started, so nothing "
                          "changed (%s)" % error, str(error))
    if done.returncode != 0:
        first = next((line.strip() for line in done.stderr.splitlines() if line.strip()),
                     "no message")
        raise Unreachable("GitHub did not answer, so nothing changed (%s)" % first, first)
    return done.stdout


def gh_json(args: Sequence[str]) -> Any:
    text = gh(args)
    decoder = json.JSONDecoder()
    values: List[Any] = []
    position = 0
    text = text.strip()
    # A paginated answer is several JSON arrays one after another.
    while position < len(text):
        value, position = decoder.raw_decode(text, position)
        values.append(value)
        while position < len(text) and text[position].isspace():
            position += 1
    if len(values) == 1:
        return values[0]
    joined: List[Any] = []
    for value in values:
        joined.extend(value if isinstance(value, list) else [value])
    return joined


def not_found(message: str) -> bool:
    return "404" in message or "Not Found" in message or "Could not resolve" in message


def read_issue(number: int) -> Dict[str, Any]:
    """The piece as GitHub holds it now: labels, assignees, body, parts."""
    try:
        data = gh_json(["api", "repos/{owner}/{repo}/issues/%d" % number])
    except Unreachable as error:
        if not_found(error.detail):
            refuse("#%d does not exist in this repository" % number, "gate.py report")
        raise
    if not isinstance(data, dict):
        raise Unreachable("GitHub returned something that is not an issue, so nothing changed")
    if data.get("pull_request"):
        refuse("#%d is a pull request, not a piece" % number, "gate.py report")
    return data


def label_names(issue: Dict[str, Any]) -> List[str]:
    names = []
    for label in issue.get("labels", []):
        names.append(label["name"] if isinstance(label, dict) else str(label))
    return names


def assignee_logins(issue: Dict[str, Any]) -> List[str]:
    return [a["login"] if isinstance(a, dict) else str(a) for a in issue.get("assignees", [])]


def is_open(issue: Dict[str, Any]) -> bool:
    return str(issue.get("state", "")).lower() == "open"


def open_parts(issue: Dict[str, Any]) -> int:
    summary = issue.get("sub_issues_summary") or {}
    return int(summary.get("total", 0)) - int(summary.get("completed", 0))


def kit_labels(names: Sequence[str]) -> List[str]:
    return sorted(n for n in names if n.startswith(FAMILIES))


def edit_issue(number: int, add: Sequence[str], remove: Sequence[str],
               body: Optional[str] = None, add_assignee: Optional[str] = None,
               remove_assignees: Sequence[str] = ()) -> None:
    """Every change to a piece in one call, so the labels never sit half moved."""
    args = ["issue", "edit", str(number)]
    if add:
        args += ["--add-label", ",".join(add)]
    if remove:
        args += ["--remove-label", ",".join(remove)]
    if add_assignee:
        args += ["--add-assignee", add_assignee]
    if remove_assignees:
        args += ["--remove-assignee", ",".join(remove_assignees)]
    if body is not None:
        args += ["--body-file", "-"]
    gh(args, stdin=body)


# --- reading a piece's body ----------------------------------------------

def section(body: str, heading: str, last: bool = False) -> Optional[str]:
    """The text under a "## heading", or None when the piece has no such section.

    A heading inside a fenced code block does not count. With last=True only
    the last such section is read, as for Readiness, which replaces any earlier
    one.
    """
    found: List[List[str]] = []
    current: Optional[List[str]] = None
    fence = False
    for line in body.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        if not fence and re.match(r"^#{1,2}\s", line):
            current = None
            if line[2:].strip().lower() == heading.lower() and line.startswith("## "):
                current = []
                found.append(current)
            continue
        if MARKER.match(line):
            current = None
            continue
        if current is not None:
            current.append(line)
    if not found:
        return None
    chosen = found[-1:] if last else found
    return "\n".join("\n".join(part) for part in chosen).strip()


def digest(text: Optional[str]) -> str:
    normal = "\n".join(line.rstrip() for line in (text or "").strip().splitlines())
    return hashlib.sha256(normal.encode("utf-8")).hexdigest()[:12]


def read_marker(body: str) -> Optional[Tuple[str, str]]:
    """The marker's sub-state and answer hash, from the last marker line."""
    found = None
    for line in body.splitlines():
        match = MARKER.match(line)
        if match:
            found = (match.group(1), match.group(3))
    return found


def with_marker(body: str, sub_state: str) -> str:
    """The body with one marker as its last line, and nothing else changed."""
    kept = [line for line in body.splitlines() if not MARKER.match(line)]
    text = "\n".join(kept).rstrip()
    heading = ANSWER_SECTION.get(sub_state)
    answer = digest(section(text, heading)) if heading else digest("")
    marker = "<!-- loop:gate sub-state=%s since=%s answer=%s -->" % (
        sub_state, datetime.date.today().isoformat(), answer)
    return (text + "\n\n" if text else "") + marker + "\n"


def questions_in(text: Optional[str]) -> int:
    return (text or "").count("?")


def readiness(body: str) -> Tuple[Optional[str], int]:
    """The Readiness verdict (Ready, Not ready or None) and its BLOCKING lines."""
    text = section(body, "Readiness", last=True)
    if text is None:
        return None, 0
    lines = [line for line in text.splitlines() if line.strip()]
    blocking = sum(1 for line in lines if "BLOCKING" in line)
    verdict: Optional[str] = None
    if lines:
        head = lines[0]
        if re.search(r"\bnot ready\b", head, re.IGNORECASE):
            verdict = "Not ready"
        elif re.search(r"\bready\b", head, re.IGNORECASE):
            verdict = "Ready"
    return verdict, blocking


# --- where a piece stands ------------------------------------------------

def position(number: int, names: Sequence[str]) -> str:
    """The one place the piece stands, or a refusal naming what is wrong."""
    states = [n for n in names if n.startswith("state:")]
    subs = [n for n in names if n.startswith("shaping:")]
    reviews = [n for n in names if n.startswith("review:")]
    report_next = "fix the labels on GitHub, then run: gate.py report"
    if not states:
        refuse("#%d carries no state" % number, "gate.py capture %d" % number)
    if len(states) > 1:
        refuse("#%d carries %d states: %s" % (number, len(states), " and ".join(states)),
               "take all but one off on GitHub, then run: gate.py report")
    state = states[0]
    if state not in STATES:
        refuse("#%d carries %s, which is not a state the kit uses" % (number, state), report_next)
    if state == "state:shaping":
        if len(subs) != 1 or subs[0] not in SHAPING:
            refuse("#%d is in state:shaping with %s" % (
                number, " and ".join(subs) if subs else "no shaping sub-label"), report_next)
        if reviews:
            refuse("#%d carries %s beside state:shaping" % (number, reviews[0]), report_next)
        return subs[0]
    if subs:
        refuse("#%d carries %s beside %s" % (number, subs[0], state), report_next)
    if reviews and state != "state:in-review":
        refuse("#%d carries %s beside %s" % (number, reviews[0], state), report_next)
    if len(reviews) > 1:
        refuse("#%d carries two review labels: %s" % (number, " and ".join(reviews)),
               report_next)
    return state


def canonical_target(word: str) -> str:
    bare = word.strip()
    for prefix in ("state:", "shaping:"):
        if bare.startswith(prefix):
            bare = bare[len(prefix):]
            break
    if bare in SUB_STATES:
        if word.startswith("state:"):
            return ""
        return "shaping:" + bare
    if bare in ("shaping", "ready", "building", "in-review"):
        if word.startswith("shaping:"):
            return ""
        return "state:" + bare
    return ""


def labels_for(place: str) -> List[str]:
    if place.startswith("shaping:"):
        return ["state:shaping", place]
    if place == "state:in-review":
        return ["state:in-review", "review:person"]
    return [place]


def short(place: str) -> str:
    return place.split(":", 1)[1]


# --- the run record ------------------------------------------------------

def main_folder() -> str:
    """The project's main folder, where a run's record lives, even from a worktree."""
    try:
        done = subprocess.run(["git", "worktree", "list", "--porcelain"],
                              capture_output=True, text=True)
        if done.returncode == 0:
            for line in done.stdout.splitlines():
                if line.startswith("worktree "):
                    return line[len("worktree "):]
    except OSError:
        pass
    return os.getcwd()


def run_path(name: str) -> str:
    return os.path.join(main_folder(), ".agents", "runs", name, "run.json")


def load_run(name: str) -> Dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        refuse("'%s' is not a run name: use letters, numbers, dots, dashes" % name,
               "gate.py move <number> <target> --run <name>")
    path = run_path(name)
    if not os.path.exists(path):
        return {"pieces": []}
    relative = os.path.relpath(path, main_folder())
    try:
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError) as error:
        refuse("the run record %s cannot be read as JSON (%s), and was left as it is"
               % (relative, error), "repair or move %s, then run the same command again" % relative)
    if (not isinstance(record, dict) or not isinstance(record.get("pieces", []), list)
            or not all(isinstance(p, dict) for p in record.get("pieces", []))):
        refuse("the run record %s does not hold a list of pieces, and was left as it is"
               % relative, "repair or move %s, then run the same command again" % relative)
    record.setdefault("pieces", [])
    return record


def run_entry(record: Dict[str, Any], number: int) -> Optional[Dict[str, Any]]:
    pieces: List[Dict[str, Any]] = record["pieces"]
    for piece in pieces:
        if piece.get("number") == number:
            return piece
    return None


def save_run(name: str, record: Dict[str, Any], number: int, status: str) -> None:
    entry = run_entry(record, number)
    if entry is None:
        record["pieces"].append({"number": number, "status": status})
    else:
        entry["status"] = status
    path = run_path(name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        json.dump(record, out, indent=2)
        out.write("\n")
    os.replace(temporary, path)


# --- the conditions ------------------------------------------------------

def check_condition(condition: str, number: int, origin: str, target: str,
                    issue: Dict[str, Any], options: Dict[str, str],
                    record: Optional[Dict[str, Any]]) -> None:
    body = str(issue.get("body") or "")
    names = label_names(issue)
    move = "gate.py move %d %s" % (number, short(target))

    if condition in ("triaged", "triaged with a question"):
        types = [n for n in names if n.startswith("type:")]
        if len(types) != 1:
            refuse("#%d carries %s; leaving raw needs exactly one type label"
                   % (number, " and ".join(types) if types else "no type label"),
                   "give it one of type:feature, type:bug or type:chore, then run: " + move)
    if condition in ("triaged with a question", "new question"):
        question = section(body, "Open question")
        if not question or questions_in(question) != 1:
            refuse("#%d has %s; %s needs an ## Open question section holding one question"
                   % (number, "no ## Open question section" if question is None
                      else "%d questions under ## Open question" % questions_in(question),
                      short(target)),
                   "write the one question under ## Open question, then run: " + move)

    if condition == "answered":
        sub = short(origin)
        heading = ANSWER_SECTION[sub]
        answer = section(body, heading)
        marker = read_marker(body)
        entered = marker[1] if marker and marker[0] == sub else digest("")
        if not answer or digest(answer) == entered:
            refuse("the answer under ## %s has not changed since #%d entered %s"
                   % (heading, number, origin),
                   "write the answer under ## %s, then run: %s" % (heading, move))
        if sub == "research":
            claims = [line for line in answer.splitlines()
                      if re.match(r"^\s*[-*]\s+\S", line)]
            unsourced = [c for c in claims
                         if not re.search(r"https?://|source:", c, re.IGNORECASE)]
            if not claims or unsourced:
                refuse("#%d has a claim under ## Research with no source" % number
                       if claims else "#%d lists no claim under ## Research" % number,
                       "write each claim as a list item naming its source, then run: " + move)

    if condition == "readiness says ready":
        verdict, blocking = readiness(body)
        if verdict != "Ready" or blocking:
            refuse("#%d's ## Readiness section says %s" % (
                number, "nothing" if verdict is None else
                "%s with %d BLOCKING line(s)" % (verdict, blocking)),
                "run the readiness check and write its ## Readiness section, then run: " + move)
    if condition == "readiness says not ready":
        verdict, blocking = readiness(body)
        if verdict != "Not ready" or not blocking:
            refuse("going back from check needs a ## Readiness section saying Not ready "
                   "with a BLOCKING line, and #%d's says %s" % (
                       number, "nothing" if verdict is None else
                       "%s with %d BLOCKING line(s)" % (verdict, blocking)),
                   "gate.py move %d ready" % number if verdict == "Ready" and not blocking
                   else "run the readiness check, then run: " + move)

    if condition == "claim":
        if not options.get("assignee") and not options.get("run"):
            refuse("a claim needs an assignee or a run",
                   "gate.py move %d building --assignee @me" % number)
        earlier = set()
        if record is not None:
            earlier = {p.get("number") for p in record["pieces"] if p.get("number") != number}
        blockers = gh_json(["api",
                            "repos/{owner}/{repo}/issues/%d/dependencies/blocked_by" % number])
        waiting = [b for b in blockers if isinstance(b, dict)
                   and str(b.get("state", "")).lower() == "open"
                   and b.get("number") not in earlier]
        if waiting:
            first = waiting[0]
            refuse("#%d waits for #%s %s, which is still open and not claimed earlier in this run"
                   % (number, first.get("number"), first.get("title", "")),
                   "build #%s first, or claim it earlier in the same run with: "
                   "gate.py move %s building --run <name>" % (first.get("number"),
                                                              first.get("number")))

    if condition == "pull request":
        pulls = gh_json(["pr", "list", "--state", "open", "--limit", "200",
                         "--json", "number,body"])
        closing = re.compile(r"\bcloses\s+#%d\b" % number, re.IGNORECASE)
        if not any(closing.search(str(p.get("body") or "")) for p in pulls
                   if isinstance(p, dict)):
            refuse("no open pull request says Closes #%d" % number,
                   "open the pull request with Closes #%d in its body, then run: %s"
                   % (number, move))

    if condition == "kickback":
        kickback = section(body, "Kickback")
        if not kickback:
            refuse("#%d has no ## Kickback section saying what happened" % number,
                   "write what happened, what was tried and the decision needed under "
                   "## Kickback, then run: " + move)

    if condition == "defect":
        if not options.get("reason", "").strip():
            refuse("a return to building needs a --reason naming the defect",
                   "gate.py move %d building --reason \"<the defect>\"" % number)

    if condition == "pulled back":
        if assignee_logins(issue):
            refuse("#%d is claimed by %s" % (number, ", ".join(assignee_logins(issue))),
                   "unassign it on GitHub once nobody is building it, then run: " + move)

    if condition == "given back":
        run = options.get("run")
        withdrawn_by = options.get("withdrawn-by")
        if run:
            entry = run_entry(record, number) if record is not None else None
            if entry is None or entry.get("status") not in ("building", "checking", "integrated"):
                refuse("#%d is not listed as building, checking or integrated in run %s"
                       % (number, run),
                       "gate.py move %d ready --withdrawn-by <the piece that was kicked back>"
                       % number)
        elif withdrawn_by:
            other = number_from(withdrawn_by)
            blocking_piece = read_issue(other)
            other_names = label_names(blocking_piece)
            blockers = gh_json(["api",
                                "repos/{owner}/{repo}/issues/%d/dependencies/blocked_by" % number])
            listed = any(isinstance(b, dict) and b.get("number") == other for b in blockers)
            if ("state:shaping" not in other_names
                    or not section(str(blocking_piece.get("body") or ""), "Kickback")
                    or not listed):
                refuse("#%d can be withdrawn by #%d only when #%d is in state:shaping with a "
                       "## Kickback section and is in #%d's blocked-by list"
                       % (number, other, other, number),
                       "gate.py move %d ready --run <name>" % number)
        else:
            refuse("a piece goes back to ready only with --run <name> or --withdrawn-by <number>",
                   "gate.py move %d ready --run <name>" % number)


def number_from(text: str) -> int:
    cleaned = text.strip().lstrip("#")
    if not cleaned.isdigit() or int(cleaned) <= 0:
        refuse("'%s' is not an issue number" % text, "gate.py report")
    return int(cleaned)


# --- the commands --------------------------------------------------------

def command_move(arguments: List[str], options: Dict[str, str]) -> None:
    if len(arguments) != 2:
        refuse("move needs a piece and a target", "gate.py move <number> <target>")
    number = number_from(arguments[0])
    target = canonical_target(arguments[1])
    if not target:
        refuse("'%s' is not a state or sub-state" % arguments[1],
               "gate.py move %d <raw|research|clarify|prototype|spec|check|ready|building|"
               "in-review>" % number)
    record = load_run(options["run"]) if options.get("run") else None

    issue = read_issue(number)
    if not is_open(issue):
        refuse("#%d is closed" % number, "reopen it on GitHub, then run: gate.py capture %d"
               % number)
    if open_parts(issue):
        refuse("#%d has open parts, and its parts carry the states, not it" % number,
               "gate.py report")
    names = label_names(issue)
    origin = position(number, names)

    if target == "state:shaping":
        if origin != "state:ready":
            refuse("a move back to shaping from %s names its sub-state" % origin,
                   "gate.py move %d <clarify|research|spec>" % number)
        target = "shaping:clarify"

    row = next((r for r in TRANSITIONS if r[0] == origin and r[1] == target), None)
    if row is None:
        allowed = [short(r[1]) for r in TRANSITIONS if r[0] == origin]
        refuse("the gate makes no move from %s to %s" % (origin, target),
               "gate.py move %d <%s>" % (number, "|".join(allowed)))
    check_condition(row[2], number, origin, target, issue, options, record)

    # Read the piece again just before writing. Another session may have moved
    # it since the first read, and a move on stale labels would undo theirs.
    again = read_issue(number)
    if kit_labels(label_names(again)) != kit_labels(names):
        refuse("#%d changed while this move was being checked: it now carries %s"
               % (number, ", ".join(kit_labels(label_names(again))) or "no state"),
               "gate.py report")

    now = kit_labels(label_names(again))
    wanted = labels_for(target)
    add = [n for n in wanted if n not in now]
    remove = [n for n in now if n not in wanted]
    body = None
    if target.startswith("shaping:"):
        body = with_marker(str(again.get("body") or ""), short(target))
    add_assignee = options.get("assignee") if target == "state:building" and \
        origin == "state:ready" else None
    remove_assignees: List[str] = []
    if target == "state:ready" and origin in ("state:building", "state:in-review"):
        remove_assignees = assignee_logins(again)
    try:
        edit_issue(number, add, remove, body, add_assignee, remove_assignees)
    except Unreachable as error:
        raise Unreachable("the labels on #%d could not be written, so nothing changed (%s)"
                          % (number, error.detail), error.detail)

    done = "#%d moved from %s to %s" % (number, origin, target)
    if record is not None:
        status = RUN_STATUS["state:shaping" if target.startswith("shaping:") else target]
        try:
            save_run(options["run"], record, number, status)
        except OSError as error:
            print("%s, but the run record %s could not be written (%s)"
                  % (done, os.path.relpath(run_path(options["run"]), main_folder()), error))
            sys.exit(2)
        done += ", and run %s records it as %s" % (options["run"], status)

    if row[2] == "defect":
        try:
            gh(["issue", "comment", str(number), "--body-file", "-"],
               stdin="Back to building: %s\n" % options["reason"].strip())
        except Unreachable as error:
            done += "; the comment naming the defect was not posted (%s)" % error.detail
    say(done)


def command_capture(arguments: List[str], options: Dict[str, str]) -> None:
    if arguments:
        if len(arguments) != 1:
            refuse("capture takes one issue number", "gate.py capture <number>")
        number = number_from(arguments[0])
        issue = read_issue(number)
        if not is_open(issue):
            refuse("#%d is closed" % number,
                   "reopen it on GitHub, then run: gate.py capture %d" % number)
        if open_parts(issue):
            refuse("#%d has open parts, and its parts carry the states, not it" % number,
                   "gate.py report")
        names = label_names(issue)
        states = [n for n in names if n.startswith("state:")]
        if states:
            refuse("#%d already carries %s" % (number, " and ".join(states)),
                   "gate.py move %d <target>" % number)
        stray = kit_labels(names)
        if stray:
            refuse("#%d carries %s with no state" % (number, ", ".join(stray)),
                   "take it off on GitHub, then run: gate.py capture %d" % number)
        again = read_issue(number)
        if kit_labels(label_names(again)) != kit_labels(names):
            refuse("#%d changed while it was being captured" % number, "gate.py report")
        try:
            edit_issue(number, ["state:shaping", "shaping:raw"], [],
                       with_marker(str(again.get("body") or ""), "raw"))
        except Unreachable as error:
            raise Unreachable("the labels on #%d could not be written, so nothing changed (%s)"
                              % (number, error.detail), error.detail)
        say("#%d captured in shaping:raw" % number)
        return

    title = options.get("title", "").strip()
    path = options.get("body-file", "")
    if not title or not path:
        refuse("capture needs a title and a file holding the person's words",
               "gate.py capture --title \"<title>\" --body-file <file>")
    try:
        with open(path, encoding="utf-8") as handle:
            words = handle.read()
    except OSError as error:
        refuse("the file %s cannot be read (%s)" % (path, error),
               "gate.py capture --title \"%s\" --body-file <file>" % title)
    try:
        out = gh(["issue", "create", "--title", title, "--body-file", "-",
                  "--label", "state:shaping,shaping:raw"], stdin=with_marker(words, "raw"))
    except Unreachable as error:
        raise Unreachable("the piece could not be opened, so nothing changed (%s)"
                          % error.detail, error.detail)
    match = re.search(r"/issues/(\d+)", out)
    say("#%s captured in shaping:raw: %s" % (match.group(1) if match else "?", title))


def command_drop(arguments: List[str], options: Dict[str, str]) -> None:
    if len(arguments) != 1:
        refuse("drop takes one issue number", "gate.py drop <number> --reason \"<why>\"")
    number = number_from(arguments[0])
    reason = options.get("reason", "").strip()
    if not reason:
        refuse("a piece is dropped only with a --reason",
               "gate.py drop %d --reason \"<why nobody will build it>\"" % number)
    issue = read_issue(number)
    if not is_open(issue):
        refuse("#%d is already closed" % number, "gate.py tidy")
    try:
        gh(["issue", "close", str(number), "--reason", "not planned",
            "--comment", "Closed as not planned: %s" % reason])
    except Unreachable as error:
        raise Unreachable("#%d could not be closed, so nothing changed (%s)"
                          % (number, error.detail), error.detail)
    labels = kit_labels(label_names(issue))
    if labels:
        try:
            edit_issue(number, [], labels)
        except Unreachable as error:
            print("#%d closed as not planned, but its state labels could not be taken off (%s); "
                  "next: gate.py tidy" % (number, error.detail))
            sys.exit(2)
    say("#%d closed as not planned, with its reason, and its state labels taken off" % number)


def command_tidy(arguments: List[str], options: Dict[str, str]) -> None:
    found: Dict[int, List[str]] = {}
    for name in STATES + SHAPING + REVIEW:
        listed = gh_json(["issue", "list", "--state", "closed", "--label", name,
                          "--limit", "1000", "--json", "number,labels"])
        for item in listed:
            if str(item.get("state", "closed")).lower() != "closed":
                continue
            labels = kit_labels(label_names(item))
            if labels:
                found[int(item["number"])] = labels
    for number, labels in sorted(found.items()):
        try:
            edit_issue(number, [], labels)
        except Unreachable as error:
            raise Unreachable("tidy stopped at #%d, whose labels could not be taken off (%s)"
                              % (number, error.detail), error.detail)
    if found:
        say("tidy took the state labels off %d closed piece(s)" % len(found))
    else:
        say("tidy found no closed piece carrying a state label")


def findings_for(item: Dict[str, Any]) -> List[str]:
    names = label_names(item)
    states = [n for n in names if n.startswith("state:")]
    subs = [n for n in names if n.startswith("shaping:")]
    reviews = [n for n in names if n.startswith("review:")]
    found: List[str] = []
    if open_parts(item):
        carried = kit_labels(names)
        if carried:
            found.append("a parent carries %s; its parts carry the states" % ", ".join(carried))
    elif not states:
        found.append("no state")
    elif len(states) > 1:
        found.append("%d states: %s" % (len(states), " and ".join(states)))
    else:
        state = states[0]
        if state not in STATES:
            found.append("%s is not a state the kit uses" % state)
        elif state == "state:shaping":
            if len(subs) != 1:
                found.append("state:shaping with %s" % (" and ".join(subs) if subs
                                                        else "no shaping sub-label"))
            for review in reviews:
                found.append("%s beside state:shaping" % review)
        else:
            for sub in subs:
                found.append("%s beside %s" % (sub, state))
            if state == "state:in-review":
                if len(reviews) > 1:
                    found.append("two review labels: %s" % " and ".join(reviews))
                elif not reviews:
                    found.append("state:in-review with no review sub-label")
            else:
                for review in reviews:
                    found.append("%s beside %s" % (review, state))
    for name in names:
        if name in OLD_MODEL:
            found.append("carries %s, a label from AI Build Kit's model that this kit does not "
                         "use; left alone" % name)
    return found


def command_report(arguments: List[str], options: Dict[str, str]) -> None:
    listed = gh_json(["api", "repos/{owner}/{repo}/issues?state=open&per_page=100",
                      "--paginate"])
    pieces = [i for i in listed if isinstance(i, dict) and not i.get("pull_request")
              and is_open(i)]
    lines = []
    for item in sorted(pieces, key=lambda i: int(i["number"])):
        found = findings_for(item)
        if found:
            lines.append("#%s %s: %s" % (item["number"], item.get("title", ""), "; ".join(found)))
    if not lines:
        say("report: every open piece has one state and the sub-label it needs (%d open)"
            % len(pieces))
        return
    say("report: %d piece(s) need attention; nothing was changed" % len(lines))
    for line in lines:
        say(line)


def command_labels(arguments: List[str], options: Dict[str, str]) -> None:
    listed = gh_json(["label", "list", "--limit", "1000", "--json", "name"])
    have = {str(item.get("name", "")).lower() for item in listed if isinstance(item, dict)}
    wanted = STATES + SHAPING + REVIEW + TYPES + LOOPS + SUBJECTS
    made, missing = [], []
    for name in wanted:
        if name.lower() in have:
            continue
        family = name.split(":", 1)[0] if ":" in name else "subject"
        try:
            gh(["label", "create", name, "--color", COLOURS[family],
                "--description", DESCRIPTIONS.get(name, "What the piece is about: " + name)])
            made.append(name)
        except Unreachable:
            missing.append(name)
    if missing:
        say("labels: created %d; this account could not create %d, which pieces will go "
            "without until someone with write access runs gate.py labels: %s"
            % (len(made), len(missing), ", ".join(missing)))
    elif made:
        say("labels: created %d; all %d labels the kit uses are there" % (len(made), len(wanted)))
    else:
        say("labels: all %d labels the kit uses are already there" % len(wanted))


COMMANDS = {"move": command_move, "capture": command_capture, "drop": command_drop,
            "tidy": command_tidy, "report": command_report, "labels": command_labels}
OPTIONS = ("--run", "--assignee", "--reason", "--withdrawn-by", "--title", "--body-file")


def parse(argv: List[str]) -> Tuple[List[str], Dict[str, str]]:
    arguments: List[str] = []
    options: Dict[str, str] = {}
    i = 0
    while i < len(argv):
        word = argv[i]
        name = word.split("=", 1)[0]
        if name in OPTIONS:
            if "=" in word:
                options[name[2:]] = word.split("=", 1)[1]
                i += 1
                continue
            if i + 1 >= len(argv):
                refuse("%s needs a value" % word, "gate.py %s" % " ".join(argv[:i]))
            options[name[2:]] = argv[i + 1]
            i += 2
            continue
        if word.startswith("--"):
            refuse("%s is not an option the gate takes" % word, "gate.py --help")
        arguments.append(word)
        i += 1
    return arguments, options


def main(argv: List[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print((__doc__ or "").strip())
        return 0
    try:
        if not argv or argv[0] not in COMMANDS:
            refuse("'%s' is not a gate command" % (argv[0] if argv else ""),
                   "gate.py report")
        arguments, options = parse(argv[1:])
        COMMANDS[argv[0]](arguments, options)
        return 0
    except Refused as refusal:
        print("gate.py %s refused: %s" % (" ".join(argv), refusal.what), file=sys.stderr)
        print("next: " + refusal.next_step, file=sys.stderr)
        return 1
    except Unreachable as error:
        print("gate.py %s: %s" % (argv[0], error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
