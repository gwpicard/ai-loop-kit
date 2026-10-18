"""Judge writing follows the approved paths and leaves a committed bar."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import GOOD_CODE, KIT, Project, git

# isort: split
from loopkit import Refused, exit_ready, run_judge


class JudgeWriterContractTest(unittest.TestCase):
    def setUp(self):
        self.new_project()
        self.judge = "tests/judge/test_habits.py"
        self.data = {"Intent": "Add a habit", "Approach": "",
                     "Contract": "D1: adding a habit appends it.", "Files": self.judge}
        self.brief = (KIT / "briefs/judge-writer.md").read_text()

    def new_project(self):
        self.project = Project()
        self.addCleanup(self.project.close)
        self.root = self.project.root
        self.base = self.root.parent
        git(self.root, "switch", "--quiet", "-c", "piece/1")

    def invoke(self, backend, writes=None, files=None):
        fake = self.base / "fake-agent"
        fake.write_text(
            f"#!{sys.executable}\n"
            "import json, os, pathlib, sys\n"
            "pathlib.Path(os.environ['PROMPT']).write_text(' '.join(sys.argv[1:]))\n"
            "for name, text in json.loads(os.environ['WRITES']).items():\n"
            "    path = pathlib.Path(name)\n"
            "    path.parent.mkdir(parents=True, exist_ok=True)\n"
            "    path.write_text(text)\n"
            "text = os.environ['ANSWER']\n"
            "event = ({'type':'assistant','message':{'content':[{'type':'text','text':text}]}}\n"
            " if '-p' in sys.argv else {'type':'item.completed','item':\n"
            " {'type':'agent_message','text':text}})\n"
            "print(json.dumps(event))\n")
        fake.chmod(0o755)
        source = self.base / "input.json"
        source.write_text(json.dumps(self.data))
        output = self.base / "answer.txt"
        verdict = {"judge_files": files or [self.judge], "tests_per_id": True, "notes": "ok"}
        env = {**os.environ, "LOOP_CLAUDE": str(fake), "LOOP_CODEX": str(fake),
               "PROMPT": str(self.base / "prompt.txt"),
               "WRITES": json.dumps(writes if writes is not None else {self.judge: "# judge\n"}),
               "ANSWER": "<verdict>" + json.dumps(verdict) + "</verdict>"}
        result = subprocess.run(
            [sys.executable, str(KIT / "scripts/session.py"), "--role", "judge-writer",
             "--agent", backend, "--folder", str(self.root), "--input", str(source),
             "--output", str(output)], env=env, capture_output=True, text=True,
            timeout=10, check=False)
        return result, output

    def test_D1_exact_exit_paths_reach_both_backends(self):
        for backend in ("claude", "codex"):
            with self.subTest(backend=backend):
                result, _ = self.invoke(backend)
                self.assertEqual(result.returncode, 0, result.stderr)
                prompt = (self.base / "prompt.txt").read_text()
                self.assertIn(self.judge, prompt)
                self.assertIn("Write only to these exact paths", prompt)

    def test_D1_undeclared_writes_and_verdict_paths_are_refused(self):
        for backend in ("claude", "codex"):
            for reported in ([self.judge], ["wrong.py"]):
                with self.subTest(backend=backend, reported=reported):
                    result, output = self.invoke(backend, {"wrong.py": "# wrong\n"}, reported)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertFalse(output.exists())
                    self.assertEqual(git(self.root, "log", "--format=%s", "main..HEAD"), "")
                    (self.root / "wrong.py").unlink(missing_ok=True)

    def test_D1_D3_new_ignored_judges_and_helpers_are_refused(self):
        for backend in ("claude", "codex"):
            for unexpected in ("tests/judge/test_wrong.py", ".loop/helper.py"):
                with self.subTest(backend=backend, unexpected=unexpected):
                    self.new_project()
                    ignore = self.root / ".gitignore"
                    ignore.write_text(ignore.read_text() + "tests/judge/test_wrong.py\n")
                    git(self.root, "add", ".gitignore")
                    git(self.root, "commit", "--quiet", "-m", "Ignore a judge path")
                    before = git(self.root, "rev-parse", "HEAD")
                    writes = {self.judge: "# approved judge\n", unexpected: "# undeclared\n"}
                    result, output = self.invoke(backend, writes)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("outside the approved Exit Files", result.stderr)
                    self.assertFalse(output.exists())
                    self.assertEqual(git(self.root, "rev-parse", "HEAD"), before)
                    self.assertEqual((self.root / unexpected).read_text(), "# undeclared\n")
                    self.assertEqual((self.root / self.judge).read_text(), "# approved judge\n")

    def test_D1_paths_outside_the_project_are_refused_before_launch(self):
        outside = self.base / "outside.py"
        outside.write_text("Keep this file\n")
        (self.root / "linked.py").symlink_to(outside)
        git(self.root, "add", "linked.py")
        git(self.root, "commit", "--quiet", "-m", "Link an outside file")
        for path in ("../outside.py", str(outside), "linked.py"):
            with self.subTest(path=path):
                self.data["Files"] = path
                result, _ = self.invoke("codex")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse((self.base / "prompt.txt").exists())
                self.assertEqual(outside.read_text(), "Keep this file\n")

    def test_D2_missing_module_example_fails_on_assertion_and_gate_accepts(self):
        examples = re.findall(r"```python\n(.*?)```", self.brief, re.DOTALL)
        self.assertEqual(len(examples), 1, "the brief needs a runnable missing-module example")
        (self.root / "judge.py").write_text(examples[0])
        command = (f'{sys.executable} -c "import runpy, sys, unittest; '
                   "test = runpy.run_path('judge.py')['test_D1_add']; "
                   "result = unittest.TextTestRunner().run("
                   "unittest.TestSuite([unittest.FunctionTestCase(test)])); "
                   'sys.exit(not result.wasSuccessful())"')
        checks = ({"type": "tests", "command": command, "files": ["judge.py"]},)
        records, output = exit_ready(self.root, checks, {"D1": "add a habit"}, ())
        self.assertEqual(len(records), 1)
        self.assertIn("AssertionError", output)
        self.assertNotIn("ModuleNotFoundError:", output)
        (self.root / "habits.py").write_text(GOOD_CODE)
        code, output = run_judge(self.root, command)
        self.assertEqual(code, 0, output)
        with self.assertRaises(Refused):
            exit_ready(self.root, checks, {"D1": "add a habit"}, ())
        (self.root / "habits.py").write_text("import missing_habit_dependency\n")
        with self.assertRaisesRegex(Refused, "wrong reason"):
            exit_ready(self.root, checks, {"D1": "add a habit"}, ())

    def test_D3_success_commits_only_judges_and_leaves_shared_tree_clean(self):
        existing = self.root / ".loop" / "existing.py"
        existing.parent.mkdir()
        existing.write_text("# keep existing ignored files\n")
        for backend in ("claude", "codex"):
            with self.subTest(backend=backend):
                result, _ = self.invoke(backend, {self.judge: f"# {backend} judge\n"})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(git(self.root, "status", "--porcelain"), "")
                self.assertEqual(git(self.root, "diff", "--name-only", "main...HEAD"), self.judge)
                git(self.root, "switch", "--quiet", "main")
                self.assertEqual(git(self.root, "status", "--porcelain"), "")
                self.assertFalse((self.root / self.judge).exists())
                self.assertEqual(existing.read_text(), "# keep existing ignored files\n")
                git(self.root, "switch", "--quiet", "piece/1")
        self.assertEqual(git(self.root, "rev-list", "--count", "main..HEAD"), "2")

    def test_D3_main_and_existing_uncommitted_work_are_refused_before_launch(self):
        git(self.root, "switch", "--quiet", "main")
        result, _ = self.invoke("claude")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse((self.base / "prompt.txt").exists())
        git(self.root, "switch", "--quiet", "piece/1")
        (self.root / "notes.txt").write_text("Keep this work\n")
        result, _ = self.invoke("codex")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual((self.root / "notes.txt").read_text(), "Keep this work\n")
        self.assertFalse((self.base / "prompt.txt").exists())


if __name__ == "__main__":
    unittest.main()
