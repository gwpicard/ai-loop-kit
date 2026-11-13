"""Merge one reviewed issue branch into the loop branch, or refuse with a reason."""
import collections
import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile

import common
from common import gh, git

Result = collections.namedtuple("Result", "ok park reason commit")
TEST_TIMEOUT = 1800
LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "uv.lock", "Cargo.lock", "go.sum", "Gemfile.lock", "package.json",
    "pyproject.toml", "go.mod", "Cargo.toml"}
TEST_NAMES = ("test_*", "*_test.*", "*.test.*", "*.spec.*")
TEST_DIRS = ("tests", "test", "__tests__")


def _refuse(reason, park=False):
    return Result(False, park, reason, None)


def parse_verdict(text):
    """Return (verdict, head) from the last VERDICT block, or (None, None)."""
    lines = text.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        m = re.match(r"\s*VERDICT:\s*(\w+)\s*$", lines[i])
        if m:
            for line in lines[i + 1:i + 4]:
                h = re.match(r"\s*HEAD:\s*([0-9a-fA-F]{7,40})\s*$", line)
                if h:
                    return m.group(1).upper(), h.group(1).lower()
            return m.group(1).upper(), None
    return None, None


def locked_paths(comments):
    """Paths in the last `TESTS:` block of the issue comments."""
    paths = []
    for c in comments:
        lines = (c.get("body") or "").splitlines()
        for i, line in enumerate(lines):
            if re.match(r"\s*TESTS:\s*$", line):
                found = []
                for p in lines[i + 1:]:
                    if not p.strip():
                        break
                    found.append(p.strip().lstrip("-* ").strip("` "))
                paths = found
    return paths


def is_test_file(path):
    parts = path.split("/")
    return (any(fnmatch.fnmatch(parts[-1], n) for n in TEST_NAMES)
            or any(p in TEST_DIRS for p in parts[:-1]))


def stop_reason(path, protected):
    """Why a changed path is on the stops list, or None."""
    name = path.split("/")[-1]
    for p in protected:
        if path == p.rstrip("/") or path.startswith(p.rstrip("/") + "/"):
            return "protected path " + p
    if path.startswith(".github/workflows/"):
        return "workflow file"
    if name in LOCKFILES or re.match(r"requirements.*\.txt$", name):
        return "lockfile or package manifest"
    if name in ("settings.json", "settings.local.json"):
        return "settings file"
    return None


def changed(project, base, sha):
    out = git(["diff", "--no-renames", "--name-status", base + "..." + sha],
              cwd=project)
    return [tuple(line.split("\t", 1)) for line in out.splitlines() if line]


def check_diff(project, base, sha, protected, body, locked):
    """Return a park reason for the first stop or test-lock breach, or None."""
    for status, path in changed(project, base, sha):
        if path in body:
            continue
        why = stop_reason(path, protected)
        if why is None and status[0] in "MD" and is_test_file(path):
            why = "existing test file " + ("deleted" if status[0] == "D"
                                           else "modified")
        if why:
            return "%s: %s" % (why, path)
    for path in locked:
        if path in body:
            continue
        first = git(["log", "--diff-filter=A", "--reverse", "--format=%H",
                     base + ".." + sha, "--", path], cwd=project).split("\n")[0]
        if not first:
            continue
        a = subprocess.run(["git", "show", first + ":" + path], cwd=project,
                           capture_output=True)
        b = subprocess.run(["git", "show", sha + ":" + path], cwd=project,
                           capture_output=True)
        if b.returncode != 0:
            return "locked test deleted: " + path
        if a.stdout != b.stdout:
            return "locked test modified: " + path
    return None


def run_tests(project, sha, command):
    """Run the Test command in a fresh detached worktree. Return None or a reason."""
    parent = tempfile.mkdtemp(prefix="lite-merge-")
    tree = os.path.join(parent, "tree")
    try:
        git(["worktree", "add", "--detach", tree, sha], cwd=project)
        try:
            p = subprocess.run(command, shell=True, cwd=tree, text=True,
                               capture_output=True, timeout=TEST_TIMEOUT)
        except subprocess.TimeoutExpired:
            return "the Test command timed out on " + sha[:10]
        if p.returncode != 0:
            tail = (p.stdout + p.stderr).strip().splitlines()[-1:] or [""]
            return "the Test command failed on %s: %s" % (sha[:10], tail[0])
        return None
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", tree],
                       cwd=project, capture_output=True)
        subprocess.run(["git", "worktree", "prune"], cwd=project,
                       capture_output=True)
        try:
            os.rmdir(parent)
        except OSError:
            pass


