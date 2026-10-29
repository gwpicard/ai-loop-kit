"""Reviewer verdicts and checked reviewer fixes."""
from __future__ import annotations

from helpers import git

# isort: split

import os
import unittest
from unittest.mock import patch

import gate
import run
from loopkit import records
from run_fixtures import RunFixture


class RunTest(RunFixture, unittest.TestCase):
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

    def test_last_tagged_verdict_accepts_a_code_fence_and_checks_fields(self):
        output = ('<verdict>{"findings":[],"follow_ups":[],"changes":"old"}</verdict>\n'
                  '<verdict>```json\n{"findings":[],"follow_ups":[],"changes":"none"}\n```</verdict>')
        from review import _last_verdict
        self.assertEqual(_last_verdict(output, "standards")["changes"], "none")
        with self.assertRaises(ValueError):
            _last_verdict("<verdict>{bad}</verdict>", "contract")

    def test_both_reviewers_run_without_a_project_standards_file(self):
        n, result = self.build("good", attempts=1)
        self.assertIn("pull request ready", result)
        logs = self.p.root / ".loop" / "logs"
        self.assertTrue((logs / f"piece-{n}-standards-review.log").is_file())
        self.assertTrue((logs / f"piece-{n}-contract-review.log").is_file())

    def test_both_reviewers_see_earlier_build_code_but_not_the_exit_files(self):
        import review
        import run
        prompts = []
        session = review._review_session

        def observe(folder, prompt, *args, **kwargs):
            prompts.append(prompt)
            return session(folder, prompt, *args, **kwargs)

        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "earlier.py").write_text("EARLIER = 1\n")
        git(self.p.root, "add", "earlier.py")
        git(self.p.root, "commit", "--quiet", "-m", "Earlier build")
        git(self.p.root, "switch", "--quiet", "main")
        gate.move(self.p.gh, self.p.root, n, "ready")
        with patch("review._review_session", side_effect=observe):
            result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("pull request ready", result)
        self.assertEqual(len(prompts), 2)
        for prompt in prompts:
            diff = prompt.split("## Diff", 1)[1].split("## Frozen baseline", 1)[0]
            self.assertIn("earlier.py", diff)
            self.assertIn("habits.py", diff)
            self.assertNotIn("judge_add.py", diff)

    def test_idle_reviewer_is_recorded_as_builder_failed(self):
        os.environ["FAKE_REVIEW_MODE"] = "review-idle"
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Idle limit: 1\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Set short idle limit")
        git(self.p.root, "push", "--quiet", "origin", "main")
        with patch("review.idle_limit_seconds", return_value=1):
            n, result = self.build("good", attempts=1)
        self.assertIn("standards reviewer idle", result)
        self.assertIn("builder-failed: 1", gate.report(self.p.gh))

    def test_bad_reviewer_verdict_fails_with_raw_tail_and_environment_record(self):
        os.environ["FAKE_REVIEW_MODE"] = "bad-verdict"
        n, result = self.build("good", attempts=1)
        self.assertIn("invalid verdict", result)
        self.assertIn("environment: 1", gate.report(self.p.gh))
        log = self.p.root / ".loop" / "logs" / f"piece-{n}-standards-review.log"
        self.assertIn("<verdict>{bad json}</verdict>", log.read_text())
        self.assertIn("Raw tail:", log.read_text())

    def test_standards_reviewer_changes_are_committed_and_judged(self):
        (self.p.root / "standards.md").write_text("Use small local changes.\n")
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Standards: standards.md\n")
        git(self.p.root, "add", "AGENTS.md", "standards.md")
        git(self.p.root, "commit", "--quiet", "-m", "Add review standards")
        git(self.p.root, "push", "--quiet", "origin", "main")
        os.environ["FAKE_REVIEW_MODE"] = "standard-fix"
        n, result = self.build("good", attempts=1)
        self.assertIn("pull request ready", result)
        self.assertIn("reviewed", (self.p.folder(n) / "habits.py").read_text())
        changed_by_reviewer = git(self.p.folder(n), "show", "--format=", "--name-only", "HEAD").strip()
        self.assertEqual(changed_by_reviewer, "habits.py")
        self.assertIn("Reviewer fixes kept", self.p.gh.prs[f"piece/{n}"]["body"])

    def test_failing_reviewer_fixes_are_left_out_of_the_pull_request(self):
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Standards: standards.md\n")
        (self.p.root / "standards.md").write_text("Use small local changes.\n")
        git(self.p.root, "add", "AGENTS.md", "standards.md")
        git(self.p.root, "commit", "--quiet", "-m", "Add review standards")
        git(self.p.root, "push", "--quiet", "origin", "main")
        os.environ["FAKE_REVIEW_MODE"] = "standard-break"
        n, result = self.build("good", attempts=1)
        self.assertIn("pull request ready", result)
        self.assertIn("return items if", (self.p.folder(n) / "habits.py").read_text())
        self.assertIn("Reviewer fixes were dropped", self.p.gh.prs[f"piece/{n}"]["body"])

    def test_contract_review_gap_is_recorded_and_heads_the_pull_request(self):
        os.environ["FAKE_REVIEW_MODE"] = "contract-gap"
        n, result = self.build("good", attempts=1)
        self.assertIn("pull request ready", result)
        body = self.p.gh.prs[f"piece/{n}"]["body"]
        self.assertTrue(body.startswith("## Unresolved review findings"))
        self.assertIn("D1 is not met", body)
        self.assertFalse(any("judge-gap" in comment for comment in self.p.gh.comments(n)))
        self.assertIn("judge-gap: 0", gate.report(self.p.gh))

    def earlier_build(self, code):
        """A piece made ready, then given earlier build code on its branch."""
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        (self.p.root / "habits.py").write_text(code)
        git(self.p.root, "add", "habits.py")
        git(self.p.root, "commit", "--quiet", "-m", "Earlier build")
        git(self.p.root, "switch", "--quiet", "main")
        return n

    GOOD = "def add(items, name):\n    return items if name in items else items + [name]\n"

    def test_a_passing_earlier_build_goes_straight_to_review(self):
        n = self.earlier_build(self.GOOD)
        with patch("run.build_once") as builder:
            result = run.build_piece(self.p.gh, self.p.root, n, 2)
        builder.assert_not_called()
        self.assertIn("pull request ready", result)
        self.assertIn(f"piece/{n}", self.p.gh.prs)
        submit = [r for r in records(self.p.gh.comments(n)) if r["move"] == "submit"][-1]
        self.assertEqual(submit["attempts"], 0)
        self.assertIn("passed on the first attempt: 0 / 1", gate.report(self.p.gh))

    def test_a_failing_earlier_build_starts_attempt_one_with_the_gate_output(self):
        n = self.earlier_build("def add(items, name):\n    return items\n")
        prompts = []
        build_once = run.build_once

        def observe(folder, prompt, *args, **kwargs):
            prompts.append(prompt)
            return build_once(folder, prompt, *args, **kwargs)

        with patch("run.build_once", side_effect=observe):
            result = run.build_piece(self.p.gh, self.p.root, n, 2)
        self.assertIn("pull request ready", result)
        self.assertEqual(len(prompts), 1)
        self.assertIn("The earlier build code failed", prompts[0])
        self.assertIn("judge_add.py", prompts[0])

    def test_a_reviewer_that_fails_once_costs_one_builder_session(self):
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        sessions = []
        build_once = run.build_once

        def count(*args, **kwargs):
            sessions.append(1)
            return build_once(*args, **kwargs)

        with patch("run.build_once", side_effect=count), \
                patch("review._review_session", side_effect=OSError("cannot start")):
            run.build_piece(self.p.gh, self.p.root, n, 2)
        self.assertIn("state:ready", self.p.gh.issue(n)["labels"])
        with patch("run.build_once", side_effect=count):
            result = run.build_piece(self.p.gh, self.p.root, n, 2)
        self.assertIn("pull request ready", result)
        self.assertEqual(len(sessions), 1)
        moves = [r["move"] for r in records(self.p.gh.comments(n))]
        self.assertNotIn("give-back", moves)
