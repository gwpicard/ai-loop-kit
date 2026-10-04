---
name: sync
description: True the documents up against what actually happened. Use for an interrupted session, work done outside the skills, an imported branch or contribution, a long session whose context went foggy, or reconciliation before a handover. Normal completion of /shape, /implement, /fix, /ship, and /maintain already updates the records; sync is the recovery and reconciliation route, not a routine step after every piece.
---

# Sync

The documents are supposed to describe reality. Make that true again by reading what actually happened, and correct the records instead of trusting what they claim. Propose the document changes before making anything large or ambiguous. You change documents only, never code; the single piece of machinery you keep in step is the check's own file, in step 6.

## When to run this

Normal completion of /shape, /implement, /fix, /ship, and /maintain already updates the
pieces, the changelog, and the masterplan directly; a correctly finished
piece of work doesn't need sync afterward. Reach for sync instead for: a
session that was interrupted mid-piece, work done outside the skills
entirely, an imported branch or outside contribution, a long session whose
context became unclear, reconciliation before handing the project to someone
else, or recovering after an optional automation failed to run.

## The routine

1. Bring the shared `main` branch up to date, then read the commits and changes since the last changelog entry, counting an entry waiting in `changes/` as written, plus the tool's actual behaviour where that is cheap to check, and compare them against the records and the current Git state.

   Read the result of the newest run of the project check on `main`, with `gh run list --branch main --workflow <file> --limit 1 --json status,conclusion`, where `<file>` is the name of the workflow file the capability profile's `Project check:` line records (`.github/workflows/checks.yml`, job `project-check`, where that line names no file). A run still in progress is named as waiting, never as a finding. Where the finished run is red, it leads the findings: a merge made on GitHub by hand skips the re-check the merge step makes, and this is where that shows. Find the commit of the last green run with `gh run list --branch main --workflow <file> --status success --limit 1 --json headSha`, and name the pull requests merged since the last green run, read with `git log --first-parent --oneline <that commit>..origin/main`. Where no run has ever been green, name what merged since the first run instead. Sync fixes no code, so point to `/fix`. Where GitHub cannot be reached, or the project has no such workflow, say in one line that the check on `main` could not be read.

   Uncommitted work found here is the first finding after a red `main`, not an obstacle: say what it is and whose it seems to be, leave it exactly where it is, and never sweep it into a commit of your own or discard it to get a clean tree. Where `main` cannot be reached, work from the local copy and say so in one plain line.
2. Check for stale pieces before correcting their records. On every build
   path, read the open pieces' last-updated times from GitHub.
   List pieces untouched for at least 30 days once, in one short list by title.
   Ask once: "For each of these, is it still wanted, should it be closed as not planned, or is
   it done?" Change nothing on that list without a yes to the proposed action
   for that piece. A yes to closing one closes it through the gate,
   `python3 .agents/tools/gate.py drop <number> --reason "<their reason>"`.

   Silence leaves it as it is, and sync carries on without asking again. Age
   alone never closes or relabels a piece. If the dates cannot be read, say the
   stale-piece check could not be made; do not guess from the local printout.

   Correct the pieces to match reality, and append any changelog lines the work missed, dated. An entry waiting in `changes/` counts as written, so never add a second line for the same work. On a project with issues there is usually little to do, because a merged pull request saying `Closes #<number>` closes its own piece. Look for the exceptions: a piece in `state:building` that nobody is building, a piece still open whose work plainly landed, a piece kicked back at a caution whose acceptance has since been recorded. Say what you found rather than correcting it quietly. Closing a piece is the person's decision. Whatever somebody did on GitHub by hand stands, as the `setup-ai-build-kit` skill's `references/pieces.md` describes.

   Then run `python3 .agents/tools/gate.py report`. It names each open piece whose labels are out of order: no state, two states, a sub-label beside the wrong state, or a label from AI Build Kit's model, which it leaves alone. For each, say what you found and which state what happened supports: an open pull request that closes it means `state:in-review`, work saved on a branch for it with no pull request means `state:building`, and where nothing shows which, the earliest state on it, since an earlier state only asks for another look.

   Then let the person choose. The labels the gate owns are never written by hand, so a choice is made through a gate move where the gate has one, and otherwise by the person on GitHub, and a piece with no state is taken in with `gate.py capture <number>`. Where the gate refuses a move, tell the person its line in plain words and stop that move.

   Then run `python3 .agents/tools/gate.py tidy`, which takes the state, sub-state and review labels off every closed issue, such as a piece a person merged on GitHub. Say what changed, piece by piece, then refresh the printout.

3. Correct masterplan.md where reality moved. Load the `setup-ai-build-kit` skill's `references/masterplan-changes.md`, merge each landed piece's `## Masterplan change` that has not yet been applied, and move the trued-against mark to the saved state you checked. Read from the older of that mark and the last changelog entry, so an up-to-date history cannot hide a stale page. Never rewrite the build-path section directly; if the project's character has changed, rerun the fit check instead and let it produce the new section.

   Re-read every "rests on" clause in the masterplan against what it names,
   following the decision rules in the `setup-ai-build-kit` skill's
   `references/pieces.md`. When its support has gone, say in one line which decision lost its
   ground: "The rule that a job closes once rested on a test that no longer
   exists." Keep the decision on the page and ask what should settle it;
   never quietly remove a rule because its evidence went missing.

