# Slice 22: Set AI Loop Kit's names: the kit is called AI Loop Kit in every name a person types, installs or finds on disk

Labels (today's set): enhancement, area:release, ready-able once shaped. Release label for the PR: release-major, because the founding command, the plugin and marketplace names and two record files change name.
Parent: the "AI Loop Kit v1" epic in gwpicard/ai-loop-kit. Blocked by: slice 21: Documentation sweep.

## So that
A person finds, installs, founds and updates the kit as AI Loop Kit, from gwpicard/ai-loop-kit, and never meets the old name in a command, a plugin, a record file or a document.

## Done when

### Works
- No shipped file says "AI Build Kit", `ai-build-kit` or `/setup-ai-build-kit`, outside two places: the kit-repository recognition in `check-tooling.sh` and section-builder, and the one sentence `/maintain` and founding say to a project founded with AI Build Kit. Maintainer-only history keeps its names: `docs/MIGRATION.md`, `docs/MIGRATION-READINESS.md`, `.agents/migration/`, `docs/design/` and the replay's `abk-` paths. Check: new `.agents/tests/kit-names.sh`, which walks `release-manifest.txt` and fails on a copy of the README with one old name put back.
- The founding skill is `.agents/skills/setup-ai-loop-kit/`, the command is `/setup-ai-loop-kit`, the generated adapters carry the new name, and `release-manifest.txt`, both plugin manifests and the validator's skill list name it. Check: `.agents/tools/validate-kit.sh`, `.agents/tests/claude-plugin.sh`, `.agents/tests/agent-plugin.sh`, `.agents/tests/release-builder.sh`.
- The Claude plugin and its marketplace are both named `ai-loop-kit` in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`, with descriptions that say AI Loop Kit, and `agent-plugin/plugin.json` names the plugin `ai-loop-kit`. The marketplace lists one plugin and no entry under the old name. Check: `.agents/tests/claude-plugin.sh` installs `ai-loop-kit@ai-loop-kit` from the marketplace in an isolated `CLAUDE_CONFIG_DIR` and finds no `ai-build-kit` entry; `.agents/tests/agent-plugin.sh` reads the manifest's name.
- The two record files a founded project keeps are `.ai-loop-kit-maintenance` and `.ai-loop-kit-version`; founding writes them, every skill and `worktree.sh` read them, the session-start template reads the new maintenance file, and the release builder writes the new version file. No skill reads the old names. Check: `.agents/tests/kit-version-record.sh`, `.agents/tests/session-start.sh`, `.agents/tests/kit-owns-worktrees-rehearsal.sh`, `.agents/tests/starter-rehearsal.sh`; `kit-names.sh` fails on a skill that reads `.ai-build-kit-maintenance`.
- `/maintain` and `/what-now` ask `repos/gwpicard/ai-loop-kit/releases/latest`; the shared route updates with `npx skills add gwpicard/ai-loop-kit`; a `skills-lock.json` entry counts as this kit only when it names `gwpicard/ai-loop-kit`. Check: `.agents/tests/stable-is-the-channel.sh`, `.agents/tests/shared-route-adds.sh`.
- Every workflow job's repository gate names `gwpicard/ai-loop-kit` and no other repository. The first snapshot commit already made the gates accept it, so the hosted checks have run since the first push; this slice removes any old name the snapshot left beside it. The release archive is `ai-loop-kit-<version>.tar.gz`. Check: `.agents/tests/release-publication.sh` (gate per job, archive name); `kit-names.sh` fails on a workflow naming `gwpicard/ai-build-kit`.
- A project whose `origin` names gwpicard/ai-loop-kit, or the old gwpicard/ai-build-kit, is recognised as a kit repository: founding opens no issue there and section-builder pushes nothing. Check: `.agents/tests/check-tooling.sh` with `origin` set to each name in https and ssh form; `.agents/tests/first-upload-asks.sh`.
- The Codex rules file stays `.codex/rules/ai-loop-kit.rules`, named so by slice 19. Check: `kit-names.sh`.

### Documents this slice touches
- README.md (title, badges, install lines), `llms.txt`, WORKFLOW.md (install and update), COMPATIBILITY.md (install and update commands), CONTRIBUTING.md, SECURITY.md, the issue forms ("AI Loop Kit version"), PHILOSOPHY.md, SOURCES.md's opening line, the foundation templates, root `AGENTS.md` and MAINTAINING.md carry the new name. The README says once that AI Loop Kit is for new projects and that a project founded with AI Build Kit stays on that kit. Check: `.agents/tests/kit-names.sh` over each file by name, and a rule-shape rule on the README sentence.
- The design note's "Commands" table row `/setup-ai-build-kit` becomes `/setup-ai-loop-kit`, so the note agrees with "The name". Check: `kit-names.sh` reads the row.

### When it is not the normal case
- A project founded with AI Build Kit, holding `.ai-build-kit-maintenance` and no `.ai-loop-kit-maintenance`, runs `/maintain` or `/setup-ai-loop-kit`: the kit changes nothing and says in one line that the project stays on AI Build Kit, which keeps its own fixes. It offers no move, renames no file and installs no bridge. Check: `.agents/tests/kit-names.sh` runs `/maintain`'s and founding's first step against a throwaway project holding only the old record file and finds it unchanged.
- An installation made under the old marketplace name `ai-build-kit`: it is an AI Build Kit installation, outside this kit; nothing here updates or moves it. Check: does not arise in this repository's checks, because the marketplace carries no old-name entry (`claude-plugin.sh` above).
- The old address `npx skills add gwpicard/ai-build-kit`: it installs AI Build Kit from the old repository, which stays on its 0.19 line. Nothing in this slice points at it. Check: `kit-names.sh` fails on a shipped install line naming the old repository.

## Masterplan change
Design note: "The name" (with v1 the product becomes AI Loop Kit in a repository of its own; the plugin and marketplace names, the founding command and the record files change). The note's "Commands" table changes its founding row to `/setup-ai-loop-kit`.

## Not in this piece
- A GitHub rename of gwpicard/ai-build-kit, a redirect from the old address, or a bridge plugin for old installations: none, by decisions 58, 62 and 63. The new repository already exists under its own name.
- A move for projects founded with AI Build Kit: none, by decision 63.
- Pointing the old repository's README at AI Loop Kit at the v1.0 release: the move plan's maintenance step in gwpicard/ai-build-kit, outside these slices.
- Publishing a release under the new name: slice 23: Release v1.0.
- Rewording documents beyond the name: slice 21: Documentation sweep.
- Removing the old repository's migration tooling (`docs/MIGRATION.md`, `docs/MIGRATION-READINESS.md`, `.agents/migration/`, `.agents/tools/preflight-cutover.sh`, `.agents/tools/rehearse-merged-tree.sh`) from the new repository: an open decision for the maintainer; this slice leaves it as it is.

## Decided
- The names are set in the last slice before the release, so v1.0 is the first release and carries only the new names (decisions 43, 52 and 53).
- No GitHub rename and no redirect: gwpicard/ai-loop-kit started from a clean snapshot and the old repository stays as it is (decisions 58 and 59).
- No bridge for old installations: the marketplace lists only `ai-loop-kit`, and no skill reads the old record names, because AI Loop Kit is for new projects (decision 63).
- The founding command becomes `/setup-ai-loop-kit` (decision 43 names the founding command among what changes).
- The record files take the new names outright, because 1.0 fixes the record format (decision 26) and no project needs the old names read.
- The kit-repository recognition keeps both names, because a clone of either repository is a kit repository and founding there would open issues on the kit itself.
- Internal names nobody outside reads keep their spelling: the replay's `abk-` paths and the migration tooling. MAINTAINING.md's "One owner per concept" already leaves an internal name alone where changing it churns output nobody reads.

## Data
- In founded projects: founding writes `.ai-loop-kit-maintenance` and `.ai-loop-kit-version`, and the founding skill is installed as `setup-ai-loop-kit`. No project founded with AI Build Kit is changed (decision 63).
- In this repository: the founding skill folder, the plugin and marketplace manifests, `release-manifest.txt`, the workflow gates and the release archive name.
- On GitHub: nothing; the repository already has its name.

## Leaves the tool
Nothing new leaves the tool, because every change is to files in this repository, which reach GitHub through this slice's pull request.

## Must still hold
- An installation updates only through the route it came from, and the shared route uses `npx skills add`, never a bare `npx skills update`. Check: `.agents/tests/shared-route-adds.sh`.
- `/maintain` asks only `releases/latest` and never names a draft. Check: `.agents/tests/stable-is-the-channel.sh`.
- Installers read `stable`, which only a verified release moves. Check: `.agents/tests/stable-is-the-channel.sh`.
- A pointer names a skill and a path inside it, never a fixed project folder. Check: `.agents/tests/plan-helper-routes.sh`.
- The founded `AGENTS.md` stays within its ceiling with the new command name. Check: `.agents/tests/standing-instructions.sh`.
- Founding refuses to open issues on the kit's own repository. Check: `.agents/tests/first-upload-asks.sh`, `.agents/tests/check-tooling.sh`.
- No issue numbers and no attribution lines in any tracked file. Check: `.agents/tools/validate-kit.sh`.

## Relies on
- `check-tooling.sh`'s kit-repository recognition and its rehearsal (present on main).
- The isolated plugin rehearsal in `.agents/tests/claude-plugin.sh` (present on main).
- The workflow gates accepting gwpicard/ai-loop-kit from the first snapshot commit (the move plan's step B2).
- The settled documents from slice 21: Documentation sweep.

## Reach and risk
Boundary: the founding skill's name, `/maintain`'s and `/what-now`'s release and update steps, the record file names, the plugin and marketplace metadata, the release allowlist and builder, the workflow gates, every document's product name.
Reaches: every rehearsal that names the founding skill's path (most files in `.agents/tests/`), the adapters (`validate-kit.sh`), the release machinery (`release-builder.sh`, `release-publication.sh`, `version-stamp.sh`), the installation routes (`claude-plugin.sh`, `agent-plugin.sh`, `plan-helper-routes.sh`, `starter-rehearsal.sh`).
If it breaks: a founding writes a record under the wrong name, or an install command fails, and the maintainer sees a rehearsal fail in the pull request check. Undone by reverting the slice's pull request; nothing online changes.
Depends on: 21.
Loop module: build, because each line is a rehearsal that fails today and passes after.
Crew: default for build.

## Under the hood
`git mv` the founding skill folder; replace the names in skills, templates, tools, workflows, manifests and documents; keep the old names only in the kit-repository list and the one sentence for a project founded with AI Build Kit; run `.agents/tools/build-adapters.sh`; update every rehearsal path. Write `.agents/tests/kit-names.sh` with `lib/rule-shape.sh` for the README sentence and a mechanical walk for the names. Existing rehearsals expected to change: nearly every file under `.agents/tests/` for the path, and in substance `shared-route-adds.sh`, `check-tooling.sh`, `first-upload-asks.sh`, `kit-version-record.sh`, `session-start.sh`, `claude-plugin.sh`, `agent-plugin.sh`, `release-builder.sh`, `release-publication.sh`, `stable-is-the-channel.sh`. Nothing from the overnight batch branch is reused.

Kit rules: the five questions in PHILOSOPHY.md are answered in the pull request, since the founding command and the maintain skill change; adapters rebuilt and committed with the change; validator and `run-all.sh` pass; humanizer and house rules for every sentence; no issue numbers; no attribution lines; no SOURCES.md row, since no outside idea lands.

## Evidence
Rehearsals in throwaway projects for every installation route under the new names, including an isolated plugin install from the `ai-loop-kit` marketplace; `kit-names.sh` with load-bearing proof; the full suite and the validator passing.

## Size
One sitting, mostly mechanical, with the plugin rehearsal and the one-line refusal for an AI Build Kit project as the real work.

## Consistency notes
- Decisions 56 to 63 replace the draft's "Rename to AI Loop Kit". There is no GitHub rename, no redirect check, no bridge plugin and no `/maintain` migration; the slice only sets the new names in the new repository.
- The repository-name gates in the workflows were made to accept gwpicard/ai-loop-kit in the first snapshot commit (move plan B2), so this slice only removes an old name left beside it.
- The record files are `.ai-loop-kit-maintenance` and `.ai-loop-kit-version` from this slice on; every earlier slice that names `.ai-build-kit-maintenance` means the same file before its rename.
- The one sentence for a project founded with AI Build Kit is a refusal, not a bridge: it changes nothing and points nowhere. Slice 17 says the same in `/maintain`, and this slice gives it the record file that tells the two kits apart.
- Removing the old migration tooling from the new repository is an open decision; this slice leaves it alone.
