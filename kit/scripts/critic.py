"""Capture gauntlet artefacts and collect blind critic verdicts."""
from __future__ import annotations

import json
import random
import re
import shlex
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Callable, Optional

import agents
from loopkit import Refused, run_judge

KIT = Path(__file__).resolve().parent.parent


def capture(folder: Path, command: str, label: str) -> list[str]:
    """Run Capture into its named directory and return relative artefact paths."""
    target = folder / ".loop" / "capture" / label / uuid.uuid4().hex[:8]
    target.mkdir(parents=True, exist_ok=True)
    env_command = f"LOOP_CAPTURE_DIR={shlex.quote(str(target))} {command}"
    code, output = run_judge(folder, env_command)
    if code:
        raise Refused(f"Capture failed with exit {code}:\n{output.strip()[-1200:]}")
    files = sorted(path.relative_to(folder).as_posix()
                   for path in target.rglob("*") if path.is_file())
    if not files:
        raise Refused(f"Capture succeeded but produced an empty sample in "
                      f"{target.relative_to(folder)}")
    return files


def parse_verdict(output: str, criteria: list[str]) -> dict:
    matches = re.findall(r"<verdict>\s*(.*?)\s*</verdict>", output, flags=re.I | re.S)
    if not matches:
        raise ValueError("missing <verdict> block")
    try:
        data = json.loads(matches[-1].strip())
    except ValueError as error:
        raise ValueError(f"bad verdict JSON: {error}") from error
    if not isinstance(data, dict) or data.get("winner") not in ("A", "B", "tie"):
        raise ValueError("verdict winner must be A, B or tie")
    reasons = data.get("reasons")
    if not isinstance(reasons, dict) or set(reasons) != set(criteria):
        raise ValueError("verdict needs one reason for each criterion")
    for value in reasons.values():
        if (not isinstance(value, dict) or value.get("winner") not in ("A", "B", "tie")
                or not isinstance(value.get("reason"), str) or not value["reason"].strip()):
            raise ValueError("each criterion needs a winner and a non-empty reason")
    return {"winner": data["winner"], "reasons": reasons}


def _prompt(template: str, criteria: list[str], artefacts: dict[str, str]) -> str:
    text = template.replace("{{CRITERIA}}", "\n".join(f"- {item}" for item in criteria))
    text = text.replace("{{ARTEFACT_A}}", artefacts["A"])
    return text.replace("{{ARTEFACT_B}}", artefacts["B"])


def _stage_reference(folder: Path, reference: str) -> str:
    """Download a URL once so every critic sees the same local reference."""
    if not re.match(r"^https?://", reference):
        return reference
    suffix = Path(urllib.parse.urlparse(reference).path).suffix
    if not re.fullmatch(r"\.[A-Za-z0-9]{1,8}", suffix):
        suffix = ".data"
    loop_dir = folder / ".loop"
    loop_dir.mkdir(parents=True, exist_ok=True)
    target = loop_dir / f"gauntlet-reference-{uuid.uuid4().hex}{suffix}"
    try:
        with urllib.request.urlopen(reference, timeout=60) as response, target.open("wb") as out:
            data = response.read(32 * 1024 * 1024 + 1)
            if len(data) > 32 * 1024 * 1024:
                raise Refused("gauntlet reference is larger than 32 MiB")
            out.write(data)
    except (OSError, urllib.error.URLError) as error:
        raise Refused(f"could not read gauntlet reference: {error}") from error
    return str(target)


