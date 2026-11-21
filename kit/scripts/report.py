"""What changed on the loop branch, from git, build notes and local events."""
from collections import Counter
import json
import re

import common
import merge
import status
from common import gh, git


def short(text, limit=180):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 3] + "..."


def listed(items, limit=3):
    items = list(items)
    return ", ".join(short(i) for i in items[:limit]) + (
        " and %d more" % (len(items) - limit) if len(items) > limit else "") or "none"


def changes(project, base, head):
    args = ["diff", "--no-renames", "-z"]
    states = git(args + ["--name-status", base, head], cwd=project).split("\0")
    states = dict(zip(states[1::2], states[0::2]))
    rows = []
    for row in git(args + ["--numstat", base, head], cwd=project).split("\0"):
        if row:
            added, removed, path = row.split("\t", 2)
            rows.append((path, int(added) if added != "-" else 0,
                         int(removed) if removed != "-" else 0, states[path]))
    return rows


def render(project, settings):
    base, head = "origin/" + common.default_branch(project), "origin/" + settings["Loop branch"]
    commits, seen = [], set()
    for line in git(["log", "--reverse", "--format=%H %s", base + ".." + head], cwd=project).splitlines():
        found = re.fullmatch(r"([0-9a-f]+) Issue (\d+)\b.*", line)
        if found and int(found[2]) not in seen:
            commits.append((found[1], int(found[2])))
            seen.add(int(found[2]))
    packages = set()
    for ref in (base, head):
        for path in git(["ls-tree", "-r", "--name-only", ref], cwd=project).splitlines():
            if path.count("/") == 1 and path.endswith("/__init__.py"):
                packages.add(path.split("/")[0])
    def folder(path):
        parts = path.split("/")
        depth = 2 if parts[0] == "src" or parts[0] in packages else 1
        return "/".join(parts[:min(depth, len(parts) - 1)]) if len(parts) > 1 else "."
    rows = changes(project, base, head)
    groups = {}
    for path, added, removed, _ in rows:
        totals = groups.setdefault(folder(path), [0, 0, 0])
        for i, value in enumerate((1, added, removed)):
            totals[i] += value
    tests = Counter(state for path, _, _, state in rows if merge.is_test_module(path))
    support = [p for p, _, _, _ in rows if merge.is_test_file(p) and not merge.is_test_module(p)]
    source = [r for r in rows if not merge.is_test_file(r[0])]
    manifests = [p for p, _, _, _ in rows if merge.stop_reason(p, []) == "lockfile or package manifest"]
    deleted = [p for p, _, _, s in rows if s == "D" and merge.is_test_module(p)]
    churn = sorted(rows, key=lambda r: (-(r[1] + r[2]), r[0]))[:3]
    lines = ["Issues: %d" % len(commits),
             "Files: " + listed(("%s: %d files +%d -%d" % (p, *v) for p, v in sorted(groups.items())), 6),
             "Source: %d files +%d -%d" % (len(source), sum(r[1] for r in source), sum(r[2] for r in source)),
             "Tests: %d added, %d changed, %d deleted" % (tests["A"], tests["M"] + tests["T"], tests["D"]),
             "Manifests and lockfiles: " + listed(manifests),
             "Allowed paths: ", "Deleted tests: " + listed(deleted),
             "Most churn: " + listed("%s (+%d -%d)" % (p, a, d) for p, a, d, _ in churn)]
    events, allowed = status.read_events(project), set()
    for commit, number in commits:
        info = {}
        try:
            info = json.loads(gh(["issue", "view", str(number), "--json", "title,body,comments"], retry=False))
        except (ValueError, common.GitHubError):
            pass
        allowed.update(merge.allowed_paths(info.get("body") or ""))
        note = next((c.get("body") or "" for c in reversed(info.get("comments") or [])
                     if (c.get("body") or "").startswith("## Built")), "")
        built = re.split(r"^Deviations:|^## ", note.removeprefix("## Built").strip(), maxsplit=1, flags=re.M)[0]
        why = re.split(r"(?<=[.!?])\s+", " ".join(built.split()), maxsplit=1)[0]
        deviation = re.search(r"^Deviations:\s*(.*?)(?=\n\s*\n|\Z)", note, re.M | re.S)
        touched = changes(project, commit + "^1", commit)
        history = [e for e in events if e.get("issue") == number]
        ends = [status.event_time(e["time"]) for e in history if e["kind"] == "merged"]
        end = max(ends) if ends else None
        history = [e for e in history if end is None or status.event_time(e["time"]) <= end]
        starts = [status.event_time(e["time"]) for e in history if e["kind"] == "step" and e.get("phase", "start") == "start"]
        minutes = "%.1f min" % ((end - min(starts)) / 60) if end is not None and starts else "minutes unavailable"
        rounds = max([e.get("round", 1) for e in history if e["kind"] == "step" and e.get("step") == "review"] or [0])
        rules = Counter(e["rule"] for e in history if e["kind"] == "rule" and e.get("rule"))
        lines += ["Issue %d: %s" % (number, short(info.get("title") or "title unavailable")),
                  "  Why: " + (short(why) or "unavailable"),
                  "  Folders: " + listed(sorted({folder(r[0]) for r in touched})) +
                  "; tests added: " + listed(p for p, _, _, s in touched if s == "A" and merge.is_test_module(p)) +
                  "; tests changed: " + listed(p for p, _, _, s in touched if s in ("M", "T") and merge.is_test_module(p)),
                  "  Deviations: " + (short(deviation[1]) if deviation else "unavailable"),
                  "  %d review rounds; %d parks; rules: %s; %s" % (
                      rounds, sum(e["kind"] == "parked" for e in history),
                      listed("%s=%d" % pair for pair in sorted(rules.items())), minutes)]
    lines[5] += listed(sorted(allowed))
    lines.insert(7, "test support files changed: " + (", ".join(support) or "none"))
    return "\n".join(lines)


def section(text):
    fence = "`" * max(3, max([len(m[0]) + 1 for m in re.finditer(r"`+", text)] or [0]))
    return "## What changed\n\n%stext\n%s\n%s\n" % (fence, text, fence)
