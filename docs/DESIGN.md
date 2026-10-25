# AI Loop Kit: the design

This is the one description of the kit: what it is, how it works, and why.
If the code and this file disagree, the code is the truth and this file has a
bug. Questions that are not settled live in the maintainer's `docs/OPEN.md`,
not here.

Each rule names what holds it: **code** (the gate, the run or a check),
**hook** (the guard), **sandbox**, or **words** (a brief or a skill only).
Features marked **preview** pass the automated tests but have not yet run on a
real project. Parts marked **planned** are for after 1.2; the text says what
the kit does today beside them.

## 1. What the kit is

AI Loop Kit is a Claude Code plugin for one person who builds software with
agents in a GitHub project.

> An agent cannot say a piece is done. It can only prove it, against a test
> the person approved before the build and that the agent cannot change.

The kit is a state machine. Agents do the work, scripts decide, and the
person approves the contract and the merge.

### Three phases

1. **Shape.** Most of the person's time goes here. Each piece is shaped the
   right amount: its intent, its limits, its risks and its exit condition,
   with dependencies and open choices settled before the build.
2. **Build in a loop.** Every ready piece is built by fresh attempts. The
   loop checks after each one whether the piece did what its contract
   promised and whether it was built well. A failure goes into the next
   attempt; a piece that cannot pass goes back to shaping with the reason.
   Nothing gets through until it meets the bar.
3. **Release.** Finished work waits for the person to review and merge. By
   default that is one pull request per piece. With a base branch, each
   piece's pull request targets that branch, and the run also opens one pull
   request from it into `main`. With `Base merges: run`, the run merges each
   gated piece into the base itself, and the person reviews only the pull
   request into `main`.

Around all three, a **meta loop** reads why pieces came back and improves
what surrounds the loop for this project: its quality floor, its standards,
the questions shaping asks. It proposes; the person approves.

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

## 2. The promises, and how the kit keeps them

### What the kit promises

1. **Shape the right amount.** Every piece states its intent, its limits, its
   risks and its exit condition, and nothing more. The spec holds what the
   code cannot say. After the merge it is a closed record, and the tests are
   the living spec. Too many specs turn into code and drift; the right spec
   sets the direction and the bar [Martinelli], [DevGenius].
2. **Done means proven.** A piece leaves the loop only when a script confirms
   its own exit condition and the project's quality floor. An agent's report
   of its own work is never evidence [METR], [Anthropic harnesses].
3. **Built right, and built well.** Two separate questions, each with its own
   checks: did it build what the contract promised, and did it build it with
   the craft the project expects?
4. **The loop heals or hands back.** A failure goes into the next attempt. A
   piece that cannot pass goes back to shaping with a typed reason and its
   cause, never forward.
5. **The person decides twice:** the contract, and the release.

### How the kit keeps them

1. **Agents produce, scripts decide, the person approves.** A script that
   runs the check is evidence; a report is not.
2. **One mechanism, rich data.** One loop and one gate. Everything else is a
   check declared as data: a command, a threshold, when it runs and what it
   proves. The kit does not grow a tree of special cases.
3. **Everything that decides is frozen.** The exit checks and every file they
   run, the quality floor and the check settings are fixed at ready. A
   builder that cannot change the test can only change the code
   [ImpossibleBench].
4. **Every outcome says why.** Each hand-back records its type, cause,
   attempt count, elapsed seconds, kit version and date. The report groups
   hand-backs by type and cause, and shows how many pieces passed first time.
5. **Checks over words, two layers for what matters.** Prose is read once and
   forgotten [Osmani, agent files]. Where it matters, hold a rule in two
   independent layers.
6. **Small and modular.** Each script and skill has one job and a size limit.
   Skills hold judgement; rules live in scripts [ETH AGENTS.md].
7. **Grow from evidence.** From 15 October 2026 every change follows the earn
   rule: a real run shows the need, the failure is written down, a test
   reproduces it, then the smallest fix. The first kit was designed in full
   before it ran, grew to about 35,000 lines and never built a piece.

## 3. The core and the extras

The core is the smallest set of parts that keeps the one-sentence promise.
Each core part exists because a real failure showed it was needed.

| Core part | The failure it stops |
| --- | --- |
| The judge fails on `main` on an assertion | A test that already passes, or fails on an import error, proves nothing |
| The bar is frozen: the Exit files byte for byte, and the build may not edit or delete the helpers beside them | A builder edits the test instead of the code |
| The project's Test command and any distinct `Keep:` pass on `main` and after every attempt | A field run lost old behaviour when only the judge ran |
| No old test and no check setting changed | A builder rewrote `.gitignore`; another turned off a lint rule |
| A fresh session for each attempt, three at most, given only the last failure | A failed idea carries forward in a long session [Ralph] |
| A sanctioned `bar-wrong` outcome | A builder that cannot say the test is wrong is pushed to cheat |
| Typed hand-backs, counted | One word ("parked") once meant three things, and nobody could count them |
| The run is a plain script with one lock | A coordinator agent forgot decisions after a restart and once ran twice |
| Records read only from collaborators | A stranger could post a forged ready record on a public repository |
| The guard refuses the irreversible commands, and the person merges | A loss that no later check can repair |
| Every file an exit check runs is named under `Files:` and frozen in the bar | A builder could edit the benchmark instead of the code |
| A test that fails during an attempt for the wrong reason is returned as an environment failure | A moved `main` or a broken venv looks like three failed builds |

Everything else is an extra. Extras are useful, but the promise holds
without them: the two reviewers, quality commands, walk-away runs, goal and
gauntlet judges, the researcher and the Codex backend. Mutation tools and
gauntlet critics live in the optional `ai-loop-kit-extras` plugin. The
default plugin refuses a piece that needs either capability when it is absent.

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

### One loop, one exit condition

