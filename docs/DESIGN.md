# AI Loop Kit: the design

This is the one description of the kit: what it is, how it works, and why.
If the code and this file disagree, the code is the truth and this file has a
bug. Questions that are not settled live in the maintainer's `docs/OPEN.md`,
not here.

Each rule names what holds it: **code** (the gate, the run or a check),
**hook** (the guard), **sandbox**, or **words** (a brief or a skill only).
Features marked **preview** pass the automated tests but have not yet run on a
real project.

## 1. What the kit is

AI Loop Kit is a Claude Code plugin for one person who builds software with
agents in a GitHub project.

> An agent cannot say a piece is done. It can only prove it, against a test
> the person approved before the build and that the agent cannot change.

The kit is a state machine. Agents do the work, scripts decide, and the
person approves the contract and the merge.

### The problem

Four failures come back again and again when agents build software.

| Failure | What the kit does |
| --- | --- |
| The agent says the work is done when it is not. Telling a model not to cheat does not change how often it does [METR]. | The gate runs every check itself. An agent's report is never evidence. |
| The agent changes the test, not the code [ImpossibleBench]. In a field run a builder turned off a project lint rule to pass. | The judge is frozen by a hash before the build. Old tests and check settings are compared after every attempt. |
| The spec drifts away from the code [Martinelli], [DevGenius]. | A piece is shaped just in time from today's `main`. After the merge the issue is a closed record and the tests are the living spec. |
| The person cannot keep up with review [Osmani, quality]. | The pull request carries checked facts and evidence. A waiting limit stops the run when three pull requests wait. |

Words alone did not hold in the first kit. Scripts did. So the kit answers
each failure with a mechanism, not an instruction.

## 2. The principles

1. **Agents produce, scripts decide, the person approves.** An agent's report
   of its own work is not evidence. A script that runs the check is
   [Anthropic harnesses].
2. **A piece is a contract.** Nothing is built without the person's intent
   and a judge that fails on today's `main` for the right reason. A test
   written before the build, by someone other than the builder, is the only
   proof that the build changed something [TDFlow], [Fowler, TDD].
3. **Every working state is a loop.** It has an entry check, work, an exit
   check and a way back. A failure goes back with a typed reason, never
   forward.
4. **Hold rules in code, and label what is only words.** Prose is read once
   and forgotten [Osmani, agent files]. Where it matters, hold a rule in two
   independent layers, so that one failing does not open it.
5. **Grow from evidence.** A feature enters `kit/` only when a real run shows
   the need. Write the failure down, add a test that reproduces it, then add
   the smallest fix. The first kit was designed in full before it ran, grew
   to about 35,000 lines and never built a piece.

## 3. The core and the extras

The core is the smallest set of parts that keeps the one-sentence promise.
Each core part exists because a real failure showed it was needed.

| Core part | The failure it stops |
| --- | --- |
| The judge fails on `main` on an assertion | A test that already passes, or fails on an import error, proves nothing |
| The bar (judge plus its helpers) is frozen and checked byte for byte | A builder edits the test instead of the code |
| `Keep:` passes on `main` and after every attempt | A field run lost old behaviour when only the judge ran |
| No old test and no check setting changed | A builder rewrote `.gitignore`; another turned off a lint rule |
| A fresh session for each attempt, three at most, given only the last failure | A failed idea carries forward in a long session [Ralph] |
| A sanctioned `bar-wrong` outcome | A builder that cannot say the test is wrong is pushed to cheat |
| Typed hand-backs, counted | One word ("parked") once meant three things, and nobody could count them |
| The run is a plain script with one lock | A coordinator agent forgot decisions after a restart and once ran twice |
| Records read only from collaborators | A stranger could post a forged ready record on a public repository |
| The guard refuses the irreversible commands, and the person merges | A loss that no later check can repair |

Everything else is an extra. Extras are useful, but the promise holds
without them: the two reviewers, quality commands, walk-away runs, goal and
gauntlet judges, the researcher and the Codex backend.

## 4. The engine: states and moves

