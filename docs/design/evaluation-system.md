# Evaluation system design

This is the written design the epic asks for before any of it is built. It names
the Level 1 dimensions, the two tiers, the metric, the state-assertion redesign
of the replay harness, the Level 2 code-health review, and the deterministic CI
gate. It ends with the cut: the pieces this epic should spawn, and the decisions
that still need a person.

It is grounded in a read of the harness as it stands on 21 August 2026, not
written from first principles. Where it says the harness does something today,
that was checked against the file named.

## Why this exists

The kit asks a person to direct work they cannot read. Two things then have to
be vouched for by something other than that person: that the skills behave as
written, and that the software the agent builds is sound. Today neither is
covered well, and nothing deterministic stops a new kit version that quietly
drops a behaviour or claims one it did not build.

The design keeps the two apart on purpose.

- Level 1 watches the agent follow a skill and checks it behaved right and left
  the right result on disk. This is the kit's own regression gate.
- Level 2 has the kit review the code it produced and report in plain words.
  This is a new kit capability, and once it exists Level 1 can measure it too.

## What the harness does today, and where it is thin

The replay harness (`.agents/tests/replay/`) assembles a release, stands up a
throwaway project with a real git repo and a bare remote, holds a whole
conversation with the kit, and asks a separate grader whether what happened
matched the contract in `scenarios.md`. Each scenario runs several times and the
output is a rate, not a pass. For what it covers, it is the right tool, and the
redesign keeps its spine.

Four things are thin, and all four were confirmed by reading the code.

1. **It grades the talk, not the world.** `grade_once` in `run.sh` hands the
   grader the contract and the transcript and nothing else. The harness already
   stands up the git repo, the bare remote, the fake-GitHub state file
   (seeded from `.gh-fixture.json` and now kept beside the project as
   `<project>.gh.json`), and copies in `masterplan.md` and `CHANGELOG.md`, then
   asserts on none of them. So the grader can read the kit's claim that it
   recorded an acceptance, never whether the file changed. This is the single
   biggest hole.

2. **The script cannot adapt.** In `run_once`, the whole turn-selection logic is
   `message=$(cat "$turnfile")`. Nothing reads the kit's reply before sending
   the next line. Because `clarify` asks one question at a time, a different
   interview order lets a scripted "yes, I accept" answer a question the kit
   never asked. The grader refuses to credit words the person typed, so this
   does not cause false passes; it causes noise, which shows up as flakiness in
   the rate.

3. **The early-stop guard catches a short conversation, not a sideways one.**
   `one_pass` counts kit replies against the expected turn count and refuses to
   grade a run with too few. That catches a truncated run, which would otherwise
   score as a hold it never earned. It does not catch a run that reached the
   right number of turns down the wrong path.

4. **Coverage sat on one behaviour, and has been cut back.** When this was
   written, ten cases were wired and seven of them exercised the risk notice
   and its earned acceptance. Shaping cases were added afterwards and the four
   most duplicated notice cases (3, 4, 6 and 15) were retired, which leaves ten
   wired cases with three on the notice: 5, 8, and the negative control 31. The
   founding cases 24 and 25 were removed for a separate reason and are guided
   manual checks now, recorded in `.agents/tests/replay/README.md`.

   The imbalance is dealt with. The gap it pointed at is not. Twenty-eight of
   the forty-two contracts in `scenarios.md` are still never driven through the
   grader, and no case drives `/implement`, `/ship`, `/sync`, `/queue`,
   `/maintain` or `/what-now` at all.

The functions with no working replay coverage include the ones the philosophy
calls most valuable: talking a person out of building, choosing the right form
of evidence and refusing a fake test, shaping a vague request into a sound
ready piece, the ready gate between `/shape` and `/implement`, path-adaptive
`/ship` with a backup and a restore rehearsal, and `/sync` keeping the records
true after messy work.

## Level 1: does a skill behave as written

### The dimensions

A skill is measured on seven things, in plain terms.

1. Did it switch on when it should, and stay off when it should not.
2. Did it follow its own steps and skip none.
3. Did it leave the right result on disk: files, records, commits, and issues
   changed the way they should, not merely claimed.
4. Did it obey the safety rules: warned before risk, asked before publishing,
   ran no blocked command.
5. Did it explain plainly, with no code or jargon pushed at the person.
6. Does it do this every time, measured as a rate over several clean runs.
7. Is it better than the last released version, or did a step quietly slip out.

Dimensions 3 and 4 are where the harness is weakest today, because both live in
the world the grader never reads.

### The redesign, staged

The order matters. Each stage is worth shipping on its own, and the early ones
are deterministic and cost nothing per run.

**Stage 1: assert on the world.** Grade the state the run leaves behind, next to
the transcript rather than instead of it.

- Git: read the commit log and whether the bare remote received a push, so the
  save route the contract names (checkpoint, or a pull request) is checked
  rather than assumed.
- Fake-GitHub state: the stand-in already writes every issue and pull-request
  transition to `<project>.gh.json`, which it keeps beside the project so
  the kit's own Git work cannot move it. Read it after the run and assert the issue
  transitions the contract names actually happened.
- Founding records: read `masterplan.md` and `CHANGELOG.md` and assert an
  acceptance was recorded with its date, who accepted, and which named review
  was skipped, for at least scenario 3.

These are string and structure checks over files that already exist. They catch
a kit that said the right words and wrote nothing, which is exactly the failure
the transcript grader is blind to.

**Stage 2: grade the outcome first.** Promote a single whole-session outcome
judgement, sitting on top of the state assertions, to the headline. Keep the
per-field verdicts as diagnostics underneath. A different route to the same
correct end then reads as a pass rather than a drift, which is what the
per-field grading calls it today.

