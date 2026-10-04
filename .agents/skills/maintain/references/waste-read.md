# Waste read

Before the quarterly visit proposes anything, gather three kinds of waste from
the project as it is now: code copied from one place to another, code nothing
uses any more, and dependencies nothing imports. The proposals then rest on
what is in the project rather than on what the session happened to notice.

This is a whole-project read, so the rules in
the `setup-ai-build-kit` skill's `references/whole-project-reads.md` apply.

## Where it applies

At the quarterly visit, on Build and run it and on Build with care. Not on
Explore privately.

## Engines, best first

| What | JavaScript and TypeScript | Python | Any other language |
|---|---|---|---|
| Copied code | `jscpd --ignore-identifiers --reporters json --output <temporary folder> .` | the same | the same |
| Unused code | `knip --include files,exports --reporter json` | `vulture --min-confidence 100 .` | read the code directly |
| Unused dependencies | `knip --include dependencies --reporter json` | `deptry .` | read the code directly |

The last resort for every row is reading the code directly. Keep that to the
areas the quarterly spread count already named, and say in the internal
evidence that it was the fallback.

Where an engine is not already in the project, `npx` or `pipx run` can fetch it
for this visit without adding it to the project. Ask once before doing that.
If the person says no, use the next entry.

Three settings are there on purpose:

- `--ignore-identifiers` finds a copy whose names were changed after pasting,
  as well as an exact copy.
- At `--min-confidence 100`, `vulture` names only code that certainly cannot
  run: an unused argument, or code after a return. It does not name an unused
  function or import at that setting. Imports are already the linter's job in
  the project check.
- `jscpd` writes a report folder. Point it at a temporary folder outside the
  project, made with `mktemp -d`, so nothing is saved. Leave it there for
  the computer to clear, since a recursive delete is refused.

## Checking a finding

An engine's finding is a lead. Before it becomes a proposal:

- Name the file and line. `knip` and `deptry` name a dependency without a
  line, so find its line in the package file.
- Search the whole project for the name. Code can be reached by a name built
  at run time, a framework convention or a configuration file, and no engine
  sees those. If the name turns up anywhere outside its own definition, drop
  the finding.
- Keep the kind of finding with it. A copied block, an unused export and an
  unused dependency are different claims, and the proposal says which it is.

## Turning findings into proposals

Waste findings join the other hot-spot inputs, and the cap of three proposals
holds for all of them together. Rank a finding higher when it sits in an area
the spread count or a repeated bug already named. Say it in plain words, with
the place:

- "The same total calculation is written twice, in `src/pricing.js` at line 1
  and `src/report.js` at line 1. Keeping one would mean a fix lands once."
- "`discount` in `src/pricing.js` at line 13 is never used."
- "The project lists `left-pad` as something it needs, and nothing uses it."

Say how many more findings there are in one line, and offer to list them.
Remove nothing without a yes.

Whenever a proposal names copied code, or the person asks whether duplication
was checked, say once: "This finds copied code. It does not find two pieces of
code that do the same job written differently." No tool finds that reliably.

When the read finds nothing, say nothing about it. There is no filler
proposal.
