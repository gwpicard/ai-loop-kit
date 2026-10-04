# Slice 14: /deploy sets up previews, production on merge, rollback and health once, and every builder gets its own running copy of the app

Labels (today's set): enhancement, area:skills, ready-able once shaped. Release label for the PR: release-minor (Part a: release-major, since a command a person types is renamed).
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 9: Run controller; slice 10: Crews and computer resources; slice 13: Merge policy.

## So that
A person sets up how their tool goes live once, with one command, after which every merge goes live on its own, every branch has a preview that never touches real data, and every builder in a run can boot its own copy of the app without fighting another for a port or a database.

## Done when

This slice splits into four parts, each merged on its own pull request, in order.

### Part a: the rename from /ship to /deploy

#### Works
- The canonical skill folder is `.agents/skills/deploy/`, carrying today's references, templates and recipes; no `ship` folder remains. Check: `validate-kit.sh` (the canonical inventory names `deploy` among the nine commands and fails on a `ship` folder).
- The generated adapters are `.claude/commands/deploy.md`, `.cursor/commands/deploy.md` and `.gemini/commands/deploy.toml`, the Claude plugin lists `./.claude/commands/deploy.md`, and the release allowlist ships `.agents/skills/deploy` and rebases it under `agent-plugin/skills/deploy`. Check: `build-adapters.sh` then `validate-kit.sh` (adapter drift, plugin listing); `claude-plugin.sh`; `agent-plugin.sh`; `release-builder.sh`.
- Every skill, reference, script and template that loads "the `ship` skill" or names `/ship` now names `deploy` and `/deploy`, including `merge.md`, `running-longer.md`, `second-opinion`, `screen-check`, `sync`, `what-now`, `maintain`, the founding skill's references and scripts (`check-tooling.sh`, `merge-ask-rules.py`), and the foundation templates (AGENTS.md, CHANGELOG.md, masterplan.md). Check: `validate-kit.sh` (every named skill and reference path resolves); a new stale-claim entry in `validate-kit.sh` fails on `/ship` in any shipped file outside `docs/design/` and CHANGELOG history.
- The founding menu reads recipes from the installed `deploy` skill's `recipes/` folder on every installation route. Check: `founding-menu.sh`, `plan-helper-routes.sh`, `claude-plugin.sh`, `agent-plugin.sh`.
- The skill lists `/maintain`'s existing steps read (the shared route's lockfile count and `scripts/old-skill-pointers.py`) name `deploy` in place of `ship`, so their rehearsals keep passing. No migration from `ship` to `deploy` is added, because AI Loop Kit has no project founded on `ship` (decision 63), and slice 17: /maintain absorbs /sync removes those old-project steps. Check: `shared-route-adds.sh` and `older-project-upkeep.sh` pass with the new name.
- Every rehearsal that reads the skill by path reads `deploy`: `hosting-request.sh`, `ship-runs-recipe.sh` and `ship-merges-and-deploys-once.sh` (renamed `deploy-runs-recipe.sh` and `deploy-merges-and-deploys-once.sh`), `recipes.sh`, both `recipe-*.sh`, `lib/recipe-rehearsal.sh`, `not-hosted.sh`, `request-record.sh`, `secret-location.sh`, `no-stored-logins.sh`, `one-merge-step.sh`, `offer-recipe-move.sh`, `founding-menu.sh`, `fake-host.sh`, `replay-state.sh`, `gated-turns.sh`, `pre-release-run.sh`, `mutate.sh` and the replay cases and preparations that type `/ship`. Check: `.agents/tests/run-all.sh` passes; `validate-kit.sh` ("AGENTS.md names every maintainer check") with the renamed files.
- Documents: WORKFLOW.md section 1's command list and section 9 (renamed "Going live: /deploy"), README.md's command table and "How a project flows", docs/COMPATIBILITY.md's command list, docs/MAINTAINING.md's ship control-flow notes, llms.txt, and the root AGENTS.md paragraphs on the renamed checks. Check: `validate-kit.sh` ("every shipped document that lists the commands names all of them" and the stale `/ship` entry above).