def _blind_paths(folder: Path, ours: list[str], reference: str,
                 ours_is_a: bool) -> dict[str, str]:
    """Copy local files under neutral names before exposing them to a critic."""
    loop_dir = folder / ".loop"
    loop_dir.mkdir(parents=True, exist_ok=True)
    pair = Path(tempfile.mkdtemp(prefix="loop-critic-", dir=loop_dir))
    slots = {"ours": "A" if ours_is_a else "B", "reference": "B" if ours_is_a else "A"}
    counts = {"ours": 0, "reference": 0}

    def expose(source: Path, label: str) -> str:
        counts[label] += 1
        target = pair / slots[label] / f"item-{counts[label]}"
        if source.is_dir():
            shutil.copytree(source, target)
            return str(target)
        target.mkdir(parents=True, exist_ok=True)
        suffix = source.suffix if re.fullmatch(r"\.[A-Za-z0-9]{1,8}", source.suffix) else ".data"
        copied = target / ("artefact" + suffix)
        shutil.copy2(source, copied)
        return str(copied)

    own_paths = [expose((folder / path).resolve(), "ours") for path in ours]
    if re.match(r"^https?://", reference):
        ref_path = reference
    else:
        source = (folder / reference).resolve()
        if not source.exists():
            raise Refused(f"gauntlet reference does not exist: {reference}")
        ref_path = expose(source, "reference")
    return {"A": ", ".join(own_paths) if ours_is_a else ref_path,
            "B": ref_path if ours_is_a else ", ".join(own_paths)}


def judge(folder: Path, ours: list[str], reference: str, criteria: list[str],
          template: Optional[str] = None,
          session: Optional[Callable[[str], str]] = None,
          agent: Optional[str] = None) -> list[dict]:
    """Run three fresh sessions with independently randomised artefact order."""
    brief = template if template is not None else (KIT / "briefs" / "critic.md").read_text()
    reference = _stage_reference(folder, reference)
    results = []
    for _ in range(3):
        ours_is_a = bool(random.SystemRandom().getrandbits(1))
        paths = _blind_paths(folder, ours, reference, ours_is_a)
        prompt = _prompt(brief, criteria, paths)
        if session:
            output = session(prompt)
        else:
            try:
                backend = agents.selected(folder, agent)
                proc = agents.start_session(backend, prompt, folder, role="critic")
                raw, _ = proc.communicate(timeout=600)
            except (OSError, subprocess.TimeoutExpired) as error:
                raise Refused(f"critic session did not finish: {error}") from error
            if proc.returncode:
                raise Refused("critic session failed: " + raw.decode(errors="replace")[-1200:])
            output = agents.event_text(raw, backend)
        try:
            verdict = parse_verdict(output, criteria)
        except ValueError as error:
            raise Refused(f"critic returned an invalid verdict: {error}") from error
        winner = verdict["winner"]
        verdict["order"] = "A=ours, B=reference" if ours_is_a else "A=reference, B=ours"
        if winner != "tie":
            verdict["winner"] = "ours" if (winner == "A") == ours_is_a else "reference"
        results.append(verdict)
    return results


def ready(folder: Path, capture_command: str, reference: str,
          criteria: list[str]) -> tuple[str, dict]:
    """Check that main does not already win its blind comparison."""
    artefacts = capture(folder, capture_command, "main")
    verdicts = judge(folder, artefacts, reference, criteria)
    wins = sum(verdict["winner"] == "ours" for verdict in verdicts)
    if wins >= 2:
        raise Refused("the artefact on main already wins the gauntlet",
                      "change the criteria or reference so the contract names work to do")
    return f"Main gauntlet: {wins}/3 wins; verdicts: {verdicts}", {
        "capture": capture_command, "reference": reference,
        "criteria": list(criteria), "main_capture": artefacts,
        "main_verdicts": verdicts}


def judge_attempt(folder: Path, ready_record: dict) -> tuple[int, str]:
    """Capture one attempt and require at least two blind wins."""
    try:
        number = ready_record.get("attempt", 1)
        artefacts = capture(folder, ready_record["capture"], f"attempt-{number}")
        verdicts = judge(folder, artefacts, ready_record["reference"], ready_record["criteria"],
                         agent=ready_record.get("agent"))
    except Refused as error:
        return 1, error.reason
    wins = sum(verdict["winner"] == "ours" for verdict in verdicts)
    return (0 if wins >= 2 else 1), f"Gauntlet wins: {wins}/3; verdicts: {verdicts}"
