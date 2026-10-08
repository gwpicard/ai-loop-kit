---
name: setup
description: Founds a project or meets an existing one, so the person can shape and run locally. The person types it. This is the first half of setup; the GitHub App comes in the second half.
disable-model-invocation: true
---
# Setup, first half

This skill takes a project from nothing to "shape and run locally". It runs the setup script, which writes missing foundation files. Only the generated scaffold command entry can change when the first piece is captured. You hold the conversation. The script holds the rules.

Every command below uses `"${CLAUDE_PLUGIN_ROOT}"`, the folder of the installed kit, in double quotes so a folder with a space works. A founded project has no `kit/` folder.

## Stops
- Stop when the tooling check names a missing tool. Show the install line, write nothing else, and wait for the person to install it. Held by: `kit/scripts/setup.py` runs `kit/scripts/check-tooling.sh` before it writes a file, and stops with exit code 4.
- Stop when `origin` is the kit's own repository, or when there is no `origin`. Give the `next:` line. Open no issue and change no setting. Held by: `kit/scripts/setup.py` checks `origin` before it writes a file, and stops with exit code 3.
- `found` keeps existing files. `first-piece` may update only the generated scaffold command entry; it preserves the rest of the workflow. Never remove a settings rule. Held by: `kit/scripts/setup.py` limits the update, and `kit/scripts/merge-settings.py` adds rules and takes nothing out.
- Never create the GitHub App, never show the link that makes it and never write a key. The App comes in the second half of `/setup`. Held by: `tests/setup-first-half.sh` fails if a key file, a key path or the link appears, and `kit/scripts/pre-run-check.py` refuses an unattended run with no App.
- Never call `gh`, never use the person's GitHub sign-in, and never create a label or an issue yourself. Held by: `kit/scripts/loop/github.py` is the one place that starts `gh`, and `kit/hooks/guard.py` refuses the person's sign-in.
- Never edit `.claude/settings.json` or the policy file by hand. Held by: the deny rules that `kit/scripts/merge-settings.py` writes into the settings, and `kit/scripts/setup.py`, which writes both files.
- Never stop founding on a nice-to-have answer. Write it as an open question and carry on. Held by: `kit/scripts/setup.py` writes an open question instead of stopping, and `tests/setup-first-half.sh` checks it.
- Never move the first piece to ready by any route but the gate. Held by: `kit/scripts/gate.py` is the only code that moves a piece.

## Steps
1. Run `sh "${CLAUDE_PLUGIN_ROOT}/scripts/check-tooling.sh"`. Read `references/founding.md` when it reports a missing tool.
   Done when: it exits 0, or you have shown the person the install line and stopped.
2. Look at the project. Read the files at the root, and find out whether it holds code, an `AGENTS.md` or settings.
   Done when: you can say in one sentence whether the project is empty or has code.
3. Ask one batch of questions, each with a recommended answer. Read `references/founding.md` for the list.
   Done when: each answer is in hand, or each skipped answer is a nice-to-have that the script will write as an open question.
4. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup.py" found --dry-run` with the answers as flags. Pass a chosen `--test-command` to both `found` and `first-piece`, even before a runner exists. Show the person the files it lists.
   Done when: the person has seen what will be written and what will be kept.
5. Run the same command without `--dry-run`.
   Done when: it exits 0, and its reply lists `created`, `kept` and `extended`.
6. Write what the product is into `docs/overview.md`, from the person's answers. Keep it short.
   Done when: the file holds no angle-bracket placeholder.
7. Read `warnings` and `asks` in the reply. Say each warning in plain words. Ask for each missing spend cap.
   Done when: each warning is said, and each ask is answered or written as an open question.
   The person commits the foundation on a preparation branch, reviews and merges its pull request, then fetches and updates local main. Never push to main.
8. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup.py" first-piece`, with `--test-command` when the person gave one. If the command was unknown, ask for it. If it names preparation, show the person the next step: commit the selected generated entry on a preparation branch, review and merge that pull request, then update local main and retry.
   Done when: the reply holds a piece number, or says a piece is already captured.
9. Give the person the label step. Read `labels.next` from the reply of step 5 and show it, as it is. The gate creates the labels only after a write is queued, and the first piece is that write.
   Done when: the person has the exact command, and you have created no label.
10. Close with the reply's `closing` text. Say that the second half of `/setup` makes the GitHub App, and that until then every GitHub write waits for the person.
    Done when: the person knows what they can do now and what waits.

## Gotchas
- A project with code often has its own `AGENTS.md`, settings and hooks. They stay. Tell the person which of the kit's lines are missing from them, and let the person choose.
- A private repository on the free plan has no server-side rules. Say so once, in plain words.
- `found` changes only what is missing. A later chosen scaffold command needs person preparation before capture or branching; an uncommitted workflow edit is insufficient.
- A hook the person wrote at `.githooks/pre-push` is kept. The pre-run check refuses a run until the kit's secret scan is in it.
- The first piece is a scaffold piece. With no test runner, its command is carried on the piece, not in the policy. The scaffold's own change sets the policy.
- The label step and every piece filed as an issue wait for the person. The reply's `next:` line names the exact command.

## When to read more
- Read `references/founding.md` when a tool is missing, before you ask the questions, and when the person asks what a written file is for.
