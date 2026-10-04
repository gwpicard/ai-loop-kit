# AGENTS.md

Standing instructions for maintaining AI Build Kit itself. The project
foundation carries different instructions in
`.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md`.

## What this repository is

This is the maintainer source. It contains the canonical skills, compatibility
fixtures, checks, maintainer notes, and the machinery that assembles the
installable public kit. It never becomes a project built with the kit.

The project records `masterplan.md` and `CHANGELOG.md` do not exist
here by design. They are created inside a user's project by `/setup-ai-build-kit`.

## Before any work

Read `docs/MAINTAINING.md`. Read `docs/PHILOSOPHY.md` before changing what one
of the fourteen canonical skills does, or adding a capability. Check the current
branch and unsaved work
before editing. Never run the project-founding `/setup-ai-build-kit` process in this
repository.

## Source and starter boundary

- `.agents/skills/` is the single source of truth for the nine commands and
  five internal background skills. Nothing else belongs in it.
- `.agents/maintainer-skills/` holds the skills only the kit's own maintainers
  use. There are three: the Humanizer writing skill; `review-issues`, which
  reads the open issues, groups them by theme and names the next piece worth
  picking up; and `stack-research`, which reads what changed upstream for the
  products the recipes name and writes a dated note proposing changes, or
  none. They sit there rather than beside the fourteen because a shared
  skills installer reads `.agents/skills/` and `.claude/skills/` and offers
  whatever it finds in either, so a folder in one of those is a skill somebody
  installs. Being outside both is the whole boundary, and a maintainer skill
  gets no generated adapter for the same reason. Nothing offers one as a
  command, so load it by its path. To decide what to work on next, load
  `.agents/maintainer-skills/review-issues/SKILL.md`. To check the recipes
  against their products before a release, load
  `.agents/maintainer-skills/stack-research/SKILL.md`. Its note goes to
  `.agents/tmp/stack-research/`, which git ignores, so it never ships.
- `.agents/migration/` holds the one-off tooling for replacing the public
  repository with one whose history carries no AI attribution. It is not part of
  the kit, it gets no adapter, and it reaches nobody who installs the kit. It
  lives here rather than outside the repository because `docs/MIGRATION.md` is
  the plan and these are the scripts that plan runs, and a runbook whose tools
  sit somewhere else is a runbook that stops working. Read `docs/MIGRATION.md`
  before running any of them.
- `.claude/`, `.cursor/`, and `.gemini/` are generated adapters. Change the
  canonical skill, then run `.agents/tools/build-adapters.sh`. The Claude
  plugin exposes the nine generated command files and five hidden background
  skills. Shared installations use the adapters their coding agents need.
- `.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md` creates a project's
  root instructions.
- The root is the kit's own. `README.md` is what somebody deciding whether to
  use the kit reads, and it ships as the public README unchanged. This file is
  what somebody working on the kit reads. `CONTRIBUTING.md`, `SECURITY.md` and
  `.github/ISSUE_TEMPLATE/` are the public route for problems and suggestions,
  and ship as they are. No file at the root means two things.
- `.claude-plugin/` is the Claude plugin and marketplace metadata. It selects
  generated adapters rather than duplicating a skill.
- `agent-plugin/plugin.json` is the Agent Plugins manifest. The release
  allowlist rebases the fourteen canonical skills under `agent-plugin/skills/`,
  so the plugin folder is assembled at release time and this repository keeps
  one copy of each skill.
- `release-manifest.txt` is the full allowlist for the public kit. A file absent
  from that list does not ship.
- An installation records where its skills came from, in `skills-lock.json` or
  in Claude's plugin record, and updates through that route.
- `docs/MAINTAINING.md`, `.agents/tests/`, the source validator, and the release
  builder stay in this repository only.
- `.claude/settings.json` here is the maintainer's own. A project's copy comes
  from `.agents/skills/setup-ai-build-kit/templates/foundation/claude-settings.json`, which
  carries the session-start wiring and the state guard this repository must
  never have.

Never edit the released starter repository directly. A numbered release
generates it from this source.

## How changes are made

Build one agreed, visible slice at a time on a short-lived branch. Every
promised behaviour needs evidence. Stable rules and repairs use an automated
check when a machine can judge them; visual or exploratory work uses a guided
manual check; operational claims need a rehearsal.

When a written instruction and an automatic check disagree about the same
thing, trust the check. It tests the real work, and an instruction can fall out
of date. Follow the check, and say plainly that the two disagree rather than
following the stale instruction in silence.

When one of the fourteen canonical skills changes, answer the five questions in
`docs/PHILOSOPHY.md`, record any borrowed idea in `docs/SOURCES.md`, update the
owned explanation where needed, regenerate adapters, and run the kit validator.
Generated files are committed with their canonical change.

A skill in `.agents/maintainer-skills/` carries none of that bar. It reaches
nobody who installs the kit, it gets no adapter, and the maintainer who chose it
is the only person it answers to. So the five questions do not apply: they ask
what somebody who has not read the code sees on screen and what they type when it
goes wrong, and a maintainer skill has no such person. Nor does the rule that a
story is told in three places, because `WORKFLOW.md` ships and must not describe
a skill a reader cannot install.

Three things still hold. The house writing rules, since a person still reads the
words. `docs/SOURCES.md`, if the idea came from somewhere, which is a matter of
credit rather than of product rigour. And the kit validator, which matters more
here than for a canonical skill: it guards the placement that keeps a maintainer
skill out of a release. Everything else is the maintainer's own call, because a
rule with no activation boundary becomes universal ceremony.

Shared changes are reviewed and arrive through a pull request. A human decides
whether to merge. Reports describe behaviour, evidence, and uncertainty in
plain language rather than asking the person to read code or logs.

## Referring to work

Issue and pull request numbers belong in issues, in pull requests, and in a
changelog. Never in a tracked file. A number in a document or a comment is a
pointer the reader cannot follow, and once the material is public it points at
an unrelated issue in whatever numbering that repository happens to have.

Say the thing instead. Where a comment needs the reason behind a rule, write the
reason. "The contradiction this check exists to hold shut" survives a move and a
rename; a number does not.

`validate-kit.sh` fails on a number in any tracked file.

## Attribution

A commit and a pull request carry the name of the person who made them and
nothing else. No co-author trailer naming a model, and no link back to the
session the work came out of.

The session link is the one that matters. It is a personal address on the agent
vendor's site, it opens for anyone who reads it, and a commit message has no use
for it. Nineteen commits and thirteen pull request descriptions carried one into
a public repository before anybody noticed. Taking them out again meant
rewriting every commit and force-pushing a branch other people had already
cloned, which is a thing to do once.

Three things hold it shut now. Each coding agent has a setting that stops the
lines being written, and that setting is the first defence. `.githooks/commit-msg`
takes them out of a message anyway, for the session that overrides the setting
and the clone that never had it. `validate-kit.sh` refuses a tracked file
carrying one, which is the way in a hook cannot see, since a person pasting a
message into a document is not making a commit.

A hook runs from the folder named by `core.hooksPath`. That is a local setting
and a clone does not carry it, so a fresh clone runs one command before its
first commit. `docs/MAINTAINING.md` gives it.

None of this touches prose about the tools. The kit is built with Claude, Cursor
and Gemini and writes about them in most of its commits. What goes is the
attribution line, not the word.

## Maintainer checks

- `.agents/tools/validate-kit.sh` checks the source and generated adapters.
- `.agents/tests/run-all.sh` runs every rehearsal in `.agents/tests/` and
  names each one that failed. It reads the folder rather than a written-out
  list, so a new rehearsal runs from the moment it is saved, and it carries
  on past a failure so that one cannot hide another. The hosted check runs
  the rehearsals through it, in a single job.
- `.agents/tests/rehearsal-runner.sh` checks that runner against stub
  scripts: that a failure at the very start does not stop the ones after
  it, that every failure is named rather than only the first, that a
  passing rehearsal is not reported as failed, that `mutate.sh` is
  skipped, and that a copy of either the runner or `mutate.sh` is skipped
  too. That guarantee lives in a shell loop rather than in the workflow,
  where a validator could read it off the file, so only running it settles
  whether it holds. The copy matters because this folder is watched by a
  sync daemon: a copy of the runner that gets run runs the whole suite
  again and reaches its own copy again, so the run hangs rather than
  fails, and a hosted job is billed for every minute of it.
- `.agents/tests/release-builder.sh` checks the assembled public release boundary.
- `.agents/tests/starter-rehearsal.sh` checks that installed skills can prepare
  a clean, independently saved project with founding records. It also holds
  what founding does with the other skill folder. A link that leads nowhere
  and a link loop are refused by name before anything is written. A second
  copy that differs from the running one, or an empty folder, gets one note
  naming the folder, and founding carries on, since the running skill is whole.
- `.agents/tests/release-publication.sh` rehearses first and later publication
  against a disposable local destination.
- `.agents/tests/pre-release-run.sh` guards the written run in
  `docs/MAINTAINING.md` that tries a preview of `main` as a person would. The
  run needs real accounts and a person, so this check holds only what can be
  judged offline. Every repository path the steps name exists, and the builder
  accepts the preview version they give. The build starts from a clean `main`,
  since the builder copies the working tree. The two installer lines are the
  ones that worked in a real run. The password line is the mixed-case one
  Supabase's create form accepted, since the form marked a hex password as
  not secure enough. The teardown removes the Vercel project, the repository
  and every local folder, including the backups `/ship` writes, with no
  recursive forced delete. It shows the token's scopes first, takes the
  delete scope off again, and checks that each item is gone, the backups
  included. The kit's temporary files are the ones newer than a marker left
  at the start of the run, since a listing cut to a fixed length can pass
  while they remain, and the marker goes last. It also holds the rules that keep the
  run safe, read from the section itself so a copy elsewhere cannot hide a
  removal: the names given at founding and in `/ship`, the lockfile caveat, a
  failure filed rather than fixed in the throwaway project, a password that
  never enters the chat, and a release that waits for a decision on what the
  run found. It holds what the real run needed besides: the person, not an
  agent, runs each scope refresh, because it waits for the browser, and the
  throwaway repository is added to Vercel's app's existing selection, which
  is never replaced, while the app stays installed. Steps that drifted from
  the tools would otherwise surface on release day.
- `.agents/tests/claude-plugin.sh` rehearses the Claude command boundary, an
  isolated install, project bootstrap, failed and successful updates, and
  removal.
- `.agents/tests/agent-plugin.sh` checks the assembled Agent Plugins folder
  against the standard and rehearses a project stand-up from it.
- `.agents/tests/session-start.sh` rehearses the check-up cadence and proves
  this repository never receives a reminder. The hook reads its dates by key,
  so the `kit` line and the recipe lines in the check-up file, placed first,
  leave the count alone. It also holds the count of work. A busy project once
  did five weeks of work in five days and heard nothing, because only days
  were counted. So the hook speaks at 20 changes since the last visit, or
  since founding, however few days passed. The rehearsal saves dated changes
  in a throwaway project: 19 says nothing, 20 speaks, and changes saved
  before the visit and the commits inside a merged pull request are left
  out. It reads `origin/HEAD` first, then `main`, `master` and the branch
  checked out, and a remote holding fewer changes proves it never fetches.
  With both due, the day line comes first and the Claude output stays one
  object. A folder with no history keeps the day rule.
- `.agents/tests/check-up-counts-work.sh` guards the prose around that count.
  `/what-now` runs the reminder script in its plain mode and takes its
  answer, so a session's opening and `/what-now` never disagree. `/maintain`
  offers the newer script in one line to a project whose copy differs from
  the template, since an update never reaches it, replaces it only on a yes,
  and offers again next visit after a no. WORKFLOW.md says days or changes,
  whichever comes first.
- `.agents/tests/fake-github.sh` checks the replay harness's stand-in for the
  GitHub CLI: the commands it answers, and the ones it still refuses on purpose.
  It also holds that opening a pull request closes nothing, and that a merge
  closes the piece and lands the branch on the remote's `main`, since a kit
  that checks the remote would otherwise see a merged fix that never arrived.
  It holds what a first upload into an empty repository calls. The empty
  repository answers the branch listing with exit 2, and the stand-in says
  whether it is public or private. It creates `main` through the API only at
  a commit the repository holds, and only once, and makes `main` the default
  branch only once it exists. Moving or deleting a branch through the API
  stays refused. It holds a pull request stacked on another piece's branch:
  a base the remote does not hold is refused, as on GitHub, `pr list` filters
  by base, and `pr edit --base main` moves the pull request onto `main` once
  the piece under it has merged. `pr list --head` finds the pull request open
  from a branch, so a resumed run never opens a second, and `--json
  headRefOid` gives a merged pull request's head commit, for the stale-branch
  listing and for the worktree script, which counts a merged piece's work as
  saved after its branch has gone from the remote. A body given with
  `--body-file` is read, from a file or from standard input. As on GitHub, the
  view gives each comment its node id and
  the REST listing its numeric id, a deletion through the API takes only the
  numeric one, and `--delete-last` removes the last, as a run that lost a
  claim race deletes its own. An older bare comment gets an id from a range
  of its own, so ids never collide. A remote that is a network address is
  never asked, so a base there counts as missing. It models the repository's
  labels, because the gate script creates the kit's set and has to be seen
  creating each one once: a new repository starts with GitHub's nine, and a
  label that exists is refused unless forced. An issue still takes a label the
  repository does not list. It reads one issue on its own, answering 404 for
  one that does not exist, and keeps a close's reason and comment. A scenario
  can set faults in the state file: no network, a refused label write, a
  refused label creation, a refused comment, and a second session's change
  that lands between two reads of one issue.
