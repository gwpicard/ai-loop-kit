## So that

A person can start a run of the loop kit, walk away, and come back to finished work and a short list of decisions to review. Today they come back to a run that stopped hours earlier and waited for them.

## Why this matters

This is the loop kit's central promise. The v1 build is being made the way the loop kit is meant to work. A coordinator session orders the work, and fresh agents check, build and review each piece. A second session, the person's chat assistant, answers their questions and watches the coordinator. On the first night that setup ran with nobody watching, it stood still for about four hours on a question an agent could have answered. Every cause below will happen to a person using the kit unless the kit is designed against it.

## How the v1 build runs

- The coordinator is a Claude Code session in its own terminal. It reads a written brief and keeps its place in a state file, so a new session can pick up where a dead one stopped.
- For each slice it starts fresh agents: a readiness checker, then a builder, then a reviewer. Each one reads its own brief from disk when it starts.
- Merges are pre-approved when every check passes and the review finds nothing worth stopping for.
- A live dashboard shows each slice, each step and anything waiting for the person.
- The chat assistant runs in a separate session. Overnight it ran a watchdog every 20 minutes. The watchdog did nothing while the coordinator was working, sent the resume line when the coordinator was idle, started a new coordinator if the old one had died, and left a deliberate wait alone.

## What happened on the night of 4 to 5 October 2026

All times are CEST.

- 01:00 to 01:15: before going to sleep, the person asked what could stop the run. The assistant named readiness questions as the likeliest stop. The person agreed a rule that the run takes the checker's best guess for those questions, records it and flags it for review. The assistant also set up the watchdog and said it was safe to sleep.
- Until about 03:30 the run went well. Slice 3's two parts and slice 4's first two parts were merged.
- About 03:30: while slice 4's third part was being built, the builder found that one of the slice's own "Done when" lines needed amending. The slice gave nowhere to record a kept branch when a piece had no kickback. The coordinator asked the person to approve the change and to allow the issue edit, and it stopped.
- 03:32 to 07:32: the watchdog saw the stop 13 times. Each time it decided the stop was outside the agreed rule, because the question came from a build and not from a readiness check, so it did nothing.
- About 07:40: the person woke, answered, and the run carried on.

## Why it stopped

1. **Stop rules were a list of exceptions, and the list was incomplete.** The coordinator's brief said that a check which cannot pass as written "is a finding for the maintainer". The builder's brief said that a wrong Done when line means "stop and report it". The overnight rule exempted only readiness questions. The question that stopped the run was the same kind of question: what should this slice say? It came from a different step, so no rule covered it.
2. **The assistant promised more than the rule delivered.** It said it was safe to sleep when only one kind of stop was covered, and it did not name the build-time case when asked what else could block the run.
3. **The watchdog obeyed the letter of its rule.** It checked 13 times and logged each check, but it had no general test to apply, such as "could an agent answer this safely?". It also had no way to wake the person.
4. **There was no safe way to reach the running coordinator.** The only way in was typing into its terminal. Nobody can read that input box from outside, and it once held an unsent line nobody had typed on purpose. So a rule changed mid-run reached only the agents that read their brief fresh. The coordinator itself kept the old rule until it restarted.
5. **Changing the rule mid-run was refused.** The next morning the person asked the assistant to widen the rule to every question about what a slice should say. Claude Code's automatic safety check refused the edit to the coordinator's, builder's and reviewer's briefs. It called the edit instruction poisoning: one agent rewriting another agent's instructions so that it stops less often. The check was right to be wary. A policy like this should be set by the person before the run, not edited by an agent during it.
6. **Nothing else could go ahead while it waited.** Slices 1 to 9 are a strict chain, so a stop on one slice stopped everything. The rule that lets a run skip ahead covers only steps that need real accounts.
7. **The watchdog was fragile.** It was a scheduled job inside the chat session, so it would have ended if that session closed, and it expires after seven days. It also needed the computer to stay awake with its lid open. Earlier in the build the computer crashed twice from memory pressure with too many agents at once.

## What "walk away" has to mean

The person sets the run's limits once, before leaving. After that the run stops only for something that truly needs them: real accounts, money, a repository or account setting, going public, a release, or a change that cannot be undone. Anything else is decided by the run, written down and flagged. When the run does stop, it tells the person straight away. It also carries on with any work that does not depend on the stopped piece.

## Proposed changes to the loop kit

1. **One rule for deciding alone, instead of a list of exceptions.** A run may answer a question itself when the answer can be undone, keeps every settled decision, and is recorded and flagged. This holds wherever the question comes from: shaping, a readiness check, a build or a review. Briefs and skills should send each "ask the person" through this one rule rather than stopping.
2. **A decisions record and a morning review.** Every decision the run made alone goes on the piece under `## Decided`, marked for review, and also into one list the person reads on their return. Undoing one is a single command.
3. **The autonomy policy is set by the person before the run.** It lives in the project's settings, which the person approves once. Agents read it and never edit it. This keeps the safety check's concern intact: no agent loosens another agent's limits.
4. **A mailbox the coordinator reads at every step.** The person, the chat assistant or the watchdog can leave an instruction in a file, and the coordinator reads it at its next step. Nobody has to type into a terminal they cannot see.
5. **A watchdog that ships with the kit and runs on its own.** The coordinator writes a heartbeat at every step. A scheduled job on the computer, independent of any chat session, reads the heartbeat's age and restarts or resumes the coordinator. It sends the person a notification when it gives up, or when the run has waited for them longer than a set time.
6. **A real stop notifies the person and does not freeze the run.** The run sends a notification, then takes any piece that does not depend on the stopped one.
7. **A check before the person walks away.** One command reports whether the computer will stay awake, is on mains power, and has enough free memory and disk for the planned number of agents. It also lists the stops the run can foresee.
8. **Logs a person can investigate.** Keep what the v1 build added: a log of each step, a watchdog log with every check and action, a log of the assistant's changes with backups and how to undo each one, and the dashboard's events. Write a short report when the run ends.

## Evidence

These records are on the maintainer's computer, in the build's working folder, which git ignores: the watchdog log of all 21 checks overnight, the chat assistant's change log, the run state, the settled decisions with the overnight rule as decision 50, and the coordinator's brief. The safety check's refusal was "Permission for this action was denied by the Claude Code auto mode classifier. Reason: [Instruction Poisoning]."

## Open questions

- Should the decide-alone rule be one rule for every project, or a setting with a safe default?
- Where should the watchdog live on each coding agent the kit supports: a system scheduler, a hook, or a small background process?
- Which slice of the v1 epic should take this on? The unattended run, the controller and the boards slices all touch it.
