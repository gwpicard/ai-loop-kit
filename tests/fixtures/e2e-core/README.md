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
pull request themselves. The local pieces remain in review. The check keeps
that known gap visible: sync does not advance the waiting pull request entry,
and check-main does not adopt the manual merge. This needs a follow-up.

The changelog must hold one entry for the scaffold and two new entries for the
feature and bug. Records checks and the merged project's tests must pass in
both cases. A passing rehearsal means today's behaviour matches these
assertions; it does not mean the before-App completion gap is fixed.

The real App path is a separate manual smoke in `tests/smoke/run-real.sh`.
It requires an explicit opt-in, a terminal and a separate tiny test repository
with an installed test App. It calls real Claude and leaves each merge to the
person. The person also merges the founding and policy-configuration pull
requests. The generated hosted check refuses the empty policy test command
during founding and the scaffold; that existing kit limitation remains a
follow-up. The automated suite never runs the real smoke.
