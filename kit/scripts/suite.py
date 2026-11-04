"""The full Test command and Keep, run once on the base before the final pull request.

A tiered run narrows the check after each attempt. This suite is what still catches
old behaviour that a piece broke outside the tests it touched.
"""
from __future__ import annotations

import tempfile
from contextlib import suppress
from pathlib import Path

import gate
import regression
from loop_pr import in_main
from loopkit import GitHub, keep_limit_seconds, loop_settings, prepare, run_keep, sh, sh_network
from run_start import remove_worktree


def full_suite(root: Path, commit: str, settings: dict) -> tuple[bool, str]:
    """Run Prepare, the Test command and a distinct Keep in a fresh copy of `commit`."""
    tmp = Path(tempfile.mkdtemp(prefix="loop-suite-"))
    folder = tmp / "base"
    try:
        sh(["git", "worktree", "add", "--detach", "--quiet", str(folder), commit], root)
        ok, output = prepare(folder, settings.get("prepare", ""))
        if not ok:
            return False, "Prepare failed:\n" + output
        limit = keep_limit_seconds(settings)
        result, output = regression.check(folder, settings["test"], limit, label="Full suite")
        keep = settings.get("keep", settings["test"])
        if result["reason"] or keep == settings["test"]:
            return not result["reason"], output
        code, koutput = run_keep(folder, keep, timeout=limit)
        return code == 0, output + "\n" + koutput
    finally:
        remove_worktree(root, folder)
        with suppress(OSError):
            tmp.rmdir()


def merged_this_run(gh: GitHub, root: Path, base: str,
                    numbers: list[int]) -> list[tuple[int, str]]:
    """This run's pieces merged into the base and not yet in main, in base order."""
    merged = {}
    for pr in gh.pull_requests(base, "merged"):
        name, _, number = pr.get("headRefName", "").partition("/")
        commit = (pr.get("mergeCommit") or {}).get("oid", "")
        if name == "piece" and number.isdigit() and int(number) in numbers and commit:
            merged[commit] = int(number)
    order = sh(["git", "rev-list", "--first-parent", "--reverse", f"origin/{base}"], root,
               check=False).stdout.split()
    return [(merged[c], c) for c in order if c in merged and not in_main(root, c)]


def final_check(gh: GitHub, root: Path, base: str, numbers: list[int]) -> str:
    """Run the full suite on the base tip. Returns a result line, or "" when nothing merged."""
    sh_network(["git", "fetch", "--quiet", "origin", "main", base], root, check=False)
    pieces = merged_this_run(gh, root, base, numbers)
    if not pieces:
        return ""
    shown = sh(["git", "show", f"origin/{base}:AGENTS.md"], root, check=False)
    settings = loop_settings(root, shown.stdout if shown.returncode == 0 else None)
    ok, output = full_suite(root, f"origin/{base}", settings)
    if ok:
        return f"Full suite passed on {base} ({len(pieces)} pieces)"
    print(output.strip()[-1500:])
    n, found, _ = find_breaker(root, base, pieces, settings)
    if n is None:
        return (f"Full suite failed on {base}; no single piece found; "
                "final pull request held until it passes")
    return hand_back(gh, root, base, n, found or output, settings["test"])


def find_breaker(root: Path, base: str, merged: list[tuple[int, str]],
                 settings: dict) -> tuple[int | None, str, int]:
    """Binary search for the first piece whose merge fails the full suite.

    The start-of-run baseline counts as good and the base tip as bad. Returns the piece, or
    None when no merge fails, the output of its failing run ("" when that run was the tip's)
    and the suite runs taken, the tip's included.
    """
    tip = sh(["git", "rev-parse", f"origin/{base}"], root, check=False).stdout.strip()
    good, bad = -1, len(merged) - 1 if merged and merged[-1][1] == tip else len(merged)
    outputs, runs = {}, 1
    while bad - good > 1:
        mid = (good + bad) // 2
        ok, outputs[mid] = full_suite(root, merged[mid][1], settings)
        runs += 1
        good, bad = (mid, bad) if ok else (good, mid)
    if bad == len(merged):
        return None, "", runs
    return merged[bad][0], outputs.get(bad, ""), runs


def hand_back(gh: GitHub, root: Path, base: str, n: int, output: str, command: str) -> str:
    """Move the piece that broke the suite from done back to shaping, reopened, with the output."""
    if gh.issue(n).get("state", "OPEN") != "OPEN":
        gh.reopen(n)
    gate.move(gh, root, n, "shaping", reason=f"broke the full suite on {base}: {command}",
              reason_type="builder-failed", needs_you=True)
    gh.comment(n, f"**Run:** the full suite `{command}` fails on {base} from this piece's "
               f"merge. The last 3,000 characters of its output:\n\n```\n{output[-3000:]}\n```")
    return f"piece {n}: back to shaping, broke the full suite on {base}"
