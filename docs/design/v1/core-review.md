# Post-hoc review of the v1 core

The merged core follows the design in part. It has working offline coverage, but
several decided rules are missing or weaker than the design. A green rehearsal
can also assert a limitation, so it is not evidence that the limitation is fixed.

This review covers P1 to P27 at `c7340d9828a30ebfe74c3e89be456d2c16bec319`.
Three fresh, ephemeral Codex sessions reviewed P1 to P9, P10 to P18 and P19 to
P27 in read-only sandboxes. Each read the design and decisions as well as the
plan, implementation and tests. The decisions file wins where sources disagree.
The plan's recorded interim rules and L1 to L10 deferrals are stated separately.
R1 changes this document only; it fixes none of the findings.

“Fix now” means shape a repair before claiming the core conforms. “Fix later”
means planned v1 release work, a documented limitation or a maintainer decision.
Neither judgement authorises a change to settings, a real credential, a release
or a public repository. F1 and F2 are separate repairs under review. Their
baseline faults remain open until those repairs merge and pass checks.

## Evidence and limits

The P1 to P9 reviewer ran 149 selected unit tests successfully. Its separate
single-file spec invocation passed 40 overlapping tests, not 40 additional
checks. In-memory probes reproduced several findings below. The other two
reviewers supplied source reviews; their test citations mean assertions read,
not executed passes. This is not a real Claude, App, sandbox or hosted-workflow
validation. The real smoke script was not run.

The preserved baseline check results and the final document checks are recorded
in the pull request. Check copies disable recursive cleanup only and retain
scratch work; tracked checks are unchanged. The audit reports are local run
evidence, not installed product files.

## Piece coverage

“No separate finding” means this audit found no additional departure in that
piece. It does not prove every input or runtime boundary.

| Piece | Source and test evidence inspected | Conclusion |
| --- | --- | --- |
| P1 foundations | `loop/cli.py`, `loop/paths.py`, `tests/harness.sh`, `tests/script-contracts.sh`, `test_cli.py`, `test_paths.py` | Infrastructure present; contracts and skip reporting need CR-04 and CR-05. |
| P2 parser | `loop/spec.py`, `kit/spec-format.md`, `test_spec.py`, `tests/spec-parse.sh` | Shared versioned parser, raw block and writers present; example/source wording remains later work. |
| P3 guard and log | `kit/hooks/guard.py`, `command-log.py`, `test_guard.py`, `test_command_log.py` | Common forms protected and events deduplicated; indirect forms remain CR-03. |
| P4 secrets | `secret-scan.py`, pre-push template, `loop/github.py`, `test_secret_scan.py` | Two scan points; commit-message blind spot remains CR-21. |
| P5 dependencies | `dependency-check.py`, npm/uv templates, `test_dependency_check.py`, `tests/dependency-check.sh` | Age/licence checks present; unchecked parsing and formats remain CR-06. |
| P6 new tests | `loop/newtest_lint.py`, `newtest-lint.py`, test-smell fixtures and mutations | Supported-language rules present; silent exclusions remain CR-07. |
| P7 skills lint | `check-skills.py`, plugin manifest, skill fixtures, `tests/check-skills.sh` | Structural lint present; hard-rule and installed-path gaps remain CR-01. |
| P8 needs | `loop/lint.py`, `needs.py`, `test_lint.py`, `test_needs.py` | Most needs present; acceptance and list projection remain CR-10 and CR-12. |
| P9 judges and evidence | `loop/judge.py`, `fingerprint.py`, `evidence.py`, `heldout.py`, runner fixtures and unit tests | Storage and keyed evidence present; assertion/report and semantic fingerprint gaps remain CR-08 and CR-09. |
| P10 settings | settings templates, `hooks.json`, `tests/settings.sh`, permission matcher | Common layers present; real installed-root protection remains CR-02. |
| P11 gate | `loop/states.py`, `moves.py`, `github.py`, `tests/gate.sh`, `test_moves.py` | States/moves and pre-App queue present; completion is F1 and hand-label reconciliation is later work. |
| P12 sessions | `loop/sessions.py`, handoff doors, builder brief, worktree rehearsal and unit tests | Fresh sessions and credential scrubbing present; callable contracts and planned bar allowance need CR-04 and CR-06. |
| P13 pre-run | `pre-run-check.py`, policy module, `tests/pre-run-check.sh` | Version, guards, computer and scaffold exception checked; policy/runner classification needs CR-20. |
| P14 ready | `loop/gates/ready.py`, test lists, `test_ready.py`, `tests/ready-gate.sh` | Main checks present; notice, executable hidden cases and freshness need CR-10, CR-11 and CR-13. |
| P15 claim | `loop/gates/claim.py`, research parsing, `test_claim.py`, `tests/claim-gate.sh` | Quick research, fingerprint and slots checked; L9 refresh is deliberate, rebase/freshness remains CR-13. |
| P16 attempt | attempt/bar/log modules, `test_attempt.py`, `test_bar.py`, attempt rehearsal | Most gate checks present; unchecked dependencies/tests remain CR-06 and CR-07. |
| P17 records | `loop/records.py`, templates, records/document rehearsals | Mechanical checks present but narrower than decided sensitivity/rules requirements, CR-14. |
| P18 shape | shape skill, references, duplicate helper, eval specifications, `tests/shape-skill.sh` | Helpers and sequence described; installed commands/holders need CR-01 and model evals remain unproved. |
| P19 trim | `loop/trim.py`, trim-check door/brief, `tests/trim.sh` | Standalone remove/fold limits present; stacked pieces skip it, CR-19. |
| P20 setup first half | `setup.py`, setup skill, project templates, setup rehearsal | Preserves files and founds locally; F2, existing-runner scaffolds and update paths remain. |
| P21 run | `run.py`, engine/plan/gateway/record/summary modules, run rehearsal and engine tests | Scheduling and resume present; parked records, spend and project lock need CR-15 to CR-17. |
| P22 stuck and answers | watch/mailbox/inbox modules, watch/answer rehearsals and unit tests | Stuck/reset/input routes present; visible parking remains CR-15. L1/L3 supervise and notify later. |
| P23 integration | integrate/docs-commit modules, integration rehearsal and unit tests | Trial/rebuild mechanics present; complete checks and current-doc projection need CR-18 and CR-14. |
| P24 review | review module, reviewer brief/settings, review rehearsal and unit tests | Fresh rounds/findings present; cost accounting and output permission need CR-16 and CR-22. |
| P25 run skill | run skill/fixtures, `tests/run-skill.sh` | Launch commands use plugin root; report injection and claimed guard still need CR-01. |
| P26 merge | pull-request/merge gates and merge-door tests | Exact-head checks present; manual completion is F1, indirect mutation forms CR-03. |
| P27 rehearsal | e2e-core fixtures/script, stand-ins, manual smoke entry | Useful diagnostic coverage; explicitly asserts F1 and supplies a manual policy transition around F2. |

