"""Setup diagnostics for a project's loop settings and environment."""
from __future__ import annotations

import shutil
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "quality"))
from proposed_quality import apply as apply_proposed_quality


def quality_on_fresh_main(root: Path, main: str, command: str,
                          test_command: str = "",
                          protected_paths: list[str] | None = None,
                          prepare_command: str | None = None,
                          proposed_quality: str = "") -> tuple[bool, str]:
    """Run Test, then one Quality command in its own prepared copy of main."""
    tmp = Path(tempfile.mkdtemp(prefix="loop-doctor-quality-"))
    folder = tmp / "main"
    try:
        sh(["git", "worktree", "add", "--detach", "--quiet", str(folder), main], root)
        if proposed_quality:
            apply_proposed_quality(folder / "AGENTS.md", proposed_quality,
                                   prepare_command, test_command)
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
        sh(["git", "worktree", "remove", "--force", str(folder)], root, check=False)
        with suppress(OSError):
            tmp.rmdir()


def doctor(gh: GitHub, root: Path, extra_quality: list[str] | None = None,
           proposed_prepare: str | None = None,
           proposed_test: str | None = None,
           walk_away: bool = False,
           agent: str | None = None) -> list[tuple[bool, str, str]]:
    """Setup's checks, in code. Each is (passed, what, next step)."""
    checks: list[tuple[bool, str, str]] = []

    def add(ok: bool, what: str, fix: str) -> bool:
        checks.append((ok, what, "" if ok else fix))
        return ok

    origin = sh(["git", "remote", "get-url", "origin"], root, check=False).stdout.strip()
    if not add(bool(origin), "the project has an origin",
               "create the GitHub repository and add it as origin"):
        return checks
    try:
        signed_in = gh.signed_in()
    except RuntimeError as error:
        add(False, str(error), "run: gh auth login")
        return checks
    if not add(signed_in, "gh is signed in", "run: gh auth login"):
        return checks
    try:
        main = main_ref(root)
        add(main == "origin/main", "main has a commit on origin", "push a first commit to main")
    except Refused as r:
        add(False, "main has a commit on origin", r.next_step)
        return checks
    protection = gh.main_protection() if hasattr(gh, "main_protection") else "unknown"
    checks.append((True, f"main branch protection: {protection}", ""))
    have = set(gh.labels())
    add(all(STATE_PREFIX + s in have for s in STATES), "the state labels exist",
        "run: gate.py init")

    old_worktrees = root / ".loop" / "worktrees"
    if old_worktrees.is_dir() and any(old_worktrees.iterdir()):
        folders = ", ".join(
            child.relative_to(root).as_posix() for child in sorted(old_worktrees.iterdir()))
        checks.append((True,
                       f"warning: old in-project worktrees can break project tests: {folders}",
                       f"The person may remove these folders after checking them: {folders}."))

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
        if keep_command == settings["test"]:
            code, output = run_keep(folder, keep_command, timeout=keep_timeout)
            check_name = f"the tests pass on a fresh copy of main ({settings['test']})"
        else:
            code, output = run_judge(folder, settings["test"])
            add(code == 0, f"the tests pass on a fresh copy of main ({settings['test']})",
                "fix the Test command or the environment, or add a Prepare command:\n"
                + output.strip()[-800:])
            code, output = run_keep(folder, keep_command, timeout=keep_timeout)
            check_name = f"Keep passes on a fresh copy of main ({keep_command})"
        duration = next((line for line in output.splitlines()
                         if line.startswith("Keep took: ")), "")
        if duration:
            check_name += f" ({duration.removeprefix('Keep took: ')})"
        if code == 124:
            fix = ("increase Keep limit in AGENTS.md or make the Keep command finish sooner:\n"
                   + output.strip()[-800:])
        else:
            fix = ("fix the Keep command or the environment, or add a Prepare command:\n"
                   + output.strip()[-800:])
        add(code == 0, check_name, fix)

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
        sh(["git", "worktree", "remove", "--force", str(folder)], root, check=False)
        shutil.rmtree(tmp, ignore_errors=True)
    if walk_away and all(ok for ok, _, _ in checks):
        import walkaway
        checks.extend(walkaway.preflight(gh, root, baseline_checked=True, agent=agent))
    return checks
