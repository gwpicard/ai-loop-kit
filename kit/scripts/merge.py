"""Merge one reviewed issue branch into the loop branch, or refuse with a reason."""
import ast
import collections
import contextlib
import fnmatch
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess

import common
import status
from common import gh, git

Result = collections.namedtuple("Result", "ok park reason commit rule", defaults=(None,))
TEST_TIMEOUT = 1800
TARGETED_MODULE_CAP = 40
LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "uv.lock", "cargo.lock", "go.sum", "gemfile.lock", "package.json",
    "pyproject.toml", "go.mod", "cargo.toml", "pipfile.lock", "composer.lock",
    "gemfile", "pipfile", "composer.json", "bun.lock", "bun.lockb", "npm-shrinkwrap.json",
    "podfile.lock", "mix.lock", "pubspec.lock", "flake.lock", "package.resolved",
    "pdm.lock", "deno.lock", "pom.xml", "build.gradle"}
TEST_NAMES = ("test[ _]*", "*_test.*", "*_tests.*", "*-test.*", "*_spec.*", "*.test.*", "*.spec.*", "tests.py", "test.py", "conftest.py")
TEST_DIRS = ("tests", "test", "__tests__", "spec")
TEST_CLASS = re.compile(r"(Tests?\.(java|php|kt|cs|swift)|Spec\.(scala|hs)|(^|/)Test[^/]*\.java)$")  # case matters: Contest.swift is source
ARTEFACT = re.compile(r"(^|/)__pycache__/|\.(pyc|pyo|class|o)$")  # compiled output is never a test
BUILD = re.compile(r"(^|/)(node_modules|\.pytest_cache|build|dist|target)/")  # not a test unless named like one


AGENT_TRAILER = re.compile(
    r"^\s*co-authored-by:.*(claude|codex|chatgpt|openai|@anthropic\.com|@openai\.com)",
    re.I)
AGENT_FOOTER = re.compile(
    r"^[ \t]*claude-session:|claude\.ai/code/" + r"session_"
    r"|generated (with|by) \[claude code\]"
    r"|^[^a-z0-9]*generated (with|by) claude code[ \t.]*$"
    # Co-author addresses remain governed by Agent attribution.
    r"|^(?![ \t]*co-authored-by:).*noreply@anthropic\.com",
    re.I)


def squash_body(project, loop, sha, settings):
    """The builder's commit messages in order, with the project's chosen trailers."""
    log = git(["log", "--reverse", "--format=%B%x00", "origin/%s..%s" % (loop, sha)],
              cwd=project)
    messages = []
    sign_off = ""
    if settings["Sign-off"]:
        name = git(["config", "user.name"], cwd=project)
        email = git(["config", "user.email"], cwd=project)
        sign_off = "Signed-off-by: %s <%s>" % (name, email)
    for raw in log.split("\0"):
        lines = [l for l in raw.strip().splitlines()
                 if (settings["Agent attribution"] or not AGENT_TRAILER.match(l))
                 and not AGENT_FOOTER.search(l)
                 and (not sign_off or l.strip().casefold() != sign_off.casefold())]
        if text := "\n".join(lines).strip():
            messages.append(text)
    return "\n\n".join(messages + ([sign_off] if sign_off else []))


def _refuse(rule, reason, park=False):
    return Result(False, park, reason, None, rule)


def parse_verdict(text):
    """Return (verdict, head) from the last VERDICT block, or (None, None)."""
    lines = text.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        header = re.match(r"[\s*`]*VERDICT[*`]*:", lines[i])
        if header:
            m = re.match(r"[\s*`]*(\w+)([\s*`.,;:!]*)(.*)$", lines[i][header.end():])
            if not m:
                return None, None
            # Trailing words after the verdict word: a non-APPROVE verdict stands, an APPROVE does not.
            if m.group(3).strip("*` ") and m.group(1).upper() == "APPROVE":
                return "UNCLEAR", None
            for line in lines[i + 1:i + 4]:
                h = re.match(r"[\s*`]*HEAD[*`]*:[\s*`]*([0-9a-fA-F]{7,40})[\s*`.,;:!]*$", line)
                if h:
                    return m.group(1).upper(), h.group(1).lower()
            return m.group(1).upper(), None
    return None, None