A piece is a GitHub issue with exactly one `state:` label. Only `gate.py`
moves it (code). Every move writes a record comment that holds the evidence
as JSON. The state lives on GitHub, so a new session, a phone or an audit
script can read it. Nothing lives only in a context window.

```text
                capture          ready (gate checks)          claim
  idea ───────► SHAPING ─────────────────────────────► READY ───────► BUILDING
                 ▲  ▲  ▲                                 │                │
                 │  │  └────── pull-back (typed) ────────┘                │
                 │  └───────── give-back (typed, needs-you) ──────────────┤
                 │                                                        │ submit
                 │    reject (person-rejected, needs-you)                 │ (gate runs judge,
                 └───────────────────────────── APPROVAL ◄────────────────┘  Keep, Quality)
                                                    │
                                                    │ the person merges on GitHub
                                                    ▼ gate.py sync
                                                   DONE

  shaping, ready, building or approval ──drop──► DROPPED ──reopen──► SHAPING
```

| Move | From, to | Started by | The gate checks |
| --- | --- | --- | --- |
| capture | new, shaping | shape skill | nothing |
| ready | shaping, ready | shape skill | the ready checks (section 8) |
| pull-back | ready, shaping | person or agent | a typed reason |
| claim | ready, building | `run.py` | spec and bar hashes unchanged; the pushed branch has nothing the local one lacks |
| submit | building, approval | `run.py` | the submit checks (section 8), all run by the gate |
| give-back | building, shaping | `run.py` | a typed reason; adds `needs-you` |
| merged | approval, done | `gate.py sync` | the pull request is merged on GitHub |
| reject | approval, shaping | the person's words, through the run skill | a typed reason; adds `needs-you` |
| drop, reopen | to and from dropped | person | a reason |

**Why six states.** `shaping` holds work that is not yet clear; most of the
effort goes here. `ready` is the line between deciding and doing. `building`
means one run owns the piece. `approval` means the gate passed it and a pull
request waits. `done` is reached only by reading GitHub. `dropped` keeps
abandoned work with its reason. The first design had a separate `review`
state; the thin kit removed it, because the person reviews each pull request.

**Typed reasons.** Every move back carries one type: `spec-unclear`,
`bar-wrong`, `judge-gap`, `environment`, `builder-failed`, `person-rejected`,
`conflict` or `stopped`, plus free text. `gate.py report` counts them. This
shows where the system fails: weak judges, unclear specs or a broken
environment. It is the seed of the meta loop.

**`needs-you`** is a flag label, not a state. The gate adds it on give-back
and reject, and removes it on ready, drop and done.

## 5. The loops

```text
┌─ META: typed reasons across many pieces → the person changes the kit or project ─┐
│                                                                                   │
│  SHAPING: person + shaper, ≤5 questions → spec → judge writer → gate check        │
│           (loops until the gate accepts ready)                                     │
│                                                                                   │
│  BUILD:  fresh builder ──► gate judges ──► pass? ──no──► retry (3 at most)        │
│             ▲                              │ yes            │ all fail            │
│             └── last failure only ─────────┘                ▼                     │
│                                                       back to shaping             │
│  REVIEW: standards reviewer + contract reviewer, once ──► gate checks again       │
│                                                                                   │
│  PERSON: merge, or reject with a reason ──────────────► back to shaping ──────────┘
```

| Loop | What turns | Stops when | Why |
| --- | --- | --- | --- |
| Shaping | questions, the spec, the judge | the gate accepts ready | A judge that breaks the project's lint, or names an ID that never fails, sends shaping round again. |
| Build | fresh builder attempts | the gate passes, or three attempts fail | A fresh session does not carry a failed idea forward [Ralph]. |
| Review | two reviewers | once, always | A review asked for gaps always finds some, so it never converges. One pass with cited findings is the honest form [Pocock, code-review]. |
| Meta | typed reasons | the person changes something | The same failure should not happen a third time. A lesson becomes a check, not a sentence. |

### One loop, many judges

