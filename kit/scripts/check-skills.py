#!/usr/bin/env python3
# contract: agent
"""Check the skills under a folder against the 17 skill principles.

    check-skills.py [--json] [--glossary FILE] [DIR]

DIR holds one folder for each skill, and each holds a `SKILL.md`, and perhaps
`references/` and `evals/`. It defaults to `kit/skills/` beside this script.
Without DIR, a kit with no skills folder passes with zero skills. With a DIR
that does not exist, the check stops, since a check that did not run is never
green.

Each finding has a rule id that starts with its principle, such as `P3-lines`.
A finding fails the check (exit 1). A warning does not. The rules:

    P1   every stop and every "Never" line says `Held by:` and names a holder
    P2   no copy of the gate's table: its labels or its exit codes
    P3   SKILL.md has 150 lines, 2,000 words, a 300 character description;
         a reference has 300 lines
    P4   Stops, Steps and Gotchas are present and in the template's order
    P5   setup, run and maintain are not model-invoked; a model-invoked
         description says "Use when"
    P6   references go one level deep, each is named in SKILL.md with a
         condition word, and a long one has a contents list
    P7   a shell block has three lines at most, and no pipe into a state change
    P9   no capitalised emphasis; a warning for a "do not" with no positive
         instruction beside it
    P10  a `## Gotchas` section with at least one entry
    P11  no paragraph repeated across skills (document-bloat.py), and no
         banned synonym from the glossary
    P12  every numbered step has a `Done when:` line
    P13  what-now and run start with the gate's report and a fallback line
    P15  at least three eval cases, as files under `evals/`
    P16  no date, version, model name, issue number or commit hash
    P17  a guard is held by more than the skill's own frontmatter

Principle 8 is held by tests/script-contracts.sh, principle 14 by the run
script's own test, and the rest of 10 by the scenario evals.

It reads the skills and writes nothing in them.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop import cli

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
DEFAULT_SKILLS = KIT / "skills"
DEFAULT_GLOSSARY = KIT / "glossary.md"
BLOAT = HERE / "document-bloat.py"

MAX_LINES = 150
MAX_WORDS = 2000
MAX_DESCRIPTION = 300
MAX_REFERENCE_LINES = 300
CONTENTS_AFTER = 100
MAX_SHELL_LINES = 3
SHELL_LANGUAGES = ("", "sh", "bash", "shell", "zsh", "console")
MIN_EVALS = 3

# The facts of the gate that a skill must point at and never copy. This is a
# small list for now. The gate's states module can feed it later, so the list
# has one home.
GATE_LABELS = (
    "state:shaping",
    "state:ready",
    "state:building",
    "state:in-review",
    "shaping:check",
)
GATE_EXIT_WORDS = ("ok", "failed", "usage", "refused")

MODEL_INVOKED_NEVER = ("setup", "run", "maintain")
REPORT_SKILLS = ("what-now", "run")
REPORT_LINE = re.compile(r"^!`[^`]*gate\.py report --json --brief[^`]*`$")

# Template order of the second-level sections.
ORDER = ("now", "stops", "steps", "gotchas", "when to read more")
REQUIRED = ("stops", "steps")

CONDITION = re.compile(
    r"\b(when|if|before|after|once|unless|while|until|whenever|for)\b", re.IGNORECASE
)
EMPHASIS = re.compile(
    r"\b(NEVER|ALWAYS|MUST|IMPORTANT|CRITICAL|WARNING|ONLY|NOT|SHALL|FORBIDDEN|DO NOT)\b"
)
NEGATIVE = re.compile(r"\b(do not|don't|never|avoid)\b", re.IGNORECASE)
POSITIVE = re.compile(
    r"\b(instead|use|run|ask|write|say|show|tell|stop|read|check|then|keep|name|"
    r"report|offer|point|send|wait|give|put|make)\b",
    re.IGNORECASE,
)
STATE_CHANGE_PIPE = re.compile(
    r"\|\s*(xargs|tee|sh|bash|zsh|gh|git|rm|mv|cp|dd|sed\s+-i|"
    r"python3?\s+\S*(gate|run|merge|worktree)\S*)\b"
)
HELD_BY = re.compile(r"held by:", re.IGNORECASE)
FRONTMATTER_CLAIM = re.compile(
    r"(skill-scoped|this skill'?s? (own )?(frontmatter|hooks)|allowed-tools|frontmatter)",
    re.IGNORECASE,
)
HOLDER = re.compile(
    r"(script|setting|gate|github|deny rule|ask rule|\.py\b|\.sh\b|\bhook\b|"
    r"settings\.json|sandbox|lint|check)",
    re.IGNORECASE,
)

MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)
TIMELESS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("a date", re.compile(r"\b20\d\d-\d\d-\d\d\b")),
    ("a date", re.compile(rf"\b({MONTHS})\s+\d{{1,2}}(st|nd|rd|th)?,?\s+20\d\d\b")),
    ("a date", re.compile(rf"\b\d{{1,2}}\s+({MONTHS})\s+20\d\d\b")),
    ("a version number", re.compile(r"\bv?\d+\.\d+\.\d+\b")),
    ("a version number", re.compile(r"\bversion\s+\d")),
    (
        "a model name",
        re.compile(
            r"\b(claude-[a-z0-9.-]+|opus|sonnet|haiku|fable|gpt-?\d\S*|gemini)\b", re.IGNORECASE
        ),
    ),
    ("an issue or pull request number", re.compile(r"(?<![\w&])#\d+\b")),
    (
        "a commit hash",
        re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b"),
    ),
)


@dataclass
class Report:
    findings: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def fail(self, rule: str, where: Path | str, line: int, message: str) -> None:
        self.findings.append({"rule": rule, "file": str(where), "line": line, "message": message})

    def warn(self, rule: str, where: Path | str, line: int, message: str) -> None:
        self.warnings.append({"rule": rule, "file": str(where), "line": line, "message": message})


@dataclass
class Skill:
    folder: Path
    lines: list[str]
    front: dict[str, str]
    body_start: int  # index of the first line after the frontmatter

    @property
    def name(self) -> str:
        return self.folder.name

    @property
    def skill_file(self) -> Path:
        return self.folder / "SKILL.md"


def parse_frontmatter(lines: list[str]) -> tuple[dict[str, str], int]:
    """Read `key: value` pairs between the first two `---` lines. Plain YAML only."""
    if not lines or lines[0].strip() != "---":
        return {}, 0
    front: dict[str, str] = {}
    key = ""
    for index in range(1, len(lines)):
        line = lines[index]
        if line.strip() == "---":
            return front, index + 1
        match = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if match:
            key = match.group(1)
            front[key] = match.group(2).strip().strip("\"'")
        elif key and line.startswith((" ", "\t")):
            front[key] = (front[key] + " " + line.strip()).strip()
    return {}, 0


def load_skill(folder: Path) -> Skill:
    text = (folder / "SKILL.md").read_text(encoding="utf-8")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    front, start = parse_frontmatter(lines)
    return Skill(folder, lines, front, start)


def prose_lines(lines: list[str], start: int = 0) -> list[tuple[int, str]]:
    """Lines outside fenced blocks, with inline code removed. Numbers are 1-based."""
    out: list[tuple[int, str]] = []
    fenced = False
    for index in range(start, len(lines)):
        line = lines[index]
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        out.append((index + 1, re.sub(r"`[^`]*`", "", line)))
    return out


def sections(skill: Skill) -> list[tuple[str, int]]:
    """The second-level headings outside code: (lowered name, 0-based line index)."""
    found: list[tuple[str, int]] = []
    fenced = False
    for index in range(skill.body_start, len(skill.lines)):
        line = skill.lines[index]
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("## "):
            found.append((line[3:].strip().lower(), index))
    return found


def section_lines(skill: Skill, name: str) -> list[tuple[int, str]]:
    """The lines of one section, as (1-based number, text)."""
    marks = sections(skill)
    for position, (title, index) in enumerate(marks):
        if title == name:
            end = marks[position + 1][1] if position + 1 < len(marks) else len(skill.lines)
            return [(n + 1, skill.lines[n]) for n in range(index + 1, end)]
    return []


def bullets(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Join each top-level bullet with its indented continuation lines."""
    out: list[tuple[int, str]] = []
    for number, line in lines:
        if line.startswith("- "):
            out.append((number, line[2:]))
        elif out and line.startswith("  ") and line.strip():
            out[-1] = (out[-1][0], out[-1][1] + " " + line.strip())
    return out


