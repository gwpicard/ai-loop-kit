# Slice 12: A piece judged against an example the person approved gets built until a blind critic prefers it

Labels (today's set): enhancement, area:skills, ready-able once shaped. Release label for the PR: release-minor.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 3: Contract v2 and the ready-gate lint; slice 4: Shaping sub-states in /shape; slice 5: Area map for the whole project, kept by the project check; slice 6: Frozen-bar enforcement; slice 7: Build and fix loop modules; slice 8: Automatic reviewer; slice 9: Run controller; slice 10: Crews and computer resources.

## So that
A person who can point at an example and say "make it at least this good" approves that example once in shaping, and the system builds until a critic who cannot tell which is which picks the work, or sends the piece back with what it learned.

## Done when
### Works
- In `shaping:clarify`, once the person approves a gauntlet piece's reference through slice 4's step, the reference is saved: a file in the project (a picture, a PDF or a document) is copied, and a web address is captured once with the walk-through's means into a picture and a saved copy, so the reference cannot change after approval. The person's approval, the reference's path and its hash, the comparison method and the budget are written into the piece before the label moves. Check: new `.agents/tests/gauntlet.sh` (rule-shape) reads these rules from the `clarify` skill and from `/shape`, and proves each load-bearing.
- The ready gate refuses a `loop:gauntlet` piece whose reference file is missing, whose hash does not match, or whose comparison method names nothing a critic can judge (no criteria line). Check: new `.agents/tests/gauntlet-rehearsal.sh` runs slice 3's lint and the gate script on three throwaway contracts and reads each refusal and the one-line next step it names.
- The reference and the comparison method are part of the frozen bar: a builder change to the reference file is refused by the build gate. Check: `gauntlet-rehearsal.sh` with a stand-in builder that edits the reference, reading the refusal.
- After each build attempt, the run controller renders the work the way the comparison method says (a page through the coordinator's browser or Playwright, a PDF through `pdftoppm`, an office file through `soffice` then `pdftoppm`), and hands each critic the contract's criteria, the reference and the work, labelled only A and B with the assignment drawn at random and recorded in the run record. Check: `gauntlet-rehearsal.sh` reads the stand-in critic's inputs and finds no file name, path or word that says which is the reference, and finds the mapping in the run record.
- Each critic judges both orders, A then B and B then A. The work wins only when every critic prefers it in both orders; a split inside one critic, a tie, or a split between critics is not a win. Check: `gauntlet-rehearsal.sh` drives stand-in critics returning a clean win, an order-dependent split, a tie and a two-to-one panel, and reads win, no win, no win, no win.
- A critic verdict comes back in the fixed shape slice 10 defines, naming for each criterion which of A and B meets it better and why; a verdict naming no criterion is no verdict. Check: `gauntlet-rehearsal.sh` with a verdict carrying only prose.
- When the work wins and every guard check is green, the piece goes on to the automatic review. Check: `gauntlet-rehearsal.sh` reads the piece status `checking` in the run record.
- Between attempts, the next attempt note the run controller builds carries each critic's per-criterion reasons and nothing from the builder's own account. Check: `gauntlet-rehearsal.sh` reads the attempt note after a lost round.
- A gauntlet that spends its budget is kicked back to `shaping:clarify` with a Kickback section holding the last pictures' paths, each round's verdicts and the question for the person: change the reference, change the criteria, or drop the piece. Its branch is kept. Check: `gauntlet-rehearsal.sh` reads the gate's labels in the stand-in GitHub log and the Kickback section it wrote.
- The `second-opinion` skill has a comparison mode used as the gauntlet critic: it reads only the criteria, A and B, never the contract's history, the builder's transcript or which item is the reference, and returns the fixed verdict. Check: `gauntlet.sh` reads the mode's rules from `second-opinion/SKILL.md`.
- Critics from another model family are used only when the contract's `Crew:` line names that coding agent's command and shaping told the person that the criteria, the reference and the work go to that vendor; the run checks the command exists and is signed in with its own `--version` and status commands, and otherwise runs the same family and says so once. Check: `gauntlet-rehearsal.sh` with a stand-in second command present, missing, and present but signed out; `no-stored-logins.sh` still passes.
- The `screen-check` skill returns its result as a check a bar can name: one line per rule applied, passed, failed or not checked, which the gauntlet's guard checks and a build bar can list by name; its claim boundary (never "accessible", "compliant" or "good") stays. Check: `screen-rules.sh` extended to read the named-check shape, and its existing claim-boundary assertions still pass.
- `running-longer.md` has a "Gauntlet loop" section with these rules. Check: `gauntlet.sh`.
- WORKFLOW.md explains the gauntlet in plain words: when shaping picks it, that the person approves the example once, that the critic never knows which is which, and what happens when the budget runs out. Check: `gauntlet.sh` reads each sentence and proves it load-bearing.
- README.md names the gauntlet among the loop modules where it describes how a project flows, and docs/COMPATIBILITY.md says which coding agents can run a critic from another model family. Check: `gauntlet.sh` reads both.
- docs/SOURCES.md credits robonuggets/gauntlet-loop for the blind comparison with a fetchable reference, and Anthropic's harness design post for the separate evaluator. Check: `gauntlet.sh` reads both credits; `validate-kit.sh` resolves the links.
- The root AGENTS.md describes both new checks and the extended `screen-rules.sh`. Check: `validate-kit.sh`.

### When it is not the normal case
- The reference is a web address that later changes or disappears: does not affect the loop, because the saved capture is the reference. Check: `gauntlet-rehearsal.sh` deletes the stand-in address after approval and the loop still runs.
- The work cannot be rendered (Playwright missing, a renderer fails): the attempt is environment failed, never a lost round; slice 7's route retries and then pauses the run. Check: `gauntlet-rehearsal.sh` with a renderer that exits non-zero.
- No browser is free because another builder's walk-through holds it: the render waits for the coordinator's browser and counts no attempt. Check: `gauntlet-rehearsal.sh` with the browser marked as held.
- The reference holds personal or confidential data: shaping refuses to save it until the person gives a version without it, because the reference is committed with the spec. Check: `gauntlet.sh` reads the rule from `clarify`.
- The person rejects every reference offered: the piece stays in `shaping:clarify`; no gauntlet piece reaches `ready` without an approved reference. Check: `gauntlet-rehearsal.sh` lint refusal above.
- A critic from another family returns a verdict in a different shape: no verdict, counted against the budget. Check: `gauntlet-rehearsal.sh`.

## Masterplan change
Design note: "Loop modules" (the gauntlet row and the paragraph on spending the budget) and the gauntlet line of "Crews" in docs/design/agentic-loop.md. Two sentences are added there: the reference is saved at approval so it cannot change, and a kickback after a spent budget goes to `clarify`.

## Not in this piece
- The gauntlet bar fields in the contract and their lint: slice 3: Contract v2 and the ready-gate lint; this slice extends them with the saved copy, its hash and the lint's file and hash check, which it owns.
- The clarify sub-state, the question box, and the approval of the reference and its budget: slice 4: Shaping sub-states in /shape; this slice adds only the saving of the reference slice 4's clarify step approves.
- The crew starter and the both-orders helper: slice 10: Crews and computer resources, reused here.
- The loop board's round and last verdict: slice 16: Boards and notifications.
- A recorded real gauntlet run: slice 20: Replay harness rewrite and real runs.

## Decided
- The reference is approved in `shaping:clarify` with a budget (decision record, points resolved in the note), and saved at approval, because the most common gauntlet failure is a vague or moving reference (research "Loops and goals").
- The work wins only when preferred in both orders by every critic, because a comparison runs in both orders and a split verdict is not a win (decision 44); a panel is a unanimous vote, not a majority, so a second critic can only make the bar harder.
- A spent budget goes back to `clarify`, because the reference or the criteria need a decision, and only the person makes decisions (decision 5).
- Critics from another model family need the person's agreement in shaping, because the criteria, the reference and the work then leave for another vendor's service.
- Screen-check becomes a named check here because the gauntlet is the first bar that needs it by name; the build bar uses the same shape.

## Data
- The saved reference under the piece's folder in `.agents/references/<issue number>-<short name>/`, committed with the spec on the spec branch, with its hash in the contract. It is project data and stays after the merge as the record of what the person approved. The area map (slice 5) leaves hidden top-level folders such as `.agents/` out, so the project check stays green.
- Per round, the A and B mapping, the verdicts and the rendered pictures' paths in the run folder, which git ignores; the pictures go to the main folder's walk-through folder, never into a worktree.

## Leaves the tool
The saved reference reaches GitHub with the spec branch. Critics from another model family send the criteria, the reference and the work to that vendor's service, only with the person's agreement recorded in shaping. Nothing else new leaves the tool.

## Must still hold
- The walk-through's means, order and picture folder. Check: `walk-through-eyes.sh`.
- Screen-check never claims a screen is accessible, compliant or good. Check: `screen-rules.sh`.
- The kit never reads another tool's stored login. Check: `no-stored-logins.sh`.
- A critic never sees the builder's transcript. Check: `crews-rehearsal.sh` from slice 10.
- No issue numbers and no attribution lines in tracked files. Check: `validate-kit.sh`.

## Relies on
- `clarify/SKILL.md`, `second-opinion/SKILL.md`, `screen-check/SKILL.md`, `section-builder/SKILL.md` step 6 and its walk-through means: on main today.
- The lint and gauntlet bar fields: slice 3. The clarify sub-state: slice 4. The area map: slice 5. The frozen bar: slice 6. Attempt notes and statuses: slice 7. The fixed reviewer verdict: slice 8. The run controller: slice 9. The crew starter, comparison helper and browser ownership: slice 10.

## Reach and risk
Boundary: the `implement` skill's run references and scripts, the `second-opinion`, `screen-check` and `clarify` skills, `/shape`, WORKFLOW.md, README.md, docs/COMPATIBILITY.md, docs/SOURCES.md, the root AGENTS.md checks list.
Reaches: the walk-through (`walk-through-eyes.sh`), screen rules (`screen-rules.sh`), reviews (`named-reviewer-is-a-person.sh`), prototypes in clarify (`prototype-recipes.sh`, `existing-artifact.sh`), stored logins (`no-stored-logins.sh`).
If it breaks: a critic approves weak work, or every gauntlet piece bounces back to shaping; the person sees it in review or on the shaping board. Undone by reverting the slice's pull request.
Depends on: 3, 4, 5, 6, 7, 8, 9, 10.
Loop module: build, because blinding, order and verdict rules are judged by stand-in critics in a rehearsal.
Crew: default.

## Under the hood
Add a gauntlet path to slice 9's run controller (render, blind, compare in both orders, tally, kickback), using slice 10's starter and comparison helper. Add the comparison mode to `second-opinion`, the named-check output to `screen-check`, the approval step to `clarify` and `/shape`, and the file and hash check to slice 3's lint. Reuse the existing `existing-artifact.md` route in `clarify` for a mock the person already has, since an approved mock is a natural reference. Add `gauntlet.sh` (rule-shape) and `gauntlet-rehearsal.sh` (throwaway project, stand-in critics, stand-in renderer, stand-in GitHub); extend `screen-rules.sh`. Canonical skills change: five questions in the pull request, SOURCES.md credits, adapters rebuilt, validator run, humanizer on the prose, no issue numbers.

## Evidence
A rule-shape check with each rule proved load-bearing; a script rehearsal with stand-in critics and renderer in a throwaway project. The real gauntlet run is slice 20's.

## Size
Two sittings: the loop, blinding and rehearsal first; then the clarify approval step, second-opinion's mode, screen-check's named output and the documents.

## Consistency notes
- The reference is approved, with its budget, in slice 4's `shaping:clarify` step. This slice owns saving the approved reference as a fixed copy, its path and hash in the contract, and the lint's check of both, extending slice 3's gauntlet bar.
- The gauntlet is driven by the run controller, `implement/scripts/run.py` (slice 9); the drafts' "run script" means that script.
- The area map leaves hidden top-level folders such as `.agents/` out (slice 5), so the saved reference needs no area of its own.
