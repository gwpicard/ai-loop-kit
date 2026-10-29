"""Numeric goal measurements and target comparisons."""
from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from loopkit import Refused, run_judge


@dataclass(frozen=True)
class Target:
    operator: str
    value: float

    def accepts(self, measured: float) -> bool:
        return {"<": measured < self.value, "<=": measured <= self.value,
                ">": measured > self.value, ">=": measured >= self.value}[self.operator]


def parse_target(text: str) -> Target:
    match = re.fullmatch(r"\s*(<=|>=|<|>)\s*(-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*", text)
    if not match:
        raise Refused("Target must use <, <=, > or >= followed by a number")
    value = float(match.group(2))
    if not math.isfinite(value):
        raise Refused("Target must be a finite number")
    return Target(match.group(1), value)


def parse_value(output: str) -> float:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        raise Refused("Measure printed no number")
    try:
        value = float(lines[-1])
    except ValueError as error:
        raise Refused("Measure's last line must be one number") from error
    if not math.isfinite(value):
        raise Refused("Measure's last line must be a finite number")
    return value


def measure_values(command: str, cwd: Optional[Path] = None,
                   runner: Optional[Callable[[str], tuple[int, str]]] = None,
                   protected_paths: list[str] | None = None) -> list[float]:
    """Run a measurement three times and return each last-line value."""
    def run() -> tuple[int, str]:
        if runner:
            return runner(command)
        code, output = run_judge(cwd or Path.cwd(), command, protected_paths=protected_paths)
        return code, output

    values = []
    for _ in range(3):
        code, output = run()
        if code:
            raise Refused(f"Measure failed with exit {code}:\n{output.strip()[-1200:]}")
        values.append(parse_value(output))
    return values


def median(values: list[float]) -> float:
    if len(values) != 3:
        raise Refused("Measure must produce exactly three values")
    return statistics.median(values)


def ready(folder: Path, command: str, target_text: str) -> tuple[str, dict]:
    """Check that main has not already reached a goal target."""
    target = parse_target(target_text)
    values = measure_values(command, folder)
    result = median(values)
    if target.accepts(result):
        raise Refused(f"Measure on main already meets Target {target_text}: {result}",
                      "change the goal so it names work that remains to be done")
    return f"Measure on main: {values}; median {result}; Target {target_text}", {
        "measure": command, "target": target_text,
        "main_measurements": values, "main_median": result}


def judge_attempt(folder: Path, ready_record: dict,
                  protected_paths: list[str] | None = None) -> tuple[int, str]:
    """Check one goal attempt and require its hypothesis record."""
    hypothesis = folder / ".loop" / "hypothesis"
    if not hypothesis.is_file() or not hypothesis.read_text().strip():
        return 1, "goal attempt did not record a hypothesis in .loop/hypothesis"
    try:
        values = measure_values(ready_record["measure"], folder, protected_paths=protected_paths)
        result = median(values)
        target = parse_target(ready_record["target"])
    except Refused as error:
        return 1, error.reason
    passed = target.accepts(result)
    return (0 if passed else 1), (f"Hypothesis: {hypothesis.read_text().strip()}\n"
                                  f"Measure values: {values}; median: {result}; "
                                  f"Target {ready_record['target']}: {'met' if passed else 'missed'}")