Module paths in this table are under `kit/scripts/` and unit files under
`tests/unit/` unless a full path is given.

## Findings to shape

### CR-01. Harden skill commands and claimed holders

**Pieces:** P7, P18, P25. **Fix now.**

**Design:** “lint requires a `Held by:` pointer after every hard rule” and
“lint fails on a copied row of the gate's table, label names or exit codes”
(`design.md:868-869`). Principle 13 requires live state injection and a fallback;
principle 17 makes skill-scoped tools conveniences, not guards.

**Evidence:** `kit/scripts/check-skills.py:77-83` has a stale label list;
`:279-318` misses paragraph hard rules and accepts fictional gate/settings
holders. The P1 to P9 probes reproduced both escapes. It counts lines/words
but not the estimated tokens named in principle 3. No new token threshold is
implied. `kit/skills/shape/SKILL.md:10-45` uses project-relative kit paths;
`kit/skills/run/SKILL.md:14-15` does too for injection/fallback, despite corrected
launch commands. `tests/run-skill.sh:81-94` checks frontmatter strings rather
than independently proving the source-editing restriction.

**Repair:** use authoritative labels and real holders, check all hard-rule
forms, count estimated tokens, and test commands from a founded project with
no local `kit/`. Run the tools/order/files/reply scenario evals and no-plugin
baseline before release. Existing eval documents do not prove model behaviour.

### CR-02. Protect the actual installed guard paths

**Pieces:** P10, P12, P20. **Fix now.**

**Design:** “deny rules and sandbox write-blocks on the gate, hooks, settings
and workflows” (`decisions-2026-10-05.md`, research B2).

**Evidence:** `kit/templates/claude-settings.json:105-117` has credential read
blocks but no guard write blocks. Its edit deny assumes the simplified cache
path. `tests/settings.sh:109` models that same path. Builder settings separately
protect the resolved root, so this finding concerns an incomplete independent
layer, not proof that all isolation fails.

**Repair:** render the actual marketplace/version root into both protections
and test the attended and builder settings. Coordinate update re-rendering
with L5; the present first-half guard cannot wait for that extension.

### CR-03. Refuse opaque mutation and hook-bypass forms

**Pieces:** P3, P10, P26. **Fix now.**

**Design:** “Every important rule is held in at least two independent layers”
(`design.md:23`); research B3 requires parsed commands.

**Evidence:** `kit/hooks/guard.py:685-755,796-848` allows unresolved executable
variables, file-fed GraphQL and exotic Git configuration overrides. The P1 to
P9 reviewer called the parser in memory, without executing those commands,
and reproduced the recorded indirect `gh`, `--config-env` and
`GIT_CONFIG_COUNT` gaps. Literal merge and ordinary hook-path/alias changes
are now refused.

**Repair:** refuse or ask when a protected executable/configuration/payload
cannot be inspected. Arbitrary agent-written code importing gate internals
remains a sandbox and App-key boundary, not something text parsing can prove.
L1 must exercise that boundary in the authorised real smoke.

### CR-04. Check callable contracts with valid operations

**Pieces:** P1, P12, P18. **Fix now.**

**Design:** “no prompts, `--help`, JSON out, distinct exit codes, idempotent,
`--dry-run`, errors that name the next command” (`design.md:875`). Contracts
cover every script the skills call (`design.md:943`).

