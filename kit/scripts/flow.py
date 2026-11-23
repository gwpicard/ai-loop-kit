"""Build one issue end to end: tests, code, review, merge."""
import collections
import json
import os
import re
import time

import common
import merge
import session
import shapecheck
from common import gh, git

Result = collections.namedtuple("Result", "status reason")  # merged, parked, failed
BRIEFS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "briefs")


class Parked(Exception):
    pass


def push_issue(branch, tree):
    """Refuse rewritten remote history before pushing the issue branch."""
    git(["fetch", "--no-prune", "origin"], cwd=tree)
    remote = "origin/" + branch
    if git(["branch", "-r", "--list", remote], cwd=tree):
        missing = git(["log", "--format=%H %s", branch + ".." + remote], cwd=tree)
        if missing:
            raise Parked("The branch history was rewritten on %s. Remote commits missing locally:\n%s"
                         % (branch, missing),
                         "Restore the missing remote commits without rewriting pushed history, then retry.")
    git(["push", "origin", branch], cwd=tree)


def parse_block(text, name="TESTS"):
    """Items in the last `NAME:` block of a reply, without bullets or numbers."""
    text = text.replace("\r\n", "\n")
    headers = list(re.finditer(r"^[ \t*`]*" + re.escape(name) + r"[*`]*:[*`]*[ \t]*$", text, re.M))
    if not headers:
        return []
    items = []
    for line in text[headers[-1].end():].splitlines():
        if re.fullmatch(r"[ \t*`]*[A-Z]+(?:[ -][A-Z]+)*[*`]*:[*`]*[ \t]*", line):
            break
        if not line.strip():
            if items:
                break
            continue
        item = re.sub(r"^\s*[-*]\s+", "", line).strip()
        items.append(re.sub(r"^\d+[.)]\s+", "", item))
    if name == "TESTS":
        items = [re.sub(r"^`([^`]+)`.*", r"\1", i.strip("* ")).strip("` ") for i in items]
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


def after_merge(issue, report, review, commit, files, pr, post=True, earlier=(), shape_note=""):
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
    if shape_note:
        note += "\n" + shape_note + "\n"
    if post:
        post_once(issue, note)
        if pr:
            gh(["pr", "edit", str(pr), "--body-file", "-"], input=note)
    for line in [l for r in (*earlier, review) for l in parse_block(r, "FOLLOW-UPS")
                 if len(l.split()) >= 4 and not re.search(r"\bunverified\b", l, re.I)][:2]:
        title = line[:100]
        once(lambda: gh(["issue", "create", "--title", title, "--label", "inbox", "--body-file", "-"],
                        input="Follow-up from #%s.\n\n%s\n\n%s\n" % (issue, line, common.MARKER),
                        retry=False),
             lambda: any(same(i["title"]) == same(title) for i in json.loads(gh(
                 ["issue", "list", "--state", "open", "--limit", "500", "--json", "title"]) or "[]")))


def note_after_merge(issue, project, report, review, commit, files, pr, post=True, earlier=(), shape_note="",
                     selection=""):
    """after_merge that never undoes a merge: any error is logged."""
    try:
        selection = next((e.get("test_selection", "") for e in reversed(merge.status.read_events(project))
                          if e.get("kind") == "merged" and e.get("issue") == issue
                          and e.get("commit") == commit), selection)
        if selection:
            shape_note += "\nTest selection:\n" + selection + "\n"
        after_merge(issue, report, review, commit, files, pr, post, earlier, shape_note)
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


