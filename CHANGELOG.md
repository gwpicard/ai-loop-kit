# Changelog

## 0.10.0

This version follows v0.9.0 of the first kit.

Setup records the project's prepare and test commands. Shape writes an issue
spec and its judge. The gate checks them, tracks piece states, and syncs merged
work. Run builds ready pieces in fresh Claude sessions and opens a pull request
when the judge passes. A guard refuses the hard rules. The person reviews and
merges each pull request.

Field tests covered a new project, existing Python and Node projects, a
contradictory judge, a rejected pull request, and a conflict after a merge.
The Docker scenario has not been run. See [the field results](tests/field/RESULTS.md)
and [the field scenarios](tests/field/SCENARIOS.md).

## 0.1.0

Early field-test preview for attended Claude Code runs on your own computer.
Includes setup, shape and run skills, gate scripts and a tagged plugin
installation route.

The maintainer publishes the tag and release after the release changes merge.
The preview is unfinished: no App, walk-away runs or deployment, and the known
safety and evidence gaps remain. Real-model hardening and a release rehearsal
were omitted from this light preview. See the README before trying it.