The build loop is the same for every piece. Only the **exit condition**
changes: the checks that decide when the piece is done. The first design had
four loop modules (build, fix, goal, gauntlet) and found they were one loop
with different exits.

Two things are kept apart:

| | What it decides | Where it lives |
| --- | --- | --- |
| Exit condition | When the piece is done | the spec, frozen at ready |
| Playbook | How to work: a fix reproduces the bug first and finds the cause; new work follows the Approach | the builder's brief |

```text
exit condition = the piece's own checks   (designed in shaping, frozen at ready)
               + the project quality floor (set at setup, frozen at ready)
               + review                    (two axes, every finding cites)
```

**One ready rule for every check:** each piece check is unmet on `main`, for
the right reason.

| Check | Unmet on `main` means | Passes when |
| --- | --- | --- |
| Tests | they fail on an assertion, not on an import or syntax error | they pass, with nothing skipped |
| Measure (**preview**) | the median of three runs misses the `Target:` | the median meets it |
| Critics (**preview**) | `main` wins fewer than two of three blind comparisons | ours wins at least two |

Scaffold pieces use `## Judge` with `Kind: scaffold`, as shown in
`kit/examples/scaffold.md`. The Exit format has no scaffold form. Ready
allows a missing runner and skips Prepare and the regression check on main.
After the build, the runner must pass with at least one test.

An `## Exit` section lists one or more checks: tests, a measure or critics.
A piece can combine them. Each check names the files it runs, and those files
join the frozen bar. Old `Kind:` specs still parse as one check. `Playbook:`
guides the builder and does not affect the gate.

Critics checks and legacy gauntlet pieces require the optional extras plugin
and its critic brief. Ready and claim refuse them before running checks or
starting a builder when that extra is missing. Parsing and freezing capture
files stay in the default plugin.

A goal attempt writes one hypothesis to `.loop/hypothesis` first. The brief
tells the builder to stop before editing code if writing it fails. A capture
that succeeds but writes no files is refused with a clear message. Critics
are blind only by neutral file names: they run in the build folder and could
find out which side is which. Critics answer "is ours better than the
reference?", not "does ours match it".

The Claude builder brief tells builders to stage with
`"$AI_LOOP_KIT_ROOT/bin/kit-python" "$AI_LOOP_KIT_ROOT/scripts/builder_prompt.py" --stage`. Codex builders
leave changes unstaged. After the sandboxed session exits, the run uses the
same helper and commits the project changes. The helper excludes the root
`.loop/` directory, including when it is ignored or contains the build
worktree, and refuses already staged runtime files. It stages through a
separate index and replaces the original only after a successful add. A
failed add leaves the original staged changes intact. The brief
forbids staging or force-adding `.loop/` files; submit checks them again.

Criterion keys ignore terminal full stops, commas, semicolons, colons,
exclamation marks and question marks. Ambiguous keys are refused. For a key
mismatch, the error names the missing and extra keys. The attempt log keeps
the full answer and the order shown from both the attempt and submit checks,
even after the build folder is removed. A submit without an attempt number
writes to `.loop/logs/piece-<number>-submit.log`.
Before claiming a piece, the run refuses a branch checked out outside its
own build folders and names that checkout.

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
| Keep | An optional check in addition to the required project Test command. |

`Settings: may change` in the Judge section lets a piece change check
settings. `Large file: <path>` lets a named file grow past 1,000 lines.

### Risks

Walk-throughs of real projects showed that most failures start before the
build: an open choice nobody answered, two pieces editing one shared file, an
unnamed new dependency, a protected path, tests that need a running service.
The spec has a Risks section that the gate reads, alongside Exit:

```markdown
## Risks
Protected paths: app/api/auth/login/route.ts
New dependency: none
Shared files: app/layout.tsx
Needs services: none
Open choices: none

## Exit
- Tests: `npx vitest run tests/judge/rate-limit.test.ts`
  Files: tests/judge/rate-limit.test.ts
Keep: `npm test`
```

| Line | The gate's rule |
| --- | --- |
| Protected paths | Only these protected paths may change; the guard lets the builder edit them for this piece |
| New dependency | Any dependency added that is not named here fails the attempt |
| Shared files | Ready warns when another ready piece names the same file |
| Needs services | A piece that needs services is refused for walk-away |
| Open choices | Must be empty at ready: the person answers before the build |
| Depends on (optional) | Pieces that must be done first. Ready refuses the piece's own number and a missing or dropped piece |

The gate freezes the risk lines at ready. With `Depends on:`, the run builds
a piece only when every piece named is `done`, reading each state from its
own issue because label search lags. Otherwise it holds the piece and
reports why, with a next step: in the run output, the walk-away summary and
the final pull request, which groups pieces into waves. A hold is worked out
again on every pick and never stored, so a hand-back holds its dependents and
the pieces that depend on them, and every other piece goes on. A ready record
that cannot be read holds the piece too. A hold alone does not fail the run.
A piece in approval is not done, so until the run merges into the base, its
dependents wait for the person's merge and the next run. The judge of a
dependent must still fail by assertion while the dependency is missing. Open choices must be empty.
It warns when a ready piece lists the same shared file. A piece that needs
services cannot run unattended. At submit, the gate refuses any new
dependency in `package.json` or `pyproject.toml` that the issue does not name.
Protected paths named under Risks are allowed for this piece; other protected
paths remain blocked.

Exit tests must assert an outcome: a returned value, output or state. A test
that only checks that nothing raised fails on `main` for the right reason
and still lets a `try/except: pass` fix through.

**Why it is not waterfall.** A piece is shaped just in time, from today's
`main`, and is about one hour of work. After the merge the issue closes as a
record. Each judge file starts with a one-line comment that gives the intent.
Nobody edits a closed issue to keep it current.

## 7. The roles

