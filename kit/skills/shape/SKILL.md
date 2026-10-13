---
name: shape
description: Turns an idea into a piece the gate accepts as ready - a GitHub issue with numbered Done when items and a judge that fails on main. Use when the person describes work to build or brings a rough idea.
---
# Shape

Shaping is the work. A piece leaves here only when it is clear enough to be
built with nobody steering, and its judge proves that.

## Kit
!`echo "KIT=${CLAUDE_PLUGIN_ROOT}"`

Use the KIT path above in every command. Write it out in full. Read
`<KIT>/spec-format.md` before you write a spec.

## Now
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gate.py" status 2>&1 | head -20`

## Steps
1. Understand the idea. Read the code and docs it touches. Look at the open issues for the same idea (`gh issue list --search "<words>"`).
   Done when: you can say the idea back in one sentence, and you have shown the person any issue that looks the same.
2. Ask one batch of questions. Read `references/questions.md` first.
   Done when: each answer is in your notes, or written down as an assumption you made.
3. If the idea holds more than one piece, split it. One piece is one change a builder can finish in about an hour, with three to six Done when items.
   Done when: the person agrees to the split.
4. Write the spec in the format of `<KIT>/spec-format.md`, with a test name per Done when item, and show it to the person.
   Done when: the person says yes to the spec.
5. Capture it: write the body to a file in the system temp folder, then run `python3 "<KIT>/scripts/gate.py" capture --title "<title>" --body-file <file>`.
   Done when: the gate prints the piece number.
6. Write the judge. Run `git switch -c piece/<n> main`. Write the judge test files named in the spec. Each test name holds its spec ID, like `test_D2_streak_resets`. Each test fails today on an assertion, not on an import or syntax error: import new code inside the test. Commit the judge files alone. Then `git switch main`.
   Done when: `git log main..piece/<n>` shows one commit holding only the judge files, and you are back on main.
7. Check it with `python3 "<KIT>/scripts/gate.py" check <n>`. Fix what it names, on the piece branch.
   Done when: it prints `ok`.
8. Move it with `python3 "<KIT>/scripts/gate.py" move <n> ready`.
   Done when: the piece is in ready, or you have reported the refusal and its `next:` line.

## Rules
- Never change a `state:` label by hand. Only the gate moves a piece.
- Never write the code the piece asks for. Shaping writes the spec and the judge only.
- After ready, the spec and the judge are fixed. To change either, move the piece back with `gate.py move <n> shaping --reason "<why>"`, then shape it again.
- If the gate refuses, report the refusal in plain words and take the `next:` step. Never reach the same result another way.
