# Changelog

## 1.3.0 (17 October 2026)

- Fixed the Codex backend sandbox so builders can write temporary files and
  their worktree's Git data. The run stages Codex changes after the session
  exits. The staging helper handles ignored `.loop/` folders and preserves
  the original index if staging fails.
- Generated `.loop/` files stay out of commits. The builder brief, staging
  helper, submit check and field audit enforce this rule.
- A Keep rerun records the failing test names and needs evidence before
  blaming the frozen tests for a failure.
- Pull request and ready messages say what their counts cover. Reused pull
  requests get fresh checked evidence. Failed pieces make the run exit
  non-zero, and an environment refusal needs a failed tool result as evidence.
- Gauntlet checks keep invalid critic answers and the order shown, and
  compare criteria by stable keys.
- The audit counts completed attempts. The reviewer cleanup check verifies
  that process groups have exited and that no review worktrees or branches
  remain.
- Frozen-file refusals name the right reason, and logs keep tool events.
- The GitHub account check uses the account seen by the API.
- Codex sessions start without unrelated MCP servers.
- The mutation guidance explains editable adapters and why changed-function
  checks need a commit.
- Installation uses `stable`, which only a release moves. The pull-request base
  check refuses `stable` and points builders to `main`.
- No preview became stable and none was removed in 1.3. The walk-away night,
  the researcher and the attended `/shape` and `/run` pass were not field-tested.
  See the [field results](tests/field/RESULTS.md) for the runs and their limits.
- Python code in `kit/` is 5,972 lines, up 288 from 5,684 in 1.2.

## 1.2.0 (16 October 2026)

- Fixed holes in sandbox domains and the review import. Goal and gauntlet
  files are frozen, Keep checks rerun within a limit, protected paths have an
  exception for each piece, and secrets stay out of agent sessions.
- Hand-back records now include the cause, attempt count and elapsed seconds.
- Specs can name their Exit checks and Risks.
- Builds can return `needs-answer` and `spec-unclear` outcomes. The run skill
  asks a question when a person rejects a pull request.
- The README states the kit's limits and links to the [1.2 upgrade note](docs/UPGRADE-1.2.md).
- No preview became stable or was removed. Walk-away, the researcher, goal
  and gauntlet loop kinds, and the Codex backend remain previews. The attended
  loop is the tested path. The field round moves to 1.3.
- The Python code in `kit/` grew from about 4,880 lines to about 5,680. The
  1.3 work aims to shrink it.

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
and secret shapes. See [the design](docs/DESIGN.md).

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
