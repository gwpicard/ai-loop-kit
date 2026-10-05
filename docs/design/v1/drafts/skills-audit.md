# Audit of AI Build Kit's skills, for AI Loop Kit v1

Date: 5 October 2026. Scope: the fourteen folders in `.agents/skills/`. Every
SKILL.md was read in full. The references and scripts were skimmed, and the
longest references were read in the parts that carry rules. Read only: nothing
in the repository was changed except this file.

The yardstick:

- Anthropic's skill authoring guide
  (platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices):
  "Concise is key", "Default assumption: Claude is already very smart", a
  SKILL.md body under 500 lines, references one level deep, a table of
  contents in any reference over 100 lines, degrees of freedom matched to how
  fragile the task is, "Prefer scripts for deterministic operations",
  "Solve, don't defer", validation loops, no time-sensitive content, one term
  for one thing, and evaluations written before the instructions.
- The Claude Code skills page (code.claude.com/docs/en/skills): description
  and `when_to_use` cut at 1,536 characters, a loaded skill stays in context
  for the rest of the session so every line costs on every turn,
  `disable-model-invocation: true` for commands only a person should start,
  `allowed-tools` with `${CLAUDE_SKILL_DIR}` for bundled scripts, and "Claude
  skips a must-apply rule: move logic to hooks".
- The local `skill-authoring` and `eval-skill` skills in `~/.claude/skills/`,
  which repeat the same rules and add: third-person descriptions with trigger
  phrases, "For critical checks, bundle a validation script", and "No README
  inside a skill folder".
- v1's decisions in `redesign-answers.md`: five commands, the run as a plain
  script, rules held by scripts, hooks, settings and the gate, and two layers
  for any rule that matters.

Counts of "prose rules a script or hook could hold" are my estimates from
reading. They count distinct rules, not lines.

## 1. Summary table

Size is SKILL.md lines and words, then the total with the references it loads
on its normal path. "Asks needlessly" lists places where the person is asked
something a default, a script or a record could settle.

