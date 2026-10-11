"""Verify a public release and keep its baseline outside the moving plugin cache."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from loop.paths import data_home

REPOSITORY = "https://github.com/gwpicard/ai-loop-kit.git"
PLUGIN = "ai-loop-kit"
SCHEMA = 1
_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_HASH = re.compile(r"[0-9a-f]{64}")
_FIELDS = {"schema", "repository", "plugin", "version", "tag", "commit", "files"}
_DEVELOPMENT_FIELDS = {"schema", "repository", "plugin", "mode", "commit", "files"}
DEVELOPMENT_MARKER = "# ai-loop-kit: development"
_DEVELOPMENT_NEXT = (
    "verify the development kit and prepare its generated workflow selector, then run "
    "setup.py found --development --kit-ref <full lowercase commit SHA>"
)


class VersionError(ValueError):
    """Release provenance is missing or inconsistent; never substitute a mutable ref."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.next_command = (
            "verify the installed release, then run setup.py found with its release tag"
        )


def manifest_version(kit: Path) -> str:
    path = kit / ".claude-plugin/plugin.json"
    if path.is_symlink():
        raise VersionError("the plugin manifest must not be a symlink")
    try:
        manifest = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as error:
        raise VersionError("the plugin manifest cannot be read") from error
    if not isinstance(manifest, dict) or manifest.get("name") != PLUGIN:
        raise VersionError("the installed plugin is not ai-loop-kit")
    version = manifest.get("version")
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise VersionError("the installed plugin has no valid release version")
    return version


def _development_error(message: str) -> VersionError:
    error = VersionError(message)
    error.next_command = _DEVELOPMENT_NEXT
    return error


def _development_manifest(kit: Path) -> None:
    """Accept a named development plugin, with no fabricated release version."""
    path = kit / ".claude-plugin/plugin.json"
    if path.is_symlink():
        raise _development_error("the plugin manifest must not be a symlink")
    try:
        manifest = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as error:
        raise _development_error("the plugin manifest cannot be read") from error
    if not isinstance(manifest, dict) or manifest.get("name") != PLUGIN:
        raise _development_error("the installed plugin is not ai-loop-kit")
    if "version" in manifest:
        manifest_version(kit)


def _development_request(kit: Path, given: str) -> str:
    _development_manifest(kit)
    if not _COMMIT.fullmatch(given):
        raise _development_error("development mode requires an explicit full lowercase commit SHA")
    return given


def development_selection(project: Path) -> str | None:
    """Read only one explicit generated mode/pin from the fixed project workflow."""
    path = project / ".github/workflows/checks.yml"
    for item in (project / ".github", path.parent, path):
        if item.is_symlink():
            raise _development_error("the development workflow selector must not contain symlinks")
    if not path.exists():
        return None
    if not path.is_file() or not path.resolve().is_relative_to(project.resolve()):
        raise _development_error("the development workflow selector must be inside the project")
    try:
        lines = path.read_text("utf-8").splitlines()
    except (OSError, ValueError) as error:
        raise _development_error("the development workflow selector cannot be read") from error
    markers = [line for line in lines if re.match(r"\s*#\s*ai-loop-kit\s*:", line)]
    if not markers:
        return None
    if not lines or lines[0] != DEVELOPMENT_MARKER or markers != [DEVELOPMENT_MARKER]:
        raise _development_error("the development workflow mode marker is invalid or ambiguous")
    selectors = [line for line in lines if re.match(r"\s*KIT_REVISION\b", line)]
    if len(selectors) != 1:
        raise _development_error("the development workflow revision is missing or ambiguous")
    selected = re.fullmatch(r'          KIT_REVISION: "([0-9a-f]{40})"', selectors[0])
    if selected is None:
        raise _development_error("the development workflow revision must be one generated full SHA")
    return selected.group(1)


def check_foundation_selection(project: Path, commit: str, *, development: bool) -> None:
    """Preserve existing workflow ownership before publication or foundation writes."""
    path = project / ".github/workflows/checks.yml"
    selected = development_selection(project)
    if development and path.exists() and selected != commit:
        raise _development_error(
            "prepare the existing workflow's development marker and matching SHA"
        )
    if not development and selected is not None:
        raise _development_error(
            "the existing workflow selects development; keep its explicit mode"
        )


def request(kit: Path, given: str) -> str:
    version = manifest_version(kit)
    selected = given or "v" + version
    if selected != "v" + version and not _COMMIT.fullmatch(selected):
        raise VersionError("select the installed release tag or its verified full commit SHA")
    return selected


