---
name: shape
description: Turns an idea into a piece the gate accepts as ready - a GitHub issue with numbered Contract items and a judge that fails on main. Use when the person describes work to build or brings a rough idea.
---
# Shape

Shaping is the work. A piece leaves here only when it is clear enough to be
built with nobody steering, and its judge proves that.

## Kit
!`echo "KIT=${CLAUDE_PLUGIN_ROOT}"`

Use the KIT path above in every command. Write it out in full. Read
`<KIT>/spec-format.md` before you write a spec.

## Now
!`"${CLAUDE_PLUGIN_ROOT}/bin/kit-python" "${CLAUDE_PLUGIN_ROOT}/scripts/gate.py" status 2>&1 | head -20`

## Steps
1. `<base>` is the `Base branch:` in AGENTS.md on `main`, or `main` when there is none. Run `git switch <base>` and `git pull --ff-only`, so you start from the merged work. Understand the idea. Read the code and docs it touches. Look at the open issues for the same idea (`gh issue list --search "<words>"`).
   Done when: you can say the idea back in one sentence, and you have shown the person any issue that looks the same.
2. Ask one batch of questions. Read `references/questions.md` first. For any
   outside fact, save a JSON object with only `question`. Run
   `"<KIT>/bin/kit-python" "<KIT>/scripts/session.py" --role researcher --input <file> --output <findings> --folder .`.
   It uses the project's backend; `--agent codex` overrides it. Add accepted
   findings to `## Research`. If web tools are unavailable, stop shaping.
   Done when: each answer is in your notes or recorded as an assumption, and
   any needed outside facts have sourced findings.
3. If the idea holds more than one piece, split it. One piece is one change a
   builder can finish in about an hour, with three to six Contract items.
   Done when: the person agrees to the split.
4. Write the spec in the format of `<KIT>/spec-format.md`, with a test
   name per Contract item, and show it to the person. When a piece adds or
   changes a module, Approach names that module and the interface a caller
   uses. The project's Test command is required. Optional `Keep:` adds
   checks; it never replaces the full suite. Equal commands run once.
   Include all five lines under `## Risks`: Protected paths, New
   dependency, Shared files, Needs services and Open choices. Write `none`
   when a line has no entries, and settle every open choice before ready.
   Add `Depends on: <piece numbers>` only when this piece needs another's
   code first; stub that code so the judge fails by assertion.
   Mark a Contract item that holds on the base today as `(stays)`; never bend a
   test so it fails on main. Put rules the gate must enforce in Contract or
   Exit. Use `Playbook: fix` for fix guidance. Add
   `Settings: may change` in `## Judge` only for a piece about lint, test
   or CI settings.
   When a piece needs stronger tests in an existing mutation adapter, name
   its path in Contract so the builder may strengthen it. Keep the adapter
   out of Exit `Files:`: those files are frozen at ready, even when Contract
   names them. Use a separate judge that does not depend on the editable
   adapter.
   `mutmut-changed.py` selects functions from committed `base...HEAD`
   changes. A builder's check before committing may find no changed
   functions. The final gate evidence comes after the runner commits the
   attempt and runs the checks again.
   Done when: the person says yes to the spec.
   Once the person approves the Intent, Out of scope, Approach and Contract, do not change those words without asking for approval again. For a `fix`, first reproduce the bug and make the first Contract item say what fails now and what should happen.
5. Capture it: write the body to a file in the system temp folder, then run `"<KIT>/bin/kit-python" "<KIT>/scripts/gate.py" capture --title "<title>" --body-file <file>`.
   Done when: the gate prints the piece number.
6. Run `git fetch origin <base>`, then `git switch -c piece/<n> origin/<base>`.
   If `piece/<n>` already exists because the piece came back, do not make it again: run `git switch piece/<n>` and `git pull --ff-only origin piece/<n>`. The judge writer adds its commit on top.
   Save JSON containing approved `Intent`, `Approach`, `Contract` and `Files`
   strings. `Files` lists exact Exit paths, one per line. Exclude shaping chat.
   Save input and output in the system temp folder. Run
   `"<KIT>/bin/kit-python" "<KIT>/scripts/session.py" --role judge-writer --input <file> --output <verdict> --folder .`.
   The fresh session reads `<KIT>/briefs/judge-writer.md` and the project code.
   The launcher requires a clean piece branch, checks paths and verdict, and
   commits judge files. Report any refusal and `next:` line. On success, run
   `git switch <base>`.
   Done when: `git log <base>..piece/<n>` shows the judge commit (the newest
   commit for a returned piece), and you are back on `<base>`.
7. Run the project's Test command on the piece branch. An Exit Tests check
   fails on main; a Measure or Critics check uses its own baseline. Read the
   output and fix errors in the check files, such as lint, type or format
   errors. Then run `"<KIT>/bin/kit-python" "<KIT>/scripts/gate.py" check <n>` and fix what it
   names on the piece branch.
   Done when: it prints `ok`.
8. If the approved spec needs an edit while shaping, write the full revised body to a temporary file and use `"<KIT>/bin/kit-python" "<KIT>/scripts/gate.py" spec <n> --body-file <file>`. Get the person's approval before replacing an approved contract. Move it with `"<KIT>/bin/kit-python" "<KIT>/scripts/gate.py" move <n> ready`.
   Done when: the piece is in ready, or you have reported the refusal and its `next:` line.

## Rules
- Never change a `state:` label by hand. Only the gate moves a piece.
- Never write the code the piece asks for. Shaping writes the spec and the judge only.
- Use `## Exit` for the checks that decide when the piece is done. Add one or more `### Tests`, `### Measure` or `### Critics` checks. Every check must be unmet on main for the right reason, and each check names its files. Combine checks when the contract needs them together. Follow `<KIT>/spec-format.md`.
- Keep `Playbook: fix` as builder guidance. A fix reproduces the reported bug first and finds its cause. Playbook text does not affect the gate.
- Old issues with `## Judge` and `Kind:` remain accepted as one check. Do not use the old format for new specs.
- Never reset, recreate or force-push a piece branch. Once pushed, it only grows.
- After ready, the spec and the judge are fixed. To change either, move the piece back with `gate.py move <n> shaping --type spec-unclear --reason "<why>"`, then shape it again.
- If the gate refuses, report the refusal in plain words and take the `next:` step. Never reach the same result another way.
