"""The supervisor: pick, build, answer, drain, keep the board, stop when idle."""
import contextlib
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import common
import flow
import merge
import pass_
import report
import session
import setup
import status
from common import GitError, gh, git, say

POLL = 120
BUSY_POLL = 45  # seconds between checks while builds run
CHECK_OUTPUT_LINES = 60
HERE = os.path.dirname(os.path.abspath(__file__))


def new_state():
    return dict(issues=[], closed=set(), factory=None, questions={}, trust={}, replies={}, building={}, deaths={}, attempts={}, deferred=None, started={}, pr=None, prs=[],
                parks={}, reaped=set(), conflict="", last="loop started", next="after the current step")


def take_lock(project):
    path = os.path.join(project, ".loop", "loop.pid")
    try:
        with open(path) as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        pid = None
    if pid is not None and alive(pid):
        return "refused: a loop is already running (pid %d)\nnext: loop.py stop, or wait" % pid
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(str(os.getpid()))


def last_pass(project):
    """The last pass report, or {} when missing or unreadable."""
    path = os.path.join(project, ".loop", "pass.json")
    try:
        with open(path) as f:
            last = json.load(f)
        if isinstance(last, dict):
            return last
    except (OSError, ValueError):
        pass
    return {}


def board_body(sections, last, next_check):
    parts = ["## %s\n\n%s\n" % (t, "\n".join(rows or ["Nothing."])) for t, rows in sections]
    return "\n".join(parts + ["Last event: " + last, "Next check: " + next_check, ""])


def step_of(project, number):
    try:
        with open(common.build_file(project, number, "step")) as f:
            return f.read().strip() or "starting"
    except OSError:
        return "starting"


def blocked_rows(st):
    """Rows for dependencies of `ready` issues that the loop will never build."""
    waiting, known = {}, {i["number"]: i for i in st["issues"]}
    for i in st["issues"]:
        if "ready" in i["labels"]:
            for d in set(common.depends_on(i["body"])) - st["closed"]:
                waiting[d] = waiting.get(d, 0) + 1
    rows = []
    for d, count in sorted(waiting.items()):
        i, by = known.get(d), "%d ready issue%s wait%s on it" % (count, "s" * (count != 1), "s" * (count == 1))
        if i and i["labels"] & {"ready", "building", "needs-user"}:
            continue
        title = i["title"] if i else "not found"
        closing = [p for p in st["prs"] if d in p["closes"] or d == p["number"]]
        if closing:
            action = "pull request #%d into %s is open, merge it" % (closing[0]["number"], closing[0]["base"])
        elif i:
            action = "shape the issue or label it `ready`"
        else:
            action = "check the `Depends on` line"
        rows.append("- #%d %s: %s (%s)" % (d, title, action, by))
    return rows


def progress_rows(st):
    """One line per open milestone with a `ready`, `building` or `needs-user` issue, counted as GitHub counts it."""
    active = {(i.get("milestone") or {}).get("number") for i in st["issues"]
              if i["labels"] & {"ready", "building", "needs-user"}} - {None}
    if not active:
        return []
    try:
        found = json.loads(gh(["api", "repos/{owner}/{repo}/milestones?state=open&per_page=100"]) or "[]")
    except ValueError:
        return []
    return ["- %s: %d of %d issues closed (%s)" % (m["title"], m["closed_issues"], m["closed_issues"] + m["open_issues"], m["html_url"])
            for m in sorted(found if isinstance(found, list) else [], key=lambda m: m["number"]) if m.get("number") in active]