| Skill | SKILL.md | With normal loads | Trigger and description | Prose rules a script could hold | Duplication | Contradictions | Depends on memory | Asks needlessly | Worth carrying | v1 home |
|---|---|---|---|---|---|---|---|---|---|---|
| change-triage | 304 / 3,024 | ~1,050 / ~10,000 (with `pieces.md`) | Hidden. Clear "what", but "Used by shape" is the only trigger. Fine for an internal skill. | ~10: capture through gate, exactly one `type:` label, sub-state per route, overlap search, content folder check, `/fix` alias | Risk notice and acceptance (also fit-check, shape, section-builder, ship); "gate refuses" boilerplate | None internal; routes context to "AGENTS.md's stack section" while section-builder routes it to concept files | "Step 5: Record only durable information" is a judgement on every turn | Mixed request split asks about the computer part first (fine) | Overlap warning that blocks nothing; work outside the project routed apart; content work kept out of git; bug fast path | `/shape` reference |
| clarify | 129 / 1,618 | ~200 / ~2,100 | Hidden. Description says "Used by start", a command that no longer exists. | ~3: settled term kept on piece; pre-mortem asked once; guess never written as answer | Acceptance rules restated | Line 9 "people who ... do not know software" against PHILOSOPHY's technical builders | "never ask it twice for one piece" (line 93) | Low; the guess-first style reduces asking | One question, labelled guess, choices only for a complete list; pre-mortem; existing artefact before prototype | `/shape` reference |
| implement | 192 / 1,984 | ~1,360 / ~13,800 for one piece; ~1,990 / ~20,300 for a run (`running-longer.md` 622 lines) | Command. 530 characters describing routing rather than triggers. | ~12: next-piece choice, claim, eligibility, "never sort by hand", resume offer | Restates shape's job, merge rule pointers, waiting-on-you rules from pieces.md | "to check" against `state:in-review` | Run state is a file (good), but the run itself is an agent following 622 lines | Group-parallel question every run | Claim before work through the gate; run state file; resume from file; "never work out the next piece by hand" | `/run` (script) |
| maintain | 894 / 9,369 | ~1,110 / ~11,200 monthly; more quarterly | Command. Clear when ("monthly", "quarterly"), but no trigger phrases. | ~25: version check, install-route detection, eleven `*-declined` bookkeeping lines, migrations, worktree tidy, AGENTS.md count | Branch, worktree and fold rules also in sync and implement | "thirteen" skills (lines 41, 78, 130) and "eight and thirteen" (709) when there are fourteen and nine; backfills `ready` and `shaping` labels (498-503, 528-529) which pieces.md says the kit no longer uses | "do not ask again this visit"; reads its own earlier no from a text file by hand | Seven one-time offers per visit (push rules, merge box, index, worktree links, project check, recipe move, pointers); the session-start script replacement is offered "again" every visit (211-216) | Stale-branch list that never removes; idempotent steps decided by what is on disk; findings become pieces | `/maintain` |
| queue | 146 / 1,647 | ~150 / ~1,650 (reads the printout) | Command. Good trigger phrases ("what can be built in parallel"). | ~8: the five-part plan, verdict per piece, command line, every verdict computed from printout marks | Whole verdict list repeats `running-longer.md` eligibility and merge conditions | "Boundary:" here, "Touches:" in the maintainer checks; "never issue numbers" against the audience | None beyond reading | None | Plan shown before running; one command at the end | None; becomes `/run --plan` output |
| screen-check | 134 / 1,099 | same | Hidden. Clear. | ~6: 24 px targets, contrast ratios, no `outline: none`, no blocked paste, sentence case, placeholder not a label | Claim boundary repeated in section-builder | None | None | None | The claim boundary; concrete rules; "do not fetch" pointers | Builder and reviewer reference, plus a lint where a linter exists |
| second-opinion | 127 / 997 | ~260 / ~2,100 with screen-check | Hidden. 457 characters of process. | ~3: independence order, same-session label | Stored-login and setting-read rules repeat ship and section-builder | "Used ... during start" | "Once you have said you cannot read a setting, never read it another way" (50-51) | None | Report format "Worth stopping for / Worth knowing"; every finding tried, not assumed; a named reviewer is a person | Review step in `/run` (fresh reviewer session) |
| section-builder | 694 / 7,264 | ~1,260 / ~12,600 (reach-check, trim, merge, test-strength); +256 / 2,471 for fix | Hidden. Short and clear. | ~30: first upload (81-123), claim, contract hash, checks-first commit order, closing words, changelog file naming, walk-through folder, area map save | Stored logins, live-service yes, secrets to `/tmp` (also ship, second-opinion, blocked-commands); "gate refuses" boilerplate | "to check" and `state:in-review` with `review:person` both used (552); acceptance in the same reply on the pull-request route (46-48) against shape's separate records pull request (387) | "Never let a fourth attempt run" counts attempts in the agent's head; agree the visible result | Step 2 "explicit yes" when ambiguous (acceptable) | Checks written first, run, seen failing, own commit; bar guard and gate running checks itself; retry-only pass is a fault; trim; one changelog file per piece | Builder prompt for `/run`; most steps move into the run script and gate |
| setup-ai-build-kit | 746 / 7,441 | ~2,450 / ~23,700 (fit-check 392, pieces 743, completion report, capability check, required tools, coverage read, check floor, clarify) | Command. Heading says "# Start" (line 6). Description clear, with a negative trigger. | ~25: branch read and switch (68-115), kit/source detection, version lookup (287-298), founding-menu line, label set and deletion, issue creation, `.env` copy, identity fallback, area map claim | Risk notice; save routes; first upload | Done-when says pieces wait "in spec" and the completion report ends on `/shape`, while the description says "point at /implement" | Many "say once", "do not mention" | Few, by design: "None of them is a gate" | Founding never stops; unneeded answers become open questions; cheaper options said once; checkpoint-only founding; resumable notes | `/setup` (half one) |
| shape | 503 / 5,589 | ~1,800 / ~19,000 (change-triage, pieces.md, clarify, readiness-check) | Command. 595 characters listing internal sub-states; no trigger phrases. | ~20: move table (129-150), spec branch naming and numbering (183-195), lint then checker order, `## Readiness` format, pick order (450) | Acceptance rules, first upload, pieces.md field rules | Acceptance saved on a separate records pull request (387) against section-builder; "No `needs-` label is written" (263) against AGENTS.md's maintainer checks that still describe them | "do not raise the question again in the same session" (115-116) | None; good "later" escape | Gate answer marker (record before label); fresh-session readiness check; research records sources and recommends, never decides; spec branch of failing tests | `/shape` |
| ship | 492 / 4,921 | ~900 to 1,300 / ~12,000 to 16,000 (recipe, parts, merge, fit-check on Build with care) | Command. "Take checked work to the copy of the tool the team actually uses" is vague; no trigger phrases. | ~20: recipe section order, warning-once, release tag arithmetic (317-324), records pull request, deploy reading, `Goes live:` line | Stored logins, live-service yes, secrets (203-266) repeat section-builder and second-opinion; merge rules point to merge.md (good) | "Say it once a visit" and "do not repeat it ... on a later /ship visit" in prose only | Warning repetition read from CHANGELOG by hand | Monitoring caution (fine, once) | Warnings never stop a launch; rollback "possible, not tried"; read the whole deploy output; secret by location never value | `/setup` (deployment half) and a GitHub Action health check |
| sync | 88 / 2,253 | ~320 / ~4,300; +743 lines when pieces.md decision rules load | Command. Good description with clear "when" and "not routine". | ~12: red `main` lookup, stale-piece list, gate report, fold, save route | Fold and save rules repeat section-builder and ship | Says "Closing a piece is the person's decision" but `gate.py tidy` acts unasked (fine, labels only) | Step 7 "a mistake the agent has now made twice" relies on recall | Stale-piece question every run (30) | Uncommitted work is a finding, never swept or discarded; corrections take the normal save route | `/maintain` (drift) and per-pull-request drift checks |
| what-now | 217 / 2,133 | ~220 / ~2,200 | Command. Good triggers. | ~10: the ordering of findings (gate report, bug, red check, run, waiting), version call, cap of three | Recovery routes repeat sync | "the other six commands" (8); hard-coded `gwpicard/ai-build-kit` (42) | None; reads files and shared script | None | Shares the session-start script so answers agree; gate report leads; cap of three; never "blocked by" and a bare number | `/what-now` |

