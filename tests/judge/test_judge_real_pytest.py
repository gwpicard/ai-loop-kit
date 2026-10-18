"""Judge writing accepts real pytest caches and refuses other side effects."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import KIT, Project, git

CACHES = ("__pycache__", ".pytest_cache", ".benchmarks", ".hypothesis",
          ".mypy_cache", ".ruff_cache")


class JudgeRealPytestTest(unittest.TestCase):
    judge = "tests/judge/test_subject.py"

    def new_project(self):
        project = Project()
        self.addCleanup(project.close)
        self.root = project.root
        self.base = self.root.parent
        (self.root / ".gitignore").unlink()
        (self.root / "subject.py").write_text("value = 1\n")
        git(self.root, "add", "--all")
        git(self.root, "commit", "--quiet", "-m", "Use a plain Python project")
        git(self.root, "switch", "--quiet", "-c", "piece/1")

    def invoke(self, backend="claude", *, suppress_caches=True, writes=None, commit=()):
        fake = self.base / "fake-agent"
        fake.write_text(
            f"#!{sys.executable}\n"
            "import json, os, pathlib, subprocess, sys\n"
            "pathlib.Path(os.environ['ENV_RECORD']).write_text(json.dumps({\n"
            "    key: os.environ.get(key) for key in\n"
            "    ('PYTHONDONTWRITEBYTECODE', 'PYTEST_ADDOPTS')}))\n"
            "for name, text in json.loads(os.environ['WRITES']).items():\n"
            "    path = pathlib.Path(name)\n"
            "    path.parent.mkdir(parents=True, exist_ok=True)\n"
            "    path.write_text(text)\n"
            "env = dict(os.environ)\n"
            "if os.environ['SUPPRESS_CACHES'] == '0':\n"
            "    for key in ('PYTHONDONTWRITEBYTECODE', 'PYTEST_ADDOPTS'):\n"
            "        env.pop(key, None)\n"
            "subprocess.run([sys.executable, '-X', 'pycache_prefix=', '-m', 'pytest',\n"
            "    'tests/judge/test_subject.py', '-q'], env=env, check=True)\n"
            "commit = json.loads(os.environ['COMMIT'])\n"
            "if commit:\n"
            "    subprocess.run(['git', 'add', '-f', '--', *commit], check=True)\n"
            "    subprocess.run(['git', 'commit', '-m', 'Write session files'], check=True)\n"
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
        changed = {self.judge: "def test_D1_value():\n"
                               "    import subject\n    assert subject.value == 1\n"}
        changed.update(writes or {})
        env = {**os.environ, "LOOP_CLAUDE": str(fake), "LOOP_CODEX": str(fake),
               "WRITES": json.dumps(changed), "ENV_RECORD": str(self.base / "env.json"),
               "SUPPRESS_CACHES": "1" if suppress_caches else "0",
               "COMMIT": json.dumps(commit), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
               "ANSWER": "<verdict>" + json.dumps(verdict) + "</verdict>"}
        for key in ("PYTHONDONTWRITEBYTECODE", "PYTEST_ADDOPTS", "PYTHONPYCACHEPREFIX"):
            env.pop(key, None)
        result = subprocess.run(
            [sys.executable, "-B", str(KIT / "scripts/session.py"), "--role", "judge-writer",
             "--agent", backend, "--folder", str(self.root), "--input", str(source),
             "--output", str(output)], env=env, capture_output=True, text=True,
            timeout=30, check=False)
        return result, output

    def test_D1_D4_real_pytest_with_and_without_cache_suppression(self):
        for backend in ("claude", "codex"):
            for suppress_caches in (True, False):
                with self.subTest(backend=backend, suppress_caches=suppress_caches):
                    self.new_project()
                    result, output = self.invoke(backend, suppress_caches=suppress_caches)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertTrue(output.is_file())
                    self.assertFalse((self.root / ".gitignore").exists())
                    self.assertIn("1 passed", (self.base / "answer.log").read_text())
                    self.assertEqual(json.loads((self.base / "env.json").read_text()), {
                        "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_ADDOPTS": "-p no:cacheprovider"})
                    self.assertEqual((self.root / ".pytest_cache").exists(), not suppress_caches)
                    self.assertEqual(bool(list(self.root.rglob("*.pyc"))), not suppress_caches)
                    self.assertEqual(git(self.root, "diff", "--name-only", "main...HEAD"),
                                     self.judge)
                    self.assertEqual(git(self.root, "diff", "--cached", "--name-only"), "")

    def test_D1_D4_only_whole_cache_folders_are_accepted(self):
        self.new_project()
        writes = {prefix + cache + "/state": "tool cache"
                  for cache in CACHES for prefix in ("", "pkg/")}
        result, _ = self.invoke(writes=writes)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git(self.root, "diff", "--name-only", "main...HEAD"), self.judge)
        # Existing cache folders also leave the next session's baseline clean.
        result, _ = self.invoke(writes={name: "updated cache" for name in writes})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_D2_other_paths_are_refused_and_named(self):
        for name in ("notes.txt", "loose.pyc", "pkg/.pytest_cache_extra/state",
                     "pkg/prefix__pycache__/state", "pkg/.mypy_cache", ".ignored/state"):
            with self.subTest(name=name):
                self.new_project()
                # Use Git's local exclude so the project still has no .gitignore.
                exclude = self.root / ".git/info/exclude"
                exclude.write_text(exclude.read_text() + ".ignored/\n")
                before = git(self.root, "rev-parse", "HEAD")
                result, output = self.invoke(writes={name: "keep this work"})
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("outside the approved Exit Files: " + name, result.stderr)
                self.assertFalse(output.exists())
                self.assertEqual(git(self.root, "rev-parse", "HEAD"), before)
                self.assertEqual((self.root / name).read_text(), "keep this work")

    def test_D2_tracked_and_existing_ignored_changes_are_refused(self):
        for name in ("subject.py", ".ignored/state"):
            with self.subTest(name=name):
                self.new_project()
                if name.startswith(".ignored"):
                    exclude = self.root / ".git/info/exclude"
                    exclude.write_text(exclude.read_text() + ".ignored/\n")
                    path = self.root / name
                    path.parent.mkdir()
                    path.write_text("existing ignored work")
                result, _ = self.invoke(writes={name: "value = 1\n# changed\n"})
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("outside the approved Exit Files: " + name, result.stderr)

    def test_D3_committed_cache_folders_are_refused(self):
        for index, cache in enumerate(CACHES):
            with self.subTest(cache=cache):
                self.new_project()
                name = ("pkg/" if index % 2 else "") + cache + "/state"
                result, output = self.invoke(writes={name: "committed cache"},
                                             commit=[self.judge, name])
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("outside the approved Exit Files: " + name, result.stderr)
                self.assertFalse(output.exists())
                self.assertEqual(git(self.root, "show", "HEAD:" + name), "committed cache")

    def test_D4_writer_can_commit_approved_files(self):
        self.new_project()
        result, output = self.invoke("codex", suppress_caches=False, commit=[self.judge])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(output.is_file())
        self.assertEqual(git(self.root, "diff", "--name-only", "main...HEAD"), self.judge)


if __name__ == "__main__":
    unittest.main()
