"""Keep merge failures available through the worker's log and park comment."""
import contextlib
import json
from pathlib import Path
import re
import shlex
import sys
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git
import common
import merge
import worker


class MergeFailureReportsTest(FakeClaudeGh):
    def setUp(self):
        super().setUp()
        self.issue_output = Path(self.tmp, "issue-output")
        self.baseline_output = Path(self.tmp, "baseline-output")
        runner = (
            "from pathlib import Path\nimport sys\n"
            "source = %r if Path('candidate').exists() else %r\n"
            "sys.stdout.write(Path(source).read_text()); sys.stdout.flush()\n"
            "print('stderr diagnostic', file=sys.stderr)\n"
            "print('Some checks failed.', flush=True)\n"
            "sys.exit(1)\n"
        ) % (str(self.issue_output), str(self.baseline_output))
        self.work, _ = make_repo(self.tmp, {
            "loop.json": json.dumps({
                "Test command": shlex.quote(sys.executable) + " runner.py",
                "Test files command": "true {files}",
                "Full suite every": 1,
            }),
            "runner.py": runner,
            "tests/test_locked.py": "# The issue's locked test fixture.\n",
        })
        run_git(["push", "origin", "HEAD:loop/main"], self.work)
        Path(self.work, "candidate").write_text("issue branch\n")
        run_git(["add", "candidate"], self.work)
        run_git(["commit", "-m", "candidate fixture"], self.work)
        run_git(["push", "origin", "HEAD:issue/7"], self.work)
        self.sha = common.git(["rev-parse", "HEAD"], self.work)
        self.logs = Path(self.work, ".loop/logs")
        self.logs.mkdir(parents=True)

    def run_worker(self, candidate, baseline=None):
        self.issue_output.write_text(candidate)
        self.baseline_output.write_text(candidate if baseline is None else baseline)
        info = {"title": "Retain merge failures", "body": "Add diagnostics.",
                "comments": [{"body": "TESTS:\ntests/test_locked.py\n"}]}
        self.scenario([
            {"match": "issue view 7", "responses": [{"stdout": json.dumps(info)}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "issue comment", "responses": [{}]},
            {"match": "issue edit", "responses": [{}]},
        ])
        self.claude({
            "builder": [{"passed": True}],
            "reviewer": [{"reply": "VERDICT: APPROVE\nHEAD: {HEAD}"}],
        })
        comments, refusals = [], []
        real_gh, real_merge = common.gh, merge.merge

        def record_comment(args, **kwargs):
            if args[:2] == ["issue", "comment"]:
                comments.append(kwargs.get("input", ""))
            return real_gh(args, **kwargs)

        def record_merge(*args, **kwargs):
            result = real_merge(*args, **kwargs)
            refusals.append(result)
            return result

        build_log = self.logs / "build-7.log"
        with build_log.open("w") as output, contextlib.redirect_stdout(output), \
                mock.patch.object(common, "gh", side_effect=record_comment), \
                mock.patch.object(merge, "merge", side_effect=record_merge):
            self.assertEqual(worker.main([self.work, "7", "[]"]), 0)
        self.assertEqual(len(refusals), 1, build_log.read_text())
        refusal = refusals[0]
        self.assertEqual((refusal.ok, refusal.park, refusal.rule),
                         (False, True, "test-command"), refusal.reason)
        self.assertEqual(refusal.reason.splitlines()[0],
                         "the Test command failed on %s: Some checks failed." % self.sha[:10])
        parks = [text for text in comments if text.startswith("## Needs you")]
        self.assertEqual(len(parks), 1, comments)
        self.assertFalse(any(call[:2] == ["pr", "merge"] for call in self.calls()))
        return parks[0], build_log.read_text()

    def assert_reports_contain(self, reports, *lines):
        for destination, report in zip(("park comment", "build log"), reports):
            with self.subTest(destination=destination):
                for line in lines:
                    self.assertIn(line, report)

    def test_full_output_from_both_branches_replaces_each_attempts_logs(self):
        paths = (self.logs / "7-merge.log", self.logs / "7-merge-baseline.log")
        for path in paths:
            path.write_text("stale output from an earlier attempt\n")
        for attempt in ("first", "second"):
            candidate = "%s issue prelude\nFAIL: test_candidate\ntraceback café\n" % attempt
            baseline = "%s baseline prelude\nERROR: test_baseline\ntraceback details\n" % attempt
            self.run_worker(candidate, baseline)
            for path, expected in zip(paths, (candidate, baseline)):
                with self.subTest(attempt=attempt, path=path.name):
                    text = path.read_text()
                    self.assertIn(expected, text)
                    self.assertIn("stderr diagnostic\nSome checks failed.\n", text)
                    self.assertNotIn("stale output", text)
                    if attempt == "second":
                        self.assertNotIn("first ", text)

    def test_park_and_build_log_quote_failure_headers_and_module_summaries(self):
        examples = (
            ["FAIL: test_save (tests.Storage)", "ERROR: test_load (tests.Storage)",
             "FAIL test_storage 12 tests"],
            ["FAIL test_network 8 tests", "ERROR: test_connect (tests.Network)",
             "FAIL: test_disconnect (tests.Network)"],
        )
        for failures in examples:
            with self.subTest(failures=failures):
                output = "ordinary progress\n" + "\n".join(failures) + "\n" + "ok progress\n" * 80
                reports = self.run_worker(output)
                self.assert_reports_contain(reports, ".loop/logs/7-merge.log",
                                            ".loop/logs/7-merge-baseline.log", *failures)
                for report in reports:
                    self.assertNotIn("ok progress", report,
                                     "recognised failure lines should take precedence over the tail")

    def test_park_and_build_log_use_the_tail_without_recognised_failure_lines(self):
        for tail in (("compiler could not open input", "missing source file"),
                     ("connection refused", "service unavailable")):
            with self.subTest(tail=tail):
                reports = self.run_worker("old progress\n" * 80 + "\n".join(tail) + "\n")
                self.assert_reports_contain(reports, ".loop/logs/7-merge.log",
                                            ".loop/logs/7-merge-baseline.log", *tail,
                                            "stderr diagnostic", "Some checks failed.")
                for report in reports:
                    self.assertNotIn("old progress", report, "the fallback must have a bounded tail")

    def test_matching_failure_sets_are_identified_despite_order_and_progress_changes(self):
        failures = ["FAIL: test_save (tests.Storage)", "ERROR: test_load (tests.Storage)"]
        reports = self.run_worker("issue progress\n" + "\n".join(failures) + "\n",
                                  "baseline progress\n" + "\n".join(reversed(failures)) + "\n")
        self.assert_reports_contain(reports, *failures)
        for report in reports:
            self.assertRegex(report.lower(), r"same[^\n]*(?:fail|test)|(?:fail|test)[^\n]*same",
                             "the report must say that both branches have the same failing tests")

    def test_different_failure_sets_are_listed_for_each_branch(self):
        issue_failure = "FAIL: test_candidate (tests.Feature)"
        baseline_failure = "ERROR: test_existing (tests.Legacy)"
        reports = self.run_worker(issue_failure + "\n", baseline_failure + "\n")
        self.assert_reports_contain(reports, issue_failure, baseline_failure,
                                    ".loop/logs/7-merge.log", ".loop/logs/7-merge-baseline.log")
        for report in reports:
            self.assertRegex(report, r"(?is)(?:issue branch|reviewed|7-merge\.log).*?"
                             + re.escape(issue_failure), "identify the issue branch's failures")
            self.assertRegex(report, r"(?is)(?:loop branch|baseline|7-merge-baseline\.log).*?"
                             + re.escape(baseline_failure), "identify the loop branch's failures")

    def test_failure_excerpt_is_bounded_while_saved_output_is_complete(self):
        failures = ["FAIL: test_case_%03d (tests.Many)" % index for index in range(200)]
        reports = self.run_worker("\n".join(failures) + "\n")
        for report in reports:
            quoted = set(re.findall(r"FAIL: test_case_\d+ \(tests.Many\)", report))
            self.assertGreater(len(quoted), 0, "quote failures instead of only the final summary")
            self.assertLess(len(quoted), len(failures), "cap the excerpt and retain the full log")
        for name in ("7-merge.log", "7-merge-baseline.log"):
            path = self.logs / name
            self.assertTrue(path.is_file(), "save the complete output at " + str(path))
            for line in failures:
                self.assertIn(line, path.read_text())
