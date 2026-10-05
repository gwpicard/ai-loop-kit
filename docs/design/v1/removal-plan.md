# Removing AI Build Kit from ai-loop-kit

Written 5 October 2026. Read-only survey of `gwpicard/ai-loop-kit` at `main`
`fbdf054`, its GitHub side, and `gwpicard/ai-build-kit` for comparison.
Nothing was changed except this file.

## 0. What the survey found

These facts shape the plan. Some differ from what the brief assumed.

- **Install routes do not point here.** `.claude-plugin/plugin.json`,
  `marketplace.json`, `agent-plugin/plugin.json` and the README all name
  `gwpicard/ai-build-kit`. This repository is private. Nobody installs Build
  Kit from it, so removing Build Kit here cannot break an install route.
- **Only three branches are live on origin:** `main`, `v1-integration`
  (`c767408`, slice 7 part a) and `slice-06b-evidence-deny` (superseded; its
  content reached `main` in `ca4f697`). The other 17 `origin/*` refs in this
  clone are stale tracking refs. GitHub already deleted those branches on merge.
- **Local branches.** 21 in all. Two hold work found nowhere else:
  `slice-07b-fix-loop` (`21d9a87`, slice 7 part b, local only, checked out in
  `.agents/worktrees/slice-07b`) and `slice-07a-build-fix-loops` (`1a29f87`,
  an earlier form of what `v1-integration` carries). `slice-06c-*`,
  `slice-06c2-*` and `slice-06f1-*` are local only, but their content reached
  `main` as rebased commits through the merged `slice-06-to-main`. The rest are
  squash-merged.
- **Tags:** none, locally or on origin. **Releases:** one draft, "AI Build Kit
  v0.0.1", made by the release drafter on 4 October.
- **History:** `main` has 20 commits. The root commit is a snapshot of
  ai-build-kit with no shared history. After it come one Build Kit repair and
  the v1 slices 1 to 6.
- **What exists only here (not on any ai-build-kit branch):**
  1. The v1 slices 1 to 6 as merged on `main` (gate, ready-lint, area map,
     bar guard, evidence record, state guard, contract v2, and the rehearsals).
     `gate.py` here differs from every ai-build-kit branch.
  2. Slice 7 part a (`v1-integration`) and part b (`slice-07b-fix-loop`).
  3. The open backlog issues carried over from AI Build Kit, and the lessons issue from the first unattended night. A title search of ai-build-kit found
     no twin, so they appear to have moved here.
  4. **The whole v1 design input set in `.agents/tmp/v1-factory/`**, which git
     ignores: `redesign-answers.md`, `inventory.md`, `decisions.md`,
     `research/*.md`, the issue drafts, and the factory's tooling and logs
     (12 MB). It is in no repository at all. This is the largest loss risk.
  5. The v1 design document lives only as a claude.ai artifact.
- **What ai-build-kit already holds:** every Build Kit skill, test and tool in
  their 0.19 form on its `main`. `docs/MIGRATION.md`,
  `docs/MIGRATION-READINESS.md`, `.agents/migration/port.py`,
  `review-issues` and `docs/design/evaluation-system.md` are byte-identical
  there. `docs/design/loop-first-*.md` and `agentic-loop-research.md` are
  identical on its `design/agentic-loop` and `handoff/ai-loop-kit-v1`
  branches only, not on its `main`.
- **Checks on pull requests today:** `release label` (refuses a pull request
  with no release label) and `pull request base` (refuses base `stable`, which
  does not exist here) are active. `source checks` and `maintainer branch
  check` are switched off, so the validator runs nowhere on GitHub.
  `update release draft` runs on every push to `main` and keeps rewriting the
  Build Kit draft release.
- **No server-side protection is possible today.** Branch protection and
  rulesets both answer "upgrade to GitHub Pro or make this repository
  public". Nothing on GitHub stops a push to `main`. Only the local Claude
  Code deny rules do.
- **`.agents/worktrees/` and `.agents/runs/` are ignored only through
  `.git/info/exclude`**, which a fresh clone does not carry.