Hidden skills (`user-invocable: false`): change-triage, clarify, screen-check,
second-opinion, section-builder. No skill uses `disable-model-invocation`,
`allowed-tools`, `argument-hint`, `context: fork` or `${CLAUDE_SKILL_DIR}`.
No reference over 100 lines has a table of contents (twelve files).

## 2. The ten biggest problems

1. **Far too long, and progressive disclosure runs backwards.** Three
   SKILL.md files pass the 500-line ceiling: maintain 894, setup 746,
   section-builder 694. The references that load on the normal path are
   larger still. `pieces.md` (743 lines, 6,945 words) is pulled in by shape,
   change-triage, setup, implement and sync. A single `/implement` loads about
   13,800 words before any code; a `/setup` loads about 23,700. Nesting goes
   three deep: implement, then `running-longer.md`, then section-builder,
   then `merge.md`. Twelve references over 100 lines have no table of
   contents.

2. **Deterministic procedures written as prose.** Exact algorithms sit in
   instructions the agent must replay: the first upload, with exit codes 0, 2
   and other (section-builder 81-123); the branch read and switch (setup
   68-115); the tag lookup that follows an annotated tag (setup 287-298); the
   claim race, "The earliest `Claimed by run` comment on the piece wins"
   (running-longer 320-330); the next release number (ship 317-324); eleven
   `*-declined|<date>|...` lines read and written by hand (maintain 279-300,
   314-331, 349-351, 436-451, 468-471, 800-807); and every queue verdict
   (queue 76-115). Each is a script with a test, not a paragraph.

