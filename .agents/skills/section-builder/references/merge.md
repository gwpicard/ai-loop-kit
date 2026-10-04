# Merging a pull request

The one merge step for every route. section-builder, `/implement`, `/fix`,
`/ship` and `/sync` load it whenever a pull request is ready to merge, and none
of them keeps its own copy of the rule. It covers the merge, and the wait for
the project check that the merge and section-builder's step 8 share. The save
that opened the pull request is section-builder's step 8, and what happens to
the piece afterwards is its step 9.

## The yes that names it

A person decides whether to merge. Before a merge, name each pull request in
one plain line: its number, its title and what it changes for the person. Then
ask for a yes that names the merge, for example: "Say yes to merge 12, which
adds the invoice list." Merge only when the person's reply plainly covers that
merge.

A reply that names several pull requests, such as "merge 1, 2 and 4", counts
for each one it names and for none it leaves out. Where the person's own words
already named the merge, as in "merge both and put it live", that is the yes:
do not ask again. A yes to going live, to a hosting step, or to any question
asked before the merge was named does not cover it: ask again, and merge
nothing until they answer. A no leaves the pull request open.

## Waiting for the check

Wait with `gh pr checks <number> --watch --fail-fast`. It returns once every
check has finished or one has failed. Where the coding agent limits how long a
command may run, run it in the background or with the agent's own tool for
watching a command, and read its result when it ends. Never a loop of `sleep`
calls: Claude Code refuses them, and a hand-made loop is easy to misread.

Read the result from the command's final output and exit code, never from a
watch that ended early. Exit code 8, or an error naming an unknown option,
means the check is not finished. Where `gh` names `--fail-fast` as unknown, run
the watch again without it. Where `gh` is too old for `--watch`, run
`gh pr checks <number>` again when the agent's own watch tool says time has
passed.

Three cases end without a green check:

- Where `gh pr checks` reports that no checks ran, say so plainly, and never
  call the pull request green.
- Where a check never finishes, the watch runs until the agent's own time limit
  ends it. Say the check has not finished, name it, and leave the piece in
  `to check`.
- Where GitHub cannot be reached while waiting, say the check could not be
  read, and call nothing green.

## Before any merge

Merge only a pull request whose project check is green. Never merge over a red
check: say it is red, and take it to `/fix`.

A green check says the pull request passed against the `main` it was cut from.
Once another pull request merges, that answer is out of date, and two pieces
that each pass alone can break `main` together. So every merge, fold or no fold,
first brings the branch up to date with `main` and checks it again. Once the
merge is approved, run this skill's `scripts/bring-up-to-date.sh`, as "The fold
before the merge" says, and wait for the project check on the commit its last
line prints, as "Waiting for the check" says. Merge only on green. The
check waited on is the project check on GitHub, never a run on this computer,
since the check on GitHub is the one the green tick reports.

Where `main` has not moved since the branch's last check and nothing is left to
fold, the script makes no commit and prints the head the branch already has.
The green check already on that head stands, with no second wait. A piece's own
file in `changes/` is always left to fold, so this covers only a pull request
with no changelog file, such as one opened outside the kit.

When the update stops the merge, nothing merges:

- Where the merge from `main` conflicts, the script exits 1 and names each
  conflicting file. Name the files in the reply, add one comment to the pull
  request naming them with `gh pr comment <number>`, and take the piece to
  `/fix`, as a red check is.
- Where the check turns red only after `main` was taken in, say that the piece
  passed alone and fails with what merged since. Name the pieces merged since
  the branch's last green check, read with
  `git log --first-parent --oneline <old base>..origin/main`, where the old base
  is `git merge-base <head before the update> origin/main`. Name each by its pull
  request's title, from the merge commit's subject, or from its body where the
  subject names only the branch. Take it to `/fix`.
- Where `origin` cannot be reached, the script exits 2 and nothing changed.
  Give the one line "How the merge is made" gives.

A pull request that stacks on another piece's branch is never merged before its
base. Where the base is still open, say which to merge first, and merge the base
first when the person's yes names both. Once the base has merged, check that the
stacked pull request now aims at `main`, and change it with
`gh pr edit <number> --base main` where it does not. Then bring it up to date
and check it again, as above, before you merge it.

## The fold before the merge

Each piece leaves its changelog entry in its own file in `changes/`. The merge
is what folds those files into `CHANGELOG.md`, so the history stays whole
without anybody typing a command. After the yes that names the merge, or under
pre-approval, and before `gh pr merge`:

