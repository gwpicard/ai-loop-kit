"""The judge writer can work after the dashboard creates its event folder."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import KIT, Project, git

# isort: split
import gate
from helpers import FakeGitHub


class JudgeLoopFolderTest(unittest.TestCase):
    def setUp(self):
        self.project = Project()
        self.addCleanup(self.project.close)
        self.root = self.project.root
        self.base = self.root.parent
        (self.root / ".gitignore").unlink()
        git(self.root, "add", "-u")
        git(self.root, "commit", "--quiet", "-m", "Start without project ignores")
        git(self.root, "switch", "--quiet", "-c", "piece/1")
        self.judge = "tests/judge/test_piece.py"
        self.data = {"Intent": "A piece", "Approach": "", "Contract": "D1: works",
                     "Files": self.judge}

    def capture(self):
        return gate.capture(FakeGitHub(), "A piece", "", root=self.root)

    def invoke(self, writes=None):
        fake = self.base / "fake-agent"
        fake.write_text(
            f"#!{sys.executable}\n"
            "import json, pathlib, sys\n"
            "for name, text in json.loads(__import__('os').environ['WRITES']).items():\n"
            "    path = pathlib.Path(name)\n"
            "    path.parent.mkdir(parents=True, exist_ok=True)\n"
            "    path.write_text(text)\n"
            "text = __import__('os').environ['ANSWER']\n"
            "print(json.dumps({'type':'assistant','message':{'content':[{'type':'text','text':text}]}}))\n")
        fake.chmod(0o755)
        source, output = self.base / "input.json", self.base / "answer.txt"
        source.write_text(json.dumps(self.data))
        verdict = {"judge_files": [self.judge], "tests_per_id": True, "notes": "ok"}
        env = {**os.environ, "LOOP_CLAUDE": str(fake), "LOOP_CODEX": str(fake),
               "WRITES": json.dumps(writes or {self.judge: "# judge\n"}),
               "ANSWER": "<verdict>" + json.dumps(verdict) + "</verdict>"}
        result = subprocess.run(
            [sys.executable, str(KIT / "scripts/session.py"), "--role", "judge-writer",
             "--agent", "claude", "--folder", str(self.root), "--input", str(source),
             "--output", str(output)], env=env, capture_output=True, text=True,
            timeout=10, check=False)
        return result, output

    def test_D1_D2_capture_event_folder_is_ignored_and_judge_is_accepted(self):
        self.capture()
        result, output = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(output.exists())
        self.assertEqual(git(self.root, "status", "--porcelain"), "")
        self.assertEqual(git(self.root, "rev-parse", "--git-path", "info/exclude"),
                         ".git/info/exclude")
        exclude = (self.root / ".git/info/exclude").read_text().splitlines()
        self.assertEqual(exclude.count("/.loop/"), 1)
        with (self.root / ".loop/events.jsonl").open("a") as events:
            events.write("{}\n")
        self.capture()
        lines = (self.root / ".git/info/exclude").read_text().splitlines()
        self.assertEqual(lines.count("/.loop/"), 1)
        self.assertEqual(git(self.root, "status", "--porcelain"), "")
        self.assertEqual(git(self.root, "diff", "--name-only", "main...HEAD"), self.judge)

    def test_D3_other_untracked_file_is_still_refused(self):
        self.capture()
        (self.root / "keep.txt").write_text("keep\n")
        result, output = self.invoke()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("judge-writer requires a clean working tree", result.stderr)
        self.assertFalse(output.exists())

    def test_D4_existing_loop_folder_is_accepted_without_committing_it(self):
        (self.root / ".loop").mkdir()
        (self.root / ".loop/events.jsonl").write_text("{}\n")
        result, _ = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git(self.root, "diff", "--name-only", "main...HEAD"), self.judge)


if __name__ == "__main__":
    unittest.main()
