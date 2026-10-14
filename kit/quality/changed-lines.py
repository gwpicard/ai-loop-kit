#!/usr/bin/env python3
"""Print changed file line ranges from a git diff with zero context."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def changed_lines(base: str, cwd: Path = Path.cwd()) -> dict[str, list[list[int]]]:
    diff = subprocess.run(["git", "diff", "--no-ext-diff", "--no-color", "-U0",
                           f"{base}...HEAD"], cwd=cwd, capture_output=True,
                          text=True, check=True).stdout
    files: dict[str, list[list[int]]] = {}
    current = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            files.setdefault(current, [])
        elif current and line.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                start = int(match.group(1))
                count = int(match.group(2) or "1")
                if count:
                    files[current].append([start, start + count - 1])
    return {path: ranges for path, ranges in files.items() if ranges}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", nargs="?", default="origin/main")
    parser.add_argument("--files", action="store_true",
                        help="print changed paths as a comma-separated list")
    args = parser.parse_args()
    changes = changed_lines(args.base)
    if args.files:
        print(",".join(changes))
    else:
        print(json.dumps(changes, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
