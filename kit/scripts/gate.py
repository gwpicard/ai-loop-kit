#!/usr/bin/env python3
"""The gate alone moves pieces, runs their checks and records the evidence."""
from __future__ import annotations
if __name__ == "__main__":
    import kit_python
    kit_python.require()

import fnmatch
import hashlib
import json
import re
import shutil
import sys
import tempfile
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import run_event as run_event  # isort: skip
from loopkit import (CAUSES, NEEDS_YOU, STATE_PREFIX, STATES, GitHub, Refused,  # noqa: E402
                     REASON_TYPES, SECRET_PATTERNS,
                     agent_options, bar_hash_at, base_branch, branch_name, changed_check_settings,
                     exit_bar,
                     bar_file_list, conflict_markers, last_record, main_ref,
                     keep_limit_seconds, loop_settings,
                     exit_attempt, exit_ready, parse_spec, prepare,
                     record_text, records, repo_root, rev,
                     run_judge, run_keep, sh, skipped_tests, spec_hash)
from doctor import doctor as doctor, quality_on_fresh_main
from extras import critics, require_extras
from gate_cli import build_parser as build_parser
import measure  # noqa: E402
import regression
from testlint import lint_files  # noqa: E402
from research import stale_findings  # noqa: E402
from risk_checks import path_covers, path_mentioned, unnamed_dependencies
from frozen import frozen_file_reason
import holds  # noqa: E402
from run_start import (capture_probe_files, release_worktree, remove_worktree,  # isort: skip
                       restore_probe_files)

# (from, to): the move's name. Anything else is refused.
MOVES = {
    ("new", "shaping"): "capture", ("shaping", "ready"): "ready",
    ("ready", "shaping"): "pull-back", ("ready", "building"): "claim",
    ("building", "shaping"): "give-back", ("building", "approval"): "submit",
    ("approval", "done"): "merged", ("approval", "shaping"): "reject",
    ("dropped", "shaping"): "reopen",
}
for _s in ("shaping", "ready", "building", "approval"):
    MOVES[(_s, "dropped")] = "drop"

NEEDS_REASON = {"pull-back", "give-back", "reject", "drop", "reopen"}
NEEDS_TYPE = {"pull-back", "give-back", "reject", "reopen"}

# The judge passes and the keep check fails only because of the judge files.
BAR_WRONG = "the bar is wrong: the keep check fails on the judge files themselves"

LABEL_COLOURS = {"shaping": "c5def5", "ready": "0e8a16", "building": "fbca04",
                 "approval": "5319e7", "done": "006b75", "dropped": "cccccc"}

def state_of(issue: dict) -> str:
    states = [lab[len(STATE_PREFIX):] for lab in issue["labels"] if lab.startswith(STATE_PREFIX)]
    if len(states) != 1:
        raise Refused(f"piece {issue['number']} has {len(states)} state labels: {states}",
                      "a person fixes the labels by hand, then runs the move again")
    if states[0] not in STATES:
        raise Refused(f"'{STATE_PREFIX}{states[0]}' is not a state")
    return states[0]


def _kind_attempt_judge(folder: Path, ready: dict) -> tuple[int, str]:
    if ready.get("kind") not in ("goal", "gauntlet"):
        return -1, ""
    adapter = measure if ready["kind"] == "goal" else critics()
    return adapter.judge_attempt(folder, ready)


def check_times(output: str) -> list[float]:
    return [float(value) for value in re.findall(
        r"Keep took: (\d+(?:\.\d+)?) seconds", output)]


