# AI Loop Kit: the design, and why

This file describes how the kit works and gives the reason for each part.
`docs/V1.md` says what v1 does, in short. This file says why. Each reason
names its evidence: a run of the kit (in `docs/LESSONS.md`,
`docs/LEDGER.md` or `tests/field/RESULTS.md`), or an outside source (listed
at the end, and in `docs/SOURCES.md`).

## 1. What the kit is

AI Loop Kit is a Claude Code plugin for one person who builds software with
agents. In one sentence: a state machine whose every state is a loop, where
agents do the work, scripts decide, and the person approves the contract and
the merge.

## 2. The problem it solves

Four failures come back again and again when agents build software.

| Failure | Evidence |
| --- | --- |
| The agent says the work is done when it is not | The first kit's own build: agents reported checks that had not run (`docs/LESSONS.md`). METR found that telling a model not to cheat did not change how often it did [METR]. |
| The agent changes the test, not the code | ImpossibleBench: models edit or delete tests to pass impossible tasks [ImpossibleBench]. In our field runs a builder turned off a lint rule project-wide to pass (`docs/LEDGER.md`, 14 October). |
| The spec drifts away from the code | Spec-driven development moves the requirements problem and adds a document that drifts [Scala Teams], [Martinelli], [DevGenius]. |
| The person cannot keep up with review | Agents can write faster than a person can check; quality depends on the constraints set around them [Osmani, quality]. |

The kit answers each with a mechanism, not an instruction. Words alone did
not hold in the first kit; scripts did (`docs/LESSONS.md`, section 2).

## 3. The five principles

| Principle | Why | Source |
| --- | --- | --- |
| **Agents produce, scripts decide, the person approves** | An agent's report of its own work is not evidence. A script that runs the check is. | [METR], [Anthropic harnesses], first kit (`docs/LESSONS.md`) |
| **A piece is a contract** | A test written before the build, that fails today, is the only proof that the build changed something. | [TDFlow], [Anthropic harnesses] |
| **Every state is a loop** | Work fails. A failure that goes back with a reason can be fixed; one that goes forward is merged. | The first kit's kickback design (`docs/archive/v1-design/design.md`) |
| **Hold rules in code, and label what is only words** | Hard constraints belong somewhere stronger than prose. Prose is read once and forgotten. | [Osmani, agent files], [ETH AGENTS.md] |
| **Grow from evidence** | The first kit was designed in full before it ran, grew to about 35,000 lines and built no piece. | `docs/ANGLE.md`, `docs/LESSONS.md` |

## 4. Why a state machine

The kit could have been a long prompt that tells an agent what to do next.
It is a state machine instead, for four reasons.

1. **One place decides.** Every piece is in exactly one state, and only one
   script, `gate.py`, may change it. An agent cannot skip a step, because the
   step is a move the gate refuses. In the first kit, a coordinator agent that
   decided the next step forgot decisions after a restart and once ran as two
   coordinators at once (`docs/LESSONS.md`, section 1.4).
2. **Every move is checked where it happens.** Each move has its own checks.
   A piece cannot reach `ready` without a judge that fails, and cannot reach
   `approval` without passing it. The checks live on the edges, so nothing
   reaches a state it has not earned.
3. **The state is visible and stored outside any session.** The state is a
   GitHub label and every move writes a record comment. A new session, a
   person on their phone, or the audit script can all read it. Nothing lives
   only in a context window.
4. **It can be tested.** A finite set of states and moves can be tested move
   by move. `tests/test_loop.py` does that with a fake `claude`.

### Why these six states

| State | Why it exists |
| --- | --- |
| shaping | Work that is not yet clear. Most of the effort goes here, because a vague piece cannot be built well by anyone. |
| ready | The contract is approved and the judge is fixed. The line between "deciding" and "doing". |
| building | One run owns the piece. The lock and the state together stop two runs building the same piece. |
| approval | The gate has passed the piece and a pull request waits for the person. |
| done | Merged. Reached only through `gate.py sync` reading GitHub. |
| dropped | Work that will not be done, kept with its reason. |

The first design had seven states, with a separate `review` state, and 14
moves. The thin kit took the review state out: the person reviews each pull
request, so a separate state added moves and no check. The field runs worked
with six (`tests/field/RESULTS.md`).

### Why moves back carry a typed reason

Every move back to shaping names a type: `spec-unclear`, `bar-wrong`,
`judge-gap`, `environment`, `builder-failed`, `person-rejected`, `conflict`
or `stopped`. A free-text reason helps the next attempt. A type can be
counted. `gate.py report` counts them, which shows where the system fails:
weak judges, unclear specs or a broken environment. The first kit used one
"parked" word for three meanings and could not tell them apart
(`docs/LESSONS.md`, section 2.2).

