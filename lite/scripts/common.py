"""Shared helpers: settings, GitHub and git calls, events, labels, trust."""
import contextlib
import fcntl
import json
import os
import re
import shlex
import signal
import subprocess
import tempfile
import time

RETRY_WAITS = (5, 20, 60)
RATE_LIMIT_CAP = 65 * 60
TIMEOUT = 120
TRANSIENT = re.compile(
    r"HTTP 5\d\d|timed? ?out|connection (reset|refused)|no such host"
    r"|network is unreachable|unexpected EOF", re.I)
RATE_LIMITED = re.compile(r"HTTP (403|429)|rate limit", re.I)

DEFAULTS = {
    "Loop branch": "loop/main",
    "Builder model": "sonnet",
    "Reviewer model": "sonnet",
    "Protected paths": ".github/, .claude/, .githooks/",
    "Idle hours": "12",
    "Max rounds": "3",
    "Session minutes": "45",
    "Check command": "",
    "Smoke command": "",
    "Test files command": "",  # {files} stands for the paths; empty means the Test command
    "Prepare command": "",  # run once in each worktree, before any test run
    "Parallel": "1",  # builds running at once
}


MARKER = "<!-- lite-loop -->"  # on every comment the loop posts; replies lack it


class LoopError(Exception):
    """An expected failure with a one-line message."""


class GitHubError(LoopError):
    pass


class GitError(LoopError):
    pass


class SettingsError(LoopError):
    pass


def sleep(seconds):
    time.sleep(seconds)


# Settings

def read_settings(root="."):
    """Read the `## Loop` section of AGENTS.md into a dict with defaults."""
    path = os.path.join(root, "AGENTS.md")
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        raise SettingsError("no AGENTS.md in " + os.path.abspath(root))
    found, inside = {}, False
    for line in text.splitlines():
        if re.match(r"#{1,6}\s", line):
            inside = line.strip().lower() == "## loop"
            continue
        m = re.match(r"\s*([A-Za-z ]+?):\s*(.*?)\s*$", line)
        if inside and m:
            found[m.group(1)] = m.group(2).replace("`", "").strip()
    settings = dict(DEFAULTS)
    settings.update({k: v for k, v in found.items() if v and k in DEFAULTS})
    if not found.get("Test command"):
        raise SettingsError("AGENTS.md has no 'Test command:' under '## Loop'")
    settings["Test command"] = found["Test command"]
    settings["Protected paths"] = [
        p.strip() for p in settings["Protected paths"].split(",") if p.strip()]
    settings["Idle hours"] = float(settings["Idle hours"])
    settings["Max rounds"] = int(settings["Max rounds"])
    settings["Session minutes"] = float(settings["Session minutes"])
    settings["Parallel"] = max(1, int(settings["Parallel"]))
    return settings


# GitHub