| Role | What it is | Sees | Produces |
| --- | --- | --- | --- |
| Shaper | the shape skill, with the person | the code, the person | Intent, Approach, Contract |
| Researcher (**preview**) | a fresh Claude or Codex session through the shared launcher | the question, web pages as data | findings with source URLs and read dates |
| Judge writer | a fresh Claude or Codex session through the shared launcher | the contract, Exit paths and code, not shaping chat | committed judge files on `piece/<n>`, and a JSON verdict |
| Builder | a fresh Claude Code (or Codex, **preview**) session per attempt | the contract, research, the judge, the last failure | code on the piece branch, `.loop/why.md`, optionally `.loop/outcome` |
| Standards reviewer | a fresh session after the gate passes | the diff, plus the project's standards file or a baseline of Fowler's code smells | small checked fixes, follow-ups, a JSON verdict |
| Contract reviewer | another fresh session | Intent, Out of scope, Approach, Contract, Research, build diff, frozen baseline and gate evidence | missing items or scope creep, a JSON verdict |
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
  pass on one cannot hide a fail on the other. Standards findings need a rule
  or smell and a changed hunk. Contract findings need an approved Contract ID,
  Research ID or Out of scope item. Changed code needs a changed hunk. Missing
  behaviour uses `kind: "missing"`, an approved D item, an existing file line
  in the judged commit and a description of what is missing. The run collapses
  findings with the same citation and claim, retaining the first location.
  It logs dropped findings with reasons and counts them in the pull request (code).
  Review diffs start at the ready commit with the base merged in, so shaping
  files and work merged from the base are baseline, not build changes. The contract reviewer also sees the attempt gate output,
  including critic verdicts. Both reviewers see numbered frozen baseline
  lines. The reviewers print one tagged JSON verdict; the run never guesses a verdict
  from free text [Sandcastle].
- **The standards reviewer may commit a non-test fix.** The fix is kept only
  if the judge passes again; otherwise its commits are dropped and the
  builder's judged commit goes forward (code).
- **Contract findings use evidence.** Reviewers may supply one test file for an
  approved Contract item. The run executes it with the approved Exit command
  in a disposable worktree at the judged commit. An assertion naming the item
  returns the piece to shaping with its test and output in a `judge-gap` record.
  Missing, passing or unrelated failures leave findings unresolved in the pull
  request, which makes no claim that the contract is met. Standards stay
  advisory (code). Reviewers may cite `baseline_conflict: "path:line"`
  when following a finding would contradict the frozen baseline. The run checks
  a non-empty line in a frozen file at ready; check-setting patterns match
  tracked paths, including configuration files in subfolders. Valid conflicts
  appear separately in the pull request and do not count as judge gaps. Numbered
  package manifests provide context; only check settings are frozen. Reviewers judge
  conflicts; scripts check citations in code and prose.
- **The gate and the run are scripts.** A coordinator agent forgets and
  drifts; a script does the same thing every time.
- **The person approves the two moments that need taste:** the contract and
  the merge. Everything in between is checked by a script.

**Backend (preview).** `Agent: claude|codex` in the loop section of
`AGENTS.md` chooses the backend for every launched role. Claude
Code is the default. The ready record freezes the choice, and
`run.py --agent codex` overrides it for one run. Interactive skills stay in
Claude Code. Codex build and review sessions use `codex exec --json` with a
workspace write boundary and network disabled. Builders may write the build
folder, its git directory
and a kit-prepared `.loop/tmp` directory, which is also their `TMPDIR`. In a
linked worktree they may also write the shared object store and their current
branch's ref, ref lock and reflog. Other worktrees and branches receive no
extra write access. System temp directories receive no extra write access.
The builder brief lists the allowed paths and permission settings. A refusal
that needs outside help returns an `environment` outcome with the path and
setting responsible. Walk-away secret denials still apply.

Every Codex session ignores the user's
config file and disables plugins and apps so their MCP servers do not start.
Codex has no guard hook and no Edit denies, so only the gate holds the rules
after the session.

Shaping starts research and judge writing with `scripts/session.py`, which
uses the same `agents.start_session` launcher as the build. Each capability
has fixed JSON input fields, required tools and an output format in
`agents.CAPABILITIES`. Shared instructions live in `kit/briefs/`. Claude's
adapter chooses `sonnet`; the brief does not name a model. Judge writing
starts on a clean `piece/<n>` branch. After validating the tagged verdict,
the launcher checks that only approved Exit files changed and commits them.
It compares untracked files, including ignored files, with the starting
baseline. Judge-writer sessions set `PYTHONDONTWRITEBYTECODE=1` and
`PYTEST_ADDOPTS=-p no:cacheprovider`. The path and clean-tree checks ignore
uncommitted files inside these tool cache folders at any depth:
`__pycache__`, `.pytest_cache`, `.benchmarks`, `.hypothesis`, `.mypy_cache`
and `.ruff_cache`. Folder names must match exactly. A loose `*.pyc` outside
these folders receives no exception. Every path committed during the session
must be an approved Exit file, including cache paths.
The path check also ignores changes inside a `node_modules` folder at any
depth, but only when Git ignores the path. Node test tools such as Vitest
write their caches there. The brief tells the writer not to install packages.
A `node_modules` folder that Git does not ignore is refused as unclean work.
Other ignored files, such as the person's own ignored notes, stay protected.
Other additions, removals and changes to contents, file types, symbolic links
or permissions outside the approved paths are refused. The refusal names
the first unexpected path and asks the person to inspect it against the
approved Exit files. A successful session leaves only tool cache files
uncommitted in the shared working tree. Refused work is kept for shaping to
inspect.