**Evidence:** `tests/lib/contract_check.py:111-145` repeats empty arguments and
argument-free dry-run failures. Marker discovery misses callable module doors
such as `loop.heldout`. `kit/scripts/loop/cli.py:119-125` does not catch an
invalid-choice `argparse.ArgumentError`; the reviewer reproduced the traceback
in memory. Some piece-specific repeat tests exist, but they do not cover every
callable door.

**Repair:** inventory skill-called entry points, test valid repeated/dry-run
operations and normalise parser errors. State hook-protocol exceptions rather
than treating unmarked entries as checked.

### CR-05. Separate skipped checks from passes

**Pieces:** P1, P14, P19, P24, P27. **Fix now.**

**Plan test rule:** “A test that skips a step prints a visible "skipped" line
and never counts the skip as a pass” (`build-plan.md:105`). The design also says
“"no checks ran" is never green” (`design.md:989`).

**Evidence:** `tests/ready-gate.sh:38-40`, `tests/judge-runner.sh:28-30`,
`tests/trim.sh:43-44` and `tests/review-loop.sh:45-46` exit zero without pytest.
`tests/run-all.sh:48-60` counts every zero as passed.

**Repair:** record pass, skip and failure separately and refuse incomplete
required validation. Retain visible optional validator/tool skips honestly.

### CR-06. Fail closed on unchecked dependencies and preserve planned edits

**Pieces:** P5, P12, P16, P21. **Fix now.**

**Design:** “Age and licence checked before a new dependency is accepted”
(`design.md:644`).

**Evidence:** `kit/scripts/dependency-check.py:115-157,520-536` misclassifies
workspace entries and can parse supported-looking lockfile content as zero
packages. An inline pnpm entry returned no packages in the reviewer probe.
`kit/scripts/loop/gates/attempt.py:580-629` notes unsupported manifests rather
than refusing them; `test_attempt.py:864-876` asserts that no-check pass.
Private source identity is not retained sufficiently. Separately,
`kit/scripts/loop/run/engine.py:827-841` drops the dependency-planned argument
when listing bar paths, although `loop/bar.py:296-318` supports it.

**Repair:** recognise supported syntax/workspaces, preserve provenance, refuse
incomplete/unsupported checks, and pass planned dependency intent into builder
settings while keeping test configuration frozen. Private registries may wait
if the unsupported path refuses acceptance.

### CR-07. Make unchecked new tests visible

**Pieces:** P6, P16. **Fix now.**

**Design:** the gate runs “the new-test lint” (`design.md:275`), and the checks
table feeds its mechanically detectable test rules (`design.md:948-952`).

**Evidence:** `kit/scripts/newtest-lint.py:130-177` silently excludes unknown
languages and unreadable changed files. Supported Python/TypeScript rules have
fixtures and mutations; those do not establish coverage of excluded files.

**Repair:** report unchecked inputs and refuse where required test evidence
cannot be read. Define the supported-language boundary and the review route
for other languages; do not report them as mechanically linted.

### CR-08. Require complete judge execution evidence

**Pieces:** P9, P14, P16. **Fix now.**

**Design:** “an assertion naming the spec ID it proves” (`design.md:47`) and
“"no checks ran" is never green” (`design.md:989`).

**Evidence:** `kit/scripts/loop/judge.py:266-300` accepts missing successful
reports and does not validate execution/skip counts. It unions failure IDs,
so a named assertion can mask an unnamed assertion. The reviewer's mixed
failure probe returned `failed` and FL-1 despite the second failure lacking
an ID. Ready now refuses unsupported-runner failure evidence, which closes
the older unknown-runner note but not this mixed case.

**Repair:** require IDs on each relevant assertion and execution/skip counts
for report-backed judges. Distinguish generic exit-code checks from acceptance
judges rather than calling either sufficient by accident.

### CR-09. Preserve meaningful spec whitespace in fingerprints

**Piece:** P9. **Fix now.**

**Design:** “a hash of the spec block and the judge files commit”
(`design.md:684`).

**Evidence:** `kit/scripts/loop/fingerprint.py:55-70` strips indentation and
blank lines. The reviewer changed Python indentation in a fenced example and
obtained identical normalised text.

**Repair:** preserve semantic whitespace, especially fenced code, and exclude
only explicitly gate-owned fields. A formatting-only equivalence test cannot
prove that every collapsed change is harmless.

### CR-10. Require the recorded risk notice

**Pieces:** P8, P14, P18. **Fix now.**

**Decision:** “The spec's Sensitive areas section holds the risk notice, the
person's exact words and the date; the ready gate refuses a sensitive piece
without it” (`decisions-2026-10-05.md`, answer 12).

**Evidence:** `kit/scripts/loop/needs.py:131-145` and `loop/gates/ready.py:248-258`
check only Accepted, quotation and date syntax. `test_ready.py:433-436`
accepts the notice-free shape. A reviewer probe also produced no sensitive need.

**Repair:** use a checkable notice/acceptance structure and a valid calendar
date. Preserve the person's words; syntax alone does not authenticate consent.

### CR-11. Validate executable hidden cases before ready

**Pieces:** P9, P14, P16. **Fix now.**

**Design:** ready sets aside “Hidden cases for an acceptance-test piece”
(`design.md:222`); ready means the frozen spec is buildable without watching.

