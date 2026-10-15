# Changelog

## 1.1.0 (15 October 2026)

- Walk-away runs (`run.py --walk-away`) use a sandbox and a pre-run probe. They wait on usage limits, write a heartbeat and make a morning summary. preview: not yet field-tested.
- The researcher role checks outside facts and records sources and dates. preview: not yet field-tested.
- The goal loop kind checks a numeric measure against a target. preview: not yet field-tested.
- The gauntlet loop kind compares captured work with a reference using blind critics. preview: not yet field-tested.
- The Codex backend is selected with `Agent: codex`. preview: not yet field-tested.
- Mutation testing checks its version and source paths. Setup tests proposed settings on a configured project.

The attended loop from 1.0 is the tested path. The v1.1 preview features have automated tests but no field tests yet.

## 1.0.0 (15 October 2026)

V1 adds an Intent and Contract format, typed hand-backs, safer runs, judge
quality checks, project Quality commands, two independent reviews, and
pull requests written from checked facts. The gate now checks protected paths
and secret shapes. See [the v1 definition](docs/V1.md).

Upgrade from 0.10.0: add a non-empty `## Intent` and `Out of scope:` to each
spec. The existing `## Done when` section is read as `## Contract`.

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