3. **The run is an agent obeying 622 lines.** `running-longer.md` holds
   eligibility, claims, worktrees, parallel groups, stacking, failure counts,
   resume and the end report. "Never let one piece consume the run" (484-512)
   is a hope, not a budget. v1 has already decided the run is a plain script.

4. **One rule, many copies.** The stored-login rule appears in
   section-builder 281-289, ship 203-221 and second-opinion 48-51. The
   live-service yes appears in section-builder 291-303 and ship 223-244. "Where
   the gate refuses a move, tell the person its line in plain words ... Never
   write the label another way" is pasted into change-triage 138-140,
   implement 55-57, shape 152-154, section-builder 141-143, setup 455-457 and
   running-longer 318-320. The risk notice is restated in at least six files.
   Copies drift, and the next problem shows they have.

5. **Contradictions and stale facts.** what-now 8: "the other six commands"
   (there are nine). maintain 41, 78, 130: "thirteen" skills; 709: "eight and
   thirteen" (there are fourteen). PHILOSOPHY 49: "eight commands". The state
   vocabulary is split: section-builder 552 "move the piece to `to check`,
   which is `state:in-review` with `review:person`". maintain 498-503 and
   528-529 add `ready` and `shaping` labels that `pieces.md` (503-509)
   says "the kit does not use". shape 387 saves an acceptance "on a records
   pull request of their own"; section-builder 46-48 writes it and builds in
   the same reply. shape 263 says "No `needs-` label is written" while the
   root AGENTS.md test list still describes them. setup line 6 is headed
   "# Start"; clarify's description says "Used by start".

6. **The audience is written two ways.** PHILOSOPHY 41-50: "technical builders
   who direct agents ... Git, branches and pull requests are familiar". Yet
   clarify 9: "people who ... do not know software"; queue 45-47: "The person
   cannot follow a number"; what-now 192: "Do not show the check's output or
   its logs". The skills hide the very facts this audience can use.

7. **Rules that police the model's own mind.** About 150 lines of fit-check
   (131-280) and 60 of fix-loop (142-204) argue with the agent: "Remembering
   that you meant to give it is not finding it." Rules that hold only if the
   agent remembers a past turn: ship 89 "Say it once a visit", ship 101-103
   "do not repeat it ... on a later /ship visit", clarify 93 "never ask it
   twice for one piece", shape 115-116 "do not raise the question again in
   the same session", second-opinion 50-51 "never read it another way". After
   compaction or in a new session these cannot hold.

8. **History, migrations and test-harness detail in runtime text.** clarify
   25: "A headless replay with a scripted plain-text interlocutor uses the
   plain-words route." setup 377: "it cost two measured runs their whole
   founding". maintain 31-33: "a project was once told it was current".
   maintain 490-751, about 260 lines of one-time migrations, loads on every
   visit. Each costs context on every turn and teaches nothing the next step
   needs.

9. **Frontmatter and packaging ignore the platform.** Commands with side
   effects (setup, implement, ship, maintain) lack
   `disable-model-invocation: true`. Descriptions describe process instead of
   triggers: sync opens "True the documents up"; shape's 595 characters list
   sub-states. Scripts are named by pseudo-paths such as "`sh <installed
   implement skill>/scripts/worktree.sh`" (sync 78, maintain 397) rather than
   `${CLAUDE_SKILL_DIR}`. The bar guard and gate are copied into
   `.agents/tools/` (maintain 233-245), so two copies can drift. The kit's
   repository name is hard-coded in five places (section-builder 84, setup
   292 and 408, what-now 42, maintain 14).

10. **Guards are single-layer, fail open, or are optional.** The state guard
    hook "never blocks a command" when missing (root AGENTS.md, state-guard
    entry). The deny list blocks `Edit` of `.agents/pieces/` but not `Write`
    or a shell write (`claude-settings.json`). "Never post in the person's
    name", "never install outside the project folder" and "a secret key is
    never written to `/tmp`" live only in prose (blocked-commands 49-60,
    section-builder 300-303). Missing deny rules are offered and may be
    declined, then the decline is remembered (maintain 261-300). v1 wants
    these present, checked before a run, and held twice.

## 3. What to carry into v1

Ideas, not text. Each should be rewritten shorter, and moved into a script
where marked.

1. **The gate as the only mover of state, refusing with a `next:` command.**
   `setup-ai-build-kit/references/pieces.md` "Only the gate moves a piece";
   `templates/foundation/gate.py`.
2. **Record before label, enforced by a fingerprint.** The gate refuses to
   move a piece out of research, clarify or prototype until `## Research` or
   `## Decided` has changed. `shape/SKILL.md` 300-304.
