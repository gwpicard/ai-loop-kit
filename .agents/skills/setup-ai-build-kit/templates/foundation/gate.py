#!/usr/bin/env python3
"""gate.py: the one way a piece changes state.

Each open piece carries one state label, and a state that has sub-labels
carries one of those. This script is the only thing that moves them. It reads
the piece, checks the condition for the move, writes the new labels and takes
the old ones off in one call, and refuses when the condition fails. A refusal
says what failed and the next thing to do, as a command.

A person can still change a label on GitHub. The person outranks the gate, so
`report` names what it finds and never puts it back. It also names the state
guard hook, .agents/hooks/state-guard.sh, when the Claude Code settings run it
and the project has no runnable copy, since nothing then stops a direct label
write.

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
from collections.abc import Sequence
from typing import Any, NoReturn

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

TRANSITIONS: list[tuple[str, str, str]] = []
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

def gh(args: Sequence[str], stdin: str | None = None) -> str:
    try:
        done = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True,
                              check=False)
    except OSError as error:
        raise Unreachable("the GitHub command-line tool could not be started, so nothing "
                          f"changed ({error})", str(error))
    if done.returncode != 0:
        first = next((line.strip() for line in done.stderr.splitlines() if line.strip()),
                     "no message")
        raise Unreachable(f"GitHub did not answer, so nothing changed ({first})", first)
    return done.stdout


def gh_json(args: Sequence[str]) -> Any:
    text = gh(args)
    decoder = json.JSONDecoder()
    values: list[Any] = []
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
    joined: list[Any] = []
    for value in values:
        joined.extend(value if isinstance(value, list) else [value])
    return joined


def not_found(message: str) -> bool:
    return "404" in message or "Not Found" in message or "Could not resolve" in message


def read_issue(number: int) -> dict[str, Any]:
    """The piece as GitHub holds it now: labels, assignees, body, parts."""
    try:
        data = gh_json(["api", f"repos/{{owner}}/{{repo}}/issues/{number}"])
    except Unreachable as error:
        if not_found(error.detail):
            refuse(f"#{number} does not exist in this repository", "gate.py report")
        raise
    if not isinstance(data, dict):
        raise Unreachable("GitHub returned something that is not an issue, so nothing changed")
    if data.get("pull_request"):
        refuse(f"#{number} is a pull request, not a piece", "gate.py report")
    return data


def label_names(issue: dict[str, Any]) -> list[str]:
    names = []
    for label in issue.get("labels", []):
        names.append(label["name"] if isinstance(label, dict) else str(label))
    return names


def assignee_logins(issue: dict[str, Any]) -> list[str]:
    return [a["login"] if isinstance(a, dict) else str(a) for a in issue.get("assignees", [])]


def is_open(issue: dict[str, Any]) -> bool:
    return str(issue.get("state", "")).lower() == "open"


def open_parts(issue: dict[str, Any]) -> int:
    summary = issue.get("sub_issues_summary") or {}
    return int(summary.get("total", 0)) - int(summary.get("completed", 0))


def kit_labels(names: Sequence[str]) -> list[str]:
    return sorted(n for n in names if n.startswith(FAMILIES))


def edit_issue(number: int, add: Sequence[str], remove: Sequence[str],
               body: str | None = None, add_assignee: str | None = None,
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

def section(body: str, heading: str, last: bool = False) -> str | None:
    """The text under a "## heading", or None when the piece has no such section.

    A heading inside a fenced code block does not count. With last=True only
    the last such section is read, as for Readiness, which replaces any earlier
    one.
    """
    found: list[list[str]] = []
    current: list[str] | None = None
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


def digest(text: str | None) -> str:
    normal = "\n".join(line.rstrip() for line in (text or "").strip().splitlines())
    return hashlib.sha256(normal.encode("utf-8")).hexdigest()[:12]


def read_marker(body: str) -> tuple[str, str] | None:
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
    since = datetime.datetime.now().astimezone().date().isoformat()
    marker = f"<!-- loop:gate sub-state={sub_state} since={since} answer={answer} -->"
    return (text + "\n\n" if text else "") + marker + "\n"


def questions_in(text: str | None) -> int:
    return (text or "").count("?")


def readiness(body: str) -> tuple[str | None, int]:
    """The Readiness verdict (Ready, Not ready or None) and its BLOCKING lines."""
    text = section(body, "Readiness", last=True)
    if text is None:
        return None, 0
    lines = [line for line in text.splitlines() if line.strip()]
    blocking = sum(1 for line in lines if "BLOCKING" in line)
    verdict: str | None = None
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
        refuse(f"#{number} carries no state", f"gate.py capture {number}")
    if len(states) > 1:
        refuse(f'#{number} carries {len(states)} states: {" and ".join(states)}',
               "take all but one off on GitHub, then run: gate.py report")
    state = states[0]
    if state not in STATES:
        refuse(f"#{number} carries {state}, which is not a state the kit uses", report_next)
    if state == "state:shaping":
        if len(subs) != 1 or subs[0] not in SHAPING:
            carried = " and ".join(subs) if subs else "no shaping sub-label"
            refuse(f"#{number} is in state:shaping with {carried}", report_next)
        if reviews:
            refuse(f"#{number} carries {reviews[0]} beside state:shaping", report_next)
        return subs[0]
    if subs:
        refuse(f"#{number} carries {subs[0]} beside {state}", report_next)
    if reviews and state != "state:in-review":
        refuse(f"#{number} carries {reviews[0]} beside {state}", report_next)
    if len(reviews) > 1:
        refuse(f'#{number} carries two review labels: {" and ".join(reviews)}',
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


def labels_for(place: str) -> list[str]:
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
                              capture_output=True, text=True, check=False)
        if done.returncode == 0:
            for line in done.stdout.splitlines():
                if line.startswith("worktree "):
                    return line[len("worktree "):]
    except OSError:
        pass
    return os.getcwd()


def run_path(name: str) -> str:
    return os.path.join(main_folder(), ".agents", "runs", name, "run.json")


def load_run(name: str) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        refuse(f"'{name}' is not a run name: use letters, numbers, dots, dashes",
               "gate.py move <number> <target> --run <name>")
    path = run_path(name)
    if not os.path.exists(path):
        return {"pieces": []}
    relative = os.path.relpath(path, main_folder())
    try:
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError) as error:
        refuse(f"the run record {relative} cannot be read as JSON ({error}), and was left "
               "as it is", f"repair or move {relative}, then run the same command again")
    if (not isinstance(record, dict) or not isinstance(record.get("pieces", []), list)
            or not all(isinstance(p, dict) for p in record.get("pieces", []))):
        refuse(f"the run record {relative} does not hold a list of pieces, and was left "
               "as it is", f"repair or move {relative}, then run the same command again")
    record.setdefault("pieces", [])
    return record


def run_entry(record: dict[str, Any], number: int) -> dict[str, Any] | None:
    pieces: list[dict[str, Any]] = record["pieces"]
    for piece in pieces:
        if piece.get("number") == number:
            return piece
    return None


def save_run(name: str, record: dict[str, Any], number: int, status: str) -> None:
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
                    issue: dict[str, Any], options: dict[str, str],
                    record: dict[str, Any] | None) -> None:
    body = str(issue.get("body") or "")
    names = label_names(issue)
    move = f"gate.py move {number} {short(target)}"

    if condition in ("triaged", "triaged with a question"):
        types = [n for n in names if n.startswith("type:")]
        if len(types) != 1:
            carried = " and ".join(types) if types else "no type label"
            refuse(f"#{number} carries {carried}; leaving raw needs exactly one type label",
                   "give it one of type:feature, type:bug or type:chore, then run: " + move)
    if condition in ("triaged with a question", "new question"):
        question = section(body, "Open question")
        if not question or questions_in(question) != 1:
            has = ("no ## Open question section" if question is None
                   else f"{questions_in(question)} questions under ## Open question")
            refuse(f"#{number} has {has}; {short(target)} needs an ## Open question "
                   "section holding one question",
                   "write the one question under ## Open question, then run: " + move)

    if condition == "answered":
        sub = short(origin)
        heading = ANSWER_SECTION[sub]
        answer = section(body, heading)
        marker = read_marker(body)
        entered = marker[1] if marker and marker[0] == sub else digest("")
        if not answer or digest(answer) == entered:
            refuse(f"the answer under ## {heading} has not changed since #{number} "
                   f"entered {origin}",
                   f"write the answer under ## {heading}, then run: {move}")
        if sub == "research":
            claims = [line for line in answer.splitlines()
                      if re.match(r"^\s*[-*]\s+\S", line)]
            unsourced = [c for c in claims
                         if not re.search(r"https?://|source:", c, re.IGNORECASE)]
            if not claims or unsourced:
                refuse(f"#{number} has a claim under ## Research with no source"
                       if claims else f"#{number} lists no claim under ## Research",
                       "write each claim as a list item naming its source, then run: " + move)

    if condition == "readiness says ready":
        verdict, blocking = readiness(body)
        if verdict != "Ready" or blocking:
            says = ("nothing" if verdict is None
                    else f"{verdict} with {blocking} BLOCKING line(s)")
            refuse(f"#{number}'s ## Readiness section says {says}",
                "run the readiness check and write its ## Readiness section, then run: " + move)
    if condition == "readiness says not ready":
        verdict, blocking = readiness(body)
        if verdict != "Not ready" or not blocking:
            says = ("nothing" if verdict is None
                    else f"{verdict} with {blocking} BLOCKING line(s)")
            refuse("going back from check needs a ## Readiness section saying Not ready "
                   f"with a BLOCKING line, and #{number}'s says {says}",
                   f"gate.py move {number} ready" if verdict == "Ready" and not blocking
                   else "run the readiness check, then run: " + move)

    if condition == "claim":
        if not options.get("assignee") and not options.get("run"):
            refuse("a claim needs an assignee or a run",
                   f"gate.py move {number} building --assignee @me")
        earlier = set()
        if record is not None:
            earlier = {p.get("number") for p in record["pieces"] if p.get("number") != number}
        blockers = gh_json(["api",
                            f"repos/{{owner}}/{{repo}}/issues/{number}/dependencies/blocked_by"])
        waiting = [b for b in blockers if isinstance(b, dict)
                   and str(b.get("state", "")).lower() == "open"
                   and b.get("number") not in earlier]
        if waiting:
            first = waiting[0]
            other = first.get("number")
            refuse(f"#{number} waits for #{other} {first.get('title', '')}, which is still "
                   "open and not claimed earlier in this run",
                   f"build #{other} first, or claim it earlier in the same run with: "
                   f"gate.py move {other} building --run <name>")

    if condition == "pull request":
        pulls = gh_json(["pr", "list", "--state", "open", "--limit", "200",
                         "--json", "number,body"])
        closing = re.compile(rf"\bcloses\s+#{number}\b", re.IGNORECASE)
        if not any(closing.search(str(p.get("body") or "")) for p in pulls
                   if isinstance(p, dict)):
            refuse(f"no open pull request says Closes #{number}",
                   f"open the pull request with Closes #{number} in its body, then run: {move}")

    if condition == "kickback":
        kickback = section(body, "Kickback")
        if not kickback:
            refuse(f"#{number} has no ## Kickback section saying what happened",
                   "write what happened, what was tried and the decision needed under "
                   "## Kickback, then run: " + move)

    if condition == "defect" and not options.get("reason", "").strip():
        refuse("a return to building needs a --reason naming the defect",
               f"gate.py move {number} building --reason \"<the defect>\"")

    if condition == "pulled back" and assignee_logins(issue):
        refuse(f'#{number} is claimed by {", ".join(assignee_logins(issue))}',
               "unassign it on GitHub once nobody is building it, then run: " + move)

    if condition == "given back":
        run = options.get("run")
        withdrawn_by = options.get("withdrawn-by")
        if run:
            entry = run_entry(record, number) if record is not None else None
            if (entry is None
                    or entry.get("status") not in ("building", "checking", "integrated")):
                refuse(f"#{number} is not listed as building, checking or integrated "
                       f"in run {run}",
                       f"gate.py move {number} ready "
                       "--withdrawn-by <the piece that was kicked back>")
        elif withdrawn_by:
            other = number_from(withdrawn_by)
            blocking_piece = read_issue(other)
            other_names = label_names(blocking_piece)
            blockers = gh_json([
                "api", f"repos/{{owner}}/{{repo}}/issues/{number}/dependencies/blocked_by"])
            listed = any(isinstance(b, dict) and b.get("number") == other for b in blockers)
            if ("state:shaping" not in other_names
                    or not section(str(blocking_piece.get("body") or ""), "Kickback")
                    or not listed):
                refuse(f"#{number} can be withdrawn by #{other} only when #{other} is in "
                       "state:shaping with a ## Kickback section and is in "
                       f"#{number}'s blocked-by list",
                       f"gate.py move {number} ready --run <name>")
        else:
            refuse("a piece goes back to ready only with --run <name> or --withdrawn-by <number>",
                   f"gate.py move {number} ready --run <name>")


def number_from(text: str) -> int:
    cleaned = text.strip().lstrip("#")
    if not cleaned.isdigit() or int(cleaned) <= 0:
        refuse(f"'{text}' is not an issue number", "gate.py report")
    return int(cleaned)


# --- the commands --------------------------------------------------------

def command_move(arguments: list[str], options: dict[str, str]) -> None:
    if len(arguments) != 2:
        refuse("move needs a piece and a target", "gate.py move <number> <target>")
    number = number_from(arguments[0])
    target = canonical_target(arguments[1])
    if not target:
        refuse(f"'{arguments[1]}' is not a state or sub-state",
               f"gate.py move {number} <raw|research|clarify|prototype|spec|check|ready|building|"
               "in-review>")
    record = load_run(options["run"]) if options.get("run") else None

    issue = read_issue(number)
    if not is_open(issue):
        refuse(f"#{number} is closed", f"reopen it on GitHub, then run: gate.py capture {number}")
    if open_parts(issue):
        refuse(f"#{number} has open parts, and its parts carry the states, not it",
               "gate.py report")
    names = label_names(issue)
    origin = position(number, names)

    if target == "state:shaping":
        if origin != "state:ready":
            refuse(f"a move back to shaping from {origin} names its sub-state",
                   f"gate.py move {number} <clarify|research|spec>")
        target = "shaping:clarify"

    row = next((r for r in TRANSITIONS if r[0] == origin and r[1] == target), None)
    if row is None:
        allowed = [short(r[1]) for r in TRANSITIONS if r[0] == origin]
        refuse(f"the gate makes no move from {origin} to {target}",
               f'gate.py move {number} <{"|".join(allowed)}>')
    check_condition(row[2], number, origin, target, issue, options, record)

    # Read the piece again just before writing. Another session may have moved
    # it since the first read, and a move on stale labels would undo theirs.
    again = read_issue(number)
    if kit_labels(label_names(again)) != kit_labels(names):
        carried = ", ".join(kit_labels(label_names(again))) or "no state"
        refuse(f"#{number} changed while this move was being checked: it now carries "
               f"{carried}",
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
    remove_assignees: list[str] = []
    if target == "state:ready" and origin in ("state:building", "state:in-review"):
        remove_assignees = assignee_logins(again)
    try:
        edit_issue(number, add, remove, body, add_assignee, remove_assignees)
    except Unreachable as error:
        raise Unreachable(f"the labels on #{number} could not be written, so nothing "
                          f"changed ({error.detail})", error.detail)

    done = f"#{number} moved from {origin} to {target}"
    if record is not None:
        status = RUN_STATUS["state:shaping" if target.startswith("shaping:") else target]
        try:
            save_run(options["run"], record, number, status)
        except OSError as error:
            relative = os.path.relpath(run_path(options["run"]), main_folder())
            print(f"{done}, but the run record {relative} could not be written ({error})")
            sys.exit(2)
        done += ", and run {} records it as {}".format(options["run"], status)

    if row[2] == "defect":
        try:
            gh(["issue", "comment", str(number), "--body-file", "-"],
               stdin="Back to building: {}\n".format(options["reason"].strip()))
        except Unreachable as error:
            done += f"; the comment naming the defect was not posted ({error.detail})"
    say(done)


def command_capture(arguments: list[str], options: dict[str, str]) -> None:
    if arguments:
        if len(arguments) != 1:
            refuse("capture takes one issue number", "gate.py capture <number>")
        number = number_from(arguments[0])
        issue = read_issue(number)
        if not is_open(issue):
            refuse(f"#{number} is closed",
                   f"reopen it on GitHub, then run: gate.py capture {number}")
        if open_parts(issue):
            refuse(f"#{number} has open parts, and its parts carry the states, not it",
                   "gate.py report")
        names = label_names(issue)
        states = [n for n in names if n.startswith("state:")]
        if states:
            refuse(f'#{number} already carries {" and ".join(states)}',
                   f"gate.py move {number} <target>")
        stray = kit_labels(names)
        if stray:
            refuse(f'#{number} carries {", ".join(stray)} with no state',
                   f"take it off on GitHub, then run: gate.py capture {number}")
        again = read_issue(number)
        if kit_labels(label_names(again)) != kit_labels(names):
            refuse(f"#{number} changed while it was being captured", "gate.py report")
        try:
            edit_issue(number, ["state:shaping", "shaping:raw"], [],
                       with_marker(str(again.get("body") or ""), "raw"))
        except Unreachable as error:
            raise Unreachable(f"the labels on #{number} could not be written, so nothing "
                              f"changed ({error.detail})", error.detail)
        say(f"#{number} captured in shaping:raw")
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
        refuse(f"the file {path} cannot be read ({error})",
               f"gate.py capture --title \"{title}\" --body-file <file>")
    try:
        out = gh(["issue", "create", "--title", title, "--body-file", "-",
                  "--label", "state:shaping,shaping:raw"], stdin=with_marker(words, "raw"))
    except Unreachable as error:
        raise Unreachable("the piece could not be opened, so nothing changed "
                          f"({error.detail})", error.detail)
    match = re.search(r"/issues/(\d+)", out)
    say("#{} captured in shaping:raw: {}".format(match.group(1) if match else "?", title))


def command_drop(arguments: list[str], options: dict[str, str]) -> None:
    if len(arguments) != 1:
        refuse("drop takes one issue number", "gate.py drop <number> --reason \"<why>\"")
    number = number_from(arguments[0])
    reason = options.get("reason", "").strip()
    if not reason:
        refuse("a piece is dropped only with a --reason",
               f"gate.py drop {number} --reason \"<why nobody will build it>\"")
    issue = read_issue(number)
    if not is_open(issue):
        refuse(f"#{number} is already closed", "gate.py tidy")
    try:
        gh(["issue", "close", str(number), "--reason", "not planned",
            "--comment", f"Closed as not planned: {reason}"])
    except Unreachable as error:
        raise Unreachable(f"#{number} could not be closed, so nothing changed "
                          f"({error.detail})", error.detail)
    labels = kit_labels(label_names(issue))
    if labels:
        try:
            edit_issue(number, [], labels)
        except Unreachable as error:
            print(f"#{number} closed as not planned, but its state labels could not be "
                  f"taken off ({error.detail}); next: gate.py tidy")
            sys.exit(2)
    say(f"#{number} closed as not planned, with its reason, and its state labels taken off")


def command_tidy(arguments: list[str], options: dict[str, str]) -> None:
    found: dict[int, list[str]] = {}
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
            raise Unreachable(f"tidy stopped at #{number}, whose labels could not be taken "
                              f"off ({error.detail})", error.detail)
    if found:
        say(f"tidy took the state labels off {len(found)} closed piece(s)")
    else:
        say("tidy found no closed piece carrying a state label")


def findings_for(item: dict[str, Any]) -> list[str]:
    names = label_names(item)
    states = [n for n in names if n.startswith("state:")]
    subs = [n for n in names if n.startswith("shaping:")]
    reviews = [n for n in names if n.startswith("review:")]
    found: list[str] = []
    if open_parts(item):
        carried = kit_labels(names)
        if carried:
            found.append(f"a parent carries {', '.join(carried)}; its parts carry the states")
    elif not states:
        found.append("no state")
    elif len(states) > 1:
        found.append(f"{len(states)} states: {' and '.join(states)}")
    else:
        state = states[0]
        if state not in STATES:
            found.append(f"{state} is not a state the kit uses")
        elif state == "state:shaping":
            if len(subs) != 1:
                named = " and ".join(subs) if subs else "no shaping sub-label"
                found.append(f"state:shaping with {named}")
            for review in reviews:
                found.append(f"{review} beside state:shaping")
        else:
            for sub in subs:
                found.append(f"{sub} beside {state}")
            if state == "state:in-review":
                if len(reviews) > 1:
                    found.append("two review labels: {}".format(" and ".join(reviews)))
                elif not reviews:
                    found.append("state:in-review with no review sub-label")
            else:
                for review in reviews:
                    found.append(f"{review} beside {state}")
    for name in names:
        if name in OLD_MODEL:
            found.append(f"carries {name}, a label from AI Build Kit's model that this kit "
                         "does not use; left alone")
    return found


HOOK = ".agents/hooks/state-guard.sh"


def missing_hook() -> str | None:
    """A finding when the Claude Code settings run the state guard and it is not there.

    The settings run the hook only when it is present and runnable, so a missing
    copy never blocks a command. Nothing then stops a direct label write, and
    this is where somebody hears about it.
    """
    root = main_folder()
    try:
        with open(os.path.join(root, ".claude", "settings.json"), encoding="utf-8") as handle:
            wired = "state-guard.sh" in handle.read()
    except OSError:
        return None
    hook = os.path.join(root, *HOOK.split("/"))
    if not wired or (os.path.isfile(hook) and os.access(hook, os.X_OK)):
        return None
    return (f"the state guard hook {HOOK} is missing or not runnable, so nothing stops a "
            "direct label write; next: run /maintain, which puts it back")


def command_report(arguments: list[str], options: dict[str, str]) -> None:
    listed = gh_json(["api", "repos/{owner}/{repo}/issues?state=open&per_page=100",
                      "--paginate"])
    pieces = [i for i in listed if isinstance(i, dict) and not i.get("pull_request")
              and is_open(i)]
    lines = []
    hook_finding = missing_hook()
    if hook_finding:
        lines.append(hook_finding)
    for item in sorted(pieces, key=lambda i: int(i["number"])):
        found = findings_for(item)
        if found:
            lines.append(f"#{item['number']} {item.get('title', '')}: {'; '.join(found)}")
    if not lines:
        say("report: every open piece has one state and the sub-label it needs "
            f"({len(pieces)} open)")
        return
    say(f"report: {len(lines)} finding(s) need attention; nothing was changed")
    for line in lines:
        say(line)


def command_labels(arguments: list[str], options: dict[str, str]) -> None:
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
        say(f"labels: created {len(made)}; this account could not create {len(missing)}, "
            "which pieces will go without until someone with write access runs "
            f"gate.py labels: {', '.join(missing)}")
    elif made:
        say(f"labels: created {len(made)}; all {len(wanted)} labels the kit uses are there")
    else:
        say(f"labels: all {len(wanted)} labels the kit uses are already there")


COMMANDS = {"move": command_move, "capture": command_capture, "drop": command_drop,
            "tidy": command_tidy, "report": command_report, "labels": command_labels}
OPTIONS = ("--run", "--assignee", "--reason", "--withdrawn-by", "--title", "--body-file")


def parse(argv: list[str]) -> tuple[list[str], dict[str, str]]:
    arguments: list[str] = []
    options: dict[str, str] = {}
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
                refuse(f"{word} needs a value", "gate.py {}".format(" ".join(argv[:i])))
            options[name[2:]] = argv[i + 1]
            i += 2
            continue
        if word.startswith("--"):
            refuse(f"{word} is not an option the gate takes", "gate.py --help")
        arguments.append(word)
        i += 1
    return arguments, options


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print((__doc__ or "").strip())
        return 0
    try:
        if not argv or argv[0] not in COMMANDS:
            command = argv[0] if argv else ""
            refuse(f"'{command}' is not a gate command",
                   "gate.py report")
        arguments, options = parse(argv[1:])
        COMMANDS[argv[0]](arguments, options)
        return 0
    except Refused as refusal:
        print("gate.py {} refused: {}".format(" ".join(argv), refusal.what), file=sys.stderr)
        print("next: " + refusal.next_step, file=sys.stderr)
        return 1
    except Unreachable as error:
        print(f"gate.py {argv[0]}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
