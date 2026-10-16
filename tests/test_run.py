"""End-to-end checks for the run loop."""
from __future__ import annotations

import json
import os
import signal
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import gate
import run
import run_helpers
from helpers import GOOD_CODE, KIT, SPEC, git, pump_events
from loopkit import Refused, records, run_judge
from run_helpers import FAKE_CLAUDE as FAKE_CLAUDE


class RunTest(run_helpers.RunCase):
    def test_setup_and_writer_briefs_cover_rehearsal_rules(self):
        setup = (KIT / "skills" / "setup" / "SKILL.md").read_text()
        builder = (KIT / "briefs" / "builder.md").read_text()
        judge_writer = (KIT / "agents" / "judge-writer.md").read_text()
        standards_reviewer = (KIT / "briefs" / "standards-reviewer.md").read_text()
        self.assertIn("standards file", setup)
        self.assertIn("Protected paths", setup)
        self.assertIn("testpaths", setup)
        self.assertNotIn("paths_to_mutate", setup)
        self.assertIn("CRAP", builder)
        self.assertIn("simple commands", builder)
        self.assertIn("new test files", builder)
        self.assertIn(".loop/outcome", builder)
        self.assertIn("IDs unique", judge_writer)
        self.assertIn("rename stale tests", judge_writer)
        self.assertIn("non-test project code", standards_reviewer)

    def test_activity_stamp_skips_generated_build_directories(self):
        import review
        root = Path(self.p.tmp.name) / "activity"
        generated = root / "build" / "large"
        generated.mkdir(parents=True)
        (generated / "output.bin").write_text("x")
        before = review._folder_activity_stamp(root)
        future = time.time() + 10
        os.utime(generated / "output.bin", (future, future))
        self.assertEqual(review._folder_activity_stamp(root), before)

    def test_activity_stamp_is_polled_at_most_twice_per_second(self):
        import review
        script = Path(self.p.tmp.name) / "activity-child.py"
        script.write_text("import time; time.sleep(.55); print('done', flush=True)\n")
        proc = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True)
        with patch.object(review, "_folder_activity_stamp", wraps=review._folder_activity_stamp) as stamp:
            with (Path(self.p.tmp.name) / "activity.log").open("w") as output:
                review._pump_session(proc, output, 2, hard_seconds=5,
                                     activity_path=Path(self.p.tmp.name))
        self.assertLessEqual(stamp.call_count, 2)

    def test_claude_result_errors_are_logged(self):
        from io import StringIO

        import review
        output = StringIO()
        review._write_claude_log_line(
            output, '{"type":"result","is_error":true,"result":"rate limited"}')
        self.assertIn("rate limited", output.getvalue())

    def test_ready_search_retries_brief_github_label_lag(self):
        from unittest.mock import Mock
        gh = Mock()
        ready = [{"number": 12}]
        gh.issues_with_label.side_effect = [[], [], ready]
        with patch.object(run.time, "sleep") as sleep:
            self.assertEqual(run.ready_pieces(gh), [12])
        self.assertEqual(gh.issues_with_label.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_standard_citation_must_be_a_whole_rule_or_known_smell(self):
        diff = "diff --git a/app.js b/app.js\n+++ b/app.js\n@@ -0,0 +1 @@\n+x\n"
        verdict = ('<verdict>{"findings":[{"rule":"clear names","hunk":"app.js:1",'
                   '"finding":"ok"},{"rule":"names","hunk":"app.js:1",'
                   '"finding":"substring only"},{"rule":"", "hunk":"app.js:1",'
                   '"finding":"empty"}],"follow_ups":[],"changes":"none"}</verdict>')
        from review import parse_standards_findings
        self.assertEqual(parse_standards_findings(
            verdict, "clear names\n", diff), ["clear names at app.js:1: ok"])
        heading = ('<verdict>{"findings":[{"rule":"# Style","hunk":"app.js:1",'
                   '"finding":"heading citation"}],"follow_ups":[],"changes":"none"}</verdict>')
        self.assertEqual(parse_standards_findings(heading, "# Style\nclear names\n", diff),
                         ["# Style at app.js:1: heading citation"])

    def test_claude_events_reset_idle_and_logs_keep_assistant_text(self):
        import review
        events = [json.dumps({"type": "assistant", "message": {
            "content": [{"type": "text", "text": "hello"}]}}) for _ in range(5)]
        status, output = pump_events(review, events, idle_seconds=2, clock_step=.75)
        self.assertEqual(status, "")
        self.assertEqual(output.count("hello"), 5)
        self.assertNotIn('"type":"assistant"', output)

    def test_pump_stops_group_when_child_keeps_pipe_open_after_parent_exits(self):
        script = ("import subprocess,sys; "
                  "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
                  "print('parent finished', flush=True)")
        proc = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True)
        def cleanup_group():
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            if proc.stdout:
                proc.stdout.close()
        self.addCleanup(cleanup_group)
        from io import StringIO

        from review import _pump_session
        output = StringIO()
        finished = threading.Event()
        errors = []

        def pump():
            try:
                _pump_session(proc, output, idle_seconds=30, hard_seconds=40)
            except BaseException as error:
                errors.append(error)
            finally:
                finished.set()

        started = time.monotonic()
        worker = threading.Thread(target=pump)
        worker.start()
        finished_promptly = finished.wait(5)
        if not finished_promptly:
            os.killpg(proc.pid, signal.SIGKILL)
            worker.join(3)
        self.assertTrue(finished_promptly, "the output pipe stayed open after the child exit")
        self.assertEqual(errors, [])
        self.assertLess(time.monotonic() - started, 5)
        self.assertIn("parent finished", output.getvalue())

    def test_all_claude_sessions_request_stream_json(self):
        fake = Path(self.p.tmp.name) / "argv-claude"
        fake.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\"\n")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        os.environ["LOOP_CLAUDE"] = str(fake)
        logfile = Path(self.p.tmp.name) / "session.log"
        run.build_once(self.p.root, "brief", [], logfile)
        self.assertIn("--output-format stream-json --verbose", logfile.read_text())

    def test_last_tagged_verdict_accepts_a_code_fence_and_checks_fields(self):
        output = ('<verdict>{"findings":[],"follow_ups":[],"changes":"old"}</verdict>\n'
                  '<verdict>```json\n{"findings":[],"follow_ups":[],"changes":"none"}\n```</verdict>')
        from review import _last_verdict
        self.assertEqual(_last_verdict(output, "standards")["changes"], "none")
        with self.assertRaises(ValueError):
            _last_verdict("<verdict>{bad}</verdict>", "contract")

    def test_missing_judge_writer_verdict_file_prints_next_step(self):
        from contextlib import redirect_stderr
        from io import StringIO

        missing = Path(self.p.tmp.name) / "missing-verdict.txt"
        errors = StringIO()
        with redirect_stderr(errors):
            status = run.main(["--verdict-kind", "judge-writer",
                               "--verdict-file", str(missing)])
        self.assertEqual(status, 2)
        self.assertIn("next:", errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())

    def test_run_lock_refuses_live_runs_and_takes_over_dead_ones(self):
        lock = run.acquire_lock(self.p.root)
        with self.assertRaises(Refused) as r:
            run.acquire_lock(self.p.root)
        self.assertIn("another run is live", r.exception.reason)
        run.release_lock(lock)
        lock.write_text('{"pid": 2147483647, "started_at": 0}\n')
        taken = run.acquire_lock(self.p.root)
        self.assertEqual(taken, lock)
        run.release_lock(taken)

    def test_run_recovers_building_pieces_to_shaping(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        gate.move(self.p.gh, self.p.root, n, "building")
        recovered = run.recover_building(self.p.gh, self.p.root)
        self.assertIn(f"piece {n}", recovered[0])
        record = records(self.p.gh.comments(n))[-1]
        self.assert_handback_record(record, reason_type="environment", cause="other",
                                    attempts=0, seconds_positive=False)
        self.assertIn("state:shaping", self.p.gh.issue(n)["labels"])

    def test_crash_recovery_records_persisted_attempts_and_elapsed_time(self):
        self.p.loop_section("true")
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        with patch("run.build_once", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                run.build_piece(self.p.gh, self.p.root, n, attempts=2)

        saved = run._run_metrics_path(self.p.root, n)
        self.assertTrue(saved.is_file())
        self.assertEqual(json.loads(saved.read_text())["attempts"], 1)
        recovered = run.recover_building(self.p.gh, self.p.root)
        self.assertIn(f"piece {n}", recovered[0])
        handback = records(self.p.gh.comments(n))[-1]
        self.assert_handback_record(handback, reason_type="environment", cause="other",
                                    attempts=1)
        self.assertFalse(saved.exists())

    def test_judge_timeout_returns_a_clear_failure(self):
        code, output = run_judge(self.p.root, "sleep 2", timeout=0.1)
        self.assertEqual(code, 124)
        self.assertIn("past 0.1 seconds", output)

    def test_quality_outputs_are_recorded_and_removed_between_attempts(self):
        folder = self.p.root
        (folder / "mutants" / "cache").mkdir(parents=True)
        (folder / "mutants" / "cache" / "result.bin").write_text("generated")
        (folder / ".stryker-tmp" / "out").mkdir(parents=True)
        (folder / ".stryker-tmp" / "out" / "result.json").write_text("generated")
        (folder / "coverage.json").write_text("{}")
        (folder / ".coverage.worker").write_text("coverage")
        recorded = run.record_quality_outputs(folder)
        self.assertGreaterEqual(len(recorded), 5)
        run.clean_quality_outputs(folder, recorded)
        self.assertFalse((folder / "mutants").exists())
        self.assertFalse((folder / ".stryker-tmp").exists())
        self.assertFalse((folder / "coverage.json").exists())
        self.assertFalse((folder / ".coverage.worker").exists())

    def test_quality_commands_run_and_their_output_reaches_the_pull_request(self):
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Quality: printf quality-check-ok\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Add quality command")
        git(self.p.root, "push", "--quiet", "origin", "main")
        n, result = self.build("good", attempts=1)
        self.assertIn("pull request ready", result)
        body = self.p.gh.prs[f"piece/{n}"]["body"]
        self.assertIn("Quality: printf quality-check-ok", body)
        self.assertIn("quality-check-ok", body)

    def test_quality_failure_returns_the_piece_with_output(self):
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Quality: printf quality-failed; exit 3\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Add failing quality command")
        git(self.p.root, "push", "--quiet", "origin", "main")
        n, result = self.build("good", attempts=1)
        self.assertIn("back to shaping", result)
        comments = self.p.gh.comments(n)
        self.assertTrue(any("quality-failed" in comment for comment in comments))
        self.assertEqual(self.p.gh.prs, {})
        handback = [r for r in records(comments) if r.get("move") == "give-back"][-1]
        self.assert_handback_record(handback, reason_type="environment",
                                    cause="quality-failed", attempts=1)
        self.assertIn("Quality check also fails on main", handback["reason"])

    def test_both_reviewers_run_without_a_project_standards_file(self):
        n, result = self.build("good", attempts=1)
        self.assertIn("pull request ready", result)
        logs = self.p.root / ".loop" / "logs"
        self.assertTrue((logs / f"piece-{n}-standards-review.log").is_file())
        self.assertTrue((logs / f"piece-{n}-contract-review.log").is_file())

    def test_pull_request_contains_facts_evidence_and_the_builder_reason(self):
        n, result = self.build("good", attempts=1)
        self.assertIn("pull request ready", result)
        body = self.p.gh.prs[f"piece/{n}"]["body"]
        for part in ("## What changed", "## Risk", "## Evidence", "Bar hash:",
                     "Judged commit:", "Judge, Keep and Quality output", "judge_add.py",
                     "This change lets the user add a habit.", "A typo could save a duplicate."):
            self.assertIn(part, body)
        self.assertIn("Tests added:", body)

    def test_import_scan_finds_python_dependants_for_approach(self):
        (self.p.root / "consumer.py").write_text("import habits\n")
        (self.p.root / "habits.py").write_text("def add(): pass\n")
        self.assertEqual(run.dependent_files(self.p.root, "Change `habits.py`", ["habits.py"]),
                         ["consumer.py"])
        ready = {"files": ["judge_add.py"], "approach": "Change `habits.py`",
                 "command": "python3 judge_add.py"}
        prompt = run.brief(1, SPEC, ready, "", folder=self.p.root)
        self.assertIn("Code that depends on what you change", prompt)
        self.assertIn("`consumer.py`", prompt)

    def test_pull_request_risk_names_files_over_one_thousand_lines(self):
        n = self.p.piece(spec=SPEC + "Large file: generated.txt\n")
        gate.move(self.p.gh, self.p.root, n, "ready")
        folder = run.worktree(self.p.root, n)
        (folder / "habits.py").write_text(GOOD_CODE)
        (folder / "generated.txt").write_text("line\n" * 1001)
        git(folder, "add", "habits.py", "generated.txt")
        git(folder, "commit", "--quiet", "-m", "Add large file")
        ready = gate.last_record(self.p.gh.comments(n), "ready")
        passed, output = gate.judge(folder, ready)
        self.assertTrue(passed, output)
        facts, _ = run.pull_request_facts(folder, ready, output)
        self.assertIn("files over 1,000 lines: `generated.txt` (1001 lines)", facts)

    def test_waiting_limit_pauses_with_a_next_step(self):
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Waiting limit: 2\nIdle limit: 2\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Set waiting limit")
        git(self.p.root, "push", "--quiet", "origin", "main")
        for _ in range(2):
            n = self.p.piece()
            self.p.gh.issues[n]["labels"] = ["state:approval"]
        note = run.waiting_limit_note(self.p.gh, self.p.root)
        self.assertEqual(run.idle_limit_seconds(self.p.root), 120)
        self.assertIn("2 pieces wait in approval", note)
        self.assertIn("next:", note)

    def test_idle_builder_is_recorded_as_builder_failed_and_stops_the_piece(self):
        with patch("run.idle_limit_seconds", return_value=1):
            n, result = self.build("idle", attempts=2)
        self.assertIn("idle", result)
        self.assertIn("state:shaping", self.p.gh.issue(n)["labels"])
        self.assertIn("builder-failed: 1", gate.report(self.p.gh))
        handback = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "give-back"][-1]
        self.assert_handback_record(handback, reason_type="builder-failed",
                                    cause="idle", attempts=1)

    def test_prepare_failure_records_zero_attempts_and_elapsed_time(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        with patch("run.prepare", return_value=(False, "Prepare failed")):
            result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("Prepare command failed", result)
        handback = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "give-back"][-1]
        self.assert_handback_record(handback, reason_type="environment",
                                    cause="prepare-failed", attempts=0)

    def test_outer_run_error_records_the_attempt_count_and_elapsed_time(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        with patch("run.build_claimed", side_effect=RuntimeError("unexpected failure")):
            result = run.build_piece(self.p.gh, self.p.root, n, 2)
        self.assertIn("unexpected failure", result)
        handback = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "give-back"][-1]
        self.assert_handback_record(handback, reason_type="environment",
                                    cause="other", attempts=0)

    def test_outer_idle_recovery_records_the_attempt_count_and_elapsed_time(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        with patch("run.build_claimed", side_effect=run.AttemptIdle("builder idle")):
            result = run.build_piece(self.p.gh, self.p.root, n, 2)
        self.assertIn("builder idle", result)
        handback = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "give-back"][-1]
        self.assert_handback_record(handback, reason_type="builder-failed",
                                    cause="idle", attempts=0)

    def test_dirty_folder_before_attempt_records_zero_and_elapsed(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        dirty_reason = "build folder has uncommitted changes the run did not make"
        with patch("run.dirty_folder_reason", side_effect=["", dirty_reason]):
            result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn(dirty_reason, result)
        handback = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "give-back"][-1]
        self.assert_handback_record(handback, reason_type="environment",
                                    cause="dirty-worktree", attempts=0)

    def test_non_conflict_merge_error_records_zero_and_elapsed(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        original_sh = run.sh

        def fail_merge(args, cwd, check=True, timeout=None):
            if args[:2] == ["git", "merge"] and "--no-edit" in args:
                return subprocess.CompletedProcess(args, 1, "", "")
            return original_sh(args, cwd, check=check, timeout=timeout)

        with patch("run.sh", side_effect=fail_merge):
            result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("does not merge", result)
        handback = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "give-back"][-1]
        self.assert_handback_record(handback, reason_type="conflict",
                                    cause="conflict", attempts=0)

    def test_changed_build_bar_records_zero_and_elapsed(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        folder = run.worktree(self.p.root, n)
        original_hash = gate.bar_hash_in

        def changed_hash(path, files):
            if Path(path).resolve() == folder.resolve():
                return "changed bar"
            return original_hash(path, files)

        with patch("gate.bar_hash_in", side_effect=changed_hash):
            result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("frozen judge bar", result)
        handback = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "give-back"][-1]
        self.assert_handback_record(handback, reason_type="bar-wrong",
                                    cause="stale-after-main", attempts=0)

