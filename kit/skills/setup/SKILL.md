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
4. Add a short section to the project's `AGENTS.md` (make the file if it is missing), and commit it on a branch. Open a pull request for the person.
   ```
   ## The loop
   This project uses AI Loop Kit. Pieces are GitHub issues with one `state:` label.
   Only the gate (gate.py) changes a state label. The person merges every pull request.
   Test command: <the confirmed command>
   ```
   Done when: the pull request is open and you have given the person its link.
5. Tell the person what comes next: if the project is empty, its first piece is a scaffold piece (see `<KIT>/spec-format.md`). Then `/ai-loop-kit:shape`.
