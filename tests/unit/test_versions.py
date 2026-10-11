"""Pinned release provenance and version state outside the plugin cache."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import select
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit/scripts"))

from loop import versions  # noqa: E402


def setup_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "distribution_setup", ROOT / "kit/scripts/setup.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExistingDistributionTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="distribution-test-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.kit = self.folder / "cache" / "ai-loop-kit" / "0.1.0"
        self.kit.mkdir(parents=True)
        (self.kit / ".claude-plugin").mkdir()
        self.manifest = self.kit / ".claude-plugin/plugin.json"
        self.manifest.write_text(json.dumps({"name": "ai-loop-kit", "version": "0.1.0"}))
        self.project = self.folder / "project"
        self.project.mkdir()
        self.setup = setup_module()
        environment = patch.dict(os.environ, {"AI_LOOP_KIT_DATA": str(self.folder / "data")})
        environment.start()
        self.addCleanup(environment.stop)

    def test_mutable_branch_is_not_a_pinned_release(self) -> None:
        with self.assertRaises(ValueError, msg="Q4: founding accepts a mutable main ref"):
            self.setup.kit_ref(self.kit, "main")

    def test_missing_manifest_version_is_a_refusal(self) -> None:
        self.manifest.write_text('{"name": "ai-loop-kit"}')
        with self.assertRaises(ValueError, msg="Q4: founding has no release identity"):
            self.setup.kit_ref(self.kit, "")

    def test_invalid_legacy_record_is_not_kept_as_provenance(self) -> None:
        legacy = self.kit / "version.json"
        legacy.write_text("broken JSON")
        with self.assertRaises(ValueError, msg="Q4: invalid cache-local state is trusted"):
            self.setup.write_kit_record(self.kit, self.project, False)
        self.assertEqual(legacy.read_text(), "broken JSON")


class VersionRegistryTest(ExistingDistributionTest):
    def setUp(self) -> None:
        super().setUp()
        self.release = self.folder / "release"
        shutil.copytree(self.kit, self.release)
        (self.release / "tool.sh").write_text("#!/bin/sh\nexit 0\n")
        (self.release / "tool.sh").chmod(0o755)
        shutil.copy2(self.release / "tool.sh", self.kit / "tool.sh")
        self.receipt: dict[str, Any] = {
            "schema": 1,
            "repository": versions.REPOSITORY,
            "plugin": "ai-loop-kit",
            "version": "0.1.0",
            "tag": "v0.1.0",
            "commit": "a" * 40,
            "files": versions.inventory(self.release),
        }

    def prepare(self, *, dry_run: bool = False, ref: str = "v0.1.0") -> versions.Prepared:
        with patch.object(versions, "_acquire", return_value=copy.deepcopy(self.receipt)):
            return versions.prepare(self.kit, self.project, ref, dry_run=dry_run)

    def test_baseline_survives_cache_relocation_and_remains_immutable(self) -> None:
        release = self.prepare()
        self.assertEqual(versions.publish(release), "written")
        before = release.path.read_bytes()
        self.assertFalse((self.kit / "version.json").exists())
        moved = self.folder / "different-cache" / "0.1.0"
        shutil.copytree(self.kit, moved)
        loaded = versions.load(moved, self.project)
        versions.verify(moved, loaded)
        self.assertEqual(loaded["commit"], "a" * 40)
        self.assertEqual(versions.publish(self.prepare(ref="a" * 40)), "kept")
        self.receipt["commit"] = "b" * 40
        with self.assertRaisesRegex(versions.VersionError, "immutable binding"):
            self.prepare()
        self.assertEqual(release.path.read_bytes(), before)

    def test_a_new_release_preserves_the_old_baseline(self) -> None:
        prior = self.prepare()
        versions.publish(prior)
        prior_bytes = prior.path.read_bytes()
        for kit in (self.kit, self.release):
            (kit / ".claude-plugin/plugin.json").write_text(
                json.dumps({"name": "ai-loop-kit", "version": "0.2.0"})
            )
        self.receipt.update(
            version="0.2.0", tag="v0.2.0", commit="b" * 40, files=versions.inventory(self.release)
        )
        current = self.prepare(ref="v0.2.0")
        self.assertEqual(versions.publish(current), "written")
        self.assertNotEqual(current.path, prior.path)
        self.assertEqual(prior.path.read_bytes(), prior_bytes)

    def test_modified_added_missing_and_nonexecutable_files_refuse(self) -> None:
        original = (self.kit / "tool.sh").read_bytes()
        (self.kit / "tool.sh").write_text("changed")
        with self.assertRaisesRegex(versions.VersionError, "differs"):
            self.prepare()
        (self.kit / "tool.sh").write_bytes(original)
        (self.kit / "extra").write_text("unexpected")
        with self.assertRaisesRegex(versions.VersionError, "differs"):
            self.prepare()
        (self.kit / "extra").unlink()
        (self.kit / "tool.sh").chmod(0o644)
        with self.assertRaisesRegex(versions.VersionError, "differs"):
            self.prepare()
        (self.kit / "tool.sh").unlink()
        with self.assertRaisesRegex(versions.VersionError, "differs"):
            self.prepare()
        self.assertFalse((self.folder / "data").exists())

    def test_dry_run_uses_existing_verified_state_without_acquisition_or_writes(self) -> None:
        with (
            patch.object(versions, "_acquire", side_effect=AssertionError("dry-run fetch")),
            self.assertRaises(versions.VersionError),
        ):
            versions.prepare(self.kit, self.project, dry_run=True)
        self.assertFalse((self.folder / "data").exists())
        release = self.prepare()
        versions.publish(release)
        before = {p: p.read_bytes() for p in (self.folder / "data").rglob("*") if p.is_file()}
        with patch.object(versions, "_acquire", side_effect=AssertionError("dry-run fetch")):
            self.assertEqual(
                versions.publish(versions.prepare(self.kit, self.project, dry_run=True)), "kept"
            )
        after = {p: p.read_bytes() for p in (self.folder / "data").rglob("*") if p.is_file()}
        self.assertEqual(after, before)

    def test_legacy_migration_revalidates_release_and_keeps_legacy_bytes(self) -> None:
        legacy = self.kit / "version.json"
        legacy.write_text(
            json.dumps(
                {
                    "record": 1,
                    "files": {name: item["sha256"] for name, item in self.receipt["files"].items()},
                }
            )
        )
        before = legacy.read_bytes()
        self.assertEqual(versions.publish(self.prepare()), "written")
        self.assertEqual(legacy.read_bytes(), before)
        data = json.loads(legacy.read_text())
        data["files"]["tool.sh"] = "b" * 64
        legacy.write_text(json.dumps(data))
        with self.assertRaisesRegex(versions.VersionError, "legacy.*disagrees"):
            self.prepare(ref="a" * 40)

    def test_unverified_full_sha_and_unsafe_home_refuse(self) -> None:
        with self.assertRaisesRegex(versions.VersionError, "no existing baseline"):
            self.prepare(ref="a" * 40)
        for home in (str(self.project / "data"), str(self.kit / "data"), "relative"):
            with (
                self.subTest(home=home),
                patch.dict(os.environ, {"AI_LOOP_KIT_DATA": home}),
                self.assertRaises(versions.VersionError),
            ):
                self.prepare()

    def test_corrupt_schema_or_unsafe_inventory_is_preserved_and_refused(self) -> None:
        release = self.prepare()
        versions.publish(release)
        for update in (
            {"schema": True},
            {"commit": "short"},
            {"files": {"../outside": {"sha256": "a" * 64, "executable": False}}},
        ):
            body = copy.deepcopy(self.receipt)
            body.update(update)
            release.path.write_text(json.dumps(body))
            before = release.path.read_bytes()
            with self.subTest(update=update), self.assertRaises(versions.VersionError):
                self.prepare(ref="a" * 40)
            self.assertEqual(release.path.read_bytes(), before)

    def test_symlink_installed_file_or_registry_path_refuses(self) -> None:
        (self.kit / "outside").symlink_to(self.release / "tool.sh")
        with self.assertRaisesRegex(versions.VersionError, "non-regular"):
            self.prepare()
        (self.kit / "outside").unlink()
        release = self.prepare()
        release.path.parent.mkdir(parents=True)
        release.path.symlink_to(self.manifest)
        with self.assertRaisesRegex(versions.VersionError, "symlink"):
            self.prepare()

    def test_concurrent_conflicting_writers_publish_one_completed_baseline(self) -> None:
        release = self.prepare()
        worker = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from loop import versions
body = json.loads(sys.argv[5]); body['commit'] = sys.argv[6]
prepared = versions.Prepared(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), body, False)
print('ready', flush=True); sys.stdin.readline()
try: print(versions.publish(prepared), flush=True)
except versions.VersionError: print('refused', flush=True)
"""
        children: list[subprocess.Popen[str]] = []
        try:
            for commit in ("a" * 40, "b" * 40):
                child = subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        worker,
                        str(ROOT / "kit/scripts"),
                        str(self.kit),
                        str(self.project),
                        str(release.path),
                        json.dumps(self.receipt),
                        commit,
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                children.append(child)
                assert child.stdout is not None
                self.assertTrue(
                    select.select([child.stdout], [], [], 10)[0], "worker did not start"
                )
                self.assertEqual(child.stdout.readline().strip(), "ready")
            for child in children:
                assert child.stdin is not None
                child.stdin.write("go\n")
                child.stdin.flush()
            results = []
            for child in children:
                output, error = child.communicate(timeout=10)
                self.assertEqual(child.returncode, 0, error)
                results.append(output.strip())
            self.assertEqual(sorted(results), ["refused", "written"])
            self.assertIn(versions.load(self.kit, self.project)["commit"], ("a" * 40, "b" * 40))
        finally:
            for child in children:
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=10)
                for stream in (child.stdin, child.stdout, child.stderr):
                    if stream is not None:
                        stream.close()