Research takes only `question`. Judge writing takes approved `Intent`,
`Approach`, `Contract` and `Files` strings, plus the code in the working folder.
`Files` lists the exact Exit paths, one per line. The brief forbids other
write paths. For a missing subject module, it gives an import stub and an
assertion inside the test, so the judge fails for the reason the gate accepts.
Missing dependencies still raise import errors. Extra input fields are
refused. Claude research enables only WebSearch and
WebFetch. Codex research enables live native web search with a read-only
sandbox and command tools disabled. Other sessions keep their existing
network policy. Walk-away research is refused. A missing executable, failed
session, missing web tool or invalid output stops shaping with a `next:`
step. Research must return dated source lines accepted by the existing
Research parser. Before accepting them, the launcher checks raw tool-failure
evidence from either backend. A failed web tool refuses research even when
the final answer is valid and the process exits successfully. The gate's
ready checks still apply.

Each builder attempt keeps the raw event stream, including tool calls and their
results, in a `.jsonl` file beside its readable `.log` file under `.loop/logs/`.
The event file is flushed as output arrives and kept when the build folder is
removed. A retry within the same attempt appends to both files.

## 8. The checks

### At ready (code, in a fresh copy of `main`)

| Check | Why |
| --- | --- |
| Intent, a non-empty `Out of scope` list and Contract IDs are present | The spec is complete enough to judge |
| Research lines have a source URL and a real read date | Outside facts need evidence |
| The Test command, any distinct `Keep:` and Prepare pass on `main` (scaffold skips the Test command and Prepare) | A red baseline makes every attempt fail for the wrong reason |
| The judge fails on `main`, not on a syntax, import, file-not-found or command-not-found error | A test that fails for the wrong reason proves nothing |
| Every non-`(stays)` ID is on a failing line; no `(stays)` ID fails | Each item is proven new, or proven kept |
| Test lint (`testlint.py`): an assertion in each test; no `assert True`, `x == x` or literal-only comparison; no skip, `xfail`, `.only` or `.skip`; no private imports or unnamed source reads; records unsupported languages and refuses unreadable judges with their paths | Tests must be able to fail [kata], and unchecked judges must stay explicit |
| The spec and the bar are hashed. The bar is the judge files plus every `conftest.py` and helper they rely on | Builders change what a test relies on, not only the test [ImpossibleBench] |
| The ready record freezes Test, Prepare, Keep, Quality, Standards, protected paths, idle, waiting and Keep limits, the base branch and the backend | A builder must not change the rules after they were agreed |

During an attempt, a syntax, import, missing-file or missing-command error in
the judge or Keep output returns the piece at once as `environment`. The cause
is `stale-after-main` when `main` moved since ready, and `import-error`
otherwise. The failure does not use another builder attempt.

A frozen-file refusal names every mismatched file. The Exit files are hashed
alone and must not change at all; a change from `main` to one of them is named
as inherited and returns the piece. The helpers and `conftest.py` files beside
them are compared with the expected tree: the ready commit with the base
merged in (`git merge-tree`, git 2.38 or later). So a sibling's judge or a
helper change that arrives from the base is free, and an edit or deletion by
the build is caught, committed or not. A file the build adds is allowed.
While a merge conflict is open, or when the expected tree has a conflict, the
helper check waits; the judge and the reviewers decide. Deleting a judge
created during shaping counts as a build edit. Between attempts, the run puts
back changed Exit files from the ready commit and edited helpers from the
expected tree. Older ready records derive the Exit hash from their commit.

When the base has moved since ready, the run runs the Exit tests once before
the first attempt. If they already pass, merged work has built the piece: it
returns as `spec-unclear` with cause `already-satisfied`, and the person drops
or reshapes it. A partial pass is built as normal. The remaining risk: a
helper can change on the base so that the judge still fails but tests less.
The re-check does not see that; the review of the base's own changes, and the
final pull request into `main`, are where a person sees it.

The ready message reports each Exit check. Tests name the contract IDs that
fail on main. Measure reports the median and missed target. Critics reports
main's wins out of three against the required two.

The required regression check runs the Test command from AGENTS.md on fresh
main before adding the judge files. `Keep:` adds a check and never replaces
that command. Identical commands run once. Ready records the regression
command, its limit in seconds and the main result. Scaffold readiness keeps
its exception while the runner does not exist.

Regression and Keep use `Keep limit:` in the project's loop settings, in
minutes. The default is 15. Doctor runs Keep on a fresh copy of `main` with
this limit and prints a `next:` step if it times out. Each Keep check records how many
seconds it took.

### At claim (code)

The spec hash and the bar hash must be unchanged. The gate checks the spec
hash again at submit, so a spec edited during the build fails. A pushed piece
branch must hold nothing the local branch lacks; the run never rewrites a
pushed branch. A ready record without the regression command is refused
with the next step to run ready again.

### At submit, after each attempt and again after the review (code)

| Check | Why |
| --- | --- |
| The Exit files are unchanged and no helper beside them was edited; a changed judge is put back and the attempt fails | The commonest cheat [ImpossibleBench], [Anthropic harnesses] |
| No existing test, `conftest.py` or fixture changed unless the Contract names it | Same cheat, one step removed. Rename detection is off, so a moved test stays visible |
| No protected path changed unless the Contract names it | Some code (auth, billing, CI) needs a person [Osmani, brownfield] |
| No generated path in the change, including runtime `.loop/` files, even if force-added. Submit and the field audit use the same path check | The field audit rejected generated files that the gate had accepted |
| No file grows from under 1,000 to 1,000 or more lines without `Large file:` | A sprawling file is a design smell agents create quickly [Cursor] |
| No secret shape (`.env` files, private keys, AWS, GitHub and `sk-` tokens) | Git history keeps a secret for ever |
| No conflict markers | A half-resolved merge |
| No file added under paths that Prepare created | `.venv` once leaked into a branch |
| No check-setting change unless `Settings: may change`. Check settings include lint, test and CI config, `.gitignore`, `AGENTS.md`, the standards file, and the check keys of `package.json` and `pyproject.toml` | A builder turned off a lint rule to pass |
| The judge passes, with nothing skipped | A skipped test passes silently |
| The recorded Test command passes. A timeout, missing runner or collection of no tests fails with its own reason | The piece must preserve the project's old behaviour |
| Any distinct `Keep:` passes. After a failure the gate retries it once with the judge files in place. If it passes, the pull request records cause `keep-flaky` and the failed test names, including unittest `FAIL:` and `ERROR:` headers. The gate blames the bar only when both failures locate a diagnostic in the same judge file and Keep passes without judge files, with nothing skipped | A judge that breaks the project's lint can never pass |
| Each `Quality:` command passes. A failure is retried, unless the same command also fails on a fresh `main` | The project's own quality bar |

