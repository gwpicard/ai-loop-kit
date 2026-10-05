# Red team of AI Loop Kit v1 as a whole

Research date: 5 October 2026. Read: `redesign-answers.md`, the three earlier reports in this folder, the lessons issue from the first unattended night, and the design document (revision 58, read from Claude Docs and searched as text). This report does not repeat the earlier findings. Where it touches one, it says whether the decision closed it.

Findings are ranked by how much each would hurt: first by whether it breaks the loop on an ordinary run, then by whether it breaks a safety promise, then by cost and confusion.

## Ranked findings

### 1. Taking a piece out of the combined branch has no working mechanism

**What is wrong.** Integration joins a piece, checks, and on red "takes it out". A rejected piece in the run's pull request is also "sent back" while the others stay (move 13, and the proposed "a comment that names one piece sends back only that piece"). But the design also says no force push and no rebase anywhere. Without rewriting history, the only way to take a merged piece out is a revert commit. Git's own documentation warns that once a merge is reverted, merging the same branch again later does not bring its changes back, because Git thinks they are already in. So the rebuilt piece rejoins silently empty, or rejoins only its new commits.

**Example.** Pieces A, C, B join in that order. B turns the branch red, is reverted and sent back to building. The builder fixes one line and B rejoins. Git merges only the one-line fix. The combined branch now lacks most of B, and B's judges fail at the join for no reason the builder can see. The same happens when the person rejects C in the pull request: C is reverted on the run branch, and A and B are now in approval on a tree nobody tested. No move takes them back to review (move 12 covers only "main moved").

