"""Shared helpers: settings, GitHub and git calls, events, labels, trust."""
import contextlib
import contextvars
import errno
import fcntl
import json
import math
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

RETRY_WAITS = (5, 20, 60)
RATE_LIMIT_CAP = 65 * 60
TIMEOUT = 120
STDERR_LINES = 20
TRANSIENT = re.compile(
    r"HTTP 5\d\d|timed? ?out|connection (reset|refused)|no such host"
    r"|network is unreachable|unexpected EOF", re.I)
RATE_LIMITED = re.compile(r"HTTP (403|429)|rate limit", re.I)

ROLES = ("Builder", "Test writer", "Reviewer", "Pass")
AGENTS = ("claude", "codex")
CODEX_FLAGS = ("-s", "-m", "-c", "--json", "-o", "--dangerously-bypass-hook-trust")

DEFAULTS = {
    "Loop branch": "loop/main",
    "Builder": "claude sonnet",
    "Test writer": "claude sonnet",
    "Reviewer": "claude sonnet",
    "Pass": "claude sonnet",
    "Protected paths": [".github/", ".claude/", ".githooks/", "loop.json", "loop.local.json"],
    "Codex writable roots": [],
    "Codex network": False,
    "Red-team surfaces": [],
    "Idle hours": 12,
    "Max rounds": 3,
    "Full suite every": 4,
    "Session minutes": 45,
    "Test minutes": 30,
    "Check command": "",
    "Smoke command": "",
    "Test files command": "",  # {files} stands for the paths; empty means the Test command
    "Prepare command": "",  # run once in each worktree, before any test run
    "Parallel": 1,  # builds running at once
    "Sign-off": False,
    "Agent attribution": False,
}


MARKER = "<!-- lite-loop -->"  # on every comment the loop posts; replies lack it. Kept as is: comments already posted carry it


class LoopError(Exception):
    """An expected failure with a bounded diagnostic message."""


class GitHubError(LoopError):
    pass


class GitError(LoopError):
    pass


class SettingsError(LoopError):
    pass


def say(text):
    # Shell redirection with > leaves an offset that can overwrite worker log entries.
    try:
        fd = sys.stdout.fileno()
        if stat.S_ISREG(os.fstat(fd).st_mode):
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            if not flags & os.O_APPEND:
                sys.stdout.flush()
                fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_APPEND)
    except (AttributeError, OSError, ValueError):
        pass  # Captured output and pipes need no append flag.
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
_MEMORY_HELD = contextvars.ContextVar("memory_held", default=False)
_BUILD = contextvars.ContextVar("build", default=(None, None))


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


def build_count(project):
    try:
        return sum(name.endswith(".pid") for name in os.listdir(os.path.join(project, ".loop", "builds")))
    except OSError:
        return 0


