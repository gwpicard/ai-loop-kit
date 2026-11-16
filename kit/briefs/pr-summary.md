Work autonomously as if given a goal: never ask the person anything and never
wait for an answer. Explain the batch on the loop branch to the person who will
open the final pull request.

Write as the project does: follow its writing rules (AGENTS.md and the product
rules in PLAN.md) in everything you write. Read `## Lessons` in PLAN.md first.
Write only what the diff, the build notes and the test results support; leave a
claim out when you cannot back it.

Hard rules, enforced by a hook: this session is read-only. You edit no tracked
file; no git push, no branch changes, no gh, no recursive delete.

Your job: read the batch diff the prompt names, PLAN.md and the build notes in
the prompt, run the tests you need to see their results, then write exactly
these three sections, in this order, and nothing before or after them.

## Summary

What changed for the user, in plain prose. Add one or more small visuals, each
placed next to the text it supports: a file tree, a call tree, a Mermaid
diagram or a trimmed diff. Show only the files, calls and boundaries a reader
needs to follow the change.

## Evidence

For each merged issue, show the proof as a before and after: the test that
failed before and passes now, by name, or the command output that changed.
"Tests pass" alone is not evidence. Where an issue has no such proof, say so.

## Merge danger

Say whether the change is a two-way door (easy to undo) or a one-way door. Name
each one-way change: a data migration, a removed command or setting, a changed
published interface. Then give the blast radius: who or what is affected if
this goes wrong. When you are unsure, say one-way.
