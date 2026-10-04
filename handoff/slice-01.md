# Slice 1: A reader learns from the kit's own documents that shaping is the work and the build is a loop

Labels (today's set): documentation, area:docs, ready-able once shaped. Release label for the PR: release-minor.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: none. This is the first slice.

## So that
Somebody reading PHILOSOPHY.md, the README or WORKFLOW.md learns the principle every later v1 slice rests on: the work is shaping the work, and looping is the consequence.

## Done when
### Works
- PHILOSOPHY.md has a `## The principle` section, placed before `## Who it is for`, that says in these words "The work is shaping the work. Looping is the consequence.", names the kit a loop kit, and names its four loop modules: fix, build, goal and gauntlet. Check: `.agents/tests/loop-first-ground.sh` gains one rule for each of the two sentences and one for the four module names, each proved load-bearing by `rs_guard`.
- The same section says that a loop which needs a person shows a gap in the shaping, and that the piece goes back to be shaped again rather than being finished by hand. Check: `.agents/tests/loop-first-ground.sh`, a rule on "goes back to be shaped again", proved load-bearing.
- PHILOSOPHY.md describes the two zones in one paragraph: shaping, where the person and the system make every decision together, and implementing, where the system works alone and the person takes part only through review, which never stops the loop. Check: `.agents/tests/loop-first-ground.sh`, rules on "every decision" and "review never stops the loop", proved load-bearing.
- The "Trust becomes mechanism" paragraph in PHILOSOPHY.md gains two sentences: a rule the agent would otherwise have to remember is held by a script wherever a script can hold it; and a gate is either a guide, which makes up for something models cannot yet do and is tested by removing it, or a sensor, which guards against the builder's incentives and stays whatever the model. Check: `.agents/tests/loop-first-ground.sh`, rules on "held by a script", "a guide" and "a sensor", proved load-bearing.
- PHILOSOPHY.md gains the worked example "Loop modules, added." It answers all five questions: it fits under /shape, which chooses the module, and /implement, which runs it; the person sees the module named on the piece; the sentence is "the kind of bar decides how the piece is built"; when a loop goes wrong, the piece comes back to /shape with what happened written on it, and they type /shape with its number; they never need to learn how a loop decides when to stop. Check: `.agents/tests/loop-first-ground.sh`, a fourth `check_five` call on the opening "loop modules, added", with each answer proved load-bearing by the existing mutation loop.
- PHILOSOPHY.md gains the worked example "Things the loop kit leaves out, rejected." It names each exclusion in decision 47 with the question it fails or its reason: a permanent model judge, agent hierarchies, specs that code is regenerated from, the same ceremony for every piece, a coverage or mutation score as a gate, debate between agents, a stored code graph or index (until the pilot measures it) and prescribed test-first steps inside a loop. Check: `.agents/tests/loop-first-ground.sh`, one rule for each of the eight, proved load-bearing.
- README.md: the opening paragraph under the title states the principle in one plain sentence, "You shape the work; the kit builds it in loops and checks it against a bar fixed before the build.", and the audience row in "At a glance" keeps naming technical builders who direct agents. Check: `.agents/tests/loop-first-ground.sh`, `rs_require_load_bearing` on the README sentence, beside the existing audience rule.
- WORKFLOW.md: its opening, before `## 1. Commands`, adds the same principle sentence after the existing audience paragraph. Check: `.agents/tests/loop-first-ground.sh`, `rs_require_load_bearing` on WORKFLOW.md and the folded-order assertion extended so the principle sits after the audience line and before the command table.
- docs/SOURCES.md credits the two outside ideas this slice states: the loop vocabulary (loop engineering, inner and outer loops, secondary source as the research note marks it) and the split of a harness into guides and sensors (Birgitta Böckeler, secondary), each linking to `docs/design/agentic-loop-research.md`. Check: `.agents/tests/loop-first-ground.sh`, two `rs_require` rules on SOURCES.md; `.agents/tools/validate-kit.sh` resolves the links.
- Root AGENTS.md: the maintainer-checks entry for `loop-first-ground.sh` names the principle, the two zones, guides and sensors, and the two new worked examples. Check: guided check: the maintainer reads the entry beside the rule list in `loop-first-ground.sh` and finds every new rule named; `.agents/tools/validate-kit.sh` passes, with no issue number added.
### When it is not the normal case
- A person installs the kit while this slice sits on `main`: they read the last release's documents, because installers read the `stable` branch and decision 52 holds every release until v1 is complete. Check: `.agents/tests/stable-is-the-channel.sh` passes unchanged.
- WORKFLOW.md's numbered sections still describe today's commands, states and merges: that is intended, because each operational section changes with the slice that changes the behaviour, and slice 21: documentation sweep makes the whole set tell one story. Check: `.agents/tests/one-story-try.sh` and every other rehearsal that reads WORKFLOW.md pass unchanged under `.agents/tests/run-all.sh`.
- Somebody restores the old worktree rejection or the old growth sentence while editing PHILOSOPHY.md: the existing absence checks fail. Check: `.agents/tests/loop-first-ground.sh`, existing `absence_catches` cases.
- A later edit drops one of the five answers from a new worked example: the check names the missing answer. Check: `.agents/tests/loop-first-ground.sh`, the `check_five` mutation loop.

## Masterplan change
Design note: realises "The principle", "Who it is for" and "Two zones" of `docs/design/agentic-loop.md`, and the guide and sensor paragraph of "What a machine enforces". The note needs no change.

## Not in this piece
- The command count, the command table and the per-command wording in README.md and WORKFLOW.md: slice 4: shaping sub-states (removes /fix), slice 9: run controller (absorbs /queue), slice 14: /deploy replacing /ship and slice 17: /maintain absorbs /sync each change them, and slice 21: documentation sweep checks the whole set.
- The change to "What stays yours" and to the PHILOSOPHY.md paragraph on the person's standing duty to merge: slice 13: merge policy, when automatic merge is earned.
- The product name AI Loop Kit in titles, commands and record names: slice 22: Set AI Loop Kit's names.
- Rewriting or retiring the `/queue` worked example ("The loop, added"): slice 9: run controller.
- The guide removal tests themselves: slice 17: /maintain absorbs /sync.

## Decided
- The principle is stated in the design note's own words, so the two documents never drift apart (decision 41).
- The audience sentence already in PHILOSOPHY.md, the README and WORKFLOW.md stays as it is, because it already matches decision 51.
- Only PHILOSOPHY.md describes the four loop modules in full. The README and WORKFLOW.md carry one sentence each, because their operational sections are not yet true of v1 and the house rule gives each concept one home.
- Guides and sensors go into PHILOSOPHY.md now rather than with the removal tests, because every later slice names which kind its gate is (decision 46).
- The exclusions are written as one rejected worked example rather than eight, so the list stays short and the five-question format is kept for additions.
- "Loop module" is the name used everywhere, never "implementation mode" (decision 42).

## Data
No stored data changes, because this slice edits documents only.

## Leaves the tool
Nothing new leaves the tool, because the change is prose in the repository and the release that would publish it waits for v1.

## Must still hold
- The audience line in the README, WORKFLOW.md and PHILOSOPHY.md, and the Claude Code first line in COMPATIBILITY.md (`loop-first-ground.sh`).
- The one story about who tries a piece (`one-story-try.sh`).
- The records-are-written-for-agents-first section (`loop-first-ground.sh`).
- No issue or pull request numbers in a tracked file, no attribution lines, every local link resolves (`validate-kit.sh`).
- House writing rules: British spelling, no em dashes, paragraphs under about 100 words, the banned words (humanizer pass, guided).
- The README ships as the public README unchanged at release, so it stays written for someone deciding whether to use the kit (`release-builder.sh`).

## Relies on
- `docs/design/agentic-loop.md` and `docs/design/agentic-loop-research.md`, in the first commit of gwpicard/ai-loop-kit (decision 58).
- `.agents/tests/loop-first-ground.sh` and `.agents/tests/lib/rule-shape.sh`, on main today.
- `.agents/maintainer-skills/humanizer/SKILL.md`, on main today.

## Reach and risk
Boundary: PHILOSOPHY.md, README.md, WORKFLOW.md opening, SOURCES.md, root AGENTS.md maintainer-checks entry, the loop-first ground check.
Reaches: the one story about trying a piece (`one-story-try.sh`); the compatibility grades (`compatibility-grades.sh`); the release boundary for the README (`release-builder.sh`); validator link and number checks (`validate-kit.sh`).
If it breaks: the maintainer sees `loop-first-ground.sh` fail in the pull request check; nothing reaches an installed project, because the release waits for v1. Reverting the pull request undoes it.
Depends on: none.
Loop module: build, because every line is a rule a rehearsal can pass or fail.
Crew: default for the module.

## Under the hood
Edit PHILOSOPHY.md first, then the README opening and WORKFLOW.md opening, then SOURCES.md, then the AGENTS.md entry. Extend `loop-first-ground.sh` with the new `rs_rule` lines and a fourth `check_five` call before writing the prose, so each rule is seen to fail first. Load `.agents/maintainer-skills/humanizer/SKILL.md` and apply the house rules in `docs/MAINTAINING.md` before saving prose. No canonical skill changes, so the five questions are answered only for the two new worked examples, inside PHILOSOPHY.md itself, and no adapters need rebuilding. Nothing is reused from the overnight batch branch. Existing rehearsals expected to change: `loop-first-ground.sh` only.

## Evidence
Rule-shape rehearsal: `loop-first-ground.sh` extended, each new rule proved load-bearing by removal, the new worked examples proved to answer all five questions by mutation. The full suite through `.agents/tests/run-all.sh` and `.agents/tools/validate-kit.sh` pass.

## Size
One sitting.

## Consistency notes
- The slices live in gwpicard/ai-loop-kit, whose first commit holds the current kit and both design notes (decisions 58 and 59). This slice's Relies on names that commit rather than the old design branch.
- Slice 22 is now "Set AI Loop Kit's names": it sets the new names and moves no installed project, so the "Not in this piece" line names it that way.
