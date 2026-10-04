---
name: screen-check
description: Apply the kit's screen rules during a build or review that touches an interface. Read the project's own design system first, report what was applied and what remains for a person to try, and make no claim that the screen is accessible, compliant, or good.
user-invocable: false
---

# Screen check

Apply these rules while a screen is being built, and when that change gets its
build-time review. They shape the first result before the walk-through looks at
it, or the person tries it. They do not run at founding, shaping, or `/ship`.
A fix uses them only when the fault is on a screen.

## When it applies

Run when the piece carries `visual`, or when the changed files render what a
person sees or uses on a screen. Page, view, component, template, style, and
native interface files all count. The file trigger still applies when the piece
missed its `visual` subject. Do nothing when the piece and the change have no
screen.

Read the agreed behaviour, the changed screen files, and any current render or
screenshot that is already available. Do not require a browser or service that
the current coding agent does not have.

## Read the project first

Read `DESIGN.md` when the project has one. Read the `Stack, and how to run and
check it` section of `AGENTS.md` too. A design system or component library named
in either place wins where it conflicts with a house rule below. Say once which
project rule you followed. If the two project records disagree, name the
contradiction instead of choosing one silently.

Do not create `DESIGN.md`, choose a component library, or install anything.
Use only the project files, supplied evidence, and capabilities already
available. Do not fetch, download, install, or call a service to perform this
check.

## Build the screen

Use one spacing scale based on multiples of 4 or 8. Group related things with
space before adding a box around them. Use one accent colour with neutral greys,
and reserve colour for meaning. Colour is never the only carrier of meaning.

Use one productive type scale and no more than two weights. Avoid light
weights. Keep prose lines between 65 and 75 characters where the screen gives
them room.

Design the empty, loading, and error states before calling the happy path
finished. An empty list says why it is empty and what to do next. Use a spinner
for work expected to take 2 to 9 seconds and a real percentage after 10 seconds
where progress can be measured. Skeletons belong only on tables and tiles.

Put a visible label above every field. A placeholder is an example or hint,
never the label. Size a field for the content it accepts. Validate after focus
leaves a filled field, never while an empty field is waiting for input. On
submit, move focus to an error summary even when there is one error. Repeat the
field label in the error and say how to fix it. Do not say "please", "sorry",
"invalid", or "you forgot". Keep the person's entry after an error and never
make them enter the same information again.

Use a list or table for like records, not a set of cards. Give the table the
width it needs instead of placing it inside a smaller container. Keep column
titles short. Right-align numbers and use tabular figures so their digits line
up.

Give each screen one primary action and place it once. On a form, put it on the
left. Prefer undo to confirmation. Confirm only an action that cannot be undone,
with buttons that name the outcome, such as "Delete" and "Keep". Require typing
a name only when the loss is expensive. Return to the list after deletion.

Everything works from a keyboard. Focus stays visible and unobscured. Escape
closes a dialog and returns focus to the control that opened it. Interaction
targets are at least 24 pixels wide and high.

Body text has at least 4.5:1 contrast. Controls, focus, and state indicators
have at least 3:1 contrast. The screen works at 400 pixels wide without
scrolling in two directions. Only a table may overflow its own box.

Use sentence case. Button labels use a verb and a noun. Links do not say "click
here", and instructions do not rely on "above" or "below". Errors use plain
words, name the fix, and take no more than two lines beside a field. The same
thing looks and works the same way throughout the tool.

Put an error beside the thing that failed. Do not hide it in a toast that
vanishes. A modal is for a decision that needs protected focus, such as a final
confirmation, not for reporting an error.

## Refuse the defaults

Unless a project rule deliberately requires one, refuse:

- gradients and gradient text;
- glass or blur used as decoration;
- emoji or text glyphs used as icons;
- cards inside cards;
- all-caps eyebrow labels and hero headings on a product screen;
- the same entrance animation on every section;
- `outline: none` without a visible replacement;
- blocked paste or disabled zoom;
- a placeholder used as a label;
- a toast used for an error;
- a confirmation that asks only "Are you sure?".

## Hand over the screen

Before the guided manual check, say: "I applied the screen rules before your
check, and I will name what they could not prove."

Then report three short parts:

- `Applied:` the project rules and house rules used;
- `Could not check:` rules that the available files and tools could not settle;
- `Try:` the exact action and expected result for the person's guided check.

During a build review, put screen findings inside `Worth stopping for` or
`Worth knowing`. Do not add a screen heading. A finding says which rule was
applied, what was tried, what happened, and what remains untested.

## Claim boundary

Never call a screen accessible, compliant, or good. A rule followed is evidence
only that the rule was applied. Say which rules you applied, which you could not
check, and what a person still has to try. That may include a screen reader, a
real keyboard pass, or a colleague who uses the tool. A conformance or quality
claim needs a person and a method this skill does not provide.

## Reference pointers

The [Vercel Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines/blob/main/AGENTS.md)
give a longer practical checklist. The [WCAG 2.2 quick
reference](https://www.w3.org/WAI/WCAG22/quickref/) owns the accessibility
criteria behind several rules above. These are reading pointers, not run-time
dependencies. Do not fetch either one while applying this skill.
