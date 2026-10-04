# COMPATIBILITY.md: one kit across coding agents

## The portable core

AI Build Kit works when the coding agent can read and edit project files, run
shell commands, and use Git. Native skill pickers, slash commands, hooks,
subagents, and command deny lists can improve the experience, but the workflow
does not depend on them.

The fourteen skills use the open Agent Skills folder format. Each skill keeps its
own instructions and supporting files together. A command that needs a
background skill loads it by name.

Claude Code comes first. The kit is designed and measured on it, and a feature
that needs more than the portable core, such as a run that builds several
pieces in a chain with nobody watching, is built for Claude Code before
anything else. Other coding agents get the one-at-a-time core: one piece
shaped, built, checked and saved at a time, with the same records and the same
rules. A run there builds its pieces one after another in one folder, where
Claude Code gives each piece its own worktree. Only Claude Code offers to build
a group's pieces at the same time, each with its own background agent.
Elsewhere, and on Claude Code with Git older than 2.17, the run does not ask
and builds one piece at a time. Only Claude Code shows a confirmation box
before a merge that goes live, on a project whose host puts every merge live.
Elsewhere the written rule, a yes that names the merge, is the only guard. The
grades below say how much of that has been proved on each agent.

## How much has been proved on each agent

Meeting the portable core means the kit should work on an agent. It does not
mean anybody has watched it work there. Each agent this page names carries one
of three grades, so you can see how much evidence sits behind your choice
before you make it.

- **Tested.** The kit's replay harness has driven this agent through whole
  scripted conversations, and the results are on record with the date, the
  kit that was run and the models used. The replay harness is a maintainer
  tool: it sets up a throwaway project, talks to the kit, and grades what the
  kit did against what it promises.
- **Expected to work.** The agent reads the same skill files a tested agent
  reads, and nothing known stops the kit working there. Nobody has recorded a
  run. Its known limits are listed below.
- **Experimental.** Nobody has recorded running the kit on this agent. The
  files it needs ship with the kit, and the only checks on them are checks of
  their shape.

| Coding agent | Grade |
|---|---|
| Claude Code | Tested |
| Codex | Expected to work |
| Cursor | Experimental |
| Gemini CLI | Experimental |
| GitHub Copilot | Experimental |
| Any other coding agent | Experimental |

### Moving up a grade

An agent moves up on evidence and on nothing else. A quiet issue tracker is not
evidence. An absence of complaints may only mean that nobody has tried.

To move from Experimental to Expected to work, somebody runs a published
release on the agent, from a blank folder through founding and one built
piece, and the maintainer writes down what happened and on which release. A
maintainer's own walk-through counts, and so does a report from a real user
that says the same.

To move from Expected to work to Tested, the replay harness drives the agent
through the replayed conversations and the rates are recorded beside the
Claude Code ones. The record names the agent the harness drove, and it names a
published release or the commit that release was cut from. The harness can already drive Codex. What Codex lacks is a
recorded run. The harness cannot drive Cursor, Gemini CLI or GitHub Copilot,
so each of them needs that work first.

An agent moves down when a recorded run shows the kit failing there in a way
it does not fail elsewhere.

### What Tested means for Claude Code

Tested describes a rate. The harness runs each conversation several
times and counts how often the kit behaved as promised, and some cases hold
less often than others. One case, a bug that resists repeated fixes, held in
four runs of five on one Claude model and in none of five on another. The runs
have no person in them, so a failure they show is a lead to check by hand.

The last time every case was measured together was 25 August 2026. Some cases
have been measured again since, on a changed kit, and the rest have not.

Every Claude Code run on record was on a commit of `main` between two
releases, not on a published release. The record names each commit, so a rate
can be traced to the exact kit it measured. No rate yet describes a release you
can install. From now on, a run that keeps an agent at Tested is recorded
against a published release or the commit that release was cut from.

The plugin route is rehearsed for installing, updating and removing the kit.
Its conversations cannot be replayed, because plugin commands do not load in
the unattended sessions the harness uses. The replayed conversations use the
skills installed into the project, which is the shared installer's route.

### Known limits of Codex

- Nobody has recorded a run. A check proves the harness can start, resume and
  grade a Codex conversation, against a stand-in for Codex and without a model.
  That proves the harness wiring, and says nothing yet about how the kit
  behaves.
- The kit ships no Codex command files. Codex finds the skills in
  `.agents/skills/`, and you start a command by naming it.
- Nothing reminds you of a check-up when a session opens. `what-now` says when
  a visit is overdue.
- There is no deny list set up for you. Codex's own approval settings do that
  job, and you set them yourself.
- Nobody has checked whether Codex keeps the five background skills out of
  your hands.
