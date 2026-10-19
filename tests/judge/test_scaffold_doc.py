"""Setup leads an empty project to a scaffold spec the gate recognises."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2] / "kit"
sys.path.insert(0, str(KIT.parent / "tests"))

from helpers import Project, git  # noqa: E402
from spec import Refused, parse_spec  # noqa: E402


class ScaffoldDocTest(unittest.TestCase):
    def test_D1_setup_links_to_a_supported_scaffold_example(self):
        setup = (KIT / "skills/setup/SKILL.md").read_text()
        self.assertTrue("<KIT>/examples/scaffold.md" in setup,
                        "setup must link directly to the scaffold example")
        guide = (KIT / "examples/scaffold.md").read_text()
        examples = re.findall(r"```markdown\n(.*?)```", guide, re.DOTALL)
        self.assertEqual(len(examples), 1)
        spec = parse_spec(examples[0])
        self.assertEqual(spec.kind, "scaffold")
        self.assertEqual(spec.checks[0]["legacy_kind"], "scaffold")
        self.assertEqual(spec.command, "python3 -m unittest discover -s tests -v")
        self.assertEqual(list(spec.done_when), ["D1"])
        self.assertIn("## Risks", examples[0])
        self.assertIn("[scaffold example](examples/scaffold.md)",
                      (KIT / "spec-format.md").read_text())

    def test_D2_scaffold_uses_the_existing_judge_form(self):
        body = self.example()
        self.assertIn("## Judge\nKind: scaffold", body)
        self.assertNotIn("## Exit", body)
        for path in (KIT / "examples/scaffold.md", KIT.parent / "docs/DESIGN.md"):
            with self.subTest(path=path):
                text = " ".join(path.read_text().split())
                self.assertIn("Scaffold pieces use `## Judge` with `Kind: scaffold`", text)

    def example(self):
        guide = (KIT / "examples/scaffold.md").read_text()
        return re.search(r"```markdown\n(.*?)```", guide, re.DOTALL).group(1)

    def test_D1_example_keeps_existing_ready_and_submit_rules(self):
        import gate
        import run

        body = self.example()
        project = Project()
        self.addCleanup(project.close)
        command = parse_spec(body).command
        project.loop_section(command, prepare="test -f tests/test_runner.py")
        n = project.piece(spec=body)
        gate.move(project.gh, project.root, n, "ready")
        ready = gate.last_record(project.gh.comments(n), "ready")
        self.assertEqual(ready["kind"], "scaffold")
        self.assertEqual(ready["regression_main"]["reason"], "scaffold: no test runner on main")
        gate.move(project.gh, project.root, n, "building")
        folder = run.worktree(project.root, n)
        (folder / "tests").mkdir()
        passed, output = gate.judge(folder, ready)
        self.assertFalse(passed)
        self.assertIn("Ran 0 tests", output)
        (folder / "tests/test_runner.py").write_text(
            "import unittest\nclass RunnerTest(unittest.TestCase):\n"
            "    def test_runner(self):\n        self.assertEqual(2 + 2, 4)\n")
        git(folder, "add", "tests")
        git(folder, "commit", "--quiet", "-m", "Add the first test")
        gate.move(project.gh, project.root, n, "approval", folder=folder)
        self.assertIn("state:approval", project.gh.issue(n)["labels"])

    def test_D3_parser_keeps_existing_scaffold_syntax(self):
        body = ("## Intent\nSet up tests.\nOut of scope:\n- Product features.\n"
                "## Contract\n- D1: The runner runs a test.\n## Judge\n"
                "Kind: scaffold\nCommand: `python3 -m unittest discover -s tests -v`\n")
        parsed = parse_spec(body)
        self.assertEqual(parsed.kind, "scaffold")
        self.assertEqual(parsed.files, [])
        self.assertEqual(parsed.checks[0]["legacy_kind"], "scaffold")
        with self.assertRaises(Refused) as caught:
            parse_spec(body.replace("## Judge", "## Exit\n### Tests"))
        self.assertIn("'Kind:' does not belong in an Exit check", caught.exception.reason)


if __name__ == "__main__":
    unittest.main()
