---
name: setup
description: Prepares a project for the loop. Runs the kit's own checks, agrees how the project prepares and tests itself, and records both in AGENTS.md. Use once per project, before the first shape, and again when a check fails.
---
# Setup

## Kit
!`echo "KIT=${CLAUDE_PLUGIN_ROOT}"`

Use the KIT path above in every command below. Write it out in full.

The kit checks the project in code with `gate.py doctor`. You read its result
and fix what it names; you do not judge the ground by eye.

## Steps
1. Make the labels with `python3 "<KIT>/scripts/gate.py" init`, then run `python3 "<KIT>/scripts/gate.py" doctor`.
   Done when: every check above "AGENTS.md on main" says ok. For each FAIL, give the person its `next:` line and stop until it is fixed. You never make the first commit or push to main yourself.
2. Find how the project already builds and tests. Read its files: `package.json` and its lockfile, `pyproject.toml`, `uv.lock`, `requirements*.txt`, `go.mod`, `Cargo.toml`, `Makefile`, `Dockerfile`, `docker-compose.yml` or `compose.yaml`, and the CI workflow if there is one. The CI workflow usually shows the exact install and test steps.
   Done when: you can say in one sentence how a fresh clone gets ready and runs its tests.
3. Agree the commands with the person. Offer the way the project already works as the recommended answer, and the other real options beside it. Never impose a tool the project does not use.
   - **Prepare command**: makes a fresh clone runnable. Examples: `npm ci` (with a lockfile) or `npm install`; `uv sync`; `python3 -m venv .venv && .venv/bin/pip install -e '.[test]'`; `docker compose build`. Leave it out when a fresh clone needs nothing.
   - **Test command**: runs every test. Examples: `npm test`; `python -m pytest`; `go test ./...`; `docker compose run --rm app npm test`.
   - **Quality commands**: optional checks that run after the judge and Test command pass. For Python, mutation testing with mutmut is experimental. Offer `python3 "$AI_LOOP_KIT_ROOT/quality/mutmut-changed.py" origin/main` only when the project's tests call changed code in-process and the project uses mutmut 3.8 or later. The helper checks the installed mutmut version and fails if `source_paths` is missing. Mutmut tracks calls in the test process, so tests that only launch a separate process do not score mutants. For those projects, use a project-specific subprocess-aware mutation command if one exists, or add an in-process test for the changed behaviour before offering mutmut. You may also offer `coverage json -o coverage.json && python3 "$AI_LOOP_KIT_ROOT/quality/crap.py" --coverage coverage.json --base origin/main`; the project must collect coverage data during its Test command. For Node, offer `npx eslint --rule 'complexity: ["error", 10]' .`. These can take much longer than the regular tests. Say what each command runs and ask before adding it. Before recording a proposed Quality command, run `python3 "<KIT>/scripts/gate.py" doctor --quality-command '<command>'`. If Prepare or Test is changing at the same time, pass its proposed value with `--prepare-command '<command>'` or `--test-command '<command>'`; pass an empty Prepare command to clear it. Doctor runs the command on a fresh copy of main with those proposed settings. Do not record a command that fails there; show its named failure and offer a correction.
   - When adding mutmut, use its 3.8 or later `source_paths` and `pytest_add_cli_args_test_selection` keys. Set pytest `testpaths` to the project's test directory so mutmut does not collect tool output.
   - **Standards and protected paths**: offer the existing standards file as the recommended standards choice. Never use `AGENTS.md` as the standards file. If none exists, offer to create `STANDARDS.md` with a short starter, or use the built-in baseline. Offer protected paths as well, recommending existing `.claude/`, `.githooks/`, secret and deployment configuration paths that must not change. Record either choice only after the person says yes. If they decline, leave it out.
   - **Branch protection**: ask whether the person wants protection on `main`. Offer it only for a public repository or a plan that supports it. If they say yes, use `gh api` to require pull requests. Do not change repository settings before that yes. Doctor reports whether protection is enabled.
   For an empty project, recommend a plain stack for the language the person wants, and ask.
   The gate runs both in a fresh copy of main for every piece, and the run runs Prepare before every build, so both must work from a fresh clone. A project `.venv` made by Prepare is put first on `PATH`.
   Done when: the person has confirmed both commands, or confirmed that Prepare is not needed, and has accepted or declined the offered standards file and protected paths.
4. Add the loop section to the project's `AGENTS.md` (make the file if it is missing), commit it on a branch, and open a pull request for the person:
   ```
   ## The loop
   This project uses AI Loop Kit. Pieces are GitHub issues with one `state:` label.
   Only the gate (gate.py) changes a state label. The person merges every pull request.
   Prepare command: `<the confirmed command>`
   Test command: `<the confirmed command>`
   Quality: `<each confirmed optional command>`
   Standards: `<confirmed path>`
   Protected paths: `<paths builders and reviewers must not edit>`
   Idle limit: 10
   Waiting limit: 3
   ```
   Leave out Prepare if it is not needed, Standards when the built-in baseline is used, and `Protected paths:` when there are none. Ask before changing the idle or waiting defaults. The gate reads these settings from the loop section.
   Done when: the pull request is open and you have given the person its link.
5. After the person merges, run `python3 "<KIT>/scripts/gate.py" doctor` again.
   Done when: every check says ok. If the tests fail on a fresh copy of main, show the failures and find the cause, often the environment and not the code. Recommend a fix: a better Prepare command, or a piece to fix the tests. Never narrow the Test command to hide failures without the person's yes.
6. Tell the person what comes next: if the project is empty, its first piece is a scaffold piece (see `<KIT>/spec-format.md`). Then `/ai-loop-kit:shape`.
