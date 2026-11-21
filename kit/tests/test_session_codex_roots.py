import json
import os
import sys
import unittest

from kit.tests.fake_codex import FakeCodexGh
from kit.tests.helpers import make_repo, write_exe, settings_json, write_settings
import session

AGENTS = "## Loop\nTest command: true\nLoop branch: loop/main\n"
PREFIX = "sandbox_workspace_write.writable_roots="


class CodexWritableRootsTest(FakeCodexGh):
    def setUp(self):
        super().setUp()
        session.SWEPT.clear()
        self.work, _ = make_repo(self.tmp, {"loop.json": settings_json(AGENTS)})
        self.temp = self.folder("tmpdir")
        os.environ["TMPDIR"] = self.temp
        self.addCleanup(self.restore_env, "TMPDIR", os.environ.get("TMPDIR"))
        self.addCleanup(self.restore_env, "PATH", os.environ.get("PATH"))

    @staticmethod
    def restore_env(name, value):
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def folder(self, name):
        path = os.path.join(self.tmp, name)
        os.makedirs(path, exist_ok=True)
        return path

    def settings(self, body):
        write_settings(os.path.join(self.work, "loop.json"), AGENTS + body)

    def fake_getconf(self, answers):
        """A `getconf` on PATH: prints the folder for a known name, fails otherwise."""
        write_exe(os.path.join(self.tmp, "bin", "getconf"),
                  "#!PYTHON\nimport sys\nanswers = %r\n"
                  "if len(sys.argv) > 1 and sys.argv[1] in answers:\n"
                  "    print(answers[sys.argv[1]] + '/')\nelse:\n    sys.exit(1)\n" % (answers,))

    def roots(self, call=0):
        argv = self.codex_calls()[call]["argv"]
        values = [argv[i + 1] for i, a in enumerate(argv[:-1])
                  if a == "-c" and argv[i + 1].startswith(PREFIX)]
        self.assertEqual(len(values), 1)
        return json.loads(values[0][len(PREFIX):])

    def real(self, paths):
        return sorted(os.path.realpath(p) for p in paths)

    def start(self, resume=None):
        return session.run("builder", "do it", self.work, "gpt-6", self.work, 7,
                           resume=resume, agent="codex")

    def common_dir(self):
        import subprocess
        return os.path.realpath(subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=self.work,
            capture_output=True, text=True).stdout.strip())

    def test_roots_hold_the_git_common_folder_and_the_real_tmpdir(self):
        link = os.path.join(self.tmp, "link")
        os.symlink(self.temp, link)
        os.environ["TMPDIR"] = link
        self.start()
        roots = self.roots()
        self.assertIn(self.common_dir(), [os.path.realpath(r) for r in roots])
        self.assertIn(os.path.realpath(self.temp), roots)
        self.assertNotIn(link, roots)

    def test_no_tmpdir_adds_no_temp_folder(self):
        del os.environ["TMPDIR"]
        self.start()
        self.assertNotIn(os.path.realpath(self.temp), self.roots())

    @unittest.skipUnless(sys.platform == "darwin", "the per-user folders are a macOS feature")
    def test_macos_adds_the_user_temp_and_cache_folders(self):
        user_temp, user_cache = self.folder("user-temp"), self.folder("user-cache")
        self.fake_getconf({"DARWIN_USER_TEMP_DIR": user_temp, "DARWIN_USER_CACHE_DIR": user_cache})
        os.environ["PATH"] = os.path.join(self.tmp, "bin") + os.pathsep + os.environ["PATH"]
        self.start()
        roots = self.roots()
        self.assertIn(os.path.realpath(user_temp), roots)
        self.assertIn(os.path.realpath(user_cache), roots)

    @unittest.skipUnless(sys.platform == "darwin", "the per-user folders are a macOS feature")
    def test_a_failing_getconf_leaves_them_out_and_the_session_starts(self):
        self.fake_getconf({})
        os.environ["PATH"] = os.path.join(self.tmp, "bin") + os.pathsep + os.environ["PATH"]
        text, _ = self.start()
        self.assertEqual(text, "ok")
        roots = self.roots()
        self.assertIn(os.path.realpath(self.temp), roots)
        self.assertEqual(len(roots), len(set(roots)))

    def test_the_setting_adds_folders_with_tilde_expanded(self):
        one, two = self.folder("one"), self.folder("home/cache")
        home = os.path.join(self.tmp, "home")
        os.environ["HOME"] = home
        self.addCleanup(self.restore_env, "HOME", os.environ.get("HOME"))
        self.settings("Codex writable roots: %s, ~/cache\n" % one)
        self.start()
        roots = self.roots()
        self.assertIn(os.path.realpath(one), roots)
        self.assertIn(os.path.realpath(two), roots)

    def test_a_missing_folder_is_left_out_and_duplicates_are_removed(self):
        one = self.folder("one")
        missing = os.path.join(self.tmp, "missing")
        self.settings("Codex writable roots: %s, %s, %s, %s\n" % (one, missing, one, self.temp))
        self.start()
        roots = self.roots()
        self.assertNotIn(missing, roots)
        self.assertNotIn(os.path.realpath(missing), roots)
        self.assertEqual(len(roots), len(set(roots)))
        self.assertEqual(roots.count(os.path.realpath(one)), 1)
        self.assertEqual(roots.count(os.path.realpath(self.temp)), 1)

    def test_the_setting_defaults_to_nothing_extra(self):
        self.start()
        self.assertEqual(self.real(self.roots()), self.real(set(self.roots())))
        self.assertLessEqual(len(self.roots()), 4)

    def test_a_resume_gets_the_same_list(self):
        one = self.folder("one")
        self.settings("Codex writable roots: %s\n" % one)
        self.codex([{"reply": "first", "thread": "t-1"}, {"reply": "again"}])
        _, sid = self.start()
        self.start(resume=sid)
        self.assertIn("resume", self.codex_calls()[1]["argv"])
        self.assertEqual(self.roots(1), self.roots(0))
        self.assertIn(os.path.realpath(one), self.roots(1))


class ReadmeTest(unittest.TestCase):
    def test_readme_describes_the_setting_with_the_marcdown_example(self):
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "..", "README.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("Codex writable roots", text)
        self.assertIn("~/Library/Caches/org.swift.swiftpm", text)


if __name__ == "__main__":
    unittest.main()
