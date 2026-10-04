# Slice 5: Every folder of a founded project belongs to a named area, and the project check says when one does not

Labels (today's set): enhancement, area:skills, ready-able once shaped. Release label for the PR: release-minor.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 2: Label model and gate script; slice 3: Contract v2 and the ready-gate lint.

## So that
A piece's `Boundary:` and `Reaches:` always name real places in the code, on every project, so a run can plan from them and a diff outside them can be caught.

## Done when
### Works
- A new foundation template, `templates/working-rules.md`, gives every founded project `docs/working-rules.md` with an `## Areas` section, where each area is one line `- <name>: <path>, <path>` with at most one indented `sensitive: <name>` line and at most one indented `boundary:` line. `docs/README.md`'s list names the file, and the founded `AGENTS.md` points at it. The masterplan's build-path section keeps its `Sensitive areas:` lines, which no longer carry `paths:` or `none:` lines. Check: new `.agents/tests/area-map.sh` (rule-shape, replacing `sensitive-area-map.sh`) requires the shape in `templates/working-rules.md`, the absence of `paths:` in `templates/masterplan.md`, and proves each rule load-bearing.
- A new foundation script, `area-map.py`, installed by the bootstrap step at `.agents/hooks/area-map.py` and read from `docs/working-rules.md`, has three actions: `check` (the map is true), `which <path>...` (prints the area each path belongs to, or `unclaimed`), and `areas` (prints every area name with its `sensitive:` name or `-`). Check: new `.agents/tests/area-map-rehearsal.sh` runs all three in a throwaway project and reads their output.
- `area-map.py check` turns red on every build path, not only Build with care, naming the folder: a tracked folder holding tracked files is unclaimed unless it, or a folder above it, is listed, or every tracked file and folder directly inside it is claimed in turn. Hidden top-level folders (such as `.github` and `.agents`) and tracked files at the root are exempt. Check: `area-map-rehearsal.sh` builds a project with `src/billing/` listed and `src/reports/` not, and reads `src/reports is a folder no area claims. Say which area it belongs to in the Areas section of docs/working-rules.md.`
- The check also turns red, naming the line, on a listed path that does not exist, a path listed under two areas, a `sensitive:` name with no matching line under `Sensitive areas:`, and a line under `Sensitive areas:` that no area points at. A nested listing (`src/` in one area, `src/billing/` in another) passes, and the more specific area wins in `which`. Check: `area-map-rehearsal.sh`, one case for each, with a passing control.
- An area written as `- <name>: none yet` passes the check, so a new project can name its areas before any code exists, and the first piece that creates the folder adds its path in the same save. Check: `area-map-rehearsal.sh`.
- The kit's own `checks.yml` runs `python3 .agents/hooks/area-map.py check` in a step named `Check the area map`, in place of `Check sensitive-area map`, and the step prints one line when it passes. Check: `area-map.sh` reads `templates/foundation/checks.yml`; `adopted-ci-rehearsal.sh` and `check-floor-rehearsal.sh` updated to the new step name.
- A founded project's own type check and linter stay green with `.agents/hooks/area-map.py` in place. Check: `.agents/tests/check-floor-rehearsal.sh`, extended so the founded Python and TypeScript projects carry the placed script and stay green.
- Founding writes the `## Areas` section of `docs/working-rules.md` on every build path, from the code where code exists and from the masterplan's own description where none does, reads each area and its home back in plain words ("Billing is the refund button, and it lives in the billing folder"), and runs `area-map.py check` before the first checkpoint. Check: `area-map.sh` reads the setup-ai-build-kit skill; `starter-rehearsal.sh` founds a throwaway project and finds `.agents/hooks/area-map.py` and a `docs/working-rules.md` whose `## Areas` section passes the check.
- The ready-gate lint refuses a piece whose `Boundary:` or `Reaches:` names an area `area-map.py areas` does not print, naming the area, and refuses a piece whose boundary or reach holds an area with a `sensitive:` line and no `Accepted:` line or done caution for that sensitive area. This replaces slice 3's reading of sensitive areas from the masterplan's build-path section. Check: the lint's own rehearsal from slice 3, extended with both cases, in `.agents/tests/area-map-rehearsal.sh`.
- section-builder's save step names the rule that a code move and its map change share one save, and its review step reads `area-map.py which` on the changed paths instead of reading the masterplan's sensitive-area paths by hand. Check: `area-map.sh` reads `section-builder/SKILL.md`.
- `/maintain` runs `area-map.py check` on every visit, on every build path, and on a red result asks which area each named folder belongs to, changing the map only after the answer. Check: `area-map.sh` reads `maintain/SKILL.md`.
- The documents this change touches each tell it, held by `area-map.sh`: WORKFLOW.md's "The build path" section (the map covers the whole project and exists on every path); `references/fit-check.md` (the sensitive area points into the map rather than carrying paths); the foundation `AGENTS.md` "Sensitive areas" section, renamed "Areas and sensitive areas"; `references/boundary-rules.md` (a boundary line sits under its area in `docs/working-rules.md`); `references/project-check.md` ("The kit's steps" names `Check the area map`); `references/masterplan-changes.md` and `section-builder/references/test-strength.md` (they read the map through `area-map.py which`); the ship skill's line that walks the map.
- Root `AGENTS.md` names `area-map.sh` and `area-map-rehearsal.sh` and no longer names `sensitive-area-map.sh`. Check: `validate-kit.sh` ("AGENTS.md names every maintainer check").

### When it is not the normal case
- A project with no `docs/working-rules.md`, or one with no `## Areas` section: `area-map.py check` fails with one line naming the missing file or section and the founding step that writes it. It never falls back to the masterplan's `paths:` lines, because AI Loop Kit carries no project founded before the map (decision 63). Check: `area-map-rehearsal.sh` runs it on a project with neither.
- No `python3` on the computer or the runner: the script exits 2 with one line naming Python 3 as the missing tool, never 0. Check: `area-map-rehearsal.sh` runs it with a PATH that has no `python3`, through the shim.
- A tracked folder the map cannot sensibly own, such as vendored code: it is listed under an area named for what it is (`- vendored libraries: vendor/`); there is no exempt list beyond hidden top-level folders and root files. Check: `area-map.sh` holds the sentence in `fit-check.md` that says so.
- A path written with a leading `./` or without a trailing slash: read the same as `src/billing/`. Check: `area-map-rehearsal.sh`.

## Masterplan change
Design note: "Reach and risk", the paragraph "The area map covers the whole project, not only the sensitive areas", and the ready-gate sentence "every area exists in the map" and "every sensitive area in the boundary or the reach has an acceptance". The note needs one added sentence under "Reach and risk": "The map lives in the Areas section of `docs/working-rules.md`, outside the masterplan; a sensitive area points into it by name."

## Not in this piece
- Working out a piece's reach, the co-change query and the pre-mortem question: slice 4: Shaping sub-states in /shape.
- The diff check that forces `review:person` when a change touches files outside its `Boundary:`: slice 6: Frozen-bar enforcement, which uses `area-map.py which`.
- Planning a run's waves from overlapping boundaries: slice 9: Run controller.
- Moving the sensitive areas, the accepted cautions and the other build and review rules into `docs/working-rules.md` beside the map: slice 18: Compact masterplan and behaviour deltas.
- Any move of a map for a project founded with AI Build Kit: none, by decision 63.

## Decided
- The map lives in its own file, `docs/working-rules.md`, in an `## Areas` section, rather than in the masterplan, because slice 18 makes the masterplan a 500-word overview that a whole-project map does not fit, and putting the map in its final home now means no later slice moves it. The file is the one slice 18 names for build and review rules. (Decision 40.)
- The map exists on every build path, because a boundary has to name real paths on every piece the ready gate passes, whatever the path. Today's map exists only on Build with care. (Decision 40.)
- The map behaves the same on all three build paths: Explore privately, Build and run it and Build with care each get the map, the check and the lint's area rule. Only Build with care names sensitive areas today, so only there does a `sensitive:` line and its acceptance rule come into play, as today.
- Sensitive areas keep their caution and acceptance lines in the masterplan's build-path section until slice 18 moves them beside the map; an area in the map marks itself sensitive with `sensitive: <name>`. This keeps the risk notice and `Accepted:` lines, which several rehearsals guard, where they are.
- Claiming works on folders, top down, with files allowed as paths, and no exempt list beyond hidden top-level folders and root files, because an exempt list is where an unclaimed folder hides.
- One script with three actions, rather than a shell check plus a separate reader, because the lint (slice 3), the boundary diff check (slice 6) and the run planner (slice 9) all need the same reading of the map. It is Python, like `fold-changes.py`, because the folder-claiming rule is awkward in POSIX shell.
- The step's failure message says what to do next, in the house rule for scripts: quiet on a pass, one line, and on a failure the fix.

## Data
A founded project gains `docs/working-rules.md` with its `## Areas` section; founding and the builder write it, `/maintain` corrects it on a yes. A founded project gains `.agents/hooks/area-map.py`, written by the bootstrap step and refreshed by `/maintain`. The foundation no longer carries `check-sensitive-areas.sh`. No project founded with AI Build Kit is moved (decision 63). No limit beyond one line per area.

## Leaves the tool
Nothing new leaves the tool, because the check runs in the project's existing CI job on GitHub, which already runs the sensitive-area step, and the map is in a file already pushed with the project.

## Must still hold
- The `Accepted:` line and the risk notice stay in the build-path section and keep their wording: `acceptance-is-earned.sh`, `notice-is-owed-by-the-refusal.sh`, `named-reviewer-is-a-person.sh`.
- A boundary rule is offered, never imposed, and is green on the day it is added: `boundary-rules.sh`, `boundary-rules-rehearsal.sh` (updated to read the boundary line from `## Areas`).
- The founded AGENTS.md stays within its ceiling and its sections stay 12 lines or fewer: `standing-instructions.sh`, `agent-first-records.sh`.
- A founded project's own type check and linter stay green with the kit's copied scripts in it: `check-floor-rehearsal.sh`.
- An adopted project's own CI stays its project check, and the kit's steps are added only on a yes: `adopted-ci.sh`, `adopted-ci-rehearsal.sh`.
- No product is named outside a recipe: `hosting-request.sh`.
- No issue number in a tracked file, and every rehearsal named in root AGENTS.md: `validate-kit.sh`.
- Pointers name a skill and a path inside it, never a fixed project folder: `plan-helper-routes.sh`.

## Relies on
- `.agents/skills/setup-ai-build-kit/templates/foundation/check-sensitive-areas.sh`, `checks.yml`, `templates/masterplan.md`, `scripts/bootstrap-project.sh` (lines installing the hook), `references/fit-check.md`, `references/boundary-rules.md`, `references/project-check.md`: all on main today.
- `.agents/tests/sensitive-area-map.sh` and `.agents/tests/lib/rule-shape.sh`: on main today.
- The ready-gate lint and the `Boundary:`/`Reaches:` fields: produced by slice 3: Contract v2 and the ready-gate lint.
- The gate script's refusal format (names the next allowed action): produced by slice 2: Label model and gate script.

## Reach and risk
Boundary: the setup-ai-build-kit skill (masterplan and working-rules templates, foundation check and workflow, bootstrap, fit check, boundary rules, project check record), section-builder (review and save steps, test-strength reference), maintain (the monthly map step), ship (the map walk), WORKFLOW.md.
Reaches: founding and the installation routes, guarded by `starter-rehearsal.sh`, `claude-plugin.sh`, `agent-plugin.sh`, `plan-helper-routes.sh`; the risk notice and acceptance, guarded by `acceptance-is-earned.sh`; the boundary rules, guarded by `boundary-rules-rehearsal.sh`; adopted CI, guarded by `adopted-ci-rehearsal.sh`; the check floor, guarded by `check-floor-rehearsal.sh`; replay preparation that writes masterplans, guarded by `gated-turns.sh` (`turn-gate.sh` mentions the map).
If it breaks: a founded project's check goes red on every pull request with a message about a folder, and the person sees it on GitHub. Undone by reverting the slice's pull request.
Depends on: 2, 3.
Loop module: build, because every promise here is a script result or a written rule a rehearsal can hold.
Crew: default for the module.

## Under the hood
- Add `templates/foundation/area-map.py` and `templates/working-rules.md`; remove `check-sensitive-areas.sh` from the foundation. Update `bootstrap-project.sh` to install the script and write the file.
- Rewrite the map paragraphs of `references/fit-check.md` and the setup-ai-build-kit SKILL.md step that writes the map; move `paths:`, `none:` and `boundary:` out of the masterplan's build-path example into the `## Areas` example in `templates/working-rules.md`, and add the file to `docs/README.md`'s list.
- Point section-builder step 7, `references/test-strength.md`, `references/masterplan-changes.md`, the ship skill and maintain step 7 at `area-map.py which` or `check`.
- Extend slice 3's lint with the two area rules.
- Rename `sensitive-area-map.sh` to `area-map.sh` and widen it; add `area-map-rehearsal.sh`. Expected to change: `boundary-rules.sh`, `boundary-rules-rehearsal.sh`, `adopted-ci.sh`, `adopted-ci-rehearsal.sh`, `check-floor-rehearsal.sh`, `founding-carries-on.sh`, `test-strength.sh`, `starter-rehearsal.sh`, and `replay/turn-gate.sh`, each because it names the old step, file or map lines.
- Nothing is reused from the overnight batch branch.
- Kit rules: answer the five questions in PHILOSOPHY.md in the pull request; no new borrowed idea for SOURCES.md; rebuild adapters with `build-adapters.sh`; run `validate-kit.sh`; load the Humanizer before saving WORKFLOW.md and skill prose; no issue numbers.

## Evidence
Rule-shape rehearsal with load-bearing checks for every written rule (`area-map.sh`), and a script rehearsal in throwaway Git projects (`area-map-rehearsal.sh`) covering each red case, its passing control and the missing-file case. One guided check: found a throwaway project from the kit, read the area read-back, then add a folder and see the check name it.

## Size
Two sittings: one for the script, its rehearsal and the foundation wiring; one for the prose across fit check, founding, builder, maintain and WORKFLOW.md, with the rehearsals that read them.

## Consistency notes
- The ready-gate lint is slice 3's. The rule that every area under `Boundary:` and `Reaches:` exists in the map is this slice's, because the map is built here; it replaces slice 3's reading of sensitive areas from the masterplan.
- The whole-project area map lives in the `## Areas` section of `docs/working-rules.md` from this slice on, the file slice 18 names for build and review rules, so the compact masterplan never has to hold or move it. Slices 6, 9 and 18 read the map there, through `area-map.py`.
- The build paths behave as today. The map, the check and the lint's area rule apply on all three; sensitive areas and their acceptance exist only where the masterplan names them, which is Build with care.
- `area-map.py` is copied into a founded project, because the project check runs it on GitHub's runner, so this slice adds a `check-floor-rehearsal.sh` line holding the project's own lint green with it.
- No fallback to the old map format and no shim for an older `checks.yml`, because AI Loop Kit carries no project founded with AI Build Kit (decision 63).
