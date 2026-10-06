"""The one parser for the spec block. The format is written in kit/spec-format.md.

The gate, the lint, the needs list and the fingerprint all read a spec through
`parse`. This is the only module that names the spec markers. A second reader
would drift from this one, and the test in tests/unit/test_spec.py fails if one
appears under kit/scripts/.

`parse` returns a `Spec` whose `to_dict()` has the same keys every time, so a
caller never checks for a missing key. A body with no spec block is not an
error: `found` is false and every field is empty. A block the parser cannot
trust, such as an unknown version, raises `SpecError`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SUPPORTED_VERSIONS = (1,)

START = re.compile(r"^<!-- spec:start(?: version=(\S+))? -->\s*$")
END = re.compile(r"^<!-- spec:end -->\s*$")

# (key, heading) in the order the spec holds them.
FIELDS: tuple[tuple[str, str], ...] = (
    ("goal", "Goal"),
    ("user_story", "User story"),
    ("expected_flow", "Expected flow"),
    ("how_to_observe", "How to observe it"),
    ("edge_cases", "Edge cases"),
    ("limits", "Limits"),
    ("must_stay_the_same", "Must stay the same"),
    ("follow", "Follow"),
    ("changes", "Changes to current behaviour"),
    ("coverage", "Coverage"),
    ("not_in_this_piece", "Not in this piece"),
    ("judge", "Judge"),
    ("links", "Links"),
    ("sensitive_areas", "Sensitive areas"),
    ("decisions", "Decisions"),
    ("research", "Research"),
    ("open_questions", "Open questions"),
)

REQUIRED_FULL = (
    "goal",
    "user_story",
    "expected_flow",
    "how_to_observe",
    "edge_cases",
    "limits",
    "must_stay_the_same",
    "follow",
    "changes",
    "coverage",
    "not_in_this_piece",
    "judge",
    "links",
    "sensitive_areas",
)
REQUIRED_QUICK = (
    "goal",
    "expected_flow",
    "edge_cases",
    "must_stay_the_same",
    "judge",
    "links",
)

COVERAGE_CATEGORIES = (
    "permissions",
    "data kept",
    "errors",
    "empty states",
    "what leaves the tool",
)

JUDGE_KEYS = {
    "kind": "kind",
    "command": "command",
    "proves": "proves",
    "held-out cases": "held_out",
    "fails today": "fails_today",
    "route": "route",
    "hypotheses": "hypotheses",
}

# Command prefixes that name a supported test runner, longest first.
RUNNERS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("python3", "-m", "pytest"), "pytest"),
    (("python", "-m", "pytest"), "pytest"),
    (("python3", "-m", "unittest"), "unittest"),
    (("python", "-m", "unittest"), "unittest"),
    (("npx", "vitest"), "vitest"),
    (("npx", "jest"), "jest"),
    (("cargo", "test"), "cargo"),
    (("go", "test"), "go"),
    (("pytest",), "pytest"),
    (("vitest",), "vitest"),
    (("jest",), "jest"),
    (("npm",), "npm"),
    (("pnpm",), "pnpm"),
    (("yarn",), "yarn"),
    (("sh",), "shell"),
    (("bash",), "shell"),
)

ID = re.compile(r"\b[A-Z]{2,}-\d+\b")
FLOW_LINE = re.compile(r"^(FL-\d+)\s+(.*)$")
EDGE_LINE = re.compile(r"^(EC-\d+)\s+(.*)$")
LIST_MARK = re.compile(r"^(?:[-*]\s+|\d+[.)]\s+)")
KEY_LINE = re.compile(r"^([A-Za-z][A-Za-z -]*?):\s*(.*)$")
CHANGE_LABELS = ("Added", "Changed", "Removed", "Docs", "New area")


def section(body: str, heading: str, last: bool = False) -> str | None:
    """The text under a "## heading", or None when there is no such section.

    A heading inside a fenced code block does not count. Any "# " or "## "
    heading ends the section. With last=True only the last such section is read.
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
        if current is not None:
            current.append(line)
    if not found:
        return None
    chosen = found[-1:] if last else found
    return "\n".join("\n".join(part) for part in chosen).strip()


