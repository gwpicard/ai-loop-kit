"""Apply a setup Quality proposal to a temporary main worktree."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


def apply(agents: Path, quality_command: str,
          prepare_command: Optional[str] = None,
          test_command: Optional[str] = None) -> None:
    """Apply proposed loop commands to a temporary main worktree."""
    text = agents.read_text(errors="replace") if agents.is_file() else ""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines)
                  if line.strip().lower() == "## the loop"), None)
    if start is None:
        lines.extend(([""] if lines else []) + ["## The loop"])
        start = len(lines) - 1
        end = start + 1
    else:
        end = next((i for i in range(start + 1, len(lines))
                    if lines[i].startswith("## ")), len(lines))

    section = lines[start + 1:end]
    if quality_command:
        section.append(f"Quality: {quality_command}")
    updates = []
    if prepare_command is not None:
        updates.append(("Prepare command", prepare_command))
    if test_command is not None:
        updates.append(("Test command", test_command))

    for key, value in updates:
        pattern = re.compile(r"^\s*[-*]?\s*" + re.escape(key) + r"\s*:", re.IGNORECASE)
        matches = [i for i, line in enumerate(section) if pattern.match(line)]
        if value:
            replacement = f"{key}: {value}"
            if matches:
                section[matches[0]] = replacement
                section = [line for i, line in enumerate(section) if i not in matches[1:]]
            else:
                section.append(replacement)
        elif matches:
            section = [line for i, line in enumerate(section) if i not in matches]

    lines[start + 1:end] = section
    agents.write_text("\n".join(lines) + "\n")