The diagnostic must name a judge file in an explicit lint error (`error`,
`fatal` or an `E`/`F` code followed by three or four digits) or an exception
traceback. A warning, informational location or passing test's name is not
evidence. The no-judge result includes that run's own output. Without this
evidence, Keep fails the attempt without a `bar-wrong` diagnosis.

**Quality commands** belong to the project, not the kit, so the kit works for
any stack. Setup offers CRAP for Python (a limit of 30 on changed functions,
from coverage.py JSON) [CRAP], and ESLint `complexity` for Node. Mutation
testing uses the optional `ai-loop-kit-extras` plugin. Install it with
`/plugin install ai-loop-kit-extras@ai-loop-kit`, then run
`/ai-loop-kit-extras:setup`. Set `AI_LOOP_KIT_EXTRAS_ROOT` to the installed
extra's path in the shell that starts each gate or run command. A source
checkout uses its sibling `extras/` directory unless that variable is set.
The existing `quality/mutmut-check.py` and `quality/mutmut-changed.py` command
paths delegate to the extra. Ready and claim refuse a requested mutation
helper when the extra is absent, before any worktree or session starts.
They also check frozen Quality commands, so uninstalling the extra after
ready cannot weaken a contract. Walk-away checks this before doctor can
start a sandbox probe session. Gauntlet critics use the same plugin path.
Their code, brief and tests live in `extras/`; the full suite runs their
tests too. Other previews stay in the default plugin.
Mutation testing with mutmut 3.8 or later is **experimental**: it needs
configured source paths and in-process tests, because subprocess tests give no mutation
or coverage evidence [mutmut]. Doctor runs Test, then each Quality command, on
a fresh copy of `main` before setup accepts it.

If a builder must strengthen an existing mutation adapter, Contract names
its path. Keep it out of Exit `Files:` and the judge's dependencies, because
the bar is frozen even when Contract names a file. `mutmut-changed.py`
selects functions from committed `base...HEAD` changes. A builder's check
before committing may find no changed functions. Final gate evidence comes
after the runner commits the attempt and runs the checks again.

### Built well: the quality floor

The contract axis asks "did it build what was promised?". The craft axis
asks "was it built well?". Some craft questions a script can answer; some
need a reviewer.

| Question | Held by |
| --- | --- |
| Complexity and bloat | check: CRAP on changed functions, file size; lines added against the contract (**planned**) |
| Fit with the stack and architecture | check: the project's lint and type commands, import-boundary rules, no unnamed new dependency (**planned**) |
| Security | check: secret shapes, protected paths; a project scanner as a Quality command |
| Tests are real | check: test lint; mutation testing where it works (experimental) |
| Most effective approach, fit with design patterns | the standards reviewer, whose every finding cites a rule or smell and a changed line |

Two rules keep the floor lean. **The kit owns the slot; the project owns the
thresholds:** setup proposes a floor for the stack, and it is frozen at
ready. **Ratchet, not absolute** (**planned**): "not worse than `main`" works
on an old codebase where a fixed limit fails on day one. A finding that a
reviewer makes twice should become a check.

### After the merge (code, outside the loop)

`tests/field/audit.py` checks a project after the fact: one state per piece,
records present, `needs-you` only where valid, merged pieces done, the merged
code equal to the judged commit, and generated files absent.
It counts attempts from submit and give-back records. Rejections and later
pull-backs repeat earlier totals, so the audit does not count them again.

The seeded projects in `tests/field/fixtures/` test a missed regression, a
missing contract behaviour and a false review block. Each has separate
seeded code, correct code and an operator's oracle. Only the seeded project
goes into the builder workspace. `tests/field/QUALITY.md` records quality
outcomes per real run, including escapes to approval, false blocks, human
repairs, attempts and duration. `audit.py --quality <path>` checks that every
required field is present, without GitHub access. Historical `RESULTS.md`
rows keep their existing format.

The local cleanup check reads the reviewer process-group IDs retained in
`.loop/logs/reviewer-processes` and checks that each group has exited. It also
checks Git for remaining review worktrees and `review/*` branches. A missing
process record beside existing review logs fails the check. Run the audit in
the checkout that ran the build, where the local evidence lives.

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

- **Exit status.** The run exits non-zero when a piece fails, including an
  environment hand-back, a refusal or an unexpected error. It continues
  with the other pieces before returning that status.
- **Local events.** `.loop/events.jsonl` records run starts, stops and
  successful gate moves, including capture and hand-back, with UTC time,
  piece, event, resulting state, attempt and fixed reason. Boundaries use a
  null piece, empty state and attempt zero. It copies no free text, environment
  values or builder output; GitHub labels remain authoritative. Event writes
  add `/.loop/` to local `.git/info/exclude`. The judge-writer permits existing
  `.loop/` files but refuses other untracked work. A write failure warns once
  and leaves the run and gate moves running.
- **Local run page.** The run writes `.loop/dashboard.html` after each event
  and prints its full path. The run skill reports that path. The static page
  includes all its data and refreshes every five seconds without a server.
  It shows each selected piece's last recorded state, attempt, UTC time and
  pull request link, plus the run state and last event. Earlier runs are
  excluded. A visible notice reports disagreements with the GitHub labels,
  which remain the source of truth, or a failed GitHub check. Text is escaped.
  A page write failure warns and leaves the run running.
