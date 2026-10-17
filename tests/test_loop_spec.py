"""Spec parsing, settings and research contracts."""
from __future__ import annotations

from helpers import KIT, SPEC, Project

# isort: split

import unittest
from pathlib import Path

import review
import run
from loopkit import Refused, loop_settings, parse_spec, records


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
