"""Build the instructions and project context for one builder attempt."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Optional

KIT = Path(__file__).resolve().parent.parent


def dependent_files(folder: Path, approach: str, changed: list[str],
                    exclude: Optional[list[str]] = None) -> list[str]:  # noqa: UP045
    """List project source files that import a path or module named by the piece."""
    names = set()
    for path in changed:
        names.add(Path(path).stem)
    paths = re.findall(r"(?<![\w.-])([\w./-]+\.(?:py|js|jsx|ts|tsx|mjs|cjs))\b", approach)
    for path in paths:
        names.add(Path(path).stem)
    if not names:
        return []
    ignored = {".git", ".venv", "venv", "node_modules", "dist", "build", ".loop"}
    excluded = set(exclude or [])
    found = []
    for path in folder.rglob("*"):
        relative = path.relative_to(folder).as_posix()
        if not path.is_file() or ignored.intersection(path.parts) or relative in excluded:
            continue
        if any(part.lower() in {"test", "tests", "__tests__"} for part in path.parts) or \
                path.name.startswith("test_"):
            continue
        if path.suffix not in {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
            continue
        try:
            source = path.read_text(errors="replace")
        except OSError:
            continue
        depends = False
        if path.suffix == ".py":
            try:
                tree = ast.parse(source)
                imported = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported.update(alias.name.split(".")[0] for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported.add(node.module.split(".")[0])
                depends = bool(imported & names)
            except SyntaxError:
                depends = any(re.search(rf"\b{re.escape(name)}\b", source) for name in names)
        else:
            depends = bool(re.search(r"\b(?:import|require)\b", source)) and any(
                re.search(rf"(?:[/.'\"]|\b){re.escape(name)}(?:[/.'\"]|\b)", source)
                for name in names)
        if depends:
            found.append(path.relative_to(folder).as_posix())
    return sorted(set(found))


def brief(n: int, body: str, ready: dict, last_failure: str, came_back: str = "",
          folder: Optional[Path] = None) -> str:  # noqa: UP045
    text = (KIT / "briefs" / "builder.md").read_text()
    files = "\n".join(f"- `{f}`" for f in ready["files"]) or "- (none: the command is the judge)"
    command = ready.get("command", "")
    kind_rules = ""
    if ready.get("checks"):
        command = "\n".join(
            f"{check['type'].title()}: " + check.get("command", "")
            for check in ready["checks"])
        if any(check["type"] == "measure" for check in ready["checks"]):
            kind_rules += ("Before changing code, write one testable hypothesis to "
                           "`.loop/hypothesis`. The gate measures the result three times "
                           "and uses the median. Meet every Measure target and Keep check.\n")
    earlier = last_failure or "This is the first attempt."
    playbook = ("For a fix, reproduce the reported bug before changing code, then find and "
                "address its cause. This is work guidance. The gate checks only the Exit "
                "and Keep checks.\n" if ready.get("playbook") == "fix" else "")
    if came_back:
        earlier = ("This piece was built before and came back for these reasons:\n"
                   f"{came_back}\nThe branch still holds that earlier build. Change it so the "
                   f"reasons no longer apply.\n\n{earlier}")
    for key, value in {"PIECE": str(n), "SPEC": body.strip(),
                       "APPROACH": ready.get("approach", "") or "No approach was supplied.",
                       "RESEARCH": research_brief(ready),
                       "PLAYBOOK": playbook,
                       "COMMAND": command,
                       "FILES": files,
                       "DEPENDENTS": "\n".join(
                           f"- `{f}`" for f in dependent_files(
                               folder or Path.cwd(), ready.get("approach", ""), [],
                               ready.get("files")))
                       or "- (none found)",
                       "LAST_FAILURE": earlier}.items():
        text = text.replace("{{" + key + "}}", value)
    if kind_rules:
        text += "\n## Loop kind instructions\n\n" + kind_rules
    return text


def research_brief(ready: dict) -> str:
    """Format frozen findings and claim-time stale flags for the builder."""
    stale = set(ready.get("stale_research", []))
    lines = [f"- {item['id']}: {item['finding']} (source: {item['source']}, read: {item['read']})"
             + (" [possibly stale]" if item["id"] in stale else "")
             for item in ready.get("research", [])]
    return "\n".join(lines) or "- No outside facts were used."
