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
                agents.start_session("codex", prompt, folder, role="builder")
            actual = popen.call_args.args[0][-1]
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
            status = run.main([str(n)])
        handback = next(r for r in records(self.p.gh.comments(n))
                        if r.get("move") == "give-back")
        self.assertEqual(handback["type"], "environment")
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
        self.assertNotIn("here-document", handback["reason"])
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
