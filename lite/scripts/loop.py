"""The supervisor: pick, build, answer, drain, keep the board, stop when idle."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import common
import flow
import merge
import pass_
from common import GitError, gh, git

POLL = 120
say = lambda text: print(text, flush=True)


def new_state():
    return dict(issues=[], closed=set(), factory=None, questions={}, trust={}, replies={}, building=None, pr=None,
                conflict="", last="loop started", next="after the current step")


def default_branch(project):
    ref = git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=project, check=False)
    return ref.replace("origin/", "", 1) or "main"


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


def write_board(project, st):
    of = lambda label: sorted((i for i in st["issues"] if label in i["labels"]),
                              key=lambda x: x["number"])
    row = lambda i, text: "- #%d %s: %s" % (i["number"], i["title"], text)
    waits = lambda i: "not built: labelled by a non-collaborator" if st["trust"].get(
        (i["number"], i.get("updatedAt"))) is False else "waits on " + (", ".join(
            "#%d" % d for d in common.depends_on(i["body"]) if d not in st["closed"]) or "nothing")
    base, b = default_branch(project), st["building"]
    git(["fetch", "--no-prune", "origin"], cwd=project, check=False)
    landed = git(["log", "--format=- %s", "origin/%s..origin/%s" % (
        base, common.read_settings(project)["Loop branch"])], cwd=project, check=False)
    p = last_pass(project)
    body = board_body([
        ("Building now", ["#%s, %s, since %s" % b] if b else []),
        ("Needs you", [row(i, st["questions"].get(i["number"], "") + " (reply on the issue)")
                       for i in of("needs-user")]),
        ("Queue, in build order", [row(i, waits(i)) for i in of("ready")
                                   if i["number"] != (b or [0])[0]]),
        ("To shape", [row(i, l) for l in ("inbox", "shaping") for i in of(l)]),
        ("Landed since the last merge into " + base, landed.splitlines()),
        ("Pull request into " + base, [st["pr"]] if st["pr"] else []),
        ("Last pass", ["%s: %s confirmed defects, %s inbox issues created, report in %s" % (
            p["time"], p["defects"], p["inbox"], st["pr"] or "the pull request")] if p else []),
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
            common.remove_label(i["number"], "needs-user")
            common.add_label(i["number"], "ready")
            i["labels"] = (i["labels"] - {"needs-user"}) | {"ready"}


def trusted(st, i):
    key = (i["number"], i.get("updatedAt"))
    if key not in st["trust"]:
        st["trust"][key] = common.ready_is_trusted(i["number"])
    return st["trust"][key]


def pick(st):
    for i in sorted(st["issues"], key=lambda x: x["number"]):
        if ("ready" in i["labels"] and "building" not in i["labels"]
                and all(d in st["closed"] for d in common.depends_on(i["body"]))
                and trusted(st, i)):
            return i["number"]


def build_once(project, st, number):
    common.add_label(number, "building")
    common.remove_label(number, "ready")
    st["building"] = (number, "starting", time.strftime("%H:%M"))
    write_board(project, st)
    for attempt in (1, 2):
        say("building #%d, attempt %d" % (number, attempt))
        try:
            r = flow.build(number, project, st["replies"].get(number, []))
            if r.status != "failed":
                st["last"] = "#%d %s: %s" % (number, r.status, r.reason)
                return
            reason = r.reason
        except common.GitHubError as e:  # GitHub trouble is not a crash: no attempt used
            say("GitHub problem on #%d, will try again: %s" % (number, e))
            return time.sleep(POLL)
        except Exception as e:  # a crash must not stop the loop
            reason = "%s: %s" % (type(e).__name__, e)
        say("crash on #%d: %s" % (number, reason))
        if attempt == 1:
            gh(["issue", "comment", str(number), "--body-file", "-"], retry=False,
               input="The build crashed (%s). Trying once more.\n\n%s\n" % (reason, common.MARKER))
    common.park(number, "The build crashed twice: " + reason,
                "Read .lite/logs, then reply to try again or close the issue.")
    st["last"] = "#%d parked after two crashes" % number


def sync_default(project, loop, st):
    base = default_branch(project)
    git(["fetch", "--no-prune", "origin"], cwd=project)
    st["conflict"] = ""
    try:
        git(["merge-base", "--is-ancestor", "origin/" + base, "origin/" + loop], cwd=project)
        return False
    except GitError:
        say("merging origin/%s into %s" % (base, loop))
    with tempfile.TemporaryDirectory(prefix="lite-sync-") as parent:
        tree = parent + "/tree"
        try:
            git(["worktree", "add", "--detach", tree, "origin/" + loop], cwd=project)
            git(["merge", "--no-edit", "origin/" + base], cwd=tree)
            git(["push", "origin", "HEAD:" + loop], cwd=tree)
            return True
        except GitError as e:
            st["conflict"] = "Merging %s into %s did not go through: %s" % (base, loop, e)
            return False
        finally:
            git(["worktree", "remove", "--force", tree], cwd=project, check=False)
            git(["worktree", "prune"], cwd=project, check=False)


def drain(project, settings, st):
    """Test the loop branch, then create or refresh the one pull request into the default."""
    loop, base = settings["Loop branch"], default_branch(project)
    say("draining: running the Test command on " + loop)
    head, last = git(["rev-parse", "origin/" + loop], cwd=project), last_pass(project)
    failed = merge.run_tests(project, head, settings["Test command"], check=settings["Check command"])
    landed = git(["log", "--format=- %s", "origin/%s..origin/%s" % (base, loop)], cwd=project)
    body = "Built by the loop. Landed:\n\n%s\n\nTests %s on the loop branch.\n" % (
        landed or "Nothing.", "fail: " + failed if failed else "pass")
    if "- Issue " in landed and not failed and head != last.get("head"):  # new merges since the last pass
        say("running the end-of-loop pass")
        try:
            report, text = pass_.run_pass(project, settings, last.get("head") or "origin/" + base)
        except Exception as e:  # the pass never blocks the drain or the pull request
            report, text = {"errors": [str(e)]}, "## End-of-loop pass\n\nThe pass did not run: %s: %s\n" % (type(e).__name__, e)
        last = dict(head=last.get("head") if report.get("errors") else head, time=time.strftime("%Y-%m-%d %H:%M"), text=text,
                    defects=len(report.get("confirmed", [])),
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
    try:
        os.rmdir(os.path.join(os.path.dirname(project), ".lite-worktrees"))  # only when empty
    except OSError:
        pass
    trees = [l[9:] for l in git(["worktree", "list", "--porcelain"], cwd=project, check=False).splitlines()
             if l.startswith("worktree ")][1:]
    old = [b for b in git(["branch", "--format=%(refname:short)", "--list", "issue/*"], cwd=project,
                          check=False).split() if b[6:].isdigit() and int(b[6:]) in closed]
    say("left behind: worktrees: %s; branches of closed issues: %s" % (", ".join(trees) or "none", ", ".join(old) or "none"))


def run(project):
    project = os.path.abspath(project)
    settings = common.read_settings(project)
    busy = take_lock(project)
    if busy:
        return say(busy) or 1
    st, dirty, built = new_state(), True, time.time()
    stop = os.path.join(project, ".lite", "stop")
    if os.path.exists(stop):
        os.remove(stop)
    try:
        while not os.path.exists(stop):
            try:
                snapshot(st)
                for i in [i for i in st["issues"] if "building" in i["labels"]]:
                    # only this loop builds, so a building label between builds is stale
                    say("#%d was left building, queued again" % i["number"])
                    common.add_label(i["number"], "ready")
                    common.remove_label(i["number"], "building")
                    i["labels"] = (i["labels"] - {"building"}) | {"ready"}
                answer(st)
                number = pick(st)
                if number:
                    build_once(project, st, number)
                    st["building"], dirty, built = None, True, time.time()
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
        st["next"], st["last"] = "none, the loop has stopped", "loop stopped"
        write_board(project, st)
    finally:
        clean_up(project, st["closed"])
        for name in ("stop", "loop.pid"):
            if os.path.exists(os.path.join(project, ".lite", name)):
                os.remove(os.path.join(project, ".lite", name))
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
        return run(project)
    except common.LoopError as e:
        say("refused: %s\nnext: run setup, then try again" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
