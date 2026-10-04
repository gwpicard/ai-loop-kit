---
name: maintain
description: The service visit for AI Build Kit updates, project upkeep, handovers, and retirement. Trigger monthly for the light pass, quarterly or before any handover for the full one, and when a tool is being retired. Composes sync and the evidence run instead of repeating them. Do not use for building, fixing, or planning.
---

# Maintain

Small regular maintenance is what keeps the rare big problem from arriving. Report findings before applying anything beyond routine updates.

## Monthly, light

1. Read this skill's `VERSION` file, which is the version this project holds.
   Then ask for the latest published one with
   `gh api repos/gwpicard/ai-build-kit/releases/latest --jq .tag_name`. Ask
   that endpoint and no other: it is the only one that cannot answer with a
   draft or a prerelease, while `gh release list` puts an unpublished draft in
   its first row for anybody who can see the repository, which would offer an
   update that does not exist yet.

   Say both numbers, every visit, whichever way they compare: "This project
   holds v0.15.0, and the latest published AI Build Kit is v0.16.0." Where they
   differ, say so plainly rather than leaving the person to compare two numbers,
   read the newer version's notes, and add: "A newer AI Build Kit is available.
   It refreshes the installed workflow skills. Your tool, project records, and
   project instructions remain yours." Give a short summary, then wait for
   approval. Where they match, say the project is on the latest published
   release and carry on with the visit.

   Where the call cannot be made at all, because the GitHub tool is missing or
   signed out, say that the version check did not happen. Never say the project
   is up to date on the strength of a call that failed: the whole reason this
   step names one endpoint is that a project was once told it was current while
   holding work that no release had ever contained.
2. Before registering or changing the kit, require the clean checkpoint used by
   the current build path. For a shared skills installation, check whether any
   AI Build Kit skill has local edits. Project-specific rules belong in
   AGENTS.md. If such edits exist, explain them and propose moving the durable
   rule there. Wait for approval rather than replacing an edit silently.
3. Identify how this project receives AI Build Kit. Check whether
   `skills-lock.json` records skills from `gwpicard/ai-build-kit`. Where it
   does, count its entries against the fourteen names and say which are
   missing. A short installation means a skill the kit renamed or added never
   arrived. The version file cannot show this, because the same update that
   drops a skill rewrites the version, so the count is the only sign.
   In Claude Code, also use `claude plugin list --json` to check for the enabled
   `ai-build-kit@ai-build-kit` plugin and note its installation scope. Also
   check for an Agent Plugins installation: a `plugin.json` naming
   `ai-build-kit` beside a `skills` folder, wherever this coding agent keeps
   its plugins. If more than one route is active, stop and ask the person which
   one to keep. Use a plugin when one coding agent runs the project and the
   shared skills installation when the project uses several coding agents.
4. Update only through the route found in step 3:

   - For the Claude plugin, refresh its marketplace with
     `claude plugin marketplace update ai-build-kit`, then run
     `claude plugin update ai-build-kit@ai-build-kit --scope <scope>` using the
     scope reported in step 3.
   - For an Agent Plugins installation, use the coding agent's own plugin
     update command. When the agent has none, download the latest public
     Release and replace the installed `agent-plugin` folder after the same
     approval and clean checkpoint.
   - For a shared skills installation, run
     `npx skills add gwpicard/ai-build-kit` and let the person choose the same
     coding agents the project already uses. Choosing `universal` is what puts
     the real folder under `.agents/skills/`. This command refreshes a skill
     that is installed and adds one that is missing. Do not use
     `npx skills update` for the kit: it refreshes only what the lockfile
     already lists and drops any other name without a word, so it cannot
     carry a project across a rename.
   - When no route is present, this is an older installation. After
     approval, run the same `npx skills add gwpicard/ai-build-kit`. This
     registers and refreshes the existing skills, so do not run a second
     update on the same visit.

   Do not update unrelated plugins, project skills, or global skills.
5. For the shared route, confirm that this skill's `VERSION` now matches the
   version step 1 read from `releases/latest`, and that the count from step 3
   is now fourteen. When the shared installation did not have `screen-check`
   before this visit, confirm that the same `npx skills add` command added it,
   and carry on only once it is there. A matching version
   alone is not proof the installation is whole. For the Claude route, confirm
   that `claude plugin list --json` reports the matching version without the
   leading `v`. Claude loads an updated plugin after `/reload-plugins` or the
   next session, so say that plainly. For an Agent Plugins installation,
   confirm the version in the
   installed `agent-plugin/plugin.json` and in that folder's
   `skills/maintain/VERSION`. Run the project's own check and record the kit
   version in the changelog with the saved change. Once the update is
   confirmed, rewrite the `kit` line in `.ai-build-kit-maintenance` with the new
   version and the commit its tag points at, as `kit|<version>|<commit>`. Read
   the commit the way the `setup-ai-build-kit` skill's step 7 does, and write
   `unknown` where that lookup fails. The foundation created by
   start, including AGENTS.md, README.md, project records, environment files,
   application code, and the project's check, stays project-owned. When this
   update is the one that first brings in `/shape` and `/implement`, run the
   one-time migration in "Migrating a project founded before /shape and
   /implement" below. When the visit finds a `start` skill, or no
   `setup-ai-build-kit` skill, also run "Migrating a project founded before the
   setup-ai-build-kit rename". When it finds a `plan` skill, or no `shape`
   skill, also run "Migrating a project founded before the shape rename". Both
   are decided by what is on disk rather than by which update this is, because
   an update that removed the old skill without adding the new one leaves
   nothing else to say it happened. Whenever the build-path section of
   `masterplan.md` carries a `Required controls:` or `Outside help:` line, or
   a `Path:` value the kit no longer uses, also run "Migrating a masterplan
   written with four build paths" below; that too is decided by what the
   masterplan says rather than by which update this is. On the shared route,
   also run "Tidying a project founded from a whole copy of the kit" below
   whenever the leftovers it names are present. On every route and every
   visit, run "Adding the plan printout helper" below; it does nothing when
   the project's copy is already current. On every visit, run "Pointing the
   records at a skill by name" below, and whenever a `plan.md` is at the
   project root, run "Moving a plan.md into issues" below. Both are decided by
   what is on disk, so a project that missed the update which first needed
   them still gets them.
