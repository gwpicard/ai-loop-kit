# Migrating to a clean repository

A runbook for replacing the public repository with one whose history carries no
AI attribution, while keeping the issues, the releases, the numbering and the
web address.

Written 10 September 2026, after the history rewrite of the same day. Every step
below was rehearsed against real GitHub repositories before this was written.
Nothing here is theory except the two steps marked as unrehearsable, and those
were rehearsed on stand-ins that behaved the same way.

Read the whole document before starting. The middle of a migration is a bad
place to meet a surprise.

Not to be confused with `docs/MIGRATION-READINESS.md`, which is a record of a
different and finished move: retiring the private maintainer repository in
August 2026. It has nothing to do with this.

## Why this exists

A coding agent appended two lines to every commit message and pull request
description it wrote: a co-author trailer naming the model, and a
`Claude-Session:` trailer carrying a personal link to the session the work came
out of. Nobody noticed until the repository was already public.

The session link is the part that matters. It is a personal address on the agent
vendor's site, it opens for anyone who reads it, and a commit message has no use
for it.

## What has already been done

Do not repeat these. They are finished.

- The 33 commits on `main` were rewritten and force-pushed. Nineteen of them
  carried attribution. The file contents did not change at all: the tree of the
  rewritten `main` is identical to the tree it replaced.
- The four tags that moved with them, v0.11.0 through v0.13.0, were force-pushed.
  The twelve older tags never carried attribution and were untouched.
- Thirteen pull request descriptions were cleaned through the REST API.
- Issues, comments and all seventeen release notes were checked and were already
  clean.
- A hook and a validator rule now stop the lines coming back. See the
  Attribution section of the root `AGENTS.md`.

## What is left, and why a migration is the only way to reach it

GitHub creates a permanent reference for every pull request ever opened, and
those references still point at the original branch commits. Because later
branches were cut from the old `main`, that chain drags most of the old history
along with it.

**Thirty-five commits still carry attribution** and are still served. They are
reachable from each merged pull request's Commits tab, and by their address.

Those references cannot be rewritten. Git refuses a push to them and there is no
route through the API. They are deliberately immutable, so that a merged pull
request's record cannot be changed underneath a reviewer.

That single fact is why there is no smaller fix. The two ways out are asking
GitHub Support to purge them, which depends on somebody else's tooling and
judgement, or replacing the repository, which is this document.

## What the migration achieves, and what it costs

It keeps the web address, so every existing link, badge and install command
keeps working. It keeps the issues with their numbers, the labels, the releases,
the release downloads and the settings. The old repository survives, renamed and
private, so nothing is destroyed.

It costs the following, and there is no way to avoid any of them.

- **Three stars.** The new repository starts at zero. The archive keeps them but
  nobody can see a private repository's stars.
- **The repository's age.** The created date resets from 7 August 2026 to
  whenever you run this.
- **Every issue and comment timestamp.** They all show the day you run it. The
  real date is written into the text of each one instead.
- **Release dates.** The API gives no way to backdate a release. Tag dates
  survive, because those come from the commits.
- **Pull requests as pull requests.** Seventeen of them become closed issues
  holding their title, description and comments. The prose survives and stays
  searchable. The diffs and the review threads do not.
- **Traffic and insight history.**

## What happens to people who installed the kit

This is the part that matters most, so it was checked rather than assumed.

Claude Code records a marketplace by its path, not by any internal identity of
the repository. The local record reads `"source": "github"` with
`"repo": "gwpicard/ai-build-kit"`. The migration keeps that path, so the record
stays correct and nobody has to edit anything on their machine.

The marketplace is kept as an ordinary git clone whose origin is the same web
address, and an install records the commit it came from. The new repository is
pushed from the same local clone the rewrite happened in, so its commits are the
same commits with the same addresses. Nothing about the git side changes.

The install and update commands in `README.md` keep working, unchanged:

```
claude plugin marketplace add gwpicard/ai-build-kit
claude plugin install ai-build-kit@ai-build-kit --scope local
```

and `claude plugin marketplace update ai-build-kit` still finds its source.

Release downloads are addressed by tag and file name rather than by an internal
number, so those links survive as well.

**One group is already broken, and the migration is not what broke them.** The
history rewrite gave new addresses to nineteen commits, roughly everything from
v0.11.0 onwards. An installation sitting on one of those cannot move forward,
because the commit it remembers is no longer on the branch. An installation from
v0.10.0 or earlier is unaffected: those commits were never rewritten and are
still exactly where they were.

Anyone stuck that way fixes it in two commands:

```
claude plugin marketplace remove ai-build-kit
claude plugin marketplace add gwpicard/ai-build-kit
```

