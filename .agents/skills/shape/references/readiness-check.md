# The readiness check

A piece moves to `state:ready` only after a session that did not shape it has checked
it against the fixed list below. The session that shaped a piece has the same
blind spots when it judges the piece complete, so it misses the same gaps
twice. The list is fixed because an open "find the gaps" review always finds
some, even in a sound piece.

## Who runs it

A session that did not shape the piece runs the check. `/shape` starts one when
the piece is written: a subagent that starts with none of the shaping
conversation, given the piece's number and this file. A fork or a copy of the
shaping session carries its blind spots, so it does not count.

Where the coding agent cannot start a subagent, `/shape` says in one line that
the check needs a new session, and gives the exact line to paste there:
`/shape <number> check readiness`. The piece stays in `shaping:check` until
that session has written its result.

## How far it goes

One bar applies to every piece, in proportion to the piece. A colour change
answers most items with DOES NOT APPLY and one line why, and runs only the
checks its change needs. The standards always apply.

For items 8 and 9 on a project with code, use the reach check in the
`section-builder` skill's `references/reach-check.md` to find what the piece
reads and which open pieces change the same thing. The reach result is a lead:
read what it names, since the reading is what confirms it.

## The list

How to run it:
- Read the piece, the masterplan and AGENTS.md. For item 8, also read the code and data the piece names, since "confirmed" needs them.
- Answer each item PASS, GAP or DOES NOT APPLY (one line why). Ask only about states and cases the change's own screen, route or record can show.
- A GAP is BLOCKING when closing it would change what a person sees or does, what is stored, or what leaves the tool. Anything else is a NOTE. A piece is Ready when no BLOCKING gap remains. Notes go on the piece for the builder.
- Do not raise anything outside this list.

1. **Outcome.** So that states one outcome for the person.
2. **Done when, Works.** Each line is a rule, not an example; a rule given by examples names the class and its edge members. Each line maps to a check (on the line or in Evidence) that covers every surface and place the line names, and would be false on today's code. Lines that guard existing behaviour belong under item 7. For model behaviour, the check first reproduces the reported failure on today's code.
3. **Coverage.** Done when delivers all of So that, or Not in this piece names the gap and its follow-up.
4. **Not the normal case.** For each case the change can show, a line with its check, or "does not arise because":
   - empty, and people who never went through an earlier step;
   - a wait the change adds or alters: loading or slow, and a second tap or action while an answer is still arriving;
   - failure, by kind: service down; answer empty, cut off, malformed or in the wrong language; signed out; one record rejected while others pass; failing again after Try again (a retry is not a way out); success shown before the save finished;
   - leaving part-way, reload, app killed, back button: what is kept;
   - an operation stopped half-way leaves the old data intact;
   - input at its limits: very long, pasted, several lines, mixed languages;
   - arriving from outside or from an older version: a link, a cached page, a release already on the device, records written by the older version;
   - time boundaries: midnight, time zones, day counts;
   - every state, including after expanding or reading back, has a visible way out.
