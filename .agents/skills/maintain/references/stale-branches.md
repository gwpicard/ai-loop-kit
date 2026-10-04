# Old branches

A branch is a separate line of work. Once its work has reached the default
branch, the branch has done its job, but nothing removes it. Old branches build
up on the person's computer and on GitHub, and a long list hides the few still
in use. This step names the branches that can go and gives the command that
removes each one. It never removes a branch itself.

## Where it applies

At every monthly visit, on every build path. The GitHub half runs only where
the project has a remote called `origin`. Where it has none, say that only this
computer was checked.

## The default branch

Read the default branch, the one work merges into, with
`gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`. Without
the GitHub tool, read it from `git symbolic-ref refs/remotes/origin/HEAD`. With
no remote, it is `main`, or `master` where there is no `main`. Where none of
these gives an answer, say the branch check did not run, and carry on with the
visit.

Where the project has a remote called `origin`, run `git fetch origin`, so
that Git can compare GitHub's branches with the default branch. Do not add `--prune`. It deletes Git's own record of branches
already gone from GitHub, and this step deletes nothing.

## Branches that are never listed

- The default branch.
- A branch that is checked out, in this folder or in another working copy of
  the project. `git worktree list` names them all, and Git refuses to remove a
  branch that is checked out.
- A branch with an open pull request. `gh pr list --state open --json
  headRefName` names them.
- A branch the project's own AGENTS.md or masterplan says stays, such as one a
  release is published from. The kit names no such branch in a project, so
  never set one aside because of its name alone.
- A branch GitHub protects from deletion. For each branch that would otherwise
  be listed, ask `gh api repos/{owner}/{repo}/branches/<name> --jq .protected`
  and `gh api repos/{owner}/{repo}/rules/branches/<name>`. The branch is
  protected when the first answer is `true`, or when the second holds a rule
  whose `type` is `deletion`. Any other rule does not count. A rule set can
  cover every branch and only ask for signed commits, and that says nothing
  about whether a branch can go. Where these calls cannot be made, list the
  branches anyway and say that protection was not checked.

## Two groups

**Git confirms it.** Every commit on the branch is already in the default
branch.

- On this computer: `git branch --merged origin/<default>`, or the local
  default branch where there is no remote.
- On GitHub: take the list of branches from `git ls-remote --heads origin`,
  which asks GitHub directly. For each one, run
  `git merge-base --is-ancestor <commit> origin/<default>`. Do not read Git's
  own list of GitHub's branches instead. It can still hold branches somebody
  has already deleted there.

**GitHub records it as merged, and Git cannot confirm it.** A pull request
merged by squashing or rebasing puts the branch's changes into the default
branch as new commits. Git then finds the branch's own commits missing, and
`git branch --merged` leaves the branch out. So for each branch Git did not
confirm, ask
`gh pr list --state merged --head <name> --base <default> --json number,headRefOid`.

A branch joins this group only when its last commit is the last commit of that
merged pull request, or comes before it:
`git merge-base --is-ancestor <branch> <headRefOid>`. Where Git cannot find
that commit, the branch joins no group.

A branch with commits added after its pull request merged holds work the
default branch may not have. It joins neither group. Name each such branch in
one line of the report, because GitHub shows it as merged and it is not.

Where the GitHub tool is missing or signed out, this second group cannot be
read. Say so in one line rather than leaving it out in silence.

## The commands

- On this computer, first group: `git branch -d <name>`. Git refuses this
  command when the work is not merged, so it cannot lose anything.
- On this computer, second group: `git branch -D <name>`. Git cannot confirm
  the merge, so the careful command would refuse. Say that the capital `D`
  removes the branch without that check, and that it is safe here only because
  GitHub records the same work as merged.
- On GitHub, either group: `git push origin --delete <name>`. Where the branch
  had a pull request, that pull request's page on GitHub keeps a button that
  restores the branch.

Never run one of these commands. The person runs each one, and chooses which.

## What it cannot tell

- Whether somebody still means to use a branch. Merged work is the only sign
  this step reads.
- For the second group, that every change is still in the default branch. The
  record says the pull request merged. A later change could have undone part
  of it.
- Anything about a copy on a teammate's computer. Removing a branch here or on
  GitHub leaves theirs alone.
- Anything about a branch that is not merged. That is outside this step.

## What the person sees

When no branch qualifies and nothing was left out, say nothing. A branch counts
as left out when it would have qualified but was set aside: because GitHub
protects it from deletion, or because it holds work added after its merge. A
group that could not be read, or a protection check that could not be made,
counts too. Each one gets its line in the report, so a report is never silent
about a branch it set aside.

Otherwise, give one short report. It keeps this computer and GitHub apart,
names the default branch by its real name, and gives each branch its command
on its own line:

```
Some branches have finished their work, and their changes are already in main.
You can remove them. I have not removed anything.

On this computer, every change confirmed in main:
  fix-login        git branch -d fix-login

On GitHub, every change confirmed in main:
  fix-login        git push origin --delete fix-login

GitHub records these as merged, but Git cannot check every change, because
the merge combined the branch's changes into one. The capital D removes the
branch without Git's own check. It is safe here only because GitHub records
the same work as merged:
  new-report       on this computer: git branch -D new-report
  new-report       on GitHub: git push origin --delete new-report

GitHub shows this branch as merged, but it has work added after the merge.
I have left it alone:
  export-fix

GitHub protects this branch from deletion, so I have left it alone:
  release

I can tell that a branch's work reached main. I cannot tell whether somebody
still plans to use it.
```

Leave out a group or a line that is empty. Never add a branch to fill the
example.
