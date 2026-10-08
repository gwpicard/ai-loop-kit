# Plan to v1.0

The bootstrap core is merged. It needs the repairs in [core-review.md](core-review.md)
and the later capabilities below before v1.0 is ready to release. This plan
orders that work; it does not authorise a release, real credentials or a change
to the maintainer's settings.

The baseline includes the merged R1 review and F1 manual-completion repair.
F1's after-checks passed on merged main: both core rehearsal cases, 1,757 unit
tests, lint and house rules. F2's hosted empty-policy repair is authorised and
pending. It must merge and pass its after-checks before the release gate.
R1 describes the earlier baseline, so its F1 finding remains useful history.

The [decisions](decisions-2026-10-05.md) win where sources disagree, followed by
the [design](design.md) and [build plan](build-plan.md). Later decided revisions
within those files replace earlier answers. The plan retains the current
refusals for measurement, reference and open-route pieces until L7 and L8 land,
and the stricter research-refresh kickback until L9 lands.

## How to use this plan

Each identifier below names a proposed piece, not a GitHub issue number.
Before building, shape it as an issue with a checkable `## Done when` section,
fresh context against main, declared touches and a frozen judge seen failing
for the right reason. Sizes S, M and L are planning estimates, not time limits.
Split an L entry during shaping if it cannot be built and reviewed alone.

The files below are proposed touches. New paths are named explicitly; existing
paths must be rechecked against main at shaping. No listed path grants an agent
permission to change protected settings or workflows. Such a piece needs the
maintainer's allowed implementation route and independent validation first.

Every important rule needs two independent holders. New scripts follow the
agent contract; every new skill gets normal, edge and refusal eval cases before
its text. A skill carries judgement and conversation and points to its holders.
Run required checks without counting skips as passes, then a fresh review with
at most two rounds. The maintainer decides each merge. Keep unsaved work and
all failure evidence; a refused command parks the affected step, without a
workaround.

## Order and parallel work

1. Complete F2 and its after-checks. CR-20 is a separate local runner repair,
   so F2 alone does not close it.
2. Repair the safety and evidence boundaries: CR-02, CR-03, CR-05, CR-06,
   CR-07, CR-08, CR-09, CR-11, CR-17 and CR-21. Then finish the remaining
   core repair pieces with their dependencies below. All CR pieces block a
   claim that the core conforms.
3. Build L1 to L10 in dependency order. Close the extra release pieces Q1 to
   Q6 and the skills pass H1. Resolve the maintainer's open choices below.
4. Run the release rehearsal V1 and the authorised real validation V2.
   Repair or explicitly amend any remaining decided requirement before the
   maintainer makes the release decision.

Parallel work requires both satisfied dependencies and disjoint files. These
are conservative starting groups, not permission to edit a shared module:

| Group | Pieces that can run together | Serial work within the group |
| --- | --- | --- |
| A | CR-03, CR-05, CR-09, CR-17, CR-21 | Each has distinct hook, harness, fingerprint, lock or scanner files. |
| B | CR-01, CR-02, CR-06, CR-07, CR-08 | CR-06, CR-07 and CR-08 share attempt code or tests, so run them serially in that order. CR-02 needs a settings permission route. |
| C | CR-10, CR-14, CR-16, CR-20 | CR-10 and CR-20 both touch ready; finish CR-10 first. CR-14 and CR-16 use separate records and spend code. |
| D | CR-04, CR-11, CR-12, CR-13, CR-15, CR-18, CR-19, CR-22 | Ready repairs CR-11 to CR-13 are serial. CR-19 follows CR-15 and CR-18 and shares their engine/integration tests. Run CR-04 last because its inventory spans command doors. CR-22 follows CR-02 and CR-16. |
| E | L7, L4, Q1 | L7 and L4 can start together after their CR dependencies. Q1 is test-only and must avoid their new rehearsals. |
| F | L1, L10, Q2 | L1 needs security repairs; L10 follows CR-07 and CR-19. Q2 is docs-only. |
| G | L2, L9, L6 | L2 follows L1. L9 and L6 can run together only if their needs/spec and lesson edits remain separate. |
| H | L3, L8, Q3 | L3 follows L1/L2; L8 follows L7 and reviewer repairs. Q3 follows the safety repairs. |
| I | L5, Q4, Q5 | Finish L6 before L5's lesson drift work. Q4/Q5 must not share setup or records files with L5. |
| J | H1, Q6, V1, V2 | H1 follows all skills. Q6 may run beside H1. V1 follows both; V2 follows V1 and maintainer preparation. |