5. **Data.** For a new kind of stored record: where it lives; other writers (devices, people, an older version still running) and the merge rule; order on first open; size per sync and on the device, limits and what goes at the limit; backup and restore, and what newer data a restore or reset overwrites; delete, undo, time kept in backups, ids never reused; how to remove anything installed on the device. For a new writer into an existing record: its cap and what it pushes out, and when another open device learns of the change. Include records a reused part writes on the piece's behalf. Name every place that describes this data (notice, docs, detail files) that must change.
6. **Leaves the tool.** What goes where, including an address or query string reaching a host's logs; whether the recipient is new; which keys; outside text reaching a prompt; what a signed-out or removed person can still reach, and any change in what the gate covers; whether a notice the person already accepted still covers this, and who never sees a new one; whether the build path's personal-data line changes.
7. **Must still hold.** Each rule the change touches, from the masterplan, from earlier pieces' Done when, and every time limit AGENTS.md records for the route or host, with its number and where it is measured (local, preview, live). A missed number means not done. Which rule wins where rules from other modes share the same prompt or screen. The code check behind any rule that lives only in a prompt or only in a person's care. A model or service swap names the correctness rule it must still meet and the set it is measured on.
8. **Relies on.** Each existing thing used and not built here, confirmed by reading or trying it (file and line, or a sample of the data): it exists, it returns the fields needed, and its input limits. Something that will exist after a Waiting on you step counts.
9. **Reach.** The `## Reach` fields. `Boundary:` names every area the change alters. Each area under `Reaches:` names the existing tests that guard it, or says no test covers it and names the acceptance check that guards it. `If it breaks:` says who notices what and how it is undone. Open pieces whose boundary names the same area, or that change the same file, schema, prompt or record, are named with the merge order.
10. **No open choice a person would notice.** The ready-gate lint has already refused its fixed phrases: "decide during build", "consider", "or accept the limit", "acceptable", "TBD", "where sensible", "if needed", "for now", "check on the day", "may leave", "a handful", "a few" and "several". Refused here where a person would see the difference: "may", "optional", "some", "most", "short", "fast", an open "X or Y", and any other count or size without a number. Examples naming internal identifiers under the hood are fine.
11. **Complete and consistent.** Lists are complete; a list of kinds matches the code's own list. Done when agrees with Decided. No pointer to a decision or section that is not on this piece.
12. **Size.** One sitting. A container passes when every part is its own piece and its own Done when is only the joined outcome. The split is never deferred to the build, and no stub stands in for a line.
13. **A flow the person has not seen.** A new flow or screen was tried as a mock or throwaway, or Done when includes the person's try before review.
14. **Screen.** For each new control or message: where focus goes after the action, its accessible name, its target size, and whether a status is announced. Otherwise screen-check covers it at build time.
15. **Each check tests its criterion.** Match each acceptance check to the criterion it claims to test, reading the check itself. A check that tests something else is a BLOCKING gap.

What this list cannot catch, so Ready never reads as safe: domain and model quality, visual polish, platform quirks, gaps in test tools, a builder missing a correct piece, and gates ignored at merge. The independent review and screen-check stay required.

Three cases are settled here, so no checker has to decide them again:

- A Relies on line whose code or data the checker cannot read is a BLOCKING
  gap, never a PASS. "Confirmed" needs the reading, and an unread line is a
  guess about what the build will find.
- A container with parts passes item 12 when every part is its own piece and
  the container's own Done when is only the joined outcome. Each part is
  checked on its own.
- Founding takes each piece it shapes no further than `shaping:spec`, because
  writing the acceptance checks pushes a branch and founding uploads no code.
  `/shape` takes each piece on from there.

## What it writes

The check writes one section at the end of the piece, replacing any earlier
one:

```md
## Readiness
<YYYY-MM-DD>, checked by a session that did not shape it: Ready | Not ready
- BLOCKING <item>: <the gap, and what closing it would change>
- NOTE <item>: <what the builder should know>
```

That section is the stored result every later step reads. A piece with a
BLOCKING line cannot carry the verdict Ready. Notes stay on the piece for the
builder, and never hold the piece back. With no gaps and no notes, the
first line stands alone.

`/shape` reads the section back and moves the piece through the gate by what
it says. Ready moves the piece to `state:ready`. Not ready moves it to the sub-state its first BLOCKING line needs, with each blocking gap
written on the piece. The sub-state says who can close the gap:

- `shaping:clarify` for a gap a person must settle, including a Relies on
  line whose code does not exist or does not return what the piece needs;
- `shaping:research` for a fact from outside the project;
- `shaping:prototype` for a gap on item 13, a flow the person has not seen;
- `shaping:spec` for a gap the contract can close with no new answer.

The checker reads the project's code itself, so reading code is never the
reason for a label. Once a gap is closed, a session that did not shape the
piece runs the check again, which a new subagent always is.