# --- the rules -----------------------------------------------------------------


def check_size(skill: Skill, report: Report) -> None:
    where = skill.skill_file
    if len(skill.lines) > MAX_LINES:
        report.fail(
            "P3-lines", where, MAX_LINES + 1, f"{len(skill.lines)} lines; {MAX_LINES} at most"
        )
    words = sum(len(line.split()) for line in skill.lines)
    if words > MAX_WORDS:
        report.fail("P3-words", where, 1, f"{words} words; {MAX_WORDS} at most")
    description = skill.front.get("description", "")
    if not description:
        report.fail("P3-description", where, 1, "no description in the frontmatter")
    elif len(description) > MAX_DESCRIPTION:
        report.fail(
            "P3-description",
            where,
            1,
            f"description is {len(description)} characters; {MAX_DESCRIPTION} at most",
        )
    references = skill.folder / "references"
    if references.is_dir():
        for ref in sorted(p for p in references.rglob("*") if p.is_file()):
            count = len(ref.read_text(encoding="utf-8").split("\n")) - 1
            if count > MAX_REFERENCE_LINES:
                report.fail(
                    "P3-reference-lines", ref, 1, f"{count} lines; {MAX_REFERENCE_LINES} at most"
                )


def check_held_by(skill: Skill, report: Report) -> None:
    where = skill.skill_file
    hard: list[tuple[int, str]] = list(bullets(section_lines(skill, "stops")))
    stops = {number for number, _ in hard}
    for number, text in bullets(
        [(n + 1, line) for n, line in enumerate(skill.lines) if n >= skill.body_start]
    ):
        if number not in stops and re.match(r"(never|always|must)\b", text, re.IGNORECASE):
            hard.append((number, text))
    for number, text in hard:
        if not HELD_BY.search(text):
            report.fail(
                "P1-held-by", where, number, f"a hard rule with no Held by line: {text[:60]}"
            )
            continue
        holder = text[HELD_BY.search(text).end() :]  # type: ignore[union-attr]
        rest = FRONTMATTER_CLAIM.sub("", holder)
        if not HOLDER.search(rest):
            report.fail(
                "P17-guard",
                where,
                number,
                "Held by names no holder outside the skill's own frontmatter: "
                "name a script, hook, setting or gate move",
            )


