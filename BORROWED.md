# Borrowed code

Every file here was copied from the commit `fbdf054` of this repository, the last commit before AI Build Kit started to be removed. The originals stay in place until stage D deletes them. Stages C1, C2 and C3 are in.

The source column gives a path inside that commit, written with the commit prefix. A verbatim row matches `git show fbdf054:<source> | cmp - <destination>`. An edited row says what changed.

## Copied files

| Destination | Source | Commit | Verbatim or edit | What it must shed later |
|---|---|---|---|---|
| `kit/scripts/gate.py` | `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/gate.py` | `fbdf054` | adapted: Rewritten as a thin command line over `loop/states.py`, `loop/moves.py` and `loop/github.py`. It shed the old label list, the sub-state markers, the checkpoint assumptions, the always-person review stub, the `.agents/tools/` paths, the contract-hash comments, the evidence and breakage commands, and the old product name. `section()` moved to `loop/spec.py` and `chain_of()` to `loop/evidence.py`. | Nothing known. |
| `kit/scripts/ready-lint.py` | `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/ready-lint.py` | `fbdf054` | edited: Renamed the variable `l` to `ln` on two lines, because ruff refuses `l`. | Reads the old project layout and prose for the contract headings. |
| `kit/scripts/area-map.py` | `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/area-map.py` | `fbdf054` | verbatim | Carries the old product name in one line. |
| `kit/scripts/bar-guard.sh` | `fbdf054:.agents/skills/section-builder/scripts/bar-guard.sh` | `fbdf054` | verbatim | Names old project paths in its guarded list. |
| `kit/scripts/test-guard.sh` | `fbdf054:.agents/skills/section-builder/scripts/test-guard.sh` | `fbdf054` | verbatim | Nothing known. |
| `kit/scripts/co-change.sh` | `fbdf054:.agents/skills/section-builder/scripts/co-change.sh` | `fbdf054` | verbatim | Nothing known. |
| `kit/scripts/merge-ask-rules.py` | `fbdf054:.agents/skills/setup-ai-build-kit/scripts/merge-ask-rules.py` | `fbdf054` | verbatim | Nothing known. |
| `kit/templates/claude-settings.json` | `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/claude-settings.json` | `fbdf054` | verbatim | Wires hook paths of the old project layout. |
| `kit/templates/merge-ask-rules.json` | `fbdf054:.agents/skills/setup-ai-build-kit/templates/merge-ask-rules.json` | `fbdf054` | verbatim | Nothing known. |
| `kit/templates/working-rules.md` | `fbdf054:.agents/skills/setup-ai-build-kit/templates/working-rules.md` | `fbdf054` | verbatim | Old wording for the area map section. |
| `kit/templates/piece-issue.yml` | `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/piece-issue.yml` | `fbdf054` | verbatim | Old field wording; v1 may replace the form. |
| `kit/templates/checks.yml` | `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/checks.yml` | `fbdf054` | verbatim | Carries the old product name in one line. |
| `kit/templates/gitignore` | `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/gitignore` | `fbdf054` | verbatim | Nothing known. |
| `kit/templates/blocked-commands.md` | `fbdf054:.agents/skills/setup-ai-build-kit/references/blocked-commands.md` | `fbdf054` | adapted: The old product name is gone. The gate path is `kit/scripts/gate.py` and the hook is `kit/hooks/guard.py`. The references to two old skills are gone. Every heading and command list that the two rule tests read is kept. | Two rehearsals read its wording, so change both together. |
| `tests/lib/rule-shape.sh` | `fbdf054:.agents/tests/lib/rule-shape.sh` | `fbdf054` | verbatim | Nothing known. |
| `tests/lib/permission-matcher.py` | `fbdf054:.agents/tests/lib/permission-matcher.py` | `fbdf054` | verbatim | Nothing known. |
| `tests/run-all.sh` | `fbdf054:.agents/tests/run-all.sh` | `fbdf054` | edited: Folder root now `..`; the loop reads `tests/*.sh`; the help line names `tests/<name>.sh`; sets `PYTHONDONTWRITEBYTECODE=1`. The `mutate` and `run-all` copy exclusions are kept. | Nothing known. |
| `tests/rehearsal-runner.sh` | `fbdf054:.agents/tests/rehearsal-runner.sh` | `fbdf054` | edited: The throwaway tree is `$WORK/tests` (was `$WORK/.agents/tests`). | Nothing known. |
| `tests/stand-ins/fake-github/gh` | `fbdf054:.agents/tests/replay/fake-github/gh` | `fbdf054` | edited: Renamed the variable `l` to `lbl` on four lines, because ruff refuses `l`. Added the App's token exchange (`app/installations/<id>/access_tokens`, which checks the JWT's RS256 signature with openssl against `FAKE_APP_KEY`), and a call that carries a stand-in App token acts as the App's bot account. | Comments call it the replay harness stand-in. |
| `tests/ready-lint-rehearsal.sh` | `fbdf054:.agents/tests/ready-lint-rehearsal.sh` | `fbdf054` | edited: Folder root now `..`; paths point at `kit/scripts` and `tests/stand-ins`. Removed two assertions that read Build Kit prose: that the lint's Test runner table matches `check-floor.md`, and that a design note lists the length limits. | Nothing known. |
| `tests/area-map-rehearsal.sh` | `fbdf054:.agents/tests/area-map-rehearsal.sh` | `fbdf054` | edited: Folder root now `..`; paths point at `kit/scripts` and `kit/templates`; one failure message reworded. | Carries the old product name in two lines. |
| `tests/bar-guard-rehearsal.sh` | `fbdf054:.agents/tests/bar-guard-rehearsal.sh` | `fbdf054` | edited: Folder root now `..`; the guard path is `kit/scripts`. | Nothing known. |
| `tests/co-change-rehearsal.sh` | `fbdf054:.agents/tests/co-change-rehearsal.sh` | `fbdf054` | edited: Folder root now `..`; the script path is `kit/scripts/co-change.sh`. | Nothing known. |
| `tests/fake-github.sh` | `fbdf054:.agents/tests/fake-github.sh` | `fbdf054` | edited: The stand-in path is `tests/stand-ins/fake-github/gh`. One comment is reworded, "the third issue" for "issue 3", as a tidy reword. | Nothing known. |
| `tests/push-to-main-rules.sh` | `fbdf054:.agents/tests/push-to-main-rules.sh` | `fbdf054` | edited: Folder root now `..`; paths point at `kit/templates` and `tests/lib`. Removed the variables and rules that read the maintain skill and `WORKFLOW.md`. | Reads wording in `blocked-commands.md`. |
| `tests/merge-ask-rule.sh` | `fbdf054:.agents/tests/merge-ask-rule.sh` | `fbdf054` | edited: Folder root now `..`; paths point at `kit`. Removed the variables and rules that read skill prose, `WORKFLOW.md`, the compatibility page and this repository's own settings. | Reads wording in `blocked-commands.md`. |
| `tests/attribution-scrub.sh` | `fbdf054:.agents/tests/attribution-scrub.sh` | `fbdf054` | edited: Folder root now `..`; the closing check now asks that `tests/house-rules.sh` names no exemption for this file (it asked this of the old validator). | Nothing known. |
| `kit/scripts/worktree.sh` | `fbdf054:.agents/skills/implement/scripts/worktree.sh` | `fbdf054` | verbatim | Carries the old product name in two lines. |
| `kit/scripts/bring-up-to-date.sh` | `fbdf054:.agents/skills/section-builder/scripts/bring-up-to-date.sh` | `fbdf054` | edited: The fold script is found beside it (`$HERE/fold-changes.py`), because the scripts now sit in one folder. It was found under a sibling skill folder. | Its error message still says the sync skill's scripts folder. |
| `kit/scripts/fold-changes.py` | `fbdf054:.agents/skills/sync/scripts/fold-changes.py` | `fbdf054` | verbatim | Nothing known. |
| `kit/scripts/document-claims.py` | `fbdf054:.agents/skills/sync/scripts/document-claims.py` | `fbdf054` | verbatim | Nothing known. |
| `kit/scripts/document-bloat.py` | `fbdf054:.agents/skills/maintain/scripts/document-bloat.py` | `fbdf054` | verbatim | Nothing known. |
| `kit/scripts/check-tooling.sh` | `fbdf054:.agents/skills/setup-ai-build-kit/scripts/check-tooling.sh` | `fbdf054` | verbatim | Carries the old product name in one line. |
| `kit/scripts/session-start.sh` | `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/session-start.sh` | `fbdf054` | verbatim | Carries the old product name in one line, reads the old check-up file and the `AI_BUILD_KIT_TODAY` variable, and stays silent in a folder with `release-manifest.txt`. |
| `kit/scripts/bootstrap-project.sh` | `fbdf054:.agents/skills/setup-ai-build-kit/scripts/bootstrap-project.sh` | `fbdf054` | verbatim; no rehearsal drives it here | Untested in this place. It finds the guards and templates by paths under the old skill folders, so it cannot run from `kit/scripts` until those paths change. Carries the old product name in many lines. |
| `kit/scripts/place-plan-helper.sh` | `fbdf054:.agents/skills/setup-ai-build-kit/scripts/place-plan-helper.sh` | `fbdf054` | verbatim; no rehearsal drives it here | Untested in this place. It names the guards by paths under the old skill folders. Carries the old product name in one line. |
| `tests/fixtures/CHANGELOG.md` | `fbdf054:.agents/skills/setup-ai-build-kit/templates/CHANGELOG.md` | `fbdf054` | verbatim; a test fixture only, not a kit template | Nothing known. |
| `tests/kit-owns-worktrees-rehearsal.sh` | `fbdf054:.agents/tests/kit-owns-worktrees-rehearsal.sh` | `fbdf054` | edited: Folder root now `..`; the script and the ignore template are found under `kit`. Removed the section "Walk-through pictures go to the main folder", which ran a lookup taken from the section-builder skill text. | Carries the old product name in one line. |
| `tests/fold-at-merge-rehearsal.sh` | `fbdf054:.agents/tests/fold-at-merge-rehearsal.sh` | `fbdf054` | edited: Folder root now `..`; the scripts are found under `kit/scripts` and the changelog under `tests/fixtures`. The helper is loaded from `tests/lib/rule-shape.sh`. | Nothing known. |
| `tests/recheck-before-merge-rehearsal.sh` | `fbdf054:.agents/tests/recheck-before-merge-rehearsal.sh` | `fbdf054` | edited: Folder root now `..`; the script is found under `kit/scripts`. The helper is loaded from `tests/lib/rule-shape.sh`. | Nothing known. |
| `tests/check-tooling.sh` | `fbdf054:.agents/tests/check-tooling.sh` | `fbdf054` | edited: The root is now the folder above the tests (it was `.agents`); the checker is found under `kit/scripts`; the recipe lookup reads `kit/recipes`. The fallback to `tests/recipes-awaiting-run` is gone. A recipe missing from `kit/recipes` is a failure again (stage C2 had skipped it with a note, until the recipes arrived). | Carries the old product name in seven lines. |
| `tests/session-start.sh` | `fbdf054:.agents/tests/session-start.sh` | `fbdf054` | edited: Rewritten to drive the hook directly. Folder root now `..`; the hook under test is `kit/scripts/session-start.sh`. Removed the release build, the checks on this repository's own settings, and the sections on the released starter and the installer route. The founded project is written inline (a masterplan line and the three check-up lines). The cadence, the 20-changes rule and the silent cases are kept. | Carries the old product name in twelve lines, mostly the check-up file name and the date variable. |
| `tests/document-read-rehearsal.sh` | `fbdf054:.agents/tests/document-read-rehearsal.sh` | `fbdf054` | edited: Folder root now `..`; the script is found under `kit/scripts`. Its throwaway project keeps its own `WORKFLOW.md`, which is a fixture. | Nothing known. |
| `tests/document-bloat-rehearsal.sh` | `fbdf054:.agents/tests/document-bloat-rehearsal.sh` | `fbdf054` | edited: Folder root now `..`; the script is found under `kit/scripts`. Its throwaway project keeps its own `WORKFLOW.md`, which is a fixture. | Nothing known. |
| `kit/recipes/nextjs-supabase-on-vercel.md` | `fbdf054:.agents/skills/ship/recipes/nextjs-supabase-on-vercel.md` | `fbdf054` | verbatim | Nothing known. |
| `kit/recipes/nextjs-supabase-on-coolify.md` | `fbdf054:.agents/skills/ship/recipes/nextjs-supabase-on-coolify.md` | `fbdf054` | verbatim | Nothing known. |
| `kit/recipes/parts/nextjs-container.md` | `fbdf054:.agents/skills/ship/recipes/parts/nextjs-container.md` | `fbdf054` | verbatim | Nothing known. |
| `kit/recipes/parts/supabase-backup.md` | `fbdf054:.agents/skills/ship/recipes/parts/supabase-backup.md` | `fbdf054` | verbatim | Nothing known. |
| `kit/recipes/parts/supabase-restore.md` | `fbdf054:.agents/skills/ship/recipes/parts/supabase-restore.md` | `fbdf054` | verbatim | Nothing known. |
| `kit/recipes/parts/supabase-settings.md` | `fbdf054:.agents/skills/ship/recipes/parts/supabase-settings.md` | `fbdf054` | verbatim | Nothing known. |
| `kit/templates/recipe.md` | `fbdf054:.agents/skills/ship/templates/recipe.md` | `fbdf054` | verbatim | Nothing known. |
| `kit/templates/recipe-format.md` | `fbdf054:.agents/skills/ship/references/recipe-format.md` | `fbdf054` | verbatim; the format sits with the templates, not in `kit/recipes`, which holds recipes and parts only | Names the old `ship/recipes` home and the old skill layout in its rules, which `tests/recipes.sh` reads, so change both together. |
| `kit/scripts/check-recipes.sh` | `fbdf054:.agents/tools/check-recipes.sh` | `fbdf054` | verbatim | A comment names the old path of the format file. |
| `tests/stand-ins/fake-host/_common.sh` | `fbdf054:.agents/tests/replay/fake-host/_common.sh` | `fbdf054` | verbatim | Nothing known. |
| `tests/stand-ins/fake-host/curl` | `fbdf054:.agents/tests/replay/fake-host/curl` | `fbdf054` | verbatim | Nothing known. |
| `tests/stand-ins/fake-host/docker` | `fbdf054:.agents/tests/replay/fake-host/docker` | `fbdf054` | verbatim | Nothing known. |
| `tests/stand-ins/fake-host/psql` | `fbdf054:.agents/tests/replay/fake-host/psql` | `fbdf054` | verbatim | Nothing known. |
| `tests/stand-ins/fake-host/supabase` | `fbdf054:.agents/tests/replay/fake-host/supabase` | `fbdf054` | verbatim | Nothing known. |
| `tests/stand-ins/fake-host/vercel` | `fbdf054:.agents/tests/replay/fake-host/vercel` | `fbdf054` | verbatim | Nothing known. |
| `tests/stand-ins/prepare/live-on-vercel.sh` | `fbdf054:.agents/tests/replay/prepare/live-on-vercel.sh` | `fbdf054` | verbatim; a fixture builder, not the harness | Looks for the old placeholder sentence in `AGENTS.md`, needs the project to hold the recipe under `.agents/skills/ship/recipes/`, and carries the old product name in three lines. |
| `tests/stand-ins/prepare/live-on-vercel.after-commit.sh` | `fbdf054:.agents/tests/replay/prepare/live-on-vercel.after-commit.sh` | `fbdf054` | verbatim; a fixture builder, not the harness | Looks for the old placeholder sentence in `AGENTS.md`, needs the project to hold the recipe under `.agents/skills/ship/recipes/`, and carries the old product name in three lines. |
| `tests/lib/recipe-rehearsal.sh` | `fbdf054:.agents/tests/lib/recipe-rehearsal.sh` | `fbdf054` | edited: `RR_CHECKER`, `RR_MENU`, `RR_PARTS` and `RR_WAITING` point at `kit/scripts`, `kit/recipes`, `kit/recipes/parts` and `tests/recipes-awaiting-run` (a folder nobody creates here). | A comment still names the old waiting folder. |
| `tests/recipes.sh` | `fbdf054:.agents/tests/recipes.sh` | `fbdf054` | edited: Folder root now `..`; paths point at `kit/templates` and `kit/scripts`. Removed the variables and checks that read the old validator, `docs/PHILOSOPHY.md`, `docs/MAINTAINING.md` and `docs/SOURCES.md`. Added a closing loop that runs `check-recipes.sh` over every recipe and its rehearsal, every part and the blank, which the old validator used to do. | Its rules on the format read the old `ship/recipes` wording. |
| `tests/recipe-nextjs-supabase-on-vercel.sh` | `fbdf054:.agents/tests/recipe-nextjs-supabase-on-vercel.sh` | `fbdf054` | edited: Folder root now `..`; the helper libraries and the recipe are found under `tests/lib` and `kit/recipes`. | Nothing known. |
| `tests/recipe-nextjs-supabase-on-coolify.sh` | `fbdf054:.agents/tests/recipe-nextjs-supabase-on-coolify.sh` | `fbdf054` | edited: Folder root now `..`; the helper libraries and the recipe are found under `tests/lib` and `kit/recipes`. | Nothing known. |
| `tests/fake-host.sh` | `fbdf054:.agents/tests/fake-host.sh` | `fbdf054` | edited: Folder root now `..`; the stand-ins are found under `tests/stand-ins`; the throwaway project takes `AGENTS.md` from `tests/fixtures/AGENTS.md` and the recipe from `kit/recipes`. The project still holds the recipe under `.agents/skills/ship/recipes/`, because the fixture builder insists on it. | Carries the old project layout in two lines. |

