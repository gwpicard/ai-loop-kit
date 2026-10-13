# Ledger: what the kit holds, and what waits to earn a place

This file is how the kit grows. Read `docs/ANGLE.md` first.

## The rule

- A feature enters the kit only when a real run shows it is needed.
- Write the failure in "Earned so far" below first: the date, the project,
  what went wrong, and which ledger entry answers it.
- The feature arrives with a test that reproduces that failure.
- Then mark the entry below as IN THE KIT.

## Earned so far

| Date | Seen in | What went wrong | Entry it earned |
| --- | --- | --- | --- |
| 13 Oct 2026 | the thin kit's own tests | A spec ID inside a test name (`test_D1_adds`) was not found, because `\b` treats `_` as a letter. | Ready gate: judge names a spec ID (fixed in the core) |
| 13 Oct 2026 | loop-test-thin, scaffold piece | The ready note said "the judge fails on main" for a scaffold piece, where the gate skips that check. The kit claimed a check it did not run. | Gate notes state only what the gate checked (fixed, with a test) |
| 13 Oct 2026 | loop-test-thin, first run | Claude Code warned that `Write(path)` and `MultiEdit(path)` deny rules match nothing; only `Edit(path)` rules count, and they cover every file tool. | Builder judge-file block uses `Edit(path)` only (fixed) |
| 13 Oct 2026 | loop-test-thin, shaping | The person's local `main` was not pulled after the setup merge, so the piece branch started from stale `main`. | Shape pulls `main` first and branches from `origin/main` (skill text) |
| 13 Oct 2026 | loop-test-thin, piece 2 | The builder rewrote `.gitignore` and dropped the kit's `.loop/` line. The judge could not see it, and the person missed it in the diff. | `.loop/` is ignored through `.git/info/exclude`, which builders never touch (fixed, with a test) |
| 13 Oct 2026 | loop-test-thin, pieces 4 and 5 | The gate ran only the piece's own judge. The person ran the whole project's tests by hand before merging, and shaping wrote "the existing tests must still pass" under Notes, which the gate never reads. | Must stay the same: an optional `Keep:` command that passes on main at ready and again after each attempt (in the kit, with a test) |
| 13 Oct 2026 | loop-test-thin, piece 8 | The pull request's "Closes" words closed the issue on merge, and `sync` only read open issues. The piece stayed in approval for good: the kit showed a false state. | `sync` reads closed issues too, and the gate never closes an issue twice (fixed, with a test) |
| 13 Oct 2026 | loop-test-thin, piece 12 | A piece with a contradictory judge failed three times and went back to shaping, as designed. Every builder said why ("D1 and D2 contradict each other; D2 is probably wrong"), but that stayed in local logs. The issue showed only test failures. | Each failed attempt's comment carries the builder's own words (in the kit, with a test) |

## Evidence collected, not yet enough to earn a feature

| Date | Seen in | What happened | Ledger entry it points to |
| --- | --- | --- | --- |
| 13 Oct 2026 | loop-test-thin, piece 2 | A builder changed a file outside the piece (`.gitignore`) and only the person could have noticed. | The fresh reviewer; a "nothing outside the piece changed" check |
| 13 Oct 2026 | loop-test-thin, piece 4 | Shaping recommended `~/.habits.json`, against the `./habits.json` decided while shaping the piece before. The person had to correct it. | One home per fact: a project decisions record that shaping reads |
| 13 Oct 2026 | loop-test-thin, piece 8 | Showing streaks in `list` would break three older tests, so the keep check would make the piece impossible. Shaping worked round it with a `--streaks` flag. There is no route for a deliberate change to old behaviour. | A piece may update older judges, with the person's acceptance |
| 13 Oct 2026 | loop-test-thin, pieces 8 and 9 | Shaping dropped a Done when item after the person approved the spec, without asking again. Its reason was sound. | The person approves the final spec text |
| 13 Oct 2026 | loop-test-thin, pieces 8 and 9 | Two pieces built in one run both changed `habits/cli.py`. They merged cleanly one after the other, and all tests passed on the combined main. No conflict yet. | Combined-branch integration (not earned) |
| 13 Oct 2026 | loop-test-thin, piece 12 | The first builder found the judge contradicts itself. Attempts 2 and 3 found the same thing (about 30 seconds wasted). No builder gamed the judge. | A "the bar is wrong" hand-back that ends the piece's attempts early |

## What is in the thin kit today

- The shape skill, the spec format, and the judge written during shaping.
- Six states and ten moves, held by the gate. Labels change only through it.
- The ready gate: the spec parses, the judge fails on main on an assertion,
  every spec ID shows in the failing output, the bar and the spec are hashed.
- The claim check: the spec has not changed since ready.
- The run: a worktree per piece, up to three fresh `claude -p` attempts, the
  gate runs the judge, a changed judge fails and is put back, a pass pushes
  the branch and opens a pull request, three failures send it back with
  `needs-you`.
- The person merges. `gate.py sync` moves merged pieces to done.
- The guard: no push to main, no force push, no recursive delete, no
  hand-written state label, no agent merge; builders never push, never run
  `gh` and never touch `.claude/` or `.githooks/`.
- Two layers already: the judge files are blocked from edits in the builder
  session, and the gate compares their hash.

## Known gaps, written down now so they are not forgotten

- The judge command comes from the issue body. On a public repository a
  stranger could file an issue with a harmful command. Trigger: before the
  kit is used on a repository that accepts outside issues.
- Gate records are issue comments. A person could forge one by hand. Trigger:
  a record that does not match what the gate did.
- The builder runs Bash with Claude Code's normal permissions plus the guard.
  There is no sandbox yet. Trigger: before any run is left alone.

---

## The original angle

The decided principles and the core idea, in the design's own words where
possible.

- Shaping is the work, and the build is a loop. The kit spends its effort
  before the build, so that a piece can then be built with nobody watching.
- Shaping removes every ambiguity from a piece, so that it can be built with
  nobody watching. The person can walk away while the work continues.
- The kit is a state machine. Every piece is a GitHub issue in exactly one
  state, and it moves only through gates.
- Each state is a loop with an entry gate, a work loop, an exit gate and
  kickback routes.
- The gate is the only mover. It runs each move's checks itself and never
  trusts an agent's word that a check passed.
- Every task is a goal with a judge. Build, fix, goal and gauntlet collapse
  into one build loop with different kinds of judge.
- Every judge must fail on today's main before a piece is ready, and fail for
  the right reason: an assertion naming the spec ID it proves.
- The judge and everything it rests on are frozen at ready and checked byte for
  byte. Removing, skipping, loosening or retrying a test to pass is a failed
  attempt, never a pass.
- Prefer deterministic checks and blocks over written instructions wherever
  possible. Hold every important rule in at least two independent layers, so
  one failing does not open it.
- A skill holds judgement and conversation. A rule that must hold lives in a
  script, a hook, a setting or the gate.
- Each attempt is a fresh, non-interactive session. Long sessions full of failed
  approaches get worse, and clean restarts win.
- The run is a plain script, not an agent. A builder cannot ask questions, so
  nothing can stand still waiting for an answer. Decide or park.
- Merging is never automatic by default. The person merges, or pre-approves a
  merge before one run, and even then only when every condition holds.
- One home per fact. Anything a check can hold is a check, not a sentence.
- v1 is written from scratch. The old kit is a source of ideas and of tested
  code to borrow, not a base to adapt. Claude Code only for v1.0.

## 1. Principles

- **Shaping is the work, the build is a loop**
  What: effort goes before the build so the build can run unwatched. Why: the person can walk away while work continues. Tier: CORE.
- **Deterministic checks over instructions**
  What: prefer scripts, hooks, settings and the gate to written rules. Why: a written rule can be ignored by an agent; a block cannot. Tier: CORE.
- **Two independent layers for every important rule**
  What: hold each rule in two of deny rules, hook, sandbox, token scope, git hook, gate, GitHub setting. Why: one layer failing must not open the rule. Tier: CORE for the main-branch rules; the full two-layer table is LATER. Trigger: an agent gets round a single guard in a real run.
- **One loop, many judges**
  What: acceptance tests, reproducing test, measurement and fresh critic share one build loop. Why: four separate loop modules were duplication. Tier: CORE for acceptance tests and reproducing test; measurement and critic are LATER. Trigger: the person has a metric or look-alike piece that tests cannot express.
- **Gate is the only mover**
  What: only the gate changes a piece's state, and it never trusts an agent's word. Why: agents can claim a check passed when it did not. Tier: CORE.
- **v1 from scratch, borrow tested code**
  What: old kit is an idea source; borrowed code is listed with its source and what it must shed. Why: the earlier build was slow and carried behaviour v1 replaces. Tier: CORE.
- **Claude Code only**
  What: gate and spec checks are plain scripts any agent or person can run. Why: Codex can then be added later as an extension. Tier: CORE.
- **Reader is a technical builder who directs agents**
  What: the person knows Git, branches and pull requests and never reads code. Why: sets the language and detail of everything the kit says. Tier: CORE (Proposed in the design).
- **Plain words, one line per check**
  What: the person is told things in plain words, never asked to read code or logs. Why: the person directs and does not read code. Tier: CORE.
- **Trust a check over an old instruction**
  What: when a check and a document disagree, say so plainly. Why: documents drift; checks run. Tier: CORE.