def check_gate_copies(texts: list[tuple[Path, list[str]]], report: Report) -> None:
    exit_words = "|".join(GATE_EXIT_WORDS)
    exit_code = re.compile(rf"\b[0-9]\s+({exit_words})\b", re.IGNORECASE)
    for path, lines in texts:
        for number, line in enumerate(lines, 1):
            for label in GATE_LABELS:
                if label in line:
                    report.fail(
                        "P2-gate-copy",
                        path,
                        number,
                        f"the gate's label {label} is named here; point at the gate instead",
                    )
            if len(exit_code.findall(line)) >= 2:
                report.fail(
                    "P2-gate-copy",
                    path,
                    number,
                    "a copy of the gate's exit codes; point at its --help instead",
                )


def check_order(skill: Skill, report: Report) -> None:
    where = skill.skill_file
    titles = [title for title, _ in sections(skill)]
    for needed in REQUIRED:
        if needed not in titles:
            report.fail("P4-order", where, 1, f"no `## {needed.title()}` section")
    known = [t for t in titles if t in ORDER]
    ranks = [ORDER.index(t) for t in known]
    if ranks != sorted(ranks):
        report.fail(
            "P4-order",
            where,
            1,
            "sections must run Now, Stops, Steps, Gotchas, When to read more; found: "
            + ", ".join(known),
        )


