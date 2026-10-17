"""Test helpers: an in-memory GitHub and a throwaway project with a remote."""
from __future__ import annotations

import io
import os
import queue
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Optional

KIT = Path(__file__).resolve().parent.parent / "kit"
sys.path.insert(0, str(KIT / "scripts"))


def pump_events(session, events: list[str], idle_seconds: float,
                backend: str = "claude", clock_step: float = 0.75) -> tuple[str, str]:
    """Pump queued lines through a pipe while advancing a controlled clock."""
    read_fd, write_fd = os.pipe()
    finished = {"returncode": None}
    notifications = queue.Queue()
    output = _ObservedOutput(notifications)
    clock = _ManualClock()
    statuses = []
    errors = []

    class Process:
        pid = -1

        def __init__(self):
            self.stdout = os.fdopen(read_fd, "rb", buffering=0)

        def poll(self):
            return finished["returncode"]

        def wait(self):
            return finished["returncode"]

    process = Process()

    def pump():
        try:
            statuses.append(session._pump_session(
                process, output, idle_seconds, hard_seconds=10,
                backend=backend, clock=clock))
        except BaseException as error:
            errors.append(error)

    worker = threading.Thread(target=pump)
    worker.start()
    try:
        for index, event in enumerate(events):
            clock.set((index + 1) * clock_step)
            os.write(write_fd, event.encode() + b"\n")
            notifications.get(timeout=10)
            # The pump samples at startup, then checks and resets after each event.
            clock.wait_for_calls(3 + 2 * index)
        os.close(write_fd)
        write_fd = -1
        finished["returncode"] = 0
        worker.join(timeout=10)
        if worker.is_alive():
            raise AssertionError("session pump did not finish after the pipe closed")
        if errors:
            raise errors[0]
        return statuses[0], output.value()
    finally:
        if write_fd >= 0:
            os.close(write_fd)
        finished["returncode"] = 0
        if worker.is_alive():
            worker.join(timeout=10)
        if worker.is_alive():
            process.stdout.close()


class _ManualClock:
    def __init__(self):
        self.value = 0.0
        self.calls = 0
        self.condition = threading.Condition()

    def __call__(self):
        with self.condition:
            self.calls += 1
            self.condition.notify_all()
            return self.value

    def set(self, value):
        with self.condition:
            self.value = value

    def wait_for_calls(self, count):
        with self.condition:
            if not self.condition.wait_for(lambda: self.calls >= count, timeout=10):
                raise AssertionError("session pump did not sample the fake clock")


class _ObservedOutput:
    def __init__(self, notifications):
        self._buffer = io.StringIO()
        self._notifications = notifications

    def write(self, value):
        self._buffer.write(value)
        self._notifications.put(value)

    def flush(self):
        pass

    def value(self):
        return self._buffer.getvalue()


class FakeGitHub:
    """Just enough of GitHub for the gate and the run, kept in memory."""

    def __init__(self) -> None:
        self.issues: dict[int, dict] = {}
        self.notes: dict[int, list[str]] = {}
        self.prs: dict[str, dict] = {}
        self.made_labels: set[str] = set()

    def issue(self, n: int) -> dict:
        i = self.issues[n]
        return {**i, "labels": list(i["labels"])}

    def edit_body(self, n: int, body: str) -> None:
        self.issues[n]["body"] = body

    def issues_with_label(self, label: str, closed_too: bool = False) -> list[dict]:
        return [self.issue(n) for n, i in sorted(self.issues.items())
                if label in i["labels"] and (closed_too or i["state"] == "OPEN")]

    def create_issue(self, title: str, body: str, labels: list[str]) -> int:
        n = len(self.issues) + 1
        self.issues[n] = {"number": n, "title": title, "body": body,
                          "labels": list(labels), "state": "OPEN"}
        self.notes[n] = []
        return n

    def set_labels(self, n: int, add: list[str], remove: list[str]) -> None:
        labels = [x for x in self.issues[n]["labels"] if x not in remove]
        self.issues[n]["labels"] = labels + [x for x in add if x not in labels]

    def comment(self, n: int, text: str, author: str = "OWNER") -> None:
        self.notes[n].append((author, text))

    def comments(self, n: int) -> list[str]:
        import loopkit
        return [text for author, text in self.notes[n] if author in loopkit.TRUSTED]

    def close(self, n: int, reason: str) -> None:
        if self.issues[n]["state"] == "CLOSED":
            raise RuntimeError("already closed")  # be stricter than gh
        self.issues[n]["state"] = "CLOSED"

    def ensure_label(self, name: str, color: str, description: str) -> None:
        self.made_labels.add(name)

    def labels(self) -> list:
        return sorted(self.made_labels)

    def signed_in(self) -> bool:
        return True

    def create_pr(self, head: str, title: str, body: str) -> str:
        url = f"https://example.invalid/pull/{len(self.prs) + 1}"
        self.prs[head] = {"url": url, "state": "OPEN", "title": title, "body": body}
        return url

    def edit_pr(self, url: str, title: str, body: str) -> None:
        for pull_request in self.prs.values():
            if pull_request["url"] == url:
                pull_request.update(title=title, body=body)
                return
        raise RuntimeError(f"unknown pull request: {url}")

    def pr_for_branch(self, branch: str) -> Optional[dict]:
        return self.prs.get(branch)


