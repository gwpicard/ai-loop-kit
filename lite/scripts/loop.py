"""The supervisor: pick, build, answer, drain, keep the board, stop when idle."""
import contextlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

import common
import flow
import merge
import pass_
import setup
from common import GitError, gh, git

POLL = 120
BUSY_POLL = 45  # seconds between checks while builds run
MIN_FREE = 1.5e9  # bytes of free plus inactive memory below which no new build starts (macOS)
HERE = os.path.dirname(os.path.abspath(__file__))
say = lambda text: print(text, flush=True)


def new_state():
    return dict(issues=[], closed=set(), factory=None, questions={}, trust={}, replies={}, building={}, deaths={}, deferred=None, started={}, pr=None,
                conflict="", last="loop started", next="after the current step")


def take_lock(project):
    path = os.path.join(project, ".lite", "loop.pid")
    try:
        with open(path) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return "refused: a loop is already running (pid %d)\nnext: loop.py stop, or wait" % pid
    except (OSError, ValueError):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(str(os.getpid()))


def last_pass(project):
    try:
        with open(os.path.join(project, ".lite", "pass.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
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


def write_board(project, st):
    of = lambda label: sorted((i for i in st["issues"] if label in i["labels"]),
                              key=lambda x: x["number"])
    row = lambda i, text: "- #%d %s: %s" % (i["number"], i["title"], text)
    waits = lambda i: "not built: labelled by a non-collaborator" if st["trust"].get(
        (i["number"], i.get("updatedAt"))) is False else "waits on " + (", ".join(
            "#%d" % d for d in common.depends_on(i["body"]) if d not in st["closed"]) or "nothing")
    base, b = common.default_branch(project), st["building"]
    git(["fetch", "--no-prune", "origin"], cwd=project, check=False)
    landed = git(["log", "--format=- %s", "origin/%s..origin/%s" % (
        base, common.read_settings(project)["Loop branch"])], cwd=project, check=False)
    p = last_pass(project)
    body = board_body([
        ("Building now", ["#%d, %s, since %s" % (n, step_of(project, n), since) for n, (since, _) in sorted(b.items())]),
        ("Needs you", [row(i, st["questions"].get(i["number"], "") + " (reply on the issue)")
                       for i in of("needs-user")]),
        ("Queue, in build order", [row(i, waits(i)) for i in of("ready")
                                   if i["number"] not in b]),
        ("To shape", [row(i, l) for l in ("inbox", "shaping") for i in of(l)]),
        ("Landed since the last merge into " + base, landed.splitlines()),
        ("Pull request into " + base, [st["pr"]] if st["pr"] else []),
        ("Last pass", ["%s: %s confirmed defects, %s inbox issues created, report in %s" % (
            p["time"], p["defects"], p["inbox"], st["pr"] or "the pull request") + (
            "; defect rounds limit reached, defects filed as inbox" if p.get("capped") else "")] if p else []),
        ("Conflict", [st["conflict"]] if st["conflict"] else ["None."])], st["last"], st["next"])
    if st["factory"] and st["factory"]["body"].strip() != body.strip():
        gh(["issue", "edit", str(st["factory"]["number"]), "--body-file", "-"], input=body)
        st["factory"]["body"] = body


def snapshot(st):
    listing = lambda state, fields: json.loads(gh(
        ["issue", "list", "--state", state, "--limit", "500", "--json", fields]))
    opened = listing("open", "number,title,body,labels,updatedAt")
    st["factory"] = ([i for i in opened if i["title"] == "Factory"] or [None])[0]
    st["issues"] = [dict(i, labels={l["name"] for l in i["labels"]})
                    for i in opened if i["title"] != "Factory"]
    if not st["factory"]:
        say("refused: no Factory issue to write the board on\nnext: run setup")
    st["closed"] = {i["number"] for i in listing("closed", "number")}


def answer(st):
    for i in [i for i in st["issues"] if "needs-user" in i["labels"]]:
        n = i["number"]
        comments = json.loads(gh(["issue", "view", str(n), "--json", "comments"]))["comments"]
        parks = [k for k, c in enumerate(comments) if c["body"].startswith("## Needs you")]
        if not parks:
            continue
        st["questions"][n] = (comments[parks[-1]]["body"].splitlines() + ["", ""])[2]
        st["replies"][n] = [c["body"] for c in comments[parks[-1] + 1:]
                            if common.MARKER not in c["body"]
                            and common.has_write((c.get("author") or {}).get("login", ""))]
        if st["replies"][n]:
            path = parked_test_path(comments[parks[-1]]["body"])
            last = st["replies"][n][-1].strip()
            if path and AGREES.search(last) and not DOUBTS.search(last):  # a collaborator clearly said yes
                grant_path(i, path)
            common.remove_label(i["number"], "needs-user")
            common.add_label(i["number"], "ready")
            i["labels"] = (i["labels"] - {"needs-user"}) | {"ready"}


AGREES = re.compile(r"^\W*(yes|yep|yeah|agreed|approved|go ahead|ok|okay|sure|please do)\b", re.I)
DOUBTS = re.compile(r"\b(no|not|don'?t|but|except|instead|only|unless|maybe|if|wait|also)\b", re.I)


def parked_test_path(park):
    """The one test path a park asks whether to change, or None."""
    text = park.split("Reply on this issue")[0]
    paths = {t for t in re.findall(r"[\w./-]+\.\w+", text) if merge.is_test_file(t)}
    asks = "?" in text and re.search(r"\b(change|edit|modify|update|reformat|adjust|relax)\b", text, re.I)
    return paths.pop() if len(paths) == 1 and asks else None


def grant_path(i, path):
    """Add `path` to the issue's `## Paths the builder may change`."""
    body = i.get("body") or ""
    if path in merge.allowed_paths(body):
        return
    m = re.search(r"^(## Paths the builder may change[^\n]*\n)(.*?)(?=^## |\Z)", body, re.S | re.M | re.I)
    if m:
        keep = [l for l in m.group(2).splitlines() if l.strip().strip("-* `").lower() not in ("", "none")]
        body = body[:m.start()] + m.group(1) + "\n" + "\n".join(keep + [path]) + "\n\n" + body[m.end():]
    else:
        body = body.rstrip("\n") + "\n\n## Paths the builder may change\n\n" + path + "\n"
    gh(["issue", "edit", str(i["number"]), "--body-file", "-"], input=body)
    i["body"] = body


def trusted(st, i):
    key = (i["number"], i.get("updatedAt"))
    if key not in st["trust"]:
        st["trust"][key] = common.ready_is_trusted(i["number"])
    return st["trust"][key]


def pick(st):
    for i in sorted(st["issues"], key=lambda x: x["number"]):
        if ("ready" in i["labels"] and "building" not in i["labels"] and i["number"] not in st["building"]
                and all(d in st["closed"] for d in common.depends_on(i["body"]))
                and trusted(st, i)):
            return i["number"]


def claim(st, number):
    """Label the issue `building` before any work starts."""
    common.add_label(number, "building")
    common.remove_label(number, "ready")
    for i in st["issues"]:
        if i["number"] == number:
            i["labels"] = (i["labels"] - {"ready"}) | {"building"}


def build_attempts(project, number, replies):
    """Build one issue, a second time after a crash, and park it after two. Return a line for the board.
    This runs in the loop when `Parallel` is 1 and in a worker process otherwise."""
    for attempt in (1, 2):
        say("building #%d, attempt %d" % (number, attempt))
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
        say("crash on #%d: %s" % (number, reason))
        if attempt == 1:
            gh(["issue", "comment", str(number), "--body-file", "-"], retry=False,
               input="The build crashed (%s). Trying once more.\n\n%s\n" % (reason, common.MARKER))
    common.park(number, "The build crashed twice: " + reason,
                "Read .lite/logs, then reply to try again or close the issue.")
    return "#%d parked after two crashes" % number


def build_once(project, st, number):
    claim(st, number)
    st["building"][number] = (time.strftime("%H:%M"), None)
    write_board(project, st)
    st["last"] = build_attempts(project, number, st["replies"].get(number, []))
    with contextlib.suppress(OSError):
        os.remove(common.build_file(project, number, "step"))


def headroom():
    """None when the machine can take another build, else why not: load average at or above the CPU
    count, or (on macOS) free plus inactive memory below MIN_FREE."""
    try:
        load, cpus = os.getloadavg()[0], os.cpu_count() or 1
        if load >= cpus:
            return "load average %.1f is not below the %d CPUs" % (load, cpus)
        if sys.platform == "darwin":
            out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=10).stdout
            free = sum(int(re.search(name + r":\s+(\d+)", out).group(1)) for name in ("Pages free", "Pages inactive"))
            free *= int(re.search(r"page size of (\d+)", out).group(1))
            if free < MIN_FREE:
                return "free plus inactive memory is %.1f GB, below %.1f GB" % (free / 1e9, MIN_FREE / 1e9)
    except (OSError, AttributeError, ValueError, subprocess.SubprocessError):
        pass  # no way to tell: do not hold builds back
    return None


def worker_command(project, number, replies):
    return [sys.executable, os.path.join(HERE, "worker.py"), project, str(number), json.dumps(replies)]


def start_builds(project, settings, st):
    """Claim and start eligible issues, each in its own process, up to `Parallel` and while the machine has
    headroom. The first build always starts: only a second one waits on load."""
    while len(st["building"]) < settings["Parallel"] and (number := pick(st)):
        why = headroom() if st["building"] else None
        if why:
            if st["deferred"] != why.split()[0]:  # said when the kind of reason changes: load, or free memory
                say("deferring #%d: %s" % (number, why))
            st["deferred"] = why.split()[0]
            return
        st["deferred"] = None
        claim(st, number)
        os.makedirs(os.path.join(project, ".lite", "logs"), exist_ok=True)
        with open(os.path.join(project, ".lite", "logs", "build-%d.log" % number), "a") as log:
            proc = subprocess.Popen(worker_command(project, number, st["replies"].get(number, [])), cwd=project,
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
    """Pids recorded in .lite/builds/*.pid that are still running."""
    folder, pids = os.path.join(project, ".lite", "builds"), []
    for name in os.listdir(folder) if os.path.isdir(folder) else ():
        try:
            with open(os.path.join(folder, name)) as f:
                pid = int(f.read())
        except (OSError, ValueError):
            continue
        if name.endswith(".pid") and alive(pid):
            pids.append(pid)
    return pids


def reap(project, st, cap=None):
    """Collect the builds whose process has ended. One that left no result died: its issue is queued
    again once (the stale building label does it), and parked the second time."""
    for number, (_, proc) in list(st["building"].items()):
        if proc is None:
            continue
        if proc.poll() is None and cap and time.time() - st["started"].get(number, time.time()) > cap:
            say("#%d: the build process ran over %d minutes, killing it" % (number, cap // 60))
            with contextlib.suppress(OSError):
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        if proc.poll() is None:
            continue
        del st["building"][number]
        try:
            with open(common.build_file(project, number, "result")) as f:
                st["last"] = json.load(f)["last"]
        except (OSError, ValueError, KeyError):
            st["deaths"][number] = st["deaths"].get(number, 0) + 1
            reason = "the build process ended with exit code %s and no result" % proc.returncode
            say("crash on #%d: %s" % (number, reason))
            if st["deaths"][number] == 1:
                gh(["issue", "comment", str(number), "--body-file", "-"], retry=False,
                   input="The build crashed (%s). Trying once more.\n\n%s\n" % (reason, common.MARKER))
            else:
                common.park(number, "The build crashed twice: " + reason,
                            "Read .lite/logs, then reply to try again or close the issue.")
                st["last"] = "#%d parked after two crashes" % number
        for kind in ("step", "result", "pid"):
            with contextlib.suppress(OSError):
                os.remove(common.build_file(project, number, kind))


def sync_default(project, loop, st):
    base = common.default_branch(project)
    git(["fetch", "--no-prune", "origin"], cwd=project)
    st["conflict"] = ""
    try:
        git(["merge-base", "--is-ancestor", "origin/" + base, "origin/" + loop], cwd=project)
        return False
    except GitError:
        say("merging origin/%s into %s" % (base, loop))
    try:
        with common.scratch_tree(project, "origin/" + loop) as tree:
            git(["merge", "--no-edit", "origin/" + base], cwd=tree)
            git(["push", "origin", "HEAD:" + loop], cwd=tree)
        return True
    except GitError as e:
        st["conflict"] = "Merging %s into %s did not go through: %s" % (base, loop, e)
        return False


def drain(project, settings, st):
    """Test the loop branch, then create or refresh the one pull request into the default."""
    loop, base = settings["Loop branch"], common.default_branch(project)
    say("draining: running the Test command on " + loop)
    head, last = git(["rev-parse", "origin/" + loop], cwd=project), last_pass(project)
    failed = merge.run_tests(project, head, settings["Test command"], check=settings["Check command"],
                            prepare=settings["Prepare command"])
    landed = git(["log", "--format=- %s", "origin/%s..origin/%s" % (base, loop)], cwd=project)
    body = "Built by the loop. Landed:\n\n%s\n\nTests %s on the loop branch.\n" % (
        landed or "Nothing.", "fail: " + failed if failed else "pass")
    if "- Issue " in landed and not failed and head != last.get("head"):  # new merges since the last pass
        say("running the end-of-loop pass")
        try:
            report, text = pass_.run_pass(project, settings, last.get("head") or "origin/" + base, rounds=last.get("rounds", 0))
        except Exception as e:  # the pass never blocks the drain or the pull request
            report, text = {"errors": [str(e)]}, "## End-of-loop pass\n\nThe pass did not run: %s: %s\n" % (type(e).__name__, e)
        last = dict(head=last.get("head") if report.get("errors") else head, time=time.strftime("%Y-%m-%d %H:%M"), text=text,
                    defects=len(report.get("confirmed", [])), rounds=report.get("rounds", last.get("rounds", 0)),
                    capped=bool(report.get("capped")),
                    inbox=sum(i.endswith("(inbox)") for i in report.get("issues", [])))
        with open(os.path.join(project, ".lite", "pass.json"), "w") as f:
            json.dump(last, f)
    body += "\n" + last.get("text", "")  # a refresh keeps the report of the last pass
    find = lambda: json.loads(gh(["pr", "list", "--head", loop, "--base", base, "--state",
                                  "open", "--json", "number,url"]))
    found = find()
    if found:
        gh(["pr", "edit", str(found[0]["number"]), "--body-file", "-"], input=body)
    elif landed:  # a failed create is found by the next check, not repeated
        gh(["pr", "create", "--base", base, "--head", loop, "--title", "Loop branch into " + base,
            "--body-file", "-"], retry=False, input=body)
    st["pr"] = (find() or [{}])[0].get("url")
    st["last"] = "drained: " + (failed or "tests pass")


def clean_up(project, closed):
    """At loop exit: prune worktrees, drop logs older than 14 days, name what is left behind."""
    git(["worktree", "prune"], cwd=project, check=False)
    logs = os.path.join(project, ".lite", "logs")
    for path in [os.path.join(logs, n) for n in os.listdir(logs)] if os.path.isdir(logs) else ():
        if time.time() - os.path.getmtime(path) > 14 * 86400:
            os.remove(path)
    with contextlib.suppress(OSError):
        os.rmdir(os.path.join(os.path.dirname(project), ".lite-worktrees"))  # only when empty
    trees = [l[9:] for l in git(["worktree", "list", "--porcelain"], cwd=project, check=False).splitlines() if l.startswith("worktree ")][1:]
    old = [b for b in git(["branch", "--format=%(refname:short)", "--list", "issue/*"], cwd=project, check=False).split()
           if b[6:].isdigit() and int(b[6:]) in closed]
    say("left behind: worktrees: %s; branches of closed issues: %s" % (", ".join(trees) or "none", ", ".join(old) or "none"))


def run(project):
    project = os.path.abspath(project)
    settings = common.read_settings(project)
    busy = take_lock(project)
    if busy:
        return say(busy) or 1
    st, dirty, built = new_state(), True, time.time()
    cap = (3 * settings["Session minutes"] + 30) * 60  # seconds a build process may run
    builds = os.path.join(project, ".lite", "builds")
    if stray_workers(project):  # a loop that was killed left builds running: do not claim their issues again
        os.remove(os.path.join(project, ".lite", "loop.pid"))
        return say("refused: build processes of an earlier loop are still running (pids %s)\nnext: wait for them, "
                   "or end them, then start again" % ", ".join(map(str, stray_workers(project)))) or 1
    for name in os.listdir(builds) if os.path.isdir(builds) else ():  # left by a loop that was killed
        os.remove(os.path.join(builds, name))
    stop = os.path.join(project, ".lite", "stop")
    if os.path.exists(stop):
        os.remove(stop)
    try:
        while not os.path.exists(stop):
            try:
                reap(project, st, cap)
                snapshot(st)
                for i in [i for i in st["issues"] if "building" in i["labels"] and i["number"] not in st["building"]]:
                    # only this loop builds, so a building label without a running build is stale
                    say("#%d was left building, queued again" % i["number"])
                    common.add_label(i["number"], "ready")
                    common.remove_label(i["number"], "building")
                    i["labels"] = (i["labels"] - {"building"}) | {"ready"}
                answer(st)
                if settings["Parallel"] == 1:  # one build at a time, in this process
                    number = pick(st)
                    if number:
                        build_once(project, st, number)
                        st["building"], dirty, built = {}, True, time.time()
                        continue
                else:  # each build is a process of its own; see worker.py
                    start_builds(project, settings, st)
                    if st["building"]:
                        write_board(project, st)
                        dirty, built = True, time.time()
                        time.sleep(BUSY_POLL)
                        continue
                dirty = sync_default(project, settings["Loop branch"], st) or dirty
                if dirty:
                    drain(project, settings, st)
                    dirty = False
                if time.time() - built >= settings["Idle hours"] * 3600:
                    say("exiting: nothing built for %g hours" % settings["Idle hours"])
                    break
                st["next"] = time.strftime("%H:%M", time.localtime(time.time() + POLL))
                write_board(project, st)
            except Exception as e:  # one line, never a traceback or a silent death
                say("problem, will check again: %s: %s" % (type(e).__name__, e))
            for _ in range(POLL // 5):
                os.path.exists(stop) or time.sleep(5)
        else:
            say("exiting: stop requested")
        while st["building"]:  # running builds finish their current issue
            say("waiting for %d running builds" % len(st["building"]))
            time.sleep(BUSY_POLL)
            reap(project, st, cap)
        st["next"], st["last"] = "none, the loop has stopped", "loop stopped"
        write_board(project, st)
    finally:
        for _, proc in st["building"].values():  # only reached with builds left after an error or an interrupt
            if proc and proc.poll() is None:
                with contextlib.suppress(OSError):
                    os.killpg(proc.pid, signal.SIGTERM)
        for name in ("stop", "loop.pid"):
            if os.path.exists(os.path.join(project, ".lite", name)):
                os.remove(os.path.join(project, ".lite", name))
        try:
            clean_up(project, st["closed"])
        except OSError as e:
            say("clean-up problem: %s" % e)
    return 0


def main(argv):
    project, cmd = os.getcwd(), (argv or [""])[0]
    if cmd == "stop":
        os.makedirs(os.path.join(project, ".lite"), exist_ok=True)
        open(os.path.join(project, ".lite", "stop"), "w").close()
        return say("stop requested; the loop ends after its current step") or 0
    if cmd != "run":
        say("usage: loop.py run|stop")
        return 2
    try:
        if sys.platform == "darwin" and shutil.which("caffeinate"):
            subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
        problem = setup.missing(project, common.read_settings(project))
        if problem:  # before the lock is taken
            say("refused: %s\nnext: run %s" % (problem, os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup.py")))
            return 1
        return run(project)
    except common.LoopError as e:
        say("refused: %s\nnext: run setup, then try again" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