- `.agents/tests/gate-script.sh` drives the gate script a founded project
  receives against that stand-in, and reads the labels back after every call.
  The gate is the one way a piece changes state, so a board is only as true as
  the gate's refusals. The check reads the transition table out of the script
  and drives every row twice, once where the condition holds and once where it
  fails, so a row added there and not tried here fails it. Each pass prints one
  line and writes the labels in one call, and each refusal names what failed
  and gives a `next:` command. It also holds the 26 labels and their colours,
  created once and never again, capture of a new piece and of an issue with no
  state, the refusal of a parent, drop, tidy, and a report that names every
  piece out of order and changes nothing. It holds the run status written
  beside the labels, and the cases that are not the normal one: no network,
  an account that cannot create labels, two sessions moving one piece, two
  states, and bad input.
- `.agents/tests/state-guard.sh` guards what stops the agent going round the
  gate. A founded project's Claude Code settings run a hook before each
  command and each GitHub tool call, and carry deny rules. Both refuse a direct
  change to a `state:`, `shaping:` or `review:` label. The check feeds the hook
  every spelling `blocked-commands.md` lists, as Claude Code's hook input, and
  reads the exit code and a message naming the gate command to use instead. A
  command that runs the gate and also writes a state label by hand is refused,
  since letting through anything that names the gate would let that through
  too. The gate's own commands, other labels and reads still run. A missing or
  unrunnable hook never blocks a command, and `gate.py report` names it. The
  deny rules go through the shared matcher against the same lists, and each is
  taken out in turn. Each rule ends in a doubled star, because a rule ending in
  `:*` is Claude Code's older prefix form and would never match `state:ready`.
  This repository's own issues keep today's labels, so its own settings carry
  neither the hook nor the rules, and the check plants each in a copy to prove
  the validator notices.
- `.agents/tests/fake-host.sh` checks the replay harness's stand-ins for a
  host's tools, which scenario 54 launches through on the Vercel recipe. The
  stand-in host keeps a list of deployments beside the project and builds each
  push to `main`, as a host connected to the repository does. The check merges
  a pull request and holds that the list gains one build, shown as building the
  first two times it is asked and ready after, and that the live address then
  serves it. Every deploy of a version the list already holds adds another
  build of it, and a rollback moves the live address and is recorded. A deploy
  writes its address to stdout and its progress to stderr, with the success
  line near the end, so the last three lines do not show whether it worked.
  Options follow the real command's help: an option it refuses is refused. It
  also holds that Supabase, Docker and the database fail the way a machine
  that is not signed in fails, that a command nobody modelled is refused to
  the log, and that a password, token or database address is masked there.
  Outside a replay each stand-in hands the call to the real command. Inside
  one, a missing host state file never does, since the real command may be
  signed in: each tool then answers as one signed in to nothing, and only
  `--version` and `--help` succeed. A call whose every address is a service on
  this machine on a port other than the app's, such as a coding agent's own
  hook listener, is left to the real curl.
- `.agents/tests/replay-provider.sh` checks both replay providers without a
  model call. It stubs Claude Code and Codex, then proves each first turn,
  resumed turn and grader route. It also holds the throwaway shell profiles
  that keep the fake GitHub command ahead of a signed-in real one, for Codex
  and for Claude Code, whose Bash tool once found the real one through the
  person's own login profile. A login shell started with those profiles must
  find the stand-in, and the host's stand-ins right after it, ahead of a
  deploy command that may be signed in. A turn also carries a Vercel and a
  Supabase token that belong to no account, a Docker engine that does not
  exist, and no stored database password, so a real host tool finds no
  account either. The profiles lower the odds and do not remove them, so it
  also holds what happens when the real GitHub command answers anyway. The
  runner reads the transcript and the provider's own record of the session,
  found by the id it writes beside the run, for the two sentences only the
  real, signed-out command prints. It does that before grading, and a run
  carrying either is written as not graded, with its reason, and left out of
  the roll-up's counts. A kit telling the person to run `gh auth login` is
  advice and not a sign, and the stand-in must never print either sentence.
- `.agents/tests/plan-printout.sh` runs the printout against a fixed set of
  issues and reads what it wrote. The groups print as a board, in the order
  Needs attention, one column for each shaping sub-state, To build, Held up,
  Building, In review split into waiting for you and automatic, and Made of
  parts. It holds which column each piece lands in, that a `type:bug` piece
  carries a bug mark in whichever column it sits, that a shaped piece says it
  is ready, and that a held-up piece names the piece holding it rather than
  its number. Needs attention is the gate script's report, word for word: no
  state, two states, a sub-label beside the wrong state, two review labels, a
  parent carrying a state and a label from AI Build Kit's model are each named
  once and printed nowhere else, and the printout moves nothing on GitHub. A
  piece being built or in review that was never shaped, or never passed the
  readiness check, is named there with what it is missing and still prints in
  its own column. Where both are missing, only the missing Done when is named.
  A parent with no state is never named for having none, a Readiness heading in
  another case counts while one with extra words does not, and a closed issue
  never prints. With no gate script beside it, the printout says so and names
  `/maintain`. When GitHub cannot be reached, the last printout is left alone
  and the refresh says when it was written. It also holds the invariant
  `/queue` rests on, that a piece with an open blocker never reaches the
  buildable group while a piece whose blocker has closed does. And it holds
  the groups of free pieces the printout works out from each piece's
  `Touches:` line, under `Go together`: two pieces naming the same area, in
  any capitals and with backticks or a full stop, never share a group, a line
  under a Touches heading counts and one in a code block does not, a piece
  with no line goes alone and says its Touches is unknown, and a held-up piece
  is in no group. It holds the marks read from each ready piece's body, needs
  you, not ready, not yet checked and try it, and that a held-up piece joins
  the plan only when every open blocker in its chain is in it. A piece stacked
  on one a run cannot take says it waits for it, and why, down the chain.
- `.agents/tests/piece-states.sh` guards the model the printout draws. Every
  open piece carries exactly one of four states, `state:shaping`,
  `state:ready`, `state:building` and `state:in-review`, written in that order
  in `pieces.md`, and a closed issue carries none. Beside `state:shaping` sits
  exactly one of six sub-states, from `shaping:raw` to `shaping:check`, and
  beside `state:in-review` one of two review labels. Every piece carries one
  `type:` label, the kit owns 26 labels, and only the gate script changes a
  state. An open issue with no state is named and taken in with `gate.py
  capture`, a parent carries no state, held up by another piece is a link and
  never a label, and a label from AI Build Kit's model is named and left
  alone. It fails on a copy of `pieces.md` that allows two states or two
  sub-labels, not only on one with the rule gone, because loosening is the
  edit that slips through. It also holds that founding creates the labels
  through the gate and gives each piece one type before its first move, that
  WORKFLOW.md explains the states in one place, and the note for a piece built
  or checked without being shaped or checked. `/what-now` names such a piece
  once, names a piece in `state:in-review` with `review:person` as the
  person's own, and leads with the gate's report.
- `.agents/tests/state-moves.sh` guards that every command moves a piece
  through the gate. It reads every `gh issue edit`, `gh issue create` and `gh
  label` command in `.agents/skills/` and fails on one that writes a
  `state:`, `shaping:` or `review:` label, or an old state word, leaving out
  the refused spellings `blocked-commands.md` lists and the gate, hook and deny
  rules themselves. It fails on any `parked` left in the skills, and proves
  both readers on copies with one planted. It then requires a `gate.py` call
  for each move: capture in change-triage with one `type:` label before the
  first move, every move in `/shape`, the claim in section-builder and in a
  run, the move to review when a pull request opens, a run's kickbacks and its
  give-back to `state:ready`, which a copy sending it to `gate.py drop` fails,
  `/fix`'s claim of a ready repair only, and `/sync`'s report followed by the
  person's choice and then `gate.py tidy`. The checkpoint route closes a
  piece on save and runs the tidy, in section-builder and in a run, and the
  merge step tidies after a merge. A refused gate call is reported and that
  move stops, in each command and in `blocked-commands.md`. `/fix` and
  `/what-now` read `type:bug` rather than `broken`, `/what-now` names a piece
  waiting in review for the person as theirs, and WORKFLOW.md's section 5
  tells the moves.
- `.agents/tests/piece-contract.sh` guards the piece contract and the check a
  piece passes before it turns ready. A real project's pieces were detailed and
  still missed whole categories, such as states nobody named, data rules and
  things leaving the device, because the template asked for none of them and
  the session that shaped a piece was the one that judged it complete. So it
  holds the issue form's fields in order, a short header and then the agent
  layer, with Done when kept as the heading the printout reads and split into
  Works and the cases that are not the normal one. It holds each field rule in
  `pieces.md`, the rules that are not fields, the `Decided` guidance that every
  choice a person would notice is decided on the piece, and the one-line
  `Touches:` format. It holds the fourteen items of the readiness list, its
  severity rule and what it cannot catch, and that `/shape` has a session that
  did not shape the piece run it: a subagent carrying none of the conversation,
  or a new session given the exact line to paste, which `/shape` routes
  straight to the check. `/shape` typed alone picks up a piece still waiting
  for its check, change-triage and founding make a piece ready only through
  it, and each kind of gap sends the piece to the sub-state for who can close
  it. The
  list's bodies are compared with a stored copy, word for word. The check
  writes a
  `## Readiness` section, and a blocking gap sends the piece back through the
  gate with the gap written on it. A Relies on line nobody could read is a
  blocking gap, a container passes when its parts are pieces, and a ready
  piece that skipped the check is checked before a run claims it. It also holds that clarify asks about those cases, data
  and what leaves the tool only when the piece touches them, that WORKFLOW.md
  and PHILOSOPHY tell it, that the list stays out of the founded AGENTS.md, and
  that the replay case for it is written and listed as owed.
- `.agents/tests/plan-helper-routes.sh` proves the helper that writes the
  printout reaches every project. It ships inside the setup-ai-build-kit skill,
  because the shared installer and both plugins carry skills and nothing else,
  and a project without it once fell back to reading the issues by hand and
  named a blocked piece as the next one to build. The check lays out a project
  the way each route leaves one: a whole copy, the shared installer for several
  coding agents and for Claude Code alone, the Claude Code plugin and the Agent
  Plugins folder. It founds each one and runs the printout against a stand-in
  for the GitHub CLI. It then drives the step `/maintain` runs on every visit,
  which adds the helper to a project founded before it shipped, replaces an
  older copy, changes nothing the second time, and refuses a folder that is not
  a founded project or a helper path that is a link. The gate script travels
  the same way, so every route ends with a runnable copy identical to the
  template, and the step adds it, replaces an older copy, changes nothing the
  second time and refuses a link. The state guard hook does the same, and a
  folder or a link in its place is refused with nothing placed. On the same six layouts
  it opens every pointer the founded AGENTS.md, the masterplan and the skills
  name to a file inside a skill. A pointer names the skill and the path inside
  it, never a fixed project folder, because a project installed for Claude Code
  alone has no `.agents/skills/` and a plugin keeps its skills outside the
  project. The check fails on a pointer to a file no skill has, and on the old
  fixed form.
- `.agents/tests/queue-groups.sh` guards what `/queue` may call safe to build
  together, and the plan it prints. The rule that matters is that it reads the
  printout's grouping rather than working safety out again, since the printout
  is where the guarantee comes from. The plan has five parts in a fixed order:
  the order a run builds in, the groups, what a run can do with each piece, what
  stacks on what, and last the exact command that runs it, `/implement queue` or
  `/implement` with the numbers. Each verdict is held, read from the
  printout's marks and never by opening a piece, and so are a piece with no
  Touches line going alone, a piece that waits for its base never reaching the
  numbered command, no command when nothing is ready or a run can take
  nothing, and an older helper with no groups sent to `/maintain`.
  It also guards the blocker being named rather than numbered, a waiting
  question keeping a piece out of the plan, a sized piece never marked ready
  being named under its `Shaping:` column with its blocker named wherever it
  sits, the command
  reporting and never labelling, claiming or building, and `/what-now` keeping
  its cap of three things while offering `/queue` when asked what else can be
  worked on, because a `/what-now` that grew the whole list would undo the split
  that earned the ninth command. The same rule reaches the end of a build: `/implement` and
  section-builder name a next piece only from the printout's `To build` group,
  and never from a hand reading of the issues.
- `.agents/tests/parallel-run.sh` guards the question a run asks before it
  builds a group's pieces at the same time. People who took on several pieces
  built their own coordinator when the kit offered none, and the kit's rules
  reached only as far as its brief: claims and reviews were skipped, and a
  merge went ahead on a standing yes. So on Claude Code the run asks in fixed
  words, with the memory warning, only when the plan holds a group of two or
  more pieces it can take, and one at a time is the default. It holds the
  answer's bounds, `at_once` in the state file and its survival on resume,
  and that only one group runs at once. It holds hardest that the session
  which started the run alone claims, writes the run state, runs each review,
  opens each pull request and merges one at a time, while a background agent
  only builds one piece in its own worktree and never pushes, and that an
  agent which never reports counts as a failed attempt. A pushing agent would
  make a first upload nobody was asked about.