def check_ready(gh: GitHub, root: Path, issue: dict) -> dict:
    """The ready gate. Returns the record to write. Refuses on any gap."""
    n = issue["number"]
    spec = parse_spec(issue["body"] or "")
    holds.check(gh, n, spec.risks.get("depends_on", ()))
    settings = loop_settings(root)
    require_extras(settings, {"checks": spec.checks, "keep": spec.keep})
    branch = branch_name(n)
    head = rev(root, branch)
    if head is None:
        raise Refused(f"there is no branch {branch}",
                      f"create {branch} from main and commit the judge files on it")
    bar_files = bar_file_list(root, head, spec.files)
    bar = bar_hash_at(root, head, spec.files, bar_files) if spec.files else ""
    main = main_ref(root)
    main_sha = rev(root, main)
    keep_limit = keep_limit_seconds(settings)
    keep_command = spec.keep or settings.get("keep", "")
    regression_command = settings.get("test", "")
    if spec.kind == "scaffold" and not regression_command:
        regression_command = spec.command
    if not regression_command:
        raise Refused("AGENTS.md has no Test command for the required regression check",
                      "set the Test command in AGENTS.md, then run ready again")
    regression_main = {"reason": "scaffold: no test runner on main"}
    keep_output = ""
    shared_conflicts = []
    wanted_shared = set(spec.risks.get("shared_files", ()))
    if wanted_shared:
        for other in gh.issues_with_label(STATE_PREFIX + "ready"):
            if other["number"] == n:
                continue
            previous = last_record(gh.comments(other["number"]), "ready") or {}
            other_shared = previous.get("risks", {}).get("shared_files", [])
            overlaps = sorted(wanted_shared & set(other_shared))
            if overlaps:
                shared_conflicts.append({"issue": other["number"], "files": overlaps})
    # Run the judge on today's main, with only the judge files added.
    tmp = Path(tempfile.mkdtemp(prefix=f"loop-ready-{n}-"))
    folder = tmp / "main"
    before_injection = injected = {}
    try:
        sh(["git", "worktree", "add", "--detach", "--quiet", str(folder), main], root)
        ok, poutput = (True, "") if spec.kind == "scaffold" else prepare(folder)
        if not ok:
            raise Refused("the Prepare command fails on a fresh copy of main:\n"
                          f"{poutput.strip()[-1500:]}",
                          "fix the Prepare command in AGENTS.md, then run gate.py doctor")
        if spec.kind != "scaffold":
            regression_main, keep_output = regression.check(folder, regression_command, keep_limit)
            if regression_main["reason"]:
                raise Refused(f"the regression check on main {regression_main['reason']}:\n"
                              f"{keep_output.strip()[-1500:]}\nCommand: {regression_command}",
                              "fix main or the Test command and environment, then run ready again")
        if keep_command and keep_command != regression_command:
            kcode, koutput = run_keep(folder, keep_command, timeout=keep_limit)
            keep_output += "\n" + koutput
            if kcode != 0:
                raise Refused(f"the keep check already fails on main:\n{koutput.strip()[-1500:]}",
                              "fix main first, or correct the Keep: command")
        if bar_files:
            try:
                before_injection = capture_probe_files(folder, bar_files)
                sh(["git", "checkout", head, "--", *bar_files], folder)
                injected = capture_probe_files(folder, bar_files)
            except OSError as error:
                raise Refused(f"cannot read judge file {error.filename or bar_files[0]}",
                              "make the judge file readable, then run ready again") from None
        lint, test_lint_unchecked = lint_files(
            [folder / f for f in spec.files], folder, " ".join(spec.done_when.values()))
        if lint:
            raise Refused("the judge has quality problems:\n" + "\n".join(lint),
                          "fix the judge files, then run gate.py check again")
        check_records, output = exit_ready(folder, spec.checks, spec.done_when, spec.stays)
        kind_record = {"checks": check_records}
        if spec.kind in ("goal", "gauntlet"):
            kind_record.update(check_records[0])
    finally:
        if injected:
            restore_probe_files(folder, before_injection, injected)
        remove_worktree(root, folder)
        with suppress(OSError):
            tmp.rmdir()

    if spec.stays:
        judge_text = "".join(sh(["git", "show", f"{head}:{f}"], root).stdout for f in spec.files)
        untested = [i for i in spec.stays
                    if not re.search(rf"(?<![A-Za-z0-9]){i}(?![0-9])", judge_text)]
        if untested:
            raise Refused(f"no judge test names {', '.join(untested)}",
                          "give every (stays) item a test with its ID in the name")
    agent = settings.get("agent", "claude")
    if agent not in {"claude", "codex"}:
        raise Refused(f"Agent must be claude or codex, not {agent!r}",
                      "set `Agent: claude` or `Agent: codex` in the loop section of AGENTS.md")
    model, effort = agent_options(settings.get("agent model", ""), settings.get("agent effort", ""))
    return {"move": "ready", "bar": bar, "bar_files": bar_files,
            "contract": spec.done_when, "keep": keep_command,
            **{key: getattr(spec, key) for key in
               ("intent", "approach", "playbook", "files", "command", "kind", "settings")},
            "regression": regression_command, "regression_limit": keep_limit,
            "regression_main": regression_main, "keep_limit": settings.get("keep limit", "15"),
            "check_seconds": check_times(keep_output + "\n" + output), **kind_record,
            **{key: settings.get(key, "") for key in ("test", "prepare", "standards")},
            "quality": settings.get("quality", []),
            "idle_limit": settings.get("idle limit", "10"),
            "waiting_limit": settings.get("waiting limit", "3"),
            "agent": agent, **({"agent_model": model} if model else {}),
            **({"agent_effort": effort} if effort else {}), "stays": list(spec.stays), "research": list(spec.research),
            "risks": {key: list(value) for key, value in spec.risks.items()},
            "shared_conflicts": shared_conflicts,
            "test_lint_unchecked": test_lint_unchecked,
            "protected_paths": settings.get("protected paths", []),
            "large_files": list(spec.large_files), "commit": head, "main": main_sha,
            "exit_bar": bar_hash_at(root, head, spec.files, spec.files) if spec.files else "",
            "base": base_branch(root),
            "spec": spec_hash(issue["body"] or "")}


