# MAINTAINING.md: notes for the kit's own maintainers

This file is for people working on the kit itself. The release allowlist keeps
it out of the kit a project receives.

## This repository is the kit's source

The distinction is easy to lose in the middle of a session, and losing it has
produced the same mistake more than once.

- None of the project records exists here. `masterplan.md`
  and `CHANGELOG.md` are created by `/setup-ai-build-kit` from
  `.agents/skills/setup-ai-build-kit/templates/`, so the installed setup-ai-build-kit skill can prepare
  someone's project. The kit's own history lives in commit
  messages and release notes, not a root `CHANGELOG.md`.
- Root `AGENTS.md` carries the source-maintainer rules.
  `.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md` carries the rules that
  start places at the root of a project.

- A fresh clone runs one command before its first commit:
  `git config core.hooksPath .githooks`. The hook in that folder takes AI
  attribution lines and session links back out of a commit message. Git finds a
  hook through `core.hooksPath`, which is a local setting, so a clone does not
  inherit it and nothing warns you that it is missing. Root `AGENTS.md` says why
  the rule exists and what else holds it shut.

The eight user-facing commands are product under test here, not the source
repository's own operating workflow. Maintainer changes follow root `AGENTS.md`
and this guide.

## How the issues are organised

The kit's own work is tracked in this repository's GitHub issues. The scheme is
native, needs no organisation account, and carries no dates, because the work is
not on a deadline. Follow it so the board stays legible.

