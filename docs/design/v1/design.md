# AI Loop Kit v1: design

Second draft, updated with the maintainer's decisions of 5 October 2026

AI Loop Kit v1 is a state machine for building software with agents. Every piece is a GitHub issue in exactly one of seven states, and only the gate moves it. Each design element carries one label. **Decided** means the maintainer settled it on 5 October 2026, in conversation or by answering the first draft's questions and the research. **Proposed** is a recommendation the answers did not settle. **Open** is a question that remains; the open questions are listed at the end of "Decisions taken on 5 October 2026".

## Principle and scope

Shaping is the work, and the build is a loop. The kit spends its effort before the build, so that a piece can then be built with nobody watching.

- **Decided.** v1 lives in gwpicard/ai-loop-kit, which is already a new repository. It replaces AI Build Kit entirely. AI Build Kit's files are removed gracefully and carefully, by a removal plan that says what to borrow first, what to delete, and in what order, so nothing breaks mid-way (see Next steps).
- **Decided.** v1 is written from scratch. AI Build Kit is a source of ideas and of tested code to borrow, not a base to adapt.
- **Decided.** Shaping removes every ambiguity from a piece, so that it can be built with nobody watching. The person can walk away while the work continues.
- **Decided.** The kit is a state machine. Every piece is a GitHub issue in exactly one state, and it moves only through gates. Each state is a loop with an entry gate, a work loop, an exit gate and kickback routes.
- **Decided.** The core runs from the first idea to a merge to `main`. Where `main` is deployed, a merged piece goes live by itself. Live is an extension, not a core state. v1.0 ships its first layer: a health check after each deploy and automatic rollback.
- **Decided.** Merging is never automatic by default. The person merges the pull request on GitHub, or tells the agent to merge. A merge without the person happens only when they pre-approved it before that run started, and even then only when every condition holds.
- **Decided.** v1 adopts GitHub issues, labels, sub-issues and pull requests as its store.
- **Decided.** Claude Code only for v1.0. The gate script and the spec checks stay plain scripts that any agent or person can run, so Codex can be added later as an extension.
- **Proposed.** The reader of everything the kit says is a technical builder who directs agents. They know Git, branches and pull requests, and never have to read code (earlier plan, design note).

### Deterministic checks over instructions

**Decided.** The kit prefers deterministic checks and blocks over written instructions wherever possible. Every important rule is held in at least two independent layers, so that one failing does not open it. The layers to draw on are deny and ask rules in Claude Code settings, hooks that refuse commands, the filesystem sandbox, tokens whose scopes cannot perform certain actions, git hooks, the gate refusing moves, and server-side GitHub settings.

**Decided.** GitHub branch protection is unavailable on a free private repository. Rulesets, required checks, merge queues and push protection are all missing there (gates research, citing [GitHub Docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule)). On such a repository the local layers carry every rule, and `/setup` says so plainly.

