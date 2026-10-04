# Document bloat

A project collects writing. Some of it repeats what another document already
says, and some of it nobody reaches any more. Two copies of one instruction
drift apart, and a
person who does not read code cannot tell which is current. Every extra page is
also read by the agent as context. This read finds those documents so the
quarterly visit can offer to tidy them.

The document read in `/sync` is a different check. It looks for a single name
that no longer exists, in the documents that matter most. This read looks for
whole documents, or whole paragraphs, that are not needed.

This is a whole-project read, so the rules in
the `setup-ai-build-kit` skill's `references/whole-project-reads.md` apply.

## Where it applies

At the quarterly visit, on Build and run it and on Build with care. Not on
Explore privately.

## Which documents

Every Markdown document the project saves, not only the ones AGENTS.md points
at, because unlisted documents are where bloat collects. The records (the
masterplan, the changelog with its waiting files in `changes/`, AGENTS.md), the
kit's own files, and anything in a folder whose name starts with a dot are left
out.

## What counts as bloat

- A paragraph of forty words or more that appears word for word in two
  documents.
- A document no other file in the project names. A README is never one of
  these, because it is where a reader starts.

A document that names things the project no longer has is not counted here.
The document read in `/sync`, which the quarterly visit runs first, already
names each of those at its line.

Two documents that say the same thing in different words are out of reach. No
read here can find them.

## Engines, best first

1. Where `jscpd` is already in the project, run
   `jscpd --format markdown --min-lines 1 --reporters json --output <temporary folder> .`
   for repeated text. It also finds a copy with small changes. Point the report
   at a new temporary folder outside the project, made with `mktemp -d`, and
   leave it there for the computer to clear, since a recursive delete is
   refused.
2. `python3 <skill folder>/scripts/document-bloat.py`, where `<skill folder>` is
   this installed maintain skill's folder, run from the project root. It finds both kinds and prints one line for each. It prints
   nothing when there are none. It finds only word-for-word repeats.
3. Where neither can run, read the documents directly for the same two kinds,
   and say in the internal evidence that this was the fallback.

## Checking a finding

Open each document the finding names. Confirm the repeated paragraph is really
there twice, or that nothing names the unreferenced document. Drop anything
that does not survive.

A document can be unreferenced and still wanted, such as a note somebody opens
by hand. That is why a finding is only ever an offer.

## Saying it

Findings join the other hot-spot inputs, and the cap of three proposals holds
for all of them together. For each one, offer one tidy-up in plain words:

- "The release steps are written out in full in both `README.md` and
  `docs/release.md`. Keep them in one place and point to it from the other?"
- "Nothing in the project mentions `docs/scratch.md`. Delete it, or leave it?"

Change nothing without a yes. Keep the person's own words in the copy that
stays. With any finding, say once: "This finds copied and unused documents. It
cannot find two documents that say the same thing in different words."

When the read finds nothing, say nothing about it.
