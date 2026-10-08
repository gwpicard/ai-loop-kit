"""Hosted bootstrap exceptions run tests and close after the first product commit."""

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("hosted_check", ROOT / "kit/scripts/hosted-check.py")
assert SPEC is not None and SPEC.loader is not None
hosted = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hosted)


class HostedCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        # Preserve each repository for inspection, including failed checks.
        self.root = Path(tempfile.mkdtemp(prefix="ai-loop-hosted-"))
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.write("README.md", "# Project\n")
        self.commit()
        self.empty = self.git("rev-parse", "HEAD").strip()
        self.policy("")
        self.commit()
        self.founded = self.git("rev-parse", "HEAD").strip()

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.root), *args], check=True, capture_output=True, text=True
        ).stdout

    def write(self, name: str, text: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def policy(self, command: object) -> None:
        self.write(".agents/loop/policy.json", json.dumps({"test_command": command}))

    def commit(self) -> None:
        self.git("add", ".")
        self.git("commit", "-qm", "Fixture")

    def test_founding_passes_against_readme_only_base(self) -> None:
        self.assertEqual(hosted.run(self.root, self.empty, ""), 0, "F2-FOUND")

    def test_scaffold_really_runs_its_command(self) -> None:
        self.write("tests/runner.sh", "echo ran > proof\n")
        self.commit()
        self.assertEqual(hosted.run(self.root, self.founded, "sh tests/runner.sh"), 0)
        self.assertEqual((self.root / "proof").read_text(), "ran\n", "F2-SCAFFOLD")

    def test_scaffold_failure_is_red(self) -> None:
        self.write("src/app.py", "pass\n")
        self.commit()
        self.assertEqual(hosted.run(self.root, self.founded, "exit 7"), 7, "F2-RED")

    def test_scaffold_without_command_is_refused(self) -> None:
        self.write("src/app.py", "pass\n")
        self.commit()
        self.assertEqual(hosted.run(self.root, self.founded, ""), 1, "F2-MISSING")

    def test_later_empty_policy_is_refused(self) -> None:
        self.write("src/app.py", "pass\n")
        self.commit()
        base = self.git("rev-parse", "HEAD").strip()
        self.assertEqual(hosted.run(self.root, base, "exit 0"), 1, "F2-LATER")

    def test_removed_policy_command_cannot_reopen_exception(self) -> None:
        self.policy("exit 0")
        self.commit()
        base = self.git("rev-parse", "HEAD").strip()
        self.policy("")
        self.commit()
        self.assertEqual(hosted.run(self.root, base, "exit 0"), 1, "F2-REMOVAL")

    def test_missing_or_unreadable_base_is_refused(self) -> None:
        for base in ("", "missing-ref"):
            with self.subTest(base=base):
                self.assertEqual(hosted.run(self.root, base, "exit 0"), 1, "F2-BASE")

    def test_whitespace_command_is_empty(self) -> None:
        self.policy("  \n")
        self.commit()
        self.assertEqual(hosted.run(self.root, self.empty, ""), 0, "F2-WHITESPACE")

    def test_bad_policy_never_grants_exception(self) -> None:
        values: tuple[object, ...] = (None, 7, [], {})
        for value in values:
            with self.subTest(value=value):
                self.policy(value)
                self.assertEqual(hosted.run(self.root, self.empty, "exit 0"), 1, "F2-POLICY")
        self.write(".agents/loop/policy.json", "not json")
        self.assertEqual(hosted.run(self.root, self.empty, "exit 0"), 1, "F2-JSON")

    def test_configured_command_runs_without_bootstrap_base(self) -> None:
        self.policy("exit 6")
        self.assertEqual(hosted.run(self.root, "", "exit 0"), 6, "F2-CONFIGURED")