6. Re-read the capability profile's reach-check engine against what the
   harness and project can use now. Keep the same preference order as
   the `section-builder` skill's `references/reach-check.md`, and update the
   profile when a better engine has appeared or the recorded one has gone.
7. Run the sensitive-area check installed during founding. It is silent outside
   Build with care. Where it names a missing path or an unassigned source folder,
   ask which sensitive area it belongs to, or whether it belongs under `none`,
   then update the map only after the person answers.
8. If the normal route is unavailable, use the latest published Release, the
   one step 1 read, as the fallback source. A shared installation may replace
   only the fourteen AI Build Kit skill folders after the same approval and
   clean checkpoint. A Claude
   plugin installation keeps its current enabled version when the marketplace
   cannot be reached. Confirm that version with `claude plugin list --json`,
   tell the person the update did not happen, and retry when the marketplace is
   reachable. Do not create a second installation or claim that the project
   checkpoint can restore Claude's plugin cache. If the plugin is no longer
   enabled, stop and ask the person to reinstall it after the marketplace is
   reachable.
9. Read the masterplan's trued-against mark and count landed changes since it
   using the `setup-ai-build-kit` skill's `references/masterplan-changes.md`.
   When data, permissions or connections were touched, report the count and
   offer /sync in one line. An absent or unusable mark gets the same offer
   without a guessed count. Then update project dependencies and check for known
   vulnerabilities. Report what changed; apply on approval.
10. Once live: read the error alerts and the bills. Anything real becomes a piece, for implement to take: open an issue in the shape the `setup-ai-build-kit` skill's `references/pieces.md` describes. A finding nobody wrote down is a finding nobody acts on.
11. Verify backups still run where the tool has any. A check that needs a secret reads where it lives from the masterplan first, asks once when that is unknown, and never calls the secret absent. Confirm the named operational owner from the masterplan still holds that role, and that no critical service or credential is tied to someone who has left.
12. Check whether use or reliance has grown enough that the fit check should run again; if it has, run it before anything else this visit.
13. On every build path, count every line in the project's AGENTS.md, including
    blank lines, and read it for a directory layout, dependency list,
    architecture overview or style rule an automatic check could enforce. It
    stays under 200 lines and holds only what the code cannot show: the save
    and review routes, conventions that differ from the default, and pointers
    to the records.

    At 200 lines or more, or with any of the named content even below that
    count, offer a trim in one line, using the measured count and what can
    go: "The standing instructions have reached 240 lines, and 30 of them
    describe the folder layout the code already shows. Shall I trim them?"

    Where length alone triggers the offer, name that alone; never invent
    removable content to fill the example. Cut nothing without the person's
    yes. A no leaves the file intact and the visit carries on. If the file is
    short and carries none of that content, say nothing. Where step 17 will
    offer the move onto the index this visit, make that offer instead of the
    trim, since the move does the trim's work.

    On a project already on the index, the trim is a move, never a cut: on a
    yes, each fact goes to its home as step 17's move sends it. Lasting
    technical design goes to its `docs/<concept>.md`, history to a file in
    `changes/`, product facts to the masterplan, and dates, issue numbers and
    code names leave AGENTS.md. That is the fix the project check's red
    message names.
14. Unless the project explores privately, run "Offering a move onto a
    recipe" below. When no recipe on the menu is close to the project's stack,
    it says nothing.
15. On every build path, load `references/stale-branches.md` and list the
    branches whose work is already in the default branch, each with the
    command that removes it. List this computer and GitHub separately. Keep
    the ones Git confirms apart from the ones only GitHub records as merged.
    Never remove a branch. When no branch qualifies, say nothing.
16. Run "Adding the rules that stop a push to `main`" below. It says nothing
    when the project already has them, or when the person said no to the same
    rules before. Then run "Adding the confirmation box on merges that go
    live" below. It says nothing unless every merge goes live and the rules
    are missing, and nothing when the person said no to the same rules before.
17. Run "Moving the instructions onto the index" below. It says nothing when
    the project is already on the index, or when the person said no to the
    move before.
18. Run "Removing leftover worktrees" below. It says nothing when the project
    has none.
19. Run "Linking ignored build files into run worktrees" below. It says
    nothing when the project already has the links, has nothing to link, or
    said no to the same files before.
20. Run "Recording the project's own check" below. It says nothing when no
    placeholder sits beside CI of the project's own, or when the person said
    no before and the workflow files have not changed since.
21. Record the visit. In `.ai-build-kit-maintenance` at the project root, put
    today's date on the `last-light-pass` line, written as YYYY-MM-DD. If that
    file is missing, create it with a `founded` line holding the date
    masterplan.md was first saved, then the two pass lines. Where the file
    has no `kit` line, or its version differs from this skill's `VERSION`
    because the kit was updated some other way, write the line from this
    skill's `VERSION` and its tag's commit, the same way step 5 does. A project
    founded before the line existed gets it here. If the project has
    no `.agents/hooks/session-start.sh`, copy it from the installed
    setup-ai-build-kit skill's `templates/foundation/session-start.sh`, unless
    the person asked during this visit to leave kit updates alone. That script
    comes from the kit, and it changes what the project does later. Read what
    they asked, not a fixed phrase. Where the project has the script and it
    differs from that template, the project kept an older copy, since an update
    never reaches it. Say in one line: "A newer reminder script counts the work
    landed since the last visit as well as the days. Shall I replace yours?"
    Add that replacing it also drops any change made to the project's copy by
    hand. Replace it only on a yes, and make no offer when the person asked for
    no kit updates. A no changes nothing, and the next visit makes the same
    one-line offer again. Then say one sentence: "I have recorded
    today's visit, so a session will not remind you again until the next one is
    due." Where you skipped the script, say instead: "I have recorded today's
    visit. I left out the script that reminds a session when a visit is due,
    since you asked for no kit updates, so that reminder will not appear by
    itself; /what-now still reports it when asked." If the project's Claude
    settings existed before AI Build Kit did, add that the reminder cannot
    appear by itself there, and that `/what-now` reports it when asked.

