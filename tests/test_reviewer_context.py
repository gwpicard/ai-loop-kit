"""Review context and evidence from the frozen baseline."""
from __future__ import annotations

from helpers import SPEC, git

# isort: split

import json
import os
import unittest
from unittest.mock import patch

from run_fixtures import RunFixture


class ReviewerContextTest(RunFixture, unittest.TestCase):
    def test_contract_prompt_has_only_build_diff(self):
        import review
        prompts = []
        session = review._review_session

        def observe(folder, prompt, *args, **kwargs):
            prompts.append(prompt)
            return session(folder, prompt, *args, **kwargs)

        with patch("review._review_session", side_effect=observe):
            _n, result = self.build("good", attempts=1)
        self.assertIn("pull request ready", result)
        contract = next(p for p in prompts if p.startswith("# Contract reviewer brief"))
        diff = contract.split("## Diff", 1)[1]
        self.assertIn("habits.py", diff)
        self.assertNotIn("judge_add.py", diff)
        self.assertIn("judge_add.py", contract.split("## Frozen baseline", 1)[1])

    def test_contract_prompt_includes_attempt_gate_evidence(self):
        import review
        prompts = []
        session = review._review_session

        def observe(folder, prompt, *args, **kwargs):
            prompts.append(prompt)
            return session(folder, prompt, *args, **kwargs)

        with patch("review._review_session", side_effect=observe):
            n, result = self.build("good", attempts=1)
        self.assertIn("pull request ready", result)
        contract = next(p for p in prompts if p.startswith("# Contract reviewer brief"))
        self.assertIn("## Gate evidence", contract)
        log = self.p.root / ".loop" / "logs" / f"piece-{n}-attempt-1.log"
        evidence = log.read_text().split("Judge output:\n", 1)[1].split("\nAttempt timing", 1)[0]
        self.assertIn(evidence.strip(), contract)

    def test_exit_support_files_are_separate_from_tests_added(self):
        import run
        n = self.p.piece()
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        for path in ("reference.md", "capture.py", "test_extra.py"):
            (self.p.root / path).write_text("# support\n")
        git(self.p.root, "add", ".")
        git(self.p.root, "commit", "--quiet", "-m", "Exit support")
        ready = {"bar": "hash", "files": ["judge_add.py", "reference.md", "capture.py"],
                 "checks": [{"type": "tests", "files": ["judge_add.py"]},
                            {"type": "critics", "files": ["reference.md", "capture.py"]}]}
        _, evidence = run.pull_request_facts(self.p.root, ready, "passed")
        tests = next(line for line in evidence.splitlines() if "Tests added:" in line)
        self.assertIn("judge_add.py", tests)
        self.assertIn("test_extra.py", tests)
        self.assertNotIn("reference.md", tests)
        self.assertNotIn("capture.py", tests)
        self.assertIn("Frozen exit-support files:", evidence)
        self.assertIn("reference.md", evidence)

    def test_long_evidence_keeps_complete_lines_and_marks_the_cut(self):
        import run
        output = "first line\n" + "x" * 5050 + "\nlast whole line\n"
        _, evidence = run.pull_request_facts(self.p.root, {"bar": "hash"}, output)
        self.assertIn("Evidence truncated", evidence)
        self.assertIn("last whole line", evidence)
        self.assertNotIn("x" * 100, evidence)
        _, short = run.pull_request_facts(self.p.root, {"bar": "hash"}, "short\n")
        self.assertNotIn("truncated", short)
        self.assertIn("\nshort\n", short)

    def test_frozen_baseline_conflicts_are_marked_without_judge_gap_records(self):
        self.p.loop_section("true")
        os.environ["FAKE_REVIEW_MODE"] = "baseline-conflict"
        n, result = self.build("good", attempts=1)
        self.assertIn("pull request ready", result)
        body = self.p.gh.prs[f"piece/{n}"]["body"]
        self.assertIn("## Frozen baseline conflicts", body)
        self.assertIn("AGENTS.md:4", body)
        self.assertIn("future guide", body)
        self.assertFalse(any("judge-gap" in c for c in self.p.gh.comments(n)))
        self.assertNotIn("Standards findings:", body)
        self.assertNotIn("## Contract review findings", body)

    def test_pattern_matched_settings_are_frozen_baseline_conflicts(self):
        import gate
        from review import frozen_baseline, parse_contract_findings

        paths = ("vitest.config.ts", "web/vitest.config.js", ".eslintrc.json",
                 "web/.eslintrc.cjs", ".github/workflows/check.yml")
        for path in paths:
            target = self.p.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("frozen baseline setting\n")
        git(self.p.root, "add", ".")
        git(self.p.root, "commit", "--quiet", "-m", "Add baseline settings")
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        ready = gate.last_record(self.p.gh.comments(n), "ready")
        (self.p.root / paths[0]).write_text("unapproved working copy\n")
        (self.p.root / "jest.config.js").write_text("not in the ready commit\n")
        baseline = frozen_baseline(self.p.root, ready)
        self.assertNotIn("jest.config.js:1", baseline)
        diff = "+++ b/habits.py\n@@ -0,0 +1 @@\n+x\n"
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(baseline.get(f"{path}:1"), "frozen baseline setting")
                finding = {"citation": "D1", "hunk": "habits.py:1", "finding": "conflict",
                           "baseline_conflict": f"{path}:1"}
                output = "<verdict>" + json.dumps({"findings": [finding]}) + "</verdict>"
                parsed = parse_contract_findings(output, SPEC, diff, baseline)
                self.assertEqual(len(parsed), 1)
                self.assertTrue(parsed[0].startswith("Frozen baseline conflict ("))

    def test_manifest_check_settings_keep_their_source_line_numbers(self):
        from review import frozen_baseline, parse_contract_findings

        manifests = {
            "package.json": '{\n  "name": "demo",\n  "scripts": {\n'
                            '    "test": "node --test"\n  }\n}\n',
            "pyproject.toml": '# metadata\n[project]\nname = "demo"\n\n'
                              '[tool.pytest.ini_options]\naddopts = "-q"\n',
        }
        for directory in ("", "web/"):
            for name, text in manifests.items():
                path = self.p.root / (directory + name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
        git(self.p.root, "add", ".")
        git(self.p.root, "commit", "--quiet", "-m", "Add manifest check settings")
        ready = {"commit": git(self.p.root, "rev-parse", "HEAD").strip(), "files": []}
        (self.p.root / "package.json").write_text('{}\n')
        baseline = frozen_baseline(self.p.root, ready)
        diff = "+++ b/habits.py\n@@ -0,0 +1 @@\n+x\n"
        for directory in ("", "web/"):
            for name, number, expected in (
                    ("package.json", 4, '    "test": "node --test"'),
                    ("pyproject.toml", 5, '[tool.pytest.ini_options]'),
                    ("pyproject.toml", 6, 'addopts = "-q"')):
                citation = f"{directory}{name}:{number}"
                with self.subTest(citation=citation):
                    self.assertEqual(baseline.get(citation), expected)
                    finding = {"citation": "D1", "hunk": "habits.py:1", "finding": "conflict",
                               "baseline_conflict": citation}
                    output = "<verdict>" + json.dumps({"findings": [finding]}) + "</verdict>"
                    result = parse_contract_findings(output, SPEC, diff, baseline)
                    self.assertEqual(len(result), 1)
                    self.assertTrue(result[0].startswith("Frozen baseline conflict ("))

    def test_uncited_baseline_claim_stays_a_contract_finding(self):
        from review import parse_contract_findings
        finding = {"citation": "D1", "hunk": "habits.py:1", "finding": "missing",
                   "baseline_conflict": "missing.md:99"}
        output = "<verdict>" + json.dumps({"findings": [finding]}) + "</verdict>"
        diff = "+++ b/habits.py\n@@ -0,0 +1 @@\n+x\n"
        self.assertEqual(parse_contract_findings(output, SPEC, diff),
                         ["D1 at habits.py:1: missing"])
