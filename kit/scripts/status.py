"""Local loop history and current activity, without GitHub or sessions."""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re
from statistics import median


STAGES = {"test-writer": "test writer", "fails-first": "fails-first", "builder": "builder",
          "tests": "pre-review test run", "review": "reviewer", "fix": "fix", "merge": "merge",
          "drain": "drain", "pass": "pass"}


def event_time(value):
    return datetime.fromisoformat(re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", value)).timestamp()


def since_time(value, now):
    if value is None:
        return now - 12 * 3600
    duration = re.fullmatch(r"(\d+)([hm])", value)
    if duration:
        return now - int(duration[1]) * (3600 if duration[2] == "h" else 60)
    for fmt in ("%Y-%m-%d %H:%M", "%H:%M"):
        try:
            date = datetime.strptime(value, fmt)
            if fmt == "%H:%M":
                date = datetime.fromtimestamp(now).replace(hour=date.hour, minute=date.minute, second=0, microsecond=0)
            return date.timestamp()
        except ValueError:
            pass
    raise ValueError("--since needs YYYY-MM-DD HH:MM, HH:MM, or a duration such as 4h or 90m")


def read_events(project):
    events = []
    try:
        with Path(project, ".loop/events.jsonl").open(encoding="utf-8") as f:
            for line in f:
                try:
                    event = json.loads(line)
                    event_time(event["time"])
                    if not isinstance(event.get("kind"), str):
                        continue
                    events.append(event)
                except (ValueError, KeyError, TypeError):
                    pass
    except OSError:
        pass
    return events


def activity(events):
    steps, ended, active = {}, set(), set()
    for e in events:
        kind, number = e["kind"], e.get("issue")
        if kind == "step" and e.get("phase", "start") == "start":
            steps[number] = e
            ended.discard(number)
        elif kind in ("merged", "parked", "crashed"):
            ended.add(number)
            steps.pop(number, None)
        elif kind in ("drain", "pass"):
            (active.add if e.get("phase") == "start" else active.discard)(kind)
        elif kind == "exit":
            active.clear()
            ended.update(steps)
            steps.clear()
    doing = "running the end-of-loop pass" if "pass" in active else "draining" if "drain" in active else "idle"
    return steps, ended, doing


def build_state(project, alive):
    folder = Path(project, ".loop")
    def live(path):
        try:
            pid = int(path.read_text())
            return pid > 0 and alive(pid)
        except (OSError, ValueError):
            return False
    running = live(folder / "loop.pid")
    builds = {}
    for path in (folder / "builds").glob("*.step"):
        if not path.stem.isdigit():
            continue
        if not running and not live(path.with_suffix(".pid")):
            continue
        pid = path.with_suffix(".pid")
        if pid.exists() and not live(pid):
            continue
        try:
            builds[int(path.stem)] = (path.read_text().strip(), path.stat().st_mtime)
        except OSError:
            pass
    return running, builds


def throughput(events, now, since):
    """Aggregate completed work and reported usage in the selected wall-clock window."""
    window = [e for e in events if since <= event_time(e["time"]) <= now]
    seconds = max(0, now - since)
    stages, roles = {}, {}
    steps = [e for e in window if e["kind"] == "step" and e.get("phase") == "end"
             and isinstance(e.get("seconds"), (int, float))]
    for e in steps:
        stage = stages.setdefault(e["step"], {"seconds": 0})
        stage["seconds"] += e["seconds"]
    for stage in stages.values():
        stage["share"] = stage["seconds"] / seconds if seconds else 0
    for e in window:
        if e["kind"] == "session":
            role = roles.setdefault(e.get("role", "unknown"), {})
            for field in ("turns", "input_tokens", "cached_input_tokens", "output_tokens"):
                if isinstance(e.get(field), (int, float)):
                    role[field] = role.get(field, 0) + e[field]
    slowest = sorted(steps, key=lambda e: (-e["seconds"], str(e.get("issue")), e["step"]))[:5]
    return dict(window_seconds=seconds,
                merged_per_hour=sum(e["kind"] == "merged" for e in window) * 3600 / seconds if seconds else 0,
                stages=stages, roles=roles,
                parks_by_rule=dict(Counter(e.get("rule", "unknown") for e in window if e["kind"] == "parked")),
                slowest_steps=[{k: e.get(k) for k in ("issue", "step", "seconds")} for e in slowest])


def render_throughput(report):
    lines = ["Throughput:", "  Issues merged per hour: %g" % report["merged_per_hour"],
             "  Stage seconds (share of window):"]
    for step, values in sorted(report["stages"].items()):
        lines.append("    %s: %g (%g%%)" % (STAGES.get(step, step), values["seconds"], values["share"] * 100))
    lines.append("  Usage per role (turns, input tokens, cached input tokens, output tokens; reported counts):")
    for role, counts in sorted(report["roles"].items()):
        lines.append("    %s: %s" % (role, ", ".join(str(counts.get(k, "unknown")) for k in
                     ("turns", "input_tokens", "cached_input_tokens", "output_tokens"))))
    lines.append("  Parks by rule: " + (", ".join("%s=%d" % p for p in sorted(report["parks_by_rule"].items())) or "none"))
    lines.append("  Five slowest steps (seconds):")
    for e in report["slowest_steps"]:
        lines.append("    #%s %s: %g" % (e["issue"], STAGES.get(e["step"], e["step"]), e["seconds"]))
    return "\n".join(lines)


def render(events, now, since=None, running=False, builds=None, as_json=False):
    """Render local status as text, or the throughput report as JSON."""
    since = since_time(None, now) if since is None else since
    report = throughput(events, now, since)
    if as_json:
        return json.dumps({"throughput": report})
    events = sorted((e for e in events if event_time(e["time"]) <= now), key=lambda e: event_time(e["time"]))
    window = [e for e in events if event_time(e["time"]) >= since]
    _, ended, doing = activity(events)
    current = []
    for n, (step, began) in sorted((builds or {}).items()):
        if n not in ended:
            current.append("#%d %s (%d min)" % (n, step, max(0, int(now - began) // 60)))
    lines = ["Loop: " + ("running" if running else "not running"),
             "Now: " + ("; ".join(current) if current else doing if running else "idle"),
             "Since: " + datetime.fromtimestamp(since).strftime("%Y-%m-%d %H:%M")]
    merged, parked = [], []
    for e in window:
        n = e.get("issue")
        if e["kind"] == "merged":
            history = [h for h in events if h.get("issue") == n and h["kind"] == "step"]  # from its first step to the merge
            seconds = event_time(e["time"]) - min([event_time(h["time"]) for h in history] or [event_time(e["time"])])
            rounds = max([h.get("round", 1) for h in history if h.get("step") == "review"] or [0])
            merged.append("  #%d: %.1f min, %d rounds" % (n, seconds / 60, rounds))
        elif e["kind"] == "parked":
            parked.append("  #%d: %s" % (n, " ".join(e.get("reason", "").splitlines())))
    for title, rows in (("Merged", merged), ("Parked", parked)):
        lines.append(title + ":" + (" none" if not rows else ""))
        lines += rows[:7]
        if len(rows) > 7:
            lines.append("  ... %d more" % (len(rows) - 7))
    lines.append("Crashes: %d" % sum(e["kind"] == "crashed" for e in window))
    rules = Counter(e["rule"] for e in window if e["kind"] == "rule")
    lines.append("Rules: " + (", ".join("%s=%d" % p for p in sorted(rules.items())) or "none"))
    lines.append("Stage seconds (total, median; completed in window):")
    for step, label in STAGES.items():
        samples = [e["seconds"] for e in window if e.get("phase") == "end" and "seconds" in e
                   and (e.get("step") if e["kind"] == "step" else e["kind"]) == step]
        if samples:
            lines.append("  %s: %g, %g" % (label, sum(samples), median(samples)))
    for field in ("agent", "model"):
        lines.append(field.capitalize() + "s: " + (", ".join(sorted({e[field] for e in window if e.get(field)})) or "none"))
    return "\n".join(lines) + "\n" + render_throughput(report)