The build loop is the same for every kind of work. The `Kind:` line chooses
the judge. The first design had four loop modules (build, fix, goal,
gauntlet) and found they were one loop with four judges.

| Kind | Judge | Ready requires |
| --- | --- | --- |
| feature | acceptance tests for new behaviour | the tests fail on `main` |
| fix | a test that reproduces the bug | the test fails on `main` |
| scaffold | the test runner runs and passes | nothing can fail yet, so the check is skipped and the record says so |
| goal (**preview**) | a `Measure:` command run three times; the median is compared with a numeric `Target:` | `main` misses the target |
| gauntlet (**preview**) | three fresh critics compare captured work with a `Reference:` against `Criteria:`, in random order | `main` wins fewer than two of three |

A goal attempt writes one hypothesis to `.loop/hypothesis` first. A gauntlet
attempt passes when ours wins at least two comparisons and `Keep:` passes. A
capture that succeeds but writes no files is refused with a clear message.
The critics are blind only by neutral file names: they run in the build
folder and could find out which side is which.

## 6. The contract

The issue body is the contract. The person approves it before ready.
`kit/spec-format.md` gives the exact format.

```markdown
## Intent
What the person wants and why, in their words.

Out of scope:
- What this piece does not do.

## Approach
Optional. The path: files or modules to change, the interface, constraints.

## Research
- R1: The API accepts a timeout argument (source: https://example.test/api, read: 2026-10-15)

## Contract
- D1: When I run `tally --top 2 words.txt`, then it prints `b 3` then `a 2`.
- D2 (stays): Without `--top`, the output is unchanged.

## Judge
Kind: feature
Command: `python -m pytest tests/judge/test_piece_top.py -q`
Files:
- tests/judge/test_piece_top.py
Keep: `python -m pytest`
```

**Why two parts.** The intent is the person's words; the judge is the
machine's copy. Intent alone is prose that nothing checks. A judge alone
checks what the shaper thought, not what the person meant. Together the
person can read what will be checked, and the gate can check it.

| Section | Why |
| --- | --- |
| Intent | It holds what code cannot say: the why and the limits. The gate refuses an empty Intent (code). |
| Out of scope | Most of the requirements problem is scope. Naming what will not be done is the cheapest guard [Scala Teams]. The gate refuses an empty list (code). |
| Approach | Agents do better when told the path, not only the output [Osmani, agent files]. |
| Research (**preview**) | A piece that rests on an outside fact needs a checked source. Each line has a source URL and a read date (code). A finding over 30 days old is flagged at claim. |
| Contract | Numbered, concrete items, each with an example, so one test can prove each and the gate can find each ID in the output. |
| `(stays)` | "Every item must fail on main" pushed shaping to drop true items or pad tests. `(stays)` marks behaviour that must keep working: it needs a test that passes on `main`. |
| Judge, fixed by a hash | A builder that cannot change the test can only change the code [ImpossibleBench]. |
| Keep | The judge proves the new work. Keep proves the old work still works. |

`Settings: may change` in the Judge section lets a piece change check
settings. `Large file: <path>` lets a named file grow past 1,000 lines.

**Why it is not waterfall.** A piece is shaped just in time, from today's
`main`, and is about one hour of work. After the merge the issue closes as a
record. Each judge file starts with a one-line comment that gives the intent.
Nobody edits a closed issue to keep it current.

## 7. The roles

| Role | What it is | Sees | Produces |
| --- | --- | --- | --- |
| Shaper | the shape skill, with the person | the code, the person | Intent, Approach, Contract |
| Researcher (**preview**) | a fresh `sonnet` subagent with web tools only | the question, web pages as data | findings with source URLs and read dates |
| Judge writer | a fresh subagent | the contract and the code, not the shaping chat | judge files on `piece/<n>`, and a JSON verdict |
| Builder | a fresh Claude Code (or Codex, **preview**) session per attempt | the contract, research, the judge, the last failure | code on the piece branch, `.loop/why.md`, optionally `.loop/outcome` |
| Standards reviewer | a fresh session after the gate passes | the diff, plus the project's standards file or a baseline of Fowler's code smells | small checked fixes, follow-ups, a JSON verdict |
| Contract reviewer | another fresh session | Intent, Out of scope, Approach, Contract, Research and the diff | missing items or scope creep, a JSON verdict |
| Critic (**preview**) | three fresh sessions, gauntlet only | the criteria and two artefacts | a JSON verdict for each comparison |
| Gate | `gate.py`, a script | everything | every decision and record |
| Run | `run.py`, a script | the ready pieces | attempts, reviews, pull requests |
| Person | you | the contract, the pull request | approval and the merge |