## Adding the plan printout helper

`plan.local.md` is written by `.agents/tools/plan-refresh.sh` in the project.
That helper ships inside the setup-ai-build-kit skill and founding copies it
in. A project founded before that has no copy, unless it came from a whole copy
of the kit, and then its copy may be older. An update refreshes skills and
nothing else, so the helper would never arrive.

On the clean checkpoint from step 2, and after the update where the person
approved one, run `sh <installed setup-ai-build-kit skill>/scripts/place-plan-helper.sh`
from the project root. It places the helper, and beside it the gate script, `.agents/tools/gate.py`, and the state guard hook, `.agents/hooks/state-guard.sh`,
since an update brings none of them. The ready-gate lint the gate calls,
`.agents/tools/ready-lint.py`, is placed beside the gate script the same way. It adds each one when it is missing,
replaces a copy that differs from the installed one, and changes nothing when
the copy is current, so it is safe on every visit. It refuses a link or a
folder where one of them belongs.

Where it added the helper, say one sentence: "I have added the helper that
prints your list of pieces, so /what-now, /queue and /implement read what is
ready from it rather than from the issues by hand." Where it replaced one, say
that the helper was brought up to date, and that any change made to the old
copy by hand was replaced too and is kept in the checkpoint saved first. Where
it made the helper runnable again, say so, since that is a change to save.
Where it added or replaced the gate script or the hook, say so the same way:
the gate script is the one way a piece changes state, and the hook stops a
state label being written by hand. Save any of these changes with the visit's
other changes and add a dated changelog line. When it changed nothing, say
nothing. Where the harness cannot run the script and the project has no
helper, copy the installed skill's `templates/foundation/plan-refresh.sh` to
`.agents/tools/plan-refresh.sh` by hand.

## Adding the rules that stop a push to `main`

Founding copies the kit's Claude Code settings into `.claude/settings.json`
once, and no update touches that file again. A project founded before the kit
learned a new way to write a push to `main` keeps the older rules, and a push
the older rules miss goes through with nothing to stop it. The same holds for
the rules that refuse deleting a folder with everything in it and clearing
Git's recovery history. So the visit offers the missing rules, once.

1. Where the project has no `.claude/settings.json`, this step ends. Otherwise
   read its `permissions.deny` list, and the one in the installed
   setup-ai-build-kit skill's `templates/foundation/claude-settings.json`.
   Take the rules from that file, never from memory.
2. List each rule the template holds that the project's list lacks, and that
   names both `git push` and `main`, or `rm` with a recursive option, or
   `git reflog expire`, or `git gc` with `--prune`. Leave out every other
   rule, such as the force-push ones, since the person may have removed one on
   purpose. When there is none, say nothing.
3. Read the `push-rules-declined` line in `.ai-build-kit-maintenance`, if there
   is one. Where it already lists every missing rule, the earlier no stands,
   and you say nothing. Otherwise offer only the missing rules that line does
   not list. A line written before the delete rules lists none of them, so the
   offer comes back once for those.
4. Offer the change once, in one reply. Name the rules it adds, and say in
   plain words what they stop: a push to `main` written with an option before
   the remote, such as `-q`, or as `HEAD:refs/heads/main`; deleting a folder
   with everything in it, in the common spellings; and clearing the history Git
   uses to recover lost work. Say that it adds
   lines to the deny list and changes nothing else in the file. Say too that
   the `setup-ai-build-kit` skill's `references/blocked-commands.md` lists the
   spellings the rules still cannot catch. Ask for a yes.
5. On a yes, add only the missing rules to the end of `permissions.deny`. Keep
   every other entry and setting as it is, even an older push rule the new
   ones cover. Check that the file still reads as valid JSON. Save it with the
   visit's other changes and add a dated changelog line.
6. On a no, change nothing. Record the no as one line in
   `.ai-build-kit-maintenance`, replacing any earlier one:
   `push-rules-declined|<YYYY-MM-DD>|<every rule declined, this time and before, separated by " ; ">`.
   A later visit offers again only when a new release adds a rule that line
   does not list.

## Adding the confirmation box on merges that go live

Founding, the merge step and `/ship` set Claude Code's confirmation box when
they record that every merge goes live. A project that recorded that line
before the kit did so has the line and not the box, and a merge there goes
live with nothing mechanical in the way. So the visit offers the rules, once.

1. Where the project has no `.claude/settings.json`, or the masterplan's
   `Goes live:` line does not say `on every merge`, this step ends.
2. Read the rules in the installed setup-ai-build-kit skill's
   `templates/merge-ask-rules.json`, never from memory, and list each one the
   project's `permissions.ask` list lacks. Where it lacks none, say nothing.
3. Read the `merge-ask-declined` line in `.ai-build-kit-maintenance`, if there
   is one. Where that line names every missing rule, the person's no stands,
   and you say nothing.
4. Offer them once, in one reply. Name the rules, and say in plain words what
   they do: Claude Code shows a confirmation box before each merge, because
   every merge puts the tool live. Say that it adds lines to the ask list,
   leaves the rest of the file as it was, and works on Claude Code only. Wait
   for a yes.
