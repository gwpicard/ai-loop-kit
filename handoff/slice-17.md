# Slice 17: One health visit keeps the records true, learns from each run and measures the kit, and carries none of the old kit's upkeep

Labels (today's set): enhancement, area:skills, ready-able once shaped. Release label for the PR: release-major, since a command goes.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 2: Label model and gate script; slice 3: Contract v2 and the ready-gate lint; slice 4: Shaping sub-states in /shape; slice 6: Frozen-bar enforcement; slice 8: Automatic reviewer; slice 9: Run controller; slice 13: Merge policy; slice 14: /deploy replacing /ship; slice 15: Safety boundary for runs.

## So that
A person types one command, `/maintain`, to put the records right after work done outside the loop, to have what the runs learned kept where the next run reads it, and to see how well the kit is working on their project, and the visit spends none of its time on migrations for projects AI Loop Kit never founded.

## Done when

### Part a: reconciling moves into /maintain, and /sync goes

#### Works
- `maintain/SKILL.md` has a section "Putting the records right", run when the person asks to reconcile, after an interrupted session, or before a handover. It carries every step of today's `sync/SKILL.md`: the red `main` first, uncommitted work reported and left alone, stale pieces asked about once, the two label repairs (on the v1 labels, through `gate.py report`), the masterplan change and coverage reads, the document read, unfinished runs offered for resume, worktrees tidied, the project check kept honest, the save route and the fold. Check: `.agents/tests/sync-saves-like-a-piece.sh`, renamed `reconcile-saves-like-a-piece.sh`, reads every rule from the new section and proves each load-bearing.
- The `sync` skill folder is gone. `fold-changes.py` moves to `section-builder/scripts/`, beside `bring-up-to-date.sh`, which calls it from there; `document-claims.py` and `document-read.md` move to `maintain/`. Check: `validate-kit.sh` (inventory without `sync`, every skill path named in another file resolves); `.agents/tests/fold-at-merge-rehearsal.sh` and `.agents/tests/changelog-files.sh` pass with the moved script; `.agents/tests/document-read-rehearsal.sh` runs the moved `document-claims.py`.
- The opt-in session-end hook is renamed `session-end-reconcile.sh` and points at `/maintain`. Check: `validate-kit.sh` (no tracked file names `/sync` as a command, outside `docs/design/`).

#### When it is not the normal case
- The person types `/sync` from habit: there is no such command; the agent treats the request by its job, says in one line that putting the records right is part of `/maintain`, and runs that section, since the kit starts a command when the person asks for its job in plain words. Check: `.agents/tests/reconcile-saves-like-a-piece.sh` holds the sentence in `maintain/SKILL.md`.

### Part b: the old kit's migrations and upkeep go

#### Works
- `maintain/SKILL.md` carries none of the sections that moved a project founded on an earlier release of AI Build Kit: "Adding the plan printout helper" for a project founded before it shipped, "Adding the rules that stop a push to `main`", "Adding the confirmation box on merges that go live", "Moving the pieces onto the states", "Moving the instructions onto the index", "Recording the project's own check" for an older project, "Migrating a project founded before /shape and /implement", "Moving a plan.md into issues", "Pointing the records at a skill by name", "Migrating a project founded before the setup-ai-build-kit rename", "Migrating a project founded before the shape rename", "Migrating a masterplan written with four build paths", "Bringing the project's instructions up to the current names" and "Tidying a project founded from a whole copy of the kit". Check: new `.agents/tests/no-old-upkeep.sh` (rule-shape) fails on a copy of `maintain/SKILL.md` with any one of those headings put back, and on a copy that names a retired skill (`build`, `start`, `plan`, `fix`, `queue`, `sync`, `ship`) as something to tidy.
- `maintain/scripts/old-skill-pointers.py` is removed with `git rm`, and no skill names it. The shared route keeps `npx skills add` and the count of the lockfile against the current inventory, and loses its rename branches. Check: `validate-kit.sh` (every named script resolves); `.agents/tests/shared-route-adds.sh`, cut to the add route and the count, fails on a copy carrying a rename branch.
- "Offering a move onto a recipe" keeps the offer for a person who chose their own stack and the offer of a recipe the `founding-menu` line does not list, and loses the branches for a project with no `Recipe:` line or no `founding-menu` line, which only an older founding left. Check: `.agents/tests/offer-recipe-move.sh`, its no-line branches removed and a rule added that the skill names neither.
- What stays in `/maintain` is the work a project founded with AI Loop Kit needs: the update through its own route, refreshing the copied scripts (`plan-refresh.sh`, `gate.py`, `area-map.py`, `state-guard.sh`) from the installed skill after an update, removing leftover worktrees, linking a new ignored build file into run worktrees on a yes, the recipe offer above, the quarterly reads, the stale-branch list and the retirement step. Check: `no-old-upkeep.sh` holds each kept heading as a rule, proved load-bearing.
- The rehearsals that guarded only old-project upkeep are retired: `older-project-upkeep.sh` and `whole-copy-leftovers.sh`. The ones that guarded upkeep beside a lasting rule keep the lasting rule and lose the one-time offer: `push-to-main-rules.sh` and `merge-ask-rule.sh` (the offer to an older project), `adopted-ci.sh` (the offer to an older project when its workflow files change), `plan-helper-routes.sh` (adding the helper to a project founded before it shipped; the refresh after an update stays), `refused-commands.sh` (the removal of retired skill folders and whole-copy adapters). Check: `.agents/tests/run-all.sh` passes with the retired files gone, and `validate-kit.sh` ("AGENTS.md names every maintainer check") passes with their entries removed.
- WORKFLOW.md section 12 drops the paragraphs on moving an older project, on whole-copy tidying and on renamed commands; root `AGENTS.md` drops the maintainer-checks entries for the two retired rehearsals and the old-project sentences in the entries it keeps; `docs/MAINTAINING.md`'s rule that a removed command needs a migration path becomes a rule that a removed command needs a release-note line, since AI Loop Kit carries no migration. Check: `no-old-upkeep.sh` reads WORKFLOW.md and MAINTAINING.md; `validate-kit.sh` for AGENTS.md.

#### When it is not the normal case
- A project founded with AI Build Kit runs AI Loop Kit's `/maintain`: the visit changes nothing in it and says in one line that the project stays on AI Build Kit, which keeps its own fixes. Check: `no-old-upkeep.sh` holds the sentence; slice 22: Set AI Loop Kit's names gives the record file that tells the two kits apart.
- A person asks for one of the removed moves by name: the visit says AI Loop Kit does not move projects from AI Build Kit and changes nothing. Check: `no-old-upkeep.sh`.

### Part c: lessons, kit metrics and the reviewer's calibration

#### Works
- Each piece gains a `## Learned` section, a field this slice owns: the builder's result carries `Learned:` lines, limited to what the code and tests do not show, and the gate writes them into the issue at the move to `state:in-review`. `pieces.md` states the field's rule, and the ready-gate lint from slice 3 never requires the section and never counts it in the length limit. Check: `.agents/tests/piece-contract.sh` holds the field's rule in `pieces.md`; slice 3's `ready-lint-rehearsal.sh` gains a fixture that passes the length limit only when `## Learned` is left out; `.agents/tests/lessons.sh` drives the gate with a stand-in builder result and reads the issue.
- When a run closes, each piece's `Learned:` lines are sorted by `maintain/scripts/lessons.py promote` into one of four homes: a check (filed as a `type:chore` raw piece that names the check to write), a line in the founded `AGENTS.md`'s `## Lessons` section, a masterplan change, or a raw piece. The result lands through the run's pull request. Check: new `.agents/tests/lessons.sh` runs the script on a stored run with four lessons, one of each kind, and reads the run branch's diff.
- `## Lessons` holds at most 12 lines with no dates or issue numbers, and `/maintain` offers to keep, update, merge or delete each line older than three months, read from the maintenance record's `lesson|<first words>|<YYYY-MM-DD>` lines. Check: `.agents/tests/agent-first-records.sh` (the 12-line rule covers the new section); `.agents/tests/lessons.sh`.
- `/maintain` reports three kit measures from the `run-summary` blocks slice 9 writes on merged run pull requests: kickbacks by shaping sub-state, merges reverted or followed within 7 days by a `type:bug` piece whose `Caused by:` line names one of the run's pieces, and how often the automatic reviewer agreed with the person where both judged. Check: new `maintain/scripts/kit-metrics.py`, run by `.agents/tests/lessons.sh` against `fake-github.sh` holding five stored run pull requests with known answers.
- Where the reviewer and the person disagreed on a piece, `/maintain` shows each disagreement in one line and proposes a change to the project's reviewer instructions, applied only on a yes. The two verdicts are read from the issue alone, from slice 8's `<!-- loop:review round=<n> -->` and `<!-- loop:person-verdict -->` comments, so the comparison works on any computer. Check: `.agents/tests/lessons.sh` (rule-shape on the section, and the script's list of disagreements from stand-in issues carrying both comments).

#### When it is not the normal case
- No run has closed since the last visit: the metrics say "no runs since <date>" and nothing else. Check: `.agents/tests/lessons.sh`.
- A `run-summary` block is missing or does not parse: that run is named as not counted, never guessed. Check: `.agents/tests/lessons.sh`.

### Part d: drift reads after a number of runs, the offer of automatic merge, and the gate list

#### Works
- The copied-code, unused-code, structure and document-bloat reads run after every 5 merged runs, counted from the `run-summary` blocks since the `last-drift-read` line, instead of only quarterly. Each finding becomes a `type:chore` piece in `shaping:raw` with the read that found it, at most three per read. Check: `.agents/tests/waste-read.sh`, `.agents/tests/structure-read.sh` and `.agents/tests/document-bloat.sh` hold the new trigger; `.agents/tests/lessons.sh` drives the count across the boundary at 4 and 5 merged runs.
- After 5 clean runs, with the last drift and structure reads no worse than the ones before, and with GitHub protecting `main` as slice 13 checks, `/maintain` offers once to switch the project to automatic merge. A yes writes `"merge": "automatic"` in `.agents/loop-settings.json`, slice 13's setting; a no is recorded as `auto-merge-declined|<YYYY-MM-DD>|<clean runs>` and the offer returns after 5 more clean runs. Check: `.agents/tests/lessons.sh` with stored `run-summary` blocks for 4 and 5 clean runs, a worse structure read, an unprotected `main`, and a recorded no.
- Every gate `gate.py` runs is listed in `section-builder/references/gates.md` with its kind (guide or sensor) and what it catches. The gate script switches a guide off when `KIT_GUIDE_OFF` names it and refuses to switch off a sensor. Check: `validate-kit.sh` (every gate the script names is in the list, and every row has a kind and a "catches"); new `.agents/tests/gate-list.sh` runs the gate script with a guide and with a sensor named.

#### When it is not the normal case
- A clean-run count cannot be read because GitHub is unreachable: no offer is made, and the visit says the count could not be read. Check: `.agents/tests/lessons.sh`.

### The documents this change touches
- `maintain/SKILL.md`: the new sections, the removed ones, and the quarterly list without `Run sync`. Check: `.agents/tests/reconcile-saves-like-a-piece.sh`, `.agents/tests/lessons.sh`, `.agents/tests/no-old-upkeep.sh` (rule-shape).
- `WORKFLOW.md` section 12, retitled "Maintenance", tells reconciling, lessons, the measures, the reads after runs and the offer, and no longer tells any old-project move. Check: rule-shape rules in `.agents/tests/lessons.sh`, `.agents/tests/reconcile-saves-like-a-piece.sh` and `.agents/tests/no-old-upkeep.sh`.
- `README.md`: the "I'm done for today" row goes, and the `/maintain` row names putting the records right. Check: `validate-kit.sh` (no `/sync` command outside `docs/design/`).
- `docs/COMPATIBILITY.md`: the "Sync" row of the fallback table becomes "Putting the records right: run `/maintain`". Check: `validate-kit.sh`.
- The foundation `AGENTS.md` command list and `## Lessons` section. Check: `.agents/tests/standing-instructions.sh`, `.agents/tests/agent-first-records.sh`.
- `docs/MAINTAINING.md`: the session-end hook paragraph, the command count and the release-note rule for a removed command. Check: `validate-kit.sh` (stale claims list gains "nine commands"); `no-old-upkeep.sh`.
- `.claude-plugin/plugin.json`, `release-manifest.txt` and the generated adapters lose `sync`. Check: `.agents/tests/claude-plugin.sh`, `.agents/tests/agent-plugin.sh`, `.agents/tests/release-builder.sh`.
- `docs/SOURCES.md` credits compound engineering's one lesson per task. Check: `validate-kit.sh`.

## Masterplan change
Design note: "Learning and code health", "Projects founded with AI Build Kit" (the kit carries none of the old migrations and upkeep), the `/maintain` row of "Commands", the guides and sensors in "What a machine enforces", and the clean-run definition in "Merging and going live". The note needs two changes: a clean run is counted from the `run-summary` block on the run's pull request, and a bug is tied to a run by its `Caused by:` line.

## Not in this piece
- Writing the `run-summary` block at run close: slice 9: Run controller. This slice only reads it.
- Running the replay harness with each guide switched off: slice 20: Replay harness rewrite and real runs.
- Logging the reviewer's rulings: slice 8: Automatic reviewer.
- The automatic merge itself and the GitHub protection check: slice 13: Merge policy.
- Any move of a project founded with AI Build Kit onto AI Loop Kit's labels, records, settings or names: none, by decision 63. Those projects stay on AI Build Kit's 0.19 line.

## Decided
- `/sync` goes and its steps live in `/maintain` as one section the person can ask for alone. Reason: decision 21 and the design note's "Commands".
- AI Loop Kit carries none of the migrations and upkeep the old kit kept for its older projects, and has no v1 move. Reason: decision 63 and the design note's "Projects founded with AI Build Kit".
- Refreshing the copied scripts after an update stays, because it keeps a project founded with AI Loop Kit on the current kit; it moves nothing from an earlier model.
- Lessons go first to a check, and a line in `AGENTS.md` only where no machine can hold one. Reason: decisions 34 and 46, and the measured cost of model-written instruction files.
- Clean runs and merged runs are counted from the `run-summary` block on each run's pull request, not from local run folders. Reason: run folders are ignored by git and live on one computer, while a project is shared.
- 5 clean runs before the offer, 5 merged runs between drift reads, 7 days for a revert or bug to count, three months for a lesson's review: defaults to test. Reason: the design note's "Settled when built".
- Drift findings are filed as chore pieces without a question. Reason: decision 35; a raw piece is the backlog and asks nothing of the person until it is shaped.

## Data
- `.ai-build-kit-maintenance` gains `lesson`, `last-drift-read` and `auto-merge-declined` lines. Only `/maintain` writes them. Slice 22 renames the file `.ai-loop-kit-maintenance`.
- The founded `AGENTS.md` gains `## Lessons`, written at run close and by `/maintain`.
- Issues gain a `## Learned` section, written by the gate.
- No project founded with AI Build Kit is changed (decision 63).

## Leaves the tool
Chore pieces and lesson pull requests go to the project's own GitHub repository, as `/sync` and `/maintain` send today. The metrics are read from GitHub and never sent anywhere.

## Must still hold
- Uncommitted work is never swept or discarded by reconciling: `.agents/tests/reconcile-saves-like-a-piece.sh`.
- A piece closed as not planned stays closed unless a person reopens it: `.agents/tests/gate-script.sh` from slice 2.
- The fold writes each entry once and conflicts with nothing: `.agents/tests/fold-at-merge-rehearsal.sh`, `.agents/tests/changelog-files.sh`.
- The document read flags only stale names: `.agents/tests/document-read-rehearsal.sh`.
- The coverage read keeps permissions, data and connections: `.agents/tests/coverage-read.sh`.
- The update route is `npx skills add`, never `npx skills update`: `.agents/tests/shared-route-adds.sh`.
- Stale branches are listed, never removed: `.agents/tests/stale-branches.sh`.
- The version is read from `releases/latest` only: `.agents/tests/stable-is-the-channel.sh`.
- The push-to-main and merge confirmation rules a founded project receives still hold: `.agents/tests/push-to-main-rules.sh`, `.agents/tests/merge-ask-rule.sh`.
- No issue numbers in tracked files, and the founded `AGENTS.md` keeps no dates or numbers: `validate-kit.sh`, `.agents/tests/agent-first-records.sh`.

## Relies on
- The labels and the gate script that changes them: slice 2.
- The contract v2 lint, which this slice tells to leave `## Learned` out: slice 3.
- The shaping sub-states and the bug route: slice 4.
- The frozen-bar gates, which the gate list sorts into guides and sensors: slice 6.
- Logged rulings and calibration comments on each issue: slice 8.
- Run records (`.agents/runs/<run name>/run.json`), the per-piece folder, the run's pull request and its `run-summary` block: slice 9.
- The `merge` setting and the protection check: slice 13.
- `/deploy`'s name in the command list: slice 14.
- The safety gates (`gate.py push`, the dependency check and the secret scan), which the gate list also sorts: slice 15.
- On main today: `sync/SKILL.md` and its scripts and reference, `maintain/SKILL.md` and its references and scripts, `bring-up-to-date.sh`, `.agents/hooks/session-end-sync.sh`, `.agents/tests/fake-github.sh`.

## Reach and risk
Boundary: maintain, sync (removed), section-builder's scripts folder, setup-ai-build-kit's foundation templates, the plugin and release lists, WORKFLOW.md, README.md, COMPATIBILITY.md, MAINTAINING.md, SOURCES.md, the rehearsals of old-project upkeep.
Reaches: the merge step's fold (`fold-at-merge.sh`, `recheck-before-merge.sh`, `one-merge-step.sh`); founding (`starter-rehearsal.sh`, `plan-helper-routes.sh`); every check that names `/sync` (`first-upload-asks.sh`, `kit-owns-worktrees.sh`, `run-controller.sh` from slice 9, `record-habits.sh`, `masterplan-changes.sh`, `masterplan-edges.sh`, `adopted-ci.sh`, `worktree-links.sh`, `refused-commands.sh`, `mutate.sh`); the replay scenarios that type `/sync` (`.agents/tests/scenarios.md`, `.agents/tests/replay/cases/48.txt`).
If it breaks: the fold fails at a merge and the merge step stops with its message, or a step a project still needs went with the old upkeep and the person misses it at their next visit. Undone by reverting the part's pull request.
Depends on: 2, 3, 4, 6, 8, 9, 13, 14, 15.
Loop module: build, because each rule is a script result or a written rule a rehearsal reads back.
Crew: default.

## Under the hood
Move `sync/SKILL.md`'s routine into `maintain/SKILL.md` almost word for word, changing the label repairs to `gate.py report` and the `/fix` pointers to `/shape`. Move scripts with `git mv` and update `bring-up-to-date.sh`'s `FOLD` path, `section-builder/SKILL.md`, the `/deploy` skill and every test that runs them. Remove the old-upkeep sections and `old-skill-pointers.py` with `git rm`, keeping the steps listed under Part b. Add `maintain/scripts/lessons.py` and `kit-metrics.py`, run from the installed skill and never copied into a project. New rehearsals `no-old-upkeep.sh`, `lessons.sh`, `gate-list.sh` and the renamed `reconcile-saves-like-a-piece.sh`, sourcing `lib/rule-shape.sh`. Retired rehearsals: `older-project-upkeep.sh`, `whole-copy-leftovers.sh`. Existing rehearsals expected to change: every one in "Reaches" that names `/sync`, plus `document-read.sh`, `coverage-read.sh`, `waste-read.sh`, `structure-read.sh`, `document-bloat.sh`, `shared-route-adds.sh`, `offer-recipe-move.sh`, `push-to-main-rules.sh`, `merge-ask-rule.sh`, `adopted-ci.sh`, `plan-helper-routes.sh`, `refused-commands.sh`, `piece-contract.sh`, `ready-lint-rehearsal.sh`, `claude-plugin.sh`, `agent-plugin.sh`, `release-builder.sh`; `.agents/tests/mutate.sh` loses any mutation aimed at a removed section. The inventory count in `validate-kit.sh` follows whatever slices 4, 9 and 14 left. Nothing is reused from the overnight batch branch. Kit rules: the five questions for `maintain`; a release-note line for the removed command (`docs/MAINTAINING.md`, "When a release is cut"); adapters rebuilt; validator; humanizer; no issue numbers.

## Evidence
Scripts run against `fake-github.sh` and stored run pull requests with known answers; rule-shape checks on the skill, WORKFLOW.md and MAINTAINING.md, including the absence of every removed heading; the full suite passing with the retired rehearsals gone; one guided check: run `/maintain` on a throwaway project founded from this kit and read that the visit offers no old-project move.

## Size
Four parts, each one sitting: Part a, Part b, Part c, Part d. Part a goes first; the others need it but not each other.

## Consistency notes
- Decision 63 replaces the draft's Part b, which moved founded projects onto the v1 labels, records and settings, with the removal of every old-project migration and upkeep step the old kit carried. Slices 2, 4 and 14 removed or renamed only what their own changes touched; this slice removes the rest and the rehearsals that held them.
- "Old helper refresh" is read as adding the helper to a project founded before it shipped, which goes. Refreshing the copied scripts after an update stays, because a project founded with AI Loop Kit needs the current `gate.py`. The maintainer can overrule this in the open decisions.
- `## Learned` has one owner, this slice: the field rule in `pieces.md`, the gate writing it, and the lint leaving it out of the ready gate and the length limit. Slice 3 names it as this slice's, and slice 6's contract hash already leaves it out.
- Clean-run and merged-run counts read the `run-summary` block slice 9 writes on each run's pull request, and nothing else.
- Names used here: the gate script `gate.py`, the run record `run.json`, the merge setting `"merge"` in `.agents/loop-settings.json`, and the review markers `loop:review` and `loop:person-verdict`.
- Slice 15 is added to Depends on, because the gate list sorts the safety gates that slice adds.
