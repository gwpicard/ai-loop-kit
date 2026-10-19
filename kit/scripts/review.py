#!/usr/bin/env python3
"""Review sessions, verdicts and finding filters for the run."""
from __future__ import annotations

import json
import re
import shlex
import shutil
import uuid
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional

import gate
from loopkit import (CHECK_FILES, Refused, prepare,
                     judge_assertion_failed, judge_has_runner_error,
                     record_prepare_outputs, rev, sh, untracked_paths)
from procs import AttemptIdle
from run import commit_leftovers, idle_limit_seconds
from session import run_session
from run_start import cleanup_interrupted_reviews
from spec import _ITEM, _section, parse_research_section

KIT = Path(__file__).resolve().parent.parent
BASELINE_SMELLS = (
    "Mysterious Name", "Duplicated Code", "Feature Envy", "Data Clumps",
    "Primitive Obsession", "Repeated Switches", "Shotgun Surgery", "Divergent Change",
    "Speculative Generality", "Message Chains", "Middle Man", "Refused Bequest",
)
BUILTIN_RULES = (
    "Unrelated special-case branches", "Pass-through wrappers",
    "Logic in the owning layer", "Reuse existing helpers",
    "Test review: production change makes the test fail",
    "Test review: expected values are literals",
    "Test review: separate doubles for success and error paths",
    "Test review: never mock the subject under test",
    "Test review: source checks need a Contract citation",
    "Abstraction review: deletion test", "Abstraction review: two real adapters",
    "Abstraction review: replace, do not layer", "Judge review: module interface only",
)


def _diff_hunks(diff: str) -> dict[str, list[tuple[int, int]]]:
    hunks: dict[str, list[tuple[int, int]]] = {}
    path = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            hunks.setdefault(path, [])
        elif path and line.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                start, count = int(match.group(1)), int(match.group(2) or "1")
                hunks[path].append((start, start + max(count, 1) - 1))
    return hunks


def _valid_hunk(citation: str, hunks: dict[str, list[tuple[int, int]]]) -> bool:
    match = re.search(r"([^\s|]+):(\d+)(?:-(\d+))?", citation)
    if not match:
        return False
    path, start = match.group(1), int(match.group(2))
    end = int(match.group(3) or start)
    return any(start <= hi and end >= lo for lo, hi in hunks.get(path, []))