- **Idle limit.** An attempt stops after ten minutes with no output and no
  file change in the build folder (`Idle limit:` changes it). The hard limit
  is 40 minutes. Judge runs have a 900-second limit; Keep uses `Keep limit:`.
- **Build location.** The run prints the full worktree path before it starts
  a builder.
- **Worktree cleanup.** Moves to shaping, approval, done or dropped try to
  release the build folder. Ignored artefacts such as `node_modules` do not
  prevent removal. Uncommitted work and commits not merged into `main` keep
  the folder. Review cleanup checks against the piece branch instead. Probe
  cleanup first restores its injected judge files or proposed settings when
  their working and staged contents still match the injection. It preserves
  later edits and any other unfinished work. Every failed removal prints the folder and
  reason. Doctor lists leftover worktrees with their size in bytes and a
  safe-to-remove verdict, including folders outside the project.
- **Stop.** `gate.py stop` writes `.loop/stop`. The run checks it between
  attempts.
- **How the builder stops.** `.loop/outcome` accepts `bar-wrong`,
  `needs-answer` with a question, and `spec-unclear` with a cited reason. The
  last two return the piece to shaping with `needs-you`; the question appears
  in the run summary. A `spec-unclear` outcome without a citation counts as a
  failed attempt. For blocked cleanup, `environment` with a path and reason
  is checked against failed tool results in the raw event log. The run reports
  observed failed tool output, without filtering for known error phrases,
  and returns the piece to shaping before review or submit. An empty reason
  or a report without log evidence counts as a failed attempt. The builder
  no longer decides an open choice alone.
- **Interruption.** The run tracks every child process group and kills them
  on SIGINT or SIGTERM. The next run finds and removes what a killed run left.
- **The pull request.** The script writes the facts: files changed by area,
  tests added, new dependencies, risk (protected paths, migrations, config
  and check settings, large files, importer count), the judge, Keep and
  Quality output, the required regression command and result, the bar hash
  and the judged commit. It lists renames as a delete and an add. The builder writes only why, and what could go wrong. A
  person should understand the change and its danger in two minutes
  [HumanLayer], [Port]. The run never merges into `main`.

The importer count covers a Python and JavaScript/TypeScript source scan.
Its message names the exclusions: test directories, `test_*` files, exit
files and the scanner's ignored directories. An empty result means that
this scan found no importers. Built-in review rules have explicit names in
the reviewer brief; findings under these names still need a changed hunk.
When a rejected piece reuses an open pull request, submit must pass before
the run refreshes its title, body and judged-commit evidence. The evidence
uses the final submit output, including after reviewer changes, and lists
tests separately from frozen exit-support files. Output longer than
5,000 characters keeps only complete trailing lines and says it was cut. An update
failure returns the piece to shaping as `environment`, with cause
`pull-request-failed`.

### Walk-away runs (preview)

`run.py --walk-away` is for a run nobody watches. It starts only if
`gate.py doctor --walk-away` passes:

- Claude Code 2.1.285 or later, or a working Codex.
- A live probe: a real session must fail to write to the home folder, read
  `~/.ssh` and reach an outside host. Codex retries once if its answer has no
  readable probe line or has invalid exit codes. The result says it retried.
  A readable zero code or an observed home write refuses without a retry.
- Confirmed `Sandbox domains:` (package registries only). The gate reads the
  list from the loop section of `AGENTS.md` and passes it to Claude's strict
  network allowlist.
- Secret-shaped environment variables are removed from builder and reviewer
  environments. Preflight reports their names without values.
- Green Prepare and Test on a fresh `main`, 10 GB free, room in the approval
  queue.

During the run it writes `.loop/heartbeat` every minute, keeps a Mac awake
with `caffeinate`, waits once for a reported usage limit, and at the end
writes `.loop/summary.md` and posts it to a tracking issue. It never merges into `main`.

Codex denies credential folders such as `~/.ssh`, `~/.aws`, `~/.config/gh`,
`~/.config/gcloud` and `~/Library/Keychains`. Other config folders remain
readable, including `~/.config/git`. The builder brief says to carry on after
a warning from a command that exited successfully. An environment outcome
needs a failed command in the tool log. Two identical unsupported environment
reports in a row stop the piece as `builder-failed`, with the reason recorded.

## 10. The boundary

| Rule | Held by |
| --- | --- |
| No push to `main`, no force push, no agent merge, no recursive delete, no `eval`, no `xargs rm -r`, no `git clean` | hook (`guard.py`), in every session |
| A remote branch is deleted only when its live tip is in `main`; never `main`, `stable` or a piece branch | hook (`guard.py`), in every session |
| Builders and reviewers never push, never call `gh`, never run Perl or Ruby code, never use unreadable shell forms, never write into `.claude/`, `.githooks/` or protected paths | hook, in build sessions |
| Builders never edit the judge files or check settings | Edit denies, then the gate at submit |
| The gate is the only mover of state | hook refuses `state:` label edits; `audit.py` finds any it missed |
| Only owners, members and collaborators write gate records | code |
| `main` refuses direct pushes on GitHub | branch protection, set by bootstrap where the plan allows; doctor reports it |
| The first push of `main` happens once | code: bootstrap pushes only when origin has no `main`; the hook still refuses an agent's push |
| No secret in a tracked file | code at submit, and words |
| The spec says what the person meant | words: the person approves the contract |
| The person merges every pull request into `main` | the only merge in the kit refuses `main`, `master` and the default branch (code); the hook refuses `gh pr merge` from agents |
| Walk-away shell commands stay in the build folder and reach only allowed hosts | sandbox, checked by a live probe |

The guard is a seatbelt, not a sandbox. It splits words and matches patterns.
It reads the `git -C`, `git -c`, `gh -R`, `bash -c`, `sh -c` and `eval` forms,
and removes known options from leading wrappers such as `sudo`, `env`,
`command`, `exec`, `nohup` and `time` before checking the command. In build
sessions it refuses an option it cannot read. It is not a full shell parser,
and a determined agent can get round it. The
gate is the backstop, because it checks the result whatever the agent did.

