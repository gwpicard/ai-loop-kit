#!/usr/bin/env python3
"""Run project tests on a hosted pull request, including the first scaffold.

An empty policy is allowed only against a foundation-only base. Founding has
no tests; the first scaffold runs its own command. Once product files exist
or a command was configured, every pull request needs the policy command.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

FOUNDATION = {
    "README.md", "LICENSE", "LICENSE.md", ".gitignore", "AGENTS.md", "CLAUDE.md",
    "CHANGELOG.md", "docs/overview.md", "docs/README.md", "docs/area-map",
    "docs/open-questions.md", ".github/workflows/checks.yml",
    ".agents/guard/blocked-commands.md", ".claude/settings.json",
    ".agents/loop/policy.json", ".agents/loop/network-allowlist.json",
    ".githooks/pre-push", ".githooks/commit-msg",
}
POLICY = ".agents/loop/policy.json"


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    )
    return result.stdout


def foundation(root: Path, ref: str) -> bool:
    return set(git(root, "ls-tree", "-r", "--name-only", ref).splitlines()) <= FOUNDATION


def command_at_base(root: Path, base: str) -> str:
    files = git(root, "ls-tree", "-r", "--name-only", base).splitlines()
    if POLICY not in files:
        return ""
    data = json.loads(git(root, "show", f"{base}:{POLICY}"))
    return command(data)


def command(data: object) -> str:
    if not isinstance(data, dict) or not isinstance(data.get("test_command", ""), str):
        raise ValueError("test_command must be text in a policy object")
    return str(data.get("test_command", "")).strip()


def run(root: Path, base: str, scaffold_command: str) -> int:
    try:
        test_command = command(json.loads((root / POLICY).read_text("utf-8")))
        if test_command:
            return subprocess.run(["sh", "-c", test_command], cwd=root, check=False).returncode
        # A missing or unreadable base never grants the bootstrap exception.
        if not base or not foundation(root, base) or command_at_base(root, base):
            raise ValueError("the pull request base is not an untested foundation")
        if foundation(root, "HEAD"):
            print("Founding: no project tests exist yet. The records check still runs.")
            return 0
        if not scaffold_command.strip():
            raise ValueError("the first scaffold has no known test command")
        print("First scaffold: running its test command; the policy remains unconfigured.")
        return subprocess.run(["sh", "-c", scaffold_command], cwd=root, check=False).returncode
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"The policy has no test_command or cannot be read: {error}. "
              "Write the project's test command in .agents/loop/policy.json, then push again.")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="")
    parser.add_argument("--scaffold-command", default="")
    args = parser.parse_args()
    return run(Path.cwd(), args.base, args.scaffold_command)


if __name__ == "__main__":
    raise SystemExit(main())
