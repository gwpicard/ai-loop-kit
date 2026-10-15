#!/usr/bin/env python3
"""Run mutmut only for functions touched since a base ref."""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path


def source_paths(cwd: Path) -> list[Path]:
    """Read mutmut's configured source paths from pyproject.toml."""
    config = cwd / "pyproject.toml"
    try:
        import tomllib
    except ImportError:  # Python 3.10
        try:
            text = config.read_text()
        except OSError:
            return []
        section = re.search(r"(?ms)^\[tool\.mutmut\]\s*$(.*?)(?=^\[|\Z)", text)
        match = re.search(r"(?m)^\s*source_paths\s*=\s*(\[[^\]]*\])", section[1]) if section else None
        values = ast.literal_eval(match[1]) if match else []
    else:
        try:
            values = tomllib.loads(config.read_text()).get("tool", {}).get("mutmut", {}).get(
                "source_paths", [])
        except (OSError, ValueError):
            values = []
    return [Path(item) for item in values if isinstance(item, str)]


def patterns(base: str, cwd: Path = Path.cwd()) -> list[str]:
    diff = subprocess.run(["git", "diff", "--no-ext-diff", "--no-color", "-U0",
                           f"{base}...HEAD"], cwd=cwd, capture_output=True,
                          text=True, check=True).stdout
    changed: dict[str, set[int]] = {}
    path = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            changed.setdefault(path, set())
        elif path and line.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                start, count = int(match.group(1)), int(match.group(2) or "1")
                changed[path].update(range(start, start + count))

    roots = source_paths(cwd)
    out = set()
    for name, lines in changed.items():
        if not name.endswith(".py") or not lines:
            continue
        relative = Path(name)
        source_root = next((root for root in roots
                            if relative == root or root in relative.parents), None)
        if source_root is None:
            continue
        source = cwd / name
        try:
            tree = ast.parse(source.read_text())
        except (OSError, SyntaxError):
            continue
        module = relative.relative_to(source_root).with_suffix("").as_posix().replace("/", ".")
        if module.endswith(".__init__"):
            module = module[:-9]
        scopes: set[str] = set()

        def changed_in_scope(node: ast.AST) -> bool:
            start, end = getattr(node, "lineno", 0), getattr(node, "end_lineno", 0)
            nested = [(getattr(child, "lineno", 0), getattr(child, "end_lineno", 0))
                      for child in ast.walk(node) if child is not node and
                      isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))]
            return any(start <= line <= end and
                       not any(child_start <= line <= child_end
                               for child_start, child_end in nested)
                       for line in lines)

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and changed_in_scope(node):
                scopes.add(f"{module}.x_{node.name}__mutmut_*")
            elif isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and changed_in_scope(method):
                        scopes.add(f"{module}.xǁ{node.name}ǁ{method.name}__mutmut_*")
        out.update(scopes)
    return sorted(out)


def results_pass(output: str, selected: list[str]) -> bool:
    """Fail selected mutants unless mutmut recorded them as killed."""
    if not selected:
        return True
    mutants = re.findall(r"([^\s:]+__mutmut_\d+)[ \t]*:?[ \t]*(.*?)[ \t]*$",
                         output, re.IGNORECASE | re.MULTILINE)
    for target in selected:
        prefix = target.removesuffix("__mutmut_*")
        matching = [(name, status) for name, status in mutants
                    if re.fullmatch(re.escape(prefix) + r"__mutmut_\d+", name)]
        if any(status.strip().lower() != "killed" for _, status in matching):
            return False
    return True


def mutmut_version_supported(output: str) -> bool:
    """Return whether mutmut reports version 3.8 or later."""
    match = re.search(r"\bversion\s+(\d+)\.(\d+)(?:\.(\d+))?", output,
                      re.IGNORECASE)
    return bool(match and (int(match[1]), int(match[2])) >= (3, 8))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", nargs="?", default="origin/main")
    base = parser.parse_args().base
    if not source_paths(Path.cwd()):
        print("mutmut: no mutmut source paths configured", file=sys.stderr)
        return 2
    try:
        version = subprocess.run(["mutmut", "--version"], capture_output=True, text=True)
    except OSError as error:
        print(f"mutmut: version 3.8 or later is required; could not run mutmut: {error}",
              file=sys.stderr)
        return 2
    version_output = version.stdout + version.stderr
    if version.returncode or not mutmut_version_supported(version_output):
        print("mutmut: version 3.8 or later is required; got "
              + (version_output.strip() or "no version output"), file=sys.stderr)
        return 2
    selected = patterns(base)
    if not selected:
        print("no changed Python functions found")
        return 0
    for pattern in selected:
        result = subprocess.run(["mutmut", "run", pattern])
        if result.returncode:
            return result.returncode
    results = subprocess.run(["mutmut", "results", "--all", "true"],
                             capture_output=True, text=True)
    print(results.stdout, end="")
    if results.returncode:
        print(results.stderr, file=sys.stderr, end="")
        return results.returncode
    if not results_pass(results.stdout, selected):
        print("mutmut: a changed-function mutant was not killed",
              file=sys.stderr)
        return 1
    mutant_names = re.findall(r"([^\s:]+__mutmut_\d+)\s*:", results.stdout)
    for pattern in selected:
        prefix = pattern.removesuffix("__mutmut_*")
        if not any(re.fullmatch(re.escape(prefix) + r"__mutmut_\d+", name)
                   for name in mutant_names):
            print(f"mutmut: {prefix} nothing to mutate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
