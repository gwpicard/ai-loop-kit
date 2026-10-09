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
    files = body.get("files")
    if not isinstance(files, dict) or not files:
        raise VersionError("the stable release record has no file inventory")
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
            raise VersionError("the stable release record has an invalid file inventory")
    if ".claude-plugin/plugin.json" not in files:
        raise VersionError("the stable release record does not bind the plugin manifest")
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
    body = _read(_path(kit, project, environment), manifest_version(kit))
    if body is None:
        raise VersionError("the stable release record is missing; verify it through setup")
    return body


def verify(kit: Path, body: Mapping[str, Any]) -> None:
    expected = _validated(dict(body), manifest_version(kit))
    if inventory(kit) != expected["files"]:
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
    env: Mapping[str, str] | None = None,
) -> Prepared:
    environment = os.environ if env is None else env
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
    version = manifest_version(prepared.kit)
    existing = _read(prepared.path, version)
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
            existing = _read(prepared.path, version)
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
                    if _read(prepared.path, version) != prepared.body:
                        raise VersionError("another writer published conflicting state") from error
                    return "kept"
            return "written"
        finally:
            os.close(descriptor)
    except OSError as error:
        raise VersionError("the stable baseline could not be written; founding refused") from error
