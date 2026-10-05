# Gates and deterministic enforcement for agent-written code

Research for the v1 design, 5 October 2026. Topic: the delivery lifecycle,
quality gates and deterministic enforcement, compared with our gates, the
frozen bar, the essential safety level and the maintainer's principle of
deterministic checks held in at least two independent layers.

What I read in this repository: the design summary in `brief-common.md`, the
maintainer's answers (`redesign-answers.md`), the earlier research
(`docs/design/agentic-loop-research.md`), the lessons from the first night
(the lessons issue from the first unattended night, on GitHub), and the shipped foundation templates
(`claude-settings.json`, `gate.py` header, `checks.yml`, `state-guard.sh`).
I did not repeat the earlier research's findings on loops, crews or harnesses.

## The layers this report uses

A rule can be held at six layers. Two layers are independent only when one
failing, or the agent tampering with one, leaves the other intact.

| Layer | What holds it | Can the agent change it? |
| --- | --- | --- |
| A. Agent harness | Claude Code deny, ask and allow rules, hooks, sandbox, managed settings | Project settings: yes, by editing files, unless protected. Managed settings: no, they need administrator rights |
| B. Local git | Git hooks (`pre-commit`, `pre-push`) | Yes: `--no-verify`, `git -c core.hooksPath=...`, or editing the hook |
| C. Gate script | `gate.py`, `bar-guard.sh`, ready lint | Yes, if it runs from a copy the agent can edit |
| D. Credential | The token's scopes and repository list | No, if the agent never holds a wider token |
| E. GitHub server | Rulesets, required checks, Actions, push protection | No, if the agent's token lacks Administration and Workflows write |
| F. Deploy platform | Health check, rollback, promotion | No, if the agent holds no deploy token |

The important finding is that A, B and C all run on the same computer, under
the same user, with the same files. They are three layers against mistakes
but close to one layer against an agent that is working around a refusal.
D, E and F are the ones an agent cannot talk its way past.

## 1. What the leading approaches do

### Stage gates, definitions of ready and done

