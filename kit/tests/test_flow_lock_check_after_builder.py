"""Builder diff breaches return for repair before a reviewer starts."""
import inspect
import json
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git
import common
import flow
import loop
import merge


EXISTING = "Tests/MarcdownCoreTests/CommandAvailabilityTests.swift"
OTHER_EXISTING = "Tests/MarcdownUITests/SingleFileFindUITests.swift"
LOCKED = "tests/test_new.py"
PROTECTED = "policy/rules.txt"
ORIGINAL = "// Existing test.\n"
NEW_TEST = ("from pathlib import Path\n"
            "assert Path('app.py').is_file(), 'The app has not been built'\n")
APPROVE = {"reply": "VERDICT: APPROVE\nHEAD: {HEAD}\n"}
CHANGES = {"reply": "VERDICT: CHANGES\nHEAD: {HEAD}\n\n1. Handle the empty case.\n"}
MERGED = merge.Result(True, False, "merged as abc", "abc")
BREACHES = (
    (EXISTING, "// Changed existing test.\n", "existing test file changed"),
    (LOCKED, NEW_TEST + "# Builder changed the locked test.\n", "locked test modified"),
    (PROTECTED, "changed policy\n", "protected path"),
)


class FlowLockCheckAfterBuilderTest(FakeClaudeGh):
    def project(self, rounds=2, allowed=()):
        work, _ = make_repo(self.tmp, {
            "loop.json": json.dumps({
                "Test command": "python3 " + LOCKED,
                "Loop branch": "loop/main",
                "Max rounds": rounds,
                "Protected paths": ["policy"],
            }),
            EXISTING: ORIGINAL,
            OTHER_EXISTING: ORIGINAL,
            PROTECTED: "original policy\n",
        })
        run_git(["push", "origin", "HEAD:loop/main"], work)
        body = ("Build the app.\n\n## Protected paths this issue may change\n\n"
                + "\n".join(allowed or ["none"]) + "\n")
        self.scenario([
            {"match": "issue view", "responses": [{"stdout": json.dumps({
                "title": "Build the app", "body": body, "comments": []})}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "issue comment", "responses": [{}]},
            {"match": "issue edit", "responses": [{}]},
            {"match": "issue close", "responses": [{}]},
            {"match": "pr edit", "responses": [{}]},
        ])
        return work

    def sessions(self, builders, reviewers=(APPROVE,)):
        self.claude({
            "test-writer": [{"files": {LOCKED: NEW_TEST}, "reply": "TESTS:\n" + LOCKED}],
            "builder": builders,
            "reviewer": list(reviewers),
        })

    def build(self, work):
        # Merging is a later gate; it must not hide an early diff-check failure.
        with mock.patch.object(merge, "merge", return_value=MERGED) as land, \
                mock.patch.object(merge, "find_pr", return_value={"number": 9}), \
                mock.patch.object(common, "park", wraps=common.park) as park:
            result = flow.build(7, work)
        return result, land, park

    def roles(self):
        return [call["role"] for call in self.claude_calls()]

    def test_builder_breaches_never_reach_review_even_with_a_cached_test_pass(self):
        for path, changed, _ in BREACHES:
            for cached in (False, True):
                with self.subTest(path=path, cached=cached):
                    work = self.project(rounds=1)
                    self.sessions([{"files": {"app.py": "1\n", path: changed}, "passed": cached}])
                    result, land, _ = self.build(work)
                    self.assertNotIn("reviewer", self.roles(),
                                     "A passing test run must not send a forbidden diff to review")
                    self.assertEqual(result.status, "parked", result.reason)
                    land.assert_not_called()

    def test_next_builder_receives_the_reason_path_and_revert_or_park_instruction(self):
        for path, changed, reason in BREACHES:
            with self.subTest(path=path):
                work = self.project()
                self.sessions([{"files": {"app.py": "1\n", path: changed}}, {}], [CHANGES])
                self.build(work)
                builders = [call for call in self.claude_calls() if call["role"] == "builder"]
                self.assertEqual(len(builders), 2)
                prompt = builders[1]["prompt"]
                self.assertIn(path, prompt, "The repair session needs the full offending path")
                self.assertIn(reason, prompt.lower())
                self.assertRegex(prompt.lower(), r"\brevert\b")
                self.assertRegex(prompt.lower(), r"\bpark\b")
                self.assertRegex(prompt.lower(), r"\bname\b.*\bpath\b")

    def test_last_breach_parks_with_a_question_that_can_grant_the_test_path(self):
        for path in (EXISTING, OTHER_EXISTING):
            with self.subTest(path=path):
                work = self.project()
                self.sessions([{"files": {"app.py": "1\n", path: "// Changed test.\n"}}, {}], [CHANGES])
                result, land, park = self.build(work)
                self.assertEqual(result.status, "parked", result.reason)
                park.assert_called_once()
                _, question, recommendation = park.call_args.args
                self.assertIn(path, question, "The permission question must name the full test path")
                self.assertTrue(question.rstrip().endswith("?"), question)
                text = ("## Needs you\n\n" + question + "\n\nRecommended: "
                        + recommendation + "\n\n" + common.MARKER)
                self.assertEqual(loop.parked_test_paths(text), ([path], "question"))
                self.assertEqual(self.roles(), ["test-writer", "builder", "builder"])
                land.assert_not_called()

    def test_reverting_a_breach_allows_review_in_the_next_round(self):
        work = self.project()
        self.sessions([
            {"files": {"app.py": "1\n", EXISTING: "// Changed test.\n"}},
            {"files": {EXISTING: ORIGINAL}},
        ])
        result, land, park = self.build(work)
        self.assertEqual(self.roles(), ["test-writer", "builder", "builder", "reviewer"])
        self.assertEqual(result.status, "merged", result.reason)
        land.assert_called_once()
        park.assert_not_called()

    def test_a_breach_introduced_by_a_review_fix_is_checked_before_another_review(self):
        work = self.project(rounds=3)
        self.sessions([
            {"files": {"app.py": "1\n"}},
            {"files": {EXISTING: "// Changed test in a fix.\n"}, "passed": True},
            {"files": {EXISTING: ORIGINAL}},
        ], [CHANGES, APPROVE])
        result, land, park = self.build(work)
        self.assertEqual(self.roles(), ["test-writer", "builder", "reviewer",
                                        "builder", "builder", "reviewer"])
        self.assertEqual(result.status, "merged", result.reason)
        land.assert_called_once()
        park.assert_not_called()

    def test_merge_diff_check_uses_the_loop_ref_permissions_and_lock_before_revert_check(self):
        work = self.project(allowed=[OTHER_EXISTING])
        self.sessions([{"files": {"app.py": "1\n"}}])
        real_check = merge.check_diff
        order = []

        def check(*args, **kwargs):
            order.append("diff")
            return real_check(*args, **kwargs)

        def reverted(*args, **kwargs):
            order.append("revert")
            return ""

        with mock.patch.object(merge, "check_diff", side_effect=check) as diff, \
                mock.patch.object(flow, "revert_check", side_effect=reverted):
            result, _, _ = self.build(work)
        self.assertEqual(result.status, "merged", result.reason)
        self.assertEqual(order, ["diff", "revert"], "The merge diff gate must run before the revert check")
        bound = inspect.signature(real_check).bind(*diff.call_args.args, **diff.call_args.kwargs).arguments
        self.assertEqual(bound["base"], "origin/loop/main")
        self.assertEqual(set(bound["allowed"]), {OTHER_EXISTING})
        self.assertEqual(set(bound["locked"]), {LOCKED})
        self.assertEqual(bound["protected"], ["policy"])

    def test_clean_and_explicitly_allowed_changes_still_start_the_reviewer(self):
        for path, changed in ((None, None),) + tuple((p, text) for p, text, _ in BREACHES):
            with self.subTest(path=path):
                work = self.project(allowed=[path] if path else [])
                files = {"app.py": "1\n"}
                if path:
                    files[path] = changed
                self.sessions([{"files": files}])
                result, land, park = self.build(work)
                self.assertEqual(result.status, "merged", result.reason)
                self.assertEqual(self.roles(), ["test-writer", "builder", "reviewer"])
                land.assert_called_once()
                park.assert_not_called()
