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
        dependency_array = None
        dependency_pattern = r"['\"]([A-Za-z0-9_.-]+)(?:\[[^]]+\])?(?:[<>=!~; ].*)?['\"]"
        for line in content.splitlines():
            heading = re.match(r"^\s*\[([^]]+)\]", line)
            if heading:
                section = heading.group(1).lower()
                dependency_array = None
                continue
            source = line.split("#", 1)[0]
            if dependency_array is not None:
                dependency_array.append(source)
                if _array_complete("\n".join(dependency_array)):
                    names.update(_requirement_names("\n".join(dependency_array),
                                                     dependency_pattern))
                    dependency_array = None
                continue
            assignment = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*=\s*(.*)$", source)
            if not assignment:
                continue
            key, value = assignment.groups()
            if (section in {"tool.poetry.dependencies", "tool.poetry.dev-dependencies"} or
                    (section.startswith("tool.poetry.group.") and
                     section.endswith(".dependencies"))):
                if key.lower() != "python":
                    names.add(key.lower())
                continue
            array_table = ((section == "build-system" and key == "requires") or
                           (section == "project" and key == "dependencies") or
                           section.startswith("project.optional-dependencies") or
                           section in {"dependency-groups", "tool.pdm.dev-dependencies"})
            if not array_table:
                continue
            if not value.lstrip().startswith("["):
                continue
            dependency_array = [value]
            if _array_complete(value):
                names.update(_requirement_names(value, dependency_pattern))
                dependency_array = None
        return {name.lower().replace("_", "-") for name in names}
    return set()


def _array_complete(value: str) -> bool:
    depth = 0
    quote = ""
    escaped = False
    for character in value:
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = ""
        elif character in "\"'":
            quote = character
        elif character == "[":
            depth += 1
        elif character == "]":
            depth -= 1
            if depth == 0:
                return True
    return False


def _requirement_names(value: str, pattern: str) -> set[str]:
    # PEP 735 include-group tables name groups, not packages.
    values = re.sub(r"\{[^{}]*\}", "", value, flags=re.DOTALL)
    return set(re.findall(pattern, values))


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
