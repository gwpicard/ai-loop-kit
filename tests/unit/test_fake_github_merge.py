"""The merge rehearsal keeps unrelated local work out of the person's commit."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PersonMainMove(unittest.TestCase):
    def test_only_the_named_person_change_is_staged(self):
        base = Path(tempfile.mkdtemp(prefix="person-main-move-"))
        repo = base / "project"
        repo.mkdir()
        remote = base / "origin.git"
        env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
               "GIT_AUTHOR_NAME": "Test Person", "GIT_AUTHOR_EMAIL": "test@example.invalid",
               "GIT_COMMITTER_NAME": "Test Person", "GIT_COMMITTER_EMAIL": "test@example.invalid"}

        def git(*args):
            return subprocess.run(["git", *args], cwd=repo, env=env, check=True,
                                  capture_output=True, text=True).stdout

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
        subprocess.run(["sh", "-c", function.group() + "\nmove_main moved-g"],
                       cwd=repo, env={**env, "TP_ROOT": str(repo)}, check=True,
                       capture_output=True, text=True)
        self.assertEqual(git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines(),
                         ["sp/moved-g.txt"])
        self.assertEqual((repo / "CHANGELOG.md").read_text(), "unrelated local entry\n")
        # A clean remote-side merge must still succeed even though the
        # attended worktree holds a conflicting, uncommitted changelog.
        clean = base / "clone"
        git("clone", "-q", str(remote), str(clean))
        git("push", "-q", "origin", "piece")
        subprocess.run(["git", "fetch", "-q", "origin"], cwd=clean, env=env, check=True)
        subprocess.run(["git", "merge", "-q", "--no-ff", "origin/piece", "-m", "Merge the piece"],
                       cwd=clean, env=env, check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
