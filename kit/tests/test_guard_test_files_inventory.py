import os
from pathlib import Path
import shlex
import tempfile

from kit.tests.helpers import make_repo
from kit.tests.test_guard import GuardCase


class TestTestFilesInventory(GuardCase):
    def test_worktree_inventory_includes_new_modules_and_excludes_deleted_ones(self):
        with tempfile.TemporaryDirectory() as folder:
            work, _ = make_repo(folder, {"tests/test_old.py": "pass\n",
                                         "tests/test_gone.py": "pass\n"})
            Path(work, "tests/test_gone.py").unlink()
            Path(work, "tests/test_new.py").write_text("pass\n")
            kw = dict(role="builder", cwd=work, test="make test", files="pytest {files}")
            self.allowed(self.bash("pytest tests/test_old.py", **kw))
            result = self.bash("pytest tests/test_new.py tests/test_old.py", **kw)
            self.refused(result)
            self.assertIn("rule: full-test", result.stderr.splitlines())

    def test_quoted_paths_and_template_suffix_match_through_the_hook(self):
        with tempfile.TemporaryDirectory() as folder:
            modules = ("tests/test one.py", "tests/test_two.py")
            work, _ = make_repo(folder, {p: "pass\n" for p in modules})
            kw = dict(role="builder", cwd=work, test="make test",
                      files="pytest {files} --quiet")
            paths = " ".join(shlex.quote(os.path.join(work, p)) for p in modules)
            baseline = self.bash("make test", **kw)
            result = self.bash("true && pytest " + paths + " --quiet", **kw)
            self.refused(result)
            self.assertEqual(result.stderr, baseline.stderr)
            self.allowed(self.bash("pytest 'tests/test one.py' --quiet", **kw))
            self.refused(self.bash("pytest --quiet", **kw))