#### When it is not the normal case
- A person types `/ship` from habit: there is no such command; the agent treats the words that follow as a request and runs `/deploy`, since the kit starts a command when the person asks for its job in plain words. Check: `deploy.sh`, a rule in the foundation AGENTS.md command list.
- A project founded with AI Build Kit, which holds `ship`: does not arise, because AI Loop Kit does not move such a project (decision 63).

### Part b: what /deploy does

#### Works
- `/deploy` sets up the pipeline the recipe describes: previews for branches, production on every merge to `main`, rollback, secrets and the health check, then runs the recipe's checks once to prove each and reports each in one plain line, as `/ship` does today. It runs on the first deployment and again when the project moves to a new recipe; at any other time it says the pipeline is set up and what it last found. Check: new `.agents/tests/deploy.sh` (rule-shape) reads each rule from `deploy/SKILL.md` and proves it load-bearing.
- A merge to `main` goes live: `/deploy` writes `Goes live: on every merge` for a hosted tool and runs `merge-ask-rules.py add`, and the promote step ("Promoting to live") and the `through /ship` value are gone from `deploy/SKILL.md`, `merge.md`, the masterplan template and WORKFLOW.md. Check: `deploy.sh` refuses a copy carrying "Promoting to live" or `through /ship`; `merge-ask-rule.sh` still drives the script.
- The merge step reads `Goes live:` as `on every merge` or `not hosted`, and a line still saying `through /ship` is a record gap the merge step names, never a third route, because AI Loop Kit has no project founded before the promote step went (decision 63). Check: `deploy.sh` reads the reading rule; `not-hosted.sh` holds the two-way reading.
- On a tool that is `not hosted`, `/deploy` sets up no pipeline; when the person asks for a release it makes one exactly as `/ship`'s "Releasing a tool that is not hosted" does today, on a yes naming the tag. Check: `not-hosted.sh` (paths renamed, rules unchanged).
- The first deployment runs the evidence run and the launch review, the request-record check and the monitoring caution, once, and writes the hosting request where the recipe's going-live section is run by a companion or the person. Later runs of `/deploy` do none of these again. Check: `deploy.sh`; `request-record.sh` and `hosting-request.sh` still pass.
- The risk notice for a sensitive area is no longer given at deployment; `/deploy` reads each area's `Accepted:` line and a piece in an area without one never reached `main`, so `/deploy` only names areas that are not `done` or `accepted` as a warning. Check: `acceptance-is-earned.sh` changed to hold the notice in shaping and its absence from `/deploy`; `deploy.sh`.
- The build paths keep today's behaviour: on Explore privately, `/deploy` sets up previews only and never production; on Build and run it, it sets up the whole pipeline; on Build with care it does the same and runs the launch review on the first deployment, as `/ship` does today. Check: `validate-kit.sh`'s ship control-flow contract, renamed for `deploy/SKILL.md`, and `deploy.sh` for the Build with care launch review.
- Documents: WORKFLOW.md section 9 says what `/deploy` sets up, that a merge goes live, and that `/deploy` is run again only for a new home; README.md's command table line for `/deploy`; the masterplan template's "How it stays running" comment. Check: `deploy.sh` reads each and refuses the old promote sentence.

#### When it is not the normal case
- The person declines a step that changes a live service (connecting the repository, a host setting): that section is a warning, said once and written in CHANGELOG.md, and `/deploy` goes on, as `/ship` does today. Check: `deploy-runs-recipe.sh` (renamed `ship-runs-recipe.sh`).
- The project is off a recipe: `/deploy` names what it could not set up or check, one line each, and records how the tool goes live as the person says. Check: `deploy.sh`.
- A deploy's output does not show whether it went live: the whole output or the host's list is read before any second deploy. Check: `deploy-merges-and-deploys-once.sh` (renamed).

### Part c: the recipe fields for previews and a running copy per worktree

