---
name: shape
description: Captures an idea in the person's words, or shapes a piece until the ready gate accepts it. Use when the person describes work to build, brings a rough idea, or asks what a piece in shaping still needs.
---
# Shape

This skill takes one idea from the person's words to a piece that the ready gate accepts. The gate works out what the piece still needs from its spec. You settle the biggest need first, and you write each answer into the spec.

## Now
!`python3 kit/scripts/gate.py report --json --brief`
If the line above shows a disabled marker or an error, run that command by hand first.

## Stops
- Stop when a need names the person, and wait for the written answer. Silence is never an answer, and you never answer for the person. Held by: `kit/scripts/loop/needs.py` keeps the need on the list until an answer is written, and `gate.py move` refuses ready while the list holds one.
- Stop when the idea touches a sensitive area, until the person's acceptance is on the issue. Held by: `kit/scripts/loop/gates/ready.py` refuses a sensitive area with no `Accepted:` item.
- Stop when `gate.py move <n> ready` refuses. Report the refusal and its `next:` line in plain words, and take that step. Never reach the same result another way. Held by: `kit/templates/blocked-commands.md` and `kit/hooks/guard.py`.
- Never move a piece to ready by any route but the gate, and never edit a state label. Held by: `kit/scripts/gate.py` is the only code that moves a piece, and `kit/hooks/guard.py` refuses a direct label edit.
- Never put a held-out case in the issue, in a commit or in a reply. Only the fingerprint goes in the spec. Held by: `kit/scripts/loop/heldout.py` keeps the cases outside the project, and `kit/scripts/loop/gates/ready.py` compares the fingerprint with the store.
- Never post or comment in the person's name without their yes. Kit bookkeeping goes through `gate.py comment`, as the App. Held by: `kit/hooks/guard.py` and `kit/scripts/gate.py`, which posts only as the App.
- Stop after one batch of questions. The batch holds the number in the policy file's `question_cap` at most. Held by: `kit/scripts/loop/policy.py` holds the cap, and `kit/skills/shape/evals/normal.md` checks it.

## Steps
1. Search for a duplicate before you file: `python3 kit/skills/shape/scripts/find-duplicates.py search --text "<the idea, in the person's words>"`.
   Done when: you have shown the person every match, and each dropped match has its warning and reason.
2. If a match is the same idea, pass the new words to it with `find-duplicates.py comment <n> --text "<the new words>"`, and open no new piece. If the script says GitHub was not read, give the person its `next:` line.
   Done when: the person has said which match is the same idea, or has said there is none.
3. Capture the idea with `python3 kit/scripts/gate.py capture --title "<the person's words>" --body-file <file>`. Keep the person's wording in the title.
   Done when: the gate has printed a piece number.
4. Choose the path. A small change in one area takes the quick path. Read `references/quick-path.md` when the idea looks small. Anything else takes the full spec.
   Done when: you have told the person which path, and why in one sentence.
5. Read the needs with `python3 kit/scripts/gate.py report <n>`, and take the biggest one. Name it in plain words.
   Done when: the person can read which need you are settling and who can settle it.
6. Settle the need. Research what a file or a page can answer, and record each finding with its source and what it rests on. Ask the person what only they can answer. Read `references/questions.md` before you ask. Use `kit/scripts/co-change.sh <path>...` to fill `Touches:`.
   Done when: each answer is written into the spec, or each open question sits under Open questions with its reason and a recommended answer.
7. Hand the gate the new spec with `python3 kit/scripts/gate.py spec <n> --body-file <file>`, or write one answer with `gate.py answer`. The gate works out the needs again.
   Done when: the gate's reply shows the need gone, or shows the next need.
8. Set aside the hidden cases for an acceptance test. Write them to files outside the project folder, then run `PYTHONPATH=kit/scripts python3 -m loop.heldout store --piece <n> --case ID=FILE`. Write the printed fingerprint in `Held-out cases:`.
   Done when: the spec holds a fingerprint of 64 hex digits and no case text.
9. For a sensitive area, give the risk notice once, in full, in plain words. Ask first whether a different design avoids the area. Write the item under Sensitive areas with `Accepted:`, the person's exact words in quotes, and the date.
   Done when: the item holds all three, or the person has chosen a design with no sensitive area.
10. Make the piece branch with `python3 kit/scripts/gate.py branch <n>`, and commit the judge's test files alone as its first commit.
    Done when: `git log` on the branch shows one commit that holds only the judge files.
11. Run `python3 kit/scripts/spec.py lint <n>`. Fix each gap it names.
    Done when: it exits 0.
12. Ask the gate for ready with `python3 kit/scripts/gate.py move <n> ready`.
    Done when: the piece is in ready, or you have reported the refusal and its `next:` line to the person.

## Gotchas
- A short "ok" to a different question is not an answer to a need. Ask the need again, with the recommended answer written out.
- A vague idea gets no ready move. End the reply with the biggest need still open, and offer to split the idea if it holds two pieces.
- A low-impact unknown becomes an assumption under Decisions, marked as assumed by the agent. A need that names the person stays on the list.
- With no App, the gate queues its GitHub writes. Tell the person the `next:` line names `gate.py sync`, which only they run.
- Quote the person's words as they are in a title or in an acceptance, with no tidying.
- Until a crew is built, settle a research or design question alone, and note in the spec that no crew checked it.

## When to read more
- Read `references/questions.md` before you ask a question that has no obvious recommended answer, and when the gate refuses ready.
- Read `references/quick-path.md` when the idea looks like one small change in one area.