5. On a yes, run
   `python3 <installed setup-ai-build-kit skill>/scripts/merge-ask-rules.py add .claude/settings.json`
   from the project root. Where it exits 1, the file is not valid JSON: say
   so, name the file, and change nothing. Save the change with the visit's
   other changes and add a dated changelog line.
6. On a no, leave the file as it is. Record the no as one line in
   `.ai-build-kit-maintenance`, replacing any earlier one:
   `merge-ask-declined|<YYYY-MM-DD>|<the rules offered, separated by " ; ">`.
   A later visit offers again only when the template holds a rule that line
   does not list.

## Moving the instructions onto the index

A project founded before its AGENTS.md became an index keeps one long file,
often with architecture, history, dates and issue numbers in it, and its copied
project check has no step that counts the file. An update refreshes the skills
and never those two files. So the visit offers the move, once. It rewrites
records, so do it only after the clean checkpoint from step 2.

1. Where the project's AGENTS.md has a `## Standing rules` section and the job
   the capability profile's `Project check:` line records
   (`.github/workflows/checks.yml`, job `project-check`, where that line names
   no file) has the `Check the AGENTS.md ceiling` step, the project is already
   on the index: say nothing, and this step ends. A second visit after a yes
   finds both and says nothing. Where that line ends `; kit steps not added`,
   the person turned the kit's steps down: the section alone puts the project
   on the index, and the move adds no step.
2. Read `.ai-build-kit-maintenance`. Where there is an `index-declined` line,
   and the section headings it lists are the ones the installed template has
   today, the earlier no stands: say nothing, and this step ends.
3. Work out the move before saying anything, from the installed
   `setup-ai-build-kit` skill's `templates/foundation/AGENTS.md`:
   - under `## Standing rules`, the kit's rules take the template's wording,
     and the project's own rules follow them word for word;
   - each other section takes the template's shape, short, and names the file
     that owns its topic;
   - lasting technical design moves into `docs/<concept>.md`, one concept to a
     file, under the headings What it is, How it works, Rules, and Where it
     lives, each file listed with what it owns in `docs/README.md`, and the
     technical design section pointing at that list;
   - history moves into the changelog, and product facts into the masterplan;
   - dates, issue numbers and code names leave AGENTS.md;
   - the ceiling step comes with the move: copy the step named
     `Check the AGENTS.md ceiling` from the installed skill's
     `templates/foundation/checks.yml` into the recorded job, beside its own
     steps.

   Every fact that leaves AGENTS.md lands in its home. Nothing is deleted, and
   nothing goes into a new catch-all document.
4. Offer the move onto the index once, in one reply. Say how many lines
   AGENTS.md has now and would have, which concept files it creates, and that
   the check gains a step that goes red above 200 lines. Where AGENTS.md is
   already above 200 lines, say that the step alone would turn the check red,
   which is why the two come together. Then wait for the answer.
5. On a yes, make the move and add the ceiling step, then count AGENTS.md
   again and check that it is at or under 200 lines and that every file it
   points at exists. Where it is still above 200 lines, name the sections that
   remain large and offer the trim from step 13 for them, in one line. Save
   with the visit's other changes and add a dated changelog line.
6. Where the person says no, change nothing. Record the no as one line in
   `.ai-build-kit-maintenance`, replacing any earlier one:
   `index-declined|<YYYY-MM-DD>|<the template's section headings, separated by " ; ">`.
   The offer does not come back until a release changes those headings, and
   then it comes back once. The trim offer in step 13 still runs on every
   visit.

## Removing leftover worktrees

A run on Claude Code builds each piece in a worktree under
`.agents/worktrees/`, and clears it away once its pull request has closed, as
the `implement` skill's `references/running-longer.md` says. A worktree can
still be left over, such as when a session died before the next run or
`/sync`. A leftover worktree also keeps its branch out of the old-branches
list in step 15, since git will not remove a branch that is checked out.

1. Run `sh <installed implement skill>/scripts/worktree.sh leftovers` from the
   project root. It lists each worktree under `.agents/worktrees/` whose pull
   request has merged or closed, or that never had one, or that is on no
   branch, and that no unfinished run is still building. It changes nothing.
   It leaves alone every worktree another tool made, wherever it sits, and
   never lists one. When it lists none, say nothing.
2. Name each one in plain words: the piece, what happened to its pull request,
   and whether it holds unsaved work. Offer to remove the ones that hold none,
   each by name, in one reply.
3. On a yes to a worktree, remove it with `worktree.sh remove <path>`. It uses
   `git worktree remove` and never forces it, and it checks again that nothing
   in the worktree is unsaved and no pull request from it is open. It removes
   the worktree's link to `.env`, never the main `.env`.
4. Never remove a worktree that holds unsaved work. Keep it, and say what is
   unsaved: the uncommitted changes, or the commits only this computer
   holds.
5. Where it names a worktree whose folder is already gone while git still
   lists it, offer to run `git worktree prune`, which clears only that record.
   Run it on a yes.
6. Never remove a branch here. Removing a worktree leaves its branch, and
   step 15 lists that branch at the next visit once its work is in the default
   branch.

## Linking ignored build files into run worktrees

A run builds each piece in a worktree, which has only what git tracks plus the
links the kit makes. A project whose build needs a file git ignores, such as a
licensed font, has every piece in a run fail for want of it. Founding now asks
which such files a build needs and writes a `worktree-links` line. A project
founded before that has no line, so the visit offers it, once.

1. Where `.ai-build-kit-maintenance` already has a `worktree-links` line, say
   nothing, and this step ends.
2. From the project root, run `sh <installed implement skill>/scripts/worktree.sh candidates`.
   It lists the ignored files and folders at the top two levels, leaving out
   dependency and build folders, every `.env` file, `.agents/`, `.claude/`,
   system files such as `.DS_Store`, and any folder on a `confidential` line. Leave out the folder AGENTS.md records as
   confidential as well. Where nothing is left, say nothing, and this step
   ends.