**Stage 3: gate the scripted turns on a precondition, not a position.** Play a
scripted turn only once its precondition holds. The acceptance line for a risk
case fires only after the kit has actually given the notice. When the kit asks
something the script did not anticipate, inject a neutral, truthful filler
answer rather than the next line in the file. This keeps the run deterministic,
removes the interview-order noise, and lets the early-stop guard also flag a
sideways conversation, because a precondition that never becomes true is itself
a signal.

**Stage 4: broaden coverage** to the untested high-value functions above. Each
gets a wired scenario, or a recorded decision that a deterministic check already
covers it. The three `/start` cases move from authored to run and graded first,
since founding is the first thing anyone types and nothing measures it yet.

**Stage 5: a reluctant simulated user, last and narrow.** For the risk cases
only, replace the fixed acceptance lines with a model playing a reluctant
founder: a goal, a fact-sheet it may reveal but not exceed, and a rule not to
accept until the kit has named who is exposed. This is reserved for the handful
of cases whose whole value is resisting a persistent person. The fixed scripts
stay as the cheap tripwire. The guardrails matter because a cooperative
simulator inflates success, and simulator-model variance can swing the result.

### The metric

Report a skill as pass^k: it succeeded on every one of k clean runs. For a
non-coder, "works as planned" means every time, not on average, so consistency
is the product rather than a mean.

Gate a change on the delta against the previous released version. A regression
that drops a step then shows as a fall on that step's assertion, compared like
for like. Treat cross-run instability as a to-do list: a case that swings
between runs is usually pointing at an ambiguous line in a SKILL.md to tighten,
which ties the eval back to the Humanizer and the house style.

Keep only assertions that pass with the current skill and fail without it. An
assertion that passes either way proves nothing about the skill.

## Level 2: is the software sound

Since the person never reads code, a machine has to look at it and report in
plain words. This is a new kit capability, close to a code review but shaped for
someone who will never read the diff. It is best built as an evolution of
`second-opinion`, whose report already splits findings into worth stopping for
and worth knowing.

### The dimensions

1. Security: can an outsider get in, or see or change what they should not.
2. Data safety: is personal data protected and recoverable, and are secrets kept
   out of the code.
3. Soundness and maintainability: can it be changed later without breaking, or is
   it a tangle only this one chat understood.
4. Correctness past the happy path: empty input, two people at once, a service
   down, an action half finished.
5. Cost and scale: will it fall over or run up a bill when more people use it.
6. The front end people touch: is it usable and accessible.
7. The parts it leans on: are its dependencies safe and current.

### How it fits the kit rather than being a generic review

- It reports in plain words, sorted the way `second-opinion` already sorts, and
  its detail lives in the piece's under-the-hood layer.
- It is honest about its limits, like the risk notice. It catches common, known
  weaknesses and says plainly that it will miss things. It never becomes a
  promise the code is perfect. A false sense of security is worse than none.
- It respects the build path. It does not replace a sensitive area's caution;
  it raises the floor for the everyday "build and run it" tool, and a finding
  over its head is what should name an area as sensitive.

Once this exists, Level 1 can measure it: seed a project with a planted
weakness and check the review flags it in plain words.

## The two tiers

The deterministic parts run in CI on every push as a hard gate on a new kit
version. The expensive, non-deterministic parts stay a by-hand check before a
release. This is the same discipline that says a machine check which exists must
run and pass, but only the fast, repeatable, model-free checks block a merge.

- Maintainer CI, on this repo: the state assertions, the waypoint checks, and
  the prior-version delta. It proves two things on every change. Existing
  behaviour is maintained, because a regression that drops a step fails a state
  assertion. New behaviour a change claims is actually present, because its
  assertion is added and passes. So the kit cannot ship a version that quietly
  loses a behaviour or claims one it did not build.
- The LLM-judge tier stays off CI. A full replay pass is real money and hours of
  wall-clock, and the judge is biased and noisy. A maintainer runs it before a
  release and reads the rate, the way `checks.yml` already records for replay.
- User-project CI, in a project built with the kit: the Level 2 review can run
  here beside the person's own project check, so the software is reviewed on
  every change without the person reading code.

## The cut: pieces this epic should spawn

The epic should be cut down after this design is agreed, not built in one go.
The natural pieces, roughly in dependency order:

1. State and checkpoint assertions for the replay harness (Stage 1). Deterministic,
   highest value, unblocks the CI gate. Starts with scenario 3's acceptance record.
2. Run and grade the three founding cases (Stage 4). The cases exist; this
   proves them and records the rate.
3. The adoption fixture: a project the kit did not write, with one
   thing wrong the fit check should notice, plus a founding scenario against it.
4. Outcome-first grading and precondition-gated turns (Stages 2 and 3).
5. The end-to-end tier that carries a build to a shipped, running app across
   shapes, which travels with `.agents/tests/` when the repositories merge.
6. The Level 2 code-health review capability, as an evolution of `second-opinion`.
7. The deterministic CI gate that wires the above into a push check on this repo.

The `/fix` acceptance being earned too late is a standalone bug the redesigned
harness re-measures, not a piece of this epic. The state assertions in
piece 1 would give it a sharper check than the transcript grader has today.

## Decisions that still need a person

- How much of the external research (tau-bench, LangSmith simulation, the
  LLM-judge bias literature the issue lists) to fold in before building. This
  draft leans on the groundwork already in the issue and on a read of the
  harness. A deeper research pass is a real cost and may not change the first
  pieces.
- Where the Level 2 review runs first: as a by-hand release check on this repo,
  or wired into a user project's CI from the start.
- Whether the reluctant simulated user (Stage 5) is in scope for the first cut
  or deferred until the deterministic stages are proven.
- Where this document should live long term. It sits in `docs/design/` for now;
  when the repositories merge it would move with the rest of the maintainer
  material.
