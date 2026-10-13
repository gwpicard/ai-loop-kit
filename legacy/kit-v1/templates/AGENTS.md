# AGENTS.md

<!-- The standing instructions for every agent in this project. `CLAUDE.md` only
imports this file. Keep it under 150 lines, with no section over 12 lines. A
fact lives in one home, so point at that home and never copy it here. A rule that
a script or a hook can hold belongs in the script or the hook. -->

## Commands

- `<install command>`: install the project's tools.
- `<test command>`: run every check. This is the `test_command` in
  `.agents/loop/policy.json`.
- `<lint command>`: run the linter and the type check.
- `<run command>`: start the project on this computer.
- `python3 {{KIT_DIR}}/scripts/records-check.py`: check that the records
  agree with each other and with the code.

## Areas

The areas of the project are in `docs/area-map`, one `<pattern> <area>` line for
each rule, CODEOWNERS style. The last matching line wins. The map holds no
prose. The overview names each area and says whether it is sensitive. Change the
map in the same pull request as the code it describes. Run
`python3 {{KIT_DIR}}/scripts/area-map.py check` to see whether it is still true.

## Rules and the reason for each

<!-- One line for each rule, with its reason after it. Founding fills this in
from the project. Add a rule only when no check or hook can hold it. -->

- `<rule>`. `<the short reason>`.

## Guarded actions

- Never push to `main` and never force-push. Every change arrives in a pull
  request, and the person decides the merge.
- Never run a command from `.agents/guard/blocked-commands.md`. If one is
  refused, report it and stop. Do not reach the same result another way.
- Never edit the `state:` labels of a piece by hand. Only the gate moves a piece.
- Never edit `.claude/settings.json`, the policy file or the gate's piece
  records. A rule is a guard only when the agent cannot change it.
- Never put a secret in a tracked file, and never print one.
- Ask the person before anything irreversible, or anything that changes access,
  money or an online service.

## Where to read next

- `docs/overview.md`: what the product is, who it is for, and the area table.
- `docs/area-map`: which files belong to which area.
- `docs/README.md`: the index of the area docs, which hold the current behaviour.
- `CHANGELOG.md`: what changed, one entry for each merged piece.
