#!/usr/bin/env python3
# contract: agent
"""dependency-check.py: judge the new packages in a lockfile change.

Give it the lockfile now (`--lockfile`) and the lockfile before the change
(`--before FILE` or `--base-ref GIT-REF`). It finds each package and version
that is new, asks the registry when it was released and under what licence, and
refuses what is too new or has no allowed licence.

It reads npm (`package-lock.json`), pnpm (`pnpm-lock.yaml`) and uv (`uv.lock`).
The registry is a web address, or a folder shaped like tests/stand-ins/fake-registry.
It changes nothing, so it has no `--dry-run`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loop.cli import ExitCode, Failure, run

DEFAULT_MIN_AGE_DAYS = 30
DEFAULT_ALLOWED = (
    "MIT",
    "ISC",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "Apache-2.0",
    "0BSD",
    "Unlicense",
    "CC0-1.0",
    "MPL-2.0",
    "BlueOak-1.0.0",
    "Python-2.0",
    "PSF-2.0",
)
DEFAULT_REGISTRY = {"npm": "https://registry.npmjs.org", "pnpm": "https://registry.npmjs.org"}
PYPI = "https://pypi.org"
LOCKFILES = {"package-lock.json": "npm", "pnpm-lock.yaml": "pnpm", "uv.lock": "uv"}
TIMEOUT_SECONDS = 20

# Words some packages use for a licence that SPDX writes another way.
ALIASES = {
    "mit license": "MIT",
    "the mit license": "MIT",
    "isc license": "ISC",
    "apache license 2.0": "Apache-2.0",
    "apache software license": "Apache-2.0",
    "apache-2": "Apache-2.0",
}
CLASSIFIERS = {
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: ISC License (ISCL)": "ISC",
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: BSD License": "BSD-3-Clause",
}


@dataclass(frozen=True)
class Package:
    name: str
    version: str
    from_registry: bool = True


@dataclass(frozen=True)
class Release:
    released: datetime | None
    licence: str | None


class NotFound(Exception):
    """The registry has no such package or version."""


# --- reading lockfiles -----------------------------------------------------------


def detect_manager(path: Path) -> str:
    manager = LOCKFILES.get(path.name)
    if manager is None:
        raise Failure(
            f"cannot tell the package manager from the file name {path.name!r}",
            next_command="dependency-check.py --manager npm|pnpm|uv --lockfile <file>",
            code=ExitCode.USAGE,
        )
    return manager


def _npm_name(key: str) -> str:
    return key.rsplit("node_modules/", 1)[-1]


def _npm_old_format(tree: dict[str, Any], found: dict[tuple[str, str], Package]) -> None:
    for name, entry in tree.items():
        version = entry.get("version")
        if isinstance(version, str):
            found[(name, version)] = Package(name, version, True)
        _npm_old_format(entry.get("dependencies") or {}, found)


def _parse_npm(text: str) -> dict[tuple[str, str], Package]:
    data = json.loads(text)
    found: dict[tuple[str, str], Package] = {}
    for key, entry in (data.get("packages") or {}).items():
        if not key or entry.get("link"):
            continue
        version = entry.get("version")
        if not isinstance(version, str):
            continue
        resolved = entry.get("resolved")
        from_registry = resolved is None or str(resolved).startswith(("http://", "https://"))
        name = entry.get("name") if isinstance(entry.get("name"), str) else _npm_name(key)
        found[(name, version)] = Package(name, version, from_registry)
    if not data.get("packages"):
        _npm_old_format(data.get("dependencies") or {}, found)
    return found


def _split_pnpm_key(key: str) -> tuple[str, str] | None:
    key = key.strip().strip("'\"").lstrip("/")
    old_style = re.fullmatch(r"(.+)/(\d[^/]*)", key)  # lockfile 5: /name/version_peer
    if old_style:
        return old_style.group(1), old_style.group(2).split("_", 1)[0]
    key = re.sub(r"\(.*$", "", key)  # peer suffix in lockfile 6 and 9
    at = key.rfind("@")
    if at > 0:
        return key[:at], key[at + 1 :]
    return None


def _parse_pnpm(text: str) -> dict[tuple[str, str], Package]:
    found: dict[tuple[str, str], Package] = {}
    in_packages = False
    for line in text.splitlines():
        if re.match(r"^\S", line):
            in_packages = line.rstrip() == "packages:"
            continue
        if not in_packages:
            continue
        match = re.match(r"^  (\S.*):\s*$", line)
        if not match:
            continue
        pair = _split_pnpm_key(match.group(1))
        if pair and pair[1]:
            found[pair] = Package(pair[0], pair[1], True)
    return found


def _parse_uv(text: str) -> dict[tuple[str, str], Package]:
    found: dict[tuple[str, str], Package] = {}
    for block in re.split(r"^\[\[package\]\]\s*$", text, flags=re.MULTILINE)[1:]:
        block = re.split(r"^\[", block, maxsplit=1, flags=re.MULTILINE)[0]
        name = re.search(r'^name = "([^"]+)"', block, re.MULTILINE)
        version = re.search(r'^version = "([^"]+)"', block, re.MULTILINE)
        source = re.search(r"^source = \{ *(\w+)", block, re.MULTILINE)
        if not name or not version:
            continue
        kind = source.group(1) if source else "registry"
        if kind in ("virtual", "editable", "directory"):
            continue  # the project itself, not a download
        pypi_name = re.sub(r"[-_.]+", "-", name.group(1)).lower()
        found[(pypi_name, version.group(1))] = Package(
            pypi_name, version.group(1), kind == "registry"
        )
    return found


def parse_lockfile(manager: str, text: str) -> dict[tuple[str, str], Package]:
    """Every package and version a lockfile holds."""
    try:
        if manager == "npm":
            return _parse_npm(text)
        if manager == "pnpm":
            return _parse_pnpm(text)
        if manager == "uv":
            return _parse_uv(text)
    except (ValueError, AttributeError) as error:
        raise Failure(
            f"cannot read the {manager} lockfile ({error})",
            next_command="dependency-check.py --help",
            code=ExitCode.ENVIRONMENT,
        ) from error
    raise Failure(
        f"unknown package manager {manager!r}",
        next_command="dependency-check.py --manager npm|pnpm|uv --lockfile <file>",
        code=ExitCode.USAGE,
    )


def added(
    before: dict[tuple[str, str], Package], after: dict[tuple[str, str], Package]
) -> list[Package]:
    """The packages and versions in `after` that `before` does not hold."""
    return [after[key] for key in sorted(after) if key not in before]


# --- the registry ----------------------------------------------------------------


def _parse_time(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _npm_licence(entry: dict[str, Any]) -> str | None:
    licence = entry.get("license")
    if isinstance(licence, dict):
        licence = licence.get("type")
    if isinstance(licence, str) and licence.strip():
        return licence.strip()
    old = entry.get("licenses")
    if isinstance(old, list) and old:
        raw = [x.get("type") if isinstance(x, dict) else x for x in old]
        types = [t for t in raw if isinstance(t, str)]
        if types:
            return " OR ".join(types)
    return None


def _pypi_licence(info: dict[str, Any]) -> str | None:
    expression = info.get("license_expression")
    if isinstance(expression, str) and expression.strip():
        return expression.strip()
    text = info.get("license")
    if isinstance(text, str) and text.strip() and len(text) <= 80 and "\n" not in text:
        return text.strip()
    for classifier in info.get("classifiers") or []:
        if classifier in CLASSIFIERS:
            return CLASSIFIERS[classifier]
    return None


class Registry:
    """Answers the age and licence of a package version.

    `base` is a web address or a folder. A folder holds `npm/<name>.json` and
    `pypi/<name>/<version>.json`, in the shape the real registries answer.
    """

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.is_web = self.base.startswith(("http://", "https://"))

    def _fetch(self, folder_path: Path, url: str) -> dict[str, Any]:
        try:
            if self.is_web:
                with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as reply:
                    data = json.load(reply)
            else:
                data = json.loads(folder_path.read_text(encoding="utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise NotFound(url) from error
            raise self._unreachable(url, f"HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            if isinstance(error, FileNotFoundError):
                raise NotFound(str(folder_path)) from error
            raise self._unreachable(url if self.is_web else str(folder_path), str(error)) from error
        except ValueError as error:
            raise self._unreachable(url, f"not JSON ({error})") from error
        if not isinstance(data, dict):
            raise self._unreachable(url, "not a JSON object")
        return data

    def _unreachable(self, where: str, why: str) -> Failure:
        return Failure(
            f"cannot read the registry at {where} ({why})",
            next_command="dependency-check.py --registry <web address or folder> ...",
            code=ExitCode.ENVIRONMENT,
        )

    def lookup(self, manager: str, name: str, version: str) -> Release:
        if manager == "uv":
            return self._pypi(name, version)
        return self._npm(name, version)

    def _npm(self, name: str, version: str) -> Release:
        data = self._fetch(
            Path(self.base) / "npm" / f"{name}.json",
            f"{self.base}/{urllib.parse.quote(name, safe='@')}",
        )
        versions = data.get("versions") or {}
        if version not in versions:
            raise NotFound(f"{name}@{version}")
        released = _parse_time((data.get("time") or {}).get(version))
        return Release(released, _npm_licence(versions[version]))

    def _pypi(self, name: str, version: str) -> Release:
        data = self._fetch(
            Path(self.base) / "pypi" / name / f"{version}.json",
            f"{self.base}/pypi/{urllib.parse.quote(name)}/{urllib.parse.quote(version)}/json",
        )
        times = [_parse_time(u.get("upload_time_iso_8601")) for u in data.get("urls") or []]
        known = [t for t in times if t is not None]
        return Release(min(known) if known else None, _pypi_licence(data.get("info") or {}))


# --- judging ---------------------------------------------------------------------


def _tokens(expression: str) -> list[str]:
    return re.findall(r"\(|\)|[^\s()]+", expression)


def licence_allowed(expression: str, allowed: list[str] | tuple[str, ...]) -> bool:
    """True when the SPDX expression is covered by the allowed list.

    `A OR B` needs one side allowed. `A AND B` needs both. Anything that does not
    read cleanly is not allowed.
    """
    names = {item.lower() for item in allowed}
    tokens = _tokens(ALIASES.get(expression.strip().lower(), expression))
    position = 0

    def peek() -> str | None:
        return tokens[position] if position < len(tokens) else None

    def take() -> str:
        nonlocal position
        position += 1
        return tokens[position - 1]

    def atom() -> bool:
        token = peek()
        if token is None or token.upper() in ("AND", "OR", ")"):
            raise ValueError("expected a licence")
        take()
        if token == "(":
            value = either()
            if peek() != ")":
                raise ValueError("missing )")
            take()
            return value
        return token.rstrip("+").lower() in names or token.lower() in names

    def both() -> bool:
        value = atom()
        while peek() is not None and str(peek()).upper() == "AND":
            take()
            right = atom()
            value = value and right
        return value

    def either() -> bool:
        value = both()
        while peek() is not None and str(peek()).upper() == "OR":
            take()
            right = both()
            value = value or right
        return value

    try:
        result = either()
        return result and position == len(tokens)
    except ValueError:
        return False


def judge(
    package: Package,
    registry: Registry,
    now: datetime,
    min_age_days: int,
    allowed: list[str] | tuple[str, ...],
    manager: str = "npm",
) -> list[str]:
    """What is wrong with this package, as plain sentences. Empty means accepted."""
    label = f"{package.name}@{package.version}"
    if not package.from_registry:
        return [f"{label} does not come from the registry, so its age and licence cannot be read"]
    try:
        release = registry.lookup(manager, package.name, package.version)
    except NotFound:
        return [f"{label} was not found in the registry"]
    problems: list[str] = []
    if release.released is None:
        problems.append(f"{label} has no release date in the registry")
    else:
        age = now - release.released
        if age.total_seconds() < min_age_days * 86400:
            problems.append(f"{label} is {age.days} days old, and the limit is {min_age_days} days")
    if release.licence is None:
        problems.append(f"{label} has no licence in the registry")
    elif not licence_allowed(release.licence, allowed):
        problems.append(f"{label} has the licence {release.licence}, which is not allowed")
    return problems


# --- the command -----------------------------------------------------------------


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--lockfile", required=True, help="the lockfile after the change")
    parser.add_argument(
        "--manager", choices=["npm", "pnpm", "uv"], help="default: from the file name"
    )
    parser.add_argument("--before", help="the lockfile before the change")
    parser.add_argument(
        "--base-ref",
        help="read the lockfile before the change from this Git ref (a missing file means empty)",
    )
    parser.add_argument(
        "--registry", help="a web address or a folder (default: the public registry)"
    )
    parser.add_argument(
        "--min-age-days",
        type=int,
        default=DEFAULT_MIN_AGE_DAYS,
        help=f"refuse a release younger than this (default {DEFAULT_MIN_AGE_DAYS})",
    )
    parser.add_argument(
        "--allow-licence",
        action="append",
        default=[],
        metavar="SPDX",
        help="allow one more licence (repeat for more)",
    )
    parser.add_argument("--now", help="the time to measure age from, as ISO 8601 (default: now)")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise Failure(
            f"cannot read {path} ({error.strerror})",
            next_command="dependency-check.py --lockfile <an existing lockfile> ...",
            code=ExitCode.ENVIRONMENT,
        ) from error


def _from_ref(ref: str, lockfile: Path) -> str:
    folder = lockfile.resolve().parent
    try:
        top = subprocess.run(
            ["git", "-C", str(folder), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if top.returncode != 0:
            raise OSError(top.stderr.strip() or "not a Git repository")
        relative = lockfile.resolve().relative_to(Path(top.stdout.strip()).resolve())
        exists = subprocess.run(
            ["git", "-C", str(folder), "cat-file", "-e", f"{ref}:{relative.as_posix()}"],
            capture_output=True,
            check=False,
        )
        if exists.returncode != 0:
            ref_ok = subprocess.run(
                ["git", "-C", str(folder), "rev-parse", "--verify", "--quiet", ref],
                capture_output=True,
                check=False,
            )
            if ref_ok.returncode != 0:
                raise OSError(f"{ref} is not a Git ref")
            return ""  # the file is new in this change
        shown = subprocess.run(
            ["git", "-C", str(folder), "show", f"{ref}:{relative.as_posix()}"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise Failure(
            f"cannot read the lockfile at {ref} ({error})",
            next_command="dependency-check.py --before <file> --lockfile <file>",
            code=ExitCode.ENVIRONMENT,
        ) from error
    return shown.stdout


def check(args: argparse.Namespace) -> dict[str, Any]:
    lockfile = Path(args.lockfile)
    manager = args.manager or detect_manager(lockfile)
    if args.min_age_days < 0:
        raise Failure(
            "--min-age-days cannot be negative",
            next_command="dependency-check.py --help",
            code=ExitCode.USAGE,
        )
    if args.now:
        now = _parse_time(args.now)
        if now is None:
            raise Failure(
                f"{args.now!r} is not an ISO 8601 time",
                next_command="dependency-check.py --now 2026-10-06T00:00:00Z ...",
                code=ExitCode.USAGE,
            )
    else:
        now = datetime.now(timezone.utc)

    after_text = _read(lockfile)
    if args.before:
        before_text = _read(Path(args.before))
    elif args.base_ref:
        before_text = _from_ref(args.base_ref, lockfile)
    else:
        raise Failure(
            "say what the lockfile was before: --before <file> or --base-ref <git ref>",
            next_command="dependency-check.py --lockfile <file> --base-ref origin/main",
            code=ExitCode.USAGE,
        )
    before = parse_lockfile(manager, before_text) if before_text.strip() else {}
    new_packages = added(before, parse_lockfile(manager, after_text))

    registry = Registry(args.registry or DEFAULT_REGISTRY.get(manager, PYPI))
    if args.registry is None and manager == "uv":
        registry = Registry(PYPI)
    allowed = [*DEFAULT_ALLOWED, *args.allow_licence]
    findings = []
    for package in new_packages:
        for problem in judge(package, registry, now, args.min_age_days, allowed, manager):
            findings.append({"name": package.name, "version": package.version, "problem": problem})
    summary = {
        "manager": manager,
        "min_age_days": args.min_age_days,
        "added": [{"name": p.name, "version": p.version} for p in new_packages],
        "findings": findings,
    }
    if findings:
        raise Failure(
            f"{len(findings)} problem(s) in {len(new_packages)} new package(s): "
            + "; ".join(f["problem"] for f in findings),
            next_command=(
                "pick another package, wait until the release is old enough, or ask the person "
                "to approve it with --allow-licence <SPDX> or a lower --min-age-days"
            ),
            code=ExitCode.REFUSED,
            data=summary,
        )
    return summary


def main(argv: list[str]) -> int:
    return run(
        "dependency-check.py",
        "Judge the age and licence of each new package in a lockfile change.",
        setup,
        check,
        argv,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
