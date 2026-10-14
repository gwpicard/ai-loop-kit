"""Small checks for tests that could pass without testing the contract."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterable


def python_findings(path: Path, text: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as error:
        return [(error.lineno or 1, "python syntax error")]
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test"):
            continue
        calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)]
        asserts = [n for n in ast.walk(node) if isinstance(n, ast.Assert)]
        meaningful = bool(asserts or any(_name(c.func).split(".")[-1].startswith("assert") or
                         _name(c.func) == "pytest.raises" for c in calls))
        if not meaningful:
            findings.append((node.lineno, "test has no assertion"))
        for assertion in asserts:
            test = assertion.test
            if isinstance(test, ast.Constant) and test.value is True:
                findings.append((assertion.lineno, "assert True"))
            elif isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
                left, right = test.left, test.comparators[0]
                if ast.dump(left) == ast.dump(right):
                    findings.append((assertion.lineno, "assert expression equals itself"))
                elif isinstance(left, ast.Constant) and isinstance(right, ast.Constant):
                    findings.append((assertion.lineno, "assert compares two literals"))
        for call in calls:
            name = _name(call.func)
            if name == "pytest.mark.skip" or name == "pytest.mark.skipif" or name == "pytest.mark.xfail":
                findings.append((call.lineno, "pytest skip or xfail marker"))
        for decorator in node.decorator_list:
            name = _name(decorator.func if isinstance(decorator, ast.Call) else decorator)
            if name in ("pytest.mark.skip", "pytest.mark.skipif", "pytest.mark.xfail"):
                findings.append((decorator.lineno, "pytest skip or xfail marker"))
    return findings


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def javascript_findings(path: Path, text: str) -> list[tuple[int, str]]:
    findings = []
    for match in re.finditer(r"\.(only|skip)\s*\(|\b(xit|xdescribe)\s*\(", text):
        findings.append((text.count("\n", 0, match.start()) + 1, "disabled or skipped test"))
    for match in re.finditer(r"\btest\s*\(|\bit\s*\(", text):
        start = match.end()
        depth = 1
        end = start
        while end < len(text) and depth:
            if text[end] == "(":
                depth += 1
            elif text[end] == ")":
                depth -= 1
            end += 1
        block = text[start:end]
        line = text.count("\n", 0, match.start()) + 1
        if not re.search(r"\bexpect\s*\(|\bassert\b", block):
            findings.append((line, "test has no expect or assert"))
    for match in re.finditer(r"\bexpect\s*\(\s*true\s*\)", text):
        findings.append((text.count("\n", 0, match.start()) + 1, "expect(true)"))
    return findings


def lint_files(files: Iterable[Path]) -> list[str]:
    """Return one file:line:rule line for each finding."""
    out = []
    for path in files:
        text = path.read_text(errors="replace")
        if path.suffix == ".py":
            findings = python_findings(path, text)
        elif path.suffix in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
            findings = javascript_findings(path, text)
        else:
            continue
        out.extend(f"{path}:{line}: {rule}" for line, rule in findings)
    return out