Why each role is separate:

- **Only the person knows the intent.** The shaper asks, splits and writes. It
  never builds. It asks one batch of at most five questions, each with why it
  matters and a recommended answer (words).
- **Tests written first by someone else help the builder most** [TDFlow]. An
  agent that writes both code and tests confirms itself [Fowler, TDD]. The
  judge writer does not see the shaping chat, so it tests the contract, not
  the shaper's assumptions. The shaper may fix lint and type errors in the
  judge files before the gate check; it does not write tests (words).
- **The builder's context stays small.** It holds the contract, the judge and
  the last failure. Coding standards stay out of it and out of `AGENTS.md`;
  they belong to the reviewer [Pocock, code-review], [ETH AGENTS.md].
- **Two reviewers, two questions.** The standards reviewer asks "is it built
  right?". The contract reviewer asks "is it the right thing?". Kept apart, a
  pass on one cannot hide a fail on the other. Every finding must cite a rule,
  a smell or a contract line, and a changed hunk, or it is dropped (code). The
  reviewers print one tagged JSON verdict; the run never guesses a verdict
  from free text [Sandcastle].
- **The standards reviewer may commit a non-test fix.** The fix is kept only
  if the judge passes again; otherwise its commits are dropped and the
  builder's judged commit goes forward (code).
- **Contract findings are advisory.** They are recorded as `judge-gap` and put
  at the top of the pull request. They do not stop the pull request (code). A
  missing item means the judge was weak.
- **The gate and the run are scripts.** A coordinator agent forgets and
  drifts; a script does the same thing every time.
- **The person approves the two moments that need taste:** the contract and
  the merge. Everything in between is checked by a script.

**Backend (preview).** `Agent: claude|codex` in the loop section of
`AGENTS.md` chooses the backend for builders, reviewers and critics. Claude
Code is the default. The ready record freezes the choice, and
`run.py --agent codex` overrides it for one run. Interactive skills stay in
Claude Code. Codex runs `codex exec --json` with workspace-write rooted at the
build folder and network disabled. Codex has no guard hook and no Edit
denies, so only the gate holds the rules after the session.

## 8. The checks

### At ready (code, in a fresh copy of `main`)

| Check | Why |
| --- | --- |
| Intent, a non-empty `Out of scope` list and Contract IDs are present | The spec is complete enough to judge |
| Research lines have a source URL and a real read date | Outside facts need evidence |
| `Keep:` and Prepare pass on `main` (Prepare is skipped for scaffold) | A red baseline makes every attempt fail for the wrong reason |
| The judge fails on `main`, not on a syntax, import, file-not-found or command-not-found error | A test that fails for the wrong reason proves nothing |
| Every non-`(stays)` ID is on a failing line; no `(stays)` ID fails | Each item is proven new, or proven kept |
| Test lint (`testlint.py`): an assertion in each test; no `assert True`, `x == x` or literal-to-literal comparison; no skip, `xfail`, `.only` or `.skip`; no private imports; no reading source as text unless the Contract names it | A test can restate the code or never be able to fail [kata] |
| The spec and the bar are hashed. The bar is the judge files plus every `conftest.py` and helper they rely on | Builders change what a test relies on, not only the test [ImpossibleBench] |
| The ready record freezes Test, Prepare, Keep, Quality, Standards, protected paths, idle and waiting limits, and the backend | A builder must not change the rules after they were agreed |

### At claim (code)

