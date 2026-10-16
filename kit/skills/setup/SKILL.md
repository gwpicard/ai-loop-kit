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
   - **Agent backend**: offer Claude Code as the default and Codex as an alternative for builders, standards reviewers and contract reviewers. Explain that Codex can save Claude credit and uses a whole-process sandbox with network disabled. It has no kit guard hook or Claude Edit denies, so the gate still checks settings, protected paths and secrets. Record `Agent: claude` or `Agent: codex` only after the person chooses. Interactive skills stay in Claude Code.
   - **Prepare command**: makes a fresh clone runnable. Examples: `npm ci` (with a lockfile) or `npm install`; `uv sync`; `python3 -m venv .venv && .venv/bin/pip install -e '.[test]'`; `docker compose build`. Leave it out when a fresh clone needs nothing.
   - **Test command**: runs every test. Examples: `npm test`; `python -m pytest`; `go test ./...`; `docker compose run --rm app npm test`.
   - **Keep limit**: the maximum time in minutes for the project's Keep command. It defaults to 15. Doctor runs Keep on a fresh copy of main and prints a `next:` step if it times out.
   - **Quality commands**: optional checks that run after the judge and Test command pass. For Python, mutation testing with mutmut is experimental. Offer `python3 "$AI_LOOP_KIT_ROOT/quality/mutmut-check.py" origin/main` only when mutmut 3.8 or later is installed and `source_paths` is configured. The command checks both requirements and fails if either is missing. Mutmut scores code called in the same Python process. If acceptance tests only launch a separate process, keep those tests in the Test command and add a focused test that calls the entry point or changed function in-process; set `pytest_add_cli_args_test_selection` to select that test for mutmut. This is the fallback for subprocess-only suites. You may also offer `coverage json -o coverage.json && python3 "$AI_LOOP_KIT_ROOT/quality/crap.py" --coverage coverage.json --base origin/main`; the project must collect coverage data during its Test command. For Node, offer `npx eslint --rule 'complexity: ["error", 10]' .`. These can take much longer than the regular tests. Say what each command runs and ask before adding it. Before recording a proposed Quality command, run `python3 "<KIT>/scripts/gate.py" doctor --quality-command '<command>'`. If Prepare or Test is changing at the same time, pass its proposed value with `--prepare-command '<command>'` or `--test-command '<command>'`; pass an empty Prepare command to clear it. Doctor applies all proposed loop settings to a fresh copy of main before running Prepare, Test and Quality. Do not record a command that fails there; show its named failure and offer a correction.
   - When adding mutmut, use its 3.8 or later `source_paths` and `pytest_add_cli_args_test_selection` keys. Set pytest `testpaths` to the project's test directory so mutmut does not collect tool output.
   - **Standards and protected paths**: offer the existing standards file as the recommended standards choice. Never use `AGENTS.md` as the standards file. If none exists, offer to create `STANDARDS.md` with a short starter, or use the built-in baseline. Offer protected paths as well, recommending existing `.claude/`, `.githooks/`, secret and deployment configuration paths that must not change. Record either choice only after the person says yes. If they decline, leave it out.
   - **Walk-away network access**: inspect Prepare and Test for package registries they need. Show the exact domains and ask the person to confirm them before recording `Sandbox domains: <comma-separated domains>` in the loop section. These domains are reachable by shell commands during a walk-away run, so do not add GitHub or general web domains unless the person asks for them.
   - **Branch protection**: ask whether the person wants protection on `main`. Offer it only for a public repository or a plan that supports it. If they say yes, use `gh api` to require pull requests. Do not change repository settings before that yes. Doctor reports whether protection is enabled.
   For an empty project, recommend a plain stack for the language the person wants, and ask.
   The gate runs both in a fresh copy of main for every piece, and the run runs Prepare before every build, so both must work from a fresh clone. A project `.venv` made by Prepare is put first on `PATH`.
   Done when: the person has confirmed both commands, or confirmed that Prepare is not needed, chosen an agent backend, and accepted or declined the offered standards file and protected paths.
4. Add the loop section to the project's `AGENTS.md` (make the file if it is missing), commit it on a branch, and open a pull request for the person:
   ```
   ## The loop
   This project uses AI Loop Kit. Pieces are GitHub issues with one `state:` label.
   Only the gate (gate.py) changes a state label. The person merges every pull request.
   Prepare command: `<the confirmed command>`
   Test command: `<the confirmed command>`
   Agent: claude
   Quality: `<each confirmed optional command>`
   Standards: `<confirmed path>`
   Protected paths: `<paths builders and reviewers must not edit>`
   Idle limit: 10
   Waiting limit: 3
   Keep limit: 15
   Sandbox domains: registry.npmjs.org, pypi.org, files.pythonhosted.org
   ```
   Leave out Prepare if it is not needed, Standards when the built-in baseline is used, and `Protected paths:` when there are none. Write `Sandbox domains:` only after the person confirms the list. Ask before changing the idle or waiting defaults. The gate reads these settings from the loop section.
   Done when: the pull request is open and you have given the person its link.
5. After the person merges, run `python3 "<KIT>/scripts/gate.py" doctor` again.
   Done when: every check says ok. If the tests fail on a fresh copy of main, show the failures and find the cause, often the environment and not the code. Recommend a fix: a better Prepare command, or a piece to fix the tests. Never narrow the Test command to hide failures without the person's yes.
6. Tell the person what comes next: if the project is empty, its first piece is a scaffold piece (see `<KIT>/spec-format.md`). Then `/ai-loop-kit:shape`.