def wait_for_memory(project=None, issue=None):
    """Wait at most ten minutes at critical pressure, only with more than one build running."""
    root, number = _BUILD.get()
    project = project or root or project_of(".")
    issue = issue if issue is not None else number or os.environ.get("LOOP_ISSUE")
    if _MEMORY_HELD.get() or not project or build_count(project) <= 1:
        return
    level = pressure_level()
    if level != 4:
        return
    began = time.time()
    os.makedirs(os.path.join(project, ".loop"), exist_ok=True)
    path = build_file(project, issue, "memory") if issue is not None else None
    def record(end=None):
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a") as f:
                f.write("%s%s\n" % (began, " " + str(end) if end is not None else ""))
    record()
    say("waiting for memory pressure to ease (level %d)" % level)
    try:
        while level == 4 and build_count(project) > 1:
            left = 600 - (time.time() - began)
            if left <= 0:
                line = "memory pressure did not ease in 10 minutes; starting anyway"
                say(line)
                with open(os.path.join(project, ".loop", "loop.out"), "a") as f:
                    f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + line + "\n")
                return
            sleep(min(PRESSURE_POLL, left))
            level = pressure_level()
        say("memory wait ended after %d minutes" % ((time.time() - began) // 60))
    finally:
        record(time.time())
        event("memory-wait", project, level=4, seconds=int(time.time() - began),
              **({"issue": issue} if issue is not None else {}))


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
        options = re.findall(r"^\s*(-{1,2}[A-Za-z][\w-]*(?:,\s*--[\w-]+)?)",
                             ask(args + ["--help"]) or "", re.M)
        words = re.findall(r"-{1,2}[A-Za-z][\w-]*", "\n".join(options))
        for flag in CODEX_FLAGS:
            if flag not in words and not (flag == "-s" and args[1:]):  # `exec resume` has no -s
                return "%s, but `codex %s` has no %s flag" % (who, " ".join(args), flag)
    return None


def setting_lines(text):
    inside = False
    for line in text.splitlines(keepends=True):
        if re.match(r"#{1,6}\s", line):
            inside = line.strip().lower() == "## loop"
            continue
        m = re.match(r"\s*([^:]+?):\s*(.*?)\s*$", line)
        if inside and m:
            yield line, m.group(1), m.group(2).replace("`", "").strip()


NUMERIC_SETTINGS = {"Parallel", "Idle hours", "Max rounds", "Session minutes", "Test minutes", "Full suite every"}
LIST_SETTINGS = {"Protected paths", "Codex writable roots", "Red-team surfaces"}
BOOLEAN_SETTINGS = {"Sign-off", "Agent attribution", "Codex network"}
_BUILD_SETTINGS = contextvars.ContextVar("build_settings", default=None)


@contextlib.contextmanager
def settings_environment(settings):
    """Keep one validated configuration for a build and its subprocesses."""
    token = _BUILD_SETTINGS.set(settings)
    try:
        yield
    finally:
        _BUILD_SETTINGS.reset(token)


def build_settings(root="."):
    settings = _BUILD_SETTINGS.get()
    if settings is None and os.environ.get("LOOP_BUILD_SETTINGS"):
        settings = json.loads(os.environ["LOOP_BUILD_SETTINGS"])
        for role in ROLES:
            settings[role] = tuple(settings[role])
    return settings if settings is not None else read_settings(root)


def validate_settings(found, filename, local=False):
    if not isinstance(found, dict):
        raise SettingsError("%s must contain a JSON object" % filename)
    allowed = {"Parallel", "Idle hours"} if local else set(DEFAULTS) | {"Test command"}
    for key, value in found.items():
        if key not in allowed:
            raise SettingsError("%s: unknown key '%s'" % (filename, key))
        valid = (isinstance(value, bool) if key in BOOLEAN_SETTINGS else
                 type(value) in (int, float) if key in NUMERIC_SETTINGS else
                 isinstance(value, list) and all(isinstance(p, str) for p in value)
                 if key in LIST_SETTINGS else isinstance(value, str))
        if not valid:
            raise SettingsError("%s: wrong type for '%s'" % (filename, key))
        if key in NUMERIC_SETTINGS:
            if not math.isfinite(value) or value < 0 or (
                    key in {"Parallel", "Max rounds", "Full suite every", "Test minutes"} and (value < 1 or value != int(value))):
                raise SettingsError("%s: invalid number for '%s'" % (filename, key))
    if not local and not found.get("Test command"):
        raise SettingsError("%s: missing 'Test command'" % filename)
    for role in ROLES:
        if role not in found:
            continue
        words = found[role].split()
        if len(words) != 2 or words[0] not in AGENTS:
            raise SettingsError("%s: '%s' must be '<agent> <model>'; supported agents: %s"
                                % (filename, role, ", ".join(AGENTS)))


def read_settings(root="."):
    """Read validated project settings and the machine's optional overrides."""
    settings = {k: list(v) if isinstance(v, list) else v for k, v in DEFAULTS.items()}
    for filename in ("loop.json", "loop.local.json"):
        path = os.path.join(root, filename)
        try:
            with open(path, encoding="utf-8") as f:
                found = json.load(f)
        except FileNotFoundError:
            if filename == "loop.local.json":
                continue
            raise SettingsError("%s: missing file and 'Test command'; run setup" % path)
        except (OSError, ValueError) as e:
            raise SettingsError("%s: cannot read settings: %s" % (path, e))
        validate_settings(found, path, local=filename == "loop.local.json")
        settings.update(found)
    for role in ROLES:
        settings[role] = tuple(settings[role].split())
    for key in ("Max rounds", "Parallel", "Full suite every", "Test minutes"):
        settings[key] = int(settings[key])
    return settings


# GitHub

def warn_delete_branch_on_merge(project, emit):
    """Probe once with a short timeout; this advice must not hold up startup."""
    try:
        result = gh(["api", "repos/{owner}/{repo}", "--jq", ".delete_branch_on_merge"],
                    retry=False, timeout=2, cwd=project)
        if result.strip() == "true":
            emit('warning: in Settings, General, Pull Requests, turn off '
                 '"Automatically delete head branches": merging the final pull request '
                 'deletes the loop branch.')
    except Exception:
        return


def _run_gh(args, input=None, *, timeout=None, cwd=None):
    timeout = TIMEOUT if timeout is None else timeout
    try:
        p = subprocess.run(["gh"] + list(args), input=input, text=True,
                           capture_output=True, timeout=timeout, cwd=cwd)
    except subprocess.TimeoutExpired:
        return 124, "", "gh timed out after %s seconds" % timeout
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


def gh(args, input=None, retry=True, *, timeout=None, cwd=None):
    """Run gh and return stdout. Retries 5xx and network failures, waits out
    a rate limit once, and raises GitHubError with the stderr tail otherwise.
    Pass retry=False for a write that is not safe to repeat."""
    waits, limited = list(RETRY_WAITS) if retry else [], not retry
    options = {}
    if timeout is not None:
        options["timeout"] = timeout
    if cwd is not None:
        options["cwd"] = cwd
    while True:
        code, out, err = _run_gh(args, input, **options)
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
            " ".join(args[:2]), " | ".join(lines[-STDERR_LINES:]) if lines else "exit %d" % code))


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


