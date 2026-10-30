"""Questions a builder asked and the answers the person gave, read from gate records."""
from __future__ import annotations

from loopkit import records

PATHS = ("retry", "reshape")
ANSWER_LIMIT = 2000


def split_recommendation(body: list[str]) -> tuple[list[str], dict]:
    """Take `Recommend:` and `Because:` lines out of an outcome body. An invalid or
    missing `Recommend:` value gives no recommendation."""
    path, because, rest = "", "", []
    for line in body:
        if line.startswith("Recommend:"):
            path = line[10:].strip().lower()
        elif line.startswith("Because:"):
            because = line[8:].strip()
        else:
            rest.append(line)
    return rest, ({"path": path, "because": because[:200]} if path in PATHS else {})


def latest_question(comments: list[str]) -> dict | None:
    """The question of the latest hand-back, when that hand-back asked one."""
    found = None
    for r in records(comments):
        if r.get("move") == "give-back":
            asked = r.get("cause") == "needs-answer"
            found = {"text": str(r.get("reason", "")), "asked_at": r.get("date"),
                     "recommendation": r.get("recommendation") or None,
                     "answered": False} if asked else None
        elif r.get("move") == "answer" and found:
            found["answered"] = True
    return found


def answers_text(comments: list[str]) -> str:
    """Every question and answer pair on the piece, oldest first."""
    pairs, asked = [], None
    for r in records(comments):
        if r.get("move") == "give-back":
            asked = str(r.get("reason", "")) if r.get("cause") == "needs-answer" else None
        elif r.get("move") == "answer" and asked is not None:
            pairs.append(f"Question: {asked}\nAnswer: {r.get('text', '')}")
            asked = None
    return "\n\n".join(pairs)
