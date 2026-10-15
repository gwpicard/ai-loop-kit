#!/usr/bin/env python3
"""Run blind, fresh critic sessions against a captured artefact."""
from __future__ import annotations

import json
import mimetypes
import os
import random
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from urllib.request import urlopen
from loopkit import Refused, run_judge

KIT = Path(__file__).resolve().parent.parent
VERDICT = re.compile(r"<verdict>\s*(.*?)\s*</verdict>", re.I | re.S)


def capture(folder: Path, command: str) -> Path:
    target = folder / ".loop" / "capture"
    target.mkdir(parents=True, exist_ok=True)
    code, output = run_judge(folder, command)
    if code:
        raise Refused(f"Capture command failed:\n{output.strip()[-1500:]}",
                      "fix Capture: and run gate.py check again")
    files = sorted(path for path in target.iterdir() if path.is_file())
    if len(files) != 1:
        raise Refused(f"Capture must leave exactly one file in .loop/capture, found {len(files)}",
                      "write one captured artefact under .loop/capture")
    return files[0]


def reference_path(root: Path, reference: str) -> str:
    if re.match(r"^https?://", reference, re.I):
        return reference
    path = Path(reference)
    path = path.resolve() if path.is_absolute() else (root / path).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise Refused("Reference must be an existing project file or an http(s) URL",
                      "put the reference file in the project or use its URL")
    return str(path)


def parse_verdict(output: str, criteria: list[str]) -> dict:
    blocks = VERDICT.findall(output)
    if not blocks:
        raise ValueError("missing <verdict> block")
    try:
        data = json.loads(blocks[-1])
    except json.JSONDecodeError as error:
        raise ValueError(f"bad verdict JSON: {error}") from error
    if not isinstance(data, dict) or data.get("winner") not in ("A", "B", "tie"):
        raise ValueError("verdict winner must be A, B or tie")
    rows = data.get("criteria")
    if not isinstance(rows, list):
        raise ValueError("verdict needs a criteria list")
    found = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("winner") not in ("A", "B", "tie"):
            raise ValueError("each criterion verdict needs winner A, B or tie")
        name = row.get("criterion")
        if not isinstance(name, str) or name in found:
            raise ValueError("criterion names must be unique strings")
        if not isinstance(row.get("why"), str) or not row["why"].strip():
            raise ValueError(f"criterion {name!r} needs a reason")
        found[name] = row
    if set(found) != set(criteria):
        raise ValueError("verdict must name every criterion exactly once")
    data["criteria"] = [found[name] for name in criteria]
    return data


def score_verdicts(winners: list[str], ours_labels: list[str]) -> bool:
    if len(winners) != 3 or len(ours_labels) != 3:
        raise ValueError("a gauntlet needs exactly three critic verdicts")
    if any(winner not in ("A", "B", "tie") for winner in winners):
        raise ValueError("critic winner must be A, B or tie")
    return sum(winner == ours for winner, ours in zip(winners, ours_labels)) >= 2


def _reference_bytes(reference: str, folder: Path) -> tuple[bytes, str]:
    if re.match(r"^https?://", reference, re.I):
        with urlopen(reference, timeout=10) as response:
            data = response.read(10_000_001)
            content_type = response.headers.get_content_type()
        suffix = Path(urlparse(reference).path).suffix or mimetypes.guess_extension(content_type)
        return data[:10_000_000], suffix or ".bin"
    path = Path(reference)
    if not path.is_absolute():
        path = folder / path
    return path.read_bytes()[:10_000_000], path.suffix or ".txt"


def _prompt(template: str, criteria: list[str], a: str, b: str) -> str:
    text = template.replace("{{CRITERIA}}", "\n".join(f"- {item}" for item in criteria))
    return text.replace("{{A}}", a).replace("{{B}}", b)


def judge(capture: Path, reference: str, criteria: list[str], folder: Path,
          *, orders: Optional[list[bool]] = None) -> tuple[bool, str]:
    """Compare once per fresh Claude session and return pass plus full evidence."""
    current = capture.read_bytes()[:10_000_000]
    reference_data, reference_suffix = _reference_bytes(reference, folder)
    template = (KIT / "briefs" / "critic.md").read_text()
    choices = list(orders) if orders is not None else [random.SystemRandom().choice((True, False))
                                                       for _ in range(3)]
    if len(choices) != 3:
        raise ValueError("a gauntlet needs exactly three critic orders")
    claude = os.environ.get("LOOP_CLAUDE", "claude")
    verdicts, evidence = [], []
    for index, ours_is_a in enumerate(choices, 1):
        with tempfile.TemporaryDirectory(prefix="loop-critic-") as temp:
            critic_folder = Path(temp)
            ours_path = critic_folder / ("ours" + capture.suffix)
            ours_path.write_bytes(current)
            reference_path = critic_folder / ("reference" + reference_suffix)
            reference_path.write_bytes(reference_data)
            a, b = (ours_path.name, reference_path.name) if ours_is_a else \
                (reference_path.name, ours_path.name)
            prompt = _prompt(template, criteria, a, b)
            try:
                result = subprocess.run([claude, "-p", prompt, "--output-format", "text",
                                         "--tools", "Read"],
                                        cwd=critic_folder, capture_output=True, text=True,
                                        check=False, timeout=120)
            except subprocess.TimeoutExpired as error:
                raise ValueError(f"critic {index} timed out after 120 seconds") from error
        if result.returncode:
            raise ValueError(f"critic {index} failed with exit {result.returncode}: "
                             f"{result.stderr[-1000:]}")
        verdict = parse_verdict(result.stdout, criteria)
        verdicts.append(verdict["winner"])
        evidence.append({"critic": index, "ours": "A" if ours_is_a else "B",
                         "verdict": verdict})
    passed = score_verdicts(verdicts, ["A" if order else "B" for order in choices])
    return passed, json.dumps({"passed": passed, "critics": evidence}, sort_keys=True)
