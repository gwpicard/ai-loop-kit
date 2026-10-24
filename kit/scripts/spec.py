"""Read piece contracts without importing the gate or the run."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from errors import Refused
from research import parse_research


@dataclass
class Spec:
    done_when: dict[str, str]
    command: str
    files: list[str]
    kind: str  # feature, fix, scaffold, goal, or gauntlet
    intent: str = ""
    out_of_scope: tuple = ()
    approach: str = ""
    keep: str = ""  # a command that passes on main and must still pass after the build
    stays: tuple = ()  # Done when IDs that already hold on main and must keep holding
    settings: bool = False  # True when the piece may change the project's check settings
    large_files: tuple = ()  # Explicit files allowed to cross the 1,000-line mark
    research: tuple = ()  # Sourced findings used to shape and review the piece
    measure: str = ""
    target: str = ""
    capture: str = ""
    reference: str = ""
    criteria: tuple = ()
    checks: tuple = ()
    playbook: str = ""
    risks: dict = field(default_factory=dict)


_ITEM = re.compile(r"^\s*[-*]\s*(D\d+)\s*(\(stays\))?\s*[:.)]\s*(\S.*)$", re.IGNORECASE)
_FIELD = re.compile(r"^\s*(Command|Files|Kind|Keep|Settings|Large file|Measure|Target|"
                    r"Capture|Reference|Criteria|Playbook)\s*:\s*(.*)$", re.IGNORECASE)
_RISK_FIELD = re.compile(r"^\s*(Protected paths|New dependency|Shared files|Needs services|"
                         r"Open choices|Depends on)\s*:\s*(.*)$", re.IGNORECASE)


def _risk_items(value: str) -> tuple[str, ...]:
    value = value.strip().strip("`").strip()
    if not value or value.lower() == "none":
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _section(body: str, name: str,
             include_heading: bool = False) -> Optional[list[str]]:
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower() == f"## {name}".lower():
            out = [line] if include_heading else []
            for rest in lines[i + 1:]:
                if rest.startswith("## "):
                    break
                out.append(rest)
            return out
    return None


def parse_research_section(body: str) -> tuple[list[dict[str, str]], list[str]]:
    """Parse the optional Research section through its focused module."""
    return parse_research(_section(body, "Research") or [])


def parse_spec(body: str) -> Spec:
    """Read the spec from an issue body. Refuse with every gap at once."""
    gaps: list[str] = []
    intent_lines = _section(body, "Intent")
    intent = ""
    out_of_scope: list[str] = []
    if intent_lines is None:
        gaps.append("no '## Intent' section")
    else:
        in_scope = False
        for line in intent_lines:
            if re.match(r"^\s*Out of scope\s*:", line, re.IGNORECASE):
                in_scope = True
                continue
            if line.startswith("## "):
                in_scope = False
            elif in_scope:
                if re.match(r"^\s*[-*]\s+\S", line):
                    out_of_scope.append(line.strip()[1:].strip())
            elif line.strip():
                intent += ("\n" if intent else "") + line.strip()
        if not intent:
            gaps.append("'## Intent' is empty")
        if not out_of_scope:
            gaps.append("'## Intent' has no non-empty 'Out of scope:' list")
    approach_lines = _section(body, "Approach")
    approach = "\n".join(line.strip() for line in (approach_lines or []) if line.strip())
    research, research_gaps = parse_research_section(body)
    gaps.extend(research_gaps)
    risk_lines = _section(body, "Risks")
    risk_names = {"protected paths": "protected_paths", "new dependency": "new_dependencies",
                  "shared files": "shared_files", "needs services": "needs_services",
                  "open choices": "open_choices"}
    risks = {value: () for value in risk_names.values()}
    if risk_lines is not None:
        found_risks = set()
        for line in risk_lines:
            if not line.strip():
                continue
            match = _RISK_FIELD.match(line)
            if not match:
                gaps.append(f"unexpected text in Risks section: {line.strip()}")
                continue
            key = match.group(1).lower()
            if key in found_risks:
                gaps.append(f"Risks field '{match.group(1)}' is used twice")
            found_risks.add(key)
            if key == "depends on":  # optional: the run builds this piece after those
                items = _risk_items(match.group(2))
                bad = [item for item in items if not (item.isascii() and item.isdigit()
                                                      and int(item) > 0)]
                if bad:
                    gaps.append("Risks Depends on takes piece numbers only, such as 12, "
                                f"not {', '.join(bad)}")
                elif len(set(items)) < len(items):
                    gaps.append("Risks Depends on names a piece twice")
                elif items:
                    risks["depends_on"] = tuple(int(item) for item in items)
                continue
            risks[risk_names[key]] = _risk_items(match.group(2))
            if key == "new dependency":
                for dependency in risks["new_dependencies"]:
                    name, separator, reason = dependency.partition(":")
                    if not separator or not name.strip() or not reason.strip():
                        gaps.append("Risks New dependency entries need a name and reason")
        for key in risk_names:
            if key not in found_risks:
                gaps.append(f"Risks section needs '{key.title()}:'")
        if risks["open_choices"]:
            gaps.append("Risks Open choices must be empty at ready")
        for key in ("protected_paths", "shared_files"):
            for path in risks[key]:
                if path.startswith("/") or ".." in Path(path).parts:
                    label = key.replace("_", " ")
                    gaps.append(f"Risks {label} path '{path}' must be inside the project")
    done_when: dict[str, str] = {}
    stays: list[str] = []
    done = _section(body, "Contract")
    if done is None:
        done = _section(body, "Done when")
    if done is None:
        gaps.append("no '## Contract' section")
    else:
        for line in done:
            m = _ITEM.match(line)
            if m:
                if m.group(1) in done_when:
                    gaps.append(f"spec ID {m.group(1)} is used twice")
                done_when[m.group(1)] = m.group(3).strip()
                if m.group(2):
                    stays.append(m.group(1))
        if not done_when:
            gaps.append("'## Contract' has no item like '- D1: ...'")

    command, kind, keep, files, settings, large_files = "", "feature", "", [], False, []
    measure, target, capture, reference, criteria, playbook = "", "", "", "", [], ""
    judge = _section(body, "Judge")
    exit_lines = _section(body, "Exit")
    checks = []
    if exit_lines is not None:
        current = None
        for line in exit_lines:
            heading = re.match(r"^###\s+(Tests|Measure|Critics)\s*$", line, re.IGNORECASE)
            if heading:
                current = {"type": heading.group(1).lower(), "files": [], "criteria": []}
                checks.append(current)
                continue
            if current is None:
                if line.strip():
                    gaps.append("'## Exit' fields must be inside a ### Tests, ### Measure "
                                "or ### Critics check")
                continue
            field = _FIELD.match(line)
            if field:
                key, value = field.group(1).lower(), field.group(2).strip().strip("`").strip()
                if key in ("command", "measure", "capture", "reference", "target"):
                    current[key] = value
                elif key == "files":
                    current["_files"] = True
                    current["files"].extend(
                        f.strip().strip("`") for f in value.split(",") if f.strip())
                elif key == "criteria":
                    current["_criteria"] = True
                    current["criteria"].extend(
                        item.strip() for item in value.split(",") if item.strip())
                else:
                    gaps.append(f"'{field.group(1)}:' does not belong in an Exit check")
            elif (current.get("_files") and re.match(r"^\s*[-*]\s+\S", line)):
                current["files"].append(line.strip()[1:].strip().strip("`"))
            elif (current.get("_criteria") and re.match(r"^\s*[-*]\s+\S", line)):
                current["criteria"].append(line.strip()[1:].strip())
            elif line.strip() and not line.lstrip().startswith("<!--"):
                gaps.append(f"unexpected text in {current['type']} exit check: {line.strip()}")
        if not checks:
            gaps.append("'## Exit' has no checks")
        for check in checks:
            kind_name = check["type"]
            if kind_name == "tests" and (not check.get("command") or not check["files"]):
                gaps.append("Tests exit checks need 'Command:' and files under 'Files:'")
            elif kind_name == "measure" and (not check.get("command") or not check.get("target")
                                                or not check["files"]):
                gaps.append("Measure exit checks need 'Command:', 'Target:' and files "
                            "under 'Files:'")
            elif kind_name == "critics" and (not check.get("capture") or not check.get("reference")
                                                or not check["criteria"] or not check["files"]):
                gaps.append("Critics exit checks need 'Capture:', 'Reference:', non-empty "
                            "'Criteria:' and files under 'Files:'")
            for path in check["files"]:
                if path.startswith("/") or ".." in Path(path).parts:
                    gaps.append(f"exit file '{path}' must be a path inside the project")
        kind = "checks"
        files = list(dict.fromkeys(path for check in checks for path in check["files"]))
        tests = next((check for check in checks if check["type"] == "tests"), None)
        command = tests.get("command", "") if tests else ""
        if len(checks) == 1 and checks[0]["type"] == "measure":
            measure, target = checks[0]["command"], checks[0]["target"]
        if len(checks) == 1 and checks[0]["type"] == "critics":
            capture, reference, criteria = (checks[0]["capture"], checks[0]["reference"],
                                            checks[0]["criteria"])
    elif judge is None:
        gaps.append("no '## Exit' or '## Judge' section")
    else:
        in_files = False
        in_criteria = False
        for line in judge:
            m = _FIELD.match(line)
            if m:
                key, value = m.group(1).lower(), m.group(2).strip()
                in_files = key == "files"
                in_criteria = key == "criteria"
                if key == "command":
                    command = value.strip("`").strip()
                elif key == "kind":
                    kind = value.strip("`").strip().lower()
                elif key == "measure":
                    measure = value.strip("`").strip()
                elif key == "target":
                    target = value.strip("`").strip()
                elif key == "capture":
                    capture = value.strip("`").strip()
                elif key == "reference":
                    reference = value.strip("`").strip()
                elif key == "criteria":
                    criteria.extend([item.strip() for item in value.split(",") if item.strip()])
                elif key == "keep":
                    keep = value.strip("`").strip()
                elif key == "playbook":
                    playbook = value.strip("`").strip().lower()
                    if playbook not in ("", "fix"):
                        gaps.append("'Playbook:' must be 'fix'")
                elif key == "settings":
                    settings = value.strip("`").strip().lower() == "may change"
                    if not settings:
                        gaps.append(f"'Settings: {value}' is unknown; use 'Settings: may change'")
                elif key == "large file":
                    target_path = value.strip("`").strip()
                    if not target_path or target_path.startswith("/") or ".." in Path(target_path).parts:
                        gaps.append("'Large file:' must name a path inside the project")
                    else:
                        if target_path not in large_files:
                            large_files.append(target_path)
                elif value:
                    files += [f.strip().strip("`") for f in value.split(",") if f.strip()]
            elif in_files and re.match(r"^\s*[-*]\s+\S", line):
                files.append(line.strip()[1:].strip().strip("`"))
            elif in_criteria and re.match(r"^\s*[-*]\s+\S", line):
                criteria.append(line.strip()[1:].strip())
        if kind not in ("feature", "fix", "scaffold", "goal", "gauntlet"):
            gaps.append(f"'Kind: {kind}' is unknown; use feature, fix, scaffold, goal or gauntlet")
        if kind in ("feature", "fix", "scaffold") and not command:
            gaps.append("'## Judge' has no 'Command:' line")
        if kind in ("feature", "fix") and not files:
            gaps.append("'## Judge' lists no judge files under 'Files:'")
        if kind == "goal" and (not measure or not target):
            gaps.append("goal judges need 'Measure:' and 'Target:' lines")
        if kind == "goal" and not files:
            gaps.append("goal judges need files under 'Files:' to freeze the measure "
                        "and its support")
        if kind == "gauntlet" and (not capture or not reference or not criteria):
            gaps.append("gauntlet judges need 'Capture:', 'Reference:' and non-empty 'Criteria:'")
        if kind == "gauntlet" and not files:
            gaps.append("gauntlet judges need files under 'Files:' to freeze the capture "
                        "and its support")
        for f in files:
            if f.startswith("/") or ".." in Path(f).parts:
                gaps.append(f"judge file '{f}' must be a path inside the project")
        if not gaps:
            check_type = ("measure" if kind == "goal" else
                          "critics" if kind == "gauntlet" else "tests")
            checks = [{"type": check_type, "command": measure if kind == "goal" else command,
                       "target": target, "capture": capture, "reference": reference,
                       "criteria": criteria, "files": files, "legacy_kind": kind}]
    if judge is not None and exit_lines is not None:
        for line in judge:
            m = _FIELD.match(line)
            if not m:
                continue
            key, value = m.group(1).lower(), m.group(2).strip()
            if key == "keep":
                keep = value.strip("`").strip()
            elif key == "playbook":
                playbook = value.strip("`").strip().lower()
                if playbook not in ("", "fix"):
                    gaps.append("'Playbook:' must be 'fix'")
            elif key == "settings":
                settings = value.strip("`").strip().lower() == "may change"
                if not settings:
                    gaps.append(f"'Settings: {value}' is unknown; use 'Settings: may change'")
            elif key == "large file":
                target_path = value.strip("`").strip()
                if (not target_path or target_path.startswith("/") or
                        ".." in Path(target_path).parts):
                    gaps.append("'Large file:' must name a path inside the project")
                elif target_path not in large_files:
                    large_files.append(target_path)
    if exit_lines is not None and not checks:
        gaps.append("'## Exit' has no valid checks")
    if gaps:
        raise Refused("the spec is incomplete: " + "; ".join(gaps),
                      "fix the issue body to match kit/spec-format.md")
    if done_when and len(stays) == len(done_when):
        gaps.append("every Done when item is marked (stays), so there is nothing to build")
    return Spec(done_when, command, files, kind, intent, tuple(out_of_scope), approach,
                keep, tuple(stays), settings, tuple(large_files), tuple(research),
                measure, target, capture, reference, tuple(criteria), tuple(checks), playbook,
                risks)
