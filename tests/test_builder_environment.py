"""Staging ownership and evidence for builder environment reports."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import git

# isort: split
import agents
import run
import run_fixtures
import sandbox
from loopkit import records


class BuilderEnvironmentTest(unittest.TestCase):
    def test_brief_continues_after_successful_command_warnings(self):
        prompt = run.brief(1, "spec", {"files": []}, "", backend="codex")
        self.assertIn("A warning from a command that exited 0 is not an environment failure",
                      prompt)
        self.assertIn("carry on", prompt)
        self.assertIn("An environment outcome needs a failed command", prompt)

    def test_repeated_unsupported_environment_reports_stop_after_two_attempts(self):
        self._unsupported_environment_reports(["Git warned."] * 3, 2)

    def test_different_environment_reports_do_not_stop_early(self):
        self._unsupported_environment_reports(["Git warned.", "An env path warned.",
                                               "Git warned."], 3)

    def test_environment_reports_must_be_consecutive(self):
        self._unsupported_environment_reports(["Git warned.", None, "Git warned."], 3)

    def _unsupported_environment_reports(self, reasons, expected_attempts):
        run_fixtures.RunFixture.setUp(self)

        def builder(folder, prompt, files, logfile, *args, **kwargs):
            (folder / ".loop").mkdir(exist_ok=True)
            reason = reasons[build.call_count - 1]
            if reason is None:
                return ""
            (folder / ".loop" / "outcome").write_text("environment\n" + reason + "\n")
            logfile.with_suffix(".jsonl").write_text(json.dumps({
                "type": "item.completed", "item": {
                    "type": "command_execution", "exit_code": 0,
                    "aggregated_output": "warning: unable to access ~/.config/git/ignore: "
                                         "Operation not permitted\n"
                                         ".env.local: Operation not permitted"}}))
            return ""

        with patch.object(run, "build_once", side_effect=builder) as build, \
                patch("gate.judge", return_value=(False, "AssertionError: missing")) as judge:
            n, result = run_fixtures.RunFixture.build(self, "good", attempts=3)
        self.assertEqual(build.call_count, expected_attempts)
        handback = next(r for r in records(self.p.gh.comments(n))
                        if r.get("move") == "give-back")
        self.assertEqual(handback["type"], "builder-failed")
        self.assertEqual(handback["attempts"], expected_attempts)
        self.assertIn("log evidence", handback["reason"])
        if expected_attempts == 2:
            self.assertIn("two identical environment reports in a row", result)
            self.assertIn("Git warned.", handback["reason"])
        self.assertEqual(judge.call_count, reasons.count(None))

    def test_successful_batch_with_shell_refusal_hands_back_without_judging(self):
        run_fixtures.RunFixture.setUp(self)
        output = self._shell_refusal_output(1, 62)

        def builder(folder, prompt, files, logfile, *args, **kwargs):
            (folder / ".loop").mkdir(exist_ok=True)
            (folder / ".loop" / "outcome").write_text(
                "environment\nThe shell could not create a temporary file.\n")
            (folder / "guide.md").write_text("Unfinished guide.\n")
            logfile.with_suffix(".jsonl").write_text(json.dumps({
                "type": "item.completed", "item": {
                    "type": "command_execution", "exit_code": 0,
                    "aggregated_output": output}}) + "\n")
            return ""

        with patch.object(run, "build_once", side_effect=builder) as build, \
                patch("gate.judge") as judge, \
                patch.object(run, "review_piece") as review, \
                patch.object(run, "open_pull_request") as pull_request, \
                patch.object(run, "commit_leftovers", wraps=run.commit_leftovers) as commit:
            n, result = run_fixtures.RunFixture.build(self, "good", attempts=3)
        self.assertEqual(build.call_count, 1)
        handback = next(r for r in records(self.p.gh.comments(n))
                        if r.get("move") == "give-back")
        self.assertEqual(handback["type"], "environment")
        self.assertEqual(handback["attempts"], 1)
        self.assertIn(output.splitlines()[0], handback["reason"])
        # The builder's own words usually name the cause; keep them beside the evidence.
        self.assertIn("The shell could not create a temporary file.", handback["reason"])
        self.assertNotIn("... ok", handback["reason"])
        self.assertIn("environment", result)
        judge.assert_not_called()
        review.assert_not_called()
        pull_request.assert_not_called()
        commit.assert_not_called()

    @staticmethod
    def _shell_refusal_output(*line_numbers):
        return "".join(
            f"zsh:{number}: can't create temp file for here document: "
            "operation not permitted\n" for number in line_numbers
        ) + ("test_add (tests.test_calc.CalcTest.test_add) ... ok\n"
             "test_sum_range (tests.test_calc.CalcTest.test_sum_range) ... ok\n"
             "test_sum_range_rejects_non_integer_bounds "
             "(tests.test_calc.CalcTest.test_sum_range_rejects_non_integer_bounds) ... ok\n"
             "test_subtract_numbers "
             "(tests.test_mutation_inprocess.SubtractAdapterTest.test_subtract_numbers) ... ok\n"
             "test_zero (tests.test_mutation_inprocess.SubtractAdapterTest.test_zero) ... ok\n"
             "\n----------------------------------------------------------------------\n"
             "Ran 5 tests in 0.000s\n\nOK\n")

    def test_successful_command_evidence_keeps_only_zsh_refusal_lines(self):
        with tempfile.TemporaryDirectory() as temporary:
            logfile = Path(temporary) / "builder.log"
            for numbers in [(1, 62), (2, 51)]:
                with self.subTest(numbers=numbers):
                    output = self._shell_refusal_output(*numbers)
                    logfile.with_suffix(".jsonl").write_text(json.dumps({
                        "type": "item.completed", "item": {
                            "type": "command_execution", "exit_code": 0,
                            "aggregated_output": output}}))
                    self.assertEqual(agents.environment_evidence(logfile),
                                     "Observed tool failure: " +
                                     "\n".join(output.splitlines()[:2]))

    def test_successful_output_and_agent_prose_are_not_shell_refusal_evidence(self):
        denial = self._shell_refusal_output(1).splitlines()[0]
        cases = [
            ("item.completed", "agent_message", denial),
            ("item.completed", "command_execution", "Operation not permitted"),
            ("item.completed", "command_execution", "Ran 5 tests in 0.000s\n\nOK\n"),
            ("item.completed", "command_execution", "The shell reported " + denial),
            ("item.completed", "command_execution", denial + " but continued"),
            ("item.started", "command_execution", denial),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            logfile = Path(temporary) / "builder.log"
            for event_type, item_type, output in cases:
                with self.subTest(event=event_type, item=item_type, output=output):
                    logfile.with_suffix(".jsonl").write_text(json.dumps({
                        "type": event_type, "item": {
                            "type": item_type, "exit_code": 0,
                            "text": output, "aggregated_output": output}}))
                    self.assertEqual(agents.environment_evidence(logfile), "")

    def test_codex_leaves_staging_to_runner_and_runner_excludes_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve() / "repo"
            repo.mkdir()
            git(repo, "init", "-q")
            git(repo, "commit", "--allow-empty", "-qm", "Initial")
            folder = repo.parent / "piece"
            git(repo, "worktree", "add", "-qb", "piece", str(folder))
            prompt = run.brief(1, "spec", {"files": []}, "", folder=folder, backend="codex")
            paths = sandbox.codex_builder_paths(folder)
            with patch.object(agents, "command_env", return_value={}), \
                    patch.object(sandbox, "codex_builder_paths", return_value=paths), \
                    patch.object(agents.subprocess, "Popen") as popen:
                sent = []
                popen.side_effect = lambda *args, **kwargs: sent.append(
                    kwargs["stdin"].read().decode())
                agents.start_session("codex", prompt, folder, role="builder")
            self.assertEqual(popen.call_args.args[0][-1], "-")
            actual = sent[0]
            self.assertNotIn('`python3 "$AI_LOOP_KIT_ROOT/scripts/builder_prompt.py" --stage`',
                             actual)
            self.assertIn("The run stages and commits", actual)
            (folder / "guide.md").write_text("A guide.\n")
            (folder / ".loop" / "outcome").write_text("runtime\n")
            # The sandboxed session has ended. Only the runner writes the git index.
            with patch.object(run, "sh", wraps=run.sh) as shell:
                run.commit_leftovers(folder, 1, 1)
            self.assertTrue(any("--stage" in call.args[0]
                                for call in shell.call_args_list))
            self.assertEqual(git(folder, "show", "--pretty=", "--name-only", "HEAD"),
                             "guide.md")
            self.assertTrue((folder / ".loop" / "outcome").exists())
            self.assertFalse(Path(git(folder, "rev-parse", "--absolute-git-dir"),
                                  "index.lock").exists())

    def test_run_returns_nonzero_after_environment_handback(self):
        run_fixtures.RunFixture.setUp(self)
        n = self.p.piece()
        import gate
        gate.move(self.p.gh, self.p.root, n, "ready")
        previous = Path.cwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(self.p.root)
        with patch("run_cli.GitHub", return_value=self.p.gh), \
                patch.object(run, "build_once", side_effect=OSError("builder unavailable")):
            status = run.main(["--attended", str(n)])
        requeue = next(r for r in records(self.p.gh.comments(n))
                       if r.get("move") == "requeue")
        self.assertEqual(requeue["type"], "environment")
        self.assertNotEqual(status, 0)

    def test_measure_brief_stops_if_hypothesis_write_fails(self):
        prompt = run.brief(1, "spec", {"files": [], "checks": [
            {"type": "measure", "command": "python3 bench.py"}]}, "")
        self.assertIn("If writing the hypothesis fails, stop before editing code", prompt)

    def test_environment_report_uses_tool_failure_instead_of_invented_reason(self):
        self._environment_report(True)

    def test_environment_report_without_failed_tool_is_not_accepted(self):
        self._environment_report(False)

    def test_missing_hypothesis_directory_is_reported_from_tool_log(self):
        self._environment_report(True, "bash: .loop/hypothesis: No such file or directory")

    def test_open_file_limit_is_reported_from_tool_log(self):
        self._environment_report(True, "bash: .loop/hypothesis: Too many open files")

    def _environment_report(self, failed, error=(
            "fatal: Unable to create /piece/git/index.lock: Operation not permitted")):
        run_fixtures.RunFixture.setUp(self)
        def builder(folder, prompt, files, logfile, *args, **kwargs):
            (folder / ".loop").mkdir(exist_ok=True)
            (folder / ".loop" / "outcome").write_text(
                "environment\nThe shell could not create a here-document temporary file.\n")
            event = {"type": "item.completed", "item": {
                "type": "command_execution", "command": "python3 helper.py --stage",
                "exit_code": 1 if failed else 0,
                "aggregated_output": error if failed else "done"}}
            logfile.write_text("The shell could not create a here-document temporary file.\n")
            logfile.with_suffix(".jsonl").write_text(json.dumps(event) + "\n")
            return ""
        with patch.object(run, "build_once", side_effect=builder):
            n, result = run_fixtures.RunFixture.build(self, "good", attempts=1)
        handback = next(r for r in records(self.p.gh.comments(n))
                        if r.get("move") == "give-back")
        # The builder's words appear only as its claim, after the tool evidence.
        self.assertNotIn("here-document", handback["reason"].split("\nThe builder said: ")[0])
        if failed:
            self.assertEqual(handback["type"], "environment")
            self.assertIn(error, handback["reason"])
            self.assertIn(error, result)
        else:
            self.assertEqual(handback["type"], "builder-failed")
            self.assertIn("log evidence", handback["reason"])

    def test_environment_evidence_ignores_agent_messages_and_successful_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            logfile = Path(temporary) / "builder.log"
            logfile.with_suffix(".jsonl").write_text("\n".join(json.dumps(event) for event in [
                {"type": "item.completed", "item": {"type": "agent_message",
                 "text": "fatal: index.lock Operation not permitted"}},
                {"type": "item.completed", "item": {"type": "command_execution",
                 "exit_code": 0, "aggregated_output": "Operation not permitted"}},
            ]))
            self.assertEqual(agents.environment_evidence(logfile), "")

    def test_claude_environment_evidence_comes_from_failed_tool_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            logfile = Path(temporary) / "builder.log"
            logfile.with_suffix(".jsonl").write_text(json.dumps({
                "type": "user", "message": {"content": [{"type": "tool_result",
                "is_error": True, "content": "Permission denied: .loop/hypothesis"}]}}))
            self.assertIn(".loop/hypothesis", agents.environment_evidence(logfile))