3. Where every path it lists is already on a `worktree-links-declined` line,
   the earlier no stands: say nothing, and this step ends.
4. In one reply, name the paths and ask once which of them a build or a
   walk-through needs, with your best guess attached: a font, a sample input,
   or an asset folder the build reads. Say that each is linked into a run's
   worktrees and never copied.
5. On a yes, write the paths the person confirms as
   `worktree-links|<path> ; <path>`. Where AGENTS.md records a confidential
   folder and the file has no `confidential` line for it, write the
   `confidential|<folder>` line too. Save with the visit's other changes and
   add a dated changelog line.
6. Where the person says no, link nothing. Record the no as one line,
   replacing any earlier one:
   `worktree-links-declined|<YYYY-MM-DD>|<the paths offered, separated by " ; ">`.
   A later visit offers again only when a new ignored path appears that the
   line does not list.

## Recording the project's own check

A project founded before founding recorded the project check may have been
given the kit's placeholder `checks.yml` beside CI of its own that already
runs its tests. Every pull request then shows a red check beside a working
one. The visit offers to put that right, once.

1. Where `.github/workflows/checks.yml` no longer holds the kit's placeholder
   `Install and test` step, say nothing, and this step ends. Do the same
   where no other workflow in `.github/workflows/` runs on `pull_request` with
   a `run:` line containing `test`. A `Project check:` line that names
   `checks.yml`, or no file, is no reason to stop: an older founding wrote
   that form beside CI of the project's own. Where the line already names
   that other workflow, the record is done, and the offer below is only the
   removal of the placeholder.
2. Read the `project-check-declined` line in `.ai-build-kit-maintenance`, if
   there is one. Where no commit dated after that line's date has changed
   `.github/workflows/`, the earlier no stands: say nothing, and this step
   ends.
3. Choose the job as the installed `setup-ai-build-kit` skill's
   `references/project-check.md` says. In one reply, offer three changes,
   each taken only on its own yes: record that workflow and job as the
   project check; remove the placeholder `checks.yml`, which turns red on
   every pull request and checks nothing; and add the kit's steps to that
   job, saying that this changes the project's own automation and what each
   step turns red on. Leave the third out on a Windows runner, as that file
   says. The other two are asked only alongside the record, and happen only
   after a yes to it.
4. On a yes to the record, write the `Project check:` line, ending
   `; kit steps not added` where the steps were not added. Add the steps to
   the end of the job's steps and change nothing else in the file. Save with
   the visit's other changes and add a dated changelog line.
5. Where the person says no to the record, change nothing. Record the no as
   one line in `.ai-build-kit-maintenance`, replacing any earlier one:
   `project-check-declined|<YYYY-MM-DD>|<file>`. A later visit offers again
   only when the workflow files change.

## Migrating a project founded before /shape and /implement

Run this once, on the visit whose update first replaces `/build` with `/shape`
and `/implement`. It brings an existing project's records up to the new model.
It changes labels and, with approval, moves records, so do it only after the
clean checkpoint from step 2. Every part is idempotent: a later visit that finds
the project already migrated does nothing here.

1. Backfill the `ready` label. `/implement` builds only pieces labelled `ready`,
   and a project founded earlier has none, so without this its whole backlog
   goes unbuilt. For every open issue that is already shaped, a `## Done when`
   present and no `needs-clarification`, `needs-prototype`, or `needs-research`
   label, add the `ready` label. Leave anything still carrying a `needs-` label
   alone; that one is `/shape`'s to shape. Say how many pieces were marked ready,
   so the person can see their backlog is still there.

2. Move a `plan.md` into issues, as "Moving a plan.md into issues" below says.

3. Point `/build` forward. Say once that the old `/build` command has become
   two: `/shape` to shape a new idea into a ready piece, and `/implement` to build
   one. Nothing the person saved is lost; only the command names changed.

Record the migration in the changelog as a dated line.

## Moving a plan.md into issues

Run this on any visit that finds a `plan.md` at the project root, for as long
as it is there. It used to run only on the visit that first brought in
`/shape` and `/implement`, and a project that missed that visit kept its
`plan.md` for good, with nothing to say its pieces were never picked up.

A project founded without the GitHub tool signed in kept its pieces in
`plan.md`, which nothing reads any more. Where the file is plainly something
else of the person's, such as their own notes, leave it and say nothing.
Otherwise say so plainly and offer to move its rows into issues: guide the
GitHub setup first if it is not ready (the `setup-ai-build-kit` skill's
`references/manual-setup.md`), open one issue per row in the shape the
`setup-ai-build-kit` skill's `references/pieces.md` describes, carry each
row's subjects across as labels, label a shaped row `ready`, and label an
unshaped one `shaping` with the question it still waits on. Do this on the clean
checkpoint, name what moved, and only then remove `plan.md`. Record the move
in the changelog as a dated line.

Where the person declines, leave `plan.md` untouched and say its pieces are not
picked up until they are moved. Nothing records the no, so the offer comes back
on the next visit that still finds the file. Say that too, in the same reply.

## Pointing the records at a skill by name

Run this on every visit. A project founded before the kit named its pointers
by skill carries lines in AGENTS.md and masterplan.md that name a skill's file
by its place in the project's `.agents/skills/` folder. A project installed
for Claude Code alone, or through a plugin, has no such folder, so the line
opens nothing. The current form names the skill and the path inside it: the
`setup-ai-build-kit` skill's `references/pieces.md`. An update refreshes the
skills and never touches these two files, so the old lines stay until the
visit changes them.

1. From the project root, run `python3 <installed maintain
   skill>/scripts/old-skill-pointers.py`. It reads only those two files and
   prints one line for each old pointer it finds, and nothing when there is
   none. It finds a pointer into one of the kit's skills under today's name
   or one it had before, such as `start` for `setup-ai-build-kit`. A project's
   own skill, a placeholder such as `<name>`, and a mention of the folder
   itself are never found. When it prints nothing, say nothing.
