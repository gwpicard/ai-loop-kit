"""Contract findings with evidence must change the run disposition."""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))

import gate
import review
from helpers import git
from run_fixtures import RunFixture


class ReviewDispositionsTest(RunFixture, unittest.TestCase):
    def test_reproduced_contract_finding_returns_piece_to_shaping(self):
        os.environ["FAKE_REVIEW_MODE"] = "contract-reproduced"
        n, result = self.build("good", attempts=1)

        self.assertIn("back to shaping", result)
        self.assertNotIn(f"piece/{n}", self.p.gh.prs)
        handback = next(record for record in gate.records(self.p.gh.comments(n))
                        if record.get("move") == "give-back")
        self.assertEqual(handback["type"], "judge-gap")
        self.assertIn("reproducer", handback["reason"])
        self.assertIn("D1", handback["reason"])
        self.assertIn('raise AssertionError("D1")', handback["reason"])
        branch = self.p.folder(n)
        self.assertFalse((branch / "test_review_D1.py").exists())
        self.assertIn("check(\"test_D1_add_appends\", d1)",
                      git(branch, "show", "HEAD:judge_add.py"))

    def test_each_contract_finding_can_use_its_own_reproducer(self):
        os.environ["FAKE_REVIEW_MODE"] = "contract-multiple-reproduced"
        n, result = self.build("good", attempts=1)

        self.assertIn("back to shaping", result)
        self.assertNotIn(f"piece/{n}", self.p.gh.prs)
        handback = next(record for record in gate.records(self.p.gh.comments(n))
                        if record.get("move") == "give-back")
        self.assertIn("D1", handback["reason"])
        self.assertIn("D2", handback["reason"])
        self.assertIn('raise AssertionError("D1")', handback["reason"])
        self.assertIn('raise AssertionError("D2")', handback["reason"])
        branch = self.p.folder(n)
        self.assertFalse((branch / "test_review_D1.py").exists())
        self.assertFalse((branch / "test_review_D2.py").exists())

    def test_unresolved_contract_finding_heads_pr_and_removes_contract_claim(self):
        os.environ["FAKE_REVIEW_MODE"] = "contract-gap"
        n, result = self.build("good", attempts=1)

        self.assertIn("pull request ready", result)
        body = self.p.gh.prs[f"piece/{n}"]["body"]
        self.assertTrue(body.startswith("## Unresolved review findings"))
        self.assertIn("D1 is not met", body)
        self.assertNotIn("the contract is met", body.lower())

    def test_non_reproducing_finding_keeps_pull_request_and_shows_result(self):
        os.environ["FAKE_REVIEW_MODE"] = "contract-not-reproduced"
        n, result = self.build("good", attempts=1)

        self.assertIn("pull request ready", result)
        body = self.p.gh.prs[f"piece/{n}"]["body"]
        self.assertIn("Unresolved review findings", body)
        self.assertIn("reproducer", body.lower())
        self.assertIn("passed", body.lower())

    def test_reproducer_failure_without_the_named_item_does_not_stop_pr(self):
        os.environ["FAKE_REVIEW_MODE"] = "contract-unrelated"
        n, result = self.build("good", attempts=1)

        self.assertIn("pull request ready", result)
        body = self.p.gh.prs[f"piece/{n}"]["body"]
        self.assertIn("did not reproduce it", body)
        self.assertIn("FAIL X9", body)

    def test_unparseable_contract_verdict_is_a_review_error(self):
        os.environ["FAKE_REVIEW_MODE"] = "bad-contract-verdict"
        n, result = self.build("good", attempts=1)

        self.assertIn("invalid verdict", result)
        self.assertIn("environment: 1", gate.report(self.p.gh))
        self.assertTrue(any("next:" in comment.lower()
                            for comment in self.p.gh.comments(n)))

    def test_reproducer_uses_prepare_and_preserves_shell_operators(self):
        (self.p.root / "judge.py").write_text("raise AssertionError('baseline')\n")
        git(self.p.root, "add", "judge.py")
        git(self.p.root, "commit", "--quiet", "-m", "Add frozen judge")
        source = 'assert False, "D1 FileNotFoundError is expected"\n'
        test_file = Path("test_review_D1.py")
        (self.p.root / test_file).write_text(source)
        ready = {
            "checks": [{"type": "tests", "command": ".venv/bin/python judge.py && printf done",
                        "files": ["judge.py"]}],
            "prepare": ("mkdir -p .venv/bin && printf '#!/bin/sh\\nexec python3 \"$@\"\\n' "
                        "> .venv/bin/python && chmod +x .venv/bin/python"),
        }

        result = review._run_contract_reproducer(
            self.p.root, self.p.root, git(self.p.root, "rev-parse", "HEAD"), ready,
            test_file, "D1", 1, 1)

        self.assertTrue(result["reproduced"], result["output"])
        self.assertEqual(result["source"], source)
        self.assertNotIn("done", result["output"])

    def test_reproducer_substitutes_target_after_shell_setup(self):
        command, error = review._adapt_exit_command(
            "cd . && python3 judge.py", {"judge.py"}, "test_review_D1.py")

        self.assertEqual(error, "")
        self.assertEqual(command, "cd . && python3 test_review_D1.py")

    def test_reproducer_preserves_adjacent_shell_operators(self):
        for original, expected in (
                ("python3 judge.py&&printf done", "python3 test_review_D1.py&&printf done"),
                ("python3 judge.py;printf done", "python3 test_review_D1.py;printf done")):
            with self.subTest(original=original):
                command, error = review._adapt_exit_command(
                    original, {"judge.py"}, "test_review_D1.py")
                self.assertEqual(error, "")
                self.assertEqual(command, expected)

    def test_reproducer_keeps_shell_assignments_and_expansions(self):
        command, error = review._adapt_exit_command(
            'PYTHONPATH="$PWD" python3 judge.py', {"judge.py"}, "test_review_D1.py")

        self.assertEqual(error, "")
        self.assertEqual(command, 'PYTHONPATH="$PWD" python3 test_review_D1.py')

    def test_prepare_failure_is_reported_without_running_candidate(self):
        (self.p.root / "candidate.py").write_text("raise AssertionError('D1')\n")
        result = review._run_contract_reproducer(
            self.p.root, self.p.root, git(self.p.root, "rev-parse", "HEAD"),
            {"checks": [{"type": "tests", "command": "python3 judge.py",
                         "files": ["judge.py"]}],
             "prepare": "printf 'prepare failed' >&2; exit 7"},
            Path("candidate.py"), "D1", 1, 1)

        self.assertFalse(result["reproduced"])
        self.assertTrue(result["preparation_failed"])
        self.assertIn("prepare failed", result["output"])

    def test_failure_classifier_reuses_ready_gate_rule(self):
        output = ("________________ test_D1 ________________\n"
                  "E AssertionError: D1 FileNotFoundError\n")
        self.assertTrue(review.judge_assertion_failed(output, "D1"))
        self.assertFalse(review.judge_has_runner_error(output, 1))
        crash = ("FAIL: test_D1_runner\nRuntimeError: D1 runner crashed\n"
                 "FAIL: test_X9_unrelated\nAssertionError: X9 unrelated\n")
        self.assertTrue(review.judge_assertion_failed(crash, "D1"))
        self.assertTrue(review.judge_assertion_failed(
            "FAIL: test_D1\nRuntimeError: D1 expected AssertionError\n", "D1"))

    def test_javascript_reproducer_selects_its_approved_node_check(self):
        node = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if node.returncode:
            self.skipTest("node is unavailable")
        (self.p.root / "judge_add.py").write_text("print('python judge')\n")
        (self.p.root / "judge_add.js").write_text("process.exit(0)\n")
        git(self.p.root, "add", "judge_add.py", "judge_add.js")
        git(self.p.root, "commit", "--quiet", "-m", "Add frozen JavaScript judge")
        source = 'require("node:assert/strict").fail("D1")\n'
        test_file = Path("test_review_D1.js")
        (self.p.root / test_file).write_text(source)

        result = review._run_contract_reproducer(
            self.p.root, self.p.root, git(self.p.root, "rev-parse", "HEAD"),
            {"checks": [
                {"type": "tests", "command": "python3 judge_add.py",
                 "files": ["judge_add.py"]},
                {"type": "tests", "command": "cd . && node judge_add.js",
                 "files": ["judge_add.js"]},
            ]},
            test_file, "D1", 1, 1)

        self.assertTrue(result["reproduced"], result["output"])
        self.assertEqual(result["source"], source)
