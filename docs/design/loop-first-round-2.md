# Loop-first redesign, round 2

The second round of decisions for the loop-first redesign. Read
[loop-first-redesign.md](loop-first-redesign.md) first: it holds the
principle, the first round's decisions and the piece contract, and all of it
still stands. This note adds nine decisions, one for each slice from 13 to 21.

The evidence came from two external projects' usage reports, written after
each project had used the kit for several days. One was a skill library with 21
pull requests in four days, the other a report generator with 36 pull requests
in five. Neither person typed `/sync` or `/ship`, and both reports described the
same gaps from different sides.

## Decisions

### 1. The fold at the merge

Each piece writes its changelog entry to its own file in `changes/`, and until
now only `/sync` or `/ship` folded those files into `CHANGELOG.md`. On both
projects the files would have piled up for ever. So the merge step folds them,
inside the pull request being merged and just before it merges, after taking in
the latest `main`. Merges are made one at a time, which is why this cannot
conflict: a fold made when a pull request opened could. `/sync` and `/ship`
keep their fold for files a merge made on GitHub by hand left behind.

### 2. `Goes live: not hosted`

A tool with no live address, such as a library or a command-line tool, records
that in the masterplan. A merge on such a project is never a launch, and what
`/ship` makes for it is a release: a Git tag with a GitHub release.

### 3. Bringing a pull request up to date and checking it again before it merges

No pull request merges on a check that ran against an older `main`. Before every
merge the branch takes in the latest `main` and the check runs again, whether
or not there is anything to fold. The kit stops promising that a group can merge
in any order without that step.

### 4. Worktree links for ignored build files, and living beside another tool's worktrees

A run's worktree gets, as links, the ignored files a build needs that carry no
secret, so a piece builds there as it would in the main folder. Confidential
files never reach it. The kit touches only its own worktrees, and a run started
inside another tool's worktree still works.

### 5. An adopted project's own CI as the project check

Where a project the kit adopts already has working CI, that CI is the project
check. Founding records which workflow and job it is and adds no failing
placeholder beside it, and every skill that reads or edits the check uses that
record.

### 6. One story about the walk-through and the person's try

Every document tells the same story. The agent walks through each piece and
records what it saw. The person decides what merges and what goes live, and
tries a piece themselves whenever they opt in. Nothing says the person must try
each result before it is saved.

### 7. The walk-through that can see

The walk-through looks at what the person would see: a screenshot through a
browser tool for a web page, and each page rendered to an image for a file.
Founding records which of these the machine can do. A walk-through that could
not look sends the piece to `to check` for the person.

### 8. A run that asks before building a group in parallel

On Claude Code, a run asks before it starts whether to build a `Go together`
group's pieces at the same time, warns that this uses more memory, and builds
one at a time unless the person says otherwise. Each piece still gets every
step of a single build, and merges one at a time after the check runs again.

### 9. A confirmation box on a merge that goes live

Where the `Goes live:` line says `on every merge`, Claude Code shows its
confirmation box before any `gh pr merge`, so no merge goes live without a
person seeing it, whatever the session was told. A project whose merges reach
only a preview, or that is not hosted, keeps the written rule alone.