- **Free-plan honesty**
  What: on a free private repository there are no server rules, so local layers carry every rule and setup says so. Why: branch protection, rulesets and push protection are missing there. Tier: LATER. Trigger: the kit is installed on a repository where the person assumed GitHub protected main.
- **Earned complexity (the restart rule)**
  What: a feature returns only when a real run proves it is needed. Why: the earlier build kept 100 to 120 rehearsals and a 2,200-line validator green for behaviour v1 replaced. Tier: CORE.
- **Test the loop, not the words**
  What: verify the kit by end-to-end runs on a throwaway project and unit tests of the gate, not by checks that read documents for words. Why: a test that drives a piece to done fails when the loop breaks, not when a sentence moves. Tier: CORE.

## 2. States and moves

- **Seven states**
  What: shaping, ready, building, review, approval, done, dropped; one `state:` label each. Why: every piece is in exactly one place and moves only through gates. Tier: CORE for shaping, ready, building, approval, done; review and dropped LATER. Trigger: review as its own state is needed once there is integration and a reviewer; dropped when abandoned pieces clutter the board.
- **Exactly one state label**
  What: the gate refuses a second `state:` label. Why: one source of truth for where a piece is. Tier: CORE.
- **Shaping is one state, with a computed needs list**
  What: what a piece still needs is computed from the spec, not tracked by sub-state labels. Why: six sub-states (raw, research, clarify, prototype, spec, check) were replaced because a need clears only when its answer is written down. Tier: CORE in minimal form (missing fields listed); the full table of needs is LATER. Trigger: shaping stalls because nobody can tell what a piece still lacks.
- **The `needs-you` flag**
  What: a label the gate adds when a need only the person can answer exists, and removes when none remain. Why: GitHub's own list can then filter pieces waiting on the person. Tier: LATER. Trigger: the person misses a question parked on a piece.
- **Parked means one thing**
  What: waiting on the person inside the current state, with the flag set, while the run carries on. Why: scattered meanings of parked and stuck confused routing. Tier: LATER. Trigger: a builder needs an answer mid-run and the run would otherwise stall.
- **Usage-limit wait is a condition, not a state**
  What: waiting for reset sits inside building. Why: no extra state needed. Tier: LATER. Trigger: a run hits a usage limit and wastes attempts.
- **No other states**
  What: blocked, queued and idea are not states; blocking is a GitHub blocked-by link. Why: fewer states, one source for dependencies. Tier: CORE.
- **Parent issue with parts**
  What: sub-issues carry the states; the parent carries none and closes with its last part. Why: one state per piece. Tier: LATER. Trigger: a change is too large for one sitting and must split.
- **Fourteen numbered moves, all others refused**
  What: a fixed table of allowed moves; anything else is refused with the reason and the next step. Why: every way back must be named and counted. Tier: CORE for the forward moves (capture, ready, claim, build to approval, merge to done) and the send-back to shaping; the rest are LATER. Trigger: each extra move (back to ready, rebuild, reject one piece) is added when a real run needs that route.
- **Move 1: capture**
  What: new issue to shaping, in the person's words, no other checks. Why: capture must be cheap. Tier: CORE.
- **Move 3: ready back to shaping**
  What: the person pulls it back, the fingerprint changed, or the claim check found stale research. Why: a ready piece must still match what was agreed. Tier: CORE for the changed-fingerprint case.
- **Move 6: building to shaping**
  What: bar is wrong, 3 attempts used, or no real improvement. Why: a stuck build is a spec problem. Tier: CORE.
- **Move 7: back to ready, no attempt counted**
  What: environment block, run stopped, or a late answer; the spec is changed only by the gate. Why: faults of the machine must not eat the piece's attempts. Tier: LATER. Trigger: a builder fails for an environment reason and a good piece is wrongly sent to shaping.
- **Move 8: review back to building**
  What: a trial join went red, a conflict, or a review finding became a failing check. Why: the culprit goes back with the clash written on it. Tier: LATER. Trigger: the first run with two or more pieces whose results clash.
- **Move 9: review back to shaping**
  What: a review finding shows the spec was wrong. Why: bad specs must go back to the source. Tier: LATER. Trigger: reviewer finds a wrong spec, not wrong code.
- **Move 12: approval back to review**
  What: main moved or a piece was rejected, so the branch is brought up to date or rebuilt and checked again. Why: the tested tree must be the merged tree. Tier: LATER. Trigger: main moves between the check and the merge.
- **Move 13: closing or commenting on the pull request**
  What: sends pieces back with the reason; a comment naming one piece sends back only that piece. Why: there is no approve command, so rejection must be a plain act. Tier: LATER. Trigger: the person rejects one piece of a combined pull request.
- **Move 14: drop and reopen**
  What: close a piece with a reason; reopen into shaping. Why: rejected ideas should not be rebuilt by accident. Tier: LATER. Trigger: an abandoned idea is re-proposed or clutters the board.
- **Read twice, write once**
  What: the gate reads a piece to check, and again just before writing; if another session moved it, it refuses. Why: two sessions must not move the same piece. Tier: LATER. Trigger: two sessions claim the same piece.
- **Record and label written together**
  What: each move writes label and run record in one step; a failed label leaves the record unchanged. Why: labels and records must not diverge. Tier: LATER. Trigger: a label write fails mid-move.
- **Refusals print `next:`**
  What: each refusal says what failed and the command to run next; each pass prints one line. Why: agents and people need the next step named. Tier: CORE.
- **Reason on every move back**
  What: every backward move writes a reason on the issue. Why: history of why a piece went back. Tier: CORE.
- **Anti-circle rule**
  What: a move back to shaping must add a new need; a reason already on the piece is refused. Why: a piece must not loop on the same question. Tier: LATER. Trigger: a piece cycles between shaping and building on the same issue.
- **Repeat counter of 3**
  What: moves 7, 8 and 12 may repeat; after 3 of the same kind the piece goes to shaping with its history. Why: stops endless retry. Tier: LATER. Trigger: a piece bounces between building and review.
- **Gate-made spec changes re-fingerprint**
  What: when the gate edits the spec (a late answer), it takes a new fingerprint; only others' edits count as changed. Why: legitimate gate edits must not trip the changed-fingerprint check. Tier: LATER. Trigger: answers written by the gate after ready.
- **Human label outranks the gate**
  What: a hand-changed label is reported, never undone. Why: the person has the last word. Tier: LATER. Trigger: the person edits a label by hand and the gate disagrees.
- **Run stop returns building to ready**
  What: on stop, building pieces go to ready and keep their branch; review and approval wait. Why: a stopped run must lose no work. Tier: LATER. Trigger: a run is stopped mid-build.
- **Type label**
  What: exactly one `type:` label (feature, bug, chore). Why: lint limits and judge kind depend on it. Tier: CORE (cheap).
- **Gate acts without GitHub when unreachable**
  What: when GitHub cannot be reached the gate changes nothing; claimed work continues; nothing new starts. Why: no half-moves. Tier: LATER. Trigger: a run loses network mid-move.
- **Before the App exists, the gate moves state in a local record**
  What: GitHub writes are queued; the person runs a sync command with their own sign-in. Why: the person's sign-in is never used by agents as a stand-in for the App. Tier: LATER. Trigger: the kit is used before the GitHub App is set up and labels are needed.

## 3. Shaping and the spec

- **Shaping loop**
  What: choose path, take the biggest need, settle it by research, asking or prototype, write it down, recompute, then run the test-list check, then commit judge files and try ready. Why: a need clears only when its answer is written down. Tier: CORE in short form (ask, write the spec, write the judge, try ready).
- **Capture in the person's words**
  What: `/shape` captures an idea unchanged and takes in an issue opened by hand without duplicating it. Why: the person's words are the source. Tier: CORE.
- **Duplicate search before filing**
  What: search open, closed and dropped issues; a match gets the new words as a comment. Why: a rejected idea must not be rebuilt by accident. Tier: LATER. Trigger: the same idea filed twice.
- **Quick path**
  What: lighter required fields for a small change: one piece, one area, no sensitive area, no new dependency, a single-test judge. Why: heavy shaping on a small change is waste. Tier: CORE.
- **Spec IDs on flow steps and edge cases**
  What: each flow step and edge case has an ID, and each acceptance test names the ID it proves; no ID without test, no test without ID. Why: traceability, and a failing test can name the spec line it proves. Tier: CORE.
- **Edge cases as "When ..., then ..."**
  What: each case names its trigger and result, with a concrete example value. Why: vague cases cannot be tested. Tier: CORE.
- **Done when**
  What: every piece has a `Done when` section with a condition somebody can check. Why: this is what makes a piece ready. Tier: CORE.
- **Coverage categories**
  What: permissions, data kept, errors, empty states, what leaves the tool: each answered or marked not applicable with a reason. Why: silence on a category becomes a computed need. Tier: LATER. Trigger: a shipped piece missed an unconsidered category (permissions, errors, empty states).
- **Limits field**
  What: speed, size, accessibility, security or cost limits, each with a number or "none". Why: vague adjectives cannot be tested. Tier: LATER. Trigger: a piece passes its tests but is too slow or too big.
- **Must stay the same**
  What: behaviour that must keep working, proved by checks that pass on main at ready and join the frozen bar. Why: a build must not break existing behaviour. Tier: LATER. Trigger: a built piece breaks existing behaviour that no test covered.