Say that in the release notes next time a version goes out, whether or not the
migration ever happens.

## Before you start

Set aside about an hour. Steps 0 to 5 can be stopped at any point and cost
nothing, so the part that needs your attention is steps 7 and 8, which take a
few minutes and should be run back to back. The web address does not resolve
between them, and leaving it that way is worse than not starting.

You need:

- The `gh` command, signed in as the repository owner. Check with
  `gh auth status`. It needs the `repo` and `workflow` permissions, which the
  current sign-in has.
- A local clone whose `main` matches the public one, with nothing uncommitted.
- Everything you want to keep merged into `main`. Step 1 does this and explains
  it. It matters more than it looks: nothing on those branches is cleanup, since
  the cleanup was the rewrite and that is finished. What they hold is only the
  rules that stop the trailers coming back. A migration that leaves them behind
  produces a clean history with nothing defending it, and the problem starts
  again from the first commit.
- The saved social preview image. There is a copy at
  `~/ai-build-kit-backups/social-preview.png`, 1280 by 640.
- The full backup of the pre-rewrite history, at
  `~/ai-build-kit-backups/`, in case anything needs reading later.

## The facts this was written against

Check these still hold before you start. If any number has moved, that is fine,
but the export in step 1 is what the migration actually uses, so trust it over
this list.

| Thing | Count on 10 September 2026 |
| --- | --- |
| Numbered items, issues and pull requests together | 37, with no gaps |
| Pull requests, all merged | 17 |
| Issues, of which 14 open | 20 |
| Comments | 41 |
| Labels | 25 |
| Releases, one of them a draft | 17 |
| Release download files | 4 |
| Sub-issue links | issue 9 is the parent of 6, 7 and 8 |
| Stars, forks | 3, 0 |
| Secrets, environments, webhooks, deploy keys, milestones | none |

Two of those items were written by somebody else. **Issue 32 and its one comment
were written by KasperHonore.** The port marks them as theirs rather than
letting them appear under your name. Tell them the migration happened, because
their contribution moves to a new record.

## The tools

All six live in `.agents/migration/` and are maintainer-only. None ships,
because none appears in `release-manifest.txt`.

| File | What it does |
| --- | --- |
| `PROMPT.md` | What to paste into a fresh session to have it run the safe half of this plan and stop. |
| `orient.sh` | Reads the world back and says which of this plan's assumptions still hold. Changes nothing. Run it first. |
| `export.sh` | Reads issues, comments, labels, releases, sub-issue links and settings out of the old repository. Read-only. Stops if it finds a gap in the numbering or any attribution text. |
| `port.py` | Recreates all of that in the new repository, in number order. Stops dead if any item lands on the wrong number. |
| `port-settings.sh` | Release download files, merge settings, description, topics, branch ruleset. |
| `verify-port.sh` | Reads the new repository back and compares it against the old one, number by number. |

## The steps

Steps 1 to 5 change nothing on GitHub and nothing that anyone can see. If you
stop during them, you have lost only your time. Step 6 onwards is the part that
moves, and it takes a few minutes.

Names used below: the live repository is `gwpicard/ai-build-kit`, the archive
will be `gwpicard/ai-build-kit-archive`, and the replacement is built as
`gwpicard/ai-build-kit-next` before it takes the real name.

### 0. Check the ground

```
bash .agents/migration/orient.sh
```

This reads GitHub and the local clone and reports whether the plan still
describes them. It writes nothing anywhere. Read the output before going on.
A line marked ATTENTION is not always a problem, but it is something this plan
did not expect, so re-read the plan where it touches that thing.

### 1. Put everything on `main`, locally

The new repository is built from `main`, so anything not on `main` will not
exist in it. Nothing here is pushed to the old repository, which is being
retired anyway.

```
git checkout main
git merge --ff-only migration-plan
```

**Expected:** a fast-forward, with no merge commit. `migration-plan` sits in a
straight line on top of `main`, and it carries the attribution branch beneath
it, so this one merge brings both.

**If it refuses to fast-forward**, something has changed since this was written.
Stop and look rather than forcing it.

Then check nothing else is outstanding:

```
git branch --no-merged main
```

Anything still listed is either wanted, in which case merge it too, or it is a
leftover. On 10 September the two leftovers were
`clearer-issue-review-printout` and `maintainer-skill-review-issues`, both old
copies of work already on `main`. They are harmless either way, because the
rewrite cleaned them along with everything else, and step 3 pushes only `main`
and the tags.

### 2. Build the clean local repository

```
git clone --no-local /mnt/c/Users/GUP/Documents/ai-build-kit ~/ai-build-kit-clean
cd ~/ai-build-kit-clean
git remote remove origin
```

