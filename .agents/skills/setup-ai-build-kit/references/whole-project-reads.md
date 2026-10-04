# Whole-project reads

Some checks look at the whole project rather than one change: the type check and
linter in the project check, the quarterly reads that feed `/maintain`, and the
documentation read in `/sync`. Every one of them follows the rules below. Each
read points here rather than stating them again.

One idea sits under all of them. A tool finds, and the agent reports what the
tool found. No read asks the agent for its own opinion of the code. Where no
tool can answer a question, the read says the question was not checked.

## The rules

1. Each read lists the tools it can use, best first, and the last entry is
   always reading the code directly. Use the first one that is present. Name
   the one used in the internal evidence, and say when it was the fallback.
   `section-builder/references/reach-check.md` is the model.
2. Prefer a maintained tool. Before installing or recommending a tool, check
   that its repository is still maintained and not archived. An archived tool
   keeps working for a while and then stops, and a written order cannot recover
   from that by itself. If the tool a read would use has been archived, say so
   in one line and use the next one in the order.
3. Save nothing. Derive every result again from the project as it is now.
   Never write a result, index or graph to a file for a later read to trust. A
   stale index answers confidently and wrongly. Where a read compares against
   an earlier state, derive that state again from the project's saved history
   at the recorded date, rather than keeping a copy of it.
4. Each finding names a file and a line that exist. Before the person sees it,
   confirm it a second time: run the tool again, or open the file at that line
   and check that the finding is there. Drop any finding that does not survive
   the second look.
5. Put the findings in order of what they cost the person, and show no more
   than the read's cap. The quarterly visit's cap of three proposals holds for
   every read that feeds it. Summarise the rest in one line that says how many
   there are and where they are listed, rather than leaving them out without
   saying so.
6. Nothing got worse is a complete answer. When a read finds nothing new, say
   nothing, or give one line if the person asked for the read. Silence is the
   ordinary result.
7. No score, grade or percentage reaches the person. Where a tool prints one,
   leave it out. Where a tool has a confidence setting, run it at the setting
   that reports only what it is certain of.
8. Report in words the person already has: the green tick, a proposal, a named
   part of the tool. No read introduces a term the person has to be taught.

## What a read may never claim

A read says what it checked and what it found. It never says that the rest of
the project is fine, because no tool checked the rest. Some questions are
beyond every read here: whether a retry survives a real failure, whether two
pieces of code written differently do the same job, and whether a described
flow has quietly changed shape. Say so when the person asks about one of them.

## Where it applies

Always, for every read that looks across the whole project. A read about one
change, such as the reach check or the structure comparison in
`section-builder`, already follows its own reference and is not changed by this
one.