if __name__ == "__main__":
    unittest.main()


class ReleaseAcquisitionTest(ExistingDistributionTest):
    def test_public_acquisition_hashes_fetched_commit_not_installed_cache(self) -> None:
        repository = self.folder / "repository"
        repository.mkdir()
        shutil.copytree(self.kit, repository / "kit")
        (repository / "kit/tool.sh").write_text("release bytes\n")
        subprocess.run(["git", "init", "-q", str(repository)], check=True)
        subprocess.run(["git", "-C", str(repository), "add", "kit"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "Fixture",
            ],
            check=True,
        )
        commit = subprocess.check_output(
            ["git", "-C", str(repository), "rev-parse", "HEAD"], text=True
        ).strip()
        annotation = (
            f"object {commit}\ntype commit\ntag v0.1.0\n"
            "tagger Fixture <fixture@example.invalid> 0 +0000\n\nOffline fixture\n"
        )
        tag_object = subprocess.check_output(
            ["git", "-C", str(repository), "hash-object", "-t", "tag", "-w", "--stdin"],
            input=annotation,
            text=True,
        ).strip()
        subprocess.run(
            ["git", "-C", str(repository), "update-ref", "refs/tags/v0.1.0", tag_object],
            check=True,
        )
        self.assertNotEqual(tag_object, commit)
        original = versions._git
        calls: list[list[str]] = []

        def redirected(arguments: Any, folder: Path) -> str:
            arguments = list(arguments)
            calls.append(arguments.copy())
            if arguments[:3] == ["remote", "add", "origin"]:
                self.assertEqual(arguments[3], versions.REPOSITORY)
                arguments[3] = str(repository)
            if arguments[:1] == ["fetch"]:
                self.assertEqual(arguments[-1], "refs/tags/v0.1.0")
            return original(arguments, folder)

        with patch.object(versions, "_git", side_effect=redirected):
            acquired = versions._acquire("v0.1.0")
        self.assertEqual(acquired["commit"], commit)
        self.assertEqual(acquired["files"], versions.inventory(repository / "kit"))
        self.assertIn(["checkout", "-q", "--detach", "FETCH_HEAD^{commit}"], calls)
        with self.assertRaisesRegex(versions.VersionError, "differs"):
            versions.verify(self.kit, acquired)

    def test_git_acquisition_suppresses_credentials_and_errors(self) -> None:
        checkout = self.folder / "checkout"
        checkout.mkdir()
        failure = subprocess.CompletedProcess([], 1, "private-output", "private-error")
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "fixture", "GIT_CONFIG_COUNT": "1"}),
            patch("loop.versions.subprocess.run", return_value=failure) as command,
            self.assertRaisesRegex(
                versions.VersionError, "anonymous release acquisition failed"
            ) as refusal,
        ):
            versions._git(["fetch", "origin", "refs/tags/v0.1.0"], checkout)
        self.assertNotIn("private", str(refusal.exception))
        environment = command.call_args.kwargs["env"]
        self.assertNotIn("GITHUB_TOKEN", environment)
        self.assertNotIn("GIT_CONFIG_COUNT", environment)
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(environment["GIT_TERMINAL_PROMPT"], "0")
        self.assertIn("credential.helper=", command.call_args.args[0])


