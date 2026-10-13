"""The merge rehearsal keeps unrelated local work out of the person's commit."""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class PersonMainMove(unittest.TestCase):
    def test_only_the_named_person_change_is_staged(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="person-main-move-"))
        repo = base / "project"
        repo.mkdir()
        remote = base / "origin.git"
        env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_AUTHOR_NAME": "Test Person",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test Person",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }

        def git(*args: str) -> str:
            return subprocess.run(
                ["git", *args], cwd=repo, env=env, check=True, capture_output=True, text=True
            ).stdout

        git("init", "-q", "--bare", "-b", "main", str(remote))
        git("init", "-q", "-b", "main")
        (repo / "CHANGELOG.md").write_text("old entry\n")
        (repo / "sp").mkdir()
        git("add", "CHANGELOG.md")
        git("commit", "-qm", "Start the project")
        git("remote", "add", "origin", str(remote))
        git("push", "-q", "origin", "main")
        git("checkout", "-qb", "piece")
        (repo / "CHANGELOG.md").write_text("piece entry\n")
        git("add", "CHANGELOG.md")
        git("commit", "-qm", "Build the piece")
        git("checkout", "-q", "main")
        # The completed run leaves records in the attended worktree. They do
        # not belong to the independent change that moves the remote base.
        (repo / "CHANGELOG.md").write_text("unrelated local entry\n")
        (repo / "runtime-record.json").write_text("{}\n")
        source = (ROOT / "tests/merge-decision.sh").read_text()
        function = re.search(r"^move_main\(\) \{.*?^\}", source, re.M | re.S)
        assert function is not None
        subprocess.run(
            ["sh", "-c", function.group() + "\nmove_main moved-g"],
            cwd=repo,
            env={**env, "TP_ROOT": str(repo)},
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines(),
            ["sp/moved-g.txt"],
        )
        self.assertEqual((repo / "CHANGELOG.md").read_text(), "unrelated local entry\n")
        # A clean remote-side merge must still succeed even though the
        # attended worktree holds a conflicting, uncommitted changelog.
        clean = base / "clone"
        git("clone", "-q", str(remote), str(clean))
        git("push", "-q", "origin", "piece")
        subprocess.run(["git", "fetch", "-q", "origin"], cwd=clean, env=env, check=True)
        subprocess.run(
            ["git", "merge", "-q", "--no-ff", "origin/piece", "-m", "Merge the piece"],
            cwd=clean,
            env=env,
            check=True,
            capture_output=True,
        )


class FailedRemoteMerge(unittest.TestCase):
    def test_conflict_prints_git_output_and_keeps_clone(self) -> None:
        import contextlib
        import io
        import runpy
        from unittest.mock import patch

        base = Path(tempfile.mkdtemp(prefix="failed-remote-merge-"))
        repo = base / "project"
        repo.mkdir()
        remote = base / "origin.git"
        env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_AUTHOR_NAME": "Test Person",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test Person",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }

        def git(*args: str) -> None:
            subprocess.run(
                ["git", *args], cwd=repo, env=env, check=True, capture_output=True, text=True
            )

        git("init", "-q", "--bare", "-b", "main", str(remote))
        git("init", "-q", "-b", "main")
        (repo / "same.txt").write_text("start\n")
        git("add", "same.txt")
        git("commit", "-qm", "Start the project")
        git("remote", "add", "origin", str(remote))
        git("checkout", "-qb", "piece")
        (repo / "same.txt").write_text("piece\n")
        git("commit", "-qam", "Build the piece")
        git("checkout", "-q", "main")
        (repo / "same.txt").write_text("person\n")
        git("commit", "-qam", "Move main")
        git("push", "-q", "origin", "main", "piece")
        module = runpy.run_path(
            str(ROOT / "tests/stand-ins/fake-github/gh"), run_name="fake_github"
        )
        stderr = io.StringIO()
        old = Path.cwd()
        make_temp = tempfile.mkdtemp
        try:
            os.chdir(repo)
            with (
                patch.dict(os.environ, env),
                contextlib.redirect_stderr(stderr),
                patch("tempfile.mkdtemp", side_effect=lambda **kw: make_temp(dir=base, **kw)),
            ):
                landed = module["land_on_remote"]({"head": "piece", "base": "main", "number": 1})
        finally:
            os.chdir(old)
        self.assertFalse(landed)
        self.assertIn("merge", stderr.getvalue())
        self.assertIn("CONFLICT", stderr.getvalue())
        self.assertTrue(list(base.glob("fake-gh-merge-*/clone/.git")))


class ScratchEvidence(unittest.TestCase):
    def test_snapshot_omits_keys_auth_logs_and_git_object_payloads(self) -> None:
        import runpy

        base = Path(tempfile.mkdtemp(prefix="merge-evidence-"))
        raw, out = base / "raw", base / "out"
        (raw / "project/.git/objects/ab").mkdir(parents=True)
        (raw / "project/.git/refs/heads").mkdir(parents=True)
        (raw / "origin.git/objects").mkdir(parents=True)
        (raw / "data").mkdir()
        (raw / "data/app-key.pem").write_text("private fixture key\n")
        (raw / "other.txt").write_text("-----BEGIN " + "PRIVATE KEY-----\nprivate fixture key\n")
        (raw / "gh-state.json").write_text('{"app_tokens": ["private-token"]}\n')
        (raw / "gh.log").write_text("Authorization: Bearer private-token\n")
        (raw / "project/.git/objects/ab/object").write_bytes(b"compressed-secret-fixture")
        (raw / "origin.git/objects/object").write_bytes(b"compressed-secret-fixture")
        (raw / "project/.git/refs/heads/main").write_text("a" * 40 + "\n")
        (raw / "project/.git/config").write_text(
            "url = https://user:password@example.invalid/repo\n"
        )
        (raw / "merge.err").write_text("CONFLICT: same.txt\nAuthorization: Bearer private-token\n")
        (raw / "linked-key").symlink_to(raw / "data/app-key.pem")
        module = runpy.run_path(
            str(ROOT / "tests/lib/merge-rehearsal-evidence.py"), run_name="merge_evidence"
        )
        module["snapshot"](raw, out)
        files = {str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()}
        self.assertIn("project/.git/refs/heads/main", files)
        self.assertIn(b"CONFLICT: same.txt", files["merge.err"])
        text = b"\n".join(files.values())
        for value in [
            b"private fixture key",
            b"private-token",
            b"compressed-secret-fixture",
            b"password",
        ]:
            self.assertNotIn(value, text)
        self.assertTrue((raw / "data/app-key.pem").is_file())


if __name__ == "__main__":
    unittest.main()
