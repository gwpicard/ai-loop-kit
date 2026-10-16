"""Generated files cannot pass submit, even when a builder force-adds them."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import GOOD_CODE, Project, git

sys.path.insert(0, str(Path(__file__).resolve().parent / "field"))
import agents
import audit
import builder_prompt
import gate
import run
from loopkit import Refused, records


class GeneratedTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)

    def test_builder_or_runner_stages_source_without_runtime_files(self):
        for backend in ("claude", "codex"):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as temp:
                folder = Path(temp)
                git(folder, "init", "--quiet")
                fake = folder / "fake-agent"
                fake.write_text(
                    "#!/usr/bin/env python3\n"
                    "import os, pathlib, subprocess, sys\n"
                    "loop = pathlib.Path('.loop')\n"
                    "loop.mkdir(exist_ok=True)\n"
                    "for name in ('hypothesis', 'why.md', 'outcome'):\n"
                    " (loop / name).write_text('runtime output')\n"
                    "pathlib.Path('source.py').write_text('value = 1\\n')\n"
                    "prompt = (sys.argv[sys.argv.index('-p') + 1]\n"
                    "          if '-p' in sys.argv else sys.argv[-1])\n"
                    "if 'The run stages and commits' in prompt: sys.exit(0)\n"
                    "command = ([sys.executable, os.environ['AI_LOOP_KIT_ROOT'] +\n"
                    " '/scripts/builder_prompt.py', '--stage'] if 'builder_prompt.py\" --stage'\n"
                    " in prompt else ['git', 'add', '--force', '-A'])\n"
                    "subprocess.run(command, check=True)\n")
                fake.chmod(0o755)
                with patch.dict(os.environ, {"LOOP_CLAUDE": str(fake),
                                             "LOOP_CODEX": str(fake)}):
                    prompt = builder_prompt.brief(4, "spec", {"files": []}, "", folder=folder,
                                                  backend=backend)
                    proc = agents.start_session(backend, prompt, folder, role="builder")
                    output, _ = proc.communicate(timeout=10)
                self.assertEqual(proc.returncode, 0, output)
                if backend == "codex":
                    self.assertEqual(git(folder, "diff", "--cached", "--name-only"), "")
                    run.commit_leftovers(folder, 4, 1)
                    staged = git(folder, "show", "--pretty=", "--name-only", "HEAD").splitlines()
                else:
                    staged = git(folder, "diff", "--cached", "--name-only").splitlines()
                self.assertIn("source.py", staged)
                self.assertFalse(any(path.startswith(".loop/") for path in staged), staged)
                self.assertEqual((folder / ".loop/hypothesis").read_text(), "runtime output")

    def test_builder_brief_names_safe_staging_and_runtime_rule(self):
        text = builder_prompt.brief(4, "spec", {"files": []}, "")
        self.assertIn('python3 "$AI_LOOP_KIT_ROOT/scripts/builder_prompt.py" --stage', text)
        self.assertIn("Never stage or force-add `.loop/`", text)

    def stage_command(self, folder):
        return subprocess.run(
            [sys.executable, str(Path(builder_prompt.__file__)), "--stage"],
            cwd=folder, capture_output=True, text=True, check=False)

    def test_staging_from_subdirectory_keeps_deletions_and_ignored_files(self):
        folder = self.p.root
        (folder / "src").mkdir()
        (folder / ".gitignore").write_text("ignored.txt\n")
        git(folder, "add", ".gitignore")
        git(folder, "commit", "--quiet", "-m", "Ignore build output")
        (folder / "README.md").unlink()
        (folder / "src/new.py").write_text("value = 1\n")
        (folder / "ignored.txt").write_text("build output")
        (folder / ".loop").mkdir(exist_ok=True)
        (folder / ".loop/hypothesis").write_text("runtime output")
        result = self.stage_command(folder / "src")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git(folder, "diff", "--cached", "--name-status").splitlines(),
                         ["D\tREADME.md", "A\tsrc/new.py"])

    def test_staging_refuses_runtime_files_already_in_the_index(self):
        folder = self.p.root
        (folder / ".loop").mkdir(exist_ok=True)
        (folder / ".loop/why.md").write_text("runtime output")
        git(folder, "add", "--force", ".loop/why.md")
        before = git(folder, "diff", "--cached")
        (folder / "new.py").write_text("value = 1\n")
        result = self.stage_command(folder)
        self.assertEqual(result.returncode, 2)
        self.assertIn(".loop/ files are already staged", result.stderr)
        self.assertEqual(git(folder, "diff", "--cached"), before)

    def claimed(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        gate.move(self.p.gh, self.p.root, n, "building")
        folder = run.worktree(self.p.root, n)
        (folder / "habits.py").write_text(GOOD_CODE)
        git(folder, "add", "habits.py")
        git(folder, "commit", "--quiet", "-m", "Build")
        return n, folder

    def test_submit_refuses_force_added_runtime_and_generated_files(self):
        n, folder = self.claimed()
        paths = (".loop/why.md", ".loop/outcome", ".loop/hypothesis",
                 ".loop/hypotheses", ".loop/logs/attempt.log", "pkg/__pycache__/a.pyc",
                 "node_modules/pkg/index.js", ".coverage", "mutants/result.txt")
        for name in paths:
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("runtime output\n")
            git(folder, "add", "--force", name)
            git(folder, "commit", "--quiet", "-m", "Add runtime output")
            self.assertTrue(audit.generated(name))
            with self.assertRaises(Refused) as refused:
                gate.move(self.p.gh, self.p.root, n, "approval", folder=folder, pr="u")
            self.assertIn(name, refused.exception.reason)
            self.assertIn("state:building", self.p.gh.issue(n)["labels"])
            git(folder, "rm", "--", name)
            git(folder, "commit", "--quiet", "-m", "Remove runtime output")
        gate.move(self.p.gh, self.p.root, n, "approval", folder=folder, pr="u")
        self.assertIn("state:approval", self.p.gh.issue(n)["labels"])

    def test_gate_and_audit_share_generated_path_rules(self):
        paths = {
            ".loop/why.md": True, ".loop/outcome": True, ".loop/hypothesis": True,
            "a/__pycache__/b.pyc": True, "pkg.egg-info/PKG-INFO": True,
            ".DS_Store": True, "src/coverage.xml": True,
            "src/loop/a.py": False, "docs/node.md": False, "README.md": False,
            "nested/.loop/example.txt": False,
        }
        for path, expected in paths.items():
            with self.subTest(path=path):
                self.assertEqual(audit.generated(path), expected)
                self.assertEqual(gate.generated(path), expected)

    def test_submit_refuses_staged_generated_files(self):
        n, folder = self.claimed()
        (folder / ".loop").mkdir(exist_ok=True)
        (folder / ".loop/why.md").write_text("runtime output\n")
        git(folder, "add", "--force", ".loop/why.md")
        with self.assertRaises(Refused) as refused:
            gate.move(self.p.gh, self.p.root, n, "approval", folder=folder, pr="u")
        self.assertIn(".loop/why.md", refused.exception.reason)
        self.assertIn("state:building", self.p.gh.issue(n)["labels"])

    def assert_quoted_generated_files_refused(self, committed):
        paths = (".loop/café.md", ".loop/tab\tname.md", ".loop/line\nname.md",
                 '.loop/"quoted".md')
        for name in paths:
            with self.subTest(path=name):
                n, folder = self.claimed()
                (folder / ".loop").mkdir(exist_ok=True)
                (folder / name).write_text("runtime output\n")
                git(folder, "add", "--force", name)
                if committed:
                    git(folder, "commit", "--quiet", "-m", "Add runtime output")
                self.assertTrue(audit.generated(name))
                with self.assertRaises(Refused) as refused:
                    gate.move(self.p.gh, self.p.root, n, "approval", folder=folder, pr="u")
                self.assertIn(name, refused.exception.reason)
                self.assertIn("state:building", self.p.gh.issue(n)["labels"])

    def test_submit_refuses_committed_quoted_generated_files(self):
        self.assert_quoted_generated_files_refused(committed=True)

    def test_submit_refuses_staged_quoted_generated_files(self):
        self.assert_quoted_generated_files_refused(committed=False)

    def test_untracked_generated_files_do_not_block_submit(self):
        n, folder = self.claimed()
        (folder / ".loop").mkdir(exist_ok=True)
        (folder / ".loop/why.md").write_text("runtime output\n")
        gate.move(self.p.gh, self.p.root, n, "approval", folder=folder, pr="u")
        self.assertIn("state:approval", self.p.gh.issue(n)["labels"])

    def test_blocked_cleanup_returns_an_environment_failure(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        calls = []

        def build(folder, prompt, files, logfile, *args, **kwargs):
            calls.append(folder)
            (folder / ".loop").mkdir(exist_ok=True)
            if len(calls) == 1:
                (folder / "habits.py").write_text(GOOD_CODE)
                (folder / ".loop/why.md").write_text("runtime output\n")
                git(folder, "add", "--force", "habits.py", ".loop/why.md")
                git(folder, "commit", "--quiet", "-m", "Build with runtime output")
            else:
                (folder / ".loop/outcome").write_text(
                    "environment\nCleanup of .loop/why.md was blocked by permissions.\n")
                logfile.with_suffix(".jsonl").write_text(json.dumps({
                    "type": "item.completed", "item": {"type": "command_execution",
                    "exit_code": 1, "aggregated_output":
                    "Cleanup of .loop/why.md: Permission denied"}}) + "\n")
            return "done"

        with patch.object(run, "build_once", side_effect=build), patch.object(
                run, "review_piece", side_effect=AssertionError("unexpected review")):
            result = run.build_piece(self.p.gh, self.p.root, n, 3)
        seen = records(self.p.gh.comments(n))
        handback = [record for record in seen if record.get("move") == "give-back"][-1]
        self.assertEqual(handback["type"], "environment")
        self.assertEqual(handback["attempts"], 2)
        self.assertIn("Cleanup of .loop/why.md", handback["reason"])
        self.assertIn("back to shaping", result)
        self.assertEqual(len(calls), 2)
        self.assertFalse(any(record.get("move") == "submit" for record in seen))
        self.assertEqual(self.p.gh.prs, {})


if __name__ == "__main__":
    unittest.main()