def issue_kind(body):
    """Read the issue's Kind line; missing or unknown kinds mean build."""
    match = re.search(r"^[ \t]*Kind:[ \t]*([^\r\n]*)", body or "", re.I | re.M)
    return "parallel" if match and match.group(1).strip().lower() == "parallel" else "build"


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
            " ".join(args[:2]), " | ".join(lines[-STDERR_LINES:]) if lines else "exit %d" % p.returncode))
    return p.stdout.rstrip("\n")


def _record(path, pid, add, token=None):
    """Add a process group id and optional ownership token to `path`, or take it off."""
    try:
        pids = open(path).read().split() if os.path.exists(path) else []
        with open(path, "w") as f:
            entry = str(pid) + (":" + token if token else "")
            f.write("".join(p + "\n" for p in [p for p in pids if p.split(":", 1)[0] != str(pid)] + [entry] * add))
    except OSError:
        pass


def project_of(cwd):
    """The project folder holding `.loop/`: LOOP_PROJECT, else the main checkout of the repository at `cwd`.
    None when git is missing or fails: paused time is then not counted."""
    if os.environ.get("LOOP_PROJECT"):
        return os.environ["LOOP_PROJECT"]
    try:
        p = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=cwd,
                           capture_output=True, text=True)
    except OSError:
        return None
    return os.path.dirname(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else None


def paused_seconds(project, since, issue=None):
    """Seconds since `since` that the loop spent paused: finished pauses are listed in `.loop/pauses`
    by `loop resume`, a pause in progress is the `.loop/paused` mark. With `issue`, include its memory
    waits from `.loop/builds/<issue>.memory`: a start alone is still waiting, a pair is finished."""
    now, total = time.time(), 0.0
    if project is None:
        return total
    spans = []
    with contextlib.suppress(OSError, ValueError):
        with open(os.path.join(project, ".loop", "pauses")) as f:
            spans = [tuple(map(float, line.split())) for line in f if line.strip()]
    with contextlib.suppress(OSError, ValueError, KeyError):
        with open(os.path.join(project, ".loop", "paused")) as f:
            spans.append((json.load(f)["since"], now))
    if issue is not None:
        waits = {}
        with contextlib.suppress(OSError, ValueError):
            with open(build_file(project, issue, "memory")) as f:
                for line in f:
                    values = list(map(float, line.split()))
                    if values:
                        waits[values[0]] = values[1] if len(values) > 1 else now
        spans.extend(waits.items())
    until = since
    for begin, end in sorted(spans):
        total += max(0.0, min(end, now) - max(begin, until))
        until = max(until, min(end, now))
    return total


def wait_limited(wait, limit, project):
    """Call `wait(timeout)` until it returns, as `wait(limit)` would, but leave paused time out of `limit`.
    The wait sleeps to the deadline without polling: a paused waiter is frozen, finds its deadline passed
    on resume and looks again. Raises subprocess.TimeoutExpired when the unpaused time passes `limit`."""
    start = time.time()
    while True:
        left = start + limit + paused_seconds(project, start) - time.time()
        if left <= 0:
            raise subprocess.TimeoutExpired("wait", limit)
        try:
            return wait(left)
        except subprocess.TimeoutExpired:
            pass


MIN_DISK_FREE = 2 * 1024 ** 3
_BUILD_TEMP = contextvars.ContextVar("build_temp", default="")


def build_env():
    path = _BUILD_TEMP.get()
    env = dict(os.environ, TMPDIR=path, TMP=path, TEMP=path, LOOP_TMPDIR=path) if path else dict(os.environ)
    if _BUILD_SETTINGS.get() is not None:
        env["LOOP_BUILD_SETTINGS"] = json.dumps(_BUILD_SETTINGS.get())
    return env


def record_session(session_id, env):
    path = env.get("LOOP_TMPDIR")
    if path and session_id and os.path.basename(session_id) == session_id:
        open(os.path.join(path, "session-" + session_id), "a").close()


@contextlib.contextmanager
def build_environment(project, issue=None):
    folder = os.path.join(os.path.dirname(os.path.abspath(project)), ".loop-worktrees")
    os.makedirs(folder, exist_ok=True)
    path = tempfile.mkdtemp(prefix="loop-build-", dir=folder)
    created = os.stat(path)
    token = _BUILD_TEMP.set(path)
    build = _BUILD.set((project, issue))
    try:
        yield
    finally:
        _BUILD_TEMP.reset(token)
        _BUILD.reset(build)
        if not os.path.islink(path) and os.path.isdir(path) and os.path.samestat(created, os.stat(path)):
            for name in os.listdir(path):
                if name.startswith("session-"):
                    for prefix in ("passed-", "stop-"):
                        with contextlib.suppress(FileNotFoundError):
                            os.remove(os.path.join(project, ".loop", prefix + name[len("session-"):]))
            shutil.rmtree(path)


def wait_for_disk(project, reason="", **fields):
    reported, recorded = False, False
    while True:
        low = [p for p in (project, build_env().get("TMPDIR") or tempfile.gettempdir())
               if shutil.disk_usage(p).free < MIN_DISK_FREE]
        if not low and (reported or not reason):
            if reported and not recorded:
                event("disk-wait", project, reason=reason, **fields)
            return
        if not reported:
            reason = reason or "less than 2 GB free on: " + ", ".join(low)
            say("waiting for disk space: " + reason)
            reported = True
        if not recorded:
            try:
                event("disk-wait", project, reason=reason, **fields)
                recorded = True
            except OSError as e:
                if e.errno != errno.ENOSPC:
                    raise
        sleep(60)


def run_shell(command, cwd, timeout, record=None):
    code, out = _run_shell(command, cwd, timeout, record)
    if code != 0 and "no space left on device" in out.lower():  # once: the phrase may be a test's own output
        wait_for_disk(os.environ.get("LOOP_PROJECT") or cwd, reason="No space left on device")
        code, out = _run_shell(command, cwd, timeout, record)
    return code, out


def _run_shell(command, cwd, timeout, record=None):
    """Run a shell command in its own process group, or in the pass worker's group.
    Return (exit code, output); the code is None on timeout outside a pass worker.
    A pass command timeout ends the worker and its commands; the supervisor reports the error.
    With `record`, the group id is listed so whoever ends the caller can also end the command.
    Pass records remain until session cleanup, including commands whose children outlive them.
    Before it starts, the command waits at critical memory
    pressure for at most ten minutes; the wait is outside `timeout`."""
    wait_for_memory(project_of(cwd))
    wait_for_disk(os.environ.get("LOOP_PROJECT") or cwd)
    # Pass commands share the worker's lifetime, including an external kill.
    pass_worker = os.environ.get("LOOP_PASS_WORKER") == str(os.getpid())
    token = os.environ.get("LOOP_GROUP_TOKEN")
    p = subprocess.Popen(command, shell=True, cwd=cwd, env=build_env(), text=True, errors="replace", start_new_session=not pass_worker,
                         preexec_fn=(lambda: _record(record, os.getpid(), True, token)) if record and os.environ.get("LOOP_PASS_GROUPS") else None,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if record:
        _record(record, p.pid, True, token)
    try:
        out, _ = wait_limited(lambda t: p.communicate(timeout=t), timeout, project_of(cwd))
        return p.returncode, out
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgrp() if pass_worker else p.pid, signal.SIGKILL)
        out, _ = p.communicate()
        return None, out
    finally:
        # Pass cleanup also needs groups whose command exited before its children.
        if record and not os.environ.get("LOOP_PASS_GROUPS"):
            _record(record, p.pid, False)


def files_command(settings, files):
    """The Test files command for these paths, or the Test command when none is set."""
    if not settings["Test files command"]:
        return settings["Test command"]
    return settings["Test files command"].replace("{files}", " ".join(shlex.quote(f) for f in files))


def check_pass_state(cwd, settings):
    """Identify a clean session check, including its worktree and selection inputs."""
    if git(["status", "--porcelain", "--", ".", ":!.loop"], cwd=cwd).strip():
        return None
    return {"cwd": os.path.realpath(cwd), "head": git(["rev-parse", "HEAD"], cwd=cwd),
            "start": os.environ.get("LOOP_START"),
            "locked": sorted(set(os.environ.get("LOOP_LOCKED", "").splitlines())),
            "settings": json.dumps(settings, sort_keys=True)}


def check_pass_path():
    runtime = os.environ.get("LOOP_TMPDIR")
    return os.path.join(runtime, "loop-check-passed.json") if runtime else None


def read_check_pass(cwd, settings):
    """Return the build's loop check output only while its clean state still matches."""
    path = check_pass_path()
    if path:
        try:
            with open(path) as f:
                record = json.load(f)
            if record["state"] and record["state"] == check_pass_state(cwd, settings):
                return record["tails"]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return None


def write_passed(project, session_id, head, tails):
    path = os.path.join(project, ".loop", "passed-" + session_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join([head] + tails) + "\n")


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


def restore_loop_branch(project, branch):
    """Restore a missing remote branch, preserving its last known commit."""
    if git(["ls-remote", "--heads", "origin", "refs/heads/" + branch], cwd=project):
        return
    git(["fetch", "--no-prune", "origin"], cwd=project)
    source = "origin/" + branch
    commit = git(["rev-parse", "--verify", "refs/remotes/" + source + "^{commit}"],
                 cwd=project, check=False)
    if not commit:
        source = "origin/" + default_branch(project)
        commit = git(["rev-parse", "--verify", "refs/remotes/" + source + "^{commit}"], cwd=project)
    git(["push", "origin", commit + ":refs/heads/" + branch], cwd=project)
    folder = os.path.join(project, ".loop")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "loop.out")
    line = "restored %s from %s at %s" % (branch, source, commit)
    with open(path, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + line + "\n")
    event("loop-branch-restored", project, branch=branch, source=source, commit=commit)


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
        token = _MEMORY_HELD.set(True)
        try:
            yield
        finally:
            _MEMORY_HELD.reset(token)