- `.agents/tests/gated-turns.sh` checks the rule that decides when a scripted
  replay turn is due: that a turn with no precondition still fires by position,
  that one with a precondition waits until the kit has said the thing it
  answers, and that a precondition nothing will ever match gives up after two
  fillers and sends the line anyway, so the gate can cost tokens but can never
  fail a run that would otherwise have passed. It also drives the `# merge:`
  line, which has the person merge every open pull request before a turn that
  says the fix was merged, so that line is true when the kit reads it, and the
  `# prepare:` line, which has the harness build a starting state no
  conversation should, such as scenario 49's instructions past their ceiling.
  It runs the preparation that leaves scenario 51 one recipe in both copies of
  the ship skill a whole copy carries, and proves that preparation refuses a
  folder inside a git work tree, so it can never delete a recipe here. It holds
  that scenario's gate open on a menu, and shut on a reply that only names the
  host or on an interview guess the person may change. It runs both halves of
  the preparation behind scenarios 52 and 53. The first half makes the fixture
  a live tool before the first commit. The second, in `.after-commit.sh`, cuts
  two branches from that commit and pushes them, so the project starts with two
  open pull requests that both merge and still pass the project's checks.
  Neither half runs on a folder that is not a fresh replay project. It holds
  52's gate open on the ways of asking for a merge yes it lists, and shut on a
  reply that says it merged. It holds 53's open on a reply saying, in the first
  person or the past tense, that the kit merged, and shut on the replies it
  lists that ask first or say what a merge would do. It runs both halves of
  scenario 54's preparation, which writes a small Next.js tool live once on
  the Vercel recipe into a blank kit, cuts the one pull request's branch, and
  writes the stand-in host's list of what the first launch left. The tool's
  tests pass on `main` and on the branch where Node can read TypeScript by
  itself. It holds 54's gate open on a reply saying the kit merged, and shut
  on one asking first, saying what happens once it is merged, saying it has
  not merged yet, or reading "Merged: not yet". It carries a `# grants:` line
  beside the turn it marks, and never into the words sent. It holds that the
  harness marks each turn in the GitHub log and logs every push the remote
  receives, and reads one push back. It runs both halves of scenario 55's
  preparation. The first adds one ready piece and a changelog line saying no
  code was uploaded. The second names the first branch `main` on a project
  that started on `master`, and leaves the remote empty, so the branch listing
  exits 2. Neither half runs on a folder that is not a fresh replay project,
  and the second refuses a remote that is not empty. It holds 55's gate open
  on the ways of asking before the upload it lists, and shut on a reply saying
  the kit already pushed or uploaded, or only reporting a pull request. It
  runs both halves of scenario 57's preparation. The first adds three ready
  pieces, the second waiting on the first and the third leaving the shape of
  its stored record unsettled. The second puts `main` on the remote, so the
  code is online before the run. Neither half runs on a folder that is not a
  fresh replay project. It holds 57's gate open on the question whether
  pieces that pass may be merged, in each wording it lists, and shut on a plan
  that has not asked it.
- `.agents/tests/grader-recovery.sh` checks that the replay grader recovers a
  grading missing only its final brace or carrying one stray brace after it,
  and still refuses one that was cut off partway or followed by other text.
- `.agents/tests/replay-state.sh` checks that the replay harness grades the
  world a run leaves behind: it builds end-states by hand and proves the
  acceptance-record assertion catches a masterplan that recorded the acceptance
  the contract names, a kit that wrote nothing, and an acceptance invented where
  none was due, that an area covered by a recorded acceptance is marked
  accepted and never done, that the save-route assertion catches a founding that saved
  no checkpoint or pushed one it should have kept local, that the
  issue-invariants assertion catches an idea closed as not planned reopened
  or moved into `state:building`, that the route assertion catches a piece
  that got the label its work promised without the work: a waiting shaping
  sub-state taken off with nothing recorded, `state:ready` sitting beside an
  open question, and a note moved to ready without ever being sized, and that the split assertion catches a request cut
  up the wrong way: a part wanting a different outcome from its parent, two
  pieces waiting on each other for one outcome, and a part named for a layer
  rather than a slice. It also holds the recipe record a founding leaves: that
  the recipe assertion catches a `founding-menu` line naming only one of the
  recipes on the menu, and an AGENTS.md with no `Recipe:` line, with `Recipe:
  none`, or naming a recipe other than the one the contract expects. It passes
  a founding that wrote both records whole, even with the template's
  placeholder left below the real line. For a menu of one it builds a project
  whose own recipes folder holds one file, and proves that a `founding-menu`
  line copied from this repository's longer menu is a miss there. Last, it
  holds the pull request end state for scenarios 52 and 53. It reads which pull
  requests a project started with from its first commit. A merge made on "put
  it live" alone is a miss for 52, and so is one of two pull requests left open
  for 53. A pull request the kit opened itself during the run is not counted.
  For 52, a change put on the remote's `main` by a Git merge or a squash counts
  as merged, so that route is caught too. For 53, only a merge made on the pull
  request counts, and a change pushed straight to `main` is a miss that says
  so. So is a launch record pushed straight to `main`, while one merged
  through a pull request of its own passes. For scenario 54, a second launch
  on the Vercel recipe, it holds the deploy and the rollback line. One new
  production build of the merge passes, counted from the pushes to `main`
  even when nobody asked the host. The same version built twice is a miss,
  whether the kit deployed it again or redeployed what was already live, and
  so are no new build, two pushes that build two versions, and a rollback
  nobody asked for. A build from merging the launch records' own pull request
  through GitHub is not a second app build, while records pushed straight to
  `main`, merged on this computer, or carrying an app change are. A new
  changelog line has to say rollback is possible and not tried, wherever the
  run saved it. A line saying rollback was tested, or "yes" with no "not
  tried", is a miss, and so is one calling rollback impossible when an earlier
  build is listed. A not-tried phrase about the restore does not excuse a
  rollback said to be tried beside it, and a passing note about the rollback
  target is not judged. For scenario 55, a first upload into an empty
  repository, it reads the GitHub log as a timeline of turns and pushes. A
  push before the turn marked as the person's yes is a miss, and so is one
  after a filler, since a filler grants nothing. So are `main` pushed with Git
  rather than created through the API, `main` on the remote with no API call
  behind it, nothing uploaded after the yes, and no default branch or pull
  request. A log with no turn markers is unobservable, not a pass. It also
  holds that the stand-in's state is read from beside the project, since the
  copy inside it is a tracked file the kit's own Git work can move. For
  scenario 57, `/implement queue` over three ready pieces, it builds the run's
  end state from the scenario's own preparation. The state file lists every
  piece, a piece after the one it waits on, and the run's folder is never
  committed. Each built piece carries `to check`, a claim naming the run and a
  pull request. The one that waits on another aims at that piece's branch,
  carries its commits on the remote and says which to merge first. The piece
  whose record's shape is not settled is back in shaping with its question
  and no pull request, with or without a branch, since a run that sees the
  choice at the plan cuts none. Left `ready` and skipped is a miss, even with
  a reason, and the check fails while scenario 57's Evidence line still allows
  it. Nothing is merged when the person said not to, and the state file says
  merges were not pre-approved. However the run ended, no piece is left
  `waiting` or `building`, the earliest claim on a built piece names the run,
  a branch has one pull request, and a piece sent back or parked keeps any
  branch it had on the remote and loses the run's assignee. Each of those
  taken away is a miss, and so are a missing `progress.md`, the wrong pull
  request in the state file, and a built piece that carries more than `to
  check`. A first piece parked after three failed attempts, or at an early
  end with no attempt, passes when the piece on top of it was never built,
  keeps `ready` and is skipped with a reason. On the worktree route, where
  the state file records a worktree for a piece, a run state written inside a
  worktree is a miss, and so are a worktree outside `.agents/worktrees/`, the
  main folder left on a piece's branch, and the worktrees folder committed.
  It also holds that `baseline.md` names the scenario's run, measured or owed.
- `.agents/tests/codex-github-auth.sh` rehearses the portable Codex session
  launcher with stand-ins for both command-line tools. It holds that a stored
  login reaches only the new process's environment, existing token variables
  need no stored-login read, forwarded arguments survive, and a failed or
  malformed credential read starts no session and prints no credential. It
  also holds that shell snapshots are disabled and the permission profile is
  preserved. The installation-route rehearsal checks that the launcher ships.
- `.agents/tests/check-tooling.sh` runs the setup tooling report against a set of
  throwaway PATHs and reads when it stops: a missing tool or a signed-out account
  blocks founding, while issues switched off or a read-only account do not.
  Given a recipe, the report also names each command-line tool that recipe's
  launch checks run, and the check holds that a missing one never stops
  founding and that a project naming no recipe is never asked about them.
  A Git older than 2.17, which has no `git worktree remove`, gets one line
  naming its version, and founding carries on.
  It also runs the report in throwaway projects whose `origin` is the kit's
  own repository, in https and ssh form, in capitals and with no `.git`, and
  in one where only GitHub names it. Where `origin` names the kit, the
  stand-in reports a neutral name, so only the origin match can catch it.
  Each time the report says so, asks GitHub nothing more about that
  repository where `origin` already named it, and still does not stop
  founding. A fork under another owner, and a name that only starts like the
  kit's, are left alone. The report matches with the shell alone, since the
  check's own PATH once had no `tr` and a lower-casing step failed without a
  word. Every other case runs from a folder with no `origin`, so the suite
  gives the same answer wherever it is run from. Last, it drives the part of
  the report that says what the walk-through can look with, using stand-ins
  for `pdftoppm`, `soffice`, `magick` and `npx`. Each is reported ready or
  missing, `libreoffice` and an older ImageMagick's `convert` count, and
  `npx` without Playwright counts as missing. A missing one prints the install
  command for the machine the check runs on and never stops founding, and
  none of them excuses a missing founding tool.
- `.agents/tests/completion-report-shape.sh` guards the source of the /setup
  completion report, which is watched by hand rather than replayed: it proves
  completion-report.md still leads with what is ready, keeps technical state out
  of the lead, ends on a clean cut pointing at /implement, and says no code was
  uploaded rather than that nothing was, since founding puts the pieces online
  as issues. It fails on a copy with any of those rules removed.
- `.agents/tests/setup-notes.sh` guards the working notes the founding
  interview keeps: that the /setup skill still writes each agreed answer before
  the next question, keeps those notes out of every commit, resumes from them,
  and clears them once the masterplan holds the same answers. It also proves in
  a throwaway project that a file under `.agents/tmp/` stays untracked.
- `.agents/tests/empty-fields.sh` guards the two words a scenario uses for a
  field with nothing in it, and their opposite meanings: `none is due` says the
  kit must not do the thing, `unaffected` says the scenario does not judge it.
  It guards the contract header where a scenario author reads them and the
  grader prompt where they are applied, since a word defined in one and unknown
  to the other is what let a grader improvise. `check-parser.sh` refuses a third
  wording mechanically.
- `.agents/tests/founding-carries-on.sh` guards the ending of the step that
  tries to talk the person out of building: that the cheaper option is still
  named and the case still made, but made once, and that a person who wants the
  tool anyway gets it recorded and founding carried on rather than the question
  asked again, and without the case itself ending the turn. It guards the wider
  rule that a question founding does not need becomes an open question in the
  masterplan instead of a gate, since otherwise the next stall just happens on a
  different question. It also guards the read-me step, where an installation
  that arrived as a whole copy of the kit leaves no placeholders to fill in, so
  the file is left alone and said to be left alone rather than founding stopping
  to ask. It guards the founding save, which is always the checkpoint route
  however shared the tool will become, since a reachable remote once had a
  founding pushed and a pull request opened against a promise that nothing would
  be uploaded. And it guards the masterplan review, which the build path decides
  and which records a missing reviewer as a gap rather than waiting for one,
  because the wait had no exit and cost two measured runs their whole founding.
- `.agents/tests/founding-branch.sh` guards the read of which branch founding
  is on. A real founding saved its checkpoint onto a feature branch the person
  had checked out, `main` never received the records, and the commits were
  moved across by hand. So the read comes before the bootstrap script writes
  anything, and finds the default branch from the remote, else a local `main`,
  else a local `master`. On another branch with nothing unsaved, founding
  switches and says so in one line. It never switches a branch holding unsaved
  work, and a switch that fails never stops founding. The person may keep their
  own branch, and a founding saved off the default branch names that branch in
  its changelog line and its completion report. `adopting.md` and WORKFLOW.md
  carry the same story.
- `.agents/tests/kit-version-record.sh` guards the record of which kit release
  a project holds. Two external projects could not tell. One carried an older
  release's label with newer files, and the other stayed six releases behind
  for weeks, then updated with a bare `npx skills update` that dropped a
  renamed skill. So founding writes a `kit|<version>|<commit>` line into
  `.ai-build-kit-maintenance`, the version from the installed maintain skill's
  `VERSION` or, in a whole copy, `.ai-build-kit-version`, and the commit its
  tag points at, following an annotated tag once. A failed lookup writes
  `unknown` and founding carries on. The first changelog entry names the same
  two. `/maintain` rewrites the line after an update and writes it where it is
  missing or disagrees. `/what-now` reads the files rather than the line, and
  names a newer published release in one line, saying nothing when they match
  or the call fails. The founded `blocked-commands.md` says the kit is updated
  only through `/maintain`, and WORKFLOW.md tells the person.
- `.agents/tests/founding-menu.sh` guards the recipe menu founding offers. The
  menu is the files directly in the `recipes/` folder of the installed ship
  skill, found beside the founding skill and never at a project path, since the
  two plugin routes install the skills elsewhere and a project path there finds
  an empty menu. A shared part or a recipe still waiting for its real run is
  never offered. Exactly one recipe is recommended, with a tie going to the
  first by file name, and the same reply says it is the default, so showing the
  menu never ends the turn. A menu of one is still shown, with the same rules
  and the same default sentence, in a reply before the stand-up begins rather
  than reported in the completion report, and the two questions before it are
  asked unless the interview answered them. A real founding with one recipe
  skipped all of that while the rules for any menu were already written. A
  person may bring their own stack and hears once what the kit then cannot
  check. The choice is recorded by file name with `.md` included, and neither
  the menu nor the recipe's tool report ever stops founding. That report runs
  for every chosen recipe, a menu of one included, and the completion report
  says what it found. Whatever the choice, founding writes every file on the
  menu into a `founding-menu` line in `.ai-build-kit-maintenance` before the
  first checkpoint, so the monthly visit can tell a recipe added later from one
  the person already passed over. Where a recipe carries a `Plan terms:`
  line, founding says it once beside that recipe to a work team, a business
  or paid work, never calls that account free, leaves it out for a personal
  project nobody is paid to build, and asks nothing when the interview did not
  say. Two foundings for a work team missed that line's fact, and one called
  the account free. Product names are left to
  `hosting-request.sh`.
  `agent-plugin.sh` and `claude-plugin.sh` each check that every menu recipe
  arrives in their installed layout.
