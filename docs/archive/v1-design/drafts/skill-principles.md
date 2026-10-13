# Principles for AI Loop Kit v1's skills

Research for the v1 design, 5 October 2026. Topic: how v1's skills (`/setup`,
`/shape`, `/run`, `/maintain`, `/what-now`) should be written so they work as
well as possible in Claude Code, given the decisions in
`redesign-answers.md`: the run is a plain script that starts `claude -p`
builders, the gate is the only thing that moves pieces, and every important
rule is held by deterministic checks in at least two independent layers.

What I read: `redesign-answers.md`, `research/brief-common.md`, the opening of
`research/gates-determinism.md`, the local `~/.claude/skills/skill-authoring`
and `~/.claude/skills/eval-skill` skills, the sizes of the current AI Build Kit
skills in `.agents/skills/`, and the sources listed at the end.

## Sources

Primary sources, all read for this report.

- [A] Anthropic, Skill authoring best practices.
  https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- [B] Claude Code docs, Extend Claude with skills.
  https://code.claude.com/docs/en/skills
- [C] Agent Skills open standard, Specification.
  https://agentskills.io/specification
- [D] Agent Skills, Best practices for skill creators.
  https://agentskills.io/skill-creation/best-practices
- [E] Agent Skills, Using scripts in skills.
  https://agentskills.io/skill-creation/using-scripts
- [F] Agent Skills, Optimizing skill descriptions.
  https://agentskills.io/skill-creation/optimizing-descriptions
- [G] Agent Skills, Evaluating skill output quality.
  https://agentskills.io/skill-creation/evaluating-skills
- [H] Claude Code docs, How Claude remembers your project (CLAUDE.md).
  https://code.claude.com/docs/en/memory
- [I] Claude Code docs, Automate actions with hooks.
  https://code.claude.com/docs/en/hooks-guide
- [J] Claude Code docs, Run Claude Code programmatically (`claude -p`).
  https://code.claude.com/docs/en/headless
- [K] Claude Code docs, Subagents. https://code.claude.com/docs/en/sub-agents
- [L] Claude Code docs, Test plugins with evals (`claude plugin eval`).
  https://code.claude.com/docs/en/plugin-evals
- [M] Anthropic, Effective context engineering for AI agents, 29 September 2025.
  https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- [N] Anthropic, Prompting best practices.
  https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- [O] Gloaguen et al., Evaluating AGENTS.md: Are Repository-Level Context Files
  Helpful for Coding Agents?, arXiv 2602.11988, February 2026.
  https://arxiv.org/abs/2602.11988
- [P] Jaroslawicz et al., How Many Instructions Can LLMs Follow at Once?
  (IFScale), arXiv 2507.11538, July 2025. https://arxiv.org/abs/2507.11538
- [Q] Hong, Troynikov and Huber, Context Rot, Chroma, July 2025.
  https://www.trychroma.com/research/context-rot
- [R] Matt Pocock, `writing-for-agents` skill and its `SKILL-MECHANICS.md`, and
  the docs page for it. https://github.com/mattpocock/skills
  (`skills/productivity/writing-for-agents/`, `docs/productivity/writing-for-agents.md`)
- [S] Matt Pocock, `tdd` skill with `tests.md` and `mocking.md`
  (`skills/engineering/tdd/`), and the AI Hero page https://www.aihero.dev/skills-tdd
- [T] Matt Pocock, `code-review` skill (`skills/engineering/code-review/SKILL.md`),
  which uses twelve smells from Fowler's *Refactoring* as a baseline.
- [U] testsmells.org, the test smell catalogue behind tsDetect.
  https://testsmells.org/pages/testsmells.html
- [V] On the Diffusion of Test Smells in LLM-Generated Unit Tests, arXiv 2410.10628.
  https://arxiv.org/abs/2410.10628
- [W] ImpossibleBench: Measuring LLMs' Propensity of Exploiting Test Cases,
  arXiv 2510.20270. https://huggingface.co/papers/2510.20270
