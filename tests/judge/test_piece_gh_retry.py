# Intent: a run carries on through a passing GitHub fault and, when it does not pass, ends with one line and a next step.
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import Project

# isort: split

import network
import run
import run_cli
from loopkit import GitHub

ISSUE = {"number": 5, "title": "T", "body": "B", "labels": [{"name": "state:ready"}], "state": "OPEN"}
FAKE_GH = """#!{python}
import json, os, sys
d = os.environ["FAKE_GH_DIR"]
args = sys.argv[1:]
key = " ".join(args[:2])
with open(os.path.join(d, "calls.log"), "a") as f:
    f.write(key + "\\n")
with open(os.path.join(d, "calls.log")) as f:
    seen = [l.strip() for l in f].count(key) - 1
script = json.load(open(os.path.join(d, "script.json")))[key]
step = script[min(seen, len(script) - 1)]
sys.stdout.write(step.get("out", ""))
sys.stderr.write(step.get("err", ""))
sys.exit(step.get("rc", 0))
"""
OK = {"rc": 0, "out": json.dumps(ISSUE)}
HTML_504 = ('non-200 OK status code: 504 Gateway Timeout body: "<html>\\n<head><title>504</title></head>'
            '\\n<body>gateway</body>\\n</html>\\n"')


def fail(err):
    return {"rc": 1, "err": err}


def rate_limit_reply(seconds_away, remaining=0):
    reset = int(time.time()) + seconds_away
    core = {"limit": 5000, "remaining": remaining, "reset": reset}
    other = {"limit": 5000, "remaining": 4000, "reset": reset}
    return {"rc": 0, "out": json.dumps({"resources": {"core": core, "graphql": other}})}


