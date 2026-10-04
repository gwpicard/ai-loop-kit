# Slice 16: A person sees what needs them and how each run is going on two boards, and hears about the four moments that matter without looking

Labels (today's set): enhancement, area:skills, ready-able once shaped. Release label for the PR: release-minor.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 2: Label model and gate script; slice 4: Shaping sub-states in /shape; slice 8: Automatic reviewer; slice 9: Run controller; slice 11: Goal loop module; slice 12: Gauntlet loop module.

## So that
A person who directs agents can open one page, see every question, review and merge waiting on them, follow each run's progress, and get a desktop notification at the four moments that need them, without reading a log.

## Done when

### Part a: one status file

#### Works
- `what-now/scripts/board.py status` writes `.agents/board/status.json` in the main folder from two sources only: the open issues and their labels (`state:`, `shaping:`, `review:`, `type:`, `loop:`), and the run records slice 9 writes (`.agents/runs/<run name>/run.json`). Check: new `.agents/tests/boards.sh` runs it against `fake-github.sh`'s stand-in holding one issue in each state and sub-state, plus two run records, and compares the JSON with a stored copy.
- The file carries a `schema` field, a `written` time, and three blocks: `needs_you` (questions to answer, prototypes to decide, references and kickbacks to look at, reviews owed, run pull requests waiting for a merge), `shaping` (one list per sub-state plus `ready`, in the person's order) and `runs` (per run: status, start, running time, counts by piece status, preview address, budget used; per piece: status, loop module, start and end, attempts, progress in the module's own terms, session log link, "what I could not check"). Check: `.agents/tests/boards.sh` validates every field against the stored copy, including progress for one build, one goal and one gauntlet piece.
- The file is written in one step (a temporary file then a rename), so a reader never sees half of it. Check: `.agents/tests/boards.sh` reads the file while a second write runs and finds valid JSON each time.
- `plan.local.md` becomes a text view written from `status.json` by the same script, so agents on any platform read the same facts. Check: `.agents/tests/plan-printout.sh`, changed to read the printout produced through `board.py`; `.agents/tests/plan-helper-routes.sh` still finds the helper on all six installed layouts.

#### When it is not the normal case
- GitHub cannot be reached: the issue blocks keep their last values, the runs block is refreshed from the local run records, and `written` and a `github_unreachable_since` field say how old the issue part is. Check: `.agents/tests/boards.sh` with the stand-in switched off.
- A label set GitHub shows breaks the state model (two states, a sub-label without its state): the piece appears once under `needs_you` with what is wrong, as the gate script would report it. Check: `.agents/tests/boards.sh`.
- No run has ever started: the runs block is an empty list and both boards say so in one line. Check: `.agents/tests/boards.sh`.

### Part b: the local page

#### Works
- `board.py html` writes one self-contained file, `.agents/board/index.html`, with the status embedded, two tabs (Shaping and Loop), and no outside script, font or request. It reloads itself every 30 seconds while a run is `running`. Check: `.agents/tests/boards.sh` greps the file for any `http` address outside link targets the status supplied, and for the two tab headings.
- The Shaping tab lists "Needs you now" first, then the sub-states and the ready pieces as columns. Each item has one action button that copies the exact command for it: `/shape <number>` to answer, `/implement <numbers>` to start a run on the chosen ready pieces in the shown order, `/shape <number> review` to ask to review a piece. Check: `.agents/tests/boards.sh` reads the commands out of the page for a stored status and compares them.
- The Loop tab shows each run with the fields from Part a and an activity log with times. Pause, continue and stop copy the gate's run commands from slice 9 exactly, `python3 .agents/tools/gate.py run pause <run name>`, `python3 .agents/tools/gate.py run resume <run name>` and `python3 .agents/tools/gate.py run abandon <run name>`. Check: `.agents/tests/boards.sh` reads the three commands out of the page for a stored running run, and none for a merged one.
- `/what-now` refreshes the status, writes the page, opens it with the computer's own opener (`open` or `xdg-open`) and prints its path. Check: `.agents/tests/boards.sh` with a stand-in opener that records its argument.
- The page meets the screen rules: readable at phone width, both colour schemes, every status said in words as well as colour. Check: guided check: open the page from a stored status on a phone-width window in light and dark mode and read every column; `.agents/tests/screen-rules.sh` still passes.

#### When it is not the normal case
- No opener exists (a remote shell): `/what-now` prints the path and the "Needs you now" list as text. Check: `.agents/tests/boards.sh` with an empty PATH for the opener.

### Part c: the live page on Claude, the four notifications, and /what-now

#### Works
- Where the coding agent can publish a page, `/what-now` and the run publish the same two tabs as a live page and update it each time `status.json` changes. This replaces the run's live progress page in `running-longer.md`. Its buttons copy the same commands. Check: `.agents/tests/run-controller.sh` from slice 9, extended: the live page is built from `status.json`, and the old "title, state and pull request link" page is gone.
- The person hears about exactly four events: a piece needs their review, a run paused, a piece was kicked back, a run went live. The gate script and the run controller call `what-now/scripts/notify.sh <event> <piece or run>` at those four points and nowhere else. Check: `.agents/tests/boards.sh` greps the gate script and run controller for every `notify.sh` call and compares the list with the four events.
- `notify.sh` sends one desktop notification with the computer's own tool (`osascript` on a Mac, `notify-send` on Linux), adds the event to the status file's activity log, and sends nothing twice for the same event on the same piece. Check: `.agents/tests/boards.sh` with stand-in notifiers that record their calls, run twice for the same event.
- `/what-now` opens with one line counting what needs the person, then opens both boards, and keeps its recovery routes. Check: new rules in `.agents/tests/boards.sh` (rule-shape) on `what-now/SKILL.md`; `.agents/tests/check-up-counts-work.sh` and `.agents/tests/kit-version-record.sh` still pass.

#### When it is not the normal case
- No desktop notifier exists: the event still goes into the activity log and to the top of both boards, and the run's report says notifications could not be shown. Check: `.agents/tests/boards.sh` with no notifier on the PATH.
- The live page cannot be published: say so once and carry on with the local page. Check: `.agents/tests/run-controller.sh`.

### The documents this change touches
- `what-now/SKILL.md`: reads `status.json`, opens the boards, keeps its recovery routes. Check: `.agents/tests/boards.sh` (rule-shape).
- `implement/references/running-longer.md`: the live page and the activity log come from the status file. Check: `.agents/tests/run-controller.sh`.
- `WORKFLOW.md`: a section "The two boards" saying what each shows, the four notifications and the copy-a-command buttons, replacing the printout's description where it only described `plan.local.md`. Check: `.agents/tests/boards.sh` (rule-shape).
- `README.md`: the `/what-now` row says it opens the boards. Check: `.agents/tests/boards.sh`.
- `docs/COMPATIBILITY.md`: the local page and notifications work on any agent with a shell; the live page needs an agent that publishes pages. Check: `.agents/tests/boards.sh`; `.agents/tests/compatibility-grades.sh` still passes.
- The foundation `gitignore` gains `.agents/board/`. Check: `.agents/tests/boards.sh` founds a throwaway project and finds `git status` clean after a board is written.

## Masterplan change
Design note: "Boards", and the `/what-now` row of "Commands". The note needs two changes: the board's actions copy a command rather than run work from the page, and "orders the ready pieces" means the order of the numbers in the copied `/implement` command.

## Not in this piece
- Writing the run record and the gate's pause, resume and abandon actions: slice 9: Run controller.
- The plan shown when a run starts, and retiring `/queue` as a command: slice 9: Run controller.
- Progress values for goal and gauntlet pieces, which this slice only shows: slice 11: Goal loop module and slice 12: Gauntlet loop module.
- Showing the kit's own metrics: slice 17: /maintain absorbs /sync.
- Notifications through a phone or a chat service: not in v1.

## Decided
- One status file feeds both boards and the text printout, written by one script from the issues and run records. Reason: decision 22 and the design note's trap of two sources of truth.
- The local page is static and reaches nothing outside the computer; its buttons copy commands, including the gate's pause, resume and abandon. Reason: the kit's refusal to become a service ("What stays"); a page that ran commands would need a local server.
- The run's live page on Claude is the same board, replacing today's progress page. Reason: decision 22.
- Exactly four notifications, each once per event. Reason: decision 32, and the design note's trap of review requests so frequent the person stops reading.
- Notifications use the computer's own notifier, with the board as the fallback. Reason: local and free of any service.
- The scripts live in the installed `what-now` skill and are never copied into the project, except the existing printout helper. Reason: a copied Python helper turned a project's own lint red in the compact masterplan attempt.

## Data
- `.agents/board/status.json` and `.agents/board/index.html` in the main folder; git ignores both; written only by `board.py`; rebuilt from scratch every time, so a format change needs no move.
- The activity log inside `status.json` keeps the last 200 events.
- `plan.local.md` keeps its name and becomes a view of the status file.

## Leaves the tool
Nothing new leaves the computer, except the live page on Claude, which the coding agent publishes privately to the person's own account, as the run's progress page does today. It carries titles, states and links, never a key or a person's data.

## Must still hold
- The printout is one-way: nothing reads a piece back from it: `.agents/tests/plan-printout.sh`.
- The helper reaches every installed layout: `.agents/tests/plan-helper-routes.sh`.
- `/what-now` and a session's opening agree on the check-up: `.agents/tests/check-up-counts-work.sh`, `.agents/tests/session-start.sh`.
- `/what-now` names a newer release only from `releases/latest`: `.agents/tests/stable-is-the-channel.sh`.
- Run state never holds a key or a person's data: `.agents/tests/run-controller.sh` from slice 9.
- The screen rules make no claim the page is accessible: `.agents/tests/screen-rules.sh`.
- No issue numbers in tracked files: `validate-kit.sh`.

## Relies on
- The state, sub-state, review, type and loop labels: slice 2: Label model and gate script.
- Kickbacks with a Kickback section: slice 4: Shaping sub-states in /shape.
- Review rulings and `review:person`: slice 8: Automatic reviewer.
- The run record and its statuses: slice 9: Run controller.
- Progress fields per module: slice 11: Goal loop module and slice 12: Gauntlet loop module.
- On main today: `setup-ai-build-kit/templates/foundation/plan-refresh.sh`, `place-plan-helper.sh`, `what-now/SKILL.md`, `.agents/tests/fake-github.sh`, `.agents/tests/lib/rule-shape.sh`.

## Reach and risk
Boundary: what-now (skill and new scripts), implement's running-longer reference, the printout helper, the foundation gitignore, WORKFLOW.md, README.md, COMPATIBILITY.md.
Reaches: the run controller's calls (`run-controller.sh`, `run-record-rehearsal.sh`); the gate script's calls (slice 2's gate rehearsal); the printout's readers (`plan-printout.sh`, `plan-helper-routes.sh`); session start (`session-start.sh`).
If it breaks: the person sees a stale or empty board and no notification; the runs themselves go on, since nothing reads the board to decide. Undone by reverting the slice's pull request.
Depends on: 2, 4, 8, 9, 11, 12.
Loop module: build, because the file, the page's commands and the notification calls are all checkable by a script; the page's look is a guided check.
Crew: default.

## Under the hood
New `what-now/scripts/board.py` (subcommands `status` and `html`) and `what-now/scripts/notify.sh`, run from the installed skill. `plan-refresh.sh` calls `board.py status` and writes `plan.local.md` from the result, so `place-plan-helper.sh` and its `/maintain` step keep working. The HTML is one template string inside `board.py`, with the status embedded as JSON, styled with colour tokens for both schemes. `gate.py` (slice 2) and the run controller (slice 9) gain the `notify.sh` calls and call `board.py status` after each write. New rehearsal `.agents/tests/boards.sh`, sourcing `lib/rule-shape.sh` for the written rules. Existing rehearsals expected to change: `plan-printout.sh` (printout comes through the status file), `run-controller.sh` (live page source); `queue-groups.sh` is gone with `/queue` in slice 9. Kit rules: the five questions for `what-now` and `implement`; adapters rebuilt (the `what-now` description changes); validator; humanizer on all prose; no issue numbers.

## Evidence
Scripts run against `fake-github.sh` and stored run records, compared with stored outputs; stand-in notifiers and openers that record their calls; rule-shape checks for the skill's and WORKFLOW.md's rules; a guided check of the page at phone width in both schemes; one guided check on Claude that the live page updates while a run of two pieces builds.

## Size
Three sittings, one per part. Part b and Part c both need Part a.

## Consistency notes
- Board buttons never run anything: each copies the exact command for the person to paste, `/shape <number>`, `/implement <numbers>` or the gate's run commands from slice 9 (`python3 .agents/tools/gate.py run pause|resume|abandon <run name>`). No slice describes a button that starts work.
- Names: the run record is `.agents/runs/<run name>/run.json` and the run controller is `implement/scripts/run.py` (slice 9); the review markers are `loop:review` and `loop:person-verdict` (slice 8).
- `board.py` and `notify.sh` stay inside the what-now skill and are never copied, so a project's own lint never reads them. The copied `plan-refresh.sh` and `gate.py` call them; how a copied script finds a skill on every installation route is an open decision for the maintainer.
- `queue-groups.sh` went with `/queue` in slice 9, so it is not among the rehearsals this slice reaches.