## 5. The loops

The kit is loops inside loops. Each loop has an entry check, work, an exit
check and a way back.

```text
 meta loop: typed reasons across many pieces  ─────────────────────────┐
   shaping loop: question, write, judge, check  ──► ready              │
     build loop: fresh attempt ──► gate judges ──► retry (up to 3)     │
       review pass: two fresh reviewers, once ──► gate checks again    │
   the person: merge, or reject with a reason  ──► back to shaping ◄───┘
```

| Loop | What turns | Stops when | Why it is a loop |
| --- | --- | --- | --- |
| Shaping | questions, the contract, the judge | the gate accepts ready | A judge that breaks the project's lint, or names an ID that never fails, sends shaping round again. Field runs showed this three times (`docs/LEDGER.md`). |
| Build | fresh builder attempts | the gate passes, or 3 attempts fail | A fresh session per attempt does not carry a failed idea forward. This is the Ralph technique: change the input and run again [Ralph]. |
| Review | two reviewers | once, always | A review asked for gaps always finds some, so it never converges. One pass with cited findings is the honest form [Pocock, code-review]. |
| Meta | typed reasons | the person changes the kit or the project | The same failure should not happen a third time. A lesson becomes a check, not a sentence [Osmani, skill decay]. |

### One loop, many judges

The build loop is the same for every kind of work. Only the judge changes.
This came from the first design, which had four separate loop modules
(build, fix, goal, gauntlet) and found they were one loop with four judges
(`docs/archive/v1-design/design.md`).

| Kind | Judge | Why |
| --- | --- | --- |
| feature | acceptance tests that fail today | new behaviour must be shown to be new |
| fix | a test that reproduces the bug | most real work is in existing code [Martinelli], and a bug fixed without a reproducing test comes back |
| scaffold | the test runner runs | an empty project has nothing that can fail, so the record says the check was skipped |
| goal (later) | a measurement against a threshold | goal-driven agents are the next step [Port], but they need a measurement harness first |
| gauntlet (later) | a blind critic against a reference | for work a test cannot judge, like design; it needs a critic role first |

## 6. The contract

### Why two parts

A piece has an **intent** (the person's words) and a **judge** (the machine's
copy). Either alone fails. Intent alone is prose that nothing checks. A judge
alone checks what the shaper thought, not what the person meant. Together,
the person can read what will be checked, and the gate can check it.

### Why each section

| Section | Why |
| --- | --- |
| Intent | It holds what the code cannot say: the why and the limits [Osmani, brownfield]. |
| Out of scope | The requirements problem is mostly scope. Saying what will not be done is the cheapest guard against scope creep [Scala Teams]. The contract reviewer checks it. |
| Approach | Agents do better when told the path, not only the output: the module, the interface, the pattern to follow [Osmani, agent files]. |
| Contract items | Numbered and concrete, with an example each, so one test can prove each item and the gate can find each ID in the output. |
| `(stays)` | "Every item must fail on main" pushed shaping to drop true items or bend tests (`docs/LEDGER.md`, 14 October). `(stays)` marks what must keep working. |
| Judge, fixed by a hash | A builder that cannot change the test can only change the code [ImpossibleBench], [Anthropic harnesses]. |
| Keep | The judge proves the new work. Keep proves that old work still works. A field run lost old behaviour when only the judge ran (`docs/LEDGER.md`, 13 October). |

### Why it is not waterfall

Critics of spec-driven development say it is big design up front, and that
the spec drifts from the code [DevGenius], [Martinelli]. The kit avoids both.
A piece is shaped just in time, from today's `main`, and is about one hour of
work. After the merge the issue closes as a record; the tests are the living
spec, and nobody edits an old issue to keep it current.

## 7. The roles

| Role | Why it is separate |
| --- | --- |
| Shaper, with the person | Only the person knows the intent. The shaper asks, splits and writes, and never builds. |
| Judge writer | Tests written first by someone other than the builder help the builder most [TDFlow], and an agent that writes both code and tests confirms itself [Fowler, TDD in the loop]. The judge writer also does not see the shaping chat, so it tests the contract, not the shaper's assumptions. |
| Builder | A fresh `claude -p` per attempt, requested as `stream-json`. Stream events reset the idle clock. The run also checks file activity under the build folder every two seconds, skipping `dist/`, `build/` and `__pycache__`; logs keep readable assistant text. Process groups, the run lock and the main-ref cache live in `procs.py`, which the entry point and its helpers share. A small context holds the contract, the judge and the last failure only. Coding standards stay out, so the builder is not overloaded. |
| Standards reviewer | Standards belong to a reviewer that reads the diff, not to the builder's context or `AGENTS.md` [Pocock, code-review], [Osmani, agent files]. Its baseline when a project has no standards is Fowler's code smells [Fowler, Refactoring], plus the hard points of a strict maintainability review [Cursor, thermo-nuclear]. |
| Contract reviewer | A separate axis: is it the right thing? Kept apart from standards so a pass on one cannot hide a fail on the other [Pocock, code-review]. A missing item means the judge was weak, so it is counted as `judge-gap`. |
| Gate and run | Scripts. The first kit's coordinator agent forgot and drifted; a script does the same thing every time (`docs/LESSONS.md`). |
| The person | Approves the contract and the merge: the two moments that need taste and judgement. Everything between is checked by a script. |