def check_frozen(issue: dict, comments: list[str]) -> dict:
    ready = last_record(comments, "ready")
    if ready is None:
        raise Refused(f"piece {issue['number']} has no ready record",
                      "move it back to shaping and through the ready gate")
    if ready["spec"] != spec_hash(issue["body"] or ""):
        raise Refused("the spec changed after the piece became ready",
                      "pull the piece back to shaping and take it through ready again")
    return ready


def check_claim_bar(root: Path, n: int, ready: dict) -> None:
    regression.require_record(ready)
    head = rev(root, branch_name(n))
    if head is None or (ready["files"] and
                        bar_hash_at(root, head, ready["files"], ready["files"])
                        != exit_bar(root, ready)):
        raise Refused("the judge bar changed after the piece became ready",
                      "move the piece back to shaping and run the ready gate again")
    if ready.get("base", "main") != base_branch(root):
        raise Refused("the base branch changed after the piece became ready",
                      "move the piece back to shaping and run the ready gate again")


def claim_stale_research(ready: dict) -> list[str]:
    return stale_findings(ready.get("research", []))


def judge(folder: Path, ready: dict) -> tuple[bool, str]:
    """Run the frozen judge in a build folder. The bar must be unchanged."""
    frozen = frozen_file_reason(folder, ready)
    if frozen:
        return False, frozen
    changed_tests = changed_existing_tests(folder, ready)
    if changed_tests:
        return False, ("the build changes existing test files not named in the Contract or Files: "
                       + ", ".join(changed_tests))
    main = main_ref(folder)
    changed_paths = sh(["git", "diff", "--no-renames", "--name-only", "-z",
                        f"{main}...HEAD"], folder).stdout.split("\0")[:-1]
    staged_paths = sh(["git", "diff", "--cached", "--no-renames", "--name-only", "-z"],
                      folder).stdout.split("\0")[:-1]
    leaked = sorted(path for path in set(changed_paths + staged_paths) if generated(path))
    if leaked:
        return False, "the build includes generated files: " + ", ".join(leaked)
    contract_text = " ".join(ready.get("contract", {}).values()) + " " + \
        " ".join(ready.get("files", []))
    risk_paths = ready.get("risks", {}).get("protected_paths", [])
    protected = [p for p in changed_paths for target in ready.get("protected_paths", [])
                 if (p == target.rstrip("/") or p.startswith(target.rstrip("/") + "/"))
                 and not path_mentioned(contract_text, target)
                 and not any(path_covers(risk, p) for risk in risk_paths)]
    if protected:
        return False, "the build changes protected paths not named in the Contract: " + \
            ", ".join(sorted(set(protected)))
    unnamed = unnamed_dependencies(folder, main, ready.get("risks", {}).get("new_dependencies", []))
    if unnamed:
        return False, "the build adds unnamed dependencies: " + ", ".join(unnamed)
    oversized = []
    for path in changed_paths:
        target = folder / path
        if path in ready.get("large_files", []) or not target.is_file():
            continue
        before = sh(["git", "show", f"{main}:{path}"], folder, check=False).stdout
        before_lines = len(before.splitlines())
        after_lines = len(target.read_text(errors="replace").splitlines())
        if before_lines < 1000 <= after_lines:
            oversized.append(path)
    if oversized:
        return False, ("the build takes a file from under 1,000 lines to 1,000 or more: "
                       + ", ".join(oversized) + ". Add 'Large file: <path>' to the Judge section.")
    secret_files = [p for p in changed_paths if Path(p).name == ".env" or
                    Path(p).name.startswith(".env.") and Path(p).name not in
                    {".env.example", ".env.sample", ".env.template"}]
    diff_text = sh(["git", "diff", "--no-ext-diff", f"{main}...HEAD"], folder).stdout
    if secret_files or any(re.search(pattern, diff_text) for pattern in SECRET_PATTERNS):
        return False, "the diff contains a secret-shaped value or .env file"
    markers = conflict_markers(folder)
    if markers:
        return False, f"merge conflict markers are left in: {', '.join(markers)}"
    git_dir = Path(sh(["git", "rev-parse", "--absolute-git-dir"], folder).stdout.strip())
    prepare_paths = git_dir / "info" / "ai-loop-kit-prepare-paths"
    if prepare_paths.is_file():
        roots = prepare_paths.read_text().splitlines()
        if roots:
            added = sh(["git", "diff", "--no-renames", "--name-only", "--diff-filter=A",
                        f"{ready['commit']}..HEAD"], folder).stdout.splitlines()
            leaked = [path for path in added if any(
                path == root.rstrip("/") or path.startswith(root.rstrip("/") + "/")
                for root in roots)]
            if leaked:
                return False, ("the piece adds files under paths Prepare created: "
                               + ", ".join(leaked))
    if not ready.get("settings"):
        changed = changed_check_settings(folder, (ready.get("standards", ""),)
                                        if ready.get("standards") else ())
        if changed:
            if "AGENTS.md" in changed:
                return False, "the loop settings changed in AGENTS.md"
            return False, ("the build changes the project's check settings: "
                           f"{', '.join(changed)}. Put them back. A piece may change them only "
                           "when its spec says 'Settings: may change'.")
    protected_paths = ready.get("protected_paths", [])
    if ready.get("checks"):
        kind_code, kind_output = exit_attempt(folder, ready.get("checks", []),
                                              protected_paths=protected_paths)
    else:
        kind_code, kind_output = _kind_attempt_judge(folder, ready)
    if kind_code >= 0:
        code, output = kind_code, kind_output
    else:
        code, output = run_judge(folder, ready["command"], protected_paths=protected_paths)
    if kind_code < 0 and skipped_tests(output):
        return False, f"the judge reported skipped tests:\n{output.strip()[-1500:]}"
    if code != 0:
        return False, output
    regression.require_record(ready)
    regression_result, regression_output = regression.check(
        folder, ready["regression"], ready["regression_limit"], protected_paths)
    if regression_result["reason"]:
        return False, regression_output
    output += "\n\n" + regression_output
    if ready.get("keep") and ready["keep"] != ready["regression"]:
        keep_timeout = keep_limit_seconds({"keep limit": ready.get("keep_limit", "15")})
        kcode, koutput = run_keep(folder, ready["keep"], timeout=keep_timeout,
                                  protected_paths=protected_paths)
        if skipped_tests(koutput):
            return False, f"the keep check reported skipped tests:\n{koutput.strip()[-1500:]}"
        if kcode != 0:
            retry_code, retry_output = run_keep(
                folder, ready["keep"], timeout=keep_timeout,
                protected_paths=protected_paths)
            if retry_code == 0 and not skipped_tests(retry_output):
                failed_names = failing_test_names(koutput)
                names = ", ".join(failed_names) if failed_names else "see failed Keep output"
                output += (f"\n\nKeep: {ready['keep']}\nExit: {kcode}\n{koutput.strip()}"
                           f"\n\nKeep retry: {ready['keep']}\nExit: {retry_code}\n"
                           f"{retry_output.strip()}\nCause: keep-flaky\n"
                           f"Failing Keep tests: {names}")
            else:
                bar_wrong, probe_output = keep_passes_without_judge(
                    folder, ready, (koutput, retry_output))
                if bar_wrong:
                    return False, (f"{BAR_WRONG}. Keep retry also failed:\n"
                                   f"{retry_output}\nWithout judge files it passes:\n"
                                   f"{probe_output}")
                failure = f"the judge passes, but the keep check now fails:\n{koutput}"
                if kind_code >= 0:
                    failure += f"\n\n{output}"
                return False, failure
        else:
            output += f"\n\nKeep: {ready['keep']}\nExit: {kcode}\n{koutput.strip()}"
    quality_results = []
    for command in ready.get("quality", []):
        qcode, qoutput = run_judge(folder, command, protected_paths=protected_paths)
        quality_results.append(f"Quality: {command}\nExit: {qcode}\n{qoutput.strip()}")
        if qcode != 0:
            failure = "a Quality command failed:\n" + "\n\n".join(quality_results)
            if kind_code >= 0:
                failure += f"\n\n{output}"
            return False, failure
    if quality_results:
        output += "\n\n" + "\n\n".join(quality_results)
    return True, output


