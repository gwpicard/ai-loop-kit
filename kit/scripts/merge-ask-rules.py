#!/usr/bin/env python3
"""Add or remove the rules that make Claude Code ask before a merge.

Where the masterplan's `Goes live:` line says `on every merge`, each merge puts
the tool live. The rules in `kit/templates/merge-ask-rules.json` make Claude
Code show its confirmation box before any such merge. Every step that turns
the setting on or off runs this script, so the file changes the same way
whoever writes the line.

Usage:

    merge-ask-rules.py add <settings file>
    merge-ask-rules.py remove <settings file>

`add` puts each rule the file lacks at the end of `permissions.ask`, and
creates that list when there is none. `remove` takes out exactly the
template's rules, and the `ask` list too when that leaves it empty. Neither
touches any other key or entry.

Exit 0: done. It prints one line for each rule added or taken out, and
nothing when nothing changed.
Exit 1: the file is not valid JSON, or not in the shape Claude Code reads. It
is left untouched.
Exit 2: there is no such file, so the project does not use Claude Code.
Nothing is written.
Exit 64: the command was not given as above. Nothing is read or written.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "templates", "merge-ask-rules.json")


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in ("add", "remove"):
        sys.stderr.write("usage: merge-ask-rules.py add|remove <settings file>\n")
        return 64
    action, path = argv[1], argv[2]

    with open(TEMPLATE) as f:
        rules: list[str] = json.load(f)["ask"]

    if not os.path.isfile(path):
        sys.stderr.write(f"{path}: no such file, so nothing was written\n")
        return 2

    try:
        with open(path) as f:
            settings: Any = json.load(f)
    except (ValueError, UnicodeDecodeError) as error:
        sys.stderr.write(f"{path}: not valid JSON ({error}), so it was left untouched\n")
        return 1

    permissions: Any = settings.get("permissions", {}) if isinstance(settings, dict) else None
    ask: Any = permissions.get("ask", []) if isinstance(permissions, dict) else None
    if not isinstance(permissions, dict) or not isinstance(ask, list):
        sys.stderr.write(
            f"{path}: not in the shape Claude Code reads, so it was left untouched\n"
        )
        return 1

    changed: list[str] = []
    if action == "add":
        for rule in rules:
            if rule not in ask:
                ask.append(rule)
                changed.append(f"added to permissions.ask: {rule}")
        if changed:
            permissions["ask"] = ask
            settings["permissions"] = permissions
    else:
        kept = [rule for rule in ask if rule not in rules]
        changed = [f"removed from permissions.ask: {rule}" for rule in ask if rule in rules]
        if changed:
            if kept:
                permissions["ask"] = kept
            else:
                del permissions["ask"]
                changed.append("removed the permissions.ask list, which is now empty")

    if not changed:
        return 0

    folder = os.path.dirname(os.path.abspath(path))
    handle, temporary = tempfile.mkstemp(dir=folder, prefix=".merge-ask-rules.")
    with os.fdopen(handle, "w") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(temporary) as f:
        json.load(f)
    os.chmod(temporary, os.stat(path).st_mode & 0o777)
    os.replace(temporary, path)
    print("\n".join(changed))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
