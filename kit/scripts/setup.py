"""Set up a project for the loop. Safe to run again: it only adds what is missing."""
import contextlib, json, os, pathlib, sys
import common, merge
from common import LoopError, gh, git

LABELS = {"inbox": "ededed", "shaping": "fbca04", "ready": "0e8a16",
          "building": "1d76db", "needs-user": "d93f0b"}
SECTION = "## Loop\nTest command: <the command that runs your tests>\n"


V1 = {"run.lock", "heartbeat", "dashboard.html", "dashboard.json", "preferences.json", "summary.md",
      "why.md", "hypothesis", "outcome", "cache", "capture", "run-metrics"}  # files only kit 1.x kept in .loop/
OURS = {"loop.out", "loop.pid", "pass.json", "builds", "merge.lock", "stop"}  # never moved into .loop/v1/


def alive(path):
    try:
        with open(path) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        return None


def tidy(project):
    """Bring the runtime files into .loop/: kit 1.x files move into .loop/v1/, and the
    .lite/ folder of kit 2.0.0 moves into .loop/. Nothing is deleted except an emptied .lite/.
    Return (what moved, a refusal or None)."""
    loop, lite = os.path.join(project, ".loop"), os.path.join(project, ".lite")
    if alive(os.path.join(loop, "loop.pid")):  # a running loop's files are never moved
        return [], None
    pid = alive(os.path.join(lite, "loop.pid"))
    if pid:
        return [], "refused: a loop of kit 2.0.0 is running from .lite/ (pid %d)\nnext: stop it, then start again" % pid
    moved, kept = [], []
    try:
        names = sorted(os.listdir(loop)) if os.path.isdir(loop) else []
        if V1 & set(names):
            os.makedirs(os.path.join(loop, "v1"), exist_ok=True)
            for name in names:
                if name != "v1" and name not in OURS and not name.startswith(("passed-", "stop-")) \
                        and not os.path.exists(os.path.join(loop, "v1", name)):
                    os.rename(os.path.join(loop, name), os.path.join(loop, "v1", name))
                    moved.append(".loop/%s to .loop/v1/" % name)
        if os.path.isdir(lite):
            os.makedirs(loop, exist_ok=True)
            for name in sorted(os.listdir(lite)):
                old, new = os.path.join(lite, name), os.path.join(loop, name)
                if os.path.isfile(old) and os.path.isfile(new) and not os.path.exists(new + ".lite"):
                    new += ".lite"  # such as loop.out, which the start command creates first
                if not os.path.exists(new):
                    os.rename(old, new)
                    moved.append(".lite/%s to .loop/%s" % (name, os.path.basename(new) if new.endswith(".lite") else ""))
                elif os.path.isdir(old) and os.path.isdir(new):  # such as logs/: merge one level
                    for child in sorted(os.listdir(old)):
                        if not os.path.exists(os.path.join(new, child)):
                            os.rename(os.path.join(old, child), os.path.join(new, child))
                    with contextlib.suppress(OSError):
                        os.rmdir(old)  # only when emptied
                    moved.append(".lite/%s/ merged into .loop/%s/" % (name, name))
            kept = sorted(os.listdir(lite))
            if not kept:
                os.rmdir(lite)
    except OSError as e:
        return moved, "refused: the runtime files could not be moved into .loop/: %s\nnext: move them by hand, then start again" % e
    if kept:
        moved.append(".lite/ kept, as .loop/ already has: " + ", ".join(kept))
    return moved, None


def labels_present():
    return {l["name"] for l in json.loads(gh(["label", "list", "--limit", "200", "--json", "name"]))}


def factory_exists():
    found = json.loads(gh(["issue", "list", "--state", "open", "--search", "Factory in:title",
                           "--json", "number,title"]))
    return any(i["title"] == "Factory" for i in found)


