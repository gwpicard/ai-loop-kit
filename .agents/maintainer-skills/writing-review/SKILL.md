---
name: writing-review
description: Review public-facing writing for artificial simplicity, vagueness, awkward phrasing and lost precision, and propose rewrites that keep the meaning. For pull request descriptions, issue text, release notes, documentation and kit guidance. Load it by its path.
---

# Writing review

`references/framework.md` is the standard. Read it in full before you review.
It names twelve writing problems, how to fix each one, and when a rewrite is
an improvement.

## What it covers

Every text a reader outside this session will read: pull request descriptions
and comments, issue text, release notes, `CHANGELOG.md`, `README.md`,
`docs/DESIGN.md`, `CONTRIBUTING.md`, and the Markdown guidance under `kit/`.

## How to run it

1. Establish the meaning first: the actors, operations, conditions and reader.
   For a claim about the kit, read the code or the diff that supports it.
2. Review the text against the twelve criteria. Report each problem with the
   original sentence, the criterion, the reason and a rewrite.
3. Leave clear, natural and accurate sentences alone.
4. Check each rewrite against the original: the same scope, conditions and
   certainty, and no new fact.
5. Then run `.agents/maintainer-skills/humanizer/SKILL.md` in its embedded
   mode.

For a release, a long document or a text you wrote yourself, ask a fresh
reviewer to review the text: a subagent, or Codex in a read-only subprocess.
Make the recommended changes yourself, after checking each
finding against the evidence.

## Fixed constraints

These override the framework where the two conflict: British spelling, no
contractions in release notes, no em or en dashes, no issue or pull request
numbers in a tracked file, and every command, setting and name kept exactly as
written.
