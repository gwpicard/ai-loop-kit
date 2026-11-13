"""The supervisor: pick, build, answer, drain, keep the board, stop when idle."""
import functools
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
from common import GitError, gh, git

POLL = 120
NOT_REPLIES = ("## Needs you", "TESTS:", "Loop:")
say = functools.partial(print, flush=True)

def new_state():
    return dict(issues=[], closed=set(), factory=None, questions={}, building=None, pr=None,
                conflict="", last="loop started", next="after the current step")

def default_branch(project):
    ref = git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=project, check=False)
    return ref.replace("origin/", "", 1) or "main"

def take_lock(project):
    """Return a refusal if a live loop holds the lock; a dead pid's lock is taken over."""
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

def board_body(sections, last, next_check):
    """Plain Markdown from (title, rows) pairs; an empty section reads `Nothing.`"""
    out = []
    for title, rows in sections:
        out += ["## " + title, ""] + (rows or ["Nothing."]) + [""]
    return "\n".join(out + ["Last event: " + last, "Next check: " + next_check, ""])

def write_board(project, st):
    ours = sorted(st["issues"], key=lambda x: x["number"])
    of = lambda label: [i for i in ours if label in i["labels"]]
    row = lambda i, text: "- #%d %s: %s" % (i["number"], i["title"], text)
    waits = lambda i: "waits on " + (", ".join("#%d" % d for d in common.depends_on(i["body"])
                                               if d not in st["closed"]) or "nothing")
    base, b = default_branch(project), st["building"]
    landed = git(["log", "--format=- %s", "origin/%s..origin/%s" % (
        base, common.read_settings(project)["Loop branch"])], cwd=project, check=False)
    body = board_body([
        ("Building now", ["#%s, %s, since %s" % b] if b else []),
        ("Needs you", [row(i, st["questions"].get(i["number"], "") + " (reply on the issue)")
                       for i in of("needs-user")]),
        ("Queue, in build order", [row(i, waits(i)) for i in of("ready")]),
        ("To shape", [row(i, l) for l in ("inbox", "shaping") for i in of(l)]),
        ("Landed since the last merge into " + base, landed.splitlines()),
        ("Pull request into " + base, [st["pr"]] if st["pr"] else []),
        ("Conflict", [st["conflict"]] if st["conflict"] else ["None."])], st["last"], st["next"])
    if st["factory"] and st["factory"]["body"].strip() != body.strip():
        gh(["issue", "edit", str(st["factory"]["number"]), "--body-file", "-"], input=body)
        st["factory"]["body"] = body

def snapshot(st):
    """Read the open and closed issues once; the queue and the board come from this."""
    listing = lambda state, fields: json.loads(gh(
        ["issue", "list", "--state", state, "--limit", "500", "--json", fields]))
    opened = listing("open", "number,title,body,labels")
    st["factory"] = ([i for i in opened if i["title"] == "Factory"] or [None])[0]
    st["issues"] = [dict(i, labels={l["name"] for l in i["labels"]})
                    for i in opened if i["title"] != "Factory"]
    if not st["factory"] and not st.setdefault("warned", False):
        st["warned"] = True
        say("refused: no Factory issue to write the board on\nnext: run setup")
    st["closed"] = {i["number"] for i in listing("closed", "number")}

def replies_for(number):
    """Collaborator comments after the last park comment, and its question."""
    comments = json.loads(gh(["issue", "view", str(number), "--json", "comments"]))["comments"]
    parks = [i for i, c in enumerate(comments) if c["body"].startswith("## Needs you")]
    if not parks:
        return [], ""
    later = [c["body"] for c in comments[parks[-1] + 1:] if not c["body"].startswith(NOT_REPLIES)
             and common.has_write((c.get("author") or {}).get("login", ""))]
    return later, (comments[parks[-1]]["body"].splitlines() + ["", ""])[2]

def answer(st):
    for i in [i for i in st["issues"] if "needs-user" in i["labels"]]:
        replies, st["questions"][i["number"]] = replies_for(i["number"])
        if replies:
            say("reply on #%d, queued again" % i["number"])
            common.remove_label(i["number"], "needs-user")
            common.add_label(i["number"], "ready")
            i["labels"] = (i["labels"] - {"needs-user"}) | {"ready"}

def pick(st):
    for i in sorted(st["issues"], key=lambda x: x["number"]):
        if ("ready" in i["labels"] and "building" not in i["labels"]
                and all(d in st["closed"] for d in common.depends_on(i["body"]))
                and common.ready_is_trusted(i["number"])):
            return i["number"]

