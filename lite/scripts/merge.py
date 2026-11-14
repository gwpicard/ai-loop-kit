"""Merge one reviewed issue branch into the loop branch, or refuse with a reason."""
import collections
import fnmatch
import json
import os
import re
import signal
import subprocess
import sys
import tempfile

import common
from common import gh, git

Result = collections.namedtuple("Result", "ok park reason commit")
TEST_TIMEOUT = 1800
LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "uv.lock", "cargo.lock", "go.sum", "gemfile.lock", "package.json",
    "pyproject.toml", "go.mod", "cargo.toml"}
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


def _items(text):
    return [p.strip().lstrip("-* ").strip("` ") for p in text.splitlines()]


def locked_paths(comments):
    """Paths in every `TESTS:` block of the issue comments."""
    paths = []
    for c in comments:
        for m in re.finditer(r"^[ \t]*TESTS:[ \t]*\n(.*?)(?:\n[ \t]*\n|\Z)",
                             c.get("body") or "", re.S | re.M):
            paths += _items(m.group(1))
    return paths


def allowed_paths(body):
    """Paths listed under the issue's `## Paths the builder may change`."""
    m = re.search(r"^## Paths the builder may change[^\n]*\n(.*?)(?=^## |\Z)",
                  body, re.S | re.M | re.I)
    return {p for p in _items(m.group(1) if m else "")
            if p.lower() not in ("", "none")}


def is_test_file(path):
    parts = path.lower().split("/")
    return (any(fnmatch.fnmatch(parts[-1], n) for n in TEST_NAMES)
            or any(p in TEST_DIRS for p in parts[:-1]))


def stop_reason(path, protected):
    """Why a changed path is on the stops list, or None. Case-insensitive."""
    low = path.lower()
    name = low.split("/")[-1]
    for p in protected:
        if (low + "/").startswith(p.lower().rstrip("/") + "/"):
            return "protected path " + p
    if low.startswith(".github/workflows/"):
        return "workflow file"
    if name in LOCKFILES or re.match(r"requirements.*\.txt$", name):
        return "lockfile or package manifest"
    if name in ("settings.json", "settings.local.json"):
        return "settings file"
    return None


def check_diff(project, base, sha, protected, allowed, locked):
    """Return a park reason for the first stop or test-lock breach, or None."""
    out = git(["diff", "-z", "--no-renames", "--name-status", base + "..." + sha],
              cwd=project).split("\0")
    for status, path in zip(out[0::2], out[1::2]):
        if path in allowed:
            continue
        why = stop_reason(path, protected)
        if why is None and status[0] in "MDT" and is_test_file(path):
            why = "existing test file changed"
        if why:
            return "%s: %s" % (why, path)
    for path in locked:
        if path in allowed:
            continue
        first = git(["log", "--diff-filter=A", "--reverse", "--format=%H",
                     base + ".." + sha, "--", path], cwd=project).split("\n")[0]
        if not first:
            continue
        a, b = [subprocess.run(["git", "show", ref + ":" + path], cwd=project,
                               capture_output=True) for ref in (first, sha)]
        if b.returncode != 0:
            return "locked test deleted: " + path
        if a.stdout != b.stdout:
            return "locked test modified: " + path
    return None


def run_tests(project, sha, command, tail=1):
    """Run the Test command in a fresh detached worktree. Return None or a reason."""
    parent = tempfile.mkdtemp(prefix="lite-merge-")
    tree = os.path.join(parent, "tree")
    try:
        git(["worktree", "add", "--detach", tree, sha], cwd=project)
        p = subprocess.Popen(command, shell=True, cwd=tree, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             start_new_session=True)
        try:
            out, _ = p.communicate(timeout=TEST_TIMEOUT)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.communicate()
            return "the Test command timed out on " + sha[:10]
        if p.returncode != 0:
            last = "\n".join(out.strip().splitlines()[-tail:])
            return "the Test command failed on %s: %s" % (sha[:10], last)
        return None
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", tree],
                       cwd=project, capture_output=True)
        subprocess.run(["rmdir", parent], capture_output=True)


