"""Explain mismatches against the judge bar fixed at ready."""
from pathlib import Path

from loopkit import bar_hash_at, bar_hash_in, main_ref, sh


def frozen_file_reason(folder: Path, ready: dict) -> str:
    """Name each mismatch and distinguish inherited files from build edits."""
    paths = ready.get("bar_files", ready["files"])
    changed = [path for path in paths
               if bar_hash_at(folder, ready["commit"], [path], [path])
               != bar_hash_in(folder, [path])]
    base = sh(["git", "merge-base", "HEAD", main_ref(folder)], folder).stdout.strip()
    build_paths = set(sh(["git", "diff", "--no-renames", "--name-only", "-z", base],
                         folder).stdout.split("\0"))
    old_base = sh(["git", "merge-base", ready["commit"], base], folder).stdout.strip()
    main_paths = set(sh(["git", "diff", "--no-renames", "--name-only", "-z",
                         old_base, base], folder).stdout.split("\0"))
    inherited = sorted((set(changed) & main_paths) - build_paths)
    edited = sorted(set(changed) - set(inherited))
    reasons = []
    if inherited:
        reasons.append("main changed the frozen judge bar: " + ", ".join(inherited))
    if edited:
        reasons.append("the build changed frozen files: " + ", ".join(edited))
    return "; ".join(reasons)
