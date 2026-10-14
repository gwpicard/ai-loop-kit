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

Version 0.10.0 is the thin kit. It grows only when a real run shows that a
feature is needed. Use it with you nearby.

## Install

In Claude Code, add the GitHub marketplace and install the plugin:

```text
/plugin marketplace add gwpicard/ai-loop-kit
/plugin install ai-loop-kit@ai-loop-kit
/ai-loop-kit:setup
```

## First 15 minutes

You need `git`, `gh` signed in, Python 3.9 or later, and a GitHub repository
with a first commit on `main`.

1. In Claude Code in your project, run `/ai-loop-kit:setup`.
2. Shape a piece with `/ai-loop-kit:shape`.
3. Build ready pieces with `/ai-loop-kit:run`.
4. Review the pull request on GitHub and merge it.
5. Sync the merged piece with `python3 "<KIT>/scripts/gate.py" sync`, using
   the kit's installed path for `<KIT>`.

## Limits

Runs need your attention. There is no sandbox. Docker has not been tested.
The kit is for one person; teams have not been tested. A weak judge can let a
weak build pass, so review the spec and the pull request yourself.

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