An **epic** is one issue that describes an initiative, with the work under it as
**sub-issues** (GitHub's own parent and child link). The parent shows a progress
bar that fills as its children close. Keep it to two levels, an epic and its
tasks. Mark the parent with the `epic` label. Add a child with
`gh issue edit <parent> --add-sub-issue <child>`, or open one under a parent with
`gh issue create --parent <parent>`. Put an issue under an epic only when it is
genuinely part of that initiative, not merely related; a related issue is linked
by mentioning it in the body instead.

**Labels** carry the categories. Each open issue takes exactly one `area:` label,
one of `area:skills`, `area:tests`, `area:release`, or `area:docs`. Its type is
one of the existing `bug`, `enhancement`, `feature`, `documentation`, or `chore`.
Two labels carry readiness, and they never sit on one issue together:
`needs-answers` means a question only a person can answer is open, and `ready`
means a person judged the piece shaped. A project the kit founds uses
`state:ready` for that state instead. This repository's own issues keep `ready`
until the release that moves them. `status:blocked` is added only when
it says something. Colour is one hue per family, so the list stays scannable.
There is no priority label: what to pick up next is set by the maintainer's
cadence, not recorded on the issues.

Some labels are read by the release machinery and must not be renamed or removed:
`release-major`, `release-minor`, `release-patch`, `skip-release-notes`, and the
type labels `bug`, `enhancement`, `feature`, and `documentation`, which feed the
version bump and the release notes. Only add organising labels around them.

The **Kit maintenance** user Project (`github.com/users/gwpicard/projects/3`) is
the one dashboard across every open issue. Group its table by Parent issue for an
epic view, or add a second view grouped by an area field. A Project groups by its
own fields or by Parent issue, never by a label, so drive its grouping off the
parent link rather than duplicating the area labels as Project fields.

For a quick slice without the Project, bookmark an issue search:
`is:open label:epic` for the epics, `is:open no:parent -label:epic` for
top-level work, `is:open label:"area:tests"` for one area, and
`is:open label:"status:blocked"` for waiting work.

Milestones are not used, because they are release or date buckets and the work
has no timeline. Issue Types, the built-in type field, need an organisation
account this repository does not have, so the `epic` and type labels stand in for
them.

### What a shaped issue carries

A piece is shaped when its body carries a condition somebody can check, under
`## Done when`. That is the heading the kit gives a piece in a project it
founds, and it is the heading here for the same reason: the checkable condition
is what turns a request into a piece. A shaped body has this shape, with the
original report kept whole underneath it.

```md
<!-- elaborated:v1 -->
## Problem
What is wrong now, who it affects, and how often.

## Evidence
The files, functions and lines involved. Related issues and pull requests.

## Goal
The correct behaviour, in one or two sentences.

## Scope
**In scope:** what this piece changes.
**Out of scope:** the related changes it leaves alone.

## Done when
- [ ] A result a person can see or test. One result per line.

## Assumptions
- I assumed X, because Y. Correct me if this is wrong.

## Risks
What can break, and who or what the change touches.

<details><summary>Original report</summary>

The unchanged original body.

</details>
```

Two routines write that shape, and neither builds anything. One runs when an
issue is opened. The other runs each morning and picks up the answers to the
questions the first one asked. Their outputs are an issue body, an issue
comment, and a label change, and nothing else. The first line of the body,
`<!-- elaborated:v1 -->`, is how a run knows the work is done, and a question
comment opens with `<!-- elaborate:questions -->` so the morning run can tell
its own question from the answer under it.

A routine asks only about a blocker, which is an unknown where two different
answers give two different results. Everything else becomes an assumption,
written into the body so the person can correct it. A routine asks at most
twice on one issue. After that it takes its own defaults, lists them under
assumptions, and writes the body, because a piece stuck behind an unanswered
question is a piece nobody sees again.

A routine skips an epic, since an epic is an initiative rather than a piece,
and it skips a pull request. When it writes the body it also adds the one
`area:` label and the one type label the evidence supports, and swaps
`needs-answers` for `ready`. Those are guesses from the code, and the
maintainer corrects them. A routine never closes an issue, never adds a
sub-issue, and never sends a reminder.

## Adaptive process is a contract

Every rule declares where it applies (always, on named paths or changes, or
only inside a named sensitive area), the way PHILOSOPHY.md requires; do not add
a strict step to the default workflow merely because it is good engineering
practice. When changing a skill, check all three build paths: a change that
improves Build with care but burdens private exploration belongs behind a path
condition, not in the shared default.

## Changing a skill

This section governs the thirteen canonical skills in `.agents/skills/`. A
maintainer skill sits outside it, and `AGENTS.md` says what it does and does not
owe.

Start with PHILOSOPHY.md, beside this file. Its five questions get answered in
the pull request description before the skill changes. A change that cannot
answer them gets reshaped before it's considered for merge.

`.agents/skills/` is the single source of truth. Edit `<name>/SKILL.md`, run
`.agents/tools/build-adapters.sh`, and commit the canonical change together with
the regenerated compatibility fixtures. Never hand-edit anything under
`.claude/`, `.cursor/`, or `.gemini/`. New projects use the shared skills
installer, the optional Claude Code plugin, or the Agent Plugins folder. The
Claude plugin metadata lives under `.claude-plugin/`. It explicitly
selects the eight generated command files and five generated background skills.
Those thin adapters load the canonical instructions from the plugin cache. The
Agent Plugins manifest lives under `agent-plugin/`, and its `skills`
folder is assembled by the release allowlist rather than by
`build-adapters.sh`, so the canonical skills stay in one place here. The
generated files also remain as maintainer checks. There is no `.codex/` adapter tree to
protect.

One setting says how a skill is triggered. A background skill another skill
calls carries `user-invocable: false` in its own file. A skill without it is a
command. The adapter builder reads that setting and nothing else, so a dropped
or misspelt line shows up as ten commands and three background skills, and the
count check stops the build there.

The commands used to carry a second setting that stopped the agent starting one
by itself, and each description ended with a sentence saying the same. Both
went. A person who wrote `/fix` in the middle of a message, or said "let's
implement", was told to retype the message with the command first, and that
restricted the person more than it protected them. The agent may now start a
command when the person types it, names it anywhere in a message, or asks for
its job in plain words, and it says which command it is running. It never
starts one the person did not ask for. The guard worth keeping is that the
person cannot pick a background skill, and that stays where the tool enforces
it. The shared installer and an Agent Plugins client load the canonical files
directly, so the setting has to be right in the skill itself, whatever the
generated adapters look like.

`user-invocable` is not in the written Agent Skills standard, so its reference
checker reports the five background skills as invalid. Keep it anyway, with the
cost on the record: the plugin standard tells a client to skip any skill that
fails the skill standard, so a strict Agent Plugins client would load the eight
commands and skip the five. Claude Code accepts the setting, which is why that
route works today. If the standard adopts a setting of its own, follow it and
update the short person-facing version in `docs/COMPATIBILITY.md`.

Humanizer is not in that tree at all. It lives under
`.agents/maintainer-skills/`, alongside `review-issues`, which reads the open
issues, groups them by theme and names the next piece worth picking up, and
`stack-research`, which reads what changed upstream for the products the
recipes name and proposes changes in a dated note. All three belong to whoever
works on the kit, and none belongs to anybody who installs it.

`stack-research` writes its note to `.agents/tmp/stack-research/`, which git
ignores, so the note is never tracked and never ships. It changes no recipe,
part or date itself. A proposal worth keeping becomes an issue.

The reason is what a shared skills installer reads. It looks in
`.agents/skills/` and `.claude/skills/` and offers whatever it finds in either,
merging the two by the `name` in each file's frontmatter. The thirteen adapters
carry the names of the thirteen skills they point at, so they merge away and an
installer finds thirteen. No maintainer skill shares a name with one of the
thirteen, so a copy of any of them in those folders would be a fourteenth skill
offered to every project.

Sitting outside both folders is what prevents that. It is also why the skill
gets no generated adapter and no line in the release allowlist. A marker file
was tried first and cannot work: the marker is this kit's own convention, and
an installer written by somebody else has never heard of it.

Load any of them by its path when you need it. The validator checks the placement
rather than trusting it, and fails if a folder or command file named for a
maintainer skill turns up anywhere an installer reads.

The vendored copy is pinned to version 2.9.1 from
[blader/humanizer](https://github.com/blader/humanizer/tree/v2.9.1) under its
included MIT licence. Review upstream changes before replacing the local copy.

Some skills carry a `references/` folder loaded only when it applies. Keeping
rules that apply to a minority of sessions out of the always-loaded body is the
pattern to follow when a skill grows.

A project's Claude settings live in start's foundation template, not in this
repository's own `.claude/settings.json`. Change the deny list in both, because
the validator compares each of them against `.agents/guard/blocked-commands.md`.
Only the template carries the session-start wiring, and only `setup-ai-build-kit` places the
session-start script into a project.

The session-end hook, `.agents/hooks/session-end-sync.sh`, ships alongside it
but is opt-in by design rather than by oversight: a check-up cadence should not
be missed, while reconciling records at session end is a lighter prompt. Its own
header gives the per-tool wiring, and typing `/sync` by hand does the same job on
any tool.

Editing a skill's body usually produces no adapter diff, because the adapters are
pointers carrying only the frontmatter description; changing a description does.
COMPATIBILITY.md, beside this file, holds the full per-tool map.

## Maintainer validation

Every change to `.agents/skills/` or the kit's own machinery runs
`.agents/tools/validate-kit.sh`, which checks:

- the canonical skill inventory (exactly eight commands and five background
  skills, named exactly, with nothing else in the folder);
- the maintainer skill boundary: every folder under `.agents/maintainer-skills/`
  is read off the disk rather than from a list, the vendored writing skill
  carries its licence, and no folder or command file named for any of them
  exists in `.agents/skills/`, `.claude/skills/`, `.claude/commands/`,
  `.cursor/commands/`, `.gemini/commands/`, or the release allowlist;
- frontmatter on every `SKILL.md` (name, description, folder match, no
  duplicates);
- harness contracts: `.codex/skills` does not exist, and Claude's generated
  background skills carry `user-invocable: false` while its generated commands
  do not;
- trigger declarations: a background skill declares `user-invocable: false` in
  its own file, a command never carries it, and `.claude/commands/` and
  `.claude/skills/` are compared as whole listings against the expected names;
- that no tracked file carries an AI attribution line or a link back to the
  session the work came out of, and that `.githooks/commit-msg`, which takes
  those out of a commit message, is saved as a runnable file;
- that every local Markdown link and every skill, reference, or template path
  named in another file resolves;
- the fit check's structure: all three canonical build paths and their
  decision-order headings are present, and the masterplan template carries the
  same build-path fields as the fit check, `Sensitive areas` among them;
- that the plan template carries the `Subjects` column, that only the three
  canonical build-path names appear as path values, and that `team.md` is
  referenced nowhere;
- that clarify says which questions may be offered as choices and which are
  asked in plain words, with the matching maintainer scenario present;
- that `/ship` keeps its go-live and operational-readiness steps inside the
  path branches that use them, never as a shared section reachable from all
  three;
- that the generated adapters match what `.agents/skills/` produces, with no
  stale adapter folder left behind;
- shell syntax on every script, and that config files (JSON, TOML, YAML)
  parse;
- that the Claude Code deny list mirrors the mechanically enforceable entries
  in `.agents/guard/blocked-commands.md`, in this repository's own settings and
  in the settings template a project receives;
- that the project's Claude settings template carries the session-start wiring
  while this repository's own settings do not;
- that every tracked file opening with a shebang is saved as runnable, unless
  this repository only ever sources it or hands it to `sh`. It reads the mode
  git recorded rather than asking the disk, for the Windows-mount reason given
  under releases below;
- that project-facing docs carry none of the stale claims this kit has made
  before: "all markdown", "seven skills" describing the whole repository,
  "four project documents", `team.md`, a mandatory fresh session for every
  build, a universal pull-request or test-first requirement, an automatic
  rebuild treated as the fourth repair attempt, a count of nine commands or
  fourteen skills, an absolute claim that the
  five background skills never appear in any harness, incorrect Claude invocation
  semantics, `.codex/` described as a generated adapter, or a claim that
  everything in the kit is markdown.

CI runs the same script in this repository's own pull requests, alongside every
rehearsal in `.agents/tests/`. The released starter receives its deliberately
failing project check from
`.agents/skills/setup-ai-build-kit/templates/foundation/checks.yml`; `setup-ai-build-kit` replaces that
placeholder with the project's real commands during stand-up. A project that
already runs its tests on pull requests in a workflow of its own gets no
placeholder, and founding records that workflow as its project check.

## Scenario review

Before a release, work through `.agents/tests/scenarios.md` and confirm each
scenario still resolves to the path, evidence, and route it names. It is a
maintainer contract: nothing there is shown to someone building a project
with the kit.

`.agents/tests/replay/` does part of that walk for you. It holds a whole
conversation with an assembled release and asks a separate grader whether what
happened matches the contract, several times over, so the answer is a rate
rather than a pass. Read its table before a release. It settles nothing on its
own: a session with nobody in it is a lead rather than a verdict, and anything
it turns up should be repeated by hand before it counts as a defect. Its own
folder explains what it covers and what it cannot reach.

## What earns a shell test

The suite under `.agents/tests/` grew by artefact rather than by risk, which is
how a check ends up guarding something nobody would ever break. Answer these
before adding one.

1. What does a person lose if this breaks? If the honest answer is nothing they
   would notice, it does not belong here.
2. Can it break quietly? Something that fails loudly the first time anyone runs
   it needs no guard. These checks earn their place against silent failure.
3. Is it a boundary or a behaviour? Shell owns boundaries: what ships, what gets
   written, what gets published, what gets overwritten. How the kit behaves in a
   conversation is judged by the scenario review, not here.
4. Does an existing check already build this fixture? Then add the assertion
   there. A new file is justified by a new fixture, not by a new topic.
5. Would it still be true after a rewrite? A check pinned to particular wording
   or an internal path fails when someone tidies up and teaches nobody anything.

An assertion that cannot be made to fail is not protecting anything.
`.agents/tests/mutate.sh` breaks one promise at a time and records which checks
noticed, which is how that gets settled with evidence rather than opinion. Run
it when the suite changes shape. Anything it shows to be unbreakable comes out
at the next release, and anything it breaks without being noticed is the gap to
close first.

## The pull request check

`.github/workflows/source-checks.yml` is private source machinery. It never
ships. Its `source-kit-validation` job regenerates the adapters and runs
`validate-kit.sh` on pull requests here.

Its `rehearsal` job runs `.agents/tests/run-all.sh`, which is every rehearsal in
that folder, in a single job. A job for each would name a failure on the pull
request's own checks list, which reads better. But a hosted job is billed a whole
minute however long it takes, and most of these finish in seconds, so a job each
would cost about twenty five minutes to do about three minutes of work.

The runner does that naming instead. It carries on past a failure and names every
one, in its output and in the run summary, rather than stopping at the first and
hiding the rest. `rehearsal-runner.sh` is what proves it holds: a validator could
read a list off the file, but only running the thing settles whether it behaves.
The runner reads the folder rather than a written-out list, so a rehearsal runs
from the moment it is saved. Only `mutate.sh` is left out, and it audits the
suite rather than passing or failing.

`validate-kit.sh` checks that this workflow still has both jobs, that the
rehearsal job is guarded to this repository, and that it runs `run-all.sh`. The
last of those is the load-bearing one, because a rehearsal job that ran something
else, or nothing at all, would go green.

`validate-kit.sh` also calls several of those rehearsals itself by name, and runs
the whole written-rule family by finding the checks that source
`lib/rule-shape.sh` rather than by keeping a list of them. That is what keeps it
a single local command and what gives release preparation its coverage. So the
hosted run does that work twice, and at about half a minute for the whole set
that is cheaper than either half losing it.

Do not add a switch to skip the rehearsals when the hosted job runs them. Every
expensive fault this repository has had came from a check that passed by never
running, and the duplication costs half a minute and fails loudly.

The job installs Claude Code, so the Claude plugin rehearsal and `fake-github.sh`
run for real rather than being skipped for want of it. Nothing here reaches the
network or uses a token, since the stand-in for the GitHub command line tool
covers what would otherwise need an account. The replay harness stays out
altogether: it costs money and needs a model, which its own README explains.

## Keep it generic

Nothing in the released kit names a project, a company, or a person;
`/setup-ai-build-kit` is what makes it someone's. Every workflow names this
repository in a gate, so none of them runs in somebody's fork, and none of those
workflows ships.

A service a tool runs on, meaning its hosting, its data or its deploy, is
named nowhere either, except inside a recipe file under
`.agents/skills/ship/recipes/` and in the README. A recipe pairs a build stack
with a place to run it, so naming those services is its whole job. A skill that
needs to know how one behaves reads the project's recipe, which keeps
every skill the same whichever recipe a project runs on. `hosting-request.sh`
refuses a hosting, data or deploy product's name in every skill file outside
`.agents/skills/ship/recipes/`, which holds the recipes and their shared parts.
The screen rules' link to Vercel's interface guidelines is the one exception,
because it names a design guide rather than a place a tool runs. The
`stack-research` maintainer skill names those products too, because reading
their changelogs is its job, and it never ships.

A recipe waiting for its real run sits in `.agents/tests/recipes-awaiting-run/`,
which ships nowhere, and its rehearsal reads it there. Once the run is recorded
in its proven section, move the file into `.agents/skills/ship/recipes/` with
`git mv`. The rehearsal finds it on the menu from then on, and fails if a copy
is left in both places.

## When a release is cut

Ask first what an existing user must do to upgrade. The kit has had real users
since v0.5, so a release is an upgrade for them as much as a first install for a
newcomer. Name anything that breaks a project already running on an earlier
version: a renamed command, a removed feature, a changed record or label, or a
new precondition. For each, there must be a path that carries an existing project
across without losing its work, and the person must be told about it in a place
they will see. A one-time migration lives in `/maintain`, which runs on its own
clock and is idempotent, and the visible change is named in the release notes.
If a breaking change has neither, it is not ready to ship. A release that only
adds behaviour still gets this check, and answers it with "nothing to do".

Run PHILOSOPHY.md's five questions over everything already here, including what
is being added. Anything that now fails a question it used to pass has drifted
(PHILOSOPHY.md explains how), and that is the list of work for the next pass.

Check `docs/SOURCES.md` in the same sweep. A borrowed idea that arrived since
the last release belongs there, and a credit for something the kit no longer
does comes out.

Then build the released kit into a new temporary folder with
`.agents/tools/build-release.sh <version> <folder>`. The allowlist in
`release-manifest.txt` is the boundary: only its paths ship. Run
`.agents/tests/release-builder.sh`, `.agents/tests/starter-rehearsal.sh`, and
the full source validator. The release check proves the boundary and the
rehearsal proves that installed skills can prepare a clean, independently saved
project with its founding record templates in place. It does not replace a
person's guided `setup-ai-build-kit` check of the interview itself.

The release builder also writes the version without its leading `v` into the
Claude plugin manifest. Validate the assembled folder with
`claude plugin validate <folder> --strict`. One warning is expected: Claude
Code says a root `CLAUDE.md` is not loaded by a plugin. The kit keeps that file
for a project that copies the whole kit, so the rehearsal accepts that warning
and fails on any other. Then rehearse the plugin from an isolated `CLAUDE_CONFIG_DIR`. The rehearsal must cover marketplace discovery,
the manual command boundary, local project installation, bootstrap, a failed
marketplace refresh, a successful update, and removal. It must not change the
maintainer's real Claude configuration.

Run `.agents/tests/agent-plugin.sh` too. It builds a release and checks the
assembled `agent-plugin` folder against the open standard: the manifest's
permitted fields, the thirteen skills as immediate children of `skills`, no
skill hidden deeper, no maintainer-only writing skill, and a project
stand-up from that folder alone.

Run `.agents/tests/release-publication.sh` as well. It rehearses preparing a
draft against a stand-in for GitHub: a draft that does not exist yet, one naming
a different version, a Release already published, and a repeat that must leave
one archive rather than two. It then proves what no longer exists. No workflow
or tool may run a push, no file may be named for the deleted starter publisher,
no workflow may mint a credential beyond the run's own token, and only the two
workflows that edit a Release may write at all. Every job in the folder is
checked for its repository gate, per job rather than per file, because a
file-wide check is satisfied by one gated job while a second runs beside it
ungated.

Approved folders contribute only files already tracked here, so an unexpected
local file cannot enter a release.

Each merge into `main` updates one draft Release. Closing a pull request without
merging it changes nothing. The draft collects the pull request titles since the
last published version and suggests the next version. Features and enhancements
suggest a minor version; other changes suggest a patch. The `release-major`,
`release-minor`, and `release-patch` labels make the intended version visible,
with the highest matching increase winning. If labels change after a merge, run
`update release draft` from the Actions page to refresh the suggestion.
The draft workflow and its configuration are maintainer machinery and do not
ship in the released kit.

Online release still has two deliberate stages, and one thing has to happen
before either of them. Three files carry the version an installation reports:
the two plugin manifests and `maintain`'s `VERSION` marker. Both installers read
this branch, so the branch has to say which version it is. Run
`.agents/tools/stamp-version.sh vX.Y.Z` on a branch, open the pull request, let
the checks run, and merge it. Then merge nothing else until the release is
published, or the version covers work the notes do not mention.

When the draft is ready, start `prepare release` with the version shown on it,
such as `v0.1.0`. The workflow rejects a version whose tag already exists,
validates `main`, confirms `main` carries that version, assembles the starter,
and attaches the checked archive to that draft. If the Release Drafter
draft is missing, preparation stops and tells the maintainer to refresh it.
GitHub's native generated notes are not used because their pull request format
cannot omit private numbers. Check the version, archive, and notes before
publishing. If another pull request merges after preparation, run
`prepare release` again so the archive matches the latest draft.

`.github/release-drafter.yml` groups labelled work and keeps unlabelled work in
`Other changes`, so an absent label cannot silently remove a change. A pull
request title may become a line in the public notes, which makes the title
human-facing prose. Public notes omit the private pull request number. Review
the draft before publishing. Remove internal noise, correct any misleading
summary, and state any action an existing user must take. Use
`skip-release-notes` only when a merged pull request has no useful place in the
project's public history.

Edit the notes in the Release's web page. An edit through the API is where a
draft loses its tag: a `PATCH /releases/{id}` that sends only `body` resets the
draft's `tag_name` to `untagged-...`, and the tag and target then have to be set
again before publishing. If the notes must change through the API, send
`tag_name` and `target_commitish` with every edit to a draft, whatever else the
edit changes.

Publishing the draft is the release. There is nothing to copy anywhere and no
credential to mint, because the repository the version is prepared in is the
repository people install from.

`verify release` then rebuilds the published version from its own tag and
compares it with the archive that was reviewed before publication. It cannot
un-publish anything, and it is not meant to. What it catches is a draft
retargeted by hand, or a pull request that merged between preparation and
publication, either of which would leave the tag and the reviewed archive
describing different things. It accepts only a tag contained in reviewed `main`.

A publisher that took an assembled release and made it the exact tree of a
second repository used to run here, along with a GitHub App and its two Actions
settings. All of it existed because a workflow token cannot write to another
repository. There is no other repository, and that same code aimed at this one
would replace the source with a packaged release, so it was deleted rather than
pointed somewhere safer. The rehearsal now proves its absence: no workflow or
tool may run a push, and only the two workflows that edit a Release may write
at all.

A fix to a release workflow cannot rescue the release being published. A
`release` event runs the workflow from the tagged commit, not from current
`main`, so a repair sitting on `main` takes effect only for the next version.

Building a release locally on a Windows mount records the wrong file modes,
because every file on that mount reports as runnable. The same mount also hides
a script saved without its runnable bit, which is why `validate-kit.sh` reads
the mode git recorded for every script the kit runs by path rather than asking
the disk.

Preparation is safe to repeat. It refuses to create a draft where Release
Drafter has not left one, refuses when a draft names a different version,
refuses to touch a Release that is already published, and removes the archive it
replaces rather than leaving two attached. Running it twice for the same version
leaves one archive, not two.

Two of the three installation routes read the repository's default branch, so
which branch that is decides what a project receives. `stable` is the answer to
that. Only a release moves it: `verify release` rebuilds the published tag,
compares it with the reviewed archive, and a second job in the same workflow
then points `stable` at the verified commit. A release that fails verification
leaves `stable` where it was. That job carries the only repository write in
this repository, and `.agents/tools/promote-stable.sh` is where its limits are
written down.

Work still merges into `main`, and `main` is still the branch a contributor
targets. What changed is that the branch installers read is no longer the
branch the work happens on.

Because `stable` is the default, GitHub fills it in as the base of a new pull
request, and so does `gh pr create`. Open one with `gh pr create --base main`.
A version stamp once went in without `--base`, merged into `stable`, and
stopped the next release from moving the branch until a person turned its
force-push rule off by hand. The `pull request base` check now goes red on a
pull request aimed at `stable` and says how to change it. It stays off the
required list: a required check on `stable` would refuse the release job's
update in the same way a pull-request rule does. A project installing between two releases used to
receive the label of one release with the contents of another, and `/maintain`
told it that it was up to date. Now it receives the release. `/maintain` reads
the project's own version against
`/repos/gwpicard/ai-build-kit/releases/latest`, the one endpoint that cannot
answer with a draft or a prerelease, and says both numbers every visit, so a
project that installed before this arrived can still see where it stands.

The switch is done. `stable` exists, it points at the latest published
release's commit, and it is the repository's default branch. What matters now
is how the two branches are protected, because they are protected differently
and the difference is not arbitrary.

`main` requires a pull request and the `source-kit-validation` and `rehearsal`
checks, and refuses a deletion or a force push. `stable` refuses a deletion or
a force push and nothing else. It cannot require a pull request. Nothing merges
into `stable`: the release job updates the ref through the API, and a
pull-request rule rejects a ref update whoever makes it. A rule meant to keep
people out would stop the release instead.

That leaves one gap, stated here rather than papered over. An ordinary
fast-forward push to `stable` by somebody with write access is not refused. The
rule that would refuse it is the ruleset's update restriction, and on a
user-owned repository that restriction binds the workflow's own token as
readily as a person, with no bypass to tell the two apart. What is in place
stops the damage that cannot be undone, a deletion or a rewrite. A stray push
shows in the branch and is corrected by publishing again.

One trap for anybody who moves the default branch again. A ruleset whose
condition is `~DEFAULT_BRANCH` rather than a branch name follows the default
branch when it moves, and takes its rules off the branch it used to cover.
That happened here. Switching to `stable` left `main` with no rules on it at
all, and nothing said so: the ruleset list read exactly as it had before,
because the ruleset had not changed. Both rulesets now name their branch
literally. After any change of this kind, ask each branch what applies to it
rather than reading the list:

```
gh api repos/<owner>/<repo>/rules/branches/main --jq '[.[].type]'
gh api repos/<owner>/<repo>/rules/branches/stable --jq '[.[].type]'
```

If `stable` ever has to be rebuilt, confirm it against the published tag rather
than assuming:

```
git fetch origin && git rev-parse origin/stable
git rev-list -n1 vX.Y.Z
```

Those two have to match. Create `stable` by hand at the right commit rather
than cutting a release to move it.

To check a promotion from the remote side, compare `stable` with the tag
itself. The release tags are lightweight, and a lightweight tag has no `^{}`
form, so `git ls-remote origin 'refs/tags/vX.Y.Z^{}'` prints nothing and looks
like a mismatch. `git ls-remote origin refs/heads/stable refs/tags/vX.Y.Z`
prints both commits, and they have to be the same.

The bridge for projects installed before the shared installer is retired. Only
v0.1.0 and v0.1.1 shipped a `/maintain` that could reach it, v0.1.0 was never
tagged publicly, and the kit's own record says real users arrived at v0.5. A
project older than that reinstalls with `npx skills add gwpicard/ai-build-kit`
once and then updates like any other. Every installation now records where its
skills came from and updates through that route, and project records, AGENTS.md,
README.md, environment files, application code, and the project's own check stay
project-owned either way.

Only stable numbered releases update the public repository. A preview build
stays on this computer, and the next section says how to try one.

## Trying unreleased work as a person would

Do this before any release that touches founding or `/ship`. It checks what a
person sees, which no rehearsal reaches. It asks the person for one GitHub click
and one Supabase project. The Supabase Free plan allows two active projects, so
one of those two slots must be unused. Pick a number for the run and put it
wherever `N` appears.

1. Build a preview from a clean `main`. The builder copies the working tree, so
   run this in the checkout that holds `main`, not a worktree on another branch.

   ```
   touch ~/.abk-try-N-start
   git switch main
   git branch --show-current
   git status --short
   git pull --ff-only
   git rev-parse --short HEAD
   .agents/skills/setup-ai-build-kit/scripts/check-tooling.sh --recipe .agents/skills/ship/recipes/nextjs-supabase-on-vercel.md
   .agents/tools/build-release.sh v0.0.0-preview.N /private/tmp/abk-preview-N
   ```

   The first line leaves a marker file whose time is the start of the run, so
   teardown can find what the run made. The branch must print `main`, and the
   status must print nothing. Note the commit. Every line of the tooling report says ready. The builder refuses a
   folder that already exists, so a second build takes the next number.

2. Install the preview twice, into two empty folders.

   ```
   mkdir /private/tmp/abk-try-N-claude && cd /private/tmp/abk-try-N-claude && git init -q -b main
   npx skills add /private/tmp/abk-preview-N -a claude-code -s '*' -y

   mkdir /private/tmp/abk-try-N-both && cd /private/tmp/abk-try-N-both && git init -q -b main
   npx skills add /private/tmp/abk-preview-N -a claude-code -a codex -s '*' -y
   ```

   The first puts the thirteen skills in `.claude/skills/`, the second in
   `.agents/skills/` with links in `.claude/skills/`. In both, `ship/recipes/`
   holds the same recipes as `ls <kit checkout>/.agents/skills/ship/recipes/`.

   Each `skills-lock.json` now records `"sourceType": "local"`, with a path into
   `/private/tmp/abk-preview-N`. A project installed this way cannot update
   later, and a `/maintain` visit there can fail once that folder is gone.

3. Found a small internal tool in each folder: open Claude Code, run
   `/setup-ai-build-kit`, and ask for something small, such as a page where a
   team keeps short notes. When founding offers a GitHub repository, say yes
   and name it `abk-try-N` in the first folder. Say no in the second. Then
   check in each folder:

   - During the interview, the kit showed the recipe menu, marked one recipe
     as recommended, and said it would use that one unless told otherwise.
   - `grep '^Recipe:' AGENTS.md` names one recipe file.
   - `grep founding-menu .ai-build-kit-maintenance` names every recipe on the
     menu.

   A failed check is a finding. File it as an issue, and do not fix it in the
   throwaway project.

4. In the first folder only, run `/implement` on one ready piece, then `/ship`
   once, asking for a Vercel project named `abk-try-N`. Without that name,
   `/ship` names the project after the tool. The person does two things:

   - On GitHub, Settings, Applications, Installed GitHub Apps, Configure beside
     Vercel. GitHub asks for a passkey or password before it shows that page.
     Add `abk-try-N` under Only select repositories, and save. The app may
     already be installed with other repositories selected. Add `abk-try-N` to
     that selection, and never replace or clear it.
   - In the Supabase dashboard, make a project named `abk-try-N`, and paste a
     password made and copied like this:

   ```
   mkdir -p ~/.config/abk-try-N
   (umask 077 && openssl rand -base64 48 | tr -d '/+=\n' | cut -c1-40 > ~/.config/abk-try-N/db.pw)
   pbcopy < ~/.config/abk-try-N/db.pw
   pbcopy < /dev/null
   ```

   The password is 40 letters and digits drawn at random, in mixed case, since the create form
   marks a lowercase hex password as not secure enough. Only this account can
   read the file, and no command prints the password. The last line empties
   the clipboard once the password is pasted. When the kit asks where the
   password is kept, give it the file's path. A secret never goes into the
   chat. When Chrome or an agent fills the form, it can show a stale "Password
   not secure enough" message and still create the project, so check the
   project list rather than the form.

5. Tear everything down.

   ```
   vercel project rm abk-try-N
   gh auth status
   gh auth refresh -h github.com -s delete_repo
   gh repo delete <owner>/abk-try-N --yes
   gh auth refresh -h github.com -r delete_repo
   trash /private/tmp/abk-try-N-claude /private/tmp/abk-try-N-both /private/tmp/abk-preview-N ~/.config/abk-try-N ~/Backups/abk-try-N
   ```

   Answer `y` when Vercel asks. `gh auth status` lists the token's scopes. If
   `delete_repo` is already there from an earlier run, skip the first refresh.
   The first refresh adds the scope that `gh repo delete` needs, and the second
   takes it off the token again. It takes the scope off on purpose, even when
   it was there before the run, since a token keeps no more reach than it
   needs. Each refresh waits for a confirmation in the browser, which an agent
   cannot give, so the person runs it.

   Delete the Supabase project in the dashboard, since
   `supabase projects delete` cancels its own confirmation without a real
   terminal. Deleting the repository also removes it from the selection of
   Vercel's GitHub app, so leave the app installed. Only if it was installed
   for this run, uninstall it under Installed GitHub Apps.

   `/ship` leaves two things on this computer. `~/Backups/abk-try-N` holds the
   database's roles, structure and data, and the `trash` line above takes it.
   The kit also writes temporary files in `/private/tmp`, such as restore-test
   folders and logs, whose names this section cannot know. List everything
   there that is newer than the marker from step 1, trash what the run made,
   and list again. Other sessions write there too. If you cannot tell who made
   an item, leave it. Trash the marker last, once the list shows nothing the
   run made:

   ```
   find /private/tmp -maxdepth 1 -newer ~/.abk-try-N-start
   trash ~/.abk-try-N-start
   ```

   The local folders go to the Trash, since a deletion with no undo is on the
   blocked list in `.agents/guard/blocked-commands.md`. Where `trash` is
   missing, `mv <folder> ~/.Trash/` does the same.

   Then check that each item is gone:

   ```
   vercel project ls
   gh repo view <owner>/abk-try-N
   ls /private/tmp/abk-*
   ls ~/.config/abk-try-N
   ls ~/Backups/abk-try-N
   ls ~/.abk-try-N-start
   ```

   `vercel project ls` does not list `abk-try-N`. `gh repo view` answers
   "Could not resolve". Every `ls` line finds nothing. The Supabase dashboard
   no longer lists the project.

6. Write a dated log: the preview version and the commit it was built from,
   each check and whether it held, with the words that show it, what the run
   created and how it was removed, and anything that surprised you. A failure
   found here is filed as an issue before the release, and the release waits
   until somebody decides what to do about it.

## House rules for writing

Anything written into this repository, by a person or an agent, follows these.
They exist because the audience is not required to read code, so the words are the product.
A short form of the list ships in `AGENTS.md`'s project template, so a project
built with the kit inherits the plain-language spirit of it without carrying the
full editorial machinery. This is the full version, and it governs the kit's own
documents.

Before saving human-facing prose, load
`.agents/maintainer-skills/humanizer/SKILL.md` and run its embedded mode. This
covers documentation, skills, pull request titles and descriptions, issues,
release notes, interface copy, error messages, and reader-facing comments. The local
skill is the shared instruction for every supported harness; the rules below
remain the kit's own stricter house style.

Preserve the information and intended voice rather than the draft's sentence
shape. Never invent facts, names, figures, dates, quotations, or citations.
Leave code blocks, frontmatter, data, commands, and link targets untouched.
After the first edit, ask what still sounds generated and revise once more.
Technical and reference writing should stay neutral and plain; personality
belongs only where the subject and author's voice call for it.

- British spelling. No em dashes: a comma, colon, semicolon, or full stop is
  always available and always clearer.
- Plain words over jargon. When a technical term is unavoidable, define it once
  in the sentence that introduces it and then use it plainly.
- Banned: leverage, robust, comprehensive, seamless, crucial, foster, enhance,
  transformative, delve, navigate as a metaphor, empower, streamline, holistic.
- No contrastive reframes ("it's not X, it's Y"), no rhetorical triplets, no
  bulleted lists where each item opens with a bold header.
- Explain a concept where it lives, and link from everywhere else.
- One name per thing. This is a kit, and calling it a pack somewhere else only
  makes a reader wonder whether the two are different.
- Paragraphs stay under about 100 words. Four here had passed 140 before the
  rule existed, and the audience is not required to read code.
- Vary the sentence shape. Almost every explanation wants to arrive as
  "statement: a, b, and c", and a document leaning on one device reads as a
  template however clear each instance is.
- Two house aphorisms earn their keep and were both badly overused: "X is how
  something good goes wrong", and "X, never Y". Two of each per document.

## One owner per concept

This repository grew heavy through duplication, so every concept has exactly one
home and every other mention is a link.

- Root `README.md`: what the kit is, installation, and positioning for someone
  deciding whether to use it. It ships as the public README unchanged, so it is
  written for that reader rather than for a maintainer. The eight-command table
  there is a summary; what each command actually does belongs to WORKFLOW.
  Orientation for someone working on the source belongs in root `AGENTS.md`.
- `WORKFLOW.md`: everything operational. How work runs, day to day, for someone
  already using it. Operational detail belongs here and nowhere else, including
  the parts of setup that come after the README's quick start.
- Root `AGENTS.md`: standing rules for maintaining the source.
  `.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md`: standing rules for the
  agent working on a user project, plus the capability profile filled in by
  `setup-ai-build-kit`.
- `docs/PHILOSOPHY.md`: why the kit is shaped as it is, who it is for, and the
  test any addition has to pass. Read before changing what a skill does.
- `docs/COMPATIBILITY.md`: the portable core contract and per-tool detail.
  `docs/MAINTAINING.md`: this file.
- `docs/SOURCES.md`: the outside work the kit took ideas from, and what each
  source contributed. It names a borrowed idea in the kit's own vocabulary and
  links to that idea's owner rather than explaining it again.
- `.agents/skills/ship/recipes/`: one file for each recipe, and the only place
  outside the README that names a service a tool runs on. What a recipe must hold, and what
  proves it, belongs to `.agents/skills/ship/references/recipe-format.md`. A
  project records which recipe it runs on in its own AGENTS.md, in the stack
  section.

Two concepts carry two names on purpose, on the same reasoning both times: the
name a person reads is the one that matters, and an internal name is left alone
where changing it would churn output nobody reads for no reader benefit.

A person reads "background skills"; the code identifiers and check messages say
"disciplines". They are the same five skills.

A person reads that the agent chooses the method; `.agents/tests/scenarios.md`
and `.agents/tests/replay/grader-prompt.md` call that field "hidden technique".
It is a graded field, and the grader prompt was last changed in August after a
run that measured its variance, so renaming it again would make the recorded
results harder to compare against the next ones. Rename it when a measurement is
not the thing standing behind it.

One word carries two meanings, and that is deliberate too. A person reads
`/shape`, the command that turns an idea into a ready piece.
`.agents/skills/setup-ai-build-kit/references/pieces.md` uses the bare word for
what an issue has to contain, as in "Shape is what decides". The command
produces that shape, so the two belong together, and the slash is what tells
them apart. Write the command with its slash every time.

Nothing should say the old "words" name for the commands now, in prose or in an
identifier.

Before adding an explanation, check whether its owner already carries it. If it
does, link. If two documents disagree, the owner wins and the other is edited.
