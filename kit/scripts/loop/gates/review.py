"""Move 10: review to approval. The pull request opens, grouped by piece.

The run's pull request step asks for this move after it opened the pull request, once for each
piece the pull request holds, and gives the facts as options (`merge.OPENING_OPTIONS`). The gate
does not take them on trust. It reads the run record and Git, and it reads the pull request from
GitHub as the App. It passes only when:

- the final combined check was green on the head of the branch the pull request is cut from;
- the review of the track was clean on that head, and the verdict of each piece is clean;
- the pull request is open, its head is the tested commit, and its base is the one said;
- the tested commit holds each piece's join, and the branch points at it;
- every doc a piece names was changed, and no closing word stands anywhere but on a `Closes`
  line, one line for each piece.

On a pass it writes a `pull-request` entry in the piece record. Moves 11 and 12 read that entry
back, so the tested commit is the one the gate wrote and never one an agent names later.
"""

from __future__ import annotations

from loop import github
from loop.gates import CheckContext, CheckResult, passed, refused
from loop.gates import merge as merge_gate


def check(ctx: CheckContext) -> CheckResult:
    try:
        opening = merge_gate.Opening.from_options(ctx.options)
        if ctx.number not in opening.pieces:
            return refused([f"piece {ctx.number} is not one of the pieces of pull request "
                            f"{opening.number}"], "python3 -m loop.run.pull_request status "
                           f"--run {opening.run}")
        pr = merge_gate.pulls_for(ctx).view(opening.number)
        manual = ctx.person_github and ctx.authority == "person"
        online = merge_gate.online_faults(pr, opening)
        if manual and pr.state == "MERGED":
            online = [f for f in online if f != "the pull request is merged, not open"]
        faults = online + merge_gate.offline_faults(
            ctx.paths, opening, title=pr.title, body=pr.body, manual=manual)
    except merge_gate.Unreadable as error:
        return refused([str(error)], error.next_command)
    except github.GitHubError as error:
        return refused([error.message], error.next_command)
    if faults:
        return refused(faults, "fix what the gate names, close the pull request if it must "
                       "change, then run python3 -m loop.run.pull_request open --run "
                       f"{opening.run}")
    entry = opening.as_entry()
    entry["url"] = pr.url
    return passed(entries=[entry])
