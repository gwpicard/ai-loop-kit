"""Setup diagnostics for a project's loop settings and environment."""
from __future__ import annotations

import os
import re
import shlex
import sys
import tempfile
from contextlib import suppress
from pathlib import Path

from loopkit import (
    STATE_PREFIX,
    STATES,
    GitHub,
    Refused,
    clean_quality_outputs,
    keep_limit_seconds,
    loop_settings,
    main_ref,
    prepare,
    record_quality_outputs,
    run_judge,
    run_keep,
    sh,
)
from run_start import (
    capture_probe_files,
    remove_worktree,
    restore_probe_files,
    worktree_reason,
    worktrees,
)

from extras import require_extras

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "quality"))
from proposed_quality import apply as apply_proposed_quality


TEST_PATH = re.compile(r"(^|/)(tests?|spec|__tests__)/|(^|/)test_[^/]*$|"
                       r"_test\.[^/]+$|\.(test|spec)\.[^/]+$")


def print_checks(checks: list[tuple[bool, str, str]]) -> bool:
    for ok, what, fix in checks:
        mark = ("warn" if what.startswith("warning:") else "unknown"
                if what == "main branch protection: unknown" else "ok  " if ok else "FAIL")
        print(f"{mark} {what}" + (f"\n     next: {fix}" if fix else ""))
    return all(ok for ok, _, _ in checks)


def quality_on_fresh_main(root: Path, main: str, command: str, test_command: str = "",
                          protected_paths: list[str] | None = None,
                          prepare_command: str | None = None,
                          proposed_quality: str = "") -> tuple[bool, str]:
    """Run Test, then one Quality command in its own prepared copy of main."""
    tmp = Path(tempfile.mkdtemp(prefix="loop-doctor-quality-"))
    folder = tmp / "main"
    before_injection = injected = {}
    try:
        sh(["git", "worktree", "add", "--detach", "--quiet", str(folder), main], root)
        if proposed_quality:
            before_injection = capture_probe_files(folder, ["AGENTS.md"])
            apply_proposed_quality(folder / "AGENTS.md", proposed_quality,
                                   prepare_command, test_command)
            injected = capture_probe_files(folder, ["AGENTS.md"])
            settings = loop_settings(folder)
            command = settings.get("quality", [command])[-1]
            test_command = settings.get("test", "")
        ok, output = prepare(folder, command=prepare_command,
                             protected_paths=protected_paths)
        if not ok:
            return False, "Prepare failed:\n" + output.strip()[-800:]
        if test_command:
            code, test_output = run_judge(folder, test_command,
                                          protected_paths=protected_paths)
            if code:
                return False, "Test command failed before Quality:\n" + test_output.strip()[-800:]
        code, output = run_judge(folder, command, protected_paths=protected_paths)
        clean_quality_outputs(folder, record_quality_outputs(folder))
        return code == 0, output
    finally:
        if injected:
            restore_probe_files(folder, before_injection, injected)
        remove_worktree(root, folder)
        with suppress(OSError):
            tmp.rmdir()


