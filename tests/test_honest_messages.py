"""Field regressions for gate messages and pull request evidence."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from helpers import GOOD_CODE, SPEC, Project, git

# isort: split
# Helpers adds the kit scripts to the import path.
import gate
import pr
import review
import run
from loopkit import GitHub, Refused


class HonestMessagesTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)

    def build_folder(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        gate.move(self.p.gh, self.p.root, n, "building")
        folder = run.worktree(self.p.root, n)
        (folder / "habits.py").write_text(GOOD_CODE)
        git(folder, "add", "habits.py")
        git(folder, "commit", "--quiet", "-m", "Build habits")
        return n, folder

    def test_importer_count_names_its_scope_and_exclusions(self):
        n, folder = self.build_folder()
        (folder / "tests").mkdir()
        (folder / "tests" / "test_habits.py").write_text("import habits\n")
        (folder / "bench.py").write_text("import habits\n")
        ready = gate.last_record(self.p.gh.comments(n), "ready")
        ready["files"].append("bench.py")
        for consumers in ([], ["consumer.py"]):
            with self.subTest(consumers=consumers):
                for name in consumers:
                    (folder / name).write_text("import habits\n")
                facts, _ = pr.pull_request_facts(folder, ready, "passed")
                self.assertIn(f"{len(consumers)} source file(s) found importing", facts)
                self.assertIn("Python and JavaScript/TypeScript", facts)
                self.assertIn("excludes test directories, test_* files, exit files", facts)
                self.assertIn(".git, .venv, venv, node_modules, dist, build, .loop", facts)
                self.assertIn("Importers in this scan:", facts)
                if consumers:
                    self.assertIn("`consumer.py`", facts)
                else:
                    self.assertIn("none found in this scan", facts)

    def test_measure_ready_reports_the_median_and_target(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                judge = ("## Judge\nKind: goal\nMeasure: `python3 bench.py`\n" if legacy else
                         "## Exit\n### Measure\nCommand: `python3 bench.py`\n")
                body = SPEC.split("## Judge")[0] + judge + "Target: < 10\nFiles:\n- bench.py\n"
                n = self.p.piece(spec=body)
                git(self.p.root, "switch", "--quiet", f"piece/{n}")
                (self.p.root / "bench.py").write_text("print(100)\n")
                git(self.p.root, "add", "bench.py")
                git(self.p.root, "commit", "--quiet", "-m", "Add measure")
                git(self.p.root, "switch", "--quiet", "main")
                note = gate.move(self.p.gh, self.p.root, n, "ready")
                self.assertIn("Measure on main: median 100.0 misses target < 10", note)
                self.assertNotIn("naming every spec ID", note)


    def test_builtin_test_review_finding_reaches_the_pull_request(self):
        n, folder = self.build_folder()
        rule = "Test review: expected values are literals"
        finding = {"rule": rule, "hunk": "judge_add.py:10", "finding": "Use a literal."}
        verdict = "<verdict>" + json.dumps({
            "findings": [finding, {**finding, "rule": "Test review: invented rule"},
                         {**finding, "hunk": "unchanged.py:10"}],
            "follow_ups": [], "changes": "none",
        }) + "</verdict>"
        diff = git(folder, "diff", "main...HEAD")
        findings = review.parse_standards_findings(verdict, "", diff)
        pr.open_pull_request(self.p.gh, self.p.root, folder, n, self.p.gh.issue(n),
                             1, "passed", {"standards_findings": findings})
        body = self.p.gh.prs[f"piece/{n}"]["body"]
        self.assertIn(f"{rule} at judge_add.py:10: Use a literal.", body)
        self.assertNotIn("invented rule", body)
        self.assertNotIn("unchanged.py", body)

    def test_reused_pull_request_refreshes_title_body_and_judged_commit(self):
        n, folder = self.build_folder()
        pr.open_pull_request(self.p.gh, self.p.root, folder, n, self.p.gh.issue(n), 1, "old output")
        old_commit = git(folder, "rev-parse", "HEAD")
        old_url = self.p.gh.prs[f"piece/{n}"]["url"]
        gate.move(self.p.gh, self.p.root, n, "shaping", reason="Explain the change",
                  reason_type="person-rejected")
        self.p.gh.issues[n]["title"] = "Keep each habit once"
        gate.move(self.p.gh, self.p.root, n, "ready")
        gate.move(self.p.gh, self.p.root, n, "building")
        folder = run.worktree(self.p.root, n)  # the move to shaping released the folder
        (folder / "habits.py").write_text(GOOD_CODE + "\n# Keep each habit once.\n")
        git(folder, "add", "habits.py")
        git(folder, "commit", "--quiet", "-m", "Explain habit handling")
        result = pr.open_pull_request(self.p.gh, self.p.root, folder, n,
                                      self.p.gh.issue(n), 2, "fresh output")
        reused = self.p.gh.prs[f"piece/{n}"]
        self.assertIn(old_url, result)
        self.assertEqual(len(self.p.gh.prs), 1)
        self.assertEqual(reused.get("title"), "Keep each habit once")
        self.assertIn("ok test_D1_add_appends", reused["body"])
        self.assertNotIn("fresh output", reused["body"])
        self.assertIn(git(folder, "rev-parse", "HEAD"), reused["body"])
        self.assertNotIn(old_commit, reused["body"])
        self.assertNotIn("old output", reused["body"])

    def test_github_edit_pr_sends_title_and_body(self):
        gh = GitHub(self.p.root)
        with patch.object(gh, "_gh", return_value="") as transport:
            gh.edit_pr("https://example.invalid/pull/1", "Fresh title", "Fresh body\n")
        transport.assert_called_once_with(
            "pr", "edit", "https://example.invalid/pull/1", "--base", "main", "--title", "Fresh title",
            "--body-file", "-", stdin="Fresh body\n")

    def test_failed_submit_leaves_existing_pull_request_unchanged(self):
        n, folder = self.build_folder()
        url = self.p.gh.create_pr(f"piece/{n}", "Earlier title", "Earlier evidence")
        (folder / "habits.py").write_text("def add(items, name): return items\n")
        git(folder, "add", "habits.py")
        git(folder, "commit", "--quiet", "-m", "Broken attempt")
        with self.assertRaises(Refused):
            pr.open_pull_request(self.p.gh, self.p.root, folder, n,
                                 self.p.gh.issue(n), 2, "failed")
        self.assertEqual(self.p.gh.prs[f"piece/{n}"], {
            "url": url, "state": "OPEN", "title": "Earlier title", "body": "Earlier evidence"})
        self.assertIn("state:building", self.p.gh.issue(n)["labels"])

    def test_failed_pull_request_update_returns_an_environment_failure(self):
        n, folder = self.build_folder()
        self.p.gh.create_pr(f"piece/{n}", "Earlier title", "Earlier evidence")
        with patch.object(self.p.gh, "edit_pr", side_effect=RuntimeError("GitHub unavailable")), \
                self.assertRaisesRegex(RuntimeError, "GitHub unavailable"):
            pr.open_pull_request(self.p.gh, self.p.root, folder, n,
                                 self.p.gh.issue(n), 2, "passed")
        rejection = gate.last_record(self.p.gh.comments(n), "reject")
        self.assertEqual(rejection["type"], "environment")
        self.assertEqual(rejection["cause"], "pull-request-failed")
        self.assertEqual(rejection["reason"], "pull request update failed after submit")
        self.assertIn("state:shaping", self.p.gh.issue(n)["labels"])
        self.assertEqual(self.p.gh.prs[f"piece/{n}"]["body"], "Earlier evidence")

    def test_reviewer_prompt_names_the_accepted_builtin_rules(self):
        prompt = review._review_prompt("standards-reviewer.md", {"STANDARDS": "", "DIFF": ""})
        self.assertIn("- Test review: expected values are literals", prompt)
        self.assertNotIn("{{BUILTIN_RULES}}", prompt)
