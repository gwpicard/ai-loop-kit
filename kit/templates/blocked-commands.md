# Blocked commands

Never run these. They can destroy work or cross a boundary the people on this
project cannot see coming or recover from alone.

When the coding agent refuses a command, or this list forbids it, stop. Then
tell the person in one line which command was refused and what it was for,
and let them decide. Never reach the same result another way: another
spelling, another tool such as `find -delete` or a script, or the same work
split into steps. When the person asks you to run a refused command, say it
is refused and give them the command to run themselves.

This instruction holds in every harness. Where the harness supports a command
deny list, mirror these entries there as mechanical enforcement:

- `git reset --hard`
- `git push --force` and `git push -f`
- a direct push to `main`, in the spellings listed under "A direct push to
  `main`" below
- `git clean -f` and `git clean -fd`
- a recursive delete in any spelling, such as `rm -rf`, `rm -r` or
  `rm --recursive`, in the spellings listed under "Deleting files and Git
  history" below
- `git reflog expire`
- `git gc` with `--prune`
- `git commit --no-verify`, `git config core.hooksPath` and `git config
  alias.*`, which switch off the git hooks or hide a refused command behind a
  short name, in the spellings listed under "Keeping the git hooks on" below
- a direct change to a `state:`, `shaping:` or `review:` label, in the
  spellings listed under "Changing a piece's state by hand" below
- a write to the gate's record in `.agents/pieces/`, as "A piece's record"
  below describes

The following restrictions do not reduce to one reliable command pattern and
still apply:

- `git checkout .` and `git restore .` are allowed only inside the fix loop's
  announced reset step;
- never remove a worktree by force, with `git worktree remove --force` or
  `-f`, and never delete a worktree's folder by hand; one holding unsaved work
  is kept and named;
- never drop or empty a database table;
- never migrate a production database without a backup and a rehearsal on a
  copy;
- never delete or bulk-update production data without explicit approval for
  that exact action;
- never print, commit, or otherwise expose a secret;
- never disable authentication or access control to make a check pass;
- never bypass a red project check to ship or merge;
- never push a change directly to `main`; every change to `main` goes through a
  pull request, so shared work reaches it by merge rather than by a direct push.
  The one exception is the project's first upload: after the person's yes,
  and only when the remote lists no branch, `main` is created through the
  GitHub API at the commit the piece's branch was cut from. It is never
  written by a `git push`;
- never force or automate a merge over a required review;
- never activate flagged work before its recorded condition is met or the
  person has accepted the risk on the record;
- never withdraw, soften, or redefine a risk notice you have already given, and
  never offer your own reading of your own work as the independent review a
  build path names;
- never post in the person's name to anyone else, or change the title or scope
  of an issue or a pull request another account opened, without a yes that
  covers the words. The guard hook, `kit/hooks/guard.py`, asks before
  `gh issue comment`, `gh pr comment` and `gh pr review`;
- never install, replace, download to run, or remove software outside the
  project folder without a yes that names what it is, where it goes and how to
  undo it. A removal that needs a recursive delete is the person's to run, as
  the refused-command rule at the top says.
- never update the kit with a bare `npx skills update`, which can drop a
  renamed skill without a word and leave the kit half updated; the kit is
  updated only through `/maintain`, which uses the route the project installed
  it by. Where the person asks for an update, run `/maintain`.

Save a checkpoint before sweeping work. If one of these actions appears
necessary, stop, explain why, and let the person decide with the reason in
front of them.

## A direct push to `main`

The Claude Code settings the kit installs refuse a push that names `main` as
the branch, with any options before or after it, in any order. A deny rule
there reads the words of the command as written. So it catches the spellings
below, and it misses a push where `main` is not written out, or where git is
not called as `git push`.

These spellings are refused:

- `git push origin main`
- `git push -u origin main`
- `git push -q origin main`
- `git push --quiet --set-upstream origin main`
- `git push --force origin main`
- `git push -f origin main`
- `git push origin main --force`
- `git push origin HEAD:main`
- `git push origin +HEAD:main`
- `git push origin HEAD:refs/heads/main`
- `git push origin +main`
- `git push origin refs/heads/main`
- `git push origin --delete main`

A branch whose name only starts with `main`, such as `main-fix`, still
pushes. The rules may also refuse a push where `main` is the value of an
option, such as `git push -o main origin feature`. That push is rare, and the
person can run it themselves.

These spellings are not refused, and the rule above still forbids them:

