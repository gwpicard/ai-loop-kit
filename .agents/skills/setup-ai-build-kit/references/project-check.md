# The project check record

The project check is the automatic check that runs on every pull request and
shows the green tick or the red cross. A project the kit founds from nothing
gets the kit's own, `checks.yml`. A project the kit adopts may already run its
tests on every pull request in a workflow of its own, and that workflow is
then its project check. Founding records which file and job it is, and adds no
failing placeholder beside it. Every skill that reads or edits the check reads
that record first.

This covers GitHub Actions only. A project on another CI service is founded as
one with no CI.

## Which workflow counts

A workflow counts where its file in `.github/workflows/` ends in `.yml` or
`.yaml`, runs on `pull_request`, and has a `run:` line containing the word
`test`. The bootstrap script looks for one the same way. Where it finds one,
it copies no `checks.yml` beside it and prints one line naming the file.

Four workflows look close and do not count:

- The kit's own placeholder `checks.yml`, whose `Install and test` step says
  no tests have run, never counts, although that sentence contains the word.

- A workflow on pull requests that runs no tests, such as a labeller, is not a
  project check. The project's workflows stay as they are, and the kit's
  `checks.yml` is copied and recorded as for a project with no CI.
- A workflow that runs only on `push` is not a pull request check. The kit's
  `checks.yml` is copied. Say in one line that the project's own workflow
  stays as it is.
- A `checks.yml` the project already had, that is not the kit's placeholder, is
  kept, as every file the project already had is kept. Choose its job by the
  rules below, like any other workflow of the project's.

## Choosing the job

Take the first of these that applies:

1. the job whose steps run the test command AGENTS.md's stack section records;
2. else the first job, by file name then job name, triggered on pull requests
   with a `run:` line containing `test`;
3. else none. No job of the project's runs tests, so copy the kit's
   `checks.yml` where it is missing and record it, as for a project with no CI.

Say in one line which file and job you chose, so the person can say otherwise,
close to: "Your own check, the `test` job in `.github/workflows/ci.yml`, stays
the one that runs on every pull request." A workflow with several jobs and no
test command recorded yet takes the second rule, and that line names the job.

## The record

Write the choice into AGENTS.md's capability profile as one line:
`Project check: <workflow file>, job <job name>`, for example
`Project check: .github/workflows/ci.yml, job test`. A project with no CI of
its own records `Project check: .github/workflows/checks.yml, job
project-check`. A profile line that names no file means that same default, so
an older project keeps working unchanged.

## The kit's steps

The kit's own check carries two steps a project's workflow does not:
`Check sensitive-area map` and `Check the AGENTS.md ceiling`. Offer once to add
them to the chosen job, copied word for word from the installed skill's
`templates/foundation/checks.yml`, with the type check and linter from
`check-floor.md` where the job runs neither. Say that this changes the
project's own automation, and what each step turns red on: the map step on a
sensitive area whose listed paths no longer exist, the ceiling step on an
AGENTS.md above 200 lines, and the type check and linter on the problems their
tools report.

- On a yes, add them to the end of that job's steps and change nothing else in
  the file.
- On a no, add nothing and append `; kit steps not added` to the profile line.
  The completion report then says that the ceiling and the map are measured
  only by `/maintain`.
- Where the job's `runs-on` names a Windows runner, do not offer them. The kit's
  steps are written for a POSIX shell. Say why in one line, and record `; kit
  steps not added`.

Both steps need only `sh` and `awk`, and both read files from the project
root. A job on a container image without those tools, or one whose
`defaults.run.working-directory` points below the root, turns red on the first
pull request after a yes, and the fix loop then names the step. Where the job sets
such a folder, give each added step `working-directory: .` so it runs from the
root.
