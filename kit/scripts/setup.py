"""Set up a project for the loop and migrate older settings. Safe to run again."""
import argparse, json, os, pathlib, re, sys, tempfile, time
import common, merge
from common import LoopError, gh, git

LABELS = {"inbox": "ededed", "shaping": "fbca04", "ready": "0e8a16",
          "building": "1d76db", "needs-user": "d93f0b"}
SECTION = '{"Test command": "<the command that runs your tests>"}'


def change(project, what, undo, apply, dry_run=False):
    print(("would change: " if dry_run else "change: ") + what, flush=True)
    if dry_run:
        return
    result = apply()
    os.makedirs(os.path.join(project, ".loop"), exist_ok=True)
    with open(os.path.join(project, ".loop", "migrations.log"), "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(time=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                               kit=common.kit_version(), change=what, undo=undo)) + "\n")
    return result


def tidy(project, dry_run=False):
    """Refuse legacy runtime layouts and explain the intermediate upgrade."""
    loop, lite = os.path.join(project, ".loop"), os.path.join(project, ".lite")
    names = os.listdir(loop) if os.path.isdir(loop) else []
    if os.path.exists(lite) or set(names) & {"run.lock", "heartbeat", "dashboard.html", "dashboard.json",
            "preferences.json", "summary.md", "why.md", "hypothesis", "outcome", "cache", "capture", "run-metrics"}:
        return [], ("refused: this project has a .lite/ folder or kit 1.x files in .loop/\n"
                    "next: install kit 2.2.0, run its setup, then update to this version.\n"
                    "After kit 2.2.0 setup succeeds, stop any running loop and move any remaining .lite/ folder, "
                    "with all its contents, to an unused backup path outside this project before updating.")
    return [], None


def migrate_220(project, dry_run):
    path = pathlib.Path(project, "AGENTS.md")
    if not path.exists():
        return False
    with path.open(encoding="utf-8", newline="") as f:
        text = f.read()
    removed = [line for line, key, _ in common.setting_lines(text) if key == "Defect rounds"]
    if removed:
        kept = []
        inside = False
        for line in text.splitlines(keepends=True):
            if re.match(r"#{1,6}\s", line):
                inside = line.strip().lower() == "## loop"
            if not (inside and line in removed):
                kept.append(line)
        def apply():
            with path.open("w", encoding="utf-8", newline="") as f:
                f.write("".join(kept))
        change(project, "removed Defect rounds from AGENTS.md: confirmed defects now arrive as inbox issues",
               "restore under ## Loop in AGENTS.md: " + "".join(removed), apply, dry_run)
    return bool(removed)


MIGRATIONS = (("2.2.0", migrate_220),)


def migrate_issue_paths(project, dry_run=False):
    """Rename the protected-paths section, saving each original body for undo."""
    old = re.compile(r"^## Paths the builder may change(?=[ \t]*\r?$)", re.M)
    heading = "## Protected paths this issue may change"
    issues = json.loads(gh(["issue", "list", "--state", "open", "--limit", "10000",
                           "--json", "number,body"]) or "[]")
    if len(issues) >= 10000:
        raise LoopError("refused: open issue list may be truncated; no issue headings renamed")
    changed = False
    for issue in issues:
        body = issue.get("body") or ""
        renamed = old.sub(heading, body)
        if renamed == body:
            continue
        number = str(issue["number"])
        backup = pathlib.Path(".loop/migrations", "issue-%s-%s.md" % (number, time.time_ns()))
        def apply():
            path = pathlib.Path(project, backup)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as f:
                f.write(body.encode("utf-8"))
            gh(["issue", "edit", number, "--body-file", "-"], input=renamed)
        change(project, "issue %s: renamed section to %s" % (number, heading),
               "gh issue edit %s --body-file %s" % (number, backup.as_posix()), apply, dry_run)
        changed = True
    return changed


def migrate_plan(project, dry_run=False, branch="loop/main"):
    """Preserve every non-empty section of PLAN.md in one inbox issue."""
    path = pathlib.Path(project, "PLAN.md")
    log = pathlib.Path(project, ".loop/migrations.log")
    title = "Find a home for the contents of PLAN.md"
    if log.exists() and title in log.read_text(encoding="utf-8"):
        return False
    text, source = None, None
    ref = "refs/heads/" + branch
    if git(["ls-remote", "--heads", "origin", ref], cwd=project):
        # Keep previews read-only, including the checkout's remote-tracking refs.
        remote = git(["remote", "get-url", "origin"], cwd=project)
        if os.path.exists(os.path.join(project, remote)):
            remote = os.path.abspath(os.path.join(project, remote))
        with tempfile.TemporaryDirectory(prefix="loop-plan-") as scratch:
            git(["init", "--bare", scratch], cwd=project)
            git(["fetch", "--depth=1", remote, ref], cwd=scratch)
            if git(["ls-tree", "--name-only", "FETCH_HEAD", "--", "PLAN.md"], cwd=scratch):
                text = git(["show", "FETCH_HEAD:PLAN.md"], cwd=scratch)
                source = "origin/" + branch
    if text is None:
        if not path.exists():
            return False
        text = path.read_text(encoding="utf-8")
        source = "checkout " + git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=project)
    print("PLAN.md: read from " + source, flush=True)
    homes = {
        "decisions": "Move to AGENTS.md when every agent needs the decision and no check can enforce it.",
        "product rules": "Move to AGENTS.md when every agent needs the rule and no check can enforce it.",
        "stops": "Move the project's own stops to AGENTS.md; the kit's stops are in its preamble.",
        "surfaces": "Move to the Red-team surfaces list in loop.json.",
        "lessons": "Turn each lesson into a check or an AGENTS.md line, or drop it.",
        "deviations": "Drop these notes; git keeps them.",
        "try it": "Move the steps to README.md and include them in each issue's hands-on check when needed.",
    }
    sections = re.split(r"^##[ \t]+(.+?)[ \t]*$", text, flags=re.M)
    body = "Decide where these contents belong. PLAN.md is unchanged.\n"
    intro = re.sub(r"\A\s*# [^\n]*\n", "", sections[0]).strip()
    parts = [("Introduction", intro)] + list(zip(sections[1::2], sections[2::2]))
    for name, content in parts:
        if content.strip():
            home = homes.get(name.lower(), "Keep useful context in README.md, or in docs/ if it earns its place; otherwise drop it.")
            body += "\n## %s\n\n%s\n\nProposed home: %s\n" % (name, content.strip(), home)
            if dry_run:
                count = len(content.strip().splitlines())
                print("%s: %d %s. Proposed home: %s" %
                      (name, count, "line" if count == 1 else "lines", home), flush=True)
    if dry_run:
        change(project, title, "close the migration's inbox issue", lambda: None, True)
    else:
        # Recover an issue created before a failed log write without filing it twice.
        issues = json.loads(gh(["issue", "list", "--state", "all", "--search", title + " in:title",
                               "--limit", "500", "--json", "title,number"]) or "[]")
        number = next((str(i["number"]) for i in issues if i["title"] == title), None)
        if number is None:
            url = gh(["issue", "create", "--title", title, "--label", "inbox", "--body-file", "-"],
                     input=body, retry=False)
            number = url.strip().rsplit("/", 1)[-1]
        change(project, title, "close inbox issue " + number + "; PLAN.md was left unchanged",
               lambda: None)
    return True if dry_run else number


