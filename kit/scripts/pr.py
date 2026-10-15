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
    tests = [p for p in added if "test" in p.lower() or Path(p).name.startswith("test_")
             or p in ready.get("files", [])]
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
    risk.append(f"{len(importers)} project file(s) import a named or changed module")
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
    risk_text += "\n- Importers: " + (", ".join(f"`{p}`" for p in importers) if importers else "none found")
    why_path = folder / ".loop" / "why.md"
    why = why_path.read_text(errors="replace").strip() if why_path.is_file() else "Why: not supplied.\n\nWhat could go wrong: not supplied."
    evidence = (f"- Judge, Keep and Quality output:\n\n```text\n{output.strip()[-5000:]}\n```\n"
                f"- Bar hash: `{ready['bar']}`\n- Judged commit: `{rev(folder, 'HEAD')}`\n"
                f"- Tests added: {tests_text}\n- New dependencies: {dependency_text}\n- {revert}")
    facts = ("## What changed\n\n" + areas + "\n\n## Risk\n\n" + risk_text +
             "\n\n## Why and what could go wrong\n\n" + why + "\n")
    return facts, evidence


def open_pull_request(gh: GitHub, root: Path, folder: Path, n: int, issue: dict,
                      k: int, output: str, review: Optional[dict] = None) -> str:
    sh(["git", "push", "--quiet", "-u", "origin", branch_name(n)], folder)
    facts, evidence = pull_request_facts(folder, last_record(gh.comments(n), "ready") or {}, output)
    body = (f"Builds piece #{n}: {issue['title']}\n\nCloses #{n}\n\n"
            f"The gate ran the frozen judge itself after attempt {k}, and it passed.\n\n"
            f"{facts}\n## Evidence\n\n{evidence}\n")
    review = review or {}
    if review.get("contract_findings"):
        body = ("## Contract review findings\n\n" + "\n".join(
            f"- {finding}" for finding in review["contract_findings"]) + "\n\n" + body)
    if review.get("reviewer_note"):
        body += f"\n## Review\n\n{review['reviewer_note']}\n"
    if review.get("standards_findings"):
        body += "\nStandards findings:\n" + "\n".join(
            f"- {finding}" for finding in review["standards_findings"]) + "\n"
    if review.get("follow_ups"):
        body += "\n## Follow-up pieces\n\n" + "\n".join(
            f"- {finding}" for finding in review["follow_ups"]) + "\n"
    changed = changed_check_settings(folder)
    if changed:
        body += ("\n**Check settings changed** (the spec allows it). Read these first:\n"
                 + "".join(f"- `{c}`\n" for c in changed))
    existing = gh.pr_for_branch(branch_name(n))
    if existing and existing["state"] == "OPEN":
        url = existing["url"]
        gate.move(gh, root, n, "approval", folder=folder, pr=url)
    else:
        # The submit move must pass before a new pull request can be created.
        gate.move(gh, root, n, "approval", folder=folder)
        try:
            url = gh.create_pr(branch_name(n), issue["title"], body)
        except Exception:
            gate.move(gh, root, n, "shaping", reason="pull request creation failed after submit",
                      reason_type="environment")
            raise
        gh.comment(n, f"**Gate:** pull request created after submit passed: {url}")
    return f"piece {n}: pull request ready for you: {url}"