- [X] Local: `~/.claude/skills/skill-authoring/SKILL.md` and
  `~/.claude/skills/eval-skill/SKILL.md` (summaries of [A], [B], [C] and
  Anthropic's skill-creator, plus a review rubric).

Facts worth knowing before the principles, because several principles rest on
them:

- Claude Code loads every skill's name and description at start. The body
  loads only when the skill is invoked, then **stays in the conversation on
  every later turn** and is not re-read [B].
- After auto-compaction, Claude Code re-attaches **only the first 5,000 tokens**
  of each invoked skill, with **25,000 tokens** shared across all skills, most
  recent first [B]. Whatever sits past that point in a long skill is gone after
  a compaction.
- `description` plus `when_to_use` is cut at 1,536 characters in the listing
  [B]. The standard caps `description` at 1,024 characters and recommends a body
  under 500 lines and under 5,000 tokens [C].
- `allowed-tools` grants permission only for the turn that invoked the skill,
  and it restricts nothing [B]. It is a convenience, never a guard.
- CLAUDE.md and AGENTS.md are "context, not enforced configuration"; to block an
  action regardless of what Claude decides, use a PreToolUse hook or settings
  rules [H]. Hooks give "deterministic control" [I].
- In `claude -p`, a user-invoked skill runs when the prompt contains
  `/skill-name`. With `--bare`, skills, hooks, CLAUDE.md and the skill listing
  are not loaded at all [J].
- Context files hurt: in [O], context files lowered agent success on both
  benchmarks and raised cost by over 20%, for LLM-written and developer-written
  files alike; agents followed the instructions, but ran more tests and searched
  more files. Instruction following falls as the number of instructions rises,
  with a bias towards earlier instructions [P]. Performance degrades as input
  grows, unevenly [Q].
- Local evidence: today's AI Build Kit skills are far past every limit above.
  `section-builder` is 694 lines and about 15,000 words with its references,
  `setup-ai-build-kit` 746 lines and about 28,800 words, `maintain` 894 lines.
  After one compaction most of each is no longer in context.

## 1. The principles

Each principle has a one-line rule, why, and how to check it. "Lint" means a
check in a `check-skills` script that runs on every commit at no model cost.

**P1. A skill holds judgement and conversation; a rule that must hold lives in
a script, hook, setting or the gate.**
Why: instruction files are context, not enforcement [H]; hooks and settings are
deterministic [I]; the maintainer's principle asks for two independent layers,
and a sentence in a skill is not a layer.
Check: lint finds every sentence in a skill that states a hard rule (words such
as "never", "only", "must", "refuse") and requires a `Held by:` pointer naming
the hook, setting, gate move or test that enforces it. A rule with no holder
fails the lint.

**P2. Point at the script; do not restate it.**
Why: the environment (scripts, `--help`, config) is a source of truth, and a
document that restates it is a cache that goes stale [R]; prefer scripts for
deterministic operations and make clear whether to run or read them [A].
Check: lint fails when a skill quotes the gate's transition table, label names
or exit codes that the gate script defines; the test compares skill text with
the gate's own table and flags any copied row.

**P3. Keep SKILL.md small enough to survive compaction whole: v1 budget 150
lines and 2,000 words, description at most 300 characters.**
Why: only the first 5,000 tokens of a skill come back after compaction [B]; the
standard's ceiling is 500 lines and 5,000 tokens [C]; long instruction sets
lower adherence and raise cost [O][P][Q]. The 150 line and 2,000 word figures
are this report's choice, set well under the 5,000 token cut.
Check: lint counts lines, words and an estimated token count (words times 1.35)
and fails over budget.

**P4. Put what matters most first: the purpose, the stops and the first step.**
Why: models favour earlier instructions [P]; the compaction cut keeps the start
[B]; critical instructions buried in long text get ignored [X].
Check: lint requires the template's section order (section 3), so the Stops
section sits above the steps' detail.

**P5. Choose who can invoke each skill on purpose, and write the description
for that reader.**
Why: a model-invoked skill pays context on every turn through its description;
a user-invoked one (`disable-model-invocation: true`) pays none [R][B]. Side
effect workflows should be user-only [X]. For model-invoked skills, say what it
does and when to use it, in the third person [A]. (The open standard prefers
imperative phrasing, "Use this skill when..." [F]; Claude Code is v1's only
host, so follow Anthropic's third-person rule.)
Check: lint requires `disable-model-invocation: true` on `/setup`, `/run` and
`/maintain`; requires a "Use when" clause in any model-invoked description; no
angle brackets; under 300 characters.

**P6. Disclose detail one level deep, and say when to read each file.**
Why: nested references get partly read with `head` [A]; "Read X if Y" works
better than "see references/" [D]; files over 100 lines need a contents list [A].
Check: lint resolves every link from SKILL.md, fails on a reference file that
links to another reference file, fails on a reference file nothing links to,
fails on a link line without a condition word ("when", "if", "before"), and
requires a contents list in any reference over 100 lines.

**P7. Match freedom to fragility: exact commands for fragile steps, plain goals
for conversation.**
Why: narrow bridge versus open field [A]; calibrate each part separately [D].
Check: lint fails on any shell block in a skill longer than three lines or
containing a pipe chain into a state change; that work belongs in a script.

**P8. Build every script for an agent reader: no prompts, `--help`, JSON on
stdout, diagnostics on stderr, distinct exit codes, idempotent, `--dry-run`
where it changes state, bounded output, and errors that name the next command.**
Why: agents cannot answer interactive prompts; error text shapes the next
attempt; harnesses truncate long output [E]; scripts should solve, not punt [A].
Check: a test runs each script with `--help` (exit 0, mentions every flag), with
no arguments and no TTY under a timeout (non-zero exit, usage on stderr, no
hang), twice in a row on the same input (same result), and checks stdout parses
as JSON and stays under a size limit.

**P9. Explain why, say what to do, and do not shout.**
Why: context and motivation improve results; tell Claude what to do instead of
what not to do; aggressive language such as "CRITICAL: You MUST" now causes
over-triggering [N]; a prohibition makes the forbidden act more available [R].
Check: lint fails on capitalised emphasis words (MUST, NEVER, ALWAYS, CRITICAL,
IMPORTANT) and warns on a "do not" sentence with no positive instruction beside
it.

**P10. Cut every line Claude would follow anyway, and keep the gotchas.**
Why: Claude is already very smart; only add what it lacks [A]; the no-op test,
delete the sentence and see whether behaviour changes [R]; a gotchas list of
facts that defy reasonable assumptions is often the highest-value content [D].
Check: not mechanical. The scenario eval (section 4) is the test: a section
whose removal changes no grader result is a candidate for deletion. Lint only
requires a `## Gotchas` section to exist, even if short.

**P11. One home per fact across all skills, and one word per concept.**
Why: duplication and inconsistent terms confuse the model [A][R]; contradicting
instructions get picked arbitrarily [H]; the records model already says one
home per fact.
Check: lint runs a shingle comparison across all skill and reference files and
fails on a repeated paragraph (the kit already has `document-bloat.py` for
this). A glossary file lists the kit's terms and their banned synonyms (for
example "ticket" or "task" for piece, "stage" for state); lint fails on a banned
synonym.

**P12. Give every step a done condition the agent can check.**
Why: a vague bound invites premature completion; the strongest criteria are
checkable and exhaustive [R]; checklists and validation loops stop skipped
steps [A][D].
Check: lint requires a `Done when:` line under each numbered step, and warns
when it names no observable (a command's exit, a file, a gate state).

**P13. Inject live state with `!` commands instead of asking the agent to fetch
it, and say what to do when injection is off.**
Why: `!` output is inserted before Claude reads the skill [B]; just-in-time,
high-signal context [M]. The `disableSkillShellExecution` setting replaces it
with a marker [B], so a fallback line is needed.
Check: lint requires `/what-now` and `/run` to start their state section with a
`!` call to the gate's report, and requires a fallback sentence that names the
same command.

**P14. Never rely on a skill to steer a non-interactive builder; pass the
builder's brief and settings explicitly and verify them.**
Why: `claude -p` cannot ask questions; `--bare` drops skills, hooks and
CLAUDE.md [J]; skill triggering is probabilistic [F]. The decisions already say
the pre-run check refuses `--bare` and passes guards with `--settings`.
Check: a test of the run script asserts the exact `claude -p` command line: the
brief passed by file, `--settings` present, no `--bare`, and the `Skill` tool
denied in builder settings so a builder cannot wander into `/shape`.

**P15. Write the evals before the skill, and keep them.**
Why: build evaluations first, three scenarios, baseline without the skill [A];
run with and without, grade with evidence, drop assertions that always pass [G].
Check: lint fails on a skill with fewer than three eval cases in its folder;
CI runs the cheap eval tier (section 4) when a skill changes.

**P16. Keep skills timeless: no dates, versions, issue numbers or model names in
the prose.**
Why: time-sensitive text goes wrong [A]; the repository already bans issue
numbers in tracked files; versions belong to scripts and lockfiles [R].
Check: lint regex for dates, issue numbers written with a hash, version strings and model IDs in SKILL.md
and references.

**P17. Use skill-scoped `hooks` and `allowed-tools` only as conveniences.**
Why: `allowed-tools` lasts one turn and restricts nothing [B]; a hook in skill
frontmatter only exists once the skill is invoked, so it is not an independent
layer.
Check: lint fails if a skill's prose claims a guard ("cannot", "is blocked")
whose only holder is its own frontmatter.

## 2. What belongs where

| Kind of content | Skill | Script | Hook | Setting | Gate |
| --- | --- | --- | --- | --- | --- |
| Talking with the person, asking questions with a recommended answer | yes | no | no | no | no |
| Judgement: is this idea one piece or two, which need is the person's | yes | no | no | no | no |
| Order of steps in a conversation and when to stop and say so | yes | no | no | no | no |
| Gotchas the agent would get wrong | yes | no | no | no | no |
| Which state a piece is in, which moves are legal | no (point at it) | no | no | no | yes |
| Ready checks: spec lint, judge fails on main, fingerprint | no | yes (spec lint, called by gate) | no | no | yes |
| Frozen bar byte-for-byte, new-test lint, held-out run | no | yes | no | no | yes |
| Refusing a hand-written `state:` label | no | no | yes (PreToolUse) | yes (deny rule) | yes (report names it) |
| Refusing push to main, force push, recursive delete | no | no | yes | yes (deny) | GitHub ruleset as third layer |
| Reading real env files | no | no | yes | yes (deny Read) and sandbox | no |
| Secret scan before push | no | yes | yes (pre-push git hook and PreToolUse) | no | no |
| A yes before posting in the person's name | yes (shows the words) | no | yes (ask on `gh issue comment` and similar) | yes (ask rule) | no |
| Builder brief and permissions in a run | no | yes (run script writes the command line) | no | yes (`--settings` file) | no |
| Re-injecting key context after compaction | no | no | yes (SessionStart with `compact` matcher [I]) | no | no |
| Live state shown to the person | yes (`!` injection of the report) | yes (report) | no | no | yes (source) |
| Notifications, watchdog, stuck detection | no | yes | no | no | no |
| Facts about the project | no (point at AGENTS.md and docs) | no | no | no | no |

The rule of thumb: if a wrong answer is acceptable and the person is present,
it is a skill. If a wrong answer must be impossible, it is at least two of
script, hook, setting, gate and GitHub.

## 3. A skill template for v1

Folder: `.claude/skills/<name>/` in the shipped kit (Claude Code only for v1).
Shared tools that guard rules (the gate, the spec parser, the run script) live
outside the skill folders, in the kit's tools folder that deny rules and the
sandbox protect, because a guard inside an editable skill folder is not a guard
(see the decisions on guards guarding themselves). A skill's own `scripts/`
holds only helpers that change nothing the gate owns.

```
<name>/
  SKILL.md            150 lines and 2,000 words at most
  references/         each file 300 lines at most; contents list over 100 lines
  scripts/            agent-ready helpers (P8); no rules the gate owns
  evals/              at least three cases (section 4)
```

```markdown
---
name: shape
description: Captures an idea as a piece or shapes a piece until the gate accepts it as ready. Use when the person describes something to build, change or fix, or asks to shape a piece.
disable-model-invocation: false      # true for setup, run, maintain
argument-hint: "[idea in words, or a piece number]"
allowed-tools: Bash(python3 <kit>/gate.py report *) Bash(python3 <kit>/spec.py lint *)
---

# Shape

One paragraph: what this command is for and what it leaves behind.

## Now
!`python3 <kit>/gate.py report --json --brief`
If the line above shows a disabled marker, run that command first.

## Stops
- When to stop and what to tell the person, in one line each.
  Held by: <hook, setting or gate move> for any that is a hard rule.

## Steps
1. <step in the imperative>
   Done when: <observable: an exit code, a gate state, a file>.
2. ...

## Gotchas
- <fact that defies a reasonable assumption>

## When to read more
- Read `references/questions.md` when the piece has open needs.
- Run `scripts/<helper>.py --help` before first use.
```

Budget and placement rules:

- Frontmatter: `name` equal to the folder; description at most 300 characters,
  third person, "Use when" clause for model-invoked skills, no angle brackets.
- Sections in this order: purpose, Now, Stops, Steps, Gotchas, When to read
  more. The first 60 lines carry everything a session needs if it never reads a
  reference.
- One leading word per concept, from the kit glossary [R].
- No `ALL CAPS` emphasis, no dates or numbers of issues, no copied gate rules.
- `Held by:` after every hard rule.

## 4. How v1 tests its skills, cheaply

Three tiers. The first two cost nothing and run on every commit; the third
costs model calls and runs only when a skill or the model changes.

**Tier 1, static lint (every commit, free).** `skills-ref validate` for the
standard [C], `claude plugin validate` for the plugin's files [L], and the
kit's `check-skills` lint for P1 to P17. Each lint rule gets a mutation test
the way the kit's `rule-shape.sh` works today: remove the rule from a copy and
prove the lint catches it.

**Tier 2, script contracts (every commit, free).** The P8 test for every script
the skills call, against the existing fake GitHub stand-in.

**Tier 3, scenario evals (on skill change, before release, on a model
change).** Use `claude plugin eval` [L], which v1 gets for free as a Claude Code
plugin. Each case is a `prompt.md` plus graders. A `scaffold_script` seeds a
fixture project with the fake `gh` on the path; graders available are `regex`
(over the reply or a file), `tool_used`, `tool_order`, `file_exists`, `llm` and
`baseline`. There are no custom-code graders, so world state is graded through
files the run produces (the fake `gh` log, the gate's log) with `regex`.

What a passing skill must do on its scripted scenario, at least three cases each
(normal, edge, refusal):

| Command | Normal case passes when | Edge or refusal case passes when |
| --- | --- | --- |
| `/shape` | Given a one-line idea, the gate's capture move is called (`tool_used` with `input_match`), questions come with a recommended answer and stay under the cap (`regex` count), and a ready move is called only after `spec.py lint` (`tool_order`). | Given a vague idea, no ready move is called (`tool_used` max 0). Given a sensitive area, the reply asks for the person's acceptance and no ready move happens. |
| `/run` | The pre-run check runs before the run script (`tool_order`), and the skill starts the run script rather than building itself (no `Edit` on source files: `tool_used` max 0). | With a guard missing in the fixture, the reply names which `/setup` half is missing and the run script is never started. |
| `/what-now` | The report is read (injection or `tool_used`), the reply names every needs-you piece in the fixture (`regex`) and stays within its item cap. | With GitHub unreachable in the fake, the reply says so and invents no state (`regex not_contains` for a piece name absent from the fixture). |
| `/maintain` | Each finding becomes a shaping issue through the gate (`tool_used` count), and nothing else changes without a yes. | With nothing wrong in the fixture, it says so in one line and files nothing. |
| `/setup` | A missing tool stops the first half with the install line (`regex`). | Run on the kit's own repository fixture, it opens no issue and changes no setting (`tool_used` max 0 on `gh issue create`). |

Cost controls: one grader on the result and one on the steps per case [L];
`llm` graders only for short replies [L]; `--runs 1 --ablation none` while
iterating; `--runs 3` with the no-plugin baseline only before a release, where a
near-zero difference means the skill adds nothing [L][G]; pin `--model` and
`--judge-model`; set `--max-cost-usd`; `--threshold` gates CI, exit 2 means a
partial run.

Triggering: only model-invoked skills need trigger evals. Ten queries each,
five that should trigger and five near misses that should not [F][X], three
runs each, pass at a trigger rate above 0.5 [F]. Fewer than [F]'s twenty is a
deliberate saving; add more only if a real false trigger appears.

Builder sessions are not tested through skills at all (P14): the run's own
replay rehearsals test the builder's prompt file and settings.

## 5. Checks for agent-written code and tests

"Script" says whether a script can detect it reliably (yes), with false alarms
or misses (partly), or only a reviewer can judge it (no).

| Check | What it catches | Source | Script |
| --- | --- | --- | --- |
| Tautological test | The expected value is computed the way the code computes it, so the test passes by construction | [S] | partly: flag an expected value built from the function under test or a `reduce`/loop in the test; mutation testing catches what is left |
| Implementation-coupled test | Mocks the project's own modules, asserts call counts or order, tests private methods | [S] | yes for mocks of in-repo paths and call-count assertions; partly for private methods |
| Verifying through a side channel | Queries the database instead of the interface | [S] | partly |
| Test that can never fail | Over-mocked so no change to the code turns it red | [S] (Pocock's talk, via the AI Hero summary) | yes, mutation testing |
| Horizontal slicing | All unit tests written before any code | [S] | partly, from commit order. v1's frozen judge is a deliberate exception at the acceptance level; the rule applies to the builder's own unit tests |
| Test name says how, not what | "calls paymentService.process" | [S] | no |
| Empty or unknown test | A test with no assertion | [U] | yes |
| Ignored or skipped test | `.skip`, `xit`, `@Ignore`, `pytest.mark.skip` added | [U] | yes |
| Redundant assertion | `expect(x).toBe(x)`, `assert True` | [U] | yes |
| Duplicate assert | Same condition asserted twice | [U] | yes |
| Conditional test logic | `if` or loops in a test | [U] | yes |
| Sleepy test | `sleep` in a test | [U] | yes |
| Redundant print | Debug print left in a test | [U] | yes |
| Assertion roulette, magic number test | Many unexplained assertions or bare literals; common in LLM-written tests | [U][V] | yes, but low value; report only |
| Test edited to pass | Assertion changed, test deleted, timeout or retry raised | [W] | yes, the frozen bar diff and the new-test lint |
| Special-casing test inputs | Code returns the test's expected value for the test's input | [W][N] | partly: grep production code for fixture literals; held-out cases catch the rest |
| Code that detects it is under test | `NODE_ENV === 'test'`, `"pytest" in sys.modules`, internal counters to game the check | [W] | yes, grep in production code |
| Snapshot regenerated with the code | Snapshot files rewritten in the same change, no spec line | kit's own addition | yes |
| Suppressed checks | `eslint-disable`, `@ts-ignore`, `# type: ignore`, `noqa`, lowered coverage threshold added | kit's own addition | yes |
| Speculative generality, unused code | Code no caller needs | [T] | yes (unused-code tools) |
| Duplicated code | Copied blocks | [T] | yes (copy detectors) |
| Middle man | A wrapper that only delegates | [T] | partly |
| Mysterious name, feature envy, data clumps, primitive obsession, repeated switches, shotgun surgery, divergent change, message chains, refused bequest | Fowler's design smells | [T] | no, a reviewer's call; shotgun surgery partly from change spread in history |
| Swallowed error | Empty `catch` or bare `except: pass` | kit's own addition | yes |
| Debug leftovers | `console.log`, stray `print`, new TODO | kit's own addition | yes |
| New dependency | A package added | decisions (answer 9) | yes, lockfile diff |

The "yes" rows belong in the gate's new-test lint and the trim pass as checks.
The "partly" rows become worth-knowing notes for the reviewer. The "no" rows
are the reviewer's own list, which is where Pocock's code-review skill puts them
too: documented standards first, Fowler's smells as the baseline [T].

## Disagreements between sources

- Description voice: Anthropic says third person [A]; the open standard says
  imperative "Use this skill when..." [F]. v1 follows Anthropic, since Claude
  Code is the only host.
- Emphasis: Anthropic's iteration example suggests "MUST filter" over "always
  filter" [A], while the prompting guide says to dial back aggressive language
  on current models [N]. v1 follows [N] and moves hard rules into checks (P1),
  which removes the reason to shout.
- Description length: the local skill-authoring skill says about 100 words [X];
  the limits are 1,024 characters [C] and 1,536 in Claude Code's listing [B].
  v1's 300 characters is this report's choice, since every model-invoked
  description costs context on every turn [R].
