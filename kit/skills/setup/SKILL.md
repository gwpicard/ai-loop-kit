---
name: setup
description: Prepares a project for the loop. Checks git and GitHub, makes the state labels and records the test command. Use once per project, before the first shape.
---
# Setup

## Kit
!`echo "KIT=${CLAUDE_PLUGIN_ROOT}"`

Use the KIT path above in every command below. Write it out in full.

## Steps
1. Check the ground. Run `git status`, `git remote -v`, `git log -1 --oneline main` and `gh auth status`.
   Done when: the project is a git repository with an `origin` on GitHub, `main` has at least one commit on origin, and `gh` is signed in. If any is missing, tell the person the one command that fixes it, and stop. You never make the first commit or push to main yourself.
2. Make the labels with `python3 "<KIT>/scripts/gate.py" init`.
   Done when: it prints `ok`.
3. Find the test command. Read the project's files first (package.json, pyproject.toml, Makefile). If the project is empty, recommend one that fits the language the person wants, and ask them to confirm.
   Done when: the person has confirmed the command.
4. Run the test command once on main. If any test fails, stop and show the failures. A red baseline blocks every piece, because the gate's keep check must pass on main. Find the cause: often the environment (wrong package versions), not the code. Recommend a project `.venv` (the gate and the builders put `.venv/bin` first on `PATH`), and check that git ignores it. Do not narrow the command to hide failures without the person's yes.
   Done when: the test command passes on main, or the person has chosen what to do about each failure.
5. Add a short section to the project's `AGENTS.md` (make the file if it is missing), and commit it on a branch. Open a pull request for the person.
   ```
   ## The loop
   This project uses AI Loop Kit. Pieces are GitHub issues with one `state:` label.
   Only the gate (gate.py) changes a state label. The person merges every pull request.
   Test command: <the confirmed command, such as python -m pytest>
   ```
   Done when: the pull request is open and you have given the person its link.
6. Tell the person what comes next: if the project is empty, its first piece is a scaffold piece (see `<KIT>/spec-format.md`). Then `/ai-loop-kit:shape`.
