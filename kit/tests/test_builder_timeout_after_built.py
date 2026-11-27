"""A timeout after committed work must not discard the builder's report."""
import contextlib
import json
import os
from pathlib import Path
import shlex
import sys
from unittest import mock

import common
import flow
import loop
import merge
import session
from kit.tests.helpers import FakeGh, HERE, make_repo, run_git, write_exe


STOP = str(Path(HERE, "../hooks/stop.py").resolve())
REPORTS = (
    "BUILT:\nCompleted the application.\nDEVIATIONS:\nnone\n",
    "Checks finished.\n\nDEVIATIONS:\nnone\n\nBUILT:\nCompleted the application.\n",
)
FAKE_AGENT = '''#!PYTHON
import json, os, subprocess, sys, time
from pathlib import Path

config = json.loads(Path(os.environ["TIMEOUT_SCENARIO"]).read_text())
role = os.environ["LOOP_ROLE"]
prompt = sys.stdin.read()
with open(config["calls"], "a") as log:
    log.write(json.dumps({"role": role, "prompt": prompt}) + "\\n")
agent = os.environ.get("LOOP_AGENT", "claude")
sid = "timeout-" + role
if role == "builder":
    if config.get("commit", True):
        Path("app.py").write_text("built\\n")
        subprocess.run(["git", "add", "app.py"], check=True)
        subprocess.run(["git", "commit", "-qm", "Complete application"], check=True)
    dirty = config.get("dirty")
    if dirty:
        Path("unfinished.txt" if dirty == "untracked" else "app.py").write_text("unfinished\\n")
        if dirty == "staged":
            subprocess.run(["git", "add", "app.py"], check=True)
    reply = config["report"]
else:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    reply = "VERDICT: APPROVE\\nHEAD: " + head + "\\nFOLLOW-UPS:\\n"
if agent == "codex":
    print(json.dumps({"type": "thread.started", "thread_id": sid}), flush=True)
    print(json.dumps({"type": "item.completed", "item": {
        "type": "agent_message", "text": reply}}), flush=True)
    # The final-message file may still be empty when the process is cut off.
    if role != "builder":
        Path(sys.argv[sys.argv.index("-o") + 1]).write_text(reply)
        print(json.dumps({"type": "turn.completed", "usage": {}}), flush=True)
else:
    print(json.dumps({"type": "result", "is_error": False,
                      "session_id": sid, "result": reply}), flush=True)
if role == "builder" and config.get("hook"):
    began = time.monotonic()
    stopped = subprocess.run([sys.executable, config["hook"]],
                             input=json.dumps({"session_id": sid}),
                             text=True, capture_output=True)
    Path(config["hook_result"]).write_text(json.dumps({
        "seconds": time.monotonic() - began, "code": stopped.returncode,
        "out": stopped.stdout, "err": stopped.stderr}))
elif role == "builder":
    time.sleep(300)
'''