- **Follow**
  What: existing code to imitate and any visual. Why: builders match the project's style. Tier: LATER. Trigger: builders produce code that ignores project conventions.
- **Changes to current behaviour**
  What: added, changed, removed lines; committed to overview and area docs and checked at merge. Why: records must stay true at each merge. Tier: LATER. Trigger: docs drift from behaviour after merges.
- **Not in this piece**
  What: what is deliberately left out. Why: stops scope creep. Tier: CORE (cheap).
- **Refused phrases**
  What: lint refuses "TBD", "decide during build", "for now", "a few", "several", and vague adjectives with no number. Why: ambiguity must be removed before the build. Tier: CORE.
- **Brief rules**
  What: behaviour not steps, no numbered build-step list, each criterion checkable alone. Why: builders choose the route; the spec fixes the target. Tier: CORE.
- **Two-layer piece**
  What: a short plain header for the person, then a complete layer for the builder. Why: both readers served. Tier: CORE.
- **Versioned spec format and one parser**
  What: a structured block between markers in the issue body, read by one parser shared by gate, lint, needs list and fingerprint. Why: two parsers drift. Tier: CORE.
- **Two fresh test lists**
  What: two sessions that carry none of the shaping chat each list the tests they would write; compared by spec ID covered; differences become needs. Why: catches a spec that two readers understand differently. Tier: LATER. Trigger: a builder's tests miss behaviour the person meant.
- **Cheap lint before expensive test lists**
  What: run the lint first and the model sessions only once it passes. Why: spend no model cost on a spec that fails basic checks. Tier: CORE with lint.
- **Question discipline**
  What: small batches, a cap per sitting (5), each with why it matters and a recommended answer. Why: avoids question floods and unguided choices. Tier: CORE (as a shape skill rule).
- **Assumptions recorded**
  What: low-impact unknowns become recorded assumptions marked as the agent's, for review. Why: do not block on small choices. Tier: CORE (cheap).
- **Silence is never an answer**
  What: an agent never settles a need that names the person. Why: decisions belong to the person. Tier: CORE.
- **Research records source, date, basis**
  What: each finding records its source, date and what it rests on (file and fingerprint, or page or package version). Why: the claim check can then tell when research went stale. Tier: LATER. Trigger: a build fails because research was out of date.
- **Research recommends, never decides**
  What: research gives facts and one recommendation. Why: the decision is the person's. Tier: CORE.
- **Shaping crews**
  What: several researchers on different sources, reconciled; or several prototypes side by side; only when the needs list holds a research or design question. Why: breadth and a visible choice. Tier: LATER. Trigger: single-researcher findings are wrong or the person cannot choose without seeing alternatives.
- **Researcher disagreement is a need**
  What: contradictions become a need settled by the person or a further check. Why: no silent resolution. Tier: LATER. Trigger: crews exist and disagree.
- **Prototype or an artefact the person has**
  What: settle a design question by a prototype or an existing artefact. Why: easier than describing. Tier: LATER. Trigger: the person cannot answer a design question in words.
- **Risk acceptance on the issue**
  What: the risk notice, the person's exact words and the date, under Sensitive areas; ready refuses a sensitive piece without it. Why: a risk must be knowingly accepted and recorded where it lasts. Tier: LATER. Trigger: first piece touching a sensitive area (money, personal data, access).
- **Pre-mortem**
  What: ask once "Say this went live and went wrong. Who noticed, and what did they see?" only for sensitive, data or outside-world pieces. Why: surfaces failure modes cheaply. Tier: LATER. Trigger: a live failure was one the spec could have predicted.
- **Irreversible data change mark**
  What: a `not reversible` field forces the person's merge and a backup first. Why: data loss cannot be undone. Tier: LATER. Trigger: first piece with a destructive migration.
- **Reach check, co-change query, area map**
  What: shaping fills the spec's touches field from the reach check, the last 200 commits of co-change, and the area map. Why: declared touches let the gate catch work outside scope. Tier: LATER. Trigger: a builder edits files outside the intended area.
- **Vertical slices with length limits**
  What: pieces sized for one sitting; length limits per type (80 chore, 120 bug, 250 feature) as lint. Why: small slices review and undo quickly. Tier: CORE as guidance; limits LATER. Trigger: pieces too big to finish in 3 attempts.
- **Parts versus blocked-by**
  What: parts are sub-issues; other dependencies are GitHub blocked-by links; no dependency field in the spec. Why: the gate reads one source. Tier: LATER. Trigger: the first piece that depends on another.
- **BLOCKING versus NOTE gaps**
  What: a gap blocks when closing it changes what a person sees, stores or sends out. Why: stops over-blocking on trivia. Tier: LATER. Trigger: shaping blocks on pedantic gaps.
- **A ready piece is never called safe**
  What: the gate cannot judge domain quality, polish or platform quirks and says so. Why: avoid false confidence. Tier: CORE.
- **No per-piece human approval at ready**
  What: the person answers needs and accepts risk; no extra sign-off. Why: avoid a second gate with no checkable condition. Tier: CORE.
- **Work outside the state machine**
  What: work on the person's computer, using the tool on content, and speaking for the person are kept as rules, not pieces. Why: they do not make a piece. Tier: LATER. Trigger: the kit is asked to handle non-code tasks.
- **Lessons from closed pieces read before research**
  What: lessons from the same area feed shaping. Why: avoid repeating mistakes. Tier: LATER. Trigger: the same mistake recurs across pieces.
- **Questions only the person can answer, with a labelled guess**
  What: one short question with a labelled guess (replaced by batched questions). Why: the earlier design; now folded in question discipline. Tier: CORE (merged above).

## 4. Ready gate

- **Ready gate (move 2)**
  What: lint first, then test lists, then judge files committed and seen failing, then the fingerprint. Why: nothing enters the build unshaped. Tier: CORE (lint, judge fails on main, fingerprint).
- **Needs list empty**
  What: nothing computable is still missing. Why: a need clears only when written. Tier: CORE.
- **Required fields present**
  What: goal, user story, flow, how to observe, edge cases, judge, links and the rest (fewer on the quick path). Why: the builder needs a full target. Tier: CORE for a short field set; the long set is LATER. Trigger: builds fail on missing information a field would have held.
- **Judge files are the first commit on the piece branch**
  What: shaping cuts the branch from main and commits the judge's tests first. Why: the frozen bar lives with the piece and never reaches main until merge. Tier: CORE.
- **Judge fails on today's main, for the right reason**
  What: each acceptance check runs on main in a temporary checkout and must fail on an assertion naming a spec ID, not on import or syntax error; hard timeout. Why: a judge that already passes proves nothing; an import error proves nothing. Tier: CORE.
- **Test runner report reading**
  What: pytest, Vitest, Jest and Node tell assertion from error; other runners fall back to the exit code with a note. Why: tell the right failure from the wrong one. Tier: CORE for the one runner the project uses; others LATER. Trigger: a project uses another runner.
- **Empty-project scaffold exception**
  What: the first piece in an empty project is a quick-path scaffold; its judge is that the test command runs. Why: no tests exist yet to fail. Tier: CORE (or the person sets up the runner first).
- **Fingerprint**
  What: hash of the spec block plus the judge commit, taken at ready, checked at every claim. Why: detects edits after ready. Tier: CORE.
- **Held-out cases set aside**
  What: hidden cases or a hidden twin measurement stored outside git and the issue; the spec holds only their fingerprint. Why: read-only tests do not stop special-casing; hidden cases are the second guard. Tier: LATER. Trigger: a builder special-cases visible tests and passes without real behaviour.
- **Dependencies resolve, no cycle**
  What: each blocked-by link points at a real piece; links form no cycle. Why: unbuildable plans. Tier: LATER. Trigger: the first multi-piece run.
- **Areas exist in the area map**
  What: every area the spec names exists. Why: touches and sensitivity depend on it. Tier: LATER. Trigger: area map is introduced.
- **Individual review decided at ready**
  What: the gate marks a piece for its own branch and pull request for exactly five must-look reasons: sensitive area, irreversible data, new dependency, security change, person marked it. Why: some pieces deserve a person's eye regardless. Tier: LATER. Trigger: the person wants a piece reviewed apart from a combined pull request.
- **Judge kind lives in the spec**
  What: not in a label. Why: one source. Tier: CORE.

## 5. Claim gate (ready to building)

- **Claim gate (move 4)**
  What: before a builder starts, confirm nothing changed since ready. Why: a ready piece can go stale. Tier: CORE (fingerprint and judge-still-fails).
- **Fingerprint unchanged**
  What: spec and judge files not edited after ready. Why: the agreed bar. Tier: CORE.
- **Judge still fails on today's main**
  What: re-run the judge at claim. Why: someone may already have built it, or main moved. Tier: CORE.
- **Spec lint passes again on today's main**
  What: re-lint at claim. Why: a rule may be broken by a change elsewhere. Tier: LATER. Trigger: main changes break a ready piece's assumptions.
- **Must-stay-the-same still passes**
  What: re-run those checks at claim. Why: behaviour may be broken before the build starts. Tier: LATER. Trigger: with must-stay-the-same.
