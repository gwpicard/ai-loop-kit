#!/usr/bin/env python3
"""List the project's documents that repeat each other or are no longer needed.

Reads every Markdown document git tracks, apart from the changelog, the changelog
files waiting in `changes/`, a few files from older projects, and anything in a
folder whose name starts with a dot. `AGENTS.md` and the overview are read, since
a paragraph copied from one record into another is the drift to find. It prints
one line for each of two findings, and nothing when there are none:

    repeated<TAB>document:line<TAB>other-document:line
        The same paragraph, of forty words or more, in two documents.
    unreferenced<TAB>document
        No other file in the project names the document. A README is never
        listed, since it is where a reader starts.

With `--repeated` it prints only the first finding. `records-check.py` uses that,
and reports each line as a fault of the rule `repeat`. A note nothing names is
advice for the maintainer, and never a fault in the records.

A document that names things the project no longer has is the document read's
to find, in /sync, one name at a time.

It compares paragraphs word for word, after ignoring case, spacing and
punctuation, so it finds a copy and never two documents that say the same
thing in different words.

It reads the project and writes nothing. Run it from the project root:

    python3 <kit folder>/scripts/document-bloat.py [--repeated]
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterator

SKIPPED = {"GEMINI.md", "WORKFLOW.md", "masterplan.md", "CHANGELOG.md", "plan.local.md"}
# Read for repeats, and never reported as unreferenced: a reader starts there.
ENTRY_POINTS = {"readme.md", "agents.md", "claude.md"}
SHORTEST_PARAGRAPH = 40


def tracked() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=False
    )
    return [f for f in result.stdout.split("\n") if f]


def documents(files: list[str]) -> list[str]:
    found: list[str] = []
    for name in files:
        if not name.endswith(".md") or os.path.basename(name) in SKIPPED:
            continue
        if any(part.startswith(".") for part in name.split("/")[:-1]):
            continue
        if name.startswith(("node_modules/", "changes/")) or not os.path.isfile(name):
            continue
        found.append(name)
    return found


def paragraphs(document: str) -> Iterator[tuple[int, list[str]]]:
    """Yield (first line, words) for each paragraph outside a fenced block."""
    with open(document, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    fenced = False
    start: int | None = None
    words: list[str] = []
    for number, line in enumerate([*lines, ""], start=1):
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


def repeated(docs: list[str]) -> list[tuple[str, ...]]:
    seen: defaultdict[str, list[tuple[str, int]]] = defaultdict(list)
    for document in docs:
        for line, words in paragraphs(document):
            if len(words) >= SHORTEST_PARAGRAPH:
                seen[" ".join(words)].append((document, line))
    found: list[tuple[str, ...]] = []
    for places in seen.values():
        documents_here = {document for document, _ in places}
        if len(documents_here) < 2:
            continue
        (first, first_line), *others = sorted(places)
        for other, other_line in others:
            if other != first:
                found.append(("repeated", f"{first}:{first_line}", f"{other}:{other_line}"))
    return found


def unreferenced(docs: list[str], files: list[str]) -> list[tuple[str, ...]]:
    texts: dict[str, str] = {}
    for name in files:
        try:
            with open(name, encoding="utf-8") as handle:
                texts[name] = handle.read()
        except (OSError, UnicodeDecodeError):
            continue
    found: list[tuple[str, ...]] = []
    for document in docs:
        if os.path.basename(document).lower() in ENTRY_POINTS:
            continue
        base = os.path.basename(document)
        named = any(
            other != document and (document in text or base in text)
            for other, text in texts.items()
        )
        if not named:
            found.append(("unreferenced", document))
    return found


def main() -> int:
    only_repeated = "--repeated" in sys.argv[1:]
    unknown = [a for a in sys.argv[1:] if a != "--repeated"]
    if unknown:
        print("error: unknown argument " + unknown[0], file=sys.stderr)
        print("next: python3 document-bloat.py [--repeated]", file=sys.stderr)
        return 2
    files = tracked()
    docs = documents(files)
    findings = repeated(docs) + ([] if only_repeated else unreferenced(docs, files))
    for finding in findings:
        print("\t".join(finding))
    return 0


if __name__ == "__main__":
    sys.exit(main())
