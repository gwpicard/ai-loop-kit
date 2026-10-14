#!/usr/bin/env python3
"""List the names a project's documents mention that no longer exist.

Reads README.md, AGENTS.md, docs/overview.md and every document AGENTS.md points
at. Where AGENTS.md points at `docs/README.md`, the list of the project's area
docs, each document that list names is read too, since the list is how AGENTS.md
points at them. Nothing else under `docs/` is read. For each line it looks
for five kinds of name and checks that each still exists: a file or folder, a
link to another file, an `npm run`, `pnpm run`, `yarn run` or `make` command,
and an environment variable. It prints one line per name that does not exist,
as `document:line<TAB>kind<TAB>name`, and prints nothing when every name it
found still exists.

A file name is one that ends in a file ending, and a folder name one that ends
in a slash. So `/shape`, `owner/name` and `example.com/page` are not taken for
files. A name written from some other folder is found wherever the project
keeps a path that ends with it.

The `changes/` folder is part of the changelog. It is empty between folds and
a finished piece's file leaves it at the next one, so a name inside it is
never reported.

A document may describe less than the code does, and that is never flagged.
Only a name that points at nothing is. It never says a document is right,
because a described flow can change shape without any name going missing.

Documents changed longest ago, counted in commits since, come first. That order
says where to look first and is never printed.

It reads the project and writes nothing. Run it from the project root:

    python3 <kit folder>/scripts/document-claims.py

`records-check.py` runs it, and reports each line as a fault of the rule `names`.
"""

from __future__ import annotations

import functools
import json
import os
import re
import subprocess
import sys

KIT_OWNED = {"WORKFLOW.md", "AGENTS.md", "masterplan.md", "CHANGELOG.md", "plan.local.md"}
CHANGES = "changes"
CONCEPTS = os.path.join("docs", "README.md")
OVERVIEW = os.path.join("docs", "overview.md")
EXTENSIONS = (
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py", ".rb", ".go", ".rs",
    ".java", ".kt", ".cs", ".php", ".md", ".json", ".yml", ".yaml", ".toml",
    ".sh", ".sql", ".html", ".css", ".txt", ".csv", ".ini", ".cfg",
)
CODE_SPAN = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
COMMAND = re.compile(r"\b(npm|pnpm|yarn) run ([\w:.-]+)|\bmake ([\w.-]+)")
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")

Claim = tuple[int, str, str]


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    return result.stdout if result.returncode == 0 else ""


def ignored(path: str) -> bool:
    return (
        subprocess.run(
            ["git", "check-ignore", "-q", path], capture_output=True, check=False
        ).returncode
        == 0
    )


def named_documents(source: str, found: list[str]) -> None:
    """Add each Markdown document `source` names that exists, in order."""
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    named = LINK.findall(text) + CODE_SPAN.findall(text)
    for name in named:
        name = name.split("#")[0].strip()
        if not name.endswith(".md") or name.startswith(("http:", "https:")):
            continue
        # A name in the concept list may be written from the docs/ folder.
        candidates = [os.path.normpath(name)]
        if source != "AGENTS.md":
            candidates.append(os.path.normpath(os.path.join(os.path.dirname(source), name)))
        for candidate in candidates:
            if os.path.basename(candidate) in KIT_OWNED or candidate.startswith(
                (".agents", CHANGES + "/")
            ):
                break
            if os.path.isfile(candidate):
                if candidate not in found:
                    found.append(candidate)
                break


def documents() -> list[str]:
    found: list[str] = []
    if os.path.isfile("README.md"):
        found.append("README.md")
    for own in ("AGENTS.md", OVERVIEW):
        if os.path.isfile(own):
            found.append(own)
    if os.path.isfile("AGENTS.md"):
        named_documents("AGENTS.md", found)
    if CONCEPTS in found:
        named_documents(CONCEPTS, found)
    return found


def package_scripts() -> set[str] | None:
    try:
        with open("package.json", encoding="utf-8") as handle:
            return set(json.load(handle).get("scripts", {}))
    except (OSError, ValueError):
        return None