**Evidence:** ready checks hidden fingerprints but defers safe placement
markers and command linkage to `kit/scripts/loop/gates/attempt.py:384-442`.
`tests/ready-gate.sh` reaches ready with descriptive hidden-case text rather
than executable marked files.

**Repair:** check hidden file shape, safe paths and judge-command substitution
at ready, and use executable hidden cases in its rehearsal. Do not expose
those cases to the builder.

### CR-12. Project list differences into needs and tighten examples

**Pieces:** P8, P14. **Fix now.**

**Design:** “An ID one list covers and the other does not becomes a need”
(`design.md:140`); edge cases have “a concrete example value” (`design.md:152`).

**Evidence:** `kit/scripts/loop/gates/ready.py:603-609` does not pass lists to
needs, though `:642-650` separately refuses disagreement. `loop/lint.py:103,250`
accepts any occurrence of the word no as example data.

**Repair:** expose the recorded list disagreement in computed needs and make
example validation precise. Align the empty-month design example when changing
that rule. The independent list refusal already protects readiness.

### CR-13. Establish current main and safe rebase recovery

**Pieces:** P14, P15. **Fix now.**

**Design:** “Every judge must fail on today's `main`” (`design.md:47`). The
house rule forbids force-pushes.

**Evidence:** ready/claim use local main without establishing origin freshness.
`kit/scripts/loop/gates/ready.py:356` recommends rebasing an already-publishable
piece branch without a no-force recovery route; `test_ready.py:291` asserts it.
`loop/gates/claim.py:249-298` treats a content-preserving judge-commit rebase
as a changed judge.

**Repair:** record the fetched baseline and compare judge content as well as
ancestry. Recommend a recovery that preserves published history. Keep the
new need/repeat rules from trapping an unchanged judge in repeated kickbacks.

### CR-14. Hold the decided records model

**Pieces:** P17, P23. **Fix now.**

**Decision:** “area map (CODEOWNERS-style, every file in an area, flags agree
with the overview)” (`decisions-2026-10-05.md`, records model). Area docs hold
“Current text only” (`design.md:834`). The records table also requires optional
area-rule paths to match the map and AGENTS lines not to repeat a hook/check.

**Evidence:** `kit/scripts/loop/records.py:27-28,259-273` has no map sensitivity
flags to compare. Optional area-rule paths are not checked; duplicate prose
checks cover literal long paragraphs, not copied enforcement. The plan narrows
those requirements without a superseding decision.
`loop/run/docs_commit.py:233-263` appends Changed lines like Added lines,
retaining superseded behaviour and a textual piece reference rather than a
real issue link. Current decisions/reasons are not reliably projected.

**Repair:** make sensitivity mechanically comparable, implement the optional
rules checks when those files exist, and replace or refuse ambiguous current
behaviour updates. Keep real links and decision reasons. A maintainer can
instead make an explicit design amendment; R1 makes none.

### CR-15. Write parked questions and decisions onto the piece

**Pieces:** P21, P22. **Fix now.**

**Design:** “the question written on it and the `needs-you` flag set”
(`design.md:577`); decisions go “on the piece under its decisions, marked for
the person's review” (`design.md:576`).

**Evidence:** `kit/scripts/loop/run/engine.py:978` parks in the run record
without the corresponding issue/spec update. `tests/run-loop.sh:439-466`
checks internal parking and state, not the required visible question/flag.
The summary collects decisions, but does not replace their durable piece home.

**Repair:** provide gate-owned park/clear and decision operations, preserving
the current state while making the person's next action visible. Before the
App, queue those writes through the existing person sync route.

### CR-16. Account for reviewer spend and reserve parallel budgets

**Pieces:** P21, P24. **Fix now.**

**Design:** “a spend cap per piece and per run” and “Reaching a cap waits for
the person” (`design.md:303`).

**Evidence:** `kit/scripts/loop/run/review.py:604-607` records nothing for an
unreadable reviewer cost. `engine.py:747-765` gives each active worker the
current remaining budget, and records spend after completion at `:952`.
There is no reservation preventing several slots receiving the same remainder.
The race is inferred from source; no overspend was reproduced.

**Repair:** use conservative reviewer fallback and atomic budget reservations.
Keep the existing safe-direction build fallback and add a caller-level check
that fails if its budget argument is dropped.

### CR-17. Acquire one atomic project lock

**Piece:** P21. **Fix now.**

**Design:** “Only one run per project runs at a time, held by a lock file”
(`design.md:401`).

**Evidence:** `kit/scripts/loop/paths.py:125` locates locks inside each named
run. `loop/run/record.py:291-299` atomically locks that name only. `run.py:241-245`
scans before acquisition, leaving a race between different names. Tests cover
the same-name case; this cross-name race was not executed.

**Repair:** acquire a project lock atomically before admitting a run, and
associate it with the run record.

### CR-18. Run the complete integration checks

**Piece:** P23. **Fix now.**

**Design:** “re-run every joined piece's judges (visible and held-out)”
(`design.md:353`) and “the full project checks, the validator if the project
has one, and every judge” (`design.md:356`).