2. A line ending in the new form is one the script can rewrite: the pointer
   stands alone, as a whole code span or a bare path, and the skill still has
   the file. A line ending in `left as written:` gives the reason it cannot,
   such as a pointer inside a code block, a command or a link, where a
   rewrite would break the line. Those are never rewritten. A rewrite changes
   the pointers and nothing else in the file, line endings included.
3. Offer the rewrite once, in one reply: say how many lines in which file, that
   each keeps its sentence and only the pointer changes, and show one line
   before and after. Name each line left as written, with its reason, as one
   the person may want to change by hand. Wait for the person's yes. Where the
   script finds only lines left as written, offer nothing: say in one line how
   many there are and in which file, since they come back on every visit
   until the person changes them.
4. On a yes, run the same command with `--apply`, then run it again without,
   and carry on only once no line it prints ends in a new form. Save the
   change with the visit's other changes and add a dated changelog line.
5. Where the person says no, leave both files as they are. The offer comes
   back on the next visit that still finds an old pointer.

Where the harness cannot run the script, leave the files as they are and say
that the check did not run. A rewrite by hand cannot tell a pointer that stands
alone from one inside a command, and getting that wrong breaks the person's
line.

## Migrating a project founded before the setup-ai-build-kit rename

Run this on any visit that finds a `start` skill installed, or no
`setup-ai-build-kit` skill. It is idempotent: a visit that finds only
`setup-ai-build-kit` does nothing here.

The founding command was renamed from `/start` to `/setup-ai-build-kit`. Founding
runs once, so a project already founded never types it again, and nothing the
person saved is affected. Two housekeeping steps keep the installation tidy:

1. Remove a stale `start` skill. The shared installer asks whether to remove a
   skill that has gone upstream, and an older installer removed nothing, so
   three states are possible. Where a `setup-ai-build-kit` skill and an old
   `start` skill both exist, offer to remove the `start` one, because it is a
   managed package the kit renamed rather than the person's own work. Where
   neither exists, the update removed the old skill without adding the new
   one: run the add command from the monthly step, then read the skill folder
   back and carry on only once `setup-ai-build-kit` is there. Where only
   `setup-ai-build-kit` exists, there is nothing to do. On a yes, remove a
   tracked `start` folder with `git rm -r <folder>`, which the saved history
   can undo and no deny rule refuses. Where the `start` folder is untracked,
   give the person the command to run, with the folder's path, since a
   recursive delete is refused.

2. Point the founding command forward. Rewrite the command list in the
   project's AGENTS.md as "Bringing the project's instructions up to the
   current names" below says, so the person is not left to do it. Then say
   once that the command that founds a project is now `/setup-ai-build-kit`,
   not `/start`, and that any saved command which updates the kit by name uses
   that new first name. The full update command is in the monthly step above.

Record the tidy-up in the changelog as a dated line.

## Migrating a project founded before the shape rename

Run this on any visit that finds a `plan` skill installed, or no `shape`
skill. It is idempotent: a visit that finds only `shape` does nothing here.

The command that turns an idea into a ready piece was renamed from `/plan` to
`/shape`. Some coding agents, Claude Code among them, now carry a `/plan` of
their own, so one name pointed at two different commands. Nothing the person
saved is affected and no record changes, but this command is typed most days, so
the new name is said out loud rather than only tidied away in the files:

1. Remove a stale `plan` skill. The shared installer asks whether to remove a
   skill that has gone upstream, and an older installer removed nothing, so
   three states are possible. Where a `shape` skill and an old `plan` skill
   both exist, offer to remove the `plan` one, because it is a managed package
   the kit renamed rather than the person's own work. Where neither exists,
   the update removed the old skill without adding the new one: run the add
   command from the monthly step, then read the skill folder back and carry on
   only once `shape` is there. Where only `shape` exists, there is nothing to
   do. On a yes, remove a tracked `plan` folder with `git rm -r <folder>`, as
   for `start` above. Where the `plan` folder is untracked, give the person the
   command to run, with the folder's path.

2. Point the command forward. Rewrite the command list in the project's
   AGENTS.md as "Bringing the project's instructions up to the current names"
   below says, rather than asking the person to do it. Then say once that
   `/shape` is the command that turns an idea into a ready piece, that it does
   everything `/plan` did, and that a saved note or shortcut typing `/plan`
   still needs changing by hand. The full update command is in the monthly
   step above.

Record the tidy-up in the changelog as a dated line.

## Migrating a masterplan written with four build paths

Run this on any visit that finds, in the build-path section of
`masterplan.md`, a `Required controls:` line, an `Outside help:` line, or a
`Path:` of `Build with expert help` or `Professional-led`. It is idempotent: a
section whose fields are Path, Why, Sensitive areas, Accepted, Recheck when
and Last checked, with a `Path:` of one of the three current names, gets
nothing here, and a second visit after the rewrite finds exactly that.

The kit went from four build paths to three. The two most careful paths asked
who should own the build. The path is now decided by what the work touches,
and a masterplan names each sensitive area with the one caution that has to
happen there. Nothing the person decided is lost: the old fields carry across,
and every accepted risk stays word for word.

1. Work out the new section before saying anything. `Explore privately` and
   `Build and run it` keep their name. `Build with expert help` and
   `Professional-led` become `Build with care`. `Outside help: none`
   contributes nothing. `Outside help: <level>, for <scope>` becomes one line
   under `Sensitive areas`: the scope named as one of the six areas in
   fit-check.md where it plainly is one, what in the tool touches it, the help
   level as its caution, and `not yet done` unless the changelog records that
   it happened. Each `Required controls` entry that protects a place in the
   tool (a review of who can see what, a backup, a rehearsal on a copy, a
   managed provider) becomes a line for the area it protects, or joins the
   line the scope already made where they are the same area. A control that
   names no area (secrets out of code, destructive actions stop for approval,
   a pull request with a check) is a standing rule of the kit and of the save
   route, so it leaves the block; say so in the changelog line. `Accepted`,
   `Recheck when` and `Last checked` are copied word for word, including an
   old line that says the path moved, because they are history and a rewrite
   is not a check.
