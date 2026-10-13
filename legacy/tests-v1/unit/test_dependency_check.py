"""Unit tests for kit/scripts/dependency-check.py.

The registry is the stand-in under tests/stand-ins/fake-registry. Nothing here
uses the network. One test serves the stand-in on 127.0.0.1 to cover the HTTP
path, and that never leaves this computer.
"""

from __future__ import annotations

import http.server
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "kit" / "scripts" / "dependency-check.py"
REGISTRY = ROOT / "tests" / "stand-ins" / "fake-registry"
NOW = "2026-10-06T00:00:00Z"
ALLOWED = ["MIT", "ISC", "Apache-2.0", "BSD-3-Clause"]

sys.path.insert(0, str(ROOT / "kit" / "scripts"))


def load() -> Any:
    spec = importlib.util.spec_from_file_location("dependency_check", SCRIPT)
    assert spec is not None and spec.loader is not None, "dependency-check.py is missing"
    module = importlib.util.module_from_spec(spec)
    sys.modules["dependency_check"] = module
    spec.loader.exec_module(module)
    return module


dc = load()

NPM_BEFORE = {
    "lockfileVersion": 3,
    "packages": {
        "": {"name": "demo", "version": "1.0.0"},
        "node_modules/old-mit": {
            "version": "1.0.0",
            "resolved": "https://registry.npmjs.org/x.tgz",
        },
    },
}
NPM_AFTER = {
    "lockfileVersion": 3,
    "packages": {
        "": {"name": "demo", "version": "1.0.0"},
        "node_modules/old-mit": {
            "version": "1.0.0",
            "resolved": "https://registry.npmjs.org/x.tgz",
        },
        "node_modules/fresh-mit": {
            "version": "2.0.0",
            "resolved": "https://registry.npmjs.org/y.tgz",
        },
        "node_modules/@scope/pkg": {
            "version": "1.2.3",
            "resolved": "https://registry.npmjs.org/z.tgz",
        },
        "node_modules/old-mit/node_modules/dual": {
            "version": "1.1.0",
            "resolved": "https://registry.npmjs.org/d.tgz",
        },
        "node_modules/linked": {"resolved": "packages/linked", "link": True},
    },
}

PNPM_V9_BEFORE = """lockfileVersion: '9.0'

importers:
  .:
    dependencies:
      old-mit:
        specifier: ^1.0.0
        version: 1.0.0

packages:

  old-mit@1.0.0:
    resolution: {integrity: sha512-aaa}

snapshots:

  old-mit@1.0.0: {}
"""
PNPM_V9_AFTER = """lockfileVersion: '9.0'

importers:
  .:
    dependencies:
      old-mit:
        specifier: ^1.0.0
        version: 1.0.0

packages:

  '@scope/pkg@1.2.3':
    resolution: {integrity: sha512-bbb}

  fresh-mit@2.0.0:
    resolution: {integrity: sha512-ccc}

  old-mit@1.0.0:
    resolution: {integrity: sha512-aaa}

snapshots:

  old-mit@1.0.0: {}
"""
PNPM_V6_AFTER = """lockfileVersion: '6.0'

packages:

  /@scope/pkg@1.2.3(peer@2.0.0):
    resolution: {integrity: sha512-bbb}
    dev: false

  /old-mit@1.0.0:
    resolution: {integrity: sha512-aaa}
    dev: false
"""
PNPM_V5_AFTER = """lockfileVersion: 5.4

packages:

  /@scope/pkg/1.2.3_peer@2.0.0:
    resolution: {integrity: sha512-bbb}

  /old-mit/1.0.0:
    resolution: {integrity: sha512-aaa}
"""

UV_BEFORE = """version = 1
revision = 3
requires-python = ">=3.10"

[[package]]
name = "demo"
version = "0.1.0"
source = { virtual = "." }
dependencies = [
    { name = "oldpy" },
]

[[package]]
name = "oldpy"
version = "1.0.0"
source = { registry = "https://pypi.org/simple" }
"""
UV_AFTER = (
    UV_BEFORE
    + """
[[package]]
name = "FreshPy"
version = "0.1.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "classpy"
version = "1.0.0"
source = { registry = "https://pypi.org/simple" }
"""
)


def keys(packages: list) -> set[tuple[str, str]]:  # type: ignore[type-arg]
    return {(p.name, p.version) for p in packages}


