---
name: release-notes
description: Write or revise a release's public notes from the changes it carries, to the maintainer's release-notes standard. For a maintainer before the release pull request, or when older notes need work. Load it by its path.
---

# Release notes

`references/framework.md` is the standard. Read it in full before you write.
It says how to establish each change from the evidence, which fourteen writing
problems to look for, how severe each one is, and when a note is acceptable.

## The reader

A person who builds software with Claude Code or Codex on a GitHub project and
reviews the pull requests the kit opens. They can install a tool such as `gh` or
`uv`, and they expect the kit to do the rest. They are a capable professional.
Write to an experienced technical writer's standard: natural, precise and
accessible. Use an established word, such as approval, configuration or branch
protection, where it is the right word. Keep a command, setting or check name
where the reader types it or sees it, such as `Base branch:` or `gate.py sync`.

## Fixed constraints

These override the framework where the two conflict.

1. British spelling, no contractions, no em or en dashes.
2. No pull request or issue numbers, and no links to them. No cost or price
   figures. No attribution lines.
3. Keep every action an existing user must take. Give each command and each
   line to type word for word.
4. Add no fact the evidence does not support. Where the evidence cannot settle a
   meaning, ask the maintainer rather than guess.

## Evidence

For a new release, read the merged pull requests since the last tag: their
descriptions, their diffs and their tests. For an older release, read the
repository at its tag, `git log <previous-tag>..<tag>` and the merge commits,
which carry the pull request descriptions. A commit title alone is not enough.
Field results in `tests/field/RESULTS.md` are evidence for what was tested.

## Shape

Write the version's file in `docs/release-notes/`, named `vX.Y.Z.md`, in this
order:

1. One sentence on what the release does for the reader.
2. Who gets each change, where that is not every project. Say it early: an
   existing user who expects a change and does not get it will think the
   update failed. Name the setting or backend that turns a change on.
3. `## Updating`: the command, whether to start a new session, any action the
   person must take, and whether their data changes.
4. `## What changes`: a numbered list, most important first. Each item has a
   short bold name, what changed and, where the evidence supports it, why it
   matters. Say which parts are still previews.
5. A short section on what was tested and what is not proven yet, where there is
   something real to say. Leave out conditions that exist only on the
   maintainer's computer.

`CHANGELOG.md` gets one short entry for the version that links to this file.
The GitHub release body opens with this file, word for word.

## Review

Before the release pull request, give the file to one fresh reviewer with this
skill and the evidence. Ask it to report findings by the framework's severity
levels, and to check every claim against the evidence. Fix each Critical and
Major finding.

## Done when

Every claim traces to the evidence, every required user action is present word
for word, and the fresh reviewer reports no Critical or Major finding.