3. **Readiness checked by a session that did not shape the piece, against a
   fixed list, with BLOCKING against NOTE.** "An open 'find the gaps' review
   always finds some, even in a sound piece."
   `shape/references/readiness-check.md` 1-40.
4. **Checks first: written, run, seen failing on their assertion, committed
   alone.** A check that passes today means the Done when line is wrong.
   `section-builder/SKILL.md` 206-245; spec branch of tests in
   `shape/SKILL.md` 164-170.
5. **The bar guard, and the gate running the checks itself.** "What you say
   about the checks counts for nothing there." `section-builder/SKILL.md`
   561-572; `scripts/bar-guard.sh`, `scripts/test-guard.sh`.
6. **A test that passes only on a retry is a fault, never a pass.**
   `section-builder/SKILL.md` 318-320.
7. **The trim with hard limits:** remove or fold only, never a test, only
   what the change added, its own commit, report the rest.
   `section-builder/references/trim.md` 25-67.
8. **Merge rules:** a yes that names the merge; every merge brought up to
   date with `main` and checked again; a stacked pull request never before its
   base; pre-approval with fixed conditions.
   `section-builder/references/merge.md` 10-24, 50-93, 265-293;
   `scripts/bring-up-to-date.sh`.
9. **Waiting for checks properly:** `gh pr checks --watch --fail-fast`, exit
   code 8 means not finished, no `sleep` loops, "no checks ran" is never green.
   `merge.md` 25-48.
10. **Closing words only on a `Closes #n` line.** GitHub closes an issue even
    from a sentence that denies it. `section-builder/SKILL.md` 536-548.
11. **One changelog file per piece, folded at merge.** Removes the conflict
    every parallel merge had at the top of `CHANGELOG.md`.
    `section-builder/SKILL.md` 638-662; `sync/scripts/fold-changes.py`.
12. **The first upload asks, and the code is online only when a remote branch
    shares history with `main`.** `section-builder/SKILL.md` 81-123 (as a
    script).
13. **Founding never gates.** "An answer you would like but do not need
    becomes an open question in the masterplan." A person who says "get on with
    it" has answered everything. `setup-ai-build-kit/SKILL.md` 44-64.
14. **The cheaper-option ladder, said once, with no stop.**
    `setup-ai-build-kit/SKILL.md` 216-239.
15. **Interview notes written before the next question, git-ignored, cleared
    once in the masterplan.** Survives a dead session.
    `setup-ai-build-kit/SKILL.md` 252-257, 164-169.
16. **Question discipline:** one question, a labelled guess, choices only when
    the list is complete, never invented options, silence is no answer.
    `clarify/SKILL.md` 13-23.
17. **The pre-mortem, once per piece:** "Say this went live and went wrong.
    Who noticed, and what did they see?" `clarify/SKILL.md` 87-93.
18. **Ask for an existing mock before building a prototype.**
    `clarify/SKILL.md` 106-112; `clarify/references/existing-artifact.md`.
19. **Research states sources and recommends, and never decides.**
    `shape/SKILL.md` 306-350.
20. **Overlap warning that blocks nothing and stays silent otherwise.** "A
    pause on every request teaches people to skip the pause."
    `change-triage/SKILL.md` 87-96.
21. **Work on this computer is routed apart from the project; content work
    stays out of git.** `change-triage/SKILL.md` 224-292.
