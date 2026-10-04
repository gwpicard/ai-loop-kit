# Slice 13: A project that has earned it merges a clean run by itself, and production checks itself and rolls back after every merge

Labels (today's set): enhancement, area:skills, ready-able once shaped. Release label for the PR: release-minor.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 2: Label model and gate script; slice 3: Contract v2 and the ready-gate lint; slice 6: Frozen-bar enforcement; slice 8: Automatic reviewer; slice 9: Run controller.

## So that
A person whose project has proved itself stops being asked to merge clean runs, while any run that touches something risky, or any project GitHub cannot protect, still waits for them, and a merge that breaks production is undone without them.

## Done when

This slice splits into three parts, each merged on its own pull request.

### Part a: the merge policy and GitHub's protection

#### Works
- The `merge` setting slice 9 adds to `.agents/loop-settings.json` takes `"person"` or `"automatic"`, and founding writes `"merge": "person"`. Check: new `.agents/tests/merge-policy-rehearsal.sh` founds a throwaway project with `bootstrap-project.sh` and reads `"merge": "person"`; `starter-rehearsal.sh` still passes.
- `gate.py merge` enables GitHub's automatic merge on a run's pull request only when all of these hold, and refuses with one line naming each that failed: the `merge` setting is `"automatic"`; every piece is `review:auto`; every gate is green on the run's head; no piece's boundary or reach names a sensitive area; GitHub protects `main` with the project check required; the run's preview passed its smoke test; the project's recipe records that previews keep their own data. Check: `merge-policy-rehearsal.sh` runs the gate script against the stand-in GitHub once with every condition true, reading `gh pr merge <number> --auto --merge` in the stand-in log, and once with each condition false in turn, reading the refusal and no merge call.
- The person's merge stays the default: with `"merge": "person"`, the gate never calls `gh pr merge`, and the agent's merge follows the `section-builder` skill's `references/merge.md` "yes that names it". Check: `merge-policy-rehearsal.sh`; `one-merge-step.sh` still holds the named yes.
- The run-time pre-approval goes from `merge.md`: "Pre-approval for a run" and its six conditions, which no run has reached since slice 9 removed the question before a run and `merge_preapproved`, are replaced by the merge policy. Check: `one-merge-step.sh` and `not-hosted.sh` rewritten to hold the new rule and to fail on a copy carrying the old six conditions; new `.agents/tests/merge-policy.sh` (rule-shape) reads the policy back from `merge.md`.
- At founding, the kit reads whether GitHub can protect `main`: it reads the repository's visibility and asks the branch protection endpoint, and a 403 naming an upgrade means a free private repository. It says in one plain line which case the project is in, and on a free private repository that the person will always merge. Check: `merge-policy-rehearsal.sh` drives `setup-ai-build-kit/scripts/check-tooling.sh` against the stand-in GitHub answering a public repository, a private repository on a paid plan and a free private repository, reading the three lines; `check-tooling.sh` (the existing rehearsal) still passes.
- Where GitHub can protect `main`, the kit offers once to set a ruleset on `main` that requires the project check, a pull request, and refuses force pushes and deletion; it creates the ruleset only on a yes that names it, and says beforehand what changes online and that it can be removed in the repository's settings. Check: `merge-policy-rehearsal.sh` reads no ruleset call without the yes and one `gh api` ruleset call after it; `merge-policy.sh` reads the explanation rule from the founding skill.
- The gate re-reads protection before each automatic merge, and a ruleset removed since founding turns automatic merge off for that run with one line. Check: `merge-policy-rehearsal.sh` with protection removed between two runs.
- The stand-in GitHub answers the protection and ruleset endpoints and `pr merge --auto` the way GitHub does for each repository kind. Check: `fake-github.sh` extended with those cases.
- The `review:person` triggers this slice owns are forced by the gate: a piece whose `If it breaks:` says a data change cannot be undone, and any run while the project has no recorded live address (its first deployment). Check: `merge-policy-rehearsal.sh` reads `review:person` written by the gate in both cases.

#### When it is not the normal case
- GitHub cannot be reached when the gate checks protection: nothing merges automatically; the run's pull request waits for the person, said once. Check: `merge-policy-rehearsal.sh` with the stand-in offline.
- The `merge` setting says `"automatic"` on a free private repository: the gate refuses, says GitHub cannot protect `main` there, and the person merges. Check: `merge-policy-rehearsal.sh`.
- A tool that is `not hosted`: the preview conditions do not apply, because there is no preview; the smoke test is the acceptance checks on the run's head, already green, and a merge means done. Check: `merge-policy-rehearsal.sh` with `Goes live: not hosted`.

### Part b: the preview smoke test

#### Works
- Before an automatic merge, the run's integration branch preview is reached at the address the project's recipe gives, and each acceptance path the run's pieces name in their contracts' `Smoke:` lines is requested there and must answer as the line says, then the recipe's health route on the preview must answer. Check: `merge-policy-rehearsal.sh` with the stand-in host serving a preview, one path answering as named and one not, reading a pass and a refusal naming the path.
- The ready-gate lint accepts a `Smoke:` line on a piece whose contract names a screen or an address, as a path and the text or status expected. Check: slice 3's lint rehearsal extended; `piece-contract.sh` reads the field rule from `pieces.md`.
- `recipe-format.md` defines an optional `Previews keep their own data:` line in a recipe's proven section, carrying the real run's date, and `check-recipes.sh` refuses the line without a date. Neither recipe carries it until slice 14's real runs, so automatic merge stays off on both recipes after this slice. Check: `recipes.sh` extended with a copy carrying the line without a date; `merge-policy-rehearsal.sh` reads the refusal on each shipped recipe.

#### When it is not the normal case
- The preview is behind the host's sign-in: the smoke test uses the recipe's own way past it where the recipe names one and the person agreed to it, and otherwise the condition fails and the person merges. Check: `merge-policy-rehearsal.sh` with the stand-in preview answering 302.
- The preview never becomes ready within the recipe's wait: the condition fails, said once; nothing merges automatically. Check: `merge-policy-rehearsal.sh`.

### Part c: health after the merge, rollback and irreversible data

#### Works
- After each merge the kit makes on a project whose merge goes live, it waits for production to serve the merge commit, then runs the recipe's health check against production. Check: `merge-policy-rehearsal.sh` with the stand-in host, reading the health read and the commit compared.
- When that health check fails and the recipe's rollback is run by the kit, it rolls back to the previous build with the recipe's own command, reads health again, files a `type:bug` piece in `shaping:raw` naming the merge, and tells the person; the recipe's commands need no second yes, as `/ship` already says. Check: `merge-policy-rehearsal.sh` with the stand-in host failing health after a merge, reading the rollback call, the second health read and the new issue in the stand-in GitHub log; `fake-host.sh` extended to serve a failing build.
- When the recipe's rollback is run by a companion or the person, the kit does not roll back: it files the bug piece, tells the person what to click and where, and automatic merge never turns on for a project on such a recipe. Check: `merge-policy-rehearsal.sh` with the Coolify recipe named.
- A piece whose `If it breaks:` marks a data change that cannot be undone never merges until a backup taken after its last green check and before its migration is applied is recorded in the run record, with the recipe's backup section run by the kit or confirmed by the person with the backup's location. Check: `merge-policy-rehearsal.sh` reads the refusal without a backup record, with a backup older than the last check, and the pass with a fresh one.
- `merge.md` says all of this under its "When a merge goes live" heading, and `/ship` points at it rather than restating it. Check: `merge-policy.sh` reads the rules and proves each load-bearing; `one-merge-step.sh` still fails on a skill restating the merge rule.

#### When it is not the normal case
- The person merged on GitHub's page, so no kit session saw the merge: the session-start hook finds a merged run pull request with no recorded health result and runs the check then, saying so. Check: `session-start.sh` extended with that case.
- Production never serves the merge commit within the recipe's wait: treated as a failed health check. Check: `merge-policy-rehearsal.sh`.
- The rollback itself fails: the kit says so plainly, files the bug piece, records it in CHANGELOG.md, and never runs a second deploy, as `ship-merges-and-deploys-once.sh` holds. Check: `merge-policy-rehearsal.sh` with a failing stand-in rollback.

### Documents this slice changes (all parts)
- WORKFLOW.md sections 7, 9 and 10 and "What stays yours": the person decides what merges until the project earns automatic merge, a free private repository always has the person merge, and production checks itself after each merge. Check: `merge-policy.sh` reads each sentence; `one-story-try.sh` changes its "deciding what merges" assertion to the new wording.
- README.md's opening, "What the kit does to reduce risk" and the FAQ answer that says the person decides what merges. Check: `one-story-try.sh` (both README places) and `merge-policy.sh`.
- docs/PHILOSOPHY.md's statement of what stays the person's. Check: `one-story-try.sh`.
- The foundation AGENTS.md template's merge line ("A merge needs a yes naming it or a run's ...") rewritten to name the merge policy. Check: `merge-policy.sh` reads it; `standing-instructions.sh` holds the ceiling.
- `setup-ai-build-kit/references/blocked-commands.md` and the root `.agents/guard/blocked-commands.md`: the gate's automatic merge is named as the one merge the confirmation box does not see, and why. Check: `merge-ask-rule.sh` extended to read the line; `validate-kit.sh` compares the deny lists.
- `completion-report.md` carries the one protection line. Check: `completion-report-shape.sh` extended.
- docs/COMPATIBILITY.md says automatic merge runs through the gate script on any coding agent that can run it. Check: `merge-policy.sh`.
- The root AGENTS.md describes the two new checks and the changed paragraphs for `one-merge-step.sh`, `not-hosted.sh`, `run-controller.sh`, `fake-github.sh` and `fake-host.sh`. Check: `validate-kit.sh`.

## Masterplan change
Design note: "Merging and going live" and the automatic merge row of "What a machine enforces" in docs/design/agentic-loop.md. Two additions the note needs: a recipe whose rollback the kit cannot run never earns automatic merge, and a `not hosted` project's smoke test is the acceptance checks on the run's head.

## Not in this piece
- The clean-run count, the kit metrics and the `/maintain` offer that switches the `merge` setting to `"automatic"`: slice 17: /maintain absorbs /sync.
- The preview address, previews with their own data and the real runs that write `Previews keep their own data:`: slice 14: /deploy replacing /ship.
- Integration one piece at a time and bisect on red: slice 9: Run controller.
- The scoped push token: slice 15: Safety boundary for runs.
- The notification that a run went live: slice 16: Boards and notifications.

## Decided
- Each project starts with the person merging, and automatic merge is earned (decision 37); this slice builds the conditions, slice 17 builds the earning.
- Automatic merge needs GitHub's protection (decision 19), read from the API's answer rather than from the account's plan, because the plan is not readable for another owner's repository.
- The gate script enables GitHub's own automatic merge rather than merging itself, so GitHub's required check is the last word (the design's "What a machine enforces").
- The person's merge stays an agent `gh pr merge` that the confirmation box sees; only the gate's automatic merge bypasses the box, and only under the policy.
- Run-time pre-approval is removed, because a run asks nothing (decision 3) and the policy replaces it.
- A failed health check rolls back first (decision 38). Where the recipe's rollback is a person's click, the kit cannot roll back, so such a recipe never earns automatic merge.
- The backup for an irreversible change is taken before the migration is applied, not only before the merge, because the recipes apply migrations before the merge (decision 48).
- Acceptance paths for the smoke test come from a `Smoke:` line in each contract, because the design names the smoke test but no field that says which paths to try.

## Data
- The `merge` setting in `.agents/loop-settings.json` (slice 9), written by founding and later by slice 17's offer.
- Run record fields: protection read, smoke test result, health result after the merge, rollback made, backup taken with its location (never its contents).
- A ruleset on GitHub, only on a named yes.
- A settings file with no `merge` key reads as `"person"`. No project founded with AI Build Kit is moved (decision 63).

## Leaves the tool
On a yes, a ruleset on the repository's `main`. GitHub's automatic merge on a run's pull request. Requests to the preview and production addresses for the smoke test and the health check, which the recipe already makes. A `type:bug` issue after a failed health check. The backup stays where the recipe puts it, outside the repository.

## Must still hold
- A merge waits for the check on the commit brought up to date with `main`. Check: `recheck-before-merge.sh`, `fold-at-merge.sh`.
- A named yes for the person's merge, and a stacked pull request never merged before its base. Check: `one-merge-step.sh`.
- No push to `main` and no force push. Check: `push-to-main-rules.sh`.
- Rollback is never run only to prove it can be, and a second deploy is never run before the first is checked. Check: `ship-runs-recipe.sh`, `ship-merges-and-deploys-once.sh`.
- No stored login is read. Check: `no-stored-logins.sh`.
- A secret is passed by its location and never shown. Check: `secret-location.sh`.
- The confirmation box on merges that go live. Check: `merge-ask-rule.sh`.
- No issue numbers and no attribution lines in tracked files. Check: `validate-kit.sh`.

## Relies on
- `section-builder/references/merge.md`, `section-builder/scripts/bring-up-to-date.sh`, `setup-ai-build-kit/scripts/check-tooling.sh` and `merge-ask-rules.py`, the recipes' health, rollback and backup sections, the stand-ins `fake-github.sh` and `fake-host.sh` exercise: on main today.
- The gate script: slice 2. The contract fields `If it breaks:`, `Boundary:` and `Reaches:`: slice 3. Green gates and the evidence record: slice 6. `review:auto`: slice 8. The run record (`run.json`), the `merge` setting in `.agents/loop-settings.json` and the run's pull request: slice 9.

## Reach and risk
Boundary: the `section-builder` skill's merge reference, the gate script, `/ship`'s pointers to the merge step, `/implement` and its run reference, founding's tooling report and completion report, the recipe format and its checker, WORKFLOW.md, README.md, PHILOSOPHY.md, COMPATIBILITY.md, the foundation AGENTS.md template, both blocked-commands files, the root AGENTS.md checks list.
Reaches: merging (`recheck-before-merge.sh`, `fold-at-merge.sh`, `closing-words.sh`), launching (`ship-runs-recipe.sh`, `ship-merges-and-deploys-once.sh`, `request-record.sh`), the replay scenarios 52 to 55 on merging and launching (`replay-state.sh`, `gated-turns.sh`), session start (`session-start.sh`).
If it breaks: a run merges without the person when it should not, or production stays broken after a merge. The person sees the run go live on the loop board or a bug piece appear. A wrong merge is undone by the rollback and a revert pull request; the setting goes back to `person` by editing one line.
Depends on: 2, 3, 6, 8, 9.
Loop module: build, because every condition is a gate decision a stand-in GitHub and host can judge.
Crew: default.

## Under the hood
Add `gate.py merge` to slice 2's gate script, and `gate.py health-after-merge`, run by the coordinating session after a kit-made merge and by the session-start hook for a hand merge. Extend the stand-ins: `fake-github` answers protection, rulesets and `pr merge --auto` by repository kind; `fake-host` serves a failing build and a failing rollback. Rewrite the pre-approval parts of `merge.md` and `running-longer.md`. Add `merge-policy.sh` (rule-shape) and `merge-policy-rehearsal.sh`. Change `one-merge-step.sh`, `not-hosted.sh`, `run-controller.sh`, `one-story-try.sh`, `merge-ask-rule.sh`, `completion-report-shape.sh`, `recipes.sh`, `fake-github.sh`, `fake-host.sh`, `session-start.sh`. Nothing is reused from the overnight batch; its force-push deny rules are slice 15's. Canonical skills change: five questions in each pull request, SOURCES.md credits (Gas Town for merging one item at a time; cloud agents' pushes limited to their branch), adapters rebuilt, validator run, humanizer on the prose, no issue numbers.

## Evidence
Rule-shape checks with each rule proved load-bearing; a script rehearsal of the gate against stand-in GitHub and host in throwaway projects. The real merge, health check and rollback on a recipe are recorded in slice 14's real runs.

## Size
Three sittings, as Part a (policy and protection), Part b (smoke test) and Part c (health, rollback, irreversible data). Part b and Part c both need Part a.

## Consistency notes
- The merge setting is the `merge` key in `.agents/loop-settings.json`, `"person"` or `"automatic"`. Slice 9 adds it with `"person"`; slice 17 offers the switch to `"automatic"`.
- Slice 9 removed the question before a run and `merge_preapproved` from `running-longer.md`; this slice removes the dead "Pre-approval for a run" section from `merge.md`, so each removal has one owner.
- The gate subcommands this slice adds are `gate.py merge` and `gate.py health-after-merge`.
- The `Smoke:` line is this slice's field: it extends slice 3's contract and lint, and slice 3 names it as this slice's.
- The force-push deny rules are slice 15's alone.
- Build paths keep today's behaviour: a sensitive area, named today only on Build with care, keeps a run's pull request with the person.