- `git push` or `git push origin` while `main` is checked out, since git
  chooses the branch and the command never names it
- `git push origin HEAD` while `main` is checked out
- `git push origin "main"` or `git push origin 'main'`, with quotes
- `git push origin $BRANCH`, with the branch in a variable
- `git push origin heads/main`, a shortened name
- `git push --all origin` and `git push --mirror origin`, which push every
  branch
- `git -C . push origin main` and `git -c push.default=current push origin
  main`, with an option between `git` and `push`
- `/usr/bin/git push origin main`, with git called by its full path
- `sh -c 'git push origin main'`, with the push inside another shell

## Deleting files and Git history

A recursive delete removes a folder with everything in it, and nothing brings
back what Git never saved. `git reflog expire` and `git gc --prune` throw away
the history Git would use to recover lost work, even work that was committed.
The Claude Code settings the kit installs refuse all three when the command
starts with the words below. Like the push rules, they read the command as
written.

These spellings are refused:

- `rm -r build`, `rm -R build` and `rm --recursive build`
- `rm -rf build`, `rm -fr build`, `rm -Rf build` and `rm -fR build`
- `rm -r -f build`
- `git reflog expire --expire=now --all`
- `git gc --prune=now` and `git gc --aggressive --prune=now`

Deleting a throwaway folder, such as a build folder, is refused too, since a
rule cannot tell it from the person's work. The person can run it themselves,
or the project's own clean command can. Deleting one file, such as
`rm -f notes.txt`, and a plain `git gc` or `git reflog` still run.

These spellings are not refused, and the rule above still forbids them:

- `rm -f -r build`, with the recursive option second
- `rm -rv build` and `rm -Rfv build`, with another option joined to the
  recursive one
- `find build -delete`
- `/bin/rm -r build`, with `rm` called by its full path
- `sh -c 'rm -r build'`, with the delete inside another shell
- `git -C . gc --prune=now`, with an option between `git` and `gc`

## Keeping the git hooks on

The git hooks check each commit and each push. Three commands switch them off,
or hide a refused command behind a short name. The Claude Code settings the kit
installs refuse all three, and the guard hook, `kit/hooks/guard.py`, refuses
them too. Where the deny rule reads the words as written, the hook reads the
command.

These spellings are refused by the hook and by the deny rules:

- `git commit --no-verify -m x`, `git commit -m x --no-verify` and
  `git commit -n -m x`
- `git config core.hooksPath /tmp/none` and
  `git config --global core.hooksPath /tmp/none`
- `git config alias.st status` and `git config --global alias.st status`

The hook refuses these spellings, and the deny rules miss them:

- `git -c core.hooksPath=/tmp/none commit -m x`, with the option before the
  subcommand
- `git -C . commit --no-verify -m x`, with an option between `git` and `commit`
- `git commit -nm x`, with the short option joined to another

Reading a value still runs, such as `git config --get core.hooksPath`. Setting
`user.name` and every other key still runs.

## Changing a piece's state by hand

A piece's state lives in its `state:`, `shaping:` and `review:` labels, and
only the gate script, `kit/scripts/gate.py`, changes them. It checks that
the move is allowed before it writes. The Claude Code settings the kit
installs run a hook, `kit/hooks/guard.py`, before each command and
each GitHub tool call, and carry deny rules that read the command as written.
Both refuse a direct change to one of those labels, and the hook names the
gate command to run instead. Run that command. If the gate refuses the move
too, tell the person what it said and stop that move. Never reach the same
change another way: another spelling, a script, the GitHub API, or a GitHub
tool in place of `gh`.

These spellings are refused by the hook and by the deny rules:

- `gh issue edit 12 --add-label state:ready`,
  `gh issue edit 12 --add-label shaping:spec` and
  `gh issue edit 12 --add-label review:person`
- `gh issue edit 12 --remove-label state:building`,
  `gh issue edit 12 --remove-label shaping:raw` and
  `gh issue edit 12 --remove-label review:auto`
- `gh issue edit 12 --add-label state:ready,type:bug`, with the state label
  first in the list
- `gh issue create --title "Login" --label state:shaping`,
  `gh issue create --title "Login" --label shaping:raw` and
  `gh issue create --title "Login" --label review:person`
- `gh label create state:done`, `gh label create shaping:later` and
  `gh label create review:team`
- `gh label edit state:ready --color 000000`,
  `gh label edit shaping:spec --color 000000` and
  `gh label edit review:auto --color 000000`
