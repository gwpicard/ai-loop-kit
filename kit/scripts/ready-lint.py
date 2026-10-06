#!/usr/bin/env python3
"""ready-lint.py: the machine half of the ready gate.

A ready piece is built with nobody there. Before it turns ready, this reads the
piece and the project and refuses it when the contract is not whole: a section
is missing, the bar does not fit the loop module, an acceptance check passes
on today's code or fails for a reason other than its assertion, or the piece
does not say what it may change and what it reaches, or names an area the
project's area map does not hold. The readiness check that
follows is a session that reads the piece; this is the part a machine can
judge, so a session never has to remember it.

Usage:
  ready-lint.py <number>

It prints one line and exits 0 when every rule holds. Otherwise it lists each
gap with the next thing to do and exits 1. It exits 2, changing nothing, when
GitHub cannot be reached or its temporary checkout cannot be made or prepared.

It reads the issue through the GitHub command-line tool already signed in on
this computer, and the project through Git, from origin/main. To run the
acceptance checks it makes a temporary checkout of the acceptance branch in a
folder of its own, installs the project's dependencies there, and removes the
checkout with `git worktree remove` when it ends. It writes nothing into the
project and nothing to GitHub. Each check, and the install, has a ten-minute
limit; READY_LINT_TIME_LIMIT, in seconds, lowers it for a rehearsal.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from typing import Any, NoReturn
from xml.etree import ElementTree

# --- the tables -------------------------------------------------------------

# Phrases that are never a settled choice. A person would read each one as a
# decision left for later. Read in the Done when, Decided, Loop and Reach
# sections only, and never inside a code span. The words that are wrong only
# where a person would see the difference stay with the readiness check.
REFUSED_PHRASES = [
    "decide during build", "consider", "or accept the limit", "acceptable", "TBD",
    "where sensible", "if needed", "for now", "check on the day", "may leave",
    "a handful", "a few", "several",
]
PHRASE_SECTIONS = ["Done when", "Decided", "Loop", "Reach"]

# Lines a piece may hold, by its type label. Readiness, Kickback and Original
# report are written by others, so they are not counted.
LENGTH_LIMITS = {"type:chore": 80, "type:bug": 120, "type:feature": 250}
UNCOUNTED = ["Readiness", "Kickback", "Original report"]

# The fields each loop module's bar needs, in the order pieces.md gives them.
MODULE_FIELDS = {
    "build": ["Acceptance branch"],
    "fix": ["Acceptance branch", "Reproduction", "Must not change"],
    "goal": ["Metric", "Measured by", "Target", "Budget", "Guard checks", "Held-out check"],
    "gauntlet": ["Reference", "Compared by", "Budget", "Guard checks"],
}
BAR_FIELDS = sorted({f for fields in MODULE_FIELDS.values() for f in fields} | {"Test runner"})
REACH_FIELDS = ["Boundary", "Reaches", "If it breaks", "Depends on", "Reach derived at"]

# A crew's steps and the most members each may have. The width never counts
# the builder, and a crew that would add a second writer is refused.
CREW_CAPS = {"research": 5, "prototype": 3, "fix": 3, "goal": 3, "gauntlet": 3}
WRITER_WORDS = re.compile(r"\b(build|builds|builder|builders|readiness|check|run|runs)\b",
                          re.IGNORECASE)

# The runner check-floor.md names for each language, for a project with no
# test command yet. The two tables are kept the same.
TEST_RUNNERS = {"python": "pytest", "typescript": "vitest", "javascript": "vitest",
                "go": "go test", "rust": "cargo test"}

# The runners whose report the lint reads, and the option that writes it.
RUNNER_REPORTS = {
    "pytest": ["--junitxml={report}"],
    "vitest": ["--reporter=json", "--outputFile={report}"],
    "jest": ["--json", "--outputFile={report}"],
    "node": ["--test-reporter=junit", "--test-reporter-destination={report}"],
}

# What a failure that is not an assertion turned out to be, by what it says.
ERROR_KINDS = [
    ((r"ModuleNotFoundError|No module named|Cannot find module|ERR_MODULE_NOT_FOUND|"
      r"Failed to (load|resolve)"), "a missing module"),
    (r"ImportError|SyntaxError: .*import", "a failed import"),
    (r"SyntaxError", "a syntax error"),
    ((r"NameError|ReferenceError|AttributeError|is not defined|has no attribute|"
      r"is not a function"), "a name that does not exist"),
    (r"collection failure", "a collection error"),
]

# The sections a piece must carry, each with something in it.
REQUIRED = ["So that", "Done when", "Masterplan change", "Not in this piece", "Decided",
            "Data", "Leaves the tool", "Must still hold", "Relies on", "Loop", "Reach",
            "Needs from the computer", "Evidence"]

# Where a file path may stand: Relies on, and the lines that name a check or a
# test. The value of Acceptance branch is a branch name, and a link is never a
# path.
PATH_FIELDS = ["Reaches", "Check", "Reproduction", "Measured by", "Guard checks",
               "Held-out check", "Smoke"]

MARKER = re.compile(r"^<!-- loop:gate .* -->\s*$")
# The area map script beside this one. The lint reads area names through it, so
# a piece's areas are matched against exactly what `area-map.py areas` prints.
AREA_MAP = "area-map.py"
DATE = r"\d{4}-\d{2}-\d{2}"


# --- how the lint speaks -------------------------------------------------------

class Refused(Exception):
    """The piece cannot be read as a contract at all."""

    def __init__(self, what: str, next_step: str) -> None:
        super().__init__(what)
        self.what = what
        self.next_step = next_step


class CannotRun(Exception):
    """GitHub, Git or the temporary checkout failed, so nothing was checked."""


def refuse(what: str, next_step: str) -> NoReturn:
    raise Refused(what, next_step)


def time_limit() -> int:
    try:
        return max(1, int(os.environ.get("READY_LINT_TIME_LIMIT", "600")))
    except ValueError:
        return 600


# --- talking to GitHub and Git ------------------------------------------------

def first_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "no message")


def gh_json(args: Sequence[str]) -> Any:
    try:
        done = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    except OSError as error:
        raise CannotRun(f"the GitHub command-line tool could not be started ({error})")
    if done.returncode != 0:
        said = first_line(done.stderr)
        if "404" in done.stderr or "Not Found" in done.stderr:
            raise LookupError(said)
        raise CannotRun(f"GitHub did not answer ({said})")
    try:
        return json.loads(done.stdout)
    except ValueError:
        raise CannotRun("GitHub answered with something that is not JSON")


def git(root: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True,
                          check=False)


def git_out(root: str, *args: str) -> str:
    done = git(root, *args)
    return done.stdout if done.returncode == 0 else ""


def read_issue(number: int) -> dict[str, Any]:
    try:
        data = gh_json(["api", f"repos/{{owner}}/{{repo}}/issues/{number}"])
    except LookupError:
        refuse(f"#{number} does not exist in this repository",
               "check the number with: gh issue list")
    if not isinstance(data, dict):
        raise CannotRun("GitHub answered with something that is not an issue")
    if data.get("pull_request"):
        refuse(f"#{number} is a pull request, not a piece", "ready-lint.py <piece number>")
    return data


def blockers_of(number: int) -> list[int]:
    try:
        listed = gh_json(["api",
                          f"repos/{{owner}}/{{repo}}/issues/{number}/dependencies/blocked_by"])
    except LookupError:
        return []
    return [int(item["number"]) for item in listed
            if isinstance(item, dict) and str(item.get("number", "")).isdigit()]


# --- reading a piece's body -------------------------------------------------------

def strip_code(text: str) -> str:
    return re.sub(r"`[^`]*`", " ", text)


def body_lines(body: str) -> list[str]:
    return [line for line in body.replace("\r\n", "\n").split("\n") if not MARKER.match(line)]


def sections(body: str) -> list[tuple[str, list[str]]]:
    """Each "## heading" outside a code fence, with its lines. The preamble is ""."""
    found: list[tuple[str, list[str]]] = [("", [])]
    fence = False
    for line in body_lines(body):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        if not fence and line.startswith("## "):
            found.append((line[3:].strip(), []))
            continue
        found[-1][1].append(line)
    return found


def section(body: str, heading: str) -> str | None:
    parts = [lines for name, lines in sections(body) if name.lower() == heading.lower()]
    if not parts:
        return None
    return "\n".join("\n".join(lines) for lines in parts).strip()


def without(body: str, headings: Sequence[str]) -> list[str]:
    """The body's lines, leaving out the named sections."""
    lowered = {h.lower() for h in headings}
    kept: list[str] = []
    for name, lines in sections(body):
        if name.lower() in lowered:
            continue
        if name:
            kept.append("## " + name)
        kept.extend(lines)
    return kept


