import contextlib
import io
import os
import pathlib

from kit.tests.helpers import FakeGh, make_repo
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
        self.assertIn(".loop/", pathlib.Path(self.work, ".gitignore").read_text())
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

    def test_optional_commands_are_reported_not_required(self):
        self.repo("## Loop\nTest command: true\nCheck command: true\nSmoke command: echo ok\n")
        self.fresh()
        code, text = run(self.work)
        self.assertEqual(code, 0, text)
        self.assertIn("optional: Check command: true; Smoke command: echo ok; Session minutes: 45; Parallel: 1", text)

    def test_no_optional_commands_is_said_plainly(self):
        self.repo()
        self.fresh()
        self.assertIn("no Check or Smoke command set", run(self.work)[1])

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


class TidyTest(FakeGh):
    def make(self, folder, names):
        for name in names:
            path = os.path.join(self.tmp, folder, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            pathlib.Path(path).write_text(name)

    def test_nothing_to_tidy(self):
        self.assertEqual(setup.tidy(self.tmp), ([], None))

    def test_1x_files_move_aside_and_lite_moves_in(self):
        self.make(".loop", ["heartbeat", "events.jsonl", "logs/piece-1-attempt-1.log"])
        self.make(".lite", ["pass.json", "events.jsonl", "logs/7-builder-1.log"])
        moved, refusal = setup.tidy(self.tmp)
        self.assertIsNone(refusal)
        loop = pathlib.Path(self.tmp, ".loop")
        self.assertEqual((loop / "v1" / "events.jsonl").read_text(), "events.jsonl")
        self.assertTrue((loop / "v1" / "heartbeat").exists())
        self.assertTrue((loop / "v1" / "logs" / "piece-1-attempt-1.log").exists())
        self.assertTrue((loop / "pass.json").exists())
        self.assertTrue((loop / "logs" / "7-builder-1.log").exists())
        self.assertFalse(pathlib.Path(self.tmp, ".lite").exists())
        self.assertIn(".lite/pass.json to .loop/", moved)
        self.assertEqual(setup.tidy(self.tmp), ([], None))  # safe to run again

    def test_a_file_already_in_loop_is_kept_and_the_old_one_moves_beside_it(self):
        self.make(".loop", ["loop.out"])  # the start command creates it before the loop runs
        pathlib.Path(self.tmp, ".loop", "loop.out").write_text("new")
        self.make(".lite", ["loop.out", "events.jsonl"])
        moved, _ = setup.tidy(self.tmp)
        self.assertEqual(pathlib.Path(self.tmp, ".loop", "loop.out").read_text(), "new")
        self.assertEqual(pathlib.Path(self.tmp, ".loop", "loop.out.lite").read_text(), "loop.out")
        self.assertTrue(pathlib.Path(self.tmp, ".loop", "events.jsonl").exists())
        self.assertFalse(pathlib.Path(self.tmp, ".lite").exists())
        self.assertIn(".lite/loop.out to .loop/loop.out.lite", moved)

    def test_the_start_command_s_output_stays_when_1x_files_move_aside(self):
        self.make(".loop", ["heartbeat", "loop.out"])
        setup.tidy(self.tmp)
        self.assertTrue(pathlib.Path(self.tmp, ".loop", "loop.out").exists())
        self.assertTrue(pathlib.Path(self.tmp, ".loop", "v1", "heartbeat").exists())

    def test_a_live_loop_in_lite_refuses_and_moves_nothing(self):
        self.make(".loop", ["heartbeat"])
        pathlib.Path(self.tmp, ".lite").mkdir()
        pathlib.Path(self.tmp, ".lite", "loop.pid").write_text(str(os.getppid()))
        moved, refusal = setup.tidy(self.tmp)
        self.assertEqual(moved, [])
        self.assertIn("running from .lite/", refusal)
        self.assertTrue(pathlib.Path(self.tmp, ".loop", "heartbeat").exists())

    def test_a_running_loop_s_own_files_are_never_moved(self):
        self.make(".loop", ["heartbeat", "builds/7.step"])
        pathlib.Path(self.tmp, ".loop", "loop.pid").write_text(str(os.getppid()))
        self.assertEqual(setup.tidy(self.tmp), ([], None))
        self.assertTrue(pathlib.Path(self.tmp, ".loop", "builds", "7.step").exists())

    def test_folders_in_both_are_merged(self):
        self.make(".loop", ["logs/8-reviewer-1.log"])
        self.make(".lite", ["logs/7-builder-1.log", "logs/8-reviewer-1.log"])
        moved, _ = setup.tidy(self.tmp)
        self.assertTrue(pathlib.Path(self.tmp, ".loop", "logs", "7-builder-1.log").exists())
        self.assertIn(".lite/logs/ merged into .loop/logs/", moved)
        self.assertTrue(pathlib.Path(self.tmp, ".lite", "logs", "8-reviewer-1.log").exists())  # never overwritten

    def test_a_loop_file_in_the_way_refuses_without_a_traceback(self):
        pathlib.Path(self.tmp, ".loop").write_text("x")
        self.make(".lite", ["pass.json"])
        moved, refusal = setup.tidy(self.tmp)
        self.assertIn("could not be moved", refusal)
        self.assertTrue(pathlib.Path(self.tmp, ".lite", "pass.json").exists())