**Evidence.** Git, [How to revert a faulty merge](https://github.com/git/git/blob/master/Documentation/howto/revert-a-faulty-merge.txt). Design document, "The integration loop", "Branch and merge flow" ("No force push and no rebase anywhere") and moves 8, 12 and 13.

**Fix.** Never advance the combined branch on trust. Do each join as a trial merge in a scratch worktree, run the checks there, and only then move the combined branch forward to the trial commit. A red join is then thrown away, not reverted. For a rejection in the pull request, cut a fresh combined branch from main, replay the accepted joins, re-check, and open a new pull request that supersedes the old one. Add one move, "approval to review: the tested tree changed", and use it for both the rejection case and "main moved".

### 2. The anti-circle rule deadlocks three of the fourteen moves

**What is wrong.** The proposed rule says every move back must add a new need to the spec, and a reason already on the piece is refused, so a piece cannot circle. But move 7 (environment failure, GitHub-only failure) keeps the spec untouched by definition. Move 12 (main moved) happens every time main moves. Move 8 (clash) can repeat with the same partner. The second time any of these happens, the gate refuses the move, and the piece is stuck in building or approval with no legal exit.

Move 7 also contradicts itself. It says "spec untouched" and then "a parked piece whose answer arrives after its run ended, with the answer written into the spec". Writing into the spec changes the fingerprint, and a changed fingerprint is a reason for move 3 (ready back to shaping). So the person's answer sends the piece back to shaping at the next claim, which is the opposite of what the person was told ("the piece is back in ready with your answer").

**Example.** A flaky network makes `npm ci` fail twice in one week on piece 14. The first failure goes back to ready. The second is refused as a repeated reason. The run cannot claim it, cannot give it back, and the watch sees a live piece making no progress.

**Evidence.** Design document, "Rules every move follows" (the anti-circle rule, from settled decision 49), moves 3, 7, 8 and 12.

**Fix.** Apply the anti-circle rule only to moves that send a piece to shaping (3, 6, 9, 13). Give moves 7, 8 and 12 a counter instead: after two of the same kind, the piece gets the needs-you flag and stays where it is. For a late answer, let the gate rewrite the fingerprint itself when the only change is a new line under Decisions, and say in the move's row that this is the one spec change move 7 allows.

### 3. "Park" means three different things, and some states have no way out on a stop

**What is wrong.** The build loop says a needs-the-person outcome parks the piece inside building and the run resumes it in the same run. Decide-or-park says park means "send the piece back to shaping". The review loop says a finding left after 2 rounds "parks that piece", and the proposed text sends it to shaping, while parked is defined as a condition inside building only. A run stop "gives every piece back" through move 7, which starts only from building or approval. Pieces in review at that moment have no move.

**Example.** A run is stopped from the mailbox while piece 9 is joined but not yet reviewed. The gate has no move from review to ready, so either the label stays on review with no run, or the gate breaks its own rule.

**Evidence.** Design document, "Outcomes", "One rule: decide or park", "The review loop", "Run details" (pause, continue and stop), and the transition table.

**Fix.** Keep one meaning: parked is "in building, waiting for an answer, run carries on". Call the other routes what they are: "back to shaping" (moves 6 and 9). Add "review to ready, given back" to move 7's start states.

### 4. The agent's fine-grained token is still the person on GitHub

**What is wrong.** Decision B1 gives agents their own fine-grained token so that "the person merges under their own account". A fine-grained personal access token acts as the user who made it. Every label, comment and merge made with it shows the person as the actor. So three things the design relies on still cannot tell agent from person: "a person who changes a label by hand outranks the gate", "only the person merges", and the gate's trust in who added a label. GitHub also does not notify you about your own mentions, so finding 5's cheapest channel is closed too. The token also needs Contents write to push branches, and that permission can push to main and merge pull requests on a free private repository, where no branch rule exists.

Two more gaps sit next to it. Nothing says how the person's own, full-power `gh` login on the same computer is made unreachable from a builder session. And a piece that must change `.github/workflows/` can never be pushed by a token without Workflows write, and no route covers that.

**Example.** At 02:00 a builder session runs `gh pr merge` with the token. The pull request shows "merged by" the person. Next morning the person cannot tell whether they merged it from their phone.

**Evidence.** GitHub Docs, [managing personal access tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens): a token "has the same capabilities ... that the owner of the token has", and GitHub Apps are recommended for long-lived integrations. The earlier gates report (item 1) already pointed at a separate identity like Copilot's agent; decision B1 did not reach it.

**Fix.** Give the gate, not the builders, a separate identity: a GitHub App installed on the one repository, or a free machine account added as a collaborator. Only the run script holds its key. Builders get no GitHub credential at all, no network route to github.com (sandbox allowlist), and a sandbox read-deny on `~/.config/gh` and other credential stores. The gate then checks the actor on every label and merge event. Add a "the person pushes this" route for pieces that touch workflows.

### 5. The decided notification channel cannot be driven by a script

**What is wrong.** Notifications were decided as "a Claude Code push notification to the person's phone, with an email as the fallback", sent once per event with quiet hours. Claude Code's push needs a Remote Control session, which needs a running interactive `claude` process signed in with a claude.ai subscription, and "Claude decides when to push". There is no command a plain script can call to send one, no per-event control, and no API-key support. The run is a plain script and its builders are `claude -p` sessions, so neither can send it. Email needs mail credentials on the computer, which is one more secret.

**Example.** The run stops on a real stop at 03:00. The script has nothing to call. The person learns about it at breakfast, which is the failure the lessons issue from the first unattended night set out to fix.

**Evidence.** Claude Code docs, [Remote Control, mobile push notifications](https://code.claude.com/docs/en/remote-control) and [Claude Code on mobile](https://code.claude.com/docs/en/mobile). The design document still lists the channel as Open, so the two records also disagree.

**Fix.** Use GitHub itself. With the separate identity from finding 4, the gate @mentions or assigns the person on the issue or pull request. GitHub Mobile pushes direct mentions and assignments, and its Working Hours setting gives quiet hours for free ([GitHub Docs, configuring notifications](https://docs.github.com/en/subscriptions-and-notifications/get-started/configuring-notifications)). The reply comes back as a comment, which is already an input channel. Keep a desktop notification as a local extra. Drop email from v1.

### 6. The sandbox brings network isolation with it, and refused commands stop the whole run

**What is wrong.** Answer 9 put the network allowlist "later", and B3 moved the filesystem sandbox into v1. In Claude Code they are one feature: turning the sandbox on also routes every command through a proxy whose allowed domains start empty. In a `-p` session with no one to answer, a new domain is denied. So in v1 every `npm install`, `pip install` or test that fetches will be refused. Separately, "a refused command" is on the list of real stops that halt the whole run. Under `dontAsk` mode, which is what makes a `-p` builder unable to ask, every command not pre-approved is refused. Refusals will be routine, and each one stops the run.

The builders' permission mode is also not decided. If it is auto mode, the classifier now allows pushing to the default branch. If it is `dontAsk`, an allowlist must cover every build command the project uses.

**Example.** The first piece adds a date library. The builder runs `npm install date-fns`. The proxy refuses `registry.npmjs.org`. That is a refused command, so the run stops and notifies at 23:40.

**Evidence.** Claude Code docs, [sandboxing](https://code.claude.com/docs/en/sandboxing) (network row of the defaults table; `strictAllowlist`; sandbox auto-allow works independently of permission mode) and [permission modes](https://code.claude.com/docs/en/permission-modes) (`dontAsk` denies anything that would prompt; auto mode allows pushing to the default branch).

**Fix.** Ship the network allowlist in v1 as part of each recipe (the package registry, the language's toolchain hosts, nothing else) with `strictAllowlist`, `allowUnsandboxedCommands: false` and `failIfUnavailable: true`. Run builders with `--permission-mode dontAsk --permission-prompts none` plus sandbox auto-allow, so sandboxed commands run and anything else is denied. Count a refused command against the attempt and log it. Make it a run stop only when the same refusal hits two pieces.

### 7. "Only the exact tested commit merges" does not hold in three places

**What is wrong.** First, the decisions say each piece's behaviour change is applied to the overview and the changelog is written "at the merge, in the same pull request". Any commit added then is a commit nobody tested. Second, the person merges on GitHub. On a free private repository nothing stops them merging after main has moved, so move 12 cannot be enforced on the person's own merges. Third, B4 removed GitHub-side checks, yet move 7 still names "a check that fails only on GitHub's machines". With no GitHub check there is no such failure to detect, and if the project has its own CI, a red result on the run's pull request cannot be pinned to one piece, while that piece's code still sits in the open pull request.

**Example.** The run opens its pull request at 05:00. The person merges a quick fix from their phone at 08:00, then merges the run's pull request at 08:05. GitHub allows it. Main now holds a combination no one checked.

**Evidence.** Design document, "Approval and the merge decision" and move 7. Free-plan limits as in the gates report, item 2. Bors's rule as cited in the gates report, item 8.

**Fix.** Write the overview, docs and changelog changes before the final combined check, so they are part of the tested tree. Have the gate post a commit status on the pull request head that names the main commit it was tested against, and turn it red (with a bot comment) when main moves. That is not binding on a free plan, but the person sees it before pressing merge. Make "tell the agent to merge" the recommended path, since the gate can check. Delete the "fails only on GitHub's machines" clause, or keep it only for a project with its own CI and route it to the whole run's pull request, not to one piece.

### 8. Automatic rollback on Vercel freezes production silently

**What is wrong.** v1 rolls back automatically to the last good deployment when the health check fails. On Vercel, an instant rollback turns off automatic assignment of production domains. Every later merge to main builds but does not go live until someone promotes a deployment. The kit would then report "went live" for merges that did not. On the Hobby plan a rollback can only reach the immediately previous deployment, so two bad deploys in a row cannot be undone automatically. A rollback also does not undo a database migration. Finally, nothing says what runs the health check. The person may merge from their phone while the laptop is asleep, and no run is going.

**Example.** Monday's deploy fails its check and rolls back. Tuesday's run merges three fixes. The health check pings the live address, which still serves Saturday's build, finds it healthy, and sends "went live".

**Evidence.** Vercel docs, [Instant Rollback](https://vercel.com/docs/instant-rollback) (updated 7 July 2026): "After a rollback, Vercel turns off auto-assignment of production domains", and Hobby users "can roll back to the previous deployment".

**Fix.** Run the health check in GitHub Actions on the `deployment_status` event, not on the laptop. Have it compare the commit the live address reports with the commit just merged. After an automatic rollback, set a "production frozen" flag that /what-now shows first and that stops "went live" messages, and open a must-look issue. Undoing the freeze (`vercel promote`) is the person's yes. Refuse automatic rollback past a piece carrying an irreversible data change.

### 9. The pre-approved merge will almost never fire, and it costs a lot

**What is wrong.** A pre-approved merge needs "no piece with a must-look reason". The must-look list includes "an assumption or decision made alone, marked for review", and decide-or-park writes such a decision every time a run answers a question itself. It also includes the first deployment, any new test from review, any flaky result and any change outside an area. In practice a run of several pieces will nearly always carry one, so the pre-approved path waits for the person anyway. It still needs its own conditions, a merge lock, tests and an extra question at every /run.

**Evidence.** Design document, "Reasons that force the person to look" and "Merges pre-approved before a run". The first unattended night produced exactly this kind of build-time decision.

**Fix.** Either leave pre-approval out of v1, or make it per piece: merge the pieces with no must-look reason in a pull request of their own and leave the rest for the person. Per piece only works after finding 1's replay, since it means building a second tested tree.

### 10. Hidden held-out cases have no safe place to live

**What is wrong.** Held-out cases must be unreadable by the builder, "held by a deny rule and a hook". A `Read` deny rule does not stop `cat` in Bash, and the sandbox's `denyRead` does not stop the Read tool, so both are needed. Neither stops `git show` if the cases were ever committed to any branch in the same repository, and option A puts every build file on the piece's branch. Neither stops `gh issue view` if the cases came from text in the issue. The design does not say where the cases are stored.

**Example.** A builder that fails twice runs `git log --all --stat` looking for examples, finds `heldout/` on the piece branch's first commit, and reads it with `git show`.

**Evidence.** Claude Code docs, [sandboxing](https://code.claude.com/docs/en/sandboxing): "A `denyRead` entry doesn't stop the Read tool". Design answer 11 (every build file on the piece branch).

**Fix.** Store held-out cases outside the repository and outside git, in a folder only the gate reads, with both a `Read` deny rule and a sandbox `denyRead` on it. Builders have no GitHub access (finding 4). The gate copies the cases into the tested tree only at the final combined check, so the person sees them in the pull request.

### 11. Dependencies across isolated review, and a strict chain, still stall a run

**What is wrong.** A piece that needs individual review "is not joined". A piece that depends on it is built only after its dependency joins the run branch. So a dependent of an isolated piece can never build in that run, and no rule says what happens to it. More widely, the run builds a dependent only after its dependency has been built and joined, so a chain of five runs one at a time, which was cause 6 in the lessons issue from the first unattended night.

**Evidence.** Design document, "Branch and merge flow" ("A piece that relies on another takes in the run branch once its dependency has joined, before it is built") and "The integration loop".

**Fix.** Let a dependent stack on its dependency's piece branch, isolated or not. If the dependency is isolated, the dependent is isolated too, and its pull request is based on the dependency's branch. Have the plan step print, before the run starts, which pieces will wait for which, so the person sees a serial run coming.

### 12. Learning additions made mid-run break other pieces' frozen bars

**What is wrong.** The learning loop may add a "cheap addition, for example a new lint pattern" during a run through decide-or-park. The frozen bar includes "test settings", checked byte for byte. A new lint pattern changes a test setting, so every piece in flight fails its bar check, which is logged as possible gaming. It is also the pattern Claude Code's classifier called instruction poisoning on the first unattended night: an agent changing the rules other agents run under during a run.

**Evidence.** redesign-answers.md, "Meta loops 2 to 5" (learning) and answer 14 (frozen bar). The lessons issue from the first unattended night, cause 5.

**Fix.** Lessons are only proposed during a run. They take effect only at the start of the next run, after the pre-run check, and each one lands as its own commit the person can see.

### 13. The watch duplicates the run and cannot see what it is asked to judge

**What is wrong.** The watch reads only the heartbeat and the run record, but it is asked to stop stuck attempts, and stuck now means "the same error 3 times" or "the same change undone and redone". That needs the builder's output, which the run script has and the watch does not. It also runs on the same laptop, so it sleeps when the laptop sleeps, and since macOS 10.11 a `StartInterval` that falls during sleep is missed, not caught up. A crash in the middle of a join is also unspecified: the run record and the labels are written in "one step", but a GitHub label write and a local file write cannot be one atomic step, and the record cannot say whether a half-done join reached the combined branch.

**Evidence.** launchd man page change, [Apple developer forums](https://developer.apple.com/forums/thread/23361). Design document, "The walk-away kit" and "Rules every move follows".

**Fix.** Put stuck detection in the run script. Run the script itself under launchd with `KeepAlive`, which restarts it at once, and wrap it in `caffeinate -i -s -w <pid>` so the computer stays awake while it runs. The watch then only checks that the heartbeat is fresh. Make joins idempotent: each join commit carries a `Piece: #n` trailer, and on resume the script reads the combined branch to decide what is done. Allow one run per project at a time with a lock file, which also removes "one run merges at a time".

### 14. Spending has no ceiling, while money is a real stop

**What is wrong.** A run has no limit, by decision. On an API key, every builder session spends money, and "anything touching money" is a real stop, so the run's own spending is the one money matter nothing guards. On a subscription, three builders spend the allowance three times faster, and the weekly limit can hold a run for days. The `claude -p` allowance itself nearly changed in June 2026: a separate monthly credit was announced and then paused.

**Evidence.** Claude Code [CLI reference](https://code.claude.com/docs/en/cli-reference) (`--max-budget-usd`, `--max-turns`); Claude Help Center, [Agent SDK and claude -p on Claude plans](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan) (16 June 2026, change paused).

**Fix.** Keep "no limit" for subscriptions. For an API key, have /setup ask for a per-piece and per-run spend cap, pass it as `--max-budget-usd`, and treat reaching it as "waiting for the person". Show tokens or cost per piece in the morning summary. Note in the docs that the kit depends on `claude -p` drawing from the plan.

### 15. `--bare` would remove every guard hook

**What is wrong.** `claude --bare -p` starts faster and is the documented way to script calls, but it skips discovery of hooks, skills and CLAUDE.md. A future change that adds it for speed would remove the command-parsing hook, which is one of the two layers on most rules.

**Evidence.** Claude Code [CLI reference](https://code.claude.com/docs/en/cli-reference), `--bare`.

**Fix.** The pre-run check refuses a run script that passes `--bare`. Pass the guard settings and hooks with `--settings` on every builder call, so they do not depend on discovery.

### 16. Day one will feel slow and noisy

What a person meets, in order:

- **/setup** asks for a lot before anything is built: the interview, a recipe, deploy, a token made in the browser, the launchd job, sandbox and allowlist, package manager settings, secret scanning, Dependabot, and phone pairing for notifications. Each one is reasonable. Together they are an hour, and the pre-run check refuses the first /run if one was skipped.
- **The first piece in an empty repository** cannot meet "the judge fails on main" honestly. With no test runner and no app, every test fails because nothing imports, not because the behaviour is missing. The gate passes a red bar that proves nothing.
- **/shape** runs a lint, a coverage list, IDs, two fresh sessions' test lists, a fresh buildability check, researchers and prototypes. Two language model sessions will almost always list different tests, and "differences become needs" turns that into questions for the person on every piece. Answer D lists that comparison without a tolerance rule.
- **The first night** ends in one pull request grouped by piece. If an overnight run ends at 03:00 with quiet hours, "pull request ready" and "waited too long" both wait, then arrive together at 08:00.

**Fix.** Split /setup into "enough to shape and run locally" and "make it safe to walk away", with the pre-run check naming which half is missing. Require each judge to fail for the stated reason (an assertion failure naming the spec ID, not an import or syntax error), and let the first piece be a quick-path "scaffold and test runner" piece whose judge is "the test command runs". Compare the two test lists by spec ID covered, not by test name, and raise a need only for an ID one list covers and the other does not. Collapse notifications held by quiet hours into one message.

### 17. What comparable tools show and v1 still lacks

- **A way for the person to try a piece.** Hosted agents put a preview link or screenshots on each pull request. v1's evidence is test results. The Vercel recipe already gives a preview deployment per branch; put its address in each piece's evidence section.
- **"Fails for the right reason".** Already raised in finding 16. It is the standard test-first check and the cheapest guard against a meaningless red bar.
- **Native GitHub dependencies.** GitHub has had "blocked by" relationships with an API since August 2025, and sub-issues allow 100 parts and eight levels. The spec's Dependencies field duplicates that and will drift. See the simplifications below.

Sources: [GitHub changelog, dependencies on issues, 21 August 2025](https://github.blog/changelog/2025-08-21-dependencies-on-issues/); [GitHub Docs, sub-issues REST API](https://docs.github.com/en/rest/issues/sub-issues).

## Decisions that did close earlier findings

- Questions stopping the run (agentic loops 1): closed by the plain script and `-p` builders, provided finding 6 is fixed.
- "Bar is wrong" outcome (agentic loops 2), fresh attempts (8), stuck by patterns (4): closed.
- Guards guarding themselves (gates 4) and text-matching deny rules (gates 5): closed on paper, but finding 15 shows a gap.
- Separate identity (gates 1): not closed. See finding 4.
- Tested tree equals merged tree (gates 8): partly closed. See finding 7.
- Second check layer on GitHub (gates 3): deliberately not adopted (B4). The bar and held-out checks therefore run only where the agent runs. Finding 4's "builders have no GitHub credential" and finding 10's "held-out cases outside git" are what make that acceptable.

## Simplifications

1. **Trial joins replace revert machinery.** Join in a scratch worktree, check, then advance the combined branch. No take-out step, no revert, no culprit re-check "without it" (the trial already is that check).
2. **Scratch files outside git.** Keep attempt notes, the frozen spec copy, judge logs and run state in a git-ignored run folder, not on the piece branch. Then nothing has to be removed before merge, and "scratch files never reach main" holds by construction.
3. **One process, not two.** The run script under launchd `KeepAlive` replaces the 15-minute watch for restarts. The watch shrinks to a heartbeat check that sends one notification.
4. **One run per project.** A lock file removes "one run merges at a time", the two-runs claim race, and doubled memory sizing.
5. **One notification channel, one input channel.** GitHub mentions out, GitHub comments in, both through the gate's identity. The mailbox file stays only as the local way to send pause, continue and stop.
6. **Use GitHub's own dependency links** for "blocked by" and the parent's parts, and drop the spec's Dependencies field, so the gate reads one source.
7. **Drop pre-approved merges from v1** (finding 9), along with its four conditions and the merge lock.
8. **One meaning of park** (finding 3). Fewer words for the same thing.
9. **Crews only when asked for.** Several researchers and several prototypes run only when the needs list holds a research or design question, not on every piece.
