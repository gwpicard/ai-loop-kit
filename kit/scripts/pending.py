"""The ready check's run in a fresh copy of main: in full, or for a piece with blockers.

A piece whose Depends on pieces are not all done has no base to prove its judge against.
It gets the checks that need no base; the base check runs when its blockers are done.
"""
from __future__ import annotations

import tempfile
from contextlib import suppress
from pathlib import Path

from errors import JudgeRefused
from loopkit import Refused, new_paths, prepare, run_keep, sh, untracked_paths
import regression
from run_start import capture_probe_files, remove_worktree, restore_probe_files
from testlint import lint_files


def run_in_main(root: Path, n: int, spec, blockers: list[int], main: str, head: str,
                bar_files: list[str], regression_command: str, keep_command: str,
                keep_limit: int) -> dict:
    """Run the judge on today's main, with only the judge files added."""
    import gate  # the seam tests patch exit_ready on gate
    from gate import covered, generated, snapshot_or_generated
    tmp = Path(tempfile.mkdtemp(prefix=f"loop-ready-{n}-"))
    folder = tmp / "main"
    before_injection = injected = {}
    made_by_test: set[str] = set()
    regression_main = {"reason": "scaffold: no test runner on main"}
    keep_output = ""
    try:
        sh(["git", "worktree", "add", "--detach", "--quiet", str(folder), main], root)
        ok, poutput = (True, "") if spec.kind == "scaffold" or blockers else prepare(folder)
        before = untracked_paths(folder)
        before_dirs = {child.name for child in folder.iterdir() if child.is_dir()}
        if not ok:
            raise Refused("the Prepare command fails on a fresh copy of main:\n"
                          f"{poutput.strip()[-1500:]}",
                          "fix the Prepare command in AGENTS.md, then run gate.py doctor")
        if blockers:
            regression_main = {"reason": "base check pending"}
        elif spec.kind != "scaffold":
            regression_main, keep_output = regression.check(folder, regression_command, keep_limit)
            if regression_main["reason"]:
                raise Refused(f"the regression check on main {regression_main['reason']}:\n"
                              f"{keep_output.strip()[-1500:]}\nCommand: {regression_command}",
                              "fix main or the Test command and environment, then run ready again")
        if keep_command and keep_command != regression_command and not blockers:
            kcode, koutput = run_keep(folder, keep_command, timeout=keep_limit)
            keep_output += "\n" + koutput
            if kcode != 0:
                raise Refused(f"the keep check already fails on main:\n{koutput.strip()[-1500:]}",
                              "fix main first, or correct the Keep: command")
        if bar_files:
            try:
                before_injection = capture_probe_files(folder, bar_files)
                sh(["git", "checkout", head, "--", *bar_files], folder)
                injected = capture_probe_files(folder, bar_files)
            except OSError as error:
                raise Refused(f"cannot read judge file {error.filename or bar_files[0]}",
                              "make the judge file readable, then run ready again") from None
        lint, test_lint_unchecked = lint_files(
            [folder / f for f in spec.files], folder, " ".join(spec.done_when.values()))
        if lint:
            raise JudgeRefused("the judge has quality problems:\n" + "\n".join(lint),
                               "fix the judge files, then run gate.py check again")
        made_by_test = new_paths(folder, before, before_dirs, snapshot_or_generated)
        check_records, output = ([dict(c) for c in spec.checks], "") if blockers else \
            gate.exit_ready(folder, spec.checks, spec.done_when, spec.stays)
        test_outputs = sorted(new_paths(folder, before, before_dirs, snapshot_or_generated))
        kind_record = {"checks": check_records}
        if spec.kind in ("goal", "gauntlet"):
            kind_record.update(check_records[0])
    finally:
        if injected:
            restore_probe_files(folder, before_injection, injected)
        # the Test command's caches and reports are the kit's
        remove_worktree(root, folder, made=lambda p: generated(p) or covered(p, made_by_test))
        with suppress(OSError):
            tmp.rmdir()
    return {"regression_main": regression_main, "keep_output": keep_output, "output": output,
            "test_outputs": test_outputs, "kind_record": kind_record,
            "test_lint_unchecked": test_lint_unchecked}