def _relative(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(
        name
        and name != "."
        and not path.is_absolute()
        and ".." not in path.parts
        and "\\" not in name
        and "\0" not in name
        and str(path) == name
    )


def inventory(kit: Path) -> dict[str, dict[str, Any]]:
    """The complete release file set, excluding named runtime and legacy state."""
    found: dict[str, dict[str, Any]] = {}
    for folder, names, files in os.walk(kit, followlinks=False):
        for name in names:
            if (Path(folder) / name).is_symlink():
                raise VersionError("the installed kit contains a symlink directory")
        names[:] = [name for name in names if name != "__pycache__"]
        for name in files:
            path = Path(folder) / name
            relative = path.relative_to(kit).as_posix()
            if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
                raise VersionError(f"the installed kit contains a non-regular file: {relative}")
            if relative == "version.json" or name.endswith(".pyc"):
                continue
            found[relative] = {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "executable": bool(path.stat().st_mode & 0o111),
            }
    return dict(sorted(found.items()))


def _legacy(kit: Path) -> dict[str, str] | None:
    path = kit / "version.json"
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise VersionError("the legacy version record must be a regular file")
    try:
        record = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as error:
        raise VersionError("the legacy version record is unreadable") from error
    if (
        not isinstance(record, dict)
        or set(record) != {"record", "files"}
        or type(record["record"]) is not int
        or record["record"] != 1
        or not isinstance(record["files"], dict)
    ):
        raise VersionError("the legacy version record has an unsupported shape")
    files = record["files"]
    if not files or any(
        not isinstance(name, str)
        or not _relative(name)
        or not isinstance(value, str)
        or not _HASH.fullmatch(value)
        for name, value in files.items()
    ):
        raise VersionError("the legacy version record has invalid file hashes")
    return dict(files)


def _validated(body: Any, version: str) -> dict[str, Any]:
    if (
        not isinstance(body, dict)
        or set(body) != _FIELDS
        or body.get("schema") != SCHEMA
        or type(body.get("schema")) is not int
        or body.get("repository") != REPOSITORY
        or body.get("plugin") != PLUGIN
        or body.get("version") != version
        or body.get("tag") != "v" + version
        or not isinstance(body.get("commit"), str)
        or not _COMMIT.fullmatch(body["commit"])
    ):
        raise VersionError("the stable release record has invalid identity or schema")
    _validated_files(body)
    return dict(body)


def _validated_files(body: Mapping[str, Any], *, label: str = "stable release") -> None:
    files = body.get("files")
    if not isinstance(files, dict) or not files:
        raise VersionError(f"the {label} record has no file inventory")
    for name, item in files.items():
        if (
            not isinstance(name, str)
            or not _relative(name)
            or not isinstance(item, dict)
            or set(item) != {"sha256", "executable"}
            or not isinstance(item["sha256"], str)
            or not _HASH.fullmatch(item["sha256"])
            or not isinstance(item["executable"], bool)
        ):
            raise VersionError(f"the {label} record has an invalid file inventory")
    if ".claude-plugin/plugin.json" not in files:
        raise VersionError(f"the {label} record does not bind the plugin manifest")


def _validated_development(body: Any, commit: str) -> dict[str, Any]:
    if (
        not isinstance(body, dict)
        or set(body) != _DEVELOPMENT_FIELDS
        or type(body.get("schema")) is not int
        or body.get("schema") != 2
        or body.get("repository") != REPOSITORY
        or body.get("plugin") != PLUGIN
        or body.get("mode") != "development"
        or body.get("commit") != commit
        or not _COMMIT.fullmatch(commit)
    ):
        raise _development_error("the development record has invalid identity or schema")
    _validated_files(body, label="development")
    return dict(body)


def _home(kit: Path, project: Path, env: Mapping[str, str]) -> Path:
    home = data_home(env)
    if not home.is_absolute():
        raise VersionError("the version data home must be absolute")
    home = home.resolve()
    if any(home == root or root in home.parents for root in (kit.resolve(), project.resolve())):
        raise VersionError("the version data home must be outside the project and plugin")
    return home


def _path(kit: Path, project: Path, env: Mapping[str, str]) -> Path:
    version = manifest_version(kit)
    home = _home(kit, project, env)
    path = home / "versions/gwpicard/ai-loop-kit/ai-loop-kit/releases" / ("v" + version + ".json")
    for parent in (*path.parents, path):
        if parent == home:
            break
        if parent.is_symlink():
            raise VersionError("the version registry must not contain symlinks")
    if path.is_symlink():
        raise VersionError("the stable release record must not be a symlink")
    return path


def _development_path(
    kit: Path, project: Path, commit: str, env: Mapping[str, str]
) -> Path:
    home = _home(kit, project, env)
    path = home / "versions/gwpicard/ai-loop-kit/ai-loop-kit/development" / (commit + ".json")
    for parent in (*path.parents, path):
        if parent == home:
            break
        if parent.is_symlink():
            raise _development_error("the version registry must not contain symlinks")
    return path


def _read_development(path: Path, commit: str) -> dict[str, Any] | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise _development_error("the development record must be a regular file")
    try:
        return _validated_development(json.loads(path.read_text("utf-8")), commit)
    except (OSError, ValueError) as error:
        raise _development_error("the development record is invalid; keep it") from error


def _read(path: Path, version: str) -> dict[str, Any] | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise VersionError("the stable release record must be a regular file")
    try:
        return _validated(json.loads(path.read_text("utf-8")), version)
    except (OSError, ValueError) as error:
        raise VersionError("the stable release record is invalid; keep it") from error


def load(kit: Path, project: Path, *, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Read the one stable baseline selected by a validated plugin manifest."""
    environment = os.environ if env is None else env
    selected = development_selection(project)
    if selected is not None:
        _development_manifest(kit)
        body = _read_development(_development_path(kit, project, selected, environment), selected)
        if body is None:
            raise _development_error(
                "the development record is missing; verify it through explicit setup"
            )
        return body
    body = _read(_path(kit, project, environment), manifest_version(kit))
    if body is None:
        raise VersionError("the stable release record is missing; verify it through setup")
    return body


def verify(kit: Path, body: Mapping[str, Any]) -> None:
    if body.get("mode") == "development":
        _development_manifest(kit)
        expected = _validated_development(dict(body), str(body.get("commit", "")))
    else:
        expected = _validated(dict(body), manifest_version(kit))
    if inventory(kit) != expected["files"]:
        if body.get("mode") == "development":
            raise _development_error(
                "the installed kit differs from the verified development content"
            )
        raise VersionError("the installed kit differs from the verified release content")
    legacy = _legacy(kit)
    hashes = {name: item["sha256"] for name, item in expected["files"].items()}
    if legacy is not None and legacy != hashes:
        raise VersionError("the legacy version record disagrees with the verified release")


def _git(arguments: Sequence[str], folder: Path) -> str:
    home = folder.parent / "anonymous-home"
    home.mkdir(exist_ok=True)
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("GIT_", "GH_", "GITHUB_", "SSH_")) and name != "ANTHROPIC_API_KEY"
    }
    env.update(
        HOME=str(home),
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
        GIT_ASKPASS="/usr/bin/false",
    )
    try:
        done = subprocess.run(
            ["git", "-c", "credential.helper=", "-c", "http.extraHeader=", *arguments],
            cwd=folder,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise VersionError("anonymous release acquisition failed") from error
    if done.returncode != 0:
        raise VersionError("anonymous release acquisition failed")
    return done.stdout.strip()


def _acquire(tag: str) -> dict[str, Any]:
    """Fetch one public tag, peel its commit and hash that commit's kit tree."""
    with tempfile.TemporaryDirectory(prefix="ai-loop-release-") as temporary:
        folder = Path(temporary) / "checkout"
        folder.mkdir()
        _git(["init", "-q"], folder)
        _git(["remote", "add", "origin", REPOSITORY], folder)
        _git(["fetch", "--depth=1", "--no-tags", "origin", "refs/tags/" + tag], folder)
        _git(["checkout", "-q", "--detach", "FETCH_HEAD^{commit}"], folder)
        commit = _git(["rev-parse", "HEAD"], folder)
        if not _COMMIT.fullmatch(commit):
            raise VersionError("the acquired release has no full commit identity")
        kit = folder / "kit"
        version = manifest_version(kit)
        if tag != "v" + version:
            raise VersionError("the acquired tag disagrees with the plugin manifest version")
        return _validated(
            {
                "schema": SCHEMA,
                "repository": REPOSITORY,
                "plugin": PLUGIN,
                "version": version,
                "tag": tag,
                "commit": commit,
                "files": inventory(kit),
            },
            version,
        )


def _acquire_development(commit: str) -> dict[str, Any]:
    """Acquire exactly one public commit, without release-tag or credential fallback."""
    with tempfile.TemporaryDirectory(prefix="ai-loop-development-") as temporary:
        folder = Path(temporary) / "checkout"
        folder.mkdir()
        _git(["init", "-q"], folder)
        _git(["remote", "add", "origin", REPOSITORY], folder)
        _git(["fetch", "--depth=1", "--no-tags", "origin", commit], folder)
        _git(["checkout", "-q", "--detach", "FETCH_HEAD^{commit}"], folder)
        fetched = _git(["rev-parse", "HEAD"], folder)
        if fetched != commit:
            raise _development_error(
                "the fetched development commit differs from the requested full SHA"
            )
        kit = folder / "kit"
        _development_manifest(kit)
        return _validated_development(
            {"schema": 2, "repository": REPOSITORY, "plugin": PLUGIN,
             "mode": "development", "commit": commit, "files": inventory(kit)}, commit
        )


@dataclass(frozen=True)
class Prepared:
    kit: Path
    project: Path
    path: Path
    body: dict[str, Any]
    dry_run: bool

    @property
    def commit(self) -> str:
        return str(self.body["commit"])


def prepare(
    kit: Path,
    project: Path,
    given: str = "",
    *,
    dry_run: bool = False,
    development: bool = False,
    env: Mapping[str, str] | None = None,
) -> Prepared:
    environment = os.environ if env is None else env
    if development:
        try:
            selected = _development_request(kit, given)
            _legacy(kit)
            path = _development_path(kit, project, selected, environment)
            existing = _read_development(path, selected)
            # Development dry-run verifies scratch only; the release dry-run stays unchanged.
            body = _acquire_development(selected)
            if existing is not None and existing != body:
                raise VersionError("the development commit conflicts with its immutable baseline")
            verify(kit, body)
            return Prepared(kit, project, path, body, dry_run)
        except VersionError as error:
            error.next_command = _DEVELOPMENT_NEXT
            raise
    selected = request(kit, given)
    _legacy(kit)  # Invalid legacy state refuses before acquisition, without altering it.
    path = _path(kit, project, environment)
    existing = _read(path, manifest_version(kit))
    if dry_run or _COMMIT.fullmatch(selected):
        if existing is None:
            raise VersionError("verify the release tag first; no existing baseline binds this SHA")
        if _COMMIT.fullmatch(selected) and existing["commit"] != selected:
            raise VersionError("the requested SHA disagrees with the verified release")
        body = existing
    else:
        body = _acquire(selected)
        if existing is not None and existing != body:
            raise VersionError("the release tag now disagrees with its existing immutable binding")
    verify(kit, body)
    return Prepared(kit, project, path, body, dry_run)


def publish(prepared: Prepared) -> str:
    """Publish one completed baseline once; cooperating writers cannot replace it."""
    verify(prepared.kit, prepared.body)

    def existing_record() -> dict[str, Any] | None:
        if prepared.body.get("mode") == "development":
            return _read_development(prepared.path, prepared.commit)
        return _read(prepared.path, manifest_version(prepared.kit))

    existing = existing_record()
    if existing is not None:
        if existing != prepared.body:
            raise VersionError("the stable version baseline conflicts; it was not replaced")
        return "kept"
    if prepared.dry_run:
        return "would write"
    try:
        prepared.path.parent.mkdir(parents=True, exist_ok=True)
        for parent in (prepared.path.parent, *prepared.path.parent.parents):
            if parent.is_symlink():
                raise VersionError("the version registry must not contain symlinks")
        descriptor = os.open(
            str(prepared.path) + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            existing = existing_record()
            if existing is not None:
                if existing != prepared.body:
                    raise VersionError("the stable version baseline conflicts; it was not replaced")
                return "kept"
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=prepared.path.parent
            ) as pending:
                json.dump(prepared.body, pending, sort_keys=True, indent=2)
                pending.write("\n")
                pending.flush()
                os.fsync(pending.fileno())
                try:
                    os.link(pending.name, prepared.path)
                except FileExistsError as error:
                    if existing_record() != prepared.body:
                        raise VersionError("another writer published conflicting state") from error
                    return "kept"
            return "written"
        finally:
            os.close(descriptor)
    except OSError as error:
        raise VersionError("the stable baseline could not be written; founding refused") from error
