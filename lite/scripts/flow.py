"""Build one issue end to end: tests, code, simplify, review, merge."""
import collections
import json
import os
import re

import common
import merge
import session
from common import gh, git

Result = collections.namedtuple("Result", "status reason")  # merged, parked, failed
BRIEFS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "briefs")


class Parked(Exception):
    pass


def parse_block(text, name="TESTS"):
    """Items in the last `NAME:` block of a reply, without bullets or numbers."""
    blocks = re.findall(r"^[\s*`]*%s:\s*\n((?:[^\S\n]*\S.*\n?)*)" % name, text, re.M)
    items = [re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", l).strip("` ")
             for l in blocks[-1].splitlines()] if blocks else []
    return [i for i in items if i and i.lower() != "none"]


def post_once(issue, body):
    """Comment on the issue unless it already holds that comment. The write is
    not safe to repeat, so after a failure read the comments again."""
    def posted():
        return any((c.get("body") or "").strip() == body.strip()
                   for c in merge.view("issue", issue, "comments").get("comments", []))
    if posted():
        return
    try:
        gh(["issue", "comment", str(issue), "--body-file", "-"], input=body, retry=False)
    except common.GitHubError:
        if not posted():
            raise


def post_tests(issue, paths):
    """Comment the locked paths where merge.py reads them."""
    post_once(issue, "TESTS:\n" + "\n".join(paths) + "\n\n" + common.MARKER + "\n")


def after_merge(issue, project, report, review, commit, files, pr):
    """Post the build note and open the reviewer's follow-ups as inbox issues."""
    m = re.search(r"^[\s*`]*BUILT:\s*(.*?)(?=^[\s*`]*DEVIATIONS:|\Z)", report, re.S | re.M)
    built = (m.group(1).strip() if m else "") or "The builder gave no BUILT block."
    deviations = "\n".join(parse_block(report, "DEVIATIONS")) or "none"
    note = ("## Built\n\n%s\n\nDeviations: %s\n\nMerged as %s.\n\nChanged files:\n%s\n\n%s\n"
            % (built, deviations, commit, "\n".join("- " + f for f in files), common.MARKER))
    if pr:
        gh(["pr", "edit", str(pr), "--body-file", "-"], input=note)
    post_once(issue, note)
    for line in parse_block(review, "FOLLOW-UPS"):
        title = line[:100]
        def exists():
            return any(i["title"] == title for i in json.loads(gh(
                ["issue", "list", "--state", "open", "--limit", "500", "--json", "title"]) or "[]"))
        if not exists():
            try:
                gh(["issue", "create", "--title", title, "--label", "inbox", "--body-file", "-"],
                   input="Follow-up from the review of issue %s.\n\n%s\n\n%s\n"
                         % (issue, line, common.MARKER), retry=False)
            except common.GitHubError:
                if not exists():
                    raise


def prompt_for(role, number, info, tree, settings, replies, report=None):
    with open(os.path.join(BRIEFS, role + ".md"), encoding="utf-8") as f:
        text = f.read()
    text += ("\n\n# Issue %s: %s\n\n%s\n\nPLAN.md: %s\nLoop branch: %s\nTest command: %s\n"
             % (number, info["title"], info.get("body") or "", os.path.join(tree, "PLAN.md"),
                settings["Loop branch"], settings["Test command"]))
    if replies:
        text += "\nThe person's replies to an earlier park:\n" + "\n---\n".join(replies) + "\n"
    if report:
        text += "\nThe builder's last report:\n" + report + "\n"
    return text


def build(issue, project, replies=()):
    """Build one issue. Return Result(status, reason)."""
    project = os.path.abspath(project)
    settings = common.read_settings(project)
    loop, branch = settings["Loop branch"], "issue/%s" % issue
    tree = os.path.join(os.path.dirname(project), ".lite-worktrees",
                        "%s-%s" % (os.path.basename(project), issue))
    try:
        info = json.loads(gh(["issue", "view", str(issue), "--json", "title,body,comments"]))
        git(["fetch", "--no-prune", "origin"], cwd=project)
        remote = git(["branch", "-r", "--list", "origin/" + branch], cwd=project)
        git(["worktree", "remove", "--force", tree], cwd=project, check=False)
        git(["worktree", "prune"], cwd=project, check=False)
        git(["worktree", "add", "-B", branch, tree,
             "origin/" + (branch if remote else loop)], cwd=project)
        return _build(issue, project, settings, info, tree, branch, replies)
    except Parked as p:
        common.park(issue, *p.args)
        return Result("parked", p.args[0])
    except common.LoopError as e:
        return Result("failed", str(e))
    finally:
        if os.path.isdir(tree):
            common.git(["worktree", "remove", "--force", tree], cwd=project, check=False)
            common.git(["worktree", "prune"], cwd=project, check=False)


def _build(issue, project, settings, info, tree, branch, replies):
    start = git(["rev-parse", "HEAD"], cwd=tree)

    def ask(role, model, report=None, resume=None, extra="", locked=()):
        prompt = (extra.strip() if resume else
                  prompt_for(role, issue, info, tree, settings, replies, report) + extra)
        text, sid = session.run(role, prompt, tree, model, project, issue,
                                resume=resume, locked=locked, start=start)
        stop = re.search(r"^[\s*`]*PARK:\s*(.+?)(?:\s*\|\s*(.+))?$", text, re.M)
        if stop:
            raise Parked(stop.group(1).strip("*` "),
                         (stop.group(2) or "Decide, then reply here.").strip("*` "))
        return text, sid

    common.event("step", project, issue=issue, step="test-writer")
    locked = merge.locked_paths(info.get("comments", []))
    rerun = git(["branch", "-r", "--list", "origin/" + branch], cwd=project) and locked
    if not rerun:
        text, writer = ask("test-writer", settings["Builder model"])
        locked = parse_block(text)
        for attempt in (1, 2) if locked else ():
            if merge.run_tests(project, start, settings["Test command"], overlay=(tree, locked)):
                break
            if attempt == 2:
                raise Parked("The tests pass before any code exists, so they do not judge "
                             "this issue.", "Reply with what the tests should check, or close the issue.")
            text, _ = ask("test-writer", settings["Builder model"], resume=writer, locked=locked,
                          extra="Your tests pass before any code exists. Make them fail for "
                                "the right reason, commit, and end with the TESTS: block again.")
            locked = parse_block(text) or locked
        git(["push", "origin", branch], cwd=tree)
        if locked:
            post_tests(issue, locked)
    common.event("step", project, issue=issue, step="builder")
    report, sid = ask("builder", settings["Builder model"], locked=locked)
    feedback = ""
    for rnd in range(1, settings["Max rounds"] + 1):
        if feedback:
            common.event("step", project, issue=issue, step="fix", round=rnd)
            report, sid = ask("builder", settings["Builder model"], resume=sid,
                              extra="\n\nFix these, run the Test command, commit:\n"
                              + feedback, locked=locked)
        ask("simplify", settings["Builder model"], locked=locked)
        head = git(["rev-parse", "HEAD"], cwd=tree)
        feedback = merge.run_tests(project, head, settings["Test command"], 80,
                                   check=settings["Check command"])
        if feedback:
            continue
        common.event("step", project, issue=issue, step="review", round=rnd)
        review, _ = ask("reviewer", settings["Reviewer model"], report=report,
                        locked=locked)
        verdict, _ = merge.parse_verdict(review)
        if verdict == "APPROVE":
            git(["push", "origin", branch], cwd=tree)
            files = git(["diff", "--name-only", "origin/%s...%s" % (settings["Loop branch"], head)],
                        cwd=tree).splitlines()
            result = merge.merge(issue, branch, review, project)
            if result.ok:
                try:
                    pr = (merge.find_pr(branch, settings["Loop branch"], head) or {}).get("number")
                    after_merge(issue, project, report, review, result.commit, files, pr)
                except common.LoopError as e:
                    common.event("note-failed", project, issue=issue, reason=str(e))
                return Result("merged", result.reason)
            if result.park:
                raise Parked("The loop refused to merge: %s." % result.reason,
                             "Name the path in the issue body if the change is "
                             "intended, otherwise tell the loop what to change.")
            feedback = "The merge was refused: " + result.reason
        else:
            feedback = review if verdict else "The review had no VERDICT block."
    raise Parked("The build did not pass review in %d rounds. Last problem: %s"
                 % (settings["Max rounds"], feedback.strip()[:600]),
                 "Reply with what to change, or close the issue.")