def make_targets() -> set[str] | None:
    try:
        with open("Makefile", encoding="utf-8") as handle:
            return {m.group(1) for m in re.finditer(r"^([\w.-]+)\s*:", handle.read(), re.M)}
    except OSError:
        return None


def looks_like_path(name: str) -> bool:
    if " " in name or name.startswith(("http:", "https:", "-", "$")):
        return False
    if any(mark in name for mark in "<>*?{}|=@~"):
        return False
    if name.startswith("node_modules") or "://" in name:
        return False
    # A file name ends in a file ending, and a folder name ends in a slash.
    # Anything else with a slash in it is a command such as /shape, a
    # repository such as owner/name, or a web address, and is not checked.
    if "/" in name and "." in name.split("/")[0].lstrip("."):
        return False
    return name.endswith(EXTENSIONS) or name.endswith("/")


@functools.cache
def saved_paths() -> set[str]:
    """Every file git tracks, and every folder holding one."""
    paths: set[str] = set()
    for path in git("ls-files").split("\n"):
        parts = [part for part in path.split("/") if part]
        paths.update("/".join(parts[:end]) for end in range(1, len(parts) + 1))
    return paths


def path_exists(name: str, document: str) -> bool:
    bare = name.split("#")[0].split(":")[0].rstrip("/")
    if not bare:
        return True
    if os.path.normpath(bare).split(os.sep)[0] == CHANGES:
        return True
    beside = os.path.join(os.path.dirname(document), bare)
    for candidate in (os.path.normpath(bare), os.path.normpath(beside)):
        if os.path.exists(candidate) or ignored(candidate):
            return True
    # Written from some other folder, a name is still present if a saved path
    # ends with it: `deploy.sh` or `lib/check.sh` wherever the project keeps it.
    tail = "/".join(p for p in bare.split("/") if p not in ("", ".", ".."))
    return any(path == tail or path.endswith("/" + tail) for path in saved_paths())


def env_named_in_code(name: str, documents_read: list[str]) -> bool:
    hits = git("grep", "-l", "-w", "-F", name).split()
    return any(hit not in documents_read and not hit.endswith(".md") for hit in hits)


def claims(
    document: str,
    documents_read: list[str],
    scripts: set[str] | None,
    targets: set[str] | None,
) -> list[Claim]:
    missing: list[Claim] = []
    fenced = False
    with open(document, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    for number, line in enumerate(lines, start=1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        for target in LINK.findall(line):
            if target.startswith(("http:", "https:", "mailto:", "#")):
                continue
            if not path_exists(target, document):
                missing.append((number, "link", target))
        for match in COMMAND.finditer(line):
            if match.group(3):
                if targets is not None and match.group(3) not in targets:
                    missing.append((number, "command", "make " + match.group(3)))
            elif scripts is not None and match.group(2) not in scripts:
                missing.append((number, "command", f"{match.group(1)} run {match.group(2)}"))
        spans = CODE_SPAN.findall(line) if not fenced else []
        for span in spans:
            span = span.strip()
            if ENV_NAME.match(span):
                if not env_named_in_code(span, documents_read):
                    missing.append((number, "environment variable", span))
            elif looks_like_path(span) and not path_exists(span, document):
                missing.append((number, "file", span))
    return missing


def commits_since(document: str) -> int:
    last = git("log", "-1", "--format=%H", "--", document).strip()
    if not last:
        return 0
    count = git("rev-list", "--count", f"{last}..HEAD").strip()
    return int(count) if count.isdigit() else 0


def main() -> int:
    read = documents()
    scripts, targets = package_scripts(), make_targets()
    found: list[tuple[int, str, int, str, str]] = []
    for document in read:
        for number, kind, name in claims(document, read, scripts, targets):
            found.append((commits_since(document), document, number, kind, name))
    found.sort(key=lambda f: (-f[0], f[1], f[2]))
    for _, document, number, kind, name in found:
        print(f"{document}:{number}\t{kind}\t{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