The spec hash and the bar hash must be unchanged. The gate checks the spec
hash again at submit, so a spec edited during the build fails. A pushed piece
branch must hold nothing the local branch lacks; the run never rewrites a
pushed branch.

### At submit, after each attempt and again after the review (code)

| Check | Why |
| --- | --- |
| The bar is unchanged; a changed judge is put back and the attempt fails | The commonest cheat [ImpossibleBench], [Anthropic harnesses] |
| No existing test, `conftest.py` or fixture changed unless the Contract names it | Same cheat, one step removed. Rename detection is off, so a moved test stays visible |
| No protected path changed unless the Contract names it | Some code (auth, billing, CI) needs a person [Osmani, brownfield] |
| No file grows from under 1,000 to 1,000 or more lines without `Large file:` | A sprawling file is a design smell agents create quickly [Cursor] |
| No secret shape (`.env` files, private keys, AWS, GitHub and `sk-` tokens) | Git history keeps a secret for ever |
| No conflict markers | A half-resolved merge |
| No file added under paths that Prepare created | `.venv` once leaked into a branch |
| No check-setting change unless `Settings: may change`. Check settings include lint, test and CI config, `.gitignore`, `AGENTS.md`, the standards file, and the check keys of `package.json` and `pyproject.toml` | A builder turned off a lint rule to pass |
| The judge passes, with nothing skipped | A skipped test passes silently |
| `Keep:` passes. If it fails only with the judge files present, the bar is wrong and the piece goes back at once | A judge that breaks the project's lint can never pass |
| Each `Quality:` command passes. A failure is retried, unless the same command also fails on a fresh `main` | The project's own quality bar |

**Quality commands** belong to the project, not the kit, so the kit works for
any stack. Setup offers CRAP for Python (a limit of 30 on changed functions,
from coverage.py JSON) [CRAP], and ESLint `complexity` for Node. Mutation
testing with mutmut 3.8 or later is **experimental**: it needs configured
source paths and in-process tests, because subprocess tests give no mutation
or coverage evidence [mutmut]. Doctor runs Test, then each Quality command, on
a fresh copy of `main` before setup accepts it.

### After the merge (code, outside the loop)

`tests/field/audit.py` checks a project after the fact: one state per piece,
records present, `needs-you` only where valid, merged pieces done, the merged
code equal to the judged commit, and generated files absent.

## 9. The run

```text
run.py
 ├─ take .loop/run.lock (refuse if another run or an orphan child is alive)
 ├─ remove review folders left by a killed run; return pieces stuck in building
 │  to shaping (environment); gate.py sync
 └─ for each ready piece, oldest first:
     ├─ approval queue ≥ Waiting limit (3)? → print next: and stop
     ├─ claim
     ├─ build folder in ~/.cache/ai-loop-kit/worktrees/ (outside the project)
     │   dirty folder → back (environment); never cleaned by the run
     ├─ merge main in; a conflict is left for the builder with a note
     ├─ Prepare
     ├─ attempt 1..3: fresh builder → gate judges
     │     pass → review → gate checks again → push → pull request → approval
     │     .loop/outcome says bar-wrong → back at once (bar-wrong)
     │     idle 10 min / hard 40 min → back (builder-failed, idle)
     │     .loop/stop present → back (stopped)
     │     else → next attempt, given this failure
     └─ any error after the claim → back to shaping with the reason
```

- **Idle limit.** An attempt stops after ten minutes with no output and no
  file change in the build folder (`Idle limit:` changes it). The hard limit
  is 40 minutes. Each judge run has a 900-second limit.
- **Stop.** `gate.py stop` writes `.loop/stop`. The run checks it between
  attempts.
- **Interruption.** The run tracks every child process group and kills them
  on SIGINT or SIGTERM. The next run finds and removes what a killed run left.
- **The pull request.** The script writes the facts: files changed by area,
  tests added, new dependencies, risk (protected paths, migrations, config
  and check settings, large files, importer count), the judge, Keep and
  Quality output, the bar hash and the judged commit. It lists renames as a
  delete and an add. The builder writes only why, and what could go wrong. A
  person should understand the change and its danger in two minutes
  [HumanLayer], [Port]. The run never merges.