22. **Speaking for the person:** any comment, review, mention, or change to
    another account's issue waits for a yes on the exact words.
    `setup-ai-build-kit/references/pieces.md` 615-660.
23. **No borrowed logins; a named yes listing every change before a live
    service changes; a secret passed by location, and "do not know where"
    never written as "absent".** `ship/SKILL.md` 203-266.
24. **Launch warnings never stop the launch, are said once and recorded.**
    Rollback is "possible, not tried". Read the whole deploy output and never
    deploy twice without checking. `ship/SKILL.md` 156-178, 386-395.
25. **Review report shape:** "Worth stopping for" and "Worth knowing", each
    finding says what was tried and what happened; a named reviewer is a
    person and no session stands in. `second-opinion/SKILL.md` 80-119.
26. **Screen claim boundary:** never call a screen accessible, compliant or
    good. `screen-check/SKILL.md` 120-126.
27. **Whole-project reads say nothing when they find nothing, cap proposals
    at three, and never show a score.**
    `setup-ai-build-kit/references/whole-project-reads.md`.
28. **what-now ordering and cap:** gate report first, then broken, red,
    unfinished run, waiting on the person; at most three things; the same
    script as the session-start reminder so the two never disagree.
    `what-now/SKILL.md` 30-35, 57-130.
29. **Worktrees owned end to end:** `.env` linked never copied, removal never
    forced, unsaved work detected and kept, main folder found with
    `git worktree list --porcelain | sed -n '1s/^worktree //p'`.
    `implement/references/running-longer.md` 200-302;
    `implement/scripts/worktree.sh`.
30. **Old branches listed, never removed, with Git-confirmed and GitHub-only
    merges kept apart.** `maintain/references/stale-branches.md`.
31. **Deny-rule spelling lists tested by a matcher, with the known gaps
    written down.** `setup-ai-build-kit/references/blocked-commands.md` 79-122;
    `.agents/tests/lib/permission-matcher.py`.
32. **Uncommitted work is a finding, never swept into a commit or
    discarded.** `sync/SKILL.md` 26.

## 4. Prose rules that should become checks, scripts, hooks or settings

Two layers are proposed where the rule matters. "Gate" means the gate script
refuses the move.

