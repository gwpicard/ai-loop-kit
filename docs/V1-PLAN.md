# v1 build plan

The plan for building v1 in one pass on the branch `kit/v1`. `docs/V1.md` is
the definition. This file is the order of work. Delete it when v1 merges.

## How this build is different

For v1 the earn rule is suspended: the features come from the plan, not from
a failed run. The rule comes back when v1 merges. The build works in this
order:

1. Build every work package below, each as one or more commits on `kit/v1`.
   Write unit tests for new code as you go, in `tests/`, in the style of
   `tests/test_loop.py`.
2. Do not run the whole suite or wait for CI after each package. Run only the
   tests you are writing, when it helps.
3. At the end, run `tests/run-all.sh` and `tests/house-rules.sh`, and fix
   everything until both pass.
4. Then the rehearsals (below) run, and their findings are fixed.

Keep the house rules: British spelling, plain short sentences, no em dashes,
no issue or pull request numbers in tracked files, no recursive deletes,
never push to `main`, never force-push. Python standard library only, Python
3.9 or later. Keep the existing behaviour that `docs/LEDGER.md` lists as
earned; each earned row has a test, and those tests must still pass.

## Work packages, in order

### W1. Contract format and parser
- New spec sections: `## Intent` (with an `Out of scope:` list),
  `## Approach` (optional), `## Contract` (replaces `## Done when`; keep
  reading `## Done when` as an old name), `## Judge` with `Kind:` one of
  `feature`, `fix`, `scaffold` (default `feature`).
- The gate refuses ready when Intent is empty, `Out of scope` is empty or
  missing, or a Contract item has no ID.
- Update `kit/spec-format.md` to the new format, with one `feature` and one
  `fix` example.

### W2. Typed reasons, report, spec command
- Every move back takes `--type` with one of `spec-unclear`, `bar-wrong`,
  `environment`, `builder-failed`, `person-rejected`, `conflict`, plus
  `--reason`. The record comment holds both. The run picks the type itself
  (three fails: `builder-failed`; early stop: `bar-wrong`; Prepare or other
  errors: `environment`; merge conflict it cannot hand over: `conflict`).
- A builder can end an attempt with the outcome "the bar is wrong" by writing
  `.loop/outcome` with `bar-wrong` and a reason. The run then gives the piece
  back at once with that type, without more attempts.
- `gate.py report`: counts by type and by piece, from the records, in plain
  lines.
- `gate.py spec <n> --body-file <file>`: replaces the spec of a piece in
  shaping only. Skills use it in place of `gh issue edit`.
- Remove the `rebuild` move (it has no caller).

### W3. Run lock, recovery and stop
- `run.py` takes `.loop/run.lock` (process id and start time). A second run
  refuses with a `next:` line. A lock whose process is dead is taken over.
- At start, any piece in building with no live run goes back to shaping,
  type `environment`.
- `gate.py stop` writes `.loop/stop`. The run checks it between attempts and
  between pieces, stops cleanly and removes it.
- Each attempt prints its elapsed time and its log path.
- Every judge, `Keep:` and quality run has a hard timeout and kills the whole
  process group.

### W4. Judge quality
- New `kit/scripts/testlint.py`, run by the gate at ready on the judge files:
  - Python (stdlib `ast`): a test function with no `assert`, no
    `pytest.raises` and no call whose name starts with `assert`; `assert True`;
    `assert x == x` or literal on both sides; `pytest.mark.skip`, `skipif`,
    `xfail`.
  - JavaScript and TypeScript (plain text scan): a `test(` or `it(` block with
    no `expect(` or `assert`; `.only(`, `.skip(`, `xit(`, `xdescribe(`;
    `expect(true)`.
  - Each finding names the file, line and rule. Any finding refuses ready.
- The bar grows: besides the judge files, the gate hashes every
  `conftest.py` and every non-judge file under the judge's folder.
- At submit the gate refuses an attempt that changes any existing test file,
  `conftest.py` or fixture not named in the Contract or under `Files:`.
- At submit, a judge or `Keep:` output that reports skipped tests fails the
  attempt (pytest and vitest or jest summary lines).

### W5. Quality commands
- The loop section of `AGENTS.md` may list `Quality:` commands, one per line.
- The gate runs each after the judge and `Keep:` pass, at submit. A failure
  fails the attempt, with the command's output in the record.
- Setup proposes defaults per stack and writes them only on the person's yes:
  Python: a `mutmut` command scoped to changed functions; Node: Stryker with
  `--mutate` on changed line ranges and `--reporters json`, and ESLint's
  `complexity` rule. Setup says each is optional and what it costs in time.
- `kit/quality/` holds the small helper scripts these defaults need (for
  example, changed line ranges from `git diff -U0`).

