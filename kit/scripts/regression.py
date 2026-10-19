"""Run the required project tests, independently of a piece's extra Keep."""
from __future__ import annotations

import re
from pathlib import Path

from loopkit import Refused, rev, run_keep, skipped_tests


def check(folder: Path, command: str, limit: int,
          protected_paths: list[str] | None = None) -> tuple[dict, str]:
    code, output = run_keep(folder, command, timeout=limit, protected_paths=protected_paths)
    if code == 124:
        reason = "timed out"
    elif code in (126, 127) or (code != 0 and re.search(
            r"No module named|command not found|not recognized|: [^\n]+: not found|"
            r"can't open file|No such file or directory", output, re.I)):
        reason = "test runner is missing or could not start"
    elif re.search(r"Ran 0 tests|no tests ran|collected 0 items|no tests? (?:files )?found|"
                   r"^#?\s*tests\s+0\s*$", output, re.I | re.M):
        reason = "collected no tests"
    elif skipped_tests(output):
        reason = "reported skipped tests"
    else:
        reason = "failed" if code else ""
    result = {"command": command, "limit": limit, "commit": rev(folder, "HEAD"),
              "exit": code, "output": output[-3000:], "reason": reason}
    evidence = (output + f"\nRegression: {command}\nCommit: {result['commit']}\nExit: {code}\n"
                + (f"Regression {reason}\n" if reason else ""))
    return result, evidence


def require_record(ready: dict) -> None:
    if not ready.get("regression") or "regression_limit" not in ready:
        raise Refused("the ready record has no required regression command",
                      "pull the piece back to shaping and run ready again")
