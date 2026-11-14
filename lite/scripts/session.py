"""Run one role session with claude -p and return its reply."""
import json
import os
import re
import shlex
import signal
import subprocess
import time

import common

TIMEOUT = 45 * 60
TEST_TIMEOUT = 1800
LIMIT = re.compile(r"usage limit|limit reached", re.I)
HOOKS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "hooks"))


class SessionError(common.LoopError):
    pass


def _wait_seconds(text):
    """Seconds until the reset named in a usage-limit message, else 30 minutes."""
    m = re.search(r"\|\s*(\d{9,11})\b", text)
    wait = int(m.group(1)) - time.time() if m else 1800
    return int(min(max(wait, 60), 6 * 3600))


def _exec(argv, prompt, cwd, env, log, role):
    p = subprocess.Popen(argv, cwd=cwd, env=env, text=True, start_new_session=True,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    try:
        out, err = p.communicate(prompt, timeout=TIMEOUT)
        problem = None
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        out, err = p.communicate()
        problem = "%s session timed out after %d minutes" % (role, TIMEOUT // 60)
    with open(log, "a", encoding="utf-8") as f:
        f.write("--- %s\n%s\n--- stderr\n%s\n" % (" ".join(argv[:3]), out, err))
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
                               prompt, cwd, env, log, role)
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
