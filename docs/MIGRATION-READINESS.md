# What is entangled between the two repositories

Preparation for retiring this repository and making `gwpicard/ai-build-kit` the
single source.

This document chooses nothing and moves nothing. It sets out what is actually
tangled, so three decisions can be made from it without opening the repository.
Everything here was read on 23 August 2026 and is checkable.

## The three decisions

1. **What sits at the root of the merged repository?** Four paths mean two
   different things today. See below.
2. **Does this repository's history become public?** The audit under B3 says it
   safely could. That is not the same as deciding it should.
3. **What becomes public that is not public now?** The tests, the maintainer
   guide, and the Humanizer skill.

Nothing else about the move can be planned until these are answered. All three
now are, and the answers with their reasoning are recorded on the migration
issue. Where an answer supersedes something below, the text says so.

---

## B1. The four paths that mean two things

The release allowlist carries nine rename mappings, on top of the fourteen that
rebase the canonical skills under `agent-plugin/skills/`. Four of the nine are
genuine collisions: a file exists at that path here **and** in the public
repository, with a different meaning in each.

| Path in the public repo | What it is there | What it is here |
|---|---|---|
| `AGENTS.md` | the instruction file a **project** receives | how to maintain **the kit** |
| `README.md` | the public shop window | settled: the root now carries that same readme |
| `.github/workflows/checks.yml` | the **project's** own check | settled: this repository's CI is `source-checks.yml` now |
| `.claude/settings.json` | a project's settings, **with** session-start wiring | the maintainer's own, which must never have that wiring |

Those four renames are why two repositories work at all. One file cannot carry
both meanings, so the layout decision is really a decision about where each half
of each pair lives.

**Three of the four remain.** `README.md` is settled: the root is the kit's own
now, carrying the installation-facing readme that ships unchanged, with the
contributor-facing instructions in `AGENTS.md` beside it. The five paths that
were never collisions, `CONTRIBUTING.md`, `SECURITY.md`, `.github/ISSUE_TEMPLATE`,
`.claude-plugin` and `agent-plugin`, have moved to their permanent homes, and
`starter/` is gone. The allowlist carries them as ordinary pass-throughs rather
than renames.

Everything else in the allowlist passes through unchanged and already means the
same thing in both places: the fourteen skills, the generated adapters, the guard
and hook folders, `CLAUDE.md`, `GEMINI.md`, `WORKFLOW.md`, `LICENSE`,
`.gitignore`, `.env.example` and the three shipped documents under `docs/`.

## B2. What exists only because there are two repositories

**Five workflows**, every one gated on the repository it may run in:
`source-checks.yml`, `maintainer-branch-check.yml`, `prepare-release.yml`,
`publish-starter.yml` and `release-drafter.yml`. Each gate now names both this
repository and the one the kit will live in, so the same file works on either
side of the move. Naming only the destination would skip every job today, and a
skipped job reports as nothing wrong. The old name of the source check is gone,
so it can no longer collide with the project template.

**A GitHub App and its credentials.** `publish-starter.yml` authenticates as an
App using the `STARTER_APP_CLIENT_ID` variable and the `STARTER_APP_PRIVATE_KEY`
secret, with Contents and Workflows read-and-write on the starter repository
only. The normal workflow token cannot write to another repository, which is the
sole reason the App exists. One repository removes the need for it.

**The two-stage publish.** `prepare release` assembles and attaches an archive;
undrafting the release fires `publish-starter`, which rebuilds the tagged source,
compares it against that archive, and only then creates the credential. With one
repository, `build-release.sh` stops generating another repository's tree and
becomes a producer of a release artefact.

## B3. The history audit

This repository has been private for its whole life, 311 commits.

**Scanned every commit** for the shapes of GitHub tokens, OpenAI keys, AWS keys,
Slack tokens and PEM private-key headers. **No matches.**

**Listed every file ever added** and looked for anything sensitive by name: no
`.env`, no `.pem`, no `.key`, nothing named for a secret, credential, token or
password. One file matched on name alone, a retired roster template added in
June and removed when the fit check was rewritten. It was empty:

> Each person adds a line below during setup, commits it, pushes, and pulls the
> others.

It never held a name.

**So the history could be published safely on this evidence.** The maintainer
has since decided not to publish it, so this stands as a finding rather than a
recommendation. Two limits worth stating. This looked for known secret shapes, not for anything embarrassing or
private in prose, and the commits carry the maintainer's own name and email
throughout, which becomes public along with everything else.

## B4. What reads as private in files that would become public

**Nineteen issue references** across sixteen files, all in `.agents/tests/` and
`docs/MAINTAINING.md`. Both trees become public under every layout.

They were not secret. They were a comprehension problem: a number means nothing
to a stranger, and worse, it points at an unrelated issue in the public
repository's own numbering.

**Settled and done.** Every one has been removed, and the standing rule is now
that a number belongs in an issue, a pull request or a changelog, and nowhere
else. Documentation and comments say the thing instead.

## B5. The bridge, and the question nobody can answer from here

`update-manifest.txt` and the generated `.ai-build-kit-managed` existed so a
project installed **before** the shared installer could take one more compatible
update. Installations since then record their source in `skills-lock.json` or in
Claude's plugin record and never read the managed list.

v0.1.0 was never tagged or released publicly at all, so the earliest release a
project could have installed from is v0.1.1. The window is one release wide, not
two.

**Settled, and done.** The bridge is retired. `update-manifest.txt`,
`update-kit.sh`, the generated `.ai-build-kit-managed` and the rehearsal that
drove them are all gone, so none of that machinery moves. What replaced the
question: a project older than the shared installer reinstalls once with
`npx skills add gwpicard/ai-build-kit`.

The paragraph below is kept because it records why the question was open, and
because the reasoning is what a later reader will want if somebody turns up
running v0.1.1.

**Nothing in either repository can answer that.** The kit collects nothing about
who is running it, which is deliberate. It is a question for the maintainer's own
knowledge of who installed before that model, and it should be answered before
the layout is chosen, because the answer changes how much moves.

## B6. What a migration must not break

- **Public tags and Releases v0.6.1 through v0.10.0.** `/maintain` reads the
  latest Release's notes at `gwpicard/ai-build-kit` to offer an update, so a
  renumbered or orphaned tag breaks the update path for every live project.
- **`.ai-build-kit-version` at the public root**, which is how a project knows
  what it has and how `update-kit.sh` decides whether an update applies.
- **`.ai-build-kit-managed`**, until the bridge is retired. That decision has
  since been taken and the bridge goes, so this constraint expires with it.
- **Every public tag.** Legacy projects use their current archive as the common
  starting point when comparing local changes against a new one, so losing one
  breaks that comparison. The archive a project can actually reach is the one
  GitHub generates from the tag. No public Release carries an uploaded asset,
  and the `ai-build-kit-vX.Y.Z.tar.gz` built by `prepare release` is attached to
  this repository's own Releases, which are private. That archive is the handoff
  between the two publish stages rather than anything a project downloads, so
  archiving this repository does not take a project's starting point with it.
  Losing a public tag would.
- **The plugin marketplace and installer entry points**, which read the
  repository tree directly at `gwpicard/ai-build-kit`. A layout that stops the
  root being the installable kit breaks both, and that is the strongest
  constraint on decision one.

---

## What this does not cover

The migration itself: choosing a layout, moving files, rebuilding the release
machinery, retargeting CI, moving issues, and archiving this repository. That is
a separate piece of work, and it starts once the three decisions are answered.
