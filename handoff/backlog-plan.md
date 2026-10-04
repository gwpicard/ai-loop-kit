# Backlog plan for v1, after the move to a new repository

Read on 2 October 2026 from the live repository gwpicard/ai-build-kit: 63 open issues and 8 open
pull requests. Revised the same day for decisions 56 to 63: AI Loop Kit is built in a new private
repository, gwpicard/ai-loop-kit, from a clean snapshot; AI Build Kit returns to a fixes-only 0.19
line, releases v0.19.3, keeps fixes for a stated period and is then archived; no founded project
is migrated.

Nothing on GitHub has been changed. Every operation below waits for the maintainer's yes at that
step (decisions 27, 54 and 60).

Each issue gets exactly one action:

- **TRANSFER, fold into slice N**: moved to gwpicard/ai-loop-kit with GitHub's transfer, then
  given a comment naming the slice issue and closed as a duplicate of it, so the slice is the one
  place the work is tracked. The issue's history moves with it.
- **TRANSFER, after 1.0**: moved to gwpicard/ai-loop-kit, given a comment and the `after-1.0`
  label, and left open.
- **CLOSE**: closed as not planned in gwpicard/ai-build-kit, with a comment giving the reason.
  This covers what v1 replaces, what only measured the old model, and anything that only mattered
  for moving founded projects (decision 63).
- **KEEP (0.19)**: left open in gwpicard/ai-build-kit for the 0.19 line, with a comment. A bug in
  AI Build Kit's current skills that people still meet.
- **KEEP (0.19) + slice N**: as KEEP, and the same bug exists in the snapshot AI Loop Kit starts
  from, so the named slice must carry the fix too. The slice names the issue by its title (slice
  files carry no numbers); "Slice text changes" at the end lists the lines to add.

Slice names used below (BRIEF.md, with slice 22 as decisions 62 and 63 now define it):
1 Principle, audience and the loop kit · 2 Label model and gate script · 3 Contract v2 and the
ready-gate lint · 4 Shaping sub-states in /shape · 5 Area map for the whole project · 6 Frozen-bar
enforcement · 7 Build and fix loop modules · 8 Automatic reviewer · 9 Run controller · 10 Crews
and computer resources · 11 Goal loop module · 12 Gauntlet loop module · 13 Merge policy ·
14 /deploy replacing /ship · 15 Safety boundary for runs · 16 Boards and notifications ·
17 /maintain absorbs /sync · 18 Compact masterplan and behaviour deltas · 19 Codex parity ·
20 Replay harness rewrite and real runs · 21 Documentation sweep · 22 The AI Loop Kit names ·
23 Release v1.0

---

## The GitHub operations, in order

The repository itself (create it, first commit, settings) is in move-plan.md, steps B1 to B3.
Everything here starts once B1 and B2 are done. Every step is marked **(yes)**: it changes
something online and waits for the maintainer's yes at that step.

### What GitHub's transfer does and does not do

- **Same owner only.** An issue can be transferred only between repositories owned by the same
  account. Both are under `gwpicard`, so this holds. The person needs write access to both.
- **Public to private is allowed; private to public is not.** gwpicard/ai-build-kit is public and
  gwpicard/ai-loop-kit is private, so the transfer works. A transferred issue becomes private:
  its old address redirects to the new one, and anyone without access to the new repository gets
  a "not found" page until 1.0 makes it public. All 63 open issues were opened by the maintainer,
  so no outside reporter loses sight of their own report.
