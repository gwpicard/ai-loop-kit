"""Permission for a tracked test also covers its case-insensitive lock alias."""
import json
from pathlib import Path
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git
import common
import flow
import merge


TRACKED = "Tests/test_feature.py"
LOCKED = "tests/test_feature.py"
TEST = ("from pathlib import Path\n"
        "assert Path('app.py').is_file(), 'The app has not been built'\n")


class AllowedLockPathCaseTest(FakeClaudeGh):
    def test_permission_for_the_tracked_path_allows_review_with_an_aliased_lock(self):
        for baseline in (True, False):
            with self.subTest(baseline=baseline):
                work, _ = make_repo(self.tmp, {
                    "loop.json": json.dumps({
                        "Test command": "python3 " + TRACKED,
                        "Loop branch": "loop/main",
                        "Max rounds": 1,
                    }),
                })
                run_git(["config", "core.ignorecase", "true"], work)
                run_git(["push", "origin", "HEAD:loop/main"], work)
                test = Path(work, TRACKED)
                test.parent.mkdir()
                test.write_text(TEST)
                run_git(["add", TRACKED], work)
                run_git(["commit", "-m", "Write the acceptance test"], work)
                writer = common.git(["rev-parse", "HEAD"], cwd=work)
                run_git(["push", "origin", "HEAD:issue/7"], work)
                lock = ("TESTS:\n" + LOCKED + "\n\n"
                        + ("Commit: " + writer + "\n\n" if baseline else "")
                        + common.MARKER)
                self.scenario([
                    {"match": "issue view", "responses": [{"stdout": json.dumps({
                        "title": "Build the app",
                        "body": ("Build the app.\n\n## Protected paths this issue may change\n\n"
                                 + TRACKED + "\n"),
                        "comments": [{"body": lock}],
                    })}]},
                    {"match": "pr list", "responses": [{"stdout": "[]"}]},
                    *[{"match": command, "responses": [{}]} for command in
                      ("issue comment", "issue edit", "issue close", "pr edit")],
                ])
                self.claude({
                    "builder": [{"files": {"app.py": "pass\n",
                                           TRACKED: TEST + "# Authorised test change.\n"}}],
                    "reviewer": [{"reply": "VERDICT: APPROVE\nHEAD: {HEAD}\n"}],
                })
                with mock.patch.object(merge, "merge", return_value=merge.Result(
                        True, False, "merged", "abc")) as land, \
                        mock.patch.object(merge, "find_pr", return_value={"number": 9}), \
                        mock.patch.object(common, "park", wraps=common.park) as park:
                    result = flow.build(7, work)
                self.assertEqual(result.status, "merged", result.reason)
                self.assertEqual([call["role"] for call in self.claude_calls()],
                                 ["builder", "reviewer"])
                land.assert_called_once()
                park.assert_not_called()