### Walk-away runs (preview)

`run.py --walk-away` is for a run nobody watches. It starts only if
`gate.py doctor --walk-away` passes:

- Claude Code 2.1.285 or later, or a working Codex.
- A live probe: a real session must fail to write to the home folder, read
  `~/.ssh` and reach an outside host.
- Confirmed `Sandbox domains:` (package registries only).
- No GitHub or npm token in the environment.
- Green Prepare and Test on a fresh `main`, 10 GB free, room in the approval
  queue.

During the run it writes `.loop/heartbeat` every minute, keeps a Mac awake
with `caffeinate`, waits once for a reported usage limit, and at the end
writes `.loop/summary.md` and posts it to a tracking issue. It never merges.

## 10. The boundary

| Rule | Held by |
| --- | --- |
| No push to `main`, no force push, no agent merge, no recursive delete, no `eval`, no `xargs rm -r`, no `git clean` | hook (`guard.py`), in every session |
| Builders and reviewers never push, never call `gh`, never run Perl or Ruby code, never use unreadable shell forms, never write into `.claude/`, `.githooks/` or protected paths | hook, in build sessions |
| Builders never edit the judge files or check settings | Edit denies, then the gate at submit |
| The gate is the only mover of state | hook refuses `state:` label edits; `audit.py` finds any it missed |
| Only owners, members and collaborators write gate records | code |
| `main` refuses direct pushes on GitHub | branch protection, offered by setup where the plan allows; doctor reports it |
| No secret in a tracked file | code at submit, and words |
| The spec says what the person meant | words: the person approves the contract |
| The person merges every pull request | the run has no merge step; the hook refuses `gh pr merge` |
| Walk-away shell commands stay in the build folder and reach only allowed hosts | sandbox, checked by a live probe |

The guard is a seatbelt, not a sandbox. It splits words and matches patterns.
It reads the `git -C`, `git -c`, `gh -R`, `bash -c`, `sh -c` and `eval` forms,
and in build sessions it refuses a form it cannot read. It is not a full shell
parser, and a determined agent can get round it. The
gate is the backstop, because it checks the result whatever the agent did.

Claude Code's sandbox covers Bash and its child processes. Read, Edit, Write,
web tools and hooks run outside it. So walk-away Claude sessions also load no
MCP servers, deny reads of credential paths, and use a second hook that keeps
file-tool writes in the build folder. An allowed domain can still carry data
out. Attended runs have no sandbox: the builder runs Bash with the person's
network, under the guard.

## 11. Setup, shape and run

1. **Install:** `/plugin marketplace add gwpicard/ai-loop-kit`, then
   `/plugin install ai-loop-kit@ai-loop-kit`.
2. **`/ai-loop-kit:setup`**, once per project. `gate.py init` makes the
   labels. The skill agrees these with the person: the backend, Prepare,
   Test, Quality, Standards, protected paths, sandbox domains and branch
   protection. It writes them to a `## The loop` section in `AGENTS.md` on a
   branch and opens a pull request. Doctor checks it all on a fresh copy of
   `main` (code).
3. **`/ai-loop-kit:shape <idea>`.** Pull `main`. Ask questions. Split the work
   into pieces of about one hour. Write the spec, show it, capture it. The
   judge writer writes the judge on `piece/<n>`. Run the project's Test on the
   judge files, then `gate.py check` and `gate.py move <n> ready`. A spec
   changes only through `gate.py spec`, and only in shaping.
4. **`/ai-loop-kit:run`.** Build every ready piece. Each passing piece gets a
   review and a pull request.
5. **The person** reads each pull request and merges it, or rejects it with a
   reason. `gate.py sync` moves merged pieces to done. `gate.py report` shows
   where pieces came back and why.

The skills hold judgement and conversation. Every rule that must hold lives
in a script, a hook or the gate. All gate commands print one `next:` step
when they refuse.

