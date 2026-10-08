#!/usr/bin/env python3
"""Copy failed rehearsal evidence without credentials or Git object payloads."""

import re
import sys
from pathlib import Path


def snapshot(source: Path, destination: Path) -> None:
    """Keep raw scratch locally; write only filtered text for public upload."""
    destination.mkdir(parents=True, exist_ok=False)
    kept = 0
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if path.is_symlink() or not path.is_file():
            continue
        # Git objects may hold old fixture secrets even after their working
        # files changed. Keep refs and conflict metadata, but no object store.
        if (
            "objects" in relative.parts
            or "data" in relative.parts
            or path.name in {"gh.log", "config", "index", "local.json", "credentials"}
            or path.suffix in {".pem", ".key", ".pack", ".idx"}
        ):
            continue
        try:
            text = path.read_text()
        except (UnicodeError, OSError):
            continue
        if "PRIVATE KEY-----" in text or "\x00" in text:
            continue
        text = re.sub(
            r"(?im)^.*(?:authorization|bearer|access_token|installation_token).*$",
            "[authentication line omitted]",
            text,
        )
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        kept += 1
    (destination / "EVIDENCE.txt").write_text(
        f"Retained {kept} filtered text files. Raw scratch remains on the runner.\n"
        "Omitted private keys, App data, authentication logs, Git configuration,\n"
        "object stores, indexes, binary files and symbolic links.\n"
    )


if __name__ == "__main__":
    snapshot(Path(sys.argv[1]), Path(sys.argv[2]))