def revert_check(issue, project, tree, head, settings, locked, body):
    """Tell the reviewer which builder tests do not prove the issue's change."""
    files, listed = [], []
    if settings["Test files command"]:
        base = git(["merge-base", head, "origin/" + settings["Loop branch"]], cwd=tree)
        changes = git(["diff", "--no-renames", "--name-status", "-z", base, head], cwd=tree).split("\0")
        entries = list(zip(changes[0::2], changes[1::2]))
        code = [p for _, p in entries if not merge.is_test_file(p)]
        tests = sorted(p for status, p in entries if status != "D" and merge.is_test_module(p) and p not in locked)
        if code and tests:
            with common.scratch_tree(project, head) as scratch:
                git(["restore", "--source=" + base, "--staged", "--worktree", "--"] + code, cwd=scratch)
                failure = (merge.run_in("Prepare", settings["Prepare command"], scratch, head[:10], 60)
                           if settings["Prepare command"] else None)
                if failure:
                    listed.append("Revert check unverified: " + failure)
                else:
                    for path in tests:
                        files.append(path)
                        kinds = []
                        failed = merge.run_in("Test", common.files_command(settings, [path]), scratch,
                                              head[:10], 60, kinds=kinds)
                        if not failed:
                            listed.append("passes without the change: " + path)
                        elif why := fails_properly(kinds, failed, body):
                            listed.append("Revert check unverified: %s: %s" % (path, why))
    common.event("revert-check", project, issue=issue, rule="revert-check", files=files,
                 outcome="listed" if listed else "passed" if files else "skipped")
    return "\n".join(listed) + "\n" if listed else ""


Landed = collections.namedtuple("Landed", "result conflicts head review files")


def land(issue, branch, review, project, tree, settings):
    """Merge into the loop branch, one merge at a time. Under the merge lock: catch the issue branch up
    with the loop branch, then merge.merge. A clean catch-up is pushed and the verdict's HEAD follows it;
    conflicts are left open in the tree. A refusal while the loop branch has moved is tried once more."""
    common.say("#%s: merging" % issue)
    with common.timed("step", project, issue=issue, step="merge") as end:
        landed = _land(issue, branch, review, project, tree, settings)
        end.clear()
        if landed.conflicts:
            end["outcome"] = "conflict"
        else:
            result = landed.result
            end["outcome"] = "merged" if result.ok else "refused"
            if not result.ok:
                end.update(rule=result.rule, reason=result.reason)
        return landed


def _land(issue, branch, review, project, tree, settings):
    loop = settings["Loop branch"]
    for attempt in (1, 2):
        common.wait_for_memory(project=project, issue=issue)
        with common.merge_lock(project):
            git(["fetch", "--no-prune", "origin"], cwd=project)
            based, old = git(["rev-parse", "origin/" + loop], cwd=project), git(["rev-parse", "HEAD"], cwd=tree)
            try:
                git(["merge", "--no-edit", "origin/" + loop], cwd=tree)
            except common.GitError:
                conflicts = git(["diff", "--name-only", "--diff-filter=U"], cwd=tree, check=False).splitlines()
                if not conflicts:
                    raise
                return Landed(None, conflicts, old, review, [])
            head = git(["rev-parse", "HEAD"], cwd=tree)
            if head != old:
                push_issue(branch, tree)
                review = re.sub(r"(?m)^(\s*HEAD:\s*)[0-9a-fA-F]{7,40}", lambda m: m.group(1) + head, review)
            files = git(["diff", "--name-only", "origin/%s...%s" % (loop, head)], cwd=tree).splitlines()
            result = merge.merge(issue, branch, review, project)
            if result.ok or result.park:
                break
            git(["fetch", "--no-prune", "origin"], cwd=project)
            if git(["rev-parse", "origin/" + loop], cwd=project) == based:
                break
    return Landed(result, [], head, review, files)


def brief(role):
    text = []
    for name in ("preamble", role):
        with open(os.path.join(BRIEFS, name + ".md"), encoding="utf-8") as f:
            text.append(f.read().rstrip())
    return "\n\n".join(text) + "\n"


