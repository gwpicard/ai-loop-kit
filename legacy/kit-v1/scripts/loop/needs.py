"""The computed needs list: what a piece still needs, and who can settle each need.

`needs_from_body` reads an issue body through the one parser (loop/spec.py) and
returns a list of needs. Each need is a dictionary with four keys:

- `kind`: the kind of need (see `KINDS`);
- `text`: what is missing, in plain words;
- `who`: who can settle it;
- `needs_you`: true when the person must act, so the gate sets the flag.

The list follows the needs table in the design. The biggest need comes first.
A piece is ready only when the list is empty.

Some needs come from outside the spec, so the caller passes them in:

- `tests`: the acceptance tests, as {name: text} (see `lint.read_tests`);
- `test_lists`: the IDs each of two fresh sessions would cover;
- `unresolved_dependencies`: blocked-by links that point at nothing, or a cycle.

The needs table also names "researchers disagree". Nothing in the spec can
show that two findings contradict each other, so this module does not compute
it. The research step of `/shape` settles it.

A sensitive area is accepted when its item holds an `Accepted:` label, the
person's words in quotes and a date.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from loop import lint
from loop import spec as parser_module

Need = dict[str, Any]

KINDS = (
    "missing_core",
    "coverage",
    "id_trace",
    "missing_draft",
    "test_lists_differ",
    "no_judge",
    "judge_not_failing",
    "open_question",
    "research_gap",
    "unresolved_dependency",
    "sensitive_area",
    "missing_field",
    "lint_gap",
)

CORE = ("goal", "user_story", "expected_flow")
DRAFT = ("limits", "must_stay_the_same", "follow")
# Missing fields that the lint reports and a more specific need already covers.
COVERED_ELSEWHERE = CORE + DRAFT + ("judge", "coverage")
# Lint rules that a more specific need already covers.
LINT_COVERED = ("required_field", "coverage", "id_trace")

PERSON = "the person, with the agent drafting"
CONFIRM = "the agent drafts; the person confirms"

MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
DATE = re.compile(rf"\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b\d{{1,2}}\s+(?:{MONTHS})[a-z]*\s+\d{{4}}\b")
QUOTE = re.compile(r"[\"“”]")


def need(kind: str, text: str, who: str, needs_you: bool) -> Need:
    return {"kind": kind, "text": text, "who": who, "needs_you": needs_you}


def _short(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _judge_needs(spec: dict[str, Any]) -> list[Need]:
    judge = spec["judge"]
    found: list[Need] = []
    if not judge["kind"] or not judge["command"]:
        kind = (judge["kind"] or "").lower()
        person = "metric" in kind or "reference" in kind
        who = "the agent drafts; the person approves the target or the reference" if person else (
            "the agent"
        )
        found.append(
            need(
                "no_judge",
                "The Judge field has no kind, or no command or target.",
                who,
                person,
            )
        )
    elif not judge["fails_today"]:
        found.append(
            need(
                "judge_not_failing",
                "The judge has not been seen failing on today's main.",
                "the agent asks the gate to run it",
                False,
            )
        )
    return found


def _research_needs(spec: dict[str, Any]) -> list[Need]:
    found: list[Need] = []
    for item in spec["research"]:
        parsed = parser_module.parse_finding(item)
        lacking = []
        if not parsed["source"]:
            lacking.append("a source")
        if not parsed["date"]:
            lacking.append("a date")
        if not parsed["kind"]:
            lacking.append("what it rests on (fingerprint <hex> or version <text>)")
        if lacking:
            found.append(
                need(
                    "research_gap",
                    f"A research finding has no {', no '.join(lacking)}: {_short(item, 80)}",
                    "the agent",
                    False,
                )
            )
    return found


def _sensitive_needs(spec: dict[str, Any]) -> list[Need]:
    found: list[Need] = []
    for item in spec["sensitive_areas"]:
        accepted = (
            re.search(r"\bAccepted:", item) and QUOTE.search(item) and DATE.search(item)
        )
        if not accepted:
            found.append(
                need(
                    "sensitive_area",
                    "A sensitive area has no recorded acceptance (the word Accepted:, the "
                    f"person's words in quotes and a date): {_short(item, 80)}",
                    "the person only",
                    True,
                )
            )
    return found


def compute(
    spec: dict[str, Any],
    gaps: Sequence[lint.Gap],
    *,
    test_lists: Sequence[Sequence[str]] | None = None,
    unresolved_dependencies: Sequence[str] | None = None,
) -> list[Need]:
    """The needs for a parsed spec and its lint gaps."""
    missing = set(spec["missing"])
    found: list[Need] = []
    for key in CORE:
        if key in missing:
            found.append(
                need(
                    "missing_core",
                    f"The spec has no {_heading(key)}.",
                    PERSON,
                    True,
                )
            )
    if spec["path"] != "quick":
        for name in spec["unanswered_coverage"]:
            found.append(
                need(
                    "coverage",
                    f"The coverage category {name!r} has no answer, or no reason for "
                    '"not applicable".',
                    CONFIRM,
                    True,
                )
            )
    found += [
        need("id_trace", g["message"], "the agent", False)
        for g in gaps
        if g["rule"] == "id_trace"
    ]
    for key in DRAFT:
        if key in missing:
            found.append(
                need("missing_draft", f"The spec has no {_heading(key)}.", CONFIRM, True)
            )
    if test_lists and len(test_lists) >= 2:
        first, second = set(test_lists[0]), set(test_lists[1])
        differ = sorted(first ^ second)
        if differ:
            found.append(
                need(
                    "test_lists_differ",
                    "The two fresh test lists cover different IDs: " + ", ".join(differ) + ".",
                    "the agent, or the person for a choice",
                    False,
                )
            )
    found += _judge_needs(spec)
    for question in spec["open_questions"]:
        found.append(
            need("open_question", "Open question: " + _short(question), "the person only", True)
        )
    found += _research_needs(spec)
    for problem in unresolved_dependencies or ():
        found.append(
            need(
                "unresolved_dependency",
                f"Unresolved dependency: {problem}",
                "the agent or the person",
                False,
            )
        )
    found += _sensitive_needs(spec)
    for key in spec["missing"]:
        if key not in COVERED_ELSEWHERE:
            found.append(
                need(
                    "missing_field",
                    f"The spec has no {_heading(key)}.",
                    "the agent",
                    False,
                )
            )
    found += [
        need("lint_gap", g["message"], "the agent", False)
        for g in gaps
        if g["rule"] not in LINT_COVERED
    ]
    return found


def _heading(key: str) -> str:
    return lint.HEADINGS[key]


def needs_you(needs: Sequence[Need]) -> bool:
    """True when any need names the person, so the gate sets the `needs-you` flag."""
    return any(n["needs_you"] for n in needs)


def needs_from_body(
    body: str,
    *,
    issue_type: str | None = None,
    tests: Mapping[str, str] | None = None,
    test_lists: Sequence[Sequence[str]] | None = None,
    unresolved_dependencies: Sequence[str] | None = None,
) -> list[Need]:
    """The needs for an issue body. Raises `loop.spec.SpecError` for a block it refuses."""
    spec = parser_module.parse(body).to_dict()
    gaps = lint.lint_spec(spec, issue_type=issue_type, tests=tests)
    return compute(
        spec, gaps, test_lists=test_lists, unresolved_dependencies=unresolved_dependencies
    )
