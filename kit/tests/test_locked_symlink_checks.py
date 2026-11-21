"""Locked test type changes and writes through symlinks must be refused."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from kit.tests.helpers import make_repo, run_git
import common
import merge


GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks", "guard.py")


class LockedSymlinkChecksTest(unittest.TestCase):
    def test_type_changes_name_the_locked_path_in_the_modification_reason(self):
        for baseline_is_symlink, relative in (
                (False, "tests/test_feature.py"),
                (True, "nested tests/test_other.py")):
            with self.subTest(baseline_is_symlink=baseline_is_symlink, path=relative):
                with tempfile.TemporaryDirectory() as folder:
                    work, _ = make_repo(folder, {"app.py": "pass\n"})
                    base = common.git(["rev-parse", "HEAD"], cwd=work)
                    path = os.path.join(work, relative)
                    os.makedirs(os.path.dirname(path))
                    target = "payload.py"
                    with open(os.path.join(os.path.dirname(path), target), "w") as stream:
                        stream.write("pass\n")
                    if baseline_is_symlink:
                        os.symlink(target, path)
                    else:
                        with open(path, "w") as stream:
                            stream.write(target)
                    run_git(["add", "."], work)
                    run_git(["commit", "-m", "Write locked test"], work)
                    baseline = common.git(["rev-parse", "HEAD"], cwd=work)

                    os.unlink(path)
                    if baseline_is_symlink:
                        with open(path, "w") as stream:
                            stream.write(target)
                    else:
                        os.symlink(target, path)
                    run_git(["add", "."], work)
                    run_git(["commit", "-m", "Change locked test type"], work)
                    head = common.git(["rev-parse", "HEAD"], cwd=work)
                    self.assertEqual(
                        merge.check_diff(work, base, head, [], set(), [relative], baseline),
                        "locked test modified: " + relative)

    def test_guard_refuses_writes_through_a_locked_symlink_to_a_non_test_target(self):
        for target in ("payload.py", "raise AssertionError"):
            with self.subTest(target=target):
                with tempfile.TemporaryDirectory() as folder:
                    work, _ = make_repo(folder, {"app.py": "pass\n"})
                    relative = "tests/test_feature.py"
                    os.mkdir(os.path.join(work, "tests"))
                    with open(os.path.join(work, "tests", target), "w") as stream:
                        stream.write("raise AssertionError\n")
                    os.symlink(target, os.path.join(work, relative))
                    env = {key: value for key, value in os.environ.items()
                           if not key.startswith("LOOP_")}
                    env.update(LOOP_ROLE="builder", LOOP_LOCKED=relative)
                    result = subprocess.run(
                        [sys.executable, GUARD], cwd=work, env=env,
                        input=json.dumps({"tool_name": "Write", "cwd": work,
                                          "tool_input": {"file_path": relative,
                                                         "content": "pass\n"}}),
                        capture_output=True, text=True)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("rule: test-lock", result.stderr)


if __name__ == "__main__":
    unittest.main()