- **Relied-on code unchanged**
  What: reach is worked out again; a change to a relied-on file sends the piece back. Why: the spec rested on code that moved. Tier: LATER. Trigger: builds fail because a relied-on file changed after ready.
- **Research staleness check**
  What: quick check of every finding (fingerprint for files, version and age for outside); fuller refresh when a fingerprint or version changed, age passed, or the check disagrees; back to shaping only for unconfirmable or spec-changing findings. Why: research goes stale by change and by age. Tier: LATER. Trigger: a build fails on a finding that was true when shaped.
- **Blockers done**
  What: every blocked-by piece is done or built earlier in this run (then stack). Why: dependents need their dependency. Tier: LATER. Trigger: first piece with a dependency.
- **Not already building**
  What: refuse a second claim on the same piece. Why: duplicate work. Tier: CORE (cheap with one run lock).
- **No running piece touches the same area**
  What: two builders must not change one area together. Why: avoid clashes. Tier: LATER. Trigger: parallel builders.
- **Free builder slot**
  What: slots sized from free memory, capped at 3 by default. Why: the computer can only run so many sessions. Tier: LATER. Trigger: parallel builds exhaust memory.

## 6. Judge and anti-gaming

- **Acceptance tests judge**
  What: the piece's acceptance tests pass (and hidden cases, when they exist). Why: the target for a build. Tier: CORE.
- **Reproducing test judge**
  What: for a bug, a test that reproduces it passes; no code change before the reproduction fails; read history first; two to five ranked falsifiable causes; remove temporary logs. Why: the fix loop needs a failing test first. Tier: CORE for the test; ranked causes guidance LATER.
- **Measurement judge**
  What: the metric command's last line is a number; kept only when it moved and guards stay green. Why: some goals are a number, not a test. Tier: LATER. Trigger: the person has a performance or quality metric piece.
- **Fresh critic judge**
  What: critics see work and reference as A and B in both orders and must agree; a tie is not a win. Why: match-a-reference needs a blind comparison. Tier: LATER. Trigger: a look-alike or copy-quality piece.
- **Outside critic**
  What: optionally a critic from another vendor (Codex), with the person's agreement; advisory unless a check reproduces its finding. Why: a different model family sees different faults; one study showed risk of lower pass rates. Tier: LATER. Trigger: the fresh Claude critic keeps missing a class of fault.
- **Frozen bar, byte for byte**
  What: the judge and everything it rests on (tests, measurement scripts, fixtures, references, test settings) are checked byte for byte before a piece leaves building. Why: a builder could rewrite the test to pass. Tier: CORE.
- **Bar change is a failed attempt**
  What: removing, skipping, loosening or retrying a test to pass counts as a failed attempt, logged as possible gaming. Why: never a pass. Tier: CORE.
- **Deny rules and sandbox write-blocks on the bar**
  What: the builder cannot write the bar files. Why: first layer; the byte check is the second. Tier: CORE (deny rule in the builder settings).
- **Gate runs the judge**
  What: the gate, not the builder, runs the judge and reads the result. Why: never trust a builder's claim. Tier: CORE.
- **Hold-out check for gaming**
  What: gate runs hidden cases when the builder claims the target; a hidden result much worse than the visible one is gaming. Why: catches special-casing. Tier: LATER. Trigger: a builder passes visible tests by special-casing.
- **Hypothesis list**
  What: for metric or open-route pieces, a list written before building; each attempt names the hypothesis it tests; new ones only in the goal's direction with a reason. Why: target and means cannot change after the fact. Tier: LATER. Trigger: metric pieces exist and attempts wander.
- **New-test lint**
  What: a test the builder adds must assert something, not be skipped, not mock the project's own code; plus the "yes" rows of the checks table. Why: cheap fake tests would pass the gate. Tier: LATER. Trigger: builders add empty or tautological tests.
- **Sanctioned "the bar is wrong" outcome**
  What: the builder can say the spec or tests are impossible; back to shaping, no attempt counted. Why: an explicit way out cut cheating sharply (ImpossibleBench). Tier: CORE (cheap, one hand-off).
- **Tests exist and fail first, naming the ID**
  What: the acceptance tests exist before code; type check and linter run before hand-over. Why: builds start from a proven failing target. Tier: CORE.
- **Mutation testing at the gate**
  What: where a tool is present, break the changed code once green; a check that notices nothing is a worth-knowing note; no score ever gates. Why: detect tests that can never fail. Tier: LATER. Trigger: green builds that hide weak tests.
- **Checks table for agent-written code**
  What: a list of smells (tautology, mock of own code, empty, skipped, sleepy, conditional logic, special-casing, test-detection code, snapshot regeneration, suppressed checks, swallowed errors, debug leftovers, unused or duplicated code, new dependency); script says yes, partly or no. Why: split what a script can catch from what a reviewer judges. Tier: LATER. Trigger: the same smell shows up repeatedly.
- **Must-stay-the-same joins the bar**
  What: the checks that pass on main become part of the frozen bar. Why: stops regressions. Tier: LATER. Trigger: with must-stay-the-same.
- **Controlled judge assembly**
  What: judge inputs assembled from controlled sources so a builder cannot replace test configuration. Why: the core review warned that known config files are only recognised, not controlled. Tier: LATER. Trigger: a builder subverts the judge through test configuration.

## 7. Run and build loop

- **Run is a plain script**
  What: started by `/run`; starts each builder as a separate non-interactive `claude -p` session. Why: the earlier coordinator stood still because it asked a question and waited. Tier: CORE.
- **Fresh session per attempt**
  What: each attempt starts clean and receives only the frozen spec, the gate-kept attempt log and, for metrics, the next hypothesis; never past session history. Why: long sessions full of failed approaches get worse; clean restarts win. Tier: CORE.
- **Gate-kept attempt log**
  What: each attempt's result and findings recorded by the gate and given to the next builder. Why: the next attempt learns without inheriting a poisoned context. Tier: CORE.
- **Three attempts per piece**
  What: fail after 3 attempts goes back to shaping with every attempt's findings. Why: a piece that cannot be built in 3 is badly shaped. Tier: CORE.
- **No real improvement stops early**
  What: the gate reads judge results; two failed attempts with no fewer failing IDs end the piece early. Why: spend nothing on a stuck piece. Tier: LATER. Trigger: attempts 2 and 3 repeat attempt 1.
- **No time limit on a piece, no run limit**
  What: only a clearly stuck attempt is stopped. Why: a piece can take time for good reasons. Tier: CORE.
- **Fixed hand-off outcomes**
  What: done, bar is wrong, needs the person, blocked by environment, gave up. Why: each outcome has one route. Tier: CORE for done, bar is wrong, gave up; others LATER. Trigger: environment blocks or questions occur.
- **"Needs the person" tool**
  What: the builder's one tool to park the piece and return at once. Why: builders cannot ask questions. Tier: LATER. Trigger: builders hit questions the spec did not answer.
- **Outcomes table**
  What: every outcome has one route and a rule for whether it counts as an attempt. Why: no ambiguity in routing. Tier: CORE (short form).
- **Stuck detection**
  What: the run script sees builder output; same error 3 times in a row, same change undone and redone, or a test run past its hard timeout stops the attempt and counts it. Why: idle timers kill agents waiting on long builds. Tier: LATER. Trigger: a builder loops without progress inside one attempt.
- **Hard timeout on every test and judge run**
  What: default ten minutes per check. Why: a hanging test would hang the run. Tier: CORE.
- **Usage limit pauses without counting**
  What: waiting for reset, tokens recorded per piece. Why: a limit is not the builder's failure. Tier: LATER. Trigger: a run hits a usage limit.
- **Spend caps on an API key**
  What: setup asks a cap per piece and per run, passed as `--max-budget-usd`; reaching one waits for the person. Why: no unbounded API spend. Tier: LATER. Trigger: the person runs on an API key.
- **Builder count from the computer**
  What: slots from free memory, cap 3; back-off under memory pressure. Why: sessions crash a short-of-memory machine. Tier: LATER. Trigger: parallel builds degrade the computer.
- **Plan by dependency and area, serial chains first**
  What: the run orders pieces so dependents follow, shows serial chains before starting. Why: the person sees the plan. Tier: LATER. Trigger: multi-piece runs.
- **Run record**
  What: git-ignored file with pieces, order, worktrees, attempts, judge results, heartbeat, decisions made alone; a new session resumes from it. Why: crash recovery without redoing work. Tier: CORE (small).
- **Resume after crash**
  What: from the run record and the Piece trailers on the combined branch. Why: no repeat work. Tier: LATER. Trigger: a run crashes mid-way.
- **One run per project, lock file**
  What: a lock holds the project to one run. Why: two runs clash. Tier: CORE (cheap).
- **Worktree per piece**
  What: each piece builds in its own worktree under a git-ignored folder; the main folder never switches branch; never forced removal. Why: isolation and no loss of unsaved work. Tier: CORE.
- **Throwaway env values in each worktree**
  What: builders never read a real env file; each worktree gets throwaway values under a marker. Why: no real secret reaches a builder. Tier: CORE.
- **One local app and seeded data per builder**
  What: each builder gets its own port and data. Why: avoid collisions. Tier: LATER. Trigger: UI pieces run in parallel.
- **Walk-through with sample data**
  What: builder shows what the feature does and names what could not be seen. Why: evidence beyond tests. Tier: LATER. Trigger: reviewers cannot tell what a piece looks like.
