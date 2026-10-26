# Changelog

## 1.6.0 (26 October 2026)

Walk-away runs onto a loop branch, with one final pull request into `main`;
setup from an empty folder; the kit on its own Python 3.13 through uv; Codex
model and effort settings and sandbox fixes; and stricter dependency and
check-settings rules. Install uv before you update. See the
[1.6.0 release notes](docs/release-notes/v1.6.0.md).

## 1.5.0 (20 October 2026)

- The gate always runs the project's full test command. `Keep:` adds a check
  and no longer replaces it. Review findings now have a recorded effect:
  proven contract gaps return to shaping, while unresolved findings appear at
  the top of the pull request. The guard also catches protected commands
  hidden behind wrapper options.
- A new piece can get its judge when the project does not ignore `.loop/`.
  This fixes a 1.4.0 bug: the first captured event made the working tree look
  dirty, so the judge-writer stopped. The kit now ignores its own `.loop/`
  folder locally.
- The preview field round and the kill-during-review field test moved to 1.6.
  Walk-away runs, the researcher, goal and gauntlet checks, the Codex backend,
  and mutation testing remain previews or experimental. No preview became
  stable or was removed.
- The Claude release proof passed on the first attempt. Its report records
  the checks that held and the paths that it did not exercise. See the
  [field results](tests/field/RESULTS.md).

## 1.4.0 (19 October 2026)

- The default install leaves out the experimental mutation tools and gauntlet
  critics. To use them, run `/plugin install ai-loop-kit-extras@ai-loop-kit`,
  then `/ai-loop-kit-extras:setup`, and set
  `AI_LOOP_KIT_EXTRAS_ROOT` to its installed path. Run `/ai-loop-kit:setup`
  again to agree and check mutation Quality commands. Existing mutation
  command paths keep working. A source checkout finds the sibling `extras/`
  folder by default. A missing extra refuses the affected checks before
  claim or launch; it never weakens the contract.
- Runs record local events and write a dashboard page with each piece's
  state, attempt, time and pull request link. The page opens without network
  access, escapes issue text and flags disagreements with GitHub labels.
- Research and judge writing use the shared session launcher on Claude or
  Codex. A missing tool or invalid answer stops shaping with a next step.
  The judge-writer uses only the approved Exit paths and writes assertion
  failures that the gate accepts. Its path checks accept named tool cache
  folders left by real pytest, while refusing committed caches and other
  unexpected files. Sessions suppress bytecode and the pytest cache.
- Contract reviewers see changes since ready, frozen baseline lines and the
  gate's attempt evidence. Findings that cite a valid baseline conflict are
  kept separate from judge gaps. Pull requests list tests separately from
  frozen support files, and truncated evidence keeps whole lines.
- Codex walk-away sessions deny home credential reads while keeping ordinary
  Git configuration readable. Builders carry on after successful commands
  with warnings. Two identical unsupported environment reports stop a piece.
  The sandbox probe retries an unreadable answer once, but never a readable
  leak. Environment evidence also recognises the observed zsh here-document
  refusal when the rest of a command exits successfully.
- Worktree cleanup handles ignored dependencies, keeps unfinished work and
  reports failed removals. Doctor lists leftover folders with their size and
  whether they are safe to remove.
- The spec parser, doctor and command-line handling have separate modules.
  Session execution has one owner and ready reuses its settings snapshot.
  Rare run paths load support skills only when needed. The ordinary run
  skill loads 265 source words, down from 903. Checks cap Python files at
  800 lines, set text budgets and guard test discovery after file splits.
- The Claude (Sonnet) attended rehearsal passed, including the dashboard
  and a hostile piece blocked with no leak. At `7134440`, the third re-proof
  reached ready without hand edits and opened a pull request after one
  20-second attempt and both reviews. The Claude reject path and retry after
  a failed attempt remain unproved. See the [field results](tests/field/RESULTS.md)
  for this rehearsal, the Codex runs and their limits.
- Walk-away runs, the researcher, goal and gauntlet checks, and the Codex
  backend remain previews. Mutation testing remains experimental. No preview
  became stable or was removed.
- The kit total did not shrink: runtime Python grew from 5,972 lines in 1.3
  to 6,435, up 463. The default install has 6,015 lines and the extras add
  420. Moving code into the extras reduces the default install's share of
  the bundle; it does not reduce the combined total.

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
