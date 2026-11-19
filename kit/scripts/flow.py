"""Build one issue end to end: tests, code, review, merge."""
import collections
import difflib
import json
import os
import re
import subprocess
import tempfile
import time

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
    blocks = re.findall(r"^[\s*`]*%s:[*`]*[^\S\n]*\n(?:[^\S\n]*\n)*((?:(?![\s*`]*[A-Z]+:)[^\S\n]*\S.*\n?)*)" % name, text, re.M)
    items = [re.sub(r"^`([^`]+)`.*", r"\1", re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", l).strip()).strip("` ")
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


def fixes_of(review):
    """The numbered fixes after the last VERDICT line of a review, before its FOLLOW-UPS."""
    tail = re.split(r"^[\s*`]*VERDICT:", review, flags=re.M)[-1]
    tail = re.split(r"^[\s*`]*FOLLOW-UPS:", tail, flags=re.M)[0]
    return [l.strip() for l in tail.splitlines() if re.match(r"\s*\d+[.)]\s", l)]


def after_merge(issue, report, review, commit, files, pr, post=True, earlier=()):
    """Post the build note, then the pull request body, then the follow-ups of
    every review round (`earlier` holds those before the approving `review`)
    as inbox issues. Each step is safe to run again."""
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
    for line in [l for r in (*earlier, review) for l in parse_block(r, "FOLLOW-UPS") if l.lower() != "none"]:
        title = line[:100]
        once(lambda: gh(["issue", "create", "--title", title, "--label", "inbox", "--body-file", "-"],
                        input="Follow-up from #%s.\n\n%s\n\n%s\n" % (issue, line, common.MARKER),
                        retry=False),
             lambda: any(same(i["title"]) == same(title) for i in json.loads(gh(
                 ["issue", "list", "--state", "open", "--limit", "500", "--json", "title"]) or "[]")))


def note_after_merge(issue, project, report, review, commit, files, pr, post=True, earlier=()):
    """after_merge that never undoes a merge: any error is logged."""
    try:
        after_merge(issue, report, review, commit, files, pr, post, earlier)
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


ASSERTION = re.compile(r"AssertionError|\bassert\b|--- FAIL|\u2715|Expected|Received|(?:^|\s)FAIL[: ]|\b[1-9]\d* failed|failures=[1-9]"
                       r"|expected .* got", re.M)
MISSING = re.compile(r"(?:No module named|has no attribute|cannot import name|name|Cannot find module|cannot find module|undefined:?)[^\n]*", re.I)


def fails_properly(kinds, failed, body):
    """None when a fails-first run proves a real failure, else why it does not. Only a test run that
    failed counts, by an assertion or by naming a module or symbol the issue introduces."""
    if not kinds or kinds[-1][1] != "failed" or kinds[-1][0] != "Test":
        what = kinds[-1] if kinds else ("Test", "failed")
        return "They fail because the %s command %s, which proves nothing: %s" % (
            what[0], {"timeout": "timed out", "unrunnable": "could not run"}.get(what[1], "failed"), failed)
    if ASSERTION.search(failed):
        return None
    names = [t for line in MISSING.findall(failed) for q in re.findall(r"['\"`]([^'\"`]+)['\"`]", line)
             for t in [q] + q.replace("/", ".").split(".")]
    if any(len(t) > 2 and t in body for t in names):
        return None
    return "Your tests do not fail by assertion. Make them fail by assertion for the right reason."


def keep_added_plan_lines(tree):
    """Finish a merge open in the tree when PLAN.md is the only conflict and both sides only added
    lines to it: keep both, the loop branch's lines first, and commit. Return True when it did."""
    if git(["diff", "--name-only", "--diff-filter=U"], cwd=tree, check=False).splitlines() != ["PLAN.md"]:
        return False
    base, mine, theirs = ((git(["show", ":%d:PLAN.md" % n], cwd=tree, check=False) + "\n").splitlines(True) for n in (1, 2, 3))
    for side in (mine, theirs):
        if any(op not in ("insert", "equal") for op, *_ in difflib.SequenceMatcher(None, base, side, autojunk=False).get_opcodes()):
            return False
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for name, lines in (("loop", theirs), ("base", base), ("issue", mine)):
            paths.append(os.path.join(d, name))
            with open(paths[-1], "w", encoding="utf-8", newline="") as f:
                f.writelines(lines)
        out = subprocess.run(["git", "merge-file", "-p", "--union"] + paths, cwd=tree,
                             capture_output=True, text=True, timeout=common.TIMEOUT).stdout
    with open(os.path.join(tree, "PLAN.md"), "w", encoding="utf-8", newline="") as f:
        f.write(out)
    git(["add", "PLAN.md"], cwd=tree)
    git(["commit", "--no-edit"], cwd=tree)
    return True


Landed = collections.namedtuple("Landed", "result conflicts head review files")


def land(issue, branch, review, project, tree, settings):
    """Merge into the loop branch, one merge at a time. Under the merge lock: catch the issue branch up
    with the loop branch, then merge.merge. A clean catch-up is pushed and the verdict's HEAD follows it;
    conflicts are left open in the tree. A refusal while the loop branch has moved is tried once more."""
    loop = settings["Loop branch"]
    for attempt in (1, 2):
        with common.merge_lock(project):
            git(["fetch", "--no-prune", "origin"], cwd=project)
            based, old = git(["rev-parse", "origin/" + loop], cwd=project), git(["rev-parse", "HEAD"], cwd=tree)
            try:
                git(["merge", "--no-edit", "origin/" + loop], cwd=tree)
            except common.GitError:
                conflicts = git(["diff", "--name-only", "--diff-filter=U"], cwd=tree, check=False).splitlines()
                if not conflicts:
                    raise
                if not keep_added_plan_lines(tree):
                    return Landed(None, conflicts, old, review, [])
            head = git(["rev-parse", "HEAD"], cwd=tree)
            if head != old:
                git(["push", "origin", branch], cwd=tree)
                review = re.sub(r"(?m)^(\s*HEAD:\s*)[0-9a-fA-F]{7,40}", lambda m: m.group(1) + head, review)
            files = git(["diff", "--name-only", "origin/%s...%s" % (loop, head)], cwd=tree).splitlines()
            result = merge.merge(issue, branch, review, project)
            if result.ok or result.park:
                break
            git(["fetch", "--no-prune", "origin"], cwd=project)
            if git(["rev-parse", "origin/" + loop], cwd=project) == based:
                break
    return Landed(result, [], head, review, files)


def prompt_for(role, number, info, tree, settings, replies, report=None):
    with open(os.path.join(BRIEFS, role + ".md"), encoding="utf-8") as f:
        text = f.read()
    text += ("\n\n# Issue %s: %s\n\n%s\n\nPLAN.md: %s\nLoop branch: %s\nTest command: %s\n"
             % (number, info["title"], info.get("body") or "", os.path.join(tree, "PLAN.md"),
                settings["Loop branch"], settings["Test command"]))
    if settings["Test files command"]:
        text += "Test files command: %s\n" % settings["Test files command"]
    if settings["Check command"]:
        text += "Check command: %s\n" % settings["Check command"]
    if replies:
        text += "\nThe person's replies to an earlier park:\n" + "\n---\n".join(replies) + "\n"
    if report:
        text += "\nThe builder's last report:\n" + report + "\n"
    return text


def build(issue, project, replies=()):
    """Build one issue. Return Result(status, reason)."""
    project, result = os.path.abspath(project), None
    settings = common.read_settings(project)
    loop, branch = settings["Loop branch"], "issue/%s" % issue
    tree = os.path.join(os.path.dirname(project), ".loop-worktrees",
                        "%s-%s" % (os.path.basename(project), issue))
    try:
        info = json.loads(gh(["issue", "view", str(issue), "--json", "title,body,comments"]))
        git(["fetch", "--no-prune", "origin"], cwd=project)
        if resume_merged(issue, project, branch, loop):
            return (result := Result("merged", "already merged"))
        remote = git(["branch", "-r", "--list", "origin/" + branch], cwd=project)
        git(["worktree", "remove", "--force", tree], cwd=project, check=False)
        git(["worktree", "prune"], cwd=project, check=False)
        if os.path.lexists(tree):  # not a worktree of this repository: keep it, out of the way
            os.rename(tree, "%s.stale-%s" % (tree, time.strftime("%Y%m%d-%H%M%S")))
        git(["worktree", "add", "-B", branch, tree,
             "origin/" + (branch if remote else loop)], cwd=project)
        if settings["Prepare command"] and (why := merge.run_in("Prepare", settings["Prepare command"], tree, "the worktree", 20)):
            raise common.LoopError(why)
        conflicts = []
        if remote:  # the reused branch lacks what the loop branch gained since
            try:
                git(["merge", "--no-edit", "origin/" + loop], cwd=tree)
            except common.GitError:  # the merge stays open for the builder to finish
                conflicts = git(["diff", "--name-only", "--diff-filter=U"], cwd=tree, check=False).splitlines()
                if not conflicts:
                    raise
                if keep_added_plan_lines(tree):
                    conflicts = []
        return (result := _build(issue, project, settings, info, tree, branch, replies, conflicts))
    except Parked as p:
        common.park(issue, *p.args)
        return Result("parked", p.args[0])
    except common.LoopError as e:
        return Result("failed", str(e))
    finally:
        if os.path.isdir(tree):
            common.git(["worktree", "remove", "--force", tree], cwd=project, check=False)
            common.git(["worktree", "prune"], cwd=project, check=False)
        if result and result.status == "merged":  # a squash merge makes -d refuse
            common.git(["branch", "-D", branch], cwd=project, check=False)


def _build(issue, project, settings, info, tree, branch, replies, conflicts=()):
    start = git(["rev-parse", "HEAD"], cwd=tree)

    # paths the issue lets the builder change, except those the stops list covers
    allowed = [p for p in sorted(merge.allowed_paths(info.get("body") or "")) if not merge.stop_reason(p, settings["Protected paths"])]

    def ask(role, who, report=None, resume=None, extra="", locked=()):
        if role == "builder":
            locked = [p for p in locked if p not in allowed]
        prompt = (extra.strip() if resume else
                  prompt_for(role, issue, info, tree, settings, replies, report) + extra)
        text, sid = session.run(role, prompt, tree, who[1], project, issue,
                                agent=who[0], resume=resume, locked=locked, start=start,
                                allowed=allowed if role == "builder" else ())
        stop = re.search(r"^[\s*`]*PARK:\s*(.+?)(?:\s*\|\s*(.+))?$", text, re.M)
        if stop:
            raise Parked(stop.group(1).strip("*` "),
                         (stop.group(2) or "Decide, then reply here.").strip("*` "))
        return text, sid

    posted = max([int(n) for c in info.get("comments", []) for n in
                  re.findall(r"^## Review, round (\d+)", c.get("body") or "", re.M)] or [0])  # continue after a crash or a park
    locked = merge.locked_paths(info.get("comments", []))
    if conflicts:
        common.event("step", project, issue=issue, step="conflicts")
        ask("builder", settings["Builder"], locked=locked, extra=(
            "\n\nFirst task: the branch is in the middle of merging %s and conflicts in: %s. Resolve the "
            "conflicts keeping both intents, run the Test command, then commit the merge. Do not run git merge."
            % (settings["Loop branch"], ", ".join(conflicts))))
        marked = git(["grep", "-lE", "^(<{7}|>{7})( |$)", "HEAD", "--"] + list(conflicts), cwd=tree, check=False)
        if marked or git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=tree, check=False):
            raise Parked("The issue branch conflicts with %s in: %s, and the builder did not finish the merge."
                         % (settings["Loop branch"], ", ".join(conflicts)), "Reply with how to resolve it.")
    common.event("step", project, issue=issue, step="test-writer")
    rerun = git(["branch", "-r", "--list", "origin/" + branch], cwd=project) and locked
    if not rerun:
        text, writer = ask("test-writer", settings["Test writer"])
        locked = parse_block(text)
        for attempt in (1, 2):
            if not locked or any(not os.path.isfile(os.path.join(tree, p)) or not merge.is_test_file(p)
                                 for p in locked):
                why = "Name every test file you wrote, each an existing test file, in the TESTS: block."
            elif not (failed := merge.run_tests(project, start, common.files_command(settings, locked), 60,
                                                overlay=(tree, locked), prepare=settings["Prepare command"],
                                                kinds=(kinds := []))):
                why = "Your tests pass before any code exists. Make them fail for the right reason."
            elif why := fails_properly(kinds, failed, info.get("body") or ""):
                pass
            else:
                break
            if attempt == 2:
                raise Parked("The tests are not usable: " + why[0].lower() + why[1:],
                             "Reply with what the tests should check, or close the issue.")
            text, _ = ask("test-writer", settings["Test writer"], resume=writer, locked=locked,
                          extra=why + " Commit, and end with the TESTS: block again.")
            locked = parse_block(text)
        git(["push", "origin", branch], cwd=tree)
        post_once(issue, "TESTS:\n" + "\n".join(locked) + "\n\nCommit: " + git(["rev-parse", "HEAD"], cwd=tree)
                  + "\n\n" + common.MARKER + "\n")  # where merge.py reads them
    common.event("step", project, issue=issue, step="builder")
    report, sid = ask("builder", settings["Builder"], locked=locked)
    feedback, fixes, earlier = "", [], []  # fixes: the last review's numbered fixes, when it returned CHANGES
    for rnd in range(1, settings["Max rounds"] + 1):
        if feedback:
            common.event("step", project, issue=issue, step="fix", round=rnd)
            report, sid = ask("builder", settings["Builder"], resume=sid,
                              extra="\n\nFix these, test the files you touch, commit. The Stop hook runs the "
                              "full commands when you finish:\n" + feedback, locked=locked)
        head, tails = git(["rev-parse", "HEAD"], cwd=tree), []
        passed = common.read_passed(project, sid)  # the Stop hook's pass for this very commit stands
        if passed[0] == head:
            tails = passed[1]
        else:
            feedback = merge.run_tests(project, head, settings["Test command"], 80, check=settings["Check command"],
                                       prepare=settings["Prepare command"], tails=tails)
            if feedback:
                continue
        common.event("step", project, issue=issue, step="review", round=rnd)
        review, _ = ask("reviewer", settings["Reviewer"], report=report, locked=locked,
                        extra="\nLatest test result: passed on this commit.\n" + "\n".join(tails) + "\n"
                        + ("\nThe previous review returned CHANGES with these fixes:\n" + "\n".join(fixes) + "\n"
                           if fixes else ""))
        verdict, _ = merge.parse_verdict(review)
        try:  # the person can follow the fix rounds; a failure to post never stops the build
            post_once(issue, "## Review, round %d\n\n%s\n\n%s\n" % (posted + rnd, review.strip(), common.MARKER))
        except common.GitHubError as e:
            common.event("note-failed", project, issue=issue, reason=str(e))
        if verdict == "APPROVE":
            git(["push", "origin", branch], cwd=tree)
            landed = land(issue, branch, review, project, tree, settings)
            result, head, review = landed.result, landed.head, landed.review
            if landed.conflicts:  # the merge stays open in the tree for the builder's next pass
                feedback = ("The loop branch moved and the branch now conflicts with it in: %s. The merge is "
                            "in progress: resolve the conflicts keeping both intents, run the tests, commit "
                            "the merge. Do not run git merge." % ", ".join(landed.conflicts))
            elif result.ok:
                try:
                    pr = (merge.find_pr(branch, settings["Loop branch"], head) or {}).get("number")
                except common.LoopError:
                    pr = None
                note_after_merge(issue, project, report, review, result.commit, landed.files, pr, earlier=earlier)
                return Result("merged", result.reason)
            elif result.park:
                raise Parked("The loop refused to merge: %s." % result.reason,
                             "Name the path in the issue body if the change is "
                             "intended, otherwise tell the loop what to change.")
            else:
                feedback = "The merge was refused: " + result.reason
        else:
            feedback = review if verdict else "The review had no VERDICT block."
            if verdict:
                fixes = fixes_of(review)
                earlier.append(review)
    raise Parked("The build did not pass review in %d rounds. Last problem: %s"
                 % (settings["Max rounds"], feedback.strip()[:600]),
                 "Reply with what to change, or close the issue.")