def migrate_settings(project, dry_run=False):
    """Move the old section into JSON, retaining the original text for undo."""
    path, config = pathlib.Path(project, "AGENTS.md"), pathlib.Path(project, "loop.json")
    if config.exists() or not path.exists():
        return None
    with path.open(encoding="utf-8", newline="") as f:
        text = f.read()
    if not any(line.strip().lower() == "## loop" for line in text.splitlines()):
        return None
    found = {key: value for _, key, value in common.setting_lines(text) if key != "Defect rounds"}
    for role, prefix in (("Builder", "Builder"), ("Test writer", "Builder"),
                         ("Reviewer", "Reviewer"), ("Pass", "Reviewer")):
        old = prefix + " model"
        if found.get(old) and not found.get(role):
            found[role] = "claude " + found[old]
    for prefix in ("Builder", "Reviewer"):
        old = prefix + " model"
        if old in found:
            print("notice: removed legacy setting %s; role settings now select the agent and model" % old,
                  flush=True)
            found.pop(old)
    for key in common.LIST_SETTINGS & found.keys():
        found[key] = [p.strip() for p in found[key].split(",") if p.strip()]
    for key in common.NUMERIC_SETTINGS & found.keys():
        try:
            found[key] = float(found[key])
            if found[key].is_integer():
                found[key] = int(found[key])
        except ValueError:
            raise common.SettingsError("AGENTS.md: invalid number for '%s'" % key)
    common.validate_settings(found, "loop.json")
    change(project, "created loop.json from AGENTS.md", "remove loop.json",
           lambda: config.write_text(json.dumps(found, indent=2) + "\n", encoding="utf-8"), dry_run)
    kept, removed, inside = [], [], False
    for line in text.splitlines(keepends=True):
        if re.match(r"#{1,6}\s", line):
            inside = line.strip().lower() == "## loop"
        (removed if inside else kept).append(line)
    def apply():
        with path.open("w", encoding="utf-8", newline="") as f:
            f.write("".join(kept))
    change(project, "removed ## Loop from AGENTS.md", "restore in AGENTS.md: " + "".join(removed),
           apply, dry_run)
    return found


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