def failing_test_names(output: str) -> list[str]:
    """Extract reported failing test names from common test runner output."""
    names = []
    for line in output.splitlines():
        if re.match(r"\s*FAILED\s*\(", line):
            continue  # unittest's summary is not a test name.
        match = re.search(r"^\s*(?:FAIL(?:ED)?|ERROR)\b\s*:?\s*(.+)$|\bnot ok\s+\d+\s+-\s*(.+)$",
                          line, re.IGNORECASE)
        if match:
            name = (match.group(1) or match.group(2)).strip()
            if name and name not in names:
                names.append(name)
    return names


def changed_existing_tests(folder: Path, ready: dict) -> list[str]:
    """Find edits to existing tests, fixtures or conftest files outside scope."""
    base = sh(["git", "merge-base", "HEAD", main_ref(folder)], folder).stdout.strip()
    changed = sh(["git", "diff", "--no-renames", "--name-only", base], folder).stdout.splitlines()
    contract_text = "\n".join(str(v) for v in ready.get("contract", {}).values())
    allowed = list(ready.get("files", []))
    return sorted(name for name in changed if _is_test_support(name) and
                  _exists_at(folder, base, name) and
                  not any(name == p or name.startswith(p.rstrip("/") + "/") for p in allowed) and
                  name not in contract_text)


