import contextlib
import io
import os
import pathlib

from lite.tests.helpers import FakeGh, make_repo
import setup


def rule(match, stdout="", code=0, stderr=""):
    return {"match": match, "responses": [{"stdout": stdout, "stderr": stderr, "code": code}]}


def run(project):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = setup.setup(project)
    return code, buf.getvalue()


class SetupTest(FakeGh):
    def repo(self, agents="## Loop\nTest command: true\n"):
        files = {"AGENTS.md": agents} if agents else {"README.md": "x\n"}
        self.work, self.origin = make_repo(self.tmp, files)

    def fresh(self):
        self.scenario([rule("label list", "[]"), rule("label create"), rule("issue list", "[]"),
                       rule("issue create", "https://github.com/o/r/issues/7\n"),
                       rule("issue pin")])

    def done(self, test="true"):
        self.scenario([rule("label list", '[{"name":"%s"}]' % '"},{"name":"'.join(setup.LABELS)),
                       rule("issue list", '[{"number":7,"title":"Factory"}]')])

    def writes(self):
        return [c for c in self.calls() if c[:2] in (["label", "create"], ["issue", "create"],
                                                      ["issue", "pin"])]

    def test_first_run_creates_everything(self):
        self.repo()
        self.fresh()
        code, text = run(self.work)
        self.assertEqual(code, 0, text)
        self.assertEqual(len([c for c in self.writes() if c[:2] == ["label", "create"]]), 5)
        self.assertIn(["issue", "pin", "7"], self.calls())
        self.assertIn(".lite/", pathlib.Path(self.work, ".gitignore").read_text())
        self.assertIn("preflight: the Test command passes", text)
        self.assertIn("protect main", text)
        self.assertIn("refs/heads/loop/main", __import__("subprocess").run(
            ["git", "ls-remote", self.origin], capture_output=True, text=True).stdout)

    def test_second_run_changes_nothing(self):
        self.repo()
        self.fresh()
        run(self.work)
        self.done()
        before = pathlib.Path(self.work, ".gitignore").read_text()
        code, text = run(self.work)
        self.assertEqual(code, 0, text)
        self.assertEqual(self.writes(), [])
        self.assertIn("summary: 0 change(s)", text)
        self.assertEqual(pathlib.Path(self.work, ".gitignore").read_text(), before)

    def test_missing_section_is_refused(self):
        self.repo(agents="# Project\n")
        self.fresh()
        code, text = run(self.work)
        self.assertEqual(code, 1)
        self.assertIn("refused:", text)
        self.assertIn("Test command:", text)
        self.assertEqual(self.calls(), [])

    def test_failing_preflight_is_reported(self):
        self.repo("## Loop\nTest command: false\n")
        self.fresh()
        code, text = run(self.work)
        self.assertEqual(code, 1)
        self.assertIn("preflight: the Test command failed", text)
        self.assertIn("preflight failed", text)