Claude Code's sandbox covers Bash and its child processes. Read, Edit, Write,
web tools and hooks run outside it. So walk-away Claude sessions also load no
MCP servers, deny reads of credential paths, project `.env*` files except
`.env.example`, and paths named with `Secret paths:` in the loop section. A
second hook keeps file-tool writes in the build folder. An allowed domain can
still carry data out. Attended runs have no sandbox: the builder runs Bash
with the person's network, under the guard.

## 11. Setup, shape and run

This repository's default branch, `stable`, supplies the released kit to
installers. Work merges to `main`, which carries a development version
between releases. Every pull request names `main` as its base; a workflow
refuses a base of `stable`. After publication and verification, the release
uses `.agents/tools/promote-stable.sh` to move `stable` to the published
tag's commit and read the ref back. The tool refuses an update that would
overwrite work. `CONTRIBUTING.md` gives the release steps.

1. **Install:** `/plugin marketplace add gwpicard/ai-loop-kit`, then
   `/plugin install ai-loop-kit@ai-loop-kit`.
2. **`/ai-loop-kit:setup`**, once per project, in any folder.
   `gate.py bootstrap` makes what is missing: the git repository, the
   GitHub repository (the person approves its name and visibility once), the
   first commit, the one push that makes `main` on origin, protection on
   `main` where the plan allows, and the labels. The person only signs in to
   `gh`. The skill agrees these with the person: the backend, Prepare, Test,
   Quality, Standards, protected paths and sandbox domains. They go in a
   `## The loop` section of `AGENTS.md`: in the first commit for a new
   project, or on a branch with a pull request when `main` already has
   work. Doctor checks it all on a fresh copy of `main` (code). A project
   with no tests yet gets a warning and the scaffold piece as its next step.
   A project may add `Base branch: <name>` to the loop section. Then every
   piece builds on that branch, not on `main`: ready judges against it, the
   run merges it into each piece, and each pull request targets it. The gate
   reads the setting from `AGENTS.md` on `main`, so a branch switch or a
   build cannot change it, and the ready record freezes it. Make the branch
   from `main` after the setting is merged. When the loop branch is merged
   into `main`, remove the line to end the loop. Quality commands get the
   name in `LOOP_BASE`, and doctor warns about a Quality command that names
   `origin/main`. With no setting the base is `main`. In check messages,
   "main" means the base branch.

   `Agent model:` and `Agent effort:` choose the Codex model and its
   reasoning effort, passed as `-m` and `model_reasoning_effort`; the kit
   still ignores the person's own Codex config. Ready freezes them, and the
   builder and reviewers use the frozen values. Sessions with no ready
   record, such as shaping and doctor's probe, read them from `main`. Only
   `doctor --walk-away` runs a live probe, so only it shows a wrong model
   name before a run. Claude ignores them. At the end of each run, the run opens or
   updates one pull request from the base into `main`. It lists each piece
   pull request merged into the base, in merge order, and names the check
   settings and protected paths each one changed. It also lists the piece
   pull requests still waiting and the pieces the run held, and then its
   title says "incomplete". The run never merges it.

   With `Base merges: run` (read from `AGENTS.md` on `main`), the run merges
   each piece that passed the gate and its reviews into the base, then moves
   it to done. The merge reads the pull request's real base and refuses
   `main`, `master` and the default branch, a closed pull request and a
   branch that is not a piece. It uses `--merge --match-head-commit`, so
   only the gated commit lands. The run leaves a piece for the person when
   the contract review left findings, when the base moved after the gate,
   when GitHub refuses the merge, and when the piece changes `.github/`,
   `.githooks/` or `AGENTS.md`. Workflows and hooks run code, with the
   repository's secrets, as soon as they land, and `AGENTS.md` changes the
   loop's rules, so a person reads those first; the run says so on the
   issue. A piece left for the person holds its dependents. The waiting
   limit does not apply, and a failure here never stops the run. The base
   branch must not require checks or reviews; on a free private repository
   GitHub cannot require them.
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

The run skill loads `run-recovery` only for interruptions, orphan processes,
run locks, dirty folders, conflicts, stops or environment hand-backs. It loads
`reject-handling` only when the person rejects a pull request. Both support
skills use `user-invocable: false` and remain available to the model.
`run.py --retry-conflict <n>` sequences the existing conflict hand-back and
ready checks under the run lock before retrying. A refused check stops it.
Walk-away guidance is a conditional reference. The ordinary run skill loads
265 source words, down from 903, counting frontmatter and command snippets
with `len(text.split())`. Runtime output and project data add variable text.
The word-budget test caps every skill, reference, agent definition and brief,
and their combined total. Unchanged files keep their present ceilings until
their own thinning change.

Doctor checks GitHub sign-in with `gh auth status --active`. An expired
inactive account does not block setup. If an active account fails, doctor
keeps the CLI's error message, including the account and host.

Doctor recognises empty collection from exit code 5 and either a direct
pytest command or collection output. Quiet pytest needs no summary. The next
step is to add tests or fix collection. Unrelated exit-code failures keep
their output and a general repair step.

Unknown branch protection prints `unknown`; leftover worktrees print `warn`.
Both remain non-blocking. A list Contract is refused with the next step to
encode it as one JSON string.

Status groups the current labels from one open-issue list, so a move to ready
does not wait for label search to catch up.

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
- GitHub's closing keywords apply when a pull request targets the default
  branch. Only a `Closes` line is used. In this repository, pull requests
  target `main` and the default is `stable`, so the person or the run must
  close the issue after the merge. A merge into a base branch never closes
  an issue, so the gate closes it when the piece moves to done.
- A setting merged on GitHub reaches the kit only after a fetch. Ready, claim,
  doctor and the run fetch `main` first and warn when they cannot. The ready
  record takes its base from the same read that judged the piece.
