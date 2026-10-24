"""Judge writing accepts real Vitest caches in ignored node_modules and refuses the rest."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import KIT, Project, git

VITEST = "5.0.5"


class JudgeRealVitestTest(unittest.TestCase):
    judge = "tests/judge/subject.test.js"

    @classmethod
    def setUpClass(cls):
        if not shutil.which("npm"):
            raise unittest.SkipTest("npm is not installed")
        cls.packages = tempfile.TemporaryDirectory(prefix="loop-vitest-")
        cls.template = Path(cls.packages.name)
        (cls.template / "package.json").write_text(json.dumps({
            "name": "subject", "private": True, "type": "module",
            "scripts": {"test": "vitest run"}, "devDependencies": {"vitest": VITEST}}))
        install = subprocess.run(["npm", "install", "--no-audit", "--no-fund"],
                                 cwd=cls.template, capture_output=True, text=True,
                                 timeout=300, check=False)
        if install.returncode:
            cls.packages.cleanup()
            raise unittest.SkipTest("npm cannot install vitest: " + install.stderr[-300:])

    @classmethod
    def tearDownClass(cls):
        cls.packages.cleanup()

    def new_project(self, ignore="node_modules/\n"):
        project = Project()
        self.addCleanup(project.close)
        self.root = project.root
        self.base = self.root.parent
        for name in ("package.json", "package-lock.json"):
            shutil.copy(self.template / name, self.root / name)
        (self.root / "subject.js").write_text("export const value = 1;\n")
        (self.root / ".gitignore").write_text(".loop/\n" + ignore)
        git(self.root, "add", "--all")
        git(self.root, "commit", "--quiet", "-m", "Use a plain Vitest project")
        git(self.root, "switch", "--quiet", "-c", "piece/1")
        # Prepare has already installed the packages, as `npm ci` would.
        shutil.copytree(self.template / "node_modules", self.root / "node_modules",
                        symlinks=True)

    def invoke(self, backend="claude", writes=None, commit=()):
        fake = self.base / "fake-agent"
        fake.write_text(
            f"#!{sys.executable}\n"
            "import json, os, pathlib, subprocess, sys\n"
            "for name, text in json.loads(os.environ['WRITES']).items():\n"
            "    path = pathlib.Path(name)\n"
            "    path.parent.mkdir(parents=True, exist_ok=True)\n"
            "    path.write_text(text)\n"
            "subprocess.run(['npx', 'vitest', 'run', 'tests/judge/subject.test.js'],\n"
            "    check=True)\n"
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
        changed = {self.judge: "// Intent: check the subject.\n"
                               "import { expect, test } from 'vitest';\n"
                               "import { value } from '../../subject.js';\n"
                               "test('D1 value is one', () => { expect(value).toBe(1); });\n"}
        changed.update(writes or {})
        env = {**os.environ, "LOOP_CLAUDE": str(fake), "LOOP_CODEX": str(fake),
               "WRITES": json.dumps(changed), "COMMIT": json.dumps(commit),
               "ANSWER": "<verdict>" + json.dumps(verdict) + "</verdict>"}
        env.pop("CI", None)
        result = subprocess.run(
            [sys.executable, "-B", str(KIT / "scripts/session.py"), "--role", "judge-writer",
             "--agent", backend, "--folder", str(self.root), "--input", str(source),
             "--output", str(output)], env=env, capture_output=True, text=True,
            timeout=120, check=False)
        return result, output

    def package_files(self):
        return {str(path.relative_to(self.root)) for path in
                (self.root / "node_modules").rglob("*") if path.is_file()}

    def test_D1_real_vitest_with_default_config_is_accepted(self):
        for backend in ("claude", "codex"):
            with self.subTest(backend=backend):
                self.new_project()
                before = self.package_files()
                result, output = self.invoke(backend)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(output.is_file())
                self.assertIn("1 passed", (self.base / "answer.log").read_text())
                # Vitest really wrote its caches inside node_modules.
                self.assertTrue(self.package_files() - before)
                self.assertEqual(git(self.root, "diff", "--name-only", "main...HEAD"),
                                 self.judge)
                self.assertEqual(git(self.root, "status", "--porcelain"), "")

    def test_D2_other_paths_are_still_refused_and_named(self):
        for name in ("notes.txt", "vitest.config.js", "node_modules_extra/state"):
            with self.subTest(name=name):
                self.new_project()
                before = git(self.root, "rev-parse", "HEAD")
                result, output = self.invoke(writes={name: "export default {};\n"})
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("outside the approved Exit Files: " + name, result.stderr)
                self.assertFalse(output.exists())
                self.assertEqual(git(self.root, "rev-parse", "HEAD"), before)

    def test_D2_unignored_or_committed_node_modules_are_refused(self):
        name = "node_modules/.vite/forced"
        self.new_project()
        result, _ = self.invoke(writes={name: "committed cache"}, commit=[self.judge, name])
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("outside the approved Exit Files: " + name, result.stderr)
        # Without the ignore rule, installed packages are not the kit's to accept.
        self.new_project(ignore="")
        result, _ = self.invoke()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("clean working tree", result.stderr)


if __name__ == "__main__":
    unittest.main()
