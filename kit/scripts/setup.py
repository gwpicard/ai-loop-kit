"""Set up a project for the loop. Safe to run again: it only adds what is missing."""
import json, os, pathlib, sys
import common, merge
from common import LoopError, gh, git

LABELS = {"inbox": "ededed", "shaping": "fbca04", "ready": "0e8a16",
          "building": "1d76db", "needs-user": "d93f0b"}
SECTION = "## Loop\nTest command: <the command that runs your tests>\n"


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
    try:
        settings = common.read_settings(project)
    except common.SettingsError as e:
        say("refused: %s\nnext: add these lines to AGENTS.md, then run setup again:\n%s"
            % (e, SECTION))
        return 1
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
    os.makedirs(os.path.join(project, ".lite"), exist_ok=True)
    path = os.path.join(project, ".gitignore")
    text = pathlib.Path(path).read_text(encoding="utf-8") if os.path.exists(path) else ""
    if ".lite/" not in text.split():
        with open(path, "a", encoding="utf-8") as f:
            f.write(("" if not text or text.endswith("\n") else "\n") + ".lite/\n")
        changes.append(".gitignore now lists .lite/ (commit it yourself)")
    say("%s: %s" % ("changed" if changes else "ok", "; ".join(changes) or "nothing to add"))
    failure = merge.run_tests(project, git(["rev-parse", "origin/" + branch], cwd=project), command,
                               prepare=settings["Prepare command"])
    say("preflight: " + (failure or "the Test command passes on a fresh checkout of " + branch))
    say("optional: " + ("; ".join("%s: %s" % (k, settings[k]) for k in ("Test files command", "Prepare command", "Check command", "Smoke command") if settings[k]) or "no Check or Smoke command set") + "; Session minutes: %g; Parallel: %d; Defect rounds: %d" % (settings["Session minutes"], settings["Parallel"], settings["Defect rounds"]))
    say("advice: protect %s on GitHub (Settings, Branches) so only a pull request changes it" % base)
    say("summary: %d change(s), preflight %s" % (len(changes), "failed" if failure else "passed"))
    return 1 if failure else 0


if __name__ == "__main__":
    try:
        sys.exit(setup(sys.argv[1] if len(sys.argv) > 1 else "."))
    except LoopError as e:
        print("refused: %s\nnext: fix that, then run setup again" % e)
        sys.exit(1)
