"""Shared helpers: settings, GitHub and git calls, events, labels, trust."""
import json
import os
import re
import subprocess
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


# Events

def event(kind, root=".", **fields):
    """Append one JSON line to .lite/events.jsonl."""
    folder = os.path.join(root, ".lite")
    os.makedirs(folder, exist_ok=True)
    record = dict(time=time.strftime("%Y-%m-%dT%H:%M:%S%z"), kind=kind, **fields)
    with open(os.path.join(folder, "events.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


# Parking

def park(issue, question, recommendation):
    """Hand an issue to the person: label needs-user, drop building, comment."""
    add_label(issue, "needs-user")
    remove_label(issue, "building")
    gh(["issue", "comment", str(issue), "--body-file", "-"], retry=False,
       input="## Needs you\n\n%s\n\nRecommended: %s\n\nReply on this issue; "
             "the loop picks up your reply.\n\n%s\n" % (question, recommendation, MARKER))
