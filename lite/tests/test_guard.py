import json
import os
import subprocess
import sys
import tempfile
import unittest

from lite.tests.helpers import make_repo, run_git

GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                     "hooks", "guard.py")
# Built from pieces so this file holds no secret shape itself.
PRIVATE_KEY = "-----BEGIN " + "RSA PRIVATE KEY-----"
GH_TOKEN = "gh" + "p_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
AWS_KEY = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
ANT_KEY = "sk-" + "ant-" + "api03-abcdefghijklmnop"
SLACK = "xo" + "xb-" + "1234567890-abcdefghij"
PAT = "github_" + "pat_" + "11ABCDEFG0123456789abcd"


class GuardCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.work, _ = make_repo(cls._tmp.name, {
            "README.md": "hi\n", "src/app.py": "x = 1\n",
            "tests/test_app.py": "pass\n", "tests/__pycache__/x.pyc": "1\n", "web/a.spec.js": "1\n",
            "lib/util_test.go": "1\n", "docs/notes.md": "n\n"})
        run_git(["symbolic-ref", "refs/remotes/origin/HEAD",
                 "refs/remotes/origin/main"], cls.work)
        run_git(["checkout", "-b", "feature"], cls.work)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def call(self, tool, inp, role=None, locked=None, cwd=None, default=None):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("LITE_")}
        if role:
            env["LITE_ROLE"] = role
        if default:
            env["LITE_DEFAULT_BRANCH"] = default
        if locked:
            env["LITE_LOCKED"] = "\n".join(locked)
        data = {"tool_name": tool, "tool_input": inp, "cwd": cwd or self.work}
        return subprocess.run([sys.executable, GUARD], input=json.dumps(data),
                              capture_output=True, text=True, env=env)

    def bash(self, command, **kw):
        return self.call("Bash", {"command": command}, **kw)

    def refused(self, r, text=""):
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("refused: ", r.stderr)
        self.assertIn("next: ", r.stderr)
        self.assertIn(text, r.stderr)

    def allowed(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)


