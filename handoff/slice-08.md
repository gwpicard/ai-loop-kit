# Slice 8: Every built piece is reviewed by a fresh session that sees only the contract and the change

Labels (today's set): enhancement, area:skills, ready-able once shaped. Release label for the PR: release-minor.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 2: Label model and gate script; slice 3: Contract v2 and the ready-gate lint; slice 5: Area map for the whole project, kept by the project check; slice 6: Frozen-bar enforcement; slice 7: Build and fix loop modules.

## So that
A piece reaches `state:in-review` only after an independent reader has judged it against what was agreed, and the person only gets the pieces that need their eyes, with the reason.

## Done when
### Works
- The second-opinion skill gains a section, "On a piece in a run", and a reference, `references/automatic-review.md`: the reviewer is a fresh session that receives only a packet folder holding the contract at its frozen hash and the diff against the piece's base, never the builder's transcript, result file or account of the work. Check: new `.agents/tests/automatic-review.sh` (rule-shape) reads both files.
- A new section-builder script, `scripts/review-packet.sh <number> <base> <out-dir>`, writes `contract.md` (refusing when the issue body no longer matches the hash slice 6 posted), `diff.patch` (`git diff <base>...HEAD`), and `checks.txt` (the acceptance and guard check commands), and nothing else. Check: new `.agents/tests/review-packet-rehearsal.sh` runs it in a throwaway repository with the stand-in GitHub and lists the folder.
- The founded project gains a reviewer agent definition, `.claude/agents/loop-reviewer.md`, installed by the bootstrap step from `templates/foundation/agents/loop-reviewer.md`, whose tools are reading, searching and running the project's checks, with no tool that writes files, pushes or edits issues. Check: `review-packet-rehearsal.sh` reads the installed file's tool list; `starter-rehearsal.sh` finds it.
- The reviewer returns one JSON verdict in a fixed format: `meets_contract` (`yes` or `no`), `code_sound` (`yes` or `no`), and `gaps`, each with `kind` (`missing`, `partial`, `contradicts` or `unrequested`), the criterion or file it concerns, what was tried, and `reproduced_by` (a check command or a failing check's name). The gate script, `gate.py review <number> <verdict-file>`, refuses a verdict that does not parse or uses another kind. Check: new `.agents/tests/review-verdict-rehearsal.sh` feeds the gate valid and invalid verdicts.
- A gap with no `reproduced_by` is logged as "not counted" and changes nothing; findings outside correctness and the contract's stated requirements, such as style, are refused by the format, which has no field for them. Check: `review-verdict-rehearsal.sh`.
- Each counted gap has one route, taken by the gate: `missing` and `partial` go back to the builder as a new round within the attempt limits of slice 7; `contradicts` is a kickback to `clarify` with the gap written in the Kickback section; `unrequested` goes back to the builder to be taken out, and where it remains after that round it forces `review:person`. `code_sound: no` with a reproduced finding goes back to the builder. Check: `review-verdict-rehearsal.sh` reads the route for each.
- Review rounds stop at `review_rounds` in `.agents/loop-settings.json`, default 2; a piece still holding counted `missing` or `partial` gaps at the cap goes to `state:in-review` as `review:person` with the gaps listed. Check: `review-verdict-rehearsal.sh` with a verdict that never clears.
- Every ruling is logged: the gate appends each verdict and its route to `.agents/pieces/<number>/reviews.jsonl`, and posts one bookkeeping comment on the piece's issue, `<!-- loop:review round=<n> -->`, holding the verdict JSON and the route in plain words. Check: `review-verdict-rehearsal.sh` reads both.
- The gate chooses the review label at `building -> in-review`: `review:person` when any recorded reason applies (from slice 6: a named guard change, a change outside the boundary, an acceptance check that missed a deliberate break; from slice 7: the builder's concerns; from this slice: unrequested work kept, or gaps at the cap; and a sensitive area in the piece's boundary or reach, read through slice 5's map), else `review:auto`. The reasons are written on the issue in one line each. Check: `review-verdict-rehearsal.sh`, one case per reason and an all-clear control.
- Calibration data: when a person moves an `in-review` piece back with the gate (`in-review -> building` for a defect the spec covers, `in-review -> shaping` for a spec problem), the gate posts `<!-- loop:person-verdict -->` with the outcome, and a piece the person merged with no such move counts as agreement; the automatic verdict and the person's outcome are both readable from the issue alone. Check: `review-verdict-rehearsal.sh` reads both markers from the stand-in issue.

### When it is not the normal case
- The coding agent cannot start a fresh session for the reviewer: the piece goes to `review:person` with the reason "no independent reviewer was available", never a same-session review. Check: `review-verdict-rehearsal.sh`; rule in `automatic-review.md` held by `automatic-review.sh`.
- The reviewer returns nothing, or prose instead of JSON: one retry with a fresh session, then `review:person` with the reason. Check: `review-verdict-rehearsal.sh`.
- The contract changed since its hash: `review-packet.sh` refuses, and slice 6's kickback applies before any review. Check: `review-packet-rehearsal.sh`.
- A named reviewer on the piece (a person the risk notice or the build path names): the automatic review still runs and the piece still goes to `review:person`, since no session stands in for a named reviewer. Check: `named-reviewer-is-a-person.sh`, extended.
- The masterplan review at founding and the launch review stay person-facing reports in today's format, untouched by the verdict format. Check: `automatic-review.sh` holds that the "Report format" section is kept for those two uses.

### Documents
- The second-opinion skill's description and SKILL.md: the new section, and "Independence fallback" saying a same-session fallback never meets the automatic review. Check: `automatic-review.sh`.
- section-builder's SKILL.md step 7, "Run required review": the automatic review replaces the trigger list for pieces in a run of the new model. Check: `automatic-review.sh`.
- WORKFLOW.md: "Evidence" says every piece is reviewed by a fresh session that sees only the contract and the change; "What stays yours" lists the reasons a piece comes to you. Check: `automatic-review.sh`.
- `docs/COMPATIBILITY.md`, "Harness map": where the reviewer agent definition applies and what other agents use. Check: `compatibility-grades.sh` rule.
- Root `AGENTS.md` names each new rehearsal. Check: `validate-kit.sh`.

## Masterplan change
Design note: "Review" (the automatic review, its two verdicts, gap sorting, rounds, logged rulings, the forced reasons and calibration), and the "Review" row of "Crews". The note needs one sentence under "Review" naming what happens at the round cap: the piece goes to the person with its gaps.

## Not in this piece
- Comparing the two verdicts and proposing changes to the reviewer's instructions: slice 17: /maintain absorbs /sync.
- Asking the person which pieces they want to review, and the review owed on the shaping board: slice 16: Boards and notifications.
- Forced review for a goal that missed, a first deployment and an irreversible data change: slice 11: Goal loop module, and slice 13: Merge policy.
- The other crew roles and their agent definitions: slice 10: Crews and computer resources.
- The gauntlet's blind critic, which reuses this verdict format: slice 12: Gauntlet loop module.

## Decided
- The reviewer reads the contract and the diff only, never the builder's claim, because a reviewer handed the author's account agrees with it. (Decision 29; addyosmani/agent-skills in the research note.)
- Two verdicts and four gap kinds, in a JSON format the gate reads, because a fixed verdict is what lets a script route it. (Decisions 29 and 44.)
- A finding counts only when reproduced or tied to a failing check. (Decision 44.)
- Two review rounds by default; at the cap the piece goes to the person rather than back to shaping, because the code exists and a person can judge it; this is this slice's choice, listed in OPEN-DECISIONS.md.
- Rulings are logged on the issue as well as on this computer, so calibration in slice 17 works from GitHub alone, on any computer. Bookkeeping on the project's own issue needs no yes. (Decision 46.)
- No same-session fallback for the automatic review on any path, because the review is what lets the person not read code.

## Data
New `.agents/pieces/<number>/reviews.jsonl` (git-ignored, written by the gate). New bookkeeping comments on each piece's issue: one per review round and one when a person sends a piece back. New key `review_rounds` in `.agents/loop-settings.json`. New `.claude/agents/loop-reviewer.md` in founded projects, written by founding; no project founded with AI Build Kit receives it (decision 63). Packet folders are written under `.agents/tmp/` and cleared with the piece's worktree.

## Leaves the tool
The diff and contract go to the coding agent's model service in a fresh session, as every build session already sends code there. One bookkeeping comment per review round goes to the project's GitHub issue.

## Must still hold
- A named reviewer is a person, and a session never stands in: `named-reviewer-is-a-person.sh`.
- Findings are reported in plain language for the person where a report is shown: `screen-rules.sh` (the screen axis stays for screen changes and never claims a screen is accessible).
- No stored login is read to check a setting: `no-stored-logins.sh`.
- Speaking for the person waits for a yes, and bookkeeping does not: `speaks-for-the-person.sh`.
- No issue numbers in tracked files; rehearsals named in AGENTS.md: `validate-kit.sh`.

## Relies on
- `.agents/skills/second-opinion/SKILL.md`, `.agents/skills/section-builder/SKILL.md`, `.agents/tests/replay/fake-github`: on main today.
- The gate script: slice 2. The contract fields and the `Boundary:`/`Reaches:` lines: slice 3. The area map's `which` and `sensitive:` lines: slice 5. The contract hash, evidence and forcing reasons: slice 6. Builder statuses, rounds within attempts, `.agents/loop-settings.json` and the fresh-builder route: slice 7.

## Reach and risk
Boundary: second-opinion (SKILL.md and the new reference), section-builder (step 7 and the packet script), the gate script's review action, the setup-ai-build-kit foundation templates (reviewer agent definition), WORKFLOW.md, COMPATIBILITY.md.
Reaches: the founding masterplan review and the launch review in `/ship`, guarded by `founding-carries-on.sh` and `ship-runs-recipe.sh`; runs, guarded by `the-runner.sh`; installation routes, guarded by `claude-plugin.sh` and `agent-plugin.sh`.
If it breaks: pieces pile up in `review:person` or reach `review:auto` without a real review. The first shows on the issue as a list of reasons; the second shows when the person's verdicts disagree. Undone by reverting the slice's pull request.
Depends on: 2, 3, 5, 6, 7.
Loop module: build, because every route is a gate outcome a stub verdict can drive.
Crew: default for the module.

## Under the hood
- Add `second-opinion/references/automatic-review.md` and the reviewer prompt inside it; `section-builder/scripts/review-packet.sh`; `templates/foundation/agents/loop-reviewer.md`; the gate's `review` action and label choice.
- Reuse the fresh-session route from the overnight batch branch's `task-context-capabilities.md`, brought onto main by slice 7.
- Expected to change: `named-reviewer-is-a-person.sh`, `the-runner.sh` (step 7 of each piece), `starter-rehearsal.sh` (a new founded file), `claude-plugin.sh` and `agent-plugin.sh` if they list founded files.
- SOURCES.md: credit obra/superpowers for the two verdicts and GitHub Spec Kit's `converge` for checking unrequested work, as `agentic-loop-research.md` records.
- Kit rules: five questions in the pull request; adapters rebuilt (the second-opinion background skill is in the adapter set); `validate-kit.sh`; the Humanizer before saving prose; no issue numbers.

## Evidence
A rule-shape rehearsal for the written rules (`automatic-review.sh`), script rehearsals with stub verdicts against the stand-in GitHub (`review-verdict-rehearsal.sh`, `review-packet-rehearsal.sh`). One guided check: in a throwaway founded project on Claude Code, build a piece that adds one unrequested button, and see the reviewer name it and the builder take it out.

## Size
Two sittings: one for the packet, the agent definition, the verdict format and the gate's routes; one for the prose, the forced-reason assembly and the calibration markers.

## Consistency notes
- The gate subcommand this slice adds is `gate.py review`. The review rounds setting is `review_rounds` in `.agents/loop-settings.json` (slice 7).
- Review comments on the issue use the shared `loop:` markers: `<!-- loop:review round=<n> -->` for each ruling and `<!-- loop:person-verdict -->` when a person moves a piece back. Slice 17 reads both, by these names, for calibration.
- From this slice on the gate chooses between `review:auto` and `review:person` at `state:building` to `state:in-review`; before it, slice 2 gives every piece `review:person`.
- The sensitive-area reason reads the area map in `docs/working-rules.md` through slice 5's `area-map.py`.