**Evidence:** `kit/scripts/loop/run/integrate.py:715` sets held=False for trial
joins. `:661-684,919-941` builds final checks from selected piece checks without
a distinct full-project command or validator. The integration rehearsal tests
held-out execution only at final integration. The plan's narrower test cannot
override the decided trial requirement.

**Repair:** run held-out checks at each trial and full-project/validator checks
on the exact final tree after documentation. Add a hidden cross-piece clash
and an unrelated regression that passes all selected judges.

### CR-19. Trim stacked pieces

**Pieces:** P19, P21, P23. **Fix now.**

**Design:** “The trim pass stays in v1 as the last step of the build loop”
(`design.md:317`).

**Evidence:** `kit/scripts/loop/run/engine.py:1033-1041` deliberately skips trim
when stack_base exists. `tests/unit/test_engine.py:57-65` asserts that skip.

**Repair:** carry a trustworthy stack base through the pass and its gate
checks. L10 defers extra quality checks, not the trim itself. Aggregate net
removal remains a reasonable fold interpretation; per-file growth alone is
not a separate defect.

### CR-20. Distinguish an existing runner from a proposed command

**Pieces:** P13, P14, P20. **Fix now.**

**Design:** “The first piece in an empty project is the exception”
(`design.md:47`).

**Evidence:** `kit/scripts/setup.py:525-573` captures a scaffold without using
its existing project_has_runner helper. `loop/gates/ready.py:150-154` treats a
non-empty policy command as proof a runner exists. The local pre-run exception
works for the generated empty policy, but not a proposed future command.

**Repair:** omit unnecessary scaffolds and base the exception on actual
runner state. Test an empty project with a proposed command. This is distinct
from F2's hosted workflow refusing the generated empty policy.

### CR-21. Scan known secret shapes in commit messages

**Piece:** P4. **Fix now.**

**Decision:** “a secret scan before every push” (answer 9) and “secret scan in
two places” (research G, `decisions-2026-10-05.md:46`).

**Evidence:** `kit/scripts/secret-scan.py:267` omits commit messages with
`git log -p --format=`. Its help lists this blind spot; `test_secret_scan.py:327-334`
checks the description, not protection. Both scan points use this detector.

**Repair:** include commit messages for known shapes without printing values.
Keep honest limits for split or ambiguous values; optional gitleaks cannot
establish protection when it is absent.

### CR-22. Establish the reviewer's output permission

**Pieces:** P12, P24. **Fix now.**

**Design:** “Every finding becomes one of three things”
(`design.md:371`): a failing check, shaping issue or note, produced by the fresh reviewer. Explicit session settings
hold the non-interactive boundary (`design.md:527`).

**Evidence:** `kit/templates/reviewer-settings.json:8` grants Edit on the
findings path but no Write grant. `loop/run/review.py:558-568` moves the old file
aside before launch. The stand-in writes directly and does not establish that
the real reviewer can create its new file in dontAsk mode.

**Repair:** establish creation permission for that exact output path and
exercise it in the authorised live validation. This is a configuration gap,
not a claim that a real Claude reviewer was run and failed.

## Separate F1 and F2 repairs

**F1, fix now:** move 11 includes the person's merge (`design.md:111`).
`tests/fixtures/e2e-core/rehearse.py:273-313` asserts that the manual merge is
not adopted and the pieces remain in review. The no-App ready/claim refusal
for a hosted issue is another open attended-path limitation, not F1's merge
tracking repair. Its dependency reads must never be assumed successful merely
because the person synced labels.

**F2, fix now:** the scaffold exception is decided (`design.md:47`).
`kit/templates/checks.yml:24-27` refuses the generated empty test command during
founding/scaffolding. P27 changes the policy by hand after the scaffold merge.
The hosted rule needs a narrow verified bootstrap exception and must retain
ordinary empty-policy refusal. F1 cannot fix that hosted check.

## Explicit later work

L1 to L10 are unbuilt release work, not completed core features. The core
refusals for metric/reference judges and fuller research refresh are recorded
interim rules. Do not call them accidental omissions.

| Piece | Work still required for v1 |
| --- | --- |
| L1 | App/key setup, queue sync, unattended permission, launchd KeepAlive, heartbeat watch, recipe network hosts, Dependabot and pinned Actions. Validate credential and sandbox boundaries. |
| L2 | Adapt recipes/hosts; health check, automatic rollback, revert pull request, bug issue, pinned-production notice and preview evidence. |
| L3 | Six deduplicated notifications, GitHub mentions, quiet hours and held-message collapse. |
| L4 | What-now views and the live dependency board, including state/waiting changes. |
| L5 | Maintenance, mutation checks, rates, stale branches listed, kit updates and update-time path/state migration. |
| L6 | Evidence-backed learning, checks first, next-run application and stale lesson removal. |
| L7 | Measurement judges, hidden twins and fixed hypotheses, including open-route pieces. |
| L8 | Reference judging in both orders and the agreed advisory outside critic. |
| L9 | Research/design crews, disagreements and fuller claim refresh. |
| L10 | Well-defined trim checks, researched and tested. |

The maintainer's skills-hardening pass and real scenario/no-plugin evals belong
before release. The private test repository and test App for the real smoke are
the maintainer's preparation. GitHub checks, release, public visibility and
private vulnerability reporting remain maintainer decisions/actions.