class TestEveryone(GuardCase):
    def test_push_to_main_refused(self):
        for cmd in ["git push origin main", "git push origin master",
                    "git push origin HEAD:main", "git push origin feature:refs/heads/main",
                    "git -C . push origin main", "git push --delete origin main",
                    "git push origin :main", "git add . && git push origin main",
                    "echo hi; git push origin main", "bash -c 'git push origin main'",
                    "git push origin :main",
                    "FOO=1 git push origin main", "git push --all origin"]:
            with self.subTest(cmd=cmd):
                self.refused(self.bash(cmd))

    def test_default_branch_from_environment(self):
        self.refused(self.bash("git push origin trunk", default="trunk"),
                     "default branch")
        self.allowed(self.bash("git push origin trunk"))

    def test_push_bypass_spellings_refused(self):
        for cmd in ["{ git push origin main; }", "if true; then git push origin main; fi",
                    "git push --repo=x main", "git push origin 'HEAD:main'",
                    "git push origin refs/heads/main", "eval git push origin main",
                    "xargs git push origin main"]:
            with self.subTest(cmd=cmd):
                self.refused(self.bash(cmd))

    def test_force_push_refused(self):
        for cmd in ["git push -f origin feature", "git push --force origin feature",
                    "git push --force-with-lease origin feature",
                    "git push --force-with-lease=feature origin feature",
                    "git push origin +feature", "git push -uf origin feature",
                    "git push --mirror"]:
            with self.subTest(cmd=cmd):
                self.refused(self.bash(cmd), "force")

    def test_normal_push_allowed(self):
        self.allowed(self.bash("git push origin feature"))
        self.allowed(self.bash("git push -u origin feature"))

    def test_recursive_delete_refused(self):
        for cmd in ["rm -rf build", "rm -fr build", "rm -r build", "rm -R build",
                    "rm --recursive build", "ls && rm -rf /tmp/x",
                    "sudo rm -rf x", "find . -delete",
                    "find . -name '*.pyc' -exec rm -rf {} +", "rm -f -r x",
                    "{ rm -rf x; }", "if true; then rm -rf x; fi", "! rm -rf x",
                    "xargs rm -rf", "busybox rm -rf x", "eval 'rm -rf x'",
                    "python3 -c 'import shutil; shutil.rmtree(\"x\")'",
                    "sh -c 'rm -rf x'"]:
            with self.subTest(cmd=cmd):
                self.refused(self.bash(cmd), "")

    def test_plain_delete_allowed(self):
        self.allowed(self.bash("rm file.txt"))
        self.allowed(self.bash("find . -name '*.py'"))

    def test_secret_in_write_content_refused(self):
        for secret in [PRIVATE_KEY, GH_TOKEN, AWS_KEY, ANT_KEY, SLACK, PAT]:
            with self.subTest(secret=secret[:8]):
                self.refused(self.call("Write", {
                    "file_path": "/tmp/x.txt", "content": "key = " + secret}),
                    "secret")

    def test_secret_in_edit_refused(self):
        self.refused(self.call("Edit", {
            "file_path": "/tmp/x.txt", "old_string": "a",
            "new_string": "token " + GH_TOKEN}), "secret")
        self.refused(self.call("MultiEdit", {
            "file_path": "/tmp/x.txt",
            "edits": [{"old_string": "a", "new_string": "b"},
                      {"old_string": "c", "new_string": AWS_KEY}]}), "secret")

    def test_plain_write_allowed(self):
        self.allowed(self.call("Write", {
            "file_path": "/tmp/x.txt", "content": "hello, AKIA is a word"}))

    def test_unknown_input_exits_zero(self):
        for raw in ["", "not json", "[1, 2]", '{"tool_name": "Bash"}',
                    '{"tool_name": "Bash", "tool_input": {"command": 5}}']:
            with self.subTest(raw=raw):
                r = subprocess.run([sys.executable, GUARD], input=raw,
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0)
        self.allowed(self.call("Read", {"file_path": "x"}))

    def test_without_role_tests_and_gh_allowed(self):
        self.allowed(self.bash("gh pr list"))
        self.allowed(self.bash("git merge feature"))
        self.allowed(self.call("Write", {
            "file_path": os.path.join(self.work, "tests/test_app.py"),
            "content": "pass\n"}))


