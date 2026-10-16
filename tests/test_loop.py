"""Checks for the spec, the gate, the guard and one whole run."""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import patch
from pathlib import Path

from helpers import GOOD_CODE, JUDGE, KIT, SPEC, Project, git

import gate
import review
import run
from loopkit import (Refused, command_env, loop_settings,
                     parse_spec, records, run_judge)


class SpecTest(unittest.TestCase):
    def test_new_python_entrypoints_are_saved_as_runnable(self):
        for name in ("pr.py", "review.py"):
            mode = (KIT / "scripts" / name).stat().st_mode
            self.assertTrue(mode & 0o111, f"{name} must be executable")

    def test_runtime_and_test_modules_stay_within_reviewable_sizes(self):
        self.assertLessEqual(len((KIT / "scripts" / "run.py").read_text().splitlines()), 700)
        self.assertLessEqual(len(Path(__file__).read_text().splitlines()), 1000)

    def test_reads_sandbox_domains_from_the_loop_section(self):
        project = Project()
        self.addCleanup(project.close)
        agents = project.root / "AGENTS.md"
        agents.write_text("## The loop\nSandbox domains: pypi.org, files.pythonhosted.org\n")
        self.assertEqual(loop_settings(project.root)["sandbox domains"],
                         "pypi.org, files.pythonhosted.org")

    def test_reads_a_whole_spec(self):
        spec = parse_spec(SPEC)
        self.assertEqual(list(spec.done_when), ["D1", "D2"])
        self.assertEqual(spec.command, "python3 judge_add.py")
        self.assertEqual(spec.files, ["judge_add.py"])
        self.assertEqual(spec.kind, "feature")
        self.assertEqual(spec.intent, "Add a habit to the list.")
        self.assertEqual(spec.out_of_scope, ("Editing or deleting habits.",))

    def test_names_every_gap_at_once(self):
        with self.assertRaises(Refused) as r:
            parse_spec("## Goal\nSomething.\n")
        self.assertIn("Intent", r.exception.reason)
        self.assertIn("Contract", r.exception.reason)
        self.assertIn("Judge", r.exception.reason)

    def test_refuses_a_twice_used_id_and_a_path_outside(self):
        body = SPEC.replace("- D2:", "- D1:").replace("- judge_add.py", "- ../x.py")
        with self.assertRaises(Refused) as r:
            parse_spec(body)
        self.assertIn("used twice", r.exception.reason)
        self.assertIn("inside the project", r.exception.reason)

    def test_scaffold_needs_no_files(self):
        body = ("## Intent\nRun the first project checks.\n\nOut of scope:\n- App behaviour.\n\n"
                "## Contract\n- D1: tests run.\n\n## Judge\nCommand: `true`\nKind: scaffold\n")
        self.assertEqual(parse_spec(body).kind, "scaffold")

    def test_done_when_remains_an_alias(self):
        self.assertEqual(list(parse_spec(SPEC.replace("## Contract", "## Done when")).done_when),
                         ["D1", "D2"])

    def test_judge_can_name_a_large_file_exception(self):
        self.assertEqual(parse_spec(SPEC + "Large file: src/generated.py\n").large_files,
                         ("src/generated.py",))

    def test_research_section_parses_findings_with_source_and_date(self):
        body = SPEC + ("\n## Research\n"
                       "- R1: The API accepts a timeout argument "
                       "(source: https://example.test/api, read: 2026-10-15)\n")
        research = parse_spec(body).research
        self.assertEqual(len(research), 1)
        self.assertEqual(research[0]["id"], "R1")
        self.assertEqual(research[0]["finding"], "The API accepts a timeout argument")
        self.assertEqual(research[0]["source"], "https://example.test/api")
        self.assertEqual(research[0]["read"], "2026-10-15")

    def test_research_line_requires_a_source_and_read_date(self):
        cases = (
            "- R1: Finding (read: 2026-10-15)",
            "- R1: Finding (source: https://example.test/api)",
            "- R1: Finding (source: not-a-url, read: 2026-10-15)",
            "- R1: Finding (source: https://example.test/api, read: 2026-02-30)",
            "- R1: Finding (source: https://example.test/api, read: 2999-01-01)",
        )
        for line in cases:
            with self.subTest(line=line), self.assertRaises(Refused):
                parse_spec(SPEC + "\n## Research\n" + line + "\n")

    def test_research_ids_must_be_unique_and_lines_well_formed(self):
        finding = "- R1: A fact (source: https://example.test, read: 2026-10-15)"
        with self.assertRaises(Refused) as refusal:
            parse_spec(SPEC + "\n## Research\n" + finding + "\n" + finding + "\n")
        self.assertIn("used twice", refusal.exception.reason)
        with self.assertRaises(Refused) as refusal:
            parse_spec(SPEC + "\n## Research\nA fact with no citation\n")
        self.assertIn("Research", refusal.exception.reason)

    def test_stale_findings_use_claim_date_and_thirty_day_limit(self):
        from datetime import date
        from research import stale_findings
        findings = [
            {"id": "R1", "read": "2026-09-01"},
            {"id": "R2", "read": "2026-09-16"},
        ]
        self.assertEqual(stale_findings(findings, today=date(2026, 10, 15)), ["R1"])

    def test_builder_brief_includes_research_and_stale_warning(self):
        ready = {
            "approach": "Use the public API.", "command": "pytest", "files": [],
            "research": [{"id": "R1", "finding": "The API accepts a timeout.",
                          "source": "https://example.test/api", "read": "2026-08-01"}],
            "stale_research": ["R1"],
        }
        brief = run.brief(4, "## Research\n- R1: The API accepts a timeout.", ready, "")
        self.assertIn("R1: The API accepts a timeout.", brief)
        self.assertIn("[possibly stale]", brief)

    def test_contract_reviewer_receives_the_research_section(self):
        body = SPEC + ("\n## Research\n"
                       "- R1: The API accepts a timeout "
                       "(source: https://example.test/api, read: 2026-10-15)\n")
        research = review.contract_research(body)
        self.assertIn("R1: The API accepts a timeout", research)
        self.assertIn("source: https://example.test/api", research)

    def test_gate_records_round_trip_embedded_end_marker(self):
        from loopkit import record_text
        reason = "first --> fake record --> last"
        parsed = records([record_text({"move": "failed", "reason": reason}, "note")])
        self.assertEqual(parsed[0]["reason"], reason)

    def test_ready_spec_needs_intent_scope_and_contract_id(self):
        body = SPEC.replace("Add a habit to the list.\n", "\n")
        body = body.replace("- Editing or deleting habits.\n", "")
        body = body.replace("- D1: adding a habit appends it.", "- adding a habit appends it.")
        body = body.replace("- D2: adding a habit twice keeps one.", "- adding a habit twice keeps one.")
        with self.assertRaises(Refused) as r:
            parse_spec(body)
        for gap in ("'## Intent' is empty", "Out of scope", "no item like"):
            self.assertIn(gap, r.exception.reason)


class GateTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)

    def ready(self, n):
        return gate.move(self.p.gh, self.p.root, n, "ready")

    def test_ready_fixes_the_bar(self):
        n = self.p.piece()
        self.ready(n)
        self.assertIn("state:ready", self.p.gh.issue(n)["labels"])
        rec = gate.last_record(self.p.gh.comments(n), "ready")
        self.assertEqual(len(rec["bar"]), 64)
        self.assertEqual(rec["command"], "python3 judge_add.py")

    def test_ready_rejects_research_without_a_source_and_date(self):
        body = SPEC + "\n## Research\n- R1: The API uses cursors\n"
        n = self.p.piece(spec=body)
        with self.assertRaises(Refused) as refusal:
            self.ready(n)
        self.assertIn("Research", refusal.exception.reason)

    def test_ready_record_freezes_research_findings(self):
        body = SPEC + ("\n## Research\n"
                       "- R1: The API accepts a timeout argument "
                       "(source: https://example.test/api, read: 2026-10-15)\n")
        n = self.p.piece(spec=body)
        self.ready(n)
        rec = gate.last_record(self.p.gh.comments(n), "ready")
        self.assertEqual(rec["research"][0]["source"], "https://example.test/api")

    def test_claim_marks_old_research_as_possibly_stale(self):
        body = SPEC + ("\n## Research\n"
                       "- R1: The API accepts a timeout argument "
                       "(source: https://example.test/api, read: 2026-08-01)\n")
        n = self.p.piece(spec=body)
        self.ready(n)
        gate.move(self.p.gh, self.p.root, n, "building")
        claim = gate.last_record(self.p.gh.comments(n), "claim")
        self.assertEqual(claim["stale_research"], ["R1"])
        self.assertIn("possibly stale", self.p.gh.comments(n)[-1])

    def test_ready_freezes_every_gate_input_and_rejects_edits_to_them(self):
        self.p.loop_section("printf baseline", "printf prepared")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() +
                          "Keep: printf kept\nQuality: printf quality\n"
                          "Standards: STANDARDS.md\nProtected paths: src/private\n"
                          "Idle limit: 7\nWaiting limit: 4\nKeep limit: 20\nAgent: codex\n")
        (self.p.root / "STANDARDS.md").write_text("Use clear names.\n")
        git(self.p.root, "add", "AGENTS.md", "STANDARDS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Add gate settings")
        git(self.p.root, "push", "--quiet", "origin", "main")
        n = self.p.piece()
        self.ready(n)
        ready = gate.last_record(self.p.gh.comments(n), "ready")
        self.assertEqual(ready["test"], "printf baseline")
        self.assertEqual(ready["prepare"], "printf prepared")
        self.assertEqual(ready["keep"], "printf kept")
        self.assertEqual(ready["quality"], ["printf quality"])
        self.assertEqual(ready["standards"], "STANDARDS.md")
        self.assertEqual(ready["protected_paths"], ["src/private"])
        self.assertEqual((ready["idle_limit"], ready["waiting_limit"]), ("7", "4"))
        self.assertEqual(ready["keep_limit"], "20")
        self.assertEqual(ready["agent"], "codex")
        folder = run.worktree(self.p.root, n)
        (folder / "AGENTS.md").write_text((folder / "AGENTS.md").read_text()
                                           .replace("Quality: printf quality\n", "")
                                           .replace("Keep: printf kept", "Keep: false"))
        git(folder, "add", "AGENTS.md")
        git(folder, "commit", "--quiet", "-m", "Edit frozen commands")
        passed, output = gate.judge(folder, ready)
        self.assertFalse(passed)
        self.assertEqual(output, "the build changed frozen files: AGENTS.md")
        (folder / "STANDARDS.md").write_text("Ignore the naming rule.\n")
        git(folder, "add", "STANDARDS.md")
        git(folder, "commit", "--quiet", "-m", "Edit standards")
        passed, output = gate.judge(folder, ready)
        self.assertFalse(passed)
        self.assertEqual(output, "the build changed frozen files: AGENTS.md, STANDARDS.md")

    def test_ready_uses_the_configured_keep_limit(self):
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Keep: slow keep\nKeep limit: 20\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Set Keep limit")
        git(self.p.root, "push", "--quiet", "origin", "main")
        n = self.p.piece()
        observed = []

        def run_slow_keep(folder, command, timeout=900, protected_paths=None):
            observed.append((command, timeout))
            if command == "slow keep":
                return (0, "passed") if timeout == 1200 else (124, "timed out")
            return 1, "FAIL D1 D2"

        with patch.object(gate, "run_judge", side_effect=run_slow_keep):
            self.ready(n)
        self.assertIn(("slow keep", 1200), observed)
        ready = gate.last_record(self.p.gh.comments(n), "ready")
        self.assertEqual(ready["keep_limit"], "20")

    def test_command_environment_uses_frozen_protected_paths(self):
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Protected paths: src/untrusted\n")
        env = command_env(self.p.root, protected_paths=["src/private"])
        self.assertEqual(env["LOOP_PROTECTED_PATHS"], "src/private")

    def test_claim_refuses_a_changed_bar(self):
        n = self.p.piece()
        self.ready(n)
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "judge_add.py").write_text(JUDGE.replace("add_appends", "add_appends_changed"))
        git(self.p.root, "add", "judge_add.py")
        git(self.p.root, "commit", "--quiet", "-m", "Change ready bar")
        git(self.p.root, "switch", "--quiet", "main")
        with self.assertRaises(Refused) as refused:
            gate.move(self.p.gh, self.p.root, n, "building")
        self.assertIn("bar changed", refused.exception.reason)

    def test_root_level_judge_bar_does_not_copy_project_source(self):
        n = self.p.piece()
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "habits.py").write_text(GOOD_CODE)
        git(self.p.root, "add", "habits.py")
        git(self.p.root, "commit", "--quiet", "-m", "Add implementation")
        git(self.p.root, "switch", "--quiet", "main")
        self.ready(n)
        record = gate.last_record(self.p.gh.comments(n), "ready")
        self.assertIn("judge_add.py", record["bar_files"])
        self.assertNotIn("habits.py", record["bar_files"])

    def test_submit_refuses_an_unlisted_protected_path(self):
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Protected paths: secrets\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Protect secrets")
        git(self.p.root, "push", "--quiet", "origin", "main")
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        folder = run.worktree(self.p.root, n)
        (folder / "secrets").mkdir()
        (folder / "secrets" / "key.py").write_text("private_data = True\n")
        git(folder, "add", "secrets/key.py")
        git(folder, "commit", "--quiet", "-m", "Change protected path")
        passed, output = gate.judge(folder, gate.last_record(self.p.gh.comments(n), "ready"))
        self.assertFalse(passed)
        self.assertIn("protected paths", output)

    def test_submit_refuses_env_files_and_secret_shapes(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        folder = run.worktree(self.p.root, n)
        (folder / ".env").write_text("API_TOKEN=not-a-real-secret\n")
        git(folder, "add", ".env")
        git(folder, "commit", "--quiet", "-m", "Add environment file")
        passed, output = gate.judge(folder, gate.last_record(self.p.gh.comments(n), "ready"))
        self.assertFalse(passed)
        self.assertIn("secret-shaped", output)

    def test_submit_refuses_growth_past_one_thousand_lines(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        folder = run.worktree(self.p.root, n)
        (folder / "generated.py").write_text("value = 1\n" * 1000)
        git(folder, "add", "generated.py")
        git(folder, "commit", "--quiet", "-m", "Add large file")
        passed, output = gate.judge(folder, gate.last_record(self.p.gh.comments(n), "ready"))
        self.assertFalse(passed)
        self.assertIn("1,000 or more", output)

    def test_the_ready_note_never_claims_a_check_it_skipped(self):
        n = self.p.piece(spec=SPEC.replace("Command:", "Kind: scaffold\nCommand:"))
        self.ready(n)
        note = self.p.gh.comments(n)[-1]
        self.assertIn("does not apply", note)
        self.assertNotIn("fails on main as it should", note)

    def test_ready_refuses_a_judge_that_passes_on_main(self):
        n = self.p.piece(judge="print('test_D1 test_D2 ok')\n")
        with self.assertRaises(Refused) as r:
            self.ready(n)
        self.assertIn("already passes", r.exception.reason)
        self.assertIn("state:shaping", self.p.gh.issue(n)["labels"])

    def test_ready_refuses_a_broken_judge(self):
        n = self.p.piece(judge="def oops(:\n")
        with self.assertRaises(Refused) as r:
            self.ready(n)
        self.assertIn("python syntax error", r.exception.reason)

    def test_ready_refuses_a_judge_with_no_assertion(self):
        n = self.p.piece(judge="def test_D1():\n    pass\n")
        with self.assertRaises(Refused) as r:
            self.ready(n)
        self.assertIn("test has no assertion", r.exception.reason)

    def test_bar_includes_files_under_the_judge_folder(self):
        n = self.p.piece()
        self.ready(n)
        ready = gate.last_record(self.p.gh.comments(n), "ready")
        self.assertIn("README.md", ready["bar_files"])
        folder = run.worktree(self.p.root, n)
        (folder / "README.md").write_text("changed support\n")
        git(folder, "add", "README.md")
        git(folder, "commit", "--quiet", "-m", "Change judge support")
        passed, output = gate.judge(folder, ready)
        self.assertFalse(passed)
        self.assertIn("the build changed frozen files: README.md", output)

    def test_builder_may_add_a_new_test_file_outside_contract(self):
        n = self.p.piece()
        folder = run.worktree(self.p.root, n)
        (folder / "tests").mkdir()
        (folder / "tests" / "test_new.py").write_text("def test_new_feature(): pass\n")
        git(folder, "add", "tests/test_new.py")
        git(folder, "commit", "--quiet", "-m", "Add implementation test")
        changed = gate.changed_existing_tests(folder,
            {"files": ["judge_add.py"], "contract": {}})
        self.assertEqual(changed, [])

    def test_gate_rejects_existing_test_edits_outside_contract(self):
        (self.p.root / "tests").mkdir()
        (self.p.root / "tests" / "test_existing.py").write_text("assert True\n")
        git(self.p.root, "add", "tests/test_existing.py")
        git(self.p.root, "commit", "--quiet", "-m", "Add existing test")
        git(self.p.root, "push", "--quiet", "origin", "main")
        n = self.p.piece()
        folder = run.worktree(self.p.root, n)
        (folder / "tests" / "test_existing.py").write_text("assert False\n")
        git(folder, "add", "tests/test_existing.py")
        git(folder, "commit", "--quiet", "-m", "Change existing test")
        changed = gate.changed_existing_tests(folder, {"files": ["judge_add.py"], "contract": {}})
        self.assertEqual(changed, ["tests/test_existing.py"])

    def test_judge_skip_summary_does_not_pass(self):
        ready = {"files": [], "command": "printf '1 passed, 1 skipped\\n'"}
        passed, output = gate.judge(self.p.root, ready)
        self.assertFalse(passed)
        self.assertIn("reported skipped", output)

    def test_judge_recognises_unittest_and_node_test_skip_summaries(self):
        for output in ("Ran 3 tests in 0.2s\n\nOK (skipped=1)\n",
                       "# tests 4\n# skipped 1\n"):
            with self.subTest(output=output):
                self.assertTrue(__import__("loopkit").skipped_tests(output))

    def test_assertion_message_is_not_treated_as_a_judge_error_type(self):
        judge = ("# Add a habit to the list.\n"
                 "def test_D1_adds_a_habit():\n    assert False, 'No such file or directory'\n"
                 "def test_D2_avoids_duplicates():\n    assert False, 'ERROR collecting'\n")
        n = self.p.piece(judge=judge)
        with self.assertRaises(Refused) as refused:
            self.ready(n)
        self.assertNotIn("wrong reason", refused.exception.reason)

    def test_ready_refuses_a_judge_that_names_no_spec_id(self):
        n = self.p.piece(judge=JUDGE.replace("test_D1", "test_one").replace("test_D2", "test_two"))
        with self.assertRaises(Refused) as r:
            self.ready(n)
        self.assertIn("names no spec ID", r.exception.reason)

    def test_a_passing_test_printed_by_name_does_not_count_as_failing(self):
        # Like pytest -v: D2 passes on main and is printed, but only D1 fails.
        judge = JUDGE.replace("def d2():\n    import habits\n", "def d2():\n    return\n")
        n = self.p.piece(judge=judge)
        with self.assertRaises(Refused) as r:
            self.ready(n)
        self.assertIn("no failing judge test names D2", r.exception.reason)

    def test_ready_refuses_when_an_id_has_no_test(self):
        n = self.p.piece(judge=JUDGE.replace("test_D2", "test_two"))
        with self.assertRaises(Refused) as r:
            self.ready(n)
        self.assertIn("D2", r.exception.reason)

    def test_ready_refuses_without_the_piece_branch(self):
        n = gate.capture(self.p.gh, "No branch", SPEC)
        with self.assertRaises(Refused) as r:
            self.ready(n)
        self.assertIn("no branch", r.exception.reason)

    def test_only_listed_moves_are_allowed(self):
        n = self.p.piece()
        with self.assertRaises(Refused) as r:
            gate.move(self.p.gh, self.p.root, n, "approval")
        self.assertIn("no move from shaping to approval", r.exception.reason)

    def test_moves_back_need_a_reason(self):
        n = self.p.piece()
        with self.assertRaises(Refused):
            gate.move(self.p.gh, self.p.root, n, "dropped")
        gate.move(self.p.gh, self.p.root, n, "dropped", reason="not needed")
        self.assertEqual(self.p.gh.issue(n)["state"], "CLOSED")

    def test_moves_back_need_a_known_type_and_record_it(self):
        n = self.p.piece()
        self.ready(n)
        with self.assertRaises(Refused) as r:
            gate.move(self.p.gh, self.p.root, n, "shaping", reason="unclear")
        self.assertIn("typed reason", r.exception.reason)
        gate.move(self.p.gh, self.p.root, n, "shaping", reason="unclear",
                  reason_type="spec-unclear")
        self.assertEqual(records(self.p.gh.comments(n))[-1]["type"], "spec-unclear")

    def test_spec_command_only_edits_a_valid_spec_while_shaping(self):
        n = self.p.piece()
        gate.replace_spec(self.p.gh, n, SPEC)
        self.assertEqual(self.p.gh.issue(n)["body"], SPEC)
        self.ready(n)
        with self.assertRaises(Refused):
            gate.replace_spec(self.p.gh, n, SPEC)

    def test_report_counts_typed_handbacks(self):
        n = self.p.piece()
        self.ready(n)
        gate.move(self.p.gh, self.p.root, n, "shaping", reason="bad spec",
                  reason_type="spec-unclear")
        report = gate.report(self.p.gh)
        self.assertIn("spec-unclear: 1", report)
        self.assertIn(f"{n}: spec-unclear: bad spec", report)

    def test_handback_records_have_cause_timing_version_and_date(self):
        from datetime import date
        n = self.p.piece()
        self.ready(n)
        gate.move(self.p.gh, self.p.root, n, "building")
        gate.move(self.p.gh, self.p.root, n, "shaping", reason="Prepare failed",
                  reason_type="environment")
        record = records(self.p.gh.comments(n))[-1]
        self.assertEqual(record["cause"], "prepare-failed")
        self.assertEqual(record["attempts"], 0)
        self.assertEqual(record["seconds"], 0)
        self.assertEqual(record["kit"], "1.3.0-dev")
        self.assertEqual(date.fromisoformat(record["date"]).isoformat(), record["date"])

    def test_report_groups_causes_and_counts_first_attempt_rate(self):
        first = self.p.piece()
        self.ready(first)
        gate.move(self.p.gh, self.p.root, first, "building")
        gate.move(self.p.gh, self.p.root, first, "shaping", reason="Prepare failed",
                  reason_type="environment")
        second = self.p.piece()
        self.ready(second)
        gate.move(self.p.gh, self.p.root, second, "building")
        git(self.p.root, "switch", "--quiet", f"piece/{second}")
        (self.p.root / "habits.py").write_text(GOOD_CODE)
        gate.move(self.p.gh, self.p.root, second, "approval", folder=self.p.root,
                  pr="https://example.test/pr/1", attempts=1, seconds=3.5)
        report = gate.report(self.p.gh)
        self.assertIn("environment / prepare-failed: 1", report)
        self.assertIn("pieces started: 2", report)
        self.assertIn("passed on the first attempt: 1 / 2 (50%)", report)

    def test_report_does_not_count_a_restart_as_a_first_attempt_pass(self):
        n = self.p.piece()
        self.ready(n)
        gate.move(self.p.gh, self.p.root, n, "building")
        gate.move(self.p.gh, self.p.root, n, "shaping", reason="Prepare failed",
                  reason_type="environment")
        self.ready(n)
        gate.move(self.p.gh, self.p.root, n, "building")
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "habits.py").write_text(GOOD_CODE)
        gate.move(self.p.gh, self.p.root, n, "approval", folder=self.p.root,
                  pr="https://example.test/pr/1", attempts=1, seconds=3.5)
        report = gate.report(self.p.gh)
        self.assertIn("pieces started: 1", report)
        self.assertIn("passed on the first attempt: 0 / 1 (0%)", report)

    def test_person_handbacks_record_their_cause_and_prior_attempts(self):
        n = self.p.piece()
        self.ready(n)
        gate.move(self.p.gh, self.p.root, n, "shaping", reason="clarify the scope",
                  reason_type="spec-unclear")
        pullback = records(self.p.gh.comments(n))[-1]
        self.assertEqual(pullback["cause"], "person-request")
        self.ready(n)
        gate.move(self.p.gh, self.p.root, n, "building")
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "habits.py").write_text(GOOD_CODE)
        gate.move(self.p.gh, self.p.root, n, "approval", folder=self.p.root,
                  pr="https://example.test/pr/1", attempts=2, seconds=8.25)
        gate.move(self.p.gh, self.p.root, n, "shaping", reason="please revise",
                  reason_type="person-rejected")
        rejection = records(self.p.gh.comments(n))[-1]
        self.assertEqual(rejection["cause"], "person-rejected")
        self.assertEqual(rejection["attempts"], 2)
        self.assertEqual(rejection["seconds"], 8.25)

    def test_module_not_found_text_records_an_import_error_cause(self):
        n = self.p.piece()
        self.ready(n)
        gate.move(self.p.gh, self.p.root, n, "building")
        gate.move(self.p.gh, self.p.root, n, "shaping",
                  reason="ModuleNotFoundError: No module named 'pkg'",
                  reason_type="environment")
        handback = records(self.p.gh.comments(n))[-1]
        self.assertEqual(handback["cause"], "import-error")

    def test_gate_stop_writes_a_marker_only_for_a_live_lock(self):
        with self.assertRaises(Refused):
            gate.request_stop(self.p.root)
        lock = run.acquire_lock(self.p.root)
        self.assertIn("after the current attempt", gate.request_stop(self.p.root))
        self.assertTrue(run.stop_requested(self.p.root))
        run.clear_stop(self.p.root)
        run.release_lock(lock)

    def test_claim_refuses_a_spec_changed_after_ready(self):
        n = self.p.piece()
        self.ready(n)
        self.p.gh.issues[n]["body"] += "\n- D3: a new wish.\n"
        with self.assertRaises(Refused) as r:
            gate.move(self.p.gh, self.p.root, n, "building")
        self.assertIn("spec changed", r.exception.reason)

    def test_judge_fails_when_the_bar_moves(self):
        n = self.p.piece()
        self.ready(n)
        ready = gate.last_record(self.p.gh.comments(n), "ready")
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "habits.py").write_text(GOOD_CODE)
        self.assertTrue(gate.judge(self.p.root, ready)[0])
        (self.p.root / "judge_add.py").write_text("print('all good')\n")
        passed, why = gate.judge(self.p.root, ready)
        self.assertFalse(passed)
        self.assertIn("the build changed frozen files: judge_add.py", why)

    def test_flaky_keep_is_rerun_before_the_gate_blames_the_bar(self):
        self.p.loop_section("true")
        spec = SPEC.replace("## Judge", "## Judge\nKeep: `true`")
        n = self.p.piece(spec=spec)
        self.ready(n)
        ready = gate.last_record(self.p.gh.comments(n), "ready")
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "habits.py").write_text(GOOD_CODE)
        keep_runs = iter([(1, "FAIL test_flaky_keep"), (0, "PASS test_flaky_keep")])

        def run_flaky_keep(folder, command, timeout=900, protected_paths=None):
            if command == ready["command"]:
                return 0, "ok test_D1_add_appends\\nok test_D2_add_skips_duplicates"
            return next(keep_runs)

        with patch.object(gate, "run_judge", side_effect=run_flaky_keep):
            passed, output = gate.judge(self.p.root, ready)

        self.assertTrue(passed, output)
        self.assertIn("keep-flaky", output)
        self.assertIn("test_flaky_keep", output)

    def test_submit_runs_the_judge_itself(self):
        n = self.p.piece()
        self.ready(n)
        gate.move(self.p.gh, self.p.root, n, "building")
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        with self.assertRaises(Refused) as r:
            gate.move(self.p.gh, self.p.root, n, "approval", folder=self.p.root, pr="u")
        self.assertIn("does not pass", r.exception.reason)
        (self.p.root / "habits.py").write_text(GOOD_CODE)
        gate.move(self.p.gh, self.p.root, n, "approval", folder=self.p.root, pr="u")
        self.assertIn("state:approval", self.p.gh.issue(n)["labels"])

    def test_done_needs_a_merged_pull_request(self):
        n = self.p.piece()
        self.ready(n)
        gate.move(self.p.gh, self.p.root, n, "building")
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "habits.py").write_text(GOOD_CODE)
        self.p.gh.create_pr(f"piece/{n}", "t", "b")
        gate.move(self.p.gh, self.p.root, n, "approval", folder=self.p.root, pr="u")
        with self.assertRaises(Refused):
            gate.move(self.p.gh, self.p.root, n, "done")
        self.p.gh.prs[f"piece/{n}"]["state"] = "MERGED"
        self.p.gh.issues[n]["state"] = "CLOSED"  # GitHub's closing words got there first
        self.assertEqual(len(gate.sync(self.p.gh, self.p.root)), 1)
        self.assertIn("state:done", self.p.gh.issue(n)["labels"])

    def test_changes_to_frozen_judge_support_are_refused(self):
        keep_spec = SPEC.replace("Files:", "Keep: `python3 keep_check.py`\nFiles:")
        n = self.p.piece(spec=keep_spec)
        with self.assertRaises(Refused) as r:  # no keep_check.py on main yet
            self.ready(n)
        self.assertIn("keep check already fails on main", r.exception.reason)
        (self.p.root / "keep_check.py").write_text("import pathlib, sys\nsys.exit(0 if pathlib.Path('README.md').exists() else 1)\n")
        git(self.p.root, "add", "keep_check.py")
        git(self.p.root, "commit", "--quiet", "-m", "Keep check")
        git(self.p.root, "push", "--quiet", "origin", "main")
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        git(self.p.root, "merge", "--quiet", "--no-edit", "main")
        git(self.p.root, "switch", "--quiet", "main")
        self.ready(n)
        self.assertIn("keep check", self.p.gh.comments(n)[-1])
        ready = gate.last_record(self.p.gh.comments(n), "ready")
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "habits.py").write_text(GOOD_CODE)
        self.assertTrue(gate.judge(self.p.root, ready)[0])
        (self.p.root / "README.md").unlink()  # the build breaks what worked before
        passed, why = gate.judge(self.p.root, ready)
        self.assertFalse(passed)
        self.assertIn("the build changed frozen files: README.md", why)

    def test_a_stays_item_must_hold_on_main_and_have_a_test(self):
        stays_spec = SPEC.replace("- D2: adding a habit twice keeps one.",
                                  "- D2: adding a habit twice keeps one.\n- D3 (stays): the readme is still there.")
        judge = JUDGE.replace('check("test_D2_add_skips_duplicates", d2)',
                              'check("test_D2_add_skips_duplicates", d2)\n'
                              'check("test_D3_readme_stays", lambda: open("README.md").read())')
        n = self.p.piece(spec=stays_spec, judge=judge)
        self.ready(n)
        self.assertIn("D3 already hold", self.p.gh.comments(n)[-1])

    def test_a_stays_item_bent_to_fail_on_main_is_refused(self):
        stays_spec = SPEC.replace("- D2: adding a habit twice keeps one.",
                                  "- D2: adding a habit twice keeps one.\n- D3 (stays): habits still imports.")
        judge = JUDGE.replace('check("test_D2_add_skips_duplicates", d2)',
                              'check("test_D2_add_skips_duplicates", d2)\ncheck("test_D3_still_imports", d1)')
        n = self.p.piece(spec=stays_spec, judge=judge)
        with self.assertRaises(Refused) as r:
            self.ready(n)
        self.assertIn("marked (stays) but fails on main", r.exception.reason)

    def test_a_stays_item_without_a_test_is_refused(self):
        stays_spec = SPEC.replace("- D2: adding a habit twice keeps one.",
                                  "- D2: adding a habit twice keeps one.\n- D3 (stays): nothing breaks.")
        n = self.p.piece(spec=stays_spec)
        with self.assertRaises(Refused) as r:
            self.ready(n)
        self.assertIn("no judge test names D3", r.exception.reason)

    def test_fresh_worktree_honours_path_override_without_project_venv(self):
        project_venv = self.p.root / ".venv"
        project_bin = project_venv / "bin"
        project_bin.mkdir(parents=True)
        project_python = project_bin / "python3"
        project_python.write_text("#!/bin/sh\necho from-project-venv\n")
        project_python.chmod(0o755)
        override_bin = Path(self.p.tmp.name) / "override" / "bin"
        override_bin.mkdir(parents=True)
        override_python = override_bin / "python3"
        override_python.write_text("#!/bin/sh\necho from-path-override\n")
        override_python.chmod(0o755)
        worktree = Path(self.p.tmp.name) / "wt"
        git(self.p.root, "worktree", "add", "--quiet", "--detach", str(worktree), "main")
        inherited_path = os.pathsep.join(
            [str(project_bin), str(override_bin), os.environ.get("PATH", "")])
        from loopkit import run_judge
        with patch.dict(os.environ, {"PATH": inherited_path,
                                     "VIRTUAL_ENV": str(project_venv)}):
            env = command_env(worktree)
            code, out = run_judge(worktree, "python3 --version")
        self.assertEqual(code, 0)
        self.assertIn("from-path-override", out)
        self.assertNotIn(str(project_bin), env["PATH"].split(os.pathsep))
        self.assertNotIn("VIRTUAL_ENV", env)

    def test_fresh_worktree_uses_system_path_when_caller_path_is_empty(self):
        worktree = Path(self.p.tmp.name) / "wt"
        git(self.p.root, "worktree", "add", "--quiet", "--detach", str(worktree), "main")
        with patch("loopkit.project_root", return_value=self.p.root), \
                patch.dict(os.environ, {"PATH": "", "VIRTUAL_ENV": "/project/.venv"}):
            env = command_env(worktree)
        self.assertEqual(env["PATH"], os.defpath)
        self.assertNotIn("VIRTUAL_ENV", env)

    def test_fresh_worktree_venv_precedes_project_venv(self):
        project_bin = self.p.root / ".venv" / "bin"
        project_bin.mkdir(parents=True)
        project_python = project_bin / "python3"
        project_python.write_text("#!/bin/sh\necho from-project-venv\n")
        project_python.chmod(0o755)
        worktree = Path(self.p.tmp.name) / "wt"
        git(self.p.root, "worktree", "add", "--quiet", "--detach", str(worktree), "main")
        fresh_bin = worktree / ".venv" / "bin"
        fresh_bin.mkdir(parents=True)
        fresh_python = fresh_bin / "python3"
        fresh_python.write_text("#!/bin/sh\necho from-fresh-venv\n")
        fresh_python.chmod(0o755)
        inherited_path = os.pathsep.join([str(project_bin), os.environ.get("PATH", "")])
        with patch.dict(os.environ, {"PATH": inherited_path,
                                     "VIRTUAL_ENV": str(self.p.root / ".venv")}):
            env = command_env(worktree)
            code, out = run_judge(worktree, "python3 --version")
        self.assertEqual(code, 0)
        self.assertIn("from-fresh-venv", out)
        self.assertEqual(env["PATH"].split(os.pathsep)[0], str(fresh_bin.resolve()))
        self.assertEqual(env["VIRTUAL_ENV"], str((worktree / ".venv").resolve()))
        self.assertNotIn(str(project_bin), env["PATH"].split(os.pathsep))

    def test_prepare_runs_in_the_fresh_copy_before_keep_and_judge(self):
        self.p.loop_section("true", prepare="touch prepared.txt")
        keep_spec = SPEC.replace("Files:", "Keep: `test -f prepared.txt`\nFiles:")
        n = self.p.piece(spec=keep_spec)
        self.ready(n)  # keep would fail without the Prepare step
        self.assertIn("state:ready", self.p.gh.issue(n)["labels"])

    def test_a_failing_prepare_refuses_ready(self):
        self.p.loop_section("true", prepare="exit 3")
        n = self.p.piece()
        with self.assertRaises(Refused) as r:
            self.ready(n)
        self.assertIn("Prepare command fails", r.exception.reason)

    def test_scaffold_ready_does_not_run_prepare_on_main(self):
        self.p.loop_section("true", prepare="test -f pyproject.toml")
        spec = ("## Intent\nSet up the test runner.\n\nOut of scope:\n- Product code.\n\n"
                "## Contract\n- D1: the scaffold test runs.\n\n## Judge\n"
                "Command: `true`\nKind: scaffold\n")
        n = self.p.piece(spec=spec)
        self.ready(n)
        self.assertIn("state:ready", self.p.gh.issue(n)["labels"])

    def test_doctor_names_each_gap_then_passes(self):
        checks = gate.doctor(self.p.gh, self.p.root)
        failed = [what for ok, what, _ in checks if not ok]
        self.assertIn("the state labels exist", failed)
        self.assertIn("AGENTS.md on main names the Test command", failed)
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("test -f prepared.txt", prepare="touch prepared.txt")
        checks = gate.doctor(self.p.gh, self.p.root)
        self.assertTrue(all(ok for ok, _, _ in checks), checks)
        self.assertTrue(any("main branch protection: unknown" == what for _, what, _ in checks))

    def test_doctor_checks_quality_commands_on_main(self):
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Quality: printf quality-check-failed; exit 4\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Add bad quality command")
        git(self.p.root, "push", "--quiet", "origin", "main")
        checks = gate.doctor(self.p.gh, self.p.root)
        failure = next((item for item in checks if not item[0] and "Quality" in item[1]), None)
        self.assertIsNotNone(failure, checks)
        self.assertIn("quality-check-failed", failure[2])

    def test_doctor_reports_a_timed_out_keep_with_next_step(self):
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Keep: slow keep\nKeep limit: 1\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Set slow Keep")
        git(self.p.root, "push", "--quiet", "origin", "main")

        def run_slow_keep(folder, command, timeout=900, protected_paths=None):
            if command == "slow keep":
                self.assertEqual(timeout, 60)
                return 124, "the judge ran past 60 seconds"
            return 0, ""

        with patch.object(gate, "run_judge", side_effect=run_slow_keep):
            checks = gate.doctor(self.p.gh, self.p.root)
        failed_keep = next((check for check in checks if not check[0] and "Keep" in check[1]), None)
        self.assertIsNotNone(failed_keep, checks)
        self.assertTrue(failed_keep[2], failed_keep)
        self.assertIn("Keep limit", failed_keep[2])

    def test_doctor_runs_test_before_quality_in_the_same_fresh_copy(self):
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("touch .coverage")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Quality: test -f .coverage\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Add coverage quality check")
        git(self.p.root, "push", "--quiet", "origin", "main")
        checks = gate.doctor(self.p.gh, self.p.root)
        quality = [item for item in checks if "Quality command" in item[1]]
        self.assertTrue(quality and all(item[0] for item in quality), checks)

    def test_doctor_applies_proposed_quality_to_fresh_main(self):
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("true")
        proposal = "grep -q '^Quality: ' AGENTS.md"
        checks = gate.doctor(self.p.gh, self.p.root, extra_quality=[proposal])
        proposed = [item for item in checks if "Proposed Quality command" in item[1]]
        self.assertEqual(len(proposed), 1, checks)
        self.assertTrue(proposed[0][0], proposed[0])

    def test_failed_quality_probe_runs_test_before_quality_on_main(self):
        self.p.loop_section("touch .coverage")
        failed = gate.quality_fails_on_main(
            self.p.root, "test -f .coverage", "touch .coverage")
        self.assertFalse(failed)

    def test_doctor_fails_mutation_check_without_source_paths(self):
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("true")
        helper = Path(gate.__file__).resolve().parents[1] / "quality" / "mutmut-changed.py"
        checks = gate.doctor(self.p.gh, self.p.root,
                             extra_quality=[f"python3 {helper} origin/main"])
        quality = [item for item in checks if "Quality command" in item[1]]
        self.assertTrue(quality and not quality[-1][0], checks)
        self.assertIn("no mutmut source paths configured", quality[-1][2])

    def test_doctor_uses_proposed_prepare_and_test_for_quality_probe(self):
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("true", prepare="touch old-prepare")
        proposed_quality = "printf proposed"
        with patch.object(gate, "quality_on_fresh_main", return_value=(True, "")) as probe:
            gate.doctor(self.p.gh, self.p.root, extra_quality=[proposed_quality],
                        proposed_prepare="touch new-prepare", proposed_test="test -f new-test")
        probe.assert_called_once()
        self.assertEqual(probe.call_args.args[2:4], (proposed_quality, "test -f new-test"))
        self.assertEqual(probe.call_args.kwargs["prepare_command"], "touch new-prepare")

    def test_doctor_warns_about_old_in_project_worktrees(self):
        (self.p.root / ".loop" / "worktrees" / "old").mkdir(parents=True)
        checks = gate.doctor(self.p.gh, self.p.root)
        warning = next((item for item in checks if "old in-project worktrees" in item[1]), None)
        self.assertIsNotNone(warning, checks)
        self.assertIn(".loop/worktrees/old", warning[1])
        self.assertIn("may remove", warning[2])

    def test_doctor_catches_a_red_baseline(self):
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("exit 1")
        checks = gate.doctor(self.p.gh, self.p.root)
        self.assertFalse(checks[-1][0])
        self.assertIn("tests pass on a fresh copy", checks[-1][1])

    def test_judge_output_loses_terminal_colour_codes(self):
        _, output = run_judge(self.p.root, r"printf '\033[31mFAIL\033[39m \033]8;;file:///a\007a.js\033]8;;\007'")
        self.assertEqual(output, "FAIL a.js")

    def test_keep_output_records_elapsed_seconds(self):
        with patch.object(gate.time, "monotonic", side_effect=[10.0, 12.5]), \
                patch.object(gate, "run_judge", return_value=(0, "passed")):
            code, output = gate.run_keep(self.p.root, "true", timeout=1200)
        self.assertEqual(code, 0)
        self.assertEqual(output, "passed\nKeep took: 2.500 seconds")

    def test_the_loop_folder_stays_ignored_whatever_gitignore_says(self):
        (self.p.root / ".gitignore").write_text("__pycache__/\n")
        gate.ignore_loop_folder(self.p.root)
        (self.p.root / ".loop").mkdir()
        (self.p.root / ".loop" / "x.log").write_text("log")
        self.assertNotIn(".loop", git(self.p.root, "status", "--porcelain"))

    def test_a_piece_with_two_states_is_refused(self):
        n = self.p.piece()
        self.p.gh.issues[n]["labels"].append("state:ready")
        with self.assertRaises(Refused) as r:
            gate.move(self.p.gh, self.p.root, n, "ready")
        self.assertIn("2 state labels", r.exception.reason)


