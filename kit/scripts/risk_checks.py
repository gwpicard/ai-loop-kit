"""Checks for dependency and protected path risks named by a piece."""
from __future__ import annotations

import json
import re
from pathlib import Path

from loopkit import sh


def _declared_dependencies(path: str, content: str) -> dict[str, str]:
    """Read direct dependencies, each with its version constraint, from the manifest."""
    if path.endswith("package.json"):
        data = json.loads(content or "{}")
        return {name.lower().replace("_", "-"): str(spec)
                for section in ("dependencies", "devDependencies", "optionalDependencies",
                                "peerDependencies")
                for name, spec in (data.get(section) or {}).items()}
    if path.endswith("pyproject.toml"):
        names: dict[str, str] = {}
        section = ""
        dependency_array = None
        dependency_pattern = r"['\"](([A-Za-z0-9_.-]+)(?:\[[^]]+\])?(?:[<>=!~; ][^'\"]*)?)['\"]"
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
                    names[key.lower()] = value.strip()
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
        return {name.lower().replace("_", "-"): spec for name, spec in names.items()}
    return {}


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


def _requirement_names(value: str, pattern: str) -> dict[str, str]:
    # PEP 735 include-group tables name groups, not packages.
    values = re.sub(r"\{[^{}]*\}", "", value, flags=re.DOTALL)
    return {name: re.sub(r"\s+", "", spec) for spec, name in re.findall(pattern, values)}


def unnamed_dependencies(folder: Path, base: str, named: list[str]) -> list[str]:
    allowed = {re.split(r"\s*:\s*", item, maxsplit=1)[0].lower().replace("_", "-")
               for item in named}
    added = set()
    manifests = sh(["git", "ls-files", "-z"], folder).stdout.split("\0")
    for path in (path for path in manifests
                 if Path(path).name in {"package.json", "pyproject.toml"}):
        manifest = Path(path).name
        before = sh(["git", "show", f"{base}:{path}"], folder, check=False)
        after_path = folder / path
        if not after_path.is_file():
            continue
        previous = (_declared_dependencies(manifest, before.stdout)
                    if before.returncode == 0 else {})
        current = _declared_dependencies(manifest, after_path.read_text(errors="replace"))
        added.update(name if name not in previous else f"{name} (version changed)"
                     for name, spec in current.items() if previous.get(name) != spec)
    return sorted(item for item in added if item.split(" ")[0] not in allowed)


def path_mentioned(text: str, path: str) -> bool:
    """Match a path name on component boundaries in contract prose."""
    return re.search(rf"(?<![A-Za-z0-9_.-]){re.escape(path.rstrip('/'))}(?![A-Za-z0-9_.-])",
                     text) is not None


def path_covers(declared: str, actual: str) -> bool:
    """Whether a declared relative path covers a changed path or its child."""
    declared = declared.replace("\\", "/").strip("/")
    actual = actual.replace("\\", "/").strip("/")
    return bool(declared) and (actual == declared or actual.startswith(declared + "/"))