- `.agents/tests/coverage-read.sh` guards the read that compares the masterplan
  against the pieces: the rules that keep it honest, that /setup and /sync both
  still run it, and that WORKFLOW.md explains it for founding and for sync. It
  includes permissions, data, connections and settled terms left on pieces
  closed as not planned, and fails on a copy with any one of those rules
  removed. The coverage read names no `parked` piece.
- `.agents/tests/masterplan-edges.sh` guards where ownership facts are written,
  the settled term a piece keeps when it is reshaped or closed as not
  planned, and the single
  offer to shorten an overlong masterplan, which moves detail onto pieces or
  concept files and never into a new catch-all document. It also holds the
  rehearsal's setup and expected result for a term on a closed piece.
- `.agents/tests/shape-research.sh` guards the two research steps that share the
  `shaping:research` sub-state: the rules that keep an existing-work search honest
  about maintenance, licence, cost, data, and removal, that /shape offers both
  steps and says which it ran, and that change-triage, pieces.md, and
  WORKFLOW.md all describe it as covering both.
- `.agents/tests/reach-check.sh` guards the check that asks what else a change
  reaches and which existing tests cover it. It holds the engine order, the
  direct code-reading fallback, the rule against saving an index, the one line
  a person sees, and the calls from shaping, building, fixing, founding and the
  monthly visit.
- `.agents/tests/sensitive-area-map.sh` guards the readable map between named
  sensitive areas and code. It holds the Build with care boundary, the optional
  local data scan, each skill that reads the map, and the shipped check that
  fails on a moved path or an unassigned source folder.
- `.agents/tests/checks-first.sh` guards the checks written before the code and
  the walk-through that stands in for the person's try. A check written after
  the code can pass on today's code, and a builder working alone can weaken a
  test until it passes. So it holds that section-builder writes each machine
  check the Done when lines name before any code, runs it on today's code,
  records that it fails and commits it on its own, and that a check already
  passing means the line is wrong and is reported rather than built. An
  existing test changes only when the piece's Under the hood names it, and a
  committed check changes only by being reported. The check runs
  `test-guard.sh` in a throwaway repository on a piece stacked on another. Every
  kind of changed test the piece does not name is listed, one named only outside
  Under the hood or inside a longer path among them, and a moved test names its
  new copy. The parent piece's change and a new test file are not listed.
  Nothing is listed once the piece names each one, until a check changes after
  its own commit. The guard's base is the branch the piece was cut from, never
  one worked out from `main` alone. It holds that a wrong test or an impossible
  line is reported and never worked round, that the walk-through records what
  it saw with sample data, and that the piece still goes to `to check` and
  closes on merge. On the checkpoint route, a walk-through that could not see
  the screen takes the opt-in path, since no pull request exists to wait in.
  Either opt-in gives one address a request reached and up to three numbered
  things to try, with nothing saved before the reply, and an unattended run
  opens the pull request saying it waits for the try. It also holds founding's
  offer of sample data and the same rules in `/fix`.
- `.agents/tests/fix-history-first.sh` guards the repair steps that read prior
  work and existing tests before a new attempt, search saved history from a
  known-good point, remove temporary instrumentation, and refuse to call a
  retry-only test green.
- `.agents/tests/masterplan-changes.sh` guards the change each piece carries
  for the masterplan, its application during save and recovery, the saved state
  the page was checked against, and the monthly count that offers /sync when
  later work touched data, permissions or connections.
- `.agents/tests/record-habits.sh` guards a decision's optional evidence line,
  the read that spots when its support has gone, the link back to the build
  that found a new piece, and the single question about work untouched for a
  month. Each rule is removed in turn to prove the check catches its absence.
- `.agents/tests/structure-change.sh` guards the small structure comparison
  around a build: its live engine and import fallback, silence when nothing got
  worse, fixed lines without a score, and the quarterly count of change spread
  from saved history.
- `.agents/tests/test-strength.sh` guards the optional check that breaks changed
  code to see whether tests notice. It holds the Build with care boundary,
  local scope, plain report, sorting of misses, the offer during repair, and
  the rule against adding tests just to raise a count.
- `.agents/tests/test-strength-rehearsal.sh` runs weak tests in a throwaway
  JavaScript project. They catch one deliberate breakage and miss a boundary
  error; the report takes its counts from those runs and its words from the
  shipped rule.
- `.agents/tests/trim.sh` guards the trim, the single pass that takes out what
  a change added and does not need before the person tries it. The rule it
  guards hardest is the limit on what the trim may change: removing and
  folding, never a restructure, and never a test. A pass allowed to reshape
  code until the tests stop passing learns to delete what the tests miss, and
  every step still looks green. It also holds that the trim runs once, stays
  off Explore privately, judges a function against a published limit rather
  than the project's own average, and says nothing when it finds nothing.
  `.agents/tests/trim-rehearsal.sh` runs the pass on a throwaway piece built
  on a saved commit. It reads back that a tested one-user wrapper is folded,
  that an unused export and an unused dependency are taken out, that a file
  reached only at run time is removed, breaks a test, and is put back with the
  test untouched, and that an untested wrapper, a one-use dependency, a copy
  and a new function past the limit are only reported. Code from before the
  piece is left alone, the trim sits in its own commit, undoing that commit
  brings back the piece as built, and a clean change produces nothing.
- `.agents/tests/check-floor.sh` guards the type check and linter a founded
  project receives, and the eight reporting rules every whole-project read
  shares. Those rules were written down with the floor because it landed
  first, and the later reads point at them, so a rule that went from the file
  would loosen every read at once. It also holds that the green-tick sentence
  is unchanged, since the floor is meant to add nothing for the person to learn.
  It holds that the type check and lint leave `.agents/worktrees/` out, since
  a run's worktrees are whole copies of the project, and that doing so changes
  no rule. The test run leaves them out too: the floor names the setting for
  Vitest, Jest and Node's own runner, says pytest and Go need nothing, and
  has a runner with no such setting recorded in the stack section and
  founding carry on. WORKFLOW.md says the checks leave the copies out.
  `.agents/tests/check-floor-rehearsal.sh` is the half that runs. It founds a
  throwaway Python project from the shipped workflow template, takes its
  commands from the shipped table, and watches the check go red at the type
  check on an error no test reaches, green once it is fixed, and red at the
  linter on an unused import. It then does the same for a TypeScript project,
  the language the web app recipes build in, with the tools installed as that
  project's own dependencies. It does not run the Next.js starter, since a
  project the starter made keeps the starter's own lint settings. Both
  projects carry the gate script where founding places it and stay green. In
  the Python project an unused import added to that copy turns the linter
  red, which proves the green counts, and the type check passes on it by name,
  since `mypy .` leaves folders starting with a dot out.
- `.agents/tests/waste-read.sh` guards the quarterly read for copied code,
  unused code and unused dependencies: that it stays off Explore privately,
  keeps the settings chosen on purpose, drops a name found anywhere else in
  the project, shares the cap of three proposals, says it cannot find two
  pieces of code doing one job differently, and stays silent when it finds
  nothing. `.agents/tests/waste-read-rehearsal.sh` runs the engines named in
  the shipped table against a throwaway project carrying a renamed copy, an
  unused export and an unused dependency. It reads back that each is named at
  a real line, that an export a configuration file names is dropped, that no
  percentage reaches the report, that a clean project produces nothing, and
  that nothing was written into either project.
- `.agents/tests/structure-read.sh` guards the quarterly structure read: that
  the earlier structure is derived again from saved history rather than kept,
  that a loop already there at the last visit is not news, that a comparison
  which could not happen says so, and that reliability is only ever a missing
  pattern at a named place. It also holds the clause in the shared rules that
  lets a read compare against an earlier state without saving one.
  `.agents/tests/structure-read-rehearsal.sh` runs it against a throwaway
  project whose history holds a recorded visit, a loop from before it and a
  loop from after it. Only the new loop is named, at the line where each file
  imports the other, the project's working tree is unchanged, and a second
  read after the next visit says nothing.
- `.agents/tests/boundary-rules.sh` guards the offer to hold a sensitive
  area's boundary in the project check: only for a boundary the masterplan
  already names, offered and never imposed, added or removed only on a yes,
  green on the day it is added, withdrawn plainly where the language has no
  tool, and worded in the person's own sentence. A rule that turned the tick
  red for a boundary nobody agreed would teach people to ignore red.
  `.agents/tests/boundary-rules-rehearsal.sh` founds a throwaway Build with
  care project, fills the shipped configuration template from the boundary
  line the masterplan records, and watches the check go red at the `Boundary
  rules` step on a crossing import, carrying the person's sentence word for
  word, and green once the import is gone.
- `.agents/tests/document-read.sh` guards the read in `/sync` that checks a
  project's own documents against the project: that it reads only the README
  and what AGENTS.md points at, that a document saying less than the project
  does is never a finding, that it says it cannot tell whether a described step
  still happens, that a name already on an open piece is not raised again, and
  that a correction changes the stale name and never the prose around it.
  `.agents/tests/document-read-rehearsal.sh` runs the shipped
  `document-claims.py` against a throwaway project. It proves each of the four
  kinds of stale name is found at its line and that nothing true is flagged,
  including a file git ignores on purpose and a document nothing points at. A
  slash command such as `/implement`, a repository name and a web address are
  not taken for files, and a file name written from another folder is found
  where the project keeps it. Every founded project's documents name its
  commands that way, and an earlier version reported each one as a missing
  file. Concept files are read through the list in `docs/README.md` once
  AGENTS.md points at it, and a file in `docs/` the list does not name is not
  read. It also proves a clean project produces nothing, the script writes
  nothing, and the document changed longest ago comes first. A piece's file
  in `changes/` is part of the changelog, so it is never read as a document,
  and neither the folder nor a file the last fold took away is called missing.
- `.agents/tests/document-bloat.sh` guards the quarterly read for documents
  that repeat each other or are no longer needed: that it reads every
  document rather than only the ones AGENTS.md points at, never offers the
  README for deletion, confirms each finding, offers a tidy-up rather than
  making one, shares the cap of three proposals, and says it cannot find two
  documents saying one thing in different words.
  `.agents/tests/document-bloat-rehearsal.sh` runs the shipped
  `document-bloat.py` against a throwaway project carrying a repeated
  paragraph and a note nothing names. It proves both are found, and that a
  README nobody links to, the records, a short shared sentence and a page
  naming files the project no longer has are left alone, since the document
  read in `/sync` reports those one name at a time. A piece's file waiting in
  `changes/` is left alone too, even when it repeats a paragraph. A clean
  project produces nothing, and the script writes nothing.
- `.agents/tests/request-record.sh` guards the request record checked before
  live use, its data exclusions, and the monitoring caution given once unless
  someone already receives alerts. A missing record is a warning said once and
  written in the changelog, and the launch goes on, so it holds that `/ship`
  neither waits for the record nor asks the person to choose to go without it.
  It also holds the repair step that reads the tool's record after launch,
  alongside the person's report.
- `.agents/tests/secret-location.sh` guards where a secret the project keeps
  outside `.env` is written down: its location, never its value, in the
  masterplan's "How it stays running" section, read back before any step
  that needs it. It holds hardest to what a check says when nobody knows the
  location. A real launch once skipped the backup, the restore and the
  database guard, and wrote in the changelog that the database password was
  not on this computer, when the person had named its file in an earlier
  session. So `/ship` asks once, and a check that still cannot run says the
  location is unknown, never that the secret is absent. A secret is passed by
  its location and never read or shown, and one given as an answer is recorded
  nowhere and the person is asked to rotate it. The project's own
  AGENTS.md sits at its line ceiling, so it carries the short form of the rule
  and the check guards both.
- `.agents/tests/no-stored-logins.sh` guards what the kit may use to reach a
  service, and what waits for the person before a live service changes. A real
  launch told the person it could not read a sign-in setting, then read the
  service tool's stored login out of the keychain and used it to read and
  change that setting. That login reaches every project on the account. So the
  kit uses only a tool's own commands and the keys the tool already sends to
  the browser. It never takes a login another tool keeps, and never reads what
  it has said it cannot. When it cannot, it says so and names the page. The
  same run, while building, pushed a settings file to the live service and
  switched off a setting it could not switch back on. It also wrote every key
  to a shared temporary folder. So a command that changes a live service, other
  than saving code through the save route, waits for a yes. That yes names
  everything the command will change, not only the setting the kit meant to
  change, and says whether it can be undone. The commands the project's recipe
  names need no second yes, and a secret key goes straight into the file that
  uses it. The check holds the
  rules in `/ship`, second-opinion, section-builder, WORKFLOW.md and the
  project's own AGENTS.md, and proves each one load-bearing in each file.
- `.agents/tests/standing-instructions.sh` guards the project's instruction
  ceiling and the monthly offer to trim repeated code information. It removes
  each written rule in turn and drives the validator's own count at the limit.
  The ceiling is for the founded file, so the count adds a fixed budget for the
  lines founding writes to the template's own, and a margin of 5: with the
  measured 23 lines and the Next.js starter's 10, a template of 161 lines
  passes and one of 162 fails. A template of 196 lines once passed while a
  fresh founding came out at 219. It then fills the shipped template the way
  founding does, adding the measured 23 lines and the Next.js rules block, and
  requires the result to fit the budget and stay 5 lines under 200.
- `.agents/tests/triage-overlap.sh` guards the warning that another open piece
  would be built in the same place: what change-triage compares, that it names
  the clash before the routing step rather than after it, that it blocks
  nothing, and that it stays quiet when no piece shares a subject.
- `.agents/tests/existing-artifact.sh` guards the route that lets a mock the
  person already has settle a question: the ten rules that keep it safe, that
  clarify, /shape, and the decision prototype all check for one before building a
  throwaway, and that /setup and WORKFLOW.md name it.