## Every overnight later item

The index follows the original 58-entry `later` list. A combined item is still
open if a material subitem remains. “Done” means source and inspected coverage
resolve the recorded note, not that R1 independently ran every cited test.

| Item | Original concern | Status and evidence |
| --- | --- | --- |
| 1 | Runner-table check; old workflow repository name | **Done.** `tests/unit/test_judge.py:140-152` compares the table and runners; `.github/workflows/v1-checks.yml:15` names this repository. The second audit missed the existing table assertion. |
| 2 | Untested bootstrap/place helpers and old paths | **Done.** `BORROWED.md:85-86` records their retirement; `kit/scripts/setup.py` replaces founding with installed templates and preservation checks. |
| 3 | Lost scratch exclusion and picture survival assertions | **Done.** Both are restored at `tests/kit-owns-worktrees-rehearsal.sh:184-194,426-448`; BORROWED records the adaptation. |
| 4 | SessionStart wiring and non-overwriting installation | **Done.** `tests/setup-first-half.sh:175-184` checks rendered wiring; existing-project preservation tests cover placement. Retired bootstrap is not required. |
| 5 | Empty recipe menu; missing after-commit credit | **Done.** `tests/recipes.sh:267-272` refuses an empty menu; `BORROWED.md:63,117` includes the after-commit fixture and its liabilities. |
| 6 | Contract markers on every later callable script | **Still open, fix now.** Most new entry scripts have markers, but marker discovery cannot establish completeness and skill-called module doors remain outside it, CR-04. Internal library modules are not agent-facing commands. |
| 7 | Idempotence with real arguments | **Still open, fix now.** `tests/lib/contract_check.py:111-145` repeats no-argument errors; individual gate/handoff/settings tests do not cover every valid door, CR-04. |
| 8 | Real plugin-cache layout | **Still open, fix now.** `loop/paths.py:52` retains the guessed fallback; `test_paths.py:102-105` asserts the guess. Resolved-root settings and a real installation check are still required, CR-02. |
| 9 | Done-when authority; obsolete hosting request | **Still open, fix later.** Root AGENTS now gives the checkable shape. `stack-research/SKILL.md:66-71,127-129` still treats the old hosting-request fields as current despite its earlier disclaimer. |
| 10 | Raw spec block and shared writer | **Done.** `loop/spec.py:478,610-690` preserves the block and provides writers used by gate/ready. |
| 11 | Every file-form unittest command failed | **No longer relevant as a blanket claim.** The P1 to P9 reviewer ran the exact spec-file form successfully, 40 tests. `tests/unit.sh` uses discovery. This is environment-specific evidence, not a guarantee of every file form on every machine. |
| 12 | Common hook bypass rules; create asks; both log events; merge ask | **Done for the named common forms.** Settings deny no-verify/hook-path/aliases; `guard.py:902-905` asks for create/edit; hooks wire success/failure events. Literal merge is now refused by both layers, stronger than the old ask. Exotic forms remain items 16 and 58. |
| 13 | Workspaces, empty parsing, private registry and exit 3/4 | **Still open, fix now.** Parser/provenance gaps remain, CR-06. `loop/gates/attempt.py:642-668` handles refusal/environment results without accepting them. Private registries can wait only behind an explicit refusal. |
| 14 | Loose no-as-example and EC-1 wording | **Still open, fix now.** `loop/lint.py:103,250` keeps the loose rule; align the design example when tightening it, CR-12. |
| 15 | Lists/blockers into needs; default feature type | **Still open, fix now for needs.** Ready passes unresolved dependencies and separately compares lists, but does not project list differences into needs (`ready.py:603-650`). Missing type still defaults to feature at `:182-188`; explicit type policy can be decided later. |
| 16 | Minimum version, tokens, absolute paths, duplicate hooks, exotic Git config | **Still open, fix now.** `pre-run-check.py:72,234-267` checks the minimum version; sessions scrub credentials/render absolute paths; command-log claims deduplicate shared events. Exotic configuration remains CR-03. Real double-hook behaviour still needs live validation. |
| 17 | Keyed evidence and unknown-runner/no-ID failures | **Done for the recorded gap.** Moves reads through `loop.evidence`; `ready.py:403-406` refuses unknown-runner/no-ID assertion evidence. Mixed failures and empty successful reports remain distinct CR-08 findings. |
| 18 | Broad .env exclusion in rule test | **Still open, fix later.** `tests/push-to-main-rules.sh:248` excludes any rule containing .env, wider than the intended exemption. Tighten that mutation coverage. |
| 19 | Second merge guard layer | **Done.** `kit/hooks/guard.py:884-885` refuses literal merge alongside settings denial. Indirect forms remain item 58. |
| 20 | Copier omitted loop package | **No longer relevant.** Bootstrap is retired; founded projects invoke the installed kit and adjacent package (`BORROWED.md:85-86`). |
| 21 | Wrong labels next command | **Done.** `kit/hooks/guard.py:914-915` now gives labels --create. |
| 22 | Adopt a human label change as truth | **Still open, fix later.** `loop/moves.py:416-445` preserves/reports mismatch but asks restoration, and `test_moves.py:762` asserts refusal. No adoption route exists. The design marks human precedence Proposed; obtain the maintainer's intended reconciliation rule. |
| 23 | Run flags, caffeinate and installer version record | **Done for those steps.** `run.py:149-152,237-245` passes flags and starts awake before checking; `setup.py:349-365` invokes write_record. The record's unsuitable home is item 44. |
| 24 | Unbounded command-log claims | **Still open, fix later.** `command-log.py:142-158` leaves per-event files; run close has no named-file retention cleanup. Releasing the run lock is unrelated. |
| 25 | Missing pytest counted as passed | **Still open, fix now.** Zero-exit skips reach the pass total (`tests/run-all.sh:48-60`), CR-05. Later rehearsals share the pattern. |
| 26 | Duplicate single-file unittest note | **No longer relevant as a blanket claim.** Same observed successful spec-file invocation and portability qualification as item 11. Discovery remains the suite route. |
| 27 | Hosted/copy area-map missing loop | **No longer relevant.** Retired copiers are replaced; hosted checks fetch the full kit and invoke its records checker. Private access remains item 36. |
| 28 | Missing risk notice; dependency/security inferred only from marks | **Still open, fix now.** Risk notice is unchecked, CR-10. Supported dependency changes now get attempt checks, but unsupported changes pass; security classification still relies on declared marks. Review must not call those declarations automatic discovery. |
| 29 | Rebase advice conflicts with no force-push | **Still open, fix now.** `ready.py:356` and `test_ready.py:291` retain the unsafe general recovery advice, CR-13. |
| 30 | Local main may be stale | **Still open, fix now.** Ready/claim have no current-origin proof; merge-time fetch does not repair ready evidence, CR-13. |
| 31 | Ready blocked-by reader with App stand-in/link | **Still open, fix later.** Claim (`tests/claim-gate.sh:170-190`) and integration exercise actual links. Ready units substitute a hub and `tests/ready-gate.sh` lacks the specifically requested ready-reader end-to-end case. Broader link coverage does not close that exact note. |
| 32 | Check true proves nothing | **Still open, fix later.** `loop/spec.py:386-393` accepts non-empty commands; success proves execution only. Shaping/review must judge meaningful preservation until a well-defined check can hold it. |
| 33 | Project-relative skill commands and fixtures | **Still open, fix now.** Setup/run actions partly use plugin root; shape and run injection/fallback remain relative. Lint/fixtures accept them, CR-01. |
| 34 | Confirm refusing duplicate comment on uncaptured issue | **Still open, fix later.** The P18 plan records safe refusal rather than implicit capture/label writes; the helper follows it. That implementation choice does not establish the requested maintainer confirmation. |
| 35 | Word overlap misses paraphrases | **Still open, fix later.** Shape duplicate helper retains the 0.6 threshold. Person confirmation limits false positives but does not recover missed paraphrases. No decided semantic-match guarantee is claimed. |
| 36 | Private kit checkout; founding placeholders | **Still open, fix before release.** `setup.py:372-379` renders the placeholders. `kit/templates/checks.yml:11-15` still uses the default project token for the separate private kit checkout. Decide distribution/access without giving builders broader credentials. |
| 37 | Hosted checks omit closing-piece argument | **Still open, fix later.** `loop/run/docs_commit.py:346` supplies closing pieces to the local final records check. Hosted checks still omit it, so hosted-only coverage does not enforce those entries. The local closing gate is present. |
| 38 | Sensitivity compared by name only | **Still open, fix now.** `loop/records.py:27-28` explicitly omits flags from the map, contrary to the decided model, CR-14. |
| 39 | Rebased judge SHA and anti-circle recovery | **Still open, fix now.** Claim compares commit identity (`claim.py:249-298`); unchanged content can kick back and repeat. Today-main overlays alone do not settle recovery, CR-13. |
| 40 | HTTP(S) page versus package source rule implicit | **Still open, fix later.** `kit/spec-format.md:193-201` does not state the classification rule as explicitly as `loop/gates/research.py` applies it. Clarify the one format. |
| 41 | Incompatible design research example | **Still open, fix later.** `design.md:800-803` retains the old help-page/package-version shape; fixtures/parser reject it (`test_needs.py:215-219`). Correct the maintainer's example rather than weakening the parser. |
| 42 | Invalid Checked-date fallback; lint import ignores | **Still open, fix later.** `loop/spec.py:728-738` falls back to another valid date after invalid Checked; `tests/lint.sh:178` and test_claim import ignores retain the lint cleanup. Choose explicit invalid-date refusal. |
| 43 | Absolute paths stale after plugin update | **Still open, fix later in L5.** Setup renders installed paths once and preserves existing files; there is no update-time migration. Current protection needs CR-02 before release. |
| 44 | Version state in movable plugin folder | **Still open, fix before release.** `setup.py:349-365` writes version.json into the plugin root and pre-run reads it there. Choose stable state placement and migrate it with L5. |
| 45 | No plugin release version; hosted follows main | **Still open, maintainer release step.** Manifest has no version; `setup.py:184-192` falls back to main. Select the immutable release/ref when preparing release. |
| 46 | Local empty-project pre-run deadlock | **Done for the generated empty policy.** `pre-run-check.py:911,961` and `tests/pre-run-check.sh:355-391` implement the scaffold-only exception. F2 hosted refusal and CR-20's proposed-command variant remain separate. |
| 47 | Existing-runner project gets scaffold | **Still open, fix now.** `setup.py:525-573` omits project_has_runner during first-piece capture, CR-20. |
| 48 | Guessed plugin-cache deny misses actual root | **Still open, fix now.** Early edit deny retains the guess; resolved builder sandbox is a separate useful layer, CR-02. |
| 49 | Early stop, L7 metrics, real-gate attempt-limit rehearsal | **Still open.** Engine early-stop routing exists; metric/hypothesis work is deliberately L7. Unit exhaustion coverage does not supply the requested real-gate attempt-limit end-to-end case; add it before release. |
| 50 | Bar paths, hidden markers, unknown languages, new area, main-merge brief | **Still open, fix now.** Engine supplies bar paths but session API permits omission, CR-04/CR-06; hidden validation is late, CR-11; unknown-language lint skips, CR-07. Spec/docs support declared new areas, but the person-owned area-map decision needs an explicit route. `kit/briefs/builder.md` still lacks the explicit main-merge instruction and refers to a Done-when field absent from the shared spec. |
| 51 | Frozen bar needs controlled source/bar assembly | **Still open, harden before release.** `loop/bar.py` recognises known configuration files; there is no allowed-source judge assembly. Treat this as architectural hardening after closing known routes, not a proven property or a demand to solve arbitrary code with text parsing. |
| 52 | Aggregate net trim permits per-file growth | **No longer relevant as an omitted rule.** `loop/trim.py:208` sums net lines; this is a reasonable fold interpretation. The design does not require each file to shrink. Stacked skipping remains CR-19. |
| 53 | Conservative unknown build cost; missing caller mutation | **Still open, fix now for coverage.** Safe-direction fallback remains intentional. Direct spend tests do not prove the caller retains its budget argument; add that regression with CR-16. |
| 54 | Caffeinate after pre-run | **Done.** `kit/scripts/run.py:237-245` now starts the awake wrapper first. Mac-specific checks are conditional in the watch/mailbox tests. |
| 55 | Integration leave, multiple dependencies, stacked trim | **Still open, fix now for trim.** `loop/run/review.py:780,809` calls leave during rejection. Multiple-dependency stacking lacks the requested case; stacked trim is explicitly skipped, CR-19. |
| 56 | Unreadable reviewer cost counted zero | **Still open, fix now.** `loop/run/review.py:604-607` still omits it, CR-16. |
| 57 | In-process proof forgery by arbitrary script | **Still open, L1 security validation.** Text guards cannot authenticate arbitrary imported code. Sandbox and inaccessible App credentials must hold the stronger boundary. No exploit or real credential-isolation check ran in R1. |
| 58 | Indirect gh and file-fed GraphQL | **Still open, fix now.** The parser probes reproduced the cited forms without executing them, CR-03. |

