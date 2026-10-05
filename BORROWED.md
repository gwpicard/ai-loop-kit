# Borrowed code

Every file here was copied from the commit `fbdf054` of this repository, the last commit before AI Build Kit started to be removed. The originals stay in place until stage D deletes them. This is stage C1 of three. Stages C2 and C3 add rows below.

The source column gives a path inside that commit, written with the commit prefix. A verbatim row matches `git show fbdf054:<source> | cmp - <destination>`. An edited row says what changed.

## Copied files

| Destination | Source | Commit | Verbatim or edit | What it must shed later |
|---|---|---|---|---|
| `kit/scripts/gate.py` | `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/gate.py` | `fbdf054` | verbatim | Names `.agents/tools/` paths and carries the old product name in two lines. |
| `kit/scripts/ready-lint.py` | `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/ready-lint.py` | `fbdf054` | edited: Renamed the variable `l` to `ln` on two lines, because ruff refuses `l`. | Reads the old project layout and prose for the contract headings. |
| `kit/scripts/area-map.py` | `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/area-map.py` | `fbdf054` | verbatim | Carries the old product name in one line. |
| `kit/scripts/state-guard.sh` | `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/state-guard.sh` | `fbdf054` | verbatim | Names the hook path a founded project uses. |
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
| `kit/templates/blocked-commands.md` | `fbdf054:.agents/skills/setup-ai-build-kit/references/blocked-commands.md` | `fbdf054` | verbatim | Carries the old product name and names `.agents/tools/gate.py`; two rehearsals read its wording, so change both together. |
| `tests/lib/rule-shape.sh` | `fbdf054:.agents/tests/lib/rule-shape.sh` | `fbdf054` | verbatim | Nothing known. |
| `tests/lib/permission-matcher.py` | `fbdf054:.agents/tests/lib/permission-matcher.py` | `fbdf054` | verbatim | Nothing known. |
| `tests/run-all.sh` | `fbdf054:.agents/tests/run-all.sh` | `fbdf054` | edited: Folder root now `..`; the loop reads `tests/*.sh`; the help line names `tests/<name>.sh`; sets `PYTHONDONTWRITEBYTECODE=1`. The `mutate` and `run-all` copy exclusions are kept. | Nothing known. |
| `tests/rehearsal-runner.sh` | `fbdf054:.agents/tests/rehearsal-runner.sh` | `fbdf054` | edited: The throwaway tree is `$WORK/tests` (was `$WORK/.agents/tests`). | Nothing known. |
| `tests/stand-ins/fake-github/gh` | `fbdf054:.agents/tests/replay/fake-github/gh` | `fbdf054` | edited: Renamed the variable `l` to `lbl` on four lines, because ruff refuses `l`. | Comments call it the replay harness stand-in. |
| `tests/gate-script.sh` | `fbdf054:.agents/tests/gate-script.sh` | `fbdf054` | edited: Folder root now `..`; gate and stand-in paths point at `kit/scripts` and `tests/stand-ins`; the guards are found beside the gate; two failure messages reworded. | Carries the old product name in one line. |
| `tests/ready-lint-rehearsal.sh` | `fbdf054:.agents/tests/ready-lint-rehearsal.sh` | `fbdf054` | edited: Folder root now `..`; paths point at `kit/scripts` and `tests/stand-ins`. Removed two assertions that read Build Kit prose: that the lint's Test runner table matches `check-floor.md`, and that a design note lists the length limits. | Nothing known. |
| `tests/area-map-rehearsal.sh` | `fbdf054:.agents/tests/area-map-rehearsal.sh` | `fbdf054` | edited: Folder root now `..`; paths point at `kit/scripts` and `kit/templates`; one failure message reworded. | Carries the old product name in two lines. |
| `tests/frozen-bar-rehearsal.sh` | `fbdf054:.agents/tests/frozen-bar-rehearsal.sh` | `fbdf054` | edited: Folder root now `..`; paths point at `kit/scripts`, `kit/templates` and `tests/stand-ins`. | Nothing known. |
| `tests/bar-guard-rehearsal.sh` | `fbdf054:.agents/tests/bar-guard-rehearsal.sh` | `fbdf054` | edited: Folder root now `..`; the guard path is `kit/scripts`. | Nothing known. |
| `tests/state-guard.sh` | `fbdf054:.agents/tests/state-guard.sh` | `fbdf054` | edited: Folder root now `..`; paths point at `kit`, `tests/lib` and `tests/stand-ins`. Removed the variables and checks that read the old validator and this repository's own settings. | Reads `.agents/tools/gate.py` wording in `blocked-commands.md`. |
| `tests/co-change-rehearsal.sh` | `fbdf054:.agents/tests/co-change-rehearsal.sh` | `fbdf054` | edited: Folder root now `..`; the script path is `kit/scripts/co-change.sh`. | Nothing known. |
| `tests/test-strength-rehearsal.sh` | `fbdf054:.agents/tests/test-strength-rehearsal.sh` | `fbdf054` | edited: Folder root now `..`; paths point at `kit/scripts` and `tests/stand-ins`. Removed the lines that read `references/test-strength.md` and the report assertions built on it. | Nothing known. |
| `tests/fake-github.sh` | `fbdf054:.agents/tests/fake-github.sh` | `fbdf054` | edited: The stand-in path is `tests/stand-ins/fake-github/gh`. | Nothing known. |
| `tests/push-to-main-rules.sh` | `fbdf054:.agents/tests/push-to-main-rules.sh` | `fbdf054` | edited: Folder root now `..`; paths point at `kit/templates` and `tests/lib`. Removed the variables and rules that read the maintain skill and `WORKFLOW.md`. | Reads wording in `blocked-commands.md`. |
| `tests/merge-ask-rule.sh` | `fbdf054:.agents/tests/merge-ask-rule.sh` | `fbdf054` | edited: Folder root now `..`; paths point at `kit`. Removed the variables and rules that read skill prose, `WORKFLOW.md`, the compatibility page and this repository's own settings. | Reads wording in `blocked-commands.md`. |
| `tests/attribution-scrub.sh` | `fbdf054:.agents/tests/attribution-scrub.sh` | `fbdf054` | edited: Folder root now `..`; the closing check now asks that `tests/house-rules.sh` names no exemption for this file (it asked this of the old validator). | Nothing known. |