def _exists_at(folder: Path, ref: str, name: str) -> bool:
    return sh(["git", "cat-file", "-e", f"{ref}:{name}"], folder, check=False).returncode == 0


def _is_test_support(name: str) -> bool:
    path = Path(name)
    parts = {p.lower() for p in path.parts}
    base = path.name.lower()
    return (base == "conftest.py" or "fixture" in base or "fixtures" in parts or
            "test" in parts or "tests" in parts or "__tests__" in parts or
            base.startswith("test_") or base.endswith("_test.py") or
            ".test." in base or ".spec." in base)


def keep_passes_without_judge(folder: Path, ready: dict,
                              failures: tuple[str, str]) -> tuple[bool, str]:
    traceback = (r"^Traceback \(most recent call last\):\n"
                 r"(?:[ \t]+[^\n]*\n|\n)+\w+(?:\.\w+)*(?::[^\n]*)?$")
    for name in ready["files"]:
        path = rf"(?:{re.escape(str(folder))}/)?{re.escape(name)}"
        diagnostic = (rf'^[ \t]*{path}:(?:\d+:)*[ \t]*'
                      rf'(?:(?i:error|fatal)\b|[EF]\d{{3,4}}\b)')
        frame = rf'^[ \t]+File "{path}", line \d+'
        if all(re.search(diagnostic, output, re.MULTILINE) or
               any(re.search(frame, block, re.MULTILINE)
                   for block in re.findall(traceback, output, re.MULTILINE))
               for output in failures):
            break
    else:
        return False, ""
    aside = Path(tempfile.mkdtemp(prefix="loop-aside-"))
    moved = []
    try:
        for i, f in enumerate(ready["files"]):
            if (folder / f).is_file():
                shutil.move(str(folder / f), str(aside / str(i)))
                moved.append((aside / str(i), folder / f))
        code, output = run_keep(folder, ready["keep"],
                           timeout=keep_limit_seconds(
                               {"keep limit": ready.get("keep_limit", "15")}),
                           protected_paths=ready.get("protected_paths", []))
        return code == 0 and not skipped_tests(output), output
    finally:
        for held, home in moved:
            shutil.move(str(held), str(home))
        shutil.rmtree(aside, ignore_errors=True)


def quality_fails_on_main(folder: Path, command: str, test_command: str = "",
                          protected_paths: Optional[list[str]] = None) -> bool:
    root = repo_root(folder)
    main = main_ref(folder)
    ok, _ = quality_on_fresh_main(root, main, command, test_command, protected_paths)
    return not ok


