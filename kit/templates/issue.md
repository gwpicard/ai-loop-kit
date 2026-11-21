## Goal

One or two sentences: what changes for the user, and why.

## Acceptance criteria

- [ ] A criterion an agent can check by running something or reading an output.
- [ ] Three to six of these. Each one is true or false.
- [ ] Name the exact behaviour, not the method.
- [ ] For behaviour a person triggers, name the entry point: the keys pressed,
  the menu item chosen, the command run or the HTTP route called.

## How an agent checks it

The oracle: the command, render or measurement that shows the work is right.
If nothing can show it, say so; the first issue then builds that check.

## Hands-on check

Optional. Numbered steps a person follows in the real product, each with the
result to expect, for example `1. Press Save. Expect a saved message.` The
final pull request lists them as unticked boxes; the loop never waits for
them. Omit this section when an agent can check everything.

## Failing test

Optional. A test that fails now, found by the end-of-loop pass. The test
writer commits it as given. Omit this section otherwise.

## Protected paths this issue may change

One path per line: protected paths, lockfiles, manifests, settings files or
existing tests the builder may change or delete. The builder may change every
other file. The usual value is `none`.

## Depends on

Depends on: #a, #b

## Notes

Decisions that bind this issue, links to standing rules, files to start from.
