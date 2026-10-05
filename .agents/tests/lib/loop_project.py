"""loop_project.py: a throwaway founded project for the build loop's rehearsals.

builder-status-rehearsal.sh, stop-hook.sh, attempt-note-rehearsal.sh and
failure-recovery.sh each need the same thing: a Git project laid out the way
founding leaves one, with the gate and the scripts beside it in .agents/tools/,
a bare repository standing in for its remote, an acceptance branch holding one
check, and the replay harness's stand-in for the GitHub CLI. Nothing here
reaches the network.

A rehearsal imports this file by path, makes a Lab, and asks it for projects.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

sys.dont_write_bytecode = True

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FOUNDATION = os.path.join(ROOT, ".agents", "skills", "setup-ai-build-kit", "templates",
                          "foundation")
SECTION = os.path.join(ROOT, ".agents", "skills", "section-builder", "scripts")
IMPLEMENT = os.path.join(ROOT, ".agents", "skills", "implement", "scripts")
FAKE = os.path.join(ROOT, ".agents", "tests", "replay", "fake-github")
RUN = os.path.join(IMPLEMENT, "run.py")
NOTE = os.path.join(IMPLEMENT, "attempt-note.py")
RECOVERY = os.path.join(IMPLEMENT, "recovery.py")

AGENTS = ("# AGENTS.md\n\n## Stack, and how to run and check it\n\n"
          "Test command: python3 -m pytest -q -p no:cacheprovider\n")
GITIGNORE = ("__pycache__/\nnode_modules/\n.env\n.agents/pieces/\n.agents/runs/\n"
             ".agents/worktrees/\n.agents/recovery/\n.agents/tmp/\n")
AREAS = ("# Working rules\n\n## Areas\n\n- billing: app/billing\n- tests: tests\n"
         "- project records: docs\n- kit tools: .agents/tools\n")

# The acceptance check fails on its assertion until the refund returns 10.
REFUND_CHECK = ("import importlib\n\n\ndef test_refund():\n    try:\n"
                "        module = importlib.import_module('app.billing.refund')\n"
                "    except ImportError:\n        module = None\n"
                "    assert module is not None and module.refund() == 10\n")
REFUND_DONE = "def refund():\n    return 10\n"
REFUND_WRONG = "def refund():\n    return 3\n"

READY = ("## Readiness\n2026-10-05, checked by a session that did not shape it: Ready\n"
         "- NOTE 3: the totals are rounded.\n")


def piece_body(loop: str = "Loop module: build\nAcceptance branch: spec/12-refunds",
               works: str = "A refund returns the whole amount. Check: tests/test_refund.py",
               boundary: str = "billing, tests", reaches: str = "none") -> str:
    return ("## So that\nA shop owner can refund an order.\n\n"
            "## Done when\n### Works\n- %s\n\n"
            "## Loop\n%s\n\n"
            "## Reach\nBoundary: %s\nReaches: %s\n\n"
            "<details><summary>Under the hood</summary>\n\nBuild the refund.\n\n</details>\n\n"
            "%s" % (works, loop, boundary, reaches, READY))


class Lab:
    """One rehearsal's scratch folder, its stand-in GitHub and its seed project."""

    def __init__(self, name: str) -> None:
        self.work = tempfile.mkdtemp(prefix=name + "-")
        self.state = os.path.join(self.work, "gh-state.json")
        self.log = os.path.join(self.work, "gh.log")
        self.failures: list[str] = []
        self.copies = 0
        bin_folder = os.path.join(self.work, "bin")
        os.makedirs(bin_folder)
        # A builder is never a model session the run script started. Stand-ins
        # for the coding agents' command lines log any call, so a rehearsal can
        # show none was made.
        self.model_log = os.path.join(self.work, "model-calls.log")
        for tool in ("claude", "codex", "gemini", "cursor-agent"):
            path = os.path.join(bin_folder, tool)
            with open(path, "w") as handle:
                handle.write("#!/bin/sh\necho \"%s $*\" >> \"%s\"\nexit 1\n"
                             % (tool, self.model_log))
            os.chmod(path, 0o755)
        env = dict(os.environ, GIT_AUTHOR_NAME="R", GIT_AUTHOR_EMAIL="r@example.invalid",
                   GIT_COMMITTER_NAME="R", GIT_COMMITTER_EMAIL="r@example.invalid",
                   FAKE_GH_STATE=self.state, FAKE_GH_LOG=self.log,
                   PYTHONDONTWRITEBYTECODE="1")
        env.pop("CLAUDE_PROJECT_DIR", None)
        paths = [FAKE, bin_folder]
        if subprocess.run([sys.executable, "-m", "pytest", "--version"], capture_output=True,
                          env=env).returncode != 0:
            print("  pytest is not here, installing it into a throwaway environment")
            venv = os.path.join(self.work, "venv")
            subprocess.run([sys.executable, "-m", "venv", venv], check=True)
            subprocess.run([os.path.join(venv, "bin", "pip"), "install", "--quiet", "pytest"],
                           check=True)
            paths.append(os.path.join(venv, "bin"))
        env["PATH"] = os.pathsep.join(paths + [env.get("PATH", "")])
        self.env = env
        self.seed = self.make_seed()

    # --- reporting -------------------------------------------------------------

    def expect(self, condition: bool, message: str, detail: str = "") -> None:
        if condition:
            print("ok: " + message)
        else:
            self.failures.append(message)
            print("FAIL: " + message + ((" -- " + detail) if detail else ""), file=sys.stderr)

    def finish(self, name: str) -> None:
        shutil.rmtree(self.work, ignore_errors=True)
        if self.failures:
            print("%s: %d check(s) failed" % (name, len(self.failures)), file=sys.stderr)
            sys.exit(1)
        print("%s: every check passed" % name)

    # --- Git and files ---------------------------------------------------------

    def git(self, repo: str, *args: str, check: bool = True) -> str:
        done = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                              env=self.env)
        if check and done.returncode != 0:
            raise SystemExit("git %s failed: %s" % (" ".join(args), done.stderr))
        return done.stdout.strip()

    @staticmethod
    def write(repo: str, files: dict[str, str]) -> None:
        for path, text in files.items():
            full = os.path.join(repo, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w") as handle:
                handle.write(text)

    def commit(self, repo: str, files: dict[str, str], message: str = "work") -> str:
        self.write(repo, files)
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", message)
        return self.git(repo, "rev-parse", "HEAD")

    def make_seed(self) -> str:
        """origin/main holds the first upload with the kit's tools beside the
        gate, and spec/12-refunds holds the check, checked out here."""
        repo = os.path.join(self.work, "seed")
        remote = os.path.join(self.work, "seed.git")
        os.makedirs(repo)
        self.git(repo, "init", "-q", "-b", "main")
        files = {"README.md": "A shop.\n", "AGENTS.md": AGENTS, ".gitignore": GITIGNORE,
                 "docs/working-rules.md": AREAS,
                 "app/__init__.py": "", "app/billing/__init__.py": "",
                 "app/billing/refund.py": "def refund():\n    return 0\n",
                 "tests/test_orders.py": "def test_orders():\n    assert True\n"}
        self.write(repo, files)
        tools = os.path.join(repo, ".agents", "tools")
        os.makedirs(tools)
        for source in (os.path.join(FOUNDATION, "gate.py"), os.path.join(FOUNDATION, "area-map.py"),
                       os.path.join(SECTION, "bar-guard.sh"), os.path.join(SECTION, "test-guard.sh")):
            shutil.copy(source, tools)
        # The ready-gate lint has its own rehearsal. Here it passes, but the gate
        # still reads its test-command reader and runner reports through it.
        with open(os.path.join(FOUNDATION, "ready-lint.py")) as handle:
            lint = handle.read()
        command = 'if __name__ == "__main__":\n    sys.exit(main(sys.argv[1:]))'
        if command not in lint:
            raise SystemExit("the ready-gate lint no longer ends with its command line")
        with open(os.path.join(tools, "ready-lint.py"), "w") as handle:
            handle.write(lint.replace(command, 'if __name__ == "__main__":\n'
                                               '    print("Ready-gate lint: no gaps.")'))
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", "first upload")
        subprocess.run(["git", "init", "-q", "--bare", remote], check=True)
        self.git(repo, "remote", "add", "origin", remote)
        self.git(repo, "push", "-q", "origin", "main")
        self.git(repo, "checkout", "-q", "-b", "spec/12-refunds")
        self.commit(repo, {"tests/test_refund.py": REFUND_CHECK}, "the check")
        self.git(repo, "push", "-q", "origin", "spec/12-refunds")
        self.git(repo, "fetch", "-q", "origin")
        return repo

    def project(self) -> str:
        """A copy of the seed with a bare remote of its own."""
        self.copies += 1
        repo = os.path.join(self.work, "project-%d" % self.copies)
        remote = repo + ".git"
        shutil.copytree(self.seed, repo, symlinks=True)
        shutil.copytree(self.seed + ".git", remote, symlinks=True)
        self.git(repo, "remote", "set-url", "origin", remote)
        return repo

    def remote_tip(self, repo: str, branch: str) -> str:
        url = self.git(repo, "remote", "get-url", "origin")
        out = self.git(repo, "ls-remote", url, "refs/heads/" + branch, check=False)
        return out.split()[0] if out else ""

    # --- the stand-in GitHub ---------------------------------------------------

    def fresh(self, issues: list[dict[str, Any]], faults: dict[str, Any] | None = None) -> None:
        state: dict[str, Any] = {"repo": "rehearsal/project", "next": 900, "issues": issues,
                                 "pull_requests": []}
        if faults:
            state["faults"] = faults
        with open(self.state, "w") as handle:
            json.dump(state, handle)
        if os.path.exists(self.log):
            os.remove(self.log)

    @staticmethod
    def issue(number: int, labels: list[str], body: str) -> dict[str, Any]:
        return {"number": number, "title": "Refunds %d" % number, "body": body,
                "state": "open", "labels": list(labels), "assignees": [], "blocked_by": [],
                "sub_issues": [], "comments": []}

    def load(self) -> dict[str, Any]:
        with open(self.state) as handle:
            data: dict[str, Any] = json.load(handle)
        return data

    def save(self, data: dict[str, Any]) -> None:
        with open(self.state, "w") as handle:
            json.dump(data, handle)

    def find(self, number: int) -> dict[str, Any]:
        found: dict[str, Any] = next(i for i in self.load()["issues"] if i["number"] == number)
        return found

    def labels_of(self, number: int) -> list[str]:
        return sorted(self.find(number)["labels"])

    def set_faults(self, faults: dict[str, Any]) -> None:
        data = self.load()
        data["faults"] = faults
        self.save(data)

    def calls(self) -> list[str]:
        if not os.path.exists(self.log):
            return []
        with open(self.log) as handle:
            return [line.split("\t", 1)[1].strip() for line in handle
                    if line.startswith("CALL\t")]

    def model_calls(self) -> list[str]:
        if not os.path.exists(self.model_log):
            return []
        with open(self.model_log) as handle:
            return [line.strip() for line in handle if line.strip()]

    # --- running the kit's scripts --------------------------------------------

    def run(self, cwd: str, *args: str, stdin: str | None = None,
            env: dict[str, str] | None = None) -> tuple[int, str, str]:
        done = subprocess.run(list(args), cwd=cwd, env=env or self.env, input=stdin,
                              capture_output=True, text=True)
        return done.returncode, done.stdout, done.stderr

    def gate(self, repo: str, *args: str, stdin: str | None = None) -> tuple[int, str, str]:
        return self.run(repo, sys.executable, os.path.join(repo, ".agents", "tools", "gate.py"),
                        *args, stdin=stdin)

    def runpy(self, repo: str, *args: str) -> tuple[int, str, str]:
        return self.run(repo, sys.executable, RUN, *args)

    def ready_piece(self, repo: str, number: int = 12, body: str | None = None,
                    loop_label: str = "loop:build") -> None:
        """The piece made ready through the gate, which posts its contract hash."""
        labels = ["state:shaping", "shaping:check", "type:feature", loop_label]
        self.fresh([self.issue(number, labels, body or piece_body())])
        code, out, err = self.gate(repo, "move", str(number), "ready")
        if code != 0:
            raise SystemExit("the piece could not be made ready: %s %s" % (out, err))

    # --- reading a run ---------------------------------------------------------

    @staticmethod
    def request_of(out: str) -> dict[str, Any] | None:
        """The start request run.py printed, from its `request:` line."""
        for line in out.splitlines():
            if line.startswith("request: "):
                value: dict[str, Any] = json.loads(line[len("request: "):])
                return value
        return None

    @staticmethod
    def run_name_of(out: str) -> str:
        match = re.search(r"\brun (solo-\d+-\d{8}-\d{6})\b", out)
        return match.group(1) if match else ""

    @staticmethod
    def record(repo: str, run: str) -> dict[str, Any]:
        with open(os.path.join(repo, ".agents", "runs", run, "run.json")) as handle:
            data: dict[str, Any] = json.load(handle)
        return data

    def write_result(self, repo: str, request: dict[str, Any], result: dict[str, Any]) -> None:
        """What a builder writes when it ends: its status, echoing its handoff."""
        value = dict(result)
        value.setdefault("handoff", request["handoff"])
        path = os.path.join(repo, request["result"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            json.dump(value, handle)

    def stub_builder(self, repo: str, request: dict[str, Any], files: dict[str, str] | None,
                     result: dict[str, Any] | None, commit: bool = True) -> None:
        """A stand-in for the fresh builder: a new process given only the brief.

        It reads the brief from its file, writes code in the worktree the brief
        names, commits it, and writes the result file, as a builder does.
        """
        script = ("import json, os, subprocess, sys\n"
                  "brief = json.load(open(sys.argv[1]))\n"
                  "files = json.loads(sys.argv[2])\n"
                  "folder = brief['baseline']['directory']\n"
                  "for path, text in files.items():\n"
                  "    full = os.path.join(folder, path)\n"
                  "    os.makedirs(os.path.dirname(full), exist_ok=True)\n"
                  "    open(full, 'w').write(text)\n"
                  "if files and sys.argv[3] == 'commit':\n"
                  "    subprocess.run(['git', '-C', folder, 'add', '-A'], check=True)\n"
                  "    subprocess.run(['git', '-C', folder, 'commit', '-q', '-m', 'attempt'],"
                  " check=True)\n")
        brief = os.path.join(repo, request["brief"])
        done = subprocess.run([sys.executable, "-c", script, brief, json.dumps(files or {}),
                               "commit" if commit else "keep"],
                              cwd=self.work, env=self.env, capture_output=True, text=True)
        if done.returncode != 0:
            raise SystemExit("the stub builder failed: " + done.stderr)
        if result is not None:
            self.write_result(repo, request, result)