## 12. Constraints learned from real runs

These facts about the platform shaped the design. Each one cost time once.

- `claude -p` cannot ask the person a question. So the run is a script, and a
  builder that is stuck hands back; it does not wait.
- Claude Code's auto mode refuses an agent's change to its own permissions,
  even with the person's yes in chat. Permissions are set before a run, in
  files agents cannot edit.
- A `Write(path)` deny rule matches nothing. Only `Edit(path)` rules cover
  every file tool.
- A fresh copy of `main` has no `.venv` or `node_modules`. Every check runs
  Prepare first. Only the fresh folder's own `.venv` goes on `PATH`; the
  person's checkout's `.venv` and `VIRTUAL_ENV` are removed, so they never
  choose the interpreter for a fresh folder.
- Build folders inside the project break the person's own linters. They live
  in `~/.cache/ai-loop-kit/worktrees/`.
- GitHub closes an issue when "Closes" appears in any sentence. Only a
  `Closes` line is used.
- GitHub's label search lags after a move. The run retries the ready list for
  about 20 seconds.
- A free private repository has no branch protection. The local layers must
  hold alone, and setup says so.
- A hook wired twice runs twice. Skill paths need `${CLAUDE_PLUGIN_ROOT}`.
- A skipped check once printed as "passed". A check that did not run is never
  green.
- Many parallel sessions crashed the Mac from memory pressure, and once
  filled the disk. The run builds one piece at a time.

## 13. What the kit does not do, and why

| Not done | Why |
| --- | --- |
| A combined branch and combined review | The person reviews each pull request. About 28% of agent pull requests conflict [AgenticFlict], so this returns when runs grow. A conflict after a sibling merge goes to the builder for now. |
| A GitHub App identity | The person's own sign-in is enough while runs are attended. |
| Automatic merges, even pre-approved | Merging is the person's moment. |
| Crews, design-it-twice, a skills registry or context store | Coordination cost with no proven need [Pocock, codebase-design], [Port]. |
| A fixed sentence pattern for every item | It makes odd, long issues. "When ..., then ..." is a guide only. |
| Hand-kept diagrams or data models | They drift. Generated views may come later. |
| A paid code-health score | CRAP covers the same ground for free [CodeScene]. |
| A container around each Claude process | Revisit if a walk-away run finds a gap in the built-in sandbox. |
| Maintenance and live-feedback loops | They need projects that live for weeks. |
| Parallel builders | They crashed the machine. One piece at a time. |

## 14. Size

The kit has about 4,900 Python lines in `kit/`. The target is about 2,500, so
that a person can read it in one sitting. It uses the Python standard library
only and supports Python 3.9 or later. The core (gate, spec parser, run,
guard, test lint, pull request) is about 3,000 lines; the previews and quality
scripts are most of the rest.

## Words used in this file

| Word | Meaning |
| --- | --- |
| piece | One GitHub issue: about one hour of work, with one state label |
| spec, contract | The issue body the person approves. `## Contract` is its numbered list of items (D1, D2) |
| judge | The tests (or measure, or critics) that decide whether a piece is done |
| bar | The judge files plus every helper and `conftest.py` they rely on, frozen by a hash at ready |
| gate | `gate.py`, the only script that moves a piece and the only one that decides |
| run | `run.py`, the script that claims, builds, reviews and opens pull requests |
| Keep | The project's whole test command, which must keep passing |
| Prepare | The command that installs tools in a fresh copy of `main` |
| Quality | Extra project checks, such as CRAP or mutation testing |
| check settings | Files that decide how the project checks itself: lint, test and CI config, `.gitignore`, `AGENTS.md`, the standards file |
| typed reason | The one-word type on every move back, such as `bar-wrong` or `environment` |
| protected path | A path that needs a person; a piece may change it only if its Contract names it |
| waiting limit | How many pull requests may wait before the run stops starting pieces |
| preview | A feature with automated tests only, not yet run on a real project |

## Sources

Outside work the design rests on. Nobody named here was asked first or has
endorsed the kit.