## New files, not borrowed

| Destination | What it is |
|---|---|
| `tests/house-rules.sh` | The number, attribution, stray-copy, shell-syntax and runnable-mode checks lifted from the old validator, with a self-test that plants each fault. |
| `.github/workflows/v1-checks.yml` | Runs `tests/run-all.sh` on manual dispatch only. |
| `BORROWED.md` | This file. |

## Deliberately not copied

| Source | Why |
|---|---|
| `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/plan-refresh.sh` and its rehearsals | The gate does not call it. Left to the archive tag. |
| `fbdf054:.agents/tests/trim-rehearsal.sh` | Not about borrowed code. |
| `fbdf054:docs/SOURCES.md` | Stays at `docs/SOURCES.md` and is pruned there later. |
| The replay harness under `fbdf054:.agents/tests/replay/` apart from the GitHub stand-in | Not borrowed. The host stand-ins arrive in stage C3. |
| `fbdf054:.agents/guard/blocked-commands.md` | The founded copy under `kit/templates/blocked-commands.md` is the one borrowed. |
| `codex-with-github.py` and `old-skill-pointers.py` | Not borrowed. |
| `fbdf054:.agents/skills/setup-ai-build-kit/templates/foundation/` files not listed above | Left for later stages or the archive tag. |

## Copies still carrying the old product name

These files contain the words "AI Build Kit" or the lower-case form with hyphens. Stage D's search for the old name leaves `kit/`, `tests/` and this file out for that reason.

- `kit/scripts/area-map.py`
- `kit/scripts/gate.py`
- `kit/templates/blocked-commands.md`
- `kit/templates/checks.yml`
- `tests/area-map-rehearsal.sh`
- `tests/gate-script.sh`