def check_invocation(skill: Skill, report: Report) -> None:
    where = skill.skill_file
    disabled = skill.front.get("disable-model-invocation", "").lower() == "true"
    if skill.name in MODEL_INVOKED_NEVER and not disabled:
        report.fail(
            "P5-disable", where, 1, f"/{skill.name} needs `disable-model-invocation: true`"
        )
    if not disabled and "use when" not in skill.front.get("description", "").lower():
        report.fail(
            "P5-use-when",
            where,
            1,
            "a model-invoked skill's description needs a 'Use when' clause",
        )


def check_references(skill: Skill, report: Report) -> None:
    references = skill.folder / "references"
    files = sorted(p for p in references.rglob("*") if p.is_file()) if references.is_dir() else []
    named: set[str] = set()
    for number, line in enumerate(skill.lines, 1):
        for match in re.finditer(r"references/([\w./-]+)", line):
            named.add(match.group(1).rstrip("."))
            if not CONDITION.search(line.replace(match.group(0), "")):
                report.fail(
                    "P6-condition",
                    skill.skill_file,
                    number,
                    f"the link to {match.group(0)} does not say when to read it",
                )
    for ref in files:
        relative = ref.relative_to(references).as_posix()
        text = ref.read_text(encoding="utf-8")
        if "/" in relative:
            report.fail("P6-nested", ref, 1, "a reference in a nested folder")
        elif relative not in named:
            report.fail("P6-orphan", ref, 1, "no line in SKILL.md names this reference")
        if re.search(r"references/[\w./-]+", text):
            report.fail("P6-nested", ref, 1, "a reference that points at another reference")
        count = len(text.split("\n")) - 1
        if count > CONTENTS_AFTER and not re.search(
            r"^(#+\s*)?(table of )?contents\b", text, re.IGNORECASE | re.MULTILINE
        ):
            report.fail(
                "P6-contents", ref, 1, f"{count} lines and no contents list; add one past 100"
            )


def shell_blocks(lines: list[str]) -> list[tuple[int, list[str]]]:
    """Fenced blocks that hold shell, or no language: (1-based start line, body)."""
    out: list[tuple[int, list[str]]] = []
    body: list[str] = []
    start = 0
    inside = False
    is_shell = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            if not inside:
                language = line.lstrip()[3:].strip().lower()
                inside = True
                is_shell = language in SHELL_LANGUAGES
                body, start = [], index + 1
            else:
                if is_shell:
                    out.append((start, body))
                inside = False
        elif inside:
            body.append(line)
    return out


def check_shell(skill: Skill, report: Report) -> None:
    for start, body in shell_blocks(skill.lines):
        if len([ln for ln in body if ln.strip()]) > MAX_SHELL_LINES:
            report.fail(
                "P7-long-block",
                skill.skill_file,
                start,
                f"a shell block over {MAX_SHELL_LINES} lines; put it in a script",
            )
        for offset, ln in enumerate(body, 1):
            if STATE_CHANGE_PIPE.search(ln):
                report.fail(
                    "P7-pipe", skill.skill_file, start + offset, "a pipe into a state change"
                )
    for number, line in enumerate(skill.lines, 1):
        if line.startswith("!`") and STATE_CHANGE_PIPE.search(line):
            report.fail("P7-pipe", skill.skill_file, number, "a pipe into a state change")


