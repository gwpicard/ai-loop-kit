# AI Loop Kit

A small set of Claude Code skills that build software in a checked loop. An
agent cannot say a piece of work is done. The gate runs the checks itself.

- `/ai-loop-kit:shape` turns an idea into a contract: intent, scope,
  approach, numbered items and a judge written before any code.
- The gate (`kit/scripts/gate.py`) is the only thing that moves a piece. It
  refuses "ready" unless the judge fails on today's `main` for the right
  reason, and it fixes the judge with a hash.
- `/ai-loop-kit:run` builds each ready piece in fresh `claude -p` sessions,
  up to three attempts. The gate runs the judge itself. A pass opens a pull
  request. You merge.

Read [docs/V1.md](docs/V1.md) for the v1 definition and how the kit works.
Read [docs/ANGLE.md](docs/ANGLE.md) for why it works this way.

## Status

Version 1.0.0 is the current release target. After v1, a new feature must
answer a failure seen in a real run. Use the kit with you nearby.

## Install

In Claude Code, add the GitHub marketplace and install the plugin:

```text
/plugin marketplace add gwpicard/ai-loop-kit
/plugin install ai-loop-kit@ai-loop-kit
/ai-loop-kit:setup
```

## First 15 minutes

You need `git`, `gh` signed in, Python 3.9 or later, and a GitHub repository
with a first commit on `main`. Setup agrees the Test and optional Quality
commands, protected paths, and whether to enable branch protection.

1. In Claude Code in your project, run `/ai-loop-kit:setup`.
2. Shape a piece with `/ai-loop-kit:shape`.
3. Build ready pieces with `/ai-loop-kit:run`.
4. Review the pull request on GitHub and merge it.
5. After you merge, run `gate.py sync` to move merged pieces to done.
6. Use `gate.py report` to see why pieces came back, or `gate.py stop` to
   stop a live run after its current attempt.

## Limits

Runs need your attention. The guard is not a sandbox. Docker and team use
have not been tested. A weak judge can let a weak build pass, so review the
contract and the pull request yourself.

## Where things live

- `kit/`: the plugin. Skills, the gate, the run, the guard, the builder brief.
- `tests/`: the checks. `tests/run-all.sh` takes about two to four minutes.
- `docs/ANGLE.md`: what the kit is for.
- `docs/LEDGER.md`: every idea from the first design, and what would earn it
  a place.
- `docs/LESSONS.md`: what the first build taught us.
- `docs/v1/`: the v1 findings, results and build notes; earlier plan files
  remain in git history.
- `legacy/` and `docs/archive/`: the first kit and its design, kept as a
  parts bin and as reasoning.

The kit is licensed under [MIT](LICENSE).