class FakeGh(unittest.TestCase):
    """A fake `gh` on PATH that plays a scripted answer per command, and a recorded sleep."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        gh = self.dir / "gh"
        gh.write_text(FAKE_GH.format(python=sys.executable))
        gh.chmod(0o755)
        self.sleeps = []
        for patcher in (patch.dict(os.environ, {"PATH": f"{self.dir}:{os.environ['PATH']}",
                                                "FAKE_GH_DIR": str(self.dir)}),
                        patch.object(network, "sleep", self.sleeps.append, create=True)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.gh = GitHub(self.dir)

    def script(self, **by_key):
        self.script_map = {k.replace("_", " ", 1): v for k, v in by_key.items()}
        (self.dir / "script.json").write_text(json.dumps(self.script_map))

    def calls(self, key):
        log = self.dir / "calls.log"
        return log.read_text().split("\n").count(key) if log.exists() else 0

    def unavailable(self):
        error = getattr(network, "GitHubUnavailable", None)
        self.assertIsNotNone(error, "network.GitHubUnavailable must exist")
        return error


class RetryTest(FakeGh):
    def test_D1_a_read_that_fails_once_with_a_502_is_retried_and_named(self):
        self.script(issue_view=[fail("HTTP 502: Bad Gateway"), OK])
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            issue = self.gh.issue(5)
        self.assertEqual(issue["number"], 5)
        self.assertEqual(issue["labels"], ["state:ready"])
        self.assertEqual(self.calls("issue view"), 2)
        self.assertEqual(self.sleeps, [5])
        lines = [l for l in (out.getvalue() + err.getvalue()).splitlines() if "502" in l]
        self.assertEqual(len(lines), 1)
        self.assertIn("issue view", lines[0])

    def test_D1_the_delays_are_5_20_and_60_seconds(self):
        self.assertEqual(getattr(network, "RETRY_DELAYS", None), (5, 20, 60))

    def test_D2_transient_names_a_server_fault_in_both_forms(self):
        transient = getattr(network, "transient", None)
        self.assertIsNotNone(transient, "network.transient must exist")
        self.assertEqual(transient("HTTP 502: Bad Gateway"), "server")
        self.assertEqual(transient("non-200 OK status code: 504 Gateway Timeout body: x"), "server")
        self.assertEqual(transient("HTTP 404: Not Found"), "")
        self.assertEqual(transient("boom"), "")

    def test_D3_transient_names_a_rate_limit_for_403_and_429(self):
        transient = getattr(network, "transient", None)
        self.assertIsNotNone(transient, "network.transient must exist")
        self.assertEqual(transient("API rate limit exceeded (HTTP 403)"), "rate-limit")
        self.assertEqual(transient("HTTP 429: Too Many Requests"), "rate-limit")

    def test_D2_a_read_that_keeps_failing_raises_one_clean_line_after_three_retries(self):
        unavailable = self.unavailable()
        self.script(issue_view=[fail(HTML_504)])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with self.assertRaises(unavailable) as caught:
                self.gh.issue(5)
        self.assertEqual(self.sleeps, [5, 20, 60])
        self.assertEqual(self.calls("issue view"), 4)
        text = str(caught.exception)
        self.assertNotIn("\n", text)
        self.assertNotIn("<html", text)
        self.assertIn("issue view", text)
        self.assertIn("504", text)
        self.assertIsInstance(caught.exception, RuntimeError)

    def test_D2_every_listed_read_is_retried(self):
        for key, args in (("issue list", ("issue", "list", "--state", "open")),
                          ("pr view", ("pr", "view", "u")),
                          ("pr list", ("pr", "list", "--state", "open")),
                          ("label list", ("label", "list")),
                          ("repo view", ("repo", "view")),
                          ("api repos/o/n", ("api", "repos/o/n"))):
            with self.subTest(key):
                self.sleeps.clear()
                (self.dir / "calls.log").unlink(missing_ok=True)
                (self.dir / "script.json").write_text(
                    json.dumps({key: [fail("HTTP 502: Bad Gateway"), {"rc": 0, "out": "[]"}]}))
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    self.assertEqual(self.gh._gh(*args), "[]")
                self.assertEqual(self.calls(key), 2)

    def test_D3_a_rate_limit_with_a_near_reset_waits_for_it_and_retries_once(self):
        self.script(issue_view=[fail("API rate limit exceeded for user ID 1. (HTTP 403)"), OK],
                    api_rate_limit=[rate_limit_reply(600)])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            issue = self.gh.issue(5)
        self.assertEqual(issue["number"], 5)
        self.assertEqual(len(self.sleeps), 1)
        self.assertTrue(540 <= self.sleeps[0] <= 700, self.sleeps)
        self.assertEqual(self.calls("issue view"), 2)
        self.assertEqual(self.calls("api rate_limit"), 1)

    def test_D3_a_rate_limit_that_resets_in_two_hours_raises_at_once_naming_the_reset(self):
        unavailable = self.unavailable()
        self.script(issue_view=[fail("API rate limit exceeded for user ID 1. (HTTP 403)"), OK],
                    api_rate_limit=[rate_limit_reply(7200)])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with self.assertRaises(unavailable) as caught:
                self.gh.issue(5)
        self.assertEqual(self.sleeps, [])
        self.assertEqual(self.calls("issue view"), 1)
        self.assertNotIn("\n", str(caught.exception))
        self.assertIn("reset", str(caught.exception).lower())

    def test_D3_a_403_with_no_exhausted_resource_raises_as_today(self):
        unavailable = self.unavailable()
        self.script(issue_view=[fail("HTTP 403: Resource not accessible\nmore"), OK],
                    api_rate_limit=[rate_limit_reply(600, remaining=10)])
        with self.assertRaises(RuntimeError) as caught:
            self.gh.issue(5)
        self.assertNotIsInstance(caught.exception, unavailable)
        self.assertEqual(str(caught.exception),
                         "gh issue view 5 failed: HTTP 403: Resource not accessible")
        self.assertEqual(self.sleeps, [])
        self.assertEqual(self.calls("issue view"), 1)

    def test_D4_writes_that_are_not_safe_to_repeat_run_once(self):
        for key, args in (("issue comment", ("issue", "comment", "5", "--body", "x")),
                          ("pr create", ("pr", "create", "--base", "main", "--head", "h")),
                          ("pr merge", ("pr", "merge", "u", "--merge"))):
            with self.subTest(key):
                self.sleeps.clear()
                (self.dir / "calls.log").unlink(missing_ok=True)
                (self.dir / "script.json").write_text(
                    json.dumps({key: [fail("HTTP 502: Bad Gateway"), {"rc": 0, "out": "x"}]}))
                with self.assertRaises(RuntimeError) as caught:
                    self.gh._gh(*args)
                self.assertEqual(str(caught.exception),
                                 f"gh {' '.join(args[:3])} failed: HTTP 502: Bad Gateway")
                self.assertEqual(self.calls(key), 1)
                self.assertEqual(self.sleeps, [])

    def test_D4_an_issue_edit_that_sets_labels_is_retried(self):
        self.script(issue_edit=[fail("HTTP 502: Bad Gateway"), {"rc": 0, "out": "done"}])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(self.gh._gh("issue", "edit", "5", "--add-label", "state:ready"), "done")
        self.assertEqual(self.calls("issue edit"), 2)
        self.assertEqual(self.sleeps, [5])

    def test_D4_an_api_call_with_a_write_flag_runs_once(self):
        for flag in (("-X", "POST"), ("--method", "PUT"), ("-f", "a=b"), ("-F", "a=b")):
            with self.subTest(flag):
                self.sleeps.clear()
                (self.dir / "calls.log").unlink(missing_ok=True)
                (self.dir / "script.json").write_text(
                    json.dumps({"api repos/o/n": [fail("HTTP 502: Bad Gateway"), {"rc": 0, "out": "x"}]}))
                with self.assertRaises(RuntimeError):
                    self.gh._gh("api", "repos/o/n", *flag)
                self.assertEqual(self.calls("api repos/o/n"), 1)
                self.assertEqual(self.sleeps, [])

    def test_D6_a_404_or_sign_in_error_runs_once_and_keeps_its_first_line(self):
        for err, first in (("HTTP 404: Not Found\nmore text", "HTTP 404: Not Found"),
                           ("To get started with GitHub CLI, please run: gh auth login\nx",
                            "To get started with GitHub CLI, please run: gh auth login")):
            with self.subTest(first):
                self.sleeps.clear()
                (self.dir / "calls.log").unlink(missing_ok=True)
                self.script(issue_view=[fail(err), OK])
                with self.assertRaises(RuntimeError) as caught:
                    self.gh.issue(5)
                self.assertEqual(str(caught.exception), f"gh issue view 5 failed: {first}")
                self.assertEqual(self.calls("issue view"), 1)
                self.assertEqual(self.sleeps, [])


class RunEndsCleanTest(FakeGh):
    def test_D5_a_run_whose_ready_search_gets_504_refuses_with_a_next_step_and_no_traceback(self):
        self.script(issue_list=[fail(HTML_504)])
        p = Project()
        self.addCleanup(p.close)
        out, err = io.StringIO(), io.StringIO()
        with patch.object(run_cli, "repo_root", return_value=p.root), \
                patch.object(run_cli.signal, "signal"), \
                redirect_stdout(out), redirect_stderr(err):
            code = run.main(["--attended"])
        text = err.getvalue()
        self.assertEqual(code, 2)
        self.assertIn("refused: GitHub did not answer", text)
        self.assertIn("next: run again when GitHub answers", text)
        self.assertNotIn("Traceback", text + out.getvalue())
        self.assertNotIn("<html", text)
        self.assertEqual(self.sleeps, [5, 20, 60])


if __name__ == "__main__":
    unittest.main()
