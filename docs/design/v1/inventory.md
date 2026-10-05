# AI Loop Kit v1: inventory of every concept, rule and check

Written on 5 October 2026, read only, for designing AI Loop Kit v1 from scratch
as a simple state machine. AI Build Kit is inspiration only. Nothing here was
invented: each row names where it comes from.

## How to read the tables

Source codes:

- **DN** is the v1 design note, `docs/design/agentic-loop.md`, with its section name.
- **RN** is the research note, `docs/design/agentic-loop-research.md`.
- **D n** is item n of the epic's decision record (the 63 decisions of 2 October).
- **SD n** is settled decision n in `.agents/tmp/v1-factory/decisions.md` (54 items, numbers 1 to 54; 36 is in the file but missing from the epic's copy).
- **S n** is slice n (its own GitHub issue), with its part letter where it has parts.
- **Lessons** is the lessons issue from the first unattended night: `c1` to `c7` are its causes, `p1` to `p8` its proposals.
- **Docs pass** is the core docs pass issue.
- **ABK** is AI Build Kit as it stands on `main`: `WORKFLOW.md` section number, `PHILOSOPHY.md`, `README.md`, or a skill file. Skill paths are relative to `.agents/skills/`.
- `fnd/` is short for `.agents/skills/setup-ai-build-kit/templates/foundation/`.

The last column says what exists today:

- **Code: file** means working, tested code on `main`.
- **Prose: file** means a written instruction in a skill on `main`, held by a rule-shape check at most, with no script holding it.
- **Branch: file** means code on the `v1-integration` branch (slice 7 part a) and not on `main`.
- **Plan** means it exists only as a decision or a slice.

A note on what is on `main`: the brief says slices 1 to 5 and slice 6 part a.
`main` actually holds all of slice 6 (parts a, b, c and two fixes, merged as
"slice-06-to-main"). Slice 7 part a sits on `v1-integration` only.

---

## 1. Tables per state

### 1.1 Idea (capture and backlog)

| Item | What it is | Source | Exists today |
|---|---|---|---|
| Capture in the person's words | A new piece opens with the person's words as its body and nothing settled. | DN Issue states; D4, D5; S2a; S4a | Code: `fnd/gate.py` (`capture --title --body-file`) |
| Capture of an issue opened by hand | An open issue with no state is taken in, keeping title and body, never duplicated. | S2a, S2d; ABK `shape/SKILL.md` Typed alone | Code: `fnd/gate.py` (`capture <number>`) |
| Idea is not a label | v1 has no `idea`, `parked`, `queued` or `blocked` label; captured work is `shaping:raw`, which is the backlog. | DN Issue states; D4 | Code: `fnd/gate.py` (OLD_MODEL list reported) |
| Note-only capture | "Note this for later", `/shape later` or `/shape idea` files the piece without triage or routing. | ABK `change-triage/SKILL.md` Capture; S4a | Prose: `change-triage/SKILL.md` |
| Duplicate search before filing | Search open and closed issues, including closed as not planned, and add the words as a comment on a match. | ABK `change-triage/SKILL.md` Step 1; S4a | Prose: `change-triage/SKILL.md` |
| Unreachable GitHub at capture | Nothing is filed; the person's words are repeated back in full. | S4a; ABK `shape/SKILL.md` | Prose: `shape/SKILL.md` |
| Drop as not planned | An idea nobody will do is closed as not planned with its reason, and can be reopened. | DN Issue states; D4; S2a | Code: `fnd/gate.py` (`drop --reason`) |
| Ideas left out are searched later | Closed-as-not-planned issues are read so a rejected idea is not rebuilt by accident. | ABK `change-triage/SKILL.md` Step 1; `setup-ai-build-kit/references/pieces.md` Ideas left out | Prose: `change-triage/SKILL.md` |
| Issue form gives no state | The issue form applies no state; the report names an issue with no state until it is captured. | S2c | Code: `fnd/piece-issue.yml`, `fnd/gate.py` (`report`) |
| Another author's issue | A colleague's issue keeps their words under "Original report"; title or scope changes and any reply wait for the person's yes. | ABK `pieces.md` Speaking for the person; `shape/SKILL.md` Clarify | Prose: `shape/SKILL.md`, `pieces.md` |
| Work found during a build | It becomes a raw piece that says "Found while building <title>", linked both ways. | DN Learning; D35; ABK `section-builder/SKILL.md` step 5 | Prose: `section-builder/SKILL.md` |
| Bug piece filed on red `main` | When `main` is red the kit files a `type:bug` piece rather than starting a run. | DN Runs; D38; S9a | Plan |
| Bug piece after failed health check | A failed post-merge health check rolls back and files a `type:bug` raw piece. | DN Merging; D30, D38; S13c | Plan |
| Chore piece for a flaky check | An unreliable guard or integration check becomes a `type:chore` piece, never a kickback. | DN Traps; D46; S9c; S11 | Plan |
| Chore pieces from drift reads | Copied code, unused code, structure and document-bloat findings become `type:chore` raw pieces, at most three. | DN Learning; D35; S17d | Plan (ABK quarterly reads are Prose: `maintain/references/waste-read.md` etc.) |
| Lesson that does not fit | A lesson past the 12-line limit, or whose home is the records, is filed as a raw piece. | S17c; S18 | Plan |
| Commands typed from habit | `/fix`, `/queue`, `/sync`, `/ship` are treated as a request for that job and routed. | S4d, S9a, S14a, S17a | Prose: `change-triage/SKILL.md` (`/fix` only) |
| Work on this computer, not the project | Installing or repairing software outside the folder gets no piece, no branch, no changelog, and waits for a yes. | ABK `change-triage/SKILL.md`; WORKFLOW 5 | Prose: `change-triage/SKILL.md` |
| Using the tool on content | Running the tool on material gets no piece; output goes to an ignored folder; keeping it is its own save. | ABK `change-triage/SKILL.md`; WORKFLOW 5 | Prose: `change-triage/SKILL.md` |
| Sub-issues for parts | A piece too big to hold is a parent with parts as sub-issues; the parent carries no state. | DN Issue states; D11; ABK PHILOSOPHY Sub-issues | Code: `fnd/gate.py` (refuses a parent) |
| Blocked-by links, not a label | Being held up by another piece is a GitHub blocked-by link. | DN Issue states; D4 | Code: `fnd/gate.py` (claim condition), `fnd/plan-refresh.sh` |

### 1.2 Shaping (the decision loop)

| Item | What it is | Source | Exists today |
|---|---|---|---|
| Six sub-states | `raw`, `research`, `clarify`, `prototype`, `spec`, `check`, exactly one on a shaping piece. | DN Issue states, Shaping; D5 | Code: `fnd/gate.py` |
| Each sub-state answers one kind of question | raw what is this; research what is true; clarify what we want; prototype what we want when it must be seen; spec no question; check complete and buildable. | DN Shaping | Prose: `shape/SKILL.md` |
| No fixed order, skip empty sub-states | A piece sits in the sub-state of its next open question; a chore can go raw, spec, check. | DN Shaping; D33; S4 Decided | Prose: `shape/SKILL.md` |
| Triage in raw | Writes a `type:`, a loop module guess marked `(guess, ...)`, `## Overlaps`, and the first `## Open question`. | DN Shaping; S4a | Prose: `change-triage/SKILL.md` Triage in raw |
| Repair versus wish | Behaviour the masterplan promised and the tool lacks is `type:bug`; anything else is `type:feature`; upkeep is `type:chore`. | S4a; ABK `change-triage/SKILL.md` | Prose: `change-triage/SKILL.md` |
| Consequence classification | Presentation, behaviour, data, access, integration, money, automatic action, reliance; stored as subject labels. | ABK `change-triage/SKILL.md` Step 3 | Prose; labels Code: `fnd/gate.py` |
| Overlap warning | Names an open or building piece that shares a subject and would be built in the same place; blocks nothing. | ABK `change-triage/SKILL.md` Step 3 | Prose: `change-triage/SKILL.md` |
| Fit check rerun on a change of kind | A request that adds outside users, real money, a promise or autonomy stops for the fit check before any sub-state. | ABK `change-triage/SKILL.md`; S4a | Prose |
| Masterplan first for data, access, money | Such a request updates the masterplan before routing. | ABK `change-triage/SKILL.md` | Prose |
| Data shape change on real data | Treated as flagged: backup first, rehearsal on a copy, then for real. | ABK `change-triage/SKILL.md` | Prose |
| Answer recorded before the move | What settled a question is written into the piece, read back, and only then does the label move. | DN Shaping; ABK `shape/SKILL.md`; `settled-is-recorded.sh` | Prose + Code: `fnd/gate.py` answer marker |
| Answer marker | Hidden last line `loop:gate sub-state since answer [question]` with a hash of the answer section; only the gate writes it. | DN Issue states; S2a | Code: `fnd/gate.py` |
| Answer sections per sub-state | `## Decided` for clarify and prototype, `## Research` for research, `## Loop` with `## Reach` for spec, `## Readiness` for check. | DN Issue states | Code: `fnd/gate.py` (ENTRY_SECTIONS) |
| New question rule | Leaving spec to ask again needs one new `## Open question` whose fingerprint differs from the one on entry; an old question is refused. | DN Issue states; SD49; S4c | Code: `fnd/gate.py` |
| Kept branch line excluded from spec hash | Adding `Kept branch:` alone never lets a piece leave spec. | DN Issue states | Code: `fnd/gate.py` |
| Shape typed alone, its order | Kickback first, then `check`, `research`, `clarify` and `prototype` when present, `spec`, then oldest `raw`. | S4a; ABK `shape/SKILL.md` | Prose |
| Shape given a number | Settles that piece; `/shape <n> check readiness` runs only the check. | ABK `shape/SKILL.md` | Prose |
| Shaping now, or "later" | Typing `/shape` with words is the choice to shape; "later" files what was agreed and stops. | ABK `shape/SKILL.md`; `shape-later.sh` | Prose |
| Who must be present | Research needs nobody; clarify and prototype need the person; a person-present question is never answered by the agent. | DN Shaping; ABK `shape/SKILL.md` | Prose |
| Person absent | Research is settled alone; waiting pieces are listed for the person's return. | ABK `shape/SKILL.md` | Prose |
| Research never decides | Facts with a source each, then one `Recommendation:` line; a finding that needs a choice moves to clarify. | DN Shaping; D5 | Prose: `shape/SKILL.md` |
| "Needs your decision" line | Research says up front whether its result needs the person. | ABK `shape/SKILL.md` | Prose |
| Source check | One external fact settled against the provider's own pages. | ABK `change-triage/references/source-check.md` | Prose |
| Existing-work search | Looks for something that already does the job, judged on maintenance, licence, cost, data and removal. | ABK `change-triage/references/existing-work.md`; `shape-research.sh` | Prose |
| Reach check on `origin/main` | Research works out what the piece reaches from today's code, reading files from `origin/main`. | DN Reach and risk; D39; S4b | Prose: `section-builder/references/reach-check.md` |
| Co-change query | Files changed in the same commits as the reached files, last 200 commits, most often first. | DN Reach; D39; SD11; S4b | Code: `section-builder/scripts/co-change.sh` |
| Map hits to areas | Every reach and co-change hit is named as an area via the area map; `unclaimed` is reported. | DN Reach; S5 | Code: `fnd/area-map.py` (`which`, `areas`) |
| Reach engine fallback | With no engine, read imports and callers directly and say which engine was used. | ABK `section-builder/references/reach-check.md` | Prose |
| Lessons read before research | Shaping reads AGENTS.md's Lessons and Learned sections of closed pieces sharing an area. | DN Shaping; D34; S17c | Plan |
| Question box | One short question, a labelled guess first, choices only for a complete short list, free text kept. | S4b; ABK `clarify/SKILL.md` How to ask; overnight batch | Prose: `clarify/SKILL.md`; check `question-box.sh` |
| Silence is no answer | Empty form, cancel, preselected unsent option or silence is never an answer or consent. | ABK `clarify/SKILL.md`; S4b | Prose |
| Guess never written as answer | With nobody there, the question and guess stay under `## Open question`. | ABK `clarify/SKILL.md`; `shape/SKILL.md` | Prose |
| Background agent asks through the run | A worker sends the question to the session that started the run, never opens a box itself. | ABK `clarify/SKILL.md` | Prose |
| What clarify covers | Users, main flow, failure, permissions, data and origin, confidential files, done, out of scope. | ABK `clarify/SKILL.md` | Prose |
| Settling a vague term | Name the ambiguity, propose terms, test on a scenario, settle one, record it on the piece. | ABK `clarify/SKILL.md` | Prose |
| Settled term kept on piece | A settled term stays on the piece through reshaping or closing until it reaches the records. | ABK `clarify/SKILL.md`; `masterplan-edges.sh` | Prose |
| Pressure-testing rules | Ask relevant edge cases: empty, duplicate, concurrent, no permission, service down, existing data, interrupted. | ABK `clarify/SKILL.md` | Prose |
| States, data and outside questions | Asked only when the piece touches them; they fill not-normal case, Data and Leaves the tool. | ABK `clarify/SKILL.md`; `piece-contract.sh` | Prose |
| Pre-mortem | "Say this went live and went wrong. Who noticed, and what did they see?" once, only when reach touches a sensitive area, data or the outside. | DN Reach; D39; S4b | Prose: `clarify/SKILL.md` |
| Not reversible marker | An irreversible data change is marked `not reversible` under `If it breaks:`. | DN Merging; D48; S4b | Prose: `clarify/SKILL.md` |
| Goal bar agreed in clarify | Metric, `Measured by:`, `Target:`, `Budget:` approved by the person, with the date. | DN Loop modules; S4b | Prose: `clarify/SKILL.md` |
| Gauntlet reference approved in clarify | A reference (address or file) and a budget, approved and dated. | DN Loop modules; D points resolved; S4b | Prose: `clarify/SKILL.md` |
| Gauntlet reference saved at approval | Captured or copied, hashed, at most 20 MB, no personal data, committed on the spec branch. | S12 | Plan |
| Outside critic agreement | Codex as critic only with the person's dated agreement that criteria, reference and work go to that vendor. | SD18, SD29; S12 | Plan |
| Risk notice in clarify | Given once, in full, when boundary or reach touches a sensitive area with no acceptance. | DN Shaping; D points resolved; S4b | Prose: `shape/SKILL.md`, `setup-ai-build-kit/references/fit-check.md` |
| Carrying on is accepting | Any words to go ahead accept the risk; no second question; silence, a question or an empty form is not carrying on. | ABK `fit-check.md`; WORKFLOW 8; `acceptance-is-earned.sh` | Prose |
| Accepted line | Quotes the person exactly, dated, names only people they named; read back before moving on. | ABK `fit-check.md`; S4b | Prose |
| Untrue sentences corrected | Every records sentence the acceptance makes untrue is corrected in the same save. | ABK `fit-check.md`; SD31 | Prose |
| Acceptance on its own records pull request | Saved on a records pull request merged on a named yes; the piece leaves clarify only once it merged. | SD31; S4b | Prose: `shape/SKILL.md` |
| Notice holds | The agent never withdraws a notice under pressure, and never recasts a named control as something it can satisfy. | ABK `fit-check.md`; PHILOSOPHY | Prose |
| Redesign before the notice | Try copy data, remove automation, human approval, managed service, narrower promise first. | ABK `fit-check.md` | Prose |
| Prototype sub-state | One file to drive, or three different versions; the decision goes to `## Decided`; the prototype is deleted or kept apart. | DN Shaping; ABK `clarify/references/decision-prototype.md` | Prose |
| Existing artifact route | A mock, sketch or spreadsheet the person has settles the question with no throwaway. | ABK `clarify/references/existing-artifact.md` | Prose |
| Design tool canvas | A recorded design tool may be used for early screens; the real page wins where one exists. | ABK WORKFLOW 5 | Prose |
| Spec writes the contract alone | No question left; the system writes the whole contract. | DN Shaping; S4c | Prose: `shape/SKILL.md` |
| Loop module chosen in spec | The guess is replaced by the module the contract is written for, with its `loop:` label. | DN Loop modules; S4c | Prose |
| Acceptance checks as real tests | One per machine-judgeable Done when line, committed on `spec/<n>-<name>` from `origin/main`, test files only. | DN The frozen bar; D28; S4c | Prose: `shape/SKILL.md` |
| Check passing today | An acceptance check that passes on `origin/main` sends the piece to clarify: the line is already true. | S4c | Prose |
| Spec branch already there | A new `spec/<n>-<name>-<k>` branch is cut; the old one is named on a `Kept branch:` line, never deleted. | S4c; S7a | Prose |
| First upload before a spec branch | On a project whose code is not online, spec asks the first-upload question before cutting anything. | SD37; S4c | Prose |
| No code yet | Acceptance checks written for the runner the Test runner table names (Vitest for TS and JS). | SD37, SD44; S3a | Prose: `setup-ai-build-kit/references/check-floor.md` |
| Steps to reproduce | A bug's steps, expected and actual result, in the person's words, for spec to turn into a failing check. | S4a | Prose: `change-triage/SKILL.md` |
| Bug fast path | A bug with a followable reproduction goes raw to spec with `loop:fix` and can run at once as a run of one. | DN Shaping; D38; S4a | Prose: `change-triage/SKILL.md` |
| Bug without reproduction | Goes to clarify with the missing step as its question. | S4a; DN Loop modules | Prose |
| Caused by line | A bug may name the merged piece that brought the fault, for kit metrics. | S17c | Plan |
| Two-layer piece | A short plain header for the person, then a complete agent layer for a builder who never saw the conversation. | DN The piece contract; ABK `pieces.md` | Prose + Code: `fnd/piece-issue.yml` |
| Piece fields | So that; Done when (Works, not the normal case); Masterplan or Behaviour change; Not in this piece; Decided; Data; Leaves the tool; Must still hold; Relies on; Loop; Reach; Crew; Needs from the computer; Under the hood; Evidence; Readiness. | ABK `pieces.md`; S3a | Code: `fnd/piece-issue.yml` |
| Field that does not apply | Absent (contract v2) or one line why (older rule). | S3a; ABK `pieces.md` | Prose (conflict, see table 3) |
| Decisions rest on something | A decision may carry a "rests on" line; shaping re-reads it and says when its support has gone. | ABK `pieces.md`; `record-habits.sh` | Prose |
| Every noticeable choice decided | Nothing a person would notice is left for the build. | ABK `shape/SKILL.md`; PHILOSOPHY | Prose |
| Parts versus blocked-by | One shared outcome makes parts of one parent; a different outcome is a separate piece linked by blocked-by. | ABK `shape/SKILL.md`; PHILOSOPHY; DN Loop modules | Prose |
| Groundwork is a vertical slice | No horizontal "database" or "API" layer pieces. | ABK `shape/SKILL.md`; setup step 10 | Prose |
| Size: one sitting | Small enough for a fresh session to hold whole. | ABK `shape/SKILL.md`; readiness item 12 | Prose |
| Context routed by reach | Whole-product facts to masterplan, whole-codebase to AGENTS.md stack, lasting design to a concept file. | ABK `shape/SKILL.md`; `change-triage/SKILL.md` | Prose |
| Kickback intake | Read the Kickback section and the comments first, keep the branch, settle the named question, re-spec, clear old Readiness. | DN Kickback; S4c | Prose: `shape/SKILL.md` |
| Build offer | A ready piece is offered to `/implement` in a fresh session; shape never builds. | ABK `shape/SKILL.md` | Prose |
| Durable records only | No changelog line for triage; only when the masterplan, build path or an acceptance changes, or work lands. | ABK `change-triage/SKILL.md` Step 5 | Prose |
| Ceremony follows size | Sub-states skippable, a length limit per type. | DN Shaping; D33 | Code: `fnd/ready-lint.py` (limits) |
| Founding shapes only to spec | Founding stops each piece at `shaping:spec` because spec pushes a branch and founding uploads nothing. | S3a; ABK `setup-ai-build-kit/SKILL.md` step 10 | Prose |
| Waiting on you section | A step only the person can do keeps the piece in clarify, with what and where. | ABK `pieces.md`; `manual-step.sh` | Prose |
| Shaping crew | Research readers 1 for a fact, 2 to 4 for a comparison, cap 5; prototype variants 1, cap 3. | DN Crews; D44; S10a | Plan (lint caps Code: `fnd/ready-lint.py`) |

### 1.3 The ready gate (Shaping's exit gate)

| Item | What it is | Source | Exists today |
|---|---|---|---|
| Ready gate is lint plus fresh session | No per-spec human approval; machine lint then a checker that did not shape the piece. | DN Shaping; D6 | Code: `fnd/ready-lint.py`, `fnd/gate.py`; Prose: `shape/references/readiness-check.md` |
| Gate condition for ready | Lint exits 0, `## Readiness` says Ready with no BLOCKING line, exactly one `loop:` label. | S2a, S3b | Code: `fnd/gate.py` |
| Lint runs before the checker | The checker never reads a piece the lint would refuse; the result is one line. | S3b; ABK `shape/SKILL.md` | Prose |
| Required sections | Header, agent layer, `## Loop`, `## Reach`, `## Not in this piece` present and non-empty. | S3b | Code: `fnd/ready-lint.py` |
| Bar fits the module | Build: Acceptance branch; fix: plus Reproduction, Must not change; goal: Metric, Measured by, Target, Budget, Guard checks, Held-out check; gauntlet: Reference, Compared by, Budget, Guard checks. | DN Loop modules; S3b | Code: `fnd/ready-lint.py` (MODULE_FIELDS) |
| Loop label matches | Exactly one `loop:` label equal to `Loop module:`; a guess line is never read as the bar. | S3b; S4a | Code: `fnd/ready-lint.py` |
| Budget unit | Goal and gauntlet budgets carry a number and attempts or minutes; tokens are refused. | S3b; S11 | Code: `fnd/ready-lint.py` |
| Reach fields | `Boundary:`, `Reaches:`, `If it breaks:`, `Depends on:`, `Reach derived at:` all present. | DN Reach and risk; D39; S3b | Code: `fnd/ready-lint.py` |
| Guarding tests exist | Every test named under `Reaches:` exists on `origin/main`; "no test covers it" names an acceptance check. | DN Reach; S3b | Code: `fnd/ready-lint.py` |
| Reach derived at a real commit | The commit is one `origin/main` contains. | S3b | Code: `fnd/ready-lint.py` |
| Depends on matches links | `Depends on:` matches the blocked-by links. | S3b; epic Names | Code: `fnd/ready-lint.py` |
| No dependency cycle | The dependencies form no cycle. | DN Reach and risk | Plan (not found in lint) |
| Areas exist in the map | Every area under `Boundary:` and `Reaches:` exists in the area map. | DN Reach; S5 | Code: `fnd/ready-lint.py`, `fnd/area-map.py` |
| Sensitive acceptance | A sensitive area in boundary or reach needs an `Accepted:` line or a caution done, read from `origin/main`. | DN Shaping; S3b; SD31 | Code: `fnd/ready-lint.py` |
| Crew shape | Absent, or a known step within its cap with a reason after "because"; a second writer is refused. | DN Crews; D44; S3b | Code: `fnd/ready-lint.py` (CREW_CAPS) |
| Refused phrases | "decide during build", "consider", "TBD", "for now", "a few", "several" and others, in Done when, Decided, Loop, Reach. | S3b; ABK readiness item 10 | Code: `fnd/ready-lint.py` |
| Brief rules | Behaviour not steps; interfaces not paths or line numbers outside allowed fields; no numbered build-step list; each criterion checkable alone. | DN The piece contract; D33; RN Skill collections | Code: `fnd/ready-lint.py` |
| Length limit per type | 80 lines chore, 120 bug, 250 feature, not counting Readiness, Kickback, Original report. | DN Settled when built; SD9 | Code: `fnd/ready-lint.py` |
| Checks fail on their assertion | Each acceptance check runs on today's code in a temporary checkout and must fail on its assertion, not an error. | DN The frozen bar; D46; S3b | Code: `fnd/ready-lint.py` |
| Acceptance branch holds tests only | A branch that changes anything other than test files is refused. | S3b | Code: `fnd/ready-lint.py` |
| Runner report reading | pytest, Vitest, Jest, Node runner reports are read to tell assertion from error; other runners fall back to exit code with a note. | S3b | Code: `fnd/ready-lint.py` (RUNNER_REPORTS) |
| Dependencies installed for the check | The lint installs dependencies in its temporary checkout first. | S3b | Code: `fnd/ready-lint.py` |
| Ten-minute check limit | Each check and install has ten minutes; a hang refuses the piece. | SD10; S3b | Code: `fnd/ready-lint.py` |
| Test command line | AGENTS.md stack section carries one `Test command:` line the lint reads. | S3b | Code: `fnd/ready-lint.py`; template `fnd/AGENTS.md` |
| Lint exit codes | 0 no gaps, 1 gaps each with next step, 2 unreachable or checkout failed (gate treats as refusal). | S3b | Code: `fnd/ready-lint.py` |
| Fresh checker | A subagent carrying none of the conversation; a fork does not count; else a paste line for a new session. | DN Shaping; ABK `shape/SKILL.md` | Prose: `shape/SKILL.md` |
| Fifteen-item readiness list | Outcome, Works, Coverage, not normal case, Data, Leaves the tool, Must still hold, Relies on, Reach, open choices, consistency, size, unseen flow, screen, each check tests its criterion. | ABK `shape/references/readiness-check.md`; S3a | Prose (stored copy checked by `piece-contract.sh`) |
| BLOCKING versus NOTE | A gap is blocking when closing it changes what a person sees or does, what is stored, or what leaves the tool. | ABK `readiness-check.md` | Prose |
| Checker matches checks to criteria | Item 15: a check that tests something else is blocking. | DN The frozen bar; D46 | Prose |
| Unread Relies on is blocking | A Relies on line the checker could not read is a blocking gap. | ABK `readiness-check.md` | Prose |
| What ready cannot catch | Domain quality, polish, platform quirks, ignored gates; ready never reads as safe. | ABK `readiness-check.md` | Prose |
| Readiness section format | Date, "checked by a session that did not shape it", Ready or Not ready, BLOCKING and NOTE lines. | ABK `readiness-check.md` | Prose; read by Code: `fnd/gate.py` |
| Gap routing | Each gap goes to the sub-state that closes it: clarify for a person, research for a fact, prototype for an unseen flow, spec for wording or lint. | S4c; ABK `shape/SKILL.md` | Prose; Code: `fnd/gate.py` (check to other sub-state needs changed Readiness) |
| Contract hash at ready | The gate posts `loop:contract sha256 commit=<spec commit>` on the issue, excluding Kickback, Readiness, Learned and markers. | DN The frozen bar; D28; S6a | Code: `fnd/gate.py` |
| Trusted hash author | The hash counts only when written by the account that added `state:ready`. | S6c | Code: `fnd/gate.py` |
| Parts pass as a container | A container passes size when every part is its own piece. | ABK `readiness-check.md` | Prose |
| Pull back before claim | The person can send a ready piece back to a shaping sub-state before it is claimed. | DN transition table; D6 | Code: `fnd/gate.py` |
| "Would benefit from your review" | The board marks a ready piece that reaches code no test covers. | SD32; S16a | Plan |
| Person asks to review a piece | `/shape <n> review` writes a `loop:review-request` marker that forces `review:person`. | SD32; S16a | Plan |
| Smoke line | A contract that names a screen or address carries `Smoke:` paths for the preview smoke test. | S13b | Plan (lint already allows the path) |
| Target model's "user story, expected flow, observed behaviour" | Mapped to So that, Done when and not-normal cases, and a bug's Steps to reproduce. | ABK `pieces.md`; S4a | Prose |
| Target model's "dated research" | Research claims carry sources; dates exist only for goal and gauntlet bars and recipe Plan terms. | S4b; ABK `recipe-format.md` | Partly Prose (no research date rule) |
| Target model's "budget" | Goal and gauntlet budgets in the contract; other pieces take the settings default. | S7a; S11; S12 | Code: `fnd/ready-lint.py` (goal, gauntlet); Branch: `implement/scripts/run.py` |

### 1.4 Ready to Building: the re-check before a claim

| Item | What it is | Source | Exists today |
|---|---|---|---|
| Lint again on today's `origin/main` | At the start of a run each chosen piece must pass the ready-gate lint again. | S9a | Plan (lint Code: `fnd/ready-lint.py`) |
| Reach worked out again | The reach is re-derived at run start; a commit since `Reach derived at:` that changes a file the reach covers fails the piece. | DN Reach and risk; D39; S9a | Plan |
| Acceptance checks still fail | Re-running the lint re-runs each acceptance check on today's code. | S3b; S9a | Code: `fnd/ready-lint.py` |
| Blockers closed or earlier in run | The claim needs every blocked-by piece closed or listed earlier in the run record. | DN transition table; S2a | Code: `fnd/gate.py` |
| Not already building | The gate refuses a claim on a piece already in `state:building`. | S2a | Code: `fnd/gate.py` |
| Claim names a run or assignee | `--run <name>` or `--assignee` is required for the claim. | S2a | Code: `fnd/gate.py` |
| Claim race | Each run comments "Claimed by run <name>"; the earliest comment wins and only the later claimant backs off. | ABK `implement/references/running-longer.md` For each piece; `the-runner.sh` | Prose |
| Contract unchanged since ready | `check-contract` recomputes the hash at the claim and before each attempt; a change kicks back to spec. | DN The frozen bar; S6a | Code: `fnd/gate.py` (`check-contract`) |
| Readiness present and Ready | A ready piece with no Readiness section is checked first by a fresh session. | ABK `running-longer.md` | Prose |
| Hard open choice seen at plan | A choice about stored data, sync or what leaves the tool sends the piece to clarify unclaimed, no branch. | ABK `running-longer.md`; `the-runner.sh` | Prose |
| Missing fact only | A piece lacking a build fact with no open choice is skipped with a reason and stays ready. | ABK `running-longer.md` | Prose |
| Sensitive area without acceptance | Never taken by a run; a run never accepts on the person's behalf. | DN Shaping; ABK `running-longer.md`; `acceptance-is-earned.sh` | Prose (lint Code holds it at ready) |
| Waiting on you | A piece waiting on a person's step is not taken; named and skipped. | ABK `implement/SKILL.md` | Prose |
| Red `main` blocks a run | No run starts while `main` is red, except a run of one on a `type:bug` piece. | DN Runs; D38; S9a | Plan |
| Unknown `main` result blocks | Unreachable GitHub or no finished check on `main` starts nothing. | S9a | Plan |
| Project check runs on push to `main` | So every `main` commit carries a result. | S9a | Plan (`fnd/checks.yml` runs on pull_request only) |
| First upload is the one question | A run whose code is not on GitHub asks for the first upload, naming repository and visibility, and builds nothing until then. | S9a; ABK `section-builder/SKILL.md` The first upload | Prose: `section-builder/SKILL.md` |
| Kit repository guard | A project whose `origin` is the kit's own repository pushes nothing and opens no issue. | ABK `first-upload-asks.sh`; S22 | Prose + Code: `setup-ai-build-kit/scripts/check-tooling.sh` |
| Two runs at once refused | A second run does not start while another is running. | S9c | Plan |
| Relies on re-confirmed | The start ritual re-reads each Relies on line; one that no longer holds is a hard open choice. | ABK `running-longer.md` steps 3 | Prose |
| Smoke check on `main` | A start smoke check that fails on `main` ends the run. | ABK `running-longer.md` | Prose |
| Overlap with running pieces | Pieces sharing a boundary area never build in the same wave. | DN Runs; D33; S9a | Plan (ABK groups Code: `fnd/plan-refresh.sh` `Go together`) |
| Explore privately limit | On that path a run takes only disposable work whose Done when a machine can check. | ABK `running-longer.md` | Prose |
| Research expired | The target model re-checks research age. | Not in the sources | Plan (new) |
| `main` moved | Covered in the sources only by re-lint and reach re-derivation, not by a general rebase rule. | S9a | Plan |

### 1.5 Building: the orchestrator loop

| Item | What it is | Source | Exists today |
|---|---|---|---|
| Every build is a run | A run of one opens its own pull request; a run of several uses an integration branch and one pull request. | DN Runs; D2; S9 | Plan (Branch: `implement/scripts/run.py` loop driver) |
| Run starts on the person's pick | The person picks pieces or says all ready pieces; the run asks nothing else. | DN Runs; D3 | Plan |
| Settings decide count, budgets, merge | Read from `.agents/loop-settings.json`; malformed values stop the run with the key named. | DN Runs; S7a, S9a | Branch: `templates/loop-settings.json`, `run.py` |
| Run name | `<YYYY-MM-DD>-<HHMMSS>`. | ABK `running-longer.md` | Prose |
| Run record | `.agents/runs/<name>/run.json` in the main folder, git-ignored, replacing `state.json`. | Epic Names; S2a, S9a | Partly Code: `fnd/gate.py` (piece status only) |
| Gate writes status with labels | Status and labels are written in one step; a failed label write leaves the record unchanged. | DN Runs; D10; S2a | Code: `fnd/gate.py` |
| Piece statuses | queued, building, checking, integrated, kicked back, withdrawn, each paired with an issue state. | DN Runs; D10 | Partly Code: `fnd/gate.py` (RUN_STATUS) |
| Run statuses | planned, running, paused, in preview, merged, abandoned. | DN Runs; D10; S9a | Plan |
| Plan printed once | Waves in order, each piece's module, what is left out and why; then it starts. | S9a | Plan |
| Waves from Depends on and Boundary | A piece after its dependencies; shared-area pieces never in one wave; all shared means one at a time. | DN Runs; D33; S9a | Plan (`plan-run.py`) |
| Order of numbers kept | The person's order is kept where dependencies and boundaries allow. | S16b | Plan |
| Held-up piece joins | A piece whose blockers are all in the plan joins and is ordered after them. | ABK `running-longer.md` | Prose |
| Parts of one parent | Share one branch and one pull request (ABK) or integrate like any piece (v1). | ABK `running-longer.md` Stacks and parts | Prose |
| Builder count suggested from the computer | Free memory minus reserve divided by need per builder, at most half the cores and at most four. | DN Computer resources; D45; S10b | Plan |
| `at_once` auto and the hard cap | `"auto"` uses the suggestion; a number is the person's; above the suggestion warns once; six is the hard cap. | SD28; S10b | Plan |
| Memory defaults | 2.5 GiB per builder, 4 GiB reserve, pressure and critical thresholds. | SD16; S10b | Plan |
| Pressure readings | macOS `memory_pressure` and swap; Linux `/proc/meminfo` and PSI; elsewhere one builder. | S10b | Plan |
| Back-off under pressure | No new builder, stop idle dev servers, lower the count; critical stops the newest builder with no commit. | DN Computer resources; S10b | Plan |
| Pressure stop costs no attempt | The stopped piece goes back to queued and ready with its work kept. | S10b | Plan |
| Resume starts after ten calm minutes | Starts resume at the lower count once pressure is normal for ten minutes. | DN Computer resources | Plan |
| Heavy pieces run alone | `Heavy: yes` means no other builder is alive. | DN Computer resources; S10b | Plan |
| Local app memory counts | Each running local app's memory counts in the suggestion. | S14c | Plan |
| Usage limit | Start nothing new, record the reset time, pause until it. | DN Computer resources; S10b | Plan |
| Allowance line | The opening line says N builders spend the allowance N times faster. | DN Computer resources | Plan |
| Shared resources | One package store, one browser held by the coordinator, dev server only during a walk-through, at most two test workers. | DN Computer resources; D45 | Plan |
| Browser lock | `.agents/runs/<name>/browser.lock` names the piece holding the browser. | S12 | Plan |
| Heartbeat | A builder's heartbeat is a change in its worktree; 30 minutes asks, 45 stops and counts an attempt. | DN Computer resources; D45; S10b | Plan |
| Wall-clock cap | The piece budget (120 minutes) is the cap; no contract override. | SD12; S10b | Branch: `run.py` |
| Run record resource fields | Current count, changes with reasons, peak memory, each builder's last heartbeat. | DN Computer resources; S10b | Plan |
| Start requests | `run.py` never starts a model session; it writes a start request, the coordinating session starts a subagent and writes back its id. | SD27; S7a, S10a | Branch: `implement/scripts/run.py` |
| Crew roles | Builder (only writer), critic, reader or probe (read only), checker; each an agent definition with a tool list. | DN Crews; D44; S10a | Plan (reviewer definition planned S8) |
| Role definitions placed | Four definitions placed into `.claude/agents/` when missing or generated and different; edited ones left alone. | S10a | Plan |
| Crew default and caps table | Research, prototype, readiness, fix, build, goal, gauntlet, run, each with default and cap. | DN Crews | Code (caps only): `fnd/ready-lint.py` |
| One writer per piece | No agent starts a writer; a second builder for a live piece is refused. | DN Crews; D44 | Plan |
| Declared inputs only | A critic never sees the builder's transcript; each member gets only its inputs. | DN Crews; D44 | Plan |
| Verdict formats | Reviewer JSON, reader `{answer, sources, could_not_check}`; an unparsed verdict is no verdict. | S8, S10a | Plan |
| Helpers count against budget | Read-only helpers start nothing and cost the piece's budget. | DN Crews | Plan |
| Run budget | 480 minutes by default. | SD15; S9c | Plan |
| CI round cap | Three CI failures on the run's pull request pause it. | SD15; S9c | Plan |
| Refused commands | Three refused commands in a row pause the run; each result lists them. | DN Runs; D32; S9c | Plan |
| Environment failed twice | Two in a row on different pieces pause the run. | S7a | Branch: `run.py` |
| Pause, continue, stop | `/implement pause|continue|stop <run>` call the gate's run actions; stop abandons and keeps branches. | SD24; S9c | Plan |
| Abandon gives pieces back | Building, checking and integrated pieces return to ready; kicked-back pieces stay in shaping. | DN transition table; S2a; S9 | Code: `fnd/gate.py` (given back) |
| Withdrawn | A piece whose dependency was kicked back returns to ready with `--withdrawn-by`. | DN Runs; S2a | Code: `fnd/gate.py` |
| Resume from the record | A new session resumes from `run.json`, never memory; labels win where the state file is behind. | S9c; ABK `running-longer.md` Resuming | Prose; Branch: `implement/scripts/recovery.py` |
| Recovery helper | Keeps failed work, checks a baseline, says which pieces are eligible on resume. | DN Projects founded; epic; S7a, S9c | Branch: `implement/scripts/recovery.py` |
| Old state file ignored | A run folder with only `state.json` is never resumed or counted. | S9c | Plan |
| Worktree per piece | `.agents/worktrees/<n>-<name>`, git-ignored; the main folder never switches branch. | ABK `running-longer.md`; PHILOSOPHY worktrees | Code: `implement/scripts/worktree.sh` |
| Worktree base | Cut from `origin/main`, or the integration branch head in v1. | ABK `running-longer.md`; S9b | Code: `worktree.sh` (`open`) |
| Env file link | ABK links `.env` into the worktree; v1 runs give no link and only a throwaway `.env.local`. | ABK `running-longer.md`; SD30; S15b | Code: `worktree.sh` (link); v1 Plan |
| Worktree links for ignored build files | `worktree-links` paths linked, never copied; confidential, env, tracked and outside paths refused. | ABK `running-longer.md`; `worktree-links.sh` | Code: `worktree.sh` |
| Dependencies per worktree | Installed before the start ritual with the recorded install command. | ABK `running-longer.md` | Prose |
| Port per piece | `worktree.sh port` gives a free port, recorded and named in the hand-over. | ABK `running-longer.md` | Code: `worktree.sh` (`port`) |
| Path already there | Reused only on the same branch with nothing unsaved; otherwise skipped. | ABK `running-longer.md` | Code: `worktree.sh` |
| Full disk | Stops the run at the next piece. | ABK `running-longer.md` | Code: `worktree.sh` (exit 3) |
| Unsaved work definition | Uncommitted change, a commit only this computer holds, or a real ignored file outside dependency folders. | ABK `running-longer.md` | Code: `worktree.sh` (`unsaved`) |
| Tidy and leftovers | Remove a worktree only when its pull request closed and nothing is unsaved; never by force, never with its branch. | ABK `running-longer.md`; `kit-owns-worktrees.sh` | Code: `worktree.sh` (`tidy`, `leftovers`, `remove`) |
| Other tools' worktrees | Never touched; run state and worktrees always in the main folder. | ABK `running-longer.md` | Code: `worktree.sh` |
| Git older than 2.17 | No worktree; one checkout, one piece at a time. | ABK `running-longer.md` | Code: `worktree.sh` (exit 4) |
| Local app per worktree | `worktree.sh app start|stop` runs the recipe's local app on its own port with throwaway seeded data. | DN Deployment; D46; S14c | Plan |
| Throwaway environment file | `.agents/app/.env.local` with throwaway values; builders never see a real key. | SD30; S14c; S15b | Plan |
| Integration branch | `run/<name>` cut from `main` at the start, pushed. | DN Runs; S9b | Plan |
| Live progress page | Published where the agent can, showing titles, state and links only. | ABK `running-longer.md` | Prose |
| `progress.md` | One line per step with time, piece and what happened. | ABK `running-longer.md`; S9 | Prose |
| Sandbox opening line | Each run says whether the sandbox and host fence hold. | SD22, SD38; S15a | Plan |
| Missing tool outside the folder | The piece is kicked back to clarify naming the tool; the run ends if every piece needs it. | ABK `running-longer.md`; `section-builder/SKILL.md` step 4 | Prose |
| Run ends at once | When nothing eligible is left, every piece is left in a final state and one report is given. | ABK `running-longer.md` When the run ends | Prose |
| Run report | Kickbacks first with questions, then each piece with pull request and state, flags, what was not seen, merge order. | ABK `running-longer.md` | Prose |
| Agent that never reports | Counts as a failed attempt. | ABK `running-longer.md` | Prose |
| Group built at the same time | ABK: the coordinator claims, reviews, opens pull requests and merges; background agents only build and never push. | ABK `running-longer.md`; `parallel-run.sh` | Prose |
| Codex members | On Codex each member is a fresh `codex exec` with a run permission profile. | S19c | Plan |
| Goal race | Two or three racers in separate worktrees from the same kept commit. | DN Crews; S11 | Plan |
| Coordinator mailbox | A file the coordinator reads at every step so a person or watchdog can reach a running run. | Lessons c4, p4 | Plan (new) |

### 1.6 Building: the build loop for one piece

| Item | What it is | Source | Exists today |
|---|---|---|---|
| One loop, four judges | Fix (reproduction), build (checks), goal (metric), gauntlet (reference critic). | DN Loop modules; D12; target model | Branch: `section-builder/references/build-loop.md` (build only) |
| Safe start | Refuse to start on uncommitted work; start from up-to-date `main` or the piece's acceptance branch. | ABK `section-builder/SKILL.md` step 1 | Prose |
| Build on the acceptance branch | The pull request comes from the spec branch; `main` is merged into it first. | S4c | Prose: `section-builder/SKILL.md` |
| Claim before changing anything | `gate.py move building --assignee`; unreachable GitHub means no start. | S2d; ABK `section-builder/SKILL.md` | Code: `fnd/gate.py` |
| Contract check every attempt | `check-contract` at the start of each attempt. | S6a | Code: `fnd/gate.py` |
| Agree the visible result | Say back what the person will see; ask only when ambiguous. | ABK `section-builder/SKILL.md` step 2 | Prose |
| Choose evidence | Automated test, guided manual check, operational rehearsal or source evidence by claim type. | ABK WORKFLOW 6; `section-builder/SKILL.md` step 3 | Prose |
| Checks first | Each machine check is written and seen to fail, recorded through the gate, committed alone before code. | ABK `section-builder/SKILL.md` step 4; PHILOSOPHY | Prose + Code: `fnd/gate.py` (`evidence`) |
| Acceptance checks never written by builder | On a piece with an acceptance branch the builder only confirms the checks still fail. | S4c, S6 | Prose |
| Checks commit when no acceptance branch | The commit that first holds the checks stands in for the spec commit. | S6 fix | Code: `fnd/gate.py`, `section-builder/scripts/bar-guard.sh` |
| Wrong test or impossible line | Reported, never worked round; no weaken, skip or delete. | ABK `section-builder/SKILL.md` step 4; RN Verification | Prose + Code: `test-guard.sh` |
| New checks in new files | So writing checks changes no existing test. | ABK `section-builder/SKILL.md` | Prose |
| Structure baseline | Imports between changed parts, compared after; one line only when it got worse. | ABK `section-builder/SKILL.md` steps 4, 7; `structure-change.sh` | Prose |
| Try, judge, keep or discard | Goal: the script keeps a change only when the number moved and guards are green. | DN Loop modules; D12; S11 | Plan |
| Attempt is a fresh context | Each attempt is a fresh builder carrying a script-built note, never a model summary. | DN Loop modules; D46; S7a | Branch: `run.py`, `implement/scripts/attempt-note.py` |
| Attempt note | Failing checks with exit codes and last 40 lines, files touched, end commit, status. | S7a | Branch: `attempt-note.py` |
| Failed work preserved | `recovery.py preserve` keeps it; the next attempt starts from the start commit's content. | S7a | Branch: `recovery.py` |
| Five builder statuses | done, done with concerns, needs context, blocked, environment failed; each with one route. | DN Review; D29, D46; S7a | Branch: `fnd/gate.py` (`result`) |
| Result file | `.agents/runs/<run>/results/<n>-attempt-<k>.json` with status, concerns, needs, could-not-check, refused commands, learned. | S7a, S9c, S17c | Branch: `run.py`, `gate.py` |
| Environment failure never kicks back | Retry, then pause; the kickback rate must not measure the laptop. | DN Review; D46 | Branch: `gate.py` |
| Limits | Three attempts and 120 minutes, whichever first. | DN Settled when built; SD12; S7a | Branch: `run.py` |
| At the limit | Kickback to research, or to spec when a check cannot be met as written (from the result's `needs`). | SD13; S7a | Branch: `gate.py`; Prose: `section-builder/SKILL.md` step 5 |
| Self-repair within limits | The builder may research and repair; a finding that changes Done when, Decided or the boundary ends the attempt as needs context. | DN Loop modules; D14; S7a | Branch: `build-loop.md` |
| Switching module | Only through `gate.py switch-module` when the contract already holds the new bar; logged. | DN Loop modules; D13; S7a | Branch: `gate.py` |
| Stop and SubagentStop hooks | `gate.py stop-check` sends a builder back once if its claimed result is not true. | DN What a machine enforces; S7a | Branch: `fnd/claude-settings.json`, `gate.py` |
| Frozen bar: bar guard | Lists seven kinds of change to what the piece is measured against; unnamed ones refused, named ones force review. | DN The frozen bar; D28; S6a | Code: `section-builder/scripts/bar-guard.sh`, `test-guard.sh`, `fnd/gate.py` |
| Changes the bar line | A guarded change counts as named only on a `Changes the bar: <path>, because <reason>` line; an acceptance check can never be named. | S6a | Code: `fnd/gate.py`, `bar-guard.sh`, `fnd/ready-lint.py` |
| Removal-only settings change listed | Taking a strict setting out counts as a change. | S6c | Code: `bar-guard.sh` |
| Fresh evidence run by the gate | Before review the gate runs every acceptance, guard and Test command on a clean saved commit; a retry pass is a failure. | DN The frozen bar; D28; S6b | Code: `fnd/gate.py` |
| Red before green as evidence | For build and fix, each acceptance check must have failed at the spec commit on its assertion. | DN The frozen bar; S6b | Code: `fnd/gate.py` |
| Evidence record | `.agents/pieces/<n>/evidence.jsonl`, each line hash-chained; only the gate writes it; outputs kept beside it. | S6b | Code: `fnd/gate.py` |
| Deny writes to piece records | Deny rules refuse Edit on `.agents/pieces/`. | S6b | Code: `fnd/claude-settings.json` |
| Test strength after green | Where StrykerJS or mutmut is already a dependency, break the changed code; a check noticing nothing forces review. | DN The frozen bar; D46; S6c | Code: `fnd/gate.py` (`evidence --breakage`); Prose: `section-builder/references/test-strength.md` |
| No runner, said once | Where neither runner exists, one evidence line and one pull request sentence say so. | S6c | Code: `fnd/gate.py` |
| No score as a gate | Mutation or coverage numbers never gate; they force review only. | D47; DN Traps | Prose |
| Type check and linter before hand-over | Run what AGENTS.md's stack names; a failure is fixed at the root. | ABK `section-builder/SKILL.md` step 6; `check-floor.sh` | Prose |
| Builder adds fresh ruff and mypy | On changed Python files (factory rule). | SD52 | Factory only |
| Trim pass | Remove or fold what the change added that nothing needs, never restructure, never touch a test. | ABK `section-builder/references/trim.md` | Prose |
| Walk-through | Drive the tool with sample data and record what was seen, against Done when. | ABK `section-builder/SKILL.md` step 6 | Prose |
| Walk-through eyes | Browser tool, Playwright if present, PDF via pdftoppm (30 pages), office via soffice, SVG via ImageMagick; never installs. | ABK `section-builder/SKILL.md`; `walk-through-eyes.sh` | Prose |
| Pictures in the main folder | `.agents/tmp/walkthrough/<n>/`, never in a worktree. | ABK `section-builder/SKILL.md` | Prose |
| Could not see | Named; the piece goes to the person. | ABK `section-builder/SKILL.md` | Prose |
| Screen rules | Project design system first; house rules; never claims accessible, compliant or good. | ABK `screen-check/SKILL.md` | Prose |
| Screen-check as a named check | Returns `<rule>: passed|failed|not checked` lines a bar can name. | DN Commands; S12 | Plan |
| Reach check before review | What the finished change reaches and the existing tests that cover it run first. | DN Reach; RN TDAD; ABK `section-builder/SKILL.md` step 7 | Prose |
| Outside the boundary | A changed path outside `Boundary:` or unclaimed forces review, never refuses. | DN Reach; S6a | Code: `fnd/gate.py` |
| Map change with the code | A code move and its area map change share one save. | S5 | Prose: `section-builder/SKILL.md` |
| Fix: no cause before reproduction | No non-test commit before the first evidence of the reproduction failing. | DN Loop modules; D36; S7b | Plan (Branch slice-07b) |
| Fix: ranked causes with predictions | Two to five causes, each falsifiable. | DN Loop modules; D36; ABK `fix-loop.md` | Prose: `section-builder/references/fix-loop.md` |
| Fix: history first | Read changelog and closed pieces; a failed earlier repair is ruled out. | ABK `fix-loop.md`; `fix-history-first.sh` | Prose |
| Fix: bisect from known good | Bisect saved history only when a known-good point exists. | ABK `fix-loop.md` | Prose |
| Fix: one cause at a time | Reset after a failed attempt; fixes never stack. | ABK `fix-loop.md` | Prose |
| Fix: request record | After launch read the tool's own request record beside the report. | ABK `fix-loop.md`; `request-record.sh` | Prose |
| Fix: cheapest catching check | Each fix adds the cheapest check that would have caught the fault. | DN Loop modules; D36; S7b | Prose |
| Fix: must not change | Held by a guard check (an existing test under Reaches or a new one). | DN The piece contract; D33; S7b | Plan |
| Fix: three failures | Back to research with every attempt's causes; no reproduction back to clarify. | DN Loop modules; D36; S7b | Plan (ABK escalation has six routes) |
| Fix: unreliable reproduction | Ranked as a cause of its own, never fixed on a retry. | S7b | Plan |
| Fix: cleanup | Remove every temporary log or harness and run the evidence again. | ABK `fix-loop.md` step 7 | Prose |
| Goal: measuring | The metric command's last output line is a number; non-zero or no number is a failed measurement. | S11 | Plan |
| Goal: direction | From start and target. A start already at target is a kickback. | S11 | Plan |
| Goal: attempt branches | Each round on `<piece>-goal-<k>` from the last kept commit; keeping is a fast-forward by the script; never deleted by the kit. | S11 | Plan |
| Goal: held-out check | On its own `held-out/<n>` branch, run once at the end in its own worktree; never in the builder's brief. | DN Loop modules; S11 | Plan |
| Goal: margin | `Keep when better by:` sets the smallest change that counts. | S11 | Plan |
| Goal: frozen bar | Paths on `Measured by:` and `Guard checks:` are protected; the measured code is not. | S11 | Plan |
| Goal: missed target | Best guarded result goes to `review:person` with the numbers. | DN Loop modules; D15 | Plan |
| Goal: no gain | Kickback to clarify, no pull request. | SD17; S11 | Plan |
| Goal: held-out fails | Target met but held-out fails goes to the person with both numbers. | S11 | Plan |
| Goal: resume | From the last kept commit, never an unmeasured attempt. | S11 | Plan |
| Goal: native goal mode | A native `/goal` judge never ends a goal piece. | RN Loops; S11 | Prose (ABK still treats it as a run: `running-longer.md` Goal modes) |
| Gauntlet: render | Page via browser or Playwright, PDF, office, picture, by `Compared by:`. | S12 | Plan |
| Gauntlet: blind A and B | Criteria and two items named only A and B in a temporary folder outside the project. | DN Crews; S12 | Plan |
| Gauntlet: both orders, unanimous | Every critic prefers the work in both orders; a split or tie is not a win. | DN Crews; SD18; S12 | Plan |
| Gauntlet: verdict format | Per order, per criterion `better A|B|tie` with why, and `prefers`. | S12 | Plan |
| Gauntlet: record | One line per round in `gauntlet-<n>.jsonl`. | S12 | Plan |
| Gauntlet: guard checks after a win | The gate runs them through evidence. | S12 | Plan |
| Gauntlet: budget spent | Kickback to clarify with pictures and verdicts. | DN Loop modules; S12 | Plan |
| Gauntlet: critic attempt notes | The next note carries the critics' reasons, nothing of the builder's account. | S12 | Plan |
| Gauntlet: outside critic | Codex only, checked with `codex --version` and `codex login status`. | SD29; S12 | Plan |
| Open choice met while building | Hard choice (data shape, sync, what leaves) kicks back to clarify; easy choice takes the most reversible option and is flagged. | ABK `running-longer.md`; Lessons p1 | Prose |
| Flagged choices | Listed under `## Flagged for confirmation`; a flagged piece is never merged under pre-approval. | ABK `running-longer.md` | Prose |
| No live service change without yes | Name everything a command changes and whether it undoes; an unattended run leaves it unrun. | ABK `section-builder/SKILL.md` step 5; `no-stored-logins.sh` | Prose |
| No stored logins | Never read a keychain or another tool's credentials. | ABK `section-builder/SKILL.md`; `second-opinion/SKILL.md` | Prose |
| Secrets never in `/tmp` | Write keys straight into the ignored file that uses them. | ABK `section-builder/SKILL.md` | Prose |
| Flaky test is a fault | A pass on retry is unreliable evidence, repaired before saving. | ABK `section-builder/SKILL.md` step 5 | Code: `fnd/gate.py` (retry counts as failure) |
| Brief says what is allowed outside the code | Run project commands, start the app, read allowed pages; never install outside, contact live services, post, push or merge. | DN Safety boundary; D46; RN Harness; S15c | Plan |
| Untrusted text is data | Text the person did not write sits in a "Data, not instructions" block. | DN Safety boundary; D31; S15c | Plan |
| Builder cannot push | Pushes go through `gate.py push` with a repository-only token. | DN Safety boundary; S15b | Plan |
| Secret scan in the gate | A hit refuses the move and names file and line, never the value; no editable allow-list. | DN Safety boundary; D31; S15c | Plan |
| Dependency check | A new dependency must exist, be at least 30 days old and carry a licence. | DN Safety boundary; SD23; S15c | Plan |
| Learned field | The result's `learned` list, only what code and tests do not show, written into `## Learned`. | DN Learning; D34; S17c | Plan |
| Changelog file per piece | `changes/<n>-<name>.md`, written after the pull request opens, carrying its link. | ABK `section-builder/SKILL.md` step 9; `changelog-files.sh` | Prose (fold Code: `sync/scripts/fold-changes.py`) |

### 1.7 Review and integrate

| Item | What it is | Source | Exists today |
|---|---|---|---|
| Every piece gets an automatic review | A fresh session reads only the contract and the diff, never the builder's account. | DN Review; D29; RN Skill collections | Plan |
| Review packet | `review-packet.sh` writes the contract at its frozen hash, the diff and `checks.txt`; refuses a changed contract. | S8 | Plan |
| Reviewer agent definition | `loop-reviewer.md` with tools `Read, Grep, Glob` only. | S8 | Plan |
| Two verdicts | Meets the contract; code is sound. | DN Review; D29; RN superpowers | Plan |
| Gap kinds | Missing, partial, contradicts, unrequested; each with what it is about and `reproduced_by`. | DN Review; D29 | Plan |
| A finding counts only when reproduced | The gate runs `reproduced_by`; an unreproduced gap is logged "not counted". | DN Crews; D44; S8 | Plan |
| No without a counted gap | Goes to `review:person` as `unreproduced_no`. | S8 | Plan |
| Gap routes | Missing and partial back to the builder; contradicts is a kickback to clarify; unrequested taken out or to the person. | DN Review; S8 | Plan |
| Review rounds | Two rounds, then `review:person` with the gaps. | SD14; S8 | Plan |
| Rulings logged | `.agents/pieces/<n>/reviews.jsonl` and a `loop:review round=<k>` comment on the issue. | DN Review; S8 | Plan |
| No reviewer or no verdict | One more fresh reviewer; then `review:person` with the reason. | S8 | Plan |
| No same-session fallback | For the automatic review, on any path. | S8 | Plan (ABK allows it on Explore privately: `second-opinion/SKILL.md`) |
| Named reviewer is a person | No session meets a review that names a person. | ABK `second-opinion/SKILL.md`; `named-reviewer-is-a-person.sh` | Prose |
| Second opinion axes | Agreement, risk, screen; classics tried rather than assumed. | ABK `second-opinion/SKILL.md` | Prose |
| Worth stopping for, worth knowing | Two lists so the decision is "is the first list empty?". | ABK `second-opinion/SKILL.md`; PHILOSOPHY | Prose |
| Forced reasons file | `.agents/pieces/<n>/forced.jsonl` with `reason`, `detail`, `source`; only the gate writes it. | S6a, S8 | Code: `fnd/gate.py` (guard_change, outside_boundary, weak_check) |
| Forced reasons list | Guard change, outside boundary, weak check, builder concerns, unreproduced no, no reviewer, goal missed, held-out failed, not reversible, first deployment, person asked, unchecked dependency, secret-scan dispute. | DN Review; S6, S7, S8, S11, S13, S15, S16 | Partly Code (first three) |
| Reasons posted on the issue | One bookkeeping comment listing why the person must look. | S6a | Code: `fnd/gate.py` |
| `review:auto` versus `review:person` | Auto is the default; the gate chooses. Until the reviewer exists every piece gets `review:person`. | DN Review; D8; S2 Decided | Code: `fnd/gate.py` (always person) |
| Ask which pieces to review | The system asks and warns when a piece would benefit. | DN Review; D8 | Plan |
| Review never stops the loop | The loop moves on while a review waits. | DN Two zones; D1 | Plan |
| In review back to building | A defect the spec covers, with a reason posted as one comment. | DN transition table; S2a | Code: `fnd/gate.py` |
| In review back to shaping | A problem in the spec, with a Kickback section. | DN transition table | Code: `fnd/gate.py` |
| Calibration marker | A person's move back posts `loop:person-verdict`; a merge with no move counts as agreement. | DN Review; S8 | Plan |
| Integration one at a time | Each finished piece takes in the integration branch with a merge commit, the full checks run on the combined result, then it joins. | DN Runs; D30; S9b | Plan |
| No agent conflict resolution | A conflicting piece is rebuilt once from the head; a second conflict kicks back to spec. | DN Runs; D30; S9b | Plan |
| Integrate move | `gate.py integrate <n> --run` moves to in-review once the merge commit is on `origin/run/<name>`. | S9b | Plan |
| Bisect on red | Run the failing check twice; flaky means a chore piece; otherwise bisect the piece merges and revert the breaker. | DN Runs; D30; S9c | Plan |
| Revert conflicts | Abort the revert, kick nothing back, pause with the reason. | S9c | Plan |
| Fails only on GitHub's runner | No bisect; pause as environment failed with the job's link. | S9c | Plan |
| Merge commit, never rebase | So no force push is needed. | S9 Decided | Plan |
| One pull request per run | From the integration branch with one `Closes #<n>` line per integrated piece. | DN Runs; S9b | Plan |
| Closing words rule | Only a `Closes #<n>` line closes; no closing word before any other number anywhere. | ABK `section-builder/SKILL.md` step 8; `closing-words.sh` | Prose |
| Changelog files on the run branch | One per integrated piece in one commit. | S9b | Plan |
| Bring up to date before merge | Every merge first takes in `main`, folds changelog files, and waits for the check on that commit. | ABK `section-builder/references/merge.md`; `recheck-before-merge.sh` | Code: `section-builder/scripts/bring-up-to-date.sh` |
| Fold changelog at merge | Files in `changes/` become CHANGELOG lines under the day they reached `main`. | ABK `merge.md`; `fold-at-merge.sh` | Code: `sync/scripts/fold-changes.py` |
| Conflict or red after update | No merge; one comment naming files; taken to shaping as a bug. | ABK `merge.md` | Prose |
| Waiting for the check | One `gh pr checks --watch --fail-fast`, never a sleep loop; exit 8 or unknown option is not finished; no checks is never green. | ABK `merge.md` | Prose |
| Yes that names the merge | Name each pull request; "merge 1, 2 and 4" counts for each; "put it live" is not that yes. | ABK `merge.md`; `one-merge-step.sh` | Prose |
| Merge made on the pull request | Never by merging locally and pushing `main`; stacked pull requests merge after their base. | ABK `merge.md` | Prose |
| Merge policy | `merge` setting `person` or `automatic`; founding writes `person`. | DN Merging; D37; S13a | Plan |
| Pre-approval for a run | ABK: six conditions under which a run merges pieces; removed in v1 by the merge policy. | ABK `merge.md`; S13a | Prose (to be removed) |
| Automatic merge conditions | All `review:auto`, gates green, no sensitive area, preview smoke passes, recipe proven, project has earned it, GitHub protects `main`. | DN Merging; D18, D19, D37; S13a | Plan |
| Gate enables GitHub auto-merge | The gate never merges itself; GitHub's required check is the last word. | S13 Decided | Plan |
| Protection read | Visibility and protection or ruleset endpoints decide; re-read before each automatic merge. | D19; S13a | Plan |
| Ruleset offer | Founding offers once a ruleset on `main` with `do_not_enforce_on_create`. | SD20; S13a | Plan |
| Confirmation box before merges that go live | Ask rules make Claude Code show a box before `gh pr merge`. | ABK `merge.md`; `merge-ask-rule.sh` | Code: `setup-ai-build-kit/scripts/merge-ask-rules.py`, `templates/merge-ask-rules.json` |
| Writes in the person's name ask first | Comments, reviews, new issues and API writes behind an ask rule. | SD40; S15a | Plan |
| Lessons promoted before the run's pull request | Each Learned entry goes to a check, a rule, the masterplan or a raw piece; secret-scanned; a lesson line blocks automatic merge. | DN Learning; D34; S17c | Plan |
| Run summary block | Each piece's final status and module, kickbacks by sub-state, attempts, CI rounds, budget, who merged. | S9c | Plan |
| Behaviour deltas | `## Behaviour change` entries `ADDED`, `MODIFIED`, `REMOVED`, applied at the merge, repeatable; a conflict kicks back to spec. | DN Learning; D35; RN OpenSpec; S18b | Plan |
| Masterplan change applied on save | ABK applies the piece's masterplan change during the save. | ABK `section-builder/SKILL.md` step 8; `masterplan-changes.md` | Prose (replaced by deltas in S18) |
| Reviewer sees only the diff | Review the diff against `main` only; the whole tool is read once at launch. | ABK `second-opinion/SKILL.md` | Prose |
| Speaking for the person | Comments or replies to colleagues wait for a yes on the words; bookkeeping needs none. | ABK `pieces.md`; `speaks-for-the-person.sh` | Prose |

### 1.8 Done (merged)

| Item | What it is | Source | Exists today |
|---|---|---|---|
| Closed means done or dropped | Completed by the merging pull request's `Closes` line, or not planned. | DN Issue states; D4 | Code: `fnd/gate.py` (never closes as completed itself) |
| Tidy labels | `gate.py tidy` takes state, sub-state and review labels off every closed issue after a merge. | S2a, S2d | Code: `fnd/gate.py` (`tidy`) |
| Checkpoint route closes on save | ABK: with no pull request the piece closes when saved, then tidy. | ABK `section-builder/SKILL.md` step 8 | Prose (see table 3) |
| Run close | `gate.py run close` right after the merge writes the run summary and status `merged`. | S9b | Plan |
| Merge seen outside a session | A merged run pull request found later is closed by the next board, `/what-now` or session start. | S16c | Plan |
| Branch deleted on merge | Founding sets `delete_branch_on_merge`. | ABK `setup-ai-build-kit/SKILL.md` step 10 | Prose |
| Worktree cleared | After the pull request closes and nothing is unsaved. | ABK `running-longer.md` | Code: `worktree.sh` |
| Attempt and held-out branches | Kept on the computer, named in the closing line with the removal command. | S11 | Plan |
| Piece folders cleanup | `/maintain` names `.agents/pieces/<n>/` folders closed over 30 days and gives the command. | SD6; S17b | Plan |
| Stale branch list | Branches whose work is in `main`, Git-confirmed apart from GitHub-only, with commands; never removed by the kit. | ABK `maintain/references/stale-branches.md` | Prose |
| Changelog line under the day | Folded at merge from the piece's file. | ABK WORKFLOW 2 | Code: `fold-changes.py` |
| Records current after merge | Each fact goes to one home: changelog file, masterplan, concept file, AGENTS.md rule, or the piece. | ABK `section-builder/SKILL.md` step 9 | Prose |
| Connections picture redrawn | A piece that adds or drops an outside connection redraws the masterplan picture. | ABK `section-builder/SKILL.md` step 9; `wiring-picture.sh` | Prose |
| Name the next piece from the board | Never worked out by hand from the issue list. | ABK `implement/SKILL.md` | Prose |
| Not hosted: merge means done | No live copy; a release on request. | DN Deployment; D50 | Prose: `ship/SKILL.md`; `not-hosted.sh` |
| Clean run definition | No revert, no bug naming its pieces within 7 days, reviewer agreed with the person. | DN Merging; D46; SD42; S17d | Plan |
| Kit metrics | Kickbacks by sub-state, reverts or bugs within 7 days, reviewer agreement rate. | DN Learning; S17c | Plan |

### 1.9 Live (deploy, health, rollback)

| Item | What it is | Source | Exists today |
|---|---|---|---|
| A merge to `main` goes live | Once the pipeline is set up. | DN Merging; D17 | Prose (ABK default is preview then `/ship`) |
| `/deploy` sets up the pipeline | Previews for branches, production on merge, rollback, secrets, health; run once and on a move. | DN Deployment; D17, D20; S14b | Plan (ABK `/ship`: Prose `ship/SKILL.md`) |
| Goes live line | `on every merge` or `not hosted`; missing means not set up. | S14b; ABK `merge.md` | Prose (ABK has a third value `through /ship`) |
| Live address line | `Live address: <https>` marks a first deployment done. | S13a | Plan |
| First deployment | Forces `review:person` and runs first-launch checks once. | DN Review; D8; S13a, S14b | Plan (ABK Prose: `merge.md` first-launch checks) |
| Recipes | One stack paired with one host, eight sections each with how it works, how checked, who runs it. | ABK `ship/references/recipe-format.md`; PHILOSOPHY Recipes | Prose + Code: `.agents/tools/check-recipes.sh` (kit repo) |
| Who runs a check | The kit; a companion or the person with result read back; a person looking. | ABK `recipe-format.md` | Prose |
| Recipe as the only place products are named | Hosting, data and deploy products appear only in recipes and the README. | ABK PHILOSOPHY; `hosting-request.sh` | Prose |
| Preview address field | Per branch and commit, per pull request, or none with a local checkout fallback. | DN Deployment; S14c | Plan |
| Preview data | Throwaway seeded database or host branching; never real data. | DN Deployment; D49 | Plan |
| Shared preview database at 1.0 | Supabase free plan, one shared preview database reset and seeded; automatic merge stays off. | SD21; S14c | Plan |
| Previews keep their own data line | Proven by a dated real run before a recipe can earn automatic merge. | S13b | Plan |
| Preview smoke test | Requests the `Smoke:` paths on the run's preview before automatic merge. | DN Merging; D30; S13b | Plan |
| Preview sign-in | The recipe's way past preview sign-in, recorded with a date on the person's yes. | S13b | Plan |
| Deploy wait | At most 10 minutes for a preview or for production to serve the merge commit. | S13 Decided | Plan |
| Health after each merge | Wait for production to serve the commit, run the recipe's health check. | DN Merging; D30; S13c | Plan |
| Rollback on failed health | The kit rolls back with the recipe's command, reads health again, files a bug piece. | DN Merging; D30, D38; S13c | Plan |
| Rollback the kit cannot run | No rollback; the bug is filed; automatic merge never turns on for that recipe. | SD19; S13c | Plan |
| After a rollback | Automatic merge off until the bug closes. | S13c | Plan |
| Irreversible data change | Always the person's merge, after a backup taken before the migration. | DN Merging; D48; S13c | Plan |
| Migration before the build | The recipe's going-live migration step runs first when the diff adds a migration. | S14c | Plan |
| Migrations only add | Except a dropping migration after the required backup. | S14c | Plan |
| Deploy once | Read the whole output or the host's list before any second deploy; a second deploy is announced as moving the rollback target. | ABK `ship/SKILL.md`; `ship-merges-and-deploys-once.sh` | Prose |
| Rollback possible, not tried | The rollback line says it is possible and not tried. | ABK WORKFLOW 9 | Prose |
| A check not done is a warning | Said once, written in the changelog, the launch goes on; the one wait is the address. | ABK `ship/SKILL.md`; `ship-runs-recipe.sh` | Prose |
| Settings the kit can read | Read a setting itself with public addresses or browser keys before asking. | ABK `recipe-format.md`; `second-opinion/SKILL.md` | Prose |
| Request record | The tool should keep a plain record of each request without personal data; said once if missing. | ABK `ship/SKILL.md`; `request-record.sh` | Prose |
| Monitoring caution | Said once unless somebody already receives alerts. | ABK `ship/SKILL.md` | Prose |
| Hosting request | For a server somebody else runs: eight fields, names only, carried by the person. | ABK `ship/references/hosting-request.md` | Prose |
| Secret location | Where a secret lives is recorded, never its value; unknown is never called absent. | ABK `ship/SKILL.md`; `secret-location.sh` | Prose |
| Live service changes wait for a yes | Except the recipe's own commands. | ABK WORKFLOW 9 | Prose |
| Launch records save route | One records pull request per launch, merged on its own yes; never pushed to `main`. | ABK `ship/SKILL.md` | Prose |
| Not hosted release | Names changes since the last release, runs evidence and review, proposes next minor, releases on a named yes. | DN Deployment; D50; ABK `ship/SKILL.md` | Prose |
| Run went live notification | Sent once per run when its status becomes merged on a hosted project. | DN Boards; D32; S16c | Plan |
| Evidence run and launch review | Full evidence run and independent review at first deployment. | ABK `ship/references/evidence-run.md`; S14b | Prose |
| Build with care at launch | The person's caution or the recorded acceptance; `/deploy` only reports area status. | ABK `ship/SKILL.md`; S14b | Prose |
| Handover | Prepared on request for an area or the whole build. | ABK `ship/templates/handover.md` | Prose |
| Graduation | Records what would have to change to move up a path. | ABK `ship/SKILL.md` | Prose |
| Plan terms | A recipe's dated line on who a free plan is not for, said only to work teams. | ABK `recipe-format.md`; `founding-menu.sh` | Prose |
| Real runs | One recorded real run per loop module and one `/deploy` per recipe before 1.0. | DN 1.0; D26; S20c | Plan |

---

## 2. Cross-cutting items

| Item | What it is | Source | Exists today |
|---|---|---|---|
| **GitHub store** | Issues are the pieces; labels the states; sub-issues the parts; blocked-by links the dependencies; pull requests the changes; comments the bookkeeping. | DN Issue states; ABK WORKFLOW 2 | Code: `fnd/gate.py` |
| Hidden markers | `loop:gate`, `loop:contract`, `loop:review`, `loop:person-verdict`, `loop:review-request`, `loop:lesson`, `loop:drift`. | Epic Names; S2, S6, S8, S16, S17 | Code: first two in `fnd/gate.py` |
| Bookkeeping needs no yes | Labels, claims and the kit's own comments go on without asking. | ABK `pieces.md`; `speaks-for-the-person.sh` | Prose |
| Local printout | `plan.local.md`, a git-ignored photocopy, never edited, with its age when GitHub is down. | ABK WORKFLOW 2; `pieces.md` | Code: `fnd/plan-refresh.sh` |
| Unreachable GitHub | The gate changes nothing and exits non-zero; work on a claimed piece continues; nothing new starts. | S2a; ABK `implement/SKILL.md` | Code: `fnd/gate.py` |
| Codex GitHub launcher | Lets a Codex session use the stored login without saving it. | ABK WORKFLOW 2; `codex-github-auth.sh` | Code: `setup-ai-build-kit/scripts/codex-with-github.py` |
| **Labels and sub-issues** | 26 kit labels: 4 `state:`, 6 `shaping:`, 2 `review:`, 3 `type:`, 4 `loop:`, 7 subjects; created once, colours accepted. | S2a; SD35 | Code: `fnd/gate.py` (`labels`) |
| Dimension prefixes | So a deny rule and the hook match a family by prefix. | S2 Decided | Code |
| Default GitHub labels deleted at founding | Only at founding, before any issue exists. | ABK `setup-ai-build-kit/SKILL.md` step 10 | Prose |
| Parent carries no state | Its parts carry the states; capture and move refuse a parent. | DN Issue states; S2a | Code: `fnd/gate.py` |
| Old-model labels reported | `idea`, `ready`, `parked`, `needs-` and others are named, never moved. | S2a, S2c | Code: `fnd/gate.py` |
| The kit's own issues keep old labels | Until after v1.0. | SD4; D55 | n/a |
| **Gate** | One script moves every state, checks the condition, writes labels and run record in one step, refuses otherwise. | DN Issue states; D9; S2a | Code: `fnd/gate.py` |
| Transition table | One row per move, read by the rehearsal so a new row must be tried both ways. | S2a; `gate-script.sh` | Code: `fnd/gate.py` (TRANSITIONS) |
| Read twice | Read to check, read again just before writing; refuse if another session moved it. | DN Issue states; S2a | Code: `fnd/gate.py` |
| Refusals name the next action | Each refusal prints what failed and a `next:` command; passes print one line. | DN What a machine enforces; D46; RN Harness | Code: `fnd/gate.py` |
| Report | Names pieces with no state, two states, wrong sub-label, old labels, missing hook. | S2a | Code: `fnd/gate.py` (`report`) |
| Person outranks the gate | A person's label change is reported, never undone. | DN Issue states; S2 Decided | Code |
| Gate subcommands planned | `result`, `switch-module`, `stop-check`, `review`, `integrate`, `run start|pause|resume|abandon|close`, `merge`, `push`, `ask-review`. | S2 consistency notes; S7 to S16 | Branch (result, switch-module, stop-check); rest Plan |
| State guard hook | Refuses Bash and GitHub tool calls that change a state, sub-state or review label; lets anything unreadable through. | S2b | Code: `fnd/state-guard.sh` |
| Deny rules | State-label writes, push to `main`, force push, recursive delete, reflog expire, gc prune, hard reset, clean, Edit on piece records. | S2b; ABK `blocked-commands.md` | Code: `fnd/claude-settings.json` |
| Refused command means stop | Say which command and what it was for; never reach the same result another way; give it to the person. | ABK `blocked-commands.md`; `refused-commands.sh` | Prose |
| Gate files copied beside the gate | Every script the gate or printout calls is copied into `.agents/tools/`, each kept lint-green. | SD5; SD7 | Code: `setup-ai-build-kit/scripts/bootstrap-project.sh`, `place-plan-helper.sh` |
| **Permissions and autonomy policy** | Settings in `.agents/loop-settings.json`: attempts, piece budget, review rounds, at_once, run budget, CI rounds, merge, deploy wait. | DN Computer resources; S7, S8, S9, S10, S13 | Branch: `templates/loop-settings.json` (attempts, budget) |
| Per-computer settings | `.agents/loop-settings.local.json`, git-ignored, for caps, reserve, thresholds, timeouts, models, Codex hook review date. | S10b; S19 | Plan |
| Policy set before the run, never edited by agents | The person approves the autonomy policy once; agents read it and never loosen another agent's limits. | Lessons c5, p3 | Plan (new) |
| Decide or park | A question is answered by the run when the answer is undoable, keeps settled decisions, and is recorded and flagged; otherwise park the piece and continue. | SD50, SD51; Lessons p1 | Factory only (coordinator brief) |
| Hard stops | Money, real accounts, credentials, account or repository settings, data that cannot be restored, going public, a release, three failed attempts, a refused command. | SD51; Lessons What walk away means | Factory only |
| Decisions record and morning review | Each decision under `## Decided` marked for review, also in one list; undoing one is one command. | Lessons p2; SD51 | Plan (new) |
| Sandbox and network allowlist | Native sandbox on, allowlist from the recipe plus GitHub hosts; `strictAllowlist` offered in the person's own settings. | DN Safety boundary; D31; SD38; S15a | Plan |
| Sandbox line | Capability profile says on with allowlist, on without host fence, or not available; the latter two keep automatic merge off. | SD22, SD38; S15a | Plan |
| Commands outside the sandbox | `gh`, recipe tools, the exact critic call; excluded scripts run only what the kit names. | SD40, SD47; S15a | Plan |
| Code under test runs outside the fence | Said plainly; sandboxing it is after 1.0. | SD47 | Plan |
| Env read refusals | Every ignored env file except `.agents/app/.env.local` is unreadable to every session. | SD39; S15b | Plan |
| Push token | Repository-only fine-grained token at `~/.config/ai-loop-kit/<owner>-<repo>.token`, held by the gate, never read by builders. | DN Safety boundary; D46; S15b | Plan |
| `gate.py push` | Refuses `main` always; in a run pushes only the run's branches. | S15b | Plan |
| Force-push deny rules | From the overnight batch, arriving with the safety boundary. | DN Projects founded; S15b | Code: `fnd/claude-settings.json` (force push already denied) |
| No stored logins | Use a tool's own commands and browser keys only. | ABK `no-stored-logins.sh` | Prose |
| Own-computer work boundary | Nothing installed, replaced or removed outside the folder without a yes naming what, where and how to undo. | ABK `change-triage/SKILL.md`; `own-computer-work.sh` | Prose |
| **Watchdog** | A scheduled job outside any chat session reads the heartbeat's age, resumes or restarts the coordinator, and notifies when it gives up or the wait is long. | Lessons c3, c7, p5 | Factory only: `.agents/tmp/v1-factory/watchdog.sh` (Orca-specific) |
| Heartbeat for the coordinator | The coordinator writes a heartbeat at every step. | Lessons p5 | Plan (builder heartbeat Plan in S10) |
| Pre-walk-away check | One command reports awake, mains power, free memory and disk, and the stops it can foresee. | Lessons p7 | Plan (new) |
| A real stop does not freeze the run | Notify, then take any piece that does not depend on the stopped one. | Lessons c6, p6; SD48 | Plan |
| **Logs** | `progress.md` per step, `activity.jsonl`, evidence, forced, reviews, attempt notes, gauntlet records, watchdog log, assistant change log with backups, a short end-of-run report. | ABK `running-longer.md`; S6, S8, S16; Lessons p8 | Partly Code (evidence, forced); rest Plan |
| Session log link per piece | Each piece's board entry links its session log and lists what it could not check. | DN Boards; D32; S16a | Plan |
| **Board** | One status file `.agents/board/status.json` from issues, run records and activity; written atomically. | DN Boards; D22; S16a | Plan (printout Code: `fnd/plan-refresh.sh`) |
| Shaping board | Needs you now first (questions, prototypes, references, kickbacks, reviews owed, run PRs to merge), then sub-state columns and ready. | DN Boards; S16a | Plan |
| Loop board | Each run's status, times, counts, preview address, budget; each piece's module, attempts, progress, log link, could-not-check. | DN Boards; S16 | Plan |
| Buttons copy commands | The page runs nothing; buttons copy `/shape <n>`, `/implement <numbers>`, pause, continue, stop. | SD24; S16b | Plan |
| Local page and live artifact | Self-contained HTML, reload every 30 seconds in a run; on Claude also a live page. | DN Boards; D22; S16b, S16c | Plan |
| `/what-now` | Leads with gate report findings, broken, failing, unshaped-in-build, notes count, waiting reasons, person's own pieces, unfinished run, person's steps, version line; at most three things; recap. | ABK `what-now/SKILL.md` | Prose |
| **Notifications** | Exactly four: a piece needs review, a run paused, a piece kicked back, a run went live; once per event. | DN Boards; D32; S16c | Plan |
| Notifier | `osascript` on a Mac, `notify-send` on Linux; the board is the fallback. | S16c | Plan |
| Notify on long waits | When the run has waited for the person longer than a set time, or the watchdog gives up. | Lessons p5 | Plan (new) |
| **Setup and founding** | Resume safely, orientation, capability check, fresh or adopt, test the need for software, interview, fit check, masterplan, review, ownership, cut the plan, stand up. | ABK `setup-ai-build-kit/SKILL.md` | Prose + Code: `bootstrap-project.sh`, `check-tooling.sh` |
| Founding ends stood up | No step is a gate; unneeded answers become open questions; "get on with it" takes the guesses. | ABK `setup-ai-build-kit/SKILL.md`; `founding-carries-on.sh` | Prose |
| Branch read before writing | Switch to the default branch when clean; never when work is unsaved. | ABK `setup-ai-build-kit/SKILL.md` step 0; `founding-branch.sh` | Prose |
| Setup notes | Each answer written to `.agents/tmp/setup-notes.md` before the next question; deleted once the masterplan holds them. | ABK `setup-ai-build-kit/SKILL.md` step 5; `setup-notes.sh` | Prose |
| Capability profile | Harness, file and shell access, Git, identity, repository, account, tests, walk-through eyes, review options, reach engine, hooks, subagents. | ABK `setup-ai-build-kit/references/capability-check.md` | Prose |
| Tooling report | Git, `gh`, python3 signed in; recipe tools; walk-through tools with install commands; old Git; kit repo origin. | ABK `check-tooling.sh` | Code: `setup-ai-build-kit/scripts/check-tooling.sh` |
| Need-for-software ladder | Cheaper options first; the case made once and recorded. | ABK `setup-ai-build-kit/SKILL.md` step 4 | Prose |
| Adopting existing code | Read first, interview against reality, pin behaviour with tests before changes. | ABK `setup-ai-build-kit/references/adopting.md` | Prose |
| Adopted CI is the project check | `Project check: <workflow>, job <name>`; the kit's steps offered once. | ABK `references/project-check.md`; `adopted-ci.sh` | Prose |
| Fit check and build paths | Consequence and ownership questions; three paths; six sensitive areas with default cautions. | ABK `fit-check.md` | Prose |
| Ownership answers become tasks | A no becomes a piece or a "How it stays running" fact, never a path move. | ABK `fit-check.md` | Prose |
| Masterplan review on Build with care | Independent method; skipped and logged otherwise; never waits. | ABK `setup-ai-build-kit/SKILL.md` step 8 | Prose |
| Coverage read | Every masterplan promise has a piece; includes permissions, data, connections and settled terms. | ABK `references/coverage-read.md` | Prose |
| Connections picture | Everything outside the tool it reaches, confirmed at founding. | ABK `setup-ai-build-kit/SKILL.md` step 7 | Prose |
| Sample data offer | For sign-in or growing history; a `Sample data:` line. | ABK `setup-ai-build-kit/SKILL.md` step 7 | Prose |
| Confidential folder | Ignored, recorded with handling rules, never in a run worktree. | ABK `setup-ai-build-kit/SKILL.md` step 11 | Prose + Code: `worktree.sh` refusals |
| Worktree links question | Which ignored files a build needs; asked once beside other work. | ABK step 11; `worktree-links.sh` | Code: `worktree.sh` (`candidates`) |
| Check floor | Type check and linter where the language has them; Test runner table. | ABK `references/check-floor.md` | Prose |
| Boundary rules | Offer to hold a named area boundary in the project check, worded in the person's sentence. | ABK `references/boundary-rules.md` | Prose |
| Placeholder check is red | Until replaced by real commands, by design. | ABK `fnd/checks.yml` | Code: `fnd/checks.yml` |
| Save identity fallback | "Local project user" label; never invent or copy an identity. | ABK step 11 | Prose |
| Founding save is a local checkpoint | Never a push or pull request. | ABK step 11 | Prose |
| Founding over AI Build Kit | List Build Kit's machinery, remove on one yes, rewrite the files it founded, read the old masterplan as input. | SD8, SD33, SD45, SD46; S22 | Plan |
| Kit version record | `kit|<version>|<commit>` line; first changelog line names it. | ABK step 7; `kit-version-record.sh` | Prose |
| Completion report | Leads with what is ready, says no code uploaded, ends on a clean cut. | ABK `references/completion-report.md` | Prose |
| One-command plugin or skill route | Plugin or shared installer, never both. | ABK README; `bootstrap-project.sh` | Code: `bootstrap-project.sh` |
| **Masterplan** | Present-tense description: header, build path, what and for whom, terms, permissions, connections, data, flow, correct, failure, how it stays running, out of scope. | ABK `templates/masterplan.md` | Prose |
| Compact masterplan | At most 500 visible words, a format marker, detail in owning documents. | DN 1.0; D26; S18a | Plan |
| Records files | `masterplan.md`, `docs/working-rules.md`, `docs/operations.md`, concept files listed in `docs/README.md`. | S18a | Partly Code: `templates/working-rules.md` |
| `records.py field` | Every script reads a record field through one router; a broken marker stops. | S18a | Plan |
| Trued-against stamp | ABK marks the masterplan as checked; S18 replaces it with a `records-review` line written only after a complete review. | ABK `masterplan-changes.md`; S18b | Prose (to be replaced) |
| Masterplan constraints as machine rules | With fix messages and a baseline that may only shrink. | DN Learning; D35 | Plan |
| AGENTS.md as a short index | Under 200 lines; sections of 12 lines or fewer pointing at owners; no dates, issue numbers or code names. | ABK `agent-first-records.sh`; `standing-instructions.sh` | Code: `fnd/checks.yml` ceiling step |
| Lessons section | At most 12 lines, no dates; reviewed after three months. | S17c; SD25 | Plan |
| Changelog | Dated, plain, assembled from per-piece files. | ABK WORKFLOW 2 | Code: `fold-changes.py` |
| **Recipes** | Two recipes (Next.js with Supabase on Vercel or Coolify), shared parts, menu at founding with one recommended. | ABK `ship/recipes/`; `founding-menu.sh` | Prose |
| Founding menu record | `founding-menu|<date>|<files>` so later recipes can be offered. | ABK step 11 | Prose |
| Offer a move onto a recipe | Monthly, once, never required; a yes becomes a piece. | ABK `maintain/SKILL.md`; `offer-recipe-move.sh` | Prose |
| Recipe proven by a real run | Joins the menu only after rehearsals and one recorded real run. | ABK `recipe-format.md`; `recipes.sh` | Code: `.agents/tools/check-recipes.sh` (kit repo) |
| New recipe fields | `Network allowlist:`, `Preview address:`, `## Preview data`, `## Local app`. | S14c; S15a | Plan |
| **Area map** | `## Areas` in `docs/working-rules.md`, every folder claimed, at most one `sensitive:` and one `boundary:` line per area. | DN Reach; D40; S5 | Code: `fnd/area-map.py`, `templates/working-rules.md` |
| Area map in the project check | Red on an unclaimed folder, a missing path, a double listing, a dangling sensitive name. | S5 | Code: `fnd/checks.yml`, `area-map.py check` |
| Exempt paths | Hidden top-level folders, root files, `changes/`. | S5 | Code: `area-map.py` |
| `none yet` areas | Named before code exists. | S5 | Code: `area-map.py` |
| Founding writes the map | Read back in plain words. | S5; S21 | Prose |
| Sensitive areas beside the map | Cautions and `Accepted:` lines move into `docs/working-rules.md`. | S18a | Plan |
| Richer engines wait for a pilot | Call graphs, language servers, stored indexes; the pilot also measures boundary accuracy. | DN Reach; D39, D47 | Plan |
| **Maintenance and health visits** | Monthly light visit, quarterly full visit, ending a tool. | ABK `maintain/SKILL.md` | Prose |
| Version check | `releases/latest` only; both numbers said every visit; a failed call never says up to date. | ABK `maintain/SKILL.md`; `stable-is-the-channel.sh` | Prose |
| Update route | Plugin, Agent Plugins or `npx skills add`, never `npx skills update`; count the skills. | ABK `maintain/SKILL.md`; `shared-route-adds.sh` | Prose |
| Refresh copied scripts | Gate and helpers refreshed from the installed skills after an update. | SD7; ABK `place-plan-helper.sh` | Code: `setup-ai-build-kit/scripts/place-plan-helper.sh` |
| Check-up cadence | Session start reminds after a month or 20 changes on `main`, whichever first. | ABK `session-start.sh`; `check-up-counts-work.sh` | Code: `fnd/session-start.sh` |
| Records put right | v1 `/maintain` absorbs `/sync`: red `main` first, uncommitted work left alone, stale pieces after 30 days, document names read, coverage read, fold, run folders removed. | ABK `sync/SKILL.md`; S17a | Prose; Code: `sync/scripts/document-claims.py` |
| Document read | Names stale files, links, commands and settings at their line. | ABK `sync/references/document-read.md` | Code: `sync/scripts/document-claims.py` |
| Quarterly reads | Copied code, unused code and dependencies, structure loops, document bloat; at most three proposals. | ABK `maintain/references/*`; S17d | Prose + Code: `maintain/scripts/document-bloat.py` |
| Drift reads after runs | Every 5 merged runs instead of quarterly. | SD25; S17d | Plan |
| Offer of automatic merge | When the 5 most recent counted runs are clean, reads no worse, protection holds. | DN Merging; D37; SD42; S17d | Plan |
| Reviewer calibration | Show each disagreement and propose a `## Project rules` change to the reviewer, on a yes. | DN Review; D46; S17c | Plan |
| Guides and sensors list | `gates.md` lists every gate with its kind; only guides can be switched off with `KIT_GUIDE_OFF`. | DN What a machine enforces; SD41; S17d | Plan |
| Guide removal replays | Run once per guide on the release commit. | SD34; S23 | Plan |
| Dependency and vulnerability update | Monthly, applied on approval. | ABK `maintain/SKILL.md` step 9 | Prose |
| Alerts and bills | Read once live; anything real becomes a piece. | ABK `maintain/SKILL.md` step 10 | Prose |
| Backups and owners | Verify backups and the named operational owner. | ABK `maintain/SKILL.md` step 11 | Prose |
| Fit check rerun on growth | When reliance has grown. | ABK `maintain/SKILL.md` step 12 | Prose |
| Ending a tool | Export data, tell people, revoke access, switch off services, confirm billing stopped, archive. | ABK `maintain/SKILL.md` | Prose |
| **Multi-agent support** | Claude Code first with gates as hooks; Codex the same scripts as hooks and rules; others the shaping core and one piece at a time. | DN Platforms; D23 | Partly Code (Claude hooks) |
| Codex hooks | Session start, state guard and end-of-turn check through `codex-hook.sh`. | S19a | Plan |
| Codex rules file | `.codex/rules/ai-loop-kit.rules` from the blocked list; prompt decisions for writes in the person's name. | S19b | Plan |
| Codex run profiles | Builder and read-only permission profiles with the same allowlist and read refusals. | S19b | Plan |
| Codex grade | Stays expected to work until a recorded run. | S19; ABK `compatibility-grades.sh` | Prose |
| Compatibility grades | Tested, expected to work, experimental; raised only by a recorded run. | ABK `docs/COMPATIBILITY.md` | Prose |
| Harness capability routes | Which agents can start a fresh builder, reviewer or checker. | S7a | Branch: `section-builder/references/task-context-capabilities.md` |
| **Naming** | The product, plugin, marketplace, founding command `/setup-ai-loop-kit`, record files `.ai-loop-kit-*`, recovery refs. | DN The name; D43, D53; S22 | Plan |
| Loop module, never implementation mode | Label `loop:`. | D42 | Code: `fnd/gate.py` |
| Marker says `project-records` | Not the product name. | S18 Decided | Plan |
| Commands | `/setup`, `/shape`, `/implement`, `/deploy`, `/what-now`, `/maintain`. | DN Commands; D21 | Partly (eight ABK commands on `main`) |
| **Release** | No release until v1 is complete; v1.0.0 first; public at release on a yes. | D52, D59; SD26; S23 | Plan |
| 1.0 bar | Model complete with four modules, runs, kickback, `/deploy`, two boards; real runs; compact masterplan. | DN 1.0; D26 as amended | Plan |
| 1.0 promise | Commands, records and way of building do not change until 2.0. | DN 1.0; S23 | Plan |
| Stable channel | Installers read `stable`, created at the first tag by `promote-stable.sh`. | ABK `stable-is-the-channel.sh`; S23 | Code: `.agents/tools/promote-stable.sh` (kit repo) |
| Release labels | Every pull request carries `release-major|minor|patch`. | Epic standards | Code: kit workflow `release-label.sh` |
| Version stamp | Three version-bearing files move together. | ABK `version-stamp.sh` | Code (kit repo) |
| Pre-release run as a person | A walked v1 day on a preview before release. | S23; ABK `pre-release-run.sh` | Prose (kit repo) |
| Replay harness | Scripted scenarios, held-on-every-run per model, v1 fixture. | DN Learning; S20 | Code (kit repo, pre-v1) |
| **Kit-building standards** | Five questions, three places, rule-shape checks, no issue numbers in tracked files, no attribution lines, humanizer. | Epic standards; ABK PHILOSOPHY | Code: `.agents/tests/lib/rule-shape.sh`, `validate-kit.sh`, `.githooks/commit-msg` |
| Plain words to the person | Never asked to read code or logs; one line per check; refusals say what to do next. | DN Who it is for; D51; PHILOSOPHY | Prose |
| Process level by consequence | The least process that changes an outcome; every rule declares where it applies. | ABK PHILOSOPHY | Prose |

---

## 3. Does not fit or needs a decision

| Item | The conflict | Recommendation |
|---|---|---|
| Idea as a state | The target model has Idea; the design note and D4 say captured work is `shaping:raw` and there is no idea label. | Keep Idea as the backlog state name and drop `raw`, or keep `raw` and drop Idea; do not have both. |
| Live as a state | The target model has Done then Live; the design note closes the issue at merge and "a merge goes live". | Make Live a run or deploy status (health passed), not an issue state; the issue closes at Done. |
| Done separate from Live | For hosted projects merge equals live; for not-hosted projects there is no Live. | Keep Done as the issue end; record Live per run with health and rollback. |
| Where integration happens | Design note integrates in Building (integrated = in-review); the target puts integrate in Review. | Integrate in the orchestrator before Review; Review judges per piece; the run's pull request is the last gate. |
| One pull request per run versus per piece | Design: one integration pull request per run; ABK: one per piece with stacks. | Pick one; the integration branch fits a state machine better and avoids stacked merges. |
| Review sub-labels | `review:auto` and `review:person` versus a single Review state with a reviewer field. | Keep one Review state; hold who reviews in the run record and forced reasons. |
| Three build paths | ABK's paths decide save route and ceremony; v1's design is silent and keeps sensitive areas. | Drop paths; keep sensitive areas and per-piece consequence; every piece uses a pull request. |
| Checkpoint route and Explore privately | No pull request, closes on save, cannot use runs or review. | Drop, or keep as a "local only" project mode outside the state machine. |
| Parked | Removed by S2; settled decision 51 and Lessons reintroduce "park" for the coordinator. | Park means kickback to shaping with a Kickback section and a flag; no label. |
| Pre-approval for a run | ABK's six conditions per run versus v1's merge policy in settings. | Drop pre-approval; use the merge policy setting only. |
| Person's try opt-in | The design note says the try-it opt-in does not carry over; ABK has `Waiting on you: try it` and `check-myself`. | Drop; a person who wants to look asks for `review:person`. |
| `through /ship` and promote | Removed by S14; ABK's default is preview then `/ship` promotes. | Drop; merge goes live once `/deploy` set the pipeline. |
| Masterplan change versus behaviour deltas | ABK applies masterplan changes on save; S18 applies deltas at the merge. | Keep deltas at merge only. |
| Trued-against stamp | Replaced by a review checkpoint in S18. | Drop the stamp. |
| Changelog fragments and deltas | Two record mechanisms at merge. | Keep both: deltas for current behaviour, fragments for history. |
| Founding over AI Build Kit | Settled decisions 8 and 33 add a removal step; a from-scratch product may not need it. | Keep a small detector and a one-yes removal; no migration. |
| Old-project migrations in `/maintain` | Large ABK section for older projects. | Drop entirely. |
| Fix escalation | ABK has six routes after three failures; v1 has two kickbacks. | Use the two kickbacks (research, clarify). |
| Hard versus easy open choice | ABK splits by reversibility; v1 says anything needing a person is a kickback; Lessons says decide when undoable. | One rule: decide if undoable and within settled decisions, record and flag; else park. |
| Field that does not apply | ABK writes "does not apply, because"; contract v2 leaves the field absent. | Absent, since the lint reads the module. |
| Readiness list in prose | Fifteen items judged by a session; some are machine-checkable. | Move every machine-judgeable item into the lint; keep the checker for criterion matching and open choices. |
| Native goal mode | ABK treats it as a run; S11 says its judge never ends a piece. | Drop native goal mode support. |
| Same-session review fallback | ABK allows it on Explore privately; S8 forbids it. | Forbid. |
| Parts sharing a branch | ABK parts share one branch and pull request; v1 integrates each. | Integrate each part like any piece; parent closes when parts close. |
| Worktrees only on Claude Code | Others build in one folder. | Make worktrees universal where Git is at least 2.17. |
| Printout and board | `plan.local.md` and `status.json` overlap. | One status file; the text view is generated from it. |
| Four notifications only | Lessons wants more: long wait for the person, watchdog gave up. | Allow these two more, or fold them into "run paused". |
| Automatic merge on free private repositories | GitHub offers no protection there. | Keep: person merges, said at setup. |
| Shared preview database at 1.0 | Previews do not keep their own data, so automatic merge never turns on at 1.0. | Accept for 1.0; say so plainly. |
| No sandbox computer | Run still starts, automatic merge off. | Keep. |
| Codex parity | Large slice; Codex stays "expected to work". | Defer past 1.0, ship Claude Code only. |
| Factory fast flow | `v1-integration` branch, squashed parts, local checks; a build process, not product. | Do not copy into the product; the product's integration branch is per run. |
| Answer marker in the body | Hash of an answer section kept in the issue body. | Keep; it is small and tested. |
| Length limits per type | 80, 120, 250 lines, untested in real runs. | Keep as defaults in settings. |
| Outside critic from another vendor | Codex as critic needs dated agreement. | Defer past 1.0. |
| Mutation testing only where installed | Inconsistent strength across projects. | Keep; never install; say so once. |
| Session-start reminder | Monthly visit cadence. | Keep, but fold into the board's "needs you". |
| Screen rules | Large prose skill. | Keep as a named check a bar can call. |
| 500-word masterplan | New record format and router. | Keep; it fixes the record format for 1.0. |
| Six commands in a state machine | Commands become manual overrides of the loop. | Keep the six; each is a door into a state. |
| Lessons in AGENTS.md | Model-written instructions measurably lower success. | Promote lessons to checks first; cap the AGENTS.md section. |
| Products only in recipes | A rule the from-scratch kit inherits. | Keep. |
| Research expiry | The target model wants it; no source defines it. | Decide a rule (date on each research claim, age limit) or drop. |
| Auto-pick versus person picks | Design: the person picks or says all ready. | Keep the person's pick; "all ready" as one option. |
| Two runs at once | Refused by S9. | Keep refused for 1.0. |
| Question box from the overnight batch | A prose rule with a check. | Keep as the one way to ask the person. |
| Group built at the same time (ABK) | ABK asks a question before the run; v1 asks nothing and sizes to the computer. | Drop the question; use `at_once` from settings. |
| Sub-states as separate loops | The target model treats Shaping as one state with an exit gate; the sources need six sub-states with their own entry and exit conditions. | Model each sub-state as its own small loop under Shaping. |

---

## 4. What the target model is missing that the sources say matter

- **Shaping sub-states with their own rules.** Who must be present (research alone, clarify and prototype need the person), the answer recorded before any move, and the new-question rule that stops a piece going round (DN Shaping; SD49).
- **Sensitive areas, the risk notice and recorded acceptance.** Given in shaping, the person's exact words, a records pull request merged before the piece leaves clarify, and a run never accepting for the person (DN Shaping; SD31).
- **Kickback as a first-class route with targets.** From Building and Review back to a named sub-state, with a Kickback section, branch kept and the run carrying on (DN Kickback; D16).
- **The given-back moves.** Building or Review back to Ready when a run ends early, is abandoned, a dependency was kicked back, or memory pressure stopped a builder (S2a; S10b).
- **Builder end statuses.** Five statuses with one route each; environment failure never kicks back (DN Review; D29).
- **Frozen contract, not only a frozen judge.** A contract changed during the build is a kickback (DN The frozen bar).
- **Runs as a unit.** Run record, run statuses, run budget, CI round cap, pause, continue, stop, resume from the record (DN Runs; S9).
- **Integration rules.** One at a time on the combined head, no agent conflict resolution, bisect and revert, recheck against `main` before every merge (DN Runs; D30).
- **Earned automatic merge.** Merge policy, clean-run counting, GitHub protection read, slow signal from drift reads (DN Merging; D37).
- **Red `main` gate and the bug fast path** (D38), and **the first-upload consent** with the kit-repository guard (S9a; ABK first upload).
- **Irreversible data changes.** Marked in shaping, always the person's merge, backup before the migration (D48).
- **Safety boundary.** Sandbox and allowlist, scoped push token held by the gate, untrusted text as data, dependency age and licence, secret scan, env-file read refusals, ask rules on writes in the person's name (DN Safety boundary; S15).
- **Walk-away essentials from the first night.** One decide-alone rule, a decisions list for the morning with one-command undo, autonomy policy set by the person before the run, a mailbox the coordinator reads, a pre-walk-away check, a stop that does not freeze independent work (Lessons p1 to p7).
- **Learning loop.** Learned per piece, lessons promoted at run close as checks first, reviewer calibration, kit metrics, guides tested by removal (DN Learning; D34, D46).
- **Records model.** Compact masterplan, behaviour deltas at merge, one home per fact, area map kept by the project check (S5; S18).
- **Not-hosted projects.** No Live state; a release on a yes instead (D50).
- **Local app per worktree and throwaway environment** so parallel builders never share a port, database or real key (S14c; SD30).
- **Plain-words interaction.** The question box, one-line reports, refusals that name the next action, never asking the person to read code (DN What a machine enforces; D51).
- **Out-of-loop routes.** Work on the person's computer and using the tool on content get no piece; speaking for the person needs a yes (ABK change-triage; pieces.md).
- **Usage-limit handling.** Pause until the allowance resets, and say that N builders spend it N times faster (DN Computer resources).

---

## 5. Existing code on `main` worth borrowing

All paths are on `main`. Each is tested by a rehearsal in `.agents/tests/`.

| Code | What it gives a new product | What it would need to shed |
|---|---|---|
| `fnd/gate.py` (2,205 lines) | The transition table, read-twice writes, answer marker and fingerprints, refusals with `next:`, contract hash with trusted author, evidence record with hash chain, the gate running checks itself, retry-as-failure, test-strength breakages, forced reasons, run status written with labels. | Split into modules (labels, moves, contract, evidence, guard); drop `plan-refresh` coupling, the AI Build Kit old-label list, checkpoint assumptions, the always-`review:person` stub; move from issue-body parsing helpers to one shared contract parser with the lint. |
| `fnd/ready-lint.py` (1,231 lines) | Required sections, module fields, reach fields, refused phrases, brief rules, length limits, crew caps, running acceptance checks in a temporary checkout with dependency install, assertion-versus-error from runner reports, ten-minute limit, exit codes. | Reading sensitive areas from the masterplan's build-path section, the `Touches:` case, the no-code special case if v1 requires code; share the parser with the gate. |
| `fnd/area-map.py` (362 lines) | `check`, `which`, `areas`; folder claiming, exempt rules, clear one-line errors. | Nothing major; rename the file it reads if records move. |
| `fnd/state-guard.sh` (112 lines) and `fnd/claude-settings.json` | Hook that refuses direct state-label writes, deny rules for push to `main`, force push, recursive delete, history clearing, piece records. | The session-start wiring if the board replaces it; the AI Build Kit wording. |
| `section-builder/scripts/bar-guard.sh` (284) and `test-guard.sh` (140) | Lists every change to the bar in seven kinds, named or not, including removal-only settings changes and moved tests. | Shell portability workarounds could move into Python beside the gate. |
| `section-builder/scripts/co-change.sh` (68) | The 200-commit co-change query. | Nothing. |
| `section-builder/scripts/bring-up-to-date.sh` (158) and `sync/scripts/fold-changes.py` | Take in `main` with a merge commit, undo stale folds, fold changelog files, safe exit codes on conflict, unreachable remote or unpushed commits. | The per-piece pull request assumption; adapt to the run's integration branch (`--base`). |
| `implement/scripts/worktree.sh` (743) | Open, resume, unsaved, tidy, leftovers, remove, port, candidates, links; never forced; other tools' worktrees left alone. | Linking `.env` (v1 gives runs no real secrets), reading `.ai-build-kit-maintenance`, Git older than 2.17 branch if dropped. |
| `fnd/session-start.sh` (187) | Check-up cadence by days or 20 changes, quiet otherwise, Claude hook output. | Fold into the board's "needs you"; rename record file. |
| `fnd/plan-refresh.sh` (547) | Board grouping logic, blocked-by reading, Needs attention. | Replace by `status.json`; keep only the grouping logic. |
| `setup-ai-build-kit/scripts/merge-ask-rules.py` (100) | Adds and removes the merge confirmation rules by key, keeping the person's entries. | Nothing; reuse the pattern for any settings key merge (deny rules, hooks). |
| `setup-ai-build-kit/scripts/check-tooling.sh` (246) | Tool and sign-in readiness, recipe tools, walk-through eyes with install commands, kit-repository origin guard. | AI Build Kit repository names. |
| `setup-ai-build-kit/scripts/bootstrap-project.sh` and `place-plan-helper.sh` | Copy foundation files without overwriting; place and refresh copied scripts on every visit; refuse links. | Plugin-plus-skills double-install detection specific to AI Build Kit. |
| `sync/scripts/document-claims.py` and `maintain/scripts/document-bloat.py` | Stale-name and duplicate-paragraph reads for the health visit. | `sync` paths; move into the health visit. |
| `fnd/piece-issue.yml` and `templates/working-rules.md` | The contract v2 form and the area map template. | Fields the new contract drops. |
| `.agents/tests/lib/rule-shape.sh`, `.agents/tests/lib/permission-matcher.py`, `.agents/tests/replay/fake-github/gh` and the `fake-host` stand-ins | Proving prose rules load-bearing, matching deny rules offline, a GitHub stand-in that models labels, blocked-by links and faults. | Old-model fixtures and scenarios. |
| `.agents/tests/gate-script.sh`, `ready-lint-rehearsal.sh`, `area-map-rehearsal.sh`, `frozen-bar-rehearsal.sh`, `bar-guard-rehearsal.sh`, `state-guard.sh`, `co-change-rehearsal.sh` | Rehearsals that drive the code above against stand-ins in throwaway repositories. | Assertions tied to AI Build Kit wording. |

Not on `main` but worth reading before rewriting: `implement/scripts/run.py`,
`attempt-note.py`, `recovery.py`, `section-builder/references/build-loop.md`,
`task-handoff.md` and `task-context-capabilities.md` on `v1-integration`
(slice 7 part a), and `.agents/tmp/v1-factory/watchdog.sh` with `state.json`
and `dashboard.html` (the factory's own coordinator tooling, tied to Orca's
terminal commands).
