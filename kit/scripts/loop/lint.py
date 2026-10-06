"""The spec lint: judge a spec without running anything.

`lint_body` reads an issue body through the one parser (loop/spec.py) and
returns a list of gaps. A gap is a dictionary with three keys: `rule`,
`message` and `next`. An empty list means the lint passes.

The rules, each named by its `rule` key:

- `required_field`: a field the path needs is missing (the quick path needs
  fewer fields than the full path).
- `coverage`: a coverage category has no answer, or "Not applicable" with no
  reason.
- `id_trace`: a flow step or edge case has no ID, an ID is repeated, an ID is
  not proved, or a proved ID is not in the spec. With `tests`, every ID must
  also be named by a test, and every test must name an ID.
- `edge_case`: an edge case is not "When ..., then ..." or has no example
  value (a number, a quoted or code value, or an empty value such as "no" or
  "empty").
- `limits`: a Limits sentence holds no number and no "none".
- `refused_phrase`: a phrase that leaves a choice open.
- `vague_word`: a vague adjective in a sentence with no number.
- `build_steps`: a numbered list of build steps.
- `length`: the spec is longer than its type allows.

The refused phrases and the length limits come from `kit/scripts/ready-lint.py`
(which this module reads and does not change). The masterplan reading and the
no-code special case of that file are left out.

The length counts the plain header and the spec block. Text the gate writes
below the block is not counted. The count is worked out from the parsed fields,
so it can differ from a raw line count by a few lines.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from loop import spec as parser_module

# From ready-lint.py: phrases that are never a settled choice.
REFUSED_PHRASES = (
    "decide during build",
    "consider",
    "or accept the limit",
    "acceptable",
    "TBD",
    "where sensible",
    "if needed",
    "for now",
    "check on the day",
    "may leave",
    "a handful",
    "a few",
    "several",
)

# From ready-lint.py, with the "type:" prefix removed.
LENGTH_LIMITS = {"chore": 80, "bug": 120, "feature": 250}
DEFAULT_TYPE = "feature"

VAGUE_WORDS = (
    "fast",
    "faster",
    "quick",
    "quickly",
    "slow",
    "slowly",
    "secure",
    "safe",
    "easy",
    "easily",
    "intuitive",
    "scalable",
    "robust",
    "responsive",
    "efficient",
    "performant",
    "reliable",
    "seamless",
    "lightweight",
    "user-friendly",
)

HEADINGS = {key: heading for key, heading in parser_module.FIELDS}
# Fields that hold notes and answers, not the behaviour. No prose rule reads them.
NOTE_FIELDS = ("decisions", "research", "open_questions", "judge")
VAGUE_FIELDS = (
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
)

ID_IN_TEST = re.compile(r"(?<![A-Za-z0-9])(?:FL|EC)-\d+(?!\d)")
EMPTY_VALUE = re.compile(r"\b(?:no|empty|blank|zero|none|missing)\b", re.IGNORECASE)
EXAMPLE_VALUE = re.compile("\\d|[\"'`" + chr(0x201C) + chr(0x2018) + "]")
NUMBERED = re.compile(r"^\s*\d+[.)]\s+\S")
CODE_SPAN = re.compile(r"`[^`]*`")
SENTENCE_BREAK = re.compile(r"(?<=[.;!?])\s+|\n+")

PYTHON_TEST = re.compile(r"^\s*(?:async\s+)?def\s+(test\w*)\s*\(")
GO_TEST = re.compile(r"^\s*func\s+(Test\w*)\s*\(")
JS_TEST = re.compile(r"""^\s*(?:it|test)(?:\.\w+)?\(\s*(['"`])(.*?)\1""")

Gap = dict[str, str]


def gap(rule: str, message: str, next_step: str) -> Gap:
    return {"rule": rule, "message": message, "next": next_step}


def _fix(heading: str) -> str:
    return f"edit {heading} in the spec (see kit/spec-format.md), then run spec.py lint again"


def _unfenced(text: str) -> str:
    kept: list[str] = []
    fence = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
            continue
        if not fence:
            kept.append(line)
    return "\n".join(kept)


def _plain(text: str) -> str:
    """The text with fenced blocks and code spans taken out."""
    return CODE_SPAN.sub(" ", _unfenced(text))


def _sentences(text: str) -> list[str]:
    parts = (part.strip(" -*\t") for part in SENTENCE_BREAK.split(text))
    return [part for part in parts if part]


def read_tests(source: str) -> dict[str, str]:
    """Split test source into {test name: its text}. Python, Go and JavaScript styles."""
    tests: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in source.splitlines():
        name: str | None = None
        for pattern, group in ((PYTHON_TEST, 1), (GO_TEST, 1), (JS_TEST, 2)):
            match = pattern.match(line)
            if match:
                name = match.group(group)
                break
        if name is not None:
            key = name
            count = 2
            while key in tests:
                key = f"{name} #{count}"
                count += 1
            current = tests.setdefault(key, [])
            current.append(line)
        elif current is not None:
            current.append(line)
    return {name: "\n".join(lines) for name, lines in tests.items()}


def _check_required(spec: dict[str, Any]) -> list[Gap]:
    return [
        gap(
            "required_field",
            f"the spec has no {HEADINGS[key]} field, or it is empty",
            _fix(f"the {HEADINGS[key]} field"),
        )
        for key in spec["missing"]
    ]


def _check_coverage(spec: dict[str, Any]) -> list[Gap]:
    if not spec["fields"]["coverage"]:
        return []
    return [
        gap(
            "coverage",
            f"coverage category {name!r} has no answer, or says not applicable with no reason",
            _fix("the Coverage field"),
        )
        for name in spec["unanswered_coverage"]
    ]


def _check_ids(
    spec: dict[str, Any], tests: Mapping[str, str] | None
) -> list[Gap]:
    gaps: list[Gap] = []
    step = _fix("the Expected flow, Edge cases and Judge fields")
    for line in spec["flow_without_id"] + spec["edge_cases_without_id"]:
        gaps.append(gap("id_trace", f"a line has no FL- or EC- ID: {line!r}", step))
    for repeated in spec["duplicate_ids"]:
        gaps.append(gap("id_trace", f"the ID {repeated} is used more than once", step))
    ids: list[str] = spec["ids"]
    if not ids:
        return gaps
    proved: list[str] = spec["judge"]["proves"]
    for name in ids:
        if name not in proved:
            gaps.append(gap("id_trace", f"the judge does not prove {name}", step))
    for name in proved:
        if name not in ids:
            gaps.append(
                gap("id_trace", f"the judge proves {name}, and the spec holds no such ID", step)
            )
    if tests is not None:
        named: set[str] = set()
        for test_name, text in tests.items():
            found = set(ID_IN_TEST.findall(f"{test_name}\n{text}"))
            named |= found
            if not found & set(ids):
                gaps.append(
                    gap(
                        "id_trace",
                        f"the test {test_name} names no ID from the spec",
                        "name the ID it proves in the test, then run spec.py lint again",
                    )
                )
        for name in ids:
            if name not in named:
                gaps.append(
                    gap(
                        "id_trace",
                        f"no test names {name}",
                        "write a test that names the ID, then run spec.py lint again",
                    )
                )
    return gaps


def _check_edge_cases(spec: dict[str, Any]) -> list[Gap]:
    gaps: list[Gap] = []
    step = _fix("the Edge cases field")
    for case in spec["edge_cases"]:
        label = case["id"]
        if case["trigger"] is None:
            gaps.append(gap("edge_case", f'{label} does not start with "When"', step))
            continue
        if case["result"] is None:
            gaps.append(gap("edge_case", f'{label} has no ", then ..." result', step))
        if not (EXAMPLE_VALUE.search(case["text"]) or EMPTY_VALUE.search(case["text"])):
            gaps.append(
                gap(
                    "edge_case",
                    f"{label} has no example value (a number, a quoted value or an empty one)",
                    step,
                )
            )
    return gaps


def _check_limits(spec: dict[str, Any]) -> list[Gap]:
    gaps: list[Gap] = []
    for sentence in _sentences(_plain(spec["fields"]["limits"])):
        if not (re.search(r"\d", sentence) or re.search(r"\bnone\b", sentence, re.IGNORECASE)):
            gaps.append(
                gap(
                    "limits",
                    f'a limit has no number and does not say "none": {sentence!r}',
                    _fix("the Limits field"),
                )
            )
    return gaps


def _check_phrases(spec: dict[str, Any]) -> list[Gap]:
    gaps: list[Gap] = []
    for key, heading in parser_module.FIELDS:
        if key in NOTE_FIELDS or not spec["fields"][key]:
            continue
        text = _plain(spec["fields"][key])
        for phrase in REFUSED_PHRASES:
            pattern = rf"(?<![A-Za-z0-9]){re.escape(phrase)}(?![A-Za-z0-9])"
            if re.search(pattern, text, re.IGNORECASE):
                gaps.append(
                    gap(
                        "refused_phrase",
                        f'the refused phrase "{phrase}" stands under ## {heading}; '
                        "it leaves a choice open",
                        f"settle it with a decision or a number in {heading}, then lint again",
                    )
                )
    return gaps


def _check_vague(spec: dict[str, Any]) -> list[Gap]:
    gaps: list[Gap] = []
    pattern = re.compile(
        r"(?<![A-Za-z0-9-])(" + "|".join(re.escape(w) for w in VAGUE_WORDS) + r")(?![A-Za-z0-9-])",
        re.IGNORECASE,
    )
    for key in VAGUE_FIELDS:
        for sentence in _sentences(_plain(spec["fields"][key])):
            match = pattern.search(sentence)
            if match and not re.search(r"\d", sentence):
                gaps.append(
                    gap(
                        "vague_word",
                        f'"{match.group(1)}" has no number in {HEADINGS[key]}: {sentence!r}',
                        f"give the number in {HEADINGS[key]}, then run spec.py lint again",
                    )
                )
    return gaps


def _check_build_steps(spec: dict[str, Any]) -> list[Gap]:
    gaps: list[Gap] = []
    for key, heading in parser_module.FIELDS:
        if key in NOTE_FIELDS:
            continue
        text = _unfenced(spec["fields"][key])
        if any(NUMBERED.match(line) for line in text.splitlines()):
            gaps.append(
                gap(
                    "build_steps",
                    f"## {heading} holds a numbered list of build steps; a spec says what the "
                    "tool does and leaves the order of the work to the builder",
                    f"write the behaviour instead in {heading}, then run spec.py lint again",
                )
            )
    return gaps


def spec_lines(spec: dict[str, Any]) -> int:
    """The lines of the header and the block, worked out from the parsed fields."""
    count = len(spec["header"].splitlines()) + (2 if spec["header"] else 0)
    count += 1 if spec["path"] == "quick" else 0
    for key, _heading in parser_module.FIELDS:
        text = spec["fields"][key]
        if text:
            count += 1 + len(text.splitlines()) + 1
    return count


def _check_length(spec: dict[str, Any], issue_type: str) -> list[Gap]:
    limit = LENGTH_LIMITS[issue_type]
    lines = spec_lines(spec)
    if lines <= limit:
        return []
    return [
        gap(
            "length",
            f"the spec has about {lines} lines, over the limit of {limit} for a {issue_type}",
            "split the piece into smaller pieces, then run spec.py lint again",
        )
    ]


def lint_spec(
    spec: dict[str, Any],
    *,
    issue_type: str | None = None,
    tests: Mapping[str, str] | None = None,
) -> list[Gap]:
    """Lint a parsed spec (the dictionary `to_dict()` gives)."""
    chosen = issue_type or DEFAULT_TYPE
    if chosen not in LENGTH_LIMITS:
        raise ValueError(f"unknown type {chosen!r}; use one of {', '.join(LENGTH_LIMITS)}")
    gaps = _check_required(spec)
    if not spec["found"]:
        return gaps
    gaps += _check_coverage(spec)
    gaps += _check_ids(spec, tests)
    gaps += _check_edge_cases(spec)
    gaps += _check_limits(spec)
    gaps += _check_phrases(spec)
    gaps += _check_vague(spec)
    gaps += _check_build_steps(spec)
    gaps += _check_length(spec, chosen)
    return gaps


def lint_body(
    body: str,
    *,
    issue_type: str | None = None,
    tests: Mapping[str, str] | None = None,
) -> list[Gap]:
    """Lint an issue body. Raises `loop.spec.SpecError` for a block the parser refuses."""
    return lint_spec(parser_module.parse(body).to_dict(), issue_type=issue_type, tests=tests)
