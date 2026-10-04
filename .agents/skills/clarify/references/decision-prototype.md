# Decision prototype

A prototype answers one decision that conversation cannot settle.

Before building one, check whether the person already has something that answers
it, and follow existing-artifact.md where they do. Building a throwaway to
rediscover a decision they have already made wastes their time and yours.

## Start with the question

Write one sentence:

"This prototype exists to decide whether <question>."

If more than one question appears, split them or return to clarify.

## Which kind of question is it

Say which of these two you are answering, and why, before building anything.
Building the wrong kind wastes the whole prototype, and the person cannot tell
you it was the wrong kind until it is in front of them.

- **Does this behave the way I meant?** They need something they can press
  buttons on and watch happen, driven by them rather than described to them.
  Follow prototype-behaviour.md.
- **What shape should this take?** They need genuinely different arrangements
  side by side, so they can move between them and say which is right. Follow
  prototype-structure.md.

Where a question sounds like both, it is two questions. Split them, and answer
the behaviour one first: an arrangement of something whose behaviour is still
undecided is a guess wearing a layout.

## Rules

- Use fake or disposable data.
- Do not use production credentials.
- Do not connect to live systems unless the question cannot be answered otherwise
  and the build path explicitly allows it.
- Make it trivial to run.
- Show relevant state after actions.
- Skip production error handling, abstractions, and polish.
- Do not treat prototype code as production code.
- Build the visible thing to look like what it is testing, not like a labelled
  prototype. A tax calculator's screen is titled "Tax Calculator", not "This is
  a Tax Calculator" or "Tax Calculator prototype". Narrating in the interface
  that it is a prototype changes what the person sees and makes the decision
  harder to judge.
- Let the user try alternatives where the decision is visual or behavioural.

## Finish

Record:

- question;
- what was tried;
- decision;
- rejected alternative and why, when useful;
- what the production build must preserve.

Delete the prototype or isolate it clearly. Where it is saved, remove it with
`git rm -r`. Where it is an unsaved folder, give the person the command that
removes it, with its path, since a recursive delete is refused. Keep it only
when it remains useful evidence, and never let it silently become the
production implementation.