| Rule today (source) | v1 mechanism |
|---|---|
| No direct push to `main` (blocked-commands 79-122) | Settings deny rule and a parsing hook; plus a GitHub branch rule where the plan allows it |
| No force push, `reset --hard`, `clean -f`, recursive delete, `reflog expire`, `gc --prune` (blocked-commands 15-26) | Deny rules and the parsing hook (not text matching) |
| Only the gate writes state labels (pieces.md 476-490) | Deny rules, the hook, and builders holding no GitHub credential |
| The hook must not fail open (state-guard entry in AGENTS.md) | Pre-run check refuses to start when a hook is missing or not runnable |
| No write to the gate's record (deny covers `Edit` only) | Deny `Write` and shell writes too; sandbox write-block |
| Never read stored logins or keychains (section-builder 281-289, ship 203-221) | Deny rules on `security find-*`, credential files and tool config paths; sandbox read-block |
| A secret never goes to `/tmp` (section-builder 300-303) | Hook refusing writes of `.env` content outside the project; secret scan before every push |
| Never print or commit a secret (blocked-commands 46) | Secret scan in a pre-commit hook and on the pull request |
| Never post in the person's name without a yes on the words (pieces.md 615-660) | Ask rule on `gh issue comment`, `gh pr comment`, `gh pr review`, `gh api` POSTs to comments; builders get no token |
| No install outside the project folder without a yes (blocked-commands 61-65, change-triage 236-241) | Ask rules on `brew`, `npm -g`, `pip install --user`, a download piped into a shell; sandbox write-block outside the project |
| First upload asks; online only when a remote branch shares history (section-builder 81-123) | A script returning "online", "empty", "other content" or "unreachable"; the push hook refuses until the yes is recorded |
| Never push to the kit's own repository (setup 405-415, section-builder 83-86) | Script check on `origin`; pre-run check |
| Claim before work; earliest claim wins (running-longer 314-330) | Gate `claim` with the race settled inside it |
| Contract unchanged since ready (section-builder 132-139) | Gate (already exists); keep |
| Checks committed before code and seen failing (section-builder 206-219) | Gate reads commit order and the recorded failing run |
| No test changed unless the piece names it (section-builder 231-245) | Bar guard in the gate (exists); add the new-test lint v1 agreed |
| Retry-only pass is a fault (section-builder 318-320) | Gate runs checks itself and refuses retries |
| Three attempts then back to shaping (section-builder 273-279, running-longer 486-494) | Run script counts attempts from the gate's attempt log |
| Closing word only on `Closes #n` (section-builder 536-548) | Pull request check scanning title, body, commits and changelog files |
| One changelog file per piece, named `changes/<n>-<name>.md` (section-builder 638-662) | Merge check: exactly one file for the piece, none edited in `CHANGELOG.md` |
| Merge only on green, on the up-to-date commit (merge.md 50-60) | Run script plus a GitHub rule requiring the check; merge only the tested commit |
| Pre-approval conditions (merge.md 265-293) | Run script computes them; no prose list |
| Exactly one `type:` label before the first move (change-triage 181-189) | Gate refuses the first move without it |
| A piece with no state is captured, never duplicated (shape 445-448) | Gate `report` plus `capture <number>` (exists) |
| Acceptance needed for a sensitive piece (fit-check 205-280) | Ready gate refuses a sensitive piece without the acceptance block on the issue (v1 decision 12) |
| Acceptance quotes the person exactly, never a form with nothing selected (fit-check 233-246) | Ready lint checks the block holds a quote, a date and the notice reference |
| AGENTS.md under its ceiling, no dates, issue numbers or code names (section-builder 615-619) | Project check (exists for the count); add a pattern check |
| Every folder belongs to an area (section-builder 511-515) | `area-map.py check` in the project check (exists); keep |
| Masterplan or overview change applied in the same save (section-builder 517-520) | Merge check: a piece naming a doc must change it (v1 records model) |
| Warnings said once per launch (ship 167-178, 397-400) | Launch script dedupes against the changelog; no memory rule |
| Monitoring caution once (ship 97-106) | Recorded flag in the policy file; the script checks it |
| Rollback "possible, not tried" (ship 156-160) | Deploy recipe script prints the line itself |
| Never deploy twice without checking the first (ship 386-395) | Deploy script reads the host's deployment list before any retry |
| Next release tag (ship 317-324) | Release script |
| Branch read before founding (setup 68-115) | `/setup` script step |
| Kit version and commit lookup (setup 287-298, maintain 12-33) | Plugin version from the plugin manifest; no hand lookup |
| Founding menu and decline lines (setup 549-556, maintain 279-834) | One policy file with typed fields, written by scripts |
| Never sort pieces by hand (implement 20-21, queue 15-31, what-now 16-19) | Remove the instruction: `/what-now` and `/run` call the printout script and print its output |
| Queue verdicts per piece (queue 76-115) | `/run --plan` dry run printed by the run script |
| Stale pieces untouched 30 days (sync 27-37) | `/maintain` script lists them; no recall |
| Red `main` leads (sync 24, what-now 68-72) | Status script orders findings |
| Worktree never removed by force; `.env` linked (running-longer 200-302) | `worktree.sh` (exists) plus deny rule on `git worktree remove --force` |
| Uncommitted work never swept or discarded (sync 26) | Script refuses to stage files it did not write; deny `git checkout .` outside the fix step |
| Screen rules: 24 px targets, contrast, no `outline: none`, no blocked paste (screen-check 72-103) | Lint rules where the stack has a linter (for example an accessibility plugin); the rest stays prose |
| Skill and command counts in text (what-now 8, maintain 41, 709) | Validator check, or remove counts from runtime text |
| Session-start check-up due (what-now 30-35) | Keep as a hook script (exists) |