def _run_gh(args, input=None):
    try:
        p = subprocess.run(["gh"] + list(args), input=input, text=True,
                           capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return 124, "", "gh timed out after %s seconds" % TIMEOUT
    except OSError as e:
        raise GitHubError("cannot run gh: %s" % e)
    return p.returncode, p.stdout, p.stderr


def _wait_for_reset():
    """Wait for a rate limit to reset. Return False if none is exhausted."""
    _, out, _ = _run_gh(["api", "rate_limit"])
    try:
        resets = [r["reset"] for r in json.loads(out)["resources"].values()
                  if r.get("remaining") == 0]
    except (ValueError, KeyError):
        return False
    if not resets:
        return False
    sleep(min(max(max(resets) - time.time(), 0), RATE_LIMIT_CAP))
    return True


def gh(args, input=None, retry=True):
    """Run gh and return stdout. Retries 5xx and network failures, waits out
    a rate limit once, and raises GitHubError with one line otherwise.
    Pass retry=False for a write that is not safe to repeat."""
    waits, limited = list(RETRY_WAITS) if retry else [], not retry
    while True:
        code, out, err = _run_gh(args, input)
        if code == 0:
            return out
        if TRANSIENT.search(err) and waits:
            sleep(waits.pop(0))
            continue
        if RATE_LIMITED.search(err) and not limited:
            limited = True
            if _wait_for_reset():
                continue
        lines = err.strip().splitlines()
        raise GitHubError("gh %s failed: %s" % (
            " ".join(args[:2]), lines[0] if lines else "exit %d" % code))


def add_label(number, label):
    gh(["issue", "edit", str(number), "--add-label", label])


def remove_label(number, label):
    gh(["issue", "edit", str(number), "--remove-label", label])


def _json_values(text):
    """Decode the JSON values gh --paginate prints one after another."""
    decoder, pos, values = json.JSONDecoder(), 0, []
    while True:
        text = text[pos:].lstrip()
        if not text:
            return values
        value, pos = decoder.raw_decode(text)
        values.append(value)


def ready_is_trusted(number):
    """True if the last person to add `ready` has write or admin access.
    Any failure to find out counts as not trusted."""
    out = gh(["api", "--paginate",
              "repos/{owner}/{repo}/issues/%s/timeline" % number])
    actor = None
    for page in _json_values(out):
        for e in page:
            if (e.get("label") or {}).get("name") != "ready":
                continue
            if e.get("event") == "labeled":
                actor = (e.get("actor") or {}).get("login")
            elif e.get("event") == "unlabeled":
                actor = None
    return bool(actor) and has_write(actor)


def has_write(user):
    """True if the user has write or admin access. Failure counts as no."""
    try:
        perm = json.loads(gh(["api", "repos/{owner}/{repo}/collaborators/%s/"
                              "permission" % user]))
    except (GitHubError, ValueError):
        return False
    return perm.get("permission") in ("write", "admin")


def depends_on(body):
    """Issue numbers named on `Depends on: #a, #b` lines."""
    numbers = []
    for m in re.finditer(r"^\s*Depends on:(.*)$", body or "", re.I | re.M):
        numbers += [int(n) for n in re.findall(r"#(\d+)", m.group(1))]
    return numbers


# git

def git(args, cwd=None, check=True):
    """Run git and return stdout without the trailing newline."""
    try:
        p = subprocess.run(["git"] + list(args), cwd=cwd, text=True,
                           capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise GitError("git %s timed out after %s seconds"
                       % (" ".join(args[:2]), TIMEOUT))
    if check and p.returncode != 0:
        lines = p.stderr.strip().splitlines()
        raise GitError("git %s failed: %s" % (
            " ".join(args[:2]), lines[0] if lines else "exit %d" % p.returncode))
    return p.stdout.rstrip("\n")


def _record(path, pid, add):
    """Add a process group id to the list in `path`, or take it off."""
    try:
        pids = open(path).read().split() if os.path.exists(path) else []
        with open(path, "w") as f:
            f.write("".join(p + "\n" for p in [p for p in pids if p != str(pid)] + [str(pid)] * add))
    except OSError:
        pass


def run_shell(command, cwd, timeout, record=None):
    """Run a shell command in its own process group. Return (exit code, output); the code is None on timeout.
    With `record`, the group id is listed in that file while the command runs, so whoever
    ends the caller can also end the command."""
    p = subprocess.Popen(command, shell=True, cwd=cwd, text=True, start_new_session=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if record:
        _record(record, p.pid, True)
    try:
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, out
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        return None, ""
    finally:
        if record:
            _record(record, p.pid, False)


def files_command(settings, files):
    """The Test files command for these paths, or the Test command when none is set."""
    if not settings["Test files command"]:
        return settings["Test command"]
    return settings["Test files command"].replace("{files}", " ".join(shlex.quote(f) for f in files))


def read_passed(project, session_id):
    """(commit, output tails) the Stop hook recorded when the full commands last passed for the session."""
    try:
        with open(os.path.join(project, ".lite", "passed-" + str(session_id))) as f:
            head, *tails = f.read().splitlines()
        return head.strip(), tails
    except (OSError, ValueError):
        return None, []


def default_branch(project):
    ref = git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=project, check=False)
    return ref.replace("origin/", "", 1) or "main"


@contextlib.contextmanager
def scratch_tree(project, ref):
    """A detached worktree of `ref` in a temporary folder, removed afterwards."""
    parent = tempfile.mkdtemp(prefix="lite-tree-")
    tree = os.path.join(parent, "tree")
    try:
        git(["worktree", "add", "--detach", tree, ref], cwd=project)
        yield tree
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", tree], cwd=project, capture_output=True)
        subprocess.run(["rmdir", parent], capture_output=True)


def build_file(root, issue, kind):
    """Where a running build keeps its `step` or its `result`: .lite/builds/<issue>.<kind>."""
    return os.path.join(root, ".lite", "builds", "%s.%s" % (issue, kind))


@contextlib.contextmanager
def merge_lock(root):
    """One merge into the loop branch at a time, across processes. The lock is released when the
    holder ends, even if it dies."""
    os.makedirs(os.path.join(root, ".lite"), exist_ok=True)
    with open(os.path.join(root, ".lite", "merge.lock"), "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def event(kind, root=".", **fields):
    """Append one JSON line to .lite/events.jsonl. A step of a build also becomes its step file, for the board."""
    folder = os.path.join(root, ".lite")
    os.makedirs(folder, exist_ok=True)
    if kind == "step" and "issue" in fields:
        os.makedirs(os.path.join(folder, "builds"), exist_ok=True)
        with open(build_file(root, fields["issue"], "step"), "w") as f:
            f.write(fields["step"] + (" round %s" % fields["round"] if "round" in fields else ""))
    record = dict(time=time.strftime("%Y-%m-%dT%H:%M:%S%z"), kind=kind, **fields)
    with open(os.path.join(folder, "events.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def park(issue, question, recommendation):
    """Hand an issue to the person: label needs-user, drop building, comment."""
    add_label(issue, "needs-user")
    remove_label(issue, "building")
    gh(["issue", "comment", str(issue), "--body-file", "-"], retry=False,
       input="## Needs you\n\n%s\n\nRecommended: %s\n\nReply on this issue; "
             "the loop picks up your reply.\n\n%s\n" % (question, recommendation, MARKER))
