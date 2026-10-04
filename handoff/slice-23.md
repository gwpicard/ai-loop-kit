# Slice 23: People can install AI Loop Kit 1.0 from a public repository, and its commands, records and way of building hold until 2.0

Labels (today's set): enhancement, area:release, ready-able once shaped. Release label for the PR: release-major, which carries the version suggestion to v1.0.0.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 22: Set AI Loop Kit's names, and through it every earlier slice.

## So that
A person starting a new project installs AI Loop Kit 1.0, whose commands, records and way of building will not change underneath them, and a person whose project was founded with AI Build Kit is told plainly that it stays on that kit.

## Done when

### Works

Part a: ready to release (no online change)
- Every item of the design note's 1.0 bar holds, each by its own check, on the commit to be stamped: all four loop modules, runs, kickback, `/deploy` and both boards (the rehearsals slices 7, 9, 11, 12, 14 and 16 added, passing in `.agents/tests/run-all.sh`); one real run for each loop module and one `/deploy` for each recipe (`.agents/tests/real-runs.sh` and both recipe rehearsals); the compact masterplan (slice 18's template check). Check: guided check: the maintainer runs `.agents/tests/run-all.sh` and `.agents/tools/validate-kit.sh` on that commit and both pass, and writes the commit into the release log.
- MAINTAINING.md's "Trying unreleased work as a person would" walks the v1 day on a preview: found with `/setup-ai-loop-kit` on the Vercel recipe, `/shape` one piece to `state:ready`, `/implement` a run of one and then a run of two, read both boards, `/deploy` once, and a `/maintain` visit. The founding checks read `.ai-loop-kit-maintenance`, the teardown removes every item the run made, including the preview's own database. Check: `.agents/tests/pre-release-run.sh`, updated to hold the v1 steps, the new record name, the preview database in the teardown, and the existing safety rules unchanged.
- The guide-removal tests slice 17 added are run once on the release commit and their results recorded in the release log: for each guide, whether removing it changed a replayed outcome. Check: guided check: the log names every guide in the list slice 17 keeps.
- The three version-bearing files carry `1.0.0` on `main`, through a pull request aimed at `main` and labelled `release-major`. Check: `.agents/tools/stamp-version.sh --check v1.0.0` passes, and `.agents/tests/version-stamp.sh` passes.
- The pre-release run is carried out on a preview built from the stamped `main`, and a dated log records each check and whether it held. A failure is filed as an issue, and the release waits for the maintainer's decision on it. Check: guided check: the log exists in the release pull request's description and names the preview version and commit.

Part b: the release (the maintainer approves each online step)
- One draft Release exists, named `v1.0.0`, and no other draft. Check: guided check: `gh api repos/gwpicard/ai-loop-kit/releases --jq '.[] | select(.draft) | .tag_name'` prints only `v1.0.0`.
- The draft's notes open with who the kit is for: AI Loop Kit is for new projects, and a project founded with AI Build Kit stays on that kit, which keeps fixes on its 0.19 line for a stated period. They then give the six commands and the way a piece goes from shaping to a merged run, and the install lines for each route. They name no migration and no command from AI Build Kit. Check: guided check: the maintainer reads the draft against this list before publishing.
- `prepare release` runs with `v1.0.0` and attaches `ai-loop-kit-v1.0.0.tar.gz` to the draft. Check: guided check: the workflow run is green and the draft lists one archive.
- The repository gwpicard/ai-loop-kit is made public, on the maintainer's yes, just before the draft is published (decision 59). Check: guided check: `gh api repos/gwpicard/ai-loop-kit --jq .visibility` prints `public`.
- The draft is published, `verify release` passes, and `stable`, which does not exist before this release, is created at the tag by `promote-stable.sh`. Check: guided check: `git ls-remote origin refs/heads/stable refs/tags/v1.0.0` prints one commit twice.
- Each installation route delivers 1.0 in a throwaway folder: `npx skills add gwpicard/ai-loop-kit` gives a maintain skill whose `VERSION` reads `v1.0.0`; `claude plugin install ai-loop-kit@ai-loop-kit` in an isolated configuration reports `1.0.0` in `claude plugin list --json`; the Agent Plugins folder from the release archive carries `1.0.0` in its `plugin.json`. Check: guided check, each command and its output in the release log.

