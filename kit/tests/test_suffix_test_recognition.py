import json
from pathlib import Path
import tempfile
import unittest

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import FakeGh, make_repo, run_git, settings_json
from kit.tests import test_guard, test_merge
import flow
import merge


SUFFIX_TESTS = (
    "marcdownTests/EditorTests.swift", "marcdownUITests/ReturnUITests.swift",
    "Sources/App/FooTests.swift", "src/FooSpec.scala", "src/FooSpec.hs",
    "src/foo_tests.rs", "web/login-test.js",
)
SOURCE_FILES = (
    "Sources/App/Contest.swift", "src/Respect.scala", "src/latest.rs", "web/contest.js",
)


class SuffixRecognitionTest(unittest.TestCase):
    def test_each_suffix_is_a_test_module_and_file(self):
        for path in SUFFIX_TESTS:
            for predicate in (merge.is_test_module, merge.is_test_file):
                with self.subTest(path=path, predicate=predicate.__name__):
                    self.assertTrue(predicate(path), path)

    def test_suffix_recognition_keeps_source_lookalikes_out(self):
        for path in SOURCE_FILES:
            for predicate in (merge.is_test_module, merge.is_test_file):
                with self.subTest(path=path, predicate=predicate.__name__):
                    self.assertFalse(predicate(path), path)


class SwiftWriterFlowTest(FakeClaudeGh):
    def test_swift_tests_block_reaches_fails_first(self):
        work, _ = make_repo(self.tmp, {"loop.json": settings_json(
            "## Loop\nTest command: echo 'AssertionError: implementation missing'; false\n"
            "Loop branch: loop/main\n")})
        run_git(["push", "origin", "main:loop/main"], work)
        self.scenario([
            {"match": "issue view 7", "responses": [{"stdout": json.dumps({
                "title": "Add editing", "body": "Add editing behaviour.", "comments": []})}]},
            {"match": "issue comment", "responses": [{}]},
            {"match": "issue edit", "responses": [{}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
        ])
        path = "marcdownTests/EditorTests.swift"
        self.claude({
            "test-writer": [{"files": {path: "import XCTest\n"}, "reply": "TESTS:\n" + path}],
            "builder": [{"error": "Stopped after reaching builder"}],
        })
        result = flow.build(7, work)
        calls = self.claude_calls()
        self.assertEqual([call["role"] for call in calls], ["test-writer", "builder"], result.reason)
        self.assertEqual(calls[1]["env"]["LOOP_LOCKED"], path)
        events = [json.loads(line) for line in Path(work, ".loop/events.jsonl").read_text().splitlines()]
        self.assertTrue(any(event.get("step") == "fails-first" for event in events), events)


class SwiftGuardLockTest(test_guard.GuardCase):
    def test_existing_swift_tests_are_locked_like_python_tests(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = ("tests/test_editor.py", "marcdownTests/EditorTests.swift",
                     "Sources/App/FooTests.swift")
            work, _ = make_repo(folder, {path: "original\n" for path in paths})
            for path in paths:
                for role in ("builder", "test-writer"):
                    with self.subTest(path=path, role=role):
                        result = self.call("Edit", {
                            "file_path": path, "old_string": "original", "new_string": "changed",
                        }, role=role, cwd=work)
                        self.refused(result, "existing test")
                        self.assertIn("rule: test-lock", result.stderr)


class SwiftMergeLockTest(FakeGh):
    branch = test_merge.MergeTest.branch
    rules = test_merge.MergeTest.rules
    run_merge = test_merge.MergeTest.run_merge

    def test_merge_refuses_existing_swift_tests_like_python_tests(self):
        for path in ("tests/test_editor.py", "marcdownTests/EditorTests.swift",
                     "Sources/App/FooTests.swift"):
            for deleted in (False, True):
                with self.subTest(path=path, deleted=deleted):
                    self.work, _ = make_repo(self.tmp, {
                        "loop.json": settings_json("## Loop\nTest command: true\nLoop branch: loop/main\n"),
                        path: "original\n",
                    })
                    run_git(["push", "origin", "main:loop/main"], self.work)
                    sha = self.branch({} if deleted else {path: "changed\n"},
                                      remove=[path] if deleted else [])
                    self.rules(sha, [None, "OPEN", "MERGED"])
                    result = self.run_merge(sha)
                    self.assertFalse(result.ok, result.reason)
                    self.assertEqual((result.park, result.rule), (True, "test-lock"), result.reason)
                    self.assertIn("existing test file changed: " + path, result.reason)
                    self.assertFalse(any(call[:2] == ["pr", "merge"] for call in self.calls()))


if __name__ == "__main__":
    unittest.main()
