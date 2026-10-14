"""The generated scaffold spec conserves a file that founding actually creates."""

from __future__ import annotations

import argparse
import importlib.util
import os
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
from loop import judge, spec, versions  # noqa: E402


def module_at(name: str, path: Path) -> Any:
    description = importlib.util.spec_from_file_location(name, path)
    assert description is not None and description.loader is not None
    module = importlib.util.module_from_spec(description)
    description.loader.exec_module(module)
    return module


class FirstPieceFoundationTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="first-piece-foundation-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.project = self.folder / "project"
        self.project.mkdir()
        self.scratch = self.folder / "scratch"
        self.scratch.mkdir()
        config = self.folder / "gitconfig"
        config.write_text("")
        environment = patch.dict(os.environ, {
            "GIT_CONFIG_GLOBAL": str(config), "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "Local checks", "GIT_AUTHOR_EMAIL": "checks@example.invalid",
            "GIT_COMMITTER_NAME": "Local checks", "GIT_COMMITTER_EMAIL": "checks@example.invalid",
            "GIT_TERMINAL_PROMPT": "0", "AI_LOOP_KIT_DATA": str(self.folder / "data"),
            "TMPDIR": str(self.scratch),
        })
        environment.start()
        self.addCleanup(environment.stop)
        temporary_root = patch("tempfile.tempdir", str(self.scratch))
        temporary_root.start()
        self.addCleanup(temporary_root.stop)
        self.git("init", "-q", "-b", "main")
        self.existing = self.project / "person-data.txt"
        self.existing.write_text("existing project data\n")
        self.existing.chmod(0o640)
        self.original = (self.existing.read_bytes(), self.existing.stat().st_mode)
        self.setup = module_at("first_piece_foundation_setup", ROOT / "kit/scripts/setup.py")
        self.fixture = module_at("first_piece_release_fixture",
                                 ROOT / "tests/lib/version-fixture.py")
        self.kit = self.folder / "installed-kit"
        shutil.copytree(ROOT / "kit", self.kit,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "version.json"))
        prepared: versions.Prepared = self.fixture.release(self.kit, self.project, publish=False)
        versions.verify(self.kit, prepared.body)
        parser = argparse.ArgumentParser()
        self.setup.setup(parser)
        args = parser.parse_args([
            "found", "--project", str(self.project), "--kit-dir", str(self.kit),
            "--language", "python", "--test-command", "python3 -m unittest discover -s tests",
        ])
        # The annotated offline helper already acquired and verified this immutable release.
        # Founding, stable publication and generated project files remain real.
        with (
            patch.object(self.setup, "project_root", return_value=self.project),
            patch.object(self.setup, "check_tooling", return_value=False),
            patch.object(self.setup, "check_origin", return_value="a" * 40),
            patch.object(versions, "prepare", return_value=prepared),
            patch.object(self.setup, "label_step", return_value={"status": "offline fixture"}),
        ):
            self.setup.step_found(args)

    def git(self, *arguments: str) -> str:
        result = subprocess.run(["git", "-C", str(self.project), *arguments],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                timeout=10, check=True)
        return result.stdout.strip()

    def parsed(self) -> dict[str, Any]:
        body = self.setup.first_piece_body(self.kit, "python3 -m unittest discover -s tests")
        parsed: dict[str, Any] = spec.parse(body).to_dict()
        self.assertTrue(parsed["found"])
        self.assertEqual(parsed["missing"], [])
        self.assertEqual(parsed["judge"]["kind"], "scaffold")
        return parsed

    def commit(self) -> None:
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", "Founded fixture")

    def test_foundation_without_readme_preserves_data_and_missing_runner(self) -> None:
        self.assertFalse((self.project / "README.md").exists())
        self.assertTrue((self.project / "docs/overview.md").is_file())
        self.assertEqual((self.existing.read_bytes(), self.existing.stat().st_mode), self.original)
        self.assertFalse((self.project / "tests").exists())
        self.assertFalse((self.project / "pyproject.toml").exists())

    def test_generated_conservation_passes_on_clean_founded_main_without_readme(self) -> None:
        parsed = self.parsed()
        self.assertEqual(parsed["must_stay_checks"], ["test -f docs/overview.md"])
        self.commit()
        self.assertEqual(self.git("status", "--porcelain"), "")
        for command in parsed["must_stay_checks"]:
            result = judge.run(command, self.project, "main", time_limit=10)
            self.assertEqual(result["outcome"], "passed", result)
            self.assertNotIn("cleanup_note", result)
        self.assertFalse((self.project / "README.md").exists())
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_missing_overview_fails_even_when_readme_exists(self) -> None:
        parsed = self.parsed()
        (self.project / "docs/overview.md").unlink()
        (self.project / "README.md").write_text("README does not replace the overview.\n")
        self.commit()
        for command in parsed["must_stay_checks"]:
            result = judge.run(command, self.project, "main", time_limit=10)
            self.assertNotEqual(result["outcome"], "passed", result)
            self.assertEqual(result["exit_code"], 1)
            self.assertNotIn("cleanup_note", result)
        self.assertEqual(list(self.scratch.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
