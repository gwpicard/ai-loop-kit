"""The run's calls to the gate, the trim pass and the worktree script.

Every state move goes through `gate.py`, as a command, and never through a label or a piece
record written here. The reply keeps what the gate printed: its JSON and its exit code. A reply
that is not JSON, or a command that cannot start, is a reply that failed, so no caller can take
silence for a pass.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loop.paths import Paths

Runner = Callable[..., "subprocess.CompletedProcess[str]"]
OK = 0


@dataclass(frozen=True)
class Reply:
    code: int
    data: dict[str, Any] = field(default_factory=dict)
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.code == OK and bool(self.data.get("ok", True))

    @property
    def message(self) -> str:
        return str(self.data.get("error") or self.stderr.strip() or f"exit code {self.code}")

    @property
    def next_command(self) -> str:
        return str(self.data.get("next") or "")


class Gateway:
    def __init__(
        self,
        paths: Paths,
        *,
        runner: Runner = subprocess.run,
        python: str = sys.executable,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.paths = paths
        self.runner = runner
        self.python = python
        self.env = None if env is None else dict(env)

    def _script(self, name: str) -> str:
        return str(self.paths.kit_dir / "scripts" / name)

    def _call(self, script: str, args: Sequence[str]) -> Reply:
        argv = [self.python, self._script(script), *args, "--json"]
        try:
            done = self.runner(
                argv, cwd=str(self.paths.root), env=self.env, capture_output=True, text=True,
                check=False, stdin=subprocess.DEVNULL,
            )
        except OSError as error:
            return Reply(127, {"ok": False, "error": f"{script} could not start ({error})"})
        data: dict[str, Any] = {}
        for line in reversed((done.stdout or "").strip().splitlines()):
            try:
                parsed = json.loads(line)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                data = parsed
                break
        if not data and done.returncode == OK:
            return Reply(1, {"ok": False, "error": f"{script} printed no JSON, so its answer "
                                                    "cannot be read"}, done.stderr or "")
        return Reply(done.returncode, data, done.stderr or "")

    # --- the gate --------------------------------------------------------------------

    def move(
        self, number: int, target: str, *, reason: str | None = None,
        options: Mapping[str, str] | None = None,
    ) -> Reply:
        args = ["move", str(number), target]
        if reason:
            args += ["--reason", reason]
        for key, value in (options or {}).items():
            args += ["--option", f"{key}={value}"]
        return self._call("gate.py", args)

    def branch(self, number: int) -> Reply:
        return self._call("gate.py", ["branch", str(number)])

    # --- the trim pass ---------------------------------------------------------------

    def trim(self, number: int, run: str, max_budget_usd: float | None) -> Reply:
        args = ["run", "--piece", str(number), "--run", run]
        if max_budget_usd is not None:
            args += ["--max-budget-usd", f"{max_budget_usd:.4f}"]
        return self._call("trim-check.py", args)

    # --- the stack -------------------------------------------------------------------

    def stack(self, folder: Path, numbers: Sequence[int]) -> tuple[int, str, str]:
        """Merge each dependency's branch into the piece's worktree. Returns (code, text, base).

        Each merge is a merge commit with the subject `Stack on piece <n>`, never a rebase. A
        dependency the folder already holds is skipped, so a second call changes nothing. The
        base is the last merge this call made, so it is never read from the log, where a merge
        of the builder's own could pass for it. It is "" when this call made no merge, and when
        the code is not 0 (with the files that conflicted). A conflict leaves the folder as it
        was.
        """
        root = str(self.paths.root)
        where = str(folder)
        quiet = [*_identity(self.runner, root), "-c", "commit.gpgsign=false"]

        def git(*args: str) -> subprocess.CompletedProcess[str]:
            return self.runner(["git", "-C", where, *quiet, *args], capture_output=True,
                               text=True, check=False, env=self.env)

        made = ""
        for number in numbers:
            branch = f"piece-{number}"
            held = git("merge-base", "--is-ancestor", f"refs/heads/{branch}", "HEAD")
            if held.returncode == 0:
                continue
            done = git("merge", "--no-ff", "-q", "-m", f"{STACK_SUBJECT}{number}", branch)
            if done.returncode != 0:
                listing = git("diff", "--name-only", "--diff-filter=U").stdout.split()
                git("merge", "--abort")
                named = ", ".join(listing) or (done.stderr or done.stdout).strip()[:120]
                return 1, f"merging {branch} conflicted in {named}", ""
            head = git("rev-parse", "HEAD")
            if head.returncode != 0 or not head.stdout.strip():
                return 1, f"git could not read the stacking merge of {branch}", ""
            made = head.stdout.strip()
        return 0, "stacked" if made else "already stacked", made

    # --- the worktree ----------------------------------------------------------------

    def open_worktree(self, name: str, branch: str, base: str, *, resume: bool) -> tuple[int, str]:
        argv = ["sh", self._script("worktree.sh"), "open"]
        if resume:
            argv.append("--resume")
        argv += [name, branch, base]
        try:
            done = self.runner(
                argv, cwd=str(self.paths.root), env=self.env, capture_output=True, text=True,
                check=False, stdin=subprocess.DEVNULL,
            )
        except OSError as error:
            return 127, f"worktree.sh could not start ({error})"
        return done.returncode, ((done.stdout or "") + (done.stderr or "")).strip()


STACK_SUBJECT = "Stack on piece "


def _identity(runner: Runner, root: str) -> list[str]:
    """`-c` options that give a committer when Git has none, so a stacking merge can commit."""
    done = runner(["git", "-C", root, "var", "GIT_COMMITTER_IDENT"], capture_output=True,
                  text=True, check=False)
    if done.returncode == 0:
        return []
    return ["-c", "user.name=AI Loop Kit", "-c", "user.email=loop@localhost.invalid"]


def worktree_path(paths: Path | Paths, name: str) -> Path:
    base = paths.worktrees_dir if isinstance(paths, Paths) else paths
    return base / name
