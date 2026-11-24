"""A supervisor that never completed a snapshot still writes its crash reason."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import common
import loop


class CrashBoardTest(unittest.TestCase):
    def test_first_snapshot_failure_resolves_factory_and_writes_crash_reason(self):
        with tempfile.TemporaryDirectory(dir=tempfile.gettempdir()) as folder:
            root = Path(folder)
            (root / "loop.json").write_text(json.dumps({"Test command": "true"}))
            edits, queries = [], []

            def github(args, input=None, **kwargs):
                queries.append(args)
                if args[:2] == ["issue", "list"]:
                    return 0, json.dumps([
                        {"number": 8, "title": "Factory notes", "body": "Leave this alone"},
                        {"number": 42, "title": "Factory", "body": "Old board"}]), ""
                if args[:3] == ["issue", "edit", "42"]:
                    edits.append(input)
                    return 0, "", ""
                raise AssertionError("unexpected GitHub call: %r" % args)

            def wait(path, seconds):
                if snapshot.call_count > 3:
                    Path(path).touch()

            with contextlib.ExitStack() as stack:
                stack.callback(os.chdir, os.getcwd())
                os.chdir(root)
                for name in ("setup.missing", "common.restore_loop_branch", "common.warn_delete_branch_on_merge",
                             "clean_up"):
                    stack.enter_context(mock.patch("loop." + name, return_value=None))
                stack.enter_context(mock.patch.object(loop.setup, "tidy", return_value=([], None)))
                stack.enter_context(mock.patch.object(loop, "stray_workers", return_value=[]))
                stack.enter_context(mock.patch.object(loop.shutil, "which", return_value=None))
                snapshot = stack.enter_context(mock.patch.object(
                    loop, "snapshot", side_effect=TypeError("snapshot failed before board discovery")))
                stack.enter_context(mock.patch.object(loop, "wait_stop", side_effect=wait))
                stack.enter_context(mock.patch.object(common, "_run_gh", side_effect=github))
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
                code = loop.main(["run"])

            self.assertEqual(code, 1)
            self.assertEqual(snapshot.call_count, 3)
            self.assertTrue(any(args[:2] == ["issue", "list"] for args in queries), queries)
            self.assertEqual(len(edits), 1, edits)
            self.assertIn("TypeError: snapshot failed before board discovery", edits[0])
            self.assertIn("3 identical failed cycles", edits[0])
            self.assertIn("Next check: none, the loop has stopped", edits[0])
