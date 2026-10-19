#!/usr/bin/env python3
"""Pull request facts and submission for the run."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import gate
from loopkit import (GitHub, branch_name, changed_check_settings, last_record, main_ref,
                     rev, sh)
import run

def pull_request_facts(folder: Path, ready: dict, output: str) -> tuple[str, str]:
    main = main_ref(folder)
    paths = sh(["git", "diff", "--no-renames", "--name-only",
                f"{main}...HEAD"], folder).stdout.splitlines()
    grouped: dict[str, list[str]] = {}
    for path in paths:
        area = Path(path).parts[0] if len(Path(path).parts) > 1 else "root"
        grouped.setdefault(area, []).append(path)
    areas = "\n".join(f"- **{area}:** " + ", ".join(f"`{p}`" for p in sorted(files))
                      for area, files in sorted(grouped.items())) or "- No tracked files changed."
    added = sh(["git", "diff", "--no-renames", "--name-only", "--diff-filter=A", f"{main}...HEAD"],
               folder).stdout.splitlines()
    checks = ready.get("checks", [])
    test_files = {p for check in checks if check["type"] == "tests" for p in check["files"]}
    if not checks and ready.get("kind", "feature") in ("feature", "fix", "scaffold"):
        test_files.update(ready.get("files", []))
    support = set(ready.get("files", [])) - test_files
    tests = [p for p in added if p not in support and ("test" in p.lower() or p in test_files)]
    support_text = ", ".join(f"`{p}`" for p in sorted(support)) or "none"
    tests_text = ", ".join(f"`{p}`" for p in tests) if tests else "none added"
    manifests = [p for p in paths if Path(p).name in
                 {"package.json", "pyproject.toml", "requirements.txt", "requirements-dev.txt"}
                 or Path(p).name.startswith("requirements") and p.endswith(".txt")]
    dependencies = []
    for manifest in manifests:
        diff = sh(["git", "diff", "--no-ext-diff", "--unified=0", f"{main}...HEAD", "--", manifest],
                  folder).stdout
        additions = [line[1:].strip() for line in diff.splitlines()
                     if line.startswith("+") and not line.startswith("+++")]
        dependencies.append(f"`{manifest}`: " + (", ".join(additions) if additions else "changed"))
    dependency_text = "; ".join(dependencies) if dependencies else "none"
    protected = ready.get("protected_paths", [])
    risk = []
    if any(any(path == p.rstrip("/") or path.startswith(p.rstrip("/") + "/") for p in protected)
           for path in paths):
        risk.append("protected paths touched")
    if any(re.search(r"(^|/)(migrations?|alembic)(/|$)", p, re.I) for p in paths):
        risk.append("migration files touched")
    if any(re.search(r"(^|/)(config|\.github)(/|$)|(^|/)[^/]*config[^/]*$", p, re.I)
           or p.startswith(".github/") for p in paths):
        risk.append("configuration or CI files touched")
    standards = ready.get("standards", "")
    changed_settings = changed_check_settings(folder, (standards,) if standards else ())
    if changed_settings:
        risk.append("check settings touched: " + ", ".join(changed_settings))
    importers = run.dependent_files(folder, ready.get("approach", ""), paths, ready.get("files"))
    risk.append(f"{len(importers)} source file(s) found importing a named or changed module "
                "in the Python and JavaScript/TypeScript scan; excludes test directories, "
                "test_* files, exit files, and .git, .venv, venv, node_modules, dist, build, .loop")
    large = []
    for path in paths:
        candidate = folder / path
        if candidate.is_file():
            count = len(candidate.read_text(errors="replace").splitlines())
            if count > 1000:
                large.append(f"`{path}` ({count} lines)")
    if large:
        risk.append("files over 1,000 lines: " + ", ".join(large))
    migration_count = sum(bool(re.search(r"(^|/)(migrations?|alembic)(/|$)", p, re.I)) for p in paths)
    revert = f"Revert {len(paths)} changed file(s)" + (
        f" and account for {migration_count} migration file(s)" if migration_count else "") + "."
    risk_text = "\n".join(f"- {line}" for line in risk) if risk else "- No flagged paths."
    risk_text += "\n- Importers in this scan: " + (
        ", ".join(f"`{p}`" for p in importers) if importers else "none found in this scan")
    why_path = folder / ".loop" / "why.md"
    why = why_path.read_text(errors="replace").strip() if why_path.is_file() else "Why: not supplied.\n\nWhat could go wrong: not supplied."
    shown = output.strip()
    if len(shown) > 5000:
        tail = shown[-5000:] if shown[-5001] == "\n" else shown[-5000:].partition("\n")[2]
        shown = "[Evidence truncated; earlier lines omitted.]\n" + tail
    evidence = (f"- Judge, Keep and Quality output:\n\n```text\n{shown}\n```\n"
                f"- Bar hash: `{ready['bar']}`\n- Judged commit: `{rev(folder, 'HEAD')}`\n"
                f"- Tests added: {tests_text}\n- Frozen exit-support files: {support_text}\n"
                f"- New dependencies: {dependency_text}\n- {revert}")
    facts = ("## What changed\n\n" + areas + "\n\n## Risk\n\n" + risk_text +
             "\n\n## Why and what could go wrong\n\n" + why + "\n")
    return facts, evidence


def open_pull_request(gh: GitHub, root: Path, folder: Path, n: int, issue: dict,
                      k: int, output: str, review: Optional[dict] = None,
                      seconds: float = 0) -> str:
    sh(["git", "push", "--quiet", "-u", "origin", branch_name(n)], folder)
    existing = gh.pr_for_branch(branch_name(n))
    url = existing["url"] if existing and existing["state"] == "OPEN" else ""
    checked = {}
    gate.move(gh, root, n, "approval", folder=folder, pr=url, attempts=k, seconds=seconds,
              evidence=checked)
    submitted = last_record(gh.comments(n), "submit") or {}
    ready = last_record(gh.comments(n), "ready") or {}
    facts, evidence = pull_request_facts(folder, ready, checked["output"])
    regression = submitted["regression"]
    evidence += (f"\n- Regression: `{regression['command']}`; exit {regression['exit']}; "
                 f"commit `{regression['commit']}`.")
    body = (f"Builds piece #{n}: {issue['title']}\n\nCloses #{n}\n\n"
            f"The gate ran the frozen judge itself after attempt {k}, and it passed.\n\n"
            f"{facts}\n## Evidence\n\n{evidence}\n")
    if any(check["type"] != "tests" for check in ready.get("checks", [])):
        history = output if len(output) <= 5000 else (
            "[Earlier evidence truncated.]\n" + output[-5000:].partition("\n")[2])
        body += f"\n## Earlier attempt evidence\n\n```text\n{history}\n```\n"
    review = review or {}
    if review.get("contract_findings"):
        body = ("## Contract review findings\n\n" + "\n".join(
            f"- {finding}" for finding in review["contract_findings"]) + "\n\n" + body)
    if review.get("reviewer_note"):
        body += f"\n## Review\n\n{review['reviewer_note']}\n"
    for key, heading in (("standards_findings", "Standards findings:"),
                         ("baseline_conflicts", "## Frozen baseline conflicts"),
                         ("follow_ups", "## Follow-up pieces")):
        if review.get(key):
            body += f"\n{heading}\n\n" + "\n".join(f"- {item}" for item in review[key]) + "\n"
    changed = changed_check_settings(folder)
    if changed:
        body += ("\n**Check settings changed** (the spec allows it). Read these first:\n"
                 + "".join(f"- `{c}`\n" for c in changed))
    action = "update" if url else "creation"
    try:
        if url:
            gh.edit_pr(url, issue["title"], body)
        else:
            url = gh.create_pr(branch_name(n), issue["title"], body)
    except Exception:
        gate.move(gh, root, n, "shaping", reason=f"pull request {action} failed after submit",
                  reason_type="environment", cause="pull-request-failed")
        raise
    if action == "creation":
        gh.comment(n, f"**Gate:** pull request created after submit passed: {url}")
    return f"piece {n}: pull request ready for you: {url}"