def field_name(line: str, names: Sequence[str]) -> tuple[str, str] | None:
    match = re.match(r"^\s*(?:[-*]\s+)?([A-Za-z][A-Za-z -]*?):(?:\s+(.*))?$", line)
    if not match:
        return None
    wanted = {n.lower(): n for n in names}
    name = wanted.get(match.group(1).strip().lower())
    return (name, (match.group(2) or "").strip()) if name else None


def fields_in(text: str, names: Sequence[str]) -> dict[str, str]:
    """The named "Field: value" lines. Reaches may run on in list lines below it."""
    found: dict[str, str] = {}
    current = ""
    for line in text.splitlines():
        named = field_name(line, names)
        if named:
            current = named[0]
            if current not in found:
                found[current] = named[1]
            else:
                current = ""
            continue
        if current == "Reaches" and line.strip() and (
                line.startswith((" ", "\t")) or line.lstrip().startswith(("- ", "* "))):
            found["Reaches"] += "\n" + line.strip().lstrip("-* ").strip()
            continue
        current = ""
    return found


def clean(value: str) -> str:
    return value.strip().strip("`").strip().rstrip(".").strip().strip("`").strip()


def works_lines(done_when: str) -> list[str] | None:
    """The list items under "### Works", each joined with its continuation lines."""
    inside = False
    seen = False
    items: list[str] = []
    for line in done_when.splitlines():
        if line.startswith("### "):
            inside = line[4:].strip().lower() == "works"
            seen = seen or inside
            continue
        if not inside or not line.strip():
            continue
        if re.match(r"^\s*[-*]\s+", line):
            items.append(re.sub(r"^\s*[-*]\s+", "", line).strip())
        elif items:
            items[-1] += " " + line.strip()
    return items if seen else None


def check_value(line: str) -> str | None:
    match = re.search(r"\bCheck:\s*(.*)$", line)
    return clean(match.group(1)) if match else None


# --- the project -----------------------------------------------------------------

def stack_section(agents: str) -> str:
    inside = False
    kept: list[str] = []
    for line in agents.splitlines():
        if line.startswith("## "):
            inside = line.lower().startswith("## stack")
            continue
        if inside:
            kept.append(line)
    return "\n".join(kept)


def test_command(stack: str) -> str | None:
    """The first `Test command:` line in the stack section, and no other text."""
    for line in stack.splitlines():
        match = re.match(r"^\s*(?:[-*]\s+)?Test command:\s*(.*)$", line)
        if match:
            return clean(match.group(1))
    return None


def install_command(stack: str) -> str | None:
    """The install command the stack section records, as `Install <command>`."""
    for line in stack.splitlines():
        match = re.match(r"^\s*(?:[-*]\s+)?Install(?: command)?:?\s*`([^`]+)`", line)
        if match:
            return match.group(1).strip()
    return None


def project_check(agents: str) -> tuple[str, str]:
    """The workflow file and job the capability profile's Project check line names."""
    for line in agents.splitlines():
        match = re.search(r"Project check:\s*`?([^\s,`]+)`?(?:,\s*job\s+`?([\w.-]+)`?)?", line)
        if match and not match.group(1).startswith("<"):
            path = match.group(1)
            if "/" not in path:
                path = ".github/workflows/" + path
            return path, match.group(2) or "project-check"
    return ".github/workflows/checks.yml", "project-check"


