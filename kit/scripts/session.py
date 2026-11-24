"""Run one role session with claude -p and return its reply."""
import contextlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

import common

TEST_TIMEOUT = 1800
LIMIT = re.compile(r"usage limit|limit reached", re.I)
HOOKS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "hooks"))

SWEPT = {}  # issue number -> Docker leftovers removed after its sessions, for the build note
DOCKER = (("container", ["ps", "-a", "-q"]), ("network", ["network", "ls", "-q"]),
          ("volume", ["volume", "ls", "-q"]), ("image", ["images", "-q"]))
OWNER = '{{index .Config.Labels "com.docker.compose.project.working_dir"}}\n{{range .Mounts}}{{.Source}}\n{{end}}'

class SessionError(common.LoopError):
    pass


def docker(args):
    """Output lines of a docker command, or None when docker is missing or fails."""
    try:
        p = subprocess.run(["docker"] + args, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return [l for l in p.stdout.splitlines() if l] if p.returncode == 0 else None


def docker_state():
    """Containers (also exited), networks, volumes, images now; None without a working docker."""
    return {k: set(docker(a) or ()) for k, a in DOCKER} if docker(DOCKER[0][1]) is not None else None


def owned(container, cwd):
    """True when the container's compose working directory or a bind-mount source is under cwd."""
    return any(line == r or line.startswith(r + os.sep) for line in docker(["inspect", "-f", OWNER, container]) or ()
               for r in {os.path.abspath(cwd), os.path.realpath(cwd)})


def sweep(before, cwd):
    """Remove new containers that belong to the worktree; only list anything else new. Never raises."""
    after, lines = docker_state(), []
    for kind, _ in DOCKER if before and after else ():
        for name in sorted(after[kind] - before[kind]):
            mine = kind == "container" and owned(name, cwd)
            done = ("could not remove" if docker(["rm", "-f", name]) is None else "removed") if mine else "new"
            lines.append("%s %s %s%s" % (done, kind, name, "" if mine else " (kept, not removed)"))
    return lines


def reap(pgid):
    """Kill what is left in the session's process group; return a line per process."""
    ps = subprocess.run(["ps", "-A", "-o", "pgid=,pid=,command="], capture_output=True, text=True).stdout
    left = ["left running, killed: " + l.split(None, 1)[1].strip() for l in ps.splitlines() if l.split()[:1] == [str(pgid)]]
    with contextlib.suppress(OSError):
        os.killpg(pgid, signal.SIGKILL)
    return left


def age(pid):
    """(process group, seconds since start) of a live process, else None."""
    out = subprocess.run(["ps", "-p", str(pid), "-o", "pgid=,etime="], capture_output=True, text=True).stdout.split()
    try:
        days, _, clock = out[1].rpartition("-")
        secs = [int(x) for x in clock.split(":")]
        return int(out[0]), sum(v * m for v, m in zip(reversed(secs), (1, 60, 3600))) + 86400 * int(days or 0)
    except (IndexError, ValueError):
        return None


def reap_groups(path, since):
    """Kill the process groups a Stop hook listed in `path` and still left running; return a line per process.
    Marked groups need a surviving member with the inherited ownership token.
    Older records require a live leader that started after `since`."""
    try:
        with open(path) as f:
            groups = [g.partition(":") for g in f.read().split()]
        groups = [(int(g), token) for g, _, token in groups]
    except (OSError, ValueError):
        return []
    marked = any(token for _, token in groups)
    # Inspect environments only to verify ownership; never include them in cleanup logs.
    rows = subprocess.run(["ps", "eww", "-A", "-o", "pgid=,command="],
                          capture_output=True, text=True).stdout.splitlines() if marked else []
    mine = []
    for g, token in groups:
        if g <= 1 or g == os.getpgrp():
            continue
        if token:
            owned = any(row.split()[:1] == [str(g)] and "LOOP_GROUP_TOKEN=" + token in row.split()[1:]
                        for row in rows)
        else:
            a = age(g)
            owned = a and a[0] == g and a[1] <= time.time() - since + 2
        if owned:
            mine.append(g)
    return [line for g in mine for line in reap(g)]


def _wait_seconds(text):
    """Seconds until the reset named in a usage-limit message, else 30 minutes."""
    m = re.search(r"\|\s*(\d{9,11})\b", text)
    wait = int(m.group(1)) - time.time() if m else 1800
    return int(min(max(wait, 60), 6 * 3600))


def _exec(argv, prompt, cwd, env, log, role, issue, limit):
    before, began = docker_state(), time.time()
    registry = env.get("LOOP_PASS_GROUPS")
    handle, groups = tempfile.mkstemp(prefix="pass-hooks-" if registry else "loop-groups-",
                                    dir=os.path.dirname(registry) if registry else env.get("TMPDIR"))
    os.close(handle)
    token = uuid.uuid4().hex if registry else None
    env = dict(env, LOOP_GROUPS=groups, **({"LOOP_GROUP_TOKEN": token} if token else {}))
    project_of_cwd = env.get("LOOP_PROJECT") or common.project_of(cwd)
    # files, not pipes: a leftover child that holds a pipe open must not block the wait
    with tempfile.TemporaryFile("w+", dir=env.get("TMPDIR")) as fin, \
            tempfile.TemporaryFile("w+", dir=env.get("TMPDIR")) as fout, \
            tempfile.TemporaryFile("w+", dir=env.get("TMPDIR")) as ferr:
        fin.write(prompt)
        fin.seek(0)
        background = sys.platform == "darwin" and shutil.which("taskpolicy")
        launch = [background, "-b"] + argv if background else argv
        def child_setup():
            if registry:
                common._record(registry, os.getpid(), True, token)
            if not background:
                with contextlib.suppress(OSError):
                    os.nice(10)
        p = subprocess.Popen(launch, cwd=cwd, env=env, text=True, start_new_session=True,
                             preexec_fn=child_setup,
                             stdin=fin, stdout=fout, stderr=ferr)
        try:
            common.wait_limited(p.wait, limit, project_of_cwd)
            problem = None
        except subprocess.TimeoutExpired:
            problem = "%s session timed out after %g minutes" % (role, limit / 60)
        left = reap(p.pid) + reap_groups(groups, began)
        with contextlib.suppress(OSError):
            os.remove(groups)
        p.wait()
        if registry:
            common._record(registry, p.pid, False)
        out, err = (f.seek(0) or f.read() for f in (fout, ferr))
    swept = sweep(before, cwd)
    SWEPT.setdefault(issue, []).extend(swept)
    with open(log, "a", encoding="utf-8") as f:
        f.write("--- %s\n%s\n--- stderr\n%s\n" % (" ".join(argv[:3]), out, err)
                + "".join("--- cleanup: %s\n" % l for l in left + swept))
    if problem:
        raise SessionError(problem)
    return out, err, p.returncode


def _codex_hooks():
    """The same guard and stop check as a Claude session, as a TOML inline table for `-c hooks=...`."""
    def hook(name, timeout=""):
        command = json.dumps("python3 " + shlex.quote(os.path.join(HOOKS, name)))
        return '{type = "command", command = %s%s}' % (command, ", timeout = %d" % timeout if timeout else "")
    return ('{PreToolUse = [{matcher = "Bash|apply_patch", hooks = [%s]}], '
            'Stop = [{hooks = [%s]}]}' % (hook("guard.py"), hook("stop.py", TEST_TIMEOUT)))


def codex_sandbox_config(cwd, env, settings):
    """Sandbox configuration shared by sessions and the startup probe."""
    common_dir = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=cwd,
                                capture_output=True, text=True).stdout.strip()
    # a worktree's .git points into the main checkout, so its commits need that folder writable;
    # build tools also write to the temp and cache folders, and to any the project names
    candidates = [common_dir, env.get("TMPDIR", "")]
    if sys.platform == "darwin":
        for name in ("DARWIN_USER_TEMP_DIR", "DARWIN_USER_CACHE_DIR"):
            with contextlib.suppress(OSError):
                candidates.append(subprocess.run(["getconf", name], capture_output=True, text=True).stdout.strip())
    candidates += [os.path.expanduser(p) for p in settings["Codex writable roots"]]
    folders = []
    for path in candidates:
        path = os.path.realpath(path) if path else ""
        if os.path.isdir(path) and path not in folders:
            folders.append(path)
    return ["-c", 'sandbox_mode="workspace-write"',
            "-c", "sandbox_workspace_write.writable_roots=" + json.dumps(folders),
            "-c", "sandbox_workspace_write.network_access=" + str(settings.get("Codex network", False)).lower()]


