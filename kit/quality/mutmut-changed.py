#!/usr/bin/env python3
"""Run mutmut only for functions touched since a base ref."""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path


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

    out = set()
    for name, lines in changed.items():
        if not name.endswith(".py") or not lines:
            continue
        source = cwd / name
        try:
            tree = ast.parse(source.read_text())
        except (OSError, SyntaxError):
            continue
        module = name[:-3].replace("/", ".")
        if module.endswith(".__init__"):
            module = module[:-9]
        scopes = []

        def visit(node: ast.AST, parents: tuple[str, ...] = ()) -> None:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scope = parents + (node.name,)
                if any(getattr(node, "lineno", 0) <= line <= getattr(node, "end_lineno", 0)
                       for line in lines):
                    scopes.append(".".join((module, *scope)) + "*")
                parents = scope
            elif isinstance(node, ast.ClassDef):
                parents = parents + (node.name,)
            for child in ast.iter_child_nodes(node):
                visit(child, parents)

        visit(tree)
        out.update(scopes or {module + "*"})
    return sorted(out)


def results_pass(output: str, selected: list[str]) -> bool:
    """Require named mutants for selected functions and no surviving mutants."""
    if not selected:
        return True
    if re.search(r"Survived mutants:\s*[1-9]\d*", output, re.IGNORECASE):
        return False
    mutants = re.findall(r"([\w.ǁ]+__mutmut_\d+)", output)
    if not mutants:
        return False
    targets = [pattern.rstrip("*").replace(".", "_").replace("ǁ", "_")
               for pattern in selected]
    named = [name.replace("ǁ", "_") for name in mutants]
    return all(any(name.startswith(target) for name in named) for target in targets)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", nargs="?", default="origin/main")
    base = parser.parse_args().base
    selected = patterns(base)
    if not selected:
        print("no changed Python functions found")
        return 0
    for pattern in selected:
        result = subprocess.run(["mutmut", "run", pattern])
        if result.returncode:
            return result.returncode
    results = subprocess.run(["mutmut", "results"], capture_output=True, text=True)
    print(results.stdout, end="")
    if results.returncode:
        print(results.stderr, file=sys.stderr, end="")
        return results.returncode
    if not results_pass(results.stdout, selected):
        print("mutmut: changed functions have no tested mutants or a mutant survived",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
