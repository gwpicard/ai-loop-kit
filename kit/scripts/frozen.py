"""Check the judge bar fixed at ready, and say what changed it.

The Exit files are frozen byte for byte. The support files beside them are
checked against the expected tree: the ready commit with the base merged in.
So a change that arrives from the base is free, and a build's edit is caught.
"""
from pathlib import Path
from typing import Optional

from loopkit import (bar_hash_at, bar_hash_in, clean_quality_outputs, exit_bar, in_bar_zone,
                     main_ref, record_quality_outputs, rev, run_judge, sh, skipped_tests)


def expected_tree(folder: Path, ready: dict) -> Optional[str]:
    """The ready commit merged with the base. None while a merge is open or conflicts."""
    if rev(folder, "MERGE_HEAD"):
        return None
    base = sh(["git", "merge-base", "HEAD", main_ref(folder)], folder).stdout.strip()
    res = sh(["git", "merge-tree", "--write-tree", ready["commit"], base], folder, check=False)
    return res.stdout.split()[0] if res.returncode == 0 and res.stdout.strip() else None


def neighbour_edits(folder: Path, ready: dict, tree: Optional[str]) -> list[str]:
    """Support files the build edited or deleted. Added files stay allowed."""
    if tree is None:
        return []
    changed = sh(["git", "diff", "--no-renames", "--diff-filter=MDT", "--name-only", "-z", tree],
                 folder).stdout.split("\0")
    return sorted(path for path in changed
                  if path and path not in ready["files"] and in_bar_zone(path, ready["files"]))


def frozen_file_reason(folder: Path, ready: dict) -> str:
    """Name each mismatch and tell files changed on the base from build edits."""
    files = ready["files"]
    if not files:
        return ""
    edited = neighbour_edits(folder, ready, expected_tree(folder, ready))
    inherited = []
    if bar_hash_in(folder, files) != exit_bar(folder, ready):
        changed = [path for path in files
                   if bar_hash_at(folder, ready["commit"], [path], [path])
                   != bar_hash_in(folder, [path])]
        base = sh(["git", "merge-base", "HEAD", main_ref(folder)], folder).stdout.strip()
        build_paths = set(sh(["git", "diff", "--no-renames", "--name-only", "-z", base],
                             folder).stdout.split("\0"))
        old_base = sh(["git", "merge-base", ready["commit"], base], folder).stdout.strip()
        main_paths = set(sh(["git", "diff", "--no-renames", "--name-only", "-z",
                             old_base, base], folder).stdout.split("\0"))
        inherited = sorted((set(changed) & main_paths) - build_paths)
        edited = sorted(set(edited) | (set(changed) - set(inherited)))
    reasons = []
    if inherited:
        reasons.append("main changed the frozen judge bar: " + ", ".join(inherited))
    if edited:
        reasons.append("the build changed frozen files: " + ", ".join(edited))
    return "; ".join(reasons)


def already_satisfied(folder: Path, ready: dict) -> str:
    """When the base moved since ready, run the Exit tests once before the builder.
    If they already pass, merged work built this piece."""
    tests = [check["command"] for check in ready.get("checks", []) if check["type"] == "tests"]
    if not tests or rev(folder, main_ref(folder)) == ready.get("main"):
        return ""
    tree = expected_tree(folder, ready)
    if tree is None or sh(["git", "diff", "--name-only", tree, "HEAD"], folder).stdout.strip():
        return ""  # an open merge, or code from an earlier build: the attempts decide
    try:
        for command in tests:
            code, output = run_judge(folder, command,
                                     protected_paths=ready.get("protected_paths", []))
            if code or skipped_tests(output):
                return ""
    finally:
        clean_quality_outputs(folder, record_quality_outputs(folder))
    return ("already satisfied: the judge passes on the base before any build, "
            "because merged work builds this piece. next: drop it or reshape what remains")
