# The check floor

Every founded project gets its language's own mechanical checks on the first
day: a type check and a linter, wherever the language has them. They sit in
the job the capability profile's `Project check:` line records
(`.github/workflows/checks.yml`, job `project-check`, where that line names no
file), beside install and test, so they turn the same tick red.
The person meets no new idea. Green still means the checks that exist really
passed, and red still means don't merge and tell /fix.

This is a whole-project read, so the rules in `whole-project-reads.md` apply.

## Choosing the commands

Use the first of these that the project has:

1. What the project already runs. A type check or lint script in its package
   file, or a configuration its framework's starter created. Use it as it
   stands and do not rewrite its rules.
2. The language's own checker, or its most common one, at that tool's own
   default rules. The table below lists the usual ones.
3. Nothing. Where the language has no type checker or no linter, write
   `Type check: none for <language>` or `Lint: none for <language>` in
   AGENTS.md's stack section and carry on. Never stop founding over this, and
   never invent a tool the language does not have.

| Language | Type check | Lint |
|---|---|---|
| TypeScript | `npx tsc --noEmit` | `npx eslint .` with ESLint's own recommended rules and typescript-eslint's recommended rules |
| JavaScript | none, unless the project already checks types | `npx eslint .` with ESLint's own recommended rules |
| Python | `mypy .` | `ruff check .` |
| Go | the compiler, through `go build ./...` | `go vet ./...` |
| Rust | `cargo check` | `cargo clippy` |

For any other language, the compiler the build already runs counts as the type
check. Add a linter only where the language has one that most of its users run.

## Test runner

A project with no code yet has no test command, and AGENTS.md's stack section
records `Test command: none for <language>`. Its first pieces still need
acceptance checks, so they are written for the runner this table gives for each
language in the type check table:

| Test runner | Language |
|---|---|
| `pytest` | Python |
| `vitest` | TypeScript |
| `vitest` | JavaScript |
| `go test` | Go |
| `cargo test` | Rust |

`Test runner:` names a runner from this table for the language of AGENTS.md's
stack section. Any other language has none. Spec then writes no `Test runner:`
line, so the piece is refused at the ready gate, naming the missing runner. The
ready-gate lint keeps the same table.

## Keep it quiet

A check that goes red for reasons the person cannot act on teaches them to
ignore red, and that is worse than having no check. So:

- Use each tool's own default rules. Do not import a style preset, and do not
  add a formatter check.
- The check passes on the day it is wired. Run it locally before saving, and
  fix what it finds in code founding wrote.
- In an adopted project, the new checks may fail on code that was already
  there. Do not turn the tick red for work nobody asked for. Wire only the
  checks that pass, write the other as `Lint: not yet, <count> existing
  problems` in the stack section, and file one piece to clear them.

Leave `.agents/worktrees/` out of the type check and the lint. A run on Claude
Code builds each piece in a worktree there, a whole second copy of the
project, and a check run from the main folder would otherwise read every copy
as well and report the same problem several times. Use the tool's own setting
for folders it skips, such as ESLint's `ignores`, ruff's `extend-exclude`,
mypy's `exclude` or the `exclude` list in `tsconfig.json`. This only keeps the
copies out. It changes no rule.

Leave it out of the test run too, wherever the project's test runner would find
tests there, or every piece's tests run again from the main folder. Use the
runner's own setting, and keep the folders it already skips on the list:
Vitest's `exclude`, added to `configDefaults.exclude`; Jest's
`testPathIgnorePatterns`, beside `/node_modules/`, and the same entry in
`modulePathIgnorePatterns`, so the copies' `package.json` files raise no
warning; and for Node's own test runner, a test path that does not reach
`.agents/`, naming the project's own test folder.
pytest and `go test ./...` already skip folders whose name starts with a dot, so
they need nothing. Where a runner has no setting to skip a folder, write
`Tests: the runner reads .agents/worktrees/` in AGENTS.md's stack section and
carry on, as for a missing tool.

## Wiring

Put each command in its own named step, `Type check` and `Lint`, after install
and before test, so a red tick says which one failed. In a job of the
project's own, they come with the kit's steps `project-check.md` offers, go in
only on a yes, and sit at the end of its steps. Write the same commands
in AGENTS.md's stack section, so the agent can run them locally before it hands
work over.

## Where it applies

Always, on every build path, in any language that has these tools. On Explore
privately the remote check stays optional, as it is for tests; the commands
still go in the stack section and still run before hand-over.