## What the speed-ups left

| Original deferred item | R1 disposition |
| --- | --- |
| 1. No separate core readiness review | **Done as a review.** All 27 pieces have fresh design/decision coverage above. Findings need shaped repair pieces; review does not close them. |
| 2. No removal readiness review | **Done for tracked file inventory; external housekeeping still open.** Root keep/adapt/archive paths agree with the removal inventory. Old adapters, root plugin, migration tooling/docs, WORKFLOW, GEMINI and release scripts are absent; maintainer skills, credits, guards and archived design inputs remain. Remote branches/settings need maintainer evidence. |
| 3. Parallel removal and bootstrap | **Reviewed, with known later adaptation.** Searches find old names in document exclusion/fixture inputs and fake-host recipe fixtures, not active bootstrap calls into deleted tools. BORROWED explicitly lists recipe/prepare leftovers. Baseline suite evidence is separate from this path audit. |
| 4. Short briefs | **Done as conformance review.** Reviewers read the relevant whole design and decisions; CR findings expose requirements missed or narrowed by brief/plan. |
| 5. Parallel interface assumptions | **Partly done.** P27 exercises the whole stand-in route; F1/F2 remain open baseline faults. Real smoke and missing targeted cases in items 31, 49 and 55 still need evidence. |
| 6. No GitHub checks | **Still open, maintainer decision.** Choose hosted workflows and cost before release; local green checks are not that decision. |
| 7. Refused housekeeping | **Still open for maintainer evidence.** Branch cleanup elsewhere and paused local allow rules were not changed by R1. Preserve unsaved work and leave settings to the maintainer. |
| 8. Automatic handover and host restart survival | **Still open.** Record-based run resume is implemented. launchd KeepAlive/watch belong to L1; automatic coordinator handover before context exhaustion has no implemented core path or shaped plan entry. |

This inventory checks repository paths, not remote settings or the maintainer's
other repository. Retained old names in borrowed recipe fixtures are declared
adaptation work. They do not by themselves prove a runtime dependency on a
removed implementation. The real App smoke, model scenario evals and hosted
bootstrap checks remain distinct evidence to obtain before release.
