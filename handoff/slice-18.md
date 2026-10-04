# Slice 18: A project keeps a short masterplan that orients, with the detailed rules in documents each piece updates when it merges

Labels (today's set): enhancement, area:skills, ready-able once shaped. Release label for the PR: release-major, since a founded project's record format changes.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 3: Contract v2 and the ready-gate lint; slice 5: Area map for the whole project, kept by the project check; slice 9: Run controller; slice 14: /deploy replacing /ship; slice 17: /maintain absorbs /sync.

## So that
A returning person or agent reads a masterplan of at most 500 words to understand the tool, finds every detailed rule in one owning document, and never sees two pieces conflict over the records, because each piece's change to current behaviour is applied when it merges rather than edited on its branch.

## Done when

### Part a: the compact format for a new founding

#### Works
- Founding writes `masterplan.md` opening with the marker `<!-- project-records:v1 -->` on its first line, followed by a short header, a brief architecture overview, summaries of the shared rules each with a link to its owning document, and links to the records. It holds no placeholder, no build-path field, no task history and no `Trued against:` line. Check: `.agents/tests/starter-rehearsal.sh` founds a sample project and reads the result; new `.agents/tests/project-records.sh` asserts each absence.
- The masterplan counts at most 500 visible words, every section included. Comments, link destinations, reference-style link definitions and diagram fences' markup are not words; link text and headings are. One counter is used everywhere: the founded project check's step "Check the masterplan's length", written inline in `checks.yml` like the AGENTS.md ceiling step, and the installed skill's `records.py count`, which `project-records.sh` proves give the same number on twelve fixtures, including `[text][ref]` links and a `[ref]: url` line. Check: `.agents/tests/project-records.sh`: 500 passes, 501 fails with a message naming `/maintain`, with and without a final newline.
- Detailed current intent lives in `docs/<concept>.md` files listed with what each owns in `docs/README.md`: permissions, data and its origins, connections and their picture, how the tool is used, what correct looks like, failure behaviour, settled terms, out of scope. Build and review rules live in `docs/working-rules.md`, beside the area map slice 5 put there: sensitive areas, accepted cautions (`Accepted:` lines), recheck triggers and any team review rule, word for word. Operations live in `docs/operations.md`: `Goes live:`, `Sample data:`, secret locations, owners, alerts, backup, the hosting request. Check: `.agents/tests/project-records.sh` founds the sample product and finds each fact in exactly one file; a one-sentence orientation in the masterplan names the owning document of the sample's permission rule.
- Only files `docs/README.md` lists count as records. Any other Markdown in the project (a skill library's files, the product's own content) is never read, moved or counted as a record. Check: `.agents/tests/project-records.sh` with a fixture project holding twenty unlisted `.md` files.
- The sensitive areas and their caution and `Accepted:` lines move from the masterplan's build-path section into `docs/working-rules.md`, beside the `## Areas` map that has lived there since slice 5, and `area-map.py check` matches each `sensitive:` name against them there. Check: slice 5's `area-map-rehearsal.sh`, its sensitive-area cases moved to the new home; `.agents/tests/acceptance-is-earned.sh` reads the `Accepted:` line through `records.py`.
- Every script that reads a field reads it through the installed skill's `records.py field <name>`, which picks the owning file from the marker: `merge-ask-rules.py` and `section-builder/references/merge.md` (`Goes live:`), the secret-location reads and the hosting request (`/deploy`), and the acceptance read. Check: `.agents/tests/project-records.sh` runs each reader on a founded fixture; `.agents/tests/merge-ask-rule.sh`, `.agents/tests/not-hosted.sh`, `.agents/tests/secret-location.sh`, `.agents/tests/hosting-request.sh` pass on it.

#### When it is not the normal case
- A masterplan with no marker, or a marker that is unknown, malformed or repeated, or a field found twice: `records.py` stops with a record gap naming the file and line, and never guesses a route. There is no earlier format to fall back to, because AI Loop Kit carries no project founded with AI Build Kit (decision 63). Check: `.agents/tests/project-records.sh` with six broken fixtures, the missing marker among them, and a byte-for-byte comparison showing no reader rewrote any of them.
- A founding interview's answers outgrow 500 words: detail moves to its owning document before the first save, and every decision stays. Check: `.agents/tests/coverage-read.sh` (every promise still has an owner) on a founding fixture with 900 words of answers.

### Part b: behaviour deltas applied at the merge

#### Works
- The contract field that carries a piece's record change (today `## Masterplan change`) becomes `## Behaviour change`: one or more entries of the form `ADDED`, `MODIFIED` or `REMOVED`, the owning document, the rule's heading, and the rule's text. "Nothing" stays allowed. The ready-gate lint from slice 3 checks each entry names a listed document and an existing heading for `MODIFIED` and `REMOVED`. Check: slice 3's lint rehearsal, extended with three good and four bad entries; `.agents/tests/piece-contract.sh`.
- A piece's branch never edits a record file. The deltas are applied by `section-builder/scripts/apply-behaviour.py`, called by `bring-up-to-date.sh` in the same step as the changelog fold, one piece at a time, on the integration branch or on a run of one's branch just before it merges. Check: new `.agents/tests/behaviour-deltas-rehearsal.sh`: two pieces that change the same document merge one after the other with no conflict and both rules present, while a control that edits the document on both branches conflicts.
- Applying is repeatable: an `ADDED` rule already present with the same text, a `MODIFIED` rule already reading the new text, and a `REMOVED` rule already gone are skipped, so a second run changes nothing and a superseded rule never comes back. Check: `.agents/tests/behaviour-deltas-rehearsal.sh` runs the step twice and after a later piece removed a rule.
- After applying, the masterplan is counted; an overview that would pass 500 words fails the step with the count. The overview changes only through an entry that names `masterplan.md`. Check: `.agents/tests/behaviour-deltas-rehearsal.sh`.
- The `Trued against:` stamp is gone. `/maintain`'s putting-the-records-right section writes `records-review|<full commit>|complete` in `.ai-build-kit-maintenance` only after a complete review of that saved commit, and the monthly read counts landed changes since it. No build, merge or founding moves it. Check: `.agents/tests/masterplan-changes.sh`, rewritten for the checkpoint; `.agents/tests/project-records.sh` proves a merge leaves the line unchanged and an interrupted review writes nothing.

#### When it is not the normal case
- A `MODIFIED` or `REMOVED` entry names a heading another piece already changed or removed: the step stops, nothing is applied for that piece, and the gate script kicks the piece back to `shaping:spec` with the two texts in its Kickback section. Check: `.agents/tests/behaviour-deltas-rehearsal.sh`.
- `git status --porcelain` shows a path with a leading space or a space in its name: every script reads status with `-z` and handles both. Check: `.agents/tests/behaviour-deltas-rehearsal.sh` with ` M docs/data rules.md` in the working tree.

### The documents this change touches
- `setup-ai-build-kit/templates/masterplan.md`, the `working-rules.md` template slice 5 added (extended here), new templates `operations.md` and `concept.md`, and the foundation `AGENTS.md` pointers to the record files, outside the command list. Check: `.agents/tests/project-records.sh`; `.agents/tests/plan-helper-routes.sh` opens every pointer on all six layouts; `.agents/tests/standing-instructions.sh` and `.agents/tests/agent-first-records.sh` hold the ceiling and the index.
- `setup-ai-build-kit/references/masterplan-changes.md` (rewritten for deltas and the checkpoint), `pieces.md` (the `Behaviour change` field), `coverage-read.md` (reads the concept documents as well as the overview), `fit-check.md` (writes to working rules). Check: `.agents/tests/masterplan-changes.sh`, `.agents/tests/piece-contract.sh`, `.agents/tests/coverage-read.sh`, `.agents/tests/masterplan-edges.sh`, `.agents/tests/wiring-picture.sh`.
- `clarify/SKILL.md`: settled terms go to `docs/terms.md`, listed in `docs/README.md`; still no `CONTEXT.md`. Check: `.agents/tests/coverage-read.sh` (rule-shape).
- `WORKFLOW.md` section 2, "The three records", and section 12. Check: `.agents/tests/project-records.sh` (rule-shape on the sentences "The masterplan gives the overview; linked documents hold the rules" and "a piece's change to the records is applied when it merges").
- `README.md`: the two lines naming the masterplan as where the build path and acceptance live. Check: `.agents/tests/project-records.sh`.
- `docs/SOURCES.md` credits OpenSpec's added, modified and removed changes. Check: `validate-kit.sh`.
- `.agents/tests/replay/` grading reads acceptance through `records.py`. Check: `.agents/tests/replay-state.sh` passes the acceptance-record assertion on both formats.

## Masterplan change
Design note: "Learning and code health" (the behaviour record updated by each piece's change at the merge) and "1.0" (the compact masterplan). The note needs one change: name the three record files and the 500-word limit in "1.0".

## Not in this piece
- Selecting which concept documents a session reads: a later piece, out of v1.
- Applying deltas inside the run's integration order and the kickback mechanics: slice 9: Run controller, which this slice calls into.
- Moving a masterplan written by AI Build Kit to this format: none, by decision 63. Those projects stay on AI Build Kit.
- The final pass over every document for one story: slice 21: Documentation sweep.
- A merge check that waits for a named reviewer's GitHub review: not in v1; the rule is kept word for word so a later piece can hold it.

## Decided
- At most 500 visible words, counted the same way in the project check and the skill. Reason: decision 26 needs a compact masterplan before 1.0; the 500 words and the separate owning documents were confirmed when the compact masterplan was shaped.
- A format marker names the record format, and a missing or broken marker stops rather than guessing. Reason: the earlier attempt fell back to an older route on a malformed marker, and AI Loop Kit has no older route (decision 63).
- The marker says `project-records`, not the product's name. Reason: slice 22: Set AI Loop Kit's names would otherwise have to change every founded project.
- Only files listed in `docs/README.md` are records. Reason: the earlier attempt treated a project's own Markdown as records.
- This slice copies no helper into a project; the count in the project check is an inline step. Reason: the earlier attempt copied a Python helper that turned the project's own lint red.
- Records change only at the merge, through deltas, one piece at a time. Reason: decision 35, and five of six masterplan conflicts in a real project were on the per-piece stamp.
- `Trued against:` goes; a review checkpoint is written only by a completed review. Reason: the stamp moved on every piece without a review behind it.
- No move for a masterplan written by AI Build Kit. Reason: decision 63 and the design note's "Projects founded with AI Build Kit".

## Data
- New founded files: `docs/working-rules.md`, `docs/operations.md`, `docs/README.md`, `docs/<concept>.md` files. Written by founding, by `apply-behaviour.py` at the merge, by the fit check (working rules only) and by `/deploy` (operations only).
- `.ai-build-kit-maintenance` gains `records-review|<commit>|complete`, written only by `/maintain`.
- No project founded with AI Build Kit is moved (decision 63); every reader handles this format only.

## Leaves the tool
Nothing new leaves the tool, because the records stay in the project's repository and reach GitHub only through the pull requests that already carry them.

## Must still hold
- Every promise has a piece, including permissions, data, connections and parked terms: `.agents/tests/coverage-read.sh`.
- The founded AGENTS.md stays an index under 200 lines: `.agents/tests/agent-first-records.sh`, `.agents/tests/standing-instructions.sh`.
- Secrets are recorded by location, never value: `.agents/tests/secret-location.sh`.
- A tool that is not hosted is never launched by a merge: `.agents/tests/not-hosted.sh`.
- The confirmation box on merges that go live: `.agents/tests/merge-ask-rule.sh`.
- The area map check reads the map in `docs/working-rules.md`: slice 5's `area-map-rehearsal.sh`.
- An acceptance is quoted and read back before the work: `.agents/tests/acceptance-is-earned.sh`.
- A founded project's own lint and type check stay green with the kit's files in it: `.agents/tests/check-floor-rehearsal.sh`.
- The founding date still comes from the commit that added `masterplan.md`: `.agents/tests/session-start.sh`.
- No product name outside a recipe: `.agents/tests/hosting-request.sh`. No issue numbers in tracked files: `validate-kit.sh`.

## Relies on
- The contract field and the ready-gate lint: slice 3.
- The area map in the `## Areas` section of `docs/working-rules.md`, and `area-map.py`: slice 5.
- The integration step and kickback: slice 9.
- `/deploy`, which writes operations: slice 14.
- `/maintain`'s putting-the-records-right section: slice 17.
- On main today: `bring-up-to-date.sh`, `fold-changes.py` (moved by slice 17), `area-map.py` (slice 5), `merge-ask-rules.py`, `masterplan-changes.md`, `coverage-read.md`, `checks.yml`'s ceiling step as the pattern.
- From the earlier attempt in the old repository, gwpicard/ai-build-kit, read and not merged: its record-route reference and word counter, used as a starting point with the six faults its review found fixed.

## Reach and risk
Boundary: setup-ai-build-kit (templates, records references, the new `records.py`), section-builder (merge reference, bring-up-to-date, new `apply-behaviour.py`), clarify, maintain (the move and the checkpoint), WORKFLOW.md, README.md, SOURCES.md.
Reaches: founding on every layout (`starter-rehearsal.sh`, `plan-helper-routes.sh`, `claude-plugin.sh`, `agent-plugin.sh`); the merge step (`one-merge-step.sh`, `fold-at-merge-rehearsal.sh`, `recheck-before-merge-rehearsal.sh`); the project check (`check-floor-rehearsal.sh`, `boundary-rules-rehearsal.sh`, `adopted-ci-rehearsal.sh`); record habits (`record-habits.sh`, `founding-menu.sh`, `checks-first.sh`); the replay grader (`replay-state.sh`).
If it breaks: a reader that misroutes a field could weaken a safety check, which is why a broken marker stops; a failed delta stops the merge step with the two texts. Undone by reverting the slice's pull request.
Depends on: 3, 5, 9, 14, 17.
Loop module: build, because the format, the count, the routes and the deltas are all checkable on fixtures.
Crew: default.

## Under the hood
Start from the earlier attempt's commits, read with `git show`, and fix its six reviewed faults: records found by listing rather than by extension, a broken marker stopping, porcelain read with `-z`, one word counter shared by script and check, the replay acceptance read through the resolver, and the AGENTS.md pointer placed outside the command list the validator reads. `records.py` and `apply-behaviour.py` run from the installed skills; the project receives only Markdown and an inline check step. Existing rehearsals expected to change: `masterplan-changes.sh`, `masterplan-edges.sh`, `coverage-read.sh`, `wiring-picture.sh`, `secret-location.sh`, `area-map.sh` and `area-map-rehearsal.sh` from slice 5, `not-hosted.sh`, `one-merge-step.sh`, `hosting-request.sh`, `founding-menu.sh`, `record-habits.sh`, `checks-first.sh`, `agent-first-records.sh`, `plan-helper-routes.sh`, `replay-state.sh`, `check-floor-rehearsal.sh`, each to read through the resolver. New rehearsals: `project-records.sh`, `behaviour-deltas-rehearsal.sh`. Kit rules: the five questions for setup-ai-build-kit, section-builder, clarify and maintain; SOURCES.md credit; adapters rebuilt; validator; humanizer; no issue numbers.

## Evidence
Scripts run in throwaway repositories on founded and broken fixtures, each reader exercised; two branches merged in turn to show no conflict; the installed project check run on a founded project to prove its lint stays green; one guided check: found a small tool and read the masterplan and `docs/README.md` as a returning person would.

## Size
Two parts: Part a, two sittings; Part b, one sitting. Part b needs Part a.

## Consistency notes
- The area map has lived in the `## Areas` section of `docs/working-rules.md` since slice 5, so this slice moves no map. It adds the sensitive areas, accepted cautions and other build and review rules to the same file.
- Part c, which moved a masterplan written by AI Build Kit, is gone, and so is every legacy route: a masterplan without the marker is a record gap (decision 63).
- The `## Behaviour change` field and its lint rule are this slice's, extending slice 3's contract; slice 3 names them as this slice's.
- `area-map.py` and `gate.py` are the only scripts copied into a project, by slices 5 and 2, each held by `check-floor-rehearsal.sh`. `records.py` and `apply-behaviour.py` stay in the skills.
