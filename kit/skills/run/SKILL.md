---
name: run
description: Starts a run that builds the ready pieces, after the pre-run check passes. The person types it. It asks which pieces to run and whether the merge is pre-approved for this run only.
disable-model-invocation: true
---
# Run

This skill starts a run from a conversation. It shows the gate's report, asks the two questions once, runs the pre-run check, and starts the run script. The skill only starts the run script. The script builds, judges and moves the pieces.

Every command below uses `"${CLAUDE_PLUGIN_ROOT}"`, the folder of the installed kit, in double quotes so a folder with a space works. Start each command under `caffeinate -i`. The pre-run check refuses a computer that may sleep.

## Now
!`python3 kit/scripts/gate.py report --json --brief`
If the line above shows a disabled marker or an error, run that command by hand first.

## Stops
- Stop when no piece is ready. Say so in one line, give the `next:` line that points at `/shape`, and start nothing. Held by: `kit/scripts/run.py` exits 3 with "nothing to run" and writes no run record.
- Stop when the pre-run check refuses. Show each refusal in plain words. Name the guard and the half of `/setup` that is missing, give the `next:` line as it is, and start nothing. Held by: `kit/scripts/pre-run-check.py` exits 3, and `kit/scripts/run.py` runs it again before it starts a builder.
- Stop when the person asks for a run that nobody watches, or a pre-approved merge, and the GitHub App is missing. Say that the second half of `/setup` makes the App, and offer an attended run. Held by: `kit/scripts/pre-run-check.py` refuses `--unattended` and `--merge-pre-approved` without the App key.
- Never write an answer to the policy file or to any other file. Pre-approval covers this run only. Held by: `kit/scripts/loop/policy.py` has no pre-approval key and refuses one, and `kit/scripts/run.py` takes it only as `--merge-pre-approved`.
- Never build a piece, edit a source file or move a piece yourself. Held by: `kit/scripts/gate.py` is the only code that moves a piece, and `kit/hooks/guard.py` refuses a direct label edit.
- Never start the run script by another route after a refusal, and never skip or weaken a guard to get a run. Held by: `kit/templates/blocked-commands.md` and `kit/hooks/guard.py`.

## Steps
1. Read the report above. List the ready pieces by number and title, in a few lines.
   Done when: you can name each ready piece, or you have said there is none and stopped.
2. Ask the two questions once, in one message. Give a recommended answer for each. First: which pieces to run, with every ready piece as the default. Second: is the merge pre-approved for this run only, with "not pre-approved" as the default.
   Pass the first answer as `--pieces` and the second as `--merge-pre-approved`.
   Done when: the person has answered both, or has said "you choose". A silent answer means not pre-approved.
3. Run the pre-run check before you start the run script, with the same flags the run will use:
   `caffeinate -i python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pre-run-check.py" --pieces 1,2`
   Add `--merge-pre-approved` only when the person said yes. Add `--unattended` only when the person said nobody will watch the run.
   Done when: it exits 0, or you have shown each refusal and stopped.
4. Say what the run will do, in a few lines: the pieces, "not pre-approved" or "merge pre-approved for this run", and any notice from the check. Ask for a last yes.
   Done when: the person said yes.
5. Start the run script with the same pieces and flags:
   `caffeinate -i python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run.py" --pieces 1,2`
   Done when: it prints the run name, or you have shown its refusal and stopped.
6. Tell the person the run name, how to see where it stands (`/what-now`), and that a stop signal sends each building piece back to ready.
   Done when: the person has the run name and the command to read the status.

## Gotchas
- A run is long. Start it so that this session stays free, and read the run record when the person asks.
- An attended run with no App is allowed. GitHub steps wait for the person, and the check says so in a notice. Pass the notice on.
- A refusal from the run script after a pass from the check is real. The machine may have changed. Show it and stop.
- The run parks a piece that needs the person. Leave the answer to the person.

## When to read more
- Read the run's summary file when the person asks what a finished run did. The run script prints its path.
