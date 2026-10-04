# Prompt for the session that runs the migration

Paste everything below the line into a new session, in this repository.

It asks for the safe half of the migration only. The session stops before
anything anybody can see changes, hands back a list of the things only a person
can do, and waits.

---

## The job

Run steps 0 to 5 of `docs/MIGRATION.md` in this repository, then stop and hand
back to me. Do not run step 6 or anything after it. Read the whole plan before
you touch anything.

Short version of why this exists, so you are not working blind. This repository
was public while a coding agent was appending a personal session link to every
commit message and pull request description it wrote. The commit history was
rewritten on 10 September 2026 and the pull request descriptions were cleaned,
so `main` and every clone are already clean. What could not be reached is the
set of commits GitHub keeps alive behind its own pull request references, which
no rewrite can touch because those references are read-only. Thirty-five commits
still carry attribution and are still served from each merged pull request's
Commits tab. Replacing the repository is the only remaining way to remove them.
`docs/MIGRATION.md` explains all of this properly.

## Where things are

- This repository: `/mnt/c/Users/GUP/Documents/ai-build-kit`
- The plan: `docs/MIGRATION.md`
- The scripts: `.agents/migration/`
- Copies of both, outside the repository, in case a branch was never merged:
  `~/ai-build-kit-backups/`
- The plan and its scripts currently live on the `migration-plan` branch, not on
  `main`. If you cannot find `docs/MIGRATION.md`, check what branch you are on
  before concluding anything.

## Start here, before anything else

```
bash .agents/migration/orient.sh
```

It reads GitHub and this clone and reports whether the plan still describes
them. It writes nothing anywhere.

Show me its full output and tell me in plain words what it means. Every line
marked ATTENTION needs an explanation before you continue. Some are expected:
the branch protection being switched off is known, and unmerged branches are
what step 1 deals with. A count that has moved is not expected, and the export
in step 4 is what the migration actually uses, so trust that over the numbers
written in the plan.

**Do not start step 1 until you have shown me the orientation output and I have
replied.** If something has drifted far enough that the plan no longer fits, say
so and stop. A stale plan followed confidently is the one failure this cannot
recover from.

## Then work through steps 1 to 5

Follow `docs/MIGRATION.md` exactly. In outline:

1. Merge everything onto `main` locally. It is a fast-forward. Nothing is pushed
   to the old repository, which is being retired anyway.
2. Build a clean local repository with `git clone` into `~/ai-build-kit-clean`,
   and prove it is clean before going on. Clone with `--no-local`, never copy the folder: a clone
   takes branches and tags only, so the rewrite's backup references and the old
   commits they held are left behind. A folder copy brings the whole object
   store, old commits included.
3. Create `gwpicard/ai-build-kit-next` as a **private** repository and push
   `main` and the tags to it.
4. Export the issues and everything else from the old repository, then port it
   all into the new one. Export immediately before porting, never from an older
   copy.
5. Verify, and show me the result.

Report what happened after each step in plain language, not by pasting logs at
me. If a step does something you did not expect, stop and say so rather than
carrying on.

## Things that will look like failures and are not

- **The ruleset step fails during step 4**, saying the feature needs GitHub Pro
  or a public repository. Correct and expected. The repository is still private.
  It is created later, after it goes public.
- **A rename or a settings change is refused** with `a conflicting repository
  operation is still in progress`. Wait about ten seconds and try again.
- **GitHub's pages lag by about ten seconds** after any visibility change. If a
  web address gives the wrong answer, wait and check again before reacting.

## Things that are real failures

- **The port stops with `STOP: created number N where M was expected`.** Delete
  `gwpicard/ai-build-kit-next` and start again from step 3. Do not try to repair
  it. Issue numbers cannot be reassigned, so everything after the mistake is
  wrong. Nothing on the live repository has been touched, so this costs time and
  nothing else.
- **The clean clone in step 2 still contains attribution.** Stop entirely. The
  whole exercise has failed and pushing would carry the problem across.
- **The verification in step 5 reports any FAIL.** Delete the new repository,
  find out why, start again from step 3.

## Rules

- **Never force-push anything.** It is in this repository's blocked list and in
  the Claude settings deny list, and nothing in steps 0 to 5 needs it.
- **Never delete `gwpicard/ai-build-kit`,** or the archive it later becomes. It
  is the only copy of seventeen pull request conversations.
- Deleting `gwpicard/ai-build-kit-next` is always safe. It is disposable until
  step 8.
- Ask me before anything irreversible or anything the public can see. Steps 0 to
  5 contain none of that, which is why you can run them without stopping.
- Follow the writing rules in `AGENTS.md` for anything you write down: British
  spelling, plain words, no em dashes.

## Where to stop

Stop after step 5 and give me:

1. **What is done**, in plain words, and what the verification said.
2. **What only I can do.** At minimum: upload the social preview image, which is
   web interface only, from `~/ai-build-kit-backups/social-preview.png`. Read
   the "What only you can do" section of the plan and give me the current list,
   not a remembered one.
3. **What happens next and what it costs.** Steps 7 and 8 are the few minutes
   where the web address does not resolve. Tell me plainly that you need my word
   before starting them, and roughly how long they take.
4. **Anything you are unsure about.** Say it now rather than at the point of no
   return.

Then wait. I will do my part and tell you to carry on, and you will run steps 7,
8 and 9 with me watching.