def _items(text):
    return [re.sub(r"^\d+[.)]\s+", "", p.strip()).lstrip("-* ").strip("` ") for p in text.splitlines()]


def locked_paths(comments):
    """Paths in every `TESTS:` block of the issue comments."""
    paths = []
    for c in comments:
        for m in re.finditer(r"^[ \t]*TESTS:[ \t]*\n(?:[ \t]*\n)*(.*?)(?:\n[ \t]*\n|\Z)",
                             (c.get("body") or "").replace("\r\n", "\n"), re.S | re.M):
            paths += _items(m.group(1))
    return paths


def locked_baseline(comments):
    """The commit named by the last `Commit:` line of the last `TESTS:` comment: the test writer's final
    commit. None for a comment without one."""
    for c in reversed(comments):
        body = (c.get("body") or "").replace("\r\n", "\n")
        if re.search(r"^[ \t]*TESTS:", body, re.M):
            found = re.findall(r"^[ \t]*Commit:[ \t]*([0-9a-f]{7,40})[ \t]*$", body, re.M)
            return found[-1] if found else None


def allowed_paths(body):
    """Paths listed under the issue's `## Protected paths this issue may change`."""
    body = body.replace("\r\n", "\n")
    body = re.sub(r"^ {0,3}(`{3,}|~{3,})[^\n]*\n.*?(?:^ {0,3}\1[`~]*[ \t]*$|\Z)", "", body,
                  flags=re.S | re.M)  # fenced content grants nothing
    m = re.search(r"^## Protected paths this issue may change[^\n]*\n(.*?)(?=^## |\Z)",
                  body, re.S | re.M | re.I)
    return {p.removeprefix("./") for p in _items(m.group(1) if m else "")
            if p.lower() not in ("", "none")}


def is_test_module(path):
    name = path.lower().split("/")[-1]
    return not ARTEFACT.search(path.lower()) and (
        any(fnmatch.fnmatch(name, n) for n in TEST_NAMES) or bool(TEST_CLASS.search(path)))


def is_test_file(path):
    parts = path.lower().split("/")
    return is_test_module(path) or not ARTEFACT.search(path.lower()) and any(
        p in TEST_DIRS for p in parts[:-1]) and not BUILD.search(path.lower())


def stop_reason(path, protected, project=".", ref=None):
    """Why a changed path is on the stops list, or None. Case-insensitive."""
    low = path.lower()
    name = low.split("/")[-1]
    for p in protected:
        prefix = p.lower().removeprefix("./").rstrip("/")
        if (low + "/").startswith(prefix + "/"):
            return "protected path " + p
    if low.startswith(".github/workflows/"):
        return "workflow file"
    if name == "setup.py":
        folder = os.path.dirname(path)
        if not folder or any(
                git(["ls-tree", "--name-only", ref, "--", os.path.join(folder, p)], project)
                if ref else os.path.isfile(os.path.join(project, folder, p))
                for p in ("pyproject.toml", "setup.cfg")):
            return "lockfile or package manifest"
    if name in LOCKFILES or re.match(r"requirements.*\.(txt|in)$", name):
        return "lockfile or package manifest"
    if name in ("settings.json", "settings.local.json") or low in ("loop.json", "loop.local.json"):
        return "settings file"
    return None