Documents this slice touches
- MAINTAINING.md: "When a release is cut" names the 1.0 promise (commands, records and the way work is built do not change underneath a person until 2.0) and that a change breaking it is a major release; "Trying unreleased work as a person would" as above. Check: `.agents/tests/pre-release-run.sh`, and a new rule in `.agents/tests/version-stamp.sh` that reads the 1.0 promise from MAINTAINING.md.
- README.md and COMPATIBILITY.md say the kit is 1.0 where they name a version or a stability promise, matching the design note's 1.0 section. Check: `.agents/tests/one-story-v1.sh` from slice 21, extended with the promise sentence.
- Root `AGENTS.md`'s entry for `pre-release-run.sh` describes the v1 run. Check: `.agents/tests/one-story-v1.sh`, maintainer-checks half.

### When it is not the normal case
- Release Drafter names the draft something other than `v1.0.0` after the stamp merges: run `update release draft` from the Actions page; if the draft still names another version, the maintainer deletes it with a yes and runs `update release draft` again. `prepare release` refuses a draft naming another version, so nothing is published from the wrong one. Check: `.agents/tests/release-publication.sh` (the refusal), guided check (the draft list).
- Another pull request merges after the stamp: nothing merges between the stamp and the publication, as MAINTAINING.md requires; if one does, `prepare release` runs again so the archive matches the draft. Check: `.agents/tests/release-publication.sh` (repeat leaves one archive).
- The pre-release run finds a failure: it is filed as an issue in the person's words, the release waits, and the maintainer decides whether it is fixed first or named in the notes. Check: `.agents/tests/pre-release-run.sh` holds the rule.
- `verify release` fails: `stable` is not created, so no installation receives 1.0, and the release is investigated before anything else merges. Check: `.agents/tests/stable-is-the-channel.sh`.
- An installation route fails after publication: the release stays published, the failure is filed, and the notes gain a line saying which route is affected and what to run instead, edited in the Release's web page so the tag is kept. Check: guided check.

## Masterplan change
Design note: "1.0" (the promise and its three conditions, migration having left the bar by decision 63) and "Projects founded with AI Build Kit" (no move; those projects stay on the 0.19 line). No change to the note.

## Not in this piece
- Building any of the conditions in the 1.0 bar: slices 1 to 22.
- The real runs themselves: slice 20: Replay harness rewrite and real runs.
- The name change on GitHub: slice 22: Set AI Loop Kit's names.
- A Codex grade above expected to work: slice 19: Codex parity, and not a 1.0 condition.

## Decided
- No release is cut in gwpicard/ai-loop-kit until v1 is complete, and its first published release is v1.0.0 (decisions 52 and 59). The old repository's unpublished v0.20.0 draft is deleted there, by the move plan, not here.
- 1.0 needs the three conditions in the design note and nothing more: the model complete, real runs recorded, the compact masterplan (decision 26 as amended by decision 63).
- The version is set by the `release-major` label and the stamp, through the existing Release Drafter, prepare, publish, verify and `stable` machinery; no step of that machinery changes for 1.0.
- The pre-release run as a person is required for this release, because it touches founding and replaces `/ship` (MAINTAINING.md: "Do this before any release that touches founding or `/ship`").
- The repository becomes public at this release and not before (decision 59), so a free private repository's lack of branch protection ends here, and `stable` is created at the first tag (the move plan, step B3).
- Making the repository public, publishing, deleting a draft and every other online step wait for the maintainer's yes at that step (root `AGENTS.md`, "Secrets and external changes"). Part b is written in the piece as a "Waiting on you" list, so today's `/implement` builds Part a and leaves Part b to the maintainer.

## Data
- In this repository: the three version-bearing files (`.claude-plugin/plugin.json`, `agent-plugin/plugin.json`, `.agents/skills/maintain/VERSION`) carry `1.0.0`; MAINTAINING.md's release sections change.
- On GitHub: the repository becomes public, the `v1.0.0` Release and tag are published, and `stable` is created at the tag through the release job.
- In installed projects: nothing changes for a project founded with AI Build Kit (decision 63); a new project founds on 1.0.

## Leaves the tool
The stamp pull request, the Release, its notes and its archive go to GitHub. The pre-release run creates a throwaway repository, host project and database on the maintainer's accounts, all removed in its teardown. Each is an online step that waits for a yes.

