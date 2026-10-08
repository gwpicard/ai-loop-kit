# Core rehearsal

Run `tests/e2e-core.sh` for both cases, or pass `--case local` or `--case app`.
It needs pytest and uses only the Claude, GitHub and computer stand-ins.
Each scratch project and its commands.log remain available for inspection.

The project starts with only a README. Founding leaves the test command empty.
The scaffold introduces a test runner and a small total function with a known
empty-list bug. After the scaffold merge, the person sets the policy's test
command. Each later judge is committed and shown red before its builder runs.
Four hidden cases check different inputs on the combined branch.

With the App, the unattended run builds, joins, checks and reviews the pieces,
opens a pull request as the App, and records the person's merge as done.
Before the App, the attended run makes no GitHub calls. The person sends the
queued writes with the printed sync command, then pushes, opens and merges a
pull request themselves. After sync, the kit prepares the exact push and open
commands. The person runs `python3 -m loop.run.pull_request record-manual
--run NAME --pull-request N` in their terminal to record the actual pull
request and its merge. Fetch `origin/main` before recording a merge. If main
moved or the merged tree differs, the project checks must pass on that tree.
The recorded merge must be on fetched `origin/main`. Stacked requests are
recorded in part order; a later request can retarget to main after its
predecessor reaches done. The gate checks the tested commit, review and final
checks, records the merge as the person's action, and moves each piece to done.
An agent or a pipe cannot use this command. Repeating it is safe.

The changelog must hold one entry for the scaffold and two new entries for the
feature and bug. Records checks and the merged project's tests must pass in
both cases. Both cases require done pieces and closed issues with done labels.

The real App path is a separate manual smoke in `tests/smoke/run-real.sh`.
It requires an explicit opt-in, a terminal and a separate tiny test repository
with an installed test App. It calls real Claude and leaves each merge to the
person. The person also merges the founding and policy-configuration pull
requests. The generated hosted check refuses the empty policy test command
during founding and the scaffold; that existing kit limitation remains a
follow-up. The automated suite never runs the real smoke.