Groups describe scheduling waves. A dependency in a piece's entry always wins
over a group. When a planned file overlaps another piece, serialize or split
the pieces rather than resolving cross-piece conflicts. Update this table
after shaping determines the actual file sets.

## Core repairs

Each CR identifier maps one to one to the finding of the same name in
[core-review.md](core-review.md#findings-to-shape). The test is the regression
to write first, then the condition to prove after the repair. All are **fix now**.
Paths beginning `loop/` below are under `kit/scripts/`; unit tests are under
`tests/unit/`.

| Piece and goal | Test | Proposed files | Dependencies | Size |
| --- | --- | --- | --- | --- |
| CR-01. Hold skill rules and installed commands mechanically. | Mutate paragraph hard rules, false holders and current labels; lint refuses each. Count estimated tokens without inventing a cap. Run shape and run injection/fallback from a founded project with no local kit folder. Prove the source-editing boundary outside frontmatter. Model scenario evidence belongs to H1. | Change `kit/scripts/check-skills.py`, `kit/skills/shape/`, `kit/skills/run/`, `tests/check-skills.sh`, `tests/run-skill.sh` and their fixtures. | None; H1 finishes live evals. | L |
| CR-02. Protect the actual installed guard root in attended and builder sessions. | A marketplace/version installation renders both independent write protections to the resolved root. Removing either protection is detected; real enforcement is tested in V2. | Change `kit/templates/claude-settings.json`, `kit/templates/builder-settings.json`, `kit/scripts/setup.py`, session renderer and `tests/settings.sh`. Protected changes need maintainer permission. | None; before L1 and L5 updates. | M |
| CR-03. Refuse opaque protected command forms. | In-memory parser tests refuse or ask for unresolved executable variables, file-fed GraphQL and exotic Git configuration; ordinary allowed reads still work. Never execute destructive probes. | Change `kit/hooks/guard.py`, `test_guard.py`, guard rehearsal fixtures. | None; L1/V2 cover arbitrary imported code through credential/sandbox holders. | M |
| CR-04. Check every callable agent door with valid operations. | An inventory includes skill-called modules such as heldout. Valid repeated and dry-run operations leave the expected state; invalid choices produce JSON errors with next commands rather than tracebacks. Name hook-protocol exceptions. | Change `loop/cli.py`, `tests/lib/contract_check.py`, `tests/script-contracts.sh`, callable markers and fixtures. | CR-01; repeat inventory after L1 to L10. | L |
| CR-05. Separate pass, skip and failure. | Remove a required tool in a fixture: the aggregate cannot report complete green. An optional validator skip remains visible and outside the pass total. | Change `tests/run-all.sh` and skip-producing required rehearsals, including ready, judge, trim and review scripts. | None. | S |
| CR-06. Refuse unchecked dependencies and preserve planned edits. | Workspace and supported inline lock entries parse accurately; a non-empty unparsed lock, unsupported manifest or lost source identity refuses. A caller regression fails if dependency-planned is omitted from bar paths. Test private sources as refusal until supported. | Change `kit/scripts/dependency-check.py`, `loop/bar.py`, `loop/gates/attempt.py`, `loop/run/engine.py`, dependency/attempt/engine tests. | CR-03; before CR-07 and CR-19. | L |
| CR-07. Report unchecked new tests honestly. | Unknown-language and unreadable changed tests cannot silently pass. Supported Python/TypeScript mutations still fail; an explicit unsupported-language review route reports its limits. | Change `kit/scripts/newtest-lint.py`, `loop/newtest_lint.py`, `loop/gates/attempt.py`, test-smell fixtures and tests. | CR-06. | M |
| CR-08. Require complete judge execution evidence. | A named assertion cannot mask an unnamed one. Missing reports, zero execution and skipped acceptance cases cannot count as passed judges. Generic exit-code checks are separately identified. | Change `loop/judge.py`, `loop/gates/ready.py`, attempt evidence handling, judge/ready/attempt tests and runner fixtures. | CR-05; before CR-11 and L7. | M |
| CR-09. Preserve semantic whitespace in the frozen spec. | Changing fenced Python indentation changes the fingerprint. Only explicit gate-owned fields are excluded; harmless formatting cases remain documented. | Change `loop/fingerprint.py`, `test_fingerprint.py`, spec fixtures. | None; before CR-13. | S |
| CR-10. Require notice and exact risk acceptance. | A quotation/date without the risk notice is a need and refuses ready. An invalid calendar date refuses; the person's exact words survive gate updates. Syntax is never described as authenticating consent. | Change `loop/spec.py`, `loop/needs.py`, `loop/gates/ready.py`, `kit/spec-format.md`, sensitive fixtures and tests. | CR-09; before CR-12 and CR-20. | M |
| CR-11. Validate executable hidden cases at ready. | Descriptive text, unsafe paths and missing command substitution refuse before ready. Executable hidden files run through the real gate and stay unreadable to builders. | Change `loop/heldout.py`, `loop/gates/ready.py`, `loop/gates/attempt.py`, `tests/ready-gate.sh` and hidden fixtures. | CR-08; after CR-10. | M |
| CR-12. Show list disagreements as needs and require concrete examples. | Differing spec-ID lists appear in computed needs and clear after agreement. The word no alone cannot stand in for example data; use a corrected empty-state example. | Change `loop/needs.py`, `loop/lint.py`, `loop/gates/ready.py`, spec fixtures and the design example through a reviewed docs change. | CR-10, CR-11. | M |
| CR-13. Establish current main and safe judge recovery. | Advance origin while local main is stale: ready/claim use a recorded fetched baseline. A content-preserving rewritten judge is diagnosed without accepting changed authority or requiring force-push. Recovery is gate-owned, recorded and legitimately re-fingerprinted; repeat kickbacks do not trap it. | Change ready/claim gates, fingerprint/evidence helpers, `kit/spec-format.md`, ready/claim tests. | CR-09, CR-12. | L |
| CR-14. Enforce the decided records model. | Mutations in sensitivity flags, optional area-rule paths and copied enforcement prose fail. Changed/Removed behaviour replaces or refuses ambiguous current text; decisions retain reasons and real piece links. New-area map changes have a person-owned route. | Change `loop/records.py`, `loop/run/docs_commit.py`, area/overview templates, records/document rehearsals. | CR-10; before CR-18 and L5. | L |
| CR-15. Put parked questions and decisions on the piece. | A park keeps its state but writes the question and needs-you; clear/resume removes the need. Before App, person sync delivers queued writes. Decisions made alone survive as marked spec decisions. | Change gate-owned park/decision doors, `loop/run/engine.py`, inbox/answer handling, run/watch rehearsals. New tests for visible piece records. | CR-10, CR-12, CR-17. | M |
| CR-16. Account for reviewer spend and reserve shared budgets. | Unreadable reviewer cost uses a conservative bound. Concurrent workers cannot reserve the same remaining cap. A caller mutation dropping the budget argument fails. Waiting for the person is visible. | Change `loop/run/engine.py`, `loop/run/review.py`, shared budget records and engine/review tests. | CR-17; before CR-22 and L8. | L |
| CR-17. Acquire one atomic project lock. | Two processes with different run names race: exactly one starts. A crash/restart recovers the recorded owner safely without admitting two runs. | Change `loop/paths.py`, `loop/run/record.py`, `kit/scripts/run.py`, lock/unit/run rehearsals. | None; before L1. | M |
| CR-18. Run complete checks on trial and final trees. | Hidden cross-piece conflict fails at the trial; the combined branch stays unchanged. An unrelated project regression fails final checks after docs/changelog even when every selected judge passes. Run any existing validator on that exact tree. | Change `loop/run/integrate.py`, integration/final-check tests and fixtures. | CR-08, CR-11, CR-14. | M |
| CR-19. Trim stacked pieces with a trustworthy base. | A dependent's trim runs and can only remove/fold its added code; test edits or a failed re-run discard the scratch trim without moving the piece branch. Exercise multiple dependency bases. | Change `loop/run/engine.py`, `loop/trim.py`, trim/engine/integration tests. | CR-06, CR-15, CR-18. | M |
| CR-20. Distinguish an existing runner from a proposed command. | Existing-runner setup creates no needless scaffold. An empty project with a future test command can build only its verified scaffold; normal runner checks remain required afterwards. | Change `kit/scripts/setup.py`, pre-run and ready gates, setup/pre-run rehearsals. | F2, CR-10; serialize with ready repairs. | M |
| CR-21. Scan known secret shapes in commit messages. | Safe synthetic secret shapes in messages refuse both scan points without printing values; clean messages pass without gitleaks. Keep limits for ambiguous or split values explicit. | Change `kit/scripts/secret-scan.py`, `test_secret_scan.py`, secret-scan rehearsal. | None. | S |
| CR-22. Permit exactly the reviewer's new findings output. | With the prior output moved aside, the reviewer can create its one new findings file and cannot write unrelated files. Stand-ins prove rendering; V2 proves real dontAsk enforcement. | Change `kit/templates/reviewer-settings.json`, session/review renderer, review/settings tests. Protected changes need maintainer permission. | CR-02, CR-16. | M |

The holders remain the gate's validated evidence and independent hook/settings
or sandbox layers where relevant. CR-03's parser is not a proof of arbitrary
code isolation. CR-08's report checks are not a proof that every runner is
supported. Each piece must state those limits in its shaped issue.

## Later capabilities for v1.0

These are required release work. They are not completed core features. Each
entry follows the build plan's goal, test, files, dependencies and size shape.

### L1. Make it safe to walk away

**Goal.** The person can create and install the repository-scoped gate App and
leave a guarded run running outside the host app.

**Test.** In a throwaway project, create a stand-in App credential, verify the
key is outside the project with mode 600, sync the pre-App queue exactly once
and preserve/report a differing label. Allow unattended runs only after setup.
Kill the run process and close/restart the host app: launchd KeepAlive resumes
from the record without repeating a finished join or losing workers. The watch
only checks heartbeat freshness and emits one event. Test recipe host allowlists,
credential scrubbing and denied access to the person's login, gate key and
held-out store. Real enforcement belongs to V2, with authorised credentials.

**Files.** Change setup/pre-run/session/queue/watch modules and setup skill
references. Adapt `kit/templates/github-app.json` and its App reference. New
`kit/templates/launchd/`, `tests/setup-walk-away.sh` and related unit fixtures.
Add project Dependabot and pinned Action templates through an authorised route.

**Dependencies.** F2, CR-02, CR-03, CR-15, CR-17, CR-22. Coordinate L3's event
format, but L1 can use a stand-in event sink before L3's sender exists.
**Size.** L; split App/queue and supervision into serial subpieces if needed.
**Held by.** App scopes and inaccessible credentials, settings plus sandbox,
pre-run refusal, project lock and launchd. Permission/key installation is the
person's action, never a broader builder token.

### L2. Deployment, health and rollback

**Goal.** The person can add or change deployment through either recipe, with
health checking and recovery after a main deploy even while the laptop is off.

**Test.** Drive both host stand-ins through setup/reconfiguration without
overwriting user files. A healthy deploy produces preview evidence; a broken
deploy rolls back to the last good version and creates one revert pull request,
one shaping bug and one production-pinned event. A first deployment runs its
checks once. Real host/account changes require a separate named approval.

**Files.** Adapt `kit/recipes/`, `kit/templates/recipe-format.md`, recipe parts
and host/prepare fixtures. New deploy-health/rollback scripts and pinned project
Action template, `tests/deploy-health.sh`, rollback unit tests. Change setup and
evidence integration to record previews.

**Dependencies.** L1, CR-14, CR-18; send events to the L3-compatible sink.
**Size.** L; shape one recipe adaptation at a time.
**Held by.** Health Action and host rollback API, gate-owned issue/PR writes,
recipe allowlist and explicit person permission for service changes.

### L3. Six non-blocking notifications

**Goal.** The gate App mentions the person once for each decided event, while
quiet-hour messages collapse and input remains issue/PR comments.

**Test.** Replay run finished, real stop, PR ready, live/pinned, long person
wait and stale heartbeat twice: each posts once. Quiet-hour held events collapse
into one message using GitHub Mobile working hours; a posting failure never
blocks independent work. Test the agreed way of obtaining those working hours
before claiming automatic support. Email is GitHub's fallback, not a second
agent-owned notification channel.

**Files.** New `loop/notifications.py`, notification references/fixtures,
`tests/notifications.sh`, unit tests. Change event hooks in run/watch/deploy
modules without giving workers App credentials.

**Dependencies.** L1, L2, CR-15. **Size.** M.
**Held by.** Gate-App identity, durable event keys and retry queue. If the
working-hours integration is unavailable, park that gap for the maintainer;
do not silently replace the decided source with an invented setting.

### L4. What-now and the live dependency board

**Goal.** One report shows where work is, what needs the person, progress and
decisions made alone, and drives the live dependency graph.

**Test.** A plan gains/loses pieces and changes dependencies: redraw with no
stale nodes. Show state and each waiting next line from the gate/run record.
Prove the design's ordering and cap of three proposals. Eval normal, edge and
refusal cases before the skill; test report injection and fallback from an
installed kit root.

**Files.** New `kit/skills/what-now/`, board renderer and `tests/what-now.sh`;
change gate report output only if its existing fields cannot feed the views.

**Dependencies.** CR-01, CR-04, CR-15. **Size.** M.
**Held by.** Gate report as the state source, report schema and deterministic
graph rendering. The board never moves states itself.

### L5. Maintenance and safe kit updates

**Goal.** Maintenance finds record/code drift, code and delivery decay, stale
branches and kit updates, with findings entering shaping.

**Test.** Plant drift, a mutation-surviving test and a delivery-rate fixture:
each yields an evidenced shaping finding, never a score gate. List stale
branches without deleting them. Update a simulated installed marketplace/version
root: re-render allowed paths, keep local state in a stable home and preserve
user files. Apply no protected settings change without the person's route.
Show the two-week suggestion and logged small tidying.

**Files.** New `kit/skills/maintain/`, maintenance/mutation/update modules and
`tests/maintain.sh`. Change records/setup/pre-run version handling and the
template path migration. Update adapted BORROWED rows when applicable.

**Dependencies.** CR-02, CR-14, L1, L6, Q4. **Size.** L.
**Held by.** Records checks, evidence-backed issue capture, named update
migrations and person-owned settings. Old branches are listed, never swept.

### L6. Evidence-backed learning

**Goal.** Repeated evidence becomes check-first lessons that take effect only
at the next run and can be offered for removal when stale.

**Test.** One sighting does not create a lesson; two matching sightings create
a candidate with evidence. A lesson proposed during a run does not change its
bar. The next run applies each accepted lesson as its own visible commit after
pre-run checks. Stale lessons are offered to the person without deleting work.
Use a reasoned AGENTS line only when a check cannot hold the lesson.

**Files.** New `loop/learning.py`, lesson/candidate store, `tests/learning.sh`
and unit fixtures. Change run-end/kickback collection and next-run preparation.

**Dependencies.** CR-09, CR-15, CR-17. **Size.** M.
**Held by.** Recorded evidence thresholds, next-run application gate and frozen
bar checks; automatic model memory remains disabled in run sessions.

### L7. Measurement judges and fixed hypotheses

**Goal.** Metric and open-route pieces can become ready with a target, hidden
twin and hypothesis list fixed before any attempt.

**Test.** A metric piece goes from shaping to done through real gates using
stand-ins. An off-list or goal-opposing hypothesis refuses; a gate-recorded
goal-directed addition retains its reason. A visible target win with a much
worse hidden result counts as gaming. Only then remove the core refusals.

**Files.** New measurement/hypothesis modules, `tests/measurement-judge.sh`
and fixtures; change spec/needs/ready/attempt/bar handling and shape references.

**Dependencies.** CR-08, CR-09, CR-11, CR-13, CR-18. **Size.** L.
**Held by.** Fingerprinted hypotheses and target, gate-run visible/hidden
measurements, denied held-out access and gate-recorded additions.

### L8. Fresh critic and advisory outside critic

**Goal.** Reference pieces get a fresh critic, and the person may choose a
different vendor with explicit agreement that content goes there.

**Test.** Anonymous A/B in both orders yields a win only with agreement; a tie
or split refuses. Vendor absent or consent missing leaves the Claude route or
parks, never silently sends content. Advisory review cannot kick back without
a reproducing check. Only remove reference-ready refusal once the gate works.

**Files.** New critic/advisory modules, `tests/reference-judge.sh`, critic
fixtures and evals; change judge/ready/review/policy handling and skill references.

**Dependencies.** L7, CR-16, CR-22. **Size.** L.
**Held by.** Gate's critic result contract, both-order comparison, recorded
provider choice/consent and reproduced checks for advisory findings.

### L9. Crews and fuller research refresh

**Goal.** Research/design needs can use bounded crews; claims refresh stale
findings without needless shaping when the confirmed answer leaves the spec.

**Test.** A research need launches distinct source readers; disagreement
becomes a visible need until a further check or the person settles it. Design
variants remain a person choice. Resource limits match builder limits. At
claim, changed fingerprints, versions, age or a contrary quick check trigger
refresh; a confirmed unchanged answer updates the finding through the gate,
while an unconfirmed/spec-changing answer kicks back. Remove the interim rule
only after these routes pass. Treat outside text as data.

**Files.** New crew/refresh helpers and `tests/shaping-crews.sh`; change shape
references, research/claim/needs handlers, evidence and research fixtures.

**Dependencies.** CR-09, CR-12, CR-13, CR-15, Q2. **Size.** L.
**Held by.** Resource slots, dated/source-based evidence, gate-owned writes
and legitimately renewed fingerprints. No crew settles a person-only need.

### L10. Well-defined trim checks

**Goal.** The trim and reviewer distinguish mechanically detectable test/code
smells from warnings and judgement, using the design's checks table.

**Test.** Research the named primary tests guide at shaping, record its source
and date, and mutate each adopted deterministic rule. Tautology/side-channel
limitations appear as notes; mutation tools run only when already present and
never gate on a score. Trim remains remove/fold only, never touching tests.

**Files.** Change trim/new-test check modules and reviewer brief; new check
fixtures and trim tests. Keep sources in docs/SOURCES.md and adapted credits.

**Dependencies.** CR-07, CR-19; coordinate mutation plumbing with L5.
**Size.** M. **Held by.** Deterministic checks and frozen bar for reliable
rules; reviewer findings for partial/no-script rules. A warning is not a pass
or a new must-look reason.

## Remaining release pieces

These close the R1 fix-later work which is not fully owned by L1 to L10.
Their tests and exact files must be refined during shaping.

| Piece | Goal and checkable test | Proposed files | Dependencies | Size |
| --- | --- | --- | --- | --- |
| Q1. Close missing real-gate rehearsals. | Prove ready blocked-by with the App stand-in and a real link, attempt exhaustion and no-improvement routing, plus multiple-dependency stacking. Each tests the actual gate rather than replacing it with a hub. | `tests/ready-gate.sh`, run/attempt/integration rehearsals and fixtures. | CR-08, CR-13, CR-19, L7 for metric early-stop. | M |
| Q2. Align the authoritative format and examples. | Make page/package classification explicit, refuse invalid Checked dates rather than fallback, align design/format examples, correct the stale hosting-request maintainer skill and builder's absent Done-when/main-merge instructions. Fixtures follow the single parser. | `kit/spec-format.md`, `loop/spec.py`, spec/design examples, `kit/briefs/builder.md`, `.agents/maintainer-skills/stack-research/SKILL.md`; narrow unused lint ignores if proved unnecessary. | CR-04, CR-12, CR-13. | M |
| Q3. Assemble judges from controlled inputs. | A builder's source change cannot replace base bar/test-runner inputs or gain hidden access. Plant known plugin/config bypasses and test an explicit source allowlist in a separate judge checkout. Document supported boundaries rather than promising to parse arbitrary code. | bar/judge/session assembly, `tests/judge-runner.sh`, sandbox fixtures. | CR-02, CR-06, CR-08, CR-11, CR-18. | L |
| Q4. Distribution and reproducible version state. | Choose private/public distribution with the maintainer. A generated check can obtain the kit without builders receiving broader credentials; founding placeholders are filled and the immutable kit ref resolves. Version state survives moving plugin roots. | setup/pre-run/version modules, plugin manifest, hosted template and installation/update fixtures through authorised routes. | F2, CR-02; maintainer distribution choice. | M |
| Q5. Attended hosted pieces and hosted records evidence. | Before App, hosted ready/claim dependency reads either work through a defined person route or park with an exact next line; sync alone is not proof. Hosted records checks receive closing pieces so missing changelog entries refuse. | ready/claim/GitHub read doors, hosted template, records fixtures. | F1, F2, CR-14, Q4; maintainer hosted-checks choice. | M |
| Q6. Automatic coordinator handover. | Before context exhaustion, finish agents in flight, save state and pending needs, then resume in a fresh session without duplicate work or lost unsaved changes. A replay proves this separately from host restart survival in L1. | New coordinator handover/recovery helper, run-summary/state contract, replay fixture and documented person invocation. Exact integration surface is a shaping decision. | CR-15, CR-17, L1, L4. | M |

The remaining R1 later concerns have these owners. Row numbers below refer to
the review's inventory, never issue numbers:

| R1 inventory rows | Owner and release condition |
| --- | --- |
| 6 to 8, 13 to 16, 25, 28 to 30, 33, 38 to 39, 47 to 48, 50, 53, 55 to 56, 58 | Corresponding CR pieces above; row 50's new-area route is CR-14 and builder brief is Q2; row 55's multi-dependency case is Q1. |
| 9, 40 to 42 | Q2; obtain maintainer agreement before changing their design example. |
| 18 | Tighten the broad env exemption in settings mutation coverage with CR-02; no blanket exemption may conceal a removed guard. |
| 22 | Maintainer decides the Proposed human-label precedence/reconciliation route; L1 preserves and reports mismatches until then. |
| 24 | L5 adds bounded command-log claim retention with named-file removal only, preserving active-run and needed evidence. No recursive cleanup. |
| 31, 49, part of 55 | Q1's exact missing rehearsals, including L7 metric cases. |
| 32 | H1 shapes meaningful must-stay checks; `true` only proves execution. A future reliable detector belongs to L10, otherwise review judges meaning. |
| 34 to 35 | Maintainer confirms uncaptured duplicate-comment refusal and semantic-match expectations. H1 tests the supported duplicate route and honestly states word-overlap limits; semantic matching is not a decided guarantee. |
| 36, 44 to 45 | Q4 plus the maintainer's immutable release/version choice. |
| 37 | Q5; local closing evidence does not prove hosted checks enforce it. |
| 43 | L5 installed-path migration after CR-02 closes today's protection gap. |
| 51 | Q3. |
| 57 | L1 credential isolation and V2's authorised real boundary checks. |

Rows recorded done or no longer relevant need no duplicate repair. Preserve
their regression coverage. Items marked Proposed remain choices to shape or
confirm, not new settled rules: memory-pressure back-off, per-builder ports/data,
sample-data walk-through, parent completion, unreachable-GitHub no-change
semantics and the first upload. L1 owns supervision/resource preparation; L5
owns stale-work listing. H1/Q5 shape the attended interaction and read failures.
The maintainer settles any scope left open before the release review; no branch
or worktree removal is automatic, and unsaved work always stays.

## Skills hardening before release

**H1. Goal.** Review every shipped skill against all 17 decided principles
and the prior skills audit, after the command/gate changes settle.

**Test.** Write and preserve normal, edge and refusal scenarios before changing
each skill. Mutations exercise every static lint rule and actual holders;
contracts run valid skill-called commands from the installed root. Run real
scenario evals with graders on tools, order, files and replies, then compare
with a no-plugin baseline. Inspect Gotchas for useful surprises, duplicated
enforcement and false frontmatter guard claims. Keep sizes at 150 lines/2,000
words, descriptions at 300 characters and references at 300 lines. Count
estimated tokens without introducing a new numeric cap. Obtain the person's
authorisation for paid model runs; a written eval is not executed evidence.

**Files.** `kit/skills/`, their `evals/` and references, check-skills mutations,
script contracts and the skills audit record. **Dependencies.** All CR pieces,
L1 to L10 and Q2; Q5 if it changes skill instructions. **Size.** L, split by
skill with a final cross-skill consistency review. **Held by.** Static lint,
contract tests, independently checked holders and scenario graders. Real
validator/eval capability must be verified before choosing the command; record
an unsupported tool as a gap rather than assuming a green run.

## Maintainer choices before validation

**GitHub checks and cost.** Decide whether this kit repository will re-enable
hosted workflows, retain local checks with an enforced post-merge main gate, or
use another explicit checked route. Specify who pays and the required check
set. No checks is never green, including for pre-approved merges. Test the
chosen path on the exact head and prove stale main or missing checks refuses.
The existing manual-dispatch workflow is not evidence it actually ran.

This choice is separate from F2/Q5's generated-project hosted checks and L2's
post-deploy health Action, which has to work with the laptop off. Agents may
prepare templates and tests only through the permitted route. The maintainer
authorises repository settings and workflow activation; this plan switches
nothing on.

**Distribution and safety.** Decide how a private project obtains an immutable
kit release, confirm the stable machine-local version home and accept no
broader builder credentials as a shortcut. Review the settings changes needed
for CR-02/CR-22 and updates. Confirm the unresolved Proposed choices in the
inventory above, the duplicate/refusal behaviour and human label reconciliation.
Resolve any unavailable working-hours integration rather than replacing the
decided notification behaviour silently.

**External housekeeping.** The maintainer verifies archived/merged remote
branches before any deletion, including the older repository, and removes the
paused build's obsolete local allow rules themselves. Preserve unsaved work.
This is the speed-up housekeeping left open, not a product fix R2 can claim.

## Validation and release gates

### V1. Offline release rehearsal

**Goal.** Prove the repaired core and all v1.0 capabilities hold together.
**Test.** Run required local checks with skip accounting, supported Python 3.10,
fresh lint and every judge-kind end-to-end case on throwaway projects. Cover
attended manual completion and App completion, exact tested heads, trial clashes,
stale main, all fourteen move refusals, guard removal one layer at a time,
anti-gaming cases, docs/changelog final checks, budgets/locks, deploy rollback,
notifications, lessons and host-independent resume. A failure opens a shaped
repair and the release gate stays closed. Retain scratch and evidence safely.
**Files.** Release rehearsal fixtures/report and affected end-to-end tests.
**Dependencies.** F2, all CR/L/Q pieces, H1 and maintainer choices.
**Size.** M. **Held by.** Executed required checks and independent fresh review
on the candidate immutable head; no skipped check is claimed as a pass.

### V2. Authorised real smoke and boundary checks

**Goal.** Validate the real Claude Code, installed plugin, App and sandbox
behaviour that stand-ins cannot prove.

**Preparation by the maintainer.** Create a tiny separate private test
repository and test App, install the App on that repository only and supply the
gate key by its external path. Use throwaway data, never production values.
Approve model cost, account access and each needed service/permission action.
Prepare a clean main branch and the required checks/distribution route. Review
the smoke's current prerequisites before approving execution.

**Test.** Harden `tests/smoke/run-real.sh` so hidden source copies cannot be
read by builders outside the held-out store; first prove the fixtures and safe
placement offline. Then the maintainer runs that script in their own terminal
with the real test App. Check actual installed paths, duplicate hook effects,
reviewer output creation in dontAsk, held-out/guard read-write denial and lack
of inherited personal/App credentials. Include an imported-code authority
probe against throwaway credentials, never a real destructive action. Record
the exact head, tools, results and limits without secrets. A failure is a
release blocker requiring a shaped repair, not a reason to weaken a guard.

**Files.** Smoke script/fixtures, authorised scenario evidence and release
validation report. **Dependencies.** V1, H1, L1 and maintainer preparation.
**Size.** M. **Held by.** Real App scope, independent permissions/sandbox and
gate evidence. R2 does not run the real Claude command or this smoke script.

### Release actions for the maintainer

Before publication, review the closed repair evidence, L1 to L10, H1, V1 and
V2, and any amended design decisions. Select the plugin version and immutable
kit ref; rehearse installation/update from that candidate into a fresh project,
including private checkout if the repository stays private. Check credits,
licence, support/limitations and release notes. A merge or green offline suite
alone does not declare the kit ready.

The maintainer then gives separate explicit yeses, each naming the action:

1. **Publish v1.0.** Approve the exact version and candidate head, create the
   immutable release/tag and publish the reviewed artefacts and notes. Verify
   their ref and a clean installation afterwards. No agent releases by default.
2. **Make the repository public, if chosen.** Review tracked history for secrets
   and private material, credits and the intended access change first. Public
   visibility is optional and needs its own yes, not an implication of release.
3. **Enable private vulnerability reporting.** Confirm availability for the
   chosen repository visibility/plan and the receiving maintainer, then change
   the repository setting with a named yes and verify the reporting route.

The release record holds who approved each action and the evidence, while
secrets and machine-local credentials remain outside git. Later production
error grouping and request tracing are Live stages 1 and 2 after v1.0, as the
design says; they do not replace the v1.0 health/rollback requirement.