1. On the pull request's branch, take in the latest `main` with a merge commit,
   never a rebase or a force push.
2. Fold every file now in `changes/` into `CHANGELOG.md`: the piece's own, and
   any a merge made elsewhere left behind.
3. Commit the fold as `Fold the changelog`, push the branch, and wait for the
   project check on that new commit, as "Waiting for the check" says.
4. Merge only when that check is green. Red means nothing merges: say so and
   take it to `/fix`, as the rule above says.

Where the check has not reported, because it is queued or GitHub is slow, the
merge waits: say so once in the reply, and never merge on an unfinished check.

Merges are made one at a time, so the fold always runs on a branch that holds
everything already merged. That is what keeps pieces built side by side free of
conflict: while they are built, pieces touch only their own file in `changes/`,
and only the merge writes their entries into `CHANGELOG.md`. A fold made when
the pull request opened would conflict whenever two pieces started from
different states of `main`.

This skill's `scripts/bring-up-to-date.sh <folder>` does steps 1 to 3 in the
folder given, which must be on the pull request's branch. It first undoes, with
a new commit, any `Fold the changelog` on the branch that `main` does not hold
yet, so an older fold never merges beside a newer one. An entry
`CHANGELOG.md` already holds is never written again, which covers a stacked
pull request whose base was merged by squash. A retry after a session
died, or after another merge folded the same waiting files, therefore writes
each entry once. Its last line is the commit the check must pass on. Its exit
decides the reply:

- 0: wait for the check on that commit.
- 1: the merge from `main` conflicted. The branch is left exactly as it was, and
  the script names each conflicting file. Nothing merges: name the files and
  take it to `/fix`.
- 2: `origin` could not be reached, or the folder is not on a branch or holds
  uncommitted work. Nothing changed. Where GitHub could not be reached, give
  the one line "How the merge is made" gives.
- 3: the push was refused, usually because somebody pushed to the branch
  meanwhile, or this computer holds commits on the branch that the pull request
  does not. The script's message says which. Nothing merges: say the merge
  waits and why. After a refused push, asking again takes their commit in.

Where GitHub then refuses the merge because `main` moved after the check,
run the step again, so the fold is made on the newer `main`.

Where an earlier records pull request that folded files, other than the one
being merged, is still open, pass
`--no-fold` and say so in one line, so the same entry is never written twice.
The branch still takes in `main`.

Run the script in the first of these that fits:

- in the piece's worktree under `.agents/worktrees/` when it has one;
- otherwise in the main folder, when the main folder is on that branch with no
  uncommitted change;
- otherwise in a worktree opened for the merge with the `implement` skill's
  `scripts/worktree.sh`, as
  `worktree.sh open <issue number>-<short name> <branch> origin/<branch>`, so a
  branch not held on this computer is made from the pull request's own
  branch and never cut fresh from `main`. A pull request with no issue, such
  as a records pull request, uses its own number in place of the issue's. `worktree.sh tidy` clears it away
  once the pull request closes.

The main folder is never switched to another branch for a merge, and a folder
holding uncommitted work is never used, so the person's work is never swept
into the fold. Where the folder already on that branch holds uncommitted work,
whether the piece's own worktree or the main folder, no second worktree can
hold the same branch: the merge waits, and the reply names what is unsaved
there.

## How the merge is made

Make an approved merge on the pull request itself, with `gh pr merge <number>`.
Never merge the branch on this computer and push `main`, and never delete the
branch yourself: the project's settings delete a merged branch. Where GitHub
cannot be reached, nothing merges. Say in one line that the merge waits, that
it can be asked for again once GitHub answers, and that the person can merge it
on GitHub themselves.

## When a merge goes live

The masterplan's "How it stays running" section records how the tool goes live
in its `Goes live:` line. `through /ship` is the kit's default: a merge reaches
a preview, and `/ship` promotes it to live. `on every merge` means the host puts
each merge to `main` live, so the merge is itself a launch. `not hosted` means
no server runs the tool for people to reach: people install it, copy it, or run
it on their own computer.

On `not hosted`, a merge is never a launch. The ask never says "this goes live
now", and no first-launch checks run. What goes live for such a tool is a
release, which `/ship` makes.

Where AGENTS.md names a recipe and the line says `not hosted`, the recipe wins,
since a recipe is a place the tool runs. Read its going-live section instead:
where it says a change to `main` goes live, treat the merge as `on every
merge`, and otherwise as `through /ship`.

