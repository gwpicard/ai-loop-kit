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
    return [i for i in items if i]


def once(write, found):
    """Run a write that is not safe to repeat unless found() says it is done.
    After a failure, read again before deciding."""
    if found():
        return
    try:
        write()
    except common.GitHubError:
        if not found():
            raise


def same(title):  # titles are the same when they differ only in case and punctuation
    return re.sub(r"\W+", "", title.lower())


def post_once(issue, body):
    """Comment on the issue unless it already holds that comment."""
    once(lambda: gh(["issue", "comment", str(issue), "--body-file", "-"], input=body, retry=False),
         lambda: any((c.get("body") or "").strip() == body.strip()
                     for c in merge.view("issue", issue, "comments").get("comments", [])))


def post_tests(issue, paths):
    """Comment the locked paths where merge.py reads them."""
    post_once(issue, "TESTS:\n" + "\n".join(paths) + "\n\n" + common.MARKER + "\n")


def after_merge(issue, report, review, commit, files, pr, post=True):
    """Post the build note, then the pull request body, then the reviewer's
    follow-ups as inbox issues. Each step is safe to run again."""
    m = re.search(r"^[\s*`]*BUILT:\s*(.*?)(?=^[\s*`]*DEVIATIONS:|\Z)", report, re.S | re.M)
    built = (m.group(1).strip() if m else "") or "No BUILT block in the builder's report."
    deviations = "\n".join(parse_block(report, "DEVIATIONS")) or "none"
    left = session.SWEPT.get(issue)
    swept = "\nLeft behind by sessions:\n" + "\n".join("- " + l for l in left) + "\n" if left else ""
    note = ("## Built\n\n%s\n\nDeviations: %s\n\nMerged as %s.\n\nChanged files:\n%s\n%s\n%s\n"
            % (built, deviations, commit, "\n".join("- " + f for f in files), swept, common.MARKER))
    if post:
        post_once(issue, note)
        if pr:
            gh(["pr", "edit", str(pr), "--body-file", "-"], input=note)
    for line in parse_block(review, "FOLLOW-UPS"):
        if line.lower() == "none":
            continue
        title = line[:100]
        once(lambda: gh(["issue", "create", "--title", title, "--label", "inbox", "--body-file", "-"],
                        input="Follow-up from #%s.\n\n%s\n\n%s\n" % (issue, line, common.MARKER),
                        retry=False),
             lambda: any(same(i["title"]) == same(title) for i in json.loads(gh(
                 ["issue", "list", "--state", "open", "--limit", "500", "--json", "title"]) or "[]")))


def note_after_merge(issue, project, report, review, commit, files, pr, post=True):
    """after_merge that never undoes a merge: any error is logged."""
    try:
        after_merge(issue, report, review, commit, files, pr, post)
    except Exception as e:
        common.event("note-failed", project, issue=issue, reason=str(e) or type(e).__name__)


def resume_merged(issue, project, branch, loop):
    """A crash after the merge: if the pull request is merged and the issue has
    no build note, post it now. Return True when the pull request was merged."""
    prs = json.loads(gh(["pr", "list", "--head", branch, "--base", loop, "--state", "merged",
                         "--json", "number,mergeCommit,files"]) or "[]")
    if not prs:
        return False
    pr = prs[0]
    texts = [c.get("body") or "" for c in merge.view("pr", pr["number"], "comments").get("comments", [])]
    review = ([t for t in texts if "VERDICT:" in t] or [""])[-1]
    note_after_merge(issue, project, "", review, (pr.get("mergeCommit") or {}).get("oid") or "unknown",
                     [f["path"] for f in pr.get("files", [])], pr["number"],
                     post=not any((c.get("body") or "").startswith("## Built")
                                  for c in merge.view("issue", issue, "comments").get("comments", [])))
    if merge.view("issue", issue, "state").get("state") != "CLOSED":
        gh(["issue", "close", str(issue), "--comment", "Merged into %s.\n\n%s" % (loop, common.MARKER)],
           retry=False)
    return True


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
        if resume_merged(issue, project, branch, loop):
            return Result("merged", "already merged")
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
        for attempt in (1, 2):
            if not locked or any(not os.path.isfile(os.path.join(tree, p)) or not merge.is_test_file(p)
                                 for p in locked):
                why = "Name every test file you wrote, each an existing test file, in the TESTS: block."
            elif merge.run_tests(project, start, settings["Test command"], overlay=(tree, locked)):
                break
            else:
                why = "Your tests pass before any code exists. Make them fail for the right reason."
            if attempt == 2:
                raise Parked("The tests are not usable: " + why[0].lower() + why[1:],
                             "Reply with what the tests should check, or close the issue.")
            text, _ = ask("test-writer", settings["Builder model"], resume=writer, locked=locked,
                          extra=why + " Commit, and end with the TESTS: block again.")
            locked = parse_block(text)
        git(["push", "origin", branch], cwd=tree)
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
        try:  # the person can follow the fix rounds; a failure to post never stops the build
            post_once(issue, "## Review, round %d\n\n%s\n\n%s\n" % (rnd, review.strip(), common.MARKER))
        except common.GitHubError as e:
            common.event("note-failed", project, issue=issue, reason=str(e))
        if verdict == "APPROVE":
            git(["push", "origin", branch], cwd=tree)
            files = git(["diff", "--name-only", "origin/%s...%s" % (settings["Loop branch"], head)],
                        cwd=tree).splitlines()
            result = merge.merge(issue, branch, review, project)
            if result.ok:
                try:
                    pr = (merge.find_pr(branch, settings["Loop branch"], head) or {}).get("number")
                except common.LoopError:
                    pr = None
                note_after_merge(issue, project, report, review, result.commit, files, pr)
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