def setup(project=".", dry_run=False):
    """Run every step. Return the exit code; print one line per step."""
    changes, say = [], lambda line: print(line, flush=True)
    counts, plan_references = {}, []
    agents_had_changes = False
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = pathlib.Path(project, name)
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        plan_references.extend((name, line) for line in lines if "PLAN.md" in line)
        if name == "AGENTS.md" and any(line.strip().lower() == "## loop" for line in lines):
            agents_had_changes = bool(git(["status", "--porcelain", "--", name], cwd=project))
        counts[name] = sum(len(line.split()) for line in lines
                           if not (name == "CLAUDE.md" and line.strip() == "@AGENTS.md"))
    if sum(counts.values()) > 1500:
        say("warning: standing instructions exceed the 1,500-word budget: " +
            "; ".join("%s: %s words" % (name, format(count, ",")) for name, count in counts.items()))
    old = common.kit_version_refusal(project)
    if old:
        say(old)
        return 1
    _, refusal = tidy(project, dry_run)
    if refusal:
        say(refusal)
        return 1
    if agents_had_changes:
        say("warning: AGENTS.md has uncommitted changes; migration uses those changes, not just the committed version")
    for version, migrate in MIGRATIONS:
        if migrate(project, dry_run):
            changes.append("migration " + version)
    try:
        migrated = migrate_settings(project, dry_run)
        if migrated is not None:
            changes.extend(["loop.json", "AGENTS.md"])
        if dry_run and migrated is not None:
            settings = dict(common.DEFAULTS, **migrated)
            for role in common.ROLES:
                settings[role] = tuple(settings[role].split())
        else:
            settings = common.read_settings(project)
    except common.SettingsError as e:
        say("refused: %s\nnext: set Test command: in loop.json, then run setup again:\n%s" % (e, SECTION))
        return 1
    path = pathlib.Path(project, ".loop", "kit-version")
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    if previous != common.kit_version() + "\n":
        change(project, ".loop/kit-version: " + common.kit_version(),
               "restore .loop/kit-version to " + repr(previous),
               lambda: common.record_kit_version(project), dry_run)
        changes.append("kit version " + common.kit_version())
    problem = common.codex_refusal(settings)
    if problem:
        say("refused: %s\nnext: install a current Codex or choose claude for that role, then run setup again" % problem)
        return 1
    for role in common.ROLES:
        say("%s: %s" % (role, " ".join(settings[role])))
    branch, command = settings["Loop branch"], settings["Test command"]
    common.warn_delete_branch_on_merge(project, say)
    for name in sorted(set(LABELS) - labels_present()):
        change(project, "label " + name, "remove label " + name,
               lambda: gh(["label", "create", name, "--color", LABELS[name]]), dry_run)
        changes.append("label " + name)
    plan_issue = migrate_plan(project, dry_run, branch)
    if plan_issue:
        changes.append("plan contents inbox issue")
    if migrate_issue_paths(project, dry_run):
        changes.append("protected paths issue headings")
    if not dry_run:
        git(["fetch", "origin"], cwd=project)
    base = common.default_branch(project)
    if not git(["ls-remote", "--heads", "origin", branch], cwd=project):
        change(project, "loop branch %s from %s" % (branch, base), "remove remote branch " + branch,
               lambda: git(["push", "origin", "origin/%s:refs/heads/%s" % (base, branch)], cwd=project), dry_run)
        changes.append("loop branch %s from %s" % (branch, base))
    if not factory_exists():
        url = change(project, "Factory issue", "close the newly created Factory issue",
                     lambda: gh(["issue", "create", "--title", "Factory", "--body", "The loop writes the board here."]), dry_run)
        change(project, "pin Factory issue", "unpin the Factory issue",
               lambda: gh(["issue", "pin", url.strip().rsplit("/", 1)[-1]]), dry_run)
        changes.append("Factory issue, pinned")
    path = os.path.join(project, ".gitignore")
    text = pathlib.Path(path).read_text(encoding="utf-8") if os.path.exists(path) else ""
    if "loop.local.json" not in text.splitlines():
        def ignore_local():
            with open(path, "a", encoding="utf-8") as f:
                f.write(("" if not text or text.endswith("\n") else "\n") + "loop.local.json\n")
        change(project, ".gitignore now lists loop.local.json", "remove the appended loop.local.json line from .gitignore",
               ignore_local, dry_run)
        changes.append(".gitignore now lists loop.local.json")
    if ".loop/" not in text.split():
        def ignore():
            with open(path, "a", encoding="utf-8") as f:
                f.write(("" if not text or text.endswith("\n") else "\n") + ".loop/\n")
        change(project, ".gitignore now lists .loop/ (commit it yourself)",
               "remove the appended .loop/ line from .gitignore" + (" and its preceding newline" if text and not text.endswith("\n") else ""), ignore, dry_run)
        changes.append(".gitignore now lists .loop/ (commit it yourself)")
    say("%s: %s" % (("preview" if dry_run else "changed") if changes else "ok", "; ".join(changes) or "nothing to add"))
    if dry_run:
        say("dry-run: no changes made; preflight skipped")
        return 0
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
    if plan_issue:
        say("next: place PLAN.md's contents using inbox issue %s before restarting the loop" % plan_issue)
    for name, line in plan_references:
        say('next: revise the instruction in %s that still names PLAN.md: "%s"' % (name, line))
    if migrated is not None or plan_issue or any(c.startswith("migration ") for c in changes):
        say("next: commit loop.json, AGENTS.md and .gitignore through a pull request into %s; "
            "include any revised CLAUDE.md instructions" % base)
        say("next: once the pull request merges, update the checkout with git pull, keeping any other uncommitted work safe")
        say("next: merge %s into %s before restarting the loop" % (base, branch))
    return 1 if failure else 0


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("project", nargs="?", default=".")
        parser.add_argument("--dry-run", action="store_true")
        args = parser.parse_args()
        sys.exit(setup(args.project, dry_run=args.dry_run))
    except LoopError as e:
        print("refused: %s\nnext: fix that, then run setup again" % e)
        sys.exit(1)
