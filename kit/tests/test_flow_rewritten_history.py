"""A build must park before trying to push rewritten remote history."""
import json
from pathlib import Path
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git
import common
import flow
import merge


class RewrittenHistoryTest(FakeClaudeGh):
    def test_rewritten_pushed_commit_parks_once_without_a_push(self):
        for role in ("builder", "reviewer"):
            with self.subTest(role=role):
                work, origin = make_repo(self.tmp, {"loop.json": json.dumps({
                    "Test command": "test ! -f tests/test_new.py || test -f app.py || "
                                    "{ echo AssertionError; false; }",
                    "Max rounds": 1,
                })})
                run_git(["push", "origin", "HEAD:loop/main"], work)
                self.scenario([
                    {"match": "issue view", "responses": [{"stdout": json.dumps({
                        "title": "Add an app", "body": "Build the app.", "comments": []})}]},
                    {"match": "pr list", "responses": [{"stdout": "[]"}]},
                    {"match": "issue comment", "responses": [{}]},
                    {"match": "issue edit", "responses": [{}]},
                ])
                self.claude({
                    "test-writer": [{"files": {"tests/test_new.py": "assert False\n"},
                                     "reply": "TESTS:\ntests/test_new.py"}],
                    "builder": [{"files": {"app.py": "print('hello')\n"}}],
                    "reviewer": [{"reply": "VERDICT: APPROVE\nHEAD: {HEAD}\n"}],
                })
                real_run, real_git = flow.session.run, common.git
                rewritten, missing, pushes = [], [], []

                def record_git(args, *args_rest, **kwargs):
                    if rewritten and args[0] == "push":
                        pushes.append(list(args))
                    return real_git(args, *args_rest, **kwargs)

                def rewrite(*args, **kwargs):
                    reply, sid = real_run(*args, **kwargs)
                    if role == "reviewer" and args[0] == "test-writer":
                        tree = self.claude_calls()[-1]["cwd"]
                        for message in ("Add a second test", "Add a third test"):
                            commit = real_git([
                                "commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", message,
                            ], cwd=tree)
                            run_git(["update-ref", "HEAD", commit], tree)
                    if self.claude_calls()[-1]["role"] == role:
                        tree = self.claude_calls()[-1]["cwd"]
                        old = real_git(["rev-parse", "HEAD"], cwd=tree)
                        remote = real_git(["rev-parse", "origin/issue/7"], cwd=tree)
                        missing.extend(real_git([
                            "rev-list", "origin/loop/main.." + remote,
                        ], cwd=tree).splitlines())
                        # Replace the pushed test commit and its descendants with
                        # a new commit containing the same files, as a script could.
                        replacement = real_git([
                            "commit-tree", "HEAD^{tree}", "-p", "origin/loop/main",
                            "-m", "Reword earlier commits",
                        ], cwd=tree)
                        run_git(["update-ref", "HEAD", replacement, old], tree)
                        self.assertEqual(real_git([
                            "rev-list", "HEAD..origin/issue/7"], cwd=tree).splitlines(), missing)
                        rewritten.append(replacement)
                        reply = reply.replace(old, replacement)
                    return reply, sid

                with mock.patch.object(flow.session, "run", side_effect=rewrite), \
                        mock.patch.object(common, "git", side_effect=record_git) as git, \
                        mock.patch.object(flow, "git", git), \
                        mock.patch.object(common, "park", wraps=common.park) as park, \
                        mock.patch.object(merge, "merge") as land:
                    result = flow.build(7, work)
                self.assertTrue(rewritten, "the fixture must rewrite a pushed commit")
                self.assertEqual(result.status, "parked", result.reason)
                self.assertRegex(result.reason.lower(), r"history.{0,60}rewrit|rewrit.{0,60}history")
                for commit in missing:
                    self.assertIn(commit[:7], result.reason)
                self.assertEqual(pushes, [], "history must be checked before any push")
                park.assert_called_once()
                land.assert_not_called()
                self.assertEqual(real_git(["rev-parse", "refs/heads/issue/7"], cwd=origin), missing[0])
                events = [json.loads(line) for line in
                          Path(work, ".loop/events.jsonl").read_text().splitlines()]
                parks = [event for event in events if event["kind"] == "parked"]
                self.assertEqual(len(parks), 1)
                for commit in missing:
                    self.assertIn(commit[:7], parks[0]["reason"])