def workflow_install(workflow: str, job: str) -> str | None:
    """The run: of the job's install step, where its name starts with Install."""
    lines = workflow.splitlines()
    start = next((i for i, ln in enumerate(lines)
                  if re.match(rf"^\s+{re.escape(job)}:\s*$", ln)), None)
    if start is None:
        return None
    job_indent = len(lines[start]) - len(lines[start].lstrip())
    name = ""
    i = start + 1
    while i < len(lines):
        line = lines[i]
        indent = len(line) - len(line.lstrip())
        if line.strip() and indent <= job_indent:
            break
        named = re.match(r"^\s*-?\s*name:\s*(.*)$", line)
        if named:
            name = named.group(1).strip().strip("'\"")
        run = re.match(r"^\s*-?\s*run:\s*(.*)$", line)
        if run and name.lower().startswith("install") and "test" not in name.lower():
            value = run.group(1).strip()
            if value in ("|", ">", "|-", ">-"):
                body: list[str] = []
                run_indent = indent
                i += 1
                while i < len(lines) and (not lines[i].strip() or
                                          len(lines[i]) - len(lines[i].lstrip()) > run_indent):
                    body.append(lines[i].strip())
                    i += 1
                return "\n".join(b for b in body if b) or None
            return value or None
        i += 1
    return None


def is_test_file(path: str) -> bool:
    """A test file as section-builder's test-guard.sh counts one."""
    wrapped = "/" + path
    if any(f"/{folder}/" in wrapped for folder in ("test", "tests", "__tests__", "spec")):
        return True
    name = path.rsplit("/", 1)[-1]
    if ".test." in name or ".spec." in name or name.startswith("test_"):
        return True
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return stem.endswith(("_test", "_spec"))


class Project:
    def __init__(self) -> None:
        done = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                              text=True, check=False)
        if done.returncode != 0:
            raise CannotRun("this folder is not inside the project's Git folder")
        self.root = done.stdout.strip()
        # A lint stopped half-way may have left its checkout registered.
        git(self.root, "worktree", "prune")
        self.has_origin = git(self.root, "remote", "get-url", "origin").returncode == 0
        if self.has_origin:
            fetched = git(self.root, "fetch", "--quiet", "origin")
            if fetched.returncode != 0:
                raise CannotRun(f"the fetch from origin failed ({first_line(fetched.stderr)})")
        self.main = self.has_ref("refs/remotes/origin/main")

    def has_ref(self, ref: str) -> bool:
        return git(self.root, "rev-parse", "--verify", "--quiet", ref + "^{commit}"
                   ).returncode == 0

    def read(self, path: str) -> str | None:
        """A file as origin/main holds it, or the project's own copy with no main yet."""
        if self.main:
            done = git(self.root, "show", "origin/main:" + path)
            return done.stdout if done.returncode == 0 else None
        try:
            with open(os.path.join(self.root, path), encoding="utf-8") as handle:
                return handle.read()
        except OSError:
            return None

    def holds(self, ref: str, path: str) -> bool:
        return git(self.root, "cat-file", "-e", f"{ref}:{path}").returncode == 0

    def tracked(self, refs: Sequence[str]) -> set[str]:
        names: set[str] = set()
        for ref in refs:
            for path in git_out(self.root, "ls-tree", "-r", "--name-only", ref).splitlines():
                names.add(path)
                parts = path.split("/")
                for n in range(1, len(parts)):
                    names.add("/".join(parts[:n]))
        return names


def load_area_map() -> Any:
    """The area map script beside the lint, loaded as a module, or None."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), AREA_MAP)
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location("area_map", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    writes = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = writes
    return module


# --- the temporary checkout --------------------------------------------------------

class Checkout:
    """A detached checkout of one commit in a folder made by mkdtemp.

    It is removed with `git worktree remove` when the lint ends. The test run
    leaves files behind, such as installed dependencies and reports, so the
    removal is told to count every untracked file as ignored. Git then removes
    the folder itself, and a tracked file the run changed still stops it.
    """

    def __init__(self, project: Project, ref: str) -> None:
        self.project = project
        self.ref = ref
        self.temp = ""
        self.path = ""
        self.added = False

    def open(self) -> None:
        try:
            self.temp = tempfile.mkdtemp(prefix="ready-lint-")
        except OSError as error:
            raise CannotRun(f"the temporary checkout could not be made ({error})")
        self.path = os.path.join(self.temp, "checkout")
        done = git(self.project.root, "worktree", "add", "--quiet", "--detach", self.path,
                   self.ref)
        if done.returncode != 0:
            self.clear()
            raise CannotRun("the temporary checkout could not be made "
                            f"({first_line(done.stderr)})")
        self.added = True

    def file(self, name: str) -> str:
        return os.path.join(self.temp, name)

    def clear(self) -> None:
        if self.added:
            everything = self.file("exclude-everything")
            with open(everything, "w", encoding="utf-8") as handle:
                handle.write("*\n")
            removed = git(self.project.root, "-c", f"core.excludesFile={everything}",
                          "worktree", "remove", self.path)
            if removed.returncode != 0:
                print(f"NOTE: the temporary checkout at {self.path} could not be removed "
                      f"({first_line(removed.stderr)}); remove it with: git worktree remove "
                      f"{self.path}", file=sys.stderr)
            self.added = False
        if not self.temp or not os.path.isdir(self.temp):
            return
        for name in os.listdir(self.temp):
            full = os.path.join(self.temp, name)
            if os.path.isfile(full) or os.path.islink(full):
                os.remove(full)
        try:
            os.rmdir(self.temp)
        except OSError:
            pass
        git(self.project.root, "worktree", "prune")


def run_limited(command: str, cwd: str) -> tuple[int, str, bool]:
    """Run a shell command under the time limit, stopping all it started when over."""
    env = dict(os.environ)
    env.update({"CI": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    process = subprocess.Popen(command, shell=True, cwd=cwd, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=True)
    try:
        output, _ = process.communicate(timeout=time_limit())
        return process.returncode, output or "", False
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
        output, _ = process.communicate()
        return -1, output or "", True


# --- running one check -----------------------------------------------------------------

def runner_of(text: str) -> str | None:
    words = set(re.split(r"[\s/]+", text))
    if "pytest" in words or "py.test" in words:
        return "pytest"
    if "vitest" in words:
        return "vitest"
    if "jest" in words:
        return "jest"
    if re.search(r"(^|\s)node(\s.*)?\s--test\b", text):
        return "node"
    return None


def through_script(command: str) -> bool:
    words = shlex.split(command)
    return bool(words) and words[0] in ("npm", "pnpm", "yarn")


def detect_runner(command: str, folder: str) -> str | None:
    """The runner the command starts, read through package.json for a script."""
    if not through_script(command):
        return runner_of(command)
    words = shlex.split(command)[1:]
    script = "test"
    if words[:1] in (["run"], ["run-script"]):
        script = words[1] if len(words) > 1 else "test"
    elif words:
        script = words[0]
    try:
        with open(os.path.join(folder, "package.json"), encoding="utf-8") as handle:
            scripts = json.load(handle).get("scripts", {})
    except (OSError, ValueError, AttributeError):
        return None
    return runner_of(str(scripts.get(script, ""))) if isinstance(scripts, dict) else None


def check_command(command: str, runner: str | None, path: str, report: str) -> str:
    """The Test command with the runner's report option and the check's file at the end."""
    extra = [option.format(report=report) for option in RUNNER_REPORTS.get(runner or "", [])]
    words = " ".join(shlex.quote(w) for w in extra + [path])
    return f"{command} -- {words}" if through_script(command) else f"{command} {words}"


def kind_of(text: str) -> tuple[str, str]:
    """What kind of failure the text shows, and the line that shows it."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for pattern, kind in ERROR_KINDS:
        for line in lines:
            if re.search(pattern, line):
                return kind, line
    return "an error that is not an assertion", lines[0] if lines else ""


