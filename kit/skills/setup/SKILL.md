---
name: setup
description: Set up a project for the AI Loop Kit factory, once per project or again after an update. Use when the person says set up the loop, set up loop kit, install or configure the loop in this project, or the loop refuses because the project is not set up.
---

# Set up the loop

`<plugin>` is this skill's plugin folder, two levels up. Work from the
project root.

## Steps

1. Read the project's `loop.json`. If it is missing but `AGENTS.md` has a
   `## Loop` section, let setup migrate it. Otherwise, if there is no
   `Test command`, propose one from the project itself: a `Makefile` target,
   `package.json` scripts, `pyproject.toml`, `Cargo.toml` or the CI workflow.
   Run the command once to confirm that it passes. If it takes minutes, also
   propose a `Test files command` (runs given test files, `{files}` stands for
   their paths) and a `Prepare command` (installs dependencies in a fresh
   checkout). Propose a `Check command` when the project has lint or a build
   that the tests do not run. Show the settings and ask the person to confirm
   or correct them, then write `loop.json` as a JSON object. Use lists of
   strings for `Protected paths` and `Codex writable roots`, numbers for
   `Parallel`, `Idle hours`, `Max rounds`, `Session minutes` and
   `Full suite every` (an integer of at least one, default four), and strings
   for the remaining settings.
2. Tell the person what setup changes on GitHub (the loop labels, the loop
   branch, a pinned `Factory` issue) and ask the person to confirm before you
   run it.
3. Run `python3 <plugin>/scripts/setup.py`, with `--dry-run` first on a
   project set up by an older kit. On such a project it moves the `## Loop`
   settings from `AGENTS.md` into `loop.json`, files one inbox issue that
   proposes a home for each section of the old plan file, renames the path section in
   open issues, and records each change and its undo in
   `.loop/migrations.log`. It refuses a kit 1.x or `.lite/` layout and prints
   the upgrade steps.
4. Report each line it prints, including every `next:` line in order. Do not
   start the loop until the person has seen these lines. On `refused:`, do
   the `next:` step and run it again. If the preflight fails, report the
   failure and stop. After a migration, complete the applicable `next:` steps
   before restarting the loop. If it added settings or ignore lines, tell the
   person to commit `loop.json`, any migrated removal from `AGENTS.md`, and
   the added `.gitignore` lines through a pull request.
5. Suggest the optional settings that fit: `"Parallel": 3` in the git-ignored
   `loop.local.json` on a machine with
   spare CPU and memory and a queue of independent issues; a `Smoke command`
   when the project has something runnable to exercise, such as a command-line
   tool or a server, since the end-of-loop pass runs a smoke check only when
   one is set.
6. Say what comes next: shape work with the shape skill, then start the loop
   with the loop skill.

Running setup again is safe: it adds only what is missing.