A clone takes branches and tags and nothing else. The rewrite's own backup
references are left behind, and so is every commit that only they held. That is
why this is a clone rather than a copy of the folder: a copy would bring the
whole object store, including the old commits.

The `--no-local` flag matters. Without it, git treats a clone from a folder on
the same machine as a copy and carries the whole object store across, old
commits included. They would sit unreferenced, so a push would not send them,
but the proof below could not tell you that. With the flag, git sends only what
the branches and tags reach, and the proof means what it says.

Prove it, rather than trusting it:

```
git log --all --format=%B | grep -ci "claude-session:"
git tag -l | wc -l
git log --oneline -1
```

**Expected:** `0` for the first, `16` for the second, and the newest commit for
the third. If the first prints anything but zero, stop. The whole point of the
exercise has failed and pushing would carry the problem into the new
repository.

### 3. Create the new repository and push

```
gh repo create gwpicard/ai-build-kit-next --private \
  --description "$(gh api repos/gwpicard/ai-build-kit -q .description)"
git remote add origin https://github.com/gwpicard/ai-build-kit-next.git
git push origin main
git push origin --tags
```

Private for now, so a half-built repository is never public. It goes public in
step 8.

**Expected:** `main` and 16 tags. Check with
`git ls-remote origin | grep -c refs/tags/`.

### 4. Port everything else

Run from the original working clone, which is where the scripts live:

```
cd /mnt/c/Users/GUP/Documents/ai-build-kit
bash .agents/migration/export.sh gwpicard/ai-build-kit ~/ai-build-kit-backups/export
python3 .agents/migration/port.py \
  --export ~/ai-build-kit-backups/export --target gwpicard/ai-build-kit-next
bash .agents/migration/port-settings.sh \
  gwpicard/ai-build-kit gwpicard/ai-build-kit-next
```

Export first, always, and never reuse an old one. An issue opened since the last
export is an issue that does not survive, and one opened in the middle of the
range shifts every number after it. The export script refuses to run if it finds
a gap.

The port takes about five minutes. It pauses a second between writes on purpose,
to stay under GitHub's limit on how fast an account may create things.

**Expected:** every number from 1 to 37 in order, then the sub-issue links, the
releases, the settings and the four downloads.

**The ruleset step will fail**, saying the feature needs GitHub Pro or a public
repository. That is correct and expected. The repository is still private. The
ruleset is created in step 9.

**If the port stops with `STOP: created number N where M was expected`:** delete
`gwpicard/ai-build-kit-next` and start again from step 3. Do not try to repair
it. Numbers cannot be reassigned, so everything after the mistake is wrong.
Nothing on the live repository has been touched, so this costs time and nothing
else.

### 5. Verify, while everything is still reversible

```
bash .agents/migration/verify-port.sh gwpicard/ai-build-kit gwpicard/ai-build-kit-next
```

**Expected:** nine `ok` lines and `everything matched`.

If any line says FAIL, stop. Delete the new repository, work out why, and start
again from step 3. Up to this point the live repository is untouched and you can
walk away by deleting one private repository.

### 6. Stop and read

Everything from here changes what the world sees, and the web address stops
resolving until step 8 finishes. Do not begin unless you can finish now.

Steps 7 and 8 should be run back to back.

### 7. Retire the old repository

```
gh api -X PATCH repos/gwpicard/ai-build-kit -f name=ai-build-kit-archive
gh api -X PATCH repos/gwpicard/ai-build-kit-archive -F private=true
gh api -X PATCH repos/gwpicard/ai-build-kit-archive -F archived=true
```

The second command is the one that ends the exposure. All 35 attributed commits
and every pull request reference stop being publicly reachable the moment it
lands.

**Archiving is not the same as making it private, and archiving alone fixes
nothing.** GitHub's archive setting makes a repository read-only. An archived
public repository is still fully public and every one of those commits stays
readable. Private is the setting that matters, which is why it comes first. The
archive flag is only a label saying nobody works here any more.

**If a command refuses** with `a conflicting repository operation is still in
progress`, wait about ten seconds and run it again. That happens while an
earlier change settles. It is not a failure.

### 8. Put the new repository in its place

```
gh api -X PATCH repos/gwpicard/ai-build-kit-next -f name=ai-build-kit
gh api -X PATCH repos/gwpicard/ai-build-kit -F private=false
```

Renaming into a name currently held by a redirect works, and the redirect gives
way. This was rehearsed. **If it refuses** with `name already exists on this
account`, the previous rename has not settled. Wait ten seconds and try again.

```
curl -s -o /dev/null -w "%{http_code}\n" https://github.com/gwpicard/ai-build-kit
```