def read_failures(runner: str, report: str) -> list[dict[str, Any]]:
    """Each failure the runner's report holds: the test, whether it was an assertion,
    and what it said."""
    found: list[dict[str, Any]] = []
    if runner in ("vitest", "jest"):
        with open(report, encoding="utf-8") as handle:
            data = json.load(handle)
        for result in data.get("testResults", []):
            failed = [a for a in result.get("assertionResults", [])
                      if a.get("status") == "failed"]
            for item in failed:
                said = "\n".join(str(m) for m in item.get("failureMessages", []))
                head = first_line(said)
                found.append({"test": item.get("fullName", ""), "detail": head,
                              "assertion": bool(re.match(
                                  r"^(AssertionError|Error: expect\(|expect\()", head))
                              or "[ERR_ASSERTION]" in head})
            message = str(result.get("message") or "")
            if result.get("status") == "failed" and not failed and message.strip():
                found.append({"test": result.get("name", ""), "detail": message,
                              "assertion": False})
        return found
    tree = ElementTree.parse(report)
    for case in tree.iter("testcase"):
        for tag in ("failure", "error"):
            for element in case.findall(tag):
                said = (element.get("message") or "") + "\n" + (element.text or "")
                lines = [line.strip() for line in said.splitlines() if line.strip()]
                if runner == "pytest":
                    assertion = tag == "failure" and bool(lines) and \
                        lines[-1].endswith("AssertionError")
                else:
                    assertion = "AssertionError" in said or "ERR_ASSERTION" in said
                found.append({"test": case.get("name", ""), "detail": said.strip(),
                              "assertion": assertion})
    return found


# --- the lint ---------------------------------------------------------------------------

