#!/usr/bin/env python3
"""List the project's documents that repeat each other or are no longer needed.

Reads every Markdown document git tracks, apart from the kit's own files, the
project records, the changelog files waiting in `changes/`, and anything in a
folder whose name starts with a dot. It
prints one line for each of two findings, and nothing when there are none:

    repeated<TAB>document:line<TAB>other-document:line
        The same paragraph, of forty words or more, in two documents.
    unreferenced<TAB>document
        No other file in the project names the document. A README is never
        listed, since it is where a reader starts.

A document that names things the project no longer has is the document read's
to find, in /sync, one name at a time.

It compares paragraphs word for word, after ignoring case, spacing and
punctuation, so it finds a copy and never two documents that say the same
thing in different words.

It reads the project and writes nothing. Run it from the project root:

    python3 <maintain skill folder>/scripts/document-bloat.py
"""

import os
import re
import subprocess
import sys
from collections import defaultdict

SKIPPED = {
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", "WORKFLOW.md", "masterplan.md",
    "CHANGELOG.md", "plan.local.md",
}
SHORTEST_PARAGRAPH = 40


def tracked():
    result = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
    return [f for f in result.stdout.split("\n") if f]


def documents(files):
    found = []
    for name in files:
        if not name.endswith(".md") or os.path.basename(name) in SKIPPED:
            continue
        if any(part.startswith(".") for part in name.split("/")[:-1]):
            continue
        if name.startswith(("node_modules/", "changes/")) or not os.path.isfile(name):
            continue
        found.append(name)
    return found


def paragraphs(document):
    """Yield (first line, words) for each paragraph outside a fenced block."""
    with open(document, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    fenced, start, words = False, None, []
    for number, line in enumerate(lines + [""], start=1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if line.strip() and not line.lstrip().startswith("#"):
            if start is None:
                start = number
            words.extend(re.findall(r"[a-z0-9]+", line.lower()))
        elif start is not None:
            yield start, words
            start, words = None, []


def repeated(docs):
    seen = defaultdict(list)
    for document in docs:
        for line, words in paragraphs(document):
            if len(words) >= SHORTEST_PARAGRAPH:
                seen[" ".join(words)].append((document, line))
    found = []
    for places in seen.values():
        documents_here = {document for document, _ in places}
        if len(documents_here) < 2:
            continue
        (first, first_line), *others = sorted(places)
        for other, other_line in others:
            if other != first:
                found.append(("repeated", f"{first}:{first_line}", f"{other}:{other_line}"))
    return found


def unreferenced(docs, files):
    texts = {}
    for name in files:
        try:
            with open(name, encoding="utf-8") as handle:
                texts[name] = handle.read()
        except (OSError, UnicodeDecodeError):
            continue
    found = []
    for document in docs:
        if os.path.basename(document).lower() == "readme.md":
            continue
        base = os.path.basename(document)
        named = any(
            other != document and (document in text or base in text)
            for other, text in texts.items()
        )
        if not named:
            found.append(("unreferenced", document))
    return found


def main():
    files = tracked()
    docs = documents(files)
    for finding in repeated(docs) + unreferenced(docs, files):
        print("\t".join(finding))
    return 0


if __name__ == "__main__":
    sys.exit(main())
