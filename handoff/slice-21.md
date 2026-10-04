# Slice 21: Every document a person or a maintainer reads tells the same v1 story

Labels (today's set): documentation, area:docs, ready-able once shaped. Release label for the PR: release-minor, because WORKFLOW.md, the README, COMPATIBILITY.md, the foundation templates and the issue forms ship.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slices 1 to 20 (slice 1: Principle, audience and the loop kit; slice 2: Label model and gate script; slice 3: Contract v2 and the ready-gate lint; slice 4: Shaping sub-states in /shape; slice 5: Area map; slice 6: Frozen-bar enforcement; slice 7: Build and fix loop modules; slice 8: Automatic reviewer; slice 9: Run controller; slice 10: Crews and computer resources; slice 11: Goal loop module; slice 12: Gauntlet loop module; slice 13: Merge policy; slice 14: /deploy replacing /ship; slice 15: Safety boundary for runs; slice 16: Boards and notifications; slice 17: /maintain absorbs /sync; slice 18: Compact masterplan and behaviour deltas; slice 19: Codex parity; slice 20: Replay harness rewrite and real runs).

## So that
Someone deciding whether to use the kit, someone using it, and someone maintaining it each read one account of v1, with no page still describing a command, label or step that v1 removed.

## Done when

### Works
- No shipped document, skill or foundation template names a retired command (`/fix`, `/queue`, `/sync`, `/ship`) or a retired label or state (`idea`, `parked`, `blocked`, `to check`, `needs-research`, `needs-clarification`, `needs-prototype`, `shaping` without its `state:` prefix) outside the two places that need them: `docs/design/` and `.agents/tests/`. The maintain skill carries no migration step after slice 17, so it gets no exemption. Check: new `.agents/tests/one-story-v1.sh`, which walks every path in `release-manifest.txt` and fails on a copy of WORKFLOW.md with one `/ship` put back.
- Every count of commands and skills in the README, WORKFLOW.md, COMPATIBILITY.md, PHILOSOPHY.md, MAINTAINING.md, root `AGENTS.md`, `llms.txt` and the founded `AGENTS.md` template matches the skill folders in `.agents/skills/`, split by `user-invocable: false`; the check reads the folder rather than holding a number. Check: `.agents/tests/one-story-v1.sh`, proved on a copy of the README still saying "nine commands".
- The command table is the same six commands, in the same order with the same one-line job, in the README, WORKFLOW.md section 1, `llms.txt` and the founded `AGENTS.md` template. Check: `.agents/tests/one-story-v1.sh` compares the four tables.
- WORKFLOW.md tells the v1 day: shaping on the shaping board, the ready gate, a run started from the chosen pieces, the loop board, review owed, kickback, merge and going live, and `/maintain` as the one health visit; each section names the command the person types when it goes wrong. Check: `.agents/tests/one-story-v1.sh` holds one sentence per item as a rule-shape rule.
- PHILOSOPHY.md's worked examples name no retired command; the "Automatic tests on every pull request" example says what the person does on red in v1. Check: `.agents/tests/loop-first-ground.sh`, extended to fail on a worked example naming `/fix`.
- COMPATIBILITY.md grades each coding agent from `baseline.md` and `.agents/tests/real-runs.md` as slice 20 left them, and its first section describes the v1 core other agents get: shaping and a run of one. Check: `.agents/tests/compatibility-grades.sh`, extended to read `real-runs.md`.
- MAINTAINING.md's "Changing a skill", "Maintainer validation", "One owner per concept" and "How the issues are organised" sections use v1 names: `/deploy`'s recipes folder as the one place a product is named, the six commands and five background skills, and the gate script as the owner of a state change. The release sections stay for slice 23. Check: `.agents/tests/one-story-v1.sh` reads those four sections.
- Root `AGENTS.md`: the maintainer-checks list has one entry for each `.agents/tests/*.sh` and no entry for a file that is gone, and no entry describes a retired command or label as current behaviour. Check: `.agents/tests/one-story-v1.sh`, mechanical half, proved on a copy with one entry removed and one entry still describing `/queue`.
- `docs/SOURCES.md` has a row for each outside source `docs/design/agentic-loop-research.md` links to whose idea a v1 slice built, and the check holds an explicit list of research-note links that are not credited, each with its reason (for example a source the kit decided against under "Deliberately left out"). Check: `.agents/tests/one-story-v1.sh` fails on a research-note link that is in neither SOURCES.md nor the not-credited list.
- The foundation templates (`AGENTS.md`, `README.md`, `CLAUDE.md`, `GEMINI.md`, `copilot-instructions.md`, `piece-issue.yml`, `claude-settings.json`) name only v1 commands, labels and records, and the founded `AGENTS.md` stays within its ceiling. Check: `.agents/tests/standing-instructions.sh` and `.agents/tests/agent-first-records.sh`, plus `.agents/tests/one-story-v1.sh` for the retired names.
- `CONTRIBUTING.md` and `.github/ISSUE_TEMPLATE/` describe the v1 kit: the bug form's installation-route options match COMPATIBILITY.md's routes, and its "what happened" help text asks for the loop board's status line when the problem happened during a run. Check: `.agents/tests/one-story-v1.sh` compares the route options with COMPATIBILITY.md.
- `docs/design/loop-first-redesign.md` and `docs/design/loop-first-round-2.md` each open with a line saying that `agentic-loop.md` replaces their run, merge and launch parts, linked, and naming what still stands (the piece contract, the readiness check and the principle). Check: `.agents/tests/one-story-v1.sh` reads the first ten lines of each.

Documents this slice touches
- All of the above are this slice's documents; each is held by `.agents/tests/one-story-v1.sh` or the existing check named on its line.

### When it is not the normal case
- An earlier slice left a document telling its part differently from WORKFLOW.md: WORKFLOW.md is the owner of operational detail, the other document is edited to match, and the owner rule in MAINTAINING.md decides. Check: `.agents/tests/one-story-v1.sh` compares the command tables, the counts and the state list.
- A retired name appears in the maintain skill: it is a finding like any other, because AI Loop Kit carries no migration (decision 63). Check: `.agents/tests/one-story-v1.sh` fails on a copy that adds `/sync` to any maintain section.
- A design note other than the two loop-first notes describes something v1 replaced (`evaluation-system.md`): it keeps its text, since it records a decision of its day, and gains no marker unless v1 replaced it. Check: does not arise for that note, because its replay design is extended by slice 20 rather than replaced.

## Masterplan change
Design note: "Who it is for", "Commands" and "What stays". No change to the note. The two loop-first notes are marked replaced, as the design note's opening paragraph already says.

## Not in this piece
- The behaviour behind any sentence: slices 1 to 20.
- The product name in every document: slice 22: Set AI Loop Kit's names, which follows this slice so the rename touches settled text once.
- MAINTAINING.md's release sections and the pre-release run as a person: slice 23: Release v1.0.
- Release notes: slice 23: Release v1.0.

## Decided
- One new check, `one-story-v1.sh`, holds the story across documents; the existing single-topic checks (`one-story-try.sh`, `loop-first-ground.sh`, `compatibility-grades.sh`) keep their topics, because one owner per concept applies to checks too.
- Counts are read from the skill folders rather than written in the check, so a later change to the command set cannot leave the check and the documents agreeing on a stale number.
- `docs/design/` and `.agents/tests/` are exempt from the retired-name search, because a design note records a decision of its day and a scenario contract names what it retired.
- SOURCES.md credits are audited here, but each slice that lands an idea still writes its own row, following the research note's own rule: "An idea is credited in SOURCES.md when a piece that uses it lands".
- The issue forms ask for the loop board's status line rather than a log, because a person can copy a line from the board without reading code (decision 51).

## Data
No stored data changes, because this slice edits documents and adds one check. Founded projects receive the changed templates at founding. No project founded with AI Build Kit is moved (decision 63).

## Leaves the tool
Nothing new leaves the tool, because the documents ship in the next release through the existing allowlist and nothing is published by this slice.

## Must still hold
- The founded `AGENTS.md` stays five lines under 200 after founding fills it. Check: `.agents/tests/standing-instructions.sh`.
- Each section of the founded `AGENTS.md` past the standing rules stays 12 lines or fewer and points at its owner. Check: `.agents/tests/agent-first-records.sh`.
- The person never has to read code, and trying a piece stays open to them through the opt-in. Check: `.agents/tests/one-story-try.sh`.
- The README names a product only as one option. Check: `.agents/tests/hosting-request.sh`.
- No issue numbers and no attribution lines in any tracked file. Check: `.agents/tools/validate-kit.sh`.
- A pull request aims at `main`, never `stable`. Check: `.agents/tests/pull-request-base.sh`.

## Relies on
- `docs/design/agentic-loop.md` and `docs/design/agentic-loop-research.md`, in the first commit of gwpicard/ai-loop-kit (decision 58).
- `.agents/tests/lib/rule-shape.sh` (present on `main`).
- `.agents/tests/real-runs.md` and the v1 `baseline.md` from slice 20: Replay harness rewrite and real runs.
- Each document as slices 1 to 20 left it.

## Reach and risk
Boundary: WORKFLOW.md, the README, `llms.txt`, PHILOSOPHY.md's worked examples, COMPATIBILITY.md, MAINTAINING.md outside its release sections, root `AGENTS.md`'s maintainer-checks list, SOURCES.md, the foundation templates, CONTRIBUTING.md, the issue forms, the two loop-first design notes.
Reaches: founding, which copies the templates (`starter-rehearsal.sh`, `plan-helper-routes.sh`); the validator's needles in shipped prose (`validate-kit.sh`); the written-rule checks that read WORKFLOW.md (`kit-owns-worktrees.sh`, `first-upload-asks.sh`, `ship-runs-recipe.sh` and their v1 successors).
If it breaks: a reader meets two accounts of one thing, or a written-rule check goes red in `run-all.sh`; the slice's pull request is reverted, and the earlier slices' own wording returns.
Depends on: 1 to 20.
Loop module: build, because every line is a check that fails on today's documents and passes after.
Crew: default for build.

## Under the hood
Read every shipped path in `release-manifest.txt` plus MAINTAINING.md, root `AGENTS.md`, `llms.txt` and the two loop-first notes. Write `.agents/tests/one-story-v1.sh` first, sourcing `lib/rule-shape.sh` for the prose rules and doing the mechanical comparisons (counts, tables, routes, maintainer-checks list, research-note links) directly; run it on today's documents and record each failure. Then edit the documents until it passes, owner first: WORKFLOW.md, then the README and `llms.txt`, COMPATIBILITY.md, PHILOSOPHY.md's examples, MAINTAINING.md, root `AGENTS.md`, SOURCES.md, the templates, CONTRIBUTING.md and the forms, the two design notes.

Existing rehearsals expected to change: `loop-first-ground.sh` (worked examples), `compatibility-grades.sh` (reads `real-runs.md`), `one-story-try.sh` (searched paths), and any written-rule check whose needle still quotes pre-v1 WORKFLOW.md text after slices 1 to 20. Nothing from the overnight batch branch is reused.

Kit rules: no canonical skill's behaviour changes, so the five questions are answered once in the pull request for the templates only; adapters are rebuilt if a template change reaches a generated file; the humanizer and the house rules in MAINTAINING.md apply to every sentence; no issue numbers; no attribution lines.

## Evidence
A rule-shape check with load-bearing proof for each prose rule, mechanical comparisons proved on broken copies, and the full `run-all.sh` and validator passing on the result.

## Size
Two sittings: the check and WORKFLOW.md, README, `llms.txt`, PHILOSOPHY.md and COMPATIBILITY.md in the first; MAINTAINING.md, root `AGENTS.md`, SOURCES.md, the templates, CONTRIBUTING.md, the forms and the design notes in the second.

## Consistency notes
- The retired-name search exempts only `docs/design/` and `.agents/tests/`. The maintain skill's migration exemption is gone, because slice 17 removes every migration and AI Loop Kit carries none (decision 63).
- The six commands are `/setup-ai-build-kit` (renamed `/setup-ai-loop-kit` by slice 22), `/shape`, `/implement`, `/deploy`, `/what-now` and `/maintain`; the check reads the count from the skill folders.
