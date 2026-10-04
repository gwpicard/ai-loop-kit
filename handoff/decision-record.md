# v1 decision record

Approved by the maintainer on 2 October 2026, including the three points to be resolved in the note
(gauntlet reference approved in shaping:clarify with a budget; risk notice and acceptance in shaping;
the name /implement stays). Next: external reference pass, then the design note on a branch with a draft PR,
then a backlog change list for approval.

## Process
1. Two zones: shaping (person + system, all decisions) and implementing (system alone; person only reviews, never blocking the loop).
2. Every build is a run. A single piece is a run of one (own branch, PR to main). Several pieces: integration branch, one PR to main.
3. A run starts when the person picks the pieces. No questions; parallel count and merge policy come from project settings.

## States and labels (prefixed, mutually exclusive)
4. state:shaping | state:ready | state:building | state:in-review | closed (completed / not planned). No idea, parked, queued or blocked labels.
5. shaping sub-states, exactly one: raw (backlog), research (facts, system settles), clarify (person decides), prototype (system builds, person decides), spec (system writes contract), check (machine lint + fresh session).
6. Ready gate = machine lint + fresh check. No per-spec human approval; the person can pull a piece back before it is claimed.
7. Dimensions: type: (feature, bug, chore), mode:. In review: review:auto | review:person.
8. Review default auto; the system asks whether the person wants to review some pieces and warns when a piece would benefit. Sensitive area, goal miss and first deployment force review:person.
9. Only the gate script changes a state (hook + deny rules, Claude Code first).
10. Run status in the run record. Piece: queued, building, checking, integrated, kicked-back, withdrawn. Run: planned, running, paused, in-preview, merged, abandoned.
11. Parents only when pieces really belong together; complete when all pieces are done (each shaped to ready by the person).

## Implementation modes
12. mode:fix (failing reproduction), mode:build (checks), mode:goal (metric, target, budget, guard checks), mode:gauntlet (reference approved by the person, blind critic). Shaping chooses the mode.
13. One mode per piece; the builder may switch mode during the build and log it, only when the new bar comes from the spec without a new decision.
14. Limit: attempts + budget. During the build the builder may research and self-repair when the facts do not change the spec.
15. A goal that misses its target goes to review as review:person with the best result.
16. Kickback goes to the matching sub-state (clarify, research or spec) with a Kickback section; the branch is kept; shown on the shaping board.

## Merge and deployment
17. A merge to main goes live. /ship becomes /deploy: pipeline setup (previews, production, rollback, secrets, health), first time and re-platform.
18. Run PR auto-merges when all pieces are review:auto, gates green, no sensitive area. Reverses the earlier "final merge always human" rule.
19. Auto-merge only where GitHub protects main (Pro, Team, public). Free private repos: client guards only, said clearly at setup.
20. Founding chooses the recipe; /deploy builds the pipeline.

## Commands, boards, platform
21. Commands: /setup-ai-build-kit, /shape, /implement (absorbs /queue), /deploy, /what-now (shows the boards), /maintain (absorbs /sync). /fix removed.
22. Boards: shaping board + loop board from one JSON status file; local HTML + live Claude artifact; ChatGPT later.
23. Claude Code first; Codex mirrors scripts as hooks/rules; others get the one-piece core.

## Scope and backlog
24. The open v1 batch PR is not merged; build on main, reuse its mechanisms piece by piece.
25. v0.20.0 is not published; the next release is the new model.
26. 1.0 needs: new model complete; old projects migrate; real runs recorded (one per mode, one /deploy per recipe); compact masterplan.
27. Backlog changes after the design note, from an approved list.