2. Say this, then show the section as it is and as it would be, one above the
   other: "Your masterplan's build-path section was written when the kit had
   four build paths. It now has three, and the path is decided by what the
   work touches rather than by who owns the build. I can rewrite the section
   to the new shape. Every accepted risk stays exactly as written, and nothing
   else in the masterplan changes. Shall I apply it?"
3. Apply on approval, as part of the visit's saved change. Where a control or
   a help line cannot be matched to one of the six areas, keep its words as
   they are on their own line under `Sensitive areas` and say so, rather than
   guessing; the next fit check tidies it.
4. Where the person declines, leave the section untouched. Say that the kit's
   skills now look for `Sensitive areas`, so a control recorded in the old
   fields may be missed until the section is rewritten, and that the offer
   comes back next visit.

Record the migration in the changelog as a dated line naming the old path,
the new one, and any control that left the block. Where an old `Accepted:`
line says the path moved, the changelog line says that acceptance predates the
rename, so a later reader does not go looking for a path the kit no longer
has.

## Bringing the project's instructions up to the current names

Run this from either rename migration. A project's AGENTS.md is project-owned
and no update touches it. But the line that lists the commands is the kit's own
template text, and a person made to fix it by hand after every rename will stop
updating. So the kit does it for them, with approval:

1. Find the line that lists the commands. In the foundation template it begins
   `- Commands:` and names all nine. Where it names `start`, replace it with
   `setup-ai-build-kit`. Where it names `plan`, replace it with `shape`. Where
   `queue` is missing, add it after `implement`. Where the sentences nearby
   give an older count of commands or skills, make them nine and fourteen.
2. Show the change and apply it on approval. Say what changed in one sentence.
3. Where the file lists the commands in its own words and the line cannot be
   recognised, leave the file alone and say which name needs changing, so the
   person edits one line rather than reads a diff.

Record it in the changelog with the tidy-up that called it.

## Tidying a project founded from a whole copy of the kit

Run this on any visit on the shared route that finds the leftovers below. It
is idempotent: a project that has none of them gets nothing here.

A project founded from a whole copy of the kit brought the kit's own generated
adapters with it: `.claude/commands/<name>.md`, `.cursor/commands/<name>.md`
and `.gemini/commands/<name>.toml`. Only the kit's repository and the Claude
plugin need those. On the shared route the installer's own symlinks under
`.claude/skills/` do their job, and the installer never refreshes them because
it does not know they exist. So every command appears twice in Claude Code, and
a command the kit has renamed lives on in a file nothing will ever remove.
Deleting the files by hand in one project fixes one project, which is why this
is a step here rather than advice:

1. Find the kit's adapters. An adapter is recognised only by the generated
   marker on its first lines, which names `.agents/skills/` and
   `build-adapters.sh`. Never by its name: a command file the person wrote
   themselves has no marker and is never touched. List every file under
   `.claude/commands/`, `.cursor/commands/` and `.gemini/commands/` that
   carries the marker.
2. Find retired skill folders. Look in both `.agents/skills/` and
   `.claude/skills/`, since an installation for Claude Code alone keeps its
   skills only in the second. A folder there counts only
   when it carries one of the kit's former names, `build`, `start` or `plan`,
   and the lockfile does not list it. Any other folder there is the person's
   own and is left alone.
3. Show the list and say what removing it does: each command appears once,
   and the renamed command goes. Remove on approval, and remove the empty
   folders too. Remove a tracked leftover with `git rm -r <path>`, and the
   removal is part of the visit's saved change. An untracked file goes with a
   plain `rm`. An untracked leftover folder goes to the person as the command
   to run, with its path, since a recursive delete is refused. So does a
   tracked folder that untracked files keep in place after `git rm -r`.
4. Record a changelog line saying what was removed and why.

## Offering a move onto a recipe

A project founded before the kit had recipes has no `Recipe:` line in its
AGENTS.md. A project whose person chose their own stack has `Recipe: none`.
Either one can be built much like a recipe on the menu without anybody
noticing. On a recipe, /ship checks the launch steps. Off one, it can only
name what it could not check. So the monthly visit makes the offer, and the
person decides. The move is never required.

Skip this on Explore privately. Nothing there goes live, so the launch checks
would gain nothing.

1. Read the `Recipe:` line in the stack section of the project's AGENTS.md.
   Where it names a file that is in the installed ship skill's `recipes/`
   folder, the project is on a recipe, and this step ends. `Recipe: none`, no
   line at all, or a file that is no longer there counts as off a recipe.
2. Look at the project's open pieces. Where an open piece already proposes a
   move onto a recipe, the person said yes on an earlier visit and the move is
   waiting to be built, so this step ends. Filing it again would make a copy.
3. Read the menu at this moment: each file directly in the installed ship
   skill's `recipes/` folder, not the `parts/` folder inside it. Read each
   file's `Build stack:` and `Deploy target:` lines. Take every product name
   from those files, and never write one into this skill.
4. Compare each recipe's `Build stack:` line with what the project is built
   with. Read that from the project's code and dependency files, not from
   memory. A recipe is close when the build stack matches in substance: the
   same framework and the same data service. It stays close when the project
   deploys somewhere else, or lacks something the recipe adds, such as its
   Dockerfile or its health route. A different framework or a different data
   service is not close. A copy of the data service that the project runs on
   its own server is not the same data service, because it lacks the managed
   backups that the recipe's checks rely on. Keep every close recipe for
   now, and do not pick one yet. Steps 5 and 6 drop the ones they do not
   allow, so a close recipe that is new never hides behind an older one that
   matches a little better.