#### Works
- `recipe-format.md` defines three new parts of a recipe: a `Preview address:` opening line saying what the host gives (one per branch and per commit, one per pull request, or none, where a local checkout on its own port is the fallback); a `## Preview data` section saying how each preview gets its own throwaway database seeded with the project's sample data, or the host's own database branching; and a `## Local app` section saying how to boot a copy of the app inside one worktree, on its own port, with throwaway seeded data and a log file the builder reads, and the memory that copy needs. Check: `recipes.sh` extended; `.agents/tools/check-recipes.sh` refuses a recipe missing any of the three and accepts the blank in `deploy/templates/recipe.md` once filled.
- Both recipes carry the three. The Vercel recipe's `Preview data` uses Supabase branching where the plan allows it, and records previews sharing one preview database where it does not; the Coolify recipe the same for its preview rows. Both `Local app` sections boot a local Supabase stack per worktree on ports taken from the worktree's own port, run the worktree's migrations and `supabase/seed.sql`, start the app on the worktree's port and write the log under the worktree's ignored `.agents/app.log`. Check: `recipe-nextjs-supabase-on-vercel.sh` and `recipe-nextjs-supabase-on-coolify.sh` extended, with the stand-ins for `supabase` and `docker` refusing an option the real commands lack; `lib/recipe-rehearsal.sh` holds the shared local app rules.
- `worktree.sh` gains an `app` command that runs the recipe's local app for one worktree and stops it, so a builder and the walk-through never start it by hand, and two worktrees never share a port or a database. Check: `kit-owns-worktrees-rehearsal.sh` opens two worktrees, starts the app in each through a stand-in recipe command and reads two ports, two stand-in databases and two logs, and reads both stopped after `worktree.sh app stop`.
- The run counts each running local app's memory, from the recipe's `Local app` section, in slice 10's suggestion and pressure checks. Check: `resources-rehearsal.sh` extended.
- A recipe's going-live section allows a migration that drops or rewrites data only after the backup slice 13 requires, and keeps "a migration in a release only adds" for every other migration. Check: both recipe rehearsals read the rule.
- `deploy/SKILL.md` names no product: the new sections are read from the recipe at run time. Check: `hosting-request.sh` (no product named outside the recipes).
- Documents: WORKFLOW.md section 10 says each builder boots its own copy of the app with made-up data, and section 9 says previews never touch real data. Check: `deploy.sh`.

