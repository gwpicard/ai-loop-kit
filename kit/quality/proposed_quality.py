"""Apply a setup Quality proposal to a temporary main worktree."""
from __future__ import annotations

import re
from pathlib import Path


def apply(agents: Path, command: str) -> None:
    """Replace the loop section's Quality lines with the proposed command."""
    text = agents.read_text(errors="replace") if agents.is_file() else ""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines)
                  if line.strip().lower() == "## the loop"), None)
    if start is None:
        lines.extend(([""] if lines else []) + ["## The loop", f"Quality: {command}"])
        agents.write_text("\n".join(lines) + "\n")
        return

    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("## ")), len(lines))
    section = lines[start + 1:end]
    quality = [i for i, line in enumerate(section)
               if re.match(r"^\s*[-*]?\s*Quality\s*:", line, re.IGNORECASE)]
    if quality:
        section[quality[0]] = f"Quality: {command}"
        section = [line for i, line in enumerate(section) if i not in quality[1:]]
    else:
        section.append(f"Quality: {command}")
    lines[start + 1:end] = section
    agents.write_text("\n".join(lines) + "\n")
