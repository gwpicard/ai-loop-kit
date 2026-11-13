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


def parse_tests(text):
    """Paths in the last `TESTS:` block of a reply."""
    blocks = re.findall(r"^\s*TESTS:\s*\n((?:[^\S\n]*\S.*\n?)*)", text, re.M)
    return [l.strip().lstrip("-* ").strip("` ") for l in blocks[-1].splitlines()] if blocks else []


def post_tests(issue, paths):
    """Comment the locked paths where merge.py reads them. Re-read on failure."""
    body = "TESTS:\n" + "\n".join(paths) + "\n"
    try:
        gh(["issue", "comment", str(issue), "--body-file", "-"], input=body, retry=False)
    except common.GitHubError:
        comments = merge.view("issue", issue, "comments").get("comments", [])
        if not any(c.get("body", "").strip() == body.strip() for c in comments):
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
    def ask(role, model, report=None, resume=None, extra="", locked=()):
        prompt = (extra.strip() if resume else
                  prompt_for(role, issue, info, tree, settings, replies, report) + extra)
        text, sid = session.run(role, prompt, tree, model, project, issue,
                                resume=resume, locked=locked)
        stop = re.search(r"^[\s*`]*PARK:\s*(.+?)(?:\s*\|\s*(.+))?$", text, re.M)
        if stop:
            raise Parked(stop.group(1).strip("*` "),
                         (stop.group(2) or "Decide, then reply here.").strip("*` "))
        return text, sid

    common.event("step", project, issue=issue, step="test-writer")
    locked = merge.locked_paths(info.get("comments", []))
    rerun = git(["branch", "-r", "--list", "origin/" + branch], cwd=project) and locked
    if not rerun:
        text, _ = ask("test-writer", settings["Builder model"])
        locked = parse_tests(text)
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
        feedback = merge.run_tests(project, head, settings["Test command"], 80)
        if feedback:
            continue
        common.event("step", project, issue=issue, step="review", round=rnd)
        review, _ = ask("reviewer", settings["Reviewer model"], report=report,
                        locked=locked)
        verdict, _ = merge.parse_verdict(review)
        if verdict == "APPROVE":
            git(["push", "origin", branch], cwd=tree)
            result = merge.merge(issue, branch, review, project)
            if result.ok:
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
