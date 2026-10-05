# Spec-driven development and making specs ready for agents

Research for AI Loop Kit v1, 5 October 2026. Topic: how current tools write a
spec, check that it is good enough, decide that it is ready, keep it in step
with the code, and handle research, questions and prototypes. Compared with our
shaping state, computed needs list, spec block, ready gate and records model.

The earlier research (docs/design/agentic-loop-research.md) already took four
lessons: fix how success is judged before the build, check for work nobody
asked for, record behaviour changes as deltas, and declare each task's boundary
and dependencies. This note goes deeper on readiness and on what the design
still lacks.

## 1. What the leading approaches do

### GitHub Spec Kit (version 1.1.0, 2 October 2026)

Source: [repository](https://github.com/github/spec-kit),
[agentic SDD reference](https://github.github.io/spec-kit/reference/agentic-sdd.html),
[spec-driven.md](https://github.com/github/spec-kit/blob/main/spec-driven.md),
command templates read from `templates/commands/` on 5 October 2026.

- Commands: constitution, specify, clarify, plan, tasks, analyze, checklist,
  implement, converge, and taskstoissues. Extensions add bug-assess, bug-fix,
  bug-test and a five-step idea assessment.
- Constitution: the project's principles. In `analyze`, any conflict with a
  MUST principle is CRITICAL by rule. A principle changes only by an explicit
  constitution update, never inside an analysis.
- Specify: the template keeps the spec free of implementation detail. Unknowns
  are written as `[NEEDS CLARIFICATION: question]`, with a hard limit of three
  markers. Beyond three, the agent keeps the three with most scope, security or
  UX impact and makes informed guesses for the rest. A built-in requirements
  checklist runs up to three self-repair rounds: no markers left, requirements
  testable and unambiguous, success criteria measurable and free of technology,
  edge cases identified, scope bounded, dependencies and assumptions listed.
- Clarify: scans the spec against a fixed coverage taxonomy (journeys, data,
  non-functional attributes, integrations, edge cases, terminology and more),
  marks each category Clear, Partial or Missing, and asks at most five
  questions, one at a time. Each question carries one "why it matters" sentence
  and a recommended option; "yes" accepts the recommendation. Answers are
  written back into the spec. The closing report lists each category as
  Resolved, Deferred, Clear or Outstanding.
- Checklist: "unit tests for English". It tests the quality of the
  requirements (completeness, clarity, consistency, coverage, edge cases), never
  the code. The agent must not tick its own items; ticking belongs to a
  reviewer.
- Analyze: read-only, after tasks and before implement. Six passes:
  duplication, ambiguity (vague adjectives such as fast, scalable, secure,
  intuitive, robust; placeholders such as TODO and ???), underspecification,
  constitution alignment, coverage gaps (requirements with no task, tasks with no
  requirement), and inconsistency (terminology drift, entities in one file and
  not the other). Every requirement has a stable key (FR-001, SC-001). Severity
  is CRITICAL, HIGH, MEDIUM or LOW. At most 50 findings.
- Plan has "phase -1 gates": simplicity, anti-abstraction, integration-first.
  Test-first is "non-negotiable": contract, integration, end-to-end and unit
  tests are written and seen failing before code.
- Converge: after implement, compares code with spec, plan and tasks, and
  classifies each gap as missing, partial, contradicts or unrequested. It only
  appends tasks and never edits code. Implement and converge repeat until it
  reports "converged".
- Keeping in step: maintainers say a change found after clarify starts a new
  spec cycle rather than editing a finished one
  ([discussion, 2026](https://github.com/github/spec-kit/discussions/2387)), and
  that spec and code staying in sync "requires a certain amount of discipline"
  ([discussion](https://github.com/github/spec-kit/discussions/152)). Drift
  repair is left to extensions such as
  [spec-kit-sync](https://github.com/bgervin/spec-kit-sync).

### Amazon Kiro

Source: [specs docs, updated 2 October 2026](https://kiro.dev/docs/specs/),
[best practices, 25 September 2026](https://kiro.dev/docs/specs/best-practices/),
[steering](https://kiro.dev/docs/steering/),
[new spec types, 18 February 2026](https://kiro.dev/blog/specs-bugfix-and-design-first/),
[correctness, updated 4 August 2026](https://kiro.dev/docs/specs/correctness/),
[requirements analysis](https://kiro.dev/blog/deep-spec-analysis/) (CLI 2.4.0,
20 May 2026; IDE, 13 July 2026, per the [changelog](https://kiro.dev/changelog/ide/0-12/)).

- Three files: requirements (or bugfix), design, tasks. A person approves each
  phase. "Quick Spec" writes all three with no approval gates, for
  well-understood work.
- Requirements are user stories with numbered acceptance criteria in EARS form
  ("WHEN … THE SYSTEM SHALL …"). The numbers let design, tasks and tests point
  back to a criterion.
- Design-first: start from an architecture or prototype and derive the
  requirements from it.
- Bugfix specs have three parts: current behaviour, expected behaviour and
  unchanged behaviour ("WHEN a user submits a valid form THEN the system SHALL
  CONTINUE TO process it exactly as before"). Tests are generated for all three:
  the bug exists, the fix works, the unchanged behaviour still holds.
- Correctness: properties are derived from EARS criteria and run as
  property-based tests that generate many cases and shrink a failure to its
  smallest input.
- Requirements analysis: an LLM refines vague statements into EARS criteria,
  then translates them into formal logic several times. Disagreement between
  the translations ("semantic entropy") marks a requirement as ambiguous. A
  solver then finds conflicts and gaps no rule covers. Findings reach the person
  as a question with two answers: keep it, or change it to a stated proposal.
- Steering: product.md, tech.md and structure.md, loaded always, by file
  pattern, by hand, or by description.
- Hooks fire on file events, prompt submit, tool use and task start or end.
- Keeping in step: requirements change, then "update design", then "Sync Files"
  regenerates tasks. Detecting code drift since a spec was written is an open
  request ([issue, 15 June 2026](https://github.com/kirodotdev/Kiro/issues/9435)):
  record the commit at spec creation and warn when later commits touch related
  files.

### OpenSpec

Source: [repository](https://github.com/Fission-AI/OpenSpec),
[Thoughtworks Radar vol. 34, April 2026, Assess](https://www.thoughtworks.com/en-us/radar/tools/openspec).

- Commands: explore, propose, apply, archive, validate.
- A change carries delta specs: ADDED, MODIFIED, REMOVED and RENAMED
  requirements. Requirements use SHALL or MUST. Every requirement needs at least
  one "Scenario" with WHEN and THEN. `validate --strict` enforces the format.
- Archive merges the deltas into living specs in `openspec/specs/`, one source
  of truth for current behaviour.
- A September 2026 bug is instructive: `validate` passed a scenario heading with
  no body that `archive` then refused, because the two used different parsers
  ([issue, 12 September 2026](https://github.com/Fission-AI/OpenSpec/issues/1857)).
- The Radar praises it for small, incremental changes to existing systems, and
  warns teams to keep checking whether native agent features make such tooling
  unnecessary.

### BMAD Method

Source: [docs](https://docs.bmad-method.org/),
[Test Architect module](https://github.com/bmad-code-org/bmad-method-test-architecture-enterprise).

- Work enters at a level fitted to its size: a vague notion at Clarify, a clear
  idea at Plan, a small change straight at Build and verify.
- An implementation readiness check sits between solutioning and building. It
  cross-checks the requirements, architecture and stories for coverage,
  traceability and conflicts, and returns PASS, CONCERNS or FAIL with a report.
- The Test Architect scores risk as probability times impact (1 to 9) and maps
  the score to an action (document, monitor, mitigate, block). It writes failing
  acceptance tests before code ("a test that has never failed has proven
  nothing"), builds a requirement-to-test trace matrix, audits non-functional
  evidence, and gives a gate result: PASS, CONCERNS, FAIL or WAIVED, where
  WAIVED needs a named stakeholder's documented exception. A skipped test blocks
  rather than passing quietly.

### Tessl

Source: [launch, 23 September 2025](https://tessl.io/blog/tessl-launches-spec-driven-framework-and-registry),
[skills, January 2026](https://tessl.io/blog/skills-are-software-and-they-need-a-lifecycle-introducing-skills-on-tessl),
[eval methods](https://tessl.io/blog/three-context-eval-methodologies/).

- The framework aimed at spec-as-source: each spec lists capabilities, each
  linked to a test with `[@test]`, and generated code is marked "do not edit".
- The registry held over 10,000 usage specs for open-source libraries, to stop
  agents inventing APIs.
- In January 2026 Tessl repositioned around a skills registry with evaluations.
  Spec-as-source is no longer its lead product.

### Agent OS (Builder Methods), version 3, January 2026

Source: [v3 announcement](https://github.com/buildermethods/agent-os/discussions/310),
[shape-spec](https://buildermethods.com/agent-os/shape-spec).

- Version 3 retired its own spec-writing and implementation commands and defers
  to the agent's plan mode. It argues that current models implement a good spec
  well alone.
- `/shape-spec` runs inside plan mode and asks four things: what are we
  building, are there visuals, is there similar code to follow, which standards
  apply. It saves plan.md, shape.md (scope, decisions, context), references.md,
  standards.md and a visuals folder, dated.
- `/discover-standards` and `/inject-standards` turn the codebase's habits into
  written standards and load them when relevant.

### Writings and guidance

- Birgitta Böckeler, [Understanding spec-driven development: Kiro, spec-kit and
  Tessl](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html),
  15 October 2025. Three levels: spec-first, spec-anchored, spec-as-source.
  Problems: too many markdown files to review, one workflow for every size of
  problem, agents ignoring or over-reading specs despite detail, a false sense of
  control. She warns of making things worse while trying to improve them.
- Thoughtworks [Technology Radar vol. 34](https://www.thoughtworks.com/en-us/radar/techniques),
  April 2026: spec-driven development at Assess. Context engineering and curated
  shared instructions at Adopt. Feedback sensors for coding agents at Trial.
  Agent instruction bloat at Caution.
- Anthropic, [Claude Code best practices](https://code.claude.com/docs/en/best-practices)
  (read 5 October 2026): explore, plan, then code; skip the plan if the diff fits
  in one sentence; for larger work let Claude interview you with
  AskUserQuestion and write SPEC.md, then implement in a fresh session. "The
  most useful specs are self-contained: they name the files and interfaces
  involved, state what is out of scope, and end with an end-to-end verification
  step." A reviewer prompted to find gaps will usually find some, so restrict it
  to gaps that affect correctness or stated requirements.

### Requirement quality and test-first practice

- EARS, [Alistair Mavin and colleagues at Rolls-Royce, 2009](https://alistairmavin.com/ears/):
  six patterns. Ubiquitous ("The system shall"), state ("While"), event
  ("When"), optional feature ("Where"), unwanted behaviour ("If … then"), and
  complex combinations.
- INVEST, [Bill Wake, 2003](https://xp123.com/invest-in-good-stories-and-smart-tasks/):
  independent, negotiable, valuable, estimable, small, testable.
- Given-When-Then ([Gherkin reference](https://cucumber.io/docs/gherkin/reference/))
  and [Specification by Example](https://www.oreilly.com/library/view/specification-by-example/9781617290084/)
  (Gojko Adzic, 2011): key examples with concrete values, automated, become
  living documentation.
- "Definition of Ready" is not in the Scrum Guide and is often criticised as a
  gate that keeps items from ever being ready
  ([Scrum.org](https://www.scrum.org/resources/blog/ready-or-not-demystifying-definition-ready-scrum)).

### Evidence on LLMs judging specs (2026 papers)

- Shefa, Salado, Wach and Topcu,
  [benchmark of 10 LLMs on requirement quality](https://arxiv.org/abs/2609.03230),
  3 September 2026: the best model found a median 47% of defects with 11% false
  alarms. Necessity and correctness defects were almost always missed. Newer
  models were not reliably better. The authors advise decision support with a
  person, and warn that agentic use may compound the misses.
- Broccia, Frattini, Arora and others,
  [LLM support in requirements inspection](https://arxiv.org/abs/2608.21298),
  21 August 2026, 34 participants: LLM help lowered defect detection accuracy and
  may slow how novices learn to inspect.
- Fang and others, [ClarifyCodeBench](https://arxiv.org/abs/2607.00711), July 2026:
  good code generation does not mean good clarification. More reasoning gave
  little gain in spotting ambiguity, and clarification falls sharply as the
  number of ambiguities in one task rises.
- Fawcett, [rebuild-dossier](https://arxiv.org/abs/2608.23616), August 2026:
  locking the interface and enforcing one test at a time mechanically. A weaker
  model that ignored the rules passed all tests while a compliant one failed. It
  calls for several layers of verification.
- Grabowski, [Spec Growth Engine](https://arxiv.org/html/2606.27045), 2026: a
  design (no measurements) that blocks a merge when code and spec disagree, and
  has the agent update the spec in the same commit.
- Hartman, [Consort](https://arxiv.org/abs/2609.09671), September 2026: spec
  first, immutable tests, and a deterministic orchestrator with human-approved
  gates. A pre-registered hypothesis, no results yet.

## 2. Comparison table

| Idea or practice | Who does it (source) | Do we have it | Recommendation and why |
|---|---|---|---|
| Spec before code, judged by checks fixed before the build | Spec Kit, Kiro, BMAD TEA, Consort | Yes (judge fails on main, frozen bar) | Keep. Stronger than most: only BMAD TEA and Consort enforce red first mechanically. |
| Stable IDs on each criterion, trace both ways to tests | Kiro numbered criteria; Spec Kit FR/SC keys and analyze coverage; BMAD trace matrix; Tessl `[@test]` | No. Edge cases and flow steps have no IDs; judge is one command | Adopt. Gate checks every criterion has a test that names it and fails on main, and every test names a criterion. |
| Unchanged behaviour stated and tested | Kiro bugfix spec (Feb 2026) | No ("Not in this piece" is scope, not a guard) | Adopt as a spec field whose checks pass on main and must stay green. |
| Structured criterion grammar (EARS or Given-When-Then) | Kiro, OpenSpec (WHEN/THEN scenarios), Gherkin | Partly ("each case and its result", free text) | Adapt. A light lint shape ("When/If …, then …") for edge cases; no full EARS. |
| Vague-word and placeholder list | Spec Kit analyze | Partly (refused phrases) | Adopt the vague adjectives (fast, secure, intuitive, robust, scalable) unless a number follows. |
| Coverage taxonomy with Clear, Partial, Missing | Spec Kit clarify; AI Build Kit readiness list | Partly (needs come from missing fields only) | Adapt. Fixed categories each answered or marked "not applicable" with a reason, so a silent gap becomes a need. |
| Non-functional and measurable success criteria | Spec Kit SC-###; BMAD NFR audit | No field | Adopt a short "Limits" field: each measurable or "none". |
| Question cap, one at a time, recommended option, why it matters | Spec Kit clarify (max 5); specify (max 3 markers, rest guessed) | Partly (question box, labelled guess) | Adopt the cap and the "why it matters" line; low-impact unknowns become recorded assumptions, not questions. |
| Ambiguity by disagreement between independent readings | Kiro requirements analysis (semantic entropy) | No (one fresh checker) | Adopt cheaply: two fresh sessions list the tests they would write; differences become needs. |
| Formal logic solver for conflicts and gaps | Kiro | No | Skip for v1. Heavy, product-specific; the disagreement check gets part of the value. |
| Phase approvals by a person | Kiro, BMAD, Spec Kit checklist | Partly (person settles only the needs that name them) | Keep ours, but add one plain read-back of the criteria for the person (see item 4). Phase approvals cause review overload (Böckeler). |
| Size-fitted entry and a quick path | Kiro Quick Spec; BMAD entry levels; Anthropic "skip the plan" | Partly (length limits per type) | Adapt. Required fields depend on type and size. |
| Readiness verdict with waivers | BMAD PASS/CONCERNS/FAIL/WAIVED | Yes (BLOCKING versus NOTE; Accepted: line) | Keep. |
| Constitution checked against every spec | Spec Kit analyze | Partly (policy file, area map, sensitive areas) | Adapt. Lint the spec against the overview's named boundaries and sensitive areas; no separate constitution file. |
| Steering loaded by file pattern | Kiro steering; Agent OS inject-standards | Partly (AGENTS.md index) | Covered by the records research; skills and path-scoped rules serve this. |
| Exemplar code, visuals and files named in the spec | Agent OS references.md and visuals; Anthropic best practices | Partly ("Relies on") | Adopt a "Follow" line (existing code to imitate) and a link to any visual. |
| Research file with sources | Spec Kit research.md | Yes, stronger (dated, fingerprinted, re-checked at claim) | Keep. |
| Prototype or design first, then derive requirements | Kiro design-first; Agent OS visuals | Yes (prototype settles a need; crews) | Keep. Record the chosen prototype as a decision with its picture; never build on its code. |
| Converge: missing, partial, contradicts, unrequested | Spec Kit converge | Yes (review gap kinds) | Keep. |
| Behaviour deltas merged into living specs | OpenSpec ADDED/MODIFIED/REMOVED and archive | Partly (behaviour change applied to overview at merge) | Adopt a delta field the gate checks against the pull request. |
| Commit recorded at spec time, drift warned | Kiro request; Spec Growth Engine | Yes (fingerprint, relied-on code check at claim) | Keep; add the base commit to the fingerprint record. |
| One parser shared by every check | Lesson from OpenSpec validate and archive bug | Not stated | Adopt as a rule for the gate. |
| Property-based tests from rules | Kiro correctness | No | Adapt: allow property tests as an acceptance judge where a criterion is a rule over data. Not required. |
| Spec as source, code regenerated | Tessl (now de-emphasised) | No, by choice | Skip. Tessl itself moved away. |
| Agent may not tick its own checklist | Spec Kit checklist | Yes (gate writes the needs list and fingerprint) | Keep. |
| LLM as sole judge of spec quality | Common in BMAD and Spec Kit prose checks | Partly (fresh checker) | Do not rely on it alone; 47% recall and 11% false alarms (Shefa 2026). |

## 3. The ten most important things the design is missing or getting wrong

1. **No criterion-level traceability.** The judge is one command, so the gate
   knows the suite fails but not that each edge case and flow step has a test
   that fails for that reason. Give each criterion an ID (AC-1, EC-2), require
   every acceptance test to name one, and have the gate refuse a criterion with
   no failing test or a test with no criterion (Kiro numbered criteria, Spec Kit
   `analyze` coverage, BMAD trace matrix, Tessl `[@test]`).

2. **No "must stay the same" field.** "Not in this piece" says what is out of
   scope, not what must keep working. Add an unchanged-behaviour field whose
   checks pass on main at ready and are part of the frozen bar, the mirror of a
   judge that must fail (Kiro bugfix specs, February 2026). This also makes
   regressions a judged failure rather than a reviewer's catch.

3. **The ready gate trusts one LLM reading too much.** Current models find
   about half of requirement defects with an 11% false alarm rate, LLM help made
   people worse at inspection, and clarification collapses as ambiguities pile
   up (Shefa 2026; Broccia 2026; ClarifyCodeBench 2026). Make the fresh check
   produce something comparable: two independent sessions each list the tests
   they would write, and any disagreement with each other or with the judge
   becomes a need (adapting Kiro's semantic-entropy check). Many disagreements
   mean split the piece.

4. **Needs come only from missing fields, so missing categories go unseen.** A
   spec can fill every field and still say nothing about permissions, data kept,
   errors, empty states or what leaves the tool. Add a fixed coverage list where
   each category is answered or marked "not applicable" with a reason, so
   silence becomes a computed need (Spec Kit `clarify` taxonomy; AI Build Kit's
   readiness list). Finish with one plain read-back of the criteria that the
   person confirms, since Böckeler's review-overload warning is about long
   documents, not one short list.

5. **Same ceremony for every piece.** Every piece needs a user story, expected
   flow and a fresh check, but a one-line chore does not. Make required fields
   depend on type and size, with a quick path when the change fits in one
   sentence (Anthropic best practices; Kiro Quick Spec; BMAD entry levels;
   Böckeler, October 2025). Ceremony is the most cited failure of these tools.

6. **No limits or quality attributes.** The spec block has no place for
   speed, size, accessibility, security or cost limits. Add a short "Limits"
   field where each line is measurable or the field says "none", and add Spec
   Kit's vague adjectives (fast, secure, robust, scalable, intuitive) to the
   refused phrases unless a number follows (Spec Kit success criteria and
   `analyze`; BMAD NFR audit).

7. **Behaviour changes are not recorded as a delta.** Answer 10 applies each
   piece's behaviour change to the overview in the merge, but the spec has no
   field saying what changes, so the gate cannot check it was applied. Add
   "Changes to current behaviour" as added, changed and removed lines, and have
   the gate check that the pull request touches the named overview or document
   lines; kept acceptance tests are the living spec (OpenSpec deltas and archive;
   Spec Growth Engine, 2026).

8. **Questions have no budget and unknowns no "assumed" state.** Open questions
   carry a guess, but nothing caps how many reach the person or turns a
   low-impact one into a written assumption. Cap questions per sitting (Spec Kit
   asks at most five and keeps at most three markers), give each a "why it
   matters" line and a recommended answer, and record the rest under
   Decisions as "assumed by the agent, easiest to undo", marked for review.

9. **Edge cases are free text, so lint cannot judge them.** "Each case and its
   result" invites cases with no trigger or no observable result. Require a light
   shape, "When or If <trigger>, then <what is seen or stored>", with a concrete
   example value, so lint can refuse a case with no result (EARS, 2009; OpenSpec
   WHEN/THEN scenarios; Specification by Example). Do not adopt full EARS: the
   reader is not a requirements engineer.

10. **No single parser and no exemplar line.** OpenSpec shipped a bug where
    `validate` passed what `archive` refused because each parsed the spec its own
    way (September 2026); the gate, lint, needs list and fingerprint must share
    one parser and a versioned spec schema. Also add a "Follow" line naming
    existing code to imitate and any visual, since self-contained specs that name
    files, interfaces and an end-to-end check work best (Anthropic best
    practices; Agent OS `references.md` and visuals).