| Rule | First layer | Second layer | Status |
| --- | --- | --- | --- |
| No push to `main`, no force push, no recursive delete | Deny rules in Claude Code settings | A hook that parses each command; on a public or paid repository, a GitHub branch rule as well | Decided |
| No hand-written `state:` label | Deny rules | The parsing hook; the gate reports any label it did not write | Decided |
| The frozen bar stays unchanged | Deny rules and sandbox write-blocks on the judge files | The gate compares the bar byte for byte before a piece leaves building | Decided |
| The guards stay in place | Deny rules and sandbox write-blocks on the gate, hooks, settings and workflows | The pre-run check refuses to start while a guard is missing | Decided |
| Agents cannot change settings or workflows | Builders hold no GitHub credential; only the gate holds the GitHub App | Deny rules on the settings and workflow files | Decided |
| No secret leaves the computer | A secret scan before every push | A second secret scan | Decided (two places); Proposed (the gate's push step as the second) |

### One loop, many judges

**Decided.** Every task is a goal with a judge. The four loop modules of the earlier plan (build, fix, goal, gauntlet) collapse into one build loop with four kinds of judge.

| Task | Judge kind | The judge passes when | Status |
| --- | --- | --- | --- |
| Build a piece | Acceptance tests | The piece's acceptance tests pass, and its hidden held-out cases too | Decided |
| Fix a bug | Reproducing test | A test that reproduces the bug passes | Decided |
| Hit a metric | Measurement | A measurement reaches its target, and its hidden held-out twin agrees | Decided |
| Match a reference | Fresh critic | A fresh critic prefers the work to the reference | Decided |

**Decided.** Every judge must fail on today's `main` before a piece is ready, and fail for the right reason: an assertion naming the spec ID it proves, not an import or syntax error. A judge that already passes means there is nothing to build. The first piece in an empty project is the exception. It is a quick-path scaffold and test runner piece, and its judge is that the test command runs.

## Commands

**Decided.** v1 has five commands. There is no separate capture or fix command.

| Command | What it does |
| --- | --- |
| `/setup` | Runs in two halves: "shape and run locally" first, then "make it safe to walk away". The second half creates the GitHub App the gate acts as. It also writes the recipe's network allowlist, asks for spend caps on an API key, and sets up deployment through a recipe. Run it again to add or change deployment. It says plainly when the repository is private on the free plan, with no server-side rules. |
| `/shape` | Captures an idea, or shapes one until it is ready. |
| `/run` | Builds, reviews and combines ready pieces, then opens the pull request. |
| `/maintain` | Finds drift between the records and reality, and decay in code health. Tidies leftovers, turns lessons into checks, and updates the kit. Its findings become new issues in shaping. The kit suggests it every 2 weeks. |
| `/what-now` | Says what is where, what needs the person, how a run is going, and what was decided alone. It is not called `/status`, because Claude Code already uses that name. |

**Decided.** There is no `/approve`. Merging means merging the pull request on GitHub, or telling the agent to merge. Closing the pull request, or commenting a reason on it, sends pieces back.

**Decided.** The second half of `/setup` creates the GitHub App the gate acts as, scoped to this repository. It is a one-time step for the person. The pre-run check names which half of `/setup` is missing.

## The state machine at a glance

A piece moves down the middle only through a gate, and every way back is a named, numbered move. **Decided:** the seven states, and integration inside review on the run's combined branch. Moves are marked one by one in the transition table below.

*Diagram: state machine · 7 states, 14 numbered moves. See the live document: https://claude.ai/artifact/FZwf7EWnuG5ZH94RyW7XCF*

Forward moves run down the middle. Moves 3, 6, 9 and 13 send a piece back to shaping; 7, 8, 12 and 13 send it back a step or more; 14 drops a piece or reopens it into shaping. Parked and waiting for a usage reset are conditions, not states. Parked means waiting on the person inside the current state.

## States

A piece is in exactly one of seven states at any time, shown by exactly one `state:` label on its issue. **Decided:** every piece has one state and moves only through gates, and the states below are the ones the agreed loops use. A `needs-you` flag sits beside the state when the person must answer something.

| State | What it means | Who acts | The loop inside it | Status |
| --- | --- | --- | --- | --- |
| shaping | Not buildable yet. The computed needs list says why. Covers a raw idea, an untriaged issue, and anything needing research, clarification or a prototype. | The person and the agent | The shaping loop | Decided |
| ready | The spec is complete and its judge files are the first commit on the piece branch. The judge fails today. The frozen bar is fingerprinted. Waits for a run. | Nobody; a run picks it up | None; it waits | Decided |
| building | Being built on its own piece branch, one fresh builder session per attempt, judged by the gate. Waiting for a usage reset is a condition inside building, not a state. | Builder sessions, under the run | The build loop | Decided |
| review | Joined to the run's combined branch and checked after each join, then read by a fresh reviewer. A piece needing individual review follows the same steps on its own branch. | The gate and a fresh reviewer | The integration loop, then the review loop | Decided |
| approval | Passed review. Its pull request is open: the run's, or its own. Waits for the merge. | The person, or a merge pre-approved before this run | None; it waits | Decided |
| done | Merged to `main`. The issue is closed as completed. | Nobody | None (Live follows where `main` is deployed) | Decided |
| dropped | Closed on purpose, with a reason. Can be reopened into shaping. | The person | None | Proposed |

**Decided.** `needs-you` is also a label. It is a flag, not a state. The gate adds it when a piece's computed needs include something only the person can answer, and removes it when none are left. The person never sets it. GitHub's own issue list can then filter the pieces waiting on the person.

**Decided.** Parked has one meaning: the piece waits on the person inside its current state, with the `needs-you` flag set, while the run carries on. A route that sends a piece to shaping is called back to shaping, never parked.

**Proposed.** There are no other states. Blocked, queued and idea are not states. **Decided:** being held up by another piece is a GitHub blocked-by link, and the spec has no dependency field.

**Proposed.** A parent issue with parts (sub-issues) carries no state. Its parts carry the states, and the parent closes when its last part is done (earlier plan, design note).

## Transitions and gates

These fourteen moves are the only ones the gate allows; it refuses anything else and names the reason and the next step. **Decided:** pieces move only through gates, and the moves that the agreed loops define. Integration now happens inside review, on the run's combined branch.

| # | From | To | Gate and checks | Status |
| --- | --- | --- | --- | --- |
| 1 | new issue | shaping | Capture by `/shape`, in the person's words. No other checks. | Decided (capture); Proposed (no checks) |
| 2 | shaping | ready | The ready gate. The needs list is empty. The lint passes, then two fresh sessions' test lists cover the same spec IDs. The judge files are the first commit on the piece branch and fail on `main`, on an assertion naming a spec ID. The must-stay-the-same checks pass on `main`. Every sensitive area carries the risk notice and the person's acceptance on the issue. The gate takes the fingerprint. | Decided |
| 3 | ready | shaping | With a reason: the person pulled it back, the fingerprint changed, or the claim's research check found a finding it cannot confirm or whose new answer changes the spec. | Decided |
| 4 | ready | building | The claim gate: fingerprints and a quick check of every research finding, then a free builder slot (3 by default). | Decided |
| 5 | building | review | The gate judges the attempt: frozen bar byte for byte, visible judge then held-out cases, metric target and held-out twin, hypothesis from the list, new-test lint, must-stay-the-same checks, declared touches. Then the trim pass. | Decided |
| 6 | building | shaping | The builder says the bar is wrong (no attempt counted), or 3 attempts are used, or attempts stop making real improvement. | Decided |
| 7 | building or approval | ready | Given back with the spec untouched by anyone but the gate, never counted as an attempt: blocked by the environment, including a command refused inside the piece; the run stopped, from building only, since review and approval wait; or a parked piece whose answer arrives after its run ended, which the gate writes into the spec and re-fingerprints. | Decided |
| 8 | review | building | A trial join turned red, so the trial was thrown away and the combined branch never moved; a merge conflict; or a review finding that became a failing check. The failure and the piece it clashed with are written on it. A piece that had already joined leaves through a rebuild of the combined branch, never a revert. | Decided |
| 9 | review | shaping | A review finding shows the spec was wrong. | Decided |
| 10 | review | approval | The final combined check is green locally and the review is clean. The pull request opens, grouped by piece. | Decided |
| 11 | approval | done | The person merged on GitHub or told the agent to merge, or the merge was pre-approved before this run and every condition holds. Only the exact tested commit merges. One run per project at a time, held by a lock file. | Decided |
| 12 | approval | review | The tested tree changed. If main moved after the final combined check, the combined branch is brought up to date and checked again. If a piece was rejected, the combined branch is rebuilt from main under a fresh name, the accepted joins are replayed and checked again, and a new pull request replaces the old one. | Decided |
| 13 | approval | building or shaping | The person closed the pull request or commented a reason. A comment that names one piece sends back only that piece; the others go back to review through a rebuild (move 12). | Decided |
| 14 | shaping or ready | dropped; and dropped to shaping | With a reason, both ways. | Proposed |

### Rules every move follows

- **Decided.** The gate is the only mover. It runs each move's checks itself and never trusts an agent's word that a check passed.
- **Decided.** A hook that parses commands, and deny rules, stop agents writing `state:` labels directly. The gate alone adds and removes the `needs-you` flag.
- **Proposed.** Every move reads the piece twice: once to check, once just before writing. If another session moved it in between, the gate refuses (earlier plan, slice 2).
- **Proposed.** Each move writes the label and the run record in one step. A failed label write leaves the record unchanged (earlier plan, design note).
- **Proposed.** Each refusal prints what failed and a `next:` command. Each pass prints one line.
- **Decided.** Every move back (3, 6, 7, 8, 9, 12, 13, 14) carries a written reason on the issue. The anti-circle rule applies only to moves back to shaping (3, 6, 9, and 13 when it goes to shaping): each must add a new need to the spec, and a reason already on the piece is refused. Moves 7, 8 and 12 can repeat for good reasons, so they get a counter instead. After 3 of the same kind, the piece goes back to shaping with its history.
- **Decided.** A change the gate makes to the spec itself, such as writing in a late answer, takes a new fingerprint. Only an edit the gate did not make counts as a changed fingerprint for move 3.
- **Decided.** When a run stops, every piece in building goes back to ready (move 7) and keeps its branch. Pieces in review or approval stay where they are and wait.
- **Proposed.** A person who changes a label by hand on GitHub outranks the gate. The gate reports the change and never undoes it.

## Shaping and the computed needs list

Shaping is one state for everything not buildable yet, and the gate works out what a piece still needs from its spec. **Decided:** shaping is one state; what a piece still needs is computed from the spec; and the shaping loop below, as revised with the spec-driven research on 5 October 2026.

### The shaping loop (micro loop 1)

**Decided.** The loop runs on one piece, with the person and the agent together.

1. Choose the path: the quick path for a small change, or the full spec.
2. Take the biggest need on the computed list.
3. Settle it by research, by asking the person, or by a prototype. A crew may research or prototype side by side, but only when the needs list holds a research or design question.
4. Write the answer into the spec. The gate recomputes the needs and sets or clears the `needs-you` flag.
5. Once the cheap lint passes, two fresh sessions each list the tests they would write. The lists are compared by the spec IDs they cover. An ID one list covers and the other does not becomes a need.
6. When no need is left, commit the judge files as the first commit on the piece branch, and try the ready gate.

Because the gate reads the spec rather than a label, a need clears only when its answer is written down. This replaces the earlier plan's six shaping sub-states (raw, research, clarify, prototype, spec, check) and its answer-marker rule.

### What the spec must answer

| Rule | What it holds | Status | Source |
| --- | --- | --- | --- |
| Quick path | A small change takes lighter required fields: one piece, one area, no sensitive area, no new dependency, and a judge that is a single test. | Decided | spec research, item 5 |
| Coverage categories | Each category is answered, or marked not applicable with a reason. Silence becomes a computed need. Examples: permissions, data kept, errors, empty states, what leaves the tool. | Decided (the rule); Proposed (the exact list) | spec research, item 4 |
| IDs on flow steps and edge cases | Each flow step and edge case has an ID. Every acceptance test names the ID it proves. The gate refuses an ID with no test, and a test with no ID. | Decided | spec research, item 1 |
| Edge cases as "When ..., then ..." | Each case names its trigger and what is seen or stored, with a concrete example value. Lint refuses a case with no result. | Decided | spec research, item 9 |
| Limits | Speed, size, accessibility, security or cost limits, each with a number, or the word "none". | Decided | spec research, item 6 |
| Must stay the same | Behaviour that must keep working, proved by checks that pass on `main` at ready and join the frozen bar. | Decided | spec research, item 2 |
| Follow | Existing code to imitate, and any visual. | Decided | spec research, item 10 |
| Changes to current behaviour | Added, changed and removed lines. The run commits them to the overview and area docs before the final combined check. The gate refuses a merge whose named doc the pull request did not change. | Decided | spec research, item 7 |
| One parser, one versioned format | The gate, the lint, the needs list and the fingerprint share one spec parser and a versioned spec format. | Decided | spec research, item 10 |

### Asking the person

- **Decided.** Questions come in small batches with a cap per sitting. Each says why it matters and gives a recommended answer.
- **Decided.** A low-impact unknown becomes a recorded assumption under Decisions, marked as assumed by the agent, for the person's review.
- **Proposed.** The cap is five questions per sitting, as GitHub Spec Kit asks at most five (spec research).
- **Proposed.** Silence is never an answer. An agent never settles a need that names the person.

### Research and crews

- **Decided.** Every research finding records its source, its date and what it rests on: an in-project file with its fingerprint, or an outside page or package version. The claim re-check reads this.
- **Decided.** Shaping crews are in v1, but only when the needs list holds a research or design question. Then several researchers work on different sources and their findings are reconciled, or several prototypes are built side by side for the person to choose from.
- **Decided.** When researchers disagree, the disagreement becomes a need on the piece, settled by the person or by a further check.
- **Decided.** The computer-resource sizing that limits a run also limits a crew.
- **Proposed.** Research gives facts and one recommendation, and never decides (earlier plan, decision 5).

### Judge files, held-out cases and hypotheses

- **Decided.** Shaping cuts the piece's branch from main and commits the judge's test files as its first commit. This is the frozen bar, fingerprinted at ready. The judge files and the code live on the piece branch. Scratch files live in the git-ignored run folder, and held-out cases live outside git.
- **Decided.** Shaping sets aside hidden held-out cases the builder cannot read: a second measurement for a metric piece, and a few hidden cases for an acceptance-test piece. They are stored outside git and outside the issue, in a folder only the gate reads, and the sandbox blocks builders from it. The spec holds only their fingerprint. The gate copies them into the tested tree only at the final combined check, so the person sees them in the pull request.
- **Decided.** For a metric piece, and any piece whose route is open, shaping or the first build step writes the hypothesis list. It is fixed before any attempt (see Building).

### Risk acceptance

**Decided.** A risk acceptance lives on the issue only. The spec's Sensitive areas section holds the risk notice, the person's exact words and the date. The ready gate refuses a sensitive piece without it. Any overview line the acceptance makes untrue is updated in the same pull request as the piece's merge. There is no separate records pull request.

### What the earlier plan brings to shaping

| Item from the earlier plan | What happens in v1 | Status | Source |
| --- | --- | --- | --- |
| Capture in the person's words, and take in an issue opened by hand without duplicating it | Kept as move 1, through `/shape`. | Decided (`/shape` captures); Proposed (detail) | design note; slice 2 |
| Search open and closed issues for a duplicate before filing | Kept in `/shape`. A match gets the new words as a comment. | Proposed | AI Build Kit change-triage |
| Six sub-states, each answering one kind of question | Dropped as labels. Each becomes a kind of need on the list. | Decided | design note; decision 5 |
| Who must be present: research needs nobody; clarifying and prototypes need the person | Kept. Each need names who can settle it, and the `needs-you` flag shows it on GitHub. | Decided | design note, Shaping |
| The question box: one short question with a labelled guess | Replaced by batched questions, each with why it matters and a recommended answer. | Decided | spec research, item 8 |
| Reach check, co-change query and area map | Kept. Shaping fills the spec's touches field from them. | Proposed | design note; slices 4 and 5 |
| Pre-mortem: "Say this went live and went wrong. Who noticed, and what did they see?" | Kept, asked once, only when the piece touches a sensitive area, data or the outside world. | Proposed | design note; slice 4 |
| Risk notice given once in full; carrying on is accepting; the acceptance quotes the person exactly, with the date | Kept, on the issue only. | Decided | settled decision 31 |
| An irreversible data change is marked `not reversible` | Kept as a spec field. It forces the person's merge and a backup first. | Proposed | decision 48 |
| Prototype, and an artifact the person already has, as ways to settle a question | Kept. Several prototypes may be built side by side. | Decided | AI Build Kit clarify |
| Bug fast path | No special path. A small bug takes the quick path. | Decided | decision 38; slice 4 |
| Two-layer piece: a short plain header for the person, then a complete layer for the builder | Kept. The spec block is the builder's layer. | Proposed | design note, piece contract |
| Parts versus blocked-by | Kept. Parts are sub-issues; other pieces are GitHub blocked-by links. | Decided | design note |
| Pieces are vertical slices sized for one sitting; length limits per type | Kept as lint rules and policy defaults. | Proposed | AI Build Kit shape; settled decision 9 |
| Shaping crews: several research readers, several prototype variants | Kept in v1, only when the needs list holds a research or design question. | Decided | decision 44; slice 10 |
| Work on the person's computer, using the tool on content, and speaking for the person | Kept as rules outside the state machine. None of them makes a piece. | Proposed | AI Build Kit change-triage |
| Lessons from closed pieces in the same area read before research | Kept as part of the learning loop. | Proposed | decision 34; slice 17 |

## The ready gate

The ready gate is move 2: the machine lint first, then two fresh sessions' test lists, then the judge files committed and seen failing, then the fingerprint. **Decided** where the answers set it, as marked. The earlier plan built most of the lint already (`ready-lint.py`, slice 3).

| Check | What it holds | Status | Source |
| --- | --- | --- | --- |
| Needs list empty | Nothing the gate can compute is still missing from the spec. | Decided | new in v1 |
| Required fields present | Goal, user story, expected flow with IDs, how to observe it, edge cases in "When ..., then ..." form with IDs, Limits, Must stay the same, Follow, Changes to current behaviour, Not in this piece, judge, links, sensitive areas. The quick path requires fewer. | Decided | spec research |
| Coverage categories answered | Each answered, or not applicable with a reason. | Decided | spec research, item 4 |
| IDs traced | Every ID has an acceptance test naming it, and every acceptance test names an ID. | Decided | spec research, item 1 |
| Refused phrases | "TBD", "decide during build", "for now", "a few", "several" and similar. Vague adjectives such as fast or secure with no number. | Proposed | slice 3; spec research, item 6 |
| Brief rules | Behaviour, not steps. No numbered build-step list. Each criterion checkable alone. | Proposed | design note, piece contract |
| Two fresh test lists | Run only once the lint passes. Two sessions that carry none of the shaping conversation each list the tests they would write. The lists are compared by the spec IDs they cover, not by test name. An ID one list covers and the other does not becomes a need. Many differences mean the piece should be split. | Decided | spec research, item 3 |
| Judge files first on the piece branch | The judge's test files are the first commit on the piece branch, cut from `main`. | Decided | answer 11 |
| The judge fails on its assertion | Each acceptance check runs on today's main in a temporary checkout. It must fail on an assertion naming the spec ID it proves, not an import or syntax error. Every run has a hard timeout. The first piece in an empty project, a scaffold and test runner piece, is judged by the test command running. | Decided | slice 3; settled decision 10 |
| Must stay the same passes | Its checks pass on today's `main`, and join the frozen bar. | Decided | spec research, item 2 |
| Held-out cases set aside | Hidden cases for an acceptance-test piece, a hidden twin measurement for a metric piece. Stored outside git and the issue, in a folder only the gate reads. The spec holds their fingerprint. | Decided | answer 14; research C |
| Test runner reports read | pytest, Vitest, Jest and Node's runner tell an assertion from an error; other runners fall back to the exit code with a note. | Proposed | slice 3 |
| Dependencies resolve, with no cycle | Every GitHub blocked-by link points at a real piece, and the links form no cycle. | Proposed | design note |
| Areas exist in the area map | Every area the spec names is in the map. | Proposed | slice 5 |
| Sensitive areas accepted | Each sensitive area carries the risk notice, the person's exact words and the date, on the issue. | Decided | answer 12 |
| BLOCKING versus NOTE | A gap blocks when closing it changes what a person sees or does, what is stored, or what leaves the tool. | Proposed | AI Build Kit readiness check |
| Fingerprint taken | A hash of the spec block and the judge files commit, written by the gate. The gate takes a new one when it changes the spec itself. | Decided | answer 11; slice 6 |

**Decided.** The ready gate also decides whether a piece needs individual review, with its own branch and pull request. It does so for exactly the five must-look reasons: a sensitive area, irreversible data, a new dependency, a security change, or a piece the person marked.

**Proposed.** A ready piece is never described as safe. The gate cannot judge domain quality, polish or platform quirks, and says so (AI Build Kit readiness check).

**Proposed.** There is no per-piece human approval at the ready gate. The person's part is answering the needs that name them, and accepting any risk (decision 6).

## The claim re-check

**Decided:** at every claim, the run re-checks the piece to confirm nothing changed since it became ready, and always does a quick check of every research finding. A smart escalation decides when a fuller refresh is needed. These checks make up the claim gate (move 4). A piece that fails goes back to shaping with the reason (move 3).

### Research staleness

**Decided.** Research goes stale by fingerprint and by age, and is always checked quickly at build time.

1. Every finding records its source, its date and what it rests on: an in-project file with its fingerprint, or an outside page or package version.
2. At every claim, the run does a quick check of every finding: the fingerprint for an in-project one, the version and age for an outside one.
3. A fuller refresh is needed when a fingerprint changed, a version changed, a finding is past the age limit, or the quick check disagrees. The run then re-researches that finding.
4. Only a finding it cannot confirm, or one whose new answer changes the spec, sends the piece back to shaping. Otherwise the refreshed finding is written into the spec and the build goes ahead.

**Proposed.** The age limit is a policy-file value, set after the first real runs.

### The other checks at the claim

| Check before the claim | What it catches | Status | Source |
| --- | --- | --- | --- |
| Fingerprint unchanged | The spec or the judge files were edited after ready. | Decided | answer 11; slice 6 |
| Research quick check, and a fuller refresh when needed | A finding that no longer holds. | Decided | answer 4 |
| Spec lint passes again on today's `main` | A rule broken by a change elsewhere. | Proposed | slice 9 |
| The judge still fails on today's `main` | Someone already built it, or `main` moved under it. | Proposed | slices 3 and 9 |
| Must-stay-the-same checks still pass on today's `main` | Behaviour already broken before the build starts. | Proposed | spec research, item 2 |
| Relied-on code unchanged | The reach is worked out again; a commit that changes a relied-on file sends the piece back. | Proposed | design note; slice 9 |
| Blockers done | Every blocked-by piece is done, or built earlier in the same run, in which case this piece stacks on its branch. | Proposed | slice 2 |
| Not already building | A second claim on the same piece. | Proposed | slice 2 |
| No running piece touches the same area | Two builders changing the same area at once. | Proposed | design note; decision 33 |
| Free builder slot | Slots are sized from free memory and capped at 3 by default. Without one, the piece stays ready. | Decided | run loop, agreed |

## Building

A piece in building runs the build loop on its own piece branch, one fresh builder session per attempt, and the gate judges every attempt. **Decided:** the build loop below, as agreed on 5 October 2026.

### The build loop (micro loop 2)

- **Decided.** Every attempt is a fresh, non-interactive builder session (`claude -p`). It gets only the frozen spec, the gate-kept attempt log and, for a metric piece, the next hypothesis from the list. It never sees past session history or the held-out cases. Long sessions full of failed approaches get worse, and clean restarts win (agentic loops research, item 8).
- **Decided.** A builder cannot ask questions. It has one "needs the person" tool, which parks the piece and returns at once.
- **Decided.** Every attempt ends with a fixed hand-off: done, bar is wrong, needs the person, blocked by environment, or gave up.
- **Decided.** The gate judges, never the builder. In order: the frozen bar, byte for byte (a change is a failed attempt, logged as possible gaming); the visible judge, then the hidden held-out cases; for a metric, the target and its held-out twin; the hypothesis tested is on the list; the new-test lint; the must-stay-the-same checks; the diff stays inside the declared touches.
- **Decided.** A pass goes to the trim pass, then to review. Tokens are recorded for each piece.

### Outcomes

**Decided.** Every outcome has one route.

| Outcome | What happens | Counts as an attempt | Move |
| --- | --- | --- | --- |
| The gate passes | The trim pass, then review | No | 5 |
| The gate fails, attempts left | The next attempt, in a fresh session | Yes | stays in building |
| 3 attempts used, or no real improvement | Back to shaping with every attempt's findings | Yes | 6 |
| Bar is wrong | Back to shaping with the builder's evidence | No | 6 |
| Needs the person | The piece is parked inside building and the run carries on. An answer in the same run resumes it. Otherwise the gate writes the answer into the spec, re-fingerprints it, and the piece goes back to ready. | No (Proposed) | stays, or 7 |
| Blocked by environment | Back to ready with a note. A command refused inside the piece counts here. | No | 7 |
| Usage limit reached | Waiting for reset; the run script resumes it | No | stays in building |
| Stuck | The run script stops the attempt | Yes | stays, or 6 when none are left |
| Gave up | Treated as a failed attempt | Yes (Proposed) | stays, or 6 |
| Bar changed, or a test removed, skipped, loosened or retried to pass | A failed attempt, logged as possible gaming | Yes | stays, or 6 |
| Held-out result much worse than the visible one | Treated as gaming: a failed attempt | Yes | stays, or 6 |

**Decided.** "Bar is wrong" is a sanctioned outcome. ImpossibleBench found that an explicit way to flag an impossible task cut cheating sharply, from 54% to 9% for GPT-5 (agentic loops research, item 2). The run takes the next independent piece.

### Budgets and stuck

- **Decided.** Each piece gets 3 attempts, or fewer when attempts stop making substantial improvement, for example a goal metric that no longer moves.
- **Decided.** A piece has no time limit, because it can take time for good reasons. Only a clearly stuck attempt is stopped.
- **Decided.** Stuck means the same error 3 times in a row, the same change undone and redone, or a test run past its hard timeout. The run script detects it, since it sees the builder's output. Every test and judge run has a hard timeout. Idle timers were rejected, since they kill agents waiting on long builds (agentic loops research, item 4).
- **Decided.** On a subscription, a run has no limit; it depends on how many pieces it has. On an API key, `/setup` asks for a spend cap per piece and per run, passed to each builder as `--max-budget-usd`. Reaching a cap waits for the person.
- **Decided.** A usage limit pauses the piece as waiting for reset. It is never counted as an attempt.
- **Proposed.** The gate, not the builder, decides "no substantial improvement" from the judge results. The hard timeout defaults to ten minutes per check, the earlier plan's limit.

### Anti-gaming

- **Decided.** The judge and everything it rests on (tests, measurement scripts, fixtures, references, test settings) are frozen at ready and checked byte for byte before a piece leaves building. Removing, skipping, loosening or retrying a test to pass counts as a failed attempt, never a pass.
- **Decided.** Held-out cases: the gate runs the hidden cases, or the hidden twin measurement, when the builder claims the target. They live outside git and the issue, in a folder only the gate reads. A hidden result much worse than the visible one is treated as gaming. Read-only tests do not stop special-casing, so hidden cases are the second guard (agentic loops research, item 3).
- **Decided.** The hypothesis list is written before building and fixed before any attempt. Each attempt names the hypothesis it tests and records the result, so neither the target nor the means can change after the fact. A new hypothesis may be added only in the goal's direction, with the reason recorded. Anything outside the list or against the goal is refused, or sent back to shaping.
- **Decided.** A lint on new tests: a test the builder adds must assert something, must not be skipped, and must not mock the project's own code (gates research, item 7, citing [Matt Pocock's tests guide](https://github.com/mattpocock/skills/blob/main/skills/engineering/tdd/tests.md)).
- **Proposed.** Where a mutation testing tool is already a dependency, the gate breaks the changed code once the build is green. A check that notices nothing is a worth-knowing item in the pull request, not a must-look reason. No score ever gates (decisions 46 and 47).

### The trim pass

- **Decided.** The trim pass stays in v1 as the last step of the build loop. It may only remove or fold. It never touches tests, and changes only code this piece added. It sits in its own commit, which is thrown away if any check fails afterwards.
- **Decided.** Later, well-defined checks will be written for it, researched from Matt Pocock's list of such checks (for example tautological tests).

### What each judge kind adds

| Judge kind | Rules carried over | Status | Source |
| --- | --- | --- | --- |
| Acceptance tests (build) | Tests exist and fail before any code, each naming the ID it proves. Hidden held-out cases. Type check and linter run before hand-over. | Decided (IDs, held-out); Proposed (the rest) | answer 14; AI Build Kit section-builder |
| Reproducing test (fix) | No code change before the reproduction is seen to fail. Read the history first. Two to five ranked causes, each falsifiable, one at a time. Remove every temporary log. | Proposed | decision 36; AI Build Kit fix loop |
| Measurement (goal) | The metric command's last line is a number. A change is kept only when the number moved and guard checks stay green. The hypothesis list and the held-out twin apply. | Decided (hypotheses, twin); Proposed (the rest) | answer 14; slice 11 |
| Fresh critic (reference) | Critics see the work and the reference only as A and B, in both orders, and must agree. A split or tie is not a win. | Proposed | settled decision 18; slice 12 |
| Outside critic | An available choice from v1. When a reference-match piece is shaped, the kit asks whether to use a critic from another vendor (Codex, if installed and signed in, with the person's agreement that content goes to that provider). Otherwise the critic is a fresh Claude session. The choice can be changed later in the policy file. | Decided | answer 15 |

### Around the build

| Item | What happens in v1 | Status | Source |
| --- | --- | --- | --- |
| Scratch files | Attempt notes, the frozen spec copy, judge logs and the run's working state live in a git-ignored run folder, not on the piece branch. Nothing has to be removed before merge, so they never reach main or cause conflicts. Acceptance tests stay as ordinary project tests. A cheap judge (a measuring script) may stay as a regular check; an expensive one (a reference critic) is dropped. What must last goes in the issue or the changelog. | Decided | answer 11; red team, simplification 2 |
| Throwaway values in each worktree | Builders never read a real env file. Each worktree gets throwaway values. | Decided | answer 9 |
| A worktree per piece; the main folder never switches branch | Worktrees live in `.agents/worktrees/`, which git ignores. | Proposed | AI Build Kit running-longer |
| One local app and seeded data per builder | Each builder gets its own port and its own seeded data. | Proposed | slice 14; settled decision 30 |
| Walk-through with sample data, and the means to look | Kept. What could not be seen is named. | Proposed | AI Build Kit section-builder |
| Kickback section on the issue, with the branch kept | Kept. Shaping reads it first when the piece comes back. | Proposed | design note, Kickback |
| Evidence for the learning loop | Collected on every kickback and finding. | Decided | learning loop, agreed |
| No live service change without a yes; no stored logins | Kept. An unattended run leaves such a command unrun. | Proposed | AI Build Kit section-builder |

## Review and integration

In review, the run first joins each built piece onto one combined run branch and checks the result, then a fresh reviewer reads the specs and the combined diff. **Decided:** both loops below, as agreed on 5 October 2026. All of a run's pieces are combined because all changes are expected to work together, and the relevant checks run on the combined result.

### The integration loop (micro loop 3)

**Decided.** The loop runs once per run.

1. At the start of the run, cut a combined branch from `main`.
2. Join each built piece in dependency order, one at a time, as a trial merge in a scratch copy of the combined branch, brought up to date with main first. Tests are kept; scratch files are never committed.
3. In the trial, re-run every joined piece's judges (visible and held-out), the must-stay-the-same checks and the check that each diff stays inside its declared touches.
4. Only on green does the combined branch move forward to the trial commit. On red, the trial is thrown away and the piece just joined goes back to building, with the failure and the piece it clashed with written on it. The trial is the check: there is no take-out step, no revert, and no re-check without it. The rest of the run carries on.
5. A merge conflict is treated the same way. Agents never resolve conflicts across pieces. Each join commit carries a `Piece: #n` trailer, so joins are idempotent: a resumed run reads the combined branch to see which joins are done.
6. After the last join, the run commits each piece's behaviour change to the overview and area docs, and folds the changelog, so they are part of the tested tree. Then a final combined check runs locally: the full project checks, the validator if the project has one, and every judge. A failure sends only the relevant pieces back.

- **Decided.** A piece that needs individual review is not joined. It follows the same steps on its own branch and its own pull request. A piece that depends on it stacks on its branch and needs individual review too.
- **Decided.** When a piece must leave the combined branch after it joined, because review sent it back or the person rejected it, nothing is reverted and nothing is force-pushed. The run rebuilds the combined branch from main under a fresh name, replays the accepted joins, and checks again. A new pull request replaces the old one.
- **Decided.** There is no second check layer on GitHub, per piece or per run. The research proposed one (finding B4); it was not adopted in full, and the final local combined check takes its place.
- **Decided.** The gate, not the builder, judges flakiness, by running the same commit again (research finding E).
- **Proposed.** Bringing a branch up to date uses a merge commit, never a rebase, so no force push is ever needed (slice 9).
- **Proposed.** Waiting for GitHub's checks is one `gh pr checks --watch --fail-fast`, never a sleep loop. "No checks" is never green (AI Build Kit merge step).
- **Decided.** Individual review is decided in shaping, at the ready gate, for exactly the five must-look reasons: a sensitive area, irreversible data, a new dependency, a security change, or a piece the person marked.

Each join re-runs the joined pieces' own judges, not only the project check, because about 28% of agent pull requests conflict ([AgenticFlict, 2026](https://arxiv.org/abs/2604.03551), cited in the agentic loops research) and separate worktrees do not prove two changes are compatible.

### The review loop (micro loop 4)

- **Decided.** A fresh reviewer sees only the specs and the combined diff, piece by piece. It never sees a builder's account.
- **Decided.** Every finding becomes one of three things: a failing check (the piece returns to building, move 8), a shaping issue (the spec was wrong, move 9), or a worth-knowing note.
- **Decided.** A new test that comes from a finding joins the frozen bar, with a written justification for the person to review.
- **Decided.** Up to 2 review rounds. A finding still left after them sends that piece back to shaping (move 9), with the finding as a need and the `needs-you` flag set. The combined branch is rebuilt without it, and the others go ahead.
- **Decided.** The outside critic, when chosen, is an advisory second reviewer. It sends nothing back unless a check reproduces its finding. One study found Codex reviewing Claude's code lowered pass rates from 91.4% to 82.8% ([Xiang and others, 2026](https://arxiv.org/abs/2607.21656), cited in the agentic loops research), a reason for caution rather than a rule.
- **Decided.** When review is clean, the run opens one pull request, grouped by piece, with each piece's evidence. Its pieces move to approval (move 10). A pull request that grows too large is split.
- **Decided.** Review never stops the loop. The run moves on to other pieces while one waits.
- **Decided.** Each piece's evidence in the pull request: judge results, the held-out result, any mutation result, the review verdict, and the preview deployment link where the recipe gives one. Worth-knowing items sit there too: decisions made alone, the first deployment, new tests from review, flaky results and changes outside the piece's areas (agentic loops research, item 10).
- **Proposed.** Each gap has a kind: missing, partial, contradicts or unrequested. There is no same-session fallback when no fresh reviewer is available (slice 8).

### Reasons that force the person to look

**Decided.** The must-look list is exactly five reasons, and only the gate writes it. Any one of them gives a piece individual review, and a pre-approved merge cannot go ahead while any piece has one. Decisions made alone do not block pre-approval.

| Must-look reason | Where it comes from |
| --- | --- |
| A sensitive area | The spec's Sensitive areas |
| An irreversible data change | The spec's not reversible mark |
| A new dependency | The spec, at the ready gate |
| A security change | The spec, at the ready gate |
| The person marked the piece | The person |

The other reasons on the earlier list, such as decisions made alone, the first deployment, new tests from review, flaky results and changes outside the piece's areas, are no longer must-look reasons. They appear as worth-knowing items in the pull request.

## Approval and the merge decision

A piece in approval waits on an open pull request: the run's, grouped by piece, or its own when it needed individual review. **Decided:** merging is never automatic by default, and the rules below.

- **Decided.** Approval applies to the run's pull request, or to an isolated piece's own.
- **Decided.** The person merges the pull request on GitHub, under their own account, or tells the agent to merge. There is no `/approve` command.
- **Decided.** Closing the pull request, or commenting a reason on it, sends the pieces back to building or shaping, with the reason written on each (move 13).
- **Decided.** Only the exact tested commit merges (`gh pr merge --match-head-commit`). The tested tree must be the merged tree ([bors](https://bors.tech/), cited in the gates research). Only one run per project runs at a time, held by a lock file.
- **Decided.** If main moved after the final combined check, nothing merges until the combined branch is brought up to date and checked again (move 12). A free private repository cannot stop the person merging anyway. If they do, a check runs on main after the merge.
- **Decided.** Before the final combined check, each piece's behaviour change is committed to the overview or area docs, and the changelog entries are folded, in the run's pull request. So the merge adds no commit nobody tested.
- **Decided.** A comment that names one piece sends back only that piece. The combined branch is rebuilt from main under a fresh name with the others, checked again, and a new pull request replaces the old one (move 12).
- **Proposed.** A yes to the agent must name the merge. "Put it live" is not that yes (AI Build Kit merge step).
- **Proposed.** Where every merge goes live, Claude Code shows a confirmation box before `gh pr merge` (AI Build Kit merge ask rules).
- **Proposed.** An irreversible data change is always the person's merge, after a backup taken before the migration (decision 48).
- **Proposed.** Only a pull request's `Closes #<n>` lines close pieces, one line per piece. No closing word appears before any other number, since GitHub closes on it even in a sentence saying it does not.

### Merges pre-approved before a run

**Decided.** The default is no. When `/run` starts, it asks whether the merge is pre-approved for this run. The answer covers that run only and is never a standing setting. Even when pre-approved, the merge goes ahead only when all of these hold; otherwise it waits for the person:

- green checks on the up-to-date combined branch;
- every judge passing, with an unchanged bar;
- a clean fresh review;
- no piece with a must-look reason.

These four conditions were proposed on 5 October and not objected to. The earlier plan's auto-approve policy and its six conditions (including an earned clean history and GitHub protecting `main`) are dropped.

## Done, dropped and the Live extension

Done means merged to `main`; dropped means closed on purpose with a reason; going live sits after done. **Decided:** Live is an extension, not a core state. v1.0 ships its first layer through the deploy recipe in `/setup`: a health check after each deploy of `main`, run as a small GitHub Action so it works with the laptop off, and automatic rollback to the last good deployment. After a rollback the kit opens a revert pull request and a bug issue, and sends a "production is pinned" notification. Error reporting and tracing come later, by the plan in the next section.

### Done

- **Proposed.** The merging pull request closes each piece's issue as completed, through its `Closes #<n>` line. The gate then takes the state label off.
- **Decided.** Scratch files never reach main. They live in the git-ignored run folder and are never committed, so nothing has to be stripped at merge.
- **Proposed.** The branch is deleted on merge. The worktree is removed once the pull request has closed and nothing in it is unsaved, never by force (AI Build Kit worktrees).
- **Decided.** `/maintain` tidies leftovers. **Proposed:** it lists old branches whose work is in `main` with the commands to remove them, and never removes them itself.
- **Proposed.** A project nobody hosts (`Goes live: not hosted`) treats a merge as done, and makes a release only on a yes naming it (decision 50).

### Dropped

- **Proposed.** A piece nobody will do is closed as not planned, with its reason. It can be reopened into shaping (move 14).
- **Proposed.** `/shape` searches dropped pieces before filing, so a rejected idea is not rebuilt by accident.

### Live in v1.0

| Item | What happens in v1 | Status | Source |
| --- | --- | --- | --- |
| Health check after each deploy of `main` | Runs as a small GitHub Action after each deploy of main, about a minute per deploy, so it works with the laptop off. On failure: the automatic rollback below. | Decided | answer 19 |
| Automatic rollback | On a failed health check, roll back to the last good deployment. Then open a revert pull request and a bug issue in shaping, and send a "production is pinned" notification. | Decided | answer 19 |
| Set up through `/setup` | Both are part of the deploy recipe. Running `/setup` again adds or changes deployment. | Decided | answers 7 and 19 |
| "Went live, or a live check failed" | One of the six notifications, sent once per event. | Decided | answer 18 |
| Recipes: one stack paired with one host, the only place a product is named | Kept. | Proposed | AI Build Kit recipes |
| A `Goes live:` line: `on every merge` or `not hosted` | Kept. A missing line means not set up. | Proposed | slice 14 |
| The first deployment runs the first-launch checks once | Kept. It is a worth-knowing item in the pull request, no longer a must-look reason. | Decided (not must-look); Proposed (the checks) | design note; slice 13 |
| Deploy once: read the whole output before any second deploy | Kept. | Proposed | AI Build Kit ship |
| Error reporting and tracing into issues | Later. | Decided (later) | answer 19 |
| Preview deployment link | Put in each piece's evidence, where the recipe gives a preview per branch. | Decided | red team, finding 17 |

## Live extension: plan for later

**Proposed, and later.** v1.0 ships only the health check and rollback above. The two later layers turn production errors, then slow requests, into grouped issues that enter shaping. Each layer ships only after its end-to-end test passes on a throwaway project and one real run on a real project.

| Stage | What it adds | Status |
| --- | --- | --- |
| 0. Health and rollback | A health check, run as a GitHub Action after each deploy of main; on failure, rollback, a revert pull request, a bug issue and a "production is pinned" notification. | Decided, v1.0 |
| 1. Errors into issues | Production errors grouped into bug issues in shaping. | Proposed, later |
| 2. Slow requests and tracing into issues | Performance signals measured against each piece's Limits, as issues in shaping. | Proposed, later |

### Stage 1: errors into grouped issues

- **What is set up.** The deploy recipe adds an error reporting tool to the app and its key to the host's settings. The recipe is the only place the product is named. No key enters a tracked file, and agents never read it. Personal data is scrubbed in the app before any event leaves it.
- **How events become issues.** A small intake script, run on a schedule, reads new error groups from the tool. For each group past the threshold it asks the gate to capture a bug issue. The gate stays the only mover; the intake never writes labels itself.
- **Grouping.** One issue per error group, keyed by the tool's own grouping (error type and where it was thrown). Later events add to a count on the same issue, at most once a day, instead of new issues.
- **Noise control.** A group opens an issue only past a threshold of events or affected users in a time window, both policy-file values. An ignore list lives in the policy file. A daily cap on new live issues sends the rest into one digest issue. A group that returns after its fix was merged reopens its issue as a regression.
- **Tying errors to merges.** Each deploy carries the merge commit as its release marker, so a new group can name the merge it first appeared after. That feeds the change-fail rate `/maintain` reports.
- **How it feeds shaping.** The issue body holds the error message, where it was thrown, the release, first and last seen, the count and the affected route. Error text is treated as data, never instructions, since it can carry text from outside. The gate computes the needs as for any bug: a reproducing test as the judge.
- **What the person sees.** `/what-now` lists live issues. A new group that crosses the threshold sends "a live check failed", once, and follows the quiet hours. The `needs-you` flag appears only when a need names the person.
- **How it is tested.** A stand-in for the error tool replays recorded events into a throwaway project, as the GitHub stand-in does today. Tests cover grouping, thresholds, the daily cap, regression reopening, scrubbing, and error text kept as data. One end-to-end test deploys a deliberately broken change and expects exactly one issue in shaping, which its fix later closes.

### Stage 2: slow requests and tracing into issues

- **What is set up.** The recipe turns on request tracing in the app, using the host's or the tool's standard tracing support.
- **How signals become issues.** The same intake reads, per route, the slow-request time and error rate over a window. A route past a number from a piece's Limits field, or a policy default, gets one issue.
- **Grouping and noise.** One open issue per route and signal. A signal must stay past the limit for a sustained window before an issue opens. Updates are added to the same issue.
- **How it feeds shaping.** The issue is shaped as a metric piece: the measurement judge, its target taken from the Limits field, and a held-out twin measurement.
- **What the person sees.** As in stage 1, through `/what-now` and one notification per new issue.
- **How it is tested.** A throwaway project with one deliberately slow route under synthetic load. The test expects one issue naming that route and its number, and none for the fast routes.
- **Decided later.** Which error reporting and tracing tools the deploy recipe names for these later layers is decided when this extension is planned.

## Loops: meta and micro

Micro loops work on one piece, or one run's pieces, inside one state; meta loops work across pieces or around the whole system. **Decided:** four micro loops (shaping, build, integration, review) and five meta loops (run, watch, learning, maintenance, live feedback), as agreed on 5 October 2026.

*Diagram: loop hierarchy · 5 meta loops, 4 micro loops. See the live document: https://claude.ai/artifact/FZwf7EWnuG5ZH94RyW7XCF*

The shaping loop feeds ready pieces to the run, which holds the build, integration and review loops. The run script runs under launchd, which restarts it, and the watch only checks that its heartbeat is fresh. Learning, maintenance and live feedback all send their findings back into shaping as checks or new issues.

| Loop | Kind | Works on | Ends when | Status |
| --- | --- | --- | --- | --- |
| Shaping loop | micro | one piece in shaping | The needs list is empty and the ready gate passes | Decided |
| Build loop | micro | one piece in building | The gate passes; or 3 attempts or no real improvement; or the bar is wrong | Decided |
| Integration loop | micro | a run's built pieces, joined one at a time | The final combined check is green | Decided |
| Review loop | micro | the combined diff, piece by piece | Review is clean, or 2 rounds are used | Decided |
| Run loop | meta | the pieces the person picked | One pull request (plus isolated ones), the morning summary and the lessons | Decided |
| Watch loop | meta | the run's heartbeat | Never while a run goes; it only checks that the heartbeat is fresh, and notifies once when it is not | Decided |
| Learning loop | meta | evidence from runs, kickbacks and findings | Each lesson has become a check, or been removed | Decided |
| Maintenance loop | meta | the whole project, through `/maintain` | Findings are issues in shaping, small tidying is done | Decided |
| Live feedback loop | meta | each deploy of `main`; later, errors and slow requests | Each failure is rolled back, with a revert pull request and a bug issue in shaping | Decided |

### The learning loop

- **Decided.** Evidence is collected at run end and on every kickback or finding. A pattern seen at least twice becomes a lesson candidate.
- **Decided.** Lessons need evidence, and become checks first wherever possible. Model-written context files lowered success by about 3% in one study ([ETH Zurich, 2026](https://arxiv.org/abs/2602.11988), cited in the agentic loops research), so a check beats a written line.
- **Decided.** During a run, lessons are only proposed. They take effect at the start of the next run, after the pre-run check, each as its own commit the person can see. So the frozen bar never changes under pieces in flight.
- **Decided.** Stale lessons are offered for removal.
- **Decided.** A hook logs every command the agent runs, refuses or retries, so lessons and investigations have a record to read.

### The maintenance loop

- **Decided.** The kit suggests `/maintain` every 2 weeks.
- **Decided.** It checks drift between the records and the code, code health (including mutation testing), delivery health (change-fail and rework rates), tidying, and kit updates.
- **Decided.** Findings become issues in shaping. Small tidying is done directly and logged.

## The run

A run is a plain script started by `/run`, not an agent. It starts each builder as a separate non-interactive Claude Code session (`claude -p`) that cannot ask questions. **Decided:** the run as agreed on 5 October 2026.

The reason is mechanical. The earlier run's coordinator stood still because it asked a question and waited. In `-p` mode with questions refused, a session cannot stop for the person ([permission modes](https://code.claude.com/docs/en/permission-modes), cited in the agentic loops research, item 1).

### Before the run starts

- **Decided.** A pre-run check refuses to start, with the reason, unless every guard is in place (deny rules, hooks, the sandbox and its network allowlist, the gate untouched, the gate's GitHub App), the policy file is readable, the computer's power, sleep, memory and disk are fine, and `main` is green. It refuses a run script that passes `--bare`, which skips hooks, and every builder gets the guard settings with `--settings`. It names which half of `/setup` is missing, and refuses while another run holds the project's lock.
- **Decided.** The run asks two things, once: which pieces, and whether the merge is pre-approved for this run. The default is no.
- **Proposed.** A malformed policy value stops the run, naming the key.
- **Proposed.** A project whose code is not on GitHub yet asks for the first upload, naming the repository and whether it is public or private, and builds nothing until then. A project whose `origin` is the kit's own repository pushes nothing and opens no issue (slice 9; AI Build Kit first upload).

### What the run does, in order

1. Plans the pieces by dependency and area, and shows serial chains first, before the run starts.
2. Cuts the combined branch from `main`.
3. Claims pieces as builder slots free up, each after the claim re-check. Slots are sized from free memory and capped at 3 by default in the policy file.
4. Routes each build outcome (see Building).
5. Joins each built piece to the combined branch and checks after each join (the integration loop).
6. At every step, reads GitHub comments and the local mailbox, writes the heartbeat and the run record, and sends notifications without waiting for them.
7. Runs the final combined check, then the review loop.
8. Opens one pull request grouped by piece, plus any isolated ones.
9. Merges only if pre-approved and every condition holds. Otherwise it waits for the person's merge on GitHub.
10. Closes with a morning summary, the "run finished" notification, and lessons for the learning loop.

- **Decided.** After a crash, the run resumes from the run record and the `Piece:` trailers on the combined branch, without redoing finished work.
- **Decided.** An answer to a parked question that arrives after the run has ended is written into the spec by the gate, which re-fingerprints it. The piece goes back to ready (move 7) and waits for the next `/run`. The person is told the piece is back in ready with their answer, so they know something happened.
- **Decided.** On a subscription a run has no limit of its own. On an API key the spend caps apply (see Budgets and stuck).
- **Decided.** The run script runs under launchd with `KeepAlive`, which restarts it at once if it dies, and under `caffeinate`, which keeps the computer awake while it runs.
- **Decided.** One run per project at a time, held by a lock file.
- **Decided.** The run's scratch files (attempt notes, the frozen spec copy, judge logs, run state) live in a git-ignored run folder, never on a branch.

### Run details from the earlier plan

| Item | What happens in v1 | Status | Source |
| --- | --- | --- | --- |
| A run record, git-ignored | Kept. A new session resumes from it, never from memory. Labels win where the record is behind. | Decided (record and resume); Proposed (path `.agents/runs/<name>/run.json`) | slice 9 |
| Builders started by the script | The script starts `claude -p` workers itself. The earlier rule that a coordinating session starts every agent is dropped. | Decided | research finding A |
| Builder count from the computer | Sized from free memory, capped at 3 by default. The earlier way to read free memory (a 4 GiB reserve, 2.5 GiB per builder) is a starting point. | Decided (cap); Proposed (reading) | decision 45 |
| Back-off under memory pressure | Critical pressure stops the newest builder with no commit, at no cost to its attempts. The piece is given back (move 7). | Proposed | slice 10 |
| Builder idle timer (30 minutes asks, 45 stops) | Dropped. Stuck is now read from repeated patterns and hard timeouts. | Decided | research finding E |
| Usage limit reached | Waiting for reset, never an attempt. Tokens are recorded per piece. N builders spend the allowance N times faster, and the opening line says so. | Decided (wait, tokens); Proposed (opening line) | research finding E |
| Run budget of 480 minutes | Dropped. A run has no limit on a subscription; an API key has spend caps. | Decided | answer 5 |
| CI round cap | Dropped. There is no GitHub-side check, and the GitHub-only failure case is dropped too. | Decided | answer 17 |
| Two environment failures in a row on different pieces pause the run | Kept. | Proposed | slice 7 |
| Pause, continue and stop | Sent through the local mailbox, which is only for these three. On stop, every piece in building goes back to ready and keeps its branch; pieces in review or approval wait. | Decided | settled decision 24 |
| One writer per piece; a critic or reader is read-only | Kept. | Proposed | decision 44 |
| One status file | Feeds `/what-now` and every view of progress. | Proposed | AI Build Kit running-longer; inventory |

## Autonomy and walking away

A run never stands still waiting for an answer: it decides or parks, and only a short list of real stops halts it. **Decided:** the rules in this section come from the first unattended night and are settled decisions 50 to 52. The mechanisms that carry them out are **Proposed** where marked.

### One rule: decide or park

**Decided.** This one rule replaces scattered "ask the person" stops. Faced with a question, the run takes one of two routes and always documents it:

- **Decide.** Take the answer that keeps every settled decision and is easiest to undo. Write it on the piece under its decisions, marked for the person's review, and add it to the decisions list.
- **Park.** Where no answer is safe to take, the piece waits on the person inside its current state, with the question written on it and the `needs-you` flag set. The run carries on with any work that does not depend on it.

On the night of 4 to 5 October the earlier run stood still from about 03:30 to 07:40 on one builder's request to amend a done line, because the earlier rule named readiness questions only (settled decision 51).

### The real stops

**Decided.** Only these stop the whole run:

- a fatal error the run cannot recover from;
- anything touching money;
- real accounts or credentials;
- a repository or account setting;
- data that cannot be restored;
- going public, or a release;
- repeated failure, read now as the same failure across several pieces (Proposed), since three failed attempts on one piece send only that piece back to shaping;
- the same refused command in two pieces (a refusal inside one piece is that piece's environment failure);
- an answer that would need a settled decision changed.

**Decided.** A real stop does not freeze independent work. The run notifies the person once, then carries on with everything that does not depend on the answer, and picks up the person's input whenever it arrives.

### Permissions are set before the run

**Decided.** The person writes the permissions and the policy before a run. Agents read them and cannot change their own permissions. Claude Code's own safety check refused such a change even with the person's yes.

### The walk-away kit

| Mechanism | What it does | Status |
| --- | --- | --- |
| The watch | A launchd job that only checks that the run's heartbeat is fresh, and sends one notification when it is not. The run script itself runs under launchd with KeepAlive, which restarts it at once, and under caffeinate, which keeps the computer awake. Stuck detection and the resume after a usage reset live in the run script. | Decided |
| Mailbox | A local file the run reads at every step, only for pause, continue and stop. All other input arrives as comments on the issue or the pull request. | Decided (that it exists); Proposed (its format) |
| Pre-run check | Refuses to start unless guards, policy file, computer and `main` are fine (see The run). | Decided |
| Morning summary | Every decision made alone, in one list, closing the run. | Decided (summary); Proposed (each undone by one command) |
| Notifications | Six moments, below. | Decided |

### Notifications

**Decided.** Six moments, each sent once per event:

1. the run finished;
2. the run stopped on a real stop;
3. a pull request is ready for merge;
4. something went live, or a live check failed and production is pinned;
5. something waited on the person too long (about 2 hours);
6. the watch found the heartbeat stale.

- **Decided.** Quiet hours are the person's GitHub Mobile working hours. Notifications held by them collapse into one message.
- **Decided.** Notifications never block. A notification never pauses the work.
- **Decided.** One channel out and one in. Notifications go out as GitHub @-mentions. Input comes in as comments on the issue or pull request. The local mailbox is only for pause, continue and stop. The run carries on with everything that does not depend on an answer, and resumes the affected piece when the input arrives.
- **Decided.** The gate @-mentions the person on the issue or pull request, acting as its GitHub App. GitHub Mobile pushes the mention to their phone. Email is the fallback.

## Safety and cross-cutting rules

A run with nobody watching needs a boundary the agent cannot talk its way round. **Decided:** the essential level is core in v1.0. The filesystem sandbox and a network allowlist per recipe are in v1. The gate acts on GitHub as a GitHub App, and builders hold no GitHub credential.

### The essential level, in v1.0

| Item | What it does | Status | Source |
| --- | --- | --- | --- |
| The gate's GitHub App | A GitHub App scoped to this repository, held only by the gate. Builders hold no GitHub credential and are blocked from the person's own GitHub login. The person merges under their own account. Creating the App is a one-time step in the second half of /setup. | Decided | red team, finding 4; decided by the maintainer |
| Deny rules | Push to `main`, force push, recursive delete, and hand-written state labels. | Decided | answer 9 |
| A hook that parses commands | Reads each command rather than matching its text, so a form such as `git -C . push origin main` is still caught. Bash rules alone are not a security boundary, by Anthropic's own documentation. | Decided | research finding B3; gates research, item 5 |
| Guards guard themselves | Deny rules and sandbox write-blocks on the gate, the hooks, the settings and the workflows. The pre-run check refuses to start while a guard is missing, and refuses a run script that passes --bare. Every builder gets the guards with --settings, so they do not depend on discovery. | Decided | research finding B2 |
| Filesystem sandbox | On for every agent session in v1, with a network allowlist that /setup writes per recipe: the package registry and the language's toolchain hosts. This revises answer 9, which had left both for later. | Decided | research finding B3; red team, finding 6 |
| No real env files | Agents never read a real env file. Each worktree gets throwaway values. | Decided | answer 9 |
| Secret scan | Before every push, and in a second place. | Decided | answer 9; research finding G |
| A yes before speaking for the person | Anything posted in the person's name waits for their yes. | Decided | answer 9 |
| Outside text is data | Text from issues and the web is treated as data, never instructions. | Decided | answer 9 |
| New dependencies checked | Age and licence checked before a new dependency is accepted. | Decided | answer 9 |
| A command log | A hook logs every command the agent runs, refuses or retries. | Decided | research finding F |
| The free-plan warning | `/setup` detects a free private repository with no server-side rules and says so plainly. | Decided | research finding B5 |
| Sandbox settings | `strictAllowlist`, `allowUnsandboxedCommands: false` and `failIfUnavailable: true`, and bypass mode switched off. Builders run with `--permission-mode dontAsk` and sandbox auto-allow, so a command outside the sandbox is refused, never asked about. The held-out folder is read-blocked for builders. | Decided | gates research, item 5; red team, findings 6 and 10 |

### Supply chain

**Decided.** The package manager's minimum-age setting is on, and agents install with no install scripts. Secrets are scanned in two places. Dependabot is on. GitHub Actions are pinned to exact versions. Every major package manager now has a native cooldown setting ([Nesbitt, March 2026](https://nesbitt.io/2026/03/04/package-managers-need-to-cool-down.html), cited in the gates research), so the age rule is held before an install runs, not only after.

### Cross-cutting rules

| Rule | Status | Source |
| --- | --- | --- |
| Every important rule sits in at least two independent layers. | Decided | answer 9 |
| A refused command is never reached another way. Inside a piece it is that piece's environment failure (move 7). It is logged and named, for the person to run if it is needed. | Decided (environment failure); Proposed (the rest) | AI Build Kit blocked commands |
| Bookkeeping (labels, claims, the kit's own comments) needs no yes. Speaking for the person to anyone else does. | Decided (the yes); Proposed (bookkeeping needs none) | answer 9 |
| Nothing is installed, replaced or removed outside the project folder without a yes naming what, where and how to undo it. | Proposed | AI Build Kit change-triage |
| No stored logins: only a tool's own commands and keys the tool already sends to the browser. | Proposed | AI Build Kit |
| When GitHub cannot be reached, the gate changes nothing; work already claimed continues, and nothing new starts. | Proposed | slice 2 |
| The person is told things in plain words, one line per check, and never asked to read code or logs. | Proposed | decision 51 |
| One status file feeds every view of progress. | Proposed | inventory, "does not fit" |

## Data model

The issue is the piece, its body holds a spec that people read and the gate parses, and the gate is the only thing that changes either. **Decided:** issues, labels, sub-issues and pull requests are the store; every fact has one home; and the spec fields the answers named. **Proposed:** the rest of the structure below, chosen so the gate can compute every need and check every move from data rather than from an agent's word.

*Diagram: data model · GitHub, the gate, the project folder. See the live document: https://claude.ai/artifact/FZwf7EWnuG5ZH94RyW7XCF*

The gate reads the policy the person wrote, moves labels on the issue, writes the run record and the piece records, and merges only the exact tested commit of the pull request.

### On the issue

- **Decided.** Exactly one `state:` label. The gate refuses a second.
- **Decided.** A `needs-you` flag label, which only the gate adds and removes.
- **Proposed.** Exactly one `type:` label (feature, bug or chore).
- **Proposed.** The judge kind lives in the spec, not in a label.
- **Proposed.** Parts are sub-issues. Each part is a piece with its own state; the parent carries none.
- **Decided.** "Waits for" is a GitHub blocked-by link, and parts are GitHub sub-issues. The spec has no dependency field, so the gate reads one source.
- **Decided.** The spec has a versioned format, read by one shared parser. **Proposed:** it is a structured block in the issue body between two hidden markers, under a short plain header that says what the piece is for.
- **Decided.** The gate computes the needs list from the spec. **Proposed:** it writes the list below the spec, and nobody else edits it.
- **Decided.** The fingerprint is a hash of the spec block and the judge files commit, taken when the piece becomes ready and checked at every claim. **Proposed:** it is also checked at every attempt and at review.

### The spec block

| Field | What it holds | Status |
| --- | --- | --- |
| Goal | One sentence: what changes for whom | Proposed |
| User story | As who, I want what, so that why | Proposed |
| Expected flow | Numbered steps the person would take, each with an ID | Decided (IDs) |
| How to observe it | What someone sees when it works | Proposed |
| Edge cases | "When ..., then ..." with an example value, each with an ID | Decided |
| Limits | Each limit with a number, or "none" | Decided |
| Must stay the same | Behaviour that must keep working, and the checks that prove it | Decided |
| Follow | Existing code to imitate, and any visual | Decided |
| Changes to current behaviour | Added, changed and removed lines, checked at merge | Decided |
| Coverage | Each category answered, or not applicable with a reason | Decided |
| Not in this piece | What is deliberately left out | Proposed |
| Judge | Kind; command or target; the gate's record that it fails today; the fingerprint of the hidden held-out cases (never their content); the hypothesis list for a metric piece or an open route | Decided (held-out, hypotheses); Proposed (layout) |
| Links | Relies on (code or service, by name); touches (areas). Waiting for another piece is a GitHub blocked-by link, not a spec field. | Proposed |
| Sensitive areas | Each area, the risk notice, the person's exact words and the date | Decided |
| Decisions | Each settled choice, who decided and when. Assumptions by the agent and decisions made alone during a run are marked for review. | Decided (assumptions); Proposed (layout) |
| Research | Each finding with its source, its date and what it rests on (file and fingerprint, or page or package version) | Decided |
| Open questions | Each question, why it matters, a recommended answer, and who can answer | Decided |

### The computed needs list

**Decided.** The gate derives each need from the spec, and sets the `needs-you` flag when any need names the person. A piece is ready exactly when the list is empty and every ready-gate check passes. **Proposed:** the table below.

| Need | Computed from | Who can settle it | Sets `needs-you` |
| --- | --- | --- | --- |
| No goal, user story or expected flow | A missing field | The person, with the agent drafting | Yes |
| A coverage category unanswered | No answer and no "not applicable" reason | The agent drafts; the person confirms | Yes |
| An ID with no test, or a test with no ID | The IDs and the acceptance tests | The agent | No |
| No Limits, Must stay the same or Follow | A missing field | The agent drafts; the person confirms | Yes |
| The two fresh test lists cover different spec IDs | The two sessions' lists and the judge | The agent, or the person for a choice | When a choice is needed |
| No judge | Judge kind or command missing | The agent; for a metric or a reference, the person approves the target or the reference | For a metric or a reference |
| Judge not seen failing today | No failing run on today's `main` in the gate's record | The agent asks the gate to run it | No |
| Open question for the person | An entry under Open questions | The person only | Yes |
| Researchers disagree | Two findings that contradict each other | The person, or a further check | When the person must choose |
| A research finding without source, date or basis | A finding missing one of them | The agent | No |
| Unresolved dependency | A blocked-by link to a piece that does not exist, or a cycle | The agent or the person | No |
| Sensitive area without acceptance | An area marked sensitive with no recorded acceptance | The person only | Yes |
| Lint gap | A refused phrase, a numbered build-step list, too long for its type | The agent | No |

### An example issue

**Proposed.** An illustrative piece still in shaping, with two needs left, one of them for the person. The names, numbers and commit are invented for the example.

```markdown
Title: Export a month's invoices as one CSV file
Labels: state:shaping, type:feature, needs-you

An accountant can download one month of invoices as a single CSV file.

<!-- spec:start version=1 -->
## Goal
An accountant can download every invoice from one month as one CSV file,
ready to import into the books.

## User story
As the accountant, I want one file per month, so that I can import a month
in one step.

## Expected flow
FL-1 The accountant opens Invoices and picks a month.
FL-2 They choose "Export CSV".
FL-3 The browser downloads invoices-2026-09.csv.

## How to observe it
The file has a header line and one row per invoice dated in that month.

## Edge cases
EC-1 When the month has no invoices, then the file holds the header line only.
EC-2 When an invoice is a credit note of 40.00, then its row shows -40.00.

## Limits
A month of 5,000 invoices downloads in under 10 seconds.

## Must stay the same
The single-invoice PDF download still works (tests/invoice-pdf.test.ts).

## Follow
The existing receipts export in src/export/receipts.ts.

## Changes to current behaviour
Added: an "Export CSV" button on Invoices. Docs: docs/invoices.md.

## Coverage
Permissions: only accountants see the button. Data kept: none new.
Errors: a failed export shows a message and keeps the page.
Empty states: EC-1. What leaves the tool: the downloaded file only.

## Not in this piece
PDF export. Scheduled exports.

## Judge
Kind: acceptance tests, first commit 9f8e7d6 on the piece branch
Command: npm test -- tests/acceptance/invoice-export.test.ts
Proves: FL-1, FL-2, FL-3, EC-1, EC-2
Held-out cases: fingerprint 4c1e9a2 (stored outside git; gate only)
Fails today: 5 of 5 tests fail on their assertion; main at a1b2c3d;
5 October 2026 (written by the gate)

## Links
Relies on: GET /api/invoices?month= in src/api/invoices.ts
Blocked by: a GitHub link to the credit notes piece, not a spec field
Touches: invoices, export

## Sensitive areas
None.

## Decisions
- Dates in the file use the form 2026-09-30. Decided by the person,
  4 October 2026.
- Columns follow the receipts export. Assumed by the agent, for review.

## Research
- The accounting package imports UTF-8 CSV with a header row.
  Source: the package's import help page. Checked 3 October 2026.
  Rests on: package version 4.2.

## Open questions
- Should cancelled invoices appear in the file? Why it matters: they
  change the month's total. Recommended: no. Who: the person.
<!-- spec:end -->

## Needs (written by the gate; do not edit)
- Open question for the person: should cancelled invoices appear in the file?
- The two fresh test lists have not run yet.

<!-- loop:fingerprint none yet; taken at ready -->
```

### In the project folder

- **Decided.** A policy file the person writes before a run, which agents read and cannot edit. **Proposed:** it holds the autonomy rules, the builder cap (3 by default), the attempt limit, the review round cap, the question cap, the research age limit, length limits and the outside critic choice. Settings that belong to one computer sit in a separate git-ignored file.
- **Decided.** One run record per run, git-ignored: the pieces, their order, each worktree, attempts, judge results, the heartbeat and the decisions made alone. A new session resumes from it. The run's scratch files sit in the same git-ignored run folder.
- **Decided.** A local mailbox file, only for pause, continue and stop, and a command log the hook writes.
- **Proposed.** Piece records, `.agents/pieces/<n>/`, written only by the gate: the hash-chained evidence of judge runs, must-look reasons and review rulings (earlier plan, slice 6). **Decided:** the hidden held-out cases are not here. They sit outside git and outside the issue, in a folder only the gate reads.

### The records model

**Decided.** One home per fact, adopted from the final research pass (records model report, section 3). A fact anywhere else is a pointer to its home, never a copy. Anything a check can hold is a check, not a sentence.

| Record | What it holds | Limit | Who writes it | When it changes | What checks it |
| --- | --- | --- | --- | --- | --- |
| `AGENTS.md` (`CLAUDE.md` only imports it) | The commands; the non-obvious rules, each with a short reason; the guarded actions; pointers to the overview, area map, docs index and changelog. Nothing about what the product is, no history, no dates. | 150 lines; each section 12 lines or fewer | `/setup` at founding | Only through a piece or an approved `/maintain` finding | Line ceiling on every pull request; every path and command it names exists; no line repeats a hook or check |
| `.claude/rules/<area>.md` (optional) | Conventions that apply only in one area, with `paths:` copied from the area map | 40 lines each | Not settled | Not settled | Its `paths:` match the area map |
| `docs/overview.md` | What the product is, who it is for, what it is not, how it goes live, and the area table: name, purpose, sensitive or not, the boundary of a sensitive area, the area doc | 100 lines | `/setup` | Only by a piece's behaviour change or a risk acceptance, in that piece's pull request | Areas and sensitive flags agree with the area map |
| Area map | Each area's file patterns, CODEOWNERS-style, last match wins. No prose. | Not set | Not settled | Not settled | Every tracked file falls in an area; every area matches a file; a piece's touches name real areas |
| `docs/<area>.md`, with a short `docs/README.md` index | The area's current behaviour as short requirement lines, and the decisions in force there, each with its reason and a link to the piece. Current text only. | 300 lines; past that, the area is split | The run, from each piece's Added, Changed and Removed lines | At each piece's merge, in a commit made before the final combined check | The gate refuses a merge whose behaviour change names a doc the pull request did not change |
| The piece (GitHub issue) | The spec, research, decisions and their discussion, the behaviour change, the risk notice with the person's exact words and date, and the run evidence summary | Not set | The person and the agent in shaping; the gate for its computed parts | In shaping; it lasts after closing as the record of why | Fingerprinted at ready, so later edits are caught |
| `CHANGELOG.md` | One entry per merged piece, written from its behaviour change under Added, Changed, Removed, Fixed and Security, with the piece link | Not set | The gate, one entry per piece; never from commit messages | Folded at merge, in a commit made before the final combined check | Every piece the merge closes has an entry |
| Scratch files | Attempt notes, the frozen spec copy, judge logs, run state | Not set | The run | During a run | Never committed: they live in a git-ignored run folder |
| Lessons | A check, a hook or a lint first. Only if that is impossible, one reasoned line in `AGENTS.md` with its evidence and date. | One line each | The learning loop | Proposed during a run; applied at the start of the next run, each as its own commit | Auto memory is off in every run session |
| Drift | The mechanical checks above, and a judgement read of `AGENTS.md`, rules, overview and area docs against the code | Not set | `/maintain` | Mechanical checks on every pull request; the judgement read every 2 weeks | Findings become shaping issues; small tidying is done and logged |

The limits for the overview, area docs and area rules are judgement, not measured. The 150 lines for `AGENTS.md` sits inside Anthropic's 200 and above OpenAI's 100 (records model report, notes on uncertainty).

## Branch and merge flow

Each piece has its own branch, and a run joins its built pieces on one combined run branch that reaches main through one pull request. **Decided:** the combined run branch; trial joins in dependency order that move it forward only on green; dependents stacked on their dependency's branch; a rebuild from main rather than a revert; isolated pull requests for pieces needing individual review; and merging only the exact tested commit. Proposed where marked below.

*Diagram: branch and merge flow · 3 pieces, 1 run branch, 1 merge. See the live document: https://claude.ai/artifact/FZwf7EWnuG5ZH94RyW7XCF*

Piece A joins first. B stacks on A's branch and joins next, then C. Each join is a trial in a scratch copy that re-runs the judges of every piece joined so far, and the run branch moves only on green. After the last join, the final combined check runs locally, and the run opens one pull request for the person to merge.

- **Decided.** Each piece's branch is cut from `main` at shaping, with the judge files as its first commit.
- **Decided.** A combined run branch is cut from main at run start. Built pieces join it one at a time in dependency order, each as a trial merge in a scratch copy brought up to date with main. The run branch moves to the trial commit only on green. Each join commit carries a `Piece: #n` trailer.
- **Decided.** Scratch files are never committed; they live in the git-ignored run folder. Tests join. Agents never resolve conflicts across pieces.
- **Decided.** A piece that needs individual review is not joined. It follows the same steps on its own branch and pull request. The ready gate decides which pieces need it.
- **Decided.** Only the exact tested commit merges. Only one run per project runs at a time, held by a lock file.
- **Decided.** A piece that depends on another stacks on that piece's branch. If the dependency needs individual review, the dependent does too, and its pull request is based on the dependency's branch. The plan shows serial chains first, before the run starts.
- **Decided.** No force push and no revert anywhere, so no history the person has cloned is rewritten. A piece leaving the combined branch means a rebuild from main under a fresh name. **Proposed:** no rebase either; bringing up to date uses a merge commit.
- **Proposed.** One feature branch per piece in its own worktree. The main folder never switches branch.

## Skills and checks

**Decided.** v1's skills hold judgement and conversation, and every rule that must hold lives in a script, a hook, a setting or the gate. The maintainer confirmed this section on 5 October 2026. It rests on two reports, `research/skill-principles.md` and `research/skills-audit.md`. A "lint" below is a `check-skills` script that runs on every commit at no model cost.

### The 17 principles

**Decided.** One line each, with how it is checked.

1. A skill holds judgement and conversation; a rule that must hold lives in a script, hook, setting or the gate. Checked by: lint requires a `Held by:` pointer after every hard rule.
2. Point at the script; do not restate it. Checked by: lint fails on a copied row of the gate's table, label names or exit codes.
3. Keep `SKILL.md` small enough to survive compaction whole: 150 lines, 2,000 words, a description of 300 characters at most. Checked by: lint counts lines, words and estimated tokens.
4. Put the purpose, the stops and the first step first. Checked by: lint requires the template's section order.
5. Choose who can invoke each skill on purpose, and write the description for that reader. Checked by: lint requires `disable-model-invocation: true` on `/setup`, `/run` and `/maintain`, and a "Use when" clause on any model-invoked skill.
6. Disclose detail one level deep, and say when to read each file. Checked by: lint fails on a nested reference, an orphan reference, a link with no condition word, or a long reference with no contents list.
7. Match freedom to fragility: exact commands for fragile steps, plain goals for conversation. Checked by: lint fails on a shell block over three lines or a pipe into a state change.
8. Build every script for an agent reader: no prompts, `--help`, JSON out, distinct exit codes, idempotent, `--dry-run`, errors that name the next command. Checked by: a contract test runs each script with `--help`, with no arguments and no terminal, and twice on the same input.
9. Explain why, say what to do, and do not shout. Checked by: lint fails on capitalised emphasis words and warns on a "do not" with no positive instruction.
10. Cut every line Claude would follow anyway, and keep the gotchas. Checked by: the scenario evals; lint only requires a `## Gotchas` section.
11. One home per fact across all skills, and one word per concept. Checked by: lint fails on a repeated paragraph or a banned synonym from the glossary.
12. Give every step a done condition the agent can check. Checked by: lint requires a `Done when:` line under each step.
13. Inject live state with `!` commands, with a fallback when injection is off. Checked by: lint requires `/what-now` and `/run` to start with the gate's report and a fallback line.
14. Never rely on a skill to steer a non-interactive builder; pass its brief and settings explicitly. Checked by: a test of the run script's exact `claude -p` command line.
15. Write the evals before the skill, and keep them. Checked by: lint fails on a skill with fewer than three eval cases.
16. Keep skills timeless: no dates, versions, issue numbers or model names. Checked by: lint pattern match.
17. Use skill-scoped `hooks` and `allowed-tools` only as conveniences. Checked by: lint fails on a claimed guard whose only holder is the skill's own frontmatter.

### What belongs where

**Decided.** If a wrong answer is acceptable and the person is present, it is a skill. If a wrong answer must be impossible, it is at least two of script, hook, setting, gate and GitHub.

| Kind of content | Skill | Script | Hook | Setting | Gate |
| --- | --- | --- | --- | --- | --- |
| Talking with the person, questions with a recommended answer | yes | no | no | no | no |
| Judgement: one piece or two, which need is the person's | yes | no | no | no | no |
| Order of steps in a conversation, and when to stop | yes | no | no | no | no |
| Gotchas the agent would get wrong | yes | no | no | no | no |
| A piece's state and which moves are legal | points at it | no | no | no | yes |
| Ready checks: spec lint, judge fails on main, fingerprint | no | yes, called by the gate | no | no | yes |
| Frozen bar, new-test lint, held-out run | no | yes | no | no | yes |
| Refusing a hand-written `state:` label | no | no | yes | yes, deny rule | reports it |
| Refusing push to main, force push, recursive delete | no | no | yes | yes, deny rule | GitHub rule as a third layer |
| Reading real env files | no | no | yes | yes, deny and sandbox | no |
| Secret scan before push | no | yes | yes | no | no |
| A yes before posting in the person's name | shows the words | no | yes, ask | yes, ask rule | no |
| Builder brief and permissions in a run | no | yes, the run script | no | yes, `--settings` | no |
| Key context after compaction | no | no | yes, SessionStart | no | no |
| Live state shown to the person | yes, `!` injection | yes, the report | no | no | yes, the source |
| Notifications, watch, stuck detection | no | yes | no | no | no |
| Facts about the project | points at `AGENTS.md` and docs | no | no | no | no |

### The v1 skill template

**Decided.** Each skill is a folder with `SKILL.md` (150 lines and 2,000 words at most), `references/` (300 lines each at most, with a contents list past 100 lines), `scripts/` (agent-ready helpers that change nothing the gate owns) and `evals/` (at least three cases). Guards live outside the skill folders, in the kit's protected tools folder.

```markdown
# <Name>
One paragraph: what the command is for and what it leaves behind.

## Now
!`python3 <kit>/gate.py report --json --brief`
If the line above shows a disabled marker, run that command first.

## Stops
- When to stop and what to tell the person. Held by: <hook, setting or gate move>.

## Steps
1. <step in the imperative>
   Done when: <an exit code, a gate state, a file>.

## Gotchas
- <a fact that defies a reasonable assumption>

## When to read more
- Read `references/<file>.md` when <condition>.
```

The description is at most 300 characters, in the third person. The first 60 lines carry everything a session needs if it never reads a reference.

### How skills are tested

**Decided.** At least three eval cases per skill (normal, edge, refusal) are written before the skill. There are three tiers.

- **Static lint, every commit, free.** The standard's validator, `claude plugin validate`, and the `check-skills` lint for the 17 principles. Each lint rule gets a mutation test, as `rule-shape.sh` does today.
- **Script contracts, every commit, free.** Principle 8's test for every script the skills call, against the GitHub stand-in.
- **Scenario evals, on a skill or model change and before a release.** `claude plugin eval` against a fixture project with the GitHub stand-in, with graders on the tools used, their order, the files left and the reply. A run against the no-plugin baseline before a release shows whether the skill adds anything.

Builder sessions are not tested through skills. The run's own rehearsals test the builder's brief and settings.

### Checks for agent-written code and tests

**Decided.** "Script" says whether a script can detect it reliably (yes), with false alarms or misses (partly), or only a reviewer can judge it (no). The "yes" rows feed the gate's new-test lint and the trim pass. The "partly" rows become worth-knowing notes for the reviewer. The "no" rows are the reviewer's own list.

| Check | What it catches | Script |
| --- | --- | --- |
| Tautological test | The expected value is computed the way the code computes it | partly; mutation testing catches the rest |
| Implementation-coupled test | Mocks the project's own modules, asserts call counts, tests private methods | yes for mocks and call counts; partly for private methods |
| Verifying through a side channel | Queries the database instead of the interface | partly |
| Test that can never fail | So over-mocked that no code change turns it red | yes, by mutation testing |
| Horizontal slicing | All unit tests written before any code | partly, from commit order |
| Test name says how, not what | "calls paymentService.process" | no |
| Empty test | No assertion | yes |
| Skipped test | `.skip`, `xit`, `pytest.mark.skip` added | yes |
| Redundant assertion | `assert True` | yes |
| Duplicate assert | The same condition asserted twice | yes |
| Conditional test logic | `if` or loops in a test | yes |
| Sleepy test | `sleep` in a test | yes |
| Redundant print | A debug print left in a test | yes |
| Assertion roulette, magic numbers | Many unexplained assertions or bare literals | yes, report only |
| Test edited to pass | Assertion changed, test deleted, timeout or retry raised | yes, the frozen bar and the new-test lint |
| Special-casing test inputs | Code returns the expected value for the test's input | partly; held-out cases catch the rest |
| Code that detects it is under test | `NODE_ENV === 'test'` and similar | yes |
| Snapshot regenerated with the code | Snapshots rewritten in the same change | yes |
| Suppressed checks | `eslint-disable`, `@ts-ignore`, `noqa`, a lowered threshold | yes |
| Unused code | Code no caller needs | yes |
| Duplicated code | Copied blocks | yes |
| Middle man | A wrapper that only delegates | partly |
| Fowler's design smells | Mysterious names, feature envy, shotgun surgery and the rest | no; shotgun surgery partly, from history |
| Swallowed error | An empty `catch` or `except: pass` | yes |
| Debug leftovers | `console.log`, a stray `print`, a new TODO | yes |
| New dependency | A package added | yes, from the lockfile |

### What we carry from AI Build Kit

**Decided.** Ideas, not text. Each is rewritten shorter, and moved into a script where it can be.

- The gate as the only mover, refusing with a `next:` command; a record before a label, held by a fingerprint.
- Readiness checked by a session that did not shape the piece, against a fixed list, with blocking gaps apart from notes.
- Checks written first and seen failing on their assertion; the bar guard, and the gate running the checks itself; a test that passes only on a retry is a fault.
- The trim with hard limits: remove or fold only, never a test.
- Merge rules: a yes that names the merge, every merge brought up to date and checked again, a stacked pull request never before its base; waiting for checks with one watch, and "no checks ran" is never green.
- Closing words only on a `Closes` line; one changelog file per piece, folded at merge.
- The first upload asks; founding never gates, says the cheaper option once and keeps interview notes out of git.
- Question discipline: one question, a labelled guess, silence is no answer; the pre-mortem once per piece; an existing mock before a prototype.
- Research states sources and recommends, and never decides; an overlap warning that blocks nothing.
- Work on the person's computer kept apart from the project; a yes before speaking for the person; no borrowed logins, and a secret passed by its location.
- Launch warnings said once and never stopping the launch; rollback "possible, not tried"; the whole deploy output read before any second deploy.
- The review report split into worth stopping for and worth knowing; a named reviewer is a person; never call a screen accessible or good.
- Whole-project reads silent when they find nothing, capped at three proposals, with no score; `/what-now`'s order and its cap of three.
- Worktrees owned end to end, never removed by force; old branches listed and never removed; deny-rule spellings tested by a matcher; uncommitted work never swept into a commit or discarded.

## Verifying the kit itself

**Proposed.** The kit is verified by end-to-end runs on a small throwaway project and by unit tests for the gate, not by a large set of checks that read documents for words.

### What to test

- **Proposed.** One end-to-end test per judge kind on a throwaway project. Each takes one piece from shaping to done: acceptance tests, a reproducing test, a measurement, and a fresh critic against a reference. A stand-in for the GitHub command line keeps the tests offline.
- **Proposed.** Unit tests for the gate's transition table. Every one of the fourteen moves is driven twice: once where its checks hold, and once where each check fails. A move not in the table is refused.
- **Proposed.** Unit tests for the computed needs list: each kind of need appears when its spec field is missing and clears when it is written.
- **Proposed.** Tests for the run's ordering: dependencies first, no two pieces in one area at once, and the given-back and kickback routes.
- **Proposed.** A few checks on wording stay, but only where a written rule has no script to hold it.
- **Proposed.** One end-to-end test of the integration loop: two pieces that pass alone but clash together. The clash is found at the trial join, the trial is thrown away, the culprit is sent back, and the rest of the run reaches one pull request.
- **Proposed.** Tests for the guards: each guard taken away in turn makes the pre-run check refuse, and each anti-gaming case (a changed bar, a skipped test, a held-out gap, an off-list hypothesis) is caught by the gate.

### Why the change

The earlier build was slow. Each slice rebuilt AI Build Kit's skills and had to keep about 100 to 120 rehearsals and a validator of about 2,200 lines green. Many of those rehearsals guarded behaviour v1 replaces. Most checked that a document contained certain words, not that the loop worked. A test that drives a piece from shaping to done proves the thing the person relies on, and it fails when the loop breaks rather than when a sentence moves.

## Code we can borrow

**Decided:** v1 is written from scratch in this repository, and borrows what it keeps from AI Build Kit before AI Build Kit's files are removed. **Proposed:** the list below. Each item has a rehearsal in this repository today. Full list: inventory section 5.

| Code on `main` | What it gives v1 | What it would shed |
| --- | --- | --- |
| `gate.py` (2,205 lines) | The transition table, read-twice writes, fingerprints, refusals with `next:`, the hash-chained evidence record, the gate running checks itself, retry counted as failure, must-look reasons. | Split into modules. Drop the old-label list, the checkpoint assumptions and the always-person review stub. Share the one spec parser with the lint. Add the `needs-you` flag and the new moves. |
| `ready-lint.py` (1,231 lines) | Required sections, refused phrases, brief rules, length limits, running acceptance checks in a temporary checkout, assertion versus error, time limits, exit codes. | Reading sensitive areas from the masterplan; the no-code special case. Gains IDs, coverage, Limits, When/then cases and the quick path. |
| `area-map.py` (362 lines) | Area map `check`, `which`, `areas`, with one-line errors. Becomes the check that every folder belongs to an area. | Little; the file it reads may move. |
| `state-guard.sh` and the Claude settings deny rules | The hook refusing direct state-label writes; deny rules for push to `main`, force push, recursive delete, history clearing. | Text matching, since v1's hook parses commands. AI Build Kit wording; the session-start wiring. |
| `bar-guard.sh` and `test-guard.sh` | Every change to the bar, in seven kinds, named or not. The base of the byte-for-byte frozen bar check. | The named-change escape hatch, since any bar change is now a failed attempt. Shell workarounds could move to Python beside the gate. |
| `co-change.sh` (68 lines) | The 200-commit co-change query. | Nothing. |
| `bring-up-to-date.sh` and `fold-changes.py` | Take in `main` with a merge commit, fold changelog files, safe exit codes on conflict or an unreachable remote. | The per-piece assumption, since pieces now join on a run branch. |
| `worktree.sh` (743 lines) | Open, unsaved, tidy, leftovers, remove, port, links; never forced; other tools' worktrees left alone. | Linking the real `.env`, since v1 builders get only throwaway values. |
| `merge-ask-rules.py` (100 lines) | Adds and removes settings rules by key, keeping the person's own. | Nothing; reuse the pattern. |
| `check-tooling.sh` (246 lines) | Tool and sign-in readiness, with the kit-repository guard. The base of the pre-run check. | AI Build Kit names. |
| `bootstrap-project.sh` and `place-plan-helper.sh` | Copy foundation files without overwriting; refresh copied scripts. | Plugin-plus-skills detection. |
| `piece-issue.yml` and the area-map template | The issue form and the map template. | Fields the new spec drops; gains the new fields. |
| The test helpers: the GitHub stand-in and the permission matcher | Offline GitHub with labels, links and faults; deny rules matched offline. | Old fixtures. |

**Proposed.** Also worth reading before rewriting, though not on `main`: the run driver, the attempt note and the recovery helper from slice 7 part a on the `v1-integration` branch, and the factory's own watchdog, the nearest thing to the watch loop.

## Decisions taken on 5 October 2026

The maintainer answered all nineteen questions of the first draft and decided on the three research reports and the final research pass, one by one in chat. Each line names the decision and links to the section it changed.

1. v1 lives in gwpicard/ai-loop-kit and replaces AI Build Kit entirely, removed gracefully by a plan. [Principle and scope](#mfzm5dfkkan.59746)
2. A run's pieces are combined on one run branch and checked together; a piece needing individual review gets its own pull request. [Review and integration](#mfzm5dfkkan.22799)
3. Merging is never automatic by default; a merge pre-approved before a run still needs all four conditions. [Approval](#mfzm5dfkkan.25741)
4. Research goes stale by fingerprint and age, with a quick check at every claim and a smart fuller refresh. [The claim re-check](#mfzm5dfkkan.15166)
5. 3 attempts a piece, or fewer with no real improvement; no time limit unless stuck; no run limit. [Building](#mfzm5dfkkan.17358)
6. `needs-you` is a flag label the gate sets and clears, never a state. [States](#mfzm5dfkkan.2486)
7. Five commands: `/setup`, `/shape`, `/run`, `/maintain`, `/what-now`. No `/approve`. [Commands](#mfzm5dfkkan.64203)
8. Claude Code only for v1.0; the gate and spec checks stay plain scripts. [Principle and scope](#mfzm5dfkkan.59746)
9. The essential safety level is core in v1.0, and every important rule sits in at least two layers. [Safety](#mfzm5dfkkan.36608)
10. One home per fact: a short `AGENTS.md`, a short overview, the area map, the pieces, the changelog. [Data model](#mfzm5dfkkan.52335)
11. Judge files are the first commit on the piece branch; scratch files live in a git-ignored run folder, tests are kept (revised in the final research pass). [Building](#mfzm5dfkkan.17358)
12. Risk acceptance lives on the issue only. [Shaping](#mfzm5dfkkan.7645)
13. Shaping crews are in v1, only for a research or design question (revised in the final research pass); researchers who disagree create a need. [Shaping](#mfzm5dfkkan.7645)
14. Anti-gaming: a frozen bar, held-out checks, and a hypothesis list fixed before building. [Building](#mfzm5dfkkan.17358)
15. An outside critic is a choice from v1, and advisory. [Building](#mfzm5dfkkan.17358)
16. The trim pass stays, as the build loop's last step. [Building](#mfzm5dfkkan.17358)
17. A red trial join names its culprit and is thrown away; the GitHub-only failure case was dropped (revised in the final research pass). [Review and integration](#mfzm5dfkkan.22799)
18. Six notifications, once each, with quiet hours, never blocking; input by GitHub comments, with the local mailbox only for pause, continue and stop (revised in the final research pass). [Autonomy](#mfzm5dfkkan.33569)
19. Live in v1.0 is a health check and automatic rollback; error reporting and tracing come later, by a written plan. [Live plan](#mfzm5dfkkan.103045)
20. Move 7 (back to ready, spec untouched, no attempt counted) starts from building and from approval, and covers a parked piece whose answer arrives after its run ended, which the gate writes in and re-fingerprints. [Transitions](#mfzm5dfkkan.4406)
21. Notifications go out as GitHub @-mentions, pushed to the phone by GitHub Mobile, with email as the fallback (revised in the final research pass). [Notifications](#mfzm5dfkkan.115105)
22. Individual review is decided in shaping at the ready gate: automatic for a must-look reason, and the person can mark any piece. [The ready gate](#mfzm5dfkkan.12151)
23. Error reporting and tracing tools for the later Live layers are decided when that extension is planned. [Live plan](#mfzm5dfkkan.103045)

From the research reports:

- **A.** The run is a plain script starting `claude -p` builders, which have one "needs the person" tool. [The run](#mfzm5dfkkan.30195)
- **B1 to B3.** The gate acts as a GitHub App and builders hold no GitHub credential (revised in the final research pass); guards guard themselves; the hook parses commands; the filesystem sandbox is in v1. [Safety](#mfzm5dfkkan.36608)
- **B4.** Not adopted in full: no second check layer on GitHub, but a final local combined check. [Review and integration](#mfzm5dfkkan.22799)
- **B5.** `/setup` says plainly when a free private repository has no server-side rules. [Commands](#mfzm5dfkkan.64203)
- **C.** A "bar is wrong" outcome, hidden held-out cases for acceptance tests, a lint on new tests, and a must-stay-the-same field. [Building](#mfzm5dfkkan.17358)
- **D.** Spec rules: IDs, coverage, two fresh test lists, When/then cases, Limits, Follow, question discipline, a behaviour change record, one parser, a quick path. [Shaping](#mfzm5dfkkan.7645)
- **E.** Stuck by patterns and timeouts, waiting for reset, fresh attempts, judges re-run at each join, the exact tested commit, a grouped pull request. [The run](#mfzm5dfkkan.30195)
- **F.** Findings become failing checks or shaping issues; lessons become checks and are pruned; a command log; delivery rates in `/maintain`. [Loops](#mfzm5dfkkan.49401)
- **G.** Supply chain: minimum package age, no install scripts, secret scan in two places, Dependabot, pinned Actions. [Safety](#mfzm5dfkkan.36608)
- **Loops.** Micro loops shaping, build, integration and review; meta loops run, watch, learning, maintenance and live feedback. [Loops](#mfzm5dfkkan.49401)

From the final research pass (`research/records-model.md` and `research/red-team.md`), decided 5 October 2026:

- **Records.** One home per fact: `AGENTS.md` at 150 lines, an overview at 100, area docs at 300, an area map, the issue and a folded changelog. Lessons become checks; drift is checked on every pull request and every 2 weeks. [The records model](#mfzm5dfkkan.128385)
- **Integration and review.** Trial joins in a scratch copy; the combined branch moves only on green; a rejection rebuilds it from main under a fresh name, with no revert, no force push and no take-out step. Docs and changelog are committed before the final check, and a merge after main moved triggers a check on main. [Review and integration](#mfzm5dfkkan.22799)
- **Transitions.** The anti-circle rule covers only moves back to shaping; gate-made changes re-fingerprint; parked has one meaning; on a run stop, building goes back to ready and review or approval wait. [Transitions](#mfzm5dfkkan.4406)
- **Must-look.** Exactly five reasons: sensitive area, irreversible data, new dependency, security change, marked by the person. Decisions made alone do not block pre-approval. [Reasons that force the person to look](#mfzm5dfkkan.98032)
- **Identity, notifications and input.** The gate acts as a GitHub App, held only by the gate, and builders hold no GitHub credential. Notifications are GitHub @-mentions, with GitHub Mobile push, its working hours as quiet hours, and email as the fallback. Input is GitHub comments; the local mailbox is only for pause, continue and stop. [Notifications](#mfzm5dfkkan.115105)
- **Safety.** A network allowlist per recipe, written by `/setup`; a refusal inside a piece is that piece's environment failure; `--bare` is refused and guards are passed with `--settings`; held-out cases live outside git, in a folder only the gate reads. [Safety](#mfzm5dfkkan.36608)
- **Build loop and run.** Stuck detection in the run script; launchd `KeepAlive` and `caffeinate`; a watch that only checks heartbeat freshness; idempotent joins with a `Piece:` trailer; one run per project with a lock; judges that fail for the right reason; lessons applied at the next run; API-key spend caps; scratch files in a git-ignored run folder; GitHub blocked-by links and sub-issues; dependents that stack and inherit isolation; crews only for a research or design question. [The run](#mfzm5dfkkan.30195)
- **Setup.** `/setup` runs in two halves, "shape and run locally" then "make it safe to walk away", and the second creates the GitHub App. The first piece in an empty project is a quick-path scaffold and test runner piece. [Commands](#mfzm5dfkkan.64203)
- **Live.** The post-deploy health check runs as a small GitHub Action. A rollback brings a revert pull request, a bug issue and a "production is pinned" notification. Each piece's evidence carries its preview link. [Done, dropped and the Live extension](#mfzm5dfkkan.27805)
- **Repeat counter.** Moves 7, 8 and 12 carry a counter of 3: after 3 of the same kind, the piece goes back to shaping with its history. Confirmed by the maintainer. [Transitions](#mfzm5dfkkan.4406)
- **Skills and checks.** The 17 principles, what belongs where, the skill template, the testing tiers, the checks for agent-written code and the ideas carried from AI Build Kit, as written. Confirmed by the maintainer. [Skills and checks](#mfzm5dfkkan.164361)

### Questions still open

None. The last three questions were decided on 5 October 2026 and are listed above.

## Next steps

**Decided.** In this order:

1. **Done, 5 October 2026.** A final research pass on the finished plan, the records model especially, against current best practice. Reports: `.agents/tmp/v1-factory/research/records-model.md` and `.agents/tmp/v1-factory/research/red-team.md`. Their decisions are listed above and applied throughout this document.
2. **Done, 5 October 2026.** A strict review of AI Build Kit's skills, together with the principles v1's skills must follow, including well-defined checks such as Matt Pocock's list. Reports: `.agents/tmp/v1-factory/research/skill-principles.md` and `.agents/tmp/v1-factory/research/skills-audit.md`. Their decisions are in "Skills and checks", confirmed on 5 October 2026.
3. A plan to remove AI Build Kit from this repository carefully: borrow what v1 keeps first, then delete in an order that never leaves the repository broken mid-way.
4. The build plan for v1, in small steps, each tested end to end.

## Appendix: the earlier plan by state

The earlier plan's inventory holds 586 rows across nine state tables and one cross-cutting table, plus 48 conflicts and 17 pieces of borrowable code; this appendix groups them and says what happens to each group after the decisions of 5 October 2026. The full list, with a source for every row, is in `.agents/tmp/v1-factory/inventory.md`.

| Inventory group | Items | Where it lands in v1 | What happens to the group |
| --- | --- | --- | --- |
| 1.1 Idea (capture and backlog) | 21 | shaping, move 1, and dropped | Capture kept in `/shape`. "Idea" is not a state. Out-of-loop routes kept as rules. No separate capture or fix command. |
| 1.2 Shaping (the decision loop) | 81 | shaping | Six sub-states become kinds of need. Batched questions with a cap replace the question box. Research records its basis. Crews are in v1. Risk acceptance lives on the issue only. |
| 1.3 The ready gate | 43 | move 2 | Most of the lint kept as code, extended with IDs, coverage, Limits and When/then cases. Two fresh test lists replace the single fresh checker. Judge files become the first commit on the piece branch. |
| 1.4 Ready to building: the re-check | 25 | move 4 | Kept as the claim gate, with research staleness by fingerprint and age. |
| 1.5 Building: the orchestrator loop | 73 | the run (meta loop) | Now a plain script starting `claude -p` builders. Run record, sizing (cap 3) and usage waits kept. Idle timers and the run budget dropped. The mailbox and the watch added. |
| 1.6 Building: one piece's build loop | 91 | building | One loop with four judges, a fresh session per attempt, fixed hand-offs, the gate as judge. Held-out cases, the hypothesis list, the new-test lint and the trim pass are in v1. |
| 1.7 Review and integrate | 54 | review and approval | Integration now joins pieces on one run branch, then a fresh review. Pre-approval is per run with four conditions; the auto-approve policy is dropped. Culprit finding is in v1. |
| 1.8 Done (merged) | 17 | done | Closing and tidy kept. Delivery rates feed `/maintain`. |
| 1.9 Live (deploy, health, rollback) | 40 | Live, through `/setup` | Health check and rollback in v1.0. Error reporting and tracing later, by the written plan. |
| 2 Cross-cutting | 141 | everywhere | The gate, the parsing hook and deny rules kept. The essential safety level and the filesystem sandbox are core. Setup and maintenance return as `/setup` and `/maintain`. Old-project migrations dropped. |
| 3 Does not fit or needs a decision | 48 | the sections above | Answered by the decisions of 5 October 2026; the last three were decided the same day, and none remain open. |
| 4 Missing from the target model | 19 bullets | the sections above | Folded into states, the run, autonomy and safety. |
| 5 Code worth borrowing | 17 | Code we can borrow | Copied where it helps, shedding its AI Build Kit ties, before AI Build Kit is removed. |