def build_once(project, st, number):
    """Build with one retry after a crash; the second crash parks."""
    common.remove_label(number, "ready")
    common.add_label(number, "building")
    st["building"] = (number, "starting", time.strftime("%H:%M"))
    write_board(project, st)
    for attempt in (1, 2):
        say("building #%d (attempt %d)" % (number, attempt))
        try:
            r = flow.build(number, project, replies_for(number)[0])
            if r.status != "failed":
                st["last"] = "#%d %s: %s" % (number, r.status, r.reason)
                return
            reason = r.reason
        except Exception as e:  # a crash must not stop the loop
            reason = "%s: %s" % (type(e).__name__, e)
        say("crash on #%d: %s" % (number, reason))
        if attempt == 1:
            gh(["issue", "comment", str(number), "--body-file", "-"], retry=False,
               input="Loop: the build crashed (%s). Trying once more.\n" % reason)
    common.park(number, "The build crashed twice: " + reason,
                "Read .lite/logs, then reply to try again or close the issue.")
    st["last"] = "#%d parked after two crashes" % number

def sync_default(project, loop, st):
    """Merge the default branch into the loop branch when it has moved ahead."""
    base = default_branch(project)
    git(["fetch", "--no-prune", "origin"], cwd=project)
    st["conflict"] = ""
    try:
        return git(["merge-base", "--is-ancestor", "origin/" + base, "origin/" + loop], cwd=project)
    except GitError:
        say("merging origin/%s into %s" % (base, loop))
    with tempfile.TemporaryDirectory(prefix="lite-sync-") as parent:
        tree = parent + "/tree"
        try:
            git(["worktree", "add", "--detach", tree, "origin/" + loop], cwd=project)
            git(["merge", "--no-edit", "origin/" + base], cwd=tree)
            git(["push", "origin", "HEAD:" + loop], cwd=tree)
        except GitError as e:
            st["conflict"] = "Merging %s into %s did not go through: %s" % (base, loop, e)
        git(["worktree", "remove", "--force", tree], cwd=project, check=False)
        git(["worktree", "prune"], cwd=project, check=False)

def drain(project, settings, st):
    """Test the loop branch, then create or refresh the one pull request into the default."""
    loop, base = settings["Loop branch"], default_branch(project)
    say("draining: running the Test command on " + loop)
    git(["fetch", "--no-prune", "origin"], cwd=project)
    failed = merge.run_tests(project, git(["rev-parse", "origin/" + loop], cwd=project),
                             settings["Test command"])
    landed = git(["log", "--format=- %s", "origin/%s..origin/%s" % (base, loop)], cwd=project)
    body = "Built by the loop. Landed:\n\n%s\n\n%s\n" % (landed or "Nothing.", (
        "Tests fail on the loop branch: " + failed) if failed else "Tests pass on the loop branch.")
    found = json.loads(gh(["pr", "list", "--head", loop, "--base", base, "--state", "open",
                           "--json", "number,url"]))
    if found:
        gh(["pr", "edit", str(found[0]["number"]), "--body-file", "-"], input=body)
    elif landed:  # a failed create is found by the next check, not repeated
        gh(["pr", "create", "--base", base, "--head", loop, "--title", "Loop branch into " + base,
            "--body-file", "-"], retry=False, input=body)
    st["pr"] = found[0]["url"] if found else None
    st["last"] = "drained: " + (failed or "tests pass")

def run(project):
    project = os.path.abspath(project)
    settings = common.read_settings(project)
    busy = take_lock(project)
    if busy:
        say(busy)
        return 1
    st, dirty, built = new_state(), True, time.time()
    stop = os.path.join(project, ".lite", "stop")
    try:
        while not os.path.exists(stop):
            try:
                snapshot(st)
                answer(st)
                number = pick(st)
                if number:
                    build_once(project, st, number)
                    st["building"], dirty, built = None, True, time.time()
                    snapshot(st)
                    write_board(project, st)
                    continue
                sync_default(project, settings["Loop branch"], st)
                if dirty:
                    drain(project, settings, st)
                    dirty = False
                if time.time() - built >= settings["Idle hours"] * 3600:
                    say("exiting: nothing built for %g hours" % settings["Idle hours"])
                    break
                st["next"] = time.strftime("%H:%M", time.localtime(time.time() + POLL))
                write_board(project, st)
            except common.LoopError as e:
                say("problem, will check again: %s" % e)
            say("waiting %d seconds for the next check" % POLL)
            for _ in range(POLL // 5):
                os.path.exists(stop) or time.sleep(5)
        else:
            say("exiting: stop requested")
        st["next"], st["last"] = "none, the loop has stopped", "loop stopped"
        write_board(project, st)
    finally:
        for name in ("stop", "loop.pid"):
            if os.path.exists(os.path.join(project, ".lite", name)):
                os.remove(os.path.join(project, ".lite", name))
    return 0

def main(argv):
    project, cmd = os.getcwd(), (argv or [""])[0]
    if cmd == "stop":
        os.makedirs(os.path.join(project, ".lite"), exist_ok=True)
        open(os.path.join(project, ".lite", "stop"), "w").close()
        say("stop requested; the loop ends after its current step")
        return 0
    if cmd not in ("run", "board"):
        say("usage: loop.py run|stop|board")
        return 2
    try:
        if cmd == "board":
            st = new_state()
            snapshot(st)
            return write_board(project, st) or 0
        if sys.platform == "darwin" and shutil.which("caffeinate"):
            subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
        return run(project)
    except common.LoopError as e:
        say("refused: %s\nnext: run setup, then try again" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