def check_emphasis(path: Path, lines: list[str], report: Report) -> None:
    prose = prose_lines(lines)
    for position, (number, line) in enumerate(prose):
        found = EMPHASIS.search(line)
        if found:
            report.fail(
                "P9-emphasis",
                path,
                number,
                f"capitalised emphasis '{found.group(0)}': say why, and say what to do",
            )
        if NEGATIVE.search(line):
            beside = line
            if position + 1 < len(prose) and prose[position + 1][0] == number + 1:
                beside += " " + prose[position + 1][1]
            if not POSITIVE.search(NEGATIVE.sub("", beside)):
                report.warn(
                    "P9-warn", path, number, "a 'do not' with no positive instruction beside it"
                )


def check_gotchas(skill: Skill, report: Report) -> None:
    if not bullets(section_lines(skill, "gotchas")):
        report.fail("P10-gotchas", skill.skill_file, 1, "no `## Gotchas` section with an entry")


def banned_words(glossary: Path) -> list[tuple[str, str]]:
    """(banned word, the word to use) from the `Banned:` lines under each heading."""
    pairs: list[tuple[str, str]] = []
    use = ""
    for line in glossary.read_text(encoding="utf-8").split("\n"):
        if line.startswith("## "):
            use = line[3:].strip()
        elif line.lower().startswith("banned:"):
            for word in line.split(":", 1)[1].split(","):
                if word.strip():
                    pairs.append((word.strip().lower(), use))
    return pairs


def check_banned(
    path: Path, lines: list[str], banned: list[tuple[str, str]], report: Report
) -> None:
    for number, line in prose_lines(lines):
        for word, use in banned:
            if re.search(rf"\b{re.escape(word)}s?\b", line, re.IGNORECASE):
                report.fail(
                    "P11-banned", path, number, f"'{word}' is banned; the glossary word is '{use}'"
                )


def check_repeats(folders: list[Skill], report: Report) -> None:
    """Run document-bloat.py over a git copy of the skills and keep its `repeated` lines."""
    if not BLOAT.is_file():
        raise cli.Failure(
            f"{BLOAT} is missing",
            next_command="git restore kit/scripts/document-bloat.py",
            code=cli.ExitCode.ENVIRONMENT,
        )
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        for skill in folders:
            targets = [skill.skill_file]
            references = skill.folder / "references"
            if references.is_dir():
                targets += sorted(p for p in references.rglob("*.md") if p.is_file())
            for source in targets:
                destination = root / skill.name / source.relative_to(skill.folder)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
        result = subprocess.run(
            [sys.executable, str(BLOAT)], cwd=root, check=False, capture_output=True, text=True
        )
    if result.returncode != 0:
        raise cli.Failure(
            f"document-bloat.py failed: {result.stderr.strip()[:200]}",
            next_command="python3 kit/scripts/document-bloat.py",
        )
    for row in result.stdout.split("\n"):
        parts = row.split("\t")
        if len(parts) == 3 and parts[0] == "repeated":
            report.fail(
                "P11-repeat",
                parts[1].split(":")[0],
                int(parts[1].rsplit(":", 1)[1]) if ":" in parts[1] else 1,
                f"the same paragraph as {parts[2]}; keep one home and point at it",
            )


def check_steps(skill: Skill, report: Report) -> None:
    lines = section_lines(skill, "steps")
    current = 0
    has_done = True
    for number, line in [*lines, (0, "1. end")]:
        if re.match(r"^\d+\.\s", line):
            if not has_done:
                report.fail(
                    "P12-done-when", skill.skill_file, current, "a step with no `Done when:` line"
                )
            current, has_done = number, False
        elif line.strip().lower().startswith("done when:"):
            has_done = True


