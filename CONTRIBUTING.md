# Contributing

AI Loop Kit is being built, and its maintainer sets the order of the work. Read
`docs/DESIGN.md` to see how the kit works. A feature joins the kit only when a
real run shows it is needed.

## Report a problem

Use the bug form. Say what you expected, what happened and the shortest steps
that show it. Remove passwords, tokens, personal data and private project
details before you post.

Do not report a security problem in a public issue. Read `SECURITY.md`.

## Suggest an idea

Use the idea form. Describe the situation where you would use it and what you
would expect to see. You do not need a technical design.

## Pull requests

Work merges to `main`. `stable` is the default branch and only a release
moves it. Every pull request must name `main` as its base: use
`gh pr create --base main`. A check refuses pull requests aimed at `stable`.
Keep each pull request to one slice, with evidence that it works. A person
reads and merges every pull request.

A `Closes #N` line does not close the issue when the base is not the default
branch. The person or the run closes the issue after the merge.

Run `tests/run-all.sh` before you ask for a review. Read `AGENTS.md` for the
house rules. They apply to people as well as agents.

## Releases

Between releases, `main` keeps the last release number in
`kit/.claude-plugin/plugin.json`. The release pull request sets the next one.

Each version has its notes in `docs/release-notes/vX.Y.Z.md`, written to
`.agents/maintainer-skills/release-notes/SKILL.md` and reviewed before the
release pull request. `CHANGELOG.md` keeps one short entry for the version
that links to the notes, and the GitHub release body opens with the notes,
word for word. Before a release, run
`.agents/maintainer-skills/review-public-docs/SKILL.md` over the shipped docs.

After the maintainer approves publication, publish and verify the release
from `main`, then move `stable` with:

```sh
GITHUB_REPOSITORY=gwpicard/ai-loop-kit \
  .agents/tools/promote-stable.sh vX.Y.Z <full-release-commit>
```

Replace both placeholders with the published tag and its full commit hash.
The tool checks that the release is published, that its tag names the
commit, and that `stable` reads back at that commit after the write. It
refuses draft releases, prereleases and updates that would overwrite work.
The maintainer investigates a refused promotion before trying again.