- **The maintainer's local settings** (`.claude/settings.local.json`) carry
  deny rules worth keeping and two allow rules from the paused build: running
  `.agents/tmp/v1-factory/local-checks.sh`, and `gh pr merge * --merge`. The
  second lets an agent merge without a prompt. They also deny `gh api -X
  DELETE`, `gh release delete` and `gh repo edit`, so the GitHub clean-up steps
  below are the person's to run.
- **The factory watchdog is not running.** No launchd job, cron entry or
  process was found.
- **`.claude/commands/` and `.claude/skills/` here are loaded into the
  maintainer's own Claude Code sessions in this folder.** Removing them removes
  `/shape`, `/implement` and the rest from those sessions.

## 1. Inventory

Key for the decision column:

- **Keep**: stays as it is for v1.
- **Borrow**: copied into v1's place in stage C, then adapted there.
- **Archive**: preserved by a tag, in ai-build-kit, or in a named folder, then
  removed from `main`.
- **Delete**: removed. Still reachable through the archive tag.
- **Decide**: a question for the maintainer (section 4).

"The archive tag" means `archive/build-kit-final` on `fbdf054` (stage A).

### 1.1 Root files

| Item | What it is | Decision |
|---|---|---|
| `README.md` | Build Kit's public front page, names ai-build-kit install routes | Delete; replaced by a transition README (stage B2), then v1's (stage F) |
| `AGENTS.md` (2,266 lines) | Maintainer instructions, mostly a list of Build Kit rehearsals | Replace. Carry over: house rules on numbers, attribution, pull requests, secrets, writing, "trust the check" |
| `CLAUDE.md` | One line importing AGENTS.md | Keep |
| `GEMINI.md`, `.github/copilot-instructions.md` | Pointers for other agents | Delete (v1 is Claude Code only) |
| `WORKFLOW.md` | Build Kit's user guide | Archive (tag; on ai-build-kit `main`) |
| `llms.txt` | Build Kit summary for crawlers | Delete; v1 writes its own later if wanted |
| `CONTRIBUTING.md`, `SECURITY.md` | Public routes for reports | Borrow and adapt the wording at stage F |
| `LICENSE` (MIT) | Licence | Keep |
| `release-manifest.txt` | Build Kit's release allowlist | Delete |
| `.env.example` | Build Kit's example keys file | Delete |
| `.gitignore` | Ignore list | Keep and adapt: add `.agents/worktrees/` and `.agents/runs/`, which only the local exclude file holds |

### 1.2 Skills, adapters and plugin metadata

| Item | What it is | Decision |
|---|---|---|
| `.agents/skills/` (13 skills, 110 files) | Build Kit's canonical skills | Delete the prose (the ideas are already captured in `research/skills-audit.md` section 3, which stage A commits). Borrow the scripts and templates listed in 1.3 |
| `.claude/commands/*`, `.claude/skills/*` | Generated Claude adapters | Delete |
| `.cursor/commands/*`, `.gemini/commands/*` | Generated adapters for Cursor and Gemini | Delete |
| `.claude/settings.json` | Maintainer's tracked deny rules | Keep (stage F may add the v1 deny rules for this repository) |
| `.claude-plugin/plugin.json`, `marketplace.json` | Build Kit's Claude plugin | Delete. v1 writes its own when it has commands |
| `agent-plugin/plugin.json` | Agent Plugins manifest | Delete |
| `.agents/skills/maintain/VERSION` | Build Kit version stamp | Delete |

### 1.3 Code v1 borrows (inventory section 5)

All are copied in stage C, with a note of the source commit. Paths here are the
current ones.

