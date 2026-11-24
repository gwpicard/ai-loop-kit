"""Git and GitHub errors retain a bounded tail with the actual rejection."""
import re
import subprocess
from unittest import mock

from kit.tests.helpers import FakeGh, make_repo, run_git
import common


class StderrTailTest(FakeGh):
    def test_real_non_fast_forward_rejection_is_in_the_reason(self):
        work, _ = make_repo(self.tmp)
        first = common.git(["commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", "Original"], cwd=work)
        run_git(["push", "origin", first + ":refs/heads/topic"], work)
        replacement = common.git([
            "commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", "Reworded",
        ], cwd=work)
        with self.assertRaises(common.GitError) as caught:
            common.git(["push", "origin", replacement + ":refs/heads/topic"], cwd=work)
        self.assertIn("[rejected]", str(caught.exception))
        self.assertIn("non-fast-forward", str(caught.exception))

    def test_both_wrappers_keep_a_fixed_number_of_final_stderr_lines(self):
        for wrapper in ("git", "gh"):
            retained = []
            for size in (80, 160):
                with self.subTest(wrapper=wrapper, size=size):
                    lines = ["diagnostic-%03d" % i for i in range(size)]
                    lines[-2] += " ! [rejected] topic -> topic (non-fast-forward)"
                    err = "\n".join(lines) + "\n"
                    if wrapper == "git":
                        patch = mock.patch.object(common.subprocess, "run", return_value=
                                                  subprocess.CompletedProcess([], 1, "", err))
                        call = lambda: common.git(["push", "origin", "topic"])
                    else:
                        self.scenario([{"match": "pr create", "responses": [{"code": 1, "stderr": err}]}])
                        patch = mock.patch.object(common, "sleep")
                        call = lambda: common.gh(["pr", "create"], retry=False)
                    with patch, self.assertRaises(common.LoopError) as caught:
                        call()
                    reason = str(caught.exception)
                    indices = [int(n) for n in re.findall(r"diagnostic-(\d+)", reason)]
                    retained.append(len(indices))
                    self.assertIn("non-fast-forward", reason)
                    self.assertGreaterEqual(len(indices), 2)
                    self.assertLess(len(indices), 80, "stderr must have a fixed bound")
                    self.assertEqual(indices, list(range(size - len(indices), size)))
            self.assertEqual(retained[0], retained[1], "the line bound must not grow with stderr")
