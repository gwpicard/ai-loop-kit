#!/usr/bin/env python3
"""Run a goal measurement and compare its median with a fixed target."""
from __future__ import annotations

import math
import re
import statistics
from pathlib import Path

from loopkit import Refused, parse_spec as parse_loop_spec, run_judge

NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
TARGET = re.compile(r"^(<=|>=|==|!=|<|>)\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)$")


def parse_spec(body: str):
    """Read the common spec and the fields used by goal and gauntlet judges."""
    judge = next((part for part in body.split("## Judge", 1)[1:] if part), "")
    kind_match = re.search(r"^\s*Kind\s*:\s*(goal|gauntlet)\s*$", judge,
                           re.I | re.M)
    if not kind_match:
        return parse_loop_spec(body), {}
    kind = kind_match.group(1).lower()
    fields = {}
    for key in ("Measure", "Target", "Capture", "Reference"):
        match = re.search(rf"^\s*{key}\s*:\s*(.*?)\s*$", judge,
                          re.I | re.M)
        if match:
            fields[key.lower()] = match.group(1).strip().strip("`")
    criteria_match = re.search(r"^\s*Criteria\s*:\s*\n((?:\s*[-*].*\n?)+)",
                               judge, re.I | re.M)
    if criteria_match:
        fields["criteria"] = [line.strip()[1:].strip()
                              for line in criteria_match.group(1).splitlines()
                              if line.strip()]
    required = (("measure", "target") if kind == "goal" else
                ("capture", "reference", "criteria"))
    missing = [key.title() for key in required if not fields.get(key)]
    if missing:
        raise Refused("the spec is incomplete: " + ", ".join(missing) +
                      " is required for " + kind,
                      "fix the Judge section in kit/spec-format.md")
    if kind == "goal":
        try:
            parse_target(fields["target"])
        except ValueError as error:
            raise Refused(str(error), "fix Target: in the Judge section") from error
    command = fields["measure"] if kind == "goal" else fields["capture"]
    synthetic = re.sub(r"(^\s*Kind\s*:\s*)goal\s*$", r"\1scaffold", body,
                       flags=re.I | re.M)
    synthetic = re.sub(r"(^\s*Kind\s*:\s*)gauntlet\s*$", r"\1scaffold", synthetic,
                       flags=re.I | re.M)
    if not re.search(r"^\s*Command\s*:", judge, re.I | re.M):
        synthetic = re.sub(r"(^##\s*Judge\s*$)", rf"\1\nCommand: `{command}`",
                           synthetic, count=1, flags=re.I | re.M)
    spec = parse_loop_spec(synthetic)
    spec.kind = kind
    return spec, fields


def parse_target(target: str) -> tuple[str, float]:
    match = TARGET.fullmatch(target.strip())
    if not match:
        raise ValueError("Target must use <, <=, >, >=, == or != followed by a number")
    value = float(match.group(2))
    if not math.isfinite(value):
        raise ValueError("Target must be finite")
    return match.group(1), value


def parse_measurement(output: str) -> float:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines or not NUMBER.fullmatch(lines[-1]):
        raise ValueError("Measure must print one finite number on its last non-empty line")
    value = float(lines[-1])
    if not math.isfinite(value):
        raise ValueError("Measure must print one finite number on its last non-empty line")
    return value


def target_met(value: float, target: str) -> bool:
    operator, expected = parse_target(target)
    return {"<": value < expected, "<=": value <= expected, ">": value > expected,
            ">=": value >= expected, "==": value == expected,
            "!=": value != expected}[operator]


def median_value(values: list[float]) -> float:
    if len(values) != 3 or not all(math.isfinite(value) for value in values):
        raise ValueError("Measure must produce three finite values")
    return statistics.median(values)


def run_measure(command: str, folder: Path) -> tuple[float, str]:
    values, reports = [], []
    for index in range(1, 4):
        code, output = run_judge(folder, command)
        reports.append(f"Measure run {index}: exit {code}\n{output.strip()}")
        if code:
            raise ValueError(f"Measure command failed on run {index}:\n{output.strip()[-1500:]}")
        try:
            values.append(parse_measurement(output))
        except ValueError as error:
            raise ValueError(f"Measure output was invalid on run {index}: {error}") from error
    median = median_value(values)
    return median, "\n\n".join(reports) + f"\nMedian: {median:g}"
