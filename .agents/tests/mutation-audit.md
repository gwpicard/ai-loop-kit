# Mutation audit

Reading the suite tells you what it means to catch. Only breaking something
tells you what it does catch. This records what happened when twenty-one
promises were broken one at a time, on 11 August 2026, against `bb81109`.

Reproduce it with `.agents/tests/mutate.sh`. The script clones the repository
for each mutation, applies one reversible edit, runs the checks, and records
which ones noticed. It refuses to report a mutation that left the tree
unchanged, because a mutation matching nothing looks exactly like a hole in the
suite.

## What came out of it

Twenty-one mutations. Twenty were caught. One was not.

Nothing here is dead weight. Every check file is the only thing standing between
the kit and at least one of these faults, so the answer to "can the suite be
made smaller" is no, not by deleting a file. What it can be is sharper in two
specific places.

## The hole

The session hook is supposed to stay silent inside the kit's own source, so a
maintainer is never told their own repository is overdue a check-up. Break that
guard and nothing notices.

The guard itself works. The check that claims to prove it cannot fail. Its
fixture folder in `session-start.sh` has no `masterplan.md` and no maintenance
record, so the hook says nothing because there is nothing to say, not because
the guard stopped it. Proved by hand:

| Folder that looks like the kit's source, with a masterplan | Hook |
|---|---|
| guard intact | silent |
| guard broken | speaks: "The project is 2414 days old and has had no check-up yet." |

`session-start.sh` passed either way. Giving that fixture a masterplan and a
stale maintenance record was the whole fix, and it is done. The check now also
takes the source markers back off and insists the same folder speaks, so the
silence above has to come from the guard rather than from an empty project.

Re-running `mutate.sh hook-speaks-in-source` against the fix confirms
`session-start.sh` catches it. Note that the audit clones committed history, so
a fix has to be committed before it can be measured; the first attempt at
confirming this appeared to fail for that reason alone.

## The weak spot

Three checks count skills and expect fourteen:
`release-builder.sh:120`, `release-builder.sh:126`, and
`starter-rehearsal.sh:72`. Removing a skill leaves ten and all three fail, as
they should. Replacing one skill with a copy of another leaves fourteen of the
wrong set, and all three pass.

Only `agent-plugin.sh:152-156` catches that, because it compares the sorted
names rather than counting them. The counting checks are not useless, since they
catch a skill going missing, but they are strictly weaker than a name
comparison, and a name comparison catches both faults. Replace them rather than
remove them.

## What each check is alone in catching

Excluding `validate-kit.sh`, which runs all seven of the others itself at lines
870 to 946 and is therefore an aggregate rather than an independent opinion.

| Check | The only thing catching |
|---|---|
| `agent-plugin.sh` | wrong skill set, stale adapters, a background skill claiming a person starts it, a manifest field the standard omits |
| `release-builder.sh` | the writing skill leaking, the private repository named publicly, a file dropped from the allowlist alone |
| `kit-updater.sh` | a local customisation discarded, a version advanced by a failed update |
| `release-publication.sh` | a version that is not a stable release, a used version republished with different contents |
| `session-start.sh` | the hook speaking before a visit is due |
| `validate-kit.sh` own checks | a broken local link, retired vocabulary |
| `starter-rehearsal.sh` | nothing on its own, though it catches four faults alongside others |

## Two results that look stronger than they are

Dropping `docs/SOURCES.md` from the allowlist was caught by all five checks, but
for one reason rather than five: `update-manifest.txt` still names the file, and
the builder refuses when the two disagree. Dropping a file named only in the
release allowlist is caught by `release-builder.sh` alone, and only because its
required-file list happens to name that file. A file in neither list would go
quietly.

`starter-rehearsal.sh` never caught anything by itself. It is not therefore
removable: it rehearses the shared-installer route, which nothing else does, and
the audit simply contains no mutation that only that route would reveal. That is
a gap in this audit rather than a verdict on the check.

## Corrections made while running it

Recorded because the same mistakes are easy to repeat.

Three mutations targeted wording that a recent change had rewritten, so they
edited nothing and reported three holes that did not exist. Every mutation now
asserts the text it expects is present before touching it, and the runner
refuses any mutation that leaves the tree unchanged.

One mutation created an untracked stray file and expected it to reach the
release. It did, because the runner stages changes so that new files reach the
builder's tracked-file list. Creating an untracked file does not break the
promise; the promise is that untracked files do not ship. The mutation now stops
the builder consulting Git at all, and every check catches it.

The first run was also derailed part way through by editing `mutate.sh` while it
was executing. A shell reads a script as it goes.
