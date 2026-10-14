# AI Loop Kit

A small set of Claude Code skills that build software in a loop you can
trust. An agent cannot say a piece of work is done. It can only prove it.

- `/ai-loop-kit:shape` turns an idea into a piece: a GitHub issue with
  numbered "Done when" items and a judge test written before any code.
- The gate (`kit/scripts/gate.py`) is the only thing that moves a piece. It
  refuses "ready" unless the judge fails on today's `main` for the right
  reason, and it fixes the judge with a hash.
- `/ai-loop-kit:run` builds each ready piece in fresh `claude -p` sessions,
  up to three attempts. The gate runs the judge itself. A pass opens a pull
  request. You merge.

Read [docs/ANGLE.md](docs/ANGLE.md) for why it works this way.

## Status

Version 0.2 is a restart. The first version reached 35,000 lines without
building a piece, so this one starts as the thinnest loop that works and grows
only when a real run proves a feature is needed. Use it on a scratch project,
with you nearby. It is not yet safe to leave alone.

## Try it

From a clone of this repository, in Claude Code inside your project:

```text
/plugin marketplace add /path/to/ai-loop-kit
/plugin install ai-loop-kit@ai-loop-kit
/ai-loop-kit:setup
```

You need `git`, `gh` (signed in), Python 3.9 or later, and a GitHub
repository with a first commit on `main`.

## Where things live

- `kit/`: the plugin. Skills, the gate, the run, the guard, the builder brief.
- `tests/`: the checks. `tests/run-all.sh` runs them in seconds.
- `docs/ANGLE.md`: what the kit is for.
- `docs/LEDGER.md`: every idea from the first design, and what would earn it
  a place.
- `docs/LESSONS.md`: what the first build taught us.
- `legacy/` and `docs/archive/`: the first kit and its design, kept as a
  parts bin and as reasoning.

The kit is licensed under [MIT](LICENSE).