def find_pr(branch, base):
    out = gh(["pr", "list", "--head", branch, "--base", base, "--state", "all",
              "--json", "number,state"])
    prs = [p for p in json.loads(out or "[]") if p["state"] in ("OPEN", "MERGED")]
    prs.sort(key=lambda p: p["state"] != "MERGED")
    return prs[0] if prs else None


def has_comment(pr, text):
    out = gh(["pr", "view", str(pr), "--json", "comments"])
    return any((c.get("body") or "").strip() == text.strip()
               for c in json.loads(out or "{}").get("comments", []))


def merged_commit(pr):
    out = json.loads(gh(["pr", "view", str(pr), "--json", "state,mergeCommit"]))
    if out.get("state") != "MERGED":
        return None
    return (out.get("mergeCommit") or {}).get("oid") or "unknown"


def merge(issue, branch, verdict_text, project="."):
    try:
        return _merge(issue, branch, verdict_text, project)
    except (common.LoopError, OSError, ValueError, KeyError) as e:
        return _refuse("%s" % e)


def _merge(issue, branch, verdict_text, project):
    settings = common.read_settings(project)
    loop = settings["Loop branch"]
    verdict, head = parse_verdict(verdict_text)
    if verdict != "APPROVE":
        return _refuse("the review verdict is %s, not APPROVE" % (verdict or "missing"))
    if not head:
        return _refuse("the review has no HEAD line")
    git(["fetch", "origin"], cwd=project)
    sha = git(["rev-parse", "--verify", "origin/" + branch], cwd=project)
    if sha != head and not (len(head) < 40 and sha.startswith(head)):
        return _refuse("the branch head %s is not the reviewed commit %s"
                       % (sha[:10], head[:10]))
    failure = run_tests(project, sha, settings["Test command"])
    if failure:
        return _refuse(failure)
    info = json.loads(gh(["issue", "view", str(issue), "--json", "body,comments"]))
    stop = check_diff(project, "origin/" + loop, sha, settings["Protected paths"],
                      info.get("body") or "", locked_paths(info.get("comments", [])))
    if stop:
        return _refuse(stop, park=True)
    pr = find_pr(branch, loop)
    if pr is None:
        try:
            gh(["pr", "create", "--base", loop, "--head", branch,
                "--title", "Issue %s" % issue, "--body", "Built by the loop."],
               retry=False)
        except common.GitHubError:
            pass
        pr = find_pr(branch, loop)
        if pr is None:
            return _refuse("the pull request could not be created")
    number = pr["number"]
    if pr["state"] == "OPEN":
        try:
            gh(["pr", "comment", str(number), "--body-file", "-"],
               input=verdict_text, retry=False)
        except common.GitHubError:
            if not has_comment(number, verdict_text):
                return _refuse("the review could not be posted on the pull request")
        try:
            gh(["pr", "merge", str(number), "--squash", "--match-head-commit",
                sha, "--delete-branch"], retry=False)
        except common.GitHubError as e:
            if not merged_commit(number):
                return _refuse(str(e))
    commit = merged_commit(number)
    if not commit:
        return _refuse("the pull request is not merged")
    try:
        gh(["issue", "close", str(issue), "--comment",
            "Merged into %s as %s." % (loop, commit)], retry=False)
    except common.GitHubError:
        if json.loads(gh(["issue", "view", str(issue), "--json", "state"])
                      ).get("state") != "CLOSED":
            return _refuse("merged as %s but the issue did not close" % commit)
    common.event("merged", project, issue=issue, branch=branch, commit=commit)
    return Result(True, False, "merged as " + commit, commit)


def main(argv):
    if len(argv) != 3:
        print("usage: merge.py <issue> <branch> <verdict-file or ->")
        return 2
    text = sys.stdin.read() if argv[2] == "-" else open(argv[2]).read()
    r = merge(int(argv[0]), argv[1], text, os.getcwd())
    if r.ok:
        print(r.reason)
        return 0
    print("refused: " + r.reason)
    print("next: " + ("answer the parked issue" if r.park
                      else "the loop will review or fix it again"))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
