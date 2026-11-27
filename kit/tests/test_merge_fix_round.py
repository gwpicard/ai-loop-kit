"""Return merge test failures to the builder with their diagnostics and a separate limit."""
import json
from pathlib import Path
import re
import shlex
import sys
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git
import common
import flow
import merge


ALPHA = "tests/test_alpha.py"
BETA = "tests/test_beta.py"
NEW = "tests/test_new.py"
APPROVE = {"reply": "VERDICT: APPROVE\nHEAD: {HEAD}"}
CHANGES = {"reply": "VERDICT: CHANGES\nHEAD: {HEAD}\n\n1. Handle empty input."}
STOP = {"reply": "PARK: End of the fixture | No action needed."}


def failed(*names):
    return {"code": 1, "output": "\n".join(names) + "\nSome checks failed.\n"}


PASSED = {"code": 0, "output": "All checks passed.\n"}


class MergeFixRoundTest(FakeClaudeGh):
    def setUp(self):
        super().setUp()
        self.trace = Path(self.tmp, "commands.jsonl")
        self.plan = Path(self.tmp, "test-results.json")

    def arrange(self, *, full_every=1, files_command=True, max_rounds=2):
        self.trace.write_text("")
        runner = (
            "import json, subprocess, sys\n"
            "from pathlib import Path\n"
            "candidate = Path('candidate')\n"
            "branch = candidate.read_text().strip() if candidate.exists() else 'baseline'\n"
            "mode, files = sys.argv[1], sys.argv[2:]\n"
            "head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()\n"
            "with open(%r, 'a') as trace:\n"
            "    trace.write(json.dumps(dict(branch=branch, mode=mode, files=files, head=head)) + '\\n')\n"
            "if any(not Path(path).is_file() for path in files):\n"
            "    sys.exit('a selected test module is absent from this checkout')\n"
            "result = json.loads(Path(%r).read_text())[branch][mode]\n"
            "print(result['output'], end='', flush=True)\n"
            "sys.exit(result['code'])\n"
        ) % (str(self.trace), str(self.plan))
        command = shlex.quote(sys.executable) + " runner.py "
        self.settings = {
            "Test command": command + "full",
            "Test files command": command + "files {files}" if files_command else "",
            "Full suite every": full_every,
            "Max rounds": max_rounds,
        }
        self.work, _ = make_repo(self.tmp, {
            "loop.json": json.dumps(self.settings), "runner.py": runner,
            ALPHA: "# Existing test fixture.\n", BETA: "# Existing test fixture.\n",
        })
        run_git(["push", "origin", "HEAD:loop/main"], self.work)
        self.base = common.git(["rev-parse", "HEAD"], self.work)
        Path(self.work, "candidate").write_text("first\n")
        Path(self.work, NEW).write_text("# The issue's new test fixture.\n")
        run_git(["add", "candidate", NEW], self.work)
        run_git(["commit", "-m", "candidate fixture"], self.work)
        run_git(["push", "origin", "HEAD:issue/7"], self.work)
        self.head = common.git(["rev-parse", "HEAD"], self.work)
        info = {"title": "Return merge failures to the builder", "body": "Fix the regression.",
                "comments": [{"body": "TESTS:\n" + "\n".join((ALPHA, BETA, NEW)) + "\n"}]}
        self.scenario([
            {"match": "issue view 7", "responses": [{"stdout": json.dumps(info)}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "issue comment", "responses": [{}]},
            {"match": "issue edit", "responses": [{}]},
            {"match": "issue close", "responses": [{}]},
            {"match": "pr edit", "responses": [{}]},
        ])
        self.results(failed("FAIL: test_save (kit.tests.test_alpha.AlphaTest.test_save)",
                            "FAIL test_alpha 2 tests"))

    def results(self, candidate, *, baseline_files=PASSED, baseline_full=PASSED, **attempts):
        plan = {"first": {"full": candidate, "files": candidate},
                "baseline": {"full": baseline_full, "files": baseline_files}}
        plan.update({name: {"full": result, "files": result} for name, result in attempts.items()})
        self.plan.write_text(json.dumps(plan))

    def commands(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()]

    def merge_candidate(self):
        return merge.merge(7, "issue/7", "VERDICT: APPROVE\nHEAD: " + self.head, self.work)

    def build(self, builders, reviews=(APPROVE,)):
        self.claude({"builder": builders, "reviewer": list(reviews)})
        real_which = flow.session.shutil.which

        def which(name, *args, **kwargs):
            return None if name == "taskpolicy" else real_which(name, *args, **kwargs)

        # The API fake acknowledges a successful merge; all test gates remain real.
        # Fake agents need neither macOS priority control nor child discovery.
        with mock.patch.object(merge, "find_pr", return_value={
                "number": 9, "state": "MERGED", "mergeCommit": {"oid": "abc"}}), \
                mock.patch.object(flow.session, "reap", return_value=[]), \
                mock.patch.object(flow.session.shutil, "which", side_effect=which):
            return flow.build(7, self.work)

    def builders(self):
        return [call for call in self.claude_calls() if call["role"] == "builder"]

    def test_named_modules_are_checked_on_loop_head_after_targeted_or_full_failure(self):
        orders = (("test_beta", "test_new", "test_alpha"),
                  ("test_alpha", "test_beta", "test_new"))
        for full_every in (1, 4):
            for names in orders:
                with self.subTest(full_every=full_every, names=names):
                    self.arrange(full_every=full_every)
                    lines = ["FAIL %s 2 tests" % name for name in names]
                    self.results(failed(*lines), baseline_full=failed("FAIL test_unrelated 8 tests"))
                    result = self.merge_candidate()
                    commands = self.commands()
                    self.assertEqual(len(commands), 2,
                                     "every merge Test failure needs a baseline run")
                    self.assertEqual(commands[0]["mode"], "full" if full_every == 1 else "files")
                    self.assertEqual(commands[0]["head"], self.head)
                    self.assertCountEqual(commands[1]["files"], (ALPHA, BETA))
                    self.assertEqual({k: v for k, v in commands[1].items() if k != "files"}, {
                        "branch": "baseline", "mode": "files",
                        "head": self.base,
                    }, "rerun only named modules present on the loop branch, at its head")
                    self.assertFalse(result.ok)
                    self.assertFalse(result.park, result.reason)
                    self.assertEqual(result.rule, "test-command")

    def test_baseline_falls_back_to_full_without_module_names_or_a_files_command(self):
        for full_every, files_command, output in (
                (4, True, failed("compiler rejected the generated input")),
                (1, True, failed("compiler rejected the generated input")),
                (4, False, failed("FAIL test_alpha 2 tests"))):
            with self.subTest(full_every=full_every, files_command=files_command):
                self.arrange(full_every=full_every, files_command=files_command)
                self.results(output)
                result = self.merge_candidate()
                commands = self.commands()
                self.assertEqual(len(commands), 2, "a failure without selectable modules still needs a baseline")
                self.assertEqual(commands[1], {
                    "branch": "baseline", "mode": "full", "files": [], "head": self.base,
                })
                self.assertFalse(result.ok)
                self.assertFalse(result.park, result.reason)

    def test_fix_prompt_quotes_failures_and_hung_stacks_and_gives_targeted_rerun(self):
        self.arrange()
        lines = ["FAIL: test_save (kit.tests.test_alpha.AlphaTest.test_save)",
                 "FAIL test_alpha 2 tests", "FAIL test_beta 0 tests", "FAIL test_new 1 tests"]
        dump = ["test_beta: hung after 90 seconds",
                "test_wait (kit.tests.test_beta.BetaTest.test_wait) ...",
                "Thread 0x0000000000000001 (most recent call first):",
                '  File "tests/test_beta.py", line 17 in waiting_worker',
                "Current thread 0x0000000000000002 (most recent call first):",
                '  File "tests/test_beta.py", line 31 in test_wait']
        self.results(failed(*(lines + dump)))
        self.build([{"passed": True}, STOP])
        builders = self.builders()
        self.assertEqual(len(builders), 2, "the merge failure should resume the builder")
        self.assertIn("--resume", builders[1]["argv"])
        prompt = builders[1]["prompt"]
        for line in lines + dump:
            self.assertIn(line, prompt, "retain each failure and the complete hung-test stack")
        self.assertIn(".loop/logs/7-merge.log", prompt)
        for path in (ALPHA, BETA, NEW):
            self.assertIn(path, prompt)
        self.assertIn("Test files command", prompt)
        self.assertRegex(prompt.lower(), r"\b(?:re-?run|run)\b")
        self.assertIn(self.settings["Test files command"].split("{files}")[0].strip(), prompt,
                      "give the builder the configured targeted command")

    def test_fix_prompt_separates_shared_failures_from_the_builders_work(self):
        self.arrange()
        new = "FAIL: test_save (kit.tests.test_alpha.AlphaTest.test_save)"
        shared = "FAIL: test_old (kit.tests.test_beta.BetaTest.test_old)"
        self.results(failed(new, shared, "FAIL test_alpha 2 tests", "FAIL test_beta 3 tests"),
                     baseline_files=failed(shared, "FAIL test_beta 3 tests"),
                     baseline_full=failed(shared, "FAIL test_beta 3 tests"))
        self.build([{"passed": True}, STOP])
        builders = self.builders()
        self.assertEqual(len(builders), 2, "return the new failure while identifying the shared failure")
        prompt = builders[1]["prompt"]
        self.assertIn(new, prompt)
        self.assertIn(shared, prompt)
        self.assertIn(".loop/logs/7-merge.log", prompt)
        self.assertIn(".loop/logs/7-merge-baseline.log", prompt)
        shared_note = re.compile(r"(?is)(?:already|pre-existing|existing failure)"
                                 r".{0,400}" + re.escape(shared) + r"|" + re.escape(shared)
                                 + r".{0,400}(?:already|pre-existing|existing failure)")
        self.assertRegex(prompt, shared_note)
        self.assertRegex(prompt.lower(), r"not [^\n]*to fix|do not (?:fix|change|repair)|not responsible")

    def test_last_review_round_approval_still_allows_a_merge_test_fix(self):
        self.arrange(max_rounds=2)
        self.results(failed("FAIL: test_save (kit.tests.test_alpha.AlphaTest.test_save)",
                            "FAIL test_alpha 2 tests"), fixed=PASSED)
        result = self.build([
            {"passed": True},
            {"files": {"review_fix.py": "# Review fix fixture.\n"}, "passed": True},
            {"files": {"candidate": "fixed\n"}, "passed": True},
        ], reviews=(CHANGES, APPROVE, APPROVE))
        self.assertEqual(result.status, "merged", result.reason)
        builders = self.builders()
        self.assertEqual(len(builders), 3)
        self.assertIn("--resume", builders[-1]["argv"])
        self.assertIn("test_save", builders[-1]["prompt"])
        self.assertNotIn("did not pass review", result.reason)

    def test_two_failed_merge_fixes_park_with_the_last_tests_and_a_test_recommendation(self):
        self.arrange(max_rounds=5)
        latest = "FAIL: test_latest (kit.tests.test_beta.BetaTest.test_latest)"
        self.results(
            failed("FAIL: test_first (kit.tests.test_alpha.AlphaTest.test_first)", "FAIL test_alpha 2 tests"),
            second=failed("FAIL: test_second (kit.tests.test_alpha.AlphaTest.test_second)",
                          "FAIL test_alpha 2 tests"),
            third=failed(latest, "FAIL test_beta 3 tests"))
        with mock.patch.object(common, "park", wraps=common.park) as park:
            result = self.build([
                {"passed": True},
                {"files": {"candidate": "second\n"}, "passed": True},
                {"files": {"candidate": "third\n"}, "passed": True},
            ])
        builders = self.builders()
        self.assertEqual(len(builders), 3, "one initial build and exactly two merge test fix rounds")
        self.assertEqual(sum("--resume" in call["argv"] for call in builders), 2)
        self.assertEqual(len([call for call in self.commands() if call["branch"] != "baseline"]), 3)
        self.assertEqual(result.status, "parked", result.reason)
        park.assert_called_once()
        reason, recommendation = park.call_args.args[1:3]
        self.assertIn(latest, reason)
        self.assertIn(".loop/logs/7-merge.log", reason)
        self.assertRegex(reason.lower(), r"loop branch[^\n]*(?:pass|succeed)|(?:pass|succeed)[^\n]*loop branch")
        self.assertRegex(reason.lower(), r"(?:2|two)[^\n]*(?:fix|round)|(?:fix|round)[^\n]*(?:2|two)")
        self.assertNotIn("did not pass review", reason)
        self.assertRegex(recommendation.lower(), r"test|fail|fix|investigat|diagnos")
        self.assertNotIn("Name the path", recommendation)
        self.assertNotIn("protected path", recommendation.lower())