## Additions after the external reference pass (approved 2 October 2026)
28. Frozen bar: acceptance checks written as tests in spec, red on main at the ready gate; contract hash at ready, a change in building is a kickback; the build gate refuses edits, deletions, skips, suppressions, lowered thresholds and changes to CI, hooks or deny rules (a real need forces review:person); fresh evidence (command, exit code, commit, red before green) before in-review.
29. review:auto defined: a fresh session reads only the contract and the diff; two verdicts (meets the spec, code sound); gaps sorted missing, partial, contradicts, unrequested; findings limited to correctness and requirements; rounds capped; rulings logged. Builder exit statuses: DONE -> checking, DONE_WITH_CONCERNS -> review:person, NEEDS_CONTEXT or BLOCKED -> kickback.
30. Integrated checks: pieces join the integration branch one at a time (merge-queue style) with full checks on the combined head; no agent conflict resolution on the automatic path; bisect on red and kick back only the breaker; preview smoke test of acceptance paths before auto-merge; health check after merge with automatic rollback and a bug piece.
31. Run safety boundary: native sandbox with a network allowlist from the recipe (say so where unavailable); no production secrets in run worktrees; pushes only to the run's branches; text the person did not write is data; a new dependency is checked to exist, with age and licence; secret scan in the gate.
32. Limits and supervision: run budget ceiling, CI round cap, pause after repeated denials; notifications at four moments (review:person needed, run paused, kickback, run live); stop and pause on the loop board; per piece a session log link and "what I could not check"; main must be green before a run starts.
33. Self-contained contract: dependency and boundary fields drive the run's waves (overlap or shared area -> sequential); agent-brief rules in the lint (behaviour not steps, interfaces not paths, out-of-scope list, each criterion checkable alone); "must not change" for fixes; proportional ceremony (sub-states skippable, a length limit per type).
34. Learning loop: a Learned field per piece (only what code and tests do not show), promoted at run close through the run PR as an AGENTS.md line, a masterplan change or a raw piece; shaping reads lessons first; /maintain refreshes them; each escaped defect becomes a check.
35. Code health: masterplan constraints become machine rules with fix messages and a shrinking baseline; drift, duplication and unused-code reads after a number of merged runs, findings as type:chore pieces; discovered work becomes a raw piece with a discovered-from link; the behaviour record is updated by deltas at each merge.
36. Fix discipline: no hypothesis before the reproduction; ranked hypotheses with predictions; three failed fixes -> kickback to research; no reproduction -> kickback to clarify.
37. Earned automatic merge (amends decision 18): each project starts at "person merges"; after a number of clean runs /maintain offers to switch to automatic, then decision 18's rules apply.
38. Red main or broken production: no run starts on a red main; the kit files a type:bug piece on the fast path (raw -> spec -> check) that can run at once as a run of one; a failed post-merge health check rolls back first.

## Traps to avoid (from the reference pass)
Two sources of truth (the gate writes labels and run record in one step); harness creep (each gate names what it catches); ceremony and markdown sprawl; agent hierarchies; gaming a number; review fatigue; agent-resolved merge conflicts on the automatic path.

## Reach and risk in shaping (approved 2 October 2026)
39. Research runs the reach check on main plus a co-change query from git history and maps hits to named areas; clarify asks one pre-mortem question when the reach touches a sensitive area, stored data or something leaving the tool; the contract records Boundary, Reaches (with guarding tests), If it breaks, Depends on, Reach derived at; reached tests become guard checks; the person sees one sentence and a connections diagram only for outside connections; the ready gate checks the fields mechanically and re-derives reach; a run re-derives reach and plans waves from boundaries; a diff outside the boundary forces review:person; richer engines wait for the dependency pilot.
40. The area map covers the whole project; founding writes it; the project check turns red on an unclaimed folder.

## Principle and names (approved 2 October 2026)
41. Principle: the work is shaping the work; looping is the consequence. The kit is a loop kit with loop modules.
42. "Implementation mode" is renamed "loop module" everywhere; the label is loop: (loop:fix, loop:build, loop:goal, loop:gauntlet). Amends decisions 7, 12 and 13.
43. The product becomes AI Loop Kit with v1. The rename (repository, plugin and marketplace names, founding command, moving installations) is its own piece; each online step waits for approval at that step.