4. Check the plan still covers the page. Load the `setup-ai-build-kit` skill's `references/coverage-read.md` and compare the masterplan's promises against the pieces. Reconciling after an interruption or an outside contribution is exactly when a promise quietly loses its piece.

   On every build path, count the words in the masterplan's core sections.
   Leave out `Build path`, the optional `Key terms` and `How it stays running`
   sections, headings, comments and diagram source. More than 1,000 words is the
   working measure for roughly two pages. Above that, give one line once in this run:
   "The masterplan is longer than roughly two pages. Shall I move the detail
   about individual pieces onto those pieces?" Move detail only with a yes,
   keeping every present promise and decision on the masterplan. Otherwise,
   leave it intact and carry on. On a yes, detail about a piece goes onto that
   piece, and lasting technical design goes to its `docs/<concept>.md`, one
   concept to a file, listed in AGENTS.md, never into a new catch-all document.
   At or below the measure, say nothing.

   Then read the project's own documents against it. Load
   `references/document-read.md` and check the README and every document
   AGENTS.md points at for a file, link, command or setting that no longer
   exists. Offer to correct only the stale name, or to file it as a piece.
5. Identify anything left open: an unresolved recheck trigger from the build-path section, flagged work still waiting, or interrupted manual setup. Say what's open rather than closing it quietly. Where flagged work was built during the period being reconciled, check the build-path section carries an `Accepted:` line for it; if the work happened and the line is missing, say so rather than writing one now, because an acceptance recorded after the fact is a record of nothing.

   Read each run's state file under the main folder's `.agents/runs/`, the first worktree git lists, as the `implement` skill's `references/running-longer.md` describes. Where there is an unfinished run in `.agents/runs/`, one whose state file still shows a piece waiting or being built, name how far it got and offer to resume it with `/implement queue`; never resume it here, since sync builds nothing. Remove the folder of a run whose every piece is merged, closed, given back or kicked back, counting a piece the run skipped or sent back to shaping as closed to it, and say so in one line. A recursive delete is refused, so that line gives the person the command that removes the folder, with its path. Git ignores the folder, so removing it changes nothing saved.

   Where the project has worktrees under `.agents/worktrees/`, clear away each one whose pull request has merged or closed, with `sh <installed implement skill>/scripts/worktree.sh tidy`, as the `implement` skill's `references/running-longer.md` says. It removes a worktree only when it holds no unsaved work, and never forces the removal. Pass on each line it prints: a worktree holding unsaved work is kept and named with what is unsaved.
6. Keep the check on the pull request honest. If the way the project installs or tests has moved, update the job the capability profile's `Project check:` line records (`.github/workflows/checks.yml`, job `project-check`, where that line names no file) so it runs the project's real commands, the same ones AGENTS.md's stack section names. Touch only that job. Where the recorded file no longer exists, or no longer has the recorded job, say that the recorded project check no longer exists and ask which workflow is the check now. Edit nothing until that is answered, then correct the line. An older project may still carry a separate source-validation job and repository conditions; leave those unchanged. A check still running the placeholder, or the wrong commands, is worse than no check at all because people believe the green tick.
7. Bank what was learned. A mistake the agent has now made twice becomes one line in AGENTS.md, so it stops recurring. A pattern the user approved more than once becomes a project skill, if it earns one. Keep AGENTS.md lean: point at documents instead of repeating them, and delete lines that no longer pay their way.
8. Save the corrections the way a piece is saved. Sync changes documents only, but the documents are shared, so the corrections take the save route the build path already requires: the three routes section-builder names, with no fourth for records. On the checkpoint route, commit on the current branch and state the saved checkpoint. On the pull-request route, cut a short-lived branch from the up-to-date `main`, stage only the files sync itself changed, commit, push, open a pull request titled after the reconciliation, and run the project check. The paragraph from step 9 is the body of that pull request. It is the proposal step 1 asks for, put where the person can read it and say yes. Merge it only as the `section-builder` skill's `references/merge.md` says, and never delete the branch yourself. A correction committed straight onto `main`, or left uncommitted, is a second kind of drift, since the records now disagree with what is saved. The project's first upload waits for the yes section-builder's "The first upload" describes. Where GitHub cannot be reached, save on the branch and note the step that did not happen in one plain line; a missing step is not a hazard and earns no warning. A label changed on GitHub itself in step 2 is not a file and needs no branch.

   Fold any changelog files still waiting into the history as part of this save. The merge step folds each piece's file as it merges, so what waits here is what a merge made on GitHub by hand left behind. On the branch being saved, which on the pull-request route is the one just cut from `main`, run this skill's `scripts/fold-changes.py` from the project root. It writes each file in `changes/` into `CHANGELOG.md` as one line, newest first under the day each file reached `main`, deletes the files it folded, and stages that removal; stage `CHANGELOG.md` with the other corrections. Only files on the branch being saved are folded, so the fold never puts an unmerged piece into the history, and a file nobody has committed stays where it is. Where an earlier records pull request that folded files is still open, say so in one line and do not fold again until it merges, since a second fold would write the same entries twice. Founding, /ship, /maintain and /sync write `CHANGELOG.md` directly, since none of them runs alongside another. Only section-builder and /fix write to `changes/`, because pieces are what get built side by side.
9. Say in one short paragraph what was corrected, so the user knows what had drifted.

## Done when

A teammate could start tomorrow from the documents alone, anything learned is written where the next session will read it, and nothing was closed quietly that should have stayed visible.
