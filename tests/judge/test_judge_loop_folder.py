"""The judge writer can work after the dashboard creates its event folder."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_D2_linked_worktree_uses_the_common_exclude_file(self):
        linked = self.base / "linked"
        git(self.root, "worktree", "add", "--quiet", "-b", "piece/2", str(linked), "main")
        gate.run_event(linked, "capture", 2, "shaping", reason="capture")
        self.assertEqual(git(linked, "status", "--porcelain"), "")
        exclude = (self.root / ".git/info/exclude").read_text().splitlines()
        self.assertEqual(exclude.count("/.loop/"), 1)

    def test_D2_creates_a_missing_info_directory_and_keeps_recording(self):
        root = self.base / "template-project"
        root.mkdir()
        git(self.base, "init", "--quiet", "--template=", str(root))
        self.assertFalse((root / ".git/info").exists())
        gate.run_event(root, "capture", 1, "shaping", reason="capture")
        gate.run_event(root, "pull-back", 1, "shaping", reason="pull-back")
        events = (root / ".loop/events.jsonl").read_text().splitlines()
        self.assertEqual(len(events), 2)
        self.assertEqual(git(root, "status", "--porcelain"), "")
        exclude = (root / ".git/info/exclude").read_text().splitlines()
        self.assertEqual(exclude.count("/.loop/"), 1)

    def test_D2_appends_to_non_utf8_exclude_without_changing_its_bytes(self):
        exclude = self.root / ".git/info/exclude"
        original = b"# Local exclusions: caf\xe9\n"
        exclude.write_bytes(original)
        self.capture()
        self.assertEqual(exclude.read_bytes(), original + b"/.loop/\n")
        self.assertEqual((len((self.root / ".loop/events.jsonl").read_text().splitlines()),
                          git(self.root, "status", "--porcelain")), (1, ""))

    def test_D2_separates_existing_exclude_rule_without_a_final_newline(self):
        exclude = self.root / ".git/info/exclude"
        exclude.write_bytes(b"local-only.txt")
        (self.root / "local-only.txt").write_text("ignored\n")
        gate.run_event(self.root, "capture", 1, "shaping", reason="capture")
        self.assertEqual(exclude.read_bytes(), b"local-only.txt\n/.loop/\n")
        self.assertEqual(git(self.root, "status", "--porcelain"), "")

    def test_D2_records_event_when_exclude_cannot_be_updated(self):
        self.capture()
        exclude = self.root / ".git/info/exclude"
        open_path = Path.open

        def deny_exclude(path, *args, **kwargs):
            if path == exclude and args == ("ab",):
                raise PermissionError("exclude is read-only")
            return open_path(path, *args, **kwargs)

        with patch.object(Path, "open", deny_exclude):
            gate.run_event(self.root, "pull-back", 1, "shaping", reason="pull-back")
        self.assertEqual(len((self.root / ".loop/events.jsonl").read_text().splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
