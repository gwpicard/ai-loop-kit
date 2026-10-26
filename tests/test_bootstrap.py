"""Setup starts a project from any folder, with a fake gh and a local bare remote."""
from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from helpers import KIT, git

# isort: split
import gate

# A fake gh: repo create adds the bare remote as origin, api answers from FAKE_GH_PROTECT.
FAKE_GH = """#!/bin/sh
echo "$*" >> "$FAKE_GH_LOG"
case "$1 $2" in
  "auth status") [ -n "$FAKE_GH_SIGNED_OUT" ] && { echo "not logged in" >&2; exit 1; }; exit 0 ;;
  "repo create") [ -n "$FAKE_GH_CREATE_FAIL" ] && { echo "name already exists" >&2; exit 1; }
    git remote add origin "$FAKE_GH_REMOTE"; echo "https://github.com/me/$3"; exit 0 ;;
  "repo view") echo "me/project"; exit 0 ;;
  "label create") exit 0 ;;
  "label list") echo "[]"; exit 0 ;;
esac
if [ "$1" = "api" ]; then
  case "$FAKE_GH_PROTECT" in
    plan) echo 'gh: Upgrade to GitHub Pro or make this repository public' \
      'to enable this feature. (HTTP 403)' >&2; exit 1 ;;
    *) echo '{}'; exit 0 ;;
  esac
fi
echo "unexpected gh call: $*" >&2
exit 1
"""


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="loop-bootstrap-")
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root = base / "project"
        self.root.mkdir()
        self.remote = base / "remote.git"
        git(base, "init", "--quiet", "--bare", "-b", "main", str(self.remote))
        bin_dir = base / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text(FAKE_GH)
        (bin_dir / "gh").chmod(0o755)
        self.log = base / "gh.log"
        home = base / "home"
        home.mkdir()
        (home / ".gitconfig").write_text(
            "[user]\n\temail = test@example.invalid\n\tname = Test\n"
            "[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = master\n")
        env = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "HOME": str(home),
               "GIT_CONFIG_NOSYSTEM": "1", "FAKE_GH_LOG": str(self.log),
               "FAKE_GH_REMOTE": str(self.remote), "FAKE_GH_SIGNED_OUT": "",
               "FAKE_GH_PROTECT": "ok", "FAKE_GH_CREATE_FAIL": ""}
        self.saved = {key: os.environ.get(key) for key in env}
        os.environ.update(env)
        self.addCleanup(self.restore_env)
        self.cwd = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, self.cwd)

    def restore_env(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def bootstrap(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = gate.main(["bootstrap", *args])
        return code, out.getvalue() + err.getvalue()

    def gh_calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def remote_main(self):
        return git(self.root, "ls-remote", "--heads", "origin", "main")

    def test_empty_folder_reaches_a_pushed_protected_main(self):
        code, output = self.bootstrap("--name", "project", "--protect")
        self.assertEqual(code, 0, output)
        self.assertEqual(git(self.root, "branch", "--show-current"), "main")
        self.assertTrue(self.remote_main(), output)
        self.assertIn("repo create project --private --source . --remote origin",
                      "\n".join(self.gh_calls()))
        self.assertTrue(any(call.startswith("api") and "protection" in call
                            for call in self.gh_calls()), self.gh_calls())
        self.assertIn("/.loop/", (self.root / ".gitignore").read_text())
        self.assertTrue((self.root / "README.md").exists())
        self.assertFalse(git(self.root, "status", "--porcelain"))
        import doctor
        from loopkit import GitHub
        checks = doctor.doctor(GitHub(self.root), self.root)
        ground = [c for c in checks if c[1] in (
            "the project has an origin", "gh is signed in", "main has a commit on origin")]
        self.assertEqual(len(ground), 3, checks)
        self.assertTrue(all(ok for ok, _, _ in ground), checks)

    def test_signed_out_gh_stops_before_any_change(self):
        os.environ["FAKE_GH_SIGNED_OUT"] = "1"
        code, output = self.bootstrap("--name", "project")
        self.assertEqual(code, 2)
        self.assertIn("gh auth login", output)
        self.assertFalse((self.root / ".git").exists())
        self.assertEqual(self.gh_calls(), ["auth status --active"])

    def test_missing_name_asks_before_any_online_change(self):
        code, output = self.bootstrap()
        self.assertEqual(code, 2)
        self.assertIn("--name", output)
        # The refusal comes after bootstrap made .git, so it says so.
        self.assertIn("made a git repository", output)
        self.assertLess(output.index("made a git repository"), output.index("refused:"))
        self.assertFalse(any(call.startswith("repo create") for call in self.gh_calls()))

    def test_second_run_changes_nothing(self):
        self.assertEqual(self.bootstrap("--name", "project", "--protect")[0], 0)
        head = git(self.root, "rev-parse", "HEAD")
        calls = len(self.gh_calls())
        code, output = self.bootstrap("--name", "project")
        self.assertEqual(code, 0, output)
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), head)
        later = self.gh_calls()[calls:]
        self.assertFalse(any(c.startswith(("repo create", "api")) for c in later), later)
        self.assertIn("already", output)

    def test_existing_main_on_origin_is_never_pushed(self):
        other = Path(self.tmp.name) / "other"
        git(Path(self.tmp.name), "clone", "--quiet", str(self.remote), str(other))
        (other / "README.md").write_text("theirs\n")
        git(other, "add", "README.md")
        git(other, "commit", "--quiet", "-m", "Theirs")
        git(other, "push", "--quiet", "origin", "HEAD:main")
        theirs = git(other, "rev-parse", "HEAD")
        git(self.root, "init", "--quiet", "-b", "main")
        (self.root / "app.py").write_text("print('mine')\n")
        git(self.root, "remote", "add", "origin", str(self.remote))
        code, output = self.bootstrap()
        self.assertEqual(code, 2)
        self.assertIn("ask the person", output)
        self.assertEqual(self.remote_main().split()[0], theirs)
        self.assertEqual((self.root / "app.py").read_text(), "print('mine')\n")
        made = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "main"],
                              cwd=self.root, capture_output=True, check=False)
        self.assertNotEqual(made.returncode, 0, "no local commit may be made")
        # A local main that is behind origin is never pushed either.
        git(self.root, "fetch", "--quiet", "origin", "main")
        git(self.root, "switch", "--quiet", "-c", "main", "FETCH_HEAD")
        code, output = self.bootstrap()
        self.assertEqual(code, 0, output)
        self.assertEqual(self.remote_main().split()[0], theirs)
        self.assertNotIn("pushed", output)

    def test_plan_without_protection_warns_and_passes(self):
        os.environ["FAKE_GH_PROTECT"] = "plan"
        code, output = self.bootstrap("--name", "project", "--protect")
        self.assertEqual(code, 0, output)
        self.assertIn("warn", output)
        self.assertIn("plan", output)
        self.assertTrue(self.remote_main())

    def test_code_without_git_goes_into_the_first_commit(self):
        (self.root / "app.py").write_text("print('hi')\n")
        (self.root / "src").mkdir()
        (self.root / "src" / "lib.py").write_text("X = 1\n")
        (self.root / ".env").write_text("TOKEN=not-for-git\n")
        (self.root / "README.md").write_text("mine\n")
        code, output = self.bootstrap("--name", "project")
        self.assertEqual(code, 0, output)
        tracked = git(self.root, "ls-files").splitlines()
        self.assertIn("app.py", tracked)
        self.assertIn("src/lib.py", tracked)
        self.assertNotIn(".env", tracked)
        self.assertEqual((self.root / "README.md").read_text(), "mine\n")
        self.assertEqual((self.root / ".env").read_text(), "TOKEN=not-for-git\n")

    def test_loop_section_goes_into_the_first_commit_without_a_pull_request(self):
        section = Path(self.tmp.name) / "loop.md"
        section.write_text("## The loop\nTest command: `true`\n")
        code, output = self.bootstrap("--name", "project", "--loop-section", str(section))
        self.assertEqual(code, 0, output)
        self.assertIn("Test command: `true`",
                      git(self.root, "show", "origin/main:AGENTS.md"))
        self.assertEqual(git(self.root, "branch", "--format=%(refname:short)"), "main")
        self.assertFalse(any(c.startswith("pr ") for c in self.gh_calls()))

    def test_loop_section_is_refused_when_main_already_has_a_commit(self):
        git(self.root, "init", "--quiet", "-b", "main")
        (self.root / "README.md").write_text("x\n")
        git(self.root, "add", "README.md")
        git(self.root, "commit", "--quiet", "-m", "Start")
        section = Path(self.tmp.name) / "loop.md"
        section.write_text("## The loop\nTest command: `true`\n")
        code, output = self.bootstrap("--name", "project", "--loop-section", str(section))
        self.assertEqual(code, 2)
        self.assertIn("pull request", output)
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_folder_inside_another_repository_is_refused(self):
        git(self.root, "init", "--quiet", "-b", "main")
        inner = self.root / "newapp"
        inner.mkdir()
        os.chdir(inner)
        code, output = self.bootstrap("--name", "newapp")
        self.assertEqual(code, 2)
        self.assertIn("inside another git repository", output)
        self.assertFalse(any(c.startswith("repo create") for c in self.gh_calls()))

    def test_secret_files_stop_the_first_commit(self):
        for name, text in (("id_rsa", "key\n"), ("deploy.pem", "x\n"),
                           ("config.py", "TOKEN = 'ghp_" + "a" * 30 + "'\n")):
            with self.subTest(name=name):
                (self.root / name).write_text(text)
                code, output = self.bootstrap("--name", "project")
                self.assertEqual(code, 2, output)
                self.assertIn("secret", output)
                self.assertEqual((self.root / name).read_text(), text)
                self.assertFalse(git(self.remote, "for-each-ref"))
                self.assertFalse(any(c.startswith("repo create") for c in self.gh_calls()))
                (self.root / name).unlink()

    def test_unborn_master_becomes_main(self):
        git(self.root, "init", "--quiet")
        (self.root / "app.py").write_text("x = 1\n")
        code, output = self.bootstrap("--name", "project")
        self.assertEqual(code, 0, output)
        self.assertEqual(git(self.root, "branch", "--show-current"), "main")
        self.assertTrue(self.remote_main())

    def test_retry_after_a_failed_repo_create_keeps_the_loop_section(self):
        section = Path(self.tmp.name) / "loop.md"
        section.write_text("## The loop\nTest command: `true`\n")
        os.environ["FAKE_GH_CREATE_FAIL"] = "1"
        code, output = self.bootstrap("--name", "project", "--loop-section", str(section))
        self.assertEqual(code, 2)
        self.assertIn("already exists", output)
        os.environ["FAKE_GH_CREATE_FAIL"] = ""
        code, output = self.bootstrap("--name", "project2", "--loop-section", str(section))
        self.assertEqual(code, 0, output)
        self.assertIn("Test command", git(self.root, "show", "origin/main:AGENTS.md"))

    def test_the_guard_still_refuses_an_agent_push_to_main(self):
        sys.path.insert(0, str(KIT / "hooks"))
        import guard
        self.assertTrue(guard.check_command("git push origin main", builder=False))
        self.assertTrue(guard.check_command("git push -u origin HEAD:main", builder=False))
        self.assertIsNone(guard.check_command(
            'python3 "/kit/scripts/gate.py" bootstrap --name project --protect', builder=False))


class BootstrapDocsTest(unittest.TestCase):
    def test_setup_runs_bootstrap_first_and_drops_manual_git(self):
        setup = (KIT / "skills" / "setup" / "SKILL.md").read_text()
        self.assertLess(setup.index("gate.py\" bootstrap"), setup.index("gate.py\" doctor"))
        self.assertNotIn("gate.py\" init", setup)
        self.assertNotIn("You never make the first commit", setup)
        self.assertIn("gh auth login", setup)

    def test_doctor_points_missing_ground_to_setup(self):
        text = (KIT / "scripts" / "doctor.py").read_text()
        self.assertNotIn("push a first commit to main", text)
        loopkit = (KIT / "scripts" / "loopkit.py").read_text()
        self.assertNotIn("make a first commit on main and push it", loopkit)


if __name__ == "__main__":
    unittest.main()
