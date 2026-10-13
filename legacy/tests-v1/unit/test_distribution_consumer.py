"""The pre-run consumer reads verified release state without acquiring or writing."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit/scripts"))
from loop import versions  # noqa: E402


def module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


class StableConsumerTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="distribution-consumer-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.project = self.base / "project"
        self.project.mkdir()
        self.kit = self.base / "cache/plugin"
        shutil.copytree(ROOT / "kit", self.kit,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "version.json"))
        self.data = self.base / "data"
        environment = patch.dict(os.environ, {"AI_LOOP_KIT_DATA": str(self.data)})
        environment.start()
        self.addCleanup(environment.stop)
        self.check = module("distribution_consumer", ROOT / "kit/scripts/pre-run-check.py")
        fixture = module("distribution_release_fixture", ROOT / "tests/lib/version-fixture.py")
        self.release = fixture.release(self.kit, self.project)

    def snapshot(self) -> dict[str, bytes]:
        return {str(path.relative_to(self.base)): path.read_bytes()
                for path in self.base.rglob("*") if path.is_file()}

    def check_read_only(self, kit: Path) -> list[Any]:
        before = self.snapshot()
        with (
            patch.object(versions, "_acquire", side_effect=AssertionError("pre-run acquired")),
            patch.object(versions, "publish", side_effect=AssertionError("pre-run published")),
        ):
            result: list[Any] = self.check.check_kit_folder(self.project, kit)
        self.assertEqual(self.snapshot(), before, "pre-run changed version state or kit")
        return result

    def test_verified_baseline_passes_without_cache_record_or_writes(self) -> None:
        self.assertFalse((self.kit / "version.json").exists())
        self.assertEqual(self.check_read_only(self.kit), [])

    def test_cache_relocation_uses_same_stable_baseline(self) -> None:
        moved = self.base / "moved/plugin"
        shutil.copytree(self.kit, moved)
        self.assertEqual(self.check_read_only(moved), [])

    def test_missing_stable_record_refuses_with_actionable_message(self) -> None:
        self.release.path.unlink()
        refusals = self.check_read_only(self.kit)
        self.assertEqual([r.guard for r in refusals], ["kit-folder"])
        self.assertIn("stable release record is missing", refusals[0].reason)
        self.assertTrue(refusals[0].fix)

    def test_corrupt_stable_record_is_kept_and_refused(self) -> None:
        self.release.path.write_text("broken JSON")
        refusals = self.check_read_only(self.kit)
        self.assertEqual([r.guard for r in refusals], ["kit-folder"])
        self.assertIn("stable release record is invalid", refusals[0].reason)

    def test_changed_installed_content_cannot_self_seal(self) -> None:
        (self.kit / "scripts/run.py").write_text("changed")
        refusals = self.check_read_only(self.kit)
        self.assertEqual([r.guard for r in refusals], ["kit-folder"])
        self.assertIn("differs from the verified release", refusals[0].reason)

    def test_malformed_identity_record_refuses(self) -> None:
        body = json.loads(self.release.path.read_text())
        body["commit"] = "main"
        self.release.path.write_text(json.dumps(body))
        self.assertTrue(self.check_read_only(self.kit))


class DevelopmentConsumerTest(unittest.TestCase):
    """Consume a genuine offline public commit without reacquisition or publication."""

    def setUp(self) -> None:
        source = module("development_versions_fixture", ROOT / "tests/unit/test_versions.py")
        fixture = source.DevelopmentDistributionTest(
            "test_explicit_full_commit_acquires_content_without_release_identity"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.check = module("field1_development_consumer", ROOT / "kit/scripts/pre-run-check.py")

    def snapshot(self) -> dict[str, tuple[bytes, int]]:
        return {str(p.relative_to(self.fixture.folder)): (p.read_bytes(), p.stat().st_mode & 0o777)
                for p in self.fixture.folder.rglob("*") if p.is_file()}

    def check_read_only(self, kit: Path) -> tuple[list[Any], list[str]]:
        before = self.snapshot()
        notices: list[str] = []
        with (
            patch.object(versions, "_acquire", side_effect=AssertionError("pre-run release fetch")),
            patch.object(versions, "_acquire_development", create=True,
                         side_effect=AssertionError("pre-run development fetch")),
            patch.object(versions, "publish", side_effect=AssertionError("pre-run publication")),
        ):
            result = self.check.check_kit_folder(self.fixture.project, kit, notices=notices)
        self.assertEqual(self.snapshot(), before)
        return result, notices

    def test_existing_verified_development_record_passes_and_notice_is_honest(self) -> None:
        self.fixture.workflow()
        prepared = self.fixture.development()
        versions.publish(prepared)
        refused, notices = self.check_read_only(self.fixture.kit)
        self.assertEqual(refused, [])
        self.assertTrue(any("development" in text.lower() for text in notices))
        moved = self.fixture.folder / "relocated"
        shutil.copytree(self.fixture.kit, moved)
        self.assertEqual(self.check_read_only(moved)[0], [])

    def test_unmarked_versionless_copy_cannot_infer_development_from_a_record(self) -> None:
        path = self.fixture.workflow()
        versions.publish(self.fixture.development())
        path.write_text(path.read_text().replace("# ai-loop-kit: development\n", ""))
        self.assertEqual(
            [r.guard for r in self.check_read_only(self.fixture.kit)[0]], ["kit-folder"]
        )

    def test_missing_corrupt_mismatched_records_and_content_are_read_only_refusals(self) -> None:
        path = self.fixture.workflow()
        prepared = self.fixture.development()
        versions.publish(prepared)
        original = prepared.path.read_bytes()
        prepared.path.unlink()
        with self.assertRaises(versions.VersionError) as missing:
            versions.load(self.fixture.kit, self.fixture.project)
        self.assertIn(
            "setup.py found --development --kit-ref <full lowercase commit SHA>",
            missing.exception.next_command,
        )
        self.assertNotIn("release tag", missing.exception.next_command)
        refusals, _ = self.check_read_only(self.fixture.kit)
        self.assertEqual([refusal.guard for refusal in refusals], ["kit-folder"])
        self.assertIn(missing.exception.next_command, refusals[0].fix)
        prepared.path.write_bytes(original)
        prepared.path.write_text("broken JSON")
        self.assertTrue(self.check_read_only(self.fixture.kit)[0])
        self.assertEqual(prepared.path.read_text(), "broken JSON")
        prepared.path.write_bytes(original)
        path.write_text(path.read_text().replace(self.fixture.commit, "b" * 40))
        self.assertTrue(self.check_read_only(self.fixture.kit)[0])
        self.fixture.workflow()
        (self.fixture.kit / "tool.sh").write_text("changed")
        self.assertTrue(self.check_read_only(self.fixture.kit)[0])

    def test_invalid_development_manifest_version_keeps_development_recovery(self) -> None:
        self.fixture.workflow()
        versions.publish(self.fixture.development())
        manifest = self.fixture.kit / ".claude-plugin/plugin.json"
        manifest.write_text(json.dumps({"name": "ai-loop-kit", "version": "latest"}))
        before = self.snapshot()
        with (
            patch.object(versions, "_acquire", side_effect=AssertionError("release acquisition")),
            patch.object(versions, "_acquire_development",
                         side_effect=AssertionError("development acquisition")),
            patch.object(versions, "publish", side_effect=AssertionError("publication")),
            self.assertRaises(versions.VersionError) as invalid,
        ):
            versions.load(self.fixture.kit, self.fixture.project)
        self.assertEqual(self.snapshot(), before)
        refusals, notices = self.check_read_only(self.fixture.kit)
        self.assertEqual([refusal.guard for refusal in refusals], ["kit-folder"])
        self.assertEqual(notices, [])
        with self.assertRaises(versions.VersionError) as release:
            versions.manifest_version(self.fixture.kit)
        self.assertIn("release tag", release.exception.next_command)
        self.assertIn(
            "setup.py found --development --kit-ref <full lowercase commit SHA>",
            invalid.exception.next_command,
        )
        self.assertNotIn("release tag", invalid.exception.next_command)
        self.assertIn(invalid.exception.next_command, refusals[0].fix)

    def test_development_data_home_refusals_keep_development_recovery(self) -> None:
        self.fixture.workflow()
        versions.publish(self.fixture.development())
        for data in ("relative-data", str(self.fixture.project / "inside-data")):
            with self.subTest(data=data), patch.dict(os.environ, {"AI_LOOP_KIT_DATA": data}):
                before = self.snapshot()
                with (
                    patch.object(versions, "_acquire", side_effect=AssertionError("release fetch")),
                    patch.object(versions, "_acquire_development",
                                 side_effect=AssertionError("development fetch")),
                    patch.object(versions, "publish", side_effect=AssertionError("publication")),
                    self.assertRaises(versions.VersionError) as invalid,
                ):
                    versions.load(self.fixture.kit, self.fixture.project)
                self.assertEqual(self.snapshot(), before)
                self.assertIn("version data home", str(invalid.exception))
                refusals, notices = self.check_read_only(self.fixture.kit)
                self.assertEqual([refusal.guard for refusal in refusals], ["kit-folder"])
                self.assertEqual(notices, [])
                self.assertIn(
                    "setup.py found --development --kit-ref <full lowercase commit SHA>",
                    invalid.exception.next_command,
                )
                self.assertNotIn("release tag", invalid.exception.next_command)
                self.assertIn(invalid.exception.next_command, refusals[0].fix)

    def test_development_shared_file_validators_keep_development_recovery(self) -> None:
        self.fixture.workflow()
        prepared = self.fixture.development()
        versions.publish(prepared)
        original_record = prepared.path.read_bytes()
        tool = self.fixture.kit / "tool.sh"
        original_tool = tool.read_bytes()
        original_mode = tool.stat().st_mode & 0o777
        legacy = self.fixture.kit / "version.json"
        for case in (
            "non-regular-inventory", "unreadable-legacy", "invalid-record-inventory",
            "disagreeing-legacy",
        ):
            with self.subTest(case=case):
                body = dict(prepared.body)
                if case == "non-regular-inventory":
                    tool.unlink()
                    tool.symlink_to(self.fixture.kit / ".claude-plugin/plugin.json")
                elif case == "unreadable-legacy":
                    legacy.write_text("broken JSON")
                elif case == "invalid-record-inventory":
                    body["files"] = {}
                    prepared.path.write_text(json.dumps(body))
                else:
                    hashes = {name: item["sha256"] for name, item in prepared.body["files"].items()}
                    hashes["tool.sh"] = "b" * 64
                    legacy.write_text(json.dumps({"record": 1, "files": hashes}))
                try:
                    before = self.snapshot()
                    with (
                        patch.object(versions, "_acquire",
                                     side_effect=AssertionError("release fetch")),
                        patch.object(versions, "_acquire_development",
                                     side_effect=AssertionError("development fetch")),
                        patch.object(versions, "publish",
                                     side_effect=AssertionError("publication")),
                        self.assertRaises(versions.VersionError) as invalid,
                    ):
                        versions.verify(self.fixture.kit, body)
                    self.assertEqual(self.snapshot(), before)
                    expected = {
                        "non-regular-inventory": "non-regular file",
                        "unreadable-legacy": "legacy version record is unreadable",
                        "invalid-record-inventory": "record has no file inventory",
                        "disagreeing-legacy": "legacy version record disagrees with the "
                                              "verified development",
                    }
                    self.assertIn(expected[case], str(invalid.exception))
                    refusals, notices = self.check_read_only(self.fixture.kit)
                    self.assertEqual([refusal.guard for refusal in refusals], ["kit-folder"])
                    self.assertEqual(notices, [])
                    if case == "disagreeing-legacy":
                        self.assertIn("verified development", refusals[0].reason)
                    self.assertIn(
                        "setup.py found --development --kit-ref <full lowercase commit SHA>",
                        invalid.exception.next_command,
                    )
                    self.assertNotIn("release tag", invalid.exception.next_command)
                    self.assertIn("--development --kit-ref", refusals[0].fix)
                finally:
                    if case == "non-regular-inventory":
                        tool.unlink()
                        tool.write_bytes(original_tool)
                        tool.chmod(original_mode)
                    if legacy.exists():
                        legacy.unlink()
                    prepared.path.write_bytes(original_record)

        manifest = self.fixture.kit / ".claude-plugin/plugin.json"
        original_manifest = manifest.read_bytes()
        manifest.write_text(json.dumps({"name": "ai-loop-kit", "version": "0.1.0"}))
        try:
            files = versions.inventory(self.fixture.kit)
            hashes = {name: item["sha256"] for name, item in files.items()}
            hashes["tool.sh"] = "b" * 64
            legacy.write_text(json.dumps({"record": 1, "files": hashes}))
            release_body = {
                "schema": 1, "repository": versions.REPOSITORY, "plugin": "ai-loop-kit",
                "version": "0.1.0", "tag": "v0.1.0", "commit": self.fixture.commit,
                "files": files,
            }
            before = self.snapshot()
            with (
                patch.object(versions, "_acquire", side_effect=AssertionError("release fetch")),
                patch.object(versions, "_acquire_development",
                             side_effect=AssertionError("development fetch")),
                patch.object(versions, "publish", side_effect=AssertionError("publication")),
                self.assertRaises(versions.VersionError) as disagreement,
            ):
                versions.verify(self.fixture.kit, release_body)
            self.assertEqual(self.snapshot(), before)
            self.assertIn("verified release", str(disagreement.exception))
            self.assertIn("release tag", disagreement.exception.next_command)
        finally:
            legacy.unlink()
            manifest.write_bytes(original_manifest)

    def test_publication_refusals_keep_selected_mode_recovery_and_state(self) -> None:
        self.fixture.workflow()
        prepared = self.fixture.development()
        manifest = self.fixture.kit / ".claude-plugin/plugin.json"
        original_manifest = manifest.read_bytes()
        try:
            for development in (True, False):
                if development:
                    candidate = prepared
                else:
                    manifest.write_text(json.dumps({"name": "ai-loop-kit", "version": "0.1.0"}))
                    body = {
                        "schema": 1, "repository": versions.REPOSITORY, "plugin": "ai-loop-kit",
                        "version": "0.1.0", "tag": "v0.1.0", "commit": self.fixture.commit,
                        "files": versions.inventory(self.fixture.kit),
                    }
                    candidate = versions.Prepared(
                        self.fixture.kit, self.fixture.project,
                        prepared.path.parent.parent / "releases/v0.1.0.json", body, False,
                    )
                versions.publish(candidate)
                conflict = json.loads(json.dumps(candidate.body))
                conflict["files"]["tool.sh"]["sha256"] = "b" * 64
                candidate.path.write_text(json.dumps(conflict))
                with self.subTest(development=development, refusal="immutable-conflict"):
                    before = self.snapshot()
                    with (
                        patch.object(versions, "_acquire", side_effect=AssertionError("fetch")),
                        patch.object(versions, "_acquire_development",
                                     side_effect=AssertionError("development fetch")),
                        self.assertRaises(versions.VersionError) as error,
                    ):
                        versions.publish(candidate)
                    self.assertEqual(self.snapshot(), before)
                    self.assertIn("baseline conflicts; it was not replaced", str(error.exception))
                    if development:
                        self.assertIn("--development --kit-ref", error.exception.next_command)
                        self.assertNotIn("release tag", error.exception.next_command)
                    else:
                        self.assertIn("release tag", error.exception.next_command)
                candidate.path.unlink()
                with self.subTest(development=development, refusal="write-error"):
                    before = self.snapshot()
                    with (
                        patch.object(versions, "_acquire", side_effect=AssertionError("fetch")),
                        patch.object(versions, "_acquire_development",
                                     side_effect=AssertionError("development fetch")),
                        patch.object(os, "link",
                                     side_effect=OSError("fixture link refusal")),
                        self.assertRaises(versions.VersionError) as error,
                    ):
                        versions.publish(candidate)
                    self.assertEqual(self.snapshot(), before)
                    self.assertFalse(candidate.path.exists())
                    self.assertIsInstance(error.exception.__cause__, OSError)
                    self.assertIn("stable baseline could not be written", str(error.exception))
                    if development:
                        self.assertIn("--development --kit-ref", error.exception.next_command)
                        self.assertNotIn("release tag", error.exception.next_command)
                    else:
                        self.assertIn("release tag", error.exception.next_command)
        finally:
            manifest.write_bytes(original_manifest)