class TestRole(GuardCase):
    def test_push_merge_gh_refused(self):
        for role in ["builder", "test-writer", "reviewer"]:
            for cmd in ["git push origin feature", "git merge main", "gh pr list",
                        "echo a && gh issue view 1", "git -C . merge x",
                        "/opt/homebrew/bin/gh pr list", "./gh pr list", "git restore src/app.py", "git apply p.diff",
                        "git branch -f main x", "{ git push; }"]:
                with self.subTest(role=role, cmd=cmd):
                    self.refused(self.bash(cmd, role=role))

    def test_branch_switch_refused(self):
        for cmd in ["git checkout main", "git checkout -b other", "git switch main",
                    "git switch -c other", "git checkout -- src/app.py"]:
            with self.subTest(cmd=cmd):
                self.refused(self.bash(cmd, role="builder"))

    def test_other_git_allowed(self):
        for cmd in ["git status", "git add -A && git commit -m x",
                    "git diff", "git log"]:
            with self.subTest(cmd=cmd):
                self.allowed(self.bash(cmd, role="builder"))

    def test_locked_path_refused_for_edit(self):
        locked = ["new/test_x.py"]
        for tool, inp in [("Write", {"file_path": "new/test_x.py", "content": "a"}),
                          ("Edit", {"file_path": os.path.join(self.work, "new/test_x.py"),
                                    "old_string": "a", "new_string": "b"})]:
            for role in ["builder", "test-writer"]:
                with self.subTest(tool=tool, role=role):
                    self.refused(self.call(tool, inp, role=role, locked=locked),
                                 "locked")

    def test_locked_folder_refused(self):
        self.refused(self.call("Write", {"file_path": "spec/a.py", "content": "a"},
                               role="builder", locked=["spec"]), "locked")

    def test_existing_test_refused_for_builder_and_writer(self):
        for path in ["tests/test_app.py", "web/a.spec.js", "lib/util_test.go"]:
            for role in ["builder", "test-writer"]:
                with self.subTest(path=path, role=role):
                    self.refused(self.call("Edit", {
                        "file_path": path, "old_string": "1",
                        "new_string": "2"}, role=role), "existing test")

    def test_build_artefacts_under_tests_are_not_locked(self):
        for role in ["builder", "test-writer"]:
            self.allowed(self.call("Write", {"file_path": "tests/__pycache__/x.pyc", "content": "2\n"}, role=role))

    def test_new_test_file_allowed_for_writer_and_builder(self):
        for role in ["builder", "test-writer"]:
            with self.subTest(role=role):
                self.allowed(self.call("Write", {
                    "file_path": "tests/test_new.py", "content": "pass\n"},
                    role=role))
                self.allowed(self.call("Write", {
                    "file_path": "src/new.test.js", "content": "1\n"},
                    role=role))

    def test_non_test_edit_allowed(self):
        for path in ["src/app.py", "docs/notes.md"]:
            self.allowed(self.call("Edit", {
                "file_path": path, "old_string": "x", "new_string": "y"},
                role="builder", locked=["tests/test_new.py"]))

    def test_notebook_and_multiedit_paths(self):
        self.refused(self.call("NotebookEdit", {
            "notebook_path": "tests/test_app.py", "new_source": "1"},
            role="builder"), "existing test")
        self.refused(self.call("MultiEdit", {
            "file_path": "tests/test_app.py",
            "edits": [{"old_string": "a", "new_string": "b"}]},
            role="builder"), "existing test")

    def test_redirection_onto_locked_or_existing_test_refused(self):
        for cmd in ["echo x > tests/test_app.py", "echo x >> tests/test_app.py",
                    "echo x >tests/test_app.py", "echo x | tee tests/test_app.py",
                    "echo x | tee -a tests/test_app.py", "echo x > new/test_x.py",
                    "echo x>tests/test_app.py", "echo x>>tests/test_app.py",
                    "echo x >|tests/test_app.py", "echo x 2>tests/test_app.py"]:
            with self.subTest(cmd=cmd):
                self.refused(self.bash(cmd, role="builder",
                                       locked=["new/test_x.py"]))

    def test_redirection_elsewhere_allowed(self):
        for cmd in ["echo x > src/new.py", "python3 -m unittest 2>&1 | tail -5",
                    "ls > /dev/null", "cat tests/test_app.py"]:
            with self.subTest(cmd=cmd):
                self.allowed(self.bash(cmd, role="builder"))

    def test_reviewer_edits_nothing(self):
        for tool, inp in [("Write", {"file_path": "src/new.py", "content": "a"}),
                          ("Edit", {"file_path": "docs/notes.md",
                                    "old_string": "n", "new_string": "m"}),
                          ("NotebookEdit", {"notebook_path": "a.ipynb"})]:
            with self.subTest(tool=tool):
                self.refused(self.call(tool, inp, role="reviewer"),
                             "reviewer")
        self.refused(self.bash("echo x > docs/notes.md", role="reviewer"),
                     "reviewer")
        self.allowed(self.bash("python3 -m unittest 2>&1 | tail -3",
                               role="reviewer"))

    def test_pass_writes_only_under_lite_pass(self):
        self.refused(self.call("Write", {"file_path": "src/new.py", "content": "a"}, role="pass"), "pass")
        self.refused(self.bash("echo x > docs/notes.md", role="pass"), "pass")
        self.allowed(self.call("Write", {"file_path": ".lite/pass/test_x.py", "content": "a"}, role="pass"))
        self.allowed(self.bash("echo x > .lite/pass/test_x.py", role="pass"))
        self.refused(self.bash("gh issue list", role="pass"))

    def test_everyone_rules_still_apply_with_role(self):
        self.refused(self.bash("rm -rf x", role="builder"))
        self.refused(self.call("Write", {
            "file_path": "src/k.py", "content": GH_TOKEN}, role="builder"),
            "secret")


if __name__ == "__main__":
    unittest.main()
