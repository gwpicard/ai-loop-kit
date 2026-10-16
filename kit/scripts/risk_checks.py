"""Checks for dependency and protected path risks named by a piece."""
from __future__ import annotations

import json
import re
from pathlib import Path

from loopkit import sh


def _declared_dependencies(path: str, content: str) -> set[str]:
    """Read direct dependencies from the manifest formats named by the spec."""
    if path.endswith("package.json"):
        data = json.loads(content or "{}")
        return {name.lower().replace("_", "-")
                for section in ("dependencies", "devDependencies", "optionalDependencies",
                                "peerDependencies")
                for name in (data.get(section) or {})}
    if path.endswith("pyproject.toml"):
        names = set()
        section = ""
        project_dependencies = False
        dependency_pattern = r"['\"]([A-Za-z0-9_.-]+)(?:\[[^]]+\])?(?:[<>=!~; ].*)?['\"]"
        for line in content.splitlines():
            heading = re.match(r"^\s*\[([^]]+)\]", line)
            if heading:
                section = heading.group(1).lower()
                project_dependencies = False
                continue
            if section == "project" and re.match(r"^\s*dependencies\s*=", line):
                project_dependencies = "[" in line and "]" not in line
                names.update(re.findall(dependency_pattern, line.split("=", 1)[1]))
            elif section == "project" and project_dependencies:
                names.update(re.findall(dependency_pattern, line))
                if "]" in line:
                    project_dependencies = False
            elif section.startswith("project.optional-dependencies"):
                names.update(re.findall(dependency_pattern, line))
            elif (section == "tool.poetry.dependencies" or
                  (section.startswith("tool.poetry.group.") and
                   section.endswith(".dependencies"))):
                key = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*=", line)
                if key and key.group(1).lower() != "python":
                    names.add(key.group(1))
        return {name.lower().replace("_", "-") for name in names}
    return set()


def unnamed_dependencies(folder: Path, base: str, named: list[str]) -> list[str]:
    allowed = {re.split(r"\s*:\s*", item, maxsplit=1)[0].lower().replace("_", "-")
               for item in named}
    added = set()
    for path in ("package.json", "pyproject.toml"):
        before = sh(["git", "show", f"{base}:{path}"], folder, check=False)
        after_path = folder / path
        if not after_path.is_file():
            continue
        previous = _declared_dependencies(path, before.stdout) if before.returncode == 0 else set()
        current = _declared_dependencies(path, after_path.read_text(errors="replace"))
        added.update(current - previous)
    return sorted(added - allowed)


def path_mentioned(text: str, path: str) -> bool:
    """Match a path name on component boundaries in contract prose."""
    return re.search(rf"(?<![A-Za-z0-9_.-]){re.escape(path.rstrip('/'))}(?![A-Za-z0-9_.-])",
                     text) is not None


def path_covers(declared: str, actual: str) -> bool:
    """Whether a declared relative path covers a changed path or its child."""
    declared = declared.replace("\\", "/").strip("/")
    actual = actual.replace("\\", "/").strip("/")
    return bool(declared) and (actual == declared or actual.startswith(declared + "/"))