def guard(command=None, tool="Bash", builder=False, path=None, protected=""):
    data = {"command": command} if command is not None else {"file_path": path}
    env = {**os.environ, "LOOP_BUILDER": "1" if builder else "0",
           "LOOP_PROTECTED_PATHS": protected}
    res = subprocess.run([sys.executable, str(KIT / "hooks" / "guard.py")],
                         input=json.dumps({"tool_name": tool, "tool_input": data}),
                         capture_output=True, text=True, env=env)
    return res.returncode


class GuardTest(unittest.TestCase):
    REFUSED = [
        "git push origin main", "git push origin HEAD:main", "git push --force origin piece/1",
        "git push -f", "rm -rf build", "rm -r src", "rm -fR x", "sudo rm --recursive x",
        'eval "git push --force origin piece/1"', "printf x | xargs rm -r file",
        "find . -name '*.pyc' -delete", "git clean -fdx", "git rm -r src",
        "gh pr merge 3 --squash", "gh issue edit 3 --add-label state:ready",
        "gh api repos/o/r/issues/3/labels -f labels[]=state:done",
        "echo hi && git push origin main", "FOO=1 git push origin main",
        "git -C . push origin main", 'bash -c "git push --force origin x"',
        "gh -R a/b pr merge 3", "python3 -c \"import shutil; shutil.rmtree('x')\"",
        "node -e \"rm -rf x\"", "GIT_CONFIG_COUNT=1 git push origin main",
    ]
    ALLOWED = [
        "git push -u origin piece/4", "rm build/out.txt", "git status", "gh issue list",
        "gh issue edit 3 --add-label bug", "python3 gate.py move 3 ready", "ls -la",
    ]

    def test_refuses_the_hard_rules(self):
        for cmd in self.REFUSED:
            self.assertEqual(guard(cmd), 2, cmd)

    def test_allows_ordinary_work(self):
        for cmd in self.ALLOWED:
            self.assertEqual(guard(cmd), 0, cmd)

    def test_builders_never_push_or_use_gh_or_touch_settings(self):
        self.assertEqual(guard("git push -u origin piece/4", builder=True), 2)
        self.assertEqual(guard("gh issue list", builder=True), 2)
        self.assertEqual(guard(tool="Write", path="/p/.claude/settings.json", builder=True), 2)
        self.assertEqual(guard(tool="Write", path="/p/src/app.py", builder=True), 0)

    def test_builder_refuses_protected_paths_and_unreadable_commands(self):
        self.assertEqual(guard(tool="Edit", path="/p/secrets/key.py", builder=True,
                               protected="secrets"), 2)
        self.assertEqual(guard("echo 'unfinished", builder=True), 2)

    def test_builder_refuses_unhandled_execution_and_redirect_forms(self):
        for command in ("bash -lc 'echo hi'", "sh -ec 'echo hi'", "eval 'git status'",
                        "printf x | xargs rm -r file", "perl -e 'print 1'", "ruby -e 'puts 1'",
                        "echo x > .claude/settings.json", "echo x >> .githooks/commit-msg",
                        "echo x > secrets/key.txt"):
            with self.subTest(command=command):
                self.assertEqual(guard(command, builder=True, protected="secrets"), 2)

    def test_plain_git_push_is_refused_on_main(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("loop_guard", KIT / "hooks" / "guard.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module, "current_branch", return_value="main"):
            self.assertIsNotNone(module.check_command("git push", builder=False))




if __name__ == "__main__":
    unittest.main()