class GeneratedDistributionTest(ExistingDistributionTest):
    def test_generated_check_executes_verified_sha_and_ignores_plugin_root(self) -> None:
        repository = self.folder / "public-fixture"
        scripts = repository / "kit/scripts"
        scripts.mkdir(parents=True)
        for name in ("records-check", "hosted-check"):
            (scripts / (name + ".py")).write_text(
                f"from pathlib import Path\nPath('{name}.ran').write_text('verified release')\n"
            )
        subprocess.run(["git", "init", "-q", str(repository)], check=True)
        subprocess.run(["git", "-C", str(repository), "add", "kit"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "Fixture",
            ],
            check=True,
        )
        commit = subprocess.check_output(
            ["git", "-C", str(repository), "rev-parse", "HEAD"], text=True
        ).strip()
        binaries = self.folder / "bin"
        binaries.mkdir()
        actual_git = shutil.which("git")
        assert actual_git is not None
        wrapper = binaries / "git"
        wrapper.write_text(
            f"#!{sys.executable}\nimport os,sys\n"
            "if os.environ.get('FIXTURE_BAD_IDENTITY') and 'rev-parse' in sys.argv:\n"
            " print('b' * 40); sys.exit(0)\n"
            f"args=[{str(repository)!r} if a == {versions.REPOSITORY!r} else a "
            "for a in sys.argv[1:]]\n"
            f"os.execv({actual_git!r}, [{actual_git!r}, *args])\n"
        )
        wrapper.chmod(0o755)
        text = (ROOT / "kit/templates/checks.yml").read_text()
        text = text.replace("{{KIT_REF}}", commit).replace("{{SCAFFOLD_TEST_COMMAND}}", '"true"')
        blocks: list[str] = []
        current: list[str] | None = None
        for line in text.splitlines():
            if line == "        run: |":
                current = []
                blocks.append("")
            elif current is not None and line.startswith("          "):
                current.append(line[10:])
                blocks[-1] = "\n".join(current)
            else:
                current = None
        self.assertEqual(len(blocks), 3)
        env = dict(
            os.environ,
            PATH=str(binaries) + os.pathsep + os.environ["PATH"],
            KIT_REVISION=commit,
            CLAUDE_PLUGIN_ROOT=str(self.folder / "decoy"),
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_CONFIG_NOSYSTEM="1",
            GIT_TERMINAL_PROMPT="0",
            GIT_ASKPASS="/usr/bin/false",
        )
        for block in blocks:
            result = subprocess.run(
                ["sh", "-eu", "-c", block],
                cwd=self.project,
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        for name in ("records-check", "hosted-check"):
            self.assertEqual((self.project / (name + ".ran")).read_text(), "verified release")
        self.assertEqual(
            subprocess.check_output(
                [actual_git, "-C", str(self.project / ".kit"), "rev-parse", "HEAD"], text=True
            ).strip(),
            commit,
        )
        for name in ("records-check", "hosted-check"):
            (self.project / (name + ".ran")).unlink()
        refusal = subprocess.run(
            ["sh", "-eu", "-c", blocks[0]],
            cwd=self.project,
            env=dict(env, FIXTURE_BAD_IDENTITY="1"),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        self.assertEqual(refusal.returncode, 3, refusal.stderr)
        self.assertIn("differs from its verified release", refusal.stdout)
        self.assertFalse(any(self.project.glob("*.ran")))

    def test_catalogue_selects_same_release_kit_without_duplicate_version(self) -> None:
        catalogue = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual(catalogue["name"], "ai-loop-kit")
        self.assertEqual(len(catalogue["plugins"]), 1)
        plugin = catalogue["plugins"][0]
        self.assertEqual(plugin["name"], "ai-loop-kit")
        self.assertEqual(plugin["source"], "./kit")
        self.assertNotIn("version", plugin)


class FoundingDistributionTest(VersionRegistryTest):
    def test_record_failure_and_unresolved_render_refuse_before_project_writes(self) -> None:
        import argparse

        from loop import cli

        shutil.copytree(ROOT / "kit/templates", self.release / "templates")
        shutil.copytree(self.release / "templates", self.kit / "templates")
        self.receipt["files"] = versions.inventory(self.release)
        parser = argparse.ArgumentParser()
        self.setup.setup(parser)
        args = parser.parse_args(
            [
                "found",
                "--project",
                str(self.project),
                "--kit-dir",
                str(self.kit),
                "--language",
                "python",
                "--test-command",
                "true",
            ]
        )
        before = versions.inventory(self.kit)
        with (
            patch.object(self.setup, "project_root", return_value=self.project),
            patch.object(self.setup, "check_tooling", return_value=False),
            patch.object(self.setup, "check_origin"),
            patch.object(versions, "_acquire", return_value=copy.deepcopy(self.receipt)),
            patch.object(versions, "publish", side_effect=versions.VersionError("write refused")),
            self.assertRaisesRegex(cli.Failure, "write refused"),
        ):
            self.setup.step_found(args)
        self.assertEqual(list(self.project.iterdir()), [])
        self.assertEqual(versions.inventory(self.kit), before)
        self.assertFalse((self.folder / "data").exists())
        for kit in (self.kit, self.release):
            workflow = kit / "templates/checks.yml"
            workflow.write_text(workflow.read_text() + "# {{KIT_MISSING}}\n")
        self.receipt["files"] = versions.inventory(self.release)
        with (
            patch.object(self.setup, "project_root", return_value=self.project),
            patch.object(self.setup, "check_tooling", return_value=False),
            patch.object(self.setup, "check_origin"),
            patch.object(versions, "_acquire", return_value=copy.deepcopy(self.receipt)),
            patch.object(versions, "publish") as publication,
            self.assertRaisesRegex(cli.Failure, "unresolved distribution"),
        ):
            self.setup.step_found(args)
        publication.assert_not_called()
        self.assertEqual(list(self.project.iterdir()), [])
        self.assertFalse((self.folder / "data").exists())


class FoundingHookPreflightTest(unittest.TestCase):
    def setUp(self) -> None:
        import argparse

        temporary = tempfile.TemporaryDirectory(prefix="founding-hook-preflight-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.project = self.folder / "project"
        self.project.mkdir()
        subprocess.run(["git", "init", "-q", str(self.project)], check=True,
                       capture_output=True)
        (self.project / "README.md").write_text("Person-owned project.\n")
        self.setup = setup_module()
        self.parser = argparse.ArgumentParser()
        self.setup.setup(self.parser)
        environment = patch.dict(os.environ, {"AI_LOOP_KIT_DATA": str(self.folder / "data")})
        environment.start()
        self.addCleanup(environment.stop)
        spec = importlib.util.spec_from_file_location(
            "hook_preflight_release_fixture", ROOT / "tests/lib/version-fixture.py")
        assert spec is not None and spec.loader is not None
        self.fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.fixture)

    def installed_release(self, name: str) -> versions.Prepared:
        kit = self.folder / name
        shutil.copytree(ROOT / "kit", kit,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "version.json"))
        release: versions.Prepared = self.fixture.release(kit, self.project, publish=False)
        self.assertFalse(release.path.exists())
        versions.verify(kit, release.body)
        return release

    def found(self, release: versions.Prepared) -> dict[str, Any]:
        args = self.parser.parse_args([
            "found", "--project", str(self.project), "--kit-dir", str(release.kit),
            "--language", "python", "--test-command", "true",
        ])
        # Acquisition already ran against a separately committed annotated local release.
        # Reuse that verified prepared input; publishing and project writes remain real.
        with (
            patch.object(self.setup, "project_root", return_value=self.project),
            patch.object(self.setup, "check_tooling", return_value=False),
            patch.object(self.setup, "check_origin"),
            patch.object(versions, "prepare", return_value=release),
        ):
            result: dict[str, Any] = self.setup.step_found(args)
        return result

    def snapshot(self) -> dict[str, tuple[bytes | None, int]]:
        return {str(path.relative_to(self.folder)):
                (path.read_bytes() if path.is_file() else None, path.stat().st_mode)
                for path in self.folder.rglob("*")}

    def test_unsafe_hook_path_refusal_preserves_project_kit_and_registry(self) -> None:
        from loop import cli

        release = self.installed_release("plugin$unsafe")
        before = self.snapshot()
        with self.assertRaisesRegex(cli.Failure, "pre-push hook"):
            self.found(release)
        self.assertEqual(self.snapshot(), before,
                         "hook-path refusal changed project, kit or stable registry")

    def test_plain_hook_path_founds_and_keeps_existing_verified_state(self) -> None:
        release = self.installed_release("plain-plugin")
        result = self.found(release)
        self.assertEqual(result["kit_record"], "written")
        self.assertEqual(result["kit_revision"], release.commit)
        self.assertTrue(release.path.is_file())
        hook = self.project / ".githooks/pre-push"
        self.assertIn(str(release.kit), hook.read_text())
        self.assertTrue(hook.stat().st_mode & 0o111)
        self.assertEqual((self.project / "README.md").read_text(), "Person-owned project.\n")
        before = self.snapshot()
        self.assertEqual(self.found(release)["kit_record"], "kept")
        self.assertEqual(self.snapshot(), before)


class FoundingSettingsPreflightTest(FoundingHookPreflightTest):
    def test_invalid_settings_refusal_preserves_all_state(self) -> None:
        from loop import cli

        release = self.installed_release("plain-plugin")
        target = self.project / ".claude/settings.json"
        target.parent.mkdir()
        for contents in ("broken JSON", "[]", "null", "42"):
            with self.subTest(contents=contents):
                target.write_text(contents)
                target.chmod(0o600)
                before = self.snapshot()
                with self.assertRaisesRegex(cli.Failure, "not valid JSON|not a JSON object"):
                    self.found(release)
                self.assertEqual(self.snapshot(), before)
                self.assertFalse(release.path.exists())

    def test_valid_person_settings_are_merged_and_kept_on_repeat(self) -> None:
        release = self.installed_release("plain-plugin")
        target = self.project / ".claude/settings.json"
        target.parent.mkdir()
        mine = {"sandbox": {"enabled": False}, "permissions": {"allow": ["Read"]},
                "person_note": "keep this"}
        target.write_text(json.dumps(mine))
        target.chmod(0o600)
        self.assertEqual(self.found(release)["kit_record"], "written")
        merged = json.loads(target.read_text())
        self.assertFalse(merged["sandbox"]["enabled"])
        self.assertIn("Read", merged["permissions"]["allow"])
        self.assertEqual(merged["person_note"], "keep this")
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertTrue(release.path.exists())
        before = self.snapshot()
        self.assertEqual(self.found(release)["kit_record"], "kept")
        self.assertEqual(self.snapshot(), before)


class DevelopmentDistributionTest(ExistingDistributionTest):
    """Development identity is explicit, public and independent of release tags."""

    def setUp(self) -> None:
        super().setUp()
        self.manifest.write_text(json.dumps({"name": "ai-loop-kit"}))
        (self.kit / "tool.sh").write_text("#!/bin/sh\nexit 0\n")
        (self.kit / "tool.sh").chmod(0o755)
        self.repository = self.folder / "public-development"
        shutil.copytree(self.kit, self.repository / "kit")
        subprocess.run(["git", "init", "-q", str(self.repository)], check=True)
        self.commit_fixture()
        self.calls: list[list[str]] = []
        original = versions._git

        def public_fixture(arguments: Any, folder: Path) -> str:
            arguments = list(arguments)
            self.calls.append(arguments.copy())
            if arguments[:3] == ["remote", "add", "origin"]:
                self.assertEqual(arguments[3], versions.REPOSITORY)
                arguments[3] = str(self.repository)
            return original(arguments, folder)

        acquisition = patch.object(versions, "_git", side_effect=public_fixture)
        acquisition.start()
        self.addCleanup(acquisition.stop)

    def commit_fixture(self) -> None:
        subprocess.run(["git", "-C", str(self.repository), "add", "kit"], check=True)
        subprocess.run([
            "git", "-C", str(self.repository), "-c", "user.name=Fixture",
            "-c", "user.email=fixture@example.invalid", "commit", "--no-gpg-sign",
            "-qm", "Development fixture",
        ], check=True)
        self.commit = subprocess.check_output(
            ["git", "-C", str(self.repository), "rev-parse", "HEAD"], text=True
        ).strip()

    def workflow(self, text: str | None = None) -> Path:
        path = self.project / ".github/workflows/checks.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if text is not None else (
            "# ai-loop-kit: development\n"
            f'          KIT_REVISION: "{self.commit}"\n'
        ))
        return path

    def development(self, *, dry_run: bool = False) -> versions.Prepared:
        return versions.prepare(
            self.kit, self.project, self.commit, development=True, dry_run=dry_run
        )

    def test_explicit_full_commit_acquires_content_without_release_identity(self) -> None:
        prepared = self.development()
        self.assertEqual(prepared.commit, self.commit)
        self.assertEqual(prepared.body["mode"], "development")
        self.assertEqual(prepared.body["schema"], 2)
        self.assertNotIn("version", prepared.body)
        self.assertNotIn("tag", prepared.body)
        self.assertEqual(prepared.body["files"], versions.inventory(self.kit))
        self.assertIn(["fetch", "--depth=1", "--no-tags", "origin", self.commit], self.calls)
        self.assertFalse(any("refs/tags/" in part for call in self.calls for part in call))
        self.assertFalse(prepared.path.exists())
        self.assertEqual(prepared.path.parent.name, "development")
        self.assertEqual(prepared.path.name, self.commit + ".json")
        self.workflow()
        self.assertEqual(versions.publish(prepared), "written")
        self.assertEqual(versions.load(self.kit, self.project), prepared.body)
        versions.verify(self.kit, prepared.body)
        self.assertEqual(versions.publish(self.development()), "kept")

    def test_default_missing_version_still_refuses_and_invalid_development_refs_do_not_fetch(
        self,
    ) -> None:
        with self.assertRaisesRegex(versions.VersionError, "release version"):
            versions.prepare(self.kit, self.project, self.commit)
        for given in ("", "main", "v0.1.0", self.commit[:12], "A" * 40, "g" * 40):
            with self.subTest(given=given), self.assertRaises(versions.VersionError):
                versions.prepare(self.kit, self.project, given, development=True)
        self.assertEqual(self.calls, [])
        self.assertFalse((self.folder / "data").exists())

    def test_versioned_installed_copy_can_be_explicit_development(self) -> None:
        for kit in (self.kit, self.repository / "kit"):
            (kit / ".claude-plugin/plugin.json").write_text(
                json.dumps({"name": "ai-loop-kit", "version": "0.1.0"})
            )
        self.commit_fixture()
        prepared = self.development()
        self.assertEqual(prepared.body["mode"], "development")
        self.assertNotIn("version", prepared.body)
        self.workflow()
        versions.publish(prepared)
        self.assertEqual(versions.load(self.kit, self.project)["mode"], "development")

    def test_development_dry_run_fetches_only_scratch_and_publishes_nothing(self) -> None:
        prepared = self.development(dry_run=True)
        self.assertTrue(self.calls, "development dry-run must verify its full public commit")
        self.assertEqual(versions.publish(prepared), "would write")
        self.assertEqual(list(self.project.iterdir()), [])
        self.assertFalse((self.folder / "data").exists())
        self.assertFalse((self.kit / "version.json").exists())

    def test_changed_installed_bytes_or_mode_cannot_self_seal(self) -> None:
        tool = self.kit / "tool.sh"
        original = tool.read_bytes()
        tool.write_text("changed")
        with self.assertRaises(versions.VersionError):
            self.development()
        tool.write_bytes(original)
        tool.chmod(0o644)
        with self.assertRaises(versions.VersionError):
            self.development()
        self.assertFalse((self.folder / "data").exists())

    def test_selector_near_misses_duplicates_and_wrong_pin_refuse_read_only(self) -> None:
        self.workflow()
        prepared = self.development()
        versions.publish(prepared)
        path = self.workflow()
        good = path.read_text()
        records = prepared.path.read_bytes()
        variants = [
            good.replace("# ai-loop-kit: development", "# ai-loop-kit: development "),
            "# comment\n" + good,
            good + "# ai-loop-kit: development\n",
            good + f'          KIT_REVISION: "{self.commit}"\n',
            good.replace(self.commit, "main"),
            good.replace(self.commit, "b" * 40),
            good.replace("          KIT_REVISION:", "         KIT_REVISION:"),
        ]
        for text in variants:
            path.write_text(text)
            before = path.read_bytes()
            with self.subTest(text=text), self.assertRaises(versions.VersionError):
                versions.load(self.kit, self.project)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(prepared.path.read_bytes(), records)

    def test_moved_copy_uses_record_and_corruption_is_kept(self) -> None:
        self.workflow()
        prepared = self.development()
        versions.publish(prepared)
        moved = self.folder / "moved-kit"
        shutil.copytree(self.kit, moved)
        self.assertEqual(versions.load(moved, self.project), prepared.body)
        versions.verify(moved, prepared.body)
        prepared.path.write_text("broken JSON")
        with self.assertRaises(versions.VersionError):
            versions.load(moved, self.project)
        self.assertEqual(prepared.path.read_text(), "broken JSON")


    def founding_fixture(self) -> None:
        for kit in (self.kit, self.repository / "kit"):
            shutil.copytree(ROOT / "kit/templates", kit / "templates")
        self.commit_fixture()

    def found(self, *, development: bool = True, project: Path | None = None) -> dict[str, Any]:
        import argparse

        parser = argparse.ArgumentParser()
        self.setup.setup(parser)
        target = self.project if project is None else project
        words = ["found", "--project", str(target), "--kit-dir", str(self.kit),
                 "--kit-ref", self.commit, "--language", "python", "--test-command", "true"]
        if development:
            words.append("--development")
        try:
            args = parser.parse_args(words)
        except SystemExit as error:
            self.fail(f"FIELD1: explicit development founding is refused by the CLI: {error}")
        with (
            patch.object(self.setup, "project_root", return_value=target),
            patch.object(self.setup, "check_tooling", return_value=False),
            patch.object(self.setup, "check_origin"),
            patch.object(self.setup, "project_has_runner", return_value=False),
            patch.object(self.setup, "git_out", return_value=".githooks"),
        ):
            result: dict[str, Any] = self.setup.step_found(args)
        return result

    def test_existing_full_sha_missing_version_refusal_is_preserved_separately(self) -> None:
        from loop import cli

        self.founding_fixture()
        with (
            patch.object(versions, "publish") as publication,
            self.assertRaisesRegex(cli.Failure, "no valid release version") as refused,
        ):
            self.found(development=False)
        self.assertTrue(refused.exception.next_command)
        publication.assert_not_called()
        self.assertEqual(list(self.project.iterdir()), [])
        self.assertFalse((self.folder / "data").exists())

    def test_explicit_development_cli_founds_and_reports_truthful_identity(self) -> None:
        self.founding_fixture()
        result = self.found()
        self.assertEqual(result["kit_revision"], self.commit)
        self.assertEqual(result["kit_mode"], "development")
        self.assertIsNone(result["kit_version"])
        self.assertTrue(any("development" in warning.lower() for warning in result["warnings"]))
        workflow = self.project / ".github/workflows/checks.yml"
        text = workflow.read_text()
        self.assertTrue(text.startswith("# ai-loop-kit: development\n"))
        self.assertEqual(text.count("KIT_REVISION:"), 1)
        self.assertIn(f'          KIT_REVISION: "{self.commit}"', text)
        first = {str(p.relative_to(self.project)): (p.read_bytes(), p.stat().st_mode & 0o777)
                 for p in self.project.rglob("*") if p.is_file()}
        self.found()
        second = {str(p.relative_to(self.project)): (p.read_bytes(), p.stat().st_mode & 0o777)
                  for p in self.project.rglob("*") if p.is_file()}
        self.assertEqual(first, second)

    def test_conflicting_workflow_refuses_before_any_foundation_or_record_write(self) -> None:
        from loop import cli

        self.founding_fixture()
        good = "# ai-loop-kit: development\n" + f'          KIT_REVISION: "{self.commit}"\n'
        variants = [
            good.replace("# ai-loop-kit: development\n", ""),
            good.replace(self.commit, "b" * 40),
            good + f'          KIT_REVISION: "{self.commit}"\n',
            good + "# ai-loop-kit: development\n",
            good.replace("KIT_REVISION:", "KIT_REVISION :"),
        ]
        for text in variants:
            with self.subTest(text=text), tempfile.TemporaryDirectory(prefix="field1-conflict-") as tmp:
                base = Path(tmp)
                project = base / "project"
                path = project / ".github/workflows/checks.yml"
                path.parent.mkdir(parents=True)
                path.write_text(text)
                before = {str(p.relative_to(base)): (p.read_bytes(), p.stat().st_mode & 0o777)
                          for p in base.rglob("*") if p.is_file()}
                with (
                    patch.dict(os.environ, {"AI_LOOP_KIT_DATA": str(base / "data")}),
                    patch.object(versions, "publish") as publication,
                    self.assertRaises(cli.Failure),
                ):
                    self.found(project=project)
                publication.assert_not_called()
                after = {str(p.relative_to(base)): (p.read_bytes(), p.stat().st_mode & 0o777)
                         for p in base.rglob("*") if p.is_file()}
                self.assertEqual(before, after)

    def test_wrong_fetched_head_refuses_without_publishing(self) -> None:
        current = versions._git

        def wrong_head(arguments: Any, folder: Path) -> str:
            value = current(arguments, folder)
            return "b" * 40 if list(arguments) == ["rev-parse", "HEAD"] else value

        with patch.object(versions, "_git", side_effect=wrong_head):
            with self.assertRaises(versions.VersionError):
                self.development()
        self.assertFalse((self.folder / "data").exists())

    def test_unsafe_workflow_file_and_ancestor_refuse_before_publication(self) -> None:
        from loop import cli

        self.founding_fixture()
        good = "# ai-loop-kit: development\n" + f'          KIT_REVISION: "{self.commit}"\n'
        for ancestor in (False, True):
            with self.subTest(ancestor=ancestor), tempfile.TemporaryDirectory(prefix="field1-path-") as tmp:
                base = Path(tmp)
                project = base / "project"
                project.mkdir()
                outside = base / "outside"
                outside.mkdir()
                if ancestor:
                    (outside / "workflows").mkdir()
                    (outside / "workflows/checks.yml").write_text(good)
                    (project / ".github").symlink_to(outside, target_is_directory=True)
                else:
                    target = outside / "checks.yml"
                    target.write_text(good)
                    (project / ".github/workflows").mkdir(parents=True)
                    (project / ".github/workflows/checks.yml").symlink_to(target)
                before = {str(p.relative_to(base)): (p.read_bytes(), p.stat().st_mode & 0o777)
                          for p in base.rglob("*") if p.is_file()}
                with (
                    patch.dict(os.environ, {"AI_LOOP_KIT_DATA": str(base / "data")}),
                    patch.object(versions, "publish") as publication,
                    self.assertRaises(cli.Failure),
                ):
                    self.found(project=project)
                publication.assert_not_called()
                after = {str(p.relative_to(base)): (p.read_bytes(), p.stat().st_mode & 0o777)
                         for p in base.rglob("*") if p.is_file()}
                self.assertEqual(before, after)