def quality_probe_path(root: Path, piece: int, command: str, main_commit: str) -> Path:
    key = hashlib.sha256((command + "\0" + main_commit).encode()).hexdigest()[:16]
    return root / ".loop" / f"main-quality-{piece}-{key}.json"


def _cause(name: str, reason: str, reason_type: str) -> str:
    text = reason.lower()
    choices = [
        (name == "reject" and "pull request creation failed" in text, "pull-request-failed"),
        (name == "reject", "person-rejected"), (name == "pull-back", "person-request"),
        ("prepare" in text, "prepare-failed"),
        ("rate limit" in text or "usage limit" in text, "usage-limit"),
        ("already satisfied" in text, "already-satisfied"),
        ("idle" in text, "idle"), ("stale" in text or "main changed" in text, "stale-after-main"),
        (any(word in text for word in ("importerror", "modulenotfounderror", "no module named",
                                      "module not found", "import error")), "import-error"),
        ("flaky" in text, "keep-flaky"),
        ("conflict" in text or "does not merge" in text, "conflict"),
        ("judge gap" in text, "judge-gap"),
        (reason_type == "stopped" or "person asked the run to stop" in text, "stopped"),
        ("bar" in text or reason_type == "bar-wrong", "bar-wrong"),
        ("quality" in text, "quality-failed"), ("judge" in text, "judge-failed"),
        ("dirty" in text or "uncommitted" in text, "dirty-worktree"),
        (reason_type == "builder-failed", "builder-failed"),
    ]
    return next((cause for matches, cause in choices if matches and cause in CAUSES), "other")


def _kit_version() -> str:
    manifest = Path(__file__).resolve().parents[1] / ".claude-plugin" / "plugin.json"
    try:
        return str(json.loads(manifest.read_text()).get("version") or "unknown")
    except (OSError, ValueError, AttributeError):
        return "unknown"


