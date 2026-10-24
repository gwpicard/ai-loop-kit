"""Command and file guards for builder sessions."""
from __future__ import annotations

from helpers import KIT

# isort: split

import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch


def guard(command=None, tool="Bash", builder=False, path=None, protected=""):
    data = {"command": command} if command is not None else {"file_path": path}
    env = {**os.environ, "LOOP_BUILDER": "1" if builder else "0",
           "LOOP_PROTECTED_PATHS": protected}
    res = subprocess.run([sys.executable, str(KIT / "hooks" / "guard.py")],
                         input=json.dumps({"tool_name": tool, "tool_input": data}),
                         capture_output=True, text=True, env=env)
    return res.returncode


class GuardTest(unittest.TestCase):
    REFUSED = [
        "git push origin main", "git push origin HEAD:main", "git push --force origin piece/1",
        "git push -f", "rm -rf build", "rm -r src", "rm -fR x", "sudo rm --recursive x",
        'eval "git push --force origin piece/1"', "printf x | xargs rm -r file",
        "find . -name '*.pyc' -delete", "git clean -fdx", "git rm -r src",
        "gh pr merge 3 --squash", "gh issue edit 3 --add-label state:ready",
        "gh pr merge https://github.com/o/r/pull/3 --merge --match-head-commit abc123",
        "gh api repos/o/r/issues/3/labels -f labels[]=state:done",
        "echo hi && git push origin main", "FOO=1 git push origin main",
        "git -C . push origin main", 'bash -c "git push --force origin x"',
        "gh -R a/b pr merge 3", "python3 -c \"import shutil; shutil.rmtree('x')\"",
        "node -e \"rm -rf x\"", "GIT_CONFIG_COUNT=1 git push origin main",
    ]
    ALLOWED = [
        "git push -u origin piece/4", "rm build/out.txt", "git status", "gh issue list",
        "gh issue edit 3 --add-label bug", "python3 gate.py move 3 ready", "ls -la",
    ]

    def test_refuses_the_hard_rules(self):
        for cmd in self.REFUSED:
            self.assertEqual(guard(cmd), 2, cmd)

    def test_allows_ordinary_work(self):
        for cmd in self.ALLOWED:
            self.assertEqual(guard(cmd), 0, cmd)

    def test_builders_never_push_or_use_gh_or_touch_settings(self):
        self.assertEqual(guard("git push -u origin piece/4", builder=True), 2)
        self.assertEqual(guard("gh issue list", builder=True), 2)
        self.assertEqual(guard(tool="Write", path="/p/.claude/settings.json", builder=True), 2)
        self.assertEqual(guard(tool="Write", path="/p/src/app.py", builder=True), 0)

    def test_builder_refuses_protected_paths_and_unreadable_commands(self):
        self.assertEqual(guard(tool="Edit", path="/p/secrets/key.py", builder=True,
                               protected="secrets"), 2)
        self.assertEqual(guard("echo 'unfinished", builder=True), 2)

    def test_builder_refuses_unhandled_execution_and_redirect_forms(self):
        for command in ("bash -lc 'echo hi'", "sh -ec 'echo hi'", "eval 'git status'",
                        "printf x | xargs rm -r file", "perl -e 'print 1'", "ruby -e 'puts 1'",
                        "echo x > .claude/settings.json", "echo x >> .githooks/commit-msg",
                        "echo x > secrets/key.txt"):
            with self.subTest(command=command):
                self.assertEqual(guard(command, builder=True, protected="secrets"), 2)

    def test_plain_git_push_is_refused_on_main(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("loop_guard", KIT / "hooks" / "guard.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module, "current_branch", return_value="main"):
            self.assertIsNotNone(module.check_command("git push", builder=False))


if __name__ == "__main__":
    unittest.main()