class SpecError(Exception):
    """A spec block the parser refuses or cannot read."""

    def __init__(self, message: str, *, next_command: str, refused: bool = False) -> None:
        super().__init__(message)
        self.next_command = next_command
        self.refused = refused  # true: the kit will not read it yet (exit code 3)


def _empty_judge() -> dict[str, Any]:
    return {
        "kind": None,
        "kind_note": None,
        "command": None,
        "runner": None,
        "proves": [],
        "held_out": None,
        "fails_today": None,
        "route": None,
        "hypotheses": [],
    }


@dataclass
class Spec:
    found: bool = False
    version: int | None = None
    path: str | None = None
    header: str = ""
    block: str = ""  # the raw text between the markers; the fingerprint reads it, to_dict does not
    fields: dict[str, str] = field(default_factory=lambda: {k: "" for k, _ in FIELDS})
    missing: list[str] = field(default_factory=list)
    flow: list[dict[str, str]] = field(default_factory=list)
    flow_without_id: list[str] = field(default_factory=list)
    edge_cases: list[dict[str, Any]] = field(default_factory=list)
    edge_cases_without_id: list[str] = field(default_factory=list)
    ids: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)
    coverage: dict[str, dict[str, Any]] = field(default_factory=dict)
    unanswered_coverage: list[str] = field(default_factory=list)
    judge: dict[str, Any] = field(default_factory=_empty_judge)
    route_open: bool = False
    links: dict[str, list[str]] = field(default_factory=lambda: {"relies_on": [], "touches": []})
    changes: dict[str, list[str]] = field(
        default_factory=lambda: {
            "added": [],
            "changed": [],
            "removed": [],
            "docs": [],
            "new_area": [],
        }
    )
    sensitive_areas: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    research: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "found": self.found,
            "version": self.version,
            "path": self.path,
            "header": self.header,
            "fields": self.fields,
            "missing": self.missing,
            "flow": self.flow,
            "flow_without_id": self.flow_without_id,
            "edge_cases": self.edge_cases,
            "edge_cases_without_id": self.edge_cases_without_id,
            "ids": self.ids,
            "duplicate_ids": self.duplicate_ids,
            "coverage": self.coverage,
            "unanswered_coverage": self.unanswered_coverage,
            "judge": self.judge,
            "route_open": self.route_open,
            "links": self.links,
            "changes": self.changes,
            "sensitive_areas": self.sensitive_areas,
            "decisions": self.decisions,
            "research": self.research,
            "open_questions": self.open_questions,
        }


def _fix_marker_next() -> str:
    return (
        "edit the spec markers as kit/spec-format.md says, "
        "then run spec.py show again"
    )


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _find_block(body: str) -> tuple[str, str, str] | None:
    """Return (version text, inner text, header) or None when there is no block."""
    lines = body.splitlines()
    fence = False
    start: int | None = None
    end: int | None = None
    version = ""
    for number, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
            continue
        if fence:
            continue
        opening = START.match(line)
        if opening:
            if start is not None:
                raise SpecError(
                    "the issue holds more than one spec:start marker",
                    next_command=_fix_marker_next(),
                )
            start = number
            version = opening.group(1) or ""
        elif END.match(line):
            if start is None or end is not None:
                raise SpecError(
                    "a spec:end marker has no spec:start marker before it",
                    next_command=_fix_marker_next(),
                )
            end = number
    if start is None:
        return None
    if end is None:
        raise SpecError(
            "the spec block has a spec:start marker but no spec:end marker",
            next_command=_fix_marker_next(),
        )
    inner = "\n".join(lines[start + 1 : end])
    header = "\n".join(lines[:start]).strip()
    return version, inner, header


