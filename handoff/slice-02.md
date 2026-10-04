# Slice 2: Every piece shows one state and one sub-state, and only the gate script can move it

Labels (today's set): enhancement, area:skills, ready-able once shaped. Release label for the PR: release-minor.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 1: Principle, audience and the loop kit.

## So that
A person opening a project's issues sees each piece in exactly one state and, where the state has them, one sub-state, and can trust that what the board shows is what happened, because no agent can change a state except through a script that checks the condition first.

## Done when

This slice is built in four parts, each its own pull request in order. Part a builds the gate script on its own; part b stops the agent going round it; part c makes founding, the records and the printout use the new labels; part d moves every command onto the gate.

### Part a: the gate script and the label set

#### Works
- A founded project receives `.agents/tools/gate.py`, copied from `.agents/skills/setup-ai-build-kit/templates/foundation/gate.py` by `scripts/bootstrap-project.sh` and by `scripts/place-plan-helper.sh`, which places it beside `plan-refresh.sh` on every `/maintain` visit. Check: `.agents/tests/plan-helper-routes.sh`, extended so all six installation layouts end with a runnable `.agents/tools/gate.py` identical to the template, and a second placement changes nothing.
- A founded project's own type check and linter stay green with `.agents/tools/gate.py` in place. Check: `.agents/tests/check-floor-rehearsal.sh`, extended so the founded Python project and the founded TypeScript project each carry the placed `gate.py` and their `Project check` stays green.
- `gate.py labels` creates the v1 label set, and running it twice creates nothing the second time: `state:shaping`, `state:ready`, `state:building`, `state:in-review`; `shaping:raw`, `shaping:research`, `shaping:clarify`, `shaping:prototype`, `shaping:spec`, `shaping:check`; `review:auto`, `review:person`; `type:feature`, `type:bug`, `type:chore`; `loop:fix`, `loop:build`, `loop:goal`, `loop:gauntlet`; and the seven subject labels kept from today. Each family has one colour. Check: new `.agents/tests/gate-script.sh`, run against the replay harness's stand-in GitHub (`.agents/tests/replay/fake-github/gh`), reads back all 26 labels after one run and the same 26 after a second.
- `gate.py capture --title <t> --body-file <f>` opens an issue carrying `state:shaping` and `shaping:raw`, with the person's words as the body. Check: `gate-script.sh`.
- `gate.py move <number> <target>` makes each transition in the design note's transition table, writes the new labels and removes the old ones in one call, and refuses when the condition fails. The conditions it checks are these:
  - `shaping:raw` to another sub-state: exactly one `type:` label, and, for `research`, `clarify` or `prototype`, a `## Open question` section holding one question.
  - one shaping sub-state to another: the section that records the answer (`## Decided` for clarify and prototype, `## Research` with a source for each claim for research) has changed since the piece entered the sub-state, read from the marker described under Data.
  - `shaping:check` to `state:ready`: a `## Readiness` section saying Ready with no BLOCKING line. Slice 3: contract v2 and the ready-gate lint adds the lint and the `loop:` label to this condition.
  - `state:ready` to `state:building`: an assignee or a `--run <name>`, every blocked-by piece closed or listed earlier in that run's state file, and no `state:building` already on it.
  - `state:building` to `state:in-review`: an open pull request whose body carries `Closes #<the piece>`; the piece gains `review:person`.
  - `state:building` or `state:in-review` to `state:shaping`: a `## Kickback` section on the piece, and a target sub-state of `clarify`, `research` or `spec`.
  - `state:in-review` to `state:building`: a `--reason` naming the defect, posted as one bookkeeping comment.
  - `state:ready` to `state:shaping`: the piece is not claimed.
  - `state:building` or `state:in-review` to `state:ready`: a `--run <name>` whose state file marks the piece withdrawn (a piece it needs was kicked back) or the run abandoned; the branch is kept and the piece leaves the run. Slice 9: run controller is the only caller.
  Check: `gate-script.sh` drives every row once where the condition holds and once where it fails, and reads the labels back after each.
- `gate.py drop <number> --reason <text>` closes the piece as not planned, writes the reason as a comment and takes its state labels off; `gate.py tidy` takes state, sub-state and review labels off every closed issue. Check: `gate-script.sh`.
- `gate.py report` prints one line when every open piece has exactly one state and, where needed, exactly one sub-label, and otherwise names each piece with no state, two states, a sub-label beside the wrong state, or a label from AI Build Kit's model (`idea`, `shaping`, `ready`, `building`, `to check`, `parked`, `blocked`, `broken`, `needs-clarification`, `needs-prototype`, `needs-research`), which it names as a label the kit does not use and leaves alone. A label a person changed on GitHub is reported, never reverted. Check: `gate-script.sh`, with a fixture issue for each finding.
- Every pass prints one line. Every refusal prints what failed and the next allowed action as a command line, such as "Write the answer under ## Decided, then run: gate.py move 12 spec". Check: `gate-script.sh` asserts the line count on pass and the "next:" line on each refusal.
- When a `--run <name>` is given, the gate writes the piece's run status (`queued`, `building`, `checking`, `integrated`, `kicked back`, `withdrawn`) into `.agents/runs/<name>/state.json` in the same call as the labels, and a label write that fails leaves the state file as it was. Check: `gate-script.sh`, including a stand-in GitHub that refuses the label write.
#### When it is not the normal case
- GitHub cannot be reached: the gate changes nothing, says so in one line and exits non-zero. Check: `gate-script.sh` with the stand-in returning a network error.
- The account cannot create a label (a collaborator without write access): `gate.py labels` names each missing label, creates the rest and exits zero, as founding does today. Check: `gate-script.sh`.
- Two sessions move the same piece at once: the second reads the labels again just before writing and refuses when the piece is no longer in the state it expected. Check: `gate-script.sh`, with the state changed between read and write.
- A piece carries two state labels because a person added one by hand: `move` refuses and names the two; `report` lists it. Check: `gate-script.sh`.
- A project has no `python3`: does not arise, because the plan printout already needs it and `required-tools.md` makes founding check for it. Check: `.agents/tests/check-tooling.sh` passes unchanged.

### Part b: the hook and the deny rules

#### Works
- The project settings template `templates/foundation/claude-settings.json` gains a `PreToolUse` hook that runs `.agents/hooks/state-guard.sh`, copied from `templates/foundation/state-guard.sh` by the bootstrap. It refuses, with a message naming the gate command to use instead, any Bash command or GitHub tool call that adds, removes, creates, edits or deletes a label beginning `state:`, `shaping:` or `review:`, in any of these spellings: `gh issue edit` with `--add-label` or `--remove-label` (separate, comma-joined or quoted), `gh issue create --label`, `gh label edit`, `gh label delete`, `gh api` on an issue's `labels` path, and a GitHub MCP tool call whose labels include one. A command that runs `gate.py` itself passes. Check: new `.agents/tests/state-guard.sh` feeds the hook each refused spelling and each allowed one, as Claude Code's hook input JSON, and checks the exit code and message.
- The same template's deny list gains the matching prefix rules, such as `Bash(gh issue edit * --add-label state:*)`, `Bash(gh issue edit * --remove-label state:*)` and the same for `shaping:` and `review:`, `Bash(gh issue create * --label state:*)`, `Bash(gh label delete state:*)`, `Bash(gh label edit state:*)` and `Bash(gh api *issues/*/labels*)`. Check: `state-guard.sh` runs them through the shared matcher `.agents/tests/lib/permission-matcher.py` against the refused and missed spellings written in `blocked-commands.md`, and removes each rule in turn to prove it is needed.
- `.agents/skills/setup-ai-build-kit/references/blocked-commands.md` gains a section "Changing a piece's state by hand", listing the refused spellings, the spellings the rules miss (a label inside a variable, a call from another script, a person's own browser), and the rule that a refused move is never reached another way. Check: `state-guard.sh` reads both lists from that section, as `push-to-main-rules.sh` does for its own.
- `.agents/tools/validate-kit.sh` adds the new deny rules to `expected_deny_project` only, and checks that this repository's own `.claude/settings.json` carries neither the rules nor the hook, because the kit's own issues keep today's labels (decision 55). Check: `validate-kit.sh`; `state-guard.sh` plants the hook in a copy of this repository's settings and requires the validator to fail.
#### When it is not the normal case
- The hook script is missing or not runnable in a project: the hook command in the template runs it only when present, as the session-start wiring does, so a missing copy never blocks every command; `gate.py report` then names the missing hook. Check: `state-guard.sh`.
- A person changes a label on GitHub in the browser: nothing stops them, and the next `gate.py report` names what it found. Check: `gate-script.sh`, already in part a.
- The coding agent is not Claude Code: no hook runs, and the deny rules do not apply; the written rule in `blocked-commands.md` and `gate.py report` remain. Check: does not arise in this slice's checks, because slice 19: Codex parity owns the other harness.

### Part c: founding, the records and the printout use the new labels

#### Works
- `references/pieces.md` describes the v1 model in place of the six states: the four states and closed, the six shaping sub-states, the two review sub-labels, the `type:` and `loop:` dimensions, the subject labels, that only the gate script changes a state, and that held up by another piece is a blocked-by link and never a label. Its "Labels" section counts 26 labels the kit owns. Check: `.agents/tests/piece-states.sh`, rewritten to the v1 model, fails on a copy of `pieces.md` that allows two states or two sub-labels.
- `/setup-ai-build-kit` creates the labels by running `gate.py labels` before the first issue, opens each piece through `gate.py capture` and moves it with `gate.py move`, and still deletes GitHub's own nine labels and says which went. A piece founding shapes fully ends in `shaping:check` and moves to `state:ready` only through the gate. Check: `piece-states.sh` and `.agents/tests/starter-rehearsal.sh`, extended so a founding against the stand-in GitHub leaves every piece with one state and one sub-label; `validate-kit.sh`'s label clearout check passes.
- `templates/foundation/piece-issue.yml` no longer applies a subject label by default, so a form-opened issue has no state until `gate.py report` names it and `/shape` captures it. Check: `.agents/tests/piece-contract.sh`, the form assertion updated.
- `templates/foundation/plan-refresh.sh` prints the board from the v1 labels: Needs attention (the findings `gate.py report` would print), then one column per shaping sub-state, Ready, Building, and In review split into "waiting for you" (`review:person`) and "automatic" (`review:auto`). A `type:bug` piece carries a "bug" mark in whichever column it sits. `To build` and `Go together` read `state:ready` exactly as they read `ready` today. Check: `.agents/tests/plan-printout.sh`, its fixture issues relabelled and its expected groups rewritten.
- WORKFLOW.md section 2's paragraphs on states and `needs-` labels describe the v1 states and sub-states, the gate script, and what the person does to pull a ready piece back. Check: `piece-states.sh` holds the one place WORKFLOW.md explains the states.
- docs/MAINTAINING.md's sentence saying `ready` is "the same word the kit uses for the same state in a project it founds" says instead that a founded project uses `state:ready` and the kit's own issues keep `ready` until the release. Check: guided check: the maintainer reads the "How the issues are organised" section and finds no claim that the two words match.
#### When it is not the normal case
- An issue opened by hand with no labels: the printout lists it under Needs attention as "no state", and `/shape` typed alone picks it up. Check: `plan-printout.sh`.
- An issue carrying a label from AI Build Kit's model: the printout lists it under Needs attention as a label the kit does not use, and moves nothing, because AI Loop Kit carries no move from AI Build Kit (decision 63). Check: `plan-printout.sh`, with one such fixture.

### Part d: every command moves a piece through the gate

#### Works
- No skill, reference or template writes a `state:`, `shaping:` or `review:` label with `gh` directly. Every move goes through `gate.py`: capture in change-triage, every move in `/shape`, the claim in section-builder step 1 and in `/implement`'s run, the move to review when a pull request opens, a run's kickbacks in `references/running-longer.md`, `/fix`'s claim, and `/sync`'s repair, which becomes `gate.py report` followed by the person's choice. Check: `.agents/tests/state-moves.sh`, rewritten to find every `gh issue edit`, `gh issue create` and `gh label` line in `.agents/skills/` and fail on one that touches a state family, and to require a `gate.py` call for each named move; a copy with one direct label write planted fails.
- `parked` is gone from every skill. A piece that today would be parked after three failed attempts is kicked back to `shaping:research` with a `## Kickback` section; a piece stopped at a sensitive-area caution stays in shaping until the acceptance is recorded; a piece with a `## Waiting on you` step sits in `shaping:clarify`; an idea left out is closed as not planned with `gate.py drop`. Check: `.agents/tests/manual-step.sh` and `.agents/tests/the-runner.sh`, their `parked` assertions rewritten to these routes; `state-moves.sh` fails on any `parked` left in `.agents/skills/`.
- `/what-now` names a piece in `state:in-review` with `review:person` as the person's own, in place of `to check`, and leads with `gate.py report`'s findings when there are any. Check: `.agents/tests/state-moves.sh` and `.agents/tests/piece-states.sh`, the `/what-now` assertions updated.
- `/maintain`'s offer to move an older project onto the six states is removed, so no visit moves a project onto a model that no longer exists. Check: `.agents/tests/older-project-upkeep.sh`, its six-state rules removed and a rule added that the maintain skill names no six-state move. Slice 17: /maintain absorbs /sync removes the rest of the old kit's upkeep and that rehearsal with it.
- WORKFLOW.md section 5's paragraph on how each command moves a piece names the gate and the v1 states. Check: `state-moves.sh`, its WORKFLOW.md assertion updated.
- The replay harness's issue-invariants assertion reads the v1 labels. Check: `.agents/tests/replay-state.sh`, its hand-built end states relabelled.
- Root AGENTS.md's maintainer checks describe `gate-script.sh` and `state-guard.sh`, and the entries for every rehearsal this slice rewrote say what they hold now. Check: guided check: the maintainer reads each entry beside the rehearsal's rule list; `validate-kit.sh` passes with no issue number.
#### When it is not the normal case
- A command's gate call is refused: the command reports the gate's line to the person in plain words and stops that move, never retrying with a direct label write. Check: `state-moves.sh`, a rule in each command and in `blocked-commands.md`.
- A run's session dies between the gate's label write and the next step: the state file and the labels agree, because the gate wrote both, and the resumed run reads them as `references/running-longer.md` describes. Check: `the-runner.sh`.

## Masterplan change
Design note: realises "Issue states" and the row "One state and one sub-label" of "What a machine enforces" in `docs/design/agentic-loop.md`. The note needs one addition: the marker the gate keeps in an issue body to tell whether a sub-state's question was answered (see Data).

## Not in this piece
- The ready-gate lint and the `loop:` condition on `shaping:check` to `state:ready`: slice 3: contract v2 and the ready-gate lint.
- What each shaping sub-state does inside `/shape`, the bug fast path and kickback intake: slice 4: shaping sub-states in /shape.
- The frozen bar, the evidence condition on `state:building` to `state:in-review`, and the contract hash: slice 6: frozen-bar enforcement.
- `review:auto` as a real route (every piece goes to `review:person` until then): slice 8: automatic reviewer.
- The v1 run record and run statuses beyond the piece status written here: slice 9: run controller.
- The force-push deny rules from the overnight batch: slice 15: safety boundary for runs.
- The boards that replace the printout: slice 16: boards and notifications.
- Removing the rest of the old kit's migrations and upkeep from `/maintain`: slice 17: /maintain absorbs /sync. No slice moves a project founded with AI Build Kit onto these labels (decision 63).
- The same scripts as Codex hooks and rules: slice 19: Codex parity.

## Decided
- Labels carry their dimension as a prefix with a colon, such as `state:ready`, so a deny rule and the hook can match a family by its prefix (decisions 4, 5, 7 and 42).
- The gate is a Python script, because the printout already needs `python3` and the conditions read issue bodies and JSON.
- The gate ships inside the setup-ai-build-kit skill and is placed into the project the way the printout helper is, because every installation route carries skills and nothing else.
- Until slice 8: automatic reviewer lands, every piece reaching `state:in-review` gets `review:person`, so nothing is reviewed only by a reviewer that does not exist yet.
- The gate never closes a piece as completed. A merged pull request closes it on GitHub, and `gate.py tidy` takes the labels off, because the pull request's `Closes` line is already the one way a piece closes.
- A person changing a label on GitHub is reported and never undone, because the person outranks the gate (design note, "Issue states").
- `parked` and `blocked` go in this slice, because a model with a parked label and no gate route for it would be two models at once.
- This repository's own settings get neither the hook nor the new deny rules, because the kit's own issues use today's labels until the release (decision 55).

## Data
- GitHub labels on the project's repository: 26 the kit owns, created by `gate.py labels`. Founding is the only time the kit deletes labels it did not create, as today.
- A one-line hidden marker in each piece's body, `<!-- loop:gate sub-state=<sub-state> since=<date> answer=<short hash of the answer section> -->`, written by the gate on every move into a shaping sub-state and read on the way out. Only the gate writes it. The gate rewrites that line alone and keeps the rest of the body as it read it moments before.
- A run's `.agents/runs/<name>/state.json`, which git ignores, gains a status field per piece written by the gate. The coordinating session stays its only other writer, as `running-longer.md` says.
- A founded project receives `.agents/tools/gate.py` and `.agents/hooks/state-guard.sh`. No project founded with AI Build Kit is moved onto these labels (decision 63).

## Leaves the tool
Label creation, label changes, body edits for the marker, a closing reason for a dropped piece and a bookkeeping comment for a return to building all go to the project's GitHub repository through the GitHub command-line tool already signed in. The recipient is the person's own repository, as today. Bookkeeping needs no yes, as `pieces.md` says under "Speaking for the person"; a comment addressed to a colleague still does.

## Must still hold
- Founding checks the repository is not the kit's own before creating any label (`first-upload-asks.sh`).
- Bookkeeping needs no yes, anything addressed to a person does (`speaks-for-the-person.sh`).
- Only a pull request's `Closes` line closes a piece (`closing-words.sh`).
- Deny-list parity between `blocked-commands.md` and the settings template (`validate-kit.sh`, `push-to-main-rules.sh`, `refused-commands.sh`).
- The merge ask rule and its script leave every other deny rule and hook in place (`merge-ask-rule.sh`).
- This repository's settings carry no session-start wiring (`session-start.sh`, `validate-kit.sh`).
- The founded AGENTS.md stays under its ceiling (`standing-instructions.sh`).
- A founded project's own type check and linter stay green with the kit's copied scripts in it (`check-floor-rehearsal.sh`).
- No issue numbers in tracked files; `Closes #<the piece>` is written as a placeholder (`validate-kit.sh`).

## Relies on
- `templates/foundation/plan-refresh.sh`, `scripts/place-plan-helper.sh`, `scripts/bootstrap-project.sh`, `templates/foundation/claude-settings.json`, `references/pieces.md` and `references/blocked-commands.md` in the setup-ai-build-kit skill, on main today.
- The stand-in GitHub `.agents/tests/replay/fake-github/gh`, which already answers label edits and blocked-by links on main today; part a extends it to create labels with a colon, edit a body with `--body-file`, close with a reason and list closed issues by label.
- `.agents/tests/lib/permission-matcher.py`, on main today.
- `references/running-longer.md`'s state file in `.agents/runs/<name>/state.json`, on main today.

## Reach and risk
Boundary: the setup-ai-build-kit skill (pieces.md, blocked-commands.md, founding, foundation templates, the placement script), change-triage, shape, implement and running-longer.md, section-builder, fix, sync, what-now, queue, maintain (the six-state offer only), WORKFLOW.md sections 2 and 5, MAINTAINING.md's issue section, the validator's deny parity.
Reaches: claiming and stacking in a run (`the-runner.sh`, `parallel-run.sh`, `queue-groups.sh`); settling a question (`settled-is-recorded.sh`, `who-can-settle.sh`, `shape-later.sh`); the merge step (`one-merge-step.sh`, `recheck-before-merge.sh`); the installation routes (`plan-helper-routes.sh`, `claude-plugin.sh`, `agent-plugin.sh`); the replay end states (`replay-state.sh`, `fake-github.sh`).
If it breaks: a founded project's board shows pieces in no state or two, or the agent cannot move a piece; the person sees it on the printout and from `/what-now`. Each part is its own pull request and is undone by reverting it; part d is reverted before part c.
Depends on: 1.
Loop module: build, because every rule is a script behaviour or a written rule a rehearsal can pass or fail.
Crew: default for the module.

## Under the hood
Write `gate-script.sh` against the stand-in GitHub first and see it fail; then write `gate.py` with subcommands `labels`, `capture`, `move`, `drop`, `tidy` and `report` (the later slices that add a subcommand are listed under Consistency notes), reading the transition table from one data structure so the rehearsal and the script share it. Part b writes `state-guard.sh` (the hook) as a small Python-free shell script reading the hook's JSON with `python3 -c` only where the input needs parsing, and extends `permission-matcher.py`'s callers rather than the matcher. Part c rewrites `pieces.md`'s Labels and States sections and the printout's grouping in `plan-refresh.sh`. Part d replaces every `gh issue edit ... --add-label` state line in the skills with the matching `gate.py` call.

Nothing is reused from the overnight batch branch in this slice. The idea of reading a piece back before the label moves comes from `settled-is-recorded.sh` on main and becomes the gate's answer-marker condition.

Existing rehearsals expected to change: `piece-states.sh`, `state-moves.sh`, `plan-printout.sh`, `queue-groups.sh`, `plan-helper-routes.sh`, `starter-rehearsal.sh`, `claude-plugin.sh`, `agent-plugin.sh`, `the-runner.sh`, `parallel-run.sh`, `manual-step.sh`, `who-can-settle.sh`, `shape-later.sh`, `settled-is-recorded.sh`, `older-project-upkeep.sh`, `replay-state.sh`, `fake-github.sh`, `piece-contract.sh` (the form's default label), `check-floor-rehearsal.sh` (the copied gate script) and `validate-kit.sh` (deny parity, label clearout wording). New: `gate-script.sh`, `state-guard.sh`.

The kit's own rules: answer the five questions in PHILOSOPHY.md in each pull request (fits under every command; the person sees one state and sub-state per piece; "only the gate script moves a piece, and it tells you why when it refuses"; when it goes wrong they type /what-now, which leads with the gate's report; they never need to learn the transition table); run `.agents/tools/build-adapters.sh` where a skill description changes; run `validate-kit.sh`; load the humanizer for every prose change; write no issue numbers.

## Evidence
Scripts run in throwaway repositories against the stand-in GitHub (`gate-script.sh`, `plan-printout.sh`, `starter-rehearsal.sh`), the hook and deny rules driven through the shared matcher (`state-guard.sh`), and rule-shape rehearsals with load-bearing checks for the prose (`piece-states.sh`, `state-moves.sh`, `manual-step.sh`, `older-project-upkeep.sh`).

## Size
Four sittings, one per part: a (gate script and labels), b (hook and deny rules), c (founding, records, printout), d (every command through the gate).

## Consistency notes
- The gate script is `gate.py`, shipped as `setup-ai-build-kit/templates/foundation/gate.py` and placed at `.agents/tools/gate.py`. This slice builds `labels`, `capture`, `move`, `drop`, `tidy` and `report`. Later slices add, each in its own slice: `check-contract`, `evidence` and `stop-check` (slice 6: Frozen-bar enforcement); `result` and `switch-module` (slice 7: Build and fix loop modules); `review` (slice 8: Automatic reviewer); `run` with the actions `start`, `pause`, `resume`, `abandon` and `close`, and `integrate` (slice 9: Run controller); `merge` and `health-after-merge` (slice 13: Merge policy); `push` (slice 15: Safety boundary for runs). No other slice names a gate subcommand.
- Two transitions the design note's table did not list are added here: `state:building` and `state:in-review` back to `state:ready`, for a piece withdrawn because a piece it needs was kicked back, and for every unmerged piece of an abandoned run. Slice 9 is their only caller.
- Until slice 8: Automatic reviewer lands, every piece reaching `state:in-review` gets `review:person`, so nothing waits on a reviewer that does not exist yet. Slice 8 then chooses between `review:auto` and `review:person` in the same transition.
- The run status this slice writes goes into today's `.agents/runs/<name>/state.json`. Slice 9 replaces that file with the run record, `.agents/runs/<run name>/run.json`, and the gate writes there from then on.
- The force-push deny rules belong to slice 15: Safety boundary for runs, and to no other slice.
- Hidden markers the kit writes on GitHub all start with `loop:`: `loop:gate` here, `loop:contract` (slice 6), `loop:review` and `loop:person-verdict` (slice 8).
- A script copied into a founded project carries a check that the project's own lint stays green with it. For `gate.py` that is the `check-floor-rehearsal.sh` line above. How a copied `gate.py` reaches scripts that stay inside the skills (the lint, the guards, the board) is an open decision for the maintainer.
- No project founded with AI Build Kit is moved onto these labels (decision 63). Old-model labels are reported and left alone.