def doctor(gh: GitHub, root: Path, extra_quality: list[str] | None = None,
           proposed_prepare: str | None = None, proposed_test: str | None = None,
           walk_away: bool = False, agent: str | None = None) -> list[tuple[bool, str, str]]:
    """Setup's checks, in code. Each is (passed, what, next step)."""
    checks: list[tuple[bool, str, str]] = []

    def add(ok: bool, what: str, fix: str) -> bool:
        checks.append((ok, what, "" if ok else fix))
        return ok

    def command_result(code: int, output: str, command: str, name: str) -> None:
        duration = next((line.removeprefix("Keep took: ") for line in output.splitlines()
                         if line.startswith("Keep took: ")), "")
        words = []
        with suppress(ValueError):
            words = shlex.split(command) if code == 5 else []
        runner = Path(words[0]).name if words else ""
        pytest = runner in {"pytest", "py.test"} or (
            runner.rstrip("0123456789.") == "python" and words[1:3] == ["-m", "pytest"])
        pytest = pytest and not any(char in command for char in ";&|<>()\n")
        empty = code == 5 and (pytest or "no tests ran" in output.lower()
                               or "collected 0 items" in output)
        fix = ("add tests or fix the test collection settings:\n" if empty else
               "increase Keep limit in AGENTS.md or make the Keep command finish sooner:\n"
               if code == 124 else "fix the command or environment, or add a Prepare command:\n")
        name = "no tests were collected" if empty else name
        if empty and not any(TEST_PATH.search(path.lower()) for path in sh(
                ["git", "ls-files"], folder).stdout.splitlines()):
            checks.append((True, f"warning: the project has no tests yet ({command})",
                           "shape a scaffold piece first; it adds the first tests"))
            return
        add(code == 0, f"{name} on a fresh copy of main ({command})"
            + (f" ({duration})" if duration else ""), fix + output.strip()[-800:])

    origin = sh(["git", "remote", "get-url", "origin"], root, check=False).stdout.strip()
    if not add(bool(origin), "the project has an origin",
               "run setup; it runs gate.py bootstrap"):
        return checks
    try:
        if not add(gh.signed_in(), "gh is signed in", "run: gh auth login"):
            return checks
    except RuntimeError as error:
        add(False, str(error), "run: gh auth login")
        return checks
    try:
        main = main_ref(root)
        add(main == "origin/main", "main has a commit on origin",
            "run setup; it runs gate.py bootstrap")
    except Refused as r:
        add(False, "main has a commit on origin", r.next_step)
        return checks
    protection = gh.main_protection() if hasattr(gh, "main_protection") else "unknown"
    checks.append((True, f"main branch protection: {protection}", ""))
    have = set(gh.labels())
    add(all(STATE_PREFIX + s in have for s in STATES), "the state labels exist",
        "run: gate.py init")

    old_worktrees = root / ".loop" / "worktrees"
    leftovers = {Path(entry["worktree"]) for entry in worktrees(root)[1:]}
    if old_worktrees.is_dir():
        leftovers.update(old_worktrees.iterdir())
    for leftover in sorted(leftovers):
        if leftover.resolve() == root.resolve():
            continue
        try:
            size = sum((Path(home) / name).lstat().st_size
                       for home, _, files in os.walk(leftover) for name in files)
            reason = worktree_reason(root, leftover)
            verdict = f"no ({reason})" if reason else "yes"
            detail = f"{size} bytes; safe to remove: {verdict}"
        except OSError as error:
            detail = f"size unavailable; safe to remove: no ({error})"
        kind = ("old in-project worktrees" if leftover.parent == old_worktrees
                else "leftover worktree")
        checks.append((True, f"warning: {kind}: {leftover} ({detail})",
                       f"The person may remove this folder only after checking it: {leftover}."))

    try:
        require_extras(loop_settings(root), {"quality": extra_quality or [],
                                            "prepare": proposed_prepare or "",
                                            "test": proposed_test or ""})
    except Refused as error:
        add(False, error.reason, error.next_step)
        return checks
    tmp = Path(tempfile.mkdtemp(prefix="loop-doctor-"))
    folder = tmp / "main"
    try:
        sh(["git", "worktree", "add", "--detach", "--quiet", str(folder), main], root)
        settings = loop_settings(folder)
        try:
            keep_timeout = keep_limit_seconds(settings)
        except Refused as refusal:
            add(False, "AGENTS.md has a valid Keep limit", refusal.next_step)
            return checks
        if not add("test" in settings, "AGENTS.md on main names the Test command",
                   "merge setup's AGENTS.md section, with a 'Test command:' line"):
            return checks
        if "prepare" in settings:
            ok, output = prepare(folder)
            if not add(ok, f"Prepare passes on a fresh copy of main ({settings['prepare']})",
                       "fix the Prepare command:\n" + output.strip()[-800:]):
                return checks
        keep_command = settings.get("keep", settings["test"])
        if keep_command != settings["test"]:
            command_result(*run_judge(folder, settings["test"]), settings["test"], "the tests pass")
        command_result(*run_keep(folder, keep_command, timeout=keep_timeout), keep_command,
                       "the tests pass" if keep_command == settings["test"] else "Keep passes")

        def probe(command: str, proposed: bool = False) -> None:
            qprepare = (proposed_prepare if proposed and proposed_prepare is not None
                        else settings.get("prepare", ""))
            qtest = (proposed_test if proposed and proposed_test is not None
                     else settings["test"])
            qok, qoutput = quality_on_fresh_main(
                root, main, command, qtest, prepare_command=qprepare,
                proposed_quality=command if proposed else "")
            if "no changed Python functions found" in qoutput:
                add(True, f"Quality mutation check could not be exercised on main ({command})", "")
            else:
                label = "Proposed Quality" if proposed else "Quality"
                add(qok, f"{label} command passes on a fresh copy of main ({command})",
                    f"Quality check failed: {command}\n{qoutput.strip()[-800:]}")

        for command in settings.get("quality", []):
            probe(command)
        for command in extra_quality or []:
            probe(command, proposed=True)
    finally:
        remove_worktree(root, folder)
        with suppress(OSError):
            tmp.rmdir()
    if walk_away and all(ok for ok, _, _ in checks):
        import walkaway
        checks.extend(walkaway.preflight(gh, root, baseline_checked=True, agent=agent))
    return checks
