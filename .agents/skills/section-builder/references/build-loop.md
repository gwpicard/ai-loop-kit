# The build loop

A piece labelled `loop:build` is built in a loop that stops by itself and says
why it stopped. Load it for a piece labelled `loop:build`, in place of steps 4
and 5. Steps 6 to 9 follow as for any other piece, once the loop has ended in
`done`. The scripts hold what a machine can judge: the run script, the
`implement` skill's `scripts/run.py`, counts the attempts and keeps failed
work, and the gate takes the route for each ending. This file says what the
person running the loop and each builder do around them.

## Before the first attempt

Show the acceptance checks failing. On a piece that names an `Acceptance
branch:`, run each check through the gate at the spec commit, `python3
.agents/tools/gate.py evidence <number> --phase before -- <command>`, and see it
fail on its assertion. A piece with no acceptance branch writes its checks
first, as step 4 says, and they count as its acceptance checks from the commit
that holds them. A check that already passes is reported, as step 4 says, and
never built round.

## The run script and the fresh builder

Every attempt is a fresh builder, started with the bounded brief the
`section-builder` skill's `references/task-handoff.md` describes, carrying the
previous attempt's note and nothing of its conversation. The run script never
starts a model session itself. Run it from the project's folder:

1. `python3 <implement skill>/scripts/run.py start <number>` makes the claim
   through the gate in a run of one, named `solo-<number>-<date>-<time>`, or
   adds the piece to a run given with `--run <run name>`. On a piece already
   building in a run, it resumes that run with no new claim.
2. `python3 <implement skill>/scripts/run.py next <number> --run <run name>`
   writes a start request into the run record, `.agents/runs/<run name>/run.json`
   in the main folder. The request names the piece, the attempt number, the
   worktree, the brief and the result file, and the script prints it on a line
   that starts with `request:`.
3. The session that ran the script starts the builder with its own subagent
   tool, on the route the `section-builder` skill's
   `references/task-context-capabilities.md` names for this coding agent: on
   Claude Code, a subagent that does not fork the conversation. It gives the
   builder the brief and nothing else, then writes the subagent's id back into
   the request with `run.py started <number> --run <run name> --agent <id>`.
4. When the builder ends, `run.py ended <number> --run <run name>` reads the
   result file and hands it to `python3 .agents/tools/gate.py result <number>
   <result file>`, which takes the route below. Where another attempt follows,
   the script prints its start request, and step 3 comes again.

The project's settings and deny rules stay in force for every builder, and
nothing in the loop skips them. Where the coding agent cannot start a fresh
builder, the run stops at a point it can resume from, as the task handoff
says, and tells the person to open a new session and type `/implement`.

## One attempt

The builder reads its brief and the note of the attempt before it, then builds
until every acceptance check passes, running each check through the gate,
`python3 .agents/tools/gate.py evidence <number> -- <command>`. It commits its
work on the piece's branch. A builder never claims, pushes, reviews, opens a
pull request or merges: the session that ran the script does those.

Within the limits the builder researches and repairs by itself. It may read
the code, the history and the project's documents, and try what they suggest.
A finding that would change a `Done when` line, a `Decided` line or the
boundary ends the attempt as `needs_context`, rather than being acted on. The
contract is the person's, and it changes only in `/shape`.

The builder ends each attempt with exactly one status, written as JSON to
`.agents/runs/<run name>/results/<number>-attempt-<n>.json` in the main
folder. That is outside `.agents/pieces/`, which the deny rules guard, and
outside the worktree, so nothing it writes there is saved with the code:

```json
{
  "handoff": "solo-12-20261005-101500-12-attempt-1",
  "status": "needs_context",
  "concerns": [],
  "needs": [{"kind": "clarify", "what": "Should a refund over the limit need a second person?"}],
  "could_not_check": ["The receipt layout, which needs the person's eyes."]
}
```

The status is one of `done`, `done_with_concerns`, `needs_context`, `blocked`
or `environment_failed`. Each entry under `needs` has a `kind` of `clarify`
for a decision, `research` for a fact or `spec` for a contract that needs
rewriting, and says what is needed. An entry of kind `spec` about a check that
cannot be met as written names that check under `check`. A `loop:fix` piece
also lists its `causes`, each with the cause, its prediction and its outcome:
`ruled out`, `confirmed` or `not tested`.

## Where each status goes

| Status | Route the gate takes |
|---|---|
| `done` | Checking: the gate runs the piece's checks itself on the commit the builder left. Where they hold, the piece goes on to step 7's review. Where one does not, the attempt failed |
| `done_with_concerns` | The same, and the concerns are written as a reason that forces the person's review |
| `needs_context` | A kickback to the sub-state the builder named, with a `## Kickback` section and the branch pushed and kept |
| `blocked` | The same as `needs_context` |
| `environment_failed` | Tried once more as a fresh attempt. A second one stops the piece in `state:building` and the run pauses. Never a kickback |

A failed attempt is a `done` whose checks fail when the gate runs them, or no
result once the builder is known to have ended. A builder that may still be
running has not failed. `needs_context` and `blocked` are kickbacks, and
`environment_failed` does not count.

## Attempts and limits

The loop stops at whichever comes first of three attempts and a piece budget
of 120 minutes, from `.agents/loop-settings.json`. The person may change
either there. The budget is time alone: the minutes since the piece's first
attempt started. Usage is not counted, and the brief says so. Where the file
is missing, the defaults apply and the script says so once.

After a failed attempt, the script writes its note from the evidence record
and Git, with the implement skill's `scripts/attempt-note.py`. It then keeps
the failed attempt's work with `recovery.py preserve`, under
`.agents/recovery/<run name>-<number>/`, one copy for each attempt. Installed
folders such as `node_modules/` are left out and named, and an env file is
named and never copied. It puts unsaved work away with
`git stash push --include-untracked`, then adds one commit that reverts what
the attempt committed, so the branch keeps every attempt's history and the
next attempt starts from the start commit's content. It never runs
`git reset --hard`, `git checkout .`, `git restore .` or a force push, and it
never deletes what it kept.

At the limit the gate kicks the piece back to `shaping:research`, or to
`shaping:spec` when the last result names, under `needs`, one of the piece's
acceptance checks as one that cannot be met as written. A clear bar the
attempts could not meet is a missing fact, so research is the default. The
Kickback section lists each attempt by number, status, the failing checks with
their exit codes, and where its note is on this computer. No check output goes
to GitHub. It names the folder that keeps the failed work, with the command
that deletes it.

## Switching module

A build may find it is really a repair, or the other way round. The builder
switches only through `gate.py switch-module <number> <module>`, and the gate
allows it only when the contract already holds the new module's bar: a
reproduction for `fix`, acceptance checks for `build`. The gate changes the
`loop:` label and writes the switch into the evidence record, and leaves the
contract as it is. Anything else needs a decision, so the builder ends the
attempt as `needs_context`.

## The Stop hook

On Claude Code, the project's settings run `gate.py stop-check` when a builder
stops. Where its result says `done` and an acceptance check fails, it sends
the builder back once, naming the check. A second stop in the same attempt is
let through, and the gate's own run of the checks then counts the attempt as
failed.

## A sensitive area

The build never asks for an acceptance and never writes an `Accepted:` line.
A person accepts a risk in `/shape`'s clarify step, where they are present. A
piece whose reach touches a sensitive area with no recorded acceptance is
refused its claim by the gate. One found to touch such an area during the
build ends the attempt as `needs_context`, naming `clarify` and the area.
