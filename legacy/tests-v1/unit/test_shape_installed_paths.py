"""Run the shipping shape report from a project which has no local kit."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "kit/skills/shape/SKILL.md"


def report_command(text: str) -> str:
    matches: list[str] = re.findall(r"^!`([^`]+)`$", text, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError("The skill needs one live report command")
    return matches[0]


class InstalledShapePaths(unittest.TestCase):
    def run_report(self, command: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="shape-installed-") as temporary:
            base = Path(temporary)
            project = base / "founded project"
            project.mkdir()
            (project / "AGENTS.md").write_text("A founded fixture.\n")
            self.assertFalse((project / "kit").exists())
            installation = base / "installed kit with spaces"
            scripts = installation / "scripts"
            scripts.mkdir(parents=True)
            (scripts / "gate.py").write_text(
                "import json, sys\n"
                "print(json.dumps({'argv': sys.argv[1:], 'pieces': [], 'fixture': True}))\n"
            )
            environment = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(installation))
            environment.pop("PYTHONPATH", None)
            return subprocess.run(
                ["sh", "-c", command], cwd=project, env=environment,
                capture_output=True, text=True, timeout=10, check=False,
            )

    def test_live_report_runs_from_founded_project_without_local_kit(self) -> None:
        result = self.run_report(report_command(SKILL.read_text()))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "argv": ["report", "--json", "--brief"], "pieces": [], "fixture": True,
        })

    def test_relative_path_control_fails_in_same_founded_project(self) -> None:
        result = self.run_report("python3 kit/scripts/gate.py report --json --brief")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_unquoted_installed_path_control_fails_with_spaces(self) -> None:
        result = self.run_report(
            "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gate.py report --json --brief"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_all_executable_gate_examples_select_quoted_installation(self) -> None:
        snippets = re.findall(r"`([^`]+)`", SKILL.read_text())
        executable = [text for text in snippets if re.search(
            r"gate\.py(?:\"|\')? (?:capture|report|spec|answer|branch|move <)", text
        )]
        self.assertGreaterEqual(len(executable), 8)
        for command in executable:
            with self.subTest(command=command):
                self.assertTrue(command.startswith(
                    'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gate.py" '
                ))


if __name__ == "__main__":
    unittest.main()
