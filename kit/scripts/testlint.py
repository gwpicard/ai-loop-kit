"""Small checks for tests that could pass without testing the contract."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterable, Optional


def _is_project_module(root: Path, module: str, source: Path) -> bool:
    if module.startswith("."):
        try:
            relative = source.resolve().relative_to(root.resolve()).parent
        except ValueError:
            relative = Path()
        level = len(module) - len(module.lstrip("."))
        parts = list(relative.parts[:max(0, len(relative.parts) - level + 1)])
        module = ".".join(parts + [part for part in module[level:].split(".") if part])
    parts = [part for part in module.split(".") if part]
    if not parts:
        return False
    bases = [root.joinpath(*parts), root / Path("src").joinpath(*parts)]
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(errors="replace")
        for match in re.finditer(r"(?m)^\s*where\s*=\s*\[([^]]*)\]", text):
            for location in re.findall(r"['\"]([^'\"]+)['\"]", match.group(1)):
                bases.append(root / location)
    return any(base.with_suffix(".py").is_file() or (base / "__init__.py").is_file()
               for base in bases)


def _project_source_path(root: Path, value: str) -> Optional[str]:
    value = value.strip().strip("`'\"")
    if not value or "{" in value or "$" in value:
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        try:
            candidate = candidate.resolve().relative_to(root.resolve())
        except ValueError:
            return None
    candidate = (root / candidate).resolve()
    try:
        relative = candidate.relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
    if not candidate.is_file() or candidate.suffix not in {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
        return None
    parts = Path(relative).parts
    if any(part.lower() in {"test", "tests", "__tests__"} for part in parts) or \
            candidate.name.startswith(("test_", "judge_")):
        return None
    return relative


def _contract_names_file(contract: str, relative: str) -> bool:
    text = contract.lower()
    return relative.lower() in text or Path(relative).name.lower() in text


def python_findings(path: Path, text: str,
                    project_root: Optional[Path] = None,
                    contract: str = "") -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as error:
        return [(error.lineno or 1, "python syntax error")]
    if project_root:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    private = [part for part in alias.name.split(".") if part.startswith("_")]
                    if private and _is_project_module(project_root, alias.name, path):
                        findings.append((node.lineno, "judge imports a private project name: " + alias.name))
            elif isinstance(node, ast.ImportFrom) and node.module and \
                    _is_project_module(project_root, node.module, path):
                names = [alias.name for alias in node.names if alias.name.startswith("_")]
                if node.module.rsplit(".", 1)[-1].startswith("_"):
                    names.append(node.module)
                if names:
                    findings.append((node.lineno, "judge imports a private project name: " +
                                     ", ".join(names)))
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
        if len(asserts) == 1 and isinstance(asserts[0].test, ast.Compare):
            comparison = asserts[0].test
            if len(comparison.comparators) == 1 and isinstance(comparison.left, ast.Call) and \
                    isinstance(comparison.comparators[0], ast.Call) and \
                    ast.dump(comparison.left.func) == ast.dump(comparison.comparators[0].func):
                findings.append((asserts[0].lineno,
                                 "only assertion compares calls to the same function"))
        if project_root:
            for call in calls:
                name = _name(call.func)
                if name == "open" and call.args and isinstance(call.args[0], ast.Constant) and \
                        isinstance(call.args[0].value, str):
                    source = _project_source_path(project_root, call.args[0].value)
                    if source and not _contract_names_file(contract, source):
                        findings.append((call.lineno, "test reads project source as text: " + source))
                elif name.endswith((".read_text", ".read_bytes")):
                    source_arg = next((n for n in ast.walk(call.func.value)
                                       if isinstance(n, ast.Constant) and isinstance(n.value, str)), None) \
                        if isinstance(call.func, ast.Attribute) else None
                    if source_arg:
                        source = _project_source_path(project_root, source_arg.value)
                        if source and not _contract_names_file(contract, source):
                            findings.append((call.lineno, "test reads project source as text: " + source))
        for call in calls:
            name = _name(call.func)
            if name in ("pytest.mark.skip", "pytest.mark.skipif", "pytest.mark.xfail",
                        "pytest.skip", "pytest.importorskip"):
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


def javascript_findings(path: Path, text: str,
                        project_root: Optional[Path] = None,
                        contract: str = "") -> list[tuple[int, str]]:
    findings = []
    for match in re.finditer(r"\.(only|skip|todo)\s*\(|\b(xit|xdescribe)\s*\(", text):
        findings.append((text.count("\n", 0, match.start()) + 1, "disabled or skipped test"))
    for match in re.finditer(r"(?<![\w$.])test\s*\(|(?<![\w$.])it\s*\(", text):
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
        if project_root:
            for read in re.finditer(r"\breadFileSync\s*\(\s*['\"]([^'\"]+)['\"]", block):
                source = _project_source_path(project_root, read.group(1))
                if source and not _contract_names_file(contract, source):
                    findings.append((line + block.count("\n", 0, read.start()),
                                     "test reads project source as text: " + source))
        same_calls = re.search(
            r"expect\s*\(\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*\([^)]*\)\s*\)"
            r"\s*\.to(?:Be|Equal)\s*\(\s*\1\s*\([^)]*\)\s*\)", block)
        if same_calls and len(re.findall(r"\bexpect\s*\(", block)) == 1:
            findings.append((line, "only assertion compares calls to the same function"))
    for match in re.finditer(r"\bexpect\s*\(\s*true\s*\)", text):
        findings.append((text.count("\n", 0, match.start()) + 1, "expect(true)"))
    if project_root:
        imports = [re.compile(r"import\s*\{([^}]+)\}\s*from\s*['\"]([^'\"]+)"),
                   re.compile(r"(?:const|let|var)\s*\{([^}]+)\}\s*=\s*require\s*\(\s*['\"]([^'\"]+)")]
        for pattern in imports:
            for match in pattern.finditer(text):
                names, module = match.groups()
                module = module or ""
                target = (Path(path).parent / module).resolve()
                if not any(candidate.is_file() for candidate in
                           (target, target.with_suffix(".js"), target.with_suffix(".ts"),
                            target / "index.js", target / "index.ts")):
                    continue
                private = re.findall(r"(?:^|,)\s*(_[A-Za-z0-9_$]+)", names or "")
                if private:
                    findings.append((text.count("\n", 0, match.start()) + 1,
                                     "judge imports a private project name: " + ", ".join(private)))
    return findings


def lint_files(files: Iterable[Path], project_root: Optional[Path] = None,
               contract: str = "") -> list[str]:
    """Return one file:line:rule line for each finding."""
    out = []
    for path in files:
        text = path.read_text(errors="replace")
        if path.suffix == ".py":
            findings = python_findings(path, text, project_root, contract)
        elif path.suffix in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
            findings = javascript_findings(path, text, project_root, contract)
        else:
            continue
        out.extend(f"{path}:{line}: {rule}" for line, rule in findings)
    return out