def prompt_for(role, number, info, tree, settings, replies, report=None, history=None):
    text = brief(role)
    text += ("\n\n# Issue %s: %s\n\n%s\n\nLoop branch: %s\nTest command: %s\n"
             % (number, info["title"], info.get("body") or "",
                settings["Loop branch"], settings["Test command"]))
    if settings["Test files command"]:
        text += "Test files command: %s\n" % settings["Test files command"]
    if settings["Check command"]:
        text += "Check command: %s\n" % settings["Check command"]
    if replies:
        text += "\nThe person's replies to the last park:\n" + "\n---\n".join(replies) + "\n"
    if role == "builder" and history:
        text += "\nRead earlier build and review notes: %s\n" % history
    if role == "reviewer" and report:
        blocks = re.findall(r"^[\s*`]*(BUILT|DEVIATIONS):[*`]*[^\S\n]*\n(.*?)"
                            r"(?=^[\s*`]*[A-Z][A-Z -]*:|\Z)", report, re.M | re.S)
        text += "\nThe builder's last report:\n" + "\n".join(
            name + ":\n" + body.strip() for name, body in blocks) + "\n"
    return text


def build(issue, project, replies=()):
    """Build one issue. Return Result(status, reason)."""
    project = os.path.abspath(project)
    common.wait_for_disk(project)
    with common.settings_environment(common.build_settings(project)), common.build_environment(project, issue):
        return _build_tree(issue, project, replies)


def _build_tree(issue, project, replies):
    result = None
    settings = common.build_settings(project)
    loop, branch = settings["Loop branch"], "issue/%s" % issue
    tree = os.path.join(os.path.dirname(project), ".loop-worktrees",
                        "%s-%s" % (os.path.basename(project), issue))
    try:
        info = json.loads(gh(["issue", "view", str(issue), "--json", "title,body,comments"]))
        git(["fetch", "--no-prune", "origin"], cwd=project)
        if resume_merged(issue, project, branch, loop):
            return (result := Result("merged", "already merged"))
        remote = git(["branch", "-r", "--list", "origin/" + branch], cwd=project)
        local = git(["rev-parse", "--verify", "refs/heads/" + branch], cwd=project, check=False)
        source = "origin/" + (branch if remote else loop)
        keep_local = False
        if local and (not remote or git(["rev-list", source + ".." + local], cwd=project)):
            if not remote or not git(["rev-list", local + ".." + source], cwd=project):
                source, keep_local = local, True
            else:
                backup = "%s-local-%s" % (branch, time.time_ns())
                git(["branch", backup, local], cwd=project)
                folder = os.path.join(project, ".loop")
                os.makedirs(folder, exist_ok=True)
                with open(os.path.join(folder, "loop.out"), "a", encoding="utf-8") as f:
                    f.write(time.strftime("%Y-%m-%d %H:%M:%S ")
                            + "kept divergent local branch as " + backup + "\n")
        git(["worktree", "remove", "--force", tree], cwd=project, check=False)
        git(["worktree", "prune"], cwd=project, check=False)
        if os.path.lexists(tree):  # not a worktree of this repository: keep it, out of the way
            os.rename(tree, "%s.stale-%s" % (tree, time.strftime("%Y%m%d-%H%M%S")))
        git(["worktree", "add", "-B", branch, tree, source], cwd=project)
        if keep_local:
            push_issue(branch, tree)
        if settings["Prepare command"] and (why := merge.run_in("Prepare", settings["Prepare command"], tree, "the worktree", 20)):
            raise common.LoopError(why)
        conflicts = []
        if remote or keep_local:  # the reused branch lacks what the loop branch gained since
            try:
                git(["merge", "--no-edit", "origin/" + loop], cwd=tree)
            except common.GitError:  # the merge stays open for the builder to finish
                conflicts = git(["diff", "--name-only", "--diff-filter=U"], cwd=tree, check=False).splitlines()
                if not conflicts:
                    raise
        return (result := _build(issue, project, settings, info, tree, branch, replies, conflicts))
    except Parked as p:
        try:
            remote = git(["branch", "-r", "--list", "origin/" + branch], cwd=project)
            base = "origin/" + (branch if remote else loop)
            if git(["rev-list", base + "..refs/heads/" + branch], cwd=project):
                push_issue(branch, project)
        except Parked as history:
            p = history
        except common.LoopError as e:
            return Result("failed", str(e))
        common.park(issue, *p.args, project=project)
        return Result("parked", p.args[0])
    except common.LoopError as e:
        return Result("failed", str(e))
    finally:
        if os.path.isdir(tree):
            common.git(["worktree", "remove", "--force", tree], cwd=project, check=False)
            common.git(["worktree", "prune"], cwd=project, check=False)
        if result and result.status == "merged":  # a squash merge makes -d refuse
            history = os.path.join(project, ".loop", "history-%s.md" % issue)
            if os.path.exists(history):
                os.remove(history)
            common.git(["branch", "-D", branch], cwd=project, check=False)