def test_imports(path, text):
    """Dotted import names, including from imports and ancestor packages."""
    names = set()
    for node in ast.walk(ast.parse(text, filename=path)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = node.module or ""
            if node.level:
                parts = path.split("/")[:-node.level]
                prefix = ".".join(parts + ([prefix] if prefix else []))
            if prefix:
                names.add(prefix)
            names.update(".".join(filter(None, (prefix, alias.name)))
                         for alias in node.names if alias.name != "*")
    # Importing a submodule executes each ancestor package's initialiser.
    return {".".join(name.split(".")[:i]) for name in names
            for i in range(1, name.count(".") + 2)}


def importing_tests(cwd, changed, selected, head=None):
    """Select test importers to a fixed point without executing project code."""
    paths = git(["ls-tree", "-rz", "--name-only", head] if head else
                ["ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd).split("\0")
    tests = {}
    for path in sorted(set(paths)):
        if not is_test_module(path):
            continue
        if head:
            text = git(["show", head + ":" + path], cwd)
        else:
            try:
                text = Path(cwd, path).read_text(encoding="utf-8", errors="replace")
            except FileNotFoundError:
                continue
        imports = None
        if path.endswith(".py"):
            try:
                imports = test_imports(path, text)
            except (SyntaxError, ValueError, RecursionError):
                pass  # invalid Python uses the same fallback as other languages
        tests[path] = (imports, text)
    causes = {}
    pending = set(changed) | set(selected)
    selected.difference_update(path for path in changed if path not in tests)
    visited = set()
    while pending:
        cause = min(pending)
        pending.remove(cause)
        if not cause or cause in visited:
            continue
        visited.add(cause)
        module = cause.removesuffix(".py").replace("/", ".")
        module = module.removesuffix(".__init__")
        for path, (imports, text) in tests.items():
            if path in selected:
                continue
            fallback = imports is None or not cause.endswith(".py")
            matches = (PurePosixPath(cause).stem in text if fallback else
                       any(module == name or module.endswith("." + name) for name in imports))
            if matches:
                selected.add(path)
                causes[path] = ("mentions " if fallback else "imports ") + cause
                pending.add(path)
    return causes


def targeted_command(settings, cwd, start, locked, head=None):
    if not settings["Test files command"]:
        return settings["Test command"], "Test command: full suite"
    changed = git(["diff", "-z", "--name-only", start]
                  + ([head] if head else []) + ["--"], cwd=cwd).split("\0") if start else []
    files = {p for p in list(locked) + changed if is_test_module(p)}
    causes = importing_tests(cwd, changed, files, head) if start else {}
    files = sorted(files)
    extra = "".join("\n%s: %s" % (path, causes[path]) for path in sorted(causes))
    if len(files) > TARGETED_MODULE_CAP:
        return settings["Test command"], "Test command: full suite (%d modules exceed cap %d)%s" % (
            len(files), TARGETED_MODULE_CAP, extra)
    if not files:  # an empty list would run the whole suite
        return "", "Test files command: no test files to run"
    return common.files_command(settings, files), "Test files command: " + ", ".join(files) + extra


def check_diff(project, base, sha, protected, allowed, locked, baseline=None):
    """Return a park reason for the first stop or test-lock breach, or None. A locked file must equal
    its content and mode at `baseline` (the writer's final commit), else at the commit that first added it."""
    out = git(["diff", "-z", "--no-renames", "--name-status", base + "..." + sha],
              cwd=project).split("\0")
    for status, path in zip(out[0::2], out[1::2]):
        if path in allowed:
            continue
        why = stop_reason(path, protected, project, sha)
        if why is None and status[0] in "MDT" and is_test_module(path):
            why = "existing test file changed"
        if why:
            return "%s: %s" % (why, path)
    for path in locked:
        if path in allowed or not is_test_module(path):
            continue
        first = baseline or git(["log", "--diff-filter=A", "--reverse", "--format=%H",
                                 base + ".." + sha, "--", path], cwd=project).split("\n")[0]
        if not first:
            continue
        if baseline and subprocess.run(["git", "cat-file", "-e", first + ":" + path], cwd=project).returncode:
            continue  # the writer's final commit does not hold it
        a, b = [subprocess.run(["git", "show", ref + ":" + path], cwd=project,
                               capture_output=True) for ref in (first, sha)]
        if b.returncode != 0:
            return "locked test deleted: " + path
        modes = [git(["ls-tree", ref, "--", path], cwd=project).split()[:1]
                 for ref in (first, sha)]
        if a.stdout != b.stdout or modes[0] != modes[1]:
            return "locked test modified: " + path
    return None


def run_in(name, command, tree, label, tail=1, tails=None, kinds=None, log=None):
    """Run one named command in `tree`. Return None or a reason; a pass adds its last line to `tails`.
    `kinds` collects (name, "timeout", "unrunnable" for exit 126 or 127, or "failed")."""
    code, out = common.run_shell(command, tree, TEST_TIMEOUT)
    if log:
        with open(log, "a") as f:
            f.write("$ %s\n%s%s" % (command, out, "" if out.endswith("\n") or not out else "\n"))
            if code is None:
                f.write("timed out\n")
    if kinds is not None and code != 0:
        kinds.append((name, "timeout" if code is None else "unrunnable" if code in (126, 127) else "failed"))
    if code is None:
        return "the %s command timed out on %s" % (name, label)
    if code != 0:
        return "the %s command failed on %s: %s" % (name, label, "\n".join(out.strip().splitlines()[-tail:]))
    if tails is not None:
        tails.append("%s command passed: %s" % (name, (out.strip().splitlines() or ["no output"])[-1]))


def run_tests(project, sha, command, tail=1, check="", overlay=None, prepare="", tails=None, kinds=None, log=None, where=None):
    """Run the Prepare, Test and Check commands, in that order, in a fresh detached worktree
    at sha. overlay=(folder, paths) first copies those files in. Return None or a reason;
    `tails` collects the last line of each passing Test and Check command. `log` is a file
    that is replaced by the full output of each command that ran; `where` receives the checkout path."""
    with common.scratch_tree(project, sha) as tree:
        if where is not None:
            where.append(tree)
        if log:
            os.makedirs(os.path.dirname(log), exist_ok=True)
            open(log, "w").close()
        for path in overlay[1] if overlay else ():
            if os.path.isfile(os.path.join(overlay[0], path)):
                os.makedirs(os.path.dirname(os.path.join(tree, path)), exist_ok=True)
                shutil.copy(os.path.join(overlay[0], path), os.path.join(tree, path))
        for name, cmd in (("Prepare", prepare), ("Test", command), ("Check", check)):
            if cmd:
                common.wait_for_disk(project)
            if cmd and (failure := run_in(name, cmd, tree, sha[:10], tail, tails if name != "Prepare" else None, kinds, log)):
                return failure
        return None


def find_pr(branch, base, sha):
    out = gh(["pr", "list", "--head", branch, "--base", base, "--state", "all",
              "--json", "number,state,headRefOid,mergeCommit"])
    prs = [p for p in json.loads(out or "[]")
           if p["state"] in ("OPEN", "MERGED") and p.get("headRefOid") == sha]
    return min(prs, key=lambda p: p["state"] != "MERGED", default=None)


def view(kind, number, field):
    return json.loads(gh([kind, "view", str(number), "--json", field]) or "{}")


def full_suite_due(project, settings):
    """Count successful merges since the last full run, including across restarts."""
    if "{files}" not in settings["Test files command"]:
        # A command without the placeholder cannot select the issue's tests.
        return True
    count = 0
    for event in reversed(status.read_events(project)):
        if event["kind"] == "drain" and event.get("phase") == "end" and event.get("outcome") == "pass":
            break
        if event["kind"] == "merged":
            if event.get("full_suite", True):  # older merges always ran the full suite
                break
            count += 1
    return count >= settings["Full suite every"] - 1


def merge(issue, branch, verdict_text, project="."):
    with common.timed("step", project, issue=issue, step="merge") as end:
        try:
            result = _merge(issue, branch, verdict_text, project)
        except Exception as e:  # fail closed: a refusal, never a traceback
            result = _refuse("merge-error", str(e) or type(e).__name__)
        end["outcome"] = "merged" if result.ok else "refused"
        if not result.ok:
            end.update(rule=result.rule, reason=result.reason)
            common.event("rule", project, issue=issue, role="merge", rule=result.rule, reason=result.reason)
        return result


def _merge(issue, branch, verdict_text, project):
    settings = common.build_settings(project)
    loop = settings["Loop branch"]
    verdict, head = parse_verdict(verdict_text)
    if verdict != "APPROVE":
        return _refuse("review-verdict", "the review verdict is %s, not APPROVE" % (verdict or "missing"))
    git(["fetch", "--no-prune", "origin"], cwd=project)
    common.restore_loop_branch(project, loop)
    sha = git(["rev-parse", "--verify", "origin/" + branch], cwd=project)
    if not head or not sha.startswith(head):
        return _refuse("review-head", "the branch head %s is not the reviewed commit %s"
                       % (sha[:10], (head or "none")[:10]))
    info = view("issue", issue, "body,comments")
    if stop := check_diff(project, "origin/" + loop, sha, settings["Protected paths"],
                      allowed_paths(info.get("body") or ""), locked_paths(info.get("comments", [])),
                      locked_baseline(info.get("comments", []))):
        return _refuse("test-lock" if stop.startswith(("existing test", "locked test")) else
                       "protected-path" if stop.startswith("protected path") else
                       "workflow" if stop.startswith("workflow file") else
                       "settings" if stop.startswith("settings file") else "dependency", stop, park=True)
    locked = locked_paths(info.get("comments", []))
    # Without the writer's test list, changed files alone may miss the issue's tests.
    full_suite = not any(is_test_module(path) for path in locked) or full_suite_due(project, settings)
    command, description = targeted_command(settings, project, "origin/" + loop, locked, sha)
    full_suite = full_suite or command == settings["Test command"]
    if full_suite:
        command = settings["Test command"]
        if not description.startswith("Test command: full suite"):
            why = "merge cadence" if locked else "no locked test modules"
            description = "Test command: full suite (%s)\n%s" % (why, description)
    common.say("Merge tests: " + description.replace("\n", "; "))
    kinds = []
    if failure := run_tests(project, sha, command, kinds=kinds,
                            check=settings["Check command"], prepare=settings["Prepare command"]):
        if full_suite and kinds and kinds[0][0] == "Test":
            if baseline_failure := run_tests(project, "origin/" + loop, settings["Test command"],
                                            prepare=settings["Prepare command"]):
                return _refuse("test-command", failure + "\nThe failure was already on the loop branch: "
                               + baseline_failure, park=True)
        return _refuse("test-command", failure)
    pr = find_pr(branch, loop, sha)
    if pr is None:
        with contextlib.suppress(common.GitHubError):
            gh(["pr", "create", "--base", loop, "--head", branch,
                "--title", "Issue %s" % issue, "--body", "Built by the loop."], retry=False)
        pr = find_pr(branch, loop, sha)
        if pr is None:
            return _refuse("pull-request", "the pull request could not be created")
    if pr["state"] == "OPEN":
        number, err = pr["number"], None
        comments = view("pr", number, "comments").get("comments", [])
        if not any((c.get("body") or "").strip() == verdict_text.strip()
                   for c in comments):
            gh(["pr", "comment", str(number), "--body-file", "-"],
               input=verdict_text, retry=False)
        try:
            gh(["pr", "merge", str(number), "--squash",
                "--subject", "Issue %s (#%s)" % (issue, number),
                "--body", squash_body(project, loop, sha, settings),
                "--match-head-commit", sha, "--delete-branch"], retry=False)
        except common.GitHubError as e:
            err = e
        pr = find_pr(branch, loop, sha)
        if pr is None or pr["state"] != "MERGED":
            return _refuse("merge-refused", str(err or "the pull request is not merged"))
    commit = (pr.get("mergeCommit") or {}).get("oid") or "unknown"
    try:
        gh(["issue", "close", str(issue), "--comment",
            "Merged into %s as %s.\n\n%s" % (loop, commit, common.MARKER)], retry=False)
    except common.GitHubError:
        if view("issue", issue, "state").get("state") != "CLOSED":
            return _refuse("issue-close", "merged as %s but the issue did not close" % commit)
    common.remove_label(issue, "building")
    common.event("merged", project, issue=issue, branch=branch, commit=commit, full_suite=full_suite,
                 test_selection=description)
    return Result(True, False, "merged as " + commit, commit)