def move(gh: GitHub, root: Path, n: int, to: str, reason: str = "",
         reason_type: str = "", folder: Optional[Path] = None, pr: str = "",
         cause: str = "", attempts: Optional[int] = None,
         seconds: Optional[float] = None, evidence: dict | None = None) -> str:
    issue = gh.issue(n)
    frm = state_of(issue)
    name = MOVES.get((frm, to))
    if name is None:
        allowed = sorted(t for (f, t) in MOVES if f == frm)
        raise Refused(f"there is no move from {frm} to {to}",
                      f"from {frm} a piece can go to: {', '.join(allowed)}")
    if name in NEEDS_REASON and not reason:
        raise Refused(f"the {name} move needs a reason", "pass --reason")
    if name in NEEDS_TYPE and reason_type not in REASON_TYPES:
        raise Refused(f"the {name} move needs a typed reason", "pass --type and --reason")
    record: dict = {"move": name, "from": frm, "to": to}
    note = f"{frm} → {to} ({name})."
    comments = gh.comments(n)
    if name == "ready":
        record = {**check_ready(gh, root, issue), "from": frm, "to": to}
        for check in record["checks"]:
            if check.get("legacy_kind") == "scaffold":
                note += " Scaffold piece: the fails-on-main check does not apply."
            elif check["type"] == "tests":
                note += " The judge fails on main as it should, naming every spec ID to build."
                if record["stays"]:
                    note += f" {', '.join(record['stays'])} already hold on main, as marked."
            elif check["type"] == "measure":
                note += (f" Measure on main: median {check['main_median']} "
                         f"misses target {check['target']}.")
            elif check["type"] == "critics":
                wins = sum(v["winner"] == "ours" for v in check["main_verdicts"])
                note += f" Critics on main: {wins}/3 wins; fewer than the required 2."
        note += (f" {', '.join(item['file'] for item in record['test_lint_unchecked'])} "
                 "not checked by the test lint." if record["test_lint_unchecked"] else "")
        if record["keep"]:
            note += f" The keep check `{record['keep']}` passes on main."
        note += f" Bar `{record['bar'][:12] or 'none'}` is fixed."
        for conflict in record.get("shared_conflicts", []):
            note += (f" Warning: shared files {', '.join(conflict['files'])} also appear in "
                     f"ready piece {conflict['issue']}.")
    elif name == "claim":
        ready = check_frozen(issue, comments)
        require_extras(ready, loop_settings(root))
        check_claim_bar(root, n, ready)
        stale = claim_stale_research(ready)
        if stale:
            record["stale_research"] = stale
            note += f" Research findings {', '.join(stale)} are possibly stale; check them before building."
    elif name == "submit":
        ready = check_frozen(issue, comments)
        if folder is None:
            raise Refused("submit needs the build folder",
                          "the run makes this move, not a person")
        passed, output = judge(folder, ready)
        logs = root / ".loop" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        label = f"attempt-{attempts}" if attempts is not None else "submit"
        with (logs / f"piece-{n}-{label}.log").open("a") as out:
            out.write("\nSubmit judge output:\n" + output + "\n")
        if not passed:
            raise Refused(f"the judge does not pass:\n{output.strip()[-1500:]}")
        if pr:
            record["pr"] = pr
        record["check_seconds"] = check_times(output)
        record["commit"] = rev(folder, "HEAD")
        record["regression"] = {"command": ready["regression"], "exit": 0,
                                "commit": record["commit"]}
        if evidence is not None:
            evidence["output"] = output
        record["attempts"] = max(0, int(attempts or 0))
        record["seconds"] = round(max(0.0, float(seconds or 0)), 3)
        note += f" The gate ran the judge and it passed. Pull request: {pr}"
    elif name == "merged":
        found = gh.pr_for_branch(branch_name(n))
        if not found or found["state"] != "MERGED":
            raise Refused(f"the pull request for {branch_name(n)} is not merged",
                          "the person merges it on GitHub")
    if reason:
        record["reason"] = reason
        note += f" Reason: {reason}"
    if reason_type:
        record["type"] = reason_type
    if name in ("give-back", "reject", "pull-back"):
        previous_submit = last_record(comments, "submit") or {}
        attempt_count = attempts if attempts is not None else previous_submit.get("attempts", 0)
        elapsed = seconds if seconds is not None else previous_submit.get("seconds", 0)
        record.update({
            "cause": cause if cause in CAUSES else _cause(name, reason, reason_type),
            "attempts": max(0, int(attempt_count)),
            "seconds": round(max(0.0, float(elapsed)), 3),
            "kit": _kit_version(),
            "date": datetime.now(timezone.utc).date().isoformat(),
        })
    add = [STATE_PREFIX + to]
    remove = [STATE_PREFIX + frm]
    if name in ("give-back", "reject"):
        add.append(NEEDS_YOU)
    elif NEEDS_YOU in issue["labels"] and to in ("ready", "dropped", "done"):
        remove.append(NEEDS_YOU)
    gh.comment(n, record_text(record, note))
    gh.set_labels(n, add, remove)
    run_event(root, name, n, to, int(attempts or record.get("attempts", 0)),
              reason_type if reason_type in REASON_TYPES else name)
    if issue.get("state", "OPEN") == "OPEN":
        if to == "done":
            gh.close(n, "completed")
        elif to == "dropped":
            gh.close(n, "not planned")
    if to in ("shaping", "approval", "done", "dropped"):
        release_worktree(root, n)
    return note


def capture(gh: GitHub, title: str, body: str, root: Path | None = None) -> int:
    n = gh.create_issue(title, body, [STATE_PREFIX + "shaping"])
    gh.comment(n, record_text({"move": "capture", "from": "new", "to": "shaping"},
                              "new → shaping (capture)."))
    if root is not None:
        run_event(root, "capture", n, "shaping", reason="capture")
    return n


def sync(gh: GitHub, root: Path) -> list[str]:
    notes = []
    # Closing words may close the issue before sync sees the merged pull request.
    for item in gh.issues_with_label(STATE_PREFIX + "approval", closed_too=True):
        found = gh.pr_for_branch(branch_name(item["number"]))
        if found and found["state"] == "MERGED":
            notes.append(f"{item['number']}: " + move(gh, root, item["number"], "done"))
    return notes


def init(gh: GitHub, root: Path) -> None:
    for s in STATES:
        gh.ensure_label(STATE_PREFIX + s, LABEL_COLOURS[s], f"Loop state: {s}. Only the gate sets it.")
    gh.ensure_label(NEEDS_YOU, "d93f0b", "The piece waits for the person.")
    ignore_loop_folder(root)


# Files that tools make while tests run. A run must never commit them.
GENERATED = ["/.loop/", "__pycache__/", "*.pyc", ".pytest_cache/", ".mypy_cache/",
             ".ruff_cache/", "node_modules/", ".DS_Store", "*.egg-info/", ".coverage",
             ".coverage.*", "mutants/", ".stryker-tmp/", "coverage.json", "coverage.xml",
             "coverage.lcov"]