class BuilderTimeoutAfterBuiltTest(FakeGh):
    def setUp(self):
        super().setUp()
        self.config_path = Path(self.tmp, "agent.json")
        os.environ["TIMEOUT_SCENARIO"] = str(self.config_path)
        for name in ("claude", "codex"):
            write_exe(str(Path(self.tmp, "bin", name)), FAKE_AGENT)
        self.config = {"calls": str(Path(self.tmp, "agent.calls")), "report": REPORTS[0]}
        self.configure()
        self.work, _ = make_repo(self.tmp, {
            ".gitignore": ".loop/\n",
            "loop.json": json.dumps({
                "Test command": "%s tests/test_saved.py" % shlex.quote(sys.executable),
                "Session minutes": 0.05,
            }),
            "app.py": "pending\n",
            "tests/test_saved.py": (
                "from pathlib import Path\n"
                "assert Path('app.py').read_text() == 'built\\n', 'Application is unfinished'\n"),
        })
        run_git(["push", "origin", "main:loop/main", "main:issue/7"], self.work)
        self.scenario([
            {"match": "issue view 7", "responses": [{"stdout": json.dumps({
                "title": "Finish application", "body": "Complete and review the application.",
                "comments": [{"body": "TESTS:\ntests/test_saved.py"}],
            })}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]},
            {"match": "issue comment", "responses": [{}]},
            {"match": "issue edit", "responses": [{}]},
        ])

    def configure(self, **changes):
        self.config.update(changes)
        self.config_path.write_text(json.dumps(self.config))

    def settings(self, **changes):
        path = Path(self.work, "loop.json")
        path.write_text(json.dumps(dict(json.loads(path.read_text()), **changes)))
        run_git(["commit", "-am", "Set session limits"], self.work)
        run_git(["push", "origin", "HEAD:loop/main", "HEAD:issue/7"], self.work)

    def calls_for(self):
        path = Path(self.config["calls"])
        return [json.loads(line) for line in path.read_text().splitlines()]

    def run_build(self, agent="claude"):
        if agent == "codex":
            self.settings(Builder="codex gpt-6", Reviewer="codex gpt-6")
        log = Path(self.work, ".loop/logs/build-7.log")
        log.parent.mkdir(parents=True, exist_ok=True)
        landed = merge.Result(True, False, "merged as abc", "abc")
        with mock.patch.object(merge, "merge", return_value=landed), \
                log.open("a") as output, contextlib.redirect_stdout(output):
            result = loop.build_attempts(self.work, 7, [])
        events = [json.loads(line) for line in
                  Path(self.work, ".loop/events.jsonl").read_text().splitlines()]
        return result, events, log.read_text()

    def assert_continued(self, agent):
        result, events, log = self.run_build(agent)
        self.assertIn("merged:", result,
                      "A clean, committed BUILT report must survive the session timeout: " + result)
        calls = self.calls_for()
        self.assertEqual([call["role"] for call in calls], ["builder", "reviewer"],
                         "The timeout must not consume a crash retry")
        reviewer = calls[-1]["prompt"]
        self.assertIn("Completed the application.", reviewer)
        self.assertIn("DEVIATIONS:\nnone", reviewer)
        starts = [e["step"] for e in events if e.get("phase") == "start"]
        self.assertLess(starts.index("tests"), starts.index("review"))
        self.assertTrue(any(e.get("step") == "tests" and e.get("outcome") == "passed"
                            for e in events), "The loop must run its own tests after the timeout")
        self.assertEqual([e for e in events if e["kind"] == "crashed"], [])
        self.assertFalse(any(e.get("outcome") == "crashed" for e in events))
        self.assertEqual(Path(common.build_file(self.work, 7, "attempt")).read_text(), "1")
        return log

    def test_claude_timeout_after_committed_built_runs_tests_and_review_without_retry(self):
        self.assert_continued("claude")

    def test_codex_timeout_recovers_built_from_events_without_a_final_message_file(self):
        self.configure(report=REPORTS[1])
        self.assert_continued("codex")

    def test_build_log_explains_that_timeout_after_built_continued(self):
        _, _, log = self.run_build()
        self.assertRegex(log, r"(?im)^.*timed out[^\n]*BUILT[^\n]*continu[^\n]*$",
                         "The build log must explain that the timeout after BUILT continued")

    def test_missing_report_dirty_tree_or_no_new_commit_still_times_out(self):
        cases = (
            {"report": "Checks finished.\n"},
            {"dirty": "tracked"},
            {"dirty": "staged"},
            {"dirty": "untracked"},
            {"commit": False},
        )
        for agent in ("claude", "codex"):
            for case in cases:
                with self.subTest(agent=agent, case=case):
                    self.configure(report=REPORTS[0], dirty=None, commit=True)
                    self.configure(**case)
                    start = common.git(["rev-parse", "HEAD"], cwd=self.work)
                    with self.assertRaises(session.SessionError) as error:
                        session.run("builder", "Finish application", self.work, "model", self.work,
                                    7, start=start, agent=agent)
                    self.assertIn("timed out", str(error.exception))
                    # Retain every commit and restore the fixture with a new commit.
                    Path(self.work, "app.py").write_text("pending\n")
                    unfinished = Path(self.work, "unfinished.txt")
                    if unfinished.exists():
                        unfinished.unlink()
                    run_git(["add", "-A"], self.work)
                    run_git(["commit", "--allow-empty", "-qm", "Reset application fixture"], self.work)
        self.assertTrue(all(call["role"] == "builder" for call in self.calls_for()))

    def check_hook_budget(self, minutes, slow_command):
        sleep = "%s -c %s" % (shlex.quote(sys.executable),
                                shlex.quote("import time; time.sleep(300)"))
        short_test = "%s -c %s" % (shlex.quote(sys.executable),
                                     shlex.quote("import time; time.sleep(2)"))
        self.settings(**{"Session minutes": minutes,
                         "Test command": sleep if slow_command == "Test" else short_test,
                         "Check command": sleep if slow_command == "Check" else "true"})
        result_file = Path(self.tmp, "hook-result.json")
        self.configure(hook=STOP, hook_result=str(result_file))
        start = common.git(["rev-parse", "HEAD"], cwd=self.work)
        wait_limited = common.wait_limited

        def cleanup_grace(wait, limit, project):
            # Only the enclosing session gets grace, so it cannot kill the hook
            # before the test observes whether the hook returned on its budget.
            return wait_limited(wait, limit + 3, project)

        with mock.patch.object(common, "wait_limited", side_effect=cleanup_grace):
            try:
                session.run("builder", "Finish application", self.work, "model", self.work,
                            7, start=start)
            except session.SessionError as error:
                self.assertIn("timed out", str(error))
        self.assertTrue(result_file.exists(),
                        "The Stop hook did not return within the session time left (%g seconds)"
                        % (minutes * 60))
        result = json.loads(result_file.read_text())
        self.assertEqual((result["code"], result["err"].strip()), (0, ""))
        self.assertLessEqual(result["seconds"], minutes * 60 + 1,
                             "Allow one second for process cleanup after the command limit")
        self.assertEqual(result["out"].strip(), "",
                         "A command capped by the session time left must allow the stop")
        self.assertFalse(Path(self.work, ".loop/passed-timeout-builder").exists(),
                         "A timed-out hook command must not be recorded as passed")

    def test_stop_allows_completion_with_two_minutes_left_and_a_five_minute_test(self):
        self.check_hook_budget(2, "Test")

    def test_stop_caps_the_check_command_at_the_session_time_left_too(self):
        self.check_hook_budget(0.05, "Check")