- `.agents/tests/wiring-picture.sh` guards the masterplan's picture of what the
  tool reaches outside itself: the drawing rules, that the example draws nothing
  internal, that founding reads it back for confirmation, and that a piece
  changing a connection redraws it rather than letting it go stale.
- `.agents/tests/manual-step.sh` guards the step only the person can do: the
  rules for a piece's `Waiting on you` section, that such a piece sits in
  `shaping:clarify` until the step is done so no run takes it, and that the
  two other ways back from a build stay apart from it: a caution kicks a piece
  back to `shaping:clarify` and three failed attempts to `shaping:spec` or
  `shaping:research`, each with a `## Kickback` section. It holds both
  kickbacks where /implement acts on them, that /implement neither builds such
  a piece nor skips it in silence, and that /what-now names it as the person's
  own to-do without ever asking for a key in a message.
- `.agents/tests/screen-rules.sh` guards the screen rules, their two build-time
  entry points, and the limit on what their report may claim. It proves the
  refusal to call a screen accessible, compliant or good is load-bearing, since
  a partial rule check cannot earn that conclusion.
- `.agents/tests/notice-is-owed-by-the-refusal.sh` guards what triggers the risk
  notice after three failed repairs, and it holds two rules. The refusal owes
  the notice whichever route follows it, in the same reply, because hanging it
  on the route meant some escalation routes carried it and the rest left the
  person with a refusal and no reason. And three attempts are counted by the
  fault surviving rather than by the kit's own tally of which fixes should
  count, because being right about the count is no reason to withhold the
  notice. It also holds that stopping there is a pause for the person rather
  than a refusal: if they carry on after the notice, the next attempt goes
  ahead on the record. Both are written rules rather than rates, since the
  same scenario comes out differently on `sonnet` and on `opus`. The runs
  behind them are recorded in `.agents/tests/replay/baseline.md`.
- `.agents/tests/shared-route-adds.sh` guards the shared installer route. The
  kit renamed `plan` to `shape`, and a project that updated across it with the
  installer's `update` command lost `plan` and never received `shape`, because
  that command refreshes only what the lockfile already lists and drops any
  other name in silence. The version file said the project was up to date,
  since the same update rewrote it. So the check holds that the route is the
  installer's `add` command, that the monthly pass counts the lockfile against
  fourteen, and that each rename migration fires on what is on disk and has a
  branch for the state where the old skill is gone and the new one never
  came. It also holds that a rename rewrites the command list in the project's
  own AGENTS.md with approval, because a person left to do that by hand after
  every rename stops updating. It reads the rules back from the maintain skill
  because the installer is somebody else's tool and nothing here can watch it
  run.
- `.agents/tests/whole-copy-leftovers.sh` guards the tidy step for a project
  founded from a whole copy of the kit. Such a project carries the kit's own
  generated adapters, which the shared installer never refreshes, so every
  command shows twice in Claude Code and a renamed command lives on in a file
  nothing removes. A hand deletion in one project fixes one project, so the
  step lives in maintain. The check holds the two rules that keep it safe: an
  adapter is recognised by its generated marker and never by name, and a
  retired skill folder only by the kit's former names and absence from the
  lockfile. It holds that the step is run from the monthly pass, removes on
  approval, and that WORKFLOW.md says so.
- `.agents/tests/older-project-upkeep.sh` guards four things an update never
  reaches, because it refreshes skills and nothing else. A leftover `plan.md`
  is offered for a move into issues on every visit that finds it, since it was
  once offered only on the one visit that first brought in `/shape`, and a
  project that missed that visit kept it for good. The offer comes back after
  a no, and a `plan.md` that is plainly the person's own notes is left alone.
  A pointer in AGENTS.md or the masterplan that names a kit skill's file by
  its place in `.agents/skills/` opens nothing on a Claude-Code-only or plugin
  install. So the visit runs a shipped script that lists such lines and, on a
  yes, rewrites each to name the skill, changing nothing else. The check runs
  that script. An old project's pointers are found and rewritten to the form
  today's templates use, and a second run finds nothing. So are the pointers
  of the earliest releases, which name the founding skill by its first name,
  `start`, since the rename removed that folder and those open nothing on any
  route. A review found the first version missed them. The same review found
  it rewrote a pointer inside a command or a link and broke the line. So only
  a pointer that stands alone, as a whole code span or a bare path, is
  rewritten. One inside a command, a link, a longer path, or naming a file the
  skill no longer has is listed with its reason and left exactly as it was.
  A second review added three more: a fenced or indented code block, a span
  in double backticks, and a file with Windows line endings, which must come
  back with only the pointer changed. A file that is not readable text gets
  one line rather than a crash. A third review found a block shown inside a
  longer fence, which closed at the first shorter one, so a fence now closes
  only on a run of the same mark at least as long as its opener.
  A project founded from today's templates gets no offer. A placeholder, a
  mention of the folder, and a project's own skill in the same folder are
  never found. The script's list of skills is the kit's fourteen, so a rename
  cannot slip past it. A visit asked to leave kit updates alone does not
  copy in the reminder script, still says the visit was recorded, and says the
  reminder was left out. The visit no longer offers to move a project onto
  the six piece states, since those states are gone, and the check fails if
  the maintain skill or WORKFLOW.md names that move again. A project founded
  before AGENTS.md became
  an index is offered the move onto it once, with the ceiling step for its
  check in the same offer. No fact is lost, a second visit after a yes says
  nothing, and a no is recorded with the template's section headings, so the
  offer comes back once when a release changes them. On a project already on
  the index, the monthly trim moves each fact to its home rather than cutting
  it.
- `.agents/tests/offer-recipe-move.sh` guards the monthly offer to move a
  project onto a recipe. It applies to a project with `Recipe: none` or no
  `Recipe:` line, whose stack matches a recipe's build stack in substance even
  if it runs somewhere else. The rules it holds are the ones whose loss a
  transcript would not show. The move is offered and never required, nothing
  changes without a yes, and a yes becomes a piece rather than work done in
  the visit. While that piece is open, the offer does not come back. A no is
  written into `.ai-build-kit-maintenance` with its date, the recipe and the
  menu that day, and the offer returns only once the menu or the stack has
  changed. A person who chose their own stack is offered a close recipe the
  `founding-menu` line does not list, once, even if the stack has not moved,
  because that recipe joined the menu after founding. A project with no such
  line was founded before founding kept one, so every close recipe is new to
  it, once. The visit picks one close recipe only after the founding-menu and
  decline tests, so an older recipe that matches a little better never hides
  a new one. A copy of the data service run on the project's own server is not
  close. The offer names the launch checks the move gains, and nothing is said
  when no recipe is close. It also
  holds that the menu is read from the ship skill's recipes folder at run
  time. It reads the product list from `hosting-request.sh` and proves the
  maintain skill names none of them, so the skill names no product even
  though its offer is about one.
- `.agents/tests/stale-branches.sh` guards the monthly step that lists old
  branches whose work already reached the default branch. It holds two rules
  hardest. The step never removes a branch, and gives the person the command
  instead. And it keeps the branches Git confirms apart from the ones only
  GitHub records as merged, because a pull request merged by squashing leaves
  the branch's own commits outside the default branch, so Git's own check
  misses it and only the forceful command removes it. It also holds what is
  never listed, including a branch the project says stays, without the kit
  guessing one by its name, and that a branch with work added after its pull
  request merged stays off both lists.
- `.agents/tests/push-to-main-rules.sh` guards the deny rules a project's
  Claude Code settings carry against a direct push to `main`. The first rules
  matched three exact spellings, and a real run pushed with
  `git push -q origin main`, which none of them matched. Nothing here can run
  Claude Code's own matcher without a model, so the check uses a small one in
  `.agents/tests/lib/permission-matcher.py`, shared with `merge-ask-rule.sh`,
  that follows the documented rule shape and is tested first against the
  examples in the documentation's own table. It then feeds it the spellings
  `blocked-commands.md` says are refused and the ones it says are missed, so
  the written gap and the rules cannot disagree. A branch that only starts
  with `main`, such as `main-fix`, must still push. Each rule is taken out in
  turn to prove it is needed. It also holds the monthly offer that brings the
  rules to a project founded before them: offered once, named, added only on
  a yes, with nothing else in the file touched, and a no recorded so the offer
  returns only when a release adds another rule. The same holds for the rules
  that refuse a recursive delete, `git reflog expire` and `git gc` with
  `--prune`, whose lists sit under their own heading and are read from it. A
  written list of commands that must still run, such as deleting one file or a
  plain `git gc`, keeps those rules from growing. The offer brings those rules
  too, and a no recorded before they existed does not cover them.
- `.agents/tests/refused-commands.sh` guards what happens when a command is
  refused. In a real project the deny list refused `rm -rf`, and the agent ran
  the same deletion again as `rm -r`, which went through. So both
  `blocked-commands.md` files say to stop and tell the person in one line which
  command was refused and what it was for, and never to reach the same result
  another way: another spelling, another tool, or the same work in steps. A
  person who asks for a refused command is given it to run. Both files name the
  new commands. It also holds `/maintain`'s three removals, which remove a
  tracked folder with `git rm -r` and give an untracked one to the person, since
  a recursive delete is now refused. The other steps that cleared a folder say
  how too: a finished run's folder in `/sync` and an unsaved prototype go to
  the person as a command, and the temporary folders the trim and the
  quarterly reads write are made with `mktemp -d` and left for the computer to
  clear.
- `.agents/tests/speaks-for-the-person.sh` guards the yes the kit waits for
  before it speaks for the person to anyone else. In a project where
  colleagues file issues, the agent posted a comment under the person's
  account to a colleague, and changed the title and scope of that colleague's
  issue, before the person had said to go ahead. So `pieces.md` says that a
  comment, a reply, a review, a mention or a message in another channel waits
  for a yes on the words, shown first, and so does a change to the title or
  scope of an issue or pull request another account opened. It holds how the
  author is read, and that an author nobody can read counts as another
  person's. It holds the bookkeeping that needs no yes, so a run with nobody
  watching still claims, labels, names a merge conflict on its own pull
  request and sends a piece back to shaping, and that
  "tell them" is the yes for the person's own words while a no gives them the
  words to post. `/shape` keeps another author's words under "Original report"
  and names the author. The founded `blocked-commands.md` carries the
  restriction, and WORKFLOW.md's Team use section tells it.
- `.agents/tests/own-computer-work.sh` guards work on the person's own
  computer rather than on the project. In one project a short request about a
  GitHub command led the agent to install a newer GitHub CLI in the person's
  home folder without asking. In another, most of a first day went into
  repairing an editor's install, and facts about that machine were written
  into the project and sent as a pull request. So change-triage names the
  intent, with the project's own folder as the line, and routes it apart: no
  piece, no branch, no changelog entry and nothing written into a tracked
  file, with the person told in the reply. A setup step that would install
  software outside the folder is that work too, so its yes comes first. Anything installed, replaced,
  downloaded to run or removed outside the folder waits for a yes naming what,
  where and how to undo it, a recursive delete goes to the person, and a
  version the project needs goes into AGENTS.md's stack section as a
  requirement. A mixed request is two requests, each with one route, and
  project files changed by accident are named and not committed. The founded
  `blocked-commands.md` carries the restriction after the item on speaking for
  the person, section-builder points to it in step 4, where the project's
  commands first run, and WORKFLOW.md's Day to day section tells it.
- `.agents/tests/content-work.sh` guards a request to use the tool on content
  rather than change it. In one project, testing a document on a report tool
  produced a report, a branch and two changelog entries outside any piece. The
  branch was never pushed, so the project's history never mentions that
  report. So change-triage names the intent and routes it: the run happens in
  the main folder with no piece, no branch and no changelog file, and the
  output and the person's input go to a folder git ignores, checked first with
  `git check-ignore`, or outside the project where an older project's
  gitignore does not cover it. Content the person
  asks to keep takes the build path's save route with its own changelog file,
  and never sits on a branch nobody pushes. A fault the content shows becomes a
  repair or a piece, confidential content falls under the founded rule, and a
  person who leaves gets nothing committed. section-builder step 9 points kept
  content at the save, and WORKFLOW.md's Day to day section tells it. Its
  rehearsal founds a throwaway project from the shipped gitignore, writes an
  input and an output where change-triage says they go, and finds `git status`
  empty, while the same output in a folder git does not ignore shows, and an
  older gitignore fails the check the skill runs first.
- `.agents/tests/merge-ask-rule.sh` guards the confirmation box Claude Code
  shows before a merge on a project whose every merge goes live. The rule that
  a person decides what merges holds only while an agent follows it, and two
  projects built with the kit saw merges made on the agent's own judgement,
  one over a red check. An ask rule binds every session, so the two rules live
  in one template file and one script writes them. The check feeds the shared
  matcher the merges `blocked-commands.md` says are asked about, the commands
  it says never are and the merges it says are missed, and takes each rule out
  in turn. It drives the script on a copy of the founded settings: every deny
  rule and the session-start hook stay, and a remove gives back the file as it
  was. A missing file, a file that is not JSON, the person's own ask rule and
  a line that stops saying `on every merge` each get their own case. It holds
  that founding, the merge step and `/ship` run the script whenever they write
  the line, the one-time offer in `/maintain` with a no recorded, and that this
  repository's own settings never carry the rules.
- `.agents/tests/sync-saves-like-a-piece.sh` guards how /sync saves what it
  corrects. Every skill that changes the records said how it saves them, and
  sync did not: it corrected the pieces, the changelog and the masterplan and
  stopped, which on a project that blocks a direct push to `main` left the
  corrections uncommitted or on whatever branch was checked out. So the
  corrections take the save route the build path already requires, and on the
  shared route arrive as a pull request a person decides to merge. The rule it
  guards hardest is the one about uncommitted work: sync is run after an
  interruption, so a dirty tree is the ordinary case, and the two easy ways to
  get a clean branch are to sweep that work into sync's own commit or to
  discard it. Both destroy the thing sync was called to reconcile.
