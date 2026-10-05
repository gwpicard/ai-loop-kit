# Boundary rules

An area may name one boundary it must not cross. A boundary line sits under
its area in `docs/working-rules.md`, indented, in the Areas section the fit
check describes. On its own that line is a description: a build that crosses
it gets one sentence, and the person may leave it. A boundary rule turns the line into part
of the project check, so a change that crosses it turns the tick red, and the
red check carries the person's own sentence.

This is a whole-project read, so the rules in `whole-project-reads.md` apply.

## Where it applies

On Build with care, for an area that already has a `boundary:` line. Offer it,
never impose it. It is offered at two moments: during founding, once the map is
written, and at the quarterly visit, for an area named or given a boundary
since the last one. Never invent a boundary the map does not name.

## Asking

Ask once for each area: "Should the check hold this boundary, so a change that
crosses it cannot be merged?" If the answer is yes, ask the person to say the
rule in their own words, and read it back. For example: "Nothing outside
billing touches the ledger except through the charge step."

Add no rule without a yes, and take one away only with a yes too. Record the
yes on the area's boundary line, with the sentence:

```md
  boundary: reached only through src/billing/charge.ts; held by the check: "Nothing outside billing touches the ledger except through the charge step."
```

## Engines, best first

| Language | Engine | Check command |
|---|---|---|
| JavaScript and TypeScript | dependency-cruiser | `npx depcruise --config .dependency-cruiser.cjs --output-type err-long <source folder>` |
| Python | import-linter, with a `protected` contract named with the person's sentence | `lint-imports` |
| Go | depguard, through golangci-lint | `golangci-lint run` |

A project that already enforces its boundaries with another tool, such as
eslint-plugin-boundaries, keeps that tool, and the rule is added there.

Where the language has none of these, say so in one line, write `Boundary
rules: none for <language>` in AGENTS.md's stack section, and withdraw the
offer. Never imitate a rule with a script that only looks like one.

For dependency-cruiser, write one entry for each held boundary. The comment is
the person's sentence, word for word, because that is what a red check shows:

```js
module.exports = {
  forbidden: [
    {
      name: '<area>-boundary',
      comment: '<the person\'s sentence>',
      severity: 'error',
      from: { pathNot: '^<area folder>' },
      to: { path: '^<area folder>', pathNot: '^<entry file>$' },
    },
  ],
};
```

Write a path as a pattern: `src/billing/` becomes `^src/billing/`, and a full
stop in a file name is written `[.]`.

## Wiring

Put the check command in its own step named `Boundary rules`, in the job the
capability profile's `Project check:` line records
(`.github/workflows/checks.yml`, job `project-check`, where that line names no
file), after the type check and lint steps from `check-floor.md`, so a red tick
says which one failed. Name the same command in AGENTS.md's stack section. Before saving, run
it once on the project as it stands. It has to pass. A rule that is red on the
day it is added is a rule about work nobody asked for, so say what already
crosses the boundary and let the person decide whether to fix that first or
leave the rule out.

## When it goes red

The check names the importing file and the person's sentence. The fix loop reads
it like any other failure, once `/shape` has the report. Describe it to the person with their own sentence:
"This change broke your rule: nothing outside billing touches the ledger except
through the charge step. `src/reports/sum.ts` reaches the ledger directly."

## At the quarterly visit

The ownership check already asks whether each named area is still accurate.
When an area changes or comes off, its rule changes or comes off with it, with
the person's yes.
