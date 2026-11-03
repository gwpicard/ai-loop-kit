"""Run the required project tests, independently of a piece's extra Keep."""
from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

from loopkit import Refused, main_ref, rev, run_keep, sh, skipped_tests


def tiered() -> bool:
    """The run, not a builder, asks for the narrow tier through its own environment."""
    return os.environ.get("AI_LOOP_KIT_TIER") == "narrow"


def _reason(code: int, output: str) -> str:
    if code == 124:
        return "timed out"
    if code in (126, 127) or (code != 0 and re.search(
            r"No module named|command not found|not recognized|: [^\n]+: not found|"
            r"can't open file|No such file or directory", output, re.I)):
        return "test runner is missing or could not start"
    if re.search(r"Ran 0 tests|no tests ran|collected 0 items|no tests? (?:files )?found|"
                 r"^#?\s*tests\s+0\s*$", output, re.I | re.M):
        return "collected no tests"
    if skipped_tests(output):
        return "reported skipped tests"
    return "failed" if code else ""


def check(folder: Path, command: str, limit: int,
          protected_paths: list[str] | None = None) -> tuple[dict, str]:
    code, output = run_keep(folder, command, timeout=limit, protected_paths=protected_paths)
    reason = _reason(code, output)
    result = {"command": command, "limit": limit, "commit": rev(folder, "HEAD"),
              "exit": code, "output": output[-3000:], "reason": reason}
    evidence = (output + f"\nRegression: {command}\nCommit: {result['commit']}\nExit: {code}\n"
                + (f"Regression {reason}\n" if reason else ""))
    return result, evidence


def changed_test_files(folder: Path, ready: dict) -> list[str]:
    """Test files changed since the base, in any state, plus test files the Exit names."""
    from gate import _is_test_support
    listings = (["git", "diff", "--no-renames", "--name-only", f"{main_ref(folder)}...HEAD"],
                ["git", "diff", "--no-renames", "--name-only", "HEAD"],
                ["git", "ls-files", "--others", "--exclude-standard"])
    names = {name for args in listings for name in sh(args, folder).stdout.splitlines()}
    names.update(ready.get("files", []))
    return sorted(name for name in names
                  if name and _is_test_support(name) and (folder / name).is_file())


def narrow(folder: Path, ready: dict,
           protected_paths: list[str] | None = None) -> tuple[dict, str]:
    """Run the Test files command on the touched test files, or the full Test command."""
    template = ready.get("regression_files", "")
    if not template:
        return check(folder, ready["regression"], ready["regression_limit"], protected_paths)
    if "{files}" not in template:
        raise Refused("the Test files command has no {files} placeholder",
                      "add {files} to `Test files command:` in the loop section of AGENTS.md")
    files = changed_test_files(folder, ready)
    if not files:
        return ({"command": template, "files": [], "commit": rev(folder, "HEAD"),
                 "exit": 0, "output": "", "reason": ""},
                "Narrow tests: no test files changed\n")
    command = template.replace("{files}", " ".join(shlex.quote(name) for name in files))
    limit = ready["regression_limit"]
    code, output = run_keep(folder, command, timeout=limit, protected_paths=protected_paths)
    reason = _reason(code, output)
    result = {"command": command, "files": files, "limit": limit,
              "commit": rev(folder, "HEAD"), "exit": code, "output": output[-3000:],
              "reason": reason}
    evidence = (f"Narrow tests: {command}\nFiles: {', '.join(files)}\n{output}"
                f"\nCommit: {result['commit']}\nExit: {code}\n"
                + (f"Narrow tests {reason}\n" if reason else ""))
    return result, evidence


def require_record(ready: dict) -> None:
    if not ready.get("regression") or "regression_limit" not in ready:
        raise Refused("the ready record has no required regression command",
                      "pull the piece back to shaping and run ready again")
