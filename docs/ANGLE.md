# What AI Loop Kit is for

AI Loop Kit is a small set of Claude Code skills that build software in a
loop you can trust. Read this file first. It is the reason for every other
file.

## The angle

An agent cannot say a piece of work is done. It can only prove it.

- **Shaping is the work, and the build is a loop.** Most of the effort goes
  into a clear spec before anything is built. A clear spec can then be built
  with nobody steering.
- **Every piece is a GitHub issue in exactly one state.** Only the gate moves
  it. The gate is a plain script, not an agent.
- **The gate checks, it does not trust.** It runs the judge itself. It never
  takes an agent's word that the tests pass.
- **The bar is fixed before the build starts.** The judge is written during
  shaping. It must fail on today's `main`, for a reason that names a spec ID.
  The gate then records a hash of it. A builder that changes the bar fails.
- **Deterministic checks over instructions.** A rule that matters is held by
  code, not only by a sentence in a prompt. Where it can, it is held in two
  independent places.
- **The person merges.** Nothing reaches `main` without the person's yes.

## How the loop runs

1. `/ai-loop-kit:shape` turns an idea into a piece. It asks the questions,
   writes the spec with numbered "Done when" items, and writes the judge.
2. The gate moves the piece to ready only when the judge exists, fails on
   `main` for the right reason, and has its hash recorded.
3. `/ai-loop-kit:run` builds each ready piece. Every attempt is a fresh
   `claude -p` session. The gate runs the judge after each attempt. After
   three failed attempts the piece goes back to shaping with the reason.
4. When the judge passes and the bar is unchanged, the run opens a pull
   request. The person reads it and merges.

## How the kit grows: features earn their keep

The first version of this kit was designed in full before it ran once. It
reached 35,000 lines and never built a piece. This version grows the other
way.

- The kit starts as the thinnest loop that works from idea to `main`.
- A new rule or feature enters only when a real run shows it is needed. The
  run's failure is written down in `docs/LEDGER.md` first.
- It arrives with a test that reproduces that failure.
- Every idea from the first design is kept in the ledger with the trigger
  that would earn it a place. Nothing is lost. It waits until it is needed.

This is the kit's own rule applied to the kit. A feature is a piece. Its
judge is the failure it fixes.

## What the kit is not

- It is not a builder. Claude Code builds. The kit decides what is ready,
  checks what is done and keeps the record.
- It is not yet safe to leave alone overnight. That is a later step, and it
  will be earned the same way.

## Where to read next

- `docs/LEDGER.md`: every idea from the first design, and what would earn it.
- `docs/LESSONS.md`: what the first build taught us about Claude Code, GitHub
  and our own process.
- `docs/archive/v1-design/`: the first design, kept as reasoning.
