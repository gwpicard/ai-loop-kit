#!/usr/bin/env python3
# contract: agent
"""Refuse to start a run, with the reason, unless every guard is in place.

Run from inside the project, before `run.py` starts any builder:

    pre-run-check.py [--project DIR] [--run NAME] [--unattended] [--merge-pre-approved]

It checks, and reports every refusal at once, each naming the guard and the
command that puts it back:

- the guard hook, the deny rules, the sandbox, and the settings a person's own
  value must not beat (`.claude/settings.json` and `settings.local.json`);
- the pre-push hook and the setting that turns it on;
- the installed kit folder: the plugin's version record in a founded project,
  `git status` on `kit/` in the kit's own repository;
- the policy file: readable, and every value valid (a bad one is named by key);
- the lock: no other live run holds this project;
- the computer: mains power, sleep held off, free memory, free disk (read with
  `pmset`, `vm_stat` and `df`), and a Claude Code that is new enough;
- `main`: the policy's test command passes on a clean copy of `main`;
- the tools and the origin (`check-tooling.sh --for-run`): the project must not
  point at the kit's own repository;
- an API key must have spend caps;
- the GitHub App key. An unattended run and a pre-approved merge need it. An
  attended local run passes without it, with one notice.

`--unattended` is what `run.py` passes for a run nobody watches.
`--merge-pre-approved` is what it passes when the person pre-approved the merge.
The policy file has no key for either, on purpose.

It changes nothing in the project. The test of `main` runs in a new folder under
the system's temporary folder, which is left in place.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop import cli, policy
from loop.paths import PathError, Paths, find_project_root

FIRST_HALF = "the first half of /setup (shape and run locally)"
SECOND_HALF = "the second half of /setup (make it safe to walk away)"
MIN_CLAUDE = (2, 1, 219)
RECORD = "version.json"
MAIN_BRANCH = "main"
APP_NOTICE = (
    "the second half of `/setup` is missing: the run stops if this computer sleeps "
    "or this session closes, and GitHub steps wait for you"
)
HERE = Path(__file__).resolve().parent


@dataclass
class Refusal:
    guard: str
    reason: str
    fix: str
    half: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"guard": self.guard, "half": self.half, "reason": self.reason, "fix": self.fix}


def setup_fix(half: str) -> str:
    return f"run {half}, then run pre-run-check.py again"


def first_half(guard: str, reason: str) -> Refusal:
    return Refusal(guard, reason, setup_fix(FIRST_HALF), "first")


def second_half(guard: str, reason: str) -> Refusal:
    return Refusal(guard, reason, setup_fix(SECOND_HALF), "second")


def other(guard: str, reason: str, fix: str) -> Refusal:
    return Refusal(guard, reason, fix)


# --- reading the machine -----------------------------------------------------


def read_command(argv: list[str], *, cwd: Path | None = None, timeout: float = 20) -> str | None:
    """Standard output of a command, or None when it is missing, fails or hangs."""
    try:
        done = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            cwd=cwd,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def check_power() -> list[Refusal]:
    out = read_command(["pmset", "-g", "batt"])
    if out is None:
        return [
            other(
                "battery",
                "cannot read the power source: pmset gave no answer",
                "run on a Mac with pmset, then run pre-run-check.py again",
            )
        ]
    if "Battery Power" in out:
        return [
            other(
                "battery",
                "the computer runs on battery",
                "plug in the power cable, then run pre-run-check.py again",
            )
        ]
    return []


def check_sleep() -> list[Refusal]:
    out = read_command(["pmset", "-g", "assertions"])
    if out is None:
        return [
            other(
                "sleep",
                "cannot read the sleep assertions: pmset gave no answer",
                "run on a Mac with pmset, then run pre-run-check.py again",
            )
        ]
    held = re.findall(r"(PreventUserIdleSystemSleep|PreventSystemSleep)\s+(\d+)", out)
    if any(count != "0" for _, count in held):
        return []
    return [
        other(
            "sleep",
            "nothing holds this computer awake, so it may sleep during the run",
            "start the run under caffeinate: caffeinate -i python3 run.py ...",
        )
    ]


def free_memory_mb() -> int | None:
    out = read_command(["vm_stat"])
    if out is None:
        return None
    size = re.search(r"page size of (\d+) bytes", out)
    if not size:
        return None
    pages = 0
    for name in ("free", "inactive", "speculative"):
        found = re.search(rf"Pages {name}:\s+(\d+)", out)
        if found:
            pages += int(found.group(1))
    return pages * int(size.group(1)) // (1024 * 1024)


def check_memory(floor_mb: int) -> list[Refusal]:
    free = free_memory_mb()
    if free is None:
        return [
            other(
                "memory",
                "cannot read the free memory: vm_stat gave no answer",
                "run on a Mac with vm_stat, then run pre-run-check.py again",
            )
        ]
    if free < floor_mb:
        return [
            other(
                "memory",
                f"{free} MB of memory is free, and a run needs {floor_mb} MB "
                "(the policy key min_free_memory_mb)",
                "close other programs, then run pre-run-check.py again",
            )
        ]
    return []


def check_disk(root: Path, floor_gb: int) -> list[Refusal]:
    out = read_command(["df", "-Pk", str(root)])
    lines = out.strip().splitlines() if out else []
    fields = lines[-1].split() if len(lines) >= 2 else []
    if len(fields) < 4 or not fields[3].isdigit():
        return [
            other(
                "disk",
                "cannot read the free disk space: df gave no answer",
                "check the disk, then run pre-run-check.py again",
            )
        ]
    free = int(fields[3]) // (1024 * 1024)
    if free < floor_gb:
        return [
            other(
                "disk",
                f"{free} GB of disk is free, and a run needs {floor_gb} GB "
                "(the policy key min_free_disk_gb)",
                "free some disk space, then run pre-run-check.py again",
            )
        ]
    return []


def check_claude_version() -> list[Refusal]:
    need = ".".join(str(part) for part in MIN_CLAUDE)
    fix = "update Claude Code (claude update), then run pre-run-check.py again"
    out = read_command(["claude", "--version"])
    if out is None:
        return [
            other(
                "claude-version",
                f"cannot read the Claude Code version. Version {need} "
                "or later is needed, for strictAllowlist",
                fix,
            )
        ]
    found = re.match(r"\s*(\d+)\.(\d+)\.(\d+)", out)
    if not found:
        return [
            other(
                "claude-version",
                f"cannot read a version from {out.strip()!r}. "
                f"Version {need} or later is needed, for strictAllowlist",
                fix,
            )
        ]
    version = tuple(int(part) for part in found.groups())
    if version < MIN_CLAUDE:
        return [
            other(
                "claude-version",
                f"Claude Code {'.'.join(map(str, version))} is older than "
                f"{need}, which strictAllowlist needs",
                fix,
            )
        ]
    return []


# --- the guards in the project -----------------------------------------------


def load_merge_settings() -> Any:
    spec = importlib.util.spec_from_file_location("merge_settings", HERE / "merge-settings.py")
    if spec is None or spec.loader is None:
        raise cli.Failure(
            "cannot load merge-settings.py",
            next_command="pre-run-check.py --help",
            code=cli.ExitCode.ENVIRONMENT,
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> tuple[Any, str]:
    """The JSON in `path` and an error text. The text is empty when it was read."""
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except OSError:
        return None, f"{path} is missing or cannot be read"
    except ValueError as error:
        return None, f"{path} is not valid JSON ({error})"


def check_hook(kit: Path) -> list[Refusal]:
    """The guard hook is in the kit's hook list and in the builders' settings."""
    refusals: list[Refusal] = []
    for relative in ("hooks/hooks.json", "templates/builder-settings.json"):
        data, error = read_json(kit / relative)
        if error:
            refusals.append(first_half("guard-hook", error))
            continue
        entries = (data.get("hooks", {}) if isinstance(data, dict) else {}).get("PreToolUse", [])
        commands = [
            str(hook.get("command", ""))
            for entry in entries
            if isinstance(entry, dict)
            for hook in entry.get("hooks", [])
            if isinstance(hook, dict)
        ]
        if not any("hooks/guard.py" in command for command in commands):
            refusals.append(
                first_half(
                    "guard-hook",
                    f"{kit / relative} has no PreToolUse entry that runs hooks/guard.py",
                )
            )
    if not (kit / "hooks" / "guard.py").is_file():
        refusals.append(
            first_half("guard-hook", f"the guard script {kit / 'hooks' / 'guard.py'} is missing")
        )
    return refusals


def check_settings(root: Path, kit: Path) -> list[Refusal]:
    """Deny rules, sandbox and the values a person's setting must not beat."""
    template_path = kit / "templates" / "claude-settings.json"
    try:
        text = template_path.read_text(encoding="utf-8").replace("{{KIT_DIR}}", str(kit))
        template = json.loads(text)
    except (OSError, ValueError) as error:
        return [first_half("deny-rule", f"cannot read the kit's settings template ({error})")]
    refusals: list[Refusal] = []
    settings_path = root / ".claude" / "settings.json"
    mine, settings_error = read_json(settings_path)
    if settings_error or not isinstance(mine, dict):
        reason = f"{settings_error or 'it is not a JSON object'}, so no guard setting is in place"
        return [first_half("deny-rule", reason), first_half("sandbox", reason)]
    merge_settings = load_merge_settings()
    added: list[str] = []
    overridden: list[str] = []
    merge_settings.merge(mine, template, added, overridden=overridden)
    have = (
        mine.get("permissions", {}).get("deny", [])
        if isinstance(mine.get("permissions"), dict)
        else []
    )
    missing = [rule for rule in template["permissions"]["deny"] if rule not in have]
    if missing:
        shown = ", ".join(missing[:6]) + (
            f" and {len(missing) - 6} more" if len(missing) > 6 else ""
        )
        refusals.append(
            first_half(
                "deny-rule",
                f"{len(missing)} deny rule(s) are missing from .claude/settings.json: {shown}",
            )
        )
    for entry in added:
        key = entry.split(":")[0]
        if key.startswith("sandbox"):
            refusals.append(first_half("sandbox", f"{key} is not set in .claude/settings.json"))
        elif key.startswith("permissions.deny"):
            continue
        elif key.startswith("permissions"):
            refusals.append(
                first_half(
                    "setting-override",
                    "permissions.disableBypassPermissionsMode is not set in .claude/settings.json",
                )
            )
        elif not key.startswith("hooks"):
            refusals.append(
                first_half("setting-override", f"{key} is not set in .claude/settings.json")
            )
    start = (
        mine.get("hooks", {}).get("SessionStart", []) if isinstance(mine.get("hooks"), dict) else []
    )
    if "scripts/session-start.sh" not in json.dumps(start):
        refusals.append(
            first_half(
                "settings-hook",
                "no SessionStart hook runs scripts/session-start.sh in .claude/settings.json",
            )
        )
    local, local_error = read_json(root / ".claude" / "settings.local.json")
    if not local_error and isinstance(local, dict):
        merge_settings.merge(local, template, [], overridden=overridden)
    elif (root / ".claude" / "settings.local.json").exists():
        refusals.append(first_half("setting-override", f"{local_error}, so it cannot be checked"))
    for line in overridden:
        guard = "sandbox" if line.startswith("sandbox") else "setting-override"
        refusals.append(first_half(guard, f"a setting of yours beats a kit guard: {line}"))
    builder, builder_error = read_json(kit / "templates" / "builder-settings.json")
    network: dict[str, Any] = {}
    if not builder_error and isinstance(builder, dict):
        sandbox = builder.get("sandbox", {})
        network = sandbox.get("network", {}) if isinstance(sandbox, dict) else {}
    if not network.get("strictAllowlist") or not network.get("allowedDomains"):
        refusals.append(
            first_half(
                "sandbox",
                "the builders' network allowlist is not strict: "
                "strictAllowlist is not true or allowedDomains is empty "
                f"in {kit / 'templates' / 'builder-settings.json'}",
            )
        )
    return refusals