## Retired

| File | Replaced by | Why |
|---|---|---|
| `kit/scripts/state-guard.sh` and its source `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/state-guard.sh` | `kit/hooks/guard.py` | It matched the text of a command. The new hook reads the command, so `git -C . push origin main` and `sh -c` forms are caught. |
| `tests/state-guard.sh` and its source `fbdf054:.agents/tests/state-guard.sh` | `tests/unit/test_guard.py` and `tests/guard-hook.sh` | They tested the old hook and its settings wiring. The unit test feeds the new hook every spelling in `blocked-commands.md`. The shell test runs it as Claude Code does. |
| `tests/gate-script.sh` and its source `fbdf054:.agents/tests/gate-script.sh` | `tests/unit/test_states.py`, `tests/unit/test_moves.py`, `tests/unit/test_github.py` and `tests/gate.sh` | It drove the old gate's labels, sub-states and commands, which the rewritten gate no longer has. |
| `tests/frozen-bar-rehearsal.sh` and its source `fbdf054:.agents/tests/frozen-bar-rehearsal.sh` | The attempt gate's own tests, in a later piece, which carries its cases forward from Git history | It drove the old gate's `evidence` command, which the rewritten gate no longer has. |
| `tests/test-strength-rehearsal.sh` and its source `fbdf054:.agents/tests/test-strength-rehearsal.sh` | The attempt gate's own tests, in a later piece, which carries its cases forward from Git history | It drove the old gate's `evidence --breakage` command, which the rewritten gate no longer has. |