## Must still hold
- Installers read `stable`, and only a verified release moves it. Check: `.agents/tests/stable-is-the-channel.sh`.
- A pull request aims at `main`, never `stable`. Check: `.agents/tests/pull-request-base.sh`.
- Every merged pull request carries a release label. Check: `.agents/tests/release-label.sh`.
- Only the allowlist ships, and no maintainer-only file reaches the release. Check: `.agents/tests/release-builder.sh`, `.agents/tests/agent-plugin.sh`.
- The pre-release run keeps its safety rules: no password in the chat, scopes taken off again, no recursive forced delete. Check: `.agents/tests/pre-release-run.sh`.
- No issue numbers and no attribution lines in any tracked file or in the release notes. Check: `.agents/tools/validate-kit.sh` for files; the maintainer's read of the draft for the notes.

## Relies on
- `.agents/tools/stamp-version.sh`, `.github/workflows/prepare-release.yml`, `verify-release.yml`, `release-drafter.yml`, `.agents/tools/promote-stable.sh`, `.agents/tools/build-release.sh` (all present on `main`).
- `.agents/tests/pre-release-run.sh` and MAINTAINING.md's "Trying unreleased work as a person would" (present).
- The new names and the release archive name from slice 22: Set AI Loop Kit's names.
- `.agents/tests/real-runs.sh` from slice 20, `.agents/tests/one-story-v1.sh` from slice 21, the guide-removal tests from slice 17.

## Reach and risk
Boundary: the version-bearing files, MAINTAINING.md's release sections, the pre-release run steps, the repository's visibility, the Release on GitHub, the `stable` branch through its job.
Reaches: every installation route (`claude-plugin.sh`, `agent-plugin.sh`, `starter-rehearsal.sh`, `plan-helper-routes.sh`), the release machinery (`release-publication.sh`, `version-stamp.sh`, `stable-is-the-channel.sh`), a new project founded on 1.0 (the pre-release run stands in for one).
If it breaks: a person installing 1.0 finds a route that fails, or a founding that stops; they see it at install or founding. A published release cannot be un-published; the repository's visibility can be set back to private on a yes, and a fix ships as v1.0.1.
Depends on: 22.
Loop module: build for Part a, because the stamp and the rewritten pre-release steps are checks that fail today; Part b is the maintainer's own steps.
Crew: default for build.

## Under the hood
Part a rewrites MAINTAINING.md's pre-release run for v1 and updates `pre-release-run.sh` to hold it, adds the 1.0 promise to "When a release is cut", runs the 1.0 bar's checks and the guide-removal tests, stamps `v1.0.0` with `.agents/tools/stamp-version.sh` on a branch, and opens the pull request to `main` with `release-major`. The maintainer then carries out the pre-release run on a preview from the stamped `main`. Part b follows the existing release order in MAINTAINING.md: draft, prepare, review notes, make the repository public, publish, verify, `stable`, then the route checks.

Existing rehearsals expected to change: `pre-release-run.sh` (v1 steps), `version-stamp.sh` (the promise rule), `one-story-v1.sh` (the 1.0 sentence). Nothing from the overnight batch branch is reused.

Kit rules: no canonical skill changes, so the five questions are not owed; MAINTAINING.md's release checks (the upgrade question, the five questions over everything, the SOURCES.md sweep) are run and their answers written in the pull request; validator and `run-all.sh` pass; the humanizer and house rules apply to the release notes, which are human-facing prose; no issue numbers; no attribution lines.

## Evidence
The rehearsals named above passing on the stamped commit, a dated pre-release run log, the green prepare and verify workflow runs, `stable` matching the tag, and a recorded install on every route.

## Size
Two sittings: Part a (the rewrite, the checks and the stamp) in one; the pre-release run and Part b in a second, with the maintainer present throughout.

## Consistency notes
- Decision 63 takes migration out of the 1.0 bar: the bar is the model complete, real runs recorded and the compact masterplan. The draft's founded-project move, its v0.19.2 test folder and its old-address install check are gone.
- This release is cut in gwpicard/ai-loop-kit, which has no earlier release, no v0.20.0 draft and no `stable` branch before it. The v0.20.0 draft and the stranded-plugin commands belong to the old repository and its 0.19 line.
- The repository becomes public at this release (decision 59), as an online step on the maintainer's yes.
- The record file the pre-release run reads is `.ai-loop-kit-maintenance`, named by slice 22.
