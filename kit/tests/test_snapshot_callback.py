"""A supervisor cycle keeps the one-argument snapshot callback contract."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import loop


class SnapshotCallbackTest(unittest.TestCase):
    def test_run_calls_snapshot_with_only_state(self):
        with tempfile.TemporaryDirectory() as project:
            root = Path(project)
            (root / "loop.json").write_text(json.dumps({"Test command": "true", "Loop branch": "loop/batch"}))
            (root / ".loop").mkdir()
            seen = []

            def snapshot(st):
                seen.append((st["branch"], st["project"]))

            def stop(*args):
                (root / ".loop/stop").touch()

            output = io.StringIO()
            with contextlib.ExitStack() as stack:
                for target in ("setup.tidy", "common.warn_delete_branch_on_merge",
                               "common.restore_loop_branch", "sync_default", "drain",
                               "write_board", "clean_up"):
                    stack.enter_context(mock.patch("loop." + target, return_value=([], None)
                                                   if target == "setup.tidy" else None))
                stack.enter_context(mock.patch.object(loop, "snapshot", side_effect=snapshot))
                stack.enter_context(mock.patch.object(loop, "wait_stop", side_effect=stop))
                stack.enter_context(contextlib.redirect_stdout(output))
                self.assertEqual(loop.run(project), 0)
            self.assertEqual(seen, [("loop/batch", project)], output.getvalue())
            self.assertNotIn("problem, will check again", output.getvalue())