def _check_version(text: str) -> int:
    supported = ", ".join(str(v) for v in SUPPORTED_VERSIONS)
    if not text:
        raise SpecError(
            f"the spec:start marker names no version (this kit reads version {supported})",
            next_command=_fix_marker_next(),
            refused=True,
        )
    if not text.isdigit() or int(text) not in SUPPORTED_VERSIONS:
        raise SpecError(
            f"the spec is version {text}, and this kit reads version {supported}",
            next_command=_fix_marker_next() + " (or update the kit if the spec is newer)",
            refused=True,
        )
    return int(text)


def _preamble(inner: str) -> str:
    """The lines before the first "## " heading."""
    kept: list[str] = []
    fence = False
    for line in inner.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        if not fence and line.startswith("## "):
            break
        kept.append(line)
    return "\n".join(kept)


def _path_of(inner: str) -> str:
    for line in _preamble(inner).splitlines():
        match = re.match(r"^Path:\s*(\S+)\s*$", line, re.IGNORECASE)
        if match:
            value = match.group(1).lower()
            if value not in ("quick", "full"):
                raise SpecError(
                    f'the spec says "Path: {match.group(1)}", and only quick or full is known',
                    next_command="set the line to Path: quick, or remove it (kit/spec-format.md)",
                )
            return value
    return "full"