- **Scratch files in a git-ignored run folder**
  What: attempt notes, frozen spec copy, judge logs, run state never reach a branch. Why: nothing to strip at merge, no conflicts. Tier: CORE.
- **Acceptance tests stay as ordinary project tests**
  What: at merge, tests remain; a cheap judge may stay; an expensive one is dropped; lasting facts go in the issue or changelog. Why: tests guard the behaviour later. Tier: CORE.
- **Trim pass**
  What: last step of the build loop; remove or fold only, never tests, only code this piece added, own commit, thrown away if a check fails after. Why: agents over-build. Tier: LATER. Trigger: pieces ship with bloat the reviewer flags.
- **Well-defined trim checks**
  What: specific checks (tautological tests and so on) researched from Matt Pocock's list. Why: make the trim pass checkable. Tier: LATER. Trigger: the trim pass makes subjective changes.
- **Kickback section on the issue**
  What: the issue records why a piece came back; the branch is kept; shaping reads it first. Why: a returned piece must not repeat the same mistake. Tier: CORE (comment on the issue).
- **Two environment failures in a row pause the run**
  What: two failures on different pieces stop the run. Why: a broken machine, not a bad piece. Tier: LATER. Trigger: environment failures across pieces.
- **Pause, continue, stop mailbox**
  What: a local file the run reads at each step. Why: the person controls a run in progress. Tier: LATER. Trigger: the person needs to halt a run.
- **One writer per piece, readers read-only**
  What: only a builder writes a piece's branch; critics and readers are read-only. Why: avoids conflicting edits. Tier: CORE.
- **Type check and linter before hand-over**
  What: builder runs them before declaring done. Why: cheapest checks that most often failed in CI. Tier: CORE.
- **No live service change without a yes**
  What: an unattended run leaves such a command unrun; no stored logins. Why: money, access and online services need the person. Tier: CORE.
- **Pre-run check**
  What: refuses to start unless guards, policy file, computer (power, sleep, memory, disk) and a green main are fine; refuses `--bare`; refuses API key without caps; names the missing half of setup. Why: guards must exist before agents run unwatched. Tier: CORE in short form (main green, guards present); the rest LATER. Trigger: a run starts with a guard missing or a machine unfit.
- **Two questions asked once**
  What: which pieces, and whether the merge is pre-approved (default no). Why: pre-approval is per run, never standing. Tier: CORE.
- **Empty-policy start**
  What: a project with no tests may start with only the scaffold piece. Why: avoid a deadlock before the first runner exists. Tier: CORE if empty projects are supported.
- **First upload asks**
  What: a project not on GitHub yet asks naming repository and visibility before building; a project whose origin is the kit's repository pushes nothing. Why: no accidental publication. Tier: LATER. Trigger: kit used on a project without a remote.
- **Malformed policy stops the run**
  What: a bad policy value stops the run naming the key. Why: silent defaults hide mistakes. Tier: LATER. Trigger: policy file exists.
- **Policy file**
  What: person-written JSON holding builder cap, attempt limit, review rounds, question cap, research age limit, length limits, outside critic choice; agents read it and cannot edit. Why: agents cannot change their own limits. Tier: LATER. Trigger: the defaults need to differ per project.
- **Machine-local settings file**
  What: git-ignored file for settings that belong to one computer. Why: keep machine facts out of git. Tier: LATER. Trigger: path or key settings per machine.

## 8. Review and integration

- **Combined run branch**
  What: all of a run's pieces are joined on one branch cut from main at run start; checks run on the combined result. Why: all changes are expected to work together. Tier: LATER. Trigger: runs with two or more pieces that must work together.
- **Trial joins in a scratch copy**
  What: each join is a trial; the branch advances only on green; on red the trial is thrown away and the piece goes back with the clash written on it. Why: no take-out, no revert, no force push needed. Tier: LATER. Trigger: a combined branch goes red.
- **Join order and re-run of judges**
  What: dependency order; every joined piece's judges and must-stay-the-same and declared touches re-run at each join. Why: about 28 percent of agent pull requests conflict; separate worktrees prove nothing about compatibility. Tier: LATER. Trigger: clashes found only after merge.
- **No conflict resolution by agents across pieces**
  What: a merge conflict sends the piece back. Why: cross-piece resolution is risky. Tier: LATER. Trigger: conflicts appear.
- **Piece trailer for idempotent joins**
  What: each join commit carries a Piece trailer so a resumed run knows which joins are done. Why: crash recovery. Tier: LATER. Trigger: a crash during joins.
- **Rebuild instead of revert**
  What: when a piece must leave after joining, rebuild the combined branch from main under a fresh name; no revert, no force push; new pull request replaces the old. Why: no rewrite of history the person has cloned. Tier: LATER. Trigger: a piece is rejected after joining.
- **Dependents stack on dependency branch**
  What: a dependent builds on its dependency's branch and inherits isolation. Why: dependents need their dependency's code. Tier: LATER. Trigger: first dependency chain.
- **Individual review for must-look pieces**
  What: not joined; same steps on own branch and own pull request. Why: some pieces need separate review. Tier: LATER. Trigger: a sensitive piece in a run.
- **Final combined check, run locally**
  What: full project checks, validator if any, every judge; failures send only relevant pieces back. Why: replaces a second GitHub check layer. Tier: CORE (run the judge and project checks on the branch before opening the pull request).
- **Gate judges flakiness**
  What: a red check is re-run once on the same commit; a different result marks flaky, never a pass. Why: the builder cannot judge flakiness. Tier: LATER. Trigger: flaky tests block joins.
- **Merge commit, never rebase**
  What: bring-up-to-date uses a merge commit. Why: no force push. Tier: CORE.
- **Docs and changelog committed before the final check**
  What: each piece's behaviour change is applied to overview and area docs and the changelog entries are folded, so the merge adds no untested commit. Why: the tested tree must be the merged tree. Tier: LATER. Trigger: records drift after merges.
- **Fresh reviewer**
  What: sees only the specs and the combined diff piece by piece; no builder's account; no same-session fallback. Why: independence. Tier: LATER. Trigger: bugs reach the person that a fresh reader would have caught.
- **Findings have three routes**
  What: failing check (back to building), shaping issue (spec wrong), or worth-knowing note. Why: every finding becomes something checkable. Tier: LATER. Trigger: with the reviewer.
- **New test from a finding joins the bar**
  What: with written justification for the person. Why: the lesson stays enforced. Tier: LATER. Trigger: with the reviewer.
- **Two review rounds**
  What: a finding left after 2 rounds sends that piece to shaping with the flag; others go ahead. Why: bound the loop. Tier: LATER. Trigger: with the reviewer.
- **Review never stops the loop**
  What: the run moves on to other pieces while one waits. Why: keep the run moving. Tier: LATER. Trigger: parallel runs.
- **Reviewer isolation**
  What: reviewer's settings let it write only its findings file; no shell, no network. Why: a reviewer must not change the work. Tier: LATER. Trigger: with the reviewer.
- **Reviewer spend counted**
  What: reviewer cost counted against caps. Why: spend caps would otherwise leak. Tier: LATER. Trigger: API-key runs with a reviewer.
- **Evidence per piece in the pull request**
  What: judge results, hidden result, mutation result, review verdict, preview link, worth-knowing items. Why: the person judges from evidence. Tier: CORE (judge result per piece).
- **Worth-knowing items**
  What: decisions made alone, first deployment, new tests from review, flaky results, changes outside areas. Why: visible without blocking. Tier: LATER. Trigger: the person wants to see these.
- **One pull request grouped by piece, split when too large**
  What: one pull request for the run with a section per piece; size limit splits it. Why: easy review. Tier: CORE (one pull request per piece or run).
- **Must-look reasons exactly five**
  What: sensitive area, irreversible data, new dependency, security change, person marked; only the gate writes the list; decisions made alone do not block pre-approval. Why: a short, fixed list. Tier: LATER. Trigger: pre-approval is used.
- **Culprit finding in a red combined result**
  What: just-joined piece is the suspect (answer 17, later replaced by the trial join). Why: avoid blaming everything. Tier: LATER (merged with trial joins).
- **Closing words only on a Closes line**
  What: one `Closes` line per piece; no closing word anywhere else. Why: GitHub closes issues even in a sentence saying it does not. Tier: CORE.

## 9. Merge and approval

- **No approve command**
  What: merging is merging on GitHub, or telling the agent to merge. Why: no extra ceremony. Tier: CORE.
- **Person merges under their own account**
  What: the agent does not hold the person's login. Why: separation of identity. Tier: CORE.
- **Never automatic by default**
  What: auto-merge only when pre-approved before that run started, per run. Why: stops standing authority. Tier: CORE (no auto-merge at all in the thin loop).
- **Pre-approval conditions**
  What: green checks on the up-to-date combined branch; every judge passing with an unchanged bar; a clean fresh review; no must-look piece. Why: pre-approval without these is unsafe. Tier: LATER. Trigger: the person wants runs to merge themselves overnight.
- **Merge only the exact tested commit**
  What: `gh pr merge --match-head-commit`. Why: the tested tree must be the merged tree. Tier: LATER. Trigger: with pre-approved merge.