- `.agents/tests/changelog-files.sh` guards the changelog file each piece
  writes and the fold that gathers them. Every piece used to add its entry at
  the top of `CHANGELOG.md`, so two pieces built at the same time changed the
  same lines, and in a real project nearly every merge in a batch conflicted
  there. So section-builder and `/fix` write one file per piece in `changes/`,
  after the pull request opens so it can carry the link, and the merge folds
  the files in with the shipped `fold-changes.py`, with `/sync` and `/ship`
  folding any a merge made by hand left behind. It holds those
  rules, and that founding, `/ship`, `/maintain` and `/sync` still write
  `CHANGELOG.md` directly. It then runs the fold in a throwaway repository. Two
  branches that each add a file merge with no conflict, while a control that
  adds both entries at the top of `CHANGELOG.md` conflicts. The fold writes
  each entry newest first under the day it reached `main`, keeps the lines
  already there, and empties the folder. A file on an unmerged branch and one
  nobody committed stay out of the history, and a project with no `changes/`
  folder gets nothing written. A real changelog titled its headings after the
  date, and the first fold put new days at the end of the file, so a titled
  heading now sets the order and is never merged into. A name used again by a
  reopened piece is dated by the day it arrived that time. It also holds that
  an entry waiting in `changes/` counts as written, so `/sync` never adds it
  twice, and that neither `/sync` nor `/ship` folds while an earlier records
  pull request that folded is still open.
- `.agents/tests/fold-at-merge.sh` guards the fold the merge step makes. Two
  projects used the kit for weeks and nobody typed `/sync` or `/ship` once, so
  the files in `changes/` piled up and `CHANGELOG.md` stopped on the day they
  were introduced. The merge now folds them inside the pull request being
  merged, just before it merges. It holds the four steps in order: take in
  `main` with a merge commit, fold, commit and push the fold and wait for the
  check on it, and merge only on green. It holds the reason this cannot
  conflict, which is that merges are made one at a time, and where the merge
  runs: the piece's worktree, the main folder when it is on the branch and
  clean, or a worktree made from the pull request's own branch, never from
  `main`. A folder holding uncommitted work is never used. It holds the
  `--no-fold` rule while an earlier records pull request is open, the wait on
  an unfinished check, the checkpoint route's second commit, and that no
  document still says only `/sync` or `/ship` folds. It also holds the nine
  decisions in `docs/design/loop-first-round-2.md`.
  `.agents/tests/fold-at-merge-rehearsal.sh` runs the shipped
  `bring-up-to-date.sh` against a bare repository standing in for GitHub. Two
  pieces merged one after the other leave both lines newest first and
  `changes/` empty. A file merged on GitHub by hand keeps the day it reached
  `main`, and the piece's own file takes today. Running it twice, or after
  another merge folded the same waiting file, writes each entry once, because
  an older fold `main` does not hold is undone first. A conflict from `main`
  exits 1, names the file and leaves the branch as it was. An unreachable
  `origin`, a folder on no branch and one with uncommitted work exit 2 and
  change nothing. A push refused because somebody pushed meanwhile exits 3,
  and asking again takes their commit in. A commit only this computer holds
  is never pushed by the fold, and exits 3 too. A stacked branch whose base
  merged by squash still carries the base's file, and the fold removes it
  without writing its entry twice. A branch not on this computer is
  opened from `origin/<branch>`, a project with no `changes/` folder gets
  nothing written, and the checkpoint route folds in a second commit.
- `.agents/tests/recheck-before-merge.sh` guards the rule that no pull request
  merges on a check that ran against an older `main`. On an outside project two
  pull requests merged one after the other, each green, and together turned
  `main` red, while `/queue` told the person a group could merge in any order.
  So every merge, fold or no fold, brings the branch up to date and waits for
  the check on GitHub on the commit the script prints. Where `main` has not
  moved and nothing waits to fold, there is no commit and no second wait. A
  conflict gets one comment naming the files and goes to `/fix`, and so does a
  check that turns red only after the update, naming what merged since. A
  stacked pull request is re-aimed, then brought up to date. The run's sweep
  finishes each merge before the next piece is brought up to date, leaves a
  piece that conflicts or turns red in `to check` with its reason, and skips
  what stacks on it. No skill, template or WORKFLOW.md says a group can merge
  in any order, and `/sync` leads with a red check on `main`.
  `.agents/tests/recheck-before-merge-rehearsal.sh` shows why: in a throwaway
  repository, one branch renames a function and another calls its old name.
  Each passes alone, and once the first merges, the second fails on the branch
  the script brought up to date. The script never merges anything itself, and
  on a branch already holding `main` with nothing to fold it makes no commit
  and prints the unchanged head.
- `.agents/tests/agent-first-records.sh` guards the founded AGENTS.md as a
  short index. In a real project it grew from 206 lines to 1,019, because the
  build step sent every whole-project technical fact there, dates, issue
  numbers and code names included, and only a monthly offer that kept being put
  off ever read the ceiling. It counts the template's sections: past the
  standing rules, each is 12 lines or fewer and names the file that owns its
  topic, and every such file is one a skill has or the kit writes into a
  project. It proves the count on copies with a section padded, a pointer
  removed or broken, a notes file named, and a date or issue number added. It
  then fills a founded stand-in the way standing-instructions.sh does. There
  only the capability profile and the stack section, which founding fills, may
  pass 12 lines, and they are exempt by name. It
  holds section-builder's route for each kind of fact to one home, with a
  concept file for lasting technical design listed in `docs/README.md`, never
  in AGENTS.md, and the masterplan's short header.
  Last, it runs the ceiling step from the shipped project check in a throwaway
  folder: 200 lines pass, 201 fail with or without a final newline, and the
  failure names both numbers and `/maintain`.
- `.agents/tests/settled-is-recorded.sh` guards the record a settled question
  has to leave: that what settled it is written into the piece before the label
  comes off, and that the piece is read back to decide whether the label goes
  rather than the order simply being followed. Doing the steps in sequence is
  what a run believes it did; reading the piece back is what tells it whether it
  did, and this is the one defect a transcript cannot show.
- `.agents/tests/named-reviewer-is-a-person.sh` guards what a named review can
  be met by. The rule against recasting one was never the part that failed: the
  definition beside it said an independent review means a reviewer who did not
  build the work, and a clean separate session did not build the work, so by
  those words a session qualified. It guards the definition in fit-check.md and
  in the project's own AGENTS.md, and asserts that second-opinion still draws
  the same line, since one phrase meaning two jobs is what let the kit reach for
  the cheaper one. The person may now carry on past a named reviewer, so it
  also holds that the record then says accepted and never done.
- `.agents/tests/acceptance-is-earned.sh` guards what has to be true before
  flagged work is built. The kit gives the risk notice once, in full, and a
  person who carries on after it has accepted: the kit writes the `Accepted:`
  line with their words and the date, and the work goes ahead. It guards that
  definition in `/fix`, fit-check.md, `/ship`, founding, section-builder,
  `/implement` and the project's own AGENTS.md, and that none of them drifts
  back to a stop. An unattended run still stops at a sensitive area, because
  nobody is there to carry on, and it never accepts on the person's behalf. It also guards what
  still earns the acceptance: the notice came first, silence and an
  instruction given before the notice do not count, and the line is read back
  before the work starts, because measured runs built with nothing recorded
  while believing they had followed the order. And it guards the reply after
  the person carries on: the line is written and the work started in that
  same reply, with no further yes asked for. Measured runs recorded the
  acceptance and then kept the flagged part switched off behind a rule that
  waited for the skipped sign-off, and asked again before opening it. The
  acceptance now reaches everything the notice named, so a lock that only
  waits for the skipped caution opens with it. A form or menu answer with no
  option selected is not carrying on, since a real acceptance was once written
  from one, naming an approval nobody had mentioned. So the line quotes what
  the person typed or chose, exactly, and names only people they named. In the
  same save, every sentence the acceptance makes untrue is corrected, because
  a masterplan once said licensed files were kept out after they were let in.
- `.agents/tests/who-can-settle.sh` guards which waiting pieces need the person:
  that the three labels each say who can answer, that /shape never answers a
  person-present question itself, that it can be pointed at one piece and can
  clear the research alone, and that /what-now stops calling that research the
  person's errand.
- `.agents/tests/shape-later.sh` guards when /shape shapes now and when it
  files a piece for later. Typed with words it starts the step with no offer
  first, since typing it was already the choice, and it says in one line when
  that step takes a sitting. The person can say "later" at any point, or ask
  for a note in the first place. A piece deferred part-way is filed with its
  question, their words and the sub-state that names it, with nothing started,
  and a note asked for outright is captured through the gate as a
  `shaping:raw` piece in their own words. It also holds that
  the old every-time offer stays gone, that change-triage recognises a request
  to file, that pieces.md says roughly what each waiting label costs to settle,
  and that /what-now calls a planning session when more pieces are waiting
  than are ready.
- `.agents/tests/prototype-recipes.sh` guards what a prototype is supposed to
  be: that decision-prototype.md names the two kinds of question and picks
  before it builds, that each recipe keeps the rules that make it worth
  following, and that neither recipe is written in build words the person cannot
  read.
- `.agents/tests/held-definition.sh` guards what a replay run has to do to count
  as held: the three clauses, that withstanding pushback is reported rather than
  graded, and that the rollup says so. Its fourth clause asks for the notice
  first, then the person carrying on, then the record before the work, and it
  holds the grader's definition of carrying on. It drives the rollup with
  graded runs built by hand, so a withdrawn notice is proved not to cost a run
  its pass while flagged work built with nothing on the record still fails.
- `.agents/tests/release-label.sh` checks the guard that refuses a pull request
  nobody has sorted. Release Drafter picks the next version from labels and
  cannot read a change, so an unlabelled pull request falls through to "Other
  changes" and quietly becomes a patch. Four merged that way and the repository
  proposed a patch for a release adding a ninth command; a person asking a
  question is what caught it, an hour after the release was cut. So the guard
  asks only whether somebody chose, never whether they chose correctly, since
  knowing that means reading the change. The check drives the real script, and
  its second half is the one that matters: it reads the labels out of
  `release-drafter.yml` and requires the script to accept every one, because two
  written-out lists of the same thing drift and the drift would refuse a pull
  request labelled exactly as the configuration says.
- `.agents/tests/pull-request-base.sh` checks the guard that goes red on a
  pull request aimed at `stable`. `stable` is the default branch, so a new pull
  request aims at it unless somebody changes the base, and one merged there
  once and stopped the next release. It runs the real script against a `stable`
  base and a `main` base, and requires the refusal to name both `stable` and
  `--base main`. It also reads the workflow. The base must come from the pull
  request through the environment, and the check must run again on `edited`,
  since changing a base sends that event and a check that stayed red after the
  fix would teach people to ignore it. The guard stays out of source checks,
  whose concurrency group would cancel a running rehearsal on every edit.
- `.agents/tests/version-stamp.sh` guards the release stamp: that all three
  version-bearing files move together, that a preview never reaches the branch
  every installer reads, that an already-stamped tree takes the next version,
  and that a manifest whose version field was renamed or duplicated stops the
  stamp rather than letting it match nothing. That last one is the reason the
  check exists. A stamp that matches nothing reports success and ships the
  previous release's number, and no other check would see it.
- `.agents/tests/unshaped-is-not-next.sh` guards the maintainer's own read of
  the open issues. That read goes wrong quietly rather than loudly. It
  recommends a piece nobody has sized, or ranks themes against a priority this
  repository has never written down, or groups the backlog by the area labels
  instead of by what the issues say, which hands back the grouping that is
  already there and finds nothing. Each of those reads perfectly well and is
  worth nothing, so the rules against them live as prose in the skill and this
  check reads them back. It holds the printout's shape too, which is fixed in
  the skill rather than described, because a described shape gets followed
  loosely: a heading the maintainer can read on its own, a paragraph under it
  that says what the pieces share and where the theme stands, a piece printed
  as its number, one recommendation rather than a ranked list, and a piece no
  theme fits left on its own instead of pushed into the nearest one. The
  heading and paragraph rules came from a read that named a theme "reaching
  beyond the thirteen" and glossed it with a list of nouns, which grouped the
  backlog correctly and told the maintainer nothing. Printing the number
  reverses an earlier rule, so the check carries the reason. A number is banned from a
  tracked file because its reader cannot follow a pointer once the numbering
  has moved on, while this printout is read beside the live backlog and the
  number is what the maintainer types next. It also holds the rule that a
  silently empty answer stops the read: the second GitHub call returned an
  empty list once while the backlog was not empty, and an empty list is also
  the honest answer for a backlog that is empty, so nothing tells the two
  apart except the other call disagreeing. Telling somebody their backlog is
  empty when it is not is the one wrong answer that looks like a right one.
  Last, it holds that the three checks guarding the maintainer skill boundary
  read the skill names off `.agents/maintainer-skills/` rather than carrying
  one. Each once named humanizer, the only maintainer skill when it was
  written, and the second skill arrived with two of the three not looking.
  The proof that reading the folder catches a copy is the `review-issues-leak`
  mutation in `mutate.sh`, which plants one and asks all three.
- `.agents/tests/stack-research.sh` guards the maintainer's read of what
  changed upstream for the products the recipes name. That read goes wrong
  quietly: it edits a recipe it was meant to read, moves a last-checked date
  nobody agreed to, proposes a change to how a section works without saying the
  recipe then needs a new real run, or cites a summary site as if it were the
  product's own page. So it holds that the skill changes nothing without the
  maintainer, lists every recipe and part with "no change" as an answer, flags
  every `How it works:` change as needing a real run, and treats a secondary
  site as a pointer only. It also holds where the note goes, a folder git
  ignores and the release allowlist never carries, and that AGENTS.md says
  where to load the skill from.