- GitHub access depends on the session's network permissions and the CLI's
  sign-in. See [GitHub access in Codex](#github-access-in-codex).

### GitHub access in Codex

The kit needs a signed-in `gh` with permission to read and change the project's
repository. Check `gh auth status` and `gh repo view` from the agent's command
tool. A working terminal or GitHub connector does not prove that tool has the
same access. A connector can read issues while refusing writes.

Codex can use either the standard sandbox settings or named permission profiles.
Use the system active in your configuration, keep filesystem sandboxing and
allow networking for the workspace. Do not combine the two systems. Start a new
session after changing settings, and check what the client actually selected.
The installed setup skill's
[Codex recovery guide](../.agents/skills/setup-ai-build-kit/references/codex-github.md)
holds the settings and the checks, including managed restrictions.

An HTTP 401 after networking works can mean Codex cannot retrieve the current
login. Compare token environment presence and the account, executable and
configuration directory before signing in again. On macOS a terminal can read
the Keychain while sandboxed Codex cannot. The kit includes a
[session launcher](../.agents/skills/setup-ai-build-kit/scripts/codex-with-github.py)
for that case. Run it with python3 from your project's ordinary terminal; the
agent gives the installed path. It supplies the current login to that Codex
process in memory and disables shell snapshots. It needs no editor integration
and does not change your permission settings or credential storage.

The network and credential route was tried on 1 October 2026 with Codex CLI
0.159.3 on macOS. Both account and repository reads succeeded in the new command
tool with a restricted filesystem and networking enabled. Automated checks
cover launch failure, existing token precedence, credential masking and the
installation routes. This is evidence for GitHub access, not a replayed founding
or build, so Codex keeps its grade above.

A failed plan refresh shows a credential-masked GitHub error and a recovery step,
and leaves the previous printout intact.

### Known limits of Cursor, Gemini CLI and GitHub Copilot

- Nobody has recorded a run, and the replay harness cannot drive these agents.
- The kit's release carries generated command files for Cursor and Gemini CLI.
  A check confirms each file is there and well formed. Nothing has confirmed
  that the agent lists the nine commands, or that it loads a background skill
  when a command asks for one.
- Setup creates the file that points Gemini CLI at `AGENTS.md`,
  and the one that points GitHub Copilot at it. Nobody has confirmed that
  either agent follows that pointer.
- Nothing reminds you of a check-up when a session opens. `what-now` says when
  a visit is overdue.
- There is no deny list set up for you. Where the agent has command allow and
  deny settings, you add the kit's blocked commands there yourself.
- Nobody has checked whether these agents keep the five background skills out
  of your hands.

## Choose one installation route

Every route installs the same fourteen AI Build Kit skills. Nine are commands
you type: `setup-ai-build-kit`, `shape`, `implement`, `queue`, `fix`, `ship`,
`sync`, `maintain`, and `what-now`.
Five run in the background when a command needs them: `clarify`,
`change-triage`, `screen-check`, `section-builder`, and `second-opinion`. The routes differ in
how the skills reach the project, not in what arrives.

A Claude-only project can use the public repository as a Claude Code plugin.
From the project folder, run:

```bash
claude plugin marketplace add gwpicard/ai-build-kit
claude plugin install ai-build-kit@ai-build-kit --scope local
```

The plugin uses local project scope, so it does not replace the project's
shared Claude settings. It exposes the nine commands and the five
background skills. The commands use the `ai-build-kit:` prefix, so start with
`/ai-build-kit:setup-ai-build-kit`.

Use the shared skills installer when the project uses Codex, Cursor, Gemini
CLI, another coding agent, or more than one agent. From the project folder,
run:

```bash
npx skills add gwpicard/ai-build-kit
```

The shared [skills installer](https://github.com/vercel-labs/skills) detects
installed coding agents and asks where the project skills should appear. It
keeps one project-level copy and uses the selected harness locations for
discovery. The same command can install the kit for several harnesses used on
one project.

A coding agent that installs plugins in the open
[Agent Plugins](https://agent-plugins.org) format can use the `agent-plugin`
folder. That folder gains its skills when a numbered version is packaged, so
take it from the release archive rather than from a clone of the repository,
and point the agent's own plugin installer at it. It holds a `plugin.json`
manifest and a `skills` folder with the same fourteen skills, each carrying its
own supporting files. This is the newest route, and a client may skip a skill
it judges non-standard, so prefer the shared installer when the project has a
choice.

After installation, run `setup-ai-build-kit`. That skill prepares missing project
foundation files before the interview. It preserves existing files, so every
route works for a blank folder and for a project that already has code.

Use one route per project. Do not run two AI Build Kit installations in the
same project. If the project later needs another coding agent, install the
shared skills, confirm they work, then remove the other installation.

## Update the installed skills

During `maintain`, the agent names the version this project holds and the
latest published one, reads that release's notes, and asks before changing the
kit. Every route delivers a published release, never work that has not been
released yet. The agent first identifies the installation route.

For the Claude plugin, the approved update is:

```bash
claude plugin marketplace update ai-build-kit
claude plugin update ai-build-kit@ai-build-kit --scope local
```

Claude loads the new plugin after `/reload-plugins` or the next session.
If the marketplace cannot be reached, the installed version remains enabled.
`maintain` reports that no update happened and tries again later.

The shared installer records project skill sources in `skills-lock.json`. Its
approved update is the same command that installs the kit:

```bash
npx skills add gwpicard/ai-build-kit
```

This refreshes a skill that is installed and adds one that is missing, which
is what carries a project across a rename. The installer's `update` command
is not the route: it refreshes only what the lockfile already lists and drops
any other name without a word, so a project that updated across the rename of
`plan` to `shape` lost one skill and never received the other.

That command replaces the installed skill files outright. Anyone who has edited
one of the fourteen skills in their own project loses that edit, without being
asked and without being told. This is why `maintain` looks for local edits
before it updates anything, and why a project rule belongs in `AGENTS.md`, which
no update touches. The one edit the kit makes there is to the line naming the
commands, after a rename, and only with approval.

An Agent Plugins installation belongs to the coding agent that installed it,
so use that agent's own plugin update command. When the agent has none,
download the latest public Release and replace the installed `agent-plugin`
folder, after a clean checkpoint and explicit approval.

Every route leaves application code, `AGENTS.md`, `README.md`, the three
project records, environment files, and the project check under the project's
control.

Projects created before this installation model may not have
`skills-lock.json`. The same command registers the installed skills on the
next `maintain` visit, and later visits use it again.

## Harness map

The shared installer owns the exact placement and symlinks. Its current project
paths are:

| Harness | Project skill location | Standing instructions |
|---|---|---|
| Claude Code, shared installer | `.claude/skills/` | `CLAUDE.md` points to `AGENTS.md` |
| Claude Code, plugin | Claude's plugin cache | the nine commands use the `ai-build-kit:` prefix; the five background skills stay out of the menu |
| Codex | `.agents/skills/` | reads `AGENTS.md` |
| Cursor | `.agents/skills/` | reads `AGENTS.md` |
| Gemini CLI | `.agents/skills/` | `GEMINI.md` points to `AGENTS.md` |
| GitHub Copilot | `.agents/skills/` | `.github/copilot-instructions.md` points to `AGENTS.md` |

Another coding agent may work through the same portable files. It stays
Experimental until somebody records a run on it.

The setup-ai-build-kit skill creates missing standing-instruction pointers. It does not
replace an existing harness configuration.

Use the harness's skill picker or ask for a skill by name. When native
discovery is unavailable, open `.agents/skills/<name>/SKILL.md` directly and
follow it.

## Who may start a command

You can type one of the nine commands, name it anywhere in a message, or just
say what you want done in your own words. The agent starts the right command
and says which one it is running. It never starts one you did not ask for.

The five background skills run when a command needs them. The kit marks them so
that you cannot pick one yourself, where your coding agent enforces that.

## Manual fallback

If the computer cannot run `npx`, download the latest public Release and copy
its `.agents/skills` directory into the project's `.agents/skills` directory.
Then ask the agent:

> Open `.agents/skills/setup-ai-build-kit/SKILL.md` and run the setup-ai-build-kit skill.

A later manual update replaces only the fourteen AI Build Kit skill folders,
after a clean checkpoint and explicit approval.

## Optional harness features

| Capability | Portable behaviour | Optional enhancement |
|---|---|---|
| Command invocation | Ask for a skill by name | Native skill picker or slash command |
| Background skills | Command loads the named skill | Automatic skill triggering |
| Independent review | A clean separate chat with a prepared instruction | Subagent or separate automated session |
| Readiness check | Paste `/shape <number> check readiness` into a new session | Subagent that carries none of the shaping conversation |
| Sync | Run `sync` when needed | Session-end reminder |
| Check-up due | `what-now` says when a visit is overdue | Said automatically when a session opens |
| Safety | Standing restrictions and approval gates | Mechanical command deny list |
| Long runs | Normal sequential work | Native goal or orchestration mode |

During `setup-ai-build-kit`, the capability check records which enhancements the current
harness provides and selects a fallback for anything absent. Missing optional
automation reduces convenience rather than changing the workflow's rules.

`setup-ai-build-kit` writes the session-start wiring only into a Claude settings file it
creates itself, and never into one that already exists. A project whose Claude
settings predate AI Build Kit keeps them exactly as they are, and its check-up
reminder arrives through `what-now`.