### W6. Roles: judge writer and reviewer
- `kit/agents/judge-writer.md`: a subagent definition (model `sonnet`). It
  gets the issue's Intent, Approach and Contract and the code, never the
  shaping conversation. It writes the judge files on `piece/<n>`, tests call
  the public interface, one test per ID, each file starts with a one-line
  intent comment. The shape skill calls it at its judge step, then runs the
  project's Test command on the judge and `gate.py check`.
- `kit/briefs/reviewer.md` and a review step in `run.py`: after the gate
  passes an attempt, a fresh `claude -p` reviewer reads the diff and the
  project's standards file (`Standards:` in the loop section of `AGENTS.md`;
  skip the review when none is named). It may commit small fixes. It may not
  change tests, the judge, check settings or protected paths (same guard as
  builders). Then the gate runs every submit check again. If any fails, the
  run drops the reviewer's commits (they are local and unpushed) and goes on
  with the judged commit. The pull request says what the reviewer changed.
- The builder brief gains the Approach section and loses any coding standard
  text.

### W7. Pull request for a person
- The run builds the pull request body from facts: files changed by area,
  tests added, new dependencies (diff of `package.json`, `pyproject.toml`,
  `requirements*.txt`), risk flags (protected paths, migrations, config, CI,
  check settings), the number of project files that import a changed module
  (Python `ast` imports, a plain scan of `import` and `require` for Node),
  and a revert note (number of files, any migration).
- The builder writes `.loop/why.md`: why this change, and what could go
  wrong, two short paragraphs. The run puts it in the body.
- Evidence: judge output, `Keep:` and quality results, bar hash, judged
  commit, review changes.

### W8. Boundary
- `guard.py` reads `git -C <dir>` and `git -c <k=v>` before the subcommand,
  `gh -R` and `--repo` before the subcommand, and unwraps `bash -c`,
  `sh -c` and `zsh -c` strings. It refuses `shutil.rmtree` and `rm -r`
  spellings inside `python -c` and `node -e`. A form it cannot read in a
  build session is refused, with a reason. Keep `GIT_CONFIG_COUNT` from
  triggering anything. Add a test per bypass found in the review: `git -C .
  push origin main`, `bash -c "git push --force origin x"`, `gh -R a/b pr
  merge 3`.
- `Protected paths:` in the loop section of `AGENTS.md`. The guard refuses
  builder and reviewer edits there; the gate refuses a diff that touches them
  unless the Contract names the path.
- A secret check at submit: the diff must not hold private key blocks,
  `AKIA` keys, `ghp_` or `github_pat_` tokens, `sk-` keys or `.env` files.
- Setup offers branch protection on `main` with `gh api`, only on the
  person's yes and only where GitHub allows it (public repositories, or paid
  plans). `doctor` reports whether `main` is protected, as a plain line, not
  a failure.

### W9. Skills
- `shape`: the new contract; the judge writer at the judge step; `gate.py
  spec` for edits; the person approves the final contract text, and the
  skill never changes an approved item without asking again; `fix` pieces
  start by reproducing the bug.
- `run`: typed reasons on reject, `gate.py stop`, `gate.py report`, how to
  drop a piece.
- `setup`: Quality commands, the standards file, protected paths, branch
  protection offer, all on the person's yes.

### W10. Documentation
- `README.md`: point to `docs/V1.md` for how it works; update the quick start
  and the limits.
- `docs/ANGLE.md`: the five principles and the four parts, short; note that
  v1 was built from a plan and the earn rule applies again after it.
- `CHANGELOG.md`: a `## 1.0.0 (in progress)` section.
- `kit/.claude-plugin/plugin.json`: version `1.0.0-dev`.
- `docs/LEDGER.md`: mark each ledger idea that v1 now holds as in the kit,
  with "v1 plan" as the source.

## End of build

- Run `tests/run-all.sh` and `tests/house-rules.sh`. Fix until both pass.
- Check `kit/` stays near 2,500 lines of Python: `wc -l kit/scripts/*.py kit/hooks/*.py kit/quality/*`.
- Push `kit/v1` and open one draft pull request against `main`. Do not merge.

## Rehearsals, after the build

Run by Claude with the plugin from the branch
(`claude --plugin-dir <worktree>/kit`), in the existing test repositories:

| Repository | Rehearsal |
| --- | --- |
| loop-test-install (Python) | setup with Quality, standards and protected paths; one `feature` piece; one `fix` piece for a real bug; a review that commits a fix |
| loop-test-node (Node) | one `feature` piece with Stryker as a Quality command |
| loop-test-thin (Python) | a piece whose bar is wrong: the builder reports `bar-wrong`; then `gate.py report` |
| any | a hostile builder brief that tries the three guard bypasses and a `conftest.py` change: all refused |
| any | kill a run mid-build; the next run recovers the piece; `gate.py stop` stops a run |

Each finding goes in `docs/LEDGER.md` with a test, then a fix, on `kit/v1`.
v1 merges when every rehearsal passes.
