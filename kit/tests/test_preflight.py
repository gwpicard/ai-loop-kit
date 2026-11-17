import contextlib
import io
import os
import pathlib
import tempfile
import unittest
from unittest import mock

from kit.tests.helpers import FakeGh, make_repo
import common
import setup

HINT = ("hint: a test that passes in the project folder but fails here usually depends on "
        "where the checkout lives or on files git does not track")


def rule(match, stdout="", code=0):
    return {"match": match, "responses": [{"stdout": stdout, "stderr": "", "code": code}]}


class ScratchTreePathTest(FakeGh):
    def test_checkout_path_has_no_symbolic_link(self):
        work, _ = make_repo(self.tmp, {"README.md": "x\n"})
        real = os.path.join(self.tmp, "real")
        os.makedirs(real)
        link = os.path.join(self.tmp, "link")
        os.symlink(real, link)
        with mock.patch.object(tempfile, "tempdir", link):
            with common.scratch_tree(work, "HEAD") as tree:
                self.assertEqual(tree, os.path.realpath(tree))
                self.assertNotIn(link, tree)


class PreflightOutputTest(FakeGh):
    def setup_failing(self, agents):
        self.work, _ = make_repo(self.tmp, {"AGENTS.md": agents})
        self.scenario([rule("label list", "[]"), rule("label create"), rule("issue list", "[]"),
                       rule("issue create", "https://github.com/o/r/issues/7\n"), rule("issue pin")])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = setup.setup(self.work)
        return code, buf.getvalue()

    def log(self):
        return pathlib.Path(self.work, ".lite", "logs", "preflight.log").read_text()

    def test_failure_prints_tail_log_path_folder_and_hint(self):
        code, text = self.setup_failing("## Loop\nTest command: seq 1 30; exit 1\n")
        self.assertEqual(code, 1)
        self.assertIn("preflight.log", text)
        self.assertIn("lite-tree-", text)
        self.assertIn(HINT, text)
        self.assertIn("\n30\n", text)
        self.assertIn("\n11\n", text)
        self.assertNotIn("\n10\n", text)
        log = self.log()
        self.assertIn("\n1\n", "\n" + log)
        self.assertIn("\n30\n", log + "\n")

    def test_log_holds_each_command_in_order_and_is_replaced(self):
        agents = "## Loop\nPrepare command: echo prepared-marker\nTest command: echo tested-marker; exit 1\n"
        self.setup_failing(agents)
        log = self.log()
        self.assertLess(log.index("prepared-marker"), log.index("tested-marker"))
        pathlib.Path(self.work, ".lite", "logs", "preflight.log").write_text("stale-marker\n")
        self.setup_failing(agents)
        self.assertNotIn("stale-marker", self.log())


if __name__ == "__main__":
    unittest.main()