def write_board(project, st, doing=None):
    of = lambda label: sorted((i for i in st["issues"] if label in i["labels"]),
                              key=lambda x: x["number"])
    row = lambda i, text: "- #%d %s: %s" % (i["number"], i["title"], text)
    b = st["building"]
    _, ended, recorded = status.activity(status.read_events(project))
    doing = doing or recorded
    parked = {i["number"] for i in of("needs-user")}
    parallel = {i["number"] for i in st["issues"] if common.issue_kind(i["body"]) == "parallel"}
    building = []
    for n, (since, _) in sorted(b.items()):
        if n in parked or n in ended:
            continue
        try:
            minutes = max(0, int(time.time() - os.path.getmtime(common.build_file(project, n, "step"))) // 60)
        except OSError:
            minutes = 0
        building.append("#%d%s, %s, since %s (%d min in step)" %
                        (n, " (parallel)" if n in parallel else "", step_of(project, n), since, minutes))
    if not building and doing != "idle":
        building = [doing]
    why = []
    if not building and of("ready"):
        held = {d for i in of("ready") for d in common.depends_on(i["body"]) if d not in st["closed"]}
        why = ["dependencies held by needs-user: " + ", ".join("#%d %s" % (i["number"], i["title"])
               for i in of("needs-user") if i["number"] in held)] if held & parked else []
        if st["deferred"]:
            why.append("deferred for " + st["deferred"])
        waiting = park_wait(st)
        if waiting:
            why.append("drain in %d min" % math.ceil(waiting / 60))
    last = st["last"] + ("\nWhy idle: " + "; ".join(why) if why else "")
    body = board_body([
        ("Building now", building),
        ("Needs you", [row(i, st["questions"].get(i["number"], "") + " (reply on the issue)")
                       for i in of("needs-user")] + blocked_rows(st) + ([st["pr"]] if st["pr"] else [])
                      + ([st["conflict"]] if st["conflict"] else [])),
        ("Progress", progress_rows(st))], last, st["next"])
    if st["factory"] and st["factory"]["body"].strip() != body.strip():
        gh(["issue", "edit", str(st["factory"]["number"]), "--body-file", "-"], input=body)
        st["factory"]["body"] = body


def snapshot(st):
    listing = lambda state, fields: json.loads(gh(
        ["issue", "list", "--state", state, "--limit", "500", "--json", fields]))
    opened = listing("open", "number,title,body,labels,updatedAt,milestone")
    st["factory"] = ([i for i in opened if i["title"] == "Factory"] or [None])[0]
    st["issues"] = [dict(i, labels={l["name"] for l in i["labels"]})
                    for i in opened if i["title"] != "Factory"]
    if not st["factory"]:
        say("refused: no Factory issue to write the board on\nnext: run setup")
    st["closed"] = {i["number"] for i in listing("closed", "number")}
    st["prs"] = []
    try:
        pulls = json.loads(gh(["pr", "list", "--state", "all", "--limit", "500", "--json",
                               "number,baseRefName,state,closingIssuesReferences"]) or "[]")
    except ValueError:
        pulls = []
    for p in pulls if isinstance(pulls, list) else []:
        if not isinstance(p, dict) or not isinstance(p.get("number"), int):
            continue
        if p.get("state") == "MERGED":
            st["closed"].add(p["number"])  # a merged pull request on a `Depends on` line is done
        elif p.get("state", "OPEN") == "OPEN":
            st["prs"].append(dict(number=p["number"], base=p.get("baseRefName", ""),
                                  closes={r.get("number") for r in p.get("closingIssuesReferences") or []}))


def answer(st, protected=None):
    for i in [i for i in st["issues"] if "needs-user" in i["labels"]]:
        n = i["number"]
        comments = json.loads(gh(["issue", "view", str(n), "--json", "comments"]))["comments"]
        parks = [k for k, c in enumerate(comments) if c["body"].startswith("## Needs you") and common.MARKER in c["body"]]
        if not parks:
            continue
        try:
            st["parks"][n] = datetime.fromisoformat(comments[parks[-1]]["createdAt"].replace("Z", "+00:00")).timestamp()
        except (KeyError, ValueError):
            st["parks"].pop(n, None)
        st["questions"][n] = (comments[parks[-1]]["body"].splitlines() + ["", ""])[2]
        st["replies"][n] = [c["body"] for c in comments[parks[-1] + 1:]
                            if common.MARKER not in c["body"]
                            and common.has_write((c.get("author") or {}).get("login", ""))]
        if st["replies"][n]:
            paths = parked_test_paths(comments[parks[-1]]["body"])
            last = st["replies"][n][-1].strip()
            if paths and AGREES.search(last) and not DOUBTS.search(last):  # a collaborator clearly said yes
                for path in paths:
                    grant_path(i, path, protected if protected is not None else common.DEFAULTS["Protected paths"])
            common.remove_label(i["number"], "needs-user")
            common.add_label(i["number"], "ready")
            i["labels"] = (i["labels"] - {"needs-user"}) | {"ready"}


AGREES = re.compile(r"^\W*(yes|yep|yeah|agreed|approved|go ahead|ok|okay|sure|please do)\b", re.I)
DOUBTS = re.compile(r"\b(no|not|don'?t|but|except|instead|only|unless|maybe|if|wait|also)\b", re.I)


def parked_test_paths(park):
    """The test paths named in a park's question, never just its recommendation."""
    text = park.split("Reply on this issue")[0].split("\nRecommended:")[0].split(common.MARKER)[0].strip()
    paths = {t for t in re.findall(r"[\w./-]+\.\w+", text) if merge.is_test_file(t)}
    return sorted(paths) if text.endswith("?") else []


def grant_path(i, path, protected):
    """Add `path` to the issue's `## Protected paths this issue may change`."""
    body = i.get("body") or ""
    if merge.stop_reason(path, protected) or ".." in path.split("/") or path.startswith("/"):
        return  # a protected path is never granted by a reply
    if path in merge.allowed_paths(body):
        return
    m = re.search(r"^(## Protected paths this issue may change[^\n]*\n)(.*?)(?=^## |\Z)", body, re.S | re.M | re.I)
    if m:
        keep = [l for l in m.group(2).splitlines() if l.strip().strip("-* `").lower() not in ("", "none")]
        body = body[:m.start()] + m.group(1) + "\n" + "\n".join(keep + [path]) + "\n\n" + body[m.end():]
    else:
        body = body.rstrip("\n") + "\n\n## Protected paths this issue may change\n\n" + path + "\n"
    gh(["issue", "edit", str(i["number"]), "--body-file", "-"], input=body)
    i["body"] = body


def trusted(st, i):
    key = (i["number"], i.get("updatedAt"))
    if key not in st["trust"]:
        st["trust"][key] = common.ready_is_trusted(i["number"])
    return st["trust"][key]


def pick(st, kinds=None):
    for i in sorted(st["issues"], key=lambda x: x["number"]):
        if ("ready" in i["labels"] and "building" not in i["labels"] and i["number"] not in st["building"]
                and (kinds is None or common.issue_kind(i["body"]) in kinds)
                and all(d in st["closed"] for d in common.depends_on(i["body"]))
                and trusted(st, i)):
            return i["number"]


def park_wait(st):
    """Seconds to hold the drain: while nothing builds and every ready issue is blocked, directly or
    through other ready issues, by an issue parked less than an hour ago."""
    if st["building"]:
        return 0
    open_ = {i["number"]: i for i in st["issues"]}
    parked = {n for n, i in open_.items() if "needs-user" in i["labels"]}
    ready = [n for n, i in open_.items() if "ready" in i["labels"]]
    def roots(n, seen=()):
        found = set()
        for d in set(common.depends_on(open_[n]["body"])) - st["closed"]:
            if d in parked:
                found.add(d)
            elif d in open_ and d not in seen and "ready" in open_[d]["labels"]:
                found |= roots(d, seen + (n,))
        return found
    blocking = [roots(n) for n in ready]
    if not blocking or not all(blocking):
        return 0
    return max([0] + [st["parks"][n] + 3600 - time.time() for r in blocking for n in r if n in st["parks"]])


def claim(st, number):
    """Label the issue `building` before any work starts."""
    common.add_label(number, "building")
    common.remove_label(number, "ready")
    for i in st["issues"]:
        if i["number"] == number:
            i["labels"] = (i["labels"] - {"ready"}) | {"building"}


def build_attempts(project, number, replies, previous=0):
    """Build one issue, a second time after a crash, and park it after two. Return a line for the board.
    This runs in a worker process."""
    common.wait_for_disk(project)
    for attempt in (1, 2):
        path = common.build_file(project, number, "attempt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(str(previous + attempt))
        say("building #%d, attempt %d" % (number, previous + attempt))
        for disk_retry in (False, True):  # a full disk waits and retries once without using an attempt
            try:
                r = flow.build(number, project, replies)
                if r.status != "failed":
                    return "#%d %s: %s" % (number, r.status, r.reason)
                reason = r.reason
            except common.GitHubError as e:  # GitHub trouble is not a crash: no attempt used
                say("GitHub problem on #%d, will try again: %s" % (number, e))
                time.sleep(POLL)
                return "#%d: GitHub problem, will try again" % number
            except Exception as e:  # a crash must not stop the loop
                reason = "%s: %s" % (type(e).__name__, e)
            if disk_retry or "no space left on device" not in reason.lower():
                break
            common.wait_for_disk(project, reason=reason, issue=number)
        common.event("crashed", project, issue=number, reason=reason, attempt=previous + attempt)
        say("crash on #%d: %s" % (number, reason))
        if attempt == 1:
            try:
                gh(["issue", "comment", str(number), "--body-file", "-"], retry=False,
                   input="The build crashed (%s). Trying once more.\n\n%s\n" % (reason, common.MARKER))
            except common.GitHubError as e:  # the comment is a report: a failed post must not strand the claimed issue
                say("the crash comment on #%d was not posted: %s" % (number, e))
    common.park(number, "The build crashed twice: " + reason,
                "Read .loop/logs, then reply to try again or close the issue.", project=project)
    return "#%d parked after two crashes" % number


def headroom():
    """None when the machine can take another build, else why not: load average at or above the CPU
    count, or (on macOS) critical memory pressure."""
    try:
        load, cpus = os.getloadavg()[0], os.cpu_count() or 1
        if load >= cpus:
            return "load average %.1f is not below the %d CPUs" % (load, cpus)
    except (OSError, AttributeError, ValueError):
        pass  # no way to tell: do not hold builds back
    level = common.pressure_level()
    if level == 4:
        return "memory pressure is critical"
    return None


def worker_command(project, number, replies, previous=0):
    return [sys.executable, os.path.join(HERE, "worker.py"), project, str(number), json.dumps(replies), str(previous)]


def start_builds(project, settings, st):
    """Fill `Parallel` build slots and one extra parallel slot while the machine has headroom.
    The first worker always starts; further workers wait on load and memory."""
    kinds = {i["number"]: common.issue_kind(i.get("body")) for i in st["issues"]}
    while True:
        running = [kinds.get(n, "build") for n in st["building"]]
        available = {kind for kind, cap in (("build", settings["Parallel"]), ("parallel", 1))
                     if running.count(kind) < cap}
        number = pick(st, available)
        if number is None:
            return
        if os.path.exists(os.path.join(project, ".loop", "stop")):
            return
        why = headroom() if st["building"] else None
        if why:
            if st["deferred"] != why.split()[0]:  # said when the kind of reason changes: load, or free memory
                say("deferring #%d: %s" % (number, why))
            st["deferred"] = why.split()[0]
            return
        st["deferred"] = None
        claim(st, number)
        os.makedirs(os.path.join(project, ".loop", "logs"), exist_ok=True)
        with open(os.path.join(project, ".loop", "logs", "build-%d.log" % number), "a") as log:
            proc = subprocess.Popen(worker_command(project, number, st["replies"].get(number, []), st["attempts"].get(number, st["deaths"].get(number, 0))), cwd=project,
                                    env=dict(common.build_env(), LOOP_BUILD_SETTINGS=json.dumps(settings),
                                             LOOP_TEST_WORKERS=str(max(1, (os.cpu_count() or 1) // settings["Parallel"]))),
                                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        os.makedirs(os.path.dirname(common.build_file(project, number, "pid")), exist_ok=True)
        with open(common.build_file(project, number, "pid"), "w") as f:
            f.write(str(proc.pid))
        st["started"][number] = time.time()
        st["building"][number] = (time.strftime("%H:%M"), proc)
        say("started a build process for #%d (pid %d); %d running" % (number, proc.pid, len(st["building"])))


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True


def stray_workers(project):
    """Pids recorded in .loop/builds/*.pid that are still running."""
    folder, pids = os.path.join(project, ".loop", "builds"), []
    for name in os.listdir(folder) if os.path.isdir(folder) else ():
        try:
            with open(os.path.join(folder, name)) as f:
                pid = int(f.read())
        except (OSError, ValueError):
            continue
        if name.endswith(".pid") and alive(pid):
            pids.append(pid)
    return pids


def reap(project, st, cap=None, stopped=False):
    """Collect the builds whose process has ended. One that left no result died: its issue is queued
    again once (the stale building label does it), and parked the second time."""
    for number, (_, proc) in list(st["building"].items()):
        if proc is None:
            continue
        stopping = stopped and proc.poll() is None
        if stopping:
            while True:
                rows = process_table()
                running = [p for p in live_tree(proc.pid, rows) if not rows[p][1].startswith("T")]
                if not running:
                    break
                signal_all(running, signal.SIGSTOP)
                time.sleep(0.05)
            pids = live_tree(proc.pid, process_table())
            for pid in reversed(pids):
                with contextlib.suppress(OSError):
                    os.killpg(pid, signal.SIGKILL)
            signal_all(reversed(pids), signal.SIGKILL)
            proc.wait()
        began = st["started"].get(number, time.time())
        if proc.poll() is None and cap and time.time() - began > cap and time.time() - began - common.paused_seconds(project, began, number) > cap:
            say("#%d: the build process ran over %d minutes, killing it" % (number, cap // 60))
            with contextlib.suppress(OSError):
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        if proc.poll() is None:
            continue
        del st["building"][number]
        try:
            if stopping:
                common.add_label(number, "ready")
                common.remove_label(number, "building")
                for i in st["issues"]:
                    if i["number"] == number:
                        i["labels"] = (i["labels"] - {"building"}) | {"ready"}
                common.event("exit", project, issue=number, reason="stopped")
                continue
            with open(common.build_file(project, number, "result")) as f:
                st["last"] = json.load(f)["last"]
            st["reaped"].add(number)  # a build that left a result: this cycle's labels predate it
            if st["last"].startswith("#%d parked" % number):  # the list may predate the park
                for i in st["issues"]:
                    if i["number"] == number:
                        i["labels"] = (i["labels"] - {"building", "ready"}) | {"needs-user"}
                st["parks"].setdefault(number, time.time())
            st["attempts"].pop(number, None)
            st["deaths"].pop(number, None)
        except (OSError, ValueError, KeyError):
            st["deaths"][number] = st["deaths"].get(number, 0) + 1
            reason = "the build process ended with exit code %s and no result" % proc.returncode
            try:
                with open(common.build_file(project, number, "attempt")) as f:
                    attempt = int(f.read())
            except (OSError, ValueError):
                attempt = st["deaths"][number]
            st["attempts"][number] = attempt
            common.event("crashed", project, issue=number, reason=reason, attempt=attempt)
            say("crash on #%d: %s" % (number, reason))
            if st["deaths"][number] == 1:
                try:
                    gh(["issue", "comment", str(number), "--body-file", "-"], retry=False,
                       input="The build crashed (%s). Trying once more.\n\n%s\n" % (reason, common.MARKER))
                except common.GitHubError as e:  # the comment is a report: a failed post must not stop the reap
                    say("#%d: the crash comment did not post: %s" % (number, e))
            else:
                common.park(number, "The build crashed twice: " + reason,
                            "Read .loop/logs, then reply to try again or close the issue.", project=project)
                st["last"] = "#%d parked after two crashes" % number
                st["reaped"].add(number)
                del st["deaths"][number]
                st["attempts"].pop(number, None)
        finally:
            for kind in ("step", "result", "pid", "attempt", "memory"):
                with contextlib.suppress(OSError):
                    os.remove(common.build_file(project, number, kind))


def sync_default(project, loop, st):
    base = common.default_branch(project)
    git(["fetch", "--no-prune", "origin"], cwd=project)
    try:
        git(["merge-base", "--is-ancestor", "origin/" + base, "origin/" + loop], cwd=project)
        st["conflict"] = ""
        return False
    except GitError:
        if not st["conflict"]:
            say("merging origin/%s into %s" % (base, loop))
    files = []
    try:
        with common.scratch_tree(project, "origin/" + loop) as tree:
            try:
                git(["merge", "--no-edit", "origin/" + base], cwd=tree)
            except GitError:
                files = sorted(filter(None, git(["diff", "--name-only", "--diff-filter=U", "-z"], cwd=tree).split("\0")))
                raise
            git(["push", "origin", "HEAD:" + loop], cwd=tree)
        st["conflict"] = ""
        return True
    except GitError as e:
        message = "Merging %s into %s failed: %s" % (
            base, loop, "conflicting files: " + ", ".join(files) if files else e)
        if message != st["conflict"]:
            say(message)
            common.event("default-merge-failed", project, base=base, branch=loop, files=files, reason=message)
        st["conflict"] = message
        return False


def hands_on(project, base, loop, old_body):
    """The `## Hands-on checks` section: each merged issue's steps as boxes, keeping the boxes already ticked."""
    ticked = set()
    if "## Hands-on checks" in old_body:
        kept = old_body.split("## Hands-on checks")[-1].split("\n## ")[0]
        blocks_at = re.search(r"^#\d+ ", kept, re.M)  # the steps above the first issue block hold no checks
        ticked = set(re.findall(r"^- \[[xX]\] (.*)$", kept[blocks_at.start():] if blocks_at else "", re.M))
    log = git(["log", "--format=%s", "origin/%s..origin/%s" % (base, loop)], cwd=project, check=False)
    blocks = []
    for n in sorted({int(m) for m in re.findall(r"^Issue (\d+)", log, re.M)}):
        try:
            info = json.loads(gh(["issue", "view", str(n), "--json", "title,body"]))
        except (ValueError, common.GitHubError):  # an unreadable issue only leaves its steps out
            continue
        found = re.search(r"^## Hands-on check[ \t]*\n(.*?)(?=^## |\Z)", info.get("body") or "", re.M | re.S)
        steps = re.findall(r"^\s*\d+\.\s+(.+?)\s*$", found.group(1), re.M) if found else []
        if steps:
            blocks.append("#%d %s\n\n%s" % (n, info["title"], "\n".join(
                "- [%s] %s" % ("x" if s in ticked else " ", s) for s in steps)))
    if not blocks:
        return "## Hands-on checks\n\nnone\n"
    head = git(["rev-parse", "--short", "origin/" + loop], cwd=project, check=False).strip()
    intro = "Build: `%s` at `%s`.\n\n" % (loop, head)
    return "## Hands-on checks\n\n" + intro + "\n\n".join(blocks) + "\n"


def decisions(project, base, loop):
    """List each merged issue's recorded builder deviations, without shortening them."""
    log = git(["log", "--format=%s", "origin/%s..origin/%s" % (base, loop)], cwd=project, check=False)
    added = []
    for number in sorted({int(n) for n in re.findall(r"^Issue (\d+)\b", log, re.M)}):
        try:
            info = json.loads(gh(["issue", "view", str(number), "--json", "title,body,comments"]))
        except (ValueError, common.GitHubError):
            continue
        note = next((c.get("body") or "" for c in reversed(info.get("comments") or [])
                     if (c.get("body") or "").startswith("## Built")), "")
        found = re.search(r"^Deviations:[ \t]*(.*?)(?=\n\s*\nMerged as |\Z)", note, re.M | re.S)
        for item in found[1].strip().splitlines() if found else []:
            item = re.sub(r"^\s*[-*]\s+", "", item).strip()
            if item and item.lower() != "none":
                added.append("- #%d: %s" % (number, item))
    return "## Decisions to confirm\n\n" + ("\n".join(added) or "none") + "\n"


def summary(project, settings, head, landed):
    """The Summary, Evidence and Merge danger sections: one read-only session per new batch, saved for refreshes."""
    path = os.path.join(project, ".loop", "summary.json")
    try:
        with open(path) as f:
            saved = json.load(f)
    except (OSError, ValueError):
        saved = {}
    if saved.get("head") == head or "- Issue " not in landed:
        return saved.get("text", "")
    base, loop = common.default_branch(project), settings["Loop branch"]

    text = ""
    try:
        notes = []
        try:
            pass_.batch_lines(project, "origin/" + base, loop, notes)
        except (ValueError, common.GitHubError):  # unreadable build notes only thin the evidence
            pass
        with common.scratch_tree(project, "origin/" + loop) as tree:
            prompt = flow.brief("pr-summary") + (
                "\n\nLoop branch: %s\nTest command: %s\nBatch diff: git diff origin/%s...HEAD\n\nBuild notes:\n\n%s\n" % (
                    loop, settings["Test command"], base, "\n\n".join(notes)))
            reply = session.run("pass", prompt, tree, settings["Pass"][1], project, "summary", agent=settings["Pass"][0])[0]
        found = re.search(r"^## Summary\b.*?^## Evidence\b.*?^## Merge danger\b.*", reply, re.M | re.S)
        text = found.group(0).strip() + "\n" if found else ""
    except Exception as e:  # the summary never blocks the drain
        say("the pull request summary did not run: %s: %s" % (type(e).__name__, e))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(dict(head=head, text=text), f)
    return text


def drain(project, settings, st):
    with common.timed("drain", project) as end:
        if st.get("factory"):
            write_board(project, st)
        end["outcome"] = "fail"
        failed = _drain(project, settings, st)
        end["outcome"] = "fail" if failed else "pass"


def _drain(project, settings, st):
    """Test the loop branch, then create or refresh the one pull request into the default."""
    loop, base = settings["Loop branch"], common.default_branch(project)
    say("draining: running the Test command on " + loop)
    head, last = git(["rev-parse", "origin/" + loop], cwd=project), last_pass(project)
    failed = merge.run_tests(project, head, settings["Test command"], check=settings["Check command"],
                            prepare=settings["Prepare command"])
    landed = git(["log", "--format=- %s", "origin/%s..origin/%s" % (base, loop)], cwd=project)
    if "- Issue " in landed and not failed and head != last.get("head"):  # new merges since the last pass
        say("running the end-of-loop pass")
        if st.get("factory"):
            st["last"] = "running the end-of-loop pass"
            write_board(project, st, doing="running the end-of-loop pass")
        try:
            pass_report, text = pass_.run_pass(project, settings, last.get("head") or "origin/" + base)
        except Exception as e:  # the pass never blocks the drain or the pull request
            pass_report, text = {"errors": [str(e)]}, "## End-of-loop pass\n\nThe pass did not run: %s: %s\n" % (type(e).__name__, e)
        last = dict(head=last.get("head") if pass_report.get("errors") else head, time=time.strftime("%Y-%m-%d %H:%M"), text=text,
                    defects=len(pass_report.get("confirmed", [])),
                    inbox=sum(i.endswith("(inbox)") for i in pass_report.get("issues", [])))
        with open(os.path.join(project, ".loop", "pass.json"), "w") as f:
            json.dump(last, f)
    find = lambda: json.loads(gh(["pr", "list", "--head", loop, "--base", base, "--state",
                                  "open", "--json", "number,url"]))
    found = find()
    old = ""
    if found:
        try:
            old = json.loads(gh(["pr", "view", str(found[0]["number"]), "--json", "body"])).get("body") or ""
        except (ValueError, common.GitHubError):
            pass
    top = summary(project, settings, head, landed)
    body = (top + "\n" if top else "Built by the loop.\n\nThe summary did not run.\n\n")
    if st["conflict"]:
        body += "## Default branch merge\n\n" + st["conflict"] + "\n\n"
    body += report.section(report.render(project, settings)) + "\n"
    body += hands_on(project, base, loop, old) + "\n" + decisions(project, base, loop)
    body += "\n## Landed\n\n%s\n\nTests %s on the loop branch.\n" % (
        landed or "Nothing.", "fail: " + failed if failed else "pass")
    body += "\n" + last.get("text", "")  # a refresh keeps the report of the last pass
    if found:
        gh(["pr", "edit", str(found[0]["number"]), "--body-file", "-"], input=body)
    elif landed:  # a failed create is found by the next check, not repeated
        gh(["pr", "create", "--base", base, "--head", loop, "--title", "Loop branch into " + base,
            "--body-file", "-"], retry=False, input=body)
    st["pr"] = (find() or [{}])[0].get("url")
    st["last"] = "drained: " + (failed or "tests pass")
    return failed


OWN_LOG = re.compile(r"(build-\d+|(\d+|pass)-[a-z]+(-[a-z]+)*-\d+)\.log")  # its own logs only: 1.x left piece-* and run-* logs in .loop/logs


def clean_up(project, closed):
    """At loop exit: prune worktrees, drop its own logs older than 14 days, name what is left behind."""
    git(["worktree", "prune"], cwd=project, check=False)
    logs = os.path.join(project, ".loop", "logs")
    for path in [os.path.join(logs, n) for n in os.listdir(logs) if OWN_LOG.fullmatch(n)] if os.path.isdir(logs) else ():
        if os.path.isfile(path) and time.time() - os.path.getmtime(path) > 14 * 86400:
            os.remove(path)
    with contextlib.suppress(OSError):
        os.rmdir(os.path.join(os.path.dirname(project), ".loop-worktrees"))  # only when empty
    trees = [l[9:] for l in git(["worktree", "list", "--porcelain"], cwd=project, check=False).splitlines() if l.startswith("worktree ")][1:]
    old = [b for b in git(["branch", "--format=%(refname:short)", "--list", "issue/*"], cwd=project, check=False).split()
           if b[6:].isdigit() and int(b[6:]) in closed]
    say("left behind: worktrees: %s; branches of closed issues: %s" % (", ".join(trees) or "none", ", ".join(old) or "none"))


def process_table():
    """{pid: (ppid, state)} for every process."""
    out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,stat="], capture_output=True, text=True).stdout
    rows = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            rows[int(parts[0])] = (int(parts[1]), parts[2])
    return rows


def live_tree(root, rows):
    """The pids under root in `rows`, root first, each parent before its children; zombies left out."""
    found, todo = [], [root]
    while todo:
        pid = todo.pop(0)
        if pid in rows and pid not in found and not rows[pid][1].startswith("Z"):
            found.append(pid)
            todo += sorted(p for p, r in rows.items() if r[0] == pid)
    return found


def signal_all(pids, sig):
    for pid in pids:
        with contextlib.suppress(OSError):
            os.kill(pid, sig)


def board_line(line):
    """Put `line` first on the Factory board body, or take a pause line off it when `line` is empty."""
    opened = json.loads(gh(["issue", "list", "--state", "open", "--limit", "500", "--json",
                            "number,title,body,labels,updatedAt,milestone"]))
    board = ([i for i in opened if i["title"] == "Factory"] or [None])[0]
    if not board:
        return
    old = board["body"] or ""
    body = old.partition("\n")[2].lstrip("\n") if old.startswith("Paused since") else old
    body = line + "\n\n" + body if line else body
    if body.strip() != old.strip():
        gh(["issue", "edit", str(board["number"]), "--body-file", "-"], input=body)


def live_pid(project):
    try:
        with open(os.path.join(project, ".loop", "loop.pid")) as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        return None
    return pid if alive(pid) else None


def pause(project):
    pid, mark = live_pid(project), os.path.join(project, ".loop", "paused")
    if pid is None:
        return say("refused: no loop is running here; start one with loop run") or 1
    if os.path.exists(mark):
        return say("refused: the loop is already paused; run loop resume") or 1
    since = time.time()
    with open(mark, "w") as f:  # lets the next issue leave paused time out of its limits
        json.dump(dict(since=since, pid=pid), f)
    while True:  # the supervisor first; list again until every descendant is stopped, so nothing starts a child mid-freeze
        rows = process_table()
        running = [p for p in live_tree(pid, rows) if not rows[p][1].startswith("T")]
        if not running:
            break
        signal_all(running, signal.SIGSTOP)
        time.sleep(0.05)
    line = "Paused since %s. Resume with loop resume." % time.strftime("%H:%M", time.localtime(since))
    with open(os.path.join(project, ".loop", "loop.out"), "a") as f:  # the supervisor is frozen and cannot write it
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + line + "\n")
    try:
        board_line(line)
    except (common.GitHubError, ValueError, OSError) as e:
        say("the board was not updated: %s" % e)
    return say("paused %d processes; processor use stopped, memory is not freed at once; run loop resume" % len(live_tree(pid, process_table()))) or 0


def resume(project):
    pid, mark = live_pid(project), os.path.join(project, ".loop", "paused")
    if pid is None or not os.path.exists(mark):
        return say("refused: the loop is not paused; run loop pause") or 1
    while True:  # children before the supervisor, until nothing in the tree is stopped
        rows = process_table()
        tree = live_tree(pid, rows)
        stopped = [p for p in tree if rows[p][1].startswith("T")]
        if not stopped:
            break
        signal_all(reversed(stopped), signal.SIGCONT)
        time.sleep(0.05)
    with open(mark) as f, open(os.path.join(project, ".loop", "pauses"), "a") as g:  # for the limits
        g.write("%s %s\n" % (json.load(f)["since"], time.time()))
    os.remove(mark)
    try:
        board_line("")
    except (common.GitHubError, ValueError, OSError) as e:
        say("the board was not updated: %s" % e)
    return say("resumed %d processes" % len(tree)) or 0


def run(project):
    project = os.path.abspath(project)
    settings = common.read_settings(project)
    settings_error = None
    moved, busy = setup.tidy(project)
    if moved:
        say("runtime folder: moved " + "; ".join(moved))
    busy = busy or take_lock(project)
    if busy:
        return say(busy) or 1
    st, dirty, built = new_state(), True, time.time()
    cap = (3 * settings["Session minutes"] + 30) * 60  # seconds a build process may run
    builds = os.path.join(project, ".loop", "builds")
    if stray_workers(project):  # a loop that was killed left builds running: do not claim their issues again
        os.remove(os.path.join(project, ".loop", "loop.pid"))
        return say("refused: build processes of an earlier loop are still running (pids %s)\nnext: wait for them, "
                   "or end them, then start again" % ", ".join(map(str, stray_workers(project)))) or 1
    for name in os.listdir(builds) if os.path.isdir(builds) else ():  # left by a loop that was killed
        os.remove(os.path.join(builds, name))
    stop = os.path.join(project, ".loop", "stop")
    if os.path.exists(stop):
        os.remove(stop)
    reason = "interrupted"
    try:
        while not os.path.exists(stop):
            try:
                try:
                    settings = common.read_settings(project)
                    settings_error = None
                except common.SettingsError as e:
                    if str(e) != settings_error:
                        say("keeping previous settings: %s" % e)
                        settings_error = str(e)
                cap = (3 * settings["Session minutes"] + 30) * 60
                snapshot(st)
                st["reaped"] = set()
                reap(project, st, cap)
                for i in [i for i in st["issues"] if "building" in i["labels"] and i["number"] not in st["building"]
                          and i["number"] not in st["reaped"]]:
                    # only this loop builds, so a building label without a running build is stale
                    say("#%d was left building, queued again" % i["number"])
                    common.add_label(i["number"], "ready")
                    common.remove_label(i["number"], "building")
                    i["labels"] = (i["labels"] - {"building"}) | {"ready"}
                answer(st, settings["Protected paths"])
                start_builds(project, settings, st)
                if st["building"]:
                    dirty, built = True, time.time()
                    write_board(project, st)
                    wait_stop(stop, BUSY_POLL)
                    continue
                if not park_wait(st) and not os.path.exists(stop):
                    conflict = st["conflict"]
                    dirty = sync_default(project, settings["Loop branch"], st) or dirty
                    dirty = dirty or conflict != st["conflict"]
                    if dirty:
                        with common.settings_environment(settings):
                            drain(project, settings, st)
                        dirty = False
                if time.time() - built >= settings["Idle hours"] * 3600:
                    reason = "nothing built for %g hours" % settings["Idle hours"]
                    say("exiting: nothing built for %g hours" % settings["Idle hours"])
                    break
                st["next"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() + POLL))
                write_board(project, st)
            except Exception as e:  # one line, never a traceback or a silent death
                say("problem, will check again: %s: %s" % (type(e).__name__, e))
            wait_stop(stop, POLL)
        else:
            reason = "stop requested"
            say("exiting: stop requested")
        said = 0
        while st["building"]:  # running builds finish their current issue, unless `loop stop --now`
            if stop_now(stop):
                reap(project, st, stopped=True)
                break
            if time.time() - said >= BUSY_POLL:
                say("waiting for %d running builds" % len(st["building"]))
                said = time.time()
            time.sleep(0.2)
            reap(project, st, cap)
        st["next"], st["last"] = "none, the loop has stopped", "loop stopped"
        write_board(project, st)
    finally:
        common.event("exit", project, reason=reason)
        for _, proc in st["building"].values():  # only reached with builds left after an error or an interrupt
            if proc and proc.poll() is None:
                with contextlib.suppress(OSError):
                    os.killpg(proc.pid, signal.SIGTERM)
        for name in ("stop", "loop.pid", "paused", "pauses"):
            if os.path.exists(os.path.join(project, ".loop", name)):
                os.remove(os.path.join(project, ".loop", name))
        try:
            clean_up(project, st["closed"])
        except OSError as e:
            say("clean-up problem: %s" % e)
    return 0


def stop_now(path):
    with contextlib.suppress(OSError):
        with open(path) as f:
            return f.read().strip() == "now"
    return False


def wait_stop(path, seconds):
    for _ in range(math.ceil(seconds / 0.2)):
        if os.path.exists(path):
            break
        time.sleep(0.2)


def check(project):
    """Run the session's targeted tests and guardrails with bounded output."""
    try:
        settings = common.build_settings(project)
        test, description = merge.targeted_command(
            settings, project, os.environ.get("LOOP_START"),
            os.environ.get("LOOP_LOCKED", "").splitlines())
        for command in (test, settings["Check command"]):
            if not command:
                continue
            code, output = common.run_shell(command, project, merge.TEST_TIMEOUT,
                                            record=os.environ.get("LOOP_GROUPS"))
            if code != 0:
                print("failed: %s%s" % (command, " (timed out)" if code is None else ""))
                lines = output.strip().splitlines()
                if len(lines) > CHECK_OUTPUT_LINES:
                    print("output truncated; last %d lines:" % CHECK_OUTPUT_LINES)
                for line in lines[-CHECK_OUTPUT_LINES:]:
                    print(line)
                return 1
    except (common.LoopError, OSError) as e:
        print("failed: %s" % e)
        return 1
    print("passed: " + description.split(": ", 1)[1])
    return 0


def main(argv):
    project, cmd = os.getcwd(), (argv or [""])[0]
    if cmd == "check":
        if len(argv) != 1:
            print("usage: loop check")
            return 2
        return check(project)
    if cmd == "pause":
        return pause(project)
    if cmd == "resume":
        return resume(project)
    if cmd == "report":
        if len(argv) != 1:
            print("usage: loop report")
            return 2
        try:
            print(report.render(project, common.read_settings(project)))
        except (common.LoopError, GitError) as e:
            print(str(e))
            return 1
        return 0
    if cmd == "status":
        args = argv[1:]
        as_json = "--json" in args
        if as_json:
            args.remove("--json")
        if args and not (len(args) == 2 and args[0] == "--since"):
            print("usage: loop status [--since <time>] [--json]")
            return 2
        now = time.time()
        try:
            since = status.since_time(args[1] if args else None, now)
        except ValueError as e:
            print(str(e))
            return 2
        running, builds = status.build_state(project, alive)
        print(status.render(status.read_events(project), now, since, running, builds, as_json=as_json))
        return 0
    if cmd == "stop":
        if argv not in (["stop"], ["stop", "--now"]):
            return say("usage: loop stop [--now]") or 2
        os.makedirs(os.path.join(project, ".loop"), exist_ok=True)
        with open(os.path.join(project, ".loop", "stop"), "w") as f:
            f.write("now" if "--now" in argv else "")
        if live_pid(project) and os.path.exists(os.path.join(project, ".loop", "paused")):
            resume(project)
        common.event("stop", project, reason="stop requested")
        return say("stop requested; " + ("running builds end at once and their issues return to ready" if "--now" in argv else
                   "the loop starts nothing new and ends after its running builds finish their issue")) or 0
    if cmd in ("run", "check-version"):
        old = common.kit_version_refusal(project)
        if old:
            return say(old) or 1
        if cmd == "check-version":
            return 0
        _, refusal = setup.tidy(project)
        if refusal:
            return say(refusal) or 1
        common.record_kit_version(project)
    if cmd != "run":
        say("usage: loop.py run|stop|pause|resume|check|check-version|report|status [--since <time>]")
        return 2
    try:
        try:
            if sys.platform == "darwin":
                subprocess.run(["taskpolicy", "-b", "-p", str(os.getpid())],
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.nice(10)
        except (OSError, subprocess.CalledProcessError):
            say("could not set background priority; continuing")
        if sys.platform == "darwin" and shutil.which("caffeinate"):
            subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
        settings = common.read_settings(project)
        problem = common.codex_refusal(settings)
        if problem:
            say("refused: %s\nnext: install a current Codex or choose claude for that role" % problem)
            return 1
        problem = setup.missing(project, settings)
        if problem:  # before the lock is taken
            say("refused: %s\nnext: run %s" % (problem, os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup.py")))
            return 1
        return run(project)
    except common.LoopError as e:
        say("refused: %s\nnext: run setup, then try again" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