- GitHub's label search lags after a move. The run retries the ready list for
  about 20 seconds.
- A free private repository has no branch protection. The local layers must
  hold alone, and setup says so.
- A hook wired twice runs twice. Skill paths need `${CLAUDE_PLUGIN_ROOT}`.
- A skipped check once printed as "passed". A check that did not run is never
  green.
- Many parallel sessions crashed the Mac from memory pressure, and once
  filled the disk. The run builds one piece at a time.

## 13. How the kit learns

- **Within a piece**, each attempt gets the last failure. Retries stay
  bounded at three: an open-ended "retry until good" costs money and invites
  gaming.
- **Across pieces**, the kit does not keep a growing notes file for agents to
  read; context files decay and cost accuracy [ETH AGENTS.md], [Osmani, skill
  decay]. `gate.py report` groups hand-backs by type and cause, and shows the
  number of pieces started and how many passed on the first attempt.
- **The meta loop is a person reading that report**, with one rule: the same
  cause in three different pieces earns a change. Many `judge-gap` points at
  weak exits; many `spec-unclear` at shaping questions; many `environment` at
  setup. A project change (floor, standards, questions) is made by the person
  and applies from the next ready piece. A kit change follows the earn rule.
- **From real use.** Field reports from people using the kit carry the same
  report, so their runs can earn changes too.

## 14. Where the kit goes after 1.2

Each step waits for a real run that needs it.

- **A combined branch.** Pieces join a run branch by trial merges in a
  scratch copy; each join runs every joined piece's checks again; a piece
  that must leave is rebuilt, never reverted. About 28% of agent pull
  requests conflict [AgenticFlict]. The first step is read-only: report
  whether the waiting pull requests merge cleanly together.
- **Pre-approved merges into `main`.** The run already merges gated pieces
  into a base branch; `main` still needs the person.
- **A test environment set up once**: the services tests need, a test env
  file with fake values, and a fast test command for the builder beside the
  full one for the gate.
- **Deploy** stays a project-owned command, like Quality.
- **Held-out tests**, when a builder is seen special-casing visible tests.

## 15. What the kit does not do, and why

| Not done | Why |
| --- | --- |
| Merging into `main` | The person reviews and merges the one pull request into `main`. About 28% of agent pull requests conflict [AgenticFlict]. A conflict after a sibling merge goes to the builder. |
| A GitHub App identity | The person's own sign-in is enough while runs are attended. |
| Automatic merges into `main` | Merging into `main` is the person's moment. |
| Crews, design-it-twice, a skills registry or context store | Coordination cost with no proven need [Pocock, codebase-design], [Port]. |
| A fixed sentence pattern for every item | It makes odd, long issues. "When ..., then ..." is a guide only. |
| Hand-kept diagrams or data models | They drift. Generated views may come later. |
| A paid code-health score | CRAP covers the same ground for free [CodeScene]. |
| A container around each Claude process | Revisit if a walk-away run finds a gap in the built-in sandbox. |
| Maintenance and live-feedback loops | They need projects that live for weeks. |
| Parallel builders | They crashed the machine. One piece at a time. |

## 16. Size

The default plugin has 7,058 Python lines in `kit/`, including the remaining
previews and quality entry points. The optional mutation tools and gauntlet
critics have 422 runtime lines in `extras/`. Together they have 7,480 runtime
Python lines. The kit uses the Python standard library only. It runs on one Python,
3.13, started through `kit/bin/kit-python`: uv finds or installs that
version, and the script runs on it directly. The version lives in the
launcher only. A project's own Python (its Test, Prepare and Quality
commands) stays the project's choice. Control scripts refuse an older
Python and name the launcher; if the guard cannot start or crashes, it
refuses the call. Docker was rejected for the kit: the guard runs on every
tool call, and the kit drives the person's own tools and sign-ins.

`tests/test_size_inventory.py` counts every Python file under `kit/` and
`extras/`. It checks extra test files against the 800-line file ceiling but
excludes them from the runtime total. It fails above 800 lines per file or
7,480 runtime lines in total. The suite reports the total and the
default-install size separately. The total budget follows the measured size; a smaller budget
needs a measured reduction first.

## Words used in this file

| Word | Meaning |
| --- | --- |
| piece | One GitHub issue: about one hour of work, with one state label |
| spec, contract | The issue body the person approves. `## Contract` is its numbered list of items (D1, D2) |
| judge, exit condition | The checks (tests, a measure, or critics) that decide whether a piece is done |
| playbook | How a builder works on a kind of piece, such as "reproduce the bug first" for a fix; it never decides done |
| quality floor | The project's craft checks every piece must pass, set at setup and frozen at ready |
| ratchet | A check that passes when the branch is not worse than `main` |
| cause | The hand-back's short reason, such as `keep-flaky`, `prepare-failed`, `import-error` or `pull-request-failed` |
| bar | The judge files plus every helper and `conftest.py` they rely on, frozen by a hash at ready |
| gate | `gate.py`, the only script that moves a piece and the only one that decides |
| run | `run.py`, the script that claims, builds, reviews and opens pull requests |
| Keep | An optional check that adds to the required Test command |
| Prepare | The command that installs tools in a fresh copy of `main` |
| Quality | Extra project checks, such as CRAP or mutation testing |
| check settings | Files that decide how the project checks itself: lint, test and CI config, `.gitignore`, `AGENTS.md`, the standards file |
| typed reason | The one-word type on every move back, such as `bar-wrong` or `environment` |
| protected path | A path that needs a person; a piece may change it only if its Contract names it |
| waiting limit | How many pull requests may wait before the run stops starting pieces |
| held | A ready piece the run skips because a piece it depends on is not done |
| wave | Pieces whose dependencies are all in earlier waves; the final pull request groups by wave |
| base branch | The branch pieces build on and pull requests target: `main`, or the `Base branch:` setting |
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
