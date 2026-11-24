"""Retaining stderr tails must preserve single-line wrapper errors."""
import subprocess
from unittest import mock

from kit.tests.helpers import FakeGh
import common


class StderrTailCompatibilityTest(FakeGh):
    def test_both_wrappers_join_the_retained_tail_on_one_line(self):
        lines = ["diagnostic-%02d" % i for i in range(25)]
        lines[-2] = "! [rejected] topic -> topic (non-fast-forward)"
        stderr = "\n".join(lines) + "\n"
        self.scenario([{"match": "pr create", "responses": [
            {"code": 1, "stderr": stderr}]}])
        result = subprocess.CompletedProcess([], 1, "", stderr)
        for wrapper in ("git", "gh"):
            with self.subTest(wrapper=wrapper):
                with self.assertRaises(common.LoopError) as caught:
                    if wrapper == "git":
                        with mock.patch.object(common.subprocess, "run", return_value=result):
                            common.git(["push", "origin", "topic"])
                    else:
                        common.gh(["pr", "create"], retry=False)
                reason = str(caught.exception)
                self.assertEqual(len(reason.splitlines()), 1)
                self.assertTrue(reason.endswith(" | ".join(lines[-20:])), reason)
                self.assertNotIn("diagnostic-04", reason)
