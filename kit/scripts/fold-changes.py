#!/usr/bin/env python3
"""Fold the files in changes/ into CHANGELOG.md.

Each piece writes its changelog entry into its own file in `changes/`, so two
pieces built at the same time never change the same lines. This gathers those
files into CHANGELOG.md: each becomes one line, `- <its text>`, under a
`## YYYY-MM-DD` heading for the day the file reached `main`, newest first. A
heading that is exactly that date takes the new lines at its top. Any other
`## ` heading that begins with a date, such as `## 2026-09-29 Launch`, only
sets the order: a new date goes above the first heading older than it, and
above the first `## ` heading of any kind when none is older, never at the end
of the file. The folded files are then removed with `git rm`, which stages
their removal.

It reads only files saved in the current commit, so it folds only what is on
the branch being saved. Run it on a branch cut from the up-to-date `main`, and
a file still waiting on another branch never enters the history. A file nobody
has committed, or one with changes nobody has committed, is left where it is.

With `--main <ref>`, it dates each file by `<ref>` instead. The merge step
runs it that way on a pull request's branch that has just taken in `main`,
where the newest commit adding a file from `main` is the branch's own merge of
`main`, dated today. A file `<ref>` already holds is dated by the day it reached
`<ref>`, following the first parents of `<ref>`. A file `<ref>` does not hold is
the pull request's own, and is dated today, the day of this merge. A file whose
line CHANGELOG.md already holds is removed without being written again: a
stacked branch still carries its base's file after the base merged by squash,
since the squash added and folded it in one commit.

It never stages CHANGELOG.md or commits: the save route does that. It prints
one line for each file folded, and nothing when there is nothing to fold. Run
it from the project root:

    python3 <sync skill folder>/scripts/fold-changes.py [--main <ref>]
"""

import datetime
import os
import re
import subprocess
import sys
import time

FOLDER = "changes"
CHANGELOG = "CHANGELOG.md"
EXACT = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")
STARTS = re.compile(r"^## (\d{4}-\d{2}-\d{2})\b")


def git(*args):
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git " + " ".join(args) + " failed")
    return result.stdout


def saved_files():
    """The Markdown files in changes/ saved in the current commit."""
    listed = git("ls-tree", "--name-only", "HEAD", FOLDER + "/").split("\n")
    return [name for name in listed if name.endswith(".md")]


def held(ref, name):
    """Whether the commit `ref` names holds the file."""
    result = subprocess.run(["git", "cat-file", "-e", ref + ":" + name],
                            capture_output=True, text=True)
    return result.returncode == 0


def arrival_on(ref, name):
    """The day and moment the file reached `ref`, or today when it has not."""
    if held(ref, name):
        lines = git("log", "--first-parent", "--diff-filter=A", "--format=%ct %cs",
                    ref, "--", name).split("\n")
        lines = [line for line in lines if line.strip()]
        if lines:
            moment, day = lines[0].split()
            return int(moment), day
    return int(time.time()), datetime.date.today().isoformat()


def arrival(name):
    """The day and moment the file reached this branch's line of history.

    Following only first parents, the newest commit that added the file is the
    one that brought it: the merge of its pull request, or the checkpoint commit
    on the checkpoint route. The newest, because a name used before, folded and
    removed, then written again by a reopened piece, was added more than once.
    """
    lines = git("log", "--first-parent", "--diff-filter=A", "--format=%ct %cs",
                "HEAD", "--", name).split("\n")
    lines = [line for line in lines if line.strip()]
    moment, day = lines[0].split()
    return int(moment), day


def issue_number(name):
    match = re.match(r"(\d+)", os.path.basename(name))
    return int(match.group(1)) if match else 0


def entry(name):
    text = git("show", "HEAD:" + name)
    words = " ".join(line.strip() for line in text.split("\n") if line.strip())
    if words.startswith("- "):
        words = words[2:]
    return "- " + words


def fold(changelog, entries):
    """Insert each (day, line) into the changelog text, newest day first."""
    lines = changelog.split("\n")
    by_day = {}
    for day, line in entries:
        by_day.setdefault(day, []).append(line)

    for day in sorted(by_day, reverse=True):
        new = by_day[day]
        headings = []
        in_comment = False
        for index, line in enumerate(lines):
            if "<!--" in line:
                in_comment = True
            if not in_comment and line.startswith("## "):
                exact, starts = EXACT.match(line), STARTS.match(line)
                headings.append((index, starts.group(1) if starts else None, bool(exact)))
            if "-->" in line:
                in_comment = False

        same = [index for index, heading, exact in headings if exact and heading == day]
        if same:
            at = same[0] + 1
            while at < len(lines) and not lines[at].strip():
                at += 1
            lines[at:at] = new
            continue

        older = [index for index, heading, _ in headings if heading and heading < day]
        block = ["## " + day, ""] + new + [""]
        if older:
            lines[older[0]:older[0]] = block
        elif headings:
            lines[headings[0][0]:headings[0][0]] = block
        else:
            while lines and not lines[-1].strip():
                lines.pop()
            lines += [""] + block
    text = "\n".join(lines)
    return text if text.endswith("\n") else text + "\n"


def main():
    args = sys.argv[1:]
    main_ref = None
    if args[:1] == ["--main"] and len(args) == 2:
        main_ref = args[1]
    elif args:
        print("usage: fold-changes.py [--main <ref>]", file=sys.stderr)
        return 2
    if main_ref is not None and subprocess.run(
            ["git", "rev-parse", "-q", "--verify", main_ref + "^{commit}"],
            capture_output=True).returncode != 0:
        print("fold-changes: " + main_ref + " names no commit", file=sys.stderr)
        return 1

    try:
        names = saved_files()
    except RuntimeError as problem:
        print("fold-changes: " + str(problem), file=sys.stderr)
        return 1

    ready = []
    for name in names:
        if git("status", "--porcelain", "--", name).strip():
            print(f"fold-changes: {name} has changes nobody has committed; left as it is",
                  file=sys.stderr)
            continue
        moment, day = arrival_on(main_ref, name) if main_ref else arrival(name)
        ready.append((moment, issue_number(name), name, day))
    if not ready:
        return 0

    if os.path.isfile(CHANGELOG):
        with open(CHANGELOG, encoding="utf-8") as handle:
            changelog = handle.read()
    else:
        changelog = "# Changelog\n"

    if main_ref:
        written = set(changelog.split("\n"))
        fresh = []
        for item in ready:
            if entry(item[2]) in written:
                git("rm", "-q", "--", item[2])
                print(f"removed {item[2]}, already in {CHANGELOG}")
            else:
                fresh.append(item)
        ready = fresh
        if not ready:
            return 0

    # Newest first: the latest arrival, then the higher issue number.
    ready.sort(reverse=True)
    entries = [(day, entry(name)) for _, _, name, day in ready]

    with open(CHANGELOG, "w", encoding="utf-8") as handle:
        handle.write(fold(changelog, entries))

    for _, _, name, day in ready:
        git("rm", "-q", "--", name)
        print(f"folded {name} under {day}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
