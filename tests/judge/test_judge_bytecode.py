"""Judge writing tolerates Python bytecode without admitting other paths."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import KIT, Project, git


class JudgeBytecodeTest(unittest.TestCase):
    judge = "tests/judge/test_subject.py"

    def setUp(self):
        self.project = Project()
        self.addCleanup(self.project.close)
        self.root = self.project.root
        self.base = self.root.parent
        (self.root / ".gitignore").unlink()
        (self.root / "subject.py").write_text("value = 1\n")
        git(self.root, "add", "--all")
        git(self.root, "commit", "--quiet", "-m", "Use a project without ignore rules")
        git(self.root, "switch", "--quiet", "-c", "piece/1")

    def invoke(self, backend, extra=None, reported=None, force_bytecode=False,
               commit_files=False):
        fake = self.base / "fake-agent"
        fake.write_text(
            f"#!{sys.executable}\n"
            "import json, os, pathlib, subprocess, sys\n"
            "pathlib.Path(os.environ['ENV_RECORD']).write_text(\n"
            "    os.environ.get('PYTHONDONTWRITEBYTECODE', 'unset'))\n"
            "for name, text in json.loads(os.environ['WRITES']).items():\n"
            "    path = pathlib.Path(name)\n"
            "    path.parent.mkdir(parents=True, exist_ok=True)\n"
            "    path.write_text(text)\n"
            "env = dict(os.environ)\n"
            "if os.environ['FORCE_BYTECODE'] == '1':\n"
            "    env.pop('PYTHONDONTWRITEBYTECODE', None)\n"
            "subprocess.run([sys.executable, '-c', \"import runpy, sys; sys.pycache_prefix = None; "
            "runpy.run_path('tests/judge/test_subject.py')['test_D1_value']()\"],\n"
            "    env=env, check=True)\n"
            "if os.environ['COMMIT_FILES'] == '1':\n"
            "    subprocess.run(['git', 'add', '--', *json.loads(os.environ['WRITES'])],\n"
            "        check=True)\n"
            "    subprocess.run(['git', 'commit', '-m', 'Write judge files'], check=True)\n"
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
        verdict = {"judge_files": reported if reported is not None else [self.judge],
                   "tests_per_id": True, "notes": "ok"}
        writes = {self.judge: "def test_D1_value():\n"
                             "    import subject\n    assert subject.value == 1\n"}
        writes.update(extra or {})
        env = {**os.environ, "LOOP_CLAUDE": str(fake), "LOOP_CODEX": str(fake),
               "WRITES": json.dumps(writes), "ENV_RECORD": str(self.base / "env.txt"),
               "FORCE_BYTECODE": "1" if force_bytecode else "0",
               "COMMIT_FILES": "1" if commit_files else "0",
               "ANSWER": "<verdict>" + json.dumps(verdict) + "</verdict>"}
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        result = subprocess.run(
            [sys.executable, "-B", str(KIT / "scripts/session.py"), "--role", "judge-writer",
             "--agent", backend, "--folder", str(self.root), "--input", str(source),
             "--output", str(output)], env=env, capture_output=True, text=True,
            timeout=10, check=False)
        return result, output

    def test_D1_writer_runs_its_test_without_creating_bytecode(self):
        for backend in ("claude", "codex"):
            with self.subTest(backend=backend):
                result, output = self.invoke(backend)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(output.is_file())
                self.assertEqual((self.base / "env.txt").read_text(), "1")
                self.assertEqual(list(self.root.rglob("*.pyc")), [])

    def test_D1_D4_stray_bytecode_before_and_during_the_run_is_not_committed(self):
        cache = self.root / "tests/judge/__pycache__/old.pyc"
        cache.parent.mkdir(parents=True)
        cache.write_bytes(b"old bytecode")
        loose = self.root / "loose.pyc"
        loose.write_bytes(b"loose bytecode")
        for backend in ("claude", "codex"):
            with self.subTest(backend=backend):
                result, _ = self.invoke(backend, {str(cache.relative_to(self.root)): "new cache"},
                                        force_bytecode=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(list(self.root.glob("__pycache__/subject*.pyc")))
                self.assertEqual(cache.read_text(), "new cache")
                self.assertEqual(loose.read_bytes(), b"loose bytecode")
                self.assertEqual(git(self.root, "diff", "--name-only", "main...HEAD"), self.judge)
                self.assertEqual(git(self.root, "status", "--porcelain",
                                     "--untracked-files=no"), "")

    def test_D2_D3_other_files_are_refused_and_the_first_path_is_named(self):
        for backend in ("claude", "codex"):
            with self.subTest(backend=backend):
                before = git(self.root, "rev-parse", "HEAD")
                extra = {"tests/judge/a.txt": "keep this work", "tests/judge/z.txt": "also keep"}
                result, output = self.invoke(backend, extra, force_bytecode=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("outside the approved Exit Files: tests/judge/a.txt", result.stderr)
                next_step = result.stderr.split("next:", 1)[1]
                self.assertIn("tests/judge/a.txt", next_step)
                self.assertNotIn("restore the capability", next_step)
                self.assertFalse(output.exists())
                self.assertEqual(git(self.root, "rev-parse", "HEAD"), before)
                for name, text in extra.items():
                    self.assertEqual((self.root / name).read_text(), text)
                    (self.root / name).unlink()
                (self.root / self.judge).unlink()

    def test_D2_D3_unapproved_reported_path_is_named(self):
        result, _ = self.invoke("codex", reported=["tests/judge/other.py"])
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("outside the approved Exit Files: tests/judge/other.py", result.stderr)
        self.assertIn("tests/judge/other.py", result.stderr.split("next:", 1)[1])

    def test_D2_non_bytecode_in_a_cache_folder_is_still_refused(self):
        name = "tests/judge/__pycache__/notes.txt"
        result, _ = self.invoke("claude", {name: "keep these notes"})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("outside the approved Exit Files: " + name, result.stderr)
        self.assertEqual((self.root / name).read_text(), "keep these notes")

    def test_D4_staged_bytecode_is_kept_out_of_the_judge_commit(self):
        path = self.root / "staged.pyc"
        path.write_bytes(b"keep staged bytecode")
        git(self.root, "add", "--", path.name)
        result, _ = self.invoke("claude")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git(self.root, "diff", "--name-only", "main...HEAD"), self.judge)
        self.assertEqual(git(self.root, "diff", "--cached", "--name-only"), path.name)
        self.assertEqual(path.read_bytes(), b"keep staged bytecode")

    def test_D4_writer_committed_bytecode_is_refused(self):
        name = "unapproved.pyc"
        for backend in ("claude", "codex"):
            with self.subTest(backend=backend):
                before = git(self.root, "rev-parse", "HEAD")
                text = f"{backend} cache"
                result, output = self.invoke(backend, {name: text}, commit_files=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("outside the approved Exit Files: " + name, result.stderr)
                self.assertFalse(output.exists())
                self.assertNotEqual(git(self.root, "rev-parse", "HEAD"), before)
                self.assertEqual(git(self.root, "show", "HEAD:" + name), text)
                self.assertEqual((self.root / name).read_text(), text)

    def test_D4_writer_can_commit_only_approved_files(self):
        result, output = self.invoke("codex", commit_files=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(output.is_file())
        self.assertEqual(git(self.root, "diff", "--name-only", "main...HEAD"), self.judge)


if __name__ == "__main__":
    unittest.main()