def find_pr(branch, base, sha):
    out = gh(["pr", "list", "--head", branch, "--base", base, "--state", "all",
              "--json", "number,state,headRefOid,mergeCommit"])
    prs = [p for p in json.loads(out or "[]")
           if p["state"] in ("OPEN", "MERGED") and p.get("headRefOid") == sha]
    return min(prs, key=lambda p: p["state"] != "MERGED", default=None)


def view(kind, number, field):
    return json.loads(gh([kind, "view", str(number), "--json", field]) or "{}")


def merge(issue, branch, verdict_text, project="."):
    try:
        return _merge(issue, branch, verdict_text, project)
    except Exception as e:  # fail closed: a refusal, never a traceback
        return _refuse(str(e) or type(e).__name__)


def _merge(issue, branch, verdict_text, project):
    settings = common.read_settings(project)
    loop = settings["Loop branch"]
    verdict, head = parse_verdict(verdict_text)
    if verdict != "APPROVE":
        return _refuse("the review verdict is %s, not APPROVE" % (verdict or "missing"))
    git(["fetch", "--no-prune", "origin"], cwd=project)
    sha = git(["rev-parse", "--verify", "origin/" + branch], cwd=project)
    if not head or not sha.startswith(head):
        return _refuse("the branch head %s is not the reviewed commit %s"
                       % (sha[:10], (head or "none")[:10]))
    if failure := run_tests(project, sha, settings["Test command"]):
        return _refuse(failure)
    info = view("issue", issue, "body,comments")
    if stop := check_diff(project, "origin/" + loop, sha, settings["Protected paths"],
                      allowed_paths(info.get("body") or ""), locked_paths(info.get("comments", []))):
        return _refuse(stop, park=True)
    pr = find_pr(branch, loop, sha)
    if pr is None:
        try:
            gh(["pr", "create", "--base", loop, "--head", branch,
                "--title", "Issue %s" % issue, "--body", "Built by the loop."],
               retry=False)
        except common.GitHubError:
            pass
        pr = find_pr(branch, loop, sha)
        if pr is None:
            return _refuse("the pull request could not be created")
    if pr["state"] == "OPEN":
        number, err = pr["number"], None
        comments = view("pr", number, "comments").get("comments", [])
        if not any((c.get("body") or "").strip() == verdict_text.strip()
                   for c in comments):
            gh(["pr", "comment", str(number), "--body-file", "-"],
               input=verdict_text, retry=False)
        try:
            gh(["pr", "merge", str(number), "--squash", "--match-head-commit",
                sha, "--delete-branch"], retry=False)
        except common.GitHubError as e:
            err = e
        pr = find_pr(branch, loop, sha)
        if pr is None or pr["state"] != "MERGED":
            return _refuse(str(err or "the pull request is not merged"))
    commit = (pr.get("mergeCommit") or {}).get("oid") or "unknown"
    try:
        gh(["issue", "close", str(issue), "--comment",
            "Merged into %s as %s.\n\n%s" % (loop, commit, common.MARKER)], retry=False)
    except common.GitHubError:
        if view("issue", issue, "state").get("state") != "CLOSED":
            return _refuse("merged as %s but the issue did not close" % commit)
    common.remove_label(issue, "building")
    common.event("merged", project, issue=issue, branch=branch, commit=commit)
    return Result(True, False, "merged as " + commit, commit)


def main(argv):
    try:
        text = sys.stdin.read() if argv[2] == "-" else open(argv[2]).read()
        r = merge(int(argv[0]), argv[1], text, os.getcwd())
    except Exception as e:
        r = _refuse("usage: merge.py <issue> <branch> <verdict-file or -> (%s)" % e)
    print(r.reason if r.ok else "refused: %s\nnext: %s" % (r.reason, (
        "answer the parked issue" if r.park else "review or fix it again")))
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