def _items(text: str, pattern: re.Pattern[str]) -> tuple[list[tuple[str, str]], list[str]]:
    """Split lines that start with an ID into (id, text) and collect untagged lines."""
    tagged: list[list[str]] = []
    untagged: list[str] = []
    current: list[str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            current = None
            continue
        match = pattern.match(line)
        if match:
            current = [match.group(1), match.group(2)]
            tagged.append(current)
        elif current is not None and not LIST_MARK.match(line):
            current[1] += " " + line
        else:
            untagged.append(line)
            current = None
    return [(i, _collapse(t)) for i, t in tagged], untagged


def _labelled(text: str, labels: tuple[str, ...]) -> dict[str, str]:
    """Text under each "Label:" in a run of prose. Labels may share a line."""
    names = "|".join(re.escape(label) for label in labels)
    pattern = re.compile(rf"(?:^|(?<=\s))({names}):", re.IGNORECASE | re.MULTILINE)
    matches = list(pattern.finditer(text))
    found: dict[str, str] = {}
    for index, match in enumerate(matches):
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        found[match.group(1).lower()] = _collapse(text[match.end() : stop])
    return found


def _split_list(text: str, separator: str = ",") -> list[str]:
    parts = [part.strip().strip(".").strip() for part in text.split(separator)]
    return [part for part in parts if part]


def _bullets(text: str) -> list[str]:
    items: list[list[str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^[-*]\s+", line):
            items.append([re.sub(r"^[-*]\s+", "", line)])
        elif items:
            items[-1].append(line)
    if items:
        return [_collapse(" ".join(item)) for item in items]
    if text.strip() and text.strip().strip(".").lower() != "none":
        return [_collapse(text)]
    return []


def runner_of(command: str) -> str | None:
    tokens = [t for t in command.split() if "=" not in t.split("/")[0] or t.startswith("-")]
    for prefix, name in RUNNERS:
        if tuple(tokens[: len(prefix)]) == prefix:
            return name
    return None


def _parse_judge(text: str) -> dict[str, Any]:
    judge = _empty_judge()
    values: dict[str, str] = {}
    key: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = KEY_LINE.match(line)
        if match and match.group(1).strip().lower() in JUDGE_KEYS:
            key = JUDGE_KEYS[match.group(1).strip().lower()]
            values[key] = match.group(2).strip()
        elif key is not None:
            values[key] += " " + line
    if "kind" in values:
        head, _, note = values["kind"].partition(",")
        judge["kind"] = head.strip()
        judge["kind_note"] = note.strip() or None
    if "command" in values:
        judge["command"] = values["command"]
        judge["runner"] = runner_of(values["command"])
    if "proves" in values:
        judge["proves"] = ID.findall(values["proves"])
    judge["held_out"] = values.get("held_out")
    judge["fails_today"] = values.get("fails_today")
    judge["route"] = values.get("route")
    if "hypotheses" in values:
        parts = values["hypotheses"].split(";")
        judge["hypotheses"] = [h.strip().strip(".") for h in parts if h.strip()]
    return judge


def _parse_coverage(text: str) -> dict[str, dict[str, Any]]:
    found = _labelled(text, COVERAGE_CATEGORIES)
    result: dict[str, dict[str, Any]] = {}
    for category in COVERAGE_CATEGORIES:
        answer = found.get(category, "")
        match = re.match(r"^(?:not applicable|n/a)\b[\s,.:;-]*(?:because\s+)?(.*)$", answer, re.I)
        result[category] = {
            "answer": answer,
            "not_applicable": match is not None,
            "reason": (match.group(1).strip().strip(".").strip() if match else ""),
        }
    return result


def parse(body: str) -> Spec:
    """Read the spec block in an issue body. See the module note for what it raises."""
    spec = Spec()
    block = _find_block(body)
    if block is None:
        spec.missing = list(REQUIRED_FULL)
        return spec
    version_text, inner, header = block
    spec.found = True
    spec.version = _check_version(version_text)
    spec.header = header
    spec.block = inner
    spec.path = _path_of(inner)

    for key, heading in FIELDS:
        spec.fields[key] = section(inner, heading) or ""
    required = REQUIRED_QUICK if spec.path == "quick" else REQUIRED_FULL
    spec.missing = [key for key in required if not spec.fields[key]]

    flow, spec.flow_without_id = _items(spec.fields["expected_flow"], FLOW_LINE)
    spec.flow = [{"id": i, "text": t} for i, t in flow]
    edges, spec.edge_cases_without_id = _items(spec.fields["edge_cases"], EDGE_LINE)
    for edge_id, text in edges:
        match = re.match(r"^when\s+(.+?)(?:,\s*then\s+(.+))?$", text, re.IGNORECASE | re.DOTALL)
        spec.edge_cases.append(
            {
                "id": edge_id,
                "text": text,
                "trigger": match.group(1).strip() if match else None,
                "result": (match.group(2) or "").strip() or None if match else None,
            }
        )
    spec.ids = [item["id"] for item in spec.flow] + [item["id"] for item in spec.edge_cases]
    spec.duplicate_ids = sorted({i for i in spec.ids if spec.ids.count(i) > 1})

    spec.coverage = _parse_coverage(spec.fields["coverage"])
    spec.unanswered_coverage = [
        name
        for name, entry in spec.coverage.items()
        if not entry["answer"] or (entry["not_applicable"] and not entry["reason"])
    ]

    spec.judge = _parse_judge(spec.fields["judge"])
    spec.route_open = (spec.judge["route"] or "").lower().startswith("open")

    links = _labelled(spec.fields["links"], ("Relies on", "Touches", "Blocked by"))
    spec.links = {
        "relies_on": _split_list(links.get("relies on", "")),
        "touches": _split_list(links.get("touches", "")),
    }
    changes = _labelled(spec.fields["changes"], CHANGE_LABELS)
    spec.changes = {
        "added": [changes["added"]] if changes.get("added") else [],
        "changed": [changes["changed"]] if changes.get("changed") else [],
        "removed": [changes["removed"]] if changes.get("removed") else [],
        "docs": _split_list(changes.get("docs", "")),
        "new_area": _split_list(changes.get("new area", "")),
    }

    spec.sensitive_areas = _bullets(spec.fields["sensitive_areas"])
    spec.decisions = _bullets(spec.fields["decisions"])
    spec.research = _bullets(spec.fields["research"])
    spec.open_questions = _bullets(spec.fields["open_questions"])
    return spec


# --- edits the gate makes ----------------------------------------------------------
#
# The gate is the only writer of these edits. They live here because this is the
# only module that names the spec markers.


def _block_span(lines: list[str]) -> tuple[int, int] | None:
    """The line numbers of the start and end markers, or None with no block."""
    fence = False
    start: int | None = None
    for number, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
            continue
        if fence:
            continue
        if START.match(line) and start is None:
            start = number
        elif END.match(line) and start is not None:
            return start, number
    return None


def split_after_block(body: str) -> tuple[str, str]:
    """(the text up to and including the end marker, the text after it).

    With no block it is ("", body). A block the parser refuses raises `SpecError`.
    """
    if _find_block(body) is None:
        return "", body
    lines = body.splitlines()
    span = _block_span(lines)
    assert span is not None
    end = span[1]
    return "\n".join(lines[: end + 1]), "\n".join(lines[end + 1 :])


def _heading_of(key: str) -> str:
    for field_key, heading in FIELDS:
        if field_key == key:
            return heading
    raise KeyError(key)


def _section_span(lines: list[str], start: int, end: int, heading: str) -> tuple[int, int] | None:
    """(heading line, first line after the section) inside the block, or None."""
    fence = False
    found: int | None = None
    for number in range(start + 1, end):
        line = lines[number]
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        if fence or not re.match(r"^#{1,2}\s", line):
            continue
        if found is not None:
            return found, number
        if line.startswith("## ") and line[3:].strip().lower() == heading.lower():
            found = number
    return (found, end) if found is not None else None


def _need_block(body: str) -> tuple[list[str], int, int]:
    if _find_block(body) is None:
        raise SpecError(
            "the issue holds no spec block, so the gate cannot write into it",
            next_command="add the spec block as kit/spec-format.md says, then run it again",
        )
    lines = body.splitlines()
    span = _block_span(lines)
    assert span is not None
    return lines, span[0], span[1]


def add_list_item(body: str, key: str, item: str) -> str:
    """The body with `- item` added to a list field, made if missing. "None." goes."""
    lines, start, end = _need_block(body)
    heading = _heading_of(key)
    entry = "- " + _collapse(item)
    span = _section_span(lines, start, end, heading)
    if span is None:
        new = [*lines[:end], "", f"## {heading}", entry, *lines[end:]]
        return "\n".join(new) + ("\n" if body.endswith("\n") else "")
    first, after = span
    content = list(range(first + 1, after))
    while content and not lines[content[-1]].strip():
        content.pop()
    kept = [n for n in content if lines[n].strip().strip(".").lower() != "none"]
    section = [lines[n] for n in kept] + [entry]
    new = [*lines[: first + 1], *section, *([""] if after < end else []), *lines[after:]]
    return "\n".join(new) + ("\n" if body.endswith("\n") else "")


def remove_list_item(body: str, key: str, item: str) -> str:
    """The body without the list item whose text (blanks collapsed) is `item`."""
    lines, start, end = _need_block(body)
    span = _section_span(lines, start, end, _heading_of(key))
    if span is None:
        return body
    first, after = span
    groups: list[list[int]] = []
    for number in range(first + 1, after):
        line = lines[number].strip()
        if re.match(r"^[-*]\s+", line):
            groups.append([number])
        elif line and groups:
            groups[-1].append(number)
    target = _collapse(item)
    drop: set[int] = set()
    for group in groups:
        text = _collapse(" ".join(lines[n].strip() for n in group))
        if re.sub(r"^[-*]\s+", "", text) == target:
            drop.update(group)
            break
    if not drop:
        return body
    kept = [n for n in range(first + 1, after) if n not in drop]
    section = [lines[n] for n in kept]
    if not any(line.strip() for line in section):
        section = ["None.", *([""] if after < end else [])]
    new = [*lines[: first + 1], *section, *lines[after:]]
    return "\n".join(new) + ("\n" if body.endswith("\n") else "")
