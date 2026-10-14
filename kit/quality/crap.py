#!/usr/bin/env python3
"""Check CRAP scores for changed Python functions from coverage.py JSON."""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


class Complexity(ast.NodeVisitor):
    def __init__(self) -> None:
        self.value = 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_If(self, node: ast.If) -> None:
        self.value += 1
        self.generic_visit(node)

    visit_For = visit_If
    visit_AsyncFor = visit_If
    visit_While = visit_If
    visit_IfExp = visit_If

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.value += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.value += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.value += len(node.ifs)
        self.generic_visit(node)

    def visit_match_case(self, node: ast.match_case) -> None:
        if not isinstance(node.pattern, ast.MatchAs) or node.pattern.name is not None:
            self.value += 1
        self.generic_visit(node)


def functions(source: str) -> list[dict]:
    tree = ast.parse(source)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        counter = Complexity()
        for statement in node.body:
            counter.visit(statement)
        found.append({"name": node.name, "start": node.lineno,
                      "end": getattr(node, "end_lineno", node.lineno),
                      "complexity": counter.value})
    return sorted(found, key=lambda item: (item["start"], item["name"]))


def changed_ranges(diff: str) -> dict[str, list[tuple[int, int]]]:
    ranges: dict[str, list[tuple[int, int]]] = {}
    path = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            ranges.setdefault(path, [])
        elif path and line.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                start, count = int(match.group(1)), int(match.group(2) or "1")
                if count:
                    ranges[path].append((start, start + count - 1))
                else:
                    ranges[path].append((max(1, start - 1), max(1, start)))
    return ranges


def overlap(function: dict, ranges: list[tuple[int, int]]) -> bool:
    return any(function["start"] <= end and function["end"] >= start
               for start, end in ranges)


def coverage_data(data: dict, path: str, root: Path) -> tuple[set[int], set[int]]:
    files = data.get("files", {})
    entry = files.get(path)
    if entry is None:
        target = (root / path).resolve()
        entry = next((value for name, value in files.items()
                      if Path(name).is_absolute() and Path(name).resolve() == target
                      or not Path(name).is_absolute() and Path(name).as_posix().endswith(path)), {})
    return set(entry.get("executed_lines", [])), set(entry.get("missing_lines", []))


def coverage_for(function: dict, executed: set[int], missing: set[int]) -> float:
    lines = {line for line in executed | missing
             if function["start"] <= line <= function["end"]}
    if not lines:
        return 0.0
    return len(lines & executed) / len(lines)


def score(complexity: int, coverage: float) -> float:
    return complexity * complexity * (1.0 - coverage) ** 3 + complexity


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", required=True, help="coverage.py JSON output")
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        coverage = json.loads((root / args.coverage).read_text())
        diff = git(root, "diff", "--no-ext-diff", "--unified=0", f"{args.base}...HEAD")
        ranges = changed_ranges(diff)
        failures = []
        for path, changed in ranges.items():
            if not path.endswith(".py") or not (root / path).is_file():
                continue
            current_source = (root / path).read_text(errors="replace")
            current_functions = functions(current_source)
            executed, missing = coverage_data(coverage, path, root)
            old_result = subprocess.run(["git", "show", f"{args.base}:{path}"], cwd=root,
                                        capture_output=True, text=True)
            base_functions = functions(old_result.stdout) if old_result.returncode == 0 else []
            baseline: dict[tuple[str, int], dict] = {}
            counts: dict[str, int] = {}
            for item in base_functions:
                occurrence = counts.get(item["name"], 0)
                counts[item["name"]] = occurrence + 1
                baseline[(item["name"], occurrence)] = item
            counts = {}
            for item in current_functions:
                occurrence = counts.get(item["name"], 0)
                counts[item["name"]] = occurrence + 1
                if not overlap(item, changed):
                    continue
                cover = coverage_for(item, executed, missing)
                current = score(item["complexity"], cover)
                old = baseline.get((item["name"], occurrence))
                old_score = None
                if old:
                    old_cover = coverage_for(old, executed, missing)
                    old_score = score(old["complexity"], old_cover)
                if current >= 30 or old_score is not None and current > old_score:
                    suffix = f", main={old_score:.2f}" if old_score is not None else ""
                    failures.append(f"CRAP: {path}:{item['start']} {item['name']} "
                                    f"complexity={item['complexity']} coverage={cover:.0%} "
                                    f"score={current:.2f}{suffix}")
        if failures:
            print("\n".join(failures))
            return 1
        print("CRAP: changed functions are below 30 and do not exceed main.")
        return 0
    except (OSError, ValueError, RuntimeError, SyntaxError, KeyError) as error:
        print(f"CRAP: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