class Lint:
    def __init__(self, project: Project, issue: dict[str, Any], number: int) -> None:
        self.project = project
        self.issue = issue
        self.number = number
        self.body = str(issue.get("body") or "")
        self.labels = [label["name"] if isinstance(label, dict) else str(label)
                       for label in issue.get("labels", [])]
        self.gaps: list[tuple[str, str]] = []
        self.notes: list[str] = []
        self.no_code = False
        self.shape = f"/shape {number}"

    def gap(self, what: str, next_step: str = "") -> None:
        self.gaps.append((what, next_step or f"close it on the piece in {self.shape}"))

    # The rules, in the order the person reads them.

    def run(self) -> None:
        types = [n for n in self.labels if n.startswith("type:")]
        if len(types) != 1 or types[0] not in LENGTH_LIMITS:
            carried = " and ".join(types) if types else "no type: label"
            refuse(f"#{self.number} carries {carried}; a piece needs exactly one of "
                   f"{', '.join(LENGTH_LIMITS)}", f"give it one type in {self.shape}")
        self.type = types[0]
        agents = self.project.read("AGENTS.md") or ""
        stack = stack_section(agents)
        self.agents = agents
        self.stack = stack
        self.test = test_command(stack)
        none_for = re.match(r"^none for\s+(.+)$", self.test or "", re.IGNORECASE)
        self.language = none_for.group(1).strip().lower() if none_for else ""
        if not self.project.main:
            self.no_code = True
        elif self.test is None:
            self.gap("AGENTS.md's stack section has no `Test command:` line, so no check can "
                     "be run", "add a `Test command:` line to AGENTS.md's stack section")
        elif self.language:
            self.no_code = True

        self.required_sections()
        self.loop = fields_in(section(self.body, "Loop") or "", ["Loop module"] + BAR_FIELDS)
        self.module = clean(self.loop.get("Loop module", "")).lower()
        self.works = works_lines(section(self.body, "Done when") or "")
        self.checks = self.check_list()
        self.bar()
        self.reach()
        self.crew()
        self.phrases()
        self.brief()
        self.length()
        self.acceptance()

    def required_sections(self) -> None:
        older = re.search(r"^\s*Touches:", self.body, re.MULTILINE)
        for heading in REQUIRED:
            text = section(self.body, heading)
            if text is None:
                if older and heading in ("Loop", "Reach"):
                    self.gap(f"the piece has no ## {heading} section; it carries the older "
                             "Touches: line, which ## Loop and ## Reach replace",
                             f"write ## Loop and ## Reach in {self.shape}")
                else:
                    self.gap(f"the piece has no ## {heading} section",
                             f"write ## {heading} in {self.shape}")
            elif not text.strip():
                self.gap(f"## {heading} is empty", f"write ## {heading} in {self.shape}")

    def check_list(self) -> list[str]:
        """The acceptance checks the Works lines name, then the reproduction."""
        found: list[str] = []
        for line in self.works or []:
            value = check_value(line)
            if value:
                found.append(value.split()[0].rstrip(".,;") if self.module in ("build", "fix")
                             else value)
        if self.module == "fix" and self.loop.get("Reproduction"):
            found.append(clean(self.loop["Reproduction"]).split()[0])
        unique: list[str] = []
        for value in found:
            if value not in unique:
                unique.append(value)
        return unique

    def bar(self) -> None:
        if section(self.body, "Loop") is None:
            return
        loops = [n for n in self.labels if n.startswith("loop:")]
        if self.module not in MODULE_FIELDS:
            named = self.module or "nothing"
            self.gap(f"Loop module: names {named}, not one of fix, build, goal or gauntlet",
                     f"name the loop module in {self.shape}")
        if len(loops) != 1:
            carried = " and ".join(loops) if loops else "no loop: label"
            self.gap(f"the piece carries {carried}; it needs exactly one, matching its "
                     "Loop module", f"set the loop: label in {self.shape}")
        elif self.module in MODULE_FIELDS and loops[0] != "loop:" + self.module:
            self.gap(f"the piece carries {loops[0]}, but its Loop module is {self.module}",
                     f"make the label and the module agree in {self.shape}")
        if self.module not in MODULE_FIELDS:
            return
        needed = list(MODULE_FIELDS[self.module])
        if self.module in ("build", "fix") and self.language:
            needed.append("Test runner")
        for name in BAR_FIELDS:
            value = clean(self.loop.get(name, "")) if name in self.loop else None
            if name in needed and not value:
                self.gap(f"## Loop has no `{name}:` line, which a {self.module} piece needs",
                         f"write it in {self.shape}")
            elif name in needed and (value or "").lower() == "none":
                self.gap(f"`{name}:` says none, and a {self.module} piece needs it",
                         f"write it in {self.shape}")
            elif name not in needed and value is not None:
                self.gap(f"`{name}:` does not apply to a {self.module} piece; a field that "
                         "does not apply is left out, never written as none",
                         f"take the line out in {self.shape}")
        if self.module in ("goal", "gauntlet") and self.loop.get("Budget"):
            budget = clean(self.loop["Budget"])
            if re.search(r"\btokens?\b", budget, re.IGNORECASE):
                self.gap(f"Budget: {budget} counts tokens, and nothing in the kit counts "
                         "tokens", f"give the budget in attempts or minutes in {self.shape}")
            elif not re.match(r"^\d+\s*(attempts?|minutes?)\b", budget, re.IGNORECASE):
                self.gap(f"Budget: {budget} needs a number and a unit, attempts or minutes",
                         f"give the budget in attempts or minutes in {self.shape}")
        if self.module == "gauntlet" and self.loop.get("Reference"):
            reference = self.loop["Reference"]
            if not re.search(r"https?://\S+", reference):
                self.gap("Reference: is not a link that can be fetched",
                         f"give the reference as a link in {self.shape}")
            if not re.search(DATE, reference):
                self.gap("Reference: names no date on which the person approved it",
                         f"write the approval date beside the link in {self.shape}")
        if "Test runner" in needed and self.loop.get("Test runner"):
            runner = clean(self.loop["Test runner"]).lower()
            given = TEST_RUNNERS.get(self.language)
            if given is None:
                self.gap(f"check-floor.md names no test runner for {self.language}, so the "
                         "checks have nothing to be written for",
                         f"choose the runner with the person in {self.shape}")
            elif runner != given:
                self.gap(f"Test runner: {runner} is not the runner check-floor.md names for "
                         f"{self.language}, which is {given}",
                         f"write `Test runner: {given}` in {self.shape}")
        if self.works is None:
            if section(self.body, "Done when") is not None:
                self.gap("## Done when has no ### Works group",
                         f"write the Works lines in {self.shape}")
            return
        for line in self.works:
            if check_value(line) is None:
                self.gap(f'a Works line names no `Check:` of its own: "{line[:70]}"',
                         f"name its check in {self.shape}")

    def reach(self) -> None:
        text = section(self.body, "Reach")
        if text is None:
            return
        fields = fields_in(text, REACH_FIELDS)
        for name in REACH_FIELDS:
            if not clean(fields.get(name, "")):
                self.gap(f"## Reach has no `{name}:` line", f"write it in {self.shape}")
        main = self.project.main
        for entry in self.reach_entries(fields.get("Reaches", "")):
            plain = entry.replace("`", "")
            if ":" not in plain:
                self.gap(f'Reaches: "{entry}" does not begin with an area name and a colon',
                         f"write it as `<area>: guarded by <tests>` in {self.shape}")
                continue
            plain = plain.split(":", 1)[1]
            if "no test covers it" in plain.lower():
                if not any(check and check in plain for check in self.check_refs()):
                    self.gap(f'Reaches: "{entry}" says no test covers it, and names none of '
                             "the piece's acceptance checks",
                             f"name the check that guards it in {self.shape}")
                continue
            if "guarded by" not in plain.lower():
                self.gap(f'Reaches: "{entry}" names neither the tests that guard it nor '
                         '"no test covers it"', f"name its tests in {self.shape}")
                continue
            named = self.test_paths(plain[plain.lower().index("guarded by") + len("guarded by"):])
            if not named:
                self.gap(f'Reaches: "{entry}" names no test file', f"name it in {self.shape}")
            for path in named if main else []:
                if not self.project.holds("origin/main", path.split("::")[0]):
                    self.gap(f"Reaches: names {path}, which is not on origin/main",
                             f"name a test that exists in {self.shape}")
        derived = clean(fields.get("Reach derived at", "")).split(" ")[0]
        if derived and main:
            if not self.project.has_ref(derived) or not re.fullmatch(r"[0-9a-fA-F]{4,40}",
                                                                      derived):
                self.gap(f"Reach derived at: {derived} is not a commit in this project",
                         f"work the reach out again on origin/main in {self.shape}")
            elif git(self.project.root, "merge-base", "--is-ancestor", derived,
                     "origin/main").returncode != 0:
                self.gap(f"Reach derived at: {derived} is a commit origin/main does not "
                         "contain", f"work the reach out again on origin/main in {self.shape}")
        if "Depends on" in fields:
            self.depends(clean(fields["Depends on"]))
        self.areas(fields)

    def reach_entries(self, value: str) -> list[str]:
        parts = re.split(r"\n|;|\s\|\s", value)
        return [p.strip().strip("-* ").strip() for p in parts if p.strip()]

    def test_paths(self, text: str) -> list[str]:
        found = re.findall(r"`([^`]+)`", text)
        if not found:
            found = [w.strip(".,;()") for w in text.split()]
        return [p for p in (f.strip() for f in found)
                if "/" in p or re.search(r"\.[A-Za-z]{1,5}(::\S+)?$", p)]

    def check_refs(self) -> list[str]:
        refs = list(self.checks)
        for line in (section(self.body, "Done when") or "").splitlines():
            value = check_value(line)
            if value:
                refs.append(value)
        return [r for r in refs if r]

    def depends(self, value: str) -> None:
        if value.lower() == "nothing":
            named: set[int] = set()
        else:
            numbers = re.findall(r"#(\d+)", value)
            if not numbers:
                self.gap(f"Depends on: {value} gives neither #<number> for each piece nor "
                         "nothing", f"write it in {self.shape}")
                return
            named = {int(n) for n in numbers}
        linked = set(blockers_of(self.number))
        for extra in sorted(named - linked):
            self.gap(f"Depends on: names #{extra}, which is not one of the piece's blocked-by "
                     "links", f"add the link or take #{extra} off Depends on in {self.shape}")
        for missing in sorted(linked - named):
            self.gap(f"the piece's blocked-by links name #{missing}, which Depends on: does "
                     "not", f"add #{missing} to Depends on in {self.shape}")
        ring = self.cycle(sorted(linked))
        if ring:
            chain = ", which waits on ".join(f"#{n}" for n in ring)
            self.gap(f"the pieces wait on each other in a cycle: {chain}",
                     f"take one link out of the cycle in {self.shape}")

    def cycle(self, first: list[int]) -> list[int] | None:
        stack = [(n, [self.number, n]) for n in first]
        seen: set[int] = set()
        while stack:
            node, path = stack.pop()
            if node == self.number:
                return path
            if node in seen or len(seen) > 200:
                continue
            seen.add(node)
            for after in blockers_of(node):
                stack.append((after, path + [after]))
        return None

    def areas(self, fields: dict[str, str]) -> None:
        """Every area the reach names is in the map, and a sensitive one is settled."""
        masterplan = self.project.read("masterplan.md")
        if section(masterplan or "", "Build path") is None:
            self.gap("the masterplan has no build-path section (## Build path), so its "
                     "sensitive areas cannot be read",
                     "run the fit check, which writes the build path")
            return
        area_map = load_area_map()
        if area_map is None:
            self.gap("the area map script, .agents/tools/area-map.py, is not beside the lint, "
                     "so the piece's areas cannot be read", "run /maintain, which places it")
            return
        try:
            mapped = area_map.read_map(self.project.read("docs/working-rules.md") or "")
        except area_map.MapError as error:
            self.gap(f"the area map cannot be read: {error}",
                     "run python3 .agents/tools/area-map.py check, and correct the map")
            return
        by_name = {area.name.strip().lower(): area for area in mapped}
        named = [clean(a) for a in clean(fields.get("Boundary", "")).split(",")]
        named += [clean(e.replace("`", "").split(":", 1)[0])
                  for e in self.reach_entries(fields.get("Reaches", "")) if ":" in e]
        lines = {name.lower(): line
                 for name, _, line in area_map.sensitive_lines(masterplan or "")}
        for name in dict.fromkeys(a for a in named if a):
            area = by_name.get(name.strip().lower())
            if area is None:
                self.gap(f"{name} is not an area in docs/working-rules.md, which names "
                         f"{', '.join(a.name for a in mapped) or 'none'}",
                         f"name an area `area-map.py areas` prints, or add it to the map, in "
                         f"{self.shape}")
                continue
            if area.sensitive is None:
                continue
            sensitive = area.sensitive[0]
            line = lines.get(sensitive.strip().lower(), "")
            if not re.search(rf"\b(done|accepted)\s+{DATE}\s*\.?\s*$", line):
                self.gap(f"{area.name} is in the sensitive area {sensitive}, and its caution "
                         "is neither done nor accepted in the masterplan's build path",
                         f"settle the caution, or record the person's acceptance, in "
                         f"{self.shape}")

    def crew(self) -> None:
        for line in without(self.body, UNCOUNTED):
            match = re.match(r"^\s*(?:[-*]\s+)?Crew:\s*(.*)$", line)
            if not match:
                continue
            value = match.group(1).strip()
            head = re.split(r",?\s*\bbecause\b", value, maxsplit=1)[0]
            parsed = re.match(r"^([A-Za-z][A-Za-z -]*?)\s+(\d+)\s*$", head.strip())
            if WRITER_WORDS.search(head):
                self.gap(f'"Crew: {value}" is a crew with two writers: only the builder '
                         "writes, so a crew never names the build, the readiness check or "
                         "the run, or asks for more than one builder",
                         f"take the line out in {self.shape}")
                continue
            if not parsed:
                self.gap(f'"Crew: {value}" is not written as `Crew: <step> <width>, because '
                         "<reason>`, and is left out where the crew is the module's default",
                         f"write it that way or take it out in {self.shape}")
                continue
            step, width = parsed.group(1).strip().lower(), int(parsed.group(2))
            cap = CREW_CAPS.get(step)
            if cap is None:
                self.gap(f'"Crew: {value}" names {step}, which is not a crew step '
                         f"({', '.join(CREW_CAPS)})", f"name a step in {self.shape}")
            elif width < 1 or width > cap:
                self.gap(f'"Crew: {value}" asks for {width}, over the cap of {cap} for '
                         f"{step}", f"keep it within {cap} in {self.shape}")
            reason = re.search(r"\bbecause\b\s*(.*)$", value)
            if not reason or not reason.group(1).strip(" ."):
                self.gap(f'"Crew: {value}" gives no reason after "because"',
                         f"say why the crew differs from the default in {self.shape}")

    def phrases(self) -> None:
        for heading in PHRASE_SECTIONS:
            text = section(self.body, heading)
            if not text:
                continue
            plain = strip_code(self.unfenced(text))
            for phrase in REFUSED_PHRASES:
                if re.search(rf"(?<![A-Za-z0-9]){re.escape(phrase)}(?![A-Za-z0-9])", plain,
                             re.IGNORECASE):
                    self.gap(f'the refused phrase "{phrase}" stands under ## {heading}; it '
                             "leaves a choice open",
                             f"settle it with a decision or a number in {self.shape}")
            numbered = [line for line in self.unfenced(text).splitlines()
                        if re.match(r"^\s*\d+[.)]\s+\S", line)]
            if numbered:
                self.gap(f"## {heading} holds a numbered list of build steps; a piece says "
                         "what the tool does and leaves the order of the work to the builder",
                         f"write the behaviour instead in {self.shape}")

    def unfenced(self, text: str) -> str:
        kept: list[str] = []
        fence = False
        for line in text.splitlines():
            if line.lstrip().startswith(("```", "~~~")):
                fence = not fence
                continue
            if not fence:
                kept.append(line)
        return "\n".join(kept)

    def brief(self) -> None:
        """No line number or file path outside Relies on and the lines naming a check.

        Under the hood is the one further place: a test file named anywhere in
        it, and any path on a `Changes the bar:` line in it.
        """
        refs = ["origin/main"] if self.project.main else []
        branch = clean(self.loop.get("Acceptance branch", ""))
        if branch and self.project.has_ref(f"refs/remotes/origin/{branch}"):
            refs.append(f"origin/{branch}")
        tracked = self.project.tracked(refs)
        lines = without(self.body, UNCOUNTED + ["Relies on"])
        labels = "|".join(re.escape(f) for f in PATH_FIELDS)
        allowed = re.compile(rf"\b({labels}):")
        # Under the hood may name a test file by its whole path, and nothing
        # else there is let off. This disagrees with the written rule, which
        # lists only Relies on and the check lines. The check wins: test-guard.sh
        # lets a piece change an existing test only when Under the hood names it
        # by its whole path, so refusing a test path there would refuse every
        # piece that has to change one. The block is found the way test-guard.sh
        # finds it: a collapsed details block, or a heading of its own. A
        # `Changes the bar:` line in it may name any path, because the bar guard
        # lets a change to the bar through only when such a line names it by its
        # whole path, and it reads nowhere else.
        hood = ""
        reaching = False
        named_lines: list[str] = []
        named_paths: list[str] = []
        for line in lines:
            if re.search(r"<summary>\s*Under the hood\s*</summary>", line):
                hood = "details"
                continue
            if hood == "details" and "</details>" in line:
                hood = ""
                continue
            if re.match(r"^#+\s*Under the hood\s*$", line):
                hood = "heading"
                continue
            if hood == "heading" and re.match(r"^#+\s", line):
                hood = ""
            if field_name(line, ["Reaches"]):
                reaching = True
            elif reaching and not (line.startswith((" ", "\t")) or
                                   line.lstrip().startswith(("- ", "* "))):
                reaching = False
            if reaching:
                continue
            if field_name(line, ["Acceptance branch"]):
                continue
            bar_line = bool(hood) and re.match(r"^\s*(?:[-*]\s+)?Changes the bar:",
                                               line) is not None
            cut = allowed.search(line)
            scanned = line[:cut.start()] if cut else line
            scanned = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", scanned)
            scanned = re.sub(r"https?://\S+", " ", scanned)
            named_lines.extend(re.findall(r"\blines? \d+\b|[\w./-]+\.[A-Za-z]{1,5}:\d+",
                                          scanned, re.IGNORECASE))
            for word in scanned.split():
                # Twice, so a path in backticks before a full stop is still read.
                marks = "`*_\"'()[]{}<>,;:!?"
                path = word.strip(marks).rstrip(".").strip(marks)
                path = re.sub(r":\d+$", "", path)
                if bar_line:
                    continue
                if hood and is_test_file(path):
                    continue
                if self.is_path(path, tracked):
                    named_paths.append(path)
        for found in dict.fromkeys(named_lines):
            self.gap(f'a line number outside ## Relies on: "{found}"',
                     f"name the behaviour instead, or move it to ## Relies on, in {self.shape}")
        for path in dict.fromkeys(named_paths):
            self.gap(f"a file path outside ## Relies on and the lines that name a check: "
                     f"{path}", f"name the interface or the behaviour instead in {self.shape}")

    def is_path(self, word: str, tracked: set[str]) -> bool:
        if not word or not ("/" in word or re.search(r"\.[A-Za-z]{1,5}$", word)):
            return False
        bare = word[2:] if word.startswith("./") else word.lstrip("/")
        if bare.rstrip("/") in tracked:
            return True
        return self.no_code and "/" in word and bool(re.search(r"\.[A-Za-z]{1,5}$", word))

    def length(self) -> None:
        kept = "\n".join(without(self.body, UNCOUNTED)).strip("\n")
        count = len(kept.split("\n")) if kept else 0
        limit = LENGTH_LIMITS[self.type]
        if count > limit:
            self.gap(f"the piece has {count} lines, over the limit of {limit} for a "
                     f"{self.type} piece (Readiness, Kickback and Original report are not "
                     "counted)", f"split it into pieces in {self.shape}")

    def acceptance(self) -> None:
        """For a build or fix piece, the acceptance branch and its checks."""
        if self.module not in ("build", "fix"):
            return
        if not self.project.main:
            self.gap("the project has no code on GitHub yet, so the acceptance branch the "
                     "checks live on cannot exist", "answer the first-upload question in "
                     "`/shape`")
            return
        branch = clean(self.loop.get("Acceptance branch", ""))
        if not branch or self.test is None:
            return
        ref = f"refs/remotes/origin/{branch}"
        if not self.project.has_ref(ref):
            self.gap(f"the acceptance branch {branch} is not on origin",
                     f"push the branch that holds the checks, in {self.shape}")
            return
        base = git_out(self.project.root, "merge-base", "origin/main", ref).strip()
        changed = git_out(self.project.root, "diff", "--name-only", "--no-renames", base,
                          ref).split()
        other = [path for path in changed if not is_test_file(path)]
        if other:
            self.gap(f"the acceptance branch {branch} changes more than test files: "
                     f"{', '.join(other)}", f"keep only the checks on the branch, in "
                                            f"{self.shape}")
        sound = not other
        for path in self.checks:
            if not is_test_file(path):
                self.gap(f"Check: {path} is not a test file", f"name the test file in "
                                                               f"{self.shape}")
                sound = False
            elif not self.project.holds(ref, path):
                self.gap(f"Check: {path} is not on the acceptance branch {branch}",
                         f"push it to the branch, or name the file it holds, in {self.shape}")
                sound = False
        if self.language or not sound or not self.checks:
            return
        self.run_checks(ref)

    def run_checks(self, ref: str) -> None:
        command = self.test or ""
        checkout = Checkout(self.project, ref)
        try:
            checkout.open()
            install = install_command(self.stack)
            if install is None:
                path, job = project_check(self.agents)
                install = workflow_install(self.project.read(path) or "", job)
            if install:
                code, output, late = run_limited(install, checkout.path)
                if late:
                    raise CannotRun(f"the install, `{install}`, ran past the limit of "
                                    f"{time_limit()} seconds and was stopped")
                if code != 0:
                    raise CannotRun(f"the install, `{install}`, failed with exit {code} "
                                    f"({first_line(output[-2000:])})")
            runner = detect_runner(command, checkout.path)
            for number, path in enumerate(self.checks):
                report = checkout.file(f"report-{number}")
                code, output, late = run_limited(check_command(command, runner, path, report),
                                                 checkout.path)
                if late:
                    self.gap(f"the check {path} ran past the time limit of {time_limit()} "
                             "seconds and was stopped", f"make it finish within the limit in "
                                                        f"{self.shape}")
                elif code == 0:
                    self.gap(f"the check {path} passes on today's code, so it cannot show the "
                             "piece was built", f"write it so it fails today, in {self.shape}")
                elif runner is None:
                    self.notes.append(f"NOTE: {path} fails, but the lint cannot read this "
                                      "test runner's report, so it could not tell an assertion "
                                      "from an error; the readiness check reads its output")
                else:
                    self.judge(path, runner, report, output)
        finally:
            checkout.clear()

    def judge(self, path: str, runner: str, report: str, output: str) -> None:
        try:
            failures = read_failures(runner, report)
        except (OSError, ValueError, ElementTree.ParseError):
            failures = []
        if not failures:
            self.gap(f"the check {path} failed, and {runner} wrote no failure the lint could "
                     f"read ({first_line(output[-2000:])})",
                     f"make it fail on its assertion, in {self.shape}")
            return
        for failure in failures:
            if failure["assertion"]:
                continue
            kind, line = kind_of(str(failure["detail"]))
            if kind == "an error that is not an assertion":
                kind, said = kind_of(output)
                line = said if kind != "an error that is not an assertion" else line
            self.gap(f"the check {path} fails on {kind}, not on its assertion "
                     f"({line[:120]})",
                     f"make it fail only on its assertion, in {self.shape}")
            return