- **Comments, the body, the author and assignees move with the issue.** An assignee stays only
  if they can see the new repository (only #5 has one, the maintainer).
- **Labels and milestones are kept only where the target already has one of the same name.** Any
  other label is dropped without a word. So every label below is created in gwpicard/ai-loop-kit
  before the first transfer. No open issue has a milestone.
- **The issue gets a new number** in gwpicard/ai-loop-kit. References to the old number, in
  commits, pull requests and other issues, redirect to it.
- **Pull requests cannot be transferred.** The eight open pull requests are closed in place.
- **One issue at a time.** The transfer is a GraphQL mutation (`gh issue transfer <number>
  gwpicard/ai-loop-kit`) or the "Transfer issue" button. GraphQL is refused from Claude Code
  sessions in this environment, so the maintainer runs the transfers from their own terminal or
  the web page. Comments, labels and closes can then be done through the REST API.
- **Not confirmed: sub-issue links.** Whether a parent and sub-issue link survives when one side
  moves to another repository is not documented clearly. Step 2 below transfers one sub-issue
  first to see, and the links are added back in the new repository where they were lost.

### The steps

1. **Labels in gwpicard/ai-loop-kit. (yes)** Make sure each label a transferred issue carries
   exists with the same name: `area:docs`, `area:release`, `area:skills`, `area:tests`, `bug`,
   `chore`, `documentation`, `enhancement`, `epic`, `feature`, `needs-answers`, `ready`,
   `status:blocked`. Move-plan B3 copies today's whole set; this step adds one new label,
   `after-1.0` ("Waits for after the AI Loop Kit 1.0 release"), which exists nowhere today.
2. **One trial transfer. (yes)** Transfer #308 (after 1.0, a sub-issue of #255). Check in the new
   repository: the comments are there, the labels came across, the old address redirects, and
   whether the link to #255 survived. If the trial shows anything unexpected, stop and revise this
   list before step 3.
3. **The remaining 35 transfers. (yes, one yes for the list or one per issue, as the maintainer
   prefers)** In this order, so each parent moves before its sub-issues:
   - after 1.0: #9, #6, #7, #8, #58, #5, #10, #150, #196, #309, #319, #322
   - folded: #288, #290, #291, #12, #287, #98, #242, #292, #293, #296, #298, #299, #302, #303,
     #305, #307, #311, #314, #315, #316, #317, #318, #321
4. **Links back in gwpicard/ai-loop-kit. (yes)** If step 2 showed sub-issue links are lost, add
   #6, #7 and #8 back under #9, and #5 under #58. The other links lead to issues that close.
5. **After-1.0 issues in gwpicard/ai-loop-kit. (yes)** For each of the 13: post the comment
   below, add `after-1.0`, and remove `ready` where it has it (#5, #9, #10, #196, #319, #322), so
   today's `/implement queue` in the new repository never takes one up beside the slices
   (decision 55). Rewrite #9's title and body as drafted below.
6. **Folded issues in gwpicard/ai-loop-kit. (yes)** Needs the epic and slice issues from
   move-plan B4. For each of the 23: post the comment below with the slice issue's number filled
   in, then close it as a duplicate of that slice issue. Where GitHub offers no "duplicate"
   reason through the route used, close it as not planned; the comment carries the link either
   way.
7. **Closes in gwpicard/ai-build-kit. (yes)** Close the 18 CLOSE issues as not planned, each with
   its comment. Close the epic #255 last, once its parts have each been transferred or closed, so
   its comment is true when it is posted.
8. **Comments on the kept issues in gwpicard/ai-build-kit. (yes)** Post the comment on each of
   the 9 KEEP issues. No label changes.
9. **The pull requests in gwpicard/ai-build-kit. (yes)** Close #346 with the pointer to
   gwpicard/ai-loop-kit's first commit (needs move-plan B2's commit). Close #341 and the six
   drafts with their comments. Do not tick "delete branch": every branch stays, because slices
   read mechanisms from them.
10. **#313 closes with v0.19.3. (yes, the merge of move-plan A1)** A1's pull request ports the
    Codex GitHub access fix, so its description carries the closing line for #313. Check after the
    merge that #313 closed; if it did not, close it as completed with a pointer to that pull
    request.

Comments posted in gwpicard/ai-build-kit are public and name gwpicard/ai-loop-kit, which stays
private until 1.0. Each says so, so a reader who cannot open the link knows why.

---

## Summary table

### Issues

| # | Title (short) | Action | Target |
|---|---|---|---|
| 5 | Better frontend skill? | TRANSFER, after 1.0 | stays under #58 |
| 6 | Nothing measures /start | TRANSFER, after 1.0 | stays under #9 |
| 7 | The kit has never met a project it did not write | TRANSFER, after 1.0 | stays under #9 |
| 8 | Nothing carries a build to a shipped app across shapes | TRANSFER, after 1.0 | stays under #9 |
| 9 | Evaluation system (epic) | TRANSFER, after 1.0, rewritten | slice 20 takes the replay rewrite |
| 10 | Tailored harness | TRANSFER, after 1.0 | none |
| 12 | Nothing says when the kit is 1.0 | TRANSFER, fold | slice 23 (bar), slice 21 (documents) |
| 21 | A run that holds does not record its evidence and save route | CLOSE | v1: slices 6, 20 |
| 55 | Replay baseline predates the three-path change | CLOSE | v1: slice 20 |
| 58 | Screens look and work right (epic) | TRANSFER, after 1.0 | none |
| 98 | Parts of a parent land together as one PR | TRANSFER, fold | slice 9 |
| 150 | Fit check wording assumes a workplace team | TRANSFER, after 1.0 | none (flagged; could fold into slice 4) |
| 151 | Hosting request cannot mark build-time values | KEEP (0.19) + slice 14 | still waits on the companion's maintainer |
| 173 | Founding shows the recipe menu only after stand-up | KEEP (0.19) + slice 14 | |
| 176 | One recipe still named only in the completion report | KEEP (0.19) + slice 14 | |
| 187 | Recipe line written as a bullet | KEEP (0.19) + slice 14 | |
| 196 | Compare the kit against other systems | TRANSFER, after 1.0 | slice 21 rewrites the README comparison without it |
| 203 | Scenario 5 misses its evidence field | CLOSE | v1: slice 20 |
| 210 | /ship trial-merges on local main | KEEP (0.19) | v1 has no such step (slices 9, 13, 14) |
| 211 | Free-plan note said more than once | KEEP (0.19) + slices 14 and 20 | |
| 212 | Recipe checker and UTC dates | KEEP (0.19) + slice 14 | (flagged: small enough to fix in both now) |
| 213 | Scenario 54 fixture runs 0 tests on some Node | CLOSE | lesson to slice 20 |
| 214 | Small follow-ups from 28 and 29 September reviews | KEEP (0.19) + slice 14 | pointer-script part is 0.19 only |
| 241 | Each recipe states its promote route | CLOSE | v1: slice 14 |
| 242 | Fresh founding leaves AGENTS.md headroom | TRANSFER, fold | slice 21 |
| 244 | Run the owed replay scenarios 56 and 57 | CLOSE | v1: slice 20 |
| 255 | Lessons from other projects (epic) | CLOSE | its parts spread below |
| 287 | Run the 1.0 readiness tests | TRANSFER, fold | slice 23 (with slices 14, 20, 21) |
| 288 | Goal, loop or gauntlet loop (epic) | TRANSFER, fold | slices 11 and 12 (and 7) |
| 289 | /what-now route back for an unshaped piece | CLOSE | v1: slices 2, 16 |
| 290 | A run leaves a follow-up; the answer re-enters | TRANSFER, fold | slice 4 (run side in slice 9) |
| 291 | Run's live page from one dashboard template | TRANSFER, fold | slice 16 |
| 292 | Apply four round 2 decisions | TRANSFER, fold | slice 5 (test-job part); others to 7, 13, 15 |
| 293 | Update the Coolify recipe for previews | TRANSFER, fold | slice 14 |
| 295 | Integration branch rather than one at a time? | CLOSE | v1: slices 9, 13 |
| 296 | A merge applies only affected document changes | TRANSFER, fold | slice 18 |
| 297 | "Merge when green" said in chat | CLOSE | v1: slice 13 |
| 298 | Walk-through uses only a browser on this computer | TRANSFER, fold | slice 10 |
| 299 | Deny rules refuse every force-push spelling | TRANSFER, fold | slice 15 (flagged) |
| 300 | Merge question says what was not seen; "try it" piece | CLOSE | v1: slices 8, 13, 16 |
| 301 | Assignee owes a waiting answer; since when | CLOSE | v1: slice 16 (team part to #308) |
| 302 | Changelog entries kept short | TRANSFER, fold | slice 18 |
| 303 | Interview uses the question box; worker passes question up | TRANSFER, fold | slice 4 (worker part replaced by slice 7) |
| 304 | Under a goal, /implement loads run rules first | CLOSE | v1: slices 2, 9, 11 |
| 305 | Compact masterplan and authoritative records | TRANSFER, fold | slice 18 |
| 306 | Full record of who checked a change | CLOSE | v1: slices 6, 8, 9 |
| 307 | Safer parallel runs | TRANSFER, fold | slice 10 |
| 308 | Working as a team | TRANSFER, after 1.0 | none (trial transfer) |
| 309 | Programmes, and parts that have parts | TRANSFER, after 1.0 | none |
| 310 | Simplification campaign route | CLOSE | v1: slices 11, 17 |
| 311 | Record per computer; monthly trim asks | TRANSFER, fold | slice 17 (per-computer record in slice 10) |
| 312 | Page for builders another tool starts | CLOSE | v1: slices 2, 9, 15 |
| 313 | Codex cannot reach GitHub through gh | KEEP (0.19) + slices 19 and 16 | closes with v0.19.3 |
| 314 | Do the next step in the same turn | TRANSFER, fold | slice 9 |
| 315 | Walk through a whole chain | TRANSFER, fold | slice 13 |
| 316 | Long run stops carrying finished build detail | TRANSFER, fold | slice 10 |
| 317 | Record what was tried when a run parks a piece | TRANSFER, fold | slice 7 |
| 318 | Risk questions when adopting a project | TRANSFER, fold | slice 5 |
| 319 | Detect half-wired rules | TRANSFER, after 1.0 | none (flagged; could join slice 17) |
| 321 | A failed task leaves a checked working state | TRANSFER, fold | slice 9 (script brought over by slice 7) |
| 322 | Measure richer dependency analysis | TRANSFER, after 1.0 | the dependency pilot the design names |
| 323 | Commands look up only relevant knowledge | CLOSE | v1: slices 3, 18 |
| 324 | Maintenance migrates records without losing rules | CLOSE | migration only (decision 63) |

Changes from the version before the move: #292 is folded into slice 5 rather than rewritten in
place, since nothing in it applies to the 0.19 line; #196 waits for after 1.0 rather than folding
into slice 21; #299 goes to slice 15, which is where slice 2 now sends the force-push rules; #324
closes, since it only served migration; #210, #211, #212, #214 and #313 stay for the 0.19 line
rather than being closed or folded; and the "KEEP as is" recipe and founding bugs now also name
slice 14.

### Pull requests

| # | Title (short) | Branch | Action | Reused by |
|---|---|---|---|---|
| 330 | Attempt-history candidate (for #317) | `gwpicard/v1-repair-317-r3-20261002` | CLOSE | slice 7 (lesson only) |
| 333 | Integration flow checkpoint (for #295) | `gwpicard/v1-build-295-20261002` | CLOSE | slice 9 (lesson only) |
| 335 | Final integration-flow candidate (for #295) | `gwpicard/v1-repair-295-r3-20261002` | CLOSE | slice 9 (lesson only) |
| 336 | Waiting-date candidate (for #301) | `gwpicard/v1-repair-301-r3-20261002` | CLOSE | slice 16 (lesson only) |
| 341 | v1 overnight batch | `gwpicard/v1-overnight-integration-20261001` | CLOSE | slices 4, 7, 8, 9, 10, 15 |
| 342 | Shared-output repair findings (for #295) | `gwpicard/v1-priority-repair-295-r4-20261002` | CLOSE | slice 9 (lesson only) |
| 344 | Selective context lookup (for #323) | `gwpicard/v1-priority-build-323-20261002` | CLOSE | none |
| 346 | Agentic loop design note | `design/agentic-loop` | CLOSE with pointer | every slice: the notes are in the new first commit |

The six drafts target the batch branch, not `main`. Closing a pull request never deletes its
branch, and none of these is merged, so "delete branch on merge" does not touch them either. The
branch `gwpicard/v1-build-305-20261001`, which has no open pull request, also stays: slice 18
starts from the compact masterplan attempt on it.

What each slice reads from the batch branch, from the slice files as they stand:

- slice 4: the clarify question box and `question-box.sh`; "Answers already on the piece" in
  `shape/SKILL.md`, for kickback intake.
- slice 7: `implement/scripts/recovery.py` (`preserve`), `section-builder/references/task-handoff.md`,
  `section-builder/references/task-context-capabilities.md`, `failure-recovery.sh`,
  `task-handoff.sh` and their fixtures.
- slice 8: the fresh-session route in `task-context-capabilities.md`, once slice 7 has brought it.
- slice 9: same-turn continuation in `implement/references/running-longer.md`; `recovery.py
  baseline` and `eligible`, once slice 7 has brought the script.
- slice 10: the rule that a walk-through uses only a browser on this computer, and the resource
  ownership rules in `task-handoff.md` (see "Slice text changes": slices 7 and 10 both claim to
  bring that file over).
- slice 15: the force-push deny rules (slice 2 sends them there; slice 6 also offers to bring
  them; see "Slice text changes").
- slice 18: the compact masterplan attempt on `gwpicard/v1-build-305-20261001`, with its six
  reviewed faults fixed.
- Not carried into v1: the parked state, the "try it" opt-in, shaping inside a run, the route back
  for an unshaped piece, the goal trigger, the half-wired rule detector and the selective context
  lookup.

### Epics

| Epic | Becomes |
|---|---|
| #216 Loop-first redesign (closed) | Stays closed in gwpicard/ai-build-kit. The new epic "AI Loop Kit v1" in gwpicard/ai-loop-kit takes its place; slice 21 marks the loop-first design notes as replaced. |
| #255 Lessons from other projects | Closed as not planned in gwpicard/ai-build-kit, after its open parts have each been transferred or closed. Its completed parts stay where they are. |
| #288 Goal, loop or gauntlet loop | Transferred and folded: answered by the design note, built by slices 7, 11 and 12. Its two sub-issues fold into slices 4 and 16. |
| #9 Evaluation system | Transferred, rewritten as the after-1.0 evaluation epic, with the replay rewrite taken out (slice 20). Keeps #6, #7 and #8 as sub-issues. |
| #58 Screens | Transferred, after 1.0, with its one open part, #5. |

### #12 and #287

Both are transferred and folded rather than rewritten. The 1.0 bar is now decision 26 as amended
by decision 63, written in the design note's "1.0" section: the new model complete, real runs
recorded (one for each loop module, one `/deploy` for each recipe) and the compact masterplan.
Moving founded projects is no longer part of it. That bar becomes slice 23's Done when, and the
document list in #12 becomes part of slice 21. Rewriting #12 and #287 in place would leave three
places describing one bar. The old bar's watched trial with people who do not read code no longer
fits the audience (decision 51), so it is dropped, not carried.

---

## Comments for the issues that transfer

These are posted in gwpicard/ai-loop-kit after the transfer (steps 5 and 6). `<slice N issue>`
and `<epic issue>` are filled in from move-plan B4.

### After 1.0

#### #5 Better frontend skill?

> Moved here from AI Build Kit. This waits for after the 1.0 release. The AI Loop Kit v1 epic
> (<epic issue>) changes labels, shaping and founding, and nothing here depends on it. When it is
> picked up, founding will be the v1 founding, so step 11 and the stack section it names should
> be read again then. In v1 the screen rules become a check a piece's bar can name (slice 3:
> Contract v2 and the ready-gate lint), so shape it against that.

#### #6 Nothing measures /start

> Moved here from AI Build Kit. This waits for after the 1.0 release. Slice 20: Replay harness
> rewrite and real runs (<slice 20 issue>) rewrites the harness and its scenarios for the new
> model, so scenarios 24, 25 and 26 will be rewritten or renumbered there. The 1.0 bar asks for
> one real run for each loop module and one `/deploy` for each recipe, not for founding, so
> measuring founding comes after the release, against the rewritten harness. Its goal stands: the
> first command a person types is one that has been watched. One change to carry: the audience is
> now builders who know Git, branches and pull requests, so the simulated person should answer as
> one of them, still vaguely.

#### #7 The kit has never met a project it did not write

> Moved here from AI Build Kit. This waits for after the 1.0 release, for the same reason as #6:
> slice 20 rewrites the harness, and an adoption fixture should be built on the new one. In v1,
> adopting a project also writes the whole-project area map (slice 5: Area map for the whole
> project), so the grading should add one check: whether every folder of the adopted project is
> claimed by an area, and whether the kit asked rather than guessed where it could not tell.

#### #8 Nothing carries a build to a shipped app across shapes

> Moved here from AI Build Kit. This waits for after the 1.0 release. Slice 20 records one real
> run for each loop module and one `/deploy` for each recipe, which is the short-horizon half of
> this. The long horizon asked for here, a ten-to-sixteen-piece backlog carried to a running app
> across project shapes, is not part of the 1.0 bar. When it is picked up, `/build --auto` reads
> as a v1 run over all ready pieces, and the defects it lists (an integration branch the scripts
> ignore, a plan one task wrote that task fourteen no longer honours) are what the run controller
> in slice 9 is built to catch, so this becomes its long-run test.

#### #9 Evaluation system (rewritten)

New title: **Evaluation after v1: a soundness audit of the built software, and simulated people**

Summary of the new body:

- **What v1 already covers, and where.** Slice 20 rewrites the replay harness: it grades the
  world a run leaves (git state, issue labels, the run record), not only the transcript, and
  reports for each model whether a scenario passes on every one of several clean runs (pass^k).
  Slice 6 records fresh evidence mechanically. Slice 8's automatic reviewer gives a "code sound"
  verdict on every piece. Slice 17's drift, copied-code and unused-code reads file chore pieces.
  Those parts of the old Level 1 and Level 2 are therefore out of this epic.
- **What remains, after 1.0.**
  1. A fuller soundness audit of a whole project in plain words: security, data safety,
     correctness past the happy path, cost and scale, the parts it leans on. It is a read that
     files `type:chore` or `type:bug` pieces, never a gate and never a score (decision 47
     excludes a coverage or mutation score as a gate).
  2. Simulated people for the scenarios where the person's answers matter (founding, clarify),
     with the guards against an over-cooperative simulator from the original research list.
  3. The prior-version delta: an assertion is kept only if it passes with the skill and fails
     without it.
  4. The research list and sources, kept as they are.
- **Sub-issues:** #6, #7, #8 stay.
- **Done when:** a written design for items 1 to 3 against the v1 harness; item 1 runs on one
  real project and files its findings as pieces; items 2 and 3 each cover at least one scenario.
- Labels: keep `epic`, `area:tests`; add `after-1.0`; remove `ready`.

Comment to post with the rewrite:

> Moved here from AI Build Kit and rewritten for v1. The replay rewrite, world-state grading and
> pass^k move to slice 20: Replay harness rewrite and real runs, the evidence record to slice 6:
> Frozen-bar enforcement, and the per-piece "code sound" verdict to slice 8: Automatic reviewer.
> What is left here is the whole-project soundness audit and simulated people, after 1.0.

#### #10 Tailored harness

> Moved here from AI Build Kit. This waits for after the 1.0 release and is not part of v1. v1 is
> Claude Code first, with Codex mirroring the same scripts and other agents getting the one-piece
> core (decision 23); a coding agent of the kit's own would be a fourth platform to keep in step
> with the gate script. It stays open as a question for later.

#### #58 Screens look and work right without a designer

> Moved here from AI Build Kit. This waits for after the 1.0 release. Two of its three parts are
> done; the one left, #5, is unrelated to the loop. In v1 the screen rules become a check a
> piece's bar can name, which slice 3: Contract v2 and the ready-gate lint provides, so #5 should
> be shaped against that.

#### #150 Fit check wording assumes a workplace team

> Moved here from AI Build Kit, where the 0.19 line takes fixes only and this is a rewording with
> open questions. It waits for after the 1.0 release unless the maintainer folds it into slice 4.
> Slice 1: Principle, audience and the loop kit changes the audience to builders who direct
> agents, and slice 4: Shaping sub-states in /shape moves the risk notice and its acceptance into
> shaping, so `fit-check.md` moves under it. Reword it against the text as it is after those land.
> The time-horizon rule ("yes, later") is still needed in v1, because the acceptance now has to
> exist before the ready gate. The open questions stay with the maintainer.

#### #196 Compare the kit against other systems

> Moved here from AI Build Kit. This waits for after the 1.0 release. Slice 21: Documentation
> sweep rewrites the README's "How it compares" from the design note's companion,
> `docs/design/agentic-loop-research.md`, which already sets out where the kit stands among
> related projects. The measured comparison asked for here, the same project built with five
> systems and the output judged, is a larger experiment, and it only makes sense once v1 exists.

#### #308 Working as a team

> Moved here from AI Build Kit. This waits for after the 1.0 release. When it is picked up, read
> it against v1: a team's review rule maps to `review:person`, the gate script is the one writer
> of labels and can record which session acted, and the answer-owner part of "The person assigned
> to a waiting piece owes its answer", closed in AI Build Kit, belongs here now.

#### #309 Programmes, and parts that have parts

> Moved here from AI Build Kit. This waits for after the 1.0 release. v1 covers part of it: a run
> can take any set of ready pieces and integrate them on one branch, so work bigger than one
> parent no longer needs its own route. v1 keeps parents only where pieces truly belong together
> and has no nesting, so whether nested parts are wanted at all is the maintainer's question for
> later.

#### #319 Detect half-wired rules

> Moved here from AI Build Kit. This waits for after the 1.0 release. The overnight batch built a
> bounded detector for it, which v1 does not reuse. In v1 masterplan constraints become rules in
> the project check (slice 17: /maintain absorbs /sync), which closes much of the gap; whether a
> detector is still worth having is a question for after the release. The batch branch in
> gwpicard/ai-build-kit keeps the code.

#### #322 Measure richer dependency analysis

> Moved here from AI Build Kit. This is the dependency pilot the v1 design names, after 1.0. Call
> graphs, language servers, stored indexes and the rest wait for it (decisions 39 and 47). When it
> runs, it compares against v1's reach fields rather than today's reach check, and also measures
> how closely each recorded `Boundary:` matched what the diff changed.

### Folded into a slice

Each is closed as a duplicate of the slice issue straight after its comment.

#### #12 Nothing says when the kit is 1.0 (slices 23 and 21)

> Moved here from AI Build Kit and folded into the AI Loop Kit v1 epic. The 1.0 bar is now the one
> agreed on 2 October 2026 and written in the design note's "1.0" section: the new model complete
> with all four loop modules, runs, kickback, `/deploy` and both boards; real runs recorded, one
> for each loop module and one `/deploy` for each recipe; and the compact masterplan. AI Loop Kit
> is for new projects, so moving projects founded with AI Build Kit is not part of the bar. That
> bar is the Done when of slice 23: Release v1.0 (<slice 23 issue>). The list of documents here
> (quickstart, the walkthroughs from an empty folder and for adoption, troubleshooting, the update
> guide, known limits, the compatibility matrix and the worked examples) is part of slice 21:
> Documentation sweep (<slice 21 issue>). The watched trial with people who do not read code is
> not carried over, since the audience is now builders who know Git, branches and pull requests.
> The counts in the old bar (external users, projects reaching `/ship`) are not part of the new
> one; if the maintainer wants them back, they belong in slice 23.

#### #98 Parts of a parent land together as one PR (slice 9)

> Moved here from AI Build Kit and folded into slice 9: Run controller (<slice 9 issue>). In v1
> every build of several pieces is a run: each piece builds on its own branch, joins one
> integration branch one at a time with the full checks on the combined result, and `main`
> changes once, through one pull request. So the outcome asked for here is the default, not an
> offer in `/shape`, and the question to the person goes. What carries over: the project check
> runs on a pull request into any branch, `main` is brought into the integration branch so a
> conflict shows inside the piece that meets it, and the warning from #8 that scripts must not
> quietly assume `main`.

#### #242 A fresh founding leaves AGENTS.md headroom (slice 21)

> Moved here from AI Build Kit, where the index template this measures is not in the 0.19 line,
> and folded into slice 21: Documentation sweep (<slice 21 issue>). That slice goes through the
> foundation templates after every other slice has added its lines, which is the right point to
> measure the founded `AGENTS.md` against its ceiling and record the headroom decision; a margin
> set earlier would be spent by the slices after it.

#### #287 Run the 1.0 readiness tests (slice 23)

> Moved here from AI Build Kit and folded into the AI Loop Kit v1 epic. The tests before 1.0 are
> now slice 23: Release v1.0's Done when (<slice 23 issue>), against the new bar. Line by line:
> the real `/implement queue` run becomes the real runs, one for each loop module, in slice 20:
> Replay harness rewrite and real runs; the live replays of scenarios 56 and 57 become slice 20's
> rewritten scenarios; the recipe promote routes are replaced by one real `/deploy` for each
> recipe in slice 14: /deploy replacing /ship; the headroom decision is in slice 21:
> Documentation sweep. The nine-line re-check of real use carries into slice 23 for the lines
> that still mean something in v1 (plain words, runs, parallel work, merging, hosting, records,
> adopted projects, acting beyond the project), each tried on one real project.

#### #288 Goal, loop or gauntlet loop (slices 11 and 12)

> Moved here from AI Build Kit. Answered by the v1 design and folded into its slices. The kit
> becomes a loop kit, with four loop modules (fix, build, goal, gauntlet), chosen in shaping by
> the kind of bar the piece needs and recorded as a `loop:` label. The gauntlet joins as a loop
> module, not a command, with a reference the person approves in clarify. "Software factory" is
> not a name the kit uses. Build and fix are slice 7, goal is slice 11: Goal loop module (<slice
> 11 issue>) and gauntlet is slice 12: Gauntlet loop module (<slice 12 issue>). Its two
> sub-issues fold into slice 4 (#290) and slice 16 (#291).

#### #290 A run leaves a follow-up; the answer re-enters (slice 4)

> Moved here from AI Build Kit and folded into slice 4: Shaping sub-states in /shape (<slice 4
> issue>), with the run side in slice 9: Run controller. In v1 what a run cannot settle is a
> kickback: the piece goes to `clarify`, `research` or `spec` with a Kickback section on the same
> issue, its branch is kept, and the run carries on with what does not depend on it. The
> decisions here carry over: one section on the original issue, an answer reconciled through
> shaping and the fresh readiness check before it builds, facts settled by research with no
> person, and a comment alone never making a piece ready. What does not carry: a piece becoming
> buildable again inside the same run, since shaping no longer happens inside a run. The batch's
> "Answers already on the piece" reading is brought over by slice 4; the rest of the batch's
> implementation is not.

#### #291 Run's live page from one dashboard template (slice 16)

> Moved here from AI Build Kit and folded into slice 16: Boards and notifications (<slice 16
> issue>). The loop board is this page: one status file written by a script, a local HTML page,
> and a live artifact on Claude, showing each run's status, running time and counts, and each
> piece's status, loop module, attempts, progress and what it could not check, with an activity
> log. The open questions are answered by the design note's "Boards" section.

#### #292 Apply four round 2 decisions (slice 5, with parts to 7, 13 and 15)

> Moved here from AI Build Kit, where none of these four applies: the round 2 work they amend is
> not in the 0.19 line. Each now has a v1 home. The test job: the rule that recognises an adopted
> project's own workflow as its project check also accepts vitest, jest, rspec, `npm test`,
> `pnpm test`, `yarn test`, `go test`, `cargo test` and reusable workflows that call a test job,
> with a case for each in `adopted-ci-rehearsal.sh`; that is a Done when line of slice 5: Area
> map for the whole project (<slice 5 issue>), which already holds the adopted CI rules. The merge
> confirmation box belongs to slice 13: Merge policy. The missing-tool rule is replaced by the
> builder's "environment failed" status in slice 7: Build and fix loop modules, which retries and
> then pauses the run rather than skipping the piece. The override for confidential content goes
> to slice 15: Safety boundary for runs, which decides what a run's worktree may carry.

#### #293 Update the Coolify recipe for previews (slice 14)

> Moved here from AI Build Kit and folded into slice 14: /deploy replacing /ship (<slice 14
> issue>), which updates both recipes for per-branch previews and records one real `/deploy` run
> for each. The facts here (MCP 3.6.0 and later switch previews on, a released rollback call still
> to come) are what that run on Coolify checks, and the rule stands that a `How it works:` line
> changes only if the run shows it. AI Build Kit's 0.19 recipe keeps its older wording, which
> still works: the button it names is still there.

#### #296 A merge applies only affected document changes (slice 18)

> Moved here from AI Build Kit and folded into slice 18: Compact masterplan and behaviour deltas
> (<slice 18 issue>). v1 keeps the intent: no branch edits the shared records, and the merge
> applies each piece's change to the record of current behaviour. The per-change stamp goes, as
> decided here.

#### #298 Walk-through uses only a browser on this computer (slice 10)

> Moved here from AI Build Kit and folded into slice 10: Crews and computer resources (<slice 10
> issue>). The run's coordinator holds one browser, and a walk-through never takes another
> worker's or another computer's browser. The rule built on the overnight batch branch in
> gwpicard/ai-build-kit is brought over from there.

#### #299 Deny rules refuse every force-push spelling (slice 15)

> Moved here from AI Build Kit and folded into slice 15: Safety boundary for runs (<slice 15
> issue>), which holds what a run may push: only to its own branches. The force-push rules built
> on the overnight batch branch in gwpicard/ai-build-kit are brought over from there, with their
> documented limits (bundled flags, full-path wrappers, other shells).

#### #302 Changelog entries kept short (slice 18)

> Moved here from AI Build Kit and folded into slice 18: Compact masterplan and behaviour deltas
> (<slice 18 issue>), which sets the size of every project record. The 300-character limit and the
> rule that internal work gets one short line carry over, along with the decision not to truncate
> a fact mechanically.

#### #303 Interview uses the question box; worker passes question up (slice 4)

> Moved here from AI Build Kit and folded into slice 4: Shaping sub-states in /shape (<slice 4
> issue>), where the clarify interview now lives. The question box built on the overnight batch
> branch is brought over from there. The worker half does not carry: in v1 a builder never asks a
> question. It ends with "needs context" or "blocked", and the piece is kicked back to shaping
> (slice 7: Build and fix loop modules).

#### #305 Compact masterplan and authoritative records (slice 18)

> Moved here from AI Build Kit and folded into slice 18: Compact masterplan and behaviour deltas
> (<slice 18 issue>). The compact masterplan is part of the 1.0 bar, since 1.0 fixes the
> project's record format. The decisions here carry over. The earlier attempt on
> `gwpicard/v1-build-305-20261001` in gwpicard/ai-build-kit is the slice's starting point, with
> the six faults its review found fixed. Moving existing projects to the new format is not
> planned: AI Loop Kit is for new projects only.

#### #307 Safer parallel runs (slice 10)

> Moved here from AI Build Kit and folded into slice 10: Crews and computer resources (<slice 10
> issue>): the number of builders suggested from free memory and cores, lowered under pressure
> during the run, a heartbeat that catches a stuck builder, and a model for each role in the
> settings. One part does not carry: stepping into a builder to answer its question, since a
> builder in v1 never asks; it is kicked back.

#### #311 Record per computer; monthly trim asks (slice 17)

> Moved here from AI Build Kit and folded into slice 17: /maintain absorbs /sync (<slice 17
> issue>), which rations `AGENTS.md` lines and sorts the lessons on every visit, and asks about a
> trim rather than putting it off. Facts about one computer go to the computer settings slice 10:
> Crews and computer resources introduces, not the shared `AGENTS.md`. The third gap, the offer
> to move onto the index coming back after a no, only concerns projects founded before the index
> and does not carry.

#### #314 Do the next step in the same turn (slice 9)

> Moved here from AI Build Kit and folded into slice 9: Run controller (<slice 9 issue>). The
> same-turn rule built on the overnight batch branch in gwpicard/ai-build-kit is brought over
> from there.

#### #315 Walk through a whole chain (slice 13)

> Moved here from AI Build Kit and folded into slice 13: Merge policy (<slice 13 issue>). Before a
> run's pull request merges, a smoke test runs the acceptance paths of every piece in the run on
> the run's preview, which tries the joins as one flow. Earlier runs' features are held by the
> guard checks each contract names under `Reaches:` (slice 3).

#### #316 Long run stops carrying finished build detail (slice 10)

> Moved here from AI Build Kit and folded into slice 10: Crews and computer resources (<slice 10
> issue>). The run script starts each builder fresh with only its declared inputs, and the
> coordinator stays small. The task hand-off and task-context references from the overnight batch
> branch are brought onto the new main by slice 7 and given their resource rules here.

#### #317 Record what was tried when a run parks a piece (slice 7)

> Moved here from AI Build Kit and folded into slice 7: Build and fix loop modules (<slice 7
> issue>). v1 has no parked state; a piece that runs out of attempts is kicked back, and each
> attempt carries a note the run script builds from what failed (failing checks, exit codes,
> files touched), so the Kickback section holds what was tried. The batch candidate failed review
> on an interrupted write and is not reused; that case (a stray pending file after a crash) is
> one slice 7's rehearsal should hold.

#### #318 Risk questions when adopting a project (slice 5)

> Moved here from AI Build Kit and folded into slice 5: Area map for the whole project (<slice 5
> issue>). Adoption writes the area map, and the three questions (the area everyone avoids, what
> breaks most, which tests are not trusted) feed it: an avoided or fragile area is named, and an
> untrusted test becomes a chore piece rather than a guard check. The rule that an answer creates
> no caution the person did not choose carries over.

#### #321 A failed task leaves a checked working state (slice 9)

> Moved here from AI Build Kit and folded into slice 9: Run controller (<slice 9 issue>). The
> recovery helper from the overnight batch branch, which keeps failed work and checks a baseline
> before the run carries on, is brought onto the new main by slice 7 (`preserve`), and slice 9
> uses its `baseline` and `eligible` commands. In v1 a red integration branch is bisected and
> only the piece that broke it is kicked back.

---

## Comments for the issues closed in gwpicard/ai-build-kit

Each is closed as not planned. Every comment starts with the same opening line:

> AI Build Kit is now on a fixes-only 0.19 line, and v1 is being built as AI Loop Kit in
> gwpicard/ai-loop-kit, which is private until its 1.0 release.

and then says the following.

### #21 A run that holds does not record its evidence and save route

> This is not a fix the 0.19 line will take. In AI Loop Kit the agent no longer keeps this record:
> the gate script writes the evidence before a piece can leave building (each command run, its
> exit code, the commit, and the same check failing before and passing after), and every build
> ends in a pull request, so the save route no longer varies. The replay rewrite there grades the
> world a run leaves, so a missing record shows as a failed state, not a missed field.

### #55 Replay baseline predates the three-path change

> A full pass against v0.17.0 would measure a release the 0.19 line has already moved past, and
> AI Loop Kit rewrites the harness and its scenarios and writes a new baseline. The point about not
> comparing rates across driving models carries into that rewrite.

### #203 Scenario 5 misses its evidence field

> Working out which of the three explanations holds would serve only the old harness. AI Loop
> Kit's rewritten harness grades the issue state itself, not the transcript, which rules out the
> second explanation by construction. If a 0.19 fix needs scenario 5 to grade cleanly, reopen this.

### #213 Scenario 54 fixture runs 0 tests on some Node

> The 0.19 line takes fixes to the kit, not to replay fixtures, and AI Loop Kit rewrites this
> scenario, since `/ship` becomes `/deploy` there. The lesson goes with it: a rewritten fixture
> gives the same test count on every Node the harness supports, or the harness refuses to start
> and says why. If a 0.19 fix needs scenario 54, reopen this.

### #241 Each recipe states its promote route

> The promote step this asks about is part of the loop-first redesign, which is not in the 0.19
> line. AI Loop Kit settles it the other way: a merge to `main` goes live, and a preview exists for
> each branch rather than as a stage between merge and live, so no recipe has a promote route. One
> real `/deploy` run for each recipe is part of its 1.0 bar.

### #244 Run the owed replay scenarios 56 and 57

> Scenarios 56 and 57 test shaping to the loop-first bar and a `/implement queue` run, neither of
> which is in the 0.19 line. AI Loop Kit writes their successors and records live runs, one for
> each loop module.

### #255 Lessons from other projects (epic)

> Its first twelve parts are done. The rest were written for the loop-first model, which the 0.19
> line does not carry, so each has gone where it now belongs:
>
> - Moved to gwpicard/ai-loop-kit and folded into a v1 slice: #290, #296, #298, #299, #302, #303,
>   #305, #307, #311, #314, #315, #316, #317, #318.
> - Moved to gwpicard/ai-loop-kit for after its 1.0 release: #308, #309, #319.
> - Closed, because v1 replaces them or they only served moving founded projects: #289, #295,
>   #297, #300, #301, #304, #306, #310, #312, #323, #324.
>
> Each issue carries its own comment. The moved issues' links lead to a private repository until
> AI Loop Kit 1.0.

### #289 /what-now route back for an unshaped piece

> The printout this extends is part of the loop-first redesign, which is not in the 0.19 line. In
> AI Loop Kit a piece cannot reach building without passing the ready gate, because only the gate
> script changes a state; a label changed by hand is reported by the next gate run and shown on the
> shaping board, and the route back is to shaping.

### #295 Integration branch rather than one at a time?

> Answered: yes, in AI Loop Kit. A run of several pieces integrates them on one branch, one at a
> time, with full checks on the combined result and one pull request to `main`. Two decisions here
> are replaced there: the final merge is no longer always a person's once a project earns
> automatic merge, and an agent never resolves a merge conflict on the automatic path. The runs
> this describes are not in the 0.19 line. The three attempts' findings (a shared ignored output
> invalidating another part's evidence, the moving-target refusal) become cases the new run
> controller rehearses. The branches stay.

### #297 "Merge when green" said in chat

> The run's six conditions are part of the loop-first redesign, which is not in the 0.19 line. AI
> Loop Kit takes the merge out of chat: a run's merge policy comes from project settings, the
> person merges until the project has earned automatic merge, and every merge is recorded in the
> run record by the gate script.

### #300 Merge question says what was not seen; "try it" piece

> The walk-through and the "try it" opt-in are part of the loop-first redesign, which is not in
> the 0.19 line, and AI Loop Kit does not carry the opt-in. There each piece shows what it could
> not check on the loop board, and anything that needs a person's eyes forces a review by the
> person, on the piece's preview, before the merge.

### #301 Assignee owes a waiting answer; since when

> The printout this extends is part of the loop-first redesign, which is not in the 0.19 line. In
> AI Loop Kit a question for the person sits in the clarify sub-state, and the shaping board lists
> what needs the person at the top. The team half, a colleague assigned to answer, has moved with
> "Working as a team" for after 1.0. The batch attempt is not reused; its finding, that a waiting
> date must come from when the question was asked and never from the last edit, carries into the
> board.

### #304 Under a goal, /implement loads run rules first

> Runs are part of the loop-first redesign, which is not in the 0.19 line. In AI Loop Kit every
> build is a run started by the run script, and only the gate script can move a piece to
> building, so a native `/goal` cannot start builders outside a run. A goal in the kit's own sense
> is a loop module there, with a metric, a target and a budget.

### #306 Full record of who checked a change

> This is a new capability, not a fix, so the 0.19 line will not take it. AI Loop Kit replaces the
> scattered traces with records its scripts write: fresh evidence for every piece, the automatic
> reviewer's logged verdicts, and the run record the run's pull request text is written from. Who
> on a team acted under one login has moved with "Working as a team".

### #310 Simplification campaign route

> This is a new route, not a fix, so the 0.19 line will not take it. In AI Loop Kit a
> simplification campaign is a goal piece: a metric and the command that measures it, a target, a
> budget, and guard checks that stop any named behaviour being removed. Smaller findings come from
> the drift, copied-code and unused-code reads, which file chore pieces.

### #312 Page for builders another tool starts

> Builders started by another tool belong to runs, which are part of the loop-first redesign and
> not in the 0.19 line. In AI Loop Kit the steps a brief could drop are held by the gate script, a
> hook and deny rules, every crew member is started by the run script, and the brief says what a
> builder may do outside the code, so a builder another tool starts meets the same refusals.

### #323 Commands look up only relevant knowledge

> This is a new capability, not a fix, so the 0.19 line will not take it. In AI Loop Kit the
> builder needs no lookup: the contract carries everything it needs. Shaping reads the area map
> and the lessons earlier runs recorded, and the compact masterplan points to the concept
> documents. The draft on the batch branch was never reviewed and is not reused; the branch stays.

### #324 Maintenance migrates records without losing rules

> AI Loop Kit is for new projects only: projects founded with AI Build Kit stay on it and are not
> moved, so there are no existing records to migrate. The compact format this would migrate to is
> not in the 0.19 line either. Its rule, that a move never loses a rule and never reports an
> interrupted move as finished, is the one any later move would have to keep.

---

## Comments for the issues kept in gwpicard/ai-build-kit

No label changes. Each comment is posted as it stands.

### #151 Hosting request cannot mark build-time values (KEEP + slice 14)

> Kept for the AI Build Kit 0.19 line: a Coolify launch built from the request alone still builds
> an app that points nowhere. It still waits on the hosting companion's maintainer; once the
> wording is agreed, it ships as a 0.19 fix. AI Loop Kit (gwpicard/ai-loop-kit, private until 1.0)
> keeps the hosting request in `/deploy`, so its slice 14: /deploy replacing /ship carries the same
> two marks.

### #173 Founding shows the recipe menu only after stand-up (KEEP + slice 14)

> Kept for the AI Build Kit 0.19 line: every founding with a recipe still meets it. It is a
> wording change to step 11 and a rule in `founding-menu.sh`, which a 0.19 fix can carry. AI Loop
> Kit still has founding choose the recipe, from the same step 11, so its slice 14: /deploy
> replacing /ship, which already touches the founding menu, carries the same fix.

### #176 One recipe still named only in the completion report (KEEP + slice 14)

> Kept for the AI Build Kit 0.19 line, with #173: one rule in step 11 covers both menu sizes. AI
> Loop Kit's slice 14 carries the same fix.

### #187 Recipe line written as a bullet (KEEP + slice 14)

> Kept for the AI Build Kit 0.19 line: a mechanical read of `Recipe:` still misses a bullet, and
> `/ship` and the monthly recipe offer read that line. The open question is which form every
> reader accepts. AI Loop Kit's `/deploy` reads the same line, so its slice 14 carries the answer
> chosen here.

### #210 /ship trial-merges on local main (KEEP)

> Kept for the AI Build Kit 0.19 line: `/ship` there can still leave this computer's `main`
> holding a merge GitHub never made. The fix is a sentence in the ship skill saying a trial of two
> changes together happens on a throwaway branch, and a rule check for it. AI Loop Kit needs no
> matching change: there two changes meet only on a run's integration branch, and `/deploy` does
> not merge.

### #211 Free-plan note said more than once (KEEP + slices 14 and 20)

> Kept for the AI Build Kit 0.19 line, which carries the free-plan note from v0.19.3. AI Loop
> Kit's slice 14 carries the "say it once" fix in its founding menu, and its slice 20 writes the
> personal-project scenario that shows no note, since scenarios 50 and 51 are rewritten there.

### #212 Recipe checker and UTC dates (KEEP + slice 14)

> Kept for the AI Build Kit 0.19 line: a date written after local midnight east of UTC still
> fails the hosted check. AI Loop Kit has the same `check-recipes.sh`, so its slice 14, which
> writes new dated lines into both recipes, carries the same fix. It is small enough to fix in
> both repositories at once.

### #214 Small follow-ups from 28 and 29 September reviews (KEEP + slice 14)

> Kept for the AI Build Kit 0.19 line, which carries both the `Plan terms:` line and the pointer
> script from v0.19.3. In AI Loop Kit the `Plan terms:` gaps and the Supabase free-plan reading go
> to slice 14: /deploy replacing /ship, which owns the recipe format there. The pointer script
> part stays here only: AI Loop Kit is for new projects and may drop the old-project upkeep it
> belongs to.

### #313 Codex cannot reach GitHub through gh (KEEP + slices 19 and 16)

> Fixed on `main` by the change that recovers Codex GitHub access without an editor dependency.
> It reaches people in v0.19.3, whose pull request ports that fix and closes this issue. AI Loop
> Kit starts from a snapshot that already holds the fix; its slice 19: Codex parity keeps it
> working, and the status-file script in slice 16: Boards and notifications, which replaces the
> plan helper, follows the same rule: print the real `gh` error and the next step.

---

## Comments for the pull requests

### #346 Agentic loop design note

> Closing without merging. The two design notes are in the first commit of AI Loop Kit,
> gwpicard/ai-loop-kit (`<first commit>`), which is private until its 1.0 release; v1 is built
> there. AI Build Kit stays on the 0.19 line. The branch stays.

### #341 v1 overnight batch

> Closing without merging (decisions 24 and 56). v1 is built as AI Loop Kit in
> gwpicard/ai-loop-kit, and this batch is reused there one mechanism at a time, read from this
> branch: the clarify question box and "Answers already on the piece" by slice 4; the recovery
> helper, the task hand-off and task-context references and their rehearsals by slice 7; the
> fresh-session route by slice 8; same-turn continuation and the recovery baseline by slice 9;
> the local-browser rule and resource rules by slice 10; the force-push deny rules by slice 15.
> Not carried over: the parked state, the "try it" opt-in, shaping inside a run, the route back
> for an unshaped piece, the goal trigger, the half-wired rule detector and the selective context
> lookup. The branch stays.

### #330, #333, #335, #336, #342

> Closing without merging. This draft targeted the overnight batch branch, which is not being
> merged. Its findings are kept as cases for AI Loop Kit's <slice> to rehearse, and the branch
> stays for reading. The code is not reused.

`<slice>` per pull request: #330 slice 7: Build and fix loop modules (an interrupted write of
the attempt history); #333, #335 and #342 slice 9: Run controller (a shared ignored output
invalidating evidence, the moving-target refusal, different report file names); #336 slice 16:
Boards and notifications (a waiting date taken from when the question was asked, never from the
last edit).

### #344

> Closing without merging. It targeted the overnight batch branch and was never reviewed. Its
> issue is closed as not planned, since in AI Loop Kit the contract carries what a builder needs.
> The branch stays.

---

## Slice text changes this list implies

Not made here; for whoever revises the slice files.

- **Slice 14** gains Done when lines for the KEEP + slice 14 bugs, each naming the old issue by
  title: the menu in its own reply before stand-up, for any number of recipes; one form for the
  `Recipe:` line that every reader accepts; the free-plan note said once; the future-date rule
  in `check-recipes.sh` giving the same answer in UTC; the `Plan terms:` gaps (misspelt label,
  second line, position) and the Supabase free-plan reading; the build-time mark and the `Build:`
  tool in the hosting request, still waiting on the companion's maintainer.
- **Slice 20** gains the personal-project scenario with no free-plan note, and the rule that a
  fixture gives the same test count on every supported Node or the harness refuses to start.
- **Slice 5** gains the test-job line from "Apply the maintainer's decisions on four round 2
  choices", with a case for each runner in `adopted-ci-rehearsal.sh`.
- **Slices 2, 6 and 15** disagree about the force-push deny rules: slice 2 sends them to slice 15,
  slice 15 does not mention them, and slice 6 offers to bring them "if slice 2 has not". This list
  puts them in slice 15; slice 15 needs the line and slice 6's sentence should go.
- **Slices 7 and 10** both say they bring `task-handoff.md` and `task-context-capabilities.md`
  over. This list reads it as slice 7 bringing the files and slice 10 adding the resource rules.
- **Every slice that reads the batch branch** (4, 7, 8, 9, 10, 15, 18) says `git show
  origin/<branch>:<path>`. In a clone of gwpicard/ai-loop-kit, `origin` has no such branch. Each
  needs the old repository added as a second remote first (for example `git remote add build-kit
  https://github.com/gwpicard/ai-build-kit` and `git fetch build-kit`), then `git show
  build-kit/<branch>:<path>`.
- **Decision 63** is not yet in the slices: slice 17's Part b moves founded projects onto v1
  labels and records; slice 18 says moving existing projects to the compact format is slice 17's;
  slice 22's title still says every installed project moves to the new name; slice 23's title
  says a project on an earlier release reaches 1.0 through one `/maintain` visit; and the epic
  says founded projects are carried across. Each should drop the move.

---

## Counts

| Action | Issues |
|---|---|
| TRANSFER, fold into a slice | 23: #12, #98, #242, #287, #288, #290, #291, #292, #293, #296, #298, #299, #302, #303, #305, #307, #311, #314, #315, #316, #317, #318, #321 |
| TRANSFER, after 1.0 | 13: #5, #6, #7, #8, #9, #10, #58, #150, #196, #308, #309, #319, #322 |
| CLOSE as not planned | 18: #21, #55, #203, #213, #241, #244, #255, #289, #295, #297, #300, #301, #304, #306, #310, #312, #323, #324 |
| KEEP (0.19) | 1: #210 |
| KEEP (0.19) + a v1 slice | 8: #151, #173, #176, #187, #211, #212, #214, #313 |
| Total | 63 |

Pull requests: all 8 close (#346 with the pointer to the new first commit), and no branch is
deleted.
