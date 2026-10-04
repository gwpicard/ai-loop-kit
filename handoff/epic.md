# AI Loop Kit v1

Labels (today's set): epic, enhancement.
Repository: gwpicard/ai-loop-kit, private while v1 is built and public at the v1.0 release (decision 59).

## Goal

Turn the kit into a loop kit. A person and the system shape a piece together until it can be built with nobody there; the system then builds it in the loop module its bar calls for, checks it against a bar fixed before the build, reviews it and merges it, and a merge goes live. The person decides and reviews; they never take part in a build. When a loop needs a person, the piece goes back to shaping.

v1 ends with the product named AI Loop Kit and released as 1.0 from gwpicard/ai-loop-kit. AI Loop Kit is for new projects. A project founded with AI Build Kit stays on AI Build Kit, which keeps fixes on its 0.19 line for a stated period and is then archived; no slice moves such a project (decision 63).

## Where the work lives

- The epic and its 23 slices are issues in gwpicard/ai-loop-kit. Its first commit is a clean snapshot of the current kit, the loop-first redesign included, plus both design notes (decision 58).
- `docs/design/agentic-loop.md`: the agreed v1 design. Every slice realises a named section of it, and a slice that finds the note wrong changes the note in its own pull request.
- `docs/design/agentic-loop-research.md`: the outside work behind the decisions. A slice that lands an idea from it credits the source in `docs/SOURCES.md`.
- Mechanisms reused from the overnight batch (the recovery helper, fresh builder contexts, the walk-through's browser rule, the force-push deny rules, the question box, continuing in the same turn) are read from the old repository, gwpicard/ai-build-kit, on its branch `gwpicard/v1-overnight-integration-20261001`, which stays. A clone of gwpicard/ai-loop-kit has no such branch on `origin`, so a slice first adds the old repository as a second remote (`git remote add build-kit https://github.com/gwpicard/ai-build-kit`, then `git fetch build-kit`) and reads each file with `git show build-kit/gwpicard/v1-overnight-integration-20261001:<path>`, one mechanism at a time. The earlier compact-masterplan attempt slice 18 starts from is read the same way.

## The slices, in build order

Each slice is one sub-issue of this epic, linked by blocked-by. The Blocked by column is each slice's own `Depends on:` line, so the two always agree.

| Slice | Title | Blocked by |
|---|---|---|
| 1 | Principle, audience and the loop kit in PHILOSOPHY.md, the README and WORKFLOW.md | nothing |
| 2 | Label model and gate script | 1 |
| 3 | Contract v2 and the ready-gate lint | 2 |
| 4 | Shaping sub-states in /shape | 2, 3 |
| 5 | Area map for the whole project, kept by the project check | 2, 3 |
| 6 | Frozen-bar enforcement | 2, 3, 5 |
| 7 | Build and fix loop modules | 2, 3, 4, 6 |
| 8 | Automatic reviewer | 2, 3, 5, 6, 7 |
| 9 | Run controller | 2, 3, 5, 6, 7, 8 |
| 10 | Crews and computer resources | 3, 7, 8, 9 |
| 11 | Goal loop module | 3, 6, 7, 9, 10 |
| 12 | Gauntlet loop module | 3, 4, 5, 6, 7, 8, 9, 10 |
| 13 | Merge policy | 2, 3, 6, 8, 9 |
| 14 | /deploy replacing /ship | 9, 10, 13 |
| 15 | Safety boundary for runs | 2, 6, 7, 9, 14 |
| 16 | Boards and notifications | 2, 4, 8, 9, 11, 12 |
| 17 | /maintain absorbs /sync | 2, 3, 4, 6, 8, 9, 13, 14, 15 |
| 18 | Compact masterplan and behaviour deltas | 3, 5, 9, 14, 17 |
| 19 | Codex parity | 2, 6, 9, 10, 15 |
| 20 | Replay harness rewrite and real runs | 4, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18 |
| 21 | Documentation sweep | 1 to 20 |
| 22 | Set AI Loop Kit's names | 21 |
| 23 | Release v1.0 | 22 |

The graph has no cycle: every slice is blocked only by slices with a lower number, so building in number order always meets every blocker first. Slices with no path between them (for example 4 and 5, or 10 and 13) can be shaped and built in either order.

Slices merge to `main` one by one. Each is shaped with the v1 contract's fields under today's labels, so today's `/implement queue` can build them (decisions 52 and 55). Which kit builds the slices, today's AI Build Kit installed in the new repository or AI Loop Kit as each slice lands, is an open decision (see `OPEN-DECISIONS.md`).

## Names every slice uses

- The gate script: `gate.py`, shipped in the setup-ai-build-kit skill and placed at `.agents/tools/gate.py` in a founded project. Slice 2 lists every subcommand and the slice that adds it.
- The project settings: `.agents/loop-settings.json` (slice 7), with the per-computer layer `.agents/loop-settings.local.json` (slice 10). The merge setting is its `merge` key, `"person"` or `"automatic"` (slices 9, 13 and 17).
- The run controller: `implement/scripts/run.py`, the design note's run script (slice 7's loop driver, grown by slice 9).
- The run record: `.agents/runs/<run name>/run.json` in the main folder, git-ignored, written by the gate (slice 9). A closed run leaves a `run-summary` block on its pull request (slice 9), which slice 17 counts.
- Hidden markers on GitHub: `loop:gate` (slice 2), `loop:contract` (slice 6), `loop:review` and `loop:person-verdict` (slice 8).
- The area map: the `## Areas` section of `docs/working-rules.md`, read through `area-map.py` (slice 5); slice 18 adds the other build and review rules to the same file.

## The standards every slice meets

- Work starts on a short-lived branch cut from `main`, and arrives through a pull request aimed at `main`. A person decides whether it merges. Held by `.agents/tests/pull-request-base.sh`.
- Every pull request carries one of `release-major`, `release-minor` or `release-patch`. Held by `.agents/tests/release-label.sh`.
- A change to one of the canonical skills answers the five questions in `docs/PHILOSOPHY.md` in the pull request description before the skill changes.
- An idea that lands from outside work is credited in `docs/SOURCES.md` in the same pull request.
- A rule written as prose for an agent is guarded by a check that sources `.agents/tests/lib/rule-shape.sh`, so it is proved load-bearing by removing it. A rule a machine can judge is held by a script, not by prose.
- Every promised behaviour has evidence: an automated check where a machine can judge it, a guided manual check for visual or exploratory work, a rehearsal for an operational claim.
- Every Done when line is false on `main` before the slice and true after it, and names the check that proves it.
- Every slice's Done when names, one by one, the documents its own change touches (WORKFLOW.md, the skill and the words on screen, as PHILOSOPHY.md's "told in three places" rule asks), each with the check that holds it. Slice 21 then makes the whole set tell one story.
- A script copied into a founded project comes with a check that the project's own type check and linter stay green with it, held by `.agents/tests/check-floor-rehearsal.sh`; a script that does not need to live in the project stays inside its skill.
- Each contract field has one owning slice. Slice 3 owns contract v2; slices 11, 12, 13, 17 and 18 each extend it with one named field and say so.
- Generated adapters are rebuilt with `.agents/tools/build-adapters.sh` and committed with the canonical change.
- `.agents/tools/validate-kit.sh` and `.agents/tests/run-all.sh` pass before the pull request is opened.
- Human-facing prose (documentation, skill prose, pull request text, release notes, messages) is written with `.agents/maintainer-skills/humanizer/SKILL.md` and the house rules in `docs/MAINTAINING.md`: British spelling, plain words, no em dashes, short paragraphs.
- No issue or pull request number appears in a tracked file; another slice is named by its number and title in this epic, an old issue by its title. Held by `.agents/tools/validate-kit.sh`.
- No commit or pull request carries an attribution line naming a model or a link to a session. Held by `.githooks/commit-msg` and `.agents/tools/validate-kit.sh`.
- The founded `AGENTS.md` stays within its ceiling after founding fills it, and each of its sections past the standing rules stays an index entry pointing at its owner. Held by `.agents/tests/standing-instructions.sh` and `.agents/tests/agent-first-records.sh`.
- No slice adds a move, a migration or a bridge for a project founded with AI Build Kit (decision 63). A slice that renames or removes something changes only the kit, and slice 17 removes the old-project migrations and upkeep the kit inherited.
- Each online step (a repository setting, making the repository public, a release, a draft deleted) waits for the maintainer's yes at that step.

## No release before slice 23

No release is cut in gwpicard/ai-loop-kit while v1 is being built. Its first published release is v1.0.0, cut by slice 23 once every other slice has merged (decision 52). AI Build Kit's own fixes ship as v0.19.x from the old repository, which also deletes its unpublished v0.20.0 draft.

## The 1.0 bar

1.0 promises that the commands, the records and the way work is built will not change underneath a person. It needs (decision 26 as amended by decision 63):

- the model complete, with all four loop modules, runs, kickback, `/deploy` and both boards;
- real runs recorded, one for each loop module, and one `/deploy` for each recipe;
- the compact masterplan, since 1.0 fixes the project's record format.

## Open decisions

Every decision still open for the maintainer, gathered from the slices, is in `OPEN-DECISIONS.md` beside this file, each with the slice it affects, the draft's default and a recommendation.
