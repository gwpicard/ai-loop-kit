# The records model: research for v1

Research for AI Loop Kit v1, 5 October 2026. Topic: answer 10 (the records
model), with answers 11 and 12 and research decisions D and F. It checks the
model against current practice on agent instruction files, memory, keeping
specs and docs in step with code, decision records, changelogs and drift.

The earlier notes (spec-driven.md, agentic-loops.md) already cover OpenSpec
deltas, Kiro steering in outline, the ETH Zurich context-file study in its
first version, ACE itemised lessons and Devin's stale knowledge warning. This
note does not repeat them except where a newer source changes the picture.

## 1. What leading practice says

### Instruction files: what goes in, and how long

- **Anthropic, Claude Code memory docs** ([memory](https://code.claude.com/docs/en/memory),
  read 5 October 2026). "Target under 200 lines per CLAUDE.md file. Longer
  files consume more context and reduce adherence." Imports organise a long
  file but "don't reduce its context cost". Keep to "facts Claude should hold
  in every session"; a multi-step procedure or a rule for one part of the code
  goes to a skill or a path-scoped rule in `.claude/rules/` with a `paths:`
  field, which loads only when Claude works on matching files. Contradicting
  instructions make Claude "pick one arbitrarily", so review them
  periodically; `/doctor prompt-audit` finds outdated rules, references to
  files or commands that do not exist, and contradictions, and changes nothing
  until asked. Instructions are "context, not enforced configuration"; to
  block an action, use a PreToolUse hook.
- **When to add a line** (same page). Add one when Claude makes the same
  mistake a second time, a review catches something Claude should have known,
  or you type the same correction again.
- **Claude Code reads AGENTS.md** natively since v2.1.277, but by default only
  when no `CLAUDE.md` exists in the folder or above it. A `CLAUDE.md` that
  imports `@AGENTS.md` works on every version and session type.
- **Anthropic, best practices** ([best practices](https://code.claude.com/docs/en/best-practices),
  read 5 October 2026). "For each line, ask: Would removing this cause Claude
  to make mistakes? If not, cut it." Include commands Claude cannot guess,
  style rules that differ from defaults, test instructions, branch and pull
  request etiquette, project-specific architectural decisions, environment
  quirks and gotchas. Exclude what Claude can read from the code, standard
  conventions, detailed API docs, "information that changes frequently", and
  "file-by-file descriptions of the codebase". "If Claude already does
  something correctly without the instruction, delete it or convert it to a
  hook." Emphasis on one line only.
- **Anthropic, extension overview** ([features overview](https://code.claude.com/docs/en/features-overview),
  read 5 October 2026). Context cost by feature: CLAUDE.md costs every
  request; skills cost a description until used; hooks cost nothing. "Put
  guardrails in hooks." Subagents load CLAUDE.md unless their definition sets
  `omitClaudeMd`; the built-in Explore and Plan agents omit it.
- **Anthropic, context engineering** ([post, 29 September 2025](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)).
  Aim for "the smallest set of high-signal tokens". A hybrid works best: a
  small file loaded up front, the rest fetched just in time through paths and
  tools. Structured notes kept outside the context window carry state across
  long tasks.
- **AGENTS.md standard** ([agents.md](https://agents.md/), read 5 October 2026).
  Plain Markdown, no required sections and no length rule. Suggested sections:
  overview, build and test commands, code style, testing, security, commit and
  pull request rules, deployment. Nested files in subfolders; the nearest file
  wins. Stewarded by the Agentic AI Foundation under the Linux Foundation.
- **OpenAI, harness engineering** (11 February 2026; the page refused the fetch,
  so these points come from secondary summaries such as
  [this one](https://github.com/celesteanders/harness/blob/main/docs/research/260211_openai_harness_engineering_codex.md)).
  AGENTS.md of about 100 lines as "the table of contents, not the
  encyclopedia", pointing into a structured `docs/` folder (design docs,
  execution plans, product specs, references). Linters and CI check the
  knowledge base is current and cross-linked, and a recurring "doc-gardening"
  agent opens fix-up pull requests for stale docs.
- **Thoughtworks Technology Radar vol. 34** ([techniques, April 2026](https://www.thoughtworks.com/en-us/radar/techniques)).
  "Agent instruction bloat" at Caution: files "become long and sometimes
  conflict"; "be deliberate and selective ... continuously refine toward a
  minimal, coherent set". "Curated shared instructions" and "context
  engineering" at Adopt, with "progressive context disclosure".

### Evidence on context files

- **Gloaguen and others, ETH Zurich** ([arXiv 2602.11988](https://arxiv.org/abs/2602.11988),
  first version 12 February 2026, final version 29 September 2026). The final
  version is stronger than the first: context files "do not generally improve
  task success rates" and raise cost by over 20%. Repository overviews do not
  help, although providers recommend them. Agents do follow the instructions
  in the files. Advice: keep files to non-standard, repository-specific
  practice, and evaluate before adopting.
- **Khatri** ([arXiv 2607.27250](https://arxiv.org/abs/2607.27250), July 2026;
  read through a [summary](https://codex.danielvaughan.com/2026/08/06/do-context-files-help-coding-agents-agents-md-ablation-study-codex-cli-correctness-vs-efficiency/)).
  288 paired runs, Claude Code and Codex CLI: no measurable change in
  correctness (at most 2.3 and 5.9 points). The one gain was operational: a
  line warning that the full suite is slow cut full-suite runs from 3.67 to
  1.67 and wall time by about 24%.
- **Lulla and others** ([arXiv 2601.20404](https://arxiv.org/abs/2601.20404),
  January 2026). 124 pull requests in 10 repositories: with AGENTS.md, median
  runtime fell 28.6% and output tokens 16.6%, with similar completion.
- **Chatlatanagulchai and others, "Agent READMEs"** ([arXiv 2511.12884](https://arxiv.org/abs/2511.12884),
  November 2025, revised August 2026). 2,303 files in 1,925 repositories.
  Files "evolve like configuration code through frequent, small additions"
  and become hard to read. Security (14.8%) and performance (14.5%) are rarely
  stated.
- **Chakrabarti, "Why does CLAUDE.md keep growing?"** ([arXiv 2608.11095](https://arxiv.org/abs/2608.11095),
  11 August 2026). 247,694 instruction lifetimes in 1,867 repositories: files
  more than triple over their life (+226%), gaining 4.9 net instructions per
  commit. Old lines stay because proving a deletion safe gets harder as the
  file grows. Writing the reason beside each instruction removed 99.3% of
  excess instructions in a controlled setting and improved instruction
  following by up to 23.1% in real use.
- **Galster and others** ([arXiv 2602.14690](https://arxiv.org/abs/2602.14690),
  February 2026, revised June 2026). 2,853 repositories: context files are by
  far the most used mechanism, AGENTS.md is becoming the shared standard, and
  few projects use skills, hooks or subagents.

Reading across these: a short file of commands, non-obvious rules and
pointers saves time and is followed; overviews and long descriptions cost
tokens and do not raise success; files grow unless something forces pruning,
and a written reason per line is what makes pruning safe.

### Memory

- **Claude Code auto memory** ([memory docs](https://code.claude.com/docs/en/memory#auto-memory),
  read 5 October 2026). Claude writes its own notes to a `MEMORY.md` index
  plus topic files, per repository and shared across worktrees, but
  machine-local and not in git. The first 200 lines or 25 KB load every
  session. It is on by default in local sessions and can be switched off with
  `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`.
- **Stale memory.** Devin warns one outdated knowledge item degrades every
  session (in agentic-loops.md). Helwig ([arXiv 2609.05510](https://arxiv.org/abs/2609.05510),
  31 August 2026), a single case study of months-long Claude Code use, found
  memory needed reliability engineering (health checks at session start,
  precision-gated injection) to avoid silent failures. ACE (in
  agentic-loops.md) found itemised, pruned lessons help.

### Keeping specs and docs in step with code

- **OpenSpec** ([concepts](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md),
  read 5 October 2026). Living specs per domain in `openspec/specs/`. Each
  change carries ADDED, MODIFIED and REMOVED deltas; archive merges them into
  the living spec. Design notes and task lists move to an archive folder and
  never merge into the living spec. Deltas let several changes touch one spec
  file without conflict.
- **Kiro steering** ([steering](https://kiro.dev/docs/steering/), read
  5 October 2026). `product.md` (purpose, users, objectives), `tech.md` and
  `structure.md`, loaded always, by file pattern, by hand or by description.
  `#[[file:path]]` links live files so steering does not copy code. "Treat
  steering updates like code changes requiring review."
- **Spec Kit** (in spec-driven.md): keeping spec and code in step "requires
  discipline"; drift repair is left to extensions.
- **Fiberplane Drift** ([blog](https://blog.fiberplane.com/blog/drift-documentation-linter/),
  2026). Docs are anchored to code in frontmatter as path, optional symbol and
  the commit last reviewed (`src/auth/provider.ts#AuthConfig@a1b2c3d`). CI
  compares a tree-sitter fingerprint of the symbol then and now, and fails on
  a change until a person updates the prose and re-links. It is aimed at
  agents changing code without knowing which docs depend on it, and uses no
  model.
- Other deterministic drift tools check that code examples in Markdown still
  run ([docs-drift](https://github.com/georg-nikola/docs-drift)) or still
  match the code ([doc-drift](https://github.com/sunnydachs/doc-drift)).

### Decisions: records in the repository or on issues

- **ADRs** ([adr.github.io](https://adr.github.io/); Nygard 2011). One short
  record per significant decision, kept in a decision log in the repository.
- **Davidson, "Coding agents love decision records"** ([O'Reilly Radar,
  2 October 2026](https://www.oreilly.com/radar/coding-agents-love-decision-records/)).
  Records in the repository spare agents "trawling through issues, searching
  chats and code archaeology". Risks: agents apply outdated decisions too
  rigidly, and records turn into "courtroom transcripts". Advice: current
  text only with rationale, a status (accepted, proposed, superseded), git
  history as the amendment log, and an instruction to stop and raise a
  conflict between a task and an accepted decision.
- **Rust RFCs** ([rust-lang/rfcs](https://github.com/rust-lang/rfcs), read
  5 October 2026). The decision text is merged into the repository and not
  changed afterwards; the discussion and tracking live in issues and pull
  requests; a rationale comment is added when the thread is unclear.
- **Lore** ([arXiv 2603.15566](https://arxiv.org/abs/2603.15566), 16 March
  2026). Names the "decision shadow": a commit keeps the diff and loses the
  reasoning. Proposes decision trailers in commit messages. No measurements.

### Changelogs from merged work

- **Keep a Changelog 1.1.0** ([keepachangelog.com](https://keepachangelog.com/en/1.1.0/)).
  "Changelogs are for humans"; Added, Changed, Deprecated, Removed, Fixed,
  Security; an Unreleased section; "using commit log diffs as changelogs is a
  bad idea: they're full of noise".
- **Changesets** ([intro](https://github.com/changesets/changesets/blob/main/docs/intro-to-using-changesets.md)).
  One file per change, written in the pull request while intent is fresh, so
  changes never conflict in one shared file; consumed into the changelog at
  release.
- **release-please** ([repository](https://github.com/googleapis/release-please)).
  Builds the changelog from Conventional Commit prefixes in a standing release
  pull request; advises squash merges.
- **GitHub generated release notes** ([docs](https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes)).
  A list of merged pull requests, grouped by label through `.github/release.yml`.

### Area ownership

- **CODEOWNERS** ([docs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)).
  Gitignore-style patterns, last match wins, invalid lines reported in the
  interface and the API. A proven, familiar format for mapping paths to an
  owner, which an area map can copy.

## 2. Our records model against the evidence

| Element of our records model | Confirmed, adjust or missing | Evidence | Recommendation |
|---|---|---|---|
| One home per fact | Confirmed | OpenAI table of contents; Anthropic "contradicting instructions are picked arbitrarily"; Davidson current text only | Keep. Make it checkable: a fact type table (below) names each home, and the drift check refuses a copy. |
| AGENTS.md as an index, about 150 lines | Confirmed, adjust | Anthropic under 200 lines; OpenAI about 100; ETH 2026 final: overviews do not help, instructions are followed; Khatri: the gain is operational lines | Keep at 150 as a hard check. Fill it with commands, non-obvious rules and pointers. No product overview inside it and no `@` import of the overview, since imports load in full. |
| Line growth control | Adjust | Chakrabarti: +226% growth, 4.9 lines per commit, reasons per line cut excess 99.3%; Radar Caution on bloat | Every rule line carries a short reason and its origin (a lesson, a review, a person). Pruning asks Anthropic's question per line. A rule a hook or check can hold is moved there and the line deleted. |
| Area-specific rules | Missing | Anthropic path-scoped rules; Kiro fileMatch steering | One optional `.claude/rules/<area>.md` per area, with `paths:` taken from the area map, for rules that matter in one area only. Loaded only there. |
| CLAUDE.md and AGENTS.md together | Adjust | Claude Code reads AGENTS.md only when no CLAUDE.md exists, and only from v2.1.277 | Ship `CLAUDE.md` containing only `@AGENTS.md`, so every session type and version loads one file. |
| Short project overview (what, who, areas, sensitive areas) | Confirmed, adjust | Kiro product.md; ETH: overviews do not help coding success | Keep it, but for people and for shaping, read on demand. Builders get the frozen spec, not the overview. Cap it. |
| Area map with a check that every folder belongs to an area | Confirmed, adjust | CODEOWNERS pattern format; OpenAI mechanical checks on docs | Machine-readable file, gitignore-style patterns, last match wins. Check every tracked file (not only folders) matches an area, every area matches a file, and sensitive flags agree with the overview. Run on every pull request. |
| Decisions on the pieces (issues) | Adjust | Davidson: agents should not have to trawl issues; Rust RFCs: decision text in repo, discussion in issues; Lore: decision shadow | Keep the full decision and its discussion on the issue. A decision that constrains future work in an area also gets one line (decision, reason, link) in that area's doc in the same pull request. Builders without network still see it. |
| Behaviour change applied to overview or docs in the merge | Confirmed | OpenSpec ADDED, MODIFIED, REMOVED and archive; Spec Growth Engine; decision D | Keep, with the delta as a structured spec field. The gate checks the pull request changes each named doc line. Kept acceptance tests are the executable half of the living spec. |
| Docs bound to code | Missing | Fiberplane Drift anchors with commit and fingerprint; Kiro live file links | Area docs may anchor a section to a file or symbol with the commit last reviewed. A changed fingerprint in a pull request without a doc change is a warning in CI and a finding in /maintain. |
| Changelog written from merged pieces | Confirmed, adjust | Keep a Changelog for humans; Changesets one file per change avoids conflicts; release-please and GitHub notes from merged work | Write each entry from the piece's behaviour delta (Added, Changed, Removed, Fixed, Security), one file per piece on the run branch, folded into `CHANGELOG.md` at merge. Never from commit messages. |
| Scratch build files never reach main | Confirmed, adjust | OpenSpec keeps design and tasks out of living specs; principle of two layers (answer 9) | Keep. Hold it in two layers: the gate strips them before join, and a CI path check refuses a pull request to main that contains any scratch path. |
| Risk acceptance on the issue | Confirmed | BMAD WAIVED needs a named person's documented exception (spec-driven.md) | Keep. The acceptance is inside the fingerprinted spec, so a later edit to the issue is detected. The run pull request quotes it beside the piece. |
| Lessons become checks first, and are pruned | Confirmed | Anthropic "convert it to a hook"; ACE itemised pruning; Devin stale items; decision F | Keep. A lesson that cannot be a check becomes one reasoned line in AGENTS.md with its evidence and date, and is offered for removal when unused. |
| Agent memory | Missing | Claude Code auto memory is on by default, machine-local, unreviewed, loads 200 lines | Switch auto memory off for builder, reviewer and gate sessions, so unreviewed notes cannot steer a run. The person's own interactive memory is theirs. Anything worth keeping becomes a check, a rule line or a doc change through a piece. |
| /maintain checks drift every 2 weeks | Adjust | OpenAI CI checks plus a recurring doc-gardening agent; Anthropic prompt audit | Split it. Deterministic drift checks run on every pull request (sizes, links and paths, area coverage, scratch paths, changelog entry, delta applied). The two-week /maintain does the judgement read (stale prose, contradictions, unused rules, outdated decisions) and files findings as shaping issues. |
| Non-functional facts | Missing | Agent READMEs: security and performance stated in about 15% of files | The overview's area table records each sensitive area's boundary in one line; performance limits live on pieces (the Limits field) and, once settled, in the area doc. |

## 3. The best version of the records model

The rule: every fact has one home, named in the table below. A fact anywhere
else is a pointer to that home, never a copy. Anything a check can hold is a
check, not a sentence.

**`AGENTS.md`** (with `CLAUDE.md` holding only `@AGENTS.md`).
- Holds: the commands (install, test, a single test, lint, run); the
  non-obvious rules, each with a short reason and its origin; the guarded
  actions and where they are enforced; pointers to the overview, area map,
  docs index and changelog.
- Holds nothing about what the product is, no history, no dates, no issue
  lists, no file-by-file description.
- Limit: 150 lines, checked on every pull request; each section 12 lines or
  fewer.
- Written by: /setup at founding; changed only through a piece or an approved
  /maintain finding.
- Checks: line ceiling; every path and command it names exists; no line
  duplicates a hook or check; at /maintain, each rule line is asked "would
  removing this cause a mistake", and unused rules are offered for removal.

**`.claude/rules/<area>.md`** (optional, one per area that needs it).
- Holds: conventions that apply only in that area, with `paths:` copied from
  the area map. 40 lines each.
- Checks: its `paths:` match the area map.

**`docs/overview.md`**.
- Holds: what the product is, who it is for, what it is not, how it goes live,
  and the area table (name, one-line purpose, sensitive yes or no, the
  boundary in one line for a sensitive area, the area doc).
- Read by people and by shaping on demand. Not imported into AGENTS.md and not
  given to builders.
- Limit: 100 lines.
- Written by: /setup; changed only by a piece's behaviour delta or a risk
  acceptance, in that piece's merge.
- Checks: areas and sensitive flags agree with the area map.

**`areas` map** (a machine-readable file, gitignore-style patterns, last
match wins).
- Holds: each area's patterns. No prose.
- Checks, on every pull request: every tracked file falls in an area; every
  area matches at least one file; a piece's declared touches name real areas.

**`docs/<area>.md`** plus a short `docs/README.md` index.
- Holds: current behaviour of that area as short requirement lines, and the
  decisions still in force there, each as one line with its reason and a link
  to the piece. Current text only; git history is the amendment log.
- Optional anchors to a file or symbol with the commit last reviewed.
- Limit: 300 lines per file; past that, the area is split.
- Written by: the merge of each piece, which applies the piece's Added,
  Changed and Removed lines.
- Checks: the gate refuses a merge whose delta names a doc that the pull
  request did not change; an anchored symbol whose fingerprint changed
  without a doc change is flagged.

**The piece (GitHub issue)**.
- Holds: the spec, research, the full decisions and their discussion, the
  behaviour delta, the risk notice with the person's exact words and date, and
  the run evidence summary.
- Fingerprinted at ready, so later edits are detected.
- Lasts after closing as the record of why.

**`CHANGELOG.md`**.
- Holds: one entry per merged piece, written from its delta under Added,
  Changed, Removed, Fixed and Security, in plain words, with the piece link.
- Written by: the gate as one file per piece on the run branch, folded at
  merge. Never from commit messages.
- Checks: every piece closed by the merge has an entry.

**Scratch files** (attempt notes, frozen spec copy, judge logs, run state).
- Live only on the piece and run branches.
- Checks: the gate strips them before join, and a CI path check refuses a pull
  request to main that contains one.

**Lessons**.
- Become a check, a hook or a lint first. Only if that is impossible, one
  reasoned line in AGENTS.md with its evidence and date.
- Auto memory is off in every run session.

**Drift**.
- Every pull request: the mechanical checks above.
- Every 2 weeks, /maintain: a judgement read of AGENTS.md, rules, overview and
  area docs against the code; a prompt audit for contradictions and dead
  references; unused rules and superseded decisions. Findings become shaping
  issues; small tidying is done directly and logged.

## Notes on uncertainty

- The OpenAI harness engineering post refused the fetch; its points come from
  secondary summaries.
- Khatri's study was read through a practitioner's summary; the numbers match
  the paper's listing but the paper itself was not read in full.
- Chakrabarti's 99.3% figure is from a controlled setting; the real-world gain
  is the smaller "up to 23.1%".
- The size limits for the overview (100), area docs (300) and area rules (40)
  are judgement, not measured. The 150 for AGENTS.md sits inside Anthropic's
  200 and above OpenAI's 100.
