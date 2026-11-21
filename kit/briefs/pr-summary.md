Write only what the diff, build notes and test results support.

Your job: read the batch diff the prompt names, AGENTS.md and the build notes in
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
