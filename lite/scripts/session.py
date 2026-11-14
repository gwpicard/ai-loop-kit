"""Run one role session with claude -p and return its reply."""
import contextlib
import json
import os
import re
import shlex
import signal
import subprocess
import tempfile
import time

import common

TIMEOUT = 45 * 60
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


def _wait_seconds(text):
    """Seconds until the reset named in a usage-limit message, else 30 minutes."""
    m = re.search(r"\|\s*(\d{9,11})\b", text)
    wait = int(m.group(1)) - time.time() if m else 1800
    return int(min(max(wait, 60), 6 * 3600))


def _exec(argv, prompt, cwd, env, log, role, issue):
    before = docker_state()
    # files, not pipes: a leftover child that holds a pipe open must not block the wait
    with tempfile.TemporaryFile("w+") as fin, tempfile.TemporaryFile("w+") as fout, tempfile.TemporaryFile("w+") as ferr:
        fin.write(prompt)
        fin.seek(0)
        p = subprocess.Popen(argv, cwd=cwd, env=env, text=True, start_new_session=True,
                             stdin=fin, stdout=fout, stderr=ferr)
        try:
            p.wait(timeout=TIMEOUT)
            problem = None
        except subprocess.TimeoutExpired:
            problem = "%s session timed out after %d minutes" % (role, TIMEOUT // 60)
        left = reap(p.pid)
        p.wait()
        out, err = (f.seek(0) or f.read() for f in (fout, ferr))
    swept = sweep(before, cwd)
    SWEPT.setdefault(issue, []).extend(swept)
    with open(log, "a", encoding="utf-8") as f:
        f.write("--- %s\n%s\n--- stderr\n%s\n" % (" ".join(argv[:3]), out, err)
                + "".join("--- cleanup: %s\n" % l for l in left + swept))
    if problem:
        raise SessionError(problem)
    return out, err, p.returncode


def run(role, prompt, cwd, model, project, issue, resume=None, locked=(), start=""):
    """Run claude -p as `role` in `cwd`. Return (reply text, session id)."""
    settings = common.read_settings(project)
    default = common.git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
                         cwd=project, check=False).replace("origin/", "", 1) or "main"
    env = dict(os.environ, LITE_ROLE=role, LITE_LOCKED="\n".join(locked),
               LITE_LOOP_BRANCH=settings["Loop branch"], LITE_DEFAULT_BRANCH=default,
               LITE_PROJECT=project, LITE_START=start)

    def hook(name, **more):
        return {"type": "command", "command": "python3 " + shlex.quote(
            os.path.join(HOOKS, name)), **more}
    argv = ["claude", "-p", "--output-format", "json", "--permission-mode", "auto",
            "--model", model, "--setting-sources", "project", "--strict-mcp-config",
            "--settings", json.dumps({"hooks": {
                "PreToolUse": [{"matcher": "*", "hooks": [hook("guard.py")]}],
                "Stop": [{"hooks": [hook("stop.py", timeout=TEST_TIMEOUT)]}]}})]
    logs = os.path.join(project, ".lite", "logs")
    os.makedirs(logs, exist_ok=True)
    prefix = "%s-%s-" % (issue, role)
    n = sum(1 for f in os.listdir(logs) if f.startswith(prefix)) + 1
    log = os.path.join(logs, "%s%d.log" % (prefix, n))
    while True:
        out, err, code = _exec(argv + (["--resume", resume] if resume else []),
                               prompt, cwd, env, log, role, issue)
        try:
            data = json.loads(out)
        except ValueError:
            data = None
        data = data if isinstance(data, dict) else None
        text = str(data.get("result") or "") if data else out + err
        if LIMIT.search(text) and (not data or data.get("is_error") or code):
            wait = _wait_seconds(text)
            print("%s session hit the Claude usage limit; waiting %d minutes, "
                  "then resuming" % (role, wait // 60), flush=True)
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