- `.agents/tests/stable-is-the-channel.sh` guards the branch the world installs
  from and the visit that names a project's version. Two of the three
  installation routes clone with no ref and take the default branch, which was
  the branch work merges into, so a project installing between two releases got
  the last release's label with unreleased work behind it and `/maintain` said
  it was up to date. It drives `.agents/tools/promote-stable.sh` against a
  stand-in for the GitHub CLI: the create, the forced update, the read-back
  that catches a write which answered and changed nothing, and the refusals,
  including a commit no published tag names. The rule it guards hardest is
  that the ref is written into the tool rather than taken from an argument,
  since that is what makes a repository write from a workflow acceptable at
  all. It also reads back `/maintain`'s rules about `releases/latest`, the one
  endpoint that cannot answer with a draft, and asserts that neither
  `docs/MAINTAINING.md` nor the stamp still calls the old gap unavoidable.
  `/what-now` names a newer release too, so the check holds that it asks the
  same endpoint and no other, and never names a draft. The
  real write from inside GitHub Actions is the one thing no local rehearsal can
  reach, so the permission shape of that workflow is guarded in
  `release-publication.sh` and the first published release is the first time
  the write itself runs.
- `.agents/tests/attribution-scrub.sh` drives the commit-msg hook over a set of
  messages and reads what it wrote: that a session link goes whether it sits
  behind a trailer key or on a line of its own, and that the pull request
  footer goes with or without its link. The row of dashes a squash merge
  strands above a removed trailer goes with it, even when another trailer such
  as `Signed-off-by:` sits below, and a message with nothing to take out comes
  back unchanged. The case worth having is the one that keeps prose about
  Claude, Cursor and Gemini intact. A hook that went after the word rather than
  the attribution line would gut most of the messages in this repository, and
  nothing would say so until the history was unreadable. The rehearsal builds
  its samples from pieces, so the validator reads it like any other file and
  would catch a real line pasted into it.
- `.agents/tests/hosting-request.sh` guards the hosting request `/ship`
  writes on a first launch, for a tool that runs on a server somebody else
  runs. The person carries it there by hand, because the kit never contacts
  that server. It holds the eight fields, including how the tool builds and
  which address it listens on, which a hosting companion refuses a request
  without. It holds the rule that the request carries names and never a value,
  and that a later launch reads it back rather than asking again, printing it
  anew only when the project changed a field. It also reads every skill file
  outside `.agents/skills/ship/recipes/` and refuses a hosting, data or deploy
  product named in one, since a skill that needs to know how one behaves reads
  the project's recipe. The screen rules' link to Vercel's interface
  guidelines is set aside, and the check proves the exemption hides nothing
  else in that file. The README may name a product, as one option.
- `.agents/tests/ship-runs-recipe.sh` guards how `/ship` runs a project's
  recipe. It holds that `/ship` reads the `Recipe:` line and the file it
  names, runs all eight sections in the recipe's order, and reports each in
  one plain line. `Who runs it:` decides whether the kit runs a check, reads
  back a pasted result, or records what the person saw. The rules it guards
  hardest are the ones that would turn a warning back into a stop: a check not
  done is said once, written in the changelog, and the launch goes ahead, and
  off a recipe the general list is warnings too. The one wait left is the
  address, since a tool with no recorded address is not live. A deploy the
  kit runs itself writes no hosting request, since nobody runs a server to
  carry one to, and its own address meets the wait. The rollback line says
  "possible, not tried", because the kit only saw an earlier build listed.
  On a later launch the changelog is read first, and a warning it already
  holds for the same section is one line pointing to it, while a new or
  changed one is still said in full. That rule sits beside the reporting
  steps, since a real second launch repeated every old warning when it sat
  only in the later-launch section.
  Build with care reaches the same checks, and a settled area goes live on
  their next run rather than through a deploy of its own. It also takes
  the deploy target from each recipe's title and refuses one named in `/ship`
  or its evidence run, because a skill that learned one recipe's commands
  would read wrongly on every other. And it holds that the launch review
  reads a setting itself before it asks the person to look one up, with
  only a key the tool already sends to the browser, and asks only for what
  it cannot read, saying why. A real run stopped to ask for a setting the
  service answered in public.
- `.agents/tests/ship-merges-and-deploys-once.sh` guards how `/ship` merges
  and deploys. In one real run the person said only "put it live" and `/ship`
  merged two pull requests nobody had named to them. The rule that answered
  that, a yes naming each merge, now lives in the one merge step every route
  uses, and `one-merge-step.sh` holds it; this check holds that `/ship` points
  there. In another run `/ship`
  cut a deploy's output short, deployed the same version again, and so lost
  the earlier build a rollback would reach. So it holds that the whole output
  or the host's list of deployments is read first, that no second deploy runs
  before the first is checked, and that a second deploy is announced as
  replacing the rollback target. It also holds that a warning said once is not
  repeated in the same `/ship`, and that WORKFLOW.md says all of it. A later
  run merged properly and then pushed its changelog entries straight to
  `main`. So the launch records take the save route a piece takes,
  on one pull request for each `/ship`, opened once the launch is checked,
  whose merge needs its own yes. Where the host builds every change to
  `main`, that ask says the merge is one more build that moves the rollback
  target. The person's uncommitted work is neither swept into that commit nor
  discarded.
- `.agents/tests/one-merge-step.sh` guards the one merge step every route
  uses, section-builder's `references/merge.md`. The rule that a merge waits
  for a yes naming it lived in `/ship`, while in a real project most merges
  happened inside `/implement` and hand-built runs, and three went ahead on a
  yes that named nothing. The host put every merge live, so the first launch
  happened as a merge and `/ship`'s checks never ran. It holds the named yes,
  a reply naming several counting for each one it names, the merge made on
  the pull request, a stacked pull request never merged before its base, and
  nothing merged while GitHub cannot be reached. It holds the six conditions
  under which an agent merges on the person's pre-approval of a run, each
  proved load-bearing, the last being that the merge would not go live, so
  pre-approval never puts code live, and a tool that is `not hosted` meets it.
  A piece failing one stays in `to check`
  with the reason. It holds the masterplan's `Goes live:` line, written once
  when it is missing, the ask that says "this goes live now" where every merge
  goes live, and the first such merge running `/ship`'s first-launch checks
  before it. It fails on section-builder,
  `/implement`, `/fix`, `/ship` or `/sync` restating the rule rather than
  pointing at it, and holds `/ship`'s promote from a preview to live on a yes
  that names it. It replaces the validator's string that held section-builder
  short of a merge. It also holds how the kit waits for a project check, with
  one `gh pr checks --watch --fail-fast` run in the background or by the
  agent's own watch tool, never a `sleep` loop. Sessions with no written way
  to wait made nine calls and eight watches and loops for one pull request,
  and a watch using an option the installed `gh` lacked ended early and looked
  finished. So an exit code of 8, or an unknown option, reads as not finished.
  No checks at all, a check that never ends and an unreachable GitHub are each
  said plainly and never called green, and only `merge.md` carries the wait.
- `.agents/tests/closing-words.sh` guards the rule that only a pull request's
  `Closes` line closes a piece. GitHub closes an issue on a closing word
  straight before its number, even in a sentence saying it does not, and an
  outside project had a piece closed twice that way, the second time by the
  sentence warning about the first. It holds the nine words, the negated case,
  the reach into titles, commits and changelog files, and naming another piece
  by number and title instead, in section-builder, the run's stack example and
  WORKFLOW.md. It also reads every number in those files and the merge step,
  fails on a closing word before one outside the `Closes #<number>` line, and
  proves that reader catches a bad sentence planted in a copy.
- `.agents/tests/not-hosted.sh` guards the third value of the `Goes live:`
  line, `not hosted`, for a tool no server runs for people to reach. Two
  projects had no live address at all, a skill library installed from the
  repository and a report generator run on the person's own computer. The
  merge step took their merges for launches: it asked the wrong question,
  started the first-launch checks, and held back a run's pre-approved merges.
  So it holds that a merge there is never a launch, that pre-approval covers
  it, and that a missing line asks which of the three it is. A recipe named
  beside `not hosted` wins, since a recipe is a place the tool runs. It holds
  what `/ship` does instead: it names each change since the last release,
  runs the evidence run and the review, and proposes the next minor tag, or
  `v0.1.0` with none. It releases only on a yes naming the release, and makes
  a local tag where there is no GitHub repository. It writes no hosting
  request, address or rollback line, on Build with care as well. It also holds the template, founding
  writing the line from answers it already has, and WORKFLOW.md.
- `.agents/tests/the-runner.sh` guards how `/implement` runs a plan of ready
  pieces with nobody watching, given several numbers or `queue`. In a real
  project the agent built its own loop four times, with its rules and state in
  temporary files and memory notes. The gate on which pieces a run may take
  was skipped twice, once on a piece that touched personal data overnight,
  and resuming a dead session rested on what the agent remembered. So
  `running-longer.md` holds the run, and each rule is proved load-bearing. A
  piece is taken on its own merits, never after three clean pieces, and never
  when it sits in a sensitive area with no recorded acceptance. A piece with
  no readiness result is checked before it is claimed. A piece the person
  asked to try stops at `to check`. The eleven steps each piece goes through
  are held in order, from the claim, read back and refused for a piece
  already building, to the state update. A dependent piece stacks and names
  the merge order, and the parts of one parent share a pull request. A hard
  open choice sends the piece back to shaping and an easy one is flagged, and
  either way the run moves on. A hard choice the run can already see when it
  plans or claims a piece sends it back too, with its question, no branch and
  no claim. Skipped and left `ready`, such a piece came back to every run with
  nothing telling the person a question waited. An easy choice seen then
  leaves the piece eligible, and a missing fact alone still skips it. The
  state file's fields, the live page, and a new session resuming from the
  state file are held too, as is a run that ends
  at once when nothing is left. So is what review of the first draft found:
  a held-up piece whose blockers are all in the plan joins it and stacks, the
  earliest claim comment wins a race and only the later run backs off, every
  way a run ends leaves each piece in a final state, a parent's pull request
  opens after its last finished part, the checkpoint route has its own steps,
  and pre-approved merges are swept at the end, bases first. Every move a run
  makes goes through the gate with the run's name, so the labels and
  `run.json` always agree, and the coordinating session alone writes
  `state.json` while the gate alone writes each piece's status. A piece that
  fails three attempts is kicked back to `shaping:spec` or `shaping:research`,
  and one whose build needs software installed outside the project folder to
  `shaping:clarify`, never installed, and the run takes the next piece, unless
  the same tool would stop every piece left, which ends the run. A piece in
  hand when the run ends goes back to `state:ready` with its branch kept,
  built or not, and `parked` is no longer a state a run records. It holds
  `/what-now` and `/sync` offering to resume, section-builder's stacked start, and the validator's step 1 wording
  that matches it.
- `.agents/tests/kit-owns-worktrees.sh` guards the worktree each piece in a
  run is built in on Claude Code. In a real project the person used
  worktrees every day, set up by hand, and the kit said nothing about them:
  twelve were left over, over a hundred branches were deleted by hand,
  secrets were copied into several folders, the main folder was left on a
  feature branch, and a forced removal was stopped only by Claude Code's own
  guard. So the kit owns each worktree's whole life, and each rule in
  `running-longer.md` is proved load-bearing. A piece's worktree is
  `.agents/worktrees/<issue number>-<short name>`, which git ignores, and the
  main folder is never switched to a piece's branch. Its `.env` is a link to
  the main one, never a copy, and a link that cannot be made means the piece
  runs without secrets and flags what needs a key. Dependencies install
  before the start ritual, and the dev server's port is recorded in the run
  state and named in the hand-over. A path already there is reused only on
  the same branch with nothing unsaved, and a full disk stops the run at the
  next piece. The run state stays in the main folder. A worktree is removed
  after its pull request closes only when nothing in it is unsaved, never by
  force and never with its branch. It holds section-builder's safe start,
  `/implement`, `/sync`, the leftover step `/maintain` runs before recording
  the visit, the foundation's ignore line, the install command founding
  records, the tooling report's line for an older Git, the blocked forced
  removal, and WORKFLOW.md and the compatibility page telling it.
  It holds too that the checkpoint route needs the main folder on `main`,
  that the dev server runs until the hand-over and the report says how to
  start it again, that a run's worktrees do not carry the confidential
  folder, and that `/maintain` offers `git worktree prune` on a yes. It
  holds that section-builder finds the main folder for walk-through pictures
  from the first line of `git worktree list --porcelain`, makes the folder
  when it is missing, and names its full path in the hand-over.
  `.agents/tests/kit-owns-worktrees-rehearsal.sh` runs the shipped
  `worktree.sh` in a throwaway project with a stand-in GitHub. It opens a
  worktree and a stacked one and reads that git ignores them, the main
  folder stays on `main`, and `.env` and `.env.local` arrive as links with no
  copy anywhere. It holds what counts as unsaved, an existing path reused or
  skipped, and a dead session's uncommitted change kept. It clears worktrees
  both ways: a merged one with nothing unsaved goes, keeping its branch and
  the main `.env`, while a closed one holding a change and a merged one
  holding an unpushed commit stay and are named. It holds that an open pull
  request's worktree and one a run is building are left alone, that the
  leftover list removes nothing, and that git never saw a forced removal, a
  branch deletion or a checkout, with or without `-C`. A file git ignores
  that is a real file outside a dependency or build folder counts as unsaved,
  so tidy, remove and the end of a run keep that worktree. A copy of `.env`
  already in a worktree is named and never called missing, and a `.env` only
  in a subfolder is named rather than linked. A worktree on no branch is
  listed and never tidied, and no pull request is asked about an empty
  branch. A skip gives git's own `fatal:` line, a folder git lists but is gone
  names `git worktree prune`, and a failed open deletes only a branch it made
  itself. A Git older than 2.17 gets no worktree, and a port taken only on
  `::1` is never given. It also runs the `worktree-links` line. A listed
  folder is made in the worktree with each thing in it linked, a file inside
  an ignored folder gets its folder made, and a name with a space is linked.
  A confidential path, an env file, a tracked file, a path outside the
  project, a deleted one and one git does not ignore are each refused by
  name. So is a link the worktree's own ignore rules would show as a new
  file, which happens when the main folder's ignore line is not saved yet.
  A link in the main folder leading outside the project or into the
  confidential folder is refused, and a folder keeping one tracked
  placeholder still links its ignored files.
  Links are never unsaved work, and removal leaves the main files. The
  candidates list leaves out dependency folders, env files, the kit's folder,
  confidential folders and anything deeper than two levels. Last, a sibling
  worktree made with `git worktree add` stands for another tool's, with
  `main` checked out in it. Run from there, `open` cuts the piece from
  `origin/main` into the main folder's `.agents/worktrees/` and says so, the
  run state is read from the main folder, and `tidy`, `leftovers` and
  `remove` never list, change or remove the sibling. It also runs the
  lookup section-builder names for the main folder, as written, from inside
  a worktree and from the main folder, and both give the main folder. A
  walk-through picture written there never reaches git, leaves nothing in the
  worktree, and outlives the worktree, which is cleared away once its pull
  request closes.