Every finding a reviewer makes must cite a rule, a smell or a contract line,
or it is dropped. Reviewers print one tagged JSON verdict that the run reads;
the run never guesses a verdict from free text [Sandcastle].
The standards reviewer gets the frozen standards path from the ready record,
runs Prepare in its own folder, and may keep a non-test fix only after the
judge passes again. Review folders and branches are removed on every exit.
The next run also clears and reports any review worktree or branch left by an
interrupted run.

## 8. The checks

| Check | Why |
| --- | --- |
| The judge fails on `main` on an assertion | A test that already passes, or fails only on an import error, proves nothing. |
| Test lint: an assertion in each test, no `assert True`, no `x == x`, no skips, no private imports, no reading source as text, no mirror of the code under test | Automated checks can lie: a test can restate the code, mock its subject or never be able to fail. These are the mechanical cases [kata, testing without tautologies]. |
| The bar covers `conftest.py` and test helpers | Builders change what a test relies on, not only the test file [ImpossibleBench]. |
| No existing test changed | Changing an old test is the commonest cheat [ImpossibleBench], [Anthropic harnesses]. |
| No check setting changed | Ready freezes Test, Prepare, Keep, Quality, Standards, protected paths and the idle and waiting limits. `AGENTS.md` and the named standards file are check settings, alongside project test configuration. A builder in our field runs turned off a lint rule to pass (`docs/LEDGER.md`, 14 October). |
| Protected paths | Some code (auth, billing, CI) needs a person. Zone the code [Osmani, brownfield]. |
| No file grows past 1,000 lines | A file that sprawls is a design smell agents create quickly [Cursor, thermo-nuclear]. |
| Quality commands: CRAP and mutation testing | CRAP limits changed functions to a score of 30. Mutation testing matches changed functions to mutmut's names, reads all results, requires tested mutants for each changed function and rejects survivors [CRAP], [mutmut], [Stryker], [Meta ACH]. Doctor runs Test before Quality in the same fresh copy of main. They are the project's commands, not the kit's, so the kit works for any stack. A failed Quality command is retried unless it also fails on a fresh copy of main; that check uses the frozen Test command, and its cache key includes the Quality command and main commit. |
| Secret shapes | A secret in git history stays for ever. |
| Nothing skipped | A skipped test passes silently. |

## 9. The pull request

The script writes the facts: what changed, the risk, the evidence. It lists
renames as a delete and an add, so moved tests remain visible. The
builder writes only why, and what could go wrong. A person should understand
the change and its danger in two minutes [HumanLayer], [Port, change review].
A waiting limit stops the run when three pull requests wait, so building never
outruns review [Osmani, quality].

## 10. The boundary

The guard hook refuses the hard rules in every session: no push to `main`, no
force push, no agent merge, no recursive delete, no `eval`, and no `xargs`
with `rm`. In build sessions it also refuses Perl and Ruby code execution,
unreadable shell wrappers, and redirects into `.claude/`, `.githooks/` or
protected paths. It refuses a plain push from `main`. It is a seatbelt, not a
sandbox: branch protection on GitHub is a second layer, and runs are attended.

A sandbox is later. The likely shape is a container with an `agent` user that
has the person's user id, the worktree mounted inside, and the token passed in
[Sandcastle]. Sandcastle's own notes list several kinds of permission bug with
Docker on macOS, so it waits until the boundary above is solid.

## 11. What the kit does not do, and why

| Not done | Why |
| --- | --- |
| A GitHub App identity | Useful for unattended runs; the person's own sign-in is enough while runs are attended. |
| An integration branch and combined review | Pieces merge one at a time and conflicts go back to the builder. About 28% of agent pull requests conflict, so this returns when runs grow [AgenticFlict, in the archive design]. |
| A researcher role, crews, design-it-twice | No run has needed them, and each costs many tokens [Pocock, codebase-design]. |
| A skills registry or context store | Shared infrastructure for large teams [Port]; against a thin kit. |
| A hard rule that every item uses a fixed sentence pattern | It makes odd, long issues. Used as a guide only [Scala Teams]. |
| Hand-kept diagrams or data models | They drift. Generated views may come later. |
| A paid code-health score | Proprietary [CodeScene]. CRAP covers the same ground for free. |
| Walk-away runs | Need the sandbox first. |

