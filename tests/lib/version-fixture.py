#!/usr/bin/env python3
"""Acquire a local annotated release for offline distribution fixtures."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit/scripts"))
from loop import versions  # noqa: E402


def release(kit: Path, project: Path, *, publish: bool = True) -> versions.Prepared:
    """Verify the installed copy against a separately committed local release."""
    with tempfile.TemporaryDirectory(prefix="version-fixture-") as temporary:
        repo = Path(temporary)
        shutil.copytree(ROOT / "kit", repo / "kit",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "version.json"))
        # REL0.1 owns the real manifest version; only these disposable copies use 0.1.0.
        for folder in (repo / "kit", kit):
            manifest = folder / ".claude-plugin/plugin.json"
            body = json.loads(manifest.read_text())
            body["version"] = "0.1.0"
            manifest.write_text(json.dumps(body) + "\n")
        for arguments in [
            ["init", "-q"], ["add", "kit"],
            ["-c", "user.name=Local checks", "-c", "user.email=checks@example.invalid",
             "-c", "commit.gpgsign=false", "commit", "-qm", "Offline release fixture"],
        ]:
            subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True)
        tag = "v" + versions.manifest_version(repo / "kit")
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=Local checks", "-c",
             "user.email=checks@example.invalid", "-c", "tag.gpgsign=false",
             "tag", "-a", tag, "-m", "Offline annotated release"],
            check=True, capture_output=True,
        )
        original = versions._git

        def local_git(arguments: Any, folder: Path) -> str:
            if list(arguments) == ["remote", "add", "origin", versions.REPOSITORY]:
                arguments = ["remote", "add", "origin", str(repo)]
            return original(arguments, folder)

        with patch.object(versions, "_git", side_effect=local_git):
            prepared = versions.prepare(kit, project, tag)
        if publish:
            versions.publish(prepared)
        return prepared


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kit", type=Path)
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    if not os.environ.get("AI_LOOP_KIT_DATA"):
        parser.error("fixtures must set an isolated AI_LOOP_KIT_DATA")
    prepared = release(args.kit, args.project)
    print(json.dumps({"commit": prepared.commit, "record": str(prepared.path)}))


if __name__ == "__main__":
    main()
