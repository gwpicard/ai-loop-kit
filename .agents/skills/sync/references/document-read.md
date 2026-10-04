# Document read

The records are not the only writing a project keeps. A README, a setup guide or
a page of notes can go on naming a file, a command or a setting long after the
project stopped having it. Someone who does not read code has no way to tell.
This read finds those names.

This is a whole-project read, so the rules in
the `setup-ai-build-kit` skill's `references/whole-project-reads.md` apply.

## Where it applies

Every `/sync`, on every build path, which includes the quarterly visit, since
that runs sync first.

## Which documents

`README.md`, and every document AGENTS.md points at. Nothing else. A project
that points at a document from its standing instructions has said that document
matters. Where AGENTS.md points at `docs/README.md`, the list of the project's
concept files, each file that list names counts as pointed at too. The records sync already trues (the masterplan, the changelog with
its waiting files in `changes/`, AGENTS.md itself) are not read again here, and
nor are the kit's own files or comments in the code. A name in `changes/` is
never reported missing, since that folder empties at every fold.

A project whose real documentation lives somewhere AGENTS.md never mentions
gets no read of it. The answer is to point at it from AGENTS.md.

## What counts as wrong

A document may say less than the project does. That is never a finding. A
document is wrong only where it names something that does not exist: a file or
folder, a link to another file, a command, or an environment variable.

Whether a described flow still happens the way the document says is out of
reach. No read can check it, and this one does not try.

## Engines, best first

1. `python3 <skill folder>/scripts/document-claims.py`, where `<skill folder>` is
   this installed sync skill's folder, run from the project root. It reads the documents above, checks every file, link,
   `npm run`, `pnpm run`, `yarn run` and `make` command, and environment
   variable they name, and prints one line for each that no longer exists. It
   prints nothing when every name still exists. It lists documents changed
   longest ago first.
2. Where the script cannot run, read the documents directly and check the same
   four kinds of name by hand. Say in the internal evidence that this was the
   fallback.

Where `lychee` is already in the project, it may check links to other sites as
well. Without it, links to other sites are not checked; say so if asked.

## Checking a finding

Open the document at the line the script names and confirm the name is there
and is meant as a name in this project. A name in an example of some other
project's setup is not a finding, and nor is a name the document mentions only
to say it does not exist. Drop anything that does not survive.

Before reporting a finding, look at the open pieces. A name already on an open
piece has been raised and decided, so do not raise it again.

## Saying it

Give at most three findings, in the order the script gives them, each with its
place and what is missing:

"`README.md` line 7 names `scripts/deploy.sh`, which is no longer in the
project."

Say how many more there are in one line, and offer to list them. With any
finding, say once: "This checks the names the documents use. It cannot tell
whether a described step still happens that way."

For each finding, offer two things. Correct the name on the spot, changing that
name and nothing else in the sentence around it, or file it as a piece to come
back to. Never rewrite the person's prose. A correction is saved with sync's
other corrections, in step 8.

When the read finds nothing, say nothing about it. Every name still pointing at
something real is the ordinary result.