def generated(path: str) -> bool:
    parts = path.split("/")
    for pattern in GENERATED:
        p = pattern.strip("/")
        if pattern.endswith("/"):
            dirs = parts[:1] if pattern.startswith("/") else parts[:-1]
            if any(fnmatch.fnmatch(d, p) for d in dirs):
                return True
        elif any(fnmatch.fnmatch(part, p) for part in parts):
            return True
    return False


def ignore_loop_folder(root: Path) -> None:
    common = Path(sh(["git", "rev-parse", "--git-common-dir"], root).stdout.strip())
    exclude = (common if common.is_absolute() else root / common) / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    text = exclude.read_text() if exclude.exists() else ""
    have = text.splitlines()
    missing = [g for g in GENERATED if g not in have]
    if missing:
        exclude.write_text(text + ("" if text.endswith("\n") or not text else "\n")
                           + "\n".join(missing) + "\n")


def status(gh: GitHub, root: Optional[Path] = None) -> str:
    issues = gh.issues_with_label()
    lines = [f"{s}: " + (", ".join(
        f"{i['number']}{' (needs you)' if NEEDS_YOU in i['labels'] else ''} {i['title']}"
        for i in issues if STATE_PREFIX + s in i["labels"]) or "none") for s in STATES[:4]]
    if root is not None:
        import walkaway
        heartbeat = walkaway.heartbeat_status(root)
        if heartbeat:
            lines.append(heartbeat)
    return "\n".join(lines)


def report(gh: GitHub) -> str:
    """Count hand-backs by type and cause, and report first-attempt outcomes."""
    counts: dict[str, int] = {}
    cause_counts: dict[str, int] = {}
    pieces: dict[int, list[str]] = {}
    seen: set[int] = set()
    started, first_pass = set(), set()
    for state in STATES:
        for issue in gh.issues_with_label(STATE_PREFIX + state, closed_too=True):
            n = issue["number"]
            if n in seen:
                continue
            seen.add(n)
            issue_records = records(gh.comments(n))
            claimed = False
            first_build_outcome = False
            for record in issue_records:
                if record.get("move") == "claim":
                    started.add(n)
                    claimed = True
                elif claimed and not first_build_outcome and record.get("move") in (
                        "give-back", "submit"):
                    first_build_outcome = True
                    if record.get("move") == "submit" and record.get("attempts") == 1:
                        first_pass.add(n)
                kind = record.get("type")
                if (record.get("move") not in NEEDS_TYPE and record.get("move") != "judge-gap") or \
                        kind not in REASON_TYPES:
                    continue
                key = f"{kind}: {record.get('reason', '')}"
                counts[kind] = counts.get(kind, 0) + 1
                cause_key = f"{kind} / {record.get('cause', 'other')}"
                cause_counts[cause_key] = cause_counts.get(cause_key, 0) + 1
                pieces.setdefault(n, []).append(key)
    lines = [f"{kind}: {counts.get(kind, 0)}" for kind in REASON_TYPES]
    lines.append("by type and cause:")
    lines += [f"{key}: {value}" for key, value in sorted(cause_counts.items())]
    denominator = len(started)
    percentage = round(len(first_pass) * 100 / denominator) if denominator else 0
    lines.append(f"pieces started: {denominator}")
    lines.append(f"passed on the first attempt: {len(first_pass)} / {denominator} ({percentage}%)")
    lines.append("by piece:")
    lines += [f"{n}: " + "; ".join(items) for n, items in sorted(pieces.items())]
    if not pieces:
        lines.append("none")
    return "\n".join(lines)


def replace_spec(gh: GitHub, n: int, body: str) -> None:
    issue = gh.issue(n)
    if state_of(issue) != "shaping":
        raise Refused("the spec can only change while a piece is shaping",
                      "move the piece back to shaping, then edit its spec")
    parse_spec(body)
    gh.edit_body(n, body)


def request_stop(root: Path) -> str:
    loop = root / ".loop"
    if not (loop / "run.lock").is_file():
        raise Refused("there is no run to stop", "start run.py first")
    loop.mkdir(parents=True, exist_ok=True)
    (loop / "stop").write_text("stop after the current attempt\n")
    return "the run will stop after the current attempt"


def main(argv: Optional[list[str]] = None) -> int:
    from gate_cli import main as cli_main
    return cli_main(argv, api=sys.modules[__name__])


if __name__ == "__main__":
    sys.exit(main())