## Crews, computer resources and harness points (approved 2 October 2026)
44. Crews: the declared set of agents for a step, fixed in shaping, started by the run script. Four roles (builder only writer, critic, researcher/probe read-only, checker). Shape table with defaults and caps per step. Crew: field defaults from the loop module; changes need a reason; lint checks shape and caps; one writer per piece. Helpers read only and count against the budget; fixed verdict format; findings count only when reproduced; comparisons in both orders.
45. Computer resources: suggested builders from free memory, reserve and cores (max 4), person may raise to a hard cap of 6; heavy pieces run alone; pressure and swap checked before each start; back-off under pressure; usage-limit handling; shared package store, one browser, dev server only during walk-through, at most two test workers; heartbeat 30/45 minutes, two-hour cap; numbers in settings, piece and run record.
46. Harness: acceptance checks must fail on their assertion; the checker matches checks to criteria; test-strength on acceptance checks after green; an "environment failed" builder status that never kicks back; a bootable app per worktree as a recipe field; quiet scripts that teach on failure; kit metrics define a clean run; guides (removal tests) versus sensors (stay); lessons become checks first; reviewer calibrated against the person; a slow signal for earned merge; script-built attempt notes; push token scoped and held by the gate script; the brief states what the builder may do outside the code; no prescribed steps inside a loop; a flaky guard check becomes a chore piece.

## Exclusions confirmed and the last decisions (approved 2 October 2026)
47. Exclusions confirmed: permanent judge, agent hierarchies, specs that regenerate code, ceremony per piece, coverage/mutation score as a gate, debate (deliberate); stored code graph or index (deferred to the dependency pilot); prescribed TDD steps (deliberate; red then green stays as evidence).
48. An irreversible data change always forces review:person, and the merge waits for a backup taken just before it.
49. Each preview uses its own throwaway database seeded with sample data (or host branching); automatic merge stays off on a recipe until a real run proves it.
50. Not hosted: a merge means done; /deploy makes a GitHub release with the next version when the person asks.
51. Audience: builders who direct agents and know Git, branches and pull requests; the person never has to read code.
52. v1 slices merge to main one by one; no release until v1 is complete.
53. The rename to AI Loop Kit is the last slice before the release.
54. One epic "AI Loop Kit v1" with one sub-issue per slice, linked by blocked-by in build order; existing issues changed from an approved list.
55. Slice issues use the new contract shape with today's labels, so today's /implement queue can build them.

## The move to a new repository (approved 2 October 2026)
56. The last release of AI Build Kit is v0.19.3: v0.19.2 plus the six fixes merged before the loop-first redesign, plus the Codex GitHub fix ported by hand. No loop-first redesign in it.
57. In the old repository, one PR on main reverts the redesign commits (history kept, no force push) and ports the Codex fix; the normal release process then releases v0.19.3.
58. The new repository starts from a clean snapshot: one first commit holding the current main (with the loop-first redesign) plus the two design notes. The old repository keeps the history.
59. The new repository is gwpicard/ai-loop-kit, private while v1 is built, public at the v1.0 release.
60. Old issues: those that fold into a slice or wait for after 1.0 are transferred to the new repository; those the new model replaces are closed with a reason; bugs that still apply to AI Build Kit stay for the v0.19 line.
61. The old repository gets fixes only (v0.19.x) while v1 is built; at v1.0 its README points to AI Loop Kit; a later release offers founded projects a move; it is archived once that move has run for real.
62. The design notes go into the new repository's first commit; PR 346 closes in the old repository with a pointer; the v1 epic and slices are created in gwpicard/ai-loop-kit. Slice 22 becomes "Moving from AI Build Kit to AI Loop Kit" (new plugin and marketplace names, the founding command and record names, and a move for founded projects), not a GitHub rename.
63. No migration (amends decisions 26 and 61): AI Loop Kit is for new projects only; projects founded with AI Build Kit stay on it, which keeps fixes (v0.19.x) for a stated period and is then archived. Migration leaves the 1.0 bar, slice 17 drops the move for founded projects, slice 22 only sets the new names, and the new repository may drop the old-project migrations and upkeep in /maintain.
