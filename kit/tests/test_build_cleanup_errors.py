"""A failed temporary-folder clean-up must preserve the build's outcome."""
import json
import os
from pathlib import Path
import unittest
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git
import common
import loop
import session


class BuildCleanupErrorsTest(FakeClaudeGh):
    def setUp(self):
        super().setUp()
        self.work, _ = make_repo(self.tmp, {"loop.json": json.dumps({
            "Test command": "echo AssertionError; exit 1",
            "Session minutes": 0.05,
        })})
        run_git(["push", "origin", "main:loop/main"], self.work)

    def unremovable_entry(self, folder):
        entry = Path(folder, "read-only", "remaining")
        entry.parent.mkdir()
        entry.write_text("keep until clean-up is possible\n")
        entry.parent.chmod(0o555)
        self.addCleanup(entry.parent.chmod, 0o755)
        with self.assertRaises(PermissionError):
            entry.unlink()
        return entry

    def test_removing_a_pid_from_a_missing_record_does_not_create_it(self):
        for name in ("loop-groups-missing", "pass-hooks-missing"):
            with self.subTest(name=name):
                record = Path(self.tmp, name)
                common._record(str(record), 12345, False)
                self.assertFalse(record.exists(), "removing a pid recreated its record file")

    def test_failed_folder_removal_is_logged_once_and_does_not_raise(self):
        entry = None
        try:
            with common.build_environment(self.work):
                folder = Path(common.build_env()["TMPDIR"])
                entry = self.unremovable_entry(folder)
        except OSError as error:
            self.fail("build_environment replaced the outcome with %s" % error)

        self.assertTrue(folder.is_dir())
        self.assertEqual(entry.read_text(), "keep until clean-up is possible\n")
        log = Path(self.work, ".loop", "loop.out")
        self.assertTrue(log.is_file(), "the clean-up failure was not logged")
        lines = log.read_text().splitlines()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn(str(folder), lines[0])
        self.assertIn(os.strerror(13), lines[0])

    def test_builder_timeout_survives_failed_cleanup_in_events_and_comment(self):
        self.scenario([
            {"match": "issue view 7", "responses": [{"stdout": json.dumps({
                "title": "Build it", "body": "Implement the change.", "comments": [],
            })}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "issue comment", "responses": [{}]},
            {"match": "issue edit", "responses": [{}]},
        ])
        self.claude({
            "test-writer": [{"files": {"tests/test_new.py": "assert False\n"},
                             "reply": "TESTS:\ntests/test_new.py"}],
            "builder": [{"sleep": 30}],
        })
        run = session.run
        entries = []

        def run_with_leftover(role, *args, **kwargs):
            if role == "builder":
                entries.append(self.unremovable_entry(common.build_env()["TMPDIR"]))
            return run(role, *args, **kwargs)

        with mock.patch.object(session, "run", side_effect=run_with_leftover), \
                mock.patch.object(loop, "gh", wraps=loop.gh) as gh:
            result = loop.build_attempts(self.work, 7, [])

        self.assertEqual(len(entries), 2, "both attempts must reach the builder: " + result
                         + "\n" + Path(self.work, ".loop/events.jsonl").read_text())
        self.assertTrue(all(entry.is_file() for entry in entries))
        expected = "builder session timed out after 0.05 minutes"
        events = [json.loads(line) for line in
                  Path(self.work, ".loop/events.jsonl").read_text().splitlines()]
        crashes = [event for event in events if event["kind"] == "crashed"]
        with self.subTest(report="events"):
            self.assertEqual([event["reason"] for event in crashes], [expected, expected])
        comments = [call.kwargs["input"] for call in gh.call_args_list
                    if call.args[0][:2] == ["issue", "comment"]]
        self.assertEqual(len(comments), 1)
        with self.subTest(report="issue comment"):
            self.assertIn(expected, comments[0])
            self.assertNotIn("OSError", comments[0])
            self.assertNotIn("Permission denied", comments[0])


if __name__ == "__main__":
    unittest.main()