def event(kind, root=".", **fields):
    """Append one JSON line to .loop/events.jsonl. A step of a build also becomes its step file, for the board."""
    if kind in {"step", "merged", "parked"}:
        fields.update(load=os.getloadavg()[0], pressure=pressure_level())
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
    progress = {"answered": "requeued on a reply", "merged": "merged", "parked": "parked"}.get(kind)
    if (kind == "step" and fields.get("step") == "review" and fields.get("phase") == "end"
            and fields.get("outcome") not in {None, "parked", "crashed"}):
        progress = "review: " + fields["outcome"].upper()
    if progress and "issue" in fields:
        # Workers write stdout to build logs; progress also belongs in the supervisor's log.
        with open(os.path.join(folder, "loop.out"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + "#%s %s\n" % (fields["issue"], progress))


def named_test_paths(text):
    """Test paths mentioned in text, using the same definition as the merge checks."""
    import merge
    return sorted({p for p in re.findall(r"[\w./-]+\.\w+", text) if merge.is_test_file(p)})


def park(issue, question, recommendation, project="."):
    """Hand an issue to the person: label needs-user, drop building, comment."""
    rule = None
    try:
        with open(os.path.join(project, ".loop", "events.jsonl"), encoding="utf-8") as f:
            for line in f:
                try:
                    previous = json.loads(line)
                    if not isinstance(previous, dict) or previous.get("issue") != issue:
                        continue
                    kind = previous.get("kind")
                    if kind == "rule":
                        rule = previous.get("rule")
                    elif kind in {"parked", "merged", "crashed"} or (
                            kind == "step" and previous.get("phase", "start") == "start"):
                        rule = None
                except ValueError:
                    pass
    except OSError:
        pass
    event("parked", project, issue=issue, reason=question, **({"rule": rule} if rule else {}))
    add_label(issue, "needs-user")
    remove_label(issue, "building")
    warning = ("No test path was named in the question, so a yes cannot grant one.\n\n"
               if re.search(r"\b(tests?|fixtures?|locks?)\b", question, re.I)
               and not named_test_paths(question) else "")
    gh(["issue", "comment", str(issue), "--body-file", "-"], retry=False,
       input="## Needs you\n\n%s\n\nRecommended: %s\n\n%sReply on this issue; "
             "the loop picks up your reply.\n\n%s\n" % (question, recommendation, warning, MARKER))


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
