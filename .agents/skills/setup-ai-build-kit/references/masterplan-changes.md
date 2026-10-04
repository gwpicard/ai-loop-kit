# Keeping the masterplan current

These rules apply on every build path. Each piece carries its change to the
masterplan as [pieces.md](pieces.md) describes. The masterplan keeps its existing
sections and stays a description of the present.

## Apply a piece's change

At save time, read the piece's `## Masterplan change` and apply it to the named
section, checking it against the behaviour that was actually built. A value of
"nothing" leaves the prose alone. If the result differs from the piece, correct
the piece before applying it. A safely blocked capability stays described as
waiting; do not write that it is live.

When recovering work, read the changes on pieces whose work landed, including
closed pieces. Compare each with the current page and apply only what is still
missing. A later piece may have replaced or removed the same behaviour, so
follow landing order and the current tool. Repeating /sync must not add the same
line twice or restore something deliberately removed. An open or parked piece
is not proof its work landed; check the saved work. If an older piece has no
field, recover its change from that work rather than treating absence as
"nothing".

## Record what was checked

Keep one `Trued against: <full commit hash>` line beside the masterplan's title.
The hash names a saved code state that was checked against the page. It is for
the agent to read; never ask the person to understand or maintain it. A new
masterplan starts with `Trued against: not yet checked` until that comparison
has happened.

Before moving the mark, reconcile all changes since the old mark as well as the
piece in hand. Where the mark is absent or unusable, compare the current page
against the code before setting a starting point. Never move it past work that
has not been checked, or past uncommitted work that /sync must leave alone.

Section-builder applies the change before saving, saves the checked code, then
writes that saved commit into the mark and saves the mark in a records-only
commit on the same route. Both commits belong to the same piece and pull
request. Sync uses the current saved commit it has just reconciled and saves
the updated page through its normal route. Neither tries to write the hash of
the commit that will contain the mark, since that hash does not exist yet.

## Read the gap at the monthly visit

Read the mark on the current shared branch and count later landed code changes.
Count each change once along the first-parent history; a merge contributes its
combined change, not its branch commits as well. Leave records-only commits
out, including the commit that saved the mark. Do not include unmerged work.

Read the changed code to count which of those changes touched the subjects of
the masterplan's data, permissions or connections sections. Follow renamed
paths. Use a sensitive-area map where one exists, but do not require one on the
other build paths. Count a change once for each subject it touched, even when
several files cover that subject. A section's heading changing is not evidence
that its subject changed, and a code change alone does not prove the page is
wrong.

When any subject count is non-zero, give one line with the total and the affected
subjects, then offer /sync in that same line: "Eleven changes have landed since
the masterplan was last checked, and four touched what data it holds; /sync can
check whether the page still matches." Include permissions or connections when
they were touched too. Stay quiet when all three counts are zero.

If the mark is missing, does not resolve, is outside the current branch's
history, or the available history is incomplete, do not invent a count or reset
the mark. Say in one line that the last check cannot be established and offer
/sync. Maintenance reports the gap; it never moves the mark itself.
