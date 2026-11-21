"""Judge the revert check through a complete issue build with fake agents."""
import json
from pathlib import Path
import shlex
import sys
import unittest
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git, settings_json
import common
import flow
import merge


APPROVE = {"reply": "VERDICT: APPROVE\nHEAD: {HEAD}\n"}
CHANGES = {"reply": "VERDICT: CHANGES\nHEAD: {HEAD}\n1. Extend the test.\n"}
LOCKED = "tests/test_locked.py"
BUILDER = "tests/test_builder.py"
EXISTING = "tests/test_existing.py"


def test_source(assertion):
    return ("from pathlib import Path\nimport unittest\n\n"
            "class Behaviour(unittest.TestCase):\n"
            "    def test_behaviour(self):\n        " + assertion + "\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n")


SENSITIVE = test_source("self.assertEqual(Path('app.py').read_text(), 'new\\n')")
INSENSITIVE = test_source("self.assertTrue(Path('app.py').exists())")
TESTS_ONLY = test_source("self.assertTrue(Path('tests/test_builder.py').exists())")


class RevertCheckTest(FakeClaudeGh):
    def fixture(self, *, targeted=True, code=True, builder_tests=None,
                locked=SENSITIVE, rounds=False):
        self.command_log = Path(self.tmp, "commands.jsonl")
        runner = '''import json
from pathlib import Path
import subprocess
import sys

files = sys.argv[1:] or sorted(str(p) for p in Path('tests').glob('test_*.py'))
state = {p: Path(p).read_text() if Path(p).exists() else None
         for p in ('app.py', 'added.py', 'removed.py', 'untouched.py')}
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
with open(LOG, 'a') as stream:
    stream.write(json.dumps(dict(files=files, state=state, head=head,
                                cwd=str(Path.cwd()))) + '\\n')
failed = False
for path in files:
    failed = subprocess.run([sys.executable, path]).returncode != 0 or failed
sys.exit(int(failed))
'''.replace("LOG", repr(str(self.command_log)))
        command = shlex.quote(sys.executable) + " run_tests.py"
        agents = ("## Loop\nLoop branch: loop/main\nMax rounds: 2\n"
                  "Test command: " + command + "\n")
        if targeted:
            agents += "Test files command: " + command + " {files}\n"
        self.work, _ = make_repo(self.tmp, {
            "loop.json": settings_json(agents), "run_tests.py": runner,
            "app.py": "old\n", "removed.py": "restore me\n",
            "untouched.py": "keep me\n", EXISTING: INSENSITIVE,
        })
        run_git(["push", "origin", "main:loop/main"], self.work)
        self.base = common.git(["rev-parse", "HEAD"], cwd=self.work)
        self.scenario([
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "issue view", "responses": [{"stdout": json.dumps({
                "title": "Change app behaviour", "body": "Change app behaviour.",
                "comments": []})}]},
            *[{"match": cmd, "responses": [{}]} for cmd in
              ("issue comment", "issue edit", "issue create")],
        ])
        files = {"app.py": "new\n", "added.py": "new file\n"} if code else {}
        files.update(builder_tests or {})
        builder = {"files": files, "passed": True}
        if code:
            builder["remove"] = ["removed.py"]
        self.claude({
            "test-writer": [{"files": {LOCKED: locked},
                             "reply": "TESTS:\n" + LOCKED}],
            "builder": [builder, {"files": {BUILDER: SENSITIVE}, "passed": True}],
            "reviewer": [CHANGES, APPROVE] if rounds else [APPROVE],
        })
        self.before_reviews = []
        real_run = flow.session.run

        def run(role, *args, **kwargs):
            if role == "reviewer":
                self.before_reviews.append(self.runs())
            return real_run(role, *args, **kwargs)

        with mock.patch.object(merge, "merge", return_value=merge.Result(True, False, "merged", "abc")), \
                mock.patch.object(merge, "find_pr", return_value={"number": 9}), \
                mock.patch.object(flow.session, "run", side_effect=run):
            result = flow.build(7, self.work)
        self.assertEqual(result.status, "merged", result.reason)
        self.reviews = [c for c in self.claude_calls() if c["role"] == "reviewer"]

    def runs(self):
        return ([json.loads(line) for line in self.command_log.read_text().splitlines()]
                if self.command_log.exists() else [])

    def events(self):
        return [e for line in Path(self.work, ".loop/events.jsonl").read_text().splitlines()
                if (e := json.loads(line)).get("rule") == "revert-check"]

    def reverted(self, runs):
        return [r for r in runs if BUILDER in r["files"] and r["state"]["app.py"] == "old\n"]

    def assert_clean(self):
        for run in self.runs():
            self.assertFalse(Path(run["cwd"]).exists(), "a command's scratch worktree remains")
        trees = common.git(["worktree", "list", "--porcelain"], cwd=self.work)
        self.assertEqual(sum(line.startswith("worktree ") for line in trees.splitlines()), 1)

    def test_sensitive_test_runs_at_reviewed_head_with_only_non_tests_reverted(self):
        self.fixture(builder_tests={BUILDER: SENSITIVE})
        runs = self.reverted(self.before_reviews[0])
        self.assertTrue(runs, "no revert check ran before the review")
        head = common.git(["rev-parse", "origin/issue/7"], cwd=self.work)
        for run in runs:
            self.assertEqual(run["head"], head)
            self.assertNotEqual(run["head"], self.base)
            self.assertEqual(run["files"], [BUILDER])
            self.assertEqual(run["state"], {"app.py": "old\n", "added.py": None,
                                          "removed.py": "restore me\n", "untouched.py": "keep me\n"})
        self.assertNotIn("passes without the change: " + BUILDER, self.reviews[0]["prompt"])
        self.assertEqual([(e["outcome"], e["files"]) for e in self.events()],
                         [("passed", [BUILDER])])
        self.assert_clean()

    def test_passing_builder_tests_are_listed_including_a_changed_existing_file(self):
        self.fixture(builder_tests={BUILDER: INSENSITIVE, EXISTING: INSENSITIVE + "\n"})
        prompt = self.reviews[0]["prompt"]
        for path in (BUILDER, EXISTING):
            self.assertIn("passes without the change: " + path, prompt)
        self.assertNotIn("passes without the change: " + LOCKED, prompt)
        events = self.events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["outcome"], "listed")
        self.assertEqual(set(events[0]["files"]), {BUILDER, EXISTING})
        for run in self.reverted(self.before_reviews[0]):
            self.assertNotIn(LOCKED, run["files"])
        self.assert_clean()

    def test_each_review_round_gets_a_fresh_result_even_with_a_stop_hook_pass(self):
        self.fixture(builder_tests={BUILDER: INSENSITIVE}, rounds=True)
        self.assertEqual(len(self.reviews), 2)
        self.assertIn("passes without the change: " + BUILDER, self.reviews[0]["prompt"])
        self.assertNotIn("passes without the change: " + BUILDER, self.reviews[1]["prompt"])
        first = self.reverted(self.before_reviews[0])
        second = self.reverted(self.before_reviews[1])
        self.assertTrue(first, "the first review had no revert run")
        self.assertGreater(len(second), len(first), "the second review reused the first revert run")
        self.assertNotEqual(second[-1]["head"], first[-1]["head"])
        self.assertEqual([e["outcome"] for e in self.events()], ["listed", "passed"])
        self.assert_clean()

    def test_a_failing_builder_file_does_not_hide_one_that_passes(self):
        self.fixture(builder_tests={BUILDER: SENSITIVE, EXISTING: INSENSITIVE + "\n"})
        prompt = self.reviews[0]["prompt"]
        self.assertIn("passes without the change: " + EXISTING, prompt)
        self.assertNotIn("passes without the change: " + BUILDER, prompt)
        events = self.events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["outcome"], "listed")
        self.assertEqual(set(events[0]["files"]), {BUILDER, EXISTING})
        self.assert_clean()

    def test_no_test_files_command_skips_without_running_the_full_suite(self):
        self.fixture(targeted=False, builder_tests={BUILDER: INSENSITIVE})
        self.assertEqual(len(self.runs()), 1, "a revert check ran the full Test command")
        self.assertEqual([(e["outcome"], e["files"]) for e in self.events()], [("skipped", [])])
        self.assert_clean()

    def test_no_non_test_change_skips_the_revert_run(self):
        self.fixture(code=False, builder_tests={BUILDER: INSENSITIVE}, locked=TESTS_ONLY)
        self.assertEqual(len(self.runs()), 1)
        self.assertEqual([e["outcome"] for e in self.events()], ["skipped"])
        self.assertNotIn("passes without the change: ", self.reviews[0]["prompt"])
        self.assert_clean()

    def test_no_builder_test_skips_and_does_not_rerun_locked_tests(self):
        self.fixture()
        self.assertEqual(len(self.runs()), 1)
        self.assertEqual([(e["outcome"], e["files"]) for e in self.events()], [("skipped", [])])
        self.assert_clean()

    def test_reviewer_brief_makes_a_listed_test_blocking_unless_explained(self):
        brief = " ".join(Path(flow.BRIEFS, "reviewer.md").read_text().split())
        self.assertIn("passes without the change", brief)
        self.assertRegex(brief, r"(?i)(?:CHANGES.*DEVIATIONS|DEVIATIONS.*CHANGES)")
        self.assertRegex(brief, r"(?i)(?:already existed|existing behaviour|behaviour that existed)")
        self.assertNotIn("A test that cannot fail is not a CHANGES item", brief)


if __name__ == "__main__":
    unittest.main()
