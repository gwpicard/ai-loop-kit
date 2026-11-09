"""The judge writer is not refused over files that tools write while it runs the judge."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import KIT, Project, git


class JudgeWriterToolPathsTest(unittest.TestCase):
    def setUp(self):
        self.project = Project()
        self.addCleanup(self.project.close)
        self.root = self.project.root
        self.base = self.root.parent
        git(self.root, "switch", "--quiet", "-c", "piece/1")
        self.judge = "tests/judge/test_piece.py"
        self.data = {"Intent": "A piece", "Approach": "", "Contract": "D1: works",
                     "Files": self.judge}

    def unignore(self):
        (self.root / ".gitignore").write_text("")
        git(self.root, "add", "-A")
        git(self.root, "commit", "--quiet", "-m", "Drop ignores")

    def invoke(self, writes):
        fake = self.base / "fake-agent"
        fake.write_text(
            f"#!{sys.executable}\n"
            "import json, os, pathlib\n"
            "for name, text in json.loads(os.environ['WRITES']).items():\n"
            "    path = pathlib.Path(name)\n"
            "    path.parent.mkdir(parents=True, exist_ok=True)\n"
            "    path.write_text(text)\n"
            "text = os.environ['ANSWER']\n"
            "print(json.dumps({'type':'assistant','message':{'content':[{'type':'text','text':text}]}}))\n")
        fake.chmod(0o755)
        source, output = self.base / "input.json", self.base / "answer.txt"
        source.write_text(json.dumps(self.data))
        verdict = {"judge_files": [self.judge], "tests_per_id": True, "notes": "ok"}
        env = {**os.environ, "LOOP_CLAUDE": str(fake), "LOOP_CODEX": str(fake),
               "WRITES": json.dumps({self.judge: "# judge\n", **writes}),
               "ANSWER": "<verdict>" + json.dumps(verdict) + "</verdict>"}
        result = subprocess.run(
            [sys.executable, str(KIT / "scripts/session.py"), "--role", "judge-writer",
             "--agent", "claude", "--folder", str(self.root), "--input", str(source),
             "--output", str(output)], env=env, capture_output=True, text=True,
            timeout=30, check=False)
        return result

    def committed(self):
        return git(self.root, "diff", "--name-only", "main...HEAD")

    def test_D1_pytest_of_user_folder_is_accepted_when_not_ignored(self):
        self.unignore()
        result = self.invoke({"pytest-of-someone/pytest-0/case0/data.txt": "x\n"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.committed(), self.judge)

    def test_D1_pytest_of_user_folder_is_accepted_when_ignored(self):
        (self.root / ".gitignore").write_text(".loop/\npytest-of-*/\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "--quiet", "-m", "Ignore pytest folders")
        result = self.invoke({"pytest-of-someone/pytest-0/case0/data.txt": "x\n"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.committed(), self.judge)

    def test_D2_file_under_loop_folder_is_accepted_when_not_ignored(self):
        self.unignore()
        result = self.invoke({".loop/events.jsonl": "{}\n"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.committed(), self.judge)

    def test_D2_changed_file_under_loop_folder_is_accepted(self):
        self.unignore()
        (self.root / ".loop").mkdir()
        (self.root / ".loop/events.jsonl").write_text("{}\n")
        result = self.invoke({".loop/events.jsonl": "{}\n{}\n"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.committed(), self.judge)

    def test_D3_other_new_file_is_refused_and_named(self):
        self.unignore()
        result = self.invoke({"stray/notes.txt": "n\n"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stray/notes.txt", result.stderr)

    def test_D4_dirty_tree_outside_loop_refuses_to_start(self):
        self.unignore()
        (self.root / "README.md").write_text("changed\n")
        result = self.invoke({".loop/events.jsonl": "{}\n"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("judge-writer requires a clean working tree", result.stderr)


if __name__ == "__main__":
    unittest.main()