class DiffTests(unittest.TestCase):
    def test_npm_diff_finds_added_packages(self) -> None:
        before = dc.parse_lockfile("npm", json.dumps(NPM_BEFORE))
        after = dc.parse_lockfile("npm", json.dumps(NPM_AFTER))
        self.assertEqual(
            keys(dc.added(before, after)),
            {("fresh-mit", "2.0.0"), ("@scope/pkg", "1.2.3"), ("dual", "1.1.0")},
        )

    def test_npm_diff_counts_a_new_version_of_a_known_package(self) -> None:
        bumped = json.loads(json.dumps(NPM_BEFORE))
        bumped["packages"]["node_modules/old-mit"]["version"] = "1.0.1"
        found = dc.added(
            dc.parse_lockfile("npm", json.dumps(NPM_BEFORE)),
            dc.parse_lockfile("npm", json.dumps(bumped)),
        )
        self.assertEqual(keys(found), {("old-mit", "1.0.1")})

    def test_npm_diff_reads_the_old_nested_format(self) -> None:
        old = {
            "lockfileVersion": 1,
            "dependencies": {
                "a": {"version": "1.0.0", "dependencies": {"b": {"version": "2.0.0"}}}
            },
        }
        found = dc.parse_lockfile("npm", json.dumps(old))
        self.assertEqual(set(found), {("a", "1.0.0"), ("b", "2.0.0")})

    def test_npm_git_source_is_flagged_as_not_from_the_registry(self) -> None:
        lock = {
            "packages": {"node_modules/x": {"version": "1.0.0", "resolved": "git+ssh://h/x.git"}}
        }
        found = dc.parse_lockfile("npm", json.dumps(lock))
        self.assertFalse(found[("x", "1.0.0")].from_registry)

    def test_pnpm_diff_finds_added_packages_in_each_format(self) -> None:
        before = dc.parse_lockfile("pnpm", PNPM_V9_BEFORE)
        after9 = dc.parse_lockfile("pnpm", PNPM_V9_AFTER)
        self.assertEqual(
            keys(dc.added(before, after9)), {("@scope/pkg", "1.2.3"), ("fresh-mit", "2.0.0")}
        )
        for text in (PNPM_V6_AFTER, PNPM_V5_AFTER):
            after = dc.parse_lockfile("pnpm", text)
            self.assertEqual(
                keys(dc.added(before, after)), {("@scope/pkg", "1.2.3")}, msg=text[:30]
            )

    def test_pnpm_importers_are_not_read_as_packages(self) -> None:
        found = dc.parse_lockfile("pnpm", PNPM_V9_BEFORE)
        self.assertEqual(set(found), {("old-mit", "1.0.0")})

    def test_uv_diff_finds_added_packages_and_skips_the_project(self) -> None:
        before = dc.parse_lockfile("uv", UV_BEFORE)
        after = dc.parse_lockfile("uv", UV_AFTER)
        self.assertEqual(set(before), {("oldpy", "1.0.0")})
        self.assertEqual(
            keys(dc.added(before, after)), {("freshpy", "0.1.0"), ("classpy", "1.0.0")}
        )

    def test_an_empty_before_makes_every_package_new(self) -> None:
        after = dc.parse_lockfile("uv", UV_AFTER)
        self.assertEqual(len(dc.added({}, after)), 3)

    def test_the_manager_is_found_from_the_file_name(self) -> None:
        self.assertEqual(dc.detect_manager(Path("a/package-lock.json")), "npm")
        self.assertEqual(dc.detect_manager(Path("pnpm-lock.yaml")), "pnpm")
        self.assertEqual(dc.detect_manager(Path("uv.lock")), "uv")
        with self.assertRaises(dc.Failure):
            dc.detect_manager(Path("yarn.lock"))


class JudgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = dc.Registry(str(REGISTRY))
        self.now = datetime(2026, 10, 6, tzinfo=timezone.utc)

    def judge(self, manager: str, name: str, version: str) -> list[str]:
        package = dc.Package(name, version, True)
        return dc.judge(package, self.registry, self.now, 30, ALLOWED)  # type: ignore[no-any-return]

    def test_an_old_package_with_an_allowed_licence_passes(self) -> None:
        self.assertEqual(self.judge("npm", "old-mit", "1.0.0"), [])
        self.assertEqual(self.judge("npm", "@scope/pkg", "1.2.3"), [])

    def test_a_package_that_is_too_new_is_refused(self) -> None:
        problems = self.judge("npm", "fresh-mit", "2.0.0")
        self.assertEqual(len(problems), 1)
        self.assertIn("4 days old", problems[0])
        self.assertIn("30", problems[0])

    def test_an_unknown_licence_is_refused(self) -> None:
        problems = self.judge("npm", "old-gpl", "3.1.0")
        self.assertEqual(len(problems), 1)
        self.assertIn("GPL-3.0-only", problems[0])

    def test_a_missing_licence_is_refused(self) -> None:
        problems = self.judge("npm", "no-licence", "0.4.0")
        self.assertEqual(len(problems), 1)
        self.assertIn("no licence", problems[0])

    def test_a_choice_of_licences_passes_when_one_is_allowed(self) -> None:
        self.assertEqual(self.judge("npm", "dual", "1.1.0"), [])

    def test_the_old_licences_list_is_read(self) -> None:
        self.assertEqual(self.judge("npm", "legacy-licence", "1.0.0"), [])

    def test_a_package_the_registry_does_not_know_is_refused(self) -> None:
        problems = self.judge("npm", "not-a-package", "1.0.0")
        self.assertEqual(len(problems), 1)
        self.assertIn("not found", problems[0])

    def test_a_version_the_registry_does_not_know_is_refused(self) -> None:
        problems = self.judge("npm", "old-mit", "9.9.9")
        self.assertIn("not found", problems[0])

    def test_a_package_that_is_not_from_the_registry_is_refused(self) -> None:
        package = dc.Package("old-mit", "1.0.0", False)
        problems = dc.judge(package, self.registry, self.now, 30, ALLOWED)
        self.assertIn("registry", problems[0])

    def test_pypi_packages_are_judged_the_same_way(self) -> None:
        registry = dc.Registry(str(REGISTRY))
        cases = {
            ("oldpy", "1.0.0"): "",
            ("classpy", "1.0.0"): "",
            ("freshpy", "0.1.0"): "days old",
            ("weirdpy", "1.0.0"): "Proprietary",
            ("nolicencepy", "1.0.0"): "no licence",
            ("missingpy", "1.0.0"): "not found",
        }
        for (name, version), expect in cases.items():
            problems = dc.judge(
                dc.Package(name, version, True), registry, self.now, 30, ALLOWED, "uv"
            )
            if expect:
                self.assertEqual(len(problems), 1, msg=name)
                self.assertIn(expect, problems[0], msg=name)
            else:
                self.assertEqual(problems, [], msg=name)

    def test_the_age_limit_is_inclusive_at_the_boundary(self) -> None:
        # fresh-mit is released 2026-10-01T09:00. At 2026-10-31T09:00 it is 30 days old.
        edge = datetime(2026, 10, 31, 9, 0, tzinfo=timezone.utc)
        package = dc.Package("fresh-mit", "2.0.0", True)
        self.assertEqual(dc.judge(package, self.registry, edge, 30, ALLOWED), [])
        before = datetime(2026, 10, 31, 8, 59, tzinfo=timezone.utc)
        self.assertEqual(len(dc.judge(package, self.registry, before, 30, ALLOWED)), 1)

    def test_a_package_too_new_and_unlicensed_gets_both_findings(self) -> None:
        # Both faults are reported, so one run tells the whole story.
        registry = dc.Registry(str(REGISTRY))
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "npm").mkdir()
            (Path(folder) / "npm" / "both.json").write_text(
                json.dumps({"time": {"1.0.0": "2026-10-05T00:00:00Z"}, "versions": {"1.0.0": {}}})
            )
            registry = dc.Registry(folder)
            problems = dc.judge(dc.Package("both", "1.0.0", True), registry, self.now, 30, ALLOWED)
        self.assertEqual(len(problems), 2)


class LicenceTests(unittest.TestCase):
    def test_expressions(self) -> None:
        cases = [
            ("MIT", True),
            ("mit", True),
            ("GPL-3.0-only", False),
            ("(MIT OR GPL-3.0-only)", True),
            ("MIT AND GPL-3.0-only", False),
            ("MIT AND (ISC OR GPL-2.0-only)", True),
            ("MIT AND (GPL-3.0-only OR AGPL-3.0-only)", False),
            ("MIT OR", False),
            ("(MIT", False),
            ("", False),
            ("SEE LICENSE IN LICENSE.txt", False),
        ]
        for expression, expected in cases:
            self.assertEqual(
                dc.licence_allowed(expression, ALLOWED), expected, msg=repr(expression)
            )


class HttpRegistryTests(unittest.TestCase):
    def test_the_http_path_reads_what_the_folder_path_reads(self) -> None:
        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                return

            def translate_path(self, path: str) -> str:
                # npm asks for /<name>; the stand-in keeps npm/<name>.json
                # PyPI asks for /pypi/<name>/<version>/json; the stand-in keeps
                # pypi/<name>/<version>.json
                from urllib.parse import unquote

                parts = unquote(path.split("?")[0]).strip("/").split("/")
                if parts[0] == "pypi" and parts[-1] == "json":
                    return str(REGISTRY / "pypi" / parts[1] / f"{parts[2]}.json")
                return str(REGISTRY / "npm" / ("/".join(parts) + ".json"))

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            registry = dc.Registry(f"http://127.0.0.1:{server.server_address[1]}")
            now = datetime(2026, 10, 6, tzinfo=timezone.utc)
            self.assertEqual(
                dc.judge(dc.Package("@scope/pkg", "1.2.3", True), registry, now, 30, ALLOWED), []
            )
            self.assertEqual(
                dc.judge(dc.Package("oldpy", "1.0.0", True), registry, now, 30, ALLOWED, "uv"), []
            )
            problems = dc.judge(dc.Package("fresh-mit", "2.0.0", True), registry, now, 30, ALLOWED)
            self.assertIn("days old", problems[0])
            problems = dc.judge(dc.Package("nope", "1.0.0", True), registry, now, 30, ALLOWED)
            self.assertIn("not found", problems[0])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_a_registry_that_cannot_be_reached_is_an_environment_failure(self) -> None:
        registry = dc.Registry("http://127.0.0.1:1")
        now = datetime(2026, 10, 6, tzinfo=timezone.utc)
        with self.assertRaises(dc.Failure) as caught:
            dc.judge(dc.Package("x", "1.0.0", True), registry, now, 30, ALLOWED)
        self.assertEqual(int(caught.exception.code), 4)
        self.assertIn("next:", caught.exception.next_command + "next:")


class CommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(tempfile.mkdtemp())

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=self.folder,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            check=False,
            env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def lock(self, name: str, content: object) -> Path:
        path = self.folder / name
        path.write_text(content if isinstance(content, str) else json.dumps(content))
        return path

    def base_args(self) -> list[str]:
        return ["--registry", str(REGISTRY), "--now", NOW, "--json"]

    def test_a_clean_change_passes_and_lists_what_it_checked(self) -> None:
        before = self.lock("before.json", NPM_BEFORE)
        after_data = json.loads(json.dumps(NPM_AFTER))
        del after_data["packages"]["node_modules/fresh-mit"]
        after = self.lock("package-lock.json", after_data)
        done = self.run_script("--lockfile", str(after), "--before", str(before), *self.base_args())
        self.assertEqual(done.returncode, 0, msg=done.stderr)
        body = json.loads(done.stdout)
        self.assertTrue(body["ok"])
        self.assertEqual({p["name"] for p in body["added"]}, {"@scope/pkg", "dual"})
        self.assertEqual(body["findings"], [])

    def test_a_package_too_new_is_refused_with_exit_3_and_a_next_line(self) -> None:
        before = self.lock("before.json", NPM_BEFORE)
        after = self.lock("package-lock.json", NPM_AFTER)
        done = self.run_script("--lockfile", str(after), "--before", str(before), *self.base_args())
        self.assertEqual(done.returncode, 3, msg=done.stderr)
        body = json.loads(done.stdout)
        self.assertFalse(body["ok"])
        self.assertEqual([f["name"] for f in body["findings"]], ["fresh-mit"])
        self.assertIn("next:", done.stderr)

    def test_an_extra_allowed_licence_can_be_named(self) -> None:
        before = self.lock("before.json", {"packages": {}})
        after = self.lock(
            "package-lock.json",
            {"packages": {"node_modules/old-gpl": {"version": "3.1.0", "resolved": "https://r/x"}}},
        )
        refused = self.run_script(
            "--lockfile", str(after), "--before", str(before), *self.base_args()
        )
        self.assertEqual(refused.returncode, 3)
        allowed = self.run_script(
            "--lockfile", str(after), "--before", str(before),
            "--allow-licence", "GPL-3.0-only", *self.base_args(),
        )  # fmt: skip
        self.assertEqual(allowed.returncode, 0, msg=allowed.stderr)

    def test_a_missing_lockfile_is_an_environment_failure(self) -> None:
        done = self.run_script(
            "--lockfile", "package-lock.json", "--before", "x", *self.base_args()
        )
        self.assertEqual(done.returncode, 4)
        self.assertIn("next:", done.stderr)

    def test_no_arguments_is_a_usage_failure_with_a_next_line(self) -> None:
        done = self.run_script()
        self.assertEqual(done.returncode, 2)
        self.assertIn("next:", done.stderr)

    def test_help_names_the_exit_codes(self) -> None:
        done = self.run_script("--help")
        self.assertEqual(done.returncode, 0)
        self.assertIn("exit codes", done.stdout)

    def test_the_before_file_can_come_from_a_git_ref(self) -> None:
        git_env = {
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "HOME": str(self.folder),
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
        }

        def git(*args: str) -> None:
            subprocess.run(
                ["git", *args], cwd=self.folder, check=True, capture_output=True, env=git_env
            )

        git("init", "-q", "-b", "main")
        self.lock("package-lock.json", NPM_BEFORE)
        git("add", "package-lock.json")
        git("commit", "-q", "-m", "start")
        self.lock("package-lock.json", NPM_AFTER)
        done = self.run_script(
            "--lockfile", "package-lock.json", "--base-ref", "HEAD", *self.base_args()
        )
        self.assertEqual(done.returncode, 3, msg=done.stderr)
        self.assertEqual([f["name"] for f in json.loads(done.stdout)["findings"]], ["fresh-mit"])


if __name__ == "__main__":
    unittest.main()
