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
1. Run `"<KIT>/bin/kit-python" "<KIT>/scripts/gate.py" bootstrap`. In any folder, even without git, it makes what is missing: the repository, the first commit and push of main, and the labels. It skips what exists.
   - uv or gh missing: the person runs the printed install or `! gh auth login`, then bootstrap again.
   - No GitHub repository: ask once to create it, suggesting the folder name and private. Say setup pushes the first main and requires pull requests on it, except on a free plan with a private repository. If `git rev-parse --verify main` fails, first do steps 2 and 3 (skip doctor dry-runs) and write step 4's loop section to a file outside the project. Run `"<KIT>/bin/kit-python" "<KIT>/scripts/gate.py" bootstrap --name <name> --visibility private --protect --loop-section <file>` and go to step 5; no pull request is needed. Otherwise leave out `--loop-section`.
   - Any other refusal: give the person its `next:` line and stop.
   Then run `"<KIT>/bin/kit-python" "<KIT>/scripts/gate.py" doctor`. Done when: every check above "AGENTS.md on main" says ok.
2. Find how the project already builds and tests. Read its files: `package.json` and its lockfile, `pyproject.toml`, `uv.lock`, `requirements*.txt`, `go.mod`, `Cargo.toml`, `Makefile`, `Dockerfile`, `docker-compose.yml` or `compose.yaml`, and the CI workflow if there is one. The CI workflow usually shows the exact install and test steps.
   Done when: you can say in one sentence how a fresh clone gets ready and runs its tests.
3. Agree the commands with the person. Offer the way the project already works as the recommended answer, and the other real options beside it. Never impose a tool the project does not use.
   - **Agent backend**: offer Claude Code as the default and Codex as an alternative for builders, standards reviewers, contract reviewers and critics. Explain that Codex can save Claude credit and uses a whole-process sandbox with network disabled. It has no kit guard hook or Claude Edit denies, so the gate still checks settings, protected paths and secrets. Record `Agent: claude` or `Agent: codex` only after the person chooses. Interactive skills stay in Claude Code.
   - **Prepare command**: makes a fresh clone runnable. Examples: `npm ci` (with a lockfile) or `npm install`; `uv sync`; `python3 -m venv .venv && .venv/bin/pip install -e '.[test]'`; `docker compose build`. Leave it out when a fresh clone needs nothing.
   - **Test command**: runs every test. Examples: `npm test`; `python -m pytest`; `go test ./...`; `docker compose run --rm app npm test`.
   - **Keep limit**: the maximum time in minutes for the project's Keep command. It defaults to 15. Doctor runs Keep on a fresh copy of main and prints a `next:` step if it times out.
   - **Quality commands**: optional checks that run after the judge and Test command pass. For Python, mutation testing with mutmut is experimental. `/ai-loop-kit-extras:setup` supplies the required `AI_LOOP_KIT_EXTRAS_ROOT`. Offer `python3 "$AI_LOOP_KIT_ROOT/quality/mutmut-check.py"` only when mutmut 3.8 or later is installed and `source_paths` is configured. The command refuses either missing requirement. Mutmut scores code called in the same Python process. If acceptance tests only launch a separate process, keep those tests in the Test command and add a focused test that calls the entry point or changed function in-process; set `pytest_add_cli_args_test_selection` to select that test for mutmut. This is the fallback for subprocess-only suites. You may also offer `coverage json -o coverage.json && python3 "$AI_LOOP_KIT_ROOT/quality/crap.py" --coverage coverage.json`; the project must collect coverage data during its Test command. For Node, offer `npx eslint --rule 'complexity: ["error", 10]' .`. These can take much longer than the regular tests. Say what each command runs and ask before adding it. Before recording a proposed Quality command, run `"<KIT>/bin/kit-python" "<KIT>/scripts/gate.py" doctor --quality-command '<command>'`. If Prepare or Test is changing at the same time, pass its proposed value with `--prepare-command '<command>'` or `--test-command '<command>'`; pass an empty Prepare command to clear it. Doctor applies all proposed loop settings to a fresh copy of main before running Prepare, Test and Quality. Do not record a command that fails there; show its named failure and offer a correction.
   - When adding mutmut, use its 3.8 or later `source_paths` and `pytest_add_cli_args_test_selection` keys. Set pytest `testpaths` to the project's test directory so mutmut does not collect tool output.
   - **Standards and protected paths**: offer the existing standards file as the recommended standards choice. Never use `AGENTS.md` as the standards file. If none exists, offer to create `STANDARDS.md` with a short starter, or use the built-in baseline. Offer protected paths as well, recommending existing `.claude/`, `.githooks/`, secret and deployment configuration paths that must not change. Record either choice only after the person says yes. If they decline, leave it out.
   - **Walk-away network access**: inspect Prepare and Test for package registries they need. Show the exact domains and ask the person to confirm them before recording `Sandbox domains: <comma-separated domains>` in the loop section. These domains are reachable by shell commands during a walk-away run, so do not add GitHub or general web domains unless the person asks for them.
   - **Branch protection**: if doctor reports it disabled, ask whether to require pull requests on `main`. After a yes, run `"<KIT>/bin/kit-python" "<KIT>/scripts/gate.py" bootstrap --protect`.
   For an empty project, recommend a plain stack for the language the person wants, and ask.
   The gate runs both in a fresh copy of main for every piece, and the run runs Prepare before every build, so both must work from a fresh clone. A project `.venv` made by Prepare is put first on `PATH`.
   Done when: the person has confirmed both commands, or confirmed that Prepare is not needed, chosen an agent backend, and accepted or declined the offered standards file and protected paths.
4. When main already has commits, add the loop section to the project's `AGENTS.md` (make the file if it is missing), commit it on a branch, and open a pull request for the person:
   ```
   ## The loop
   This project uses AI Loop Kit. Pieces are GitHub issues with one `state:` label.
   Only the gate (gate.py) changes a state label. The person merges every pull request into main.
   Prepare command: `<the confirmed command>`
   Test command: `<the confirmed command>`
   Agent: claude
   Quality: `<each confirmed optional command>`
   Standards: `<confirmed path>`
   Protected paths: `<paths builders and reviewers must not edit>`
   Idle limit: 10
   Waiting limit: 3
   Base branch: main
   Keep limit: 15
   Sandbox domains: registry.npmjs.org, pypi.org, files.pythonhosted.org
   ```
   Leave out Prepare if it is not needed, Standards when the built-in baseline is used, and `Protected paths:` when there are none. Write `Sandbox domains:` only after the person confirms the list. Ask before changing the idle or waiting defaults. The gate reads these settings from the loop section.
   Done when: the pull request is open and you have given the person its link.
5. After the person merges, or after bootstrap made the first commit, run `"<KIT>/bin/kit-python" "<KIT>/scripts/gate.py" doctor` again.
   Done when: every check says ok, or warns that there are no tests yet. If the tests fail on a fresh copy of main, show the failures and find the cause, often the environment and not the code. Recommend a fix: a better Prepare command, or a piece to fix the tests. Never narrow the Test command to hide failures without the person's yes.
6. Tell the person what comes next: if the project is empty, its first piece is a scaffold piece (see `<KIT>/examples/scaffold.md`). Then `/ai-loop-kit:shape`.
