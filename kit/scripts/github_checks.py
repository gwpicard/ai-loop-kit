"""Tell a billing block from a failed check, and test the commit here when GitHub would not."""
from __future__ import annotations

import json
import tempfile
from contextlib import suppress
from pathlib import Path

import regression
from loopkit import GitHub, Refused, last_record, prepare, sh

BILLING = ("recent account payments have failed", "spending limit")
FAILED = ("failure", "timed_out", "cancelled", "startup_failure", "action_required")
CHECKS = "repos/{owner}/{repo}/commits/%s/check-runs?per_page=100"


def billing_block(gh: GitHub, sha: str) -> str:
    """The annotation text when every failed check run was blocked by billing, else ''."""
    try:
        runs = json.loads(gh.api(CHECKS % sha))["check_runs"]
        notes = []
        for run in (r for r in runs if r.get("conclusion") in FAILED):
            path = f"repos/{{owner}}/{{repo}}/check-runs/{run['id']}/annotations"
            text = " ".join(a.get("message") or "" for a in json.loads(gh.api(path)))
            if not any(phrase in text.lower() for phrase in BILLING):
                return ""
            notes.append(text)
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError):
        return ""
    return " ".join(notes)


def verify_locally(root: Path, head: str, ready: dict) -> tuple[bool, str]:
    """Run Prepare and the frozen Test command in a clean checkout of `head`."""
    tmp = Path(tempfile.mkdtemp(prefix="loop-verify-"))
    folder = tmp / "head"
    try:
        regression.require_record(ready)
        sh(["git", "worktree", "add", "--detach", "--quiet", str(folder), head], root)
        protected = ready.get("protected_paths", [])
        ok, output = prepare(folder, ready.get("prepare", ""), protected)
        if not ok:
            return False, "Prepare failed:\n" + output.strip()[-1500:]
        result, _ = regression.check(folder, ready["regression"], ready["regression_limit"], protected)
        return not result["reason"], f"exit {result['exit']}" + (
            f", {result['reason']}" if result["reason"] else "") + "\n" + result["output"][-1500:]
    except (Refused, RuntimeError, OSError) as error:
        return False, getattr(error, "reason", str(error))
    finally:
        sh(["git", "worktree", "remove", "--force", str(folder)], root, check=False)
        with suppress(OSError):
            tmp.rmdir()


def billing_report(gh: GitHub, root: Path, n: int, head: str) -> str:
    """For a merge GitHub refused over billing, test the commit here and say so; else ''."""
    if not billing_block(gh, head):
        return ""
    ok, output = verify_locally(root, head, last_record(gh.comments(n), "ready") or {})
    sha, verdict = head[:10], "passed" if ok else "failed"
    gh.comment(n, f"**Run:** GitHub did not run the checks on `{sha}` (billing or spending "
                  f"limit). The Test command ran locally on that commit and {verdict}.\n\n"
                  f"```\n{output}\n```")
    return ("GitHub did not run the checks (billing or spending limit); this is not a test "
            f"failure. Local Test command on {sha}: {verdict}. "
            + ("next: merge it on GitHub after a look" if ok else
               "next: read the output in the pull request, fix it, then run the piece again"))
