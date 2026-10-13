# Questions

Ask in one batch. The batch holds the number set by `question_cap` in the policy file, and no more. If you have more questions, keep the ones that clear the biggest needs and record the rest as open questions.

## The shape of a question

Each question has three parts.

- The question, in the person's words where you can.
- Why it matters: what goes wrong in the build if the answer is missing.
- A recommended answer, labelled as yours, so the person can say yes in one word.

A question with no recommended answer is a sign that you have not read enough. Read the area doc and the code first.

## What to ask first

1. The goal, when the Goal field is empty.
2. The one flow the person will see, with a concrete example value.
3. The edge case that would hurt most, written as "When ..., then ...".
4. What must stay the same, and one command that proves it on `main`.
5. The coverage categories that are still silent.

Never ask what a file can answer. Read the file.

## Recorded assumptions

A low-impact unknown does not need a question. Write it under Decisions as an assumption, marked as assumed by the agent, so the person can review it. A need that names the person is never an assumption.

## Silence

Silence is never an answer. If the person does not reply, the need stays on the list. Ask again in a shorter form, with the recommended answer written out.

## The risk notice

When the idea touches a sensitive area, first look for a design that avoids it: copy data, remove the automation, add a human step, use a managed service, or make a narrower promise. Offer these once. If the person still wants the area, give the notice once, in full: what the area is, what can go wrong, and what the project will not protect against.

Any words that go ahead are the acceptance. Silence, a question or an empty reply is not. Write the person's exact words in quotes with the date, and read the item back before you move on. Do not withdraw the notice when the person pushes back, and do not recast a named control as something you can satisfy.

Ask the pre-mortem once, only for a piece that touches a sensitive area, data or the outside world: "Say this went live and went wrong. Who noticed, and what did they see?" Write the answer under Edge cases.

## When the gate refuses ready

The refusal lists every fault it found, and a `next:` line for the first. Report each fault in plain words. Take the step in the `next:` line. Some refusals name a later piece of the kit, such as a measurement judge or a reference judge. Tell the person the piece waits for that part of the kit, and offer to reshape the piece so it does not need it. A missing `Check:` line under Must stay the same needs a command that passes on `main` today.
