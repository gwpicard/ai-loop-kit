"""Person-published, protected, point-in-time GitHub reads before the App exists."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loop import cli, github
from loop.paths import Paths

TRUSTED_KIT = Path(__file__).resolve().parents[2]
LIMIT = 8 * 1024 * 1024
RESPONSE_LIMIT = LIMIT
TTL = 15 * 60


def refuse(paths: Paths, message: str) -> github.GitHubError:
    return github.GitHubError("person-synced reads refused: " + message,
                              next_command=github.sync_command(paths.root),
                              code=cli.ExitCode.REFUSED)


def regular(paths: Paths, path: Path, *, directory: bool = False) -> None:
    for ancestor in (path, *path.parents):
        if ancestor == paths.root.parent:
            break
        if ancestor.is_symlink():
            raise refuse(paths, "a protected path is a symlink")
    if path.exists() and not (path.is_dir() if directory else path.is_file()):
        raise refuse(paths, "a protected path has the wrong file type")


def no_duplicates(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def object_file(paths: Paths, path: Path, *, optional: bool = False) -> dict[str, Any]:
    regular(paths, path)
    if optional and not path.exists():
        return {}
    try:
        if path.stat().st_size > LIMIT:
            raise ValueError("oversized JSON")
        value = json.loads(path.read_text("utf-8"), object_pairs_hook=no_duplicates)
        if not isinstance(value, dict):
            raise ValueError("not an object")
        return value
    except (OSError, ValueError) as error:
        raise refuse(paths, "a protected JSON file is missing or malformed") from error


def protection(paths: Paths) -> None:
    """Admit only the effective, project-bound filesystem authority."""
    root = paths.root.resolve()
    if root != paths.root:
        raise refuse(paths, "the project root is not canonical")
    project = object_file(paths, root / ".claude/settings.json")
    local = object_file(paths, root / ".claude/settings.local.json", optional=True)
    try:
        template = json.loads((TRUSTED_KIT / "templates/claude-settings.json").read_text("utf-8"))
        allowed = {item.replace("{{KIT_DIR}}", str(TRUSTED_KIT))
                   for item in template["sandbox"]["excludedCommands"]}
        sandbox: dict[str, Any] = {}
        permissions: dict[str, Any] = {}
        exclusions: set[str] = set()
        edit_denies: set[str] = set()
        for settings in (project, local):
            current = settings.get("sandbox", {})
            permission = settings.get("permissions", {})
            if not isinstance(current, dict) or not isinstance(permission, dict):
                raise ValueError("malformed protection object")
            fs = current.get("filesystem", {})
            if not isinstance(fs, dict):
                raise ValueError("malformed filesystem object")
            if "disabled" in fs and fs["disabled"] is not False:
                raise ValueError("disabled filesystem protection")
            for key in ("excludedCommands",):
                values = current.get(key, [])
                if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                    raise ValueError("malformed exclusion list")
                exclusions.update(values)
            sandbox.update({k: v for k, v in current.items() if k != "filesystem"})
            denies = permission.get("deny", [])
            if not isinstance(denies, list) or any(not isinstance(v, str) for v in denies):
                raise ValueError("malformed permission deny list")
            edit_denies.update(denies)
            permissions.update(permission)
        project_fs = project.get("sandbox", {}).get("filesystem", {})
        deny = project_fs.get("denyWrite", [])
        if not isinstance(deny, list) or any(not isinstance(v, str) for v in deny):
            raise ValueError("malformed write block")
        if str(root / ".agents/loop") not in deny:
            raise ValueError("actual project loop folder lacks its write block")
        overlay_fs = local.get("sandbox", {}).get("filesystem", {})
        if "denyWrite" in overlay_fs:
            value = overlay_fs["denyWrite"]
            if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
                raise ValueError("malformed overlay write block")
        if (sandbox.get("enabled") is not True or sandbox.get("failIfUnavailable") is not True
                or sandbox.get("allowUnsandboxedCommands") is not False):
            raise ValueError("sandbox protection is absent or weakened")
        if (permissions.get("disableBypassPermissionsMode") != "disable"
                or permissions.get("defaultMode") == "bypassPermissions"):
            raise ValueError("permission bypass is available")
        required = {"Edit(//**/.agents/loop/local.json)",
                    "Edit(//**/.claude/settings.json)", "Edit(//**/.claude/settings.local.json)",
                    "Edit(/" + str(TRUSTED_KIT) + "/**)"}
        if not required <= edit_denies:
            raise ValueError("cache, settings or installed code lack their Edit deny rules")
        if str(TRUSTED_KIT) not in deny:
            raise ValueError("the trusted installed kit lacks its write block")
        if not exclusions <= allowed:
            raise ValueError("extra unsandboxed commands escape cache protection")
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise refuse(paths, str(error)) from error


def binding(paths: Paths) -> dict[str, Any]:
    literal = github.literal_origin(paths)
    owner, repo = github.origin_identity(paths, literal=literal)
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    try:
        done = subprocess.run(["git", "-C", str(paths.root), "rev-parse", "--git-common-dir"],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=5, check=False, env=env)
        if done.returncode or len(done.stdout.splitlines()) != 1:
            raise ValueError("no common Git directory")
        common = (paths.root / done.stdout.strip()).resolve()
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise refuse(paths, "the common Git directory cannot be verified") from error
    return {"root": str(paths.root.resolve()), "common_git": str(common),
            "repository": f"{owner}/{repo}", "literal_origin": literal}


def atomic(paths: Paths, value: dict[str, Any]) -> None:
    target = paths.local_settings
    regular(paths, target)
    regular(paths, target.parent, directory=True)
    try:
        text = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        if len(text.encode("utf-8")) > LIMIT:
            raise ValueError("oversized protected settings")
        target.parent.mkdir(parents=True, exist_ok=True)
        regular(paths, target.parent, directory=True)
        handle, name = tempfile.mkstemp(prefix=".person-reads-", dir=target.parent)
        temporary = Path(name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(text + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, target.stat().st_mode & 0o777 if target.exists() else 0o600)
            regular(paths, target)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    except (OSError, ValueError) as error:
        raise refuse(paths, "the complete protected generation could not be published") from error


def invalidate(paths: Paths) -> None:
    protection(paths)
    existing = object_file(paths, paths.local_settings, optional=True)
    existing.pop("github_reads", None)
    atomic(paths, existing)


def issue(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("malformed issue")
    number = value.get("number")
    if type(number) is not int or number <= 0:
        raise ValueError("malformed issue number")
    labels = value.get("labels")
    if not isinstance(labels, list):
        raise ValueError("malformed labels")
    names = [item.get("name") if isinstance(item, dict) else item for item in labels]
    if any(not isinstance(item, str) for item in names) or len(names) != len(set(names)):
        raise ValueError("malformed or duplicate labels")
    if ("body" not in value
            or not isinstance(value.get("updated_at"), str)
            or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
                                value["updated_at"])
            or value.get("state") not in ("open", "closed")
            or any(not isinstance(value.get(key), str) for key in ("title", "updated_at"))
            or (value.get("body") is not None and not isinstance(value.get("body"), str))):
        raise ValueError("malformed issue fields")
    return {"number": number, "title": value["title"], "body": value.get("body") or "",
            "labels": names, "state": value["state"], "updated_at": value["updated_at"]}


def collect(
    paths: Paths, person: Any, *, expected_identity: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Collect complete finite GET data; never publish it or send remote writes."""
    protection(paths)
    identity = binding(paths)
    if expected_identity is not None and identity != expected_identity:
        raise refuse(paths, "repository identity changed after invalidation")
    prefix = "repos/" + identity["repository"]
    started = time.monotonic()
    response_bytes = 0

    def read(endpoint: str) -> Any:
        nonlocal response_bytes
        remaining = 180 - (time.monotonic() - started)
        if remaining <= 0:
            raise ValueError("collection deadline exceeded")
        if isinstance(person, github.GitHub):
            answer = person.person_read(endpoint, timeout=min(30, remaining))
        else:
            answer = person.api_json(endpoint)
        response_bytes += len(json.dumps(answer, allow_nan=False).encode("utf-8"))
        if response_bytes > RESPONSE_LIMIT:
            raise ValueError("response budget exceeded")
        if time.monotonic() - started > 180:
            raise ValueError("collection deadline exceeded")
        return answer

    def pages(endpoint: str, limit: int) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        ids: set[int] = set()
        join = "&" if "?" in endpoint else "?"
        for page in range(1, limit // 100 + 2):
            batch = read(f"{endpoint}{join}per_page=100&page={page}")
            if not isinstance(batch, list) or len(batch) > 100:
                raise ValueError("malformed page")
            for item in batch:
                if not isinstance(item, dict):
                    raise ValueError("malformed page item")
                identifier = item.get("id")
                if type(identifier) is not int or identifier <= 0 or identifier in ids:
                    raise ValueError("duplicate or malformed page identity")
                ids.add(identifier)
                result.append(item)
                if len(result) > limit:
                    raise ValueError("page bound exceeded")
            if len(batch) < 100:
                return result
        raise ValueError("no terminal page")

    def repository() -> int:
        value = read(prefix)
        if (not isinstance(value, dict) or type(value.get("id")) is not int or value["id"] <= 0
                or value.get("full_name", "").lower() != identity["repository"].lower()):
            raise ValueError("repository identity is malformed or changed")
        return int(value["id"])

    try:
        repo_id = repository()
        catalogue = pages(prefix + "/issues?state=all", 500)
        issues: dict[str, Any] = {}
        catalogue_numbers: list[int] = []
        for raw in catalogue:
            if "pull_request" in raw:
                continue
            normal = issue(raw)
            key = str(normal["number"])
            if key in issues:
                raise ValueError("duplicate issue number")
            issues[key] = normal
            catalogue_numbers.append(normal["number"])
        pending = list(catalogue_numbers)
        visited: set[int] = set()
        edges = 0
        while pending:
            number = pending.pop(0)
            if number in visited:
                continue
            visited.add(number)
            if len(visited) > 500:
                raise ValueError("dependency node bound exceeded")
            key = str(number)
            previous = issues.get(key)
            try:
                raw = read(f"{prefix}/issues/{number}")
            except github.GitHubError as error:
                if not error.not_found:
                    raise
                issues[key] = None
                continue
            if isinstance(raw, dict) and "pull_request" in raw:
                issues[key] = {"number": number, "title": "", "body": "", "labels": [],
                               "state": "closed", "updated_at": "1970-01-01T00:00:00Z",
                               "blocked_by": [], "reason": None}
                continue
            normal = issue(raw)
            if normal["number"] != number:
                raise ValueError("dependency identity disagrees")
            if previous is not None and any(previous.get(k) != v for k, v in normal.items()):
                raise ValueError("issue changed during collection")
            issues[key] = normal
            blockers = pages(f"{prefix}/issues/{number}/dependencies/blocked_by", 500)
            linked: list[int] = []
            for raw in blockers:
                normal = issue(raw)
                blocker = normal["number"]
                if blocker in linked:
                    raise ValueError("duplicate dependency number")
                linked.append(blocker)
                old = issues.get(str(blocker))
                if str(blocker) in issues and old is None:
                    raise ValueError("missing dependency later appears")
                if old is not None and any(old.get(k) != v for k, v in normal.items()):
                    raise ValueError("inconsistent repeated issue")
                issues.setdefault(str(blocker), normal)
            edges += len(linked)
            if edges > 5000:
                raise ValueError("dependency edge bound exceeded")
            issues[key]["blocked_by"] = linked
            pending.extend(linked)
            reason = None
            if "state:dropped" in issues[key]["labels"]:
                comments = pages(f"{prefix}/issues/{number}/comments", 500)
                for comment in comments:
                    body = comment.get("body")
                    if not isinstance(body, str):
                        raise ValueError("malformed comment")
                    found = re.search(r"Reason:\s*(.+)", body)
                    if found and "dropped" in body.lower():
                        reason = found.group(1).strip()
            issues[key]["reason"] = reason
        if pages(prefix + "/issues?state=all", 500) != catalogue or repository() != repo_id:
            raise ValueError("repository or catalogue changed during collection")
        if binding(paths) != identity:
            raise ValueError("local repository identity changed during collection")
        value = {"schema": 1, "complete": True, **identity, "repository_id": repo_id,
                 "collected_at": time.time(), "catalogue": catalogue_numbers, "issues": issues}
        validate(paths, value, now=value["collected_at"])
        return value
    except (ValueError, TypeError, KeyError) as error:
        raise refuse(paths, str(error)) from error


def validate(paths: Paths, value: Any, *, now: float) -> dict[str, Any]:
    try:
        if (not isinstance(value, dict) or type(value.get("schema")) is not int
                or value.get("schema") != 1 or value.get("complete") is not True):
            raise ValueError("missing complete generation")
        if any(value.get(k) != v for k, v in binding(paths).items()):
            raise ValueError("foreign project or repository identity")
        issued = value.get("collected_at")
        if not isinstance(issued, (int, float)) or type(issued) not in (int, float):
            raise ValueError("expired or future generation")
        if not 0 <= now - issued <= TTL:
            raise ValueError("expired or future generation")
        if type(value.get("repository_id")) is not int or value["repository_id"] <= 0:
            raise ValueError("malformed recorded repository ID")
        catalogue = value.get("catalogue")
        issues = value.get("issues")
        if (not isinstance(catalogue, list) or len(catalogue) > 500
                or any(type(n) is not int or n <= 0 for n in catalogue)
                or len(catalogue) != len(set(catalogue))
                or not isinstance(issues, dict) or len(issues) > 500):
            raise ValueError("malformed catalogue or closure")
        edges = 0
        for key, raw in issues.items():
            if not isinstance(key, str) or not re.fullmatch(r"[1-9][0-9]*", key):
                raise ValueError("malformed issue key")
            if raw is None:
                continue
            normal = issue(raw)
            if str(normal["number"]) != key:
                raise ValueError("issue key disagrees")
            links = raw.get("blocked_by")
            if (not isinstance(links, list) or len(links) > 500
                    or any(type(n) is not int or str(n) not in issues for n in links)
                    or len(links) != len(set(links))):
                raise ValueError("incomplete dependency closure")
            edges += len(links)
            if ("reason" not in raw
                    or (raw["reason"] is not None and not isinstance(raw["reason"], str))):
                raise ValueError("malformed dropped reason")
        if edges > 5000 or any(issues.get(str(n)) is None for n in catalogue):
            raise ValueError("incomplete catalogue or oversized graph")
        if len(json.dumps(value, allow_nan=False).encode("utf-8")) > LIMIT:
            raise ValueError("oversized generation")
        return value
    except (ValueError, TypeError, KeyError) as error:
        raise refuse(paths, str(error)) from error


def publish(paths: Paths, value: dict[str, Any]) -> None:
    protection(paths)
    validate(paths, value, now=time.time())
    existing = object_file(paths, paths.local_settings, optional=True)
    existing["github_reads"] = value
    atomic(paths, existing)


@dataclass(frozen=True)
class Snapshot:
    issues: dict[str, Any]
    catalogue: list[int]
    age_seconds: int

    def read_issue(self, number: int) -> dict[str, Any]:
        value = self.issues.get(str(number))
        if value is None:
            raise github.GitHubError("recorded issue does not exist", next_command="sync again",
                                     not_found=True)
        return dict(value)


def load(paths: Paths, *, now: float | None = None) -> Snapshot:
    protection(paths)
    value = object_file(paths, paths.local_settings).get("github_reads")
    current = time.time() if now is None else now
    generation = validate(paths, value, now=current)
    return Snapshot(generation["issues"], generation["catalogue"],
                    int(current - generation["collected_at"]))