# --- the command ---------------------------------------------------------------------------

def stop(signum: int, frame: object) -> None:
    raise KeyboardInterrupt


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print((__doc__ or "").strip())
        return 0
    signal.signal(signal.SIGTERM, stop)
    try:
        if len(argv) != 1 or not argv[0].lstrip("#").isdigit() or int(argv[0].lstrip("#")) < 1:
            given = " ".join(argv) or "nothing"
            refuse(f"'{given}' is not an issue number", "ready-lint.py <number>")
        number = int(argv[0].lstrip("#"))
        issue = read_issue(number)
        if str(issue.get("state", "")).lower() != "open":
            refuse(f"#{number} is closed", f"reopen it on GitHub, then run: ready-lint.py "
                                           f"{number}")
        project = Project()
        lint = Lint(project, issue, number)
        lint.run()
    except Refused as refusal:
        print(f"Ready-gate lint: {refusal.what}.")
        print("next: " + refusal.next_step)
        return 1
    except CannotRun as error:
        print(f"Ready-gate lint: {error}, so nothing was checked.")
        return 2
    except KeyboardInterrupt:
        print("Ready-gate lint: stopped before it finished, so nothing was checked.")
        return 2
    title = str(issue.get("title") or f"#{number}")
    if lint.gaps:
        print(f"Ready-gate lint: {len(lint.gaps)} gap(s) on {title}:")
        for what, next_step in lint.gaps:
            print(f"- {what}; next: {next_step}")
        return 1
    suffix = "; no code yet: checks not run" if lint.no_code else ""
    print(f"Ready-gate lint: no gaps on {title}{suffix}.")
    for note in lint.notes:
        print(note)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