def sandbox_refusal(text):
    """Whether a diagnostic reports a sandbox permission refusal."""
    return bool(re.search(r"sandbox", text, re.I) and re.search(
        r"operation not permitted|permission denied|sandbox[^\n]*(?:blocked|refused|denied)", text, re.I))


def codex_probe(project, settings):
    """Check the test program and worktree writes without running project tests."""
    if not any(settings.get(role, ("claude",))[0] == "codex" for role in common.ROLES):
        return None
    program = shlex.split(common.files_command(settings, []))[0]
    write = ('import os, tempfile\n'
             'try:\n'
             '    fd, path = tempfile.mkstemp(prefix=".loop-probe-", dir=".")\n'
             '    os.close(fd)\n'
             '    os.remove(path)\n'
             'except OSError as error:\n'
             '    raise SystemExit("sandbox: worktree write denied: " + str(error))\n')
    command = ('import subprocess, sys\n'
               'try:\n'
               '    p = subprocess.run([sys.argv[1], "--version"], capture_output=True, text=True)\n'
               'except OSError as error:\n'
               '    raise SystemExit("sandbox: test program refused: " + str(error))\n'
               'sys.stdout.write(p.stdout)\n'
               'sys.stderr.write(p.stderr)\n'
               'python = sys.argv[1] if (p.stdout + p.stderr).startswith("Python ") else sys.executable\n'
               'check = subprocess.run([python, "-c", sys.argv[2]])\n'
               'sys.exit(check.returncode or p.returncode)\n')
    env = common.build_env()
    try:
        p = subprocess.run(["codex", "sandbox"] + codex_sandbox_config(project, env, settings)
                           + ["--", sys.executable, "-c", command, program, write], cwd=project, env=env,
                           capture_output=True, text=True, timeout=TEST_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as error:
        return "Codex sandbox probe failed: %s" % error
    output = p.stdout + p.stderr
    if p.returncode and sandbox_refusal(output):
        return "Codex sandbox refused the test command:\n" + "\n".join(output.splitlines()[-60:])
    return None


def _codex(role, prompt, cwd, model, env, log, issue, resume, limit, record):
    """One `codex exec` session, or `codex exec resume`; return (reply text, session id)."""
    config = codex_sandbox_config(cwd, env, common.build_settings(cwd))
    handle, last = tempfile.mkstemp(prefix="loop-codex-", dir=env.get("TMPDIR"))
    os.close(handle)
    def argv(resume):
        return (["codex", "exec"] + (["resume", resume] if resume else ["-s", "workspace-write"])
                + ["-m", model] + config
                + ["-c", "hooks=" + _codex_hooks(), "--dangerously-bypass-hook-trust", "--json", "-o", last, "-"])
    try:
        while True:
            common.wait_for_memory(project=env["LOOP_PROJECT"], issue=issue)
            out, err, code = _exec(argv(resume), prompt, cwd, env, log, role, issue, limit)
            events = []
            for line in out.splitlines():
                with contextlib.suppress(ValueError):
                    event = json.loads(line)
                    if isinstance(event, dict):
                        events.append(event)
            thread = next((e.get("thread_id") for e in events if e.get("type") == "thread.started"), None) or resume
            turns = [e for e in events if e.get("type") == "turn.completed"]
            counts = {}
            for field in ("input_tokens", "cached_input_tokens", "output_tokens"):
                values = [e["usage"][field] for e in turns if isinstance(e.get("usage"), dict)
                          and isinstance(e["usage"].get(field), (int, float))]
                if values:
                    counts[field] = sum(values)
            record(turns=len(turns), **counts)
            common.record_session(thread, env)
            with open(last, encoding="utf-8") as f:
                text = f.read()
            if not text:
                text = next((str(e.get("item", {}).get("text") or "") for e in reversed(events)
                             if e.get("type") == "item.completed"
                             and e.get("item", {}).get("type") == "agent_message"), "")
            problem = "\n".join(str(e.get("message") or "") for e in events if e.get("type") == "error") or err
            if code and LIMIT.search(problem + text):
                wait = _wait_seconds(problem + text)
                common.say("%s session hit the Codex usage limit; waiting %d minutes, "
                      "then resuming" % (role, wait // 60))
                common.sleep(wait)
                resume = thread or resume
                continue
            if code or not thread:
                lines = problem.strip().splitlines()
                raise SessionError("%s session failed (exit %d): %s" % (
                    role, code, lines[-1] if lines else "no output"))
            return text, thread
    finally:
        with contextlib.suppress(OSError):
            os.remove(last)


def run(role, prompt, cwd, model, project, issue, resume=None, locked=(), start="", allowed=(), agent="claude"):
    """Run `agent` (claude or codex) as `role` in `cwd`. Return (reply text, session id)."""
    settings = common.build_settings(project)
    env = dict(common.build_env(), LOOP_ROLE=role, LOOP_LOCKED="\n".join(locked), LOOP_ALLOWED="\n".join(allowed),
               LOOP_TEST_COMMAND=settings["Test command"], LOOP_TEST_FILES_COMMAND=settings["Test files command"],
               LOOP_PROTECTED=",".join(settings["Protected paths"]),
               LOOP_LOOP_BRANCH=settings["Loop branch"], LOOP_DEFAULT_BRANCH=common.default_branch(project),
               LOOP_PROJECT=project, LOOP_ISSUE=str(issue), LOOP_START=start)

    logs = os.path.join(project, ".loop", "logs")
    os.makedirs(logs, exist_ok=True)
    prefix = "%s-%s-" % (issue, role)
    n = sum(1 for f in os.listdir(logs) if f.startswith(prefix)) + 1
    log = os.path.join(logs, "%s%d.log" % (prefix, n))
    def record(**counts):
        common.event("session", project, issue=issue, role=role, agent=agent, model=model, **counts)
    if agent == "codex":
        env["LOOP_AGENT"] = "codex"
        return _codex(role, prompt, cwd, model, env, log, issue, resume, settings["Session minutes"] * 60, record)

    def hook(name, **more):
        return {"type": "command", "command": "python3 " + shlex.quote(
            os.path.join(HOOKS, name)), **more}
    argv = ["claude", "-p", "--output-format", "json", "--permission-mode", "auto",
            "--model", model, "--setting-sources", "project", "--strict-mcp-config",
            "--settings", json.dumps({"hooks": {
                "PreToolUse": [{"matcher": "*", "hooks": [hook("guard.py")]}],
                "Stop": [{"hooks": [hook("stop.py", timeout=TEST_TIMEOUT)]}]}})]
    while True:
        common.wait_for_memory(project=project, issue=issue)
        out, err, code = _exec(argv + (["--resume", resume] if resume else []),
                               prompt, cwd, env, log, role, issue, settings["Session minutes"] * 60)
        try:
            data = json.loads(out)
        except ValueError:
            data = None
        data = data if isinstance(data, dict) else None
        usage = (data or {}).get("usage") or {}
        counts = {field: usage[source] for field, source in (
            ("input_tokens", "input_tokens"), ("cached_input_tokens", "cache_read_input_tokens"),
            ("output_tokens", "output_tokens")) if isinstance(usage, dict) and source in usage}
        if data and "num_turns" in data:
            counts["turns"] = data["num_turns"]
        record(**counts)
        common.record_session((data or {}).get("session_id"), env)
        text = str(data.get("result") or "") if data else out + err
        if LIMIT.search(text) and (not data or data.get("is_error") or code):
            wait = _wait_seconds(text)
            common.say("%s session hit the Claude usage limit; waiting %d minutes, "
                  "then resuming" % (role, wait // 60))
            common.sleep(wait)
            resume = (data or {}).get("session_id") or resume
            continue
        if not data:
            lines = err.strip().splitlines()
            raise SessionError("%s session gave no JSON result (exit %d): %s" % (
                role, code, lines[-1] if lines else "no output"))
        if data.get("is_error") or code:
            raise SessionError("%s session failed: %s" % (
                role, (text.strip().splitlines() or ["exit %d" % code])[0]))
        return text, data.get("session_id")
