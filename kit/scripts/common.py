"""Shared helpers: settings, GitHub and git calls, events, labels, trust."""
import contextlib
import contextvars
import fcntl
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time

RETRY_WAITS = (5, 20, 60)
RATE_LIMIT_CAP = 65 * 60
TIMEOUT = 120
TRANSIENT = re.compile(
    r"HTTP 5\d\d|timed? ?out|connection (reset|refused)|no such host"
    r"|network is unreachable|unexpected EOF", re.I)
RATE_LIMITED = re.compile(r"HTTP (403|429)|rate limit", re.I)

ROLES = ("Builder", "Test writer", "Reviewer", "Pass")
AGENTS = ("claude", "codex")
CODEX_FLAGS = ("-s", "-m", "-c", "--json", "-o", "--dangerously-bypass-hook-trust")

DEFAULTS = {
    "Loop branch": "loop/main",
    "Builder model": "sonnet",  # older lines: set Builder and Test writer
    "Reviewer model": "sonnet",  # older lines: set Reviewer and Pass
    "Builder": "claude sonnet",
    "Test writer": "claude sonnet",
    "Reviewer": "claude sonnet",
    "Pass": "claude sonnet",
    "Protected paths": ".github/, .claude/, .githooks/",
    "Codex writable roots": "",  # comma-separated folders a Codex session may write, beyond temp and cache
    "Idle hours": "12",
    "Max rounds": "3",
    "Session minutes": "45",
    "Check command": "",
    "Smoke command": "",
    "Test files command": "",  # {files} stands for the paths; empty means the Test command
    "Prepare command": "",  # run once in each worktree, before any test run
    "Parallel": "1",  # builds running at once
}


MARKER = "<!-- lite-loop -->"  # on every comment the loop posts; replies lack it. Kept as is: comments already posted carry it


class LoopError(Exception):
    """An expected failure with a one-line message."""


class GitHubError(LoopError):
    pass


class GitError(LoopError):
    pass


class SettingsError(LoopError):
    pass


def say(text):
    for line in str(text).splitlines():
        print(time.strftime("%Y-%m-%d %H:%M:%S") + " " + line, flush=True)


_ACTIVE = contextvars.ContextVar("events", default={})


@contextlib.contextmanager
def timed(kind, root=".", **fields):
    key = (kind, os.path.abspath(root), fields.get("issue"), fields.get("step"))
    active = _ACTIVE.get()
    if key in active:
        yield active[key]
        return
    end = dict(outcome="crashed")
    token = _ACTIVE.set({**active, key: end})
    began = time.monotonic()
    try:
        event(kind, root, phase="start", **fields)
        yield end
    finally:
        _ACTIVE.reset(token)
        event(kind, root, phase="end", seconds=int(time.monotonic() - began), **fields, **end)


def sleep(seconds):
    time.sleep(seconds)


PRESSURE_POLL = 30  # seconds between readings while memory is under pressure
PRESSURE_REPEAT = 600  # seconds between repeats of the wait's first line