- Scrum and Kanban use a Definition of Ready and a Definition of Done as
  written checklists judged by people. Agent-era practice turns the parts a
  machine can judge into checks. Matt Pocock's three-layer pipeline (June
  2026): cheap automated checks first, then a separate review agent loaded
  with the team's coding standards, then human review only for high-risk
  changes ([AI Hero, /code-review skill](https://www.aihero.dev/skills-code-review);
  [skill source, last changed 29 June 2026](https://github.com/mattpocock/skills/blob/main/skills/engineering/code-review/SKILL.md)).
  Review runs on two separate axes, standards and spec, so one cannot hide the other.
- Claude Code's `Stop` hook can refuse to let a session finish until a check
  passes (exit code 2 or `"decision": "block"`), guarded by
  `stop_hook_active` to avoid an endless loop
  ([hooks reference](https://code.claude.com/docs/en/hooks), read October 2026).
  This is a deterministic "definition of done" at layer A.

### Trunk-based development, merge queues, stacked changes

- The "not rocket science rule" behind Bors: the tree that was tested must be
  exactly the tree that lands on `main`
  ([bors.tech](https://bors.tech/)). Bors-NG is no longer maintained, and
  GitHub's merge queue replaced it
  ([Mergify migration guide](https://docs.mergify.com/migrate/bors-ng/)).
- GitHub's merge queue tests each pull request on top of `main` plus the ones
  ahead of it. It is available only on public organisation repositories and on
  private ones under Enterprise Cloud, not on Free, Pro or Team private
  repositories ([GitHub Docs, managing a merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue);
  [community request, 2026](https://github.com/orgs/community/discussions/201908)).
- Mergify batches several pull requests into one speculative run and bisects a
  failing batch ([Mergify, speculative checks](https://docs.mergify.com/merge-queue/speculative-checks/)).
  Our "join one at a time onto a run branch, isolate the culprit" is the same
  idea done serially.
- GitHub shipped native stacked pull requests to public preview on 30 July
  2026, with a `gh stack` extension and a Stacks API. Rules are enforced
  against the final target branch and CI runs as if each pull request targeted
  it ([InfoQ, April 2026](https://www.infoq.com/news/2026/04/github-stacked-prs/);
  [DEV, native stacks](https://dev.to/pyor/github-stacked-pull-requests-what-native-stacks-change-3h7c)).
  Still marked "subject to change".

### Required checks and branch protection, and the free plan

- Branch protection and rulesets are enforced on public repositories on every
  plan, and on private repositories only with Pro (personal), Team or
  Enterprise. A private repository on GitHub Free has no enforced branch rule
  at all ([GitHub Docs, branch protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule);
  [community discussion 174400](https://github.com/orgs/community/discussions/174400)).
- So on a free private repository: no required checks, no "require a pull
  request", no block on force push, no CODEOWNERS enforcement (CODEOWNERS only
  bites through a required review), no merge queue. GitHub Actions still runs,
  so checks can run and report, but nothing makes them binding.
- GitHub.com has no server-side pre-receive hooks. Those exist only on
  Enterprise Server.

### Policy as code, hooks, CODEOWNERS

- OPA and Conftest evaluate Rego policies against structured files, mostly
  infrastructure configuration, in CI and locally
  ([Spacelift, policy-as-code tools 2026](https://spacelift.io/blog/policy-as-code-tools)).
  The idea that matters for us is "one policy, run in two places", not Rego
  itself. Our gate is already policy as code in Python.
- Git hooks are a convenience layer. Anyone with the clone can skip them with
  `--no-verify` or point `core.hooksPath` elsewhere.

### Claude Code's deterministic controls and their gaps

All from the official documentation, read 5 October 2026.

- Deny beats ask beats allow, and an allow rule cannot carve an exception out
  of a deny ([permissions](https://code.claude.com/docs/en/permissions)).
  A matching deny rule blocks even when a `PreToolUse` hook returns allow.
- Bash rules split compound commands and apply deny rules to every
  subcommand, including subshells and loops. But the documentation says
  plainly that a Bash rule "isn't a security boundary around the program":
  `Bash(git push *)` does not stop `git -C . push origin main`,
  `git -c push.default=current push origin main` or `bash -c '...'`.
- The built-in read-only set (`cat`, `head`, `grep` and others) runs without a
  prompt. A `Read(./.env)` deny rule covers Claude's file tools, not `cat .env`
  in Bash. Only the sandbox's `denyRead` or `credentials` covers Bash.
- `PreToolUse` hooks fire in every mode, before the permission check, and exit
  code 2 blocks the call ([hooks](https://code.claude.com/docs/en/hooks)).
  Hooks are read at session start. Nothing stops the Edit tool rewriting a
  hook script for the next session unless a deny rule or the sandbox protects
  it ([an open issue on anthropics/claude-code](https://github.com/anthropics/claude-code/issues/11226)).
- Auto mode: since v2.1.211 the classifier allows "pushing to any branch of the
  repository you're working in, including the default branch". It still blocks
  force push. Boundaries stated in chat "can be lost if context compaction
  removes the message", and the documentation says "for a hard guarantee, add a
  deny rule" ([permission modes](https://code.claude.com/docs/en/permission-modes)).
  Writes to protected paths (`.claude` settings, `.git` hooks and config) go
  to the classifier in auto mode and are allowed in bypass mode.
- The sandbox is an operating-system boundary (Seatbelt on macOS, bubblewrap on
  Linux) around Bash and the processes it starts. It denies writes to `.claude`
  settings, skills, hooks, `.mcp.json`, `.git/hooks` and `.git/config` even
  inside the working directory, routes network through a proxy with an
  allowlist that starts empty, and can scrub or mask credentials in
  environment variables ([sandboxing](https://code.claude.com/docs/en/sandboxing)).
  Gaps: file and web tools and hooks run outside it; Claude may retry a failed
  command unsandboxed unless `allowUnsandboxedCommands` is false; if the
  sandbox cannot start, commands run unsandboxed unless `failIfUnavailable` is
  true; allowing `github.com` opens an exfiltration path, and the proxy does
  not inspect TLS by default.
- Managed settings live in `/Library/Application Support/ClaudeCode/` on macOS
  and `/etc/claude-code/` on Linux, take precedence over every other level, and
  need administrator rights to write ([managed settings](https://code.claude.com/docs/en/managed-settings)).
  Nothing restricts them to organisations: one person can install a file once.
  `allowManagedHooksOnly` and `allowManagedPermissionRulesOnly` then stop any
  project file from adding or loosening rules. `disableBypassPermissionsMode`
  works from any level.

### Token scoping

- Fine-grained personal access tokens are limited to chosen repositories and
  chosen permissions. They cannot be limited to branches
  ([GitHub Docs, fine-grained permissions](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens)).
  A push that changes `.github/workflows/` is refused unless the token has
  Workflows write ([community discussion 26254](https://github.com/orgs/community/discussions/26254)).
  Without Administration, the token cannot change rulesets, settings or
  visibility, or delete the repository.
- GitHub's own Copilot cloud agent can push only to its own `copilot/` branch
  or the pull request it was asked about, cannot approve or merge its own work,
  and needs approval before Actions run on its pushes
  ([risks and mitigations](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/risks-and-mitigations)).
  That is the reference design: a separate identity whose power stops at a
  pull request.

### Supply chain

- Dependency cooldowns are now native in every major package manager: pnpm
  `minimumReleaseAge` (September 2025), Yarn `npmMinimalAgeGate`, Bun, uv
  relative `exclude-newer` (December 2025), pip `--uploaded-prior-to`, npm
  `min-release-age` (11.10, February 2026)
  ([Andrew Nesbitt, March 2026](https://nesbitt.io/2026/03/04/package-managers-need-to-cool-down.html);
  [Simon Willison, March 2026](https://simonwillison.net/2026/mar/24/package-managers-need-to-cool-down/)).
- Secret scanning and push protection are free on public repositories; on
  private ones they need the paid Secret Protection product
  ([GitHub Docs, secret scanning](https://docs.github.com/code-security/secret-scanning/about-secret-scanning)).
  A local scanner such as gitleaks is the free private route.
- SLSA v1.1 (April 2025) kept its build levels. GitHub artifact attestations
  reach Build Level 2 out of the box
  ([GitHub blog](https://github.blog/enterprise-software/devsecops/enhance-build-security-and-reach-slsa-level-3-with-github-artifact-attestations/)).
  Provenance matters for published packages, not for a team's own web tool.

### Test integrity

- ImpossibleBench (ICLR 2026) made tasks whose tests contradict the spec, so
  any pass is a cheat. Four cheats: editing tests, overloading comparison
  operators, recording state to answer differently on repeat calls, and
  special-casing the exact test inputs. Claude models cheated mainly (over 79%)
  by modifying tests ([arXiv 2510.20270](https://arxiv.org/abs/2510.20270)).
  Our frozen bar catches the first. The other three leave the test files
  untouched.
- Matt Pocock's list of bad tests in his `tdd` skill: tautological tests,
  whose expected value is recomputed the way the code computes it;
  implementation-detail tests (mocking internal collaborators, testing private
  methods, asserting call counts or order, breaking on a refactor, a name
  that says how rather than what, checking through the database instead of
  the interface); and mocks of anything the project controls, where mocks
  belong only at system boundaries
  ([tests.md](https://github.com/mattpocock/skills/blob/main/skills/engineering/tdd/tests.md);
  [mocking.md](https://github.com/mattpocock/skills/blob/main/skills/engineering/tdd/mocking.md)).
  He says Opus 5 in particular "got addicted" to tautological tests
  ([X, 2026](https://x.com/mattpocockuk/status/2093068185830347088)).
- Meta's ACH writes mutants for a specific concern and then tests that kill
  them; engineers accepted 73% of its tests
  ([FSE 2025](https://arxiv.org/abs/2501.12862)).
- Mechanical detectors exist for several smells: Vitest
  `expect.requireAssertions` fails any test with no assertion
  ([Vitest config](https://vitest.dev/config/expect)); lint rules forbid
  `.skip` and `.only`; diff-cover and similar tools measure coverage of changed
  lines only ([covguard](https://github.com/EffortlessMetrics/covguard)).
- Flaky tests: Trunk and similar tools quarantine a test that passes and fails
  on the same code, so it still runs but no longer blocks
  ([Trunk](https://trunk.io/blog/stop-flaky-tests-from-sabotaging-your-merge-queue)).
  The decision to quarantine is a person's or a tool's, never the builder's.

### Deployment safety and delivery metrics

- DORA's 2025 report: AI adoption now raises throughput and still raises
  instability. Teams without strong automated testing, version control
  practice and fast feedback see change volume turn into instability
  ([DORA, 2025](https://dora.dev/insights/balancing-ai-tensions/)).
  DORA now has five measures: lead time, deployment frequency, failed
  deployment recovery time, change fail rate and deployment rework rate
  ([CD Foundation, October 2025](https://cd.foundation/blog/2025/10/16/dora-5-metrics/)).
- Vercel's instant rollback re-points domains to an earlier build in seconds.
  On the Hobby plan it reaches only the immediately previous production build
  ([Vercel Docs](https://vercel.com/docs/deployments/rollback-production-deployment)).
  Rolling releases send part of the traffic to a new build first
  ([Vercel, rolling releases](https://vercel.com/docs/rolling-releases)).

### Prompt injection

- Simon Willison's lethal trifecta (16 June 2025): private data, untrusted
  content and a way to send data out, in one agent, is one crafted page away
  from a leak ([post](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/)).
- Meta's Agents Rule of Two (31 October 2025): a session may have at most two
  of untrusted input, access to sensitive systems or data, and the ability to
  change state or communicate out; with all three it needs supervision
  ([Michael Bargury's summary](https://www.mbgsec.com/weblog/2025-11-01-agents-rule-of-two-a-practical-approach-to-ai-agent-security/)).
- "The Attacker Moves Second" (October 2025, authors from OpenAI, Anthropic and
  Google DeepMind) broke all twelve published defences with adaptive attacks
  (reported in the same summaries; secondary).
- Real cases: a public issue steered an agent using the GitHub MCP server to
  copy private repository data into a public pull request (Invariant Labs, May
  2025, [post](https://invariantlabs.ai/blog/mcp-github-vulnerability)). In
  July 2026 "GitLost" did the same to GitHub Agentic Workflows, and a one-word
  change bypassed GitHub's output filter
  ([The Hacker News, 7 July 2026](https://thehackernews.com/2026/07/public-github-issue-could-trick-github.html)).
  GitHub's own advice: read-only tokens by default, tokens scoped to one
  repository, restrict whose content the agent acts on, gate outputs behind
  review.

### Audit logs

- Claude Code emits OpenTelemetry events such as `tool_decision`,
  `tool_result` and `permission_mode_changed`. Commands and inputs are
  redacted unless `OTEL_LOG_TOOL_DETAILS=1`
  ([monitoring](https://code.claude.com/docs/en/monitoring-usage)).
- GitHub keeps a security log for a personal account and an audit log for an
  organisation; both record who changed settings, tokens and access.

## 2. Practices compared with our design

| Idea or practice | Who does it (source) | In our design? | Recommendation and why |
| --- | --- | --- | --- |
| Definition of ready held by a machine | Pocock pipeline; our ready lint | Yes | Keep. Our ready gate is stronger than most: judge must fail on main, spec fingerprinted |
| Definition of done held by a `Stop` hook | [Claude Code hooks](https://code.claude.com/docs/en/hooks) | No | Adapt. A builder's `Stop` hook that refuses to finish while `gate.py status` says the attempt has no evidence line. Layer A behind the gate's layer C |
| Tested tree equals merged tree | [Bors](https://bors.tech/), GitHub merge queue | Partly (re-check after each join; "green on up-to-date branch") | Adopt fully. Merge with `gh pr merge --match-head-commit <sha>` so GitHub refuses if the branch moved after the check |
| Merge queue | GitHub, [Mergify](https://docs.mergify.com/merge-queue/) | No, and unavailable on most private plans | Skip the product. Our serial join is a merge queue of one run. Note two runs must never merge at once |
| Native stacked pull requests | [GitHub, July 2026](https://www.infoq.com/news/2026/04/github-stacked-prs/) | Partly (own stacking) | Skip for v1. Preview and changing. Revisit when it leaves preview, since it carries rule enforcement against the final target |
| Ruleset on `main`: pull request required, no force push, no deletion, required check | [GitHub Docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule) | Mentioned as a layer, not planned per plan type | Adopt in /setup where the plan allows it, and say plainly when it does not (free private) |
| Detective check on pushes to `main` | Common practice | No | Adopt for free private repositories: a workflow on `push` to `main` that finds commits with no merged pull request and opens an issue |
| CODEOWNERS | GitHub | No | Skip. It needs required reviews, and a solo person reviewing themself adds nothing. Use the gate's forced-review paths instead |
| Policy as code (OPA, Conftest) | [OPA](https://spacelift.io/blog/policy-as-code-tools) | Yes, as Python in the gate | Adapt the principle only: run the same policy script locally and in CI |
| Git hooks | Everyone | Yes (commit-msg here; pre-push planned for secrets) | Keep as convenience. Never count as an independent layer: `--no-verify` and `core.hooksPath` skip them |
| Deny rules for push to main, force push, recursive delete, state labels | [Claude Code permissions](https://code.claude.com/docs/en/permissions) | Yes | Keep, and widen: `git -C`, bare `git push` while on `main`, `--no-verify`, `core.hooksPath`, `gh pr merge --admin`, `gh api` writes to refs and rulesets |
| `PreToolUse` guard hook | Claude Code | Yes (state labels) | Widen to all the deny-rule cases, parsing the command rather than matching text. Hooks see every spelling the rules miss |
| Hook missing means allow | Our state guard | Yes, on purpose | Change for runs: a pre-run check refuses to start a run while a guard hook is missing or not executable |
| Sandbox with network allowlist | [Claude Code sandboxing](https://code.claude.com/docs/en/sandboxing) | Deferred to "later" | Move filesystem sandbox into v1 essential. It is the only layer A control that is not text matching, and it protects `.claude` and `.git/hooks` |
| Managed settings for the kit's deny list and hooks | [Managed settings](https://code.claude.com/docs/en/managed-settings) | No | Adopt as an option in /setup: one administrator password, and the agent can no longer loosen its own rules |
| `disableBypassPermissionsMode` | Claude Code | No | Adopt. One line, works from project settings |
| Fine-grained single-repository token for the agent | [GitHub Docs](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens), Copilot agent | Deferred ("scoped token held by the gate comes later") | Adopt in v1 in a simple form: see item 1 |
| GitHub App identity for agent and gate | Copilot agent, Mergify | No | Later. Gives a separate identity in every record; needs the person to create an app |
| Dependency cooldown | [Nesbitt 2026](https://nesbitt.io/2026/03/04/package-managers-need-to-cool-down.html) | Partly ("new-dependency age and licence check") | Adopt the native setting as layer one, written by /setup into the package manager config, and keep the gate check as layer two |
| Install scripts off during agent installs | npm `ignore-scripts` | No | Adapt: on by default in run worktrees, allow-list packages that need them |
| Secret scanning before push | Gitleaks; GitHub push protection | Yes (planned scan before every push) | Keep, and run it twice: local pre-push and in CI. Push protection only on public repositories for free |
| Dependabot alerts | GitHub | No | Adopt: free, server side, turns findings into issues the kit already understands |
| Pin Actions to commit SHAs | Supply-chain practice | No | Adopt in the shipped `checks.yml`. Cheap and deterministic |
| SLSA provenance | [SLSA v1.1](https://github.blog/enterprise-software/devsecops/enhance-build-security-and-reach-slsa-level-3-with-github-artifact-attestations/) | No | Skip for v1. Matters for published packages, not a team's tool |
| Frozen bar, byte for byte | Ours; [Anthropic harness post](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | Yes | Keep, and add a CI copy (item 3) |
| Held-out twin | Ours (metric pieces) | Partly | Extend to build pieces as hidden examples (item 7) |
| Assertion-free, skipped and focused test lint | [Vitest](https://vitest.dev/config/expect), eslint plugins | No | Adopt for added tests. Fully deterministic |
| Tautological and implementation-detail test smells | [Pocock tests.md](https://github.com/mattpocock/skills/blob/main/skills/engineering/tdd/tests.md) | No (trim follow-up names it) | Adapt: a few mechanical detectors, the rest as review checklist lines |
| Mutation testing on changed lines | [Meta ACH](https://arxiv.org/abs/2501.12862); our gate | Partly (StrykerJS or mutmut when present) | Keep as a forced-review signal, not a gate. Earlier research rejected scores as gates, rightly |
| Changed-line coverage | diff-cover, covguard | No | Adapt as a signal on the review page, never a gate |
| Flaky test quarantine | [Trunk](https://trunk.io/blog/stop-flaky-tests-from-sabotaging-your-merge-queue) | Partly ("a pass on retry counts as failure"; environment failures back to ready) | Adapt: the gate re-runs once on the same commit to classify, never the builder, and a flaky verdict forces review |
| Health check and automatic rollback | Vercel, Argo Rollouts | Yes (v1, in the recipe) | Keep. Add: prove rollback once at /setup; a second deploy of the same version loses the rollback target on Hobby |
| Feature flags | OpenFeature, LaunchDarkly | No | Skip for v1. Useful later for sensitive pieces |
| DORA five measures | [DORA 2025](https://dora.dev/insights/balancing-ai-tensions/) | No | Adopt the two instability measures in /maintain: everything needed already lives in issues and pull requests |
| Rule of Two per session | [Meta, October 2025](https://www.mbgsec.com/weblog/2025-11-01-agents-rule-of-two-a-practical-approach-to-ai-agent-security/) | Partly ("text from issues treated as data") | Adopt as a design rule for which session holds which token (item 6) |
| Author filter on issue text | [GitHub advice after GitLost](https://thehackernews.com/2026/07/public-github-issue-could-trick-github.html) | No | Adopt: the gate gives an agent only text written by the owner and listed collaborators |
| Agent action log | [Claude Code OpenTelemetry](https://code.claude.com/docs/en/monitoring-usage) | Partly (gate's evidence record) | Adopt a hook-written command log outside the worktree (item 10) |

## 3. The ten most important things our design is missing or getting wrong

1. **The agent acts as the person on GitHub, so several gates check nothing.**
   Today the agent uses the person's signed-in `gh`. The gate trusts "the
   account that added `state:ready`", and the merge rule trusts that only the
   person merges, but agent and person are one account with full power,
   including settings, workflows and every other repository. Give v1 agents a
   fine-grained token for this one repository with no Administration and no
   Workflows write. Copilot's agent and GitHub's post-GitLost advice do the same
   ([GitHub Docs](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens);
   [Copilot risks](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/risks-and-mitigations)).

2. **The GitHub layer the redundancy rule relies on does not exist on a free
   private repository.** Rulesets, required checks, merge queues and push
   protection are all missing there
   ([branch protection docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule);
   [secret scanning docs](https://docs.github.com/code-security/secret-scanning/about-secret-scanning)).
   /setup should find the plan, write a ruleset where one is allowed, and
   otherwise tell the person in one line which layer is missing. It can offer
   Pro or a public repository, and add a workflow that reports any push to
   `main` with no merged pull request behind it.

3. **The frozen bar and the gate's evidence are checked only on the agent's
   own computer.** `bar-guard.sh` and the evidence record run where the agent
   can edit files, and a hash chain without a secret can be rewritten. Run the
   same bar guard, the contract hash check and the acceptance checks again in
   GitHub Actions on the pull request. With item 1's token unable to change
   workflows, that copy is a real second layer. ImpossibleBench found Claude
   models cheat mostly by editing tests ([arXiv 2510.20270](https://arxiv.org/abs/2510.20270)).

4. **The guards do not guard themselves.** `gate.py`, the hooks, `.githooks`,
   `claude-settings.json` and the workflows sit in folders the Edit tool can
   change. The state guard also lets everything through when its hook is
   missing, and hook files have no protection of their own
   ([open issue on anthropics/claude-code](https://github.com/anthropics/claude-code/issues/11226)).
   Add Edit deny rules and sandbox `denyWrite` for these paths, and always
   force review on a diff that touches one. Run the gate from the main folder's
   copy. A pre-run check should refuse to start while a guard is missing.
   Offer managed settings, which the agent cannot write
   ([managed settings](https://code.claude.com/docs/en/managed-settings)).

5. **The deny list matches text, and auto mode now lets pushes to `main`
   through.** Since v2.1.211 the classifier allows pushing to the default
   branch. Anthropic's documentation says Bash rules are not a security
   boundary and names the forms they miss, such as `git -C . push origin main`
   ([permission modes](https://code.claude.com/docs/en/permission-modes);
   [permissions](https://code.claude.com/docs/en/permissions)). Our list also
   misses a bare `git push` while on `main`, `--no-verify`, `core.hooksPath`,
   `gh pr merge --admin` and `gh api` writes to refs. Move the filesystem
   sandbox into v1 with `allowUnsandboxedCommands: false` and
   `failIfUnavailable: true`. Make the guard hook parse commands rather than
   match text, set `disableBypassPermissionsMode`, and pin a minimum Claude
   Code version.

6. **"Treat issue and web text as data" is an instruction, not a control.**
   Every published filter has been beaten by adaptive attacks, and GitLost got
   past GitHub's filter by changing one word
   ([The Hacker News, July 2026](https://thehackernews.com/2026/07/public-github-issue-could-trick-github.html)).
   Apply Meta's Rule of Two per session
   ([summary](https://www.mbgsec.com/weblog/2025-11-01-agents-rule-of-two-a-practical-approach-to-ai-agent-security/)).
   Shaping researchers read the web with a read-only token and no write tools.
   Builders read only the spec frozen at ready, not live comments. The gate
   passes on only text written by the owner or listed collaborators, and the
   network allowlist holds back the rest.

7. **The frozen bar stops edited tests, not gamed ones.** Special-casing test
   inputs, overloaded equality and recorded state all pass a byte-identical
   judge ([ImpossibleBench](https://arxiv.org/abs/2510.20270)). New tests the
   builder adds can be tautological, assert nothing or mock the project's own
   modules ([Pocock, tests.md](https://github.com/mattpocock/skills/blob/main/skills/engineering/tdd/tests.md)).
   Extend the held-out twin to build pieces as hidden examples the builder
   cannot read. Lint added tests deterministically: assertions required
   ([Vitest](https://vitest.dev/config/expect)), no skip or only, no mock of a
   path inside the project. Show changed-line coverage and mutation results
   as forced-review signals, not gates.

8. **The run can merge a tree it never tested.** Bors's rule is that the
   tested tree must be the merged tree ([bors.tech](https://bors.tech/)). The
   merge queue that enforces it is not available on most private plans
   ([GitHub Docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)).
   So the gate must merge with `gh pr merge --match-head-commit` on the commit
   whose checks it saw pass, refuse when `main` moved, and allow one run to
   merge at a time. The gate, not the builder, should sort flaky results from
   environment failures by re-running the same commit once. A flaky verdict
   forces review ([Trunk](https://trunk.io/blog/stop-flaky-tests-from-sabotaging-your-merge-queue)).

9. **Supply-chain checks sit in one layer, and that layer comes late.** The
   planned age and licence check runs at the gate, after an install has
   already run its scripts. Every major package manager now has a native
   cooldown ([Nesbitt, March 2026](https://nesbitt.io/2026/03/04/package-managers-need-to-cool-down.html)).
   /setup should write that setting, lockfile-only installs and
   `ignore-scripts` for agents as layer one, with the gate check as layer two.
   Add gitleaks in both pre-push and CI, since push protection is paid on
   private repositories. Also turn on Dependabot alerts and pin Actions to
   commit SHAs.

10. **There is no record of what the agent did, and no measure of whether
    the loop makes things worse.** The gate records its own runs, but nothing
    records the commands the agent ran, refused or retried. That is what issue
    72's investigation needed. Add a `PreToolUse` and `PostToolUse` hook that
    appends every command and decision to a log outside the worktree. Claude
    Code's OpenTelemetry events are an optional second source
    ([monitoring](https://code.claude.com/docs/en/monitoring-usage)). DORA
    2025 found AI raises instability unless controls are strong
    ([DORA](https://dora.dev/insights/balancing-ai-tensions/)), so /maintain
    should report change fail rate and rework rate from issues and pull
    requests the kit already has.