def check_pre_push(root: Path, kit: Path) -> list[Refusal]:
    hook = root / ".githooks" / "pre-push"
    refusals: list[Refusal] = []
    template = kit / "templates" / "githooks" / "pre-push"
    if not hook.is_file():
        refusals.append(first_half("pre-push-hook", "the hook .githooks/pre-push is missing"))
    elif not os.access(hook, os.X_OK):
        refusals.append(first_half("pre-push-hook", ".githooks/pre-push is not executable"))
    elif not template.is_file() or hook.read_bytes() != template.read_bytes():
        refusals.append(
            first_half(
                "pre-push-hook",
                ".githooks/pre-push differs from the kit's "
                "copy, so it may no longer scan for secrets",
            )
        )
    path = read_command(["git", "-C", str(root), "config", "--get", "core.hooksPath"])
    if (path or "").strip() != ".githooks":
        refusals.append(
            first_half(
                "pre-push-hook",
                "core.hooksPath is not .githooks, so Git does not run the pre-push hook",
            )
        )
    return refusals


def kit_files(kit: Path) -> dict[str, str]:
    """Each file of the kit folder, by relative path, with its SHA-256. Skips the record."""
    found: dict[str, str] = {}
    for folder, names, files in os.walk(kit):
        names[:] = [name for name in names if name != "__pycache__"]
        for name in files:
            path = Path(folder) / name
            relative = path.relative_to(kit).as_posix()
            if relative == RECORD or name.endswith(".pyc"):
                continue
            found[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(sorted(found.items()))


def write_record(kit: Path) -> None:
    """Write the plugin's version record. The installer calls this when it installs the kit."""
    record = {"record": 1, "files": kit_files(kit)}
    (kit / RECORD).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def check_kit_folder(root: Path, kit: Path) -> list[Refusal]:
    if kit.resolve() == (root / "kit").resolve():
        out = read_command(["git", "-C", str(root), "status", "--porcelain", "--", "kit"])
        if out is None:
            return [first_half("kit-folder", "cannot read git status for kit/")]
        if out.strip():
            lines = [line.strip() for line in out.strip().splitlines()]
            shown = "; ".join(lines[:5]) + (
                f"; and {len(lines) - 5} more" if len(lines) > 5 else ""
            )
            return [
                first_half(
                    "kit-folder",
                    f"kit/ has changes that are not committed: {shown}. "
                    "Undo them with git restore, or reinstall the kit",
                )
            ]
        return []
    record, error = read_json(kit / RECORD)
    if error or not isinstance(record, dict) or not isinstance(record.get("files"), dict):
        return [
            first_half(
                "kit-folder",
                f"the plugin's version record {kit / RECORD} is missing or "
                "unreadable, so the installed kit cannot be compared. Reinstall the kit",
            )
        ]
    expected: dict[str, str] = record["files"]
    now = kit_files(kit)
    changed = sorted(name for name in expected if name in now and now[name] != expected[name])
    gone = sorted(name for name in expected if name not in now)
    added = sorted(name for name in now if name not in expected)
    if not (changed or gone or added):
        return []
    parts = [
        f"{label}: {', '.join(names[:5])}"
        for label, names in (("changed", changed), ("missing", gone), ("added", added))
        if names
    ]
    return [
        first_half(
            "kit-folder",
            "the installed kit folder differs from its version record ("
            + "; ".join(parts)
            + "). Reinstall the kit",
        )
    ]


def check_lock(paths: Paths, run: str) -> list[Refusal]:
    refusals: list[Refusal] = []
    if not paths.runs_dir.is_dir():
        return refusals
    for folder in sorted(paths.runs_dir.iterdir()):
        lock = folder / "lock"
        if folder.name == run or not lock.is_file():
            continue
        found = re.search(r"\d+", lock.read_text(encoding="utf-8", errors="replace"))
        if found is None:
            refusals.append(
                other(
                    "lock",
                    f"the run {folder.name} has a lock with no process number, "
                    "so it cannot be told from a live one",
                    f"check {lock}, then run pre-run-check.py again",
                )
            )
            continue
        pid = int(found.group(1) if found.groups() else found.group(0))
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue
        except PermissionError:
            pass
        refusals.append(
            other(
                "lock",
                f"the run {folder.name} holds this project's lock (process {pid})",
                "wait for that run to finish, or stop it, then run pre-run-check.py again",
            )
        )
    return refusals


def check_main(root: Path, command: str, timeout: int) -> tuple[list[Refusal], str]:
    """The policy's test command must pass on a clean copy of `main`."""
    if not command.strip():
        return [
            other(
                "main",
                "the policy has no test_command, so main cannot be shown to be green",
                "write test_command in .agents/loop/policy.json (the command that tests "
                "the project), then run pre-run-check.py again",
            )
        ], ""
    found = read_command(
        ["git", "-C", str(root), "rev-parse", "--verify", "--quiet", f"refs/heads/{MAIN_BRANCH}"]
    )
    if found is None:
        return [
            other(
                "main",
                f"there is no {MAIN_BRANCH} branch to test",
                f"create the {MAIN_BRANCH} branch, then run pre-run-check.py again",
            )
        ], ""
    folder = Path(tempfile.mkdtemp(prefix="pre-run-main-"))
    try:
        archive = subprocess.run(
            ["git", "-C", str(root), "archive", MAIN_BRANCH],
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["tar", "-x", "-C", str(folder)], input=archive.stdout, check=True, capture_output=True
        )
        argv = shlex.split(command)
        done = subprocess.run(
            argv,
            cwd=folder,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return [
            other(
                "main",
                f"the test command ({command}) ran past {timeout} seconds on a clean "
                f"copy of {MAIN_BRANCH}",
                "make main faster or raise test_timeout_seconds in the "
                "policy, then run pre-run-check.py again",
            )
        ], str(folder)
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        return [
            other(
                "main",
                f"cannot run the test command ({command}) on a clean copy of "
                f"{MAIN_BRANCH}: {error}",
                "fix test_command in the policy, then run pre-run-check.py again",
            )
        ], str(folder)
    if done.returncode == 0:
        return [], str(folder)
    tail = " | ".join((done.stdout + done.stderr).strip().splitlines()[-5:])
    return [
        other(
            "main",
            f"main is red: the test command ({command}) failed with exit code "
            f"{done.returncode} on a clean copy of {MAIN_BRANCH}, in {folder}. {tail}".strip(),
            f"fix {MAIN_BRANCH} through a pull request, then run pre-run-check.py again",
        )
    ], str(folder)


def check_tooling(root: Path) -> list[Refusal]:
    script = HERE / "check-tooling.sh"
    try:
        done = subprocess.run(
            ["sh", str(script), "--for-run"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return [first_half("tooling", f"cannot run check-tooling.sh ({error})")]
    if done.returncode == 0:
        return []
    if done.returncode == 3:
        reason = (
            done.stderr.strip().splitlines()[0]
            if done.stderr.strip()
            else "the project points at the kit's own repository"
        )
        return [
            Refusal(
                "kit-repository",
                reason,
                setup_fix(FIRST_HALF) + ". It asks for your own repository",
                "first",
            )
        ]
    lines = [
        line
        for line in done.stdout.splitlines()
        if line
        and " is ready" not in line
        and "does not stop founding" not in line
        and not line.startswith(("Every tool", "Issues are", "Labels can", "Git is version"))
    ]
    return [first_half("tooling", " ".join(lines) or "a tool the kit needs is missing")]


def check_app(paths: Paths, root: Path, *, needs_app: bool) -> tuple[list[Refusal], list[str]]:
    key = paths.app_key_file
    if not key.is_file():
        if needs_app:
            return [
                second_half(
                    "app-key",
                    f"there is no GitHub App key at {key}, and an unattended "
                    "run or a pre-approved merge needs the App",
                )
            ], []
        return [], [APP_NOTICE]
    refusals: list[Refusal] = []
    resolved = key.resolve()
    if root.resolve() in (resolved, *resolved.parents):
        refusals.append(
            second_half(
                "app-key",
                f"the App key {key} is inside the project, where "
                "an agent could read it. Move it outside the project",
            )
        )
    if key.stat().st_mode & 0o077:
        refusals.append(
            second_half(
                "app-key", f"the App key {key} can be read by other users. Run: chmod 600 on it"
            )
        )
    return refusals, []


def check_policy(paths: Paths, root: Path) -> tuple[list[Refusal], dict[str, Any], dict[str, Any]]:
    """The refusals, the policy with defaults, and the raw data (empty when unreadable)."""
    name = paths.policy_file.relative_to(root).as_posix()
    try:
        data = policy.read(paths.policy_file)
    except policy.PolicyError as error:
        return (
            [first_half("policy", f"{error}. The policy file is {name}")],
            policy.with_defaults({}),
            {},
        )
    problems = policy.validate(data)
    refusals = [
        first_half(
            "policy-value", f"{name}: {problem.key + ': ' if problem.key else ''}{problem.message}"
        )
        for problem in problems
        if problem.message != policy.NEEDS_CAP
    ]
    raw = data if isinstance(data, dict) else {}
    if any(problem.key for problem in problems):
        usable = {
            k: v for k, v in raw.items() if not any(p.key.split(".")[0] == k for p in problems)
        }
        return refusals, policy.with_defaults(usable), raw
    return refusals, policy.with_defaults(raw), raw


def check_spend(raw: dict[str, Any], merged: dict[str, Any]) -> list[Refusal]:
    given = raw.get("billing")
    billing: dict[str, Any] = given if isinstance(given, dict) else {}
    mode = billing.get("mode", merged["billing"]["mode"])
    uses_key = mode == "api_key" or bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not uses_key:
        return []
    missing = [key for key in policy.SPEND_CAPS if billing.get(key) is None]
    if not missing:
        return []
    names = ", ".join(f"billing.{key}" for key in missing)
    return [
        second_half(
            "api-spend-cap", f"an API key is in use and the policy sets no spend caps ({names})"
        )
    ]


# --- the command -------------------------------------------------------------


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project", default=".", help="a folder inside the project (default: here)"
    )
    parser.add_argument(
        "--run", default="", help="this run's name, so its own lock is not another run's"
    )
    parser.add_argument(
        "--unattended",
        action="store_true",
        help="the run is not watched (run.py passes this): the App key is needed",
    )
    parser.add_argument(
        "--merge-pre-approved",
        action="store_true",
        dest="merge_pre_approved",
        help="the person pre-approved the merge for this run: the App key is needed",
    )


def handler(args: argparse.Namespace) -> dict[str, Any]:
    try:
        root = find_project_root(Path(args.project))
    except PathError as error:
        raise cli.Failure(
            str(error),
            next_command="cd into the project, then run pre-run-check.py again",
            code=cli.ExitCode.REFUSED,
        ) from error
    paths = Paths.for_project(root)
    kit = paths.kit_dir
    refusals: list[Refusal] = []
    notices: list[str] = []

    refusals += check_hook(kit)
    refusals += check_settings(root, kit)
    refusals += check_pre_push(root, kit)
    refusals += check_kit_folder(root, kit)
    policy_refusals, merged, raw = check_policy(paths, root)
    refusals += policy_refusals
    refusals += check_spend(raw, merged)
    refusals += check_lock(paths, args.run)
    refusals += check_power()
    refusals += check_sleep()
    refusals += check_memory(merged["min_free_memory_mb"])
    refusals += check_disk(root, merged["min_free_disk_gb"])
    refusals += check_claude_version()
    refusals += check_tooling(root)
    app_refusals, app_notices = check_app(
        paths, root, needs_app=args.unattended or args.merge_pre_approved
    )
    refusals += app_refusals
    notices += app_notices
    main_refusals, main_folder = check_main(
        root, merged["test_command"], merged["test_timeout_seconds"]
    )
    refusals += main_refusals

    if refusals:
        lines = [f"- [{r.guard}] {r.reason}. Fix: {r.fix}" for r in refusals]
        raise cli.Failure(
            "the run will not start:\n" + "\n".join(lines),
            next_command=(
                refusals[0].fix
                if len(refusals) == 1
                else "fix each refusal above, as its Fix says, then run pre-run-check.py again"
            ),
            code=cli.ExitCode.REFUSED,
            data={"refusals": [r.as_dict() for r in refusals], "notices": notices},
        )
    return {
        "attended": not args.unattended,
        "merge_pre_approved": bool(args.merge_pre_approved),
        "main_checked_in": main_folder,
        "notices": notices,
        "project": str(root),
    }


def main(argv: list[str]) -> int:
    code = cli.run(
        "pre-run-check.py",
        "Refuse to start a run, with the reason, unless every guard, the policy, the computer "
        "and main are fine.",
        setup,
        handler,
        argv,
    )
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