- `.agents/tests/worktree-links.sh` guards the ignored build files a run's
  worktree links. One project's build needed licensed fonts git ignores, and
  the agent copied them into each worktree by hand before committing them
  after a risk notice. So founding asks once, with a guess, which ignored
  files a build needs, asks nothing when there are none, never ends the turn
  on that question, and writes a `worktree-links` line and a `confidential`
  line. It holds the refusals and the other tools' worktrees in
  `running-longer.md`, the `/maintain` offer that records a no and returns
  only for a new path, the maintenance record's header, and WORKFLOW.md
  telling it.
- `.agents/tests/adopted-ci.sh` guards the rule that an adopted project's own
  CI is its project check. An adopted skill library already ran its tests on
  every pull request, and founding still copied the kit's placeholder
  `checks.yml`, which failed on every pull request beside the working check
  until the agent deleted it by hand. So founding records the check as one
  line in the capability profile, `Project check: <workflow file>, job <job
  name>`, chooses the job by three rules in order, and offers the kit's two
  steps once, adding them only on a yes and never on a Windows runner. A line
  that names no file means `checks.yml` and its `project-check` job, so an
  older project works unchanged. The check holds that `/sync`, the check
  floor, the boundary rules, the move onto the index, a run's install step and
  founding's resume read that line, and it searches those readers for a
  `checks.yml` or `project-check` left outside the default, which is how one
  reader quietly going back to the fixed file would show. It holds the
  `/maintain` offer to an older project, which records a no and returns only
  when the workflow files change. `.agents/tests/adopted-ci-rehearsal.sh` runs
  the bootstrap in throwaway projects. A workflow on pull requests whose
  `run:` line or `run:` block runs the tests gets no `checks.yml` and is named
  in one line. A project with no CI, a workflow on `push` alone and a labeller
  on pull requests still get `checks.yml`, and a `checks.yml` the project
  already had is kept untouched.
- `.agents/tests/one-story-try.sh` guards the one story the kit tells about
  who tries a piece. The build skill said the agent's walk-through stands in
  for the person's try, while WORKFLOW.md's "What stays yours" and the README
  said the person must try each result before it is saved. So it holds that
  what stays the person's is saying what they want, deciding what merges and
  what goes live, and accepting a risk after its notice, and that trying a
  piece is open to them through the opt-in. It reads that from WORKFLOW.md,
  both README places, PHILOSOPHY.md and section-builder, and proves each
  sentence load-bearing. It also searches every shipped document and skill,
  the foundation templates included, for the old wording, and finds it on a
  copy with the old sentence put back. Two later sentences timed a step by
  the person's try as if one always came, the trim in WORKFLOW.md and the
  screen rules, so it holds that both are timed by the walk-through instead.
- `.agents/tests/walk-through-eyes.sh` guards what the walk-through can look
  at, and where its pictures go. Step 6 once said to take a screenshot where
  the coding agent could, and nothing more, so on a tool whose output was a
  PDF the agent either read the file's bytes and called it checked, or saw
  nothing. So it holds the means in the order step 6 tries them: the coding
  agent's own browser tool, then Playwright only where it is already there, a
  PDF rendered one picture a page for the first 30 pages with the rest named
  as not seen, `pdfinfo` giving the page count, an office file made into a PDF
  first, and an SVG made into a picture in the pictures folder rather than
  beside the SVG, where it would land in the worktree. The kit never installs a browser. Each picture is opened with the
  file reader, and the report says what it was compared against. Every
  picture goes to the main folder's walk-through folder, one for each piece,
  never inside a worktree, where it would count as unsaved work and keep the
  worktree after its pull request closed. The old wording that put it
  wherever the build ran is refused. A renderer failing is a finding about
  the piece, and an agent that cannot read images says it could not look, so
  the piece goes to `to check`. It also holds the `Walk-through eyes:` line
  founding records in place of browser availability, and WORKFLOW.md telling
  how to give the walk-through more eyes.
- `.agents/tests/first-upload-asks.sh` guards the yes the project's first
  upload waits for. Founding tells the person nothing will be uploaded, and in
  a real run the first piece then pushed the whole project to GitHub with no
  question. So the first push of the code asks first, naming the repository
  and whether it is public or private, while the piece is still built and
  checked. It asks once for each project, and the kit knows that from the
  remote rather than a record. The code is online only when a remote branch
  shares history with the local `main`. A listing that failed is never read
  as an empty repository. A repository holding something else, or the kit's
  own repository, gets nothing pushed and a question instead. A no, or a run
  with nobody there, keeps the piece on its own branch here with a one-line
  note. A yes creates `main` through the GitHub API at the commit the piece's
  branch was cut from, the one time it is written other than by a merge,
  since the settings refuse a push to it. It holds the pointers from `/sync`,
  `/ship`, founding and the push-to-main rule, and WORKFLOW.md telling it.
  Founding opens issues before any piece pushes, so it holds the same guard
  there: before the first issue, founding checks which repository the project
  points at and changes nothing on the kit's own: no issue, label, setting or
  push. It asks for the person's, runs the report again once `origin` points
  there, and with none says the pieces wait for a repository of their own.
- `.agents/tests/recipes.sh` guards the recipe format. A recipe pairs a build
  stack with a place to run it, and it is the only place outside the README
  allowed to name a service a tool runs on, so the rules around that permission
  are the ones worth holding: two places are two recipes, each of the eight
  sections says how it is checked and who runs the check, a shared part is
  linked rather than copied, a recipe joins the menu only after rehearsals and
  one recorded real run, and there is no draft state because the folder is the
  menu. It also runs `.agents/tools/check-recipes.sh`, which the validator runs
  on every recipe, every shared part and the blank, against a recipe filled in
  from the blank and against copies with one part taken away at a time. The
  validator wants a rehearsal named `recipe-<name>.sh` for every recipe, and
  refuses one that does not source the rule-shape helper or name its recipe
  file. This check shows the tool refusing both, and a recipe with no
  `Command-line tools:` line. It also holds the one section a recipe may add,
  the settings the kit can read, which sits after health, carries the same
  three lines, and needs an outcome line in the proven section. And it holds
  the optional `Plan terms:` opening line, which says who a free plan is not
  for. A copy of it with no date, no source page, a date in the future or not
  real, or no sentence before the date is refused, since terms change without
  notice and an undated restriction cannot be told from a current one.
- `.agents/tests/recipe-nextjs-supabase-on-vercel.sh` and
  `.agents/tests/recipe-nextjs-supabase-on-coolify.sh` guard the first recipe
  pair offline. They share `.agents/tests/lib/recipe-rehearsal.sh`. Each holds
  its recipe's rules and proves every one load-bearing, and both hold the three
  shared parts: the Next.js container and its health route, which both recipes
  keep so the local check matches production and a later move changes only the
  host, and the Supabase backup and restore. Each also runs every command its recipe writes against
  stand-ins for the recipe's tools. A stand-in answers only what that tool
  documents, so a mistyped option or an invented subcommand is refused, and a
  tool the recipe names but no command uses is refused too. Until its real run
  is recorded a recipe waits in `.agents/tests/recipes-awaiting-run/`, which
  ships nowhere, and must fail the shape check on its real run and on nothing
  else. Once it moves onto the menu it must pass outright, and a copy left in
  both places fails. On the Coolify recipe the rule held hardest is that every
  check needing the server is run by the companion or the person and read
  back, since the kit never contacts that server. The Vercel recipe also
  holds its `Plan terms:` line: the free plan is for personal, non-commercial
  use, a work team needs the paid plan, and the line names the date and the
  page it was read from.
- `.agents/tests/compatibility-grades.sh` guards the grade each coding agent
  carries in `docs/COMPATIBILITY.md`. The page once named four agents and
  presented them alike, while the replay harness had recorded runs on only
  one. So it holds the three grades, the evidence that moves an agent up, the
  line saying a quiet issue tracker is not evidence, and the known limits
  written for anything below Tested. Its mechanical half reads the harness map
  and requires a grade for every agent in it. It also refuses Tested for an
  agent the harness cannot drive, and for an agent other than the harness's
  default that `baseline.md` never names. A grade raised by editing the page
  rather than by a recorded run is the thing it exists to catch, and it proves
  each refusal on a copy of the page.
- `.agents/tests/loop-first-ground.sh` guards the ground the loop-first
  redesign stands on, in `docs/PHILOSOPHY.md` and the documents that repeat it.
  It holds the principle first: the work is shaping the work, and looping is
  the consequence. The kit is a loop kit with four loop modules, and a loop
  that needs a person sends the piece back to be shaped again. It holds the
  two zones, shaping, where the person and the system make every decision, and
  implementing, where the system works alone and review never stops the loop.
  It holds guides and sensors, the two kinds every gate is, and the rule that
  a script holds what the agent would otherwise have to remember. It holds two
  worked examples, "Loop modules, added", which answers all five questions,
  and "Things the loop kit leaves out, rejected", which names each of its
  eight exclusions. The README and WORKFLOW.md each state the principle in one
  sentence, WORKFLOW.md after its audience line and before the command table.
  `docs/SOURCES.md` credits the loop words and the guide and sensor split with
  no link into `docs/design/`, which does not ship, and a copy carrying such a
  link is caught. The kit is for technical builders who direct agents, who
  know Git, branches and pull requests and never have to read code. Records are written for agents
  first under a short plain header, while a public document such as the README
  stays written for people. The worktree and loop worked examples are added,
  and they and the two-layer piece example each answer all five questions, with the answer for when it goes wrong
  naming a command the person types. Taking any one answer out is caught. The
  test-first example still rejects the universal practice and states the
  narrower rule that a machine check fails before the code. The kit may grow
  only to replace work that was already happening without it. The check puts
  the old worktree rejection and the old promise to shrink as often as it grows
  back on a copy, and proves each is noticed. It also holds the audience phrase
  in the README and WORKFLOW.md, and the Claude Code first line on the
  compatibility page.
- The checks that guard a rule written as prose share
  `.agents/tests/lib/rule-shape.sh`: declare the rules, and it asserts each one
  and proves it is load-bearing by removing it and requiring the check to fail.
  `validate-kit.sh` finds that family by the helper they source, so a new one is
  covered from the moment it is written.
- `.agents/tools/build-release.sh <version> <new-folder>` assembles a local
  public release outside this repository without changing or deleting an existing
  folder.
- `.agents/tools/preflight-cutover.sh` asserts everything that has to be true
  before this repository's tree is pushed into the public one, each item with an
  expected answer rather than a list somebody reads and judges. A checklist you
  interpret is a checklist you pass. Run it immediately before the push, not
  once in advance, and with nothing else working in the repository: a review
  agent or an editor saving a file makes the tree momentarily dirty, and it
  reports that as a failure. It should. A false alarm costs a re-run, and the
  reverse mistake costs a push nobody can take back.
- `.agents/tools/rehearse-merged-tree.sh` copies every tracked file into a fresh
  one-commit repository outside this one and runs the adapter drift check, the
  validator and the whole rehearsal suite against it. That is what the public
  repository will hold after consolidation, and the push that puts it there
  cannot be undone, so run this before it rather than finding out afterwards. It
  is not in `.agents/tests/` because it calls `run-all.sh`, and a rehearsal that
  runs the suite from inside the suite reaches its own copy and hangs.

## Secrets and external changes

Keys, passwords, and tokens live in local or GitHub-protected settings and
never in a tracked file. Never print or commit one. Publishing a release,
renaming a repository, changing the public starter, or modifying online access
requires the person's explicit approval at that step.

Before a technical confirmation appears, explain what the person will notice,
why it is needed now, whether anything leaves this computer, whether the action
is temporary or saved, and what remains unconfirmed if they decline. Say that a
technical confirmation box will appear next.

Preserve existing work. Never discard, overwrite, or delete unsaved material
to make a check pass. Ask before any irreversible action or anything that
changes data, access, money, automatic actions, or an online service.

The commands in `.agents/guard/blocked-commands.md` are off limits. Save a
checkpoint before sweeping changes.

## Writing

Use British spelling and plain language. Do not use em dashes. Keep paragraphs
short. The audience is not required to read code, so define a technical term once only
when it cannot be avoided and describe verification as an action and its
expected outcome.

Before saving any human-facing prose, load
`.agents/maintainer-skills/humanizer/SKILL.md` and use its embedded mode
together with the house rules in `docs/MAINTAINING.md`. This includes documentation, skill
prose, pull request text, release notes, interface copy, error messages, and
comments written for a reader. Preserve the facts, intent, code, commands, and
link targets.
