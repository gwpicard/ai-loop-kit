#!/usr/bin/env python3
"""Audit a field-test project: do the kit's promises hold on GitHub?

Run it in a clone of the test project after a scenario:

    python3 <kit repo>/tests/field/audit.py [--doctor]

It reads every piece (an issue with a `state:` label) and its pull request,
checks the rules below, and scores each piece. It changes nothing.

Rules (a broken rule is a kit failure, exit 1):
  one-state     the piece has exactly one state label
  records       every state the piece passed through has a gate record, in a
                listed move, and the last record names the current state
  needs-you     the needs-you flag sits only on a piece in shaping
  merged        a done piece has a merged pull request and a closed issue
  bar           the judge files in the pull request are the ones fixed at ready
  generated     the pull request holds no generated files
  doctor        (with --doctor) main passes gate.py doctor

Scores per piece: builds, attempts, pieces sent back, and whether a person
changed the pull request after the gate judged it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

KIT = Path(__file__).resolve().parent.parent.parent / "kit" / "scripts"
sys.path.insert(0, str(KIT))
import gate  # noqa: E402
from gate import generated  # noqa: E402
from loopkit import (NEEDS_YOU, STATE_PREFIX, TRUSTED, GitHub, bar_hash_at, branch_name,  # noqa: E402
                     records, repo_root, sh)

BACK_MOVES = ("pull-back", "give-back", "reject", "rebuild")


def audit_piece(piece: dict, pr: Optional[dict], root: Path) -> tuple[list[str], dict]:
    """Check one piece. Returns (broken rules, score)."""
    broken: list[str] = []
    states = [x[len(STATE_PREFIX):] for x in piece["labels"] if x.startswith(STATE_PREFIX)]
    if len(states) != 1:
        broken.append(f"one-state: {len(states)} state labels {states}")
    state = states[0] if states else ""

    recs = records(piece["comments"])
    at = "new"
    for r in recs:
        frm, to = r.get("from"), r.get("to")
        if frm != at:
            broken.append(f"records: a '{r.get('move')}' record starts from {frm}, "
                          f"but the piece was in {at}")
        if gate.MOVES.get((frm, to)) != r.get("move"):
            broken.append(f"records: '{r.get('move')}' {frm} → {to} is not a listed move")
        at = to
    if state and at != state:
        broken.append(f"records: the label says {state}, the last gate record says {at}")

    if NEEDS_YOU in piece["labels"] and state != "shaping":
        broken.append(f"needs-you: flagged while in {state}")

    moves = [r.get("move") for r in recs]
    submits = [r for r in recs if r.get("move") == "submit"]
    failed = sum(1 for c in piece["comments"] if c.startswith("**Run:** attempt"))
    score = {"piece": piece["number"], "title": piece["title"], "state": state,
             "builds": moves.count("claim"), "attempts": failed + len(submits),
             "sent_back": sum(moves.count(m) for m in BACK_MOVES), "changed_after_gate": None}

    if pr:
        bad = [f for f in pr["files"] if generated(f)]
        if bad:
            broken.append(f"generated: the pull request holds {', '.join(bad[:5])}")
        ready = [r for r in recs if r.get("move") == "ready"]
        if ready and ready[-1].get("files") and pr.get("head") and pr["state"] != "CLOSED":
            if bar_hash_at(root, pr["head"], ready[-1]["files"],
                           ready[-1].get("bar_files")) != ready[-1]["bar"]:
                broken.append("bar: the judge files in the pull request differ from ready")
        if submits and submits[-1].get("commit") and pr.get("head"):
            score["changed_after_gate"] = pr["head"] != submits[-1]["commit"]
    if state == "done":
        if not pr or pr["state"] != "MERGED":
            broken.append("merged: done, but no merged pull request")
        if piece["state"] != "CLOSED":
            broken.append("merged: done, but the issue is still open")
    return broken, score


# ---------------------------------------------------------------- GitHub

def gh_json(root: Path, *args: str):
    return json.loads(sh(["gh", *args], root).stdout)


def load(root: Path) -> list[tuple[dict, Optional[dict]]]:
    """Every piece with its comments, and its pull request with head and files."""
    out = []
    issues = gh_json(root, "issue", "list", "--state", "all", "--limit", "500",
                     "--json", "number,title,labels,state")
    for i in sorted(issues, key=lambda x: x["number"]):
        labels = [lab["name"] for lab in i["labels"]]
        if not any(x.startswith(STATE_PREFIX) for x in labels):
            continue
        n = i["number"]
        comments = [c["body"] for c in gh_json(root, "issue", "view", str(n),
                                               "--json", "comments")["comments"]
                    if c.get("authorAssociation") in TRUSTED]
        piece = {**i, "labels": labels, "comments": comments}
        found = gh_json(root, "pr", "list", "--head", branch_name(n), "--state", "all",
                        "--limit", "1", "--json", "number,url,state,headRefOid,files")
        pr = None
        if found:
            f = found[0]
            sh(["git", "fetch", "--quiet", "origin", f"refs/pull/{f['number']}/head"], root,
               check=False)
            pr = {"url": f["url"], "state": f["state"], "head": f["headRefOid"],
                  "files": [x["path"] for x in f["files"]]}
        out.append((piece, pr))
    return out


def report(results: list[tuple[list[str], dict]], doctor: Optional[list] = None) -> tuple[str, bool]:
    lines, ok = [], True
    for broken, s in results:
        changed = {None: "unknown", True: "yes", False: "no"}[s["changed_after_gate"]]
        lines.append(f"piece {s['piece']} [{s['state']}] {s['title']}: builds {s['builds']}, "
                     f"attempts {s['attempts']}, sent back {s['sent_back']}, "
                     f"changed after the gate: {changed}")
        for b in broken:
            ok = False
            lines.append(f"  BROKEN {b}")
    for passed, what, _ in doctor or []:
        if not passed:
            ok = False
        lines.append(f"{'ok    ' if passed else 'BROKEN'} doctor: {what}")
    done = [s for _, s in results if s["state"] == "done"]
    clean = [s for s in done if s["builds"] == 1 and s["attempts"] == 1
             and s["changed_after_gate"] is not True]
    lines.append(f"\nPieces: {len(results)}. Done: {len(done)}. Done on the first "
                 f"attempt with no change after the gate: {len(clean)}. Rules: {'all hold' if ok else 'BROKEN'}.")
    return "\n".join(lines), ok


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--doctor", action="store_true", help="also run gate.py doctor on main")
    args = p.parse_args(argv)
    root = repo_root(Path.cwd())
    results = [audit_piece(piece, pr, root) for piece, pr in load(root)]
    checks = gate.doctor(GitHub(root), root) if args.doctor else None
    text, ok = report(results, checks)
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as e:
        print(f"audit stopped: {e}", file=sys.stderr)
        sys.exit(2)