**Expected:** 200, within about ten seconds. If it prints 404, wait and try
again before worrying. GitHub serves repository pages from a cache that lags a
change by up to about ten seconds, in both directions. That lag is the moment
somebody panics and reverses a step that was working.

The web address is live again. Nothing after this is urgent.

### 9. Ruleset, and the last checks

```
cd /mnt/c/Users/GUP/Documents/ai-build-kit
bash .agents/migration/port-settings.sh gwpicard/ai-build-kit gwpicard/ai-build-kit
bash .agents/migration/verify-port.sh gwpicard/ai-build-kit-archive gwpicard/ai-build-kit
```

The first reapplies the settings harmlessly and creates the ruleset that could
not be created while the repository was private. **Expected:**
`ruleset created, enforcement active`.

Then point your working clone at the repository that now holds the name:

```
git remote set-url origin https://github.com/gwpicard/ai-build-kit.git
git fetch origin && git status
```

Finally, check by hand that the old commits are gone. Open one of the addresses
the orientation script listed, while signed out or in a private browser window.
It should not be found.

## What only you can do

The migration cannot finish without these, and none of them can be done from a
command line.

1. **Upload the social preview image.** Settings, then General, then Social
   preview. The file is at `~/ai-build-kit-backups/social-preview.png`. Until
   you do this, every link shared to the repository shows GitHub's generic card
   instead of yours.
2. **Tell KasperHonore.** Their issue and comment now live on a new record.
3. **Star your own repository**, if you want the count not to read zero.
4. **Check the plugin route really installs.** The web address is unchanged so
   it should, and the section above says why, but type it once and watch it
   work rather than trusting the reasoning:

   ```
   claude plugin marketplace remove ai-build-kit
   claude plugin marketplace add gwpicard/ai-build-kit
   claude plugin marketplace list
   ```

   The last command should show the marketplace pointing at
   `gwpicard/ai-build-kit`. This is the one check worth doing before you tell
   anybody the migration is finished.
5. **Tell anyone with a clone to clone again.** Their copy has the old history
   and will not merge cleanly.
6. **Decide what happens to the archive.** It can sit there privately forever at
   no cost. Do not make it public again.

## If something goes wrong

The migration is reversible up to a point, and that point is worth knowing.

| Stage | How to get back |
| --- | --- |
| Steps 0 to 5 | Delete `ai-build-kit-next`. The live repository was never touched, and the local work is all on branches. |
| After step 7, before step 8 | Make the archive public again, unarchive it, and rename it back to `ai-build-kit`. You are exactly where you started. |
| After step 8 | Rename the new repository aside, then rename the archive back and make it public. The archive still holds everything. |
| After you delete the archive | Nothing. So do not delete the archive. |

The full pre-rewrite history is in a bundle at `~/ai-build-kit-backups/`. That
is the last line of defence and it does not expire.

## Risks that remain

Said plainly rather than buried, because a runbook that claims certainty is a
runbook that gets trusted at the wrong moment.

- **The export goes stale.** This is the likeliest problem and step 1 exists to
  prevent it. An issue opened between the export and the port is lost, and one
  opened in the middle of the range shifts every number after it. Export
  immediately before porting, and do not answer an issue while the migration is
  running.
- **A rate limit mid-run.** GitHub limits how fast an account creates things.
  The port pauses a second between writes, which was enough across two full
  rehearsals, but a limit hit mid-run leaves a half-built repository. The fix is
  the same as any other failure: delete it and start again.
- **GitHub changing its behaviour.** Every step here was proved against GitHub
  as it behaved on 10 September 2026. The longer this document sits unused, the
  more likely something has moved. Re-read the failure messages rather than
  assuming a step is broken.
- **Two steps could not be rehearsed against the real repository**: making the
  live repository private, and the real name takeover. Both were rehearsed on
  disposable repositories that behaved as described, including the cache lag and
  the transient rename refusal.
- **Copies outside GitHub.** Software Heritage, which mirrors public
  repositories, has not archived this one, and that was the main risk. GH
  Archive records the public event stream, including commit messages, into
  permanently public datasets. If any push happened while the repository was
  public, those messages are likely in it and nobody can remove them. It is an
  obscure corner queried by researchers rather than something a visitor meets,
  but it is beyond reach and it is honest to say so.

## Deciding not to do it

Not migrating is a reasonable choice, and it is worth writing down what you are
accepting if you take it.

The main branch, every clone, every tag and every release are already clean. A
person browsing the repository normally sees nothing. What stays is the commit
list inside each merged pull request, and any saved address of an old commit.
Someone would have to open a merged pull request's Commits tab, which is an
ordinary thing to do but not the first thing anybody does.

Weigh that against three stars, the repository's age, and seventeen pull requests
becoming issues. There is no obviously correct answer.