## 12. How v1 was built, and how the kit grows

The thin kit grew one earned feature at a time from 13 October 2026. For v1
the maintainer chose to build from a plan in one pass (`docs/V1-PLAN.md`),
with tests and rehearsals at the end, so v1 could be used sooner. The
amendments from review and the rehearsal findings are in `docs/v1/`. After v1
merges, the earn rule applies again: a failure in `docs/LEDGER.md` first, then
a test, then the feature.

## Sources

Outside sources named above. `docs/SOURCES.md` lists the earlier ones.

- [Anthropic harnesses] Anthropic, [effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents).
- [METR] METR, [recent reward hacking](https://metr.org/blog/2025-06-05-recent-reward-hacking/).
- [ImpossibleBench] [ImpossibleBench](https://arxiv.org/abs/2510.20270), and its [repository](https://github.com/safety-research/impossiblebench).
- [TDFlow] [TDFlow](https://arxiv.org/abs/2510.23761): tests written first by someone else.
- [Meta ACH] [Mutation-guided test generation at Meta](https://arxiv.org/abs/2501.12862).
- [Ralph] Geoffrey Huntley, [the Ralph technique](https://ghuntley.com/ralph/).
- [ETH AGENTS.md] [Evaluating AGENTS.md](https://arxiv.org/abs/2602.11988).
- [Pocock, code-review] Matt Pocock, [code-review skill](https://github.com/mattpocock/skills/blob/main/skills/engineering/code-review/SKILL.md).
- [Pocock, codebase-design] Matt Pocock, [codebase-design skill](https://github.com/mattpocock/skills/blob/main/skills/engineering/codebase-design/SKILL.md), after John Ousterhout's deep modules.
- [Cursor, thermo-nuclear] Cursor, [thermo-nuclear code quality review](https://github.com/cursor/plugins/blob/main/cursor-team-kit/skills/thermo-nuclear-code-quality-review/SKILL.md).
- [Fowler, Refactoring] Martin Fowler, Refactoring, chapter 3, code smells.
- [Fowler, TDD in the loop] [TDD in the agent loop](https://martinfowler.com/articles/exploring-gen-ai/tdd-in-the-agent-loop.html).
- [kata, testing without tautologies] [kenn-io/kata](https://github.com/kenn-io/kata), its testing skill.
- [Sandcastle] Matt Pocock, [sandcastle](https://github.com/mattpocock/sandcastle).
- [CRAP] Alberto Savoia and Bob Evans, the CRAP metric (crap4j, 2007).
- [mutmut] [mutmut](https://mutmut.readthedocs.io/en/latest/); [Stryker] [StrykerJS](https://stryker-mutator.io/docs/stryker-js/incremental/).
- [Osmani, agent files] Addy Osmani, [audit your agent files](https://addyosmani.com/blog/audit-your-agent-files/).
- [Osmani, skill decay] [agentic skill decay](https://addyosmani.com/blog/agentic-skill-decay/).
- [Osmani, brownfield] [brownfield agentic engineering](https://addyosmani.com/blog/brownfield-agentic-engineering/).
- [Osmani, quality] [agentic code quality](https://addyosmani.com/blog/agentic-code-quality/).
- [CodeScene] [agentic AI coding best practice patterns](https://codescene.com/blog/agentic-ai-coding-best-practice-patterns-for-speed-with-quality).
- [Port] [agentic engineering 2.0](https://www.port.io/blog/agentic-engineering-2-0); [Port, change review] [goodbye code review, hello change](https://newsletter.port.io/p/goodbye-code-review-hello-change).
- [Martinelli] [why spec-driven development tools fail in the enterprise](https://martinelli.ch/why-spec-driven-development-tools-fail-in-the-enterprise/).
- [Scala Teams] [spec-driven development: the requirements problem](https://www.scalateams.com/blog/spec-driven-development-requirements-problem).
- [DevGenius] [the spec is the code](https://blog.devgenius.io/the-spec-is-the-code-why-i-dont-buy-spec-driven-design-f75c784f7b46) (read from a summary; the page refused access).
- [HumanLayer] HumanLayer's "show me" review approach (read from a secondary description only).
- [AgenticFlict] cited in `docs/archive/v1-design/design.md`.
