"""Committed bootstrap commands constrain captured and already existing branches."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit/scripts"))
from loop import bootstrap  # noqa: E402
from loop.cli import Failure  # noqa: E402


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="bootstrap-preparation-"))
        self.git("init", "-qb", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.write("README.md", "# Project\n")
        self.commit()

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              capture_output=True, text=True).stdout

    def write(self, path: str, text: str) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def workflow(self, command: str) -> None:
        self.write(bootstrap.WORKFLOW, bootstrap.ENTRY + json.dumps(command) + "\n")

    def commit(self) -> None:
        self.git("add", "-A")
        self.git("commit", "-qm", "Fixture")

    def test_working_only_foundation_is_refused(self) -> None:
        self.workflow("sh tests/run.sh")
        with self.assertRaises(Failure):
            bootstrap.check(self.root, "sh tests/run.sh")

    def test_committed_selected_command_passes(self) -> None:
        self.workflow("sh tests/run.sh")
        self.commit()
        bootstrap.check(self.root, "sh tests/run.sh")

    def test_a_repeated_working_only_change_is_refused(self) -> None:
        self.workflow("old")
        self.commit()
        self.workflow("new")
        for _ in range(2):
            with self.assertRaises(Failure):
                bootstrap.check(self.root, "new")

    def test_unsaved_custom_workflow_is_preserved(self) -> None:
        self.write(bootstrap.WORKFLOW, "# My workflow\n")
        before = (self.root / bootstrap.WORKFLOW).read_bytes()
        bootstrap.check(self.root, "custom")
        self.assertEqual((self.root / bootstrap.WORKFLOW).read_bytes(), before)

    def test_committed_marker_is_checked_when_working_marker_is_removed(self) -> None:
        self.workflow("old")
        self.commit()
        self.write(bootstrap.WORKFLOW, "# My unsaved change\n")
        with self.assertRaises(Failure):
            bootstrap.check(self.root, "new")

    def test_real_committed_policy_command_supersedes_bootstrap(self) -> None:
        self.workflow("old")
        self.write(bootstrap.POLICY, json.dumps({"test_command": "npm test"}))
        self.commit()
        bootstrap.check(self.root, "new")

    def test_working_policy_command_cannot_bypass_bootstrap(self) -> None:
        self.workflow("old")
        self.commit()
        self.write(bootstrap.POLICY, json.dumps({"test_command": "exit 0"}))
        with self.assertRaises(Failure):
            bootstrap.check(self.root, "new")

    def test_an_existing_branch_is_checked_against_its_own_tree(self) -> None:
        self.workflow("old")
        self.commit()
        self.git("branch", "piece-1")
        self.workflow("new")
        self.commit()
        bootstrap.check(self.root, "new")
        with self.assertRaises(Failure):
            bootstrap.check(self.root, "new", ref="piece-1", use_working_marker=False)

    def test_existing_branch_without_marker_cannot_escape_prepared_main(self) -> None:
        self.git("branch", "piece-1")
        self.workflow("selected")
        self.commit()
        with self.assertRaises(Failure):
            bootstrap.check(self.root, "selected", ref="piece-1", use_working_marker=False)

    def test_custom_main_and_existing_branch_remain_the_persons_workflow(self) -> None:
        self.write(bootstrap.WORKFLOW, "# Custom workflow\n")
        self.commit()
        self.git("branch", "piece-1")
        bootstrap.check(self.root, "selected", ref="piece-1", use_working_marker=False)
