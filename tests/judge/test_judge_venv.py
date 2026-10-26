"""Judge writing accepts changes in an ignored project .venv and refuses the rest."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import KIT, Project, git


class JudgeVenvTest(unittest.TestCase):
    judge = "tests/judge/test_subject.py"
    record = ".venv/lib/python3.13/site-packages/subject-0.1.0.dist-info/RECORD"

    def new_project(self, ignore=".venv/\n"):
        project = Project()
        self.addCleanup(project.close)
        self.root = project.root
        self.base = self.root.parent
        (self.root / ".gitignore").write_text(".loop/\n" + ignore)
        git(self.root, "add", "--all")
        git(self.root, "commit", "--quiet", "--allow-empty", "-m", "Ignore the environment")
        git(self.root, "switch", "--quiet", "-c", "piece/1")
        # Prepare has already installed the project into its .venv, as `uv sync` would.
        (self.root / self.record).parent.mkdir(parents=True)
        (self.root / self.record).write_text("subject/__init__.py,sha256=old\n")

    def invoke(self):
        fake = self.base / "fake-agent"
        fake.write_text(
            f"#!{sys.executable}\n"
            "import json, os, pathlib, sys\n"
            "for name, text in json.loads(os.environ['WRITES']).items():\n"
            "    path = pathlib.Path(name)\n"
            "    path.parent.mkdir(parents=True, exist_ok=True)\n"
            "    path.write_text(text)\n"
            "text = os.environ['ANSWER']\n"
            "event = ({'type': 'assistant', 'message': {'content': [\n"
            "    {'type': 'text', 'text': text}]}} if '-p' in sys.argv else\n"
            "    {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': text}})\n"
            "print(json.dumps(event))\n")
        fake.chmod(0o755)
        source = self.base / "input.json"
        source.write_text(json.dumps({"Intent": "Check the subject", "Approach": "",
                                      "Contract": "D1: value is one", "Files": self.judge}))
        output = self.base / "answer.txt"
        verdict = {"judge_files": [self.judge], "tests_per_id": True, "notes": "ok"}
        # `uv run` reinstalls the project, so the test run rewrites the .venv RECORD.
        writes = {self.judge: "def test_D1_value_is_one():\n    assert 1 == 2\n",
                  self.record: "subject/__init__.py,sha256=new\n"}
        env = {**os.environ, "LOOP_CLAUDE": str(fake), "LOOP_CODEX": str(fake),
               "WRITES": json.dumps(writes),
               "ANSWER": "<verdict>" + json.dumps(verdict) + "</verdict>"}
        env.pop("CI", None)
        return subprocess.run(
            [sys.executable, "-B", str(KIT / "scripts/session.py"), "--role", "judge-writer",
             "--agent", "codex", "--folder", str(self.root), "--input", str(source),
             "--output", str(output)], env=env, capture_output=True, text=True,
            timeout=120, check=False), output

    def test_D1_an_ignored_venv_rewritten_by_uv_is_accepted(self):
        self.new_project()
        result, output = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(output.is_file())
        self.assertEqual(git(self.root, "diff", "--name-only", "main...HEAD"), self.judge)

    def test_D2_an_unignored_venv_is_still_refused(self):
        self.new_project(ignore="")
        result, output = self.invoke()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