#### When it is not the normal case
- A project off a recipe has no `Local app` section: the walk-through runs the app the way `AGENTS.md`'s stack section says, one worktree at a time, as today. Check: `deploy.sh`.
- Docker is not running when a builder needs the local app: environment failed, never a kickback (slice 7's route). Check: `kit-owns-worktrees-rehearsal.sh` with the stand-in `docker info` failing.
- The host plan has no database branching: previews share one preview database, reset and seeded before each preview, never the live one; the recipe says so and `Previews keep their own data:` is never written for that case, so automatic merge stays off. Check: both recipe rehearsals.

### Part d: real runs of both recipes

#### Works
- Each recipe's proven section records a new real run, from an empty project, of `/deploy` setting up the pipeline and of a merge going live, with one outcome line for each of the eight sections and for preview data and local app, and a `Previews keep their own data:` line with its date where the run proved two previews and production each answered with a different database reference. Check: guided check: the maintainer runs `/deploy` on a throwaway project for each recipe with their own accounts, following the trial in docs/MAINTAINING.md, and records the lines; `recipes.sh` and `check-recipes.sh` then pass on both recipes.
- The run includes one failed health check after a merge on the Vercel recipe and the kit's rollback, so slice 13's health and rollback are seen once for real. Check: guided check, recorded in the Vercel recipe's proven section under Rollback.
- `docs/MAINTAINING.md`'s pre-release trial says `/deploy` where it said `/ship`, and the teardown also removes the preview database branch. Check: `pre-release-run.sh` extended.
- The recipes stay out of `recipes-awaiting-run/` throughout, because their `How it works:` lines changed and recipe-format only requires a new real run before the next release. Check: `recipes.sh` (a recipe in both places fails).

#### When it is not the normal case
- The maintainer's Supabase plan has no branching: the run records previews sharing one preview database and writes no `Previews keep their own data:` line for that recipe; automatic merge stays off for projects on it until a run on a plan with branching. Check: `recipes.sh` accepts a proven section without the line.
- A real run finds a step the recipe does not describe: the recipe is corrected in the same pull request and the run repeated for that section, as the earlier recipe runs were. Check: guided check.

## Masterplan change
Design note: "Deployment" and the `/deploy` row of "Commands" in docs/design/agentic-loop.md. The note needs two additions: a preview database shared by all previews does not count as previews keeping their own data; and the local app's memory counts in the run's builder count.

## Not in this piece
- The automatic merge conditions, the smoke test, health after a merge, rollback and the backup before an irreversible change: slice 13: Merge policy; this slice gives them the recipe fields and their first real run.
- The network allowlist taken from the recipe: slice 15: Safety boundary for runs.
- Any move of a project founded with AI Build Kit from `/ship` to `/deploy`: none, by decision 63; slice 17: /maintain absorbs /sync removes the old kit's rename migrations.
- The replay scenarios for `/deploy`: slice 20: Replay harness rewrite and real runs, which reuses these real runs rather than repeating them.
- The product's new names: slice 22: Set AI Loop Kit's names.
- Making every document tell one story: slice 21: Documentation sweep.

## Decided
- `/ship` becomes `/deploy` (decisions 17 and 21), and founding still chooses the recipe (decision 20).
- A merge to `main` goes live (decision 17), so the promote step and the `through /ship` value go.
- Each preview uses its own throwaway database or the host's branching, and automatic merge stays off on a recipe until a real run proves it (decision 49); a shared preview database is honest about not meeting that.
- The bootable app per worktree is a recipe field (decision 46), started and stopped by `worktree.sh` so the dev server lives only as long as it is used (decision 45).
- Not hosted: a merge means done, and `/deploy` makes a release when asked (decision 50), unchanged from today's release flow.
- The risk notice moves to shaping (decision record, points resolved in the note), so `/deploy` only reports where each area stands.
- The real runs of both recipes belong here, because recipe-format ties a changed `How it works:` line to a real run, and slice 20 records them as its `/deploy` runs rather than running them twice.

## Data
- The masterplan's `Goes live:` line loses the `through /ship` value.
- Each worktree's local app writes an ignored log and runs a local database that `worktree.sh app stop` removes; nothing tracked changes.
- Recipe files gain three parts and new proven lines.
- `.ai-build-kit-maintenance` gains nothing.
- No project founded with AI Build Kit is moved (decision 63); recipe changes reach AI Loop Kit projects with the update.

## Leaves the tool
What the recipe already sends, now set up once by `/deploy`: the host connection, environment variable names, preview and production builds. New: one database branch per preview on hosts that offer branching, created by the host from the Git branch. The real runs in Part d use the maintainer's own accounts, with each online step approved at that step.

## Must still hold
- No product named outside the recipes. Check: `hosting-request.sh`, `deploy-runs-recipe.sh`.
- A check not done is a warning, said once and written in CHANGELOG.md; only the address is waited for. Check: `deploy-runs-recipe.sh`.
- Rollback is "possible, not tried" unless asked for or forced by a failed health check. Check: `deploy-runs-recipe.sh`, `deploy-merges-and-deploys-once.sh`.
- Stored logins are never read; a live change waits for a named yes unless the recipe names the command. Check: `no-stored-logins.sh`.
- A secret's location, never its value. Check: `secret-location.sh`.
- The founding menu, its default and the `founding-menu` line. Check: `founding-menu.sh`, `offer-recipe-move.sh`.
- Worktree safety: `.env` linked for work outside a run, while a run's worktree carries no production secrets and no `.env` link (slice 15); no forced removal; the main folder never switched. Check: `kit-owns-worktrees.sh`, `kit-owns-worktrees-rehearsal.sh`.
- The founded AGENTS.md under its ceiling. Check: `standing-instructions.sh`, `agent-first-records.sh`.
- No issue numbers and no attribution lines in tracked files. Check: `validate-kit.sh`.

## Relies on
- `.agents/skills/ship/` with `SKILL.md`, `references/evidence-run.md`, `references/hosting-request.md`, `references/recipe-format.md`, `templates/recipe.md`, `templates/handover.md`, both recipes and four parts; `implement/scripts/worktree.sh`; `check-recipes.sh`; the stand-ins in `replay/fake-host/`: on main today.
- The run controller: slice 9. Builder memory accounting: slice 10. The merge policy, smoke test, health after merge and the `Previews keep their own data:` line's definition: slice 13.

## Reach and risk
Boundary: the `ship` skill becoming the `deploy` skill, every skill, reference and template that names it, the skill names in the `maintain` skill's existing steps, `worktree.sh`, the recipe format, both recipes and their parts, the adapters, the plugin listing, the release allowlist, WORKFLOW.md, README.md, docs/COMPATIBILITY.md, docs/MAINTAINING.md, llms.txt, the root AGENTS.md checks list.
Reaches: founding (`founding-menu.sh`, `check-tooling.sh`, `starter-rehearsal.sh`), installation routes (`claude-plugin.sh`, `agent-plugin.sh`, `plan-helper-routes.sh`, `release-builder.sh`), merging (`one-merge-step.sh`, `merge-ask-rule.sh`, `not-hosted.sh`), the replay harness (`replay-state.sh`, `gated-turns.sh`, scenarios 47 and 51 to 55), the pre-release trial (`pre-release-run.sh`).
If it breaks: a project loses its going-live command, or a preview reaches live data. The person notices `/deploy` missing, or the maintainer's real run shows a preview reading the live project. The rename is undone by reverting Part a; a recipe change by reverting its part and moving the recipe back to its last proven text.
Depends on: 9, 10, 13.
Loop module: build, because the rename, the skill rules and the recipe fields are all judged by rehearsals; Part d is a guided real run.
Crew: default.

## Under the hood
Part a is a mechanical rename across the tree (`git mv` of the skill folder and the two rehearsal files), then `build-adapters.sh`, then each named rehearsal's paths, then the skill names in `maintain`'s existing steps. No migration is written. Part b rewrites `deploy/SKILL.md` around setting up rather than launching, keeping its rules on warnings, logins, secrets, live changes and deploy output word for word where they still apply. Part c extends `recipe-format.md`, `templates/recipe.md`, `check-recipes.sh`, both recipes, `lib/recipe-rehearsal.sh` and the `supabase` and `docker` stand-ins, and adds `worktree.sh app`. Part d follows docs/MAINTAINING.md's trial. Canonical skills change in every part: five questions in each pull request, SOURCES.md credits where a borrowed idea lands (Supabase branching is the product's own feature and needs none), adapters rebuilt, validator run, humanizer on the prose, no issue numbers.

## Evidence
Parts a to c: the validator, the full rehearsal suite and new or extended rule-shape and recipe rehearsals, each rule proved load-bearing. Part d: a recorded real run for each recipe, with the maintainer's accounts and approval at each online step.

## Size
Four sittings, one per part; Part d needs the maintainer present with accounts.

## Consistency notes
- No migration from `/ship` to `/deploy` and no `through /ship` offer, because AI Loop Kit is for new projects (decision 63). The skill names in `/maintain`'s existing old-project steps change only so their rehearsals pass until slice 17 removes those steps.
- The `.env` link: a run's worktree carries no production secrets from slice 15 on, so this slice's "Must still hold" keeps the link only for work outside a run.
- Build paths keep today's behaviour, stated under Part b: previews only on Explore privately, the whole pipeline on Build and run it, and the pipeline plus the first-deployment launch review on Build with care.
- The recipe line that marks proven preview data is `Previews keep their own data:` (defined in slice 13), and slice 20 reads the same line.
- The run controller is `implement/scripts/run.py` (slice 9).