- **Main moved after check**
  What: nothing merges until the branch is brought up to date and checked again; a person merge triggers a check on main. Why: free repositories cannot stop the person merging anyway. Tier: LATER. Trigger: main moves between check and merge.
- **A yes to the agent must name the merge**
  What: "put it live" is not that yes. Why: ambiguous consent. Tier: CORE.
- **Merge confirmation box**
  What: Claude Code shows a confirmation before `gh pr merge`. Why: where every merge goes live. Tier: CORE.
- **Irreversible data is always the person's merge**
  What: after a backup taken before the migration. Why: data loss cannot be undone. Tier: LATER. Trigger: destructive migration pieces.
- **Done closes the issue; branch deleted on merge**
  What: Closes line closes the issue; the gate removes the label; worktree removed only when nothing unsaved. Why: tidy and safe. Tier: CORE.
- **No hosting means merge is done**
  What: `Goes live: not hosted` treats merge as done; a release only on a named yes. Why: not every project deploys. Tier: LATER. Trigger: hosted projects.
- **Approval waits are non-blocking**
  What: pieces waiting in approval do not block the next run. Why: runs move on. Tier: CORE.

## 10. Safety and guard

- **Deny rules**
  What: no push to main, no force push, no recursive delete, no hand-written state label. Why: the worst unrecoverable acts. Tier: CORE.
- **Parsing hook**
  What: a hook parses each command rather than matching its text, so `git -C . push origin main` is caught. Why: bash rules alone are not a security boundary. Tier: CORE (tiny hook).
- **Refuse what cannot be inspected**
  What: an unresolved executable, file-fed GraphQL or exotic git config is refused or asked about. Why: opaque forms bypass the parser. Tier: LATER. Trigger: an agent reaches a protected action by an opaque form.
- **Guards guard themselves**
  What: deny rules and write-blocks on the gate, hooks, settings and workflows; the pre-run check refuses to start while one is missing. Why: a guard the agent can edit is no guard. Tier: CORE for settings and hooks; the full list LATER.
- **Agents never edit settings**
  What: agents cannot change `.claude/settings.json` or their own permissions. Why: a rule in a file the agent can change is no guard. Tier: CORE.
- **Guards passed explicitly with `--settings`**
  What: every builder gets guard settings by flag; `--bare` is refused. Why: bare mode skips hooks; discovery cannot be relied on. Tier: CORE.
- **Filesystem sandbox with network allowlist**
  What: on for every agent session, with an allowlist per recipe (package registry and toolchain hosts); settings `strictAllowlist`, `allowUnsandboxedCommands: false`, `failIfUnavailable: true`, bypass mode off; builders run `dontAsk`. Why: contain what a builder can reach. Tier: LATER. Trigger: a builder reaches outside the project or the network.
- **No real env files**
  What: agents never read a real env file; settings refuse git-ignored env files except the throwaway one. Why: secrets stay out of sessions. Tier: CORE.
