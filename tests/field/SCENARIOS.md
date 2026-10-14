# Field scenarios

The unit tests check the kit's code with a stand-in builder. These scenarios
check the whole loop with real Claude Code sessions on real GitHub
repositories. They answer four questions after every change to the kit:

- What works? The scenarios that pass.
- What breaks? A broken audit rule, or a hand repair.
- What is missing? A scenario that cannot finish without a person.
- Is it still reliable? The same scenarios, run again, give the same result.

## How to run a scenario

1. Use the test repository the scenario names, or make a new public one.
   Install the kit from this repository with `claude --plugin-dir <kit>`.
2. Do the steps as a person would: `/ai-loop-kit:setup`, `/ai-loop-kit:shape`,
   `/ai-loop-kit:run`, then merge on GitHub and run `gate.py sync`.
3. Write down every time you had to step in by hand. That is a hand repair.
4. In the test repository, run:

   ```
   python3 <kit repo>/tests/field/audit.py --doctor
   ```

   It checks the rules on GitHub and scores each piece. It changes nothing.
5. Add one row to `RESULTS.md`.
6. A broken rule, a hand repair or a false statement from the kit goes into
   `docs/LEDGER.md` the same day. If it is the second time for one cause, it
   earns a fix: a test that shows the failure, then the fix.

## What the audit checks

Rules. A broken rule is a kit failure:

- **one-state**: each piece has exactly one state label.
- **records**: every state change has a gate record, in a listed move, and
  the last record names the current state. A label set by hand breaks this.
- **needs-you**: the flag is only on a piece in shaping.
- **merged**: a done piece has a merged pull request and a closed issue.
- **bar**: the judge files in the pull request are the ones fixed at ready.
- **generated**: the pull request holds no generated files.
- **doctor**: main passes `gate.py doctor` (with `--doctor`).

Scores, for each piece: builds, attempts, times sent back, and whether a
person changed the pull request after the gate judged it.

## The scenarios

| Name | Repository | What it proves | Last run |
| --- | --- | --- | --- |
| new-project | loop-test-thin | An empty repository becomes a working project: setup, a scaffold piece, then feature pieces. | 13 Oct 2026 |
| existing-python | loop-test-existing | The loop works in an existing Python project with its own tests and a `.venv`. | 14 Oct 2026 |
| existing-node | loop-test-node | The loop works in an existing Node project, with a Prepare command. | 14 Oct 2026 |
| wrong-bar | loop-test-thin | A judge that contradicts itself fails every attempt. The piece returns with `needs-you` and the builders' reasons. It is reshaped and built. | 13 Oct 2026 |
| rejected-pr | loop-test-node | The person rejects a pull request with a reason. The piece is fixed without hand work on the branch. | 14 Oct 2026: failed, five fixes, then passed on the re-run |
| docker | new | A project that builds and tests only in Docker. Prepare is `docker compose build`. | not run |
| conflict | loop-test-thin | Two pieces in one run change the same lines. The second pull request conflicts after the first merges. The kit says so plainly and recovers. | not run |
| hard-piece | any | A piece that a real builder cannot pass on the first attempt. Later attempts use the judge's output and pass. | not run |

### new-project

- Setup: a new empty public repository with a README.
- Steps: setup; a scaffold piece; at least three feature pieces, two of them
  in one run.
- Must hold: every audit rule; each piece done; the project's tests pass on
  main after each merge.

### existing-python

- Setup: a public copy of a small, well-tested Python library.
- Steps: setup, with a Prepare command that makes the `.venv`; one feature
  piece that keeps the old tests green (`Keep:`).
- Must hold: every audit rule; doctor passes before the first piece.

### existing-node

- Setup: a public copy of a small, well-tested Node package.
- Steps: setup with `npm install` or `npm ci` as Prepare; one feature piece.
- Must hold: every audit rule; shaping does not put install steps in `Keep:`.

### wrong-bar

- Setup: write a piece by hand whose Done when items contradict each other.
- Steps: run it; read the returned issue; reshape; run again.
- Must hold: three failed attempts; each failure comment holds the builder's
  own words; the piece is in shaping with `needs-you`; then done after the
  reshape. No builder changes the judge.

### rejected-pr

- Setup: any project with a piece in approval.
- Steps: reject the pull request with a reason; let the kit fix it.
- Must hold: no hand edits on the piece branch; no force push; the piece
  never sticks in building; the next build's brief holds the reason; the
  audit shows the piece sent back once and built twice.

### docker

- Setup: a new public repository with a `Dockerfile` and `compose.yaml`; the
  tests run only inside the container.
- Steps: setup must offer Docker commands for Prepare and Test; one piece.
- Must hold: every audit rule; doctor passes; no tool installed on the host.

### conflict

- Setup: two pieces that both change one function in different ways.
- Steps: shape both, run both in one run, merge the first.
- Must hold: the kit never claims the second pull request merges cleanly
  when it does not; the person gets a clear next step; no work is lost.

### hard-piece

- Setup: a piece with an exact output format, or a tricky edge case.
- Steps: run it with three attempts.
- Must hold: every audit rule; each later attempt gets the earlier judge
  output; the builder never changes the judge.
