"""The run loop: the plain script that builds the pieces the person picked.

`kit/scripts/run.py` is the command line. The modules here hold the parts:

- `plan.py`: the order of the pieces, the slots, and which pieces may start now;
- `attempts.py`: where each outcome of an attempt goes (move 5, 6, 7, or stay);
- `record.py`: the run record, the lock file, the heartbeat and the spend;
- `summary.py`: the morning summary, with every decision made alone;
- `gateway.py`: the calls to `gate.py` and `trim-check.py`;
- `engine.py`: the loop that ties them together;
- `integrate.py`: the integration loop, which joins each built piece to the combined branch as
  a trial, and runs the final combined check (it answers the `start`, `piece-built` and
  `built-all` events);
- `docs_commit.py`: the docs commit that comes before the final check;
- `review.py`: the review loop. After the final check is green, a fresh reviewer reads the
  specs and the combined diff, and each finding becomes a failing check (move 8), a shaping
  issue (move 9) or a worth-knowing note (it answers `built-all` and `run-end`, and asks for
  another `built-all` through the context's `another_round` when it changed the branch).

Later pieces add modules and never edit `run.py`. The engine looks for each of these modules
by name, and calls `run_hook(context, event, **data)` in the ones that exist:

- `watch.py`, `inbox.py`, `integrate.py`, `review.py` and `pull_request.py`.

The events are `start`, `tick`, `session-ended`, `piece-built`, `built-all` and `run-end`.
`context` is the engine's `HookContext`: the paths, the run name, the run record and the
policy, the lock every call to the gate goes through, `restart_piece` (build a built piece
again) and `infos` (the areas and blockers of each piece). A hook that restarts a piece at
`built-all` gets another round: the piece is built, and `built-all` is called again.

A hook may read the context and write notes and decisions into the record. A hook that raises
is recorded as a problem, and the run then ends with a failure. It is never ignored.
"""