- **Secret scan in two places**
  What: before every push and a second scan (the gate's push step). Why: git history keeps a secret for ever. Tier: CORE (pre-push hook).
- **Scan commit messages for secret shapes**
  What: widen the scan to messages. Why: secrets can hide there. Tier: LATER. Trigger: a secret in a message.
- **Yes before speaking for the person**
  What: anything posted in the person's name waits for a yes; bookkeeping needs none. Why: avoid impersonation. Tier: CORE.
- **Outside text is data**
  What: issues and web text reach a session only inside a marked data block. Why: anyone can write into an issue; prompt injection. Tier: CORE.
- **New dependency age and licence check**
  What: a dependency first released under 30 days ago is refused; licence checked. Why: supply-chain attack window. Tier: LATER. Trigger: a builder adds a dependency.
- **Supply chain settings**
  What: package manager minimum-age, no install scripts, Dependabot, Actions pinned to exact versions. Why: stop poisoned packages before install. Tier: LATER. Trigger: dependencies are introduced.
- **Command log**
  What: a hook logs every command the agent runs, refuses or retries. Why: lessons and investigations need a record. Tier: LATER. Trigger: a failure cannot be traced.
- **SessionStart hook**
  What: re-injects key context after compaction. Why: context loss. Tier: LATER. Trigger: sessions forget rules after compaction.
- **Refused command is never reached another way**
  What: report and stop; inside a piece it is that piece's environment failure. Why: a workaround defeats the guard. Tier: CORE.
- **Ask before irreversible, access, money or service changes**
  What: installs outside the project, release publishing, repository settings, public visibility need a yes naming what, where, how to undo. Why: unrecoverable or costly. Tier: CORE.
- **Held-out store read-blocked**
  What: the hidden cases folder is outside the project and blocked for builders. Why: stops peeking. Tier: LATER. Trigger: with hidden cases.
- **Builders hold no GitHub credential**
  What: scrubbed environment; sandbox read-blocks on the `gh` config and keychain. Why: builders must not change settings, workflows or merge. Tier: CORE.
- **Real stops**
  What: a fatal error, money, real accounts or credentials, repository or account setting, data that cannot be restored, going public or a release, repeated failure across pieces, same refused command in two pieces, an answer that would change a settled decision. Why: some acts always need the person. Tier: CORE as a rule list in AGENTS.md.
- **Permissions set before the run**
  What: the person writes permissions and policy; agents cannot change their own. Why: Claude Code's own safety check refused such a change. Tier: CORE.
- **Skills never the only holder of a guard**
  What: skill frontmatter hooks and allowed-tools are conveniences. Why: a skill can be skipped. Tier: CORE.

## 11. GitHub and credentials

- **GitHub issues, labels, sub-issues, pull requests as the store**
  What: no separate database. Why: visible to the person and to tools. Tier: CORE.
- **The gate's GitHub App**
  What: an App scoped to the repository, held only by the gate; created once in the second half of setup. Why: agents act with a fine-grained identity that cannot change settings or workflows; the person merges as themselves. Tier: LATER. Trigger: the person needs walk-away runs or gate-written labels and comments.
- **App key outside the project, mode 600**
  What: key path stored in machine-local settings, read-blocked from builders. Why: key theft. Tier: LATER. Trigger: with the App.
- **No use of the person's `gh` sign-in by agents**
  What: before the App, GitHub steps wait for the person. Why: keeps the person's full token out of agent processes. Tier: CORE.
- **Person-synced reads before the App**
  What: the person runs the sync command in a separate terminal (dry run then confirmation digest); agents then read a bounded snapshot. Why: allow shaping to see remote issues and dependencies without giving agents credentials. Tier: LATER. Trigger: shaping needs remote dependency or duplicate checks before the App exists.
- **Snapshot limits and freshness**
  What: readers check project root, git directory, origin, repository ID and a maximum age of fifteen minutes; collection limits (500 issues, 500 dependency nodes, 5,000 edges, 500 comments, 8 MiB, 30 seconds a read, 3 minutes in all); refuse overflow. Why: an offline snapshot is point-in-time and could be stale or hostile. Tier: LATER. Trigger: with person-synced reads.
- **Snapshot authority from the sandbox**
  What: the snapshot lives in protected loop settings; its authority comes from filesystem protection, not a hash of editable JSON. Why: an editable hash gives no authority. Tier: LATER. Trigger: with person-synced reads.
- **App failure never falls back to cached data**
  What: with the App installed, live reads are used; failure refuses. Why: stale data must not pass as live. Tier: LATER. Trigger: with the App.
- **Synthetic checks versus real sandbox check**
  What: synthetic checks prove configuration; the person checks the installed sandbox separately; the builder does not claim a real session result. Why: a stand-in does not enforce the sandbox. Tier: LATER. Trigger: before relying on the sandbox.
- **Attended setup sandbox boundary**
  What: finite exclusions for exact installed non-executing setup and gate commands, isolated Python, literal absolute installed path; origin verified in clean scratch; project-local git configuration cannot select helpers. Why: a sandbox needs narrow, checked holes. Tier: LATER. Trigger: setup commands blocked by the sandbox.
- **GitHub rulesets offered once**
  What: offered on a yes naming it, where the plan supports them. Why: server layer when available. Tier: LATER. Trigger: a paid or public repository.
- **Waiting for checks**
  What: one `gh pr checks --watch --fail-fast`; no checks is never green. Why: a sleep loop hides failure. Tier: LATER. Trigger: hosted checks exist.
- **Hosted checks**
  What: the maintainer later chose hosted checks on pull requests and main. Why: independent of the laptop; cost accepted. Tier: LATER. Trigger: local-only checks miss a CI-only failure.

## 12. Setup and distribution

- **Five commands**
  What: `/setup`, `/shape`, `/run`, `/maintain`, `/what-now`; no capture or fix command; no approve. Why: small surface. Tier: CORE for shape and run (and a minimal setup); the rest LATER. Trigger: maintain, what-now are earned by drift and by board confusion.
- **`/setup` in two halves**
  What: first "shape and run locally", then "make it safe to walk away". Why: the person can start without the App; the pre-run check names the missing half. Tier: LATER. Trigger: the person wants unattended runs.
- **`/setup` first half contents**
  What: tooling check, foundation files without overwriting, policy, hooks and pre-push hook, default allowlist for the language, spend caps for an API key, free-plan warning, first scaffold piece. Why: a local-safe start. Tier: CORE in minimal form (hook, settings, labels).
- **Foundation files copied without overwriting**
  What: setup never replaces the person's existing files; settings merged by key. Why: keep the person's rules. Tier: CORE.
- **Kit runs from the plugin folder**
  What: scripts run from the installed plugin; nothing copied into a project to refresh. Why: updates need no copy. Tier: CORE.
- **Plugin manifest**
  What: plugin root with skills, hooks and scripts. Why: distribution. Tier: CORE.
- **Public plugin from a pinned tagged release**
  What: maintainer chose distribution on 8 October; immutable ref; version state in a stable home. Why: reproducible installs. Tier: LATER. Trigger: release.
- **Founding removes the old kit's machinery on one yes**
  What: list the old kit's files and remove on a single yes; project's code and issues untouched. Why: one kit per project. Tier: LATER. Trigger: a project with the old kit installed.
- **Old kit is a separate product**
  What: no support window promised; the two are separate. Why: avoid false promises. Tier: CORE (a statement).
- **Meeting projects the kit did not write**
  What: setup copes with existing projects; setup must not assume a team. Why: maintainer called it important for v1. Tier: LATER. Trigger: use on an existing project.
- **Python 3.10 standard library only; JSON policy**
  What: scripts need no installs. Why: the kit installs into projects that may not have more. Tier: CORE.
- **Script contract (principle 8)**
  What: no prompts, `--help`, JSON out, distinct exit codes, idempotent, `--dry-run`, errors name the next command. Why: scripts are read by agents. Tier: CORE (as a style).
- **Repository ruff and mypy rules**
  What: a lint rule set; a check that did not run is never green. Why: quality of the kit's own code. Tier: CORE.
- **Throwaway project and stand-ins**
  What: GitHub stand-in, Claude stand-in and App stand-in for offline tests; real smoke tests by hand. Why: tests run with no network, account or model. Tier: CORE.
- **Skipped is never a pass**
  What: a skipped check prints a visible line and does not count as a pass. Why: a check that did not run proves nothing. Tier: CORE.

## 13. Records and documents

- **One home per fact**
  What: a fact anywhere else is a pointer. Why: duplicates drift. Tier: CORE.
- **AGENTS.md as index**
  What: about 150 lines at most; commands, non-obvious rules with reasons, guarded actions, pointers; CLAUDE.md only imports it. Why: an overlong file loses attention; model-written context lowered success in one study. Tier: CORE.
- **Overview**
  What: 100 lines; what it is, who for, how it goes live, area table with sensitive flag. Why: a short stable description. Tier: LATER. Trigger: agents misunderstand the product.
- **Area map**
  What: CODEOWNERS-style patterns, last match wins, no prose; every tracked file in an area. Why: touches, sensitivity and docs depend on it. Tier: LATER. Trigger: pieces touch many areas.
- **Area docs**
  What: 300 lines each; current behaviour and decisions in force, updated at merge. Why: current behaviour recorded in one place. Tier: LATER. Trigger: behaviour questions come up repeatedly.
- **Area rules files**
  What: optional `.claude/rules/<area>.md` at 40 lines. Why: area-specific conventions. Tier: LATER. Trigger: area conventions are lost.
- **The piece (issue) holds spec, decisions, risk, evidence**
  What: the record of why. Why: lasts after closing. Tier: CORE.
- **Changelog**
  What: one entry per merged piece from its behaviour change, never from commit messages. Why: an accurate history for the person. Tier: LATER. Trigger: the person needs release notes.
- **Merge refused if named doc not updated**
  What: gate refuses a merge whose behaviour change names a doc the pull request did not change. Why: records stay true. Tier: LATER. Trigger: docs drift.
- **Piece records**
  What: gate-written hash-chained evidence per piece. Why: hard to forge. Tier: LATER. Trigger: need an audit trail of judge runs.
- **Records checks**
  What: line ceilings, named paths and commands exist, areas agree, repeated paragraphs, closed pieces have changelog entries. Why: mechanical drift detection. Tier: LATER. Trigger: drift found by `/maintain`.
- **Auto memory off in run sessions**
  What: builder sessions do not use auto memory. Why: unreviewed memory pollutes builds. Tier: CORE.
- **Lessons**
  What: a check, hook or lint first; only if impossible, one reasoned line in AGENTS.md with evidence and date. Why: checks beat prose. Tier: LATER. Trigger: the same failure repeats.
- **British spelling and humanizer pass**
  What: prose written in British spelling, no em dashes, run through the humanizer skill. Why: easy to read and to check. Tier: CORE (house rule).
- **Never put an issue or pull request number in a tracked file**
  What: house rule checked by script. Why: numbers point at nothing when the repository moves. Tier: CORE.
- **BORROWED.md**
  What: lists borrowed code with source commit and what it must shed. Why: provenance. Tier: CORE while borrowing.
- **Skills rules (17 principles) and lint**
  What: size limits, section order, Held by pointers, Done when per step, timeless text, three eval cases; `check-skills` lint. Why: skills that survive compaction and do not carry guards. Tier: CORE for a short template and size limits; the full 17-rule lint is LATER. Trigger: skill quality problems seen in real sessions.
- **Skill template**
  What: Now (injected report), Stops, Steps with Done when, Gotchas, When to read more. Why: consistent skills. Tier: CORE.
- **Disable model invocation on setup, run, maintain**
  What: only the person starts them. Why: avoid accidental runs. Tier: CORE.
- **Skill evals**
  What: at least three cases (normal, edge, refusal) written before the skill; three test tiers. Why: skills tested like code. Tier: LATER. Trigger: a skill misbehaves in a real run.
- **Live state injected into skills**
  What: `!` command with a fallback line. Why: the skill sees live state. Tier: LATER. Trigger: `/run` and `/what-now` start with stale state.
- **Risk-acceptance doc updates**
  What: any overview line the acceptance makes untrue is updated in the same pull request. Why: records stay true. Tier: LATER. Trigger: with overview.

## 14. Notifications and walk-away

- **The watch**
  What: a launchd job that only checks the run's heartbeat is fresh and notifies once when it is not. Why: stuck detection lives in the run script; the watch is the outside check. Tier: LATER. Trigger: a run dies silently while the person is away.
- **launchd KeepAlive and caffeinate**
  What: the run script restarts at once if it dies and the computer stays awake. Why: a sleeping or crashed run stops all work. Tier: LATER. Trigger: a run is lost to sleep or crash.
- **Heartbeat**
  What: the run writes a heartbeat at every step. Why: gives the watch something to read. Tier: LATER. Trigger: with the watch.
- **Decide or park**
  What: faced with a question, the run takes the answer that keeps every settled decision and is easiest to undo (documented), or parks the piece with the flag set; independent work continues. Why: the earlier run stood still four hours on a done-line question. Tier: CORE as a rule (never block the whole run on one question).
- **Real stops do not freeze independent work**
  What: notify once, carry on with whatever does not depend on the answer. Why: avoid idle runs. Tier: LATER. Trigger: a stop halts a multi-piece run.
- **Morning summary**
  What: every decision made alone in one list, closing the run. Why: the person reviews what was decided without them. Tier: CORE (short summary).
- **Six notifications**
  What: run finished; real stop; pull request ready; went live or live check failed; waited on the person about 2 hours; heartbeat stale. Why: the moments the person acts on. Tier: LATER. Trigger: the person misses a moment when away.
- **Notifications by GitHub mention**
  What: the gate mentions the person; GitHub Mobile pushes it; email is the fallback; quiet hours follow GitHub's working hours and collapse into one message. Why: one channel out, reusing tools the person has. Tier: LATER. Trigger: with notifications.
- **Non-blocking notifications; one channel in**
  What: a notification never pauses work; input arrives as issue or pull request comments; the mailbox is only for pause, continue and stop. Why: runs continue without waiting. Tier: LATER. Trigger: with notifications.
- **Late answer handling**
  What: an answer arriving after the run ended is written into the spec by the gate, re-fingerprinted, and the piece returns to ready; the person is told. Why: nothing is lost. Tier: LATER. Trigger: answers after a run.
- **Answers read from comments**
  What: only from the owner, a member or a collaborator, never a bot. Why: avoid hijack by an outsider. Tier: LATER. Trigger: with comment input.
- **`/what-now`**
  What: says what is where, what needs the person, how a run goes, what was decided alone; order and cap of three. Why: the person needs a single status; not `/status`, which is taken. Tier: LATER. Trigger: the person loses track of piece states.
- **Live dependency board**
  What: the plan as a graph redrawn when it changes, with state and waiting lines. Why: maintainer requirement of 6 October. Tier: LATER. Trigger: multi-piece runs where order is unclear.
- **One status file**
  What: one file feeds every view of progress. Why: single source. Tier: LATER. Trigger: with what-now.
- **Coordinator handover**
  What: before context exhaustion, finish agents, save state, resume in a fresh session. Why: context limits. Tier: LATER. Trigger: a coordinating session runs out of context.

## 15. Deployment

- **Live is an extension, not a core state**
  What: where main is deployed, a merged piece goes live by itself. Why: not every project deploys. Tier: LATER. Trigger: the project has a host.
- **Recipes**
  What: one stack paired with one host; the only place a product is named; Vercel and Coolify kept. Why: keeps product names out of the core. Tier: LATER. Trigger: first deployed project.
- **`Goes live:` line**
  What: `on every merge` or `not hosted`; missing means not set up. Why: the kit must know whether merge means live. Tier: LATER. Trigger: with recipes.
- **Health check after each deploy of main**
  What: a small GitHub Action, about a minute per deploy, so it works with the laptop off. Why: catch a bad deploy. Tier: LATER. Trigger: a broken deploy reached users unnoticed.
- **Automatic rollback**
  What: roll back to the last good deployment; open a revert pull request, a bug issue and a "production is pinned" notification. Why: restore service fast. Tier: LATER. Trigger: a failed deploy needs manual recovery.
- **Rollback possible, not tried**
  What: a recipe whose rollback the kit cannot run never earns automatic merge. Why: auto-merge needs a safe undo. Tier: LATER. Trigger: with pre-approved merge.
- **Deploy once, read whole output**
  What: read the whole deploy output before a second deploy. Why: avoid double deploy. Tier: LATER. Trigger: with recipes.
- **First deployment runs first-launch checks once**
  What: a worth-knowing item, no longer a must-look reason. Why: first launch has special risks. Tier: LATER. Trigger: first deploy.
- **Preview link in evidence**
  What: each piece's evidence carries a preview URL where the recipe gives one. Why: the person can try it. Tier: LATER. Trigger: UI pieces.
- **Launch warnings said once**
  What: never stopping the launch. Why: avoid nagging. Tier: LATER. Trigger: with recipes.
- **Live stage 1: errors into grouped issues**
  What: an error tool, an intake script that opens one grouped bug issue per error group past a threshold, with a daily cap, ignore list, regression reopening, scrubbing of personal data and error text treated as data. Why: production errors enter shaping. Tier: LATER (after v1.0). Trigger: production errors are missed.
- **Live stage 2: slow requests into issues**
  What: tracing; routes past a Limits number open one issue each. Why: performance regressions enter shaping. Tier: LATER (after v1.0). Trigger: performance complaints.
- **Release marker per deploy**
  What: each deploy carries the merge commit so errors map to merges. Why: feeds the change-fail rate. Tier: LATER. Trigger: with stage 1.
- **Supabase free plan limits**
  What: previews share one preview database; automatic merge stays off on both recipes at 1.0. Why: no branching on that plan. Tier: LATER. Trigger: with that host.

## 16. Learning and maintenance

- **Learning loop**
  What: collect evidence at run end and on every kickback or finding; a pattern seen twice becomes a lesson candidate; lessons become checks first; stale lessons offered for removal. Why: improve without bloating prose. Tier: LATER. Trigger: the same failure recurs across runs.
- **Lessons applied at the next run**
  What: proposed during a run, applied after the next pre-run check as their own commits. Why: the frozen bar must not change under pieces in flight. Tier: LATER. Trigger: with the learning loop.
- **Every finding becomes a failing check or a shaping issue**
  What: no finding is left as advice. Why: checks hold; advice fades. Tier: LATER. Trigger: with the reviewer.
- **`/maintain`**
  What: drift between records and code, code health (including mutation testing), delivery health (change-fail and rework rates), tidying, kit updates; findings become issues; the kit suggests it every 2 weeks. Why: decay is quiet. Tier: LATER. Trigger: drift or decay seen after several runs.
- **Stale branches listed, never removed by the kit**
  What: old branches whose work is in main are listed with commands. Why: no irreversible delete. Tier: LATER. Trigger: leftover branches pile up.
- **Whole-project reads are silent when clean, capped at three proposals, with no score**
  What: reports only what matters. Why: avoid noise. Tier: LATER. Trigger: with maintain.
- **Delivery rates**
  What: change-fail and rework rates. Why: see whether the loop delivers. Tier: LATER. Trigger: enough runs to measure.
- **Guides and sensors**
  What: guides are the lint rules, review and crew checks; everything else is a sensor never switched off. Why: keep checks permanently. Tier: LATER. Trigger: with auto-merge eligibility.
- **Clean-run count for auto-merge**
  What: offered when the 5 most recent counted runs are clean. Why: earn auto-merge. Tier: LATER. Trigger: the person wants overnight merges.
- **Kit update path migration**
  What: installed-path rendering updated when the plugin moves; version state stable. Why: absolute paths go stale. Tier: LATER. Trigger: a plugin update breaks guard paths.
- **Command-log retention**
  What: bounded retention with named-file removal only. Why: unbounded logs. Tier: LATER. Trigger: log growth.

## 17. Factory and overnight-run rules (earlier plan)

These came from the overnight builds. They are rules for how the kit's own
factory worked. Most describe building the kit, not using it.

- **Pre-approved overnight merges**
  What: the coordinator merges a slice when checks are green and a fresh review is clean; anything else waits. Why: unattended building. Tier: LATER (factory only). Trigger: another unattended build of the kit.
- **Decide-or-park for builder questions**
  What: the coordinator records the decision or parks the piece; real stops listed. Why: the night run stood still on a builder's question. Tier: CORE (same as decide or park above).
- **Fast flow on an integration branch**
  What: parts land on an integration branch on quick checks; one pull request per slice. Why: parts took 60 minutes, half of it waiting. Tier: LATER (factory only). Trigger: build time dominated by review waits.
- **Local checks, GitHub at the end**
  What: run checks locally to spare Actions minutes; one suite at a time. Why: private repository, limited minutes. Tier: CORE (local checks).
- **Build the core first**
  What: build the smallest kit, then add features as fixes after use. Why: use and harden sooner. Tier: CORE (the thin restart is the same idea).
- **Guided checks**
  What: a guided check blocks a merge only when a later slice relies on it; otherwise queue it for the person. Why: avoid stopping the run for minor checks. Tier: LATER (factory only). Trigger: queued person tasks pile up.
- **Skip ahead past a person's step**
  What: mark that part waiting and continue later slices that do not need it. Why: avoid idle runs. Tier: LATER (factory only).
- **Gate files held by a floor rehearsal**
  What: gate scripts copied beside the gate and guarded. Why: old design for founding; replaced by running from the plugin. Tier: LATER (superseded).
- **Open question fingerprint**
  What: a new question differs from an old one by fingerprint; a question already answered is refused. Why: a piece cannot circle on the same question. Tier: LATER. Trigger: pieces circle on one question.
- **Time and budget defaults of the earlier plan**
  What: 120 minutes per piece, 480-minute run budget, 3 CI rounds, review 2 rounds. Why: replaced: no run limit, no CI round cap, attempts rather than minutes. Tier: LATER (dropped).

## 18. Things the papers dropped or replaced

Kept here so the reasoning is not lost.

- **Idle timer for builders (30 asks, 45 stops)**: dropped. Idle timers kill agents waiting on long builds.
- **Run budget of 480 minutes**: dropped. A run has no limit on a subscription.
- **CI round cap and GitHub-only failure case**: dropped. There is no second check layer on GitHub.
- **Auto-approve policy with six conditions (earned history, GitHub protecting main)**: dropped for per-run pre-approval with four conditions.
- **Take-out and re-check of a red joined piece**: replaced by trial joins in a scratch copy.
- **Scratch files removed before merge**: replaced by a git-ignored run folder.
- **Six shaping sub-states and the answer-marker rule**: replaced by the computed needs list.
- **Single fresh readiness checker**: replaced by two fresh test lists.
- **Dependency field in the spec**: replaced by GitHub blocked-by links.
- **Local-only protection for private repository** and **Claude Code push notification**: replaced by layered guards and GitHub mentions.
- **Second GitHub check layer per piece (finding B4)**: not adopted. A final local combined check takes its place.
- **Coordinator starts all agents**: dropped. The run script starts `claude -p` workers itself.
- **Migration tooling for old projects**: dropped.
- **Watch restarts the run, stops stuck attempts, gives up after three restarts**: moved into launchd and the run script; the watch only checks the heartbeat.

## 19. Core review lessons (from the first build)

The first build found gaps between decided rules and what shipped. These are
reasons, not features. They guide the restart.

- **A green rehearsal can assert a limitation.** A passing test is not proof that a rule holds.
- **A skip counted as a pass is a hole.** A check that did not run is never green.
- **Guard paths must be the real installed paths.** A guessed plugin path left an independent layer empty.
- **Opaque command forms bypass text parsing.** The parser must refuse what it cannot inspect, and the sandbox must hold the rest.
- **A stand-in does not enforce the sandbox.** Every sandbox claim needs a real smoke case.
- **Fingerprints must keep meaningful whitespace.** Otherwise a spec change can hide.
- **A judge needs complete execution evidence.** An empty or partial report is not a pass.
- **Hidden cases must be validated before ready.** A broken hidden case discovered late wastes a run.
- **Rebase advice conflicts with no-force-push.** Recovery must use merge commits.
- **Local main may be stale.** Ready and claim need proof of current origin.
- **A project lock must be atomic.**
- **Reviewer cost counted as zero when unreadable** leaks spend caps.
- **A scaffold piece must not be offered when a runner already exists.**
- **In-process forgery by arbitrary script** cannot be stopped by text guards; the sandbox and an inaccessible App key must hold that boundary.
- **A distribution choice is needed** for the separate private kit checkout in hosted checks.
- **Some Proposed items were never placed**: memory-pressure back-off, per-builder ports and data, walk-through with sample data, branch removal on merge, parent closing with last part, unreachable-GitHub semantics, the first upload. They stay LATER until a run needs them.