## New files, not borrowed

| Destination | What it is |
|---|---|
| `tests/house-rules.sh` | The number, attribution, stray-copy, shell-syntax and runnable-mode checks lifted from the old validator, with a self-test that plants each fault. |
| `.github/workflows/v1-checks.yml` | Runs `tests/run-all.sh` on manual dispatch only. Its job carries the repository gate the old release check demands, which names the old repository as well. It carries the old product name in that one line, until stage D removes the old check. |
| `tests/fixtures/AGENTS.md` | A few lines for the fake-host rehearsal. It holds the placeholder sentence under a stack heading, which the Vercel fixture builder looks for. It is not a copy of the old template. |
| `BORROWED.md` | This file. |

## Deliberately not copied

| Source | Why |
|---|---|
| `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/plan-refresh.sh` and its rehearsals | The gate does not call it. Left to the archive tag. |
| `fbdf054:.agents/tests/trim-rehearsal.sh` | Not about borrowed code. |
| `fbdf054:docs/SOURCES.md` | Stays at `docs/SOURCES.md` and is pruned there later. |
| The replay harness under `fbdf054:.agents/tests/replay/` apart from the GitHub stand-in, the host stand-ins and the two Vercel fixture builders | Not borrowed. |
| `fbdf054:.agents/tests/recipes-awaiting-run/parts` | A symbolic link to nothing the rehearsals need here. No recipe is waiting. |
| `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/AGENTS.md` | Deleted from the templates. `tests/fixtures/AGENTS.md` stands in for it. |
| `fbdf054:.agents/guard/blocked-commands.md` | The founded copy under `kit/templates/blocked-commands.md` is the one borrowed. |
| `codex-with-github.py` and `old-skill-pointers.py` | Not borrowed. |
| `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/` files not listed above | Left for later stages or the archive tag. |

## Copies still carrying the old product name

These files contain the words "AI Build Kit" or the lower-case form with hyphens. Stage D's search for the old name leaves `kit/`, `tests/` and this file out for that reason.

- `kit/scripts/area-map.py`
- `kit/scripts/bootstrap-project.sh`
- `kit/scripts/check-tooling.sh`
- `kit/scripts/place-plan-helper.sh`
- `kit/scripts/session-start.sh`
- `kit/scripts/worktree.sh`
- `kit/templates/checks.yml`
- `tests/area-map-rehearsal.sh`
- `tests/check-tooling.sh`
- `tests/kit-owns-worktrees-rehearsal.sh`
- `tests/session-start.sh`
- `tests/fixtures/AGENTS.md`
- `tests/stand-ins/prepare/live-on-vercel.sh`
- `tests/stand-ins/prepare/live-on-vercel.after-commit.sh`
- `.github/workflows/v1-checks.yml` (stage D1 removes it with the old check)