Where the line is missing, read the going-live section of the project's recipe.
Where it says a change to `main` goes live, treat the merge as `on every merge`.
Otherwise ask, in the reply that asks for the merge, which of the three it is:
the merge reaches a preview, the merge goes live, or nothing is hosted. Treat
it as going live until the person says it does not. Write
their answer into "How it stays running" as the `Goes live:` line, with the
merge's save or the next one, so the question is asked once for each project.
In the same save, set the confirmation box as "The confirmation box on a merge
that goes live" says.
Where the recipe settled it with no question asked, write the line the same way,
`on every merge` or `through /ship`, and set the box with it.

On `on every merge`, the ask says so, as "this goes live now": for example, "Say
yes to merge 12, which adds the invoice list. This goes live now." Where no live
address is recorded in "How it stays running", this merge is the first launch.
Before asking for it, load the `ship` skill and run its first-launch checks on
the current build path, up to going live. The merge is then that path's
going-live step, and `/ship` records what it found, the live address included,
so a later merge is not taken for a first launch. Where `/ship` itself makes the
merge, it has already run those checks, and the merge step does not run them a
second time.

## The confirmation box on a merge that goes live

Claude Code can show its own confirmation box before a command runs, and it
shows it whatever the session was told. Two rules make it ask before a merge.
The rules sit in the `setup-ai-build-kit` skill's
`templates/merge-ask-rules.json`. Take them from that file, never from memory. The same skill's
`scripts/merge-ask-rules.py` writes them, so every step that records the
`Goes live:` line changes the file the same way.

Whoever writes `Goes live: on every merge`, whether founding, this step or
`/ship`, runs
`python3 <installed setup-ai-build-kit skill>/scripts/merge-ask-rules.py add .claude/settings.json`
from the project root, in the same save. It adds only the rules that are missing
to the end of `permissions.ask`, creates that list when there is none, and keeps
every other entry and setting as it is. Then say one line: "Claude Code will now
show a confirmation box before each merge, because every merge goes live."

Where a recipe wins over a `not hosted` line and says a change to `main` goes
live, as above, the merge goes live, so run `add` there too. Whoever writes any
other value runs the same command with `remove`. It takes
out exactly the template's rules, and the `ask` list too when that leaves it
empty. A rule the person wrote stays. Where it took something out, say one
line: "Claude Code will no longer show its confirmation box before a merge,
because a merge no longer goes live."

The script's exit decides the rest:

- 0: done. It prints each rule it added or took out, and nothing when nothing
  changed: say nothing then.
- 1: the file is not valid JSON, and it was left untouched. Write nothing, and
  say in the reply that `.claude/settings.json` could not be read, so the box
  was not set up.
- 2: the project has no `.claude/settings.json`, because it does not use Claude
  Code. Write nothing, and leave the line out of the reply.

The box is a second guard. The written rule, a yes that names the merge, still
holds on every route, and on other coding agents it is the only one. The
`setup-ai-build-kit` skill's `references/blocked-commands.md` lists the merges
the box does not catch.

## Pre-approval for a run

Before a run starts, the person may say that pieces which pass may be merged.
Write that as `merge_preapproved` in the run's state file. It holds for that run
alone and ends with it, so it never reaches a later run or a piece built outside
one. It covers merges that reach a preview. Nothing goes live without the
person's yes naming it, or `/ship`. A merge on a tool that is `not hosted` puts nothing
live, so pre-approval covers it too.

With pre-approval, merge a piece only when all six hold:

1. its project check is green on the commit brought up to date with `main`;
2. its review found nothing worth stopping for;
3. its pull request flags no choice for the person to confirm, and names nothing
   the walk-through could not see;
4. it touches no sensitive area named in the build-path section, accepted or not;
5. the person has not opted in to check it: the piece has no `Waiting on you:
   try it` line, and `.ai-build-kit-maintenance` has no `check-myself|yes` line;
6. its merge would not go live: the `Goes live:` line says `through /ship` or
   `not hosted`. Where it says `on every merge`, where the recipe says a change
   to `main` goes live, or where the route is not known, the merge would go
   live.

A pre-approved run never meets the confirmation box, because condition 6 keeps
it from making a merge that goes live.

A piece that fails any of the six is not merged. It stays in `to check` for the
person, and the run's report names the condition it failed. The rule for a
stacked pull request holds under pre-approval too.