def git(cwd: Path, *args: str) -> str:
    res = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {res.stderr}")
    return res.stdout.strip()


# A tiny judge that needs no test library: it checks habits.add and names D1, D2.
JUDGE = '''import sys
sys.path.insert(0, ".")
failed = []
def check(name, fn):
    try:
        fn()
        print("ok", name)
    except Exception as e:
        print("FAIL", name, type(e).__name__, e)
        failed.append(name)
def d1():
    import habits
    assert habits.add([], "read") == ["read"], "add should append"
def d2():
    import habits
    assert habits.add(["read"], "read") == ["read"], "no duplicates"
check("test_D1_add_appends", d1)
check("test_D2_add_skips_duplicates", d2)
sys.exit(1 if failed else 0)
'''

GOOD_CODE = '''def add(items, name):
    return items if name in items else items + [name]
'''

SPEC = """## Goal
Add a habit.

## Intent
Add a habit to the list.

Out of scope:
- Editing or deleting habits.

## Approach
Keep the public add function.

## Contract
- D1: adding a habit appends it.
- D2: adding a habit twice keeps one.

## Judge
Command: `python3 judge_add.py`
Files:
- judge_add.py
"""


class Project:
    """A throwaway project with a bare remote, a main commit and a piece branch."""

    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="loop-test-")
        base = Path(self.tmp.name)
        self.remote = base / "remote.git"
        self.root = base / "project"
        git(base, "init", "--quiet", "--bare", "-b", "main", str(self.remote))
        git(base, "init", "--quiet", "-b", "main", str(self.root))
        git(self.root, "config", "user.email", "test@example.invalid")
        git(self.root, "config", "user.name", "Test")
        git(self.root, "config", "commit.gpgsign", "false")
        (self.root / "README.md").write_text("habits\n")
        (self.root / ".gitignore").write_text(".loop/\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "--quiet", "-m", "Start")
        git(self.root, "remote", "add", "origin", str(self.remote))
        git(self.root, "push", "--quiet", "-u", "origin", "main")
        self.gh = FakeGitHub()
        self._worktrees = os.environ.get("LOOP_WORKTREES")
        os.environ["LOOP_WORKTREES"] = str(base / "build-folders")

    def piece(self, judge: str = JUDGE, spec: str = SPEC) -> int:
        import gate
        n = gate.capture(self.gh, "Add a habit", spec)
        git(self.root, "switch", "--quiet", "-c", f"piece/{n}", "main")
        (self.root / "judge_add.py").write_text(judge)
        git(self.root, "add", "judge_add.py")
        git(self.root, "commit", "--quiet", "-m", "Judge")
        git(self.root, "switch", "--quiet", "main")
        return n

    def loop_section(self, test: str, prepare: str = "") -> None:
        """Commit an AGENTS.md loop section on main and push it."""
        lines = ["# AGENTS.md", "", "## The loop", f"Test command: `{test}`"]
        if prepare:
            lines.append(f"Prepare command: `{prepare}`")
        (self.root / "AGENTS.md").write_text("\n".join(lines) + "\n")
        git(self.root, "add", "AGENTS.md")
        git(self.root, "commit", "--quiet", "-m", "Loop section")
        git(self.root, "push", "--quiet", "origin", "main")

    def folder(self, n: int) -> Path:
        """The run's build folder for a piece."""
        import run
        return run.worktree_home(self.root) / f"piece-{n}"

    def close(self) -> None:
        if self._worktrees is None:
            os.environ.pop("LOOP_WORKTREES", None)
        else:
            os.environ["LOOP_WORKTREES"] = self._worktrees
        self.tmp.cleanup()
