"""The morning summary: what the run did, what waits for the person, and what was decided alone.

It is written from the run record, so it holds the decisions of the builders and of the run
script alike. Each decision names who made it. A summary with no decision says so, so the
person never has to wonder whether the list was left out.
"""

from __future__ import annotations

from pathlib import Path

from loop.run import record

SUMMARY_FILE = "summary.md"

_WORDS = {
    record.PENDING: "not started",
    record.BUILDING: "building",
    record.PARKED_PERSON: "parked, waiting for your answer",
    record.WAITING_PERSON: "waiting for you",
    record.WAITING: "waiting, never started",
    record.PARKED_SPEND: "parked at a spend cap",
    record.STOPPED: "stopped, back in ready with its branch kept",
    record.BUILT: "built",
    record.SENT_BACK: "back in shaping",
    record.RETURNED: "back in ready",
}


def render(run: record.RunRecord) -> str:
    data = run.data
    lines = [f"# Run {run.name}", ""]
    lines.append(
        f"The run is {data.get('status')}. It was "
        f"{'attended' if data.get('attended') else 'unattended'}, and the merge was "
        f"{'pre-approved' if data.get('merge_pre_approved') else 'not pre-approved'}."
    )
    lines.append(f"Spend: ${run.spend_total():.2f}.")
    lines += ["", "## Pieces", ""]
    for number in run.numbers():
        piece = run.piece(number)
        title = piece.get("title") or f"piece {number}"
        state = _WORDS.get(str(piece["status"]), str(piece["status"]))
        line = f"- Piece {number}, {title}: {state}."
        if piece.get("attempts"):
            line += f" Attempts used: {piece['attempts']}."
        if piece.get("spend_usd"):
            line += f" Spend: ${float(piece['spend_usd']):.2f}."
        lines.append(line)
        if piece.get("joined_to") and piece.get("joined"):
            lines.append(f"  Joined to {piece['joined_to']}.")
        if piece.get("reason"):
            lines.append(f"  Why: {piece['reason']}")
        if piece.get("question"):
            lines.append(f"  Question: {piece['question']}")
        if piece.get("next"):
            lines.append(f"  next: {piece['next']}")
    lines += ["", "## Decisions made alone", ""]
    decisions = data.get("decisions", [])
    if not decisions:
        lines.append("No decision was made alone.")
    for item in decisions:
        where = f"piece {item['piece']}" if item.get("piece") is not None else "the run"
        lines.append(f"- {item['by']}, {where}: {item['text']}")
    integration = data.get("integration") or {}
    final = integration.get("final") or {}
    if final or integration.get("worth_knowing"):
        lines += ["", "## Integration", ""]
        for name, item in final.items():
            lines.append(f"- {item.get('branch', name)}: the final check was "
                         f"{item.get('status')}, and the push was {item.get('push', 'not made')}.")
            if item.get("next"):
                lines.append(f"  next: {item['next']}")
    if integration.get("worth_knowing"):
        lines += ["", "## Worth knowing", ""]
        lines += [f"- {item['text']}" for item in integration["worth_knowing"]]
    if data.get("problems"):
        lines += ["", "## Problems", ""]
        lines += [f"- {item['text']}" for item in data["problems"]]
    if data.get("notes"):
        lines += ["", "## Notes", ""]
        lines += [f"- {item['text']}" for item in data["notes"]]
    return "\n".join(lines) + "\n"


def write(run: record.RunRecord) -> Path:
    target = run.paths.run_dir(run.name) / SUMMARY_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(run), encoding="utf-8")
    return target
