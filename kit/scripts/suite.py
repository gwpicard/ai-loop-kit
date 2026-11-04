"""The full Test command and Keep, run once on the base before the final pull request.

A tiered run narrows the check after each attempt. This suite is what still catches
old behaviour that a piece broke outside the tests it touched.
"""
from __future__ import annotations

import tempfile
from contextlib import suppress
from pathlib import Path

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
    return f"Full suite failed on {base}; final pull request held until it passes"