5. Where the person chose their own stack at founding, offer the move only
   when the stack has become close since, or when the close recipe is new
   since founding. Read the stack at founding from the commit that first
   saved masterplan.md. Read the `founding-menu` line in
   `.ai-build-kit-maintenance`: it lists the recipe files on the menu
   founding showed. A close recipe that line does not list joined the menu
   later, so the person never had the chance to choose it. Offer it once,
   even if the stack has not changed. A project with no `founding-menu` line
   was founded before founding kept one, so every close recipe counts as new
   for it, once. Where a close recipe was on that menu and the stack was
   already that close then, their choice stands. After a no, step 6 decides
   whether the offer comes back.
6. Read the `recipe-move-declined` line in `.ai-build-kit-maintenance`, if
   there is one. It holds the date of an earlier no, the recipe file that was
   offered, and the recipe files on the menu that day. Offer again only when
   the menu or the project's stack has changed since that no: a recipe file on
   the menu now that the line does not list, or a saved change to the
   project's dependency files after that date. Where only the menu changed,
   allow only the close recipes the line does not list, and the ones it lists
   stay declined. Otherwise the earlier no stands.
7. When no recipe is close, or an earlier no stands, say nothing. Compare
   only the close recipes that steps 5 and 6 still allow. Where several are
   left, take the one whose `Build stack:` line matches the most, or the
   first by file name.
8. Offer the move once, in one reply. Name the recipe from its file. Say what
   it gains in plain words: the launch checks /ship would then run, one for
   each section the recipe checks, such as preview, rollback, backup and
   restore. Say what it would change, from the differences step 4 found: for
   example, add the recipe's shared Dockerfile and health route, move the tool
   to the recipe's deploy target, or, where the recipe expects tables made by
   migrations and the project's tables are made only in the data service's
   dashboard, move those tables into migrations. Never quote a price. Say that
   the project keeps working as it is if they say no. For example: "This
   project is built much like the [recipe name] recipe. On that recipe, /ship
   would check the preview, rollback, backup and restore for you. The move
   would add a Dockerfile and a health route, and move the tool to [deploy
   target]. Shall I file it as a piece? Nothing changes if you say no."
9. Change nothing without approval. On a yes, open an issue in the shape
   the `setup-ai-build-kit` skill's `references/pieces.md` describes, titled
   as a move onto the recipe. It holds the recipe's file name and the changes
   the offer named. Leave it for /shape and /implement like any other piece.
   Do not make the move during the visit. The `Recipe:` line changes only
   when that piece lands.
10. On a no, leave the project alone and do not ask again this visit. Record
    the no in `.ai-build-kit-maintenance` as one line, replacing any earlier
    one: `recipe-move-declined|<YYYY-MM-DD>|<recipe file>|<menu files, comma
    separated>`. Step 6 reads it on later visits.

## Quarterly, or before a handover

Everything above, plus:

1. Run sync.
2. A hot-spot review, not a general architecture pass. Look first at: areas
   changed repeatedly, areas behind repeated bugs, areas whose evidence is
   slow or unreliable, areas where one change spreads across many files,
   integrations that fail often, and records that no longer explain reality.
   For spread, read the quarter's landed changes from Git and count the files
   each change touched in each area. Use that count to name the widest-spreading
   areas rather than judging them from memory. This is a comparison, not a
   health score.
   On Build and run it and Build with care, load `references/waste-read.md`
   and gather copied code, unused code and unused dependencies before
   proposing anything. Load `references/structure-read.md` too, and compare
   the structure with the last full visit. Then load
   `references/document-bloat.md` and look for documents that repeat each
   other or are no longer needed.
   Propose no more than three simplifications; for each, state the repeated
   problem, the plain-language change, what becomes easier to verify or
   recover, the cost, and whether a person outside the team has to look.
   Apply on approval.
   Do not run a broad architecture programme merely because the quarter
   changed.
3. Review project skills for instructions that no longer pay their way and
   offer to remove them. AGENTS.md was already checked in the monthly pass;
   do not repeat its trim offer or cut anything without the person's yes.
4. Run ship's evidence run, scoped by the build path and its sensitive areas.
5. The ownership and graduation check: can the team still explain the main
   flows? Can it verify important changes without reading code? Can it
   identify where data, secrets, service owners, and bills live? Can it
   recover, or use the manual fallback? Has reliability, complexity, or
   reliance grown? Are the named sensitive areas and their cautions still
   accurate? Name a new area when the answers require it. Where an area was
   named or given a boundary since the last full visit, offer the boundary
   rule in the `setup-ai-build-kit` skill's `references/boundary-rules.md`,
   and change or remove an existing rule with its area, on a yes. An area comes off
   only when a genuine redesign has removed what put it there; an acceptance
   drops its caution and leaves the area named. Where the person asks for a
   handover, or a caution names a person the team has to find, prepare
   the `ship` skill's `templates/handover.md` for the area or the whole
   build.
6. Put today's date on the `last-full-pass` line as well as the
   `last-light-pass` line in `.ai-build-kit-maintenance`.

## When a tool's time is over

Own the ending. Export the data somewhere the team can reach it, in a
documented, usable format, and tell the people who relied on the tool.
Revoke access, rotate or delete credentials, confirm any retention
obligations, remove scheduled jobs and webhooks, switch off the services so
nothing keeps billing quietly, confirm billing has actually stopped, and
archive the repo. An abandoned tool with real data in it is a liability; a
retired one is finished.

## Done when

The findings are reported, the approved changes are applied and recorded, today's visit is written into `.ai-build-kit-maintenance`, and the calendar says when the next visit is due.