def _build(issue, project, settings, info, tree, branch, replies, conflicts=()):
    start = git(["rev-parse", "HEAD"], cwd=tree)
    baseline = git(["merge-base", "HEAD", "origin/" + settings["Loop branch"]], cwd=tree)
    notes = [c.get("body") or "" for c in info.get("comments", [])
             if re.match(r"^## (?:Review, round \d+|Built)\b", c.get("body") or "")]
    history = None
    if notes:
        history = os.path.join(project, ".loop", "history-%s.md" % issue)
        os.makedirs(os.path.dirname(history), exist_ok=True)
        with open(history, "w", encoding="utf-8") as f:
            f.write("\n\n".join(notes) + "\n")

    allowed = sorted(merge.allowed_paths(info.get("body") or ""))
    found = shapecheck.paths(info.get("body") or "", tree, settings["Protected paths"],
                             ref="origin/" + settings["Loop branch"])
    shape_note = ""
    if found:
        unapproved = [p for p in found if p not in allowed]
        shape_note = ("### Build-time shaping check\n\nExisting paths on the current loop branch:\n"
                      + "\n".join("- " + p for p in found)
                      + "\n\nPaths without approval: " + (", ".join(unapproved) or "none")
                      + ". This report does not grant permission to change these paths.\n"
                      + "\n".join(shapecheck.warnings(found)))
        post_once(issue, shape_note + "\n\n" + common.MARKER + "\n")

    def ask(role, who, report=None, resume=None, extra="", locked=(), step=None, rnd=None):
        if role == "builder":
            locked = [p for p in locked if p not in allowed]
        prompt = (extra.strip() if resume else
                  prompt_for(role, issue, info, tree, settings, replies, report, history) + extra)
        fields = dict(issue=issue, step=step or ("review" if role == "reviewer" else role),
                      agent=who[0], model=who[1])
        if rnd is not None:
            fields["round"] = rnd
        common.say("#%s: %s (%s %s)" % (issue, fields["step"], who[0], who[1]))
        with common.timed("step", project, **fields) as end:
            text, sid = session.run(role, prompt, tree, who[1], project, issue,
                                    agent=who[0], resume=resume, locked=locked,
                                    start=baseline if role == "builder" else start,
                                    allowed=allowed if role == "builder" else ())
            stop = re.search(r"^[\s*`]*PARK:\s*(.+?)(?:\s*\|\s*(.+))?$", text, re.M)
            if stop:
                end["outcome"] = "parked"
                raise Parked(stop.group(1).strip("*` "),
                             (stop.group(2) or "Decide, then reply here.").strip("*` "))
            end["outcome"] = ((merge.parse_verdict(text)[0] or "changes").lower()
                              if role == "reviewer" else "done")
            return text, sid

    def tests(step, sha, command, tail, rnd=None, **kwargs):
        fields = dict(issue=issue, step=step)
        if rnd is not None:
            fields["round"] = rnd
        common.say("#%s: %s" % (issue, step))
        with common.timed("step", project, **fields) as end:
            failure = merge.run_tests(project, sha, command, tail, **kwargs)
            end["outcome"] = "failed" if failure else "passed"
            return failure

    posted = max([int(n) for c in info.get("comments", []) for n in
                  re.findall(r"^## Review, round (\d+)", c.get("body") or "", re.M)] or [0])  # continue after a crash or a park
    locked = merge.locked_paths(info.get("comments", []))
    if conflicts:
        ask("builder", settings["Builder"], step="conflicts", locked=locked, extra=(
            "\n\nFirst task: the branch is in the middle of merging %s and conflicts in: %s. Resolve the "
            "conflicts keeping both intents, test the files involved, then commit the merge. Do not run git merge."
            % (settings["Loop branch"], ", ".join(conflicts))))
        marked = git(["grep", "-lE", "^(<{7}|>{7})( |$)", "HEAD", "--"] + list(conflicts), cwd=tree, check=False)
        if marked or git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=tree, check=False):
            raise Parked("The issue branch conflicts with %s in: %s, and the builder did not finish the merge."
                         % (settings["Loop branch"], ", ".join(conflicts)), "Reply with how to resolve it.")
    rerun = git(["branch", "-r", "--list", "origin/" + branch], cwd=project) and locked
    if not rerun:
        text, writer = ask("test-writer", settings["Test writer"])
        locked = parse_block(text)
        for attempt in (1, 2):
            if not locked or any(not os.path.isfile(os.path.join(tree, p)) or not merge.is_test_module(p)
                                 for p in locked):
                why = "Name every test file you wrote, each an existing test file, in the TESTS: block."
            elif not (failed := tests("fails-first", baseline, common.files_command(settings, locked), 60, rnd=attempt,
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
            text, _ = ask("test-writer", settings["Test writer"], rnd=attempt + 1, resume=writer, locked=locked,
                          extra=why + " Commit, and end with the TESTS: block again.")
            locked = parse_block(text)
        push_issue(branch, tree)
        post_once(issue, "TESTS:\n" + "\n".join(locked) + "\n\nCommit: " + git(["rev-parse", "HEAD"], cwd=tree)
                  + "\n\n" + common.MARKER + "\n")  # where merge.py reads them
    report, sid = ask("builder", settings["Builder"], locked=locked)
    feedback, fixes, earlier = "", [], []  # fixes: the last review's numbered fixes, when it returned CHANGES
    for rnd in range(1, settings["Max rounds"] + 1):
        if feedback:
            report, sid = ask("builder", settings["Builder"], step="fix", rnd=rnd, resume=sid,
                              extra="\n\nFix these, test the files you touch, commit. The Stop hook checks them "
                              "when you finish:\n" + feedback, locked=locked)
        head, tails = git(["rev-parse", "HEAD"], cwd=tree), []
        passed = common.read_passed(project, sid)  # the Stop hook's pass for this very commit stands
        if passed[0] == head:
            tails = passed[1]
        else:
            command, description = merge.targeted_command(settings, tree, start, locked)
            tails.append(description)
            feedback = tests("tests", head, command, 80, rnd=rnd, check=settings["Check command"],
                                       prepare=settings["Prepare command"], tails=tails)
            if feedback:
                continue
        reverted = revert_check(issue, project, tree, head, settings, locked, info.get("body") or "")
        review, _ = ask("reviewer", settings["Reviewer"], rnd=rnd, report=report, locked=locked,
                        extra="\nLatest test result: passed on this commit. " + " | ".join(tails) + "\n"
                        + reverted
                        + ("\nThe previous review returned CHANGES with these fixes:\n" + "\n".join(fixes) + "\n"
                           if fixes else ""))
        verdict, _ = merge.parse_verdict(review)
        if verdict != "APPROVE" and settings["Reviewer"][0] == "codex" and session.sandbox_refusal(review):
            raise Parked("The Codex sandbox refused the review command.",
                         "Resolve the sandbox refusal, then retry the review.")
        try:  # the person can follow the fix rounds; a failure to post never stops the build
            post_once(issue, "## Review, round %d\n\n%s\n\n%s\n" % (posted + rnd, review.strip(), common.MARKER))
        except common.GitHubError as e:
            common.event("note-failed", project, issue=issue, reason=str(e))
        if verdict == "APPROVE":
            push_issue(branch, tree)
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
                note_after_merge(issue, project, report, review, result.commit, landed.files, pr,
                                 earlier=earlier, shape_note=shape_note, selection=tails[0] if tails else "")
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