def pressure_level():
    """The macOS memory-pressure level (1 normal, 2 warning, 4 critical), or None when it cannot be read."""
    if sys.platform != "darwin":
        return None
    try:
        out = subprocess.run(["sysctl", "-n", "kern.memorystatus_vm_pressure_level"],
                             capture_output=True, text=True, timeout=10).stdout
        return int(out.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def wait_for_memory(patience=None):
    """Hold while macOS reports memory pressure, reading again every PRESSURE_POLL seconds. Give up after
    `patience` seconds when set. Print a line when the wait begins, every ten minutes and when it ends."""
    level = pressure_level()
    if level is None or level < 2:
        return
    began = last = time.time()
    say("waiting for memory pressure to ease (level %d)" % level)
    while level is not None and level >= 2:
        if patience is not None and time.time() - began >= patience:
            say("memory pressure did not ease in %d minutes; starting anyway" % (patience // 60))
            return
        sleep(PRESSURE_POLL)
        level = pressure_level()
        if level and level >= 2 and time.time() - last >= PRESSURE_REPEAT:
            last = time.time()
            say("still waiting for memory pressure to ease (level %d)" % level)
    say("memory pressure eased after %d minutes" % ((time.time() - began) // 60))


# Settings

def codex_refusal(settings):
    """Why the installed Codex cannot run the roles set to codex, or None. It runs no session."""
    roles = [r for r in ROLES if settings[r][0] == "codex"]
    if not roles:
        return None
    who = "%s set to codex" % ", ".join(roles)

    def ask(args):
        try:
            p = subprocess.run(["codex"] + args, capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
        return p.stdout + p.stderr if p.returncode == 0 else None
    if ask(["--version"]) is None:
        return "%s, but the codex command is missing or does not run" % who
    if not any(l.split()[:1] == ["hooks"] for l in (ask(["features", "list"]) or "").splitlines()):
        return "%s, but this Codex has no hooks feature, so the guard cannot run" % who
    for args in (["exec"], ["exec", "resume"]):
        words = re.findall(r"(?<![\w-])-{1,2}[A-Za-z][\w-]*", ask(args + ["--help"]) or "")
        for flag in CODEX_FLAGS:
            if flag not in words and not (flag == "-s" and args[1:]):  # `exec resume` has no -s
                return "%s, but `codex %s` has no %s flag" % (who, " ".join(args), flag)
    return None


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
    for role, old in (("Builder", "Builder model"), ("Test writer", "Builder model"),
                      ("Reviewer", "Reviewer model"), ("Pass", "Reviewer model")):
        if found.get(old) and not found.get(role):
            found[role] = "claude " + found[old]
    settings = dict(DEFAULTS)
    settings.update({k: v for k, v in found.items() if v and k in DEFAULTS})
    if not found.get("Test command"):
        raise SettingsError("AGENTS.md has no 'Test command:' under '## Loop'")
    settings["Test command"] = found["Test command"]
    for role in ROLES:
        words = settings[role].split()
        if len(words) != 2:
            raise SettingsError("AGENTS.md line '%s: %s' must be '<agent> <model>', such as 'claude sonnet'"
                                % (role, settings[role]))
        if words[0] not in AGENTS:
            raise SettingsError("AGENTS.md line '%s: %s' names an agent the kit does not support; supported: %s"
                                % (role, settings[role], ", ".join(AGENTS)))
        settings[role] = tuple(words)
    settings["Protected paths"] = [
        p.strip() for p in settings["Protected paths"].split(",") if p.strip()]
    settings["Codex writable roots"] = [
        p.strip() for p in settings["Codex writable roots"].split(",") if p.strip()]
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


def run_shell(command, cwd, timeout, record=None, patience=None):
    """Run a shell command in its own process group. Return (exit code, output); the code is None on timeout.
    With `record`, the group id is listed in that file while the command runs, so whoever
    ends the caller can also end the command. Before it starts, the command waits while memory is under
    pressure (at most `patience` seconds when set); the wait does not count against `timeout`."""
    wait_for_memory(patience)
    p = subprocess.Popen(command, shell=True, cwd=cwd, text=True, errors="replace", start_new_session=True,
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
    """(commit, output tails) the Stop hook recorded when its commands last passed for the session."""
    try:
        with open(os.path.join(project, ".loop", "passed-" + str(session_id))) as f:
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
    parent = tempfile.mkdtemp(prefix="loop-tree-", dir=os.path.realpath(tempfile.gettempdir()))
    tree = os.path.join(parent, "tree")
    try:
        git(["worktree", "add", "--detach", tree, ref], cwd=project)
        yield tree
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", tree], cwd=project, capture_output=True)
        subprocess.run(["rmdir", parent], capture_output=True)


def build_file(root, issue, kind):
    """Where a running build keeps its `step` or its `result`: .loop/builds/<issue>.<kind>."""
    return os.path.join(root, ".loop", "builds", "%s.%s" % (issue, kind))


@contextlib.contextmanager
def merge_lock(root):
    """One merge into the loop branch at a time, across processes. The lock is released when the
    holder ends, even if it dies."""
    os.makedirs(os.path.join(root, ".loop"), exist_ok=True)
    with open(os.path.join(root, ".loop", "merge.lock"), "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def event(kind, root=".", **fields):
    """Append one JSON line to .loop/events.jsonl. A step of a build also becomes its step file, for the board."""
    folder = os.path.join(root, ".loop")
    os.makedirs(folder, exist_ok=True)
    if kind == "step" and "issue" in fields and fields.get("phase", "start") == "start":
        os.makedirs(os.path.join(folder, "builds"), exist_ok=True)
        with open(build_file(root, fields["issue"], "step"), "w") as f:
            f.write(fields["step"] + (" round %s" % fields["round"] if "round" in fields else ""))
    record = dict(time=time.strftime("%Y-%m-%dT%H:%M:%S%z"), kind=kind, kit=kit_version(),
                  project=os.path.basename(os.path.abspath(root)), **fields)
    with open(os.path.join(folder, "events.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def park(issue, question, recommendation, project="."):
    """Hand an issue to the person: label needs-user, drop building, comment."""
    event("parked", project, issue=issue, reason=question)
    add_label(issue, "needs-user")
    remove_label(issue, "building")
    gh(["issue", "comment", str(issue), "--body-file", "-"], retry=False,
       input="## Needs you\n\n%s\n\nRecommended: %s\n\nReply on this issue; "
             "the loop picks up your reply.\n\n%s\n" % (question, recommendation, MARKER))


def _version_key(text):
    return tuple(int(part) for part in re.findall(r"\d+", text))


def kit_version():
    """The running kit's version, from the plugin's manifest."""
    manifest = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude-plugin", "plugin.json")
    with open(manifest, encoding="utf-8") as f:
        return json.load(f)["version"]


def kit_version_refusal(project):
    """The two refusal lines when the running kit is older than the one this clone was set up with, else None."""
    path, running = os.path.join(project, ".loop", "kit-version"), kit_version()
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        recorded = f.read().strip()
    if recorded and _version_key(running) < _version_key(recorded):
        return ("refused: this session runs kit %s, but this project was set up with kit %s\n"
                "next: restart Claude Code so it loads kit %s, then try again" % (running, recorded, recorded))
    return None


def record_kit_version(project):
    """Write the running version to .loop/kit-version. Call only after kit_version_refusal passed."""
    os.makedirs(os.path.join(project, ".loop"), exist_ok=True)
    with open(os.path.join(project, ".loop", "kit-version"), "w", encoding="utf-8") as f:
        f.write(kit_version() + "\n")