def missing(project, settings):
    """Why the project is not set up for the loop, or None. Changes nothing."""
    branch = settings["Loop branch"]
    if not git(["remote", "get-url", "origin"], cwd=project, check=False):
        return "this folder has no origin remote"
    if not git(["ls-remote", "--heads", "origin", branch], cwd=project):
        return "the loop branch %s is not on origin" % branch
    if set(LABELS) - labels_present():  # also fails, with gh's reason, when gh cannot read the repository
        return "the loop labels are missing on GitHub"
    return None if factory_exists() else "there is no Factory issue"


def setup(project="."):
    """Run every step. Return the exit code; print one line per step."""
    changes, say = [], lambda line: print(line, flush=True)
    old = common.kit_version_refusal(project)
    if old:
        say(old)
        return 1
    common.record_kit_version(project)
    try:
        settings = common.read_settings(project)
    except common.SettingsError as e:
        say("refused: %s\nnext: add these lines to AGENTS.md, then run setup again:\n%s"
            % (e, SECTION))
        return 1
    moved, refusal = tidy(project)
    if refusal:
        say(refusal)
        return 1
    if moved:
        say("runtime folder: moved " + "; ".join(moved))
    problem = common.codex_refusal(settings)
    if problem:
        say("refused: %s\nnext: install a current Codex or choose claude for that role, then run setup again" % problem)
        return 1
    for role in common.ROLES:
        say("%s: %s" % (role, " ".join(settings[role])))
    branch, command = settings["Loop branch"], settings["Test command"]
    for name in sorted(set(LABELS) - labels_present()):
        gh(["label", "create", name, "--color", LABELS[name]])
        changes.append("label " + name)
    git(["fetch", "origin"], cwd=project)
    base = common.default_branch(project)
    if not git(["ls-remote", "--heads", "origin", branch], cwd=project):
        git(["push", "origin", "origin/%s:refs/heads/%s" % (base, branch)], cwd=project)
        changes.append("loop branch %s from %s" % (branch, base))
    if not factory_exists():
        url = gh(["issue", "create", "--title", "Factory", "--body", "The loop writes the board here."])
        gh(["issue", "pin", url.strip().rsplit("/", 1)[-1]])
        changes.append("Factory issue, pinned")
    os.makedirs(os.path.join(project, ".loop"), exist_ok=True)
    path = os.path.join(project, ".gitignore")
    text = pathlib.Path(path).read_text(encoding="utf-8") if os.path.exists(path) else ""
    if ".loop/" not in text.split():
        with open(path, "a", encoding="utf-8") as f:
            f.write(("" if not text or text.endswith("\n") else "\n") + ".loop/\n")
        changes.append(".gitignore now lists .loop/ (commit it yourself)")
    say("%s: %s" % ("changed" if changes else "ok", "; ".join(changes) or "nothing to add"))
    log, where = os.path.join(project, ".loop", "logs", "preflight.log"), []
    failure = merge.run_tests(project, git(["rev-parse", "origin/" + branch], cwd=project), command, tail=20,
                               check=settings["Check command"], prepare=settings["Prepare command"], log=log, where=where)
    say("preflight: " + (failure.replace(": ", ":\n", 1) if failure else "the Test command passes on a fresh checkout of " + branch))
    if failure:
        say("log: %s (the checkout ran in %s, removed afterwards)" % (log, where[0]))
        say("hint: a test that passes in the project folder but fails here usually depends on where the checkout lives or on files git does not track")
    say("optional: " + ("; ".join("%s: %s" % (k, settings[k]) for k in ("Test files command", "Prepare command", "Check command", "Smoke command") if settings[k]) or "no Check or Smoke command set") + "; Session minutes: %g; Parallel: %d" % (settings["Session minutes"], settings["Parallel"]))
    say("advice: protect %s on GitHub (Settings, Branches) so only a pull request changes it" % base)
    say("summary: %d change(s), preflight %s" % (len(changes), "failed" if failure else "passed"))
    return 1 if failure else 0


if __name__ == "__main__":
    try:
        sys.exit(setup(sys.argv[1] if len(sys.argv) > 1 else "."))
    except LoopError as e:
        print("refused: %s\nnext: fix that, then run setup again" % e)
        sys.exit(1)