def _last_verdict(output: str, reviewer: str) -> dict:
    matches = re.findall(r"<verdict>\s*(.*?)\s*</verdict>", output, flags=re.I | re.S)
    if not matches:
        raise ValueError("missing <verdict> block")
    payload = matches[-1].strip()
    fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", payload, flags=re.I)
    if fenced:
        payload = fenced.group(1).strip()
    try:
        data = json.loads(payload)
    except ValueError as error:
        raise ValueError(f"bad verdict JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValueError("verdict must be a JSON object")
    if reviewer in ("standards", "contract"):
        if not isinstance(data.get("findings"), list):
            raise ValueError(f"{reviewer} verdict needs a findings list")
        keys = ("rule" if reviewer == "standards" else "citation", "hunk", "finding")
        for finding in data["findings"]:
            if not isinstance(finding, dict) or any(not isinstance(finding.get(key), str)
                                                    for key in keys):
                raise ValueError(f"each {reviewer} finding needs {', '.join(keys)} strings")
            if reviewer == "contract" and "reproducer" in finding:
                reproducer = finding["reproducer"]
                if (not isinstance(reproducer, dict)
                        or not isinstance(reproducer.get("file"), str)
                        or not isinstance(reproducer.get("item"), str)):
                    raise ValueError("a contract reproducer needs file and item strings")
        if reviewer == "standards" and (
                not isinstance(data.get("follow_ups"), list)
                or any(not isinstance(item, str) for item in data["follow_ups"])
                or not isinstance(data.get("changes"), str)):
            raise ValueError("standards verdict needs follow_ups strings and changes")
    elif reviewer == "judge-writer":
        if not isinstance(data.get("judge_files"), list) or not all(
                isinstance(item, str) for item in data["judge_files"]):
            raise ValueError("judge-writer verdict needs judge_files")
        if data.get("tests_per_id") is not True or not isinstance(data.get("notes"), str):
            raise ValueError("judge-writer verdict needs tests_per_id true and notes")
    return data


def _logged_verdict(logfile: Path, reviewer: str) -> dict:
    output = logfile.read_text(errors="replace") if logfile.exists() else ""
    try:
        return _last_verdict(output, reviewer)
    except ValueError as error:
        with logfile.open("a") as out:
            out.write(f"\nInvalid {reviewer} verdict: {error}\nRaw tail:\n{output[-2000:]}\n")
        raise Refused(f"{reviewer} returned an invalid verdict: {error}; next: read {logfile} "
                      "and correct the review output",
                      f"read {logfile} and correct the review output") from error


def parse_standards_findings(output: str, standards: str, diff: str,
                             baseline: dict[str, str] | None = None,
                             *, dropped: list[dict] | None = None) -> list[str]:
    """Keep only findings that cite a rule or smell and a changed hunk."""
    hunks = _diff_hunks(diff)
    allowed = {name.casefold() for name in (*BASELINE_SMELLS, *BUILTIN_RULES)}
    standard_rules = {line.strip().casefold() for line in standards.splitlines()
                      if line.strip()}
    verdict = _last_verdict(output, "standards")
    candidates = []
    for finding in verdict["findings"]:
        rule, hunk, description = (finding["rule"].strip(), finding["hunk"].strip(),
                                   finding["finding"].strip())
        reason = ""
        if not rule or rule.casefold() not in allowed | standard_rules:
            reason = "rule is not an approved standard or known smell"
        elif not _valid_hunk(hunk, hunks):
            reason = "location cites no changed hunk"
        candidates.append((finding, rule, hunk, description, reason))
    return _filter_findings(candidates, baseline, dropped)


def parse_contract_findings(output: str, body: str, diff: str,
                            baseline: dict[str, str] | None = None, *,
                            folder: Path | None = None, judged: str = "HEAD",
                            dropped: list[dict] | None = None) -> list[str]:
    """Check approved citations and changed or explicitly missing behaviour."""
    data = _last_verdict(output, "contract")
    contract = _section(body, "Contract") or _section(body, "Done when") or []
    ids = {match[1] for line in contract if (match := _ITEM.match(line))}
    research = {item["id"] for item in parse_research_section(body)[0]}
    scope = re.search(r"(?im)^\s*out of scope:\s*\n([\s\S]*)",
                      "\n".join(_section(body, "Intent") or []))
    out_of_scope = re.findall(r"(?m)^\s*[-*]\s+(\S.*)", scope[1]) if scope else []
    candidates = []
    hunks = _diff_hunks(diff)
    for finding in data.get("findings", []):
        citation = str(finding.get("citation", "")).strip()
        hunk = str(finding.get("hunk", "")).strip()
        detail = str(finding.get("finding", "")).strip()
        cited_ids = set(re.findall(r"\b([DR]\d+)\b", citation))
        cites_scope = any(item and item in citation for item in out_of_scope)
        reason = ""
        if not detail:
            reason = "finding has no description"
        elif not (cited_ids or cites_scope) or cited_ids - (ids | research):
            reason = "citation is not in the approved Contract, Research or Out of scope"
        elif folder and not _location_in_commit(hunk, folder, judged):
            reason = "location is not an existing file line in the judged commit"
        elif finding.get("kind", "changed") == "missing":
            if not cited_ids & ids or folder is None:
                reason = "missing behaviour needs an approved D item and a judged file location"
        elif not _valid_hunk(hunk, hunks):
            reason = "location cites no changed hunk"
        candidates.append((finding, citation, hunk, detail, reason))
    return _filter_findings(candidates, baseline, dropped)


def _location_in_commit(citation: str, folder: Path, judged: str) -> bool:
    match = re.fullmatch(r"([^\s|:]+):(\d+)(?:-(\d+))?", citation)
    if not match or Path(match[1]).is_absolute() or ".." in Path(match[1]).parts:
        return False
    content = sh(["git", "cat-file", "blob", f"{judged}:{match[1]}"], folder, check=False)
    return content.returncode == 0 and 1 <= int(match[2]) <= int(match[3] or match[2]) <= len(
        content.stdout.splitlines())


def _filter_findings(candidates: list, baseline: dict | None,
                     dropped: list[dict] | None) -> list[str]:
    findings, seen = [], set()
    for finding, citation, hunk, detail, reason in candidates:
        key = (citation.strip(), detail.strip())
        if not reason and key in seen:
            reason = "duplicate citation and claim"
        if reason:
            if dropped is not None:
                dropped.append({"finding": finding, "reason": reason})
        else:
            seen.add(key)
            findings.append(_finding_text(finding, f"{citation} at {hunk}: {detail}", baseline))
    return findings


def _finding_text(finding: dict, text: str, baseline: dict[str, str] | None) -> str:
    citation = finding.get("baseline_conflict", "")
    if isinstance(citation, str) and baseline and citation in baseline:
        return f"Frozen baseline conflict ({citation}: {baseline[citation]}): {text}"
    return text


def frozen_baseline(folder: Path, ready: dict) -> dict[str, str]:
    """Read numbered baseline lines from the commit approved at ready."""
    patterns = [*CHECK_FILES, "package.json", "pyproject.toml",
                ready.get("standards", ""), *ready.get("bar_files", ready.get("files", []))]
    paths = sh(["git", "ls-tree", "-rz", "--name-only", ready["commit"]], folder).stdout.split("\0")
    return {f"{path}:{i}": line
            for path in paths if path and any(
                fnmatch(path if "/" in p else Path(path).name, p) for p in patterns)
            for i, line in enumerate(
                sh(["git", "show", f"{ready['commit']}:{path}"], folder).stdout.splitlines(), 1)
            if line.strip()}


def _review_prompt(name: str, values: dict[str, str]) -> str:
    prompt = (KIT / "briefs" / name).read_text()
    prompt = prompt.replace("{{BUILTIN_RULES}}", "\n".join(f"- {rule}" for rule in BUILTIN_RULES))
    for key, value in values.items():
        prompt = prompt.replace("{{" + key + "}}", value)
    return prompt


def _review_session(folder: Path, prompt: str, logfile: Path, disallowed: list[str],
                    idle_seconds: int, protected_paths: Optional[list[str]] = None,
                    walk_away: bool = False, domains: Optional[list[str]] = None,
                    backend: str = "claude") -> str:
    def waiting(seconds: int) -> None:
        with logfile.open("a") as out:
            out.write(f"\nUsage limit; waiting {seconds} seconds before one retry.\n")

    return run_session(
        folder, prompt, logfile, idle_seconds, role="reviewer", backend=backend,
        result_event={}, on_wait=waiting, process_record=logfile.parent / "reviewer-processes",
        disallowed=disallowed, protected_paths=protected_paths,
        walk_away=walk_away, domains=domains)


def _cleanup_review_worktrees(root: Path, n: int, k: int) -> None:
    prefixes = (f"review/standards-{n}-{k}-", f"review/contract-{n}-{k}-")
    cleanup_interrupted_reviews(root, prefixes)


def review_piece(root: Path, folder: Path, n: int, k: int, issue: dict,
                 ready: dict, walk_away: bool = False,
                 domains: Optional[list[str]] = None, evidence: str = "") -> dict:
    try:
        return _review_piece(root, folder, n, k, issue, ready, walk_away, domains, evidence)
    finally:
        _cleanup_review_worktrees(root, n, k)


def contract_research(body: str) -> str:
    """Return the approved Research section for the contract reviewer."""
    return "\n".join(_section(body, "Research", include_heading=True) or ["No outside findings."])


def _review_piece(root: Path, folder: Path, n: int, k: int, issue: dict,
                  ready: dict, walk_away: bool = False,
                  domains: Optional[list[str]] = None, evidence: str = "") -> dict:
    """Run both reviewers against the approved baseline and checked attempt."""
    base, body = ready["commit"], issue["body"] or ""
    baseline = frozen_baseline(folder, ready)
    standards_path = ready.get("standards", "")
    standards = (folder / standards_path).read_text(errors="replace") if standards_path else ""
    context = {"STANDARDS": standards or "Use the built-in baseline.",
               "CONTRACT": "\n".join(line for section in
                   ("Intent", "Approach", "Contract", "Done when")
                   for line in (_section(body, section, include_heading=True) or [])),
               "RESEARCH": contract_research(body), "EVIDENCE": evidence,
               "BASELINE": "\n".join(f"{key}: {line}" for key, line in baseline.items()),
               "READY_COMMIT": base}
    logs = root / ".loop" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    denied = [*ready.get("files", []), *CHECK_FILES, *ready.get("protected_paths", []),
              "tests/**", "**/test_*", "**/*_test.py", "**/*.test.*",
              "**/*.spec.*", "**/conftest.py"]
    results = {"reviewer_note": "Standards review ran once.", "baseline_conflicts": [],
               "dropped_findings": 0}
    for role in ("standards", "contract"):
        diff = sh(["git", "diff", "--no-ext-diff", "--no-color", f"{base}..HEAD"], folder).stdout
        target = folder.parent / f"review-{role}-{n}-{k}-{uuid.uuid4().hex[:8]}"
        branch = f"review/{role}-{n}-{k}-{uuid.uuid4().hex[:8]}"
        judged = rev(folder, "HEAD")
        sh(["git", "worktree", "add", "--quiet", "-b", branch, str(target), judged], root)
        before = untracked_paths(target)
        before_dirs = {child.name for child in target.iterdir() if child.is_dir()}
        prepared, output = prepare(target, ready.get("prepare", ""),
                                   ready.get("protected_paths", []))
        if not prepared:
            raise Refused(f"Prepare failed in the {role} review folder:\n{output[-1200:]}")
        record_prepare_outputs(target, before, before_dirs)
        logfile = logs / f"piece-{n}-{role}-review.log"
        role_denied = denied
        if role == "contract":
            role_denied = [pattern for pattern in denied
                           if pattern not in ("tests/**", "**/test_*", "**/*_test.py",
                                              "**/*.test.*", "**/*.spec.*",
                                              "**/conftest.py")]
        before_review = set(sh(["git", "ls-files", "--others", "--exclude-standard", "-z"],
                               target).stdout.split("\0"))
        if _review_session(target, _review_prompt(f"{role}-reviewer.md", {
            **context, "DIFF": diff}), logfile, role_denied,
            idle_limit_seconds(folder, ready.get("idle_limit")), ready.get("protected_paths", []),
            walk_away, domains, ready.get("agent", "claude")) == "idle":
            raise AttemptIdle(f"{role} reviewer idle; see {logfile}")
        verdict = _logged_verdict(logfile, role)
        output = logfile.read_text(errors="replace")
        parser = parse_standards_findings if role == "standards" else parse_contract_findings
        dropped = []
        location = {"folder": folder, "judged": judged} if role == "contract" else {}
        findings = parser(output, standards if role == "standards" else body, diff, baseline,
                          dropped=dropped, **location)
        results["dropped_findings"] += len(dropped)
        with logfile.open("a") as out:
            for item in dropped:
                out.write("\nDropped finding: " + json.dumps(item) + "\n")
        if role == "contract":
            results["contract_findings"] = findings
            results["contract_reproducers"] = []
            verdict_findings = verdict["findings"]
            contract = (_section(body, "Contract") or _section(body, "Done when") or [])
            approved_ids = {match[1] for line in contract
                            if (match := _ITEM.match(line))}
            changed = sh(["git", "diff", "--name-only", judged], target).stdout.splitlines()
            staged = sh(["git", "diff", "--cached", "--name-only"], target).stdout.splitlines()
            added = set(sh(["git", "ls-files", "--others", "--exclude-standard", "-z"],
                           target).stdout.split("\0")) - before_review
            added.discard("")
            clean_reproducer = not changed and not staged and len(added) == 1
            for finding in verdict_findings:
                reproducer = finding.get("reproducer")
                if not reproducer or not any(
                        finding.get("finding", "").strip() in kept
                        for kept in findings):
                    continue
                path = Path(reproducer["file"])
                item = reproducer["item"]
                cited_ids = set(re.findall(r"\bD\d+\b", finding.get("citation", "")))
                if (item not in approved_ids or path.is_absolute() or ".." in path.parts
                        or item not in cited_ids or not path.suffix
                        or not clean_reproducer or path.as_posix() not in added
                        or not (target / path).is_file() or (target / path).is_symlink()):
                    continue
                if not re.search(rf"(?<![A-Za-z0-9]){re.escape(item)}(?![0-9])",
                                 (target / path).read_text(errors="replace")):
                    continue
                try:
                    result = _run_contract_reproducer(root, target, judged, ready,
                                                      path, item, n, k)
                    results["contract_reproducers"].append({
                        "file": path.as_posix(), "item": item, **result})
                finally:
                    _remove_untracked_reproducer(target, path)
            continue
        results[f"{role}_findings"] = []
        for finding in findings:
            key = ("baseline_conflicts" if finding.startswith("Frozen baseline conflict (")
                   else f"{role}_findings")
            results[key].append(finding)
        results["follow_ups"] = verdict["follow_ups"]
        commit_leftovers(target, n, k)
        if rev(target, "HEAD") != judged:
            passed, output = gate.judge(target, ready)
            if passed:
                sh(["git", "merge", "--ff-only", "--quiet", branch], folder)
                passed, output = gate.judge(folder, ready)
            if passed:
                commits = sh(["git", "log", "--oneline", f"{judged}..HEAD"], folder).stdout.strip()
                results["reviewer_note"] += " Reviewer fixes kept:\n" + (commits or "none")
            else:
                results["reviewer_note"] += (" Reviewer fixes were dropped because a submit check "
                                             "failed:\n" + output[-1200:])
    results["reviewer_note"] += f"\nDropped review findings: {results['dropped_findings']}"
    return results


def _run_contract_reproducer(root: Path, reviewer_folder: Path, judged: str,
                             ready: dict, test_file: Path,
                             item: str, n: int, k: int) -> dict:
    """Run one approved-item test in a prepared checkout of the judged commit."""
    source = (reviewer_folder / test_file).read_text(errors="replace")
    checks = [check for check in ready.get("checks", []) if check.get("type") == "tests"]
    command = checks[0].get("command", ready.get("command", "")) if checks else ready.get(
        "command", "")
    if not command:
        return {"reproduced": False, "source": source,
                "output": "No approved Exit test command is available."}
    target = root / ".loop" / "review-reproducers" / f"piece-{n}-{k}-{uuid.uuid4().hex[:8]}"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        sh(["git", "worktree", "add", "--quiet", "--detach", str(target), judged], root)
        before_prepare = untracked_paths(target)
        before_dirs = {child.name for child in target.iterdir() if child.is_dir()}
        prepared, prepare_output = prepare(target, ready.get("prepare", ""),
                                           ready.get("protected_paths", []))
        if not prepared:
            return {"reproduced": False, "preparation_failed": True, "source": source,
                    "output": prepare_output.strip()[-3000:]}
        record_prepare_outputs(target, before_prepare, before_dirs)
        destination = target / test_file
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(reviewer_folder / test_file, destination)
        approved_files = {path for check in checks for path in check.get("files", [])}
        adapted, adapt_error = _adapt_exit_command(command, approved_files, test_file.as_posix())
        if adapt_error:
            return {"reproduced": False, "source": source, "output": adapt_error}
        code, output = gate.run_judge(target, adapted,
                                      protected_paths=ready.get("protected_paths", []))
        reproduced = code != 0 and not judge_has_runner_error(output, code) \
            and judge_assertion_failed(output, item)
        return {"reproduced": reproduced, "source": source,
                "output": output.strip()[-3000:]}
    finally:
        _remove_untracked_reproducer(target, test_file)
        sh(["git", "worktree", "remove", str(target)], root, check=False)
        sh(["git", "worktree", "prune"], root, check=False)


def _adapt_exit_command(command: str, approved_files: set[str], test_file: str
                        ) -> tuple[str, str]:
    """Replace a frozen test target in its shell segment without moving the runner."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = []
        while True:
            cursor = lexer.instream.tell()
            token = lexer.get_token()
            after = lexer.instream.tell()
            if token == lexer.eof:
                break
            raw = command[cursor:after]
            leading = len(raw) - len(raw.lstrip())
            end = len(raw.rstrip())
            tokens.append((token, cursor + leading, cursor + end))
    except ValueError as error:
        return "", f"Could not adapt the approved Exit command: {error}"
    controls = {"if", "then", "else", "elif", "fi", "for", "while", "until",
                "do", "done", "case", "esac", "function"}
    operators = re.compile(r"^[;&|()<>]+$")
    segments = [[]]
    for entry in tokens:
        token = entry[0]
        if operators.fullmatch(token):
            segments.append([entry])
            segments.append([])
        else:
            segments[-1].append(entry)
    command_heads = [segment[0][0] for segment in segments if segment
                     and not operators.fullmatch(segment[0][0])]
    if controls.intersection(command_heads):
        return "", "Could not adapt a compound shell control command for the reproducer."
    target = next((segment for segment in segments
                   if any(token in approved_files for token, _, _ in segment)), None)
    if target is None:
        return "", "Could not locate a frozen test file in the approved Exit command."
    paths = [(start, end) for token, start, end in target if token in approved_files]
    edits = [(paths[0][0], paths[0][1], shlex.quote(test_file))]
    edits.extend((start, end, "") for start, end in paths[1:])
    adapted = command
    for start, end, replacement in sorted(edits, reverse=True):
        adapted = adapted[:start] + replacement + adapted[end:]
    return adapted, ""


def _remove_untracked_reproducer(folder: Path, path: Path) -> None:
    """Remove only the named test file and empty directories it created."""
    status = sh(["git", "status", "--porcelain", "--", path.as_posix()], folder).stdout
    candidate = folder / path
    if status.startswith("??") and candidate.is_file():
        candidate.unlink()
        parent = candidate.parent
        while parent != folder:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
