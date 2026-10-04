# Slice 19: A project worked on in Codex is held by the same gates, rules and run controller as one worked on in Claude Code

Labels (today's set): enhancement, area:skills, ready-able once shaped. Release label for the PR: release-minor.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 2: Label model and gate script; slice 6: Frozen-bar enforcement; slice 9: Run controller; slice 10: Crews and computer resources; slice 15: Safety boundary for runs.

## So that
A person whose team uses Codex gets the same machine-held rules as on Claude Code: states changed only by the gate script, the frozen bar, fresh evidence before review, the refused commands, and runs that start every crew member through the run controller.

## Done when

### Part a: the same scripts as Codex hooks

#### Works
- Founding writes Codex's project hook configuration, in the file and format the Codex documentation names on the day of the build, wiring three events to the same scripts Claude Code's hooks call: session start to `.agents/hooks/session-start.sh`, the check before a shell command to slice 2's state guard, `.agents/hooks/state-guard.sh`, and the end of a turn to slice 6's `gate.py stop-check`. Check: new `.agents/tests/codex-parity.sh` founds a throwaway project and reads each event's command from the written file.
- A small adapter, `setup-ai-build-kit/scripts/codex-hook.sh`, turns each Codex hook payload into the input the shared script reads and turns its verdict back into Codex's reply. The gate logic is never copied. Check: `.agents/tests/codex-parity.sh` feeds recorded Codex payloads and the matching Claude payloads for ten cases (a state label edited directly, a frozen-bar edit, a turn ending with no fresh evidence, an allowed command, and six more from the gate rehearsal) and requires the same verdict for each pair.
- `session-start.sh` gains a `--codex-hook` mode giving the same one line in Codex's reply shape. Check: `.agents/tests/session-start.sh`, extended: the three modes print the same sentence for the same project state.

#### When it is not the normal case
- The installed Codex does not offer one of the three events: founding writes the others, records `Codex hooks: <events missing>` in the capability profile, and says in one line which rule is then held only by the run controller and the written instruction. Check: `.agents/tests/check-tooling.sh` with a stand-in `codex` reporting an older version.
- A Codex project is not trusted, so Codex ignores its project configuration: founding says so in one line and names Codex's own step to trust the folder. It never edits the person's own Codex configuration without a yes naming the file. Check: `.agents/tests/codex-parity.sh`; `.agents/tests/own-computer-work.sh` still passes.

### Part b: the refused commands as Codex rules, and the fence

#### Works
- Founding writes `.codex/rules/ai-loop-kit.rules` with a forbidden rule for each entry in `blocked-commands.md` that Codex's command-prefix rules can express. Check: `validate-kit.sh` compares the template rules with the written list, as it does for the Claude deny list.
- `blocked-commands.md` (both copies) has a section "On Codex" listing the spellings Codex's rules refuse and the ones they miss, such as a push that names `main` after an option. Check: new matcher `.agents/tests/lib/codex-rule-matcher.py`, tested first against the examples in Codex's own rules documentation, then fed every listed spelling by `.agents/tests/codex-parity.sh`; each rule removed in turn makes the check fail.
- Founding writes a Codex permission profile for runs with filesystem sandboxing on and network allowed only to the recipe's `Network allowlist:` hosts where the installed Codex supports host entries. Check: `.agents/tests/codex-parity.sh` reads the written profile for each recipe.

#### When it is not the normal case
- The installed Codex supports network only as on or off: the profile turns it on, the capability profile records `Sandbox: on, no network allowlist`, and slice 15's rule keeps automatic merge off. Check: `.agents/tests/codex-parity.sh` and `.agents/tests/check-tooling.sh`.

### Part c: runs and crews on Codex

#### Works
- The run controller starts each crew member on Codex as a fresh `codex exec` session given only its declared inputs, the same inputs slice 10 gives a Claude member, and reads back the fixed verdict format. Check: `.agents/tests/replay-provider.sh`-style stand-in for `codex` in new cases of `.agents/tests/codex-parity.sh`: a builder, a critic and a checker each receive only their inputs, and a critic never receives the builder's transcript.
- The suggested builder count on Codex never exceeds Codex's own cap on subagents, read from its documentation and recorded in `docs/SOURCES.md`. Check: `.agents/tests/codex-parity.sh` with stand-in memory and cores that would suggest more.
- Pushes on Codex go through `gate.py push` with the scoped token, as on Claude Code. Check: `.agents/tests/run-safety.sh` from slice 15, run with the Codex rules in place.

#### When it is not the normal case
- `codex exec` is missing or signed out: the run does not start, and the opening line names the missing tool. Check: `.agents/tests/codex-parity.sh`.

### The documents this change touches
- `docs/COMPATIBILITY.md`: "Known limits of Codex" rewritten (deny rules and session-start now set up; what each missing hook event costs), and the fallback table's rows for safety, check-up and long runs. Codex stays "Expected to work". Check: `.agents/tests/compatibility-grades.sh` (no grade raised without a recorded run); `.agents/tests/codex-parity.sh` (rule-shape on the new limits).
- `README.md`: the "Works with" row keeps Codex's grade and says the same gates hold. Check: `.agents/tests/compatibility-grades.sh`.
- `WORKFLOW.md`: the Codex lines in sections 1 and 4 say what founding writes for Codex. Check: `.agents/tests/codex-parity.sh` (rule-shape).
- `setup-ai-build-kit/references/codex-github.md`: the network section points at the run profile and keeps its rule against combining Codex's two permission systems. Check: `.agents/tests/codex-github-auth.sh` still passes; `.agents/tests/codex-parity.sh`.
- `setup-ai-build-kit/SKILL.md` and `references/capability-check.md`: founding writes the Codex files and the `Codex hooks:` line. Check: `.agents/tests/codex-parity.sh`, `.agents/tests/check-tooling.sh`.
- `docs/SOURCES.md` credits the Codex hook, rules and permission documentation it was built from, with dates. Check: `validate-kit.sh`.

## Masterplan change
Design note: "Platforms", and the "Codex" lines of "What a machine enforces". The note needs no change.

## Not in this piece
- A recorded Codex run, which is what moves Codex to Tested: slice 20: Replay harness rewrite and real runs.
- Gates on Cursor, Gemini CLI and GitHub Copilot, which keep the shaping core and one piece at a time: not in v1.
- Codex command files: the kit still ships none; Codex finds the skills in `.agents/skills/`.
- Boards and notifications, which already work on any agent with a shell: slice 16: Boards and notifications.

## Decided
- Codex runs the same scripts through an adapter, never a second copy of the gate logic. Reason: decision 23 and the design note's "Platforms".
- Codex keeps "Expected to work" until a recorded run. Reason: the design note's "Platforms" and the grading rules in `docs/COMPATIBILITY.md`.
- The hook and rule formats are taken from Codex's documentation on the day of the build and credited with that date. Reason: Codex's configuration changes between releases, and a format written from memory cannot be told from a current one.
- A missing hook event is said once and recorded, and the rule falls back to the run controller and the instruction. Reason: the kit's habit of saying what it cannot check rather than stopping.
- The founded project's `.codex/` holds configuration and rules only, never skills. Reason: the validator's existing rule that no `.codex/skills` tree exists, and one copy of each skill.

## Data
- New founded files: Codex's project hook configuration, `.codex/rules/ai-loop-kit.rules` and the run permission profile. Founding writes them; nobody else writes them. No project founded with AI Build Kit receives them (decision 63).
- The capability profile gains `Codex hooks:`.
- No record format changes.

## Leaves the tool
Nothing new leaves the tool, because the hooks, rules and profile are local files and the crew members talk only to the model service the person already uses.

## Must still hold
- The Claude deny list mirrors the written list: `validate-kit.sh`.
- The written gaps and the rules agree: `.agents/tests/push-to-main-rules.sh`, and the new Codex half in `codex-parity.sh`.
- The session-start hook never reminds this repository: `.agents/tests/session-start.sh`.
- The Codex launcher passes a login only to its own process: `.agents/tests/codex-github-auth.sh`.
- The replay providers still drive Claude Code and Codex: `.agents/tests/replay-provider.sh`.
- Grades move only on recorded runs: `.agents/tests/compatibility-grades.sh`.
- Work outside the project folder waits for a yes: `.agents/tests/own-computer-work.sh`.
- No issue numbers in tracked files: `validate-kit.sh`.

## Relies on
- The gate script and its command check: slice 2.
- The evidence check at the end of a turn: slice 6.
- The run controller: slice 9.
- Crew inputs and the computer's suggested count: slice 10.
- The fence, the scoped token and `run-safety.sh`: slice 15.
- On main today: `session-start.sh`, `codex-github.md`, `codex-with-github.py`, `check-tooling.sh`, `.agents/tests/lib/permission-matcher.py` as the pattern for the new matcher, `.agents/tests/replay/provider.sh`'s Codex route.

## Reach and risk
Boundary: setup-ai-build-kit (founding, capability check, blocked commands, Codex reference and templates), the session-start script, the run controller's member starter, COMPATIBILITY.md, README.md, WORKFLOW.md, SOURCES.md.
Reaches: founding on every layout (`starter-rehearsal.sh`, `plan-helper-routes.sh`, `agent-plugin.sh`); the Claude hooks the adapter shares scripts with (slice 2's and slice 6's rehearsals, `session-start.sh`); the replay providers (`replay-provider.sh`).
If it breaks: on Codex a gate does not fire and the run's written rules are the only guard, which the capability line says; on Claude Code nothing changes, since its hooks call the same scripts unchanged. Undone by reverting the slice's pull request.
Depends on: 2, 6, 9, 10, 15.
Loop module: build, because each verdict pair, rule and written file is checkable against stand-ins.
Crew: default.

## Under the hood
Add the Codex templates under `setup-ai-build-kit/templates/foundation/codex/`, the adapter `codex-hook.sh` in setup's scripts, `--codex-hook` in `session-start.sh`, a Codex route in the run controller's member starter, and `lib/codex-rule-matcher.py`. Extend `validate-kit.sh` to compare the Codex rules with `blocked-commands.md`. New rehearsal `.agents/tests/codex-parity.sh`, sourcing `lib/rule-shape.sh`, with stand-ins for `codex` in the style of `replay-provider.sh`. Existing rehearsals expected to change: `session-start.sh` (third mode), `check-tooling.sh` (Codex lines), `push-to-main-rules.sh` (shares the written list's new section), `starter-rehearsal.sh` (the new files); `compatibility-grades.sh` is expected to pass unchanged. Kit rules: the five questions for setup-ai-build-kit; SOURCES.md credit; adapters rebuilt; validator; humanizer; no issue numbers.

## Evidence
Paired payloads fed through both hook routes with identical verdicts required; a rules matcher tested first against Codex's documented examples, then against every written spelling, with each rule removed in turn; stand-ins for `codex exec` recording each member's inputs. One guided check on a computer with Codex installed: found a throwaway project, open Codex in it, ask it to add a state label directly, and see the gate refuse it.

## Size
Three sittings, one per part. Part b and Part c need Part a's adapter.

## Consistency notes
- "The run controller" is `implement/scripts/run.py` from slice 9, the design note's run script; Codex members are started by it, as Claude members are.
- The Codex rules file takes the new name, `.codex/rules/ai-loop-kit.rules`, from the start, since it is a new file and slice 22 then has nothing to rename in it.
- The hooks call the same `gate.py` subcommands as Claude Code's hooks: the command check from slice 2's state guard and `gate.py stop-check` from slice 6.
- No project founded with AI Build Kit receives the Codex files (decision 63).