| Item | Decision |
|---|---|
| `setup-ai-build-kit/templates/foundation/gate.py` | Borrow (split into modules later; drop old labels, checkpoint route, `plan-refresh` coupling) |
| `.../foundation/ready-lint.py` | Borrow (share one contract parser with the gate) |
| `.../foundation/area-map.py` | Borrow |
| `.../foundation/state-guard.sh`, `claude-settings.json` | Borrow |
| `.../foundation/session-start.sh` | Borrow (fold into `/what-now` later) |
| `.../foundation/plan-refresh.sh` | Borrow the grouping logic only; decide in stage C whether to copy the file or leave it to the archive |
| `.../foundation/piece-issue.yml`, `templates/working-rules.md` | Borrow as starting points for the v1 spec form and area map template |
| `.../foundation/checks.yml`, `gitignore` | Borrow as starting points |
| `.../foundation/AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `README.md`, `copilot-instructions.md`, `env.example`, `templates/masterplan.md`, `templates/CHANGELOG.md`, `templates/maintenance-record`, `templates/merge-ask-rules.json` | Delete (v1 records model replaces them); `merge-ask-rules.json` goes with its script if that is borrowed |
| `setup-ai-build-kit/scripts/merge-ask-rules.py` | Borrow (pattern for merging settings keys) |
| `setup-ai-build-kit/scripts/check-tooling.sh` | Borrow |
| `setup-ai-build-kit/scripts/bootstrap-project.sh`, `place-plan-helper.sh` | Borrow |
| `setup-ai-build-kit/scripts/codex-with-github.py` | Archive (Codex is later) |
| `section-builder/scripts/bar-guard.sh`, `test-guard.sh` | Borrow |
| `section-builder/scripts/co-change.sh` | Borrow |
| `section-builder/scripts/bring-up-to-date.sh` | Borrow (adapt to the run's combined branch) |
| `sync/scripts/fold-changes.py` | Borrow |
| `implement/scripts/worktree.sh` | Borrow (drop `.env` linking and the maintenance-record reads) |
| `sync/scripts/document-claims.py`, `maintain/scripts/document-bloat.py` | Borrow (move into `/maintain`) |
| `maintain/scripts/old-skill-pointers.py` | Delete (Build Kit upgrade path) |
| `ship/recipes/nextjs-supabase-on-vercel.md` and `recipes/parts/*`, `ship/templates/recipe.md`, `ship/references/recipe-format.md`, `.agents/tools/check-recipes.sh` | Decide (Q5). Recommend borrow, since v1's `/setup` deploys through a recipe |
| `ship/recipes/nextjs-supabase-on-coolify.md` | Decide (Q5). Recommend archive |
| `.agents/guard/blocked-commands.md` | Borrow and rewrite for v1 safety level |
| `.githooks/commit-msg` | Keep where it is |
| `.agents/hooks/session-end-sync.sh` | Delete (points at `/sync`) |

### 1.4 Tests

| Item | Decision |
|---|---|
| `tests/lib/rule-shape.sh`, `tests/lib/permission-matcher.py` | Borrow |
| `tests/run-all.sh`, `tests/rehearsal-runner.sh` | Borrow |
| `tests/replay/fake-github/gh`, `tests/replay/fake-host/*` | Borrow |
| Rehearsals that drive borrowed code: `gate-script.sh`, `ready-lint-rehearsal.sh`, `area-map-rehearsal.sh`, `frozen-bar-rehearsal.sh`, `bar-guard-rehearsal.sh`, `state-guard.sh`, `co-change-rehearsal.sh`, `fold-at-merge-rehearsal.sh`, `recheck-before-merge-rehearsal.sh`, `kit-owns-worktrees-rehearsal.sh`, `fake-github.sh`, `fake-host.sh`, `attribution-scrub.sh`, `push-to-main-rules.sh`, `merge-ask-rule.sh`, `check-tooling.sh`, `session-start.sh`, `document-read-rehearsal.sh`, `document-bloat-rehearsal.sh`, `test-strength-rehearsal.sh`, `trim-rehearsal.sh` | Borrow. Strip assertions that read Build Kit skill prose; keep the ones that drive code. Each must pass at its new path before stage D |
| `tests/lib/recipe-rehearsal.sh`, `recipe-*.sh`, `recipes.sh`, `tests/recipes-awaiting-run/` | Follow Q5 |
| All other `.agents/tests/*.sh` (about 95 prose-shape guards) | Delete |
| `tests/replay/` apart from the stand-ins (harness, 23 cases, fixtures, grader, `baseline.md`) | Archive (tag). Q7 asks whether v1 wants the harness back later |
| `tests/scenarios.md`, `mutate.sh`, `mutation-audit.md` | Archive (tag) |

### 1.5 Tools and release machinery

| Item | Decision |
|---|---|
| `.agents/tools/validate-kit.sh` (2,357 lines) | Delete. First borrow its two checks that still matter: no issue or pull request number in a tracked file, and no attribution line or session link in a tracked file (stage C, as a small v1 check) |
| `build-adapters.sh`, `build-release.sh`, `stamp-version.sh`, `promote-stable.sh`, `finish-release-draft.sh`, `check-release-label.sh`, `check-pull-request-base.sh`, `preflight-cutover.sh`, `rehearse-merged-tree.sh`, `plan-refresh.sh` | Delete |
| `.agents/migration/*`, `docs/MIGRATION.md`, `docs/MIGRATION-READINESS.md` | Delete (identical on ai-build-kit `main`) |

### 1.6 Documents

| Item | Decision |
|---|---|
| `docs/MAINTAINING.md` | Delete. Carry the house writing rules and the `core.hooksPath` command into v1's AGENTS.md |
| `docs/PHILOSOPHY.md` | Archive. v1's "Skills and checks" section replaces it |
| `docs/SOURCES.md` | Borrow and prune to what v1 still uses. Credits must survive |
| `docs/COMPATIBILITY.md` | Delete (v1 is Claude Code only) |
| `docs/design/loop-first-redesign.md`, `loop-first-round-2.md`, `agentic-loop-research.md`, `evaluation-system.md` | Archive (tag; also on ai-build-kit branches or `main`) |
| `docs/design/agentic-loop.md` | Archive (tag; identical on ai-build-kit `design/agentic-loop`) |
| v1 design document (claude.ai artifact) | New: export into `docs/design/v1/` in stage A |

### 1.7 Maintainer skills

| Item | Decision |
|---|---|
| `humanizer` (with its MIT `LICENSE`) | Keep |
| `review-issues` | Keep; adapt to v1 labels in stage G |
| `stack-research` | Follow Q5 (keep if recipes are borrowed) |

### 1.8 GitHub: workflows, templates, settings

| Item | Decision |
|---|---|
| Workflow `source checks` (off) | Delete file in stage D |
| Workflow `maintainer branch check` (off) | Delete file in stage D |
| Workflow `prepare release`, `verify release` | Delete files in stage D |
| Workflow `update release draft` and `.github/release-drafter.yml` | Switch off in stage B (person), delete files in stage D |
| Workflow `release label` | Delete in stage D. Until then every removal pull request carries `skip-release-notes` |
| Workflow `pull request base` | Delete in stage D (guards a `stable` branch this repository does not have) |
| New: v1 check workflow | Added in stage C, running the borrowed rehearsals and the number and attribution check |
| `.github/ISSUE_TEMPLATE/*` | Decide (Q8). Recommend keep `config.yml`, rewrite the two forms at stage F |
| Setting: private | Decide (Q2) |
| Setting: no branch protection (not available) | Decide (Q2) |
| Setting: squash and merge commit both allowed, delete branch on merge on | Keep for now; v1 decides its merge method |
| Secrets, webhooks, environments | None found. Nothing to do |

### 1.9 GitHub: issues, labels, releases

| Item | Decision |
|---|---|
| The old v1 epic, "AI Loop Kit v1" (open) | Decide (Q3). Recommend close as not planned and open a new epic from the design document |
| The slice 1 to 6 issues (closed, still labelled `building`) | Keep closed; drop the stale `building` label in stage G |
| The slice 7 issue (`building`) | Close as not planned, comment naming the two archive tags |
| The slice 8 to 23 issues (`ready`) | Close as not planned, comment "superseded by the v1 design" |
| The core docs pass issue | Close as not planned |
| The lessons issue from the first unattended night | Keep open; relabel in stage G |
| The Build Kit backlog issues (open, `after-1.0`) | Decide (Q4) |
| The closed Build Kit issues carried over | Keep as history |
| Labels: the nine GitHub defaults | Keep |
| Labels: `area:docs`, `area:skills`, `area:tests`, `area:release`, `epic`, `feature`, `chore` | Decide with v1's label set (Q6). Recommend keep until v1's gate creates its own |
| Labels: `ready`, `building`, `status:blocked`, `needs-answers`, `after-1.0` | Delete in stage G, after the issues using them are closed or relabelled |
| Labels: `release-major`, `release-minor`, `release-patch`, `skip-release-notes` | Delete in stage G (they serve the release drafter) |
| Draft release "AI Build Kit v0.0.1" | Delete (person, stage B) |

### 1.10 The paused build's leftovers

| Item | Decision |
|---|---|
| Remote branch `v1-integration` | Archive by tag `archive/v1-paused-slice-07a`, then delete (person) |
| Remote branch `slice-06b-evidence-deny` | Delete (content is on `main`) |
| Local branch `slice-07b-fix-loop` (only copy) | Archive by tag `archive/v1-paused-slice-07b`, then delete |
| Local branch `slice-07a-build-fix-loops` | Archive by tag `archive/v1-paused-slice-07a-early`, then delete |
| Other 18 local branches | Delete after a content check (all on `main`) |
| 17 stale `origin/*` tracking refs | Prune with `git fetch --prune origin` |
| `build-kit` remote and its one tracking ref | Keep the remote (reference) |
| Worktree `.agents/worktrees/integration` | Remove with `git worktree remove` (never forced) after the tag, once `git status` there is clean |
| Worktree `.agents/worktrees/slice-07b` | Same, after the tag. Check it first for uncommitted work |
| `.agents/tmp/v1-factory/` design inputs (`redesign-answers.md`, `inventory.md`, `decisions.md`, `research/*.md`, `issue-*.md`) | Archive into `docs/design/v1/` on `main` in stage A |
| `.agents/tmp/v1-factory/` tooling and logs (coordinator, briefs, watchdog, dashboard, `state.json`, `packs/`, `reports/`, `backups/`, `cross*/`, `.bak` files) | Archive to a dated tarball outside the repository (person), then remove the folder |
| `.claude/settings.local.json` allow rules for the paused build | Remove the `local-checks.sh` rules and `gh pr merge * --merge` (person). Keep every deny rule |
| Auto memory file for the v1 factory | Update its paths once stage A lands (the maintainer's call) |

## 2. Staged plan

Every stage that changes `main` is one pull request from a short-lived branch.
The person merges it. Every pull request carries `skip-release-notes` until
stage D removes the `release label` workflow. Undo for any merged pull request
is a revert pull request (`git revert -m 1 <merge commit>` on a new branch);
the archive tags are the deeper fallback. "Person" marks a step only the
maintainer can do, because it touches settings, deletes something on GitHub,
or hits a local deny rule.

### Stage A. Safety tags and archive (person, then one pull request)

What changes:

1. Person: copy `.agents/tmp/v1-factory/` whole to a tarball outside the
   repository, for example
   `~/ARCHIVE/ai-loop-kit-v1-factory-20261005.tar.gz`.
2. Person: create and push four annotated tags:
   `archive/build-kit-final` on `fbdf054`,
   `archive/v1-paused-slice-07a` on `c767408`,
   `archive/v1-paused-slice-07b` on `21d9a87`,
   and `archive/v1-paused-slice-07a-early` on `1a29f87`.
   No `v` prefix, so nothing reads them as releases.
3. Pull request: add `docs/design/v1/` with the design document exported from
   claude.ai, `redesign-answers.md`, `inventory.md`, `decisions.md`, the eight
   `research/*.md` files and the two issue drafts. Before saving, take out the
   issue numbers found in `agentic-loops.md`, `gates-determinism.md`,
   `red-team.md`, `skill-principles.md`, `skills-audit.md` and `decisions.md`.

Before: `git status` clean on `main`; tarball opens and lists `redesign-answers.md`.
After: `git ls-remote --tags origin 'archive/*'` lists four tags at the four
commits above; `git ls-files docs/design/v1 | wc -l` is 13 or more;
`grep -rEn '#[0-9]+' docs/design/v1` prints nothing.
Undo: tags can be deleted by the person; the pull request reverts.
Who: person for 1 and 2; an agent may prepare 3.

### Stage B. Close out the paused build (person, plus one small pull request)

What changes:

1. Person: in each worktree, run `git status`. Save or discard anything there
   on purpose. Then `git worktree remove .agents/worktrees/integration` and
   `git worktree remove .agents/worktrees/slice-07b`. Never `--force`.
2. Person: delete remote branches `v1-integration` and
   `slice-06b-evidence-deny`; `git fetch --prune origin`; delete the local
   slice branches, `v1-integration` and `fix/plugin-root-claude-warning`.
3. Person: switch off the `update release draft` workflow and delete the draft
   release "AI Build Kit v0.0.1".
4. Person: remove the paused build's allow rules from
   `.claude/settings.local.json`.
5. Person, or an agent with a yes on the exact words: close the slice 7 to 23 issues and
   the core docs pass issue as not planned, each with one comment naming the archive tags and the v1
   design. Settle the old v1 epic per Q3.
6. Pull request B2 (transition text): replace `README.md` and `AGENTS.md` with
   short transition versions. README: "This repository is becoming AI Loop
   Kit v1. AI Build Kit lives on at gwpicard/ai-build-kit. Its last state here
   is the tag `archive/build-kit-final`." AGENTS.md keeps the house rules and
   says the Build Kit files below are being removed, so agents read no
   instructions about checks that are going away. Add `.agents/worktrees/` and
   `.agents/runs/` to `.gitignore`.

Before: stage A's checks pass.
After: `git worktree list` shows one line; `git ls-remote --heads origin`
shows only `main`; `git branch` shows only `main`; `gh release list` is empty;
`gh workflow list --all` shows `update release draft` as disabled;
`gh issue list --state open` lists only 1 (if kept), 26 to 38 and 72;
`wc -l AGENTS.md` is under 150.
Undo: branches and worktrees come back from the tags
(`git worktree add <path> archive/v1-paused-slice-07b -b slice-07b-fix-loop`);
issues reopen; the workflow switches back on; B2 reverts.
Who: person for 1 to 4; 5 as noted; an agent may prepare B2.

### Stage C. Copy the borrowed code into v1's place (one pull request)

What changes: copy (not move) every item marked Borrow in 1.3, 1.4 and 1.6
into the layout v1 chooses (Q1). Add a short `BORROWED.md` there listing each
file, the commit it came from (`fbdf054`) and what it must shed (taken from
inventory section 5). Fix paths inside the copied rehearsals and strip
assertions on Build Kit prose. Add a small check for issue and pull request
numbers and attribution lines in tracked files, lifted from `validate-kit.sh`.
Add a v1 workflow that runs the copied rehearsals and that check on every pull
request.

Before: stage B2 merged.
After: the new workflow is green on the pull request. Running the new
`run-all.sh` locally names no failure. `.agents/skills/` is unchanged, so the
originals still run as before.
Undo: revert; nothing else depends on the copies yet.
Who: an agent prepares, the person reviews and merges.

### Stage D. Remove Build Kit (two pull requests)

D1, machinery: delete `.claude/commands/`, `.claude/skills/`, `.cursor/`,
`.gemini/`, `.claude-plugin/`, `agent-plugin/`, `release-manifest.txt`,
`.agents/tools/` (all of it), `.agents/migration/`, `docs/MIGRATION*.md`,
`docs/COMPATIBILITY.md`, `.github/release-drafter.yml` and the workflows
`source-checks`, `maintainer-branch-check`, `prepare-release`,
`verify-release`, `release-drafter`, `release-label`, `pull-request-base`,
plus `GEMINI.md`, `.github/copilot-instructions.md`, `llms.txt`,
`.env.example`, `.agents/hooks/`.

D2, skills, tests and documents: delete `.agents/skills/`, `.agents/tests/`
(the originals; v1's copies live elsewhere), `WORKFLOW.md`,
`docs/MAINTAINING.md`, `docs/PHILOSOPHY.md`, `docs/design/*.md` outside
`docs/design/v1/`, and anything decided under Q5 and Q7.

Files are removed with `git rm`, never `rm -r`, which the deny rules refuse.
`git rm -r` is not refused, but on a sweep this size the person runs it or
approves the exact command.

Before: stage C merged and its workflow green on `main`.
After: `git ls-files .agents/skills .agents/tests .agents/tools .claude/commands .claude/skills .cursor .gemini | wc -l` is 0;
`gh workflow list --all` shows only the v1 workflow;
`git grep -nI -e 'AI Build Kit' -e 'ai-build-kit'` matches only README's
pointer, `docs/SOURCES.md`, `BORROWED.md` and `docs/design/v1/`;
the v1 workflow is green on the pull request.
Undo: revert the pull request, or restore any path with
`git checkout archive/build-kit-final -- <path>` on a branch.
Who: an agent prepares; the person reviews and merges. The maintainer's
`/shape` and other Build Kit commands in this folder stop after D1.

### Stage E. Confirm nothing points at a removed file (one pull request, often empty)

What changes: fix any reference left behind: `.gitignore` lines for removed
paths, `CONTRIBUTING.md` and `SECURITY.md` pointers, `.githooks/` comments,
the transition AGENTS.md list.

Before: stage D merged.
After: a script lists every path named in a tracked Markdown file and finds
each one exists (the borrowed `document-claims.py` does this); v1 workflow
green.
Undo: revert.
Who: an agent prepares; the person merges.

### Stage F. v1's minimal root files (one pull request)

What changes: write v1's `README.md` (what it is, Claude Code only, status:
being built, pointer to Build Kit), `AGENTS.md` at 150 lines or fewer under
the records model (commands, non-obvious rules with reasons, pointers),
`CLAUDE.md` importing it, `CONTRIBUTING.md`, `SECURITY.md`, issue forms, and
a pruned `docs/SOURCES.md`. Every word goes through the humanizer in embedded
mode. `.claude/settings.json` gains the v1 deny rules this repository wants
for itself.

Before: stage E merged.
After: `wc -l AGENTS.md` is 150 or fewer; the number and attribution check is
green; the v1 workflow is green.
Undo: revert to the transition texts.
Who: an agent drafts; the person reviews the words and merges.

### Stage G. Labels, issues and settings (person)

What changes: settle the Build Kit backlog issues per Q4 and relabel the lessons issue from the first unattended night; delete the
labels listed in 1.9 once no open issue uses them; create v1's label set only
when v1's gate defines it; apply the answer to Q2.

Before: stage F merged.
After: `gh label list` shows no `ready`, `building`, `status:blocked`,
`needs-answers`, `release-*` or `skip-release-notes`; no open issue carries a
deleted label.
Undo: labels can be recreated by name and colour (record them first with
`gh label list --json name,color,description > labels-before.json` outside the
repository); issues reopen.
Who: person.

## 3. Risks and how each is avoided

| Risk | How it is avoided |
|---|---|
| Breaking an install route people use | None points here: every manifest and the README name ai-build-kit, and this repository is private. Stage F's README points at ai-build-kit so nobody looks here for Build Kit |
| Losing work that is not in ai-build-kit | Stage A comes first: tags for `main`, both slice 7 parts and the early 7a; the design inputs committed to `docs/design/v1/`; the whole factory folder in a tarball. Nothing is deleted before stage A's checks pass |
| Losing uncommitted work in a worktree | The person runs `git status` in each worktree before removing it, and never uses `--force` |
| The validator or CI blocking the removal | The validator runs nowhere today (both workflows are off). `release label` would refuse unlabelled pull requests, so each carries `skip-release-notes` until D1 removes it. `pull request base` passes, since the base is `main` |
| Losing the guards the validator gave | Stage C lifts the number and attribution checks into the v1 workflow before D1 deletes `validate-kit.sh`. The commit-msg hook stays |
| `main` describing files that are gone | Stage B2 replaces README and AGENTS.md with transition texts before anything is deleted, so each later stage matches what `main` says |
| The draft release or release drafter reacting to merges | Stage B switches `update release draft` off and deletes the draft before the deletions begin |
| The maintainer's Claude Code settings | `.claude/settings.json` is kept. Only the paused build's two allow rules leave the local file; every deny rule stays. The maintainer loses `/shape` and friends in this folder at D1, which is expected, and should know before merging |
| An agent merging without the person | The `gh pr merge * --merge` allow rule goes in stage B. With no branch protection available, the deny rules are the only guard on `main` until Q2 is answered |
| Borrowed code breaking silently in its new place | Stage C copies and tests before stage D deletes; the originals keep running until then |
| Issue numbers or session links entering `docs/design/v1/` | Stage A scrubs the files before committing; stage C's check holds it from then on |
| Fresh clones committing worktrees | Stage B2 adds `.agents/worktrees/` and `.agents/runs/` to the tracked `.gitignore` |
| History hard to follow after copy and delete | `BORROWED.md` names each file's source commit; the archive tag keeps the old paths |

## 4. Questions for the maintainer

1. **Where does borrowed code live?** Recommend `kit/scripts/` for runtime
   scripts, `kit/templates/` for files copied into projects, `kit/recipes/`
   for recipes, and `tests/` (with `tests/lib/` and `tests/stand-ins/`) at the
   root, with `.agents/` kept only for maintainer skills and the guard list.
   Settle this before stage C.
2. **Server-side protection.** A free private repository cannot protect
   `main`, which the v1 safety principle (two independent layers) needs.
   Recommend GitHub Pro (or making the repository public once v1 is ready) and
   then a ruleset on `main`: pull request required, no force push, no
   deletion. Until then, say so plainly in AGENTS.md, as answer B5 asks `/setup`
   to do for users.
3. **The old v1 epic.** Recommend closing it as not planned with a
   comment, and opening a fresh epic for v1 built from the design document, so
   the new epic carries no list of superseded slices.
4. **The Build Kit backlog issues.** No twin was found in ai-build-kit. Recommend:
   transfer the Build-Kit-only ones (working as a team, measuring /start, the
   fit check wording that assumes a workplace team, and work bigger than one
   parent) to ai-build-kit with `gh issue transfer`; keep the ones on
   evaluation after v1, screens without a designer, a tailored harness,
   comparing performance with other systems, half-wired rules and richer
   dependency analysis for v1 with a v1 label; close the ones on meeting a
   project the kit did not write, carrying a build to a shipped app, and a
   better frontend skill if v1's own testing plan covers them.
5. **Recipes.** Recommend borrowing the Vercel recipe, its parts, the format
   and `check-recipes.sh` (v1's `/setup` deploys through a recipe), keeping
   `stack-research`, and archiving the Coolify recipe and the awaiting-run
   folder.
6. **v1's labels.** Recommend keeping `area:*`, `epic`, `feature` and `chore`
   until v1's gate creates its own set, then deleting what the gate does not
   use. Never reuse `ready` or `building` with a new meaning on the same
   issues.
7. **Replay harness.** Recommend archiving it (tag only) and borrowing just
   the two stand-ins; v1's testing plan decides later whether a replay harness
   returns.
8. **Issue forms.** Recommend keeping `config.yml` and rewriting the bug and
   feature forms in stage F to file into `/shape`'s raw state.
9. **Design branches in ai-build-kit** (`design/agentic-loop`,
   `handoff/ai-loop-kit-v1`, the `gwpicard/v1-*` branches). Out of scope here.
   Recommend leaving them until stage A has landed, then tidying them in that
   repository as a separate job.
10. **Merge method for the removal pull requests.** Recommend a merge commit
    (not squash), so each stage is one revertable merge and `BORROWED.md`'s
    source commits stay reachable.
