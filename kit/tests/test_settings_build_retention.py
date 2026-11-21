"""A reload failure must not turn eligible builds into crashes or parks."""
import contextlib
import io
import json
import os
from pathlib import Path
import time
from unittest import mock

from kit.tests import test_flow, test_loop_pause
from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git, settings_json, write_exe
import loop


SLEEP = time.sleep
STOP = str(Path(__file__).resolve().parents[1] / "hooks" / "stop.py")


class BuildRetentionTest(FakeClaudeGh):
    def check_build(self, damaged, parallel):
        self.work, _ = make_repo(self.tmp, {
            "loop.json": settings_json(test_flow.AGENTS + "Parallel: %d\nIdle hours: 12\n" % parallel)})
        root = Path(self.work)
        (root / "loop.local.json").write_text("{}")
        run_git(["push", "origin", "main:loop/main"], self.work)
        gh_dir = Path(self.tmp, "gh2")
        gh_dir.mkdir()
        os.environ["FAKE_GH2"] = str(gh_dir)
        write_exe(str(Path(self.tmp, "bin", "gh")), test_loop_pause.FAKE_GH)
        self.claude({
            "test-writer": [test_flow.WRITER],
            "builder": [{"files": {"app.py": "1\n"}, "stop_hook": STOP}],
            "reviewer": [test_flow.APPROVE]})
        cycles = []

        def world(st):
            cycles.append(True)
            if len(cycles) == 1:
                st["issues"] = []
                (root / damaged).write_text("{")
                return
            state_path = gh_dir / "state.json"
            state = json.loads(state_path.read_text()) if state_path.exists() else {}
            done = state.get("closed") or "needs-user" in state.get("labels", [])
            st["issues"] = [] if done else [dict(number=7, title="Piece", body="Do it.", labels={"ready"})]
            if done or len(cycles) > 1000:
                (root / ".loop" / "stop").touch()

        output = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.callback(os.chdir, os.getcwd())
            os.chdir(self.work)
            for target, options in (
                    ("loop.setup.missing", {"return_value": None}),
                    ("loop.snapshot", {"side_effect": world}),
                    ("loop.write_board", {"return_value": None}),
                    ("loop.sync_default", {"return_value": False}),
                    ("loop.drain", {"return_value": None}),
                    ("loop.headroom", {"return_value": None}),
                    ("common.ready_is_trusted", {"return_value": True}),
                    ("loop.POLL", {"new": 5}),
                    ("loop.BUSY_POLL", {"new": 0.01}),
                    ("loop.time.sleep", {"side_effect": lambda _: SLEEP(0.01)})):
                stack.enter_context(mock.patch(target, **options))
            with contextlib.redirect_stdout(output):
                self.assertEqual(loop.main(["run"]), 0)
        text = output.getvalue()
        logs = root / ".loop" / "logs"
        text += "".join(p.read_text() for p in logs.glob("build-*.log"))
        self.assertTrue(json.loads((gh_dir / "state.json").read_text()).get("closed"), text)
        self.assertEqual([c["role"] for c in self.claude_calls()],
                         ["test-writer", "builder", "reviewer"], text)
        self.assertEqual(text.count("keeping previous settings"), 1, text)
        self.assertNotIn("crash on", text)
        self.assertNotIn("parked", text)

    def test_serial_build_keeps_settings_after_committed_file_fails(self):
        self.check_build("loop.json", 1)

    def test_serial_build_keeps_settings_after_local_file_fails(self):
        self.check_build("loop.local.json", 1)

    def test_worker_build_keeps_settings_after_committed_file_fails(self):
        self.check_build("loop.json", 2)

    def test_worker_build_keeps_settings_after_local_file_fails(self):
        self.check_build("loop.local.json", 2)
