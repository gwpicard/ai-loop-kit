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