- `gh label delete state:ready`, `gh label delete shaping:raw` and
  `gh label delete review:person`
- `gh api repos/o/r/issues/12/labels -f "labels[]=state:ready"` and
  `gh api -X DELETE repos/o/r/issues/12/labels/state:ready`

The hook refuses these spellings, and the deny rules miss them:

- `gh issue edit 12 --add-label "state:ready"` and
  `gh issue edit 12 --add-label 'state:ready'`, with quotes
- `gh issue edit 12 --add-label type:bug,state:ready` and
  `gh issue edit 12 --add-label "type:bug, state:ready"`, with the state label
  later in the list
- `gh issue edit 12 --add-label=state:ready`, with an equals sign
- `gh issue edit --add-label state:ready 12`, with the number last
- `gh issue create --title "Login" -l state:shaping`, with the short option
- `gh label delete "state:ready"`, with quotes
- `/opt/homebrew/bin/gh issue edit 12 --add-label state:ready`, with `gh`
  called by its full path
- `sh -c 'gh issue edit 12 --add-label state:ready'`, inside another shell
- a GitHub tool call, such as `mcp__github__add_issue_labels`, whose labels
  include a `state:`, `shaping:` or `review:` label

Neither refuses these spellings, and the rule above still forbids them:

- `gh issue edit 12 --add-label "$LABEL"`, with the label in a variable
- `sh scripts/relabel.sh 12`, a call from another script that changes the
  label
- `gh api graphql`, with the label named by its id inside a query
- a change made in a browser on GitHub, which nothing here can see. The next
  `gate.py report` names it and leaves it as it is

The deny rule on `gh api` refuses every call on an issue's labels path, reads
included, such as `gh api repos/o/r/issues/12/labels`. No skill reads labels
that way: `gh issue view 12 --json labels` reads them. Adding or removing any
other label still runs, such as `gh issue edit 12 --add-label type:bug`, and
so do `gh issue list --label state:ready`, `gh label list` and every
`gate.py` command except `gate.py sync`, which only the person runs.

The settings run the hook only when it is present and runnable, so a missing
copy never blocks every command. `/maintain` puts a missing hook back. Another
coding agent runs neither the hook nor the deny rules. There this written rule
and `gate.py report`, which names a label changed by hand, are what remain.

## A piece's record

The gate script keeps what it records about each piece in
`.agents/pieces/<number>/` in the project's main folder: a line for each check
it ran, and the reasons a piece goes to the person's review. Only the gate
writes there. The Claude Code settings the kit installs refuse the file tools
on that folder, writing and editing alike. The rule is read from the root of
the computer, so a session started in a run's worktree is refused too.

When one is refused, tell the person in one line which file it was and what
the write was for, and stop. Never write the record another way: a script, a
copy put in its place, or the same lines written in steps. A script that opens
the file itself is not refused, and the rule still forbids it. The gate chains
each line it writes to the one before, so it refuses a record holding a line
it did not write. Before a piece goes to review it runs every check again
itself, so a line in the record never stands in for a check. Reading the
record still runs, and so does every `gate.py` command.

## A merge that goes live

Where the masterplan's `Goes live:` line says `on every merge`, each merge puts
the tool live. There the kit adds two rules to the ask list in the project's
Claude Code settings, so Claude Code shows its confirmation box before the
merge runs, whatever the session was told. Like a deny rule, an ask rule
matches only the command as it is typed.

These merges are asked about:

- `gh pr merge`, which merges the pull request of the branch checked out
- `gh pr merge 12`
- `gh pr merge 12 --squash`
- `gh pr merge --merge 12`
- `gh pr merge 12 --auto`
- `gh api -X PUT repos/o/r/pulls/12/merge`

The second rule also asks before `gh api repos/o/r/pulls/12/merge` with no
method, which only reads whether the pull request has merged. Answer the box,
or read the same thing with `gh pr view 12`.

These commands are never asked about:

- `gh pr view 12`
- `gh pr list`
- `gh pr checks 12`
- `gh api repos/o/r/pulls/12`

These merges are not asked about, and a merge still needs a yes that names it:

- a merge made on GitHub's website
- a merge through another program, or with `gh` called another way, such as
  `/opt/homebrew/bin/gh pr merge 12`, `sh -c 'gh pr merge 12'`, or
  `gh api graphql` with a merge in its query
- any merge in a session in `bypassPermissions` mode, which skips every
  confirmation box