def check_now(skill: Skill, report: Report) -> None:
    if skill.name not in REPORT_SKILLS:
        return
    where = skill.skill_file
    marks = sections(skill)
    if not marks or marks[0][0] != "now":
        report.fail("P13-now", where, 1, "the first section must be `## Now`")
        return
    body = [(n, ln) for n, ln in section_lines(skill, "now") if ln.strip()]
    if not body or not REPORT_LINE.match(body[0][1].strip()):
        report.fail(
            "P13-now",
            where,
            body[0][0] if body else marks[0][1] + 1,
            "`## Now` must start with a line that runs gate.py report --json --brief",
        )
        return
    if len(body) < 2 or body[1][1].lstrip().startswith(("!", "#", "-")):
        report.fail("P13-now", where, body[0][0], "no fallback line after the injected report")


def check_evals(skill: Skill, report: Report) -> None:
    evals = skill.folder / "evals"
    cases = (
        [p for p in evals.iterdir() if p.is_file() and not p.name.startswith(".")]
        if evals.is_dir()
        else []
    )
    if len(cases) < MIN_EVALS:
        report.fail(
            "P15-evals",
            evals if evals.is_dir() else skill.folder,
            1,
            f"{len(cases)} eval cases; {MIN_EVALS} at least (normal, edge, refusal)",
        )


def check_timeless(path: Path, lines: list[str], report: Report) -> None:
    for number, line in enumerate(lines, 1):
        for what, pattern in TIMELESS:
            found = pattern.search(line)
            if found:
                report.fail(
                    "P16-timeless", path, number, f"{what} ('{found.group(0)}') in a timeless skill"
                )
                break


# --- the run ---------------------------------------------------------------------


def skill_folders(root: Path) -> list[Path]:
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def lint(root: Path, glossary: Path) -> tuple[Report, int]:
    report = Report()
    banned = banned_words(glossary) if glossary.is_file() else []
    if not banned:
        raise cli.Failure(
            f"no banned words found in {glossary}",
            next_command="add `Banned:` lines to kit/glossary.md, or pass --glossary FILE",
            code=cli.ExitCode.ENVIRONMENT,
        )
    skills = [load_skill(folder) for folder in skill_folders(root)]
    for skill in skills:
        check_size(skill, report)
        check_held_by(skill, report)
        check_order(skill, report)
        check_invocation(skill, report)
        check_references(skill, report)
        check_shell(skill, report)
        check_gotchas(skill, report)
        check_steps(skill, report)
        check_now(skill, report)
        check_evals(skill, report)
        texts = [(skill.skill_file, skill.lines)]
        references = skill.folder / "references"
        if references.is_dir():
            for ref in sorted(p for p in references.rglob("*") if p.is_file()):
                texts.append((ref, ref.read_text(encoding="utf-8").split("\n")))
        check_gate_copies(texts, report)
        for path, lines in texts:
            check_emphasis(path, lines, report)
            check_banned(path, lines, banned, report)
            check_timeless(path, lines, report)
    if skills:
        check_repeats(skills, report)
    return report, len(skills)


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "dir", nargs="?", default=None, help="the folder of skills (default: kit/skills/)"
    )
    parser.add_argument(
        "--glossary",
        default=str(DEFAULT_GLOSSARY),
        help="the glossary with the banned words (default: kit/glossary.md)",
    )


def handle(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.dir) if args.dir else DEFAULT_SKILLS
    if not root.is_dir():
        if args.dir:
            raise cli.Failure(
                f"{root} is not a folder",
                next_command="check-skills.py --help",
                code=cli.ExitCode.ENVIRONMENT,
            )
        return {"skills": 0, "findings": [], "warnings": [], "note": f"no {root} yet"}
    report, count = lint(root, Path(args.glossary))
    if report.findings:
        raise cli.Failure(
            f"{len(report.findings)} finding(s) in {count} skill(s)",
            next_command="fix the first finding, then run check-skills.py again",
            data={"skills": count, "findings": report.findings, "warnings": report.warnings},
        )
    return {"skills": count, "findings": [], "warnings": report.warnings}


if __name__ == "__main__":
    sys.exit(
        cli.run(
            "check-skills.py",
            "Check skills against the 17 principles.",
            setup,
            handle,
            sys.argv[1:],
        )
    )