- [Anthropic harnesses] Anthropic, [effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents). Removing or editing a test is unacceptable; a progress file a new session reads.
- [METR] [Recent reward hacking](https://metr.org/blog/2025-06-05-recent-reward-hacking/). Telling a model not to cheat did not change how often it did.
- [ImpossibleBench] [ImpossibleBench](https://arxiv.org/abs/2510.20270). Models edit or delete tests to pass impossible tasks; an explicit way out reduces it.
- [TDFlow] [TDFlow](https://arxiv.org/abs/2510.23761). Tests written first by someone else.
- [Fowler, TDD] [TDD in the agent loop](https://martinfowler.com/articles/exploring-gen-ai/tdd-in-the-agent-loop.html). Martin Fowler, Refactoring, chapter 3, for the code smells.
- [Ralph] Geoffrey Huntley, [the Ralph technique](https://ghuntley.com/ralph/), and Clayton Farr's [Ralph Playbook](https://github.com/ClaytonFarr/ralph-playbook). Change the input and run again.
- [Pocock, code-review] Matt Pocock, [skills](https://github.com/mattpocock/skills): the code-review and codebase-design skills, and a recommended answer with every interview question.
- [Sandcastle] Matt Pocock, [sandcastle](https://github.com/mattpocock/sandcastle). Tagged verdicts.
- [ETH AGENTS.md] [Evaluating AGENTS.md](https://arxiv.org/abs/2602.11988). Keep standing instructions to what the code cannot show.
- [Osmani, agent files] Addy Osmani, [audit your agent files](https://addyosmani.com/blog/audit-your-agent-files/); [brownfield agentic engineering](https://addyosmani.com/blog/brownfield-agentic-engineering/); [agentic code quality](https://addyosmani.com/blog/agentic-code-quality/).
- [Cursor] Cursor, [thermo-nuclear code quality review](https://github.com/cursor/plugins/blob/main/cursor-team-kit/skills/thermo-nuclear-code-quality-review/SKILL.md).
- [kata] [kenn-io/kata](https://github.com/kenn-io/kata), its testing skill: testing without tautologies.
- [CRAP] Alberto Savoia and Bob Evans, the CRAP metric (crap4j, 2007).
- [mutmut] [mutmut](https://mutmut.readthedocs.io/en/latest/), [StrykerJS incremental](https://stryker-mutator.io/docs/stryker-js/incremental/), and [mutation-guided test generation at Meta](https://arxiv.org/abs/2501.12862).
- [Claude sandboxing] Anthropic, [the sandboxed Bash tool](https://code.claude.com/docs/en/sandboxing), [settings](https://code.claude.com/docs/en/settings-reference) and [permissions](https://code.claude.com/docs/en/permissions).
- [Scala Teams] [Spec-driven development: the requirements problem](https://www.scalateams.com/blog/spec-driven-development-requirements-problem).
- [Martinelli] [Why spec-driven development tools fail in the enterprise](https://martinelli.ch/why-spec-driven-development-tools-fail-in-the-enterprise/).
- [DevGenius] [The spec is the code](https://blog.devgenius.io/the-spec-is-the-code-why-i-dont-buy-spec-driven-design-f75c784f7b46) (read from a summary; the page refused access).
- [HumanLayer] HumanLayer's "show me" review approach (read from a secondary description only).
- [Port] [Agentic engineering 2.0](https://www.port.io/blog/agentic-engineering-2-0) and [goodbye code review, hello change](https://newsletter.port.io/p/goodbye-code-review-hello-change).
- [CodeScene] [Agentic AI coding best practice patterns](https://codescene.com/blog/agentic-ai-coding-best-practice-patterns-for-speed-with-quality).
- [AgenticFlict] A study of merge conflicts in agent pull requests, cited in the first design's research (not re-read for this file).
- Also borrowed: [github/spec-kit](https://github.com/github/spec-kit) (a read-only analyse pass), [OpenSpec](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md) (each requirement checkable alone), [GitHub CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners) (path lists for protected paths).
