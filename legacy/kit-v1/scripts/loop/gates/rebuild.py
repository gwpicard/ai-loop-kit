"""Move 8: review to building. A trial join turned red, so the trial was thrown away and the
combined branch never moved. Or a merge conflict. Or a review finding became a failing check.

The gate's shared rules hold this move: the written reason, and the repeat counter, which
sends the piece back to shaping after three of the same move. The integration loop
(`loop/run/integrate.py`) supplies the reason: the failure, and the piece it clashed with.

A review finding that is a failing check also brings a new test, which joins the frozen bar.
The review loop (`loop/run/review.py`) commits the test file to the piece branch, then asks
for this move with four options:

- `review_test_path`: the test file, relative to the project, in a place where tests live;
- `review_test_commit`: the commit on the piece branch that holds it;
- `review_test_command`: the command that runs it, and names the file;
- `review_justification`: why the person may trust the test, in the reviewer's words.

The gate checks all four and writes a `review-test` entry in the piece record. From then on
`loop.bar` lists the file as frozen and the attempt gate runs its command on every attempt.
A builder cannot write the entry, so the review loop and the gate hold it, not the builder.
A half set of options is a refusal, never a plain move back.
"""

from __future__ import annotations

import shlex
from pathlib import PurePosixPath

from loop import bar
from loop.gates import CheckContext, CheckResult, passed, refused
from loop.gates import ready as ready_gate

OPTIONS = ("review_test_path", "review_test_commit", "review_test_command",
           "review_justification")


def _refuse(ctx: CheckContext, text: str) -> CheckResult:
    return refused([text], f"gate.py move {ctx.number} building --reason \"<why>\" with the four "
                   f"review options ({', '.join(OPTIONS)}) as the review loop gives them")


def check(ctx: CheckContext) -> CheckResult:
    given = {name: str(ctx.options.get(name, "")) for name in OPTIONS if name in ctx.options}
    if not given:
        return passed()
    missing = [name for name in OPTIONS if not given.get(name, "").strip()]
    if missing:
        return _refuse(ctx, f"a review test needs all four options, and {', '.join(missing)} "
                       "is missing or blank, so the gate will not freeze half a test")
    path, commit = given["review_test_path"].strip(), given["review_test_commit"].strip()
    command = given["review_test_command"].strip()
    pure = PurePosixPath(path)
    if (pure.is_absolute() or ".." in pure.parts or any(c in path for c in "*?[]{}")
            or not bar.is_test(path) or bar.is_guarded(path) or bar.is_settings(path)):
        return _refuse(ctx, f"the review test path {path!r} is not one test file inside the "
                       "project, so the gate will not freeze it")
    root = ctx.paths.root
    branch = ready_gate.branch_name(ctx.number)
    code, full = ready_gate._git(root, "rev-parse", "--verify", "-q", f"{commit}^{{commit}}")
    if code != 0:
        return _refuse(ctx, f"the commit {commit[:12]} of the review test does not exist")
    code, _ = ready_gate._git(root, "merge-base", "--is-ancestor", full,
                              f"refs/heads/{branch}")
    if code != 0:
        return _refuse(ctx, f"the commit {commit[:12]} of the review test is not on the piece "
                       f"branch {branch}, so the builder would not have the test")
    code, listing = ready_gate._git(root, "ls-tree", full, "--", path)
    if code != 0 or not listing.strip():
        return _refuse(ctx, f"the commit {commit[:12]} does not hold the file {path}")
    try:
        words = shlex.split(command)
    except ValueError:
        words = []
    if path not in words:
        return _refuse(ctx, f"the review test command does not name the file {path} as a "
                       "word, so it would not run the test")
    if path in bar.review_files(ctx.record):
        return _refuse(ctx, f"the file {path} is already frozen by an earlier review test")
    return passed(entries=[{
        "kind": bar.REVIEW_KIND, "path": path, "commit": full, "command": command,
        "justification": given["review_justification"].strip(),
    }])


__all__ = ["check"]
