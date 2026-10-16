"""Integration checks for builds, reviews and hand-backs."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import gate
import run
import run_helpers
from helpers import SPEC, git
from loopkit import Refused, changed_check_settings, records
from run_helpers import FAKE_CLAUDE as FAKE_CLAUDE


class RunBuildTest(run_helpers.RunCase):
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

    def test_dirty_build_folder_is_refused_without_cleaning_it(self):
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        folder = run.worktree(self.p.root, n)
        dirty = folder / "person-work.txt"
        dirty.write_text("keep this work\n")
        result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("next:", result)
        self.assertTrue(dirty.is_file())
        self.assertIn("environment: 1", gate.report(self.p.gh))
        handback = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "give-back"][-1]
        self.assert_handback_record(handback, reason_type="environment",
                                    cause="dirty-worktree", attempts=0)

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
        self.assertTrue(body.startswith("## Contract review findings"))
        self.assertIn("D1 is not met", body)
        self.assertTrue(any("judge-gap" in comment for comment in self.p.gh.comments(n)))
        self.assertIn("judge-gap: 1", gate.report(self.p.gh))

    def test_a_good_build_opens_a_pull_request(self):
        n, result = self.build("good")
        self.assertIn("pull request ready", result)
        self.assertIn("state:approval", self.p.gh.issue(n)["labels"])
        self.assertIn(f"piece/{n}", git(self.p.remote, "branch"))

    def test_builder_can_edit_a_protected_path_named_in_the_contract(self):
        self.p.loop_section("true")
        agents_file = self.p.root / "AGENTS.md"
        agents_file.write_text(agents_file.read_text() + "Protected paths: src/auth.py\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Protect auth route")
        git(self.p.root, "push", "--quiet", "origin", "main")
        spec = SPEC.replace("- D1: adding a habit appends it.",
                            "- D1: update src/auth.py to add the auth route control.")
        os.environ["FAKE_MODE"] = "protected"
        n = self.p.piece(spec=spec)
        gate.move(self.p.gh, self.p.root, n, "ready")
        result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("pull request ready", result)
        self.assertEqual((self.p.folder(n) / "src/auth.py").read_text(),
                         "protected change\n")

    def test_builder_cannot_edit_a_protected_path_missing_from_the_contract(self):
        self.p.loop_section("true")
        agents_file = self.p.root / "AGENTS.md"
        agents_file.write_text(agents_file.read_text() + "Protected paths: src/auth.py\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Protect auth route")
        git(self.p.root, "push", "--quiet", "origin", "main")
        os.environ["FAKE_MODE"] = "protected"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("back to shaping", result)
        self.assertFalse((self.p.folder(n) / "src/auth.py").exists())
        self.assertEqual(self.p.gh.prs, {})

    def test_gate_refuses_a_protected_path_missing_from_the_contract(self):
        self.p.loop_section("true")
        agents_file = self.p.root / "AGENTS.md"
        agents_file.write_text(agents_file.read_text() + "Protected paths: src/auth.py\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Protect auth route")
        git(self.p.root, "push", "--quiet", "origin", "main")
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        folder = run.worktree(self.p.root, n)
        (folder / "src").mkdir()
        (folder / "src/auth.py").write_text("protected change\n")
        git(folder, "add", "src/auth.py")
        git(folder, "commit", "--quiet", "-m", "Change protected path")
        passed, output = gate.judge(
            folder, gate.last_record(self.p.gh.comments(n), "ready"))
        self.assertFalse(passed)
        self.assertIn("protected paths", output)

    def test_submit_evidence_includes_a_passing_keep_result(self):
        self.p.loop_section("true")
        n = self.p.piece(spec=SPEC.replace("Files:", "Keep: `true`\nFiles:"))
        gate.move(self.p.gh, self.p.root, n, "ready")
        folder = run.worktree(self.p.root, n)
        os.environ["FAKE_MODE"] = "good"
        fake = Path(os.environ["LOOP_CLAUDE"])
        subprocess.run([str(fake)], cwd=folder, check=True, env={**os.environ,
                       "LOOP_BUILDER": "1"})
        run.commit_leftovers(folder, n, 1)
        passed, output = gate.judge(folder, gate.last_record(self.p.gh.comments(n), "ready"))
        self.assertTrue(passed, output)
        self.assertIn("Keep: true", output)

    def test_a_failing_build_goes_back_to_shaping(self):
        n, result = self.build("bad")
        self.assertIn("back to shaping", result)
        labels = self.p.gh.issue(n)["labels"]
        self.assertIn("state:shaping", labels)
        self.assertIn("needs-you", labels)
        handback = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "give-back"][-1]
        self.assert_handback_record(handback, reason_type="builder-failed",
                                    cause="judge-failed", attempts=2)
        failed = [c for c in self.p.gh.comments(n) if c.startswith("**Run:** attempt")]
        self.assertEqual(len(failed), 2)
        self.assertIn("The builder said:", failed[0])
        self.assertIn("built", failed[0])  # the stand-in's own words reach the issue

    def test_a_build_never_commits_generated_files(self):
        run.gate.ignore_loop_folder(self.p.root)
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        fake = Path(os.environ["LOOP_CLAUDE"])
        fake.write_text(fake.read_text().replace("git add -A", "mkdir -p __pycache__ && touch __pycache__/x.pyc && git add -A"))
        run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertNotIn("__pycache__", git(self.p.root, "ls-tree", "-r", "--name-only", f"piece/{n}"))

    def test_the_run_prepares_the_build_folder_first(self):
        self.p.loop_section("true", prepare="touch prepared.txt")
        n, result = self.build("good", attempts=1)
        self.assertIn("pull request ready", result)
        self.assertTrue((self.p.folder(n) / "prepared.txt").exists())

    def test_prepare_output_is_excluded_from_the_piece_branch(self):
        self.p.loop_section("true", prepare="mkdir -p .venv/lib && touch .venv/lib/python.py")
        n, result = self.build("good", attempts=1)
        self.assertIn("pull request ready", result, self.p.gh.comments(n))
        self.assertNotIn(".venv/", git(self.p.root, "ls-tree", "-r", "--name-only", f"piece/{n}"))
        exclude = Path(git(self.p.folder(n), "rev-parse", "--path-format=absolute",
                           "--git-path", "info/exclude"))
        self.assertIn(".venv/", exclude.read_text())

    def test_gate_refuses_additions_under_prepare_output_paths(self):
        self.p.loop_section("true", prepare="mkdir -p .venv/lib && touch .venv/lib/python.py")
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        fake = Path(os.environ["LOOP_CLAUDE"])
        fake.write_text(fake.read_text().replace(
            "git add -A", "touch .venv/lib/forced.py && git add -f .venv/lib/forced.py && git add -A"))
        result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("back to shaping", result)
        failed = [c for c in self.p.gh.comments(n) if c.startswith("**Run:** attempt")]
        self.assertIn("Prepare created", failed[-1])
        self.assertEqual(self.p.gh.prs, {})

    def test_keep_failing_on_the_judge_files_stops_the_piece_at_once(self):
        # A lint step in the keep check rejects the judge file itself. No build can fix that.
        (self.p.root / "lint.py").write_text(
            "import os, sys\n"
            "if os.path.exists('judge_add.py'):\n"
            "    print('judge_add.py: assertion inside a loop')\n"
            "    sys.exit(1)\n")
        git(self.p.root, "add", "lint.py")
        git(self.p.root, "commit", "--quiet", "-m", "Lint")
        git(self.p.root, "push", "--quiet", "origin", "main")
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece(spec=SPEC.replace("Files:", "Keep: `python3 lint.py`\nFiles:"))
        gate.move(self.p.gh, self.p.root, n, "ready")
        result = run.build_piece(self.p.gh, self.p.root, n, 3)
        self.assertIn("fails on the judge files themselves", result)
        self.assertIn("state:shaping", self.p.gh.issue(n)["labels"])
        handback = [r for r in records(self.p.gh.comments(n))
                    if r.get("move") == "give-back"][-1]
        self.assert_handback_record(handback, reason_type="bar-wrong",
                                    cause="bar-wrong", attempts=1)

    def test_builder_bar_wrong_outcome_returns_on_first_attempt(self):
        n, result = self.build("bar-wrong", attempts=3)
        self.assertIn("The judge contradicts", result)
        seen = records(self.p.gh.comments(n))
        handbacks = [r for r in seen if r.get("move") == "give-back"]
        self.assertEqual(len(handbacks), 1)
        self.assert_handback_record(handbacks[0], reason_type="bar-wrong",
                                    cause="bar-wrong", attempts=1)
        attempts = [c for c in self.p.gh.comments(n) if c.startswith("**Run:** attempt")]
        self.assertEqual(len(attempts), 1)
        # The build folder is gone, so shaping can switch to the branch; the work stays on it.
        self.assertFalse(self.p.folder(n).exists())
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        git(self.p.root, "switch", "--quiet", "main")

    def test_a_stale_outcome_is_cleared_before_attempt_one(self):
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        folder = run.worktree(self.p.root, n)
        (folder / ".loop").mkdir(exist_ok=True)
        (folder / ".loop" / "outcome").write_text("bar-wrong\nstale result\n")
        result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("pull request ready", result)
        submit = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "submit"][-1]
        self.assertEqual(submit["attempts"], 1)
        self.assertGreaterEqual(submit["seconds"], 0)
        self.assertIn("passed on the first attempt: 1 / 1 (100%)", gate.report(self.p.gh))

    def test_stop_records_stopped_and_report_counts_it(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        (self.p.root / ".loop").mkdir(exist_ok=True)
        (self.p.root / ".loop" / "stop").write_text("stop\n")
        result = run.build_piece(self.p.gh, self.p.root, n, 2)
        self.assertIn("person asked the run to stop", result)
        handbacks = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "give-back"]
        self.assert_handback_record(handbacks[0], reason_type="stopped",
                                    cause="stopped", attempts=0,
                                    seconds_positive=False)
        self.assertIn("stopped: 1", gate.report(self.p.gh))

    def test_stop_keeps_the_previous_judge_failure_reason(self):
        with patch("run.stop_requested", side_effect=[False, True]):
            n, result = self.build("bad", attempts=3)
        self.assertIn("back to shaping", result)
        handback = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "give-back"][-1]
        self.assert_handback_record(handback, reason_type="stopped",
                                    cause="stopped", attempts=1)
        self.assertTrue(handback["reason"].startswith("Attempt 1 failed."))

    def test_run_refuses_lock_with_a_live_orphan_process_group(self):
        sleeper = subprocess.Popen(["sleep", "30"], start_new_session=True)
        def stop_sleeper():
            if sleeper.poll() is None:
                sleeper.kill()
            sleeper.wait()
        self.addCleanup(stop_sleeper)
        lock = run.lock_path(self.p.root)
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({"pid": 2147483647, "started_at": 0,
                                    "children": [sleeper.pid]}))
        with self.assertRaises(Refused) as refused:
            run.acquire_lock(self.p.root)
        self.assertIn("orphan", refused.exception.reason)

    def test_quality_probe_cache_key_includes_command_and_main_commit(self):
        base = gate.quality_probe_path(self.p.root, 7, "coverage run", "main-a")
        self.assertEqual(base, gate.quality_probe_path(self.p.root, 7, "coverage run", "main-a"))
        self.assertNotEqual(base, gate.quality_probe_path(self.p.root, 7, "mutmut", "main-a"))
        self.assertNotEqual(base, gate.quality_probe_path(self.p.root, 7, "coverage run", "main-b"))

    def test_run_kills_tracked_process_groups_on_interrupt(self):
        sleeper = subprocess.Popen(["sleep", "30"], start_new_session=True)
        def stop_sleeper():
            if sleeper.poll() is None:
                sleeper.kill()
            sleeper.wait()
        self.addCleanup(stop_sleeper)
        run.track_process(sleeper, self.p.root)
        self.assertTrue(run.kill_active_processes())
        sleeper.wait(timeout=2)
        self.assertNotEqual(sleeper.returncode, 0)

    def test_an_error_after_the_claim_gives_the_piece_back(self):
        def broken(*args, **kwargs):
            raise RuntimeError("git push failed: rejected")
        original = run.open_pull_request
        run.open_pull_request = broken
        self.addCleanup(setattr, run, "open_pull_request", original)
        n, result = self.build("good")
        self.assertIn("the run stopped with an error", result)
        labels = self.p.gh.issue(n)["labels"]
        self.assertIn("state:shaping", labels)
        self.assertIn("needs-you", labels)
        handback = [r for r in records(self.p.gh.comments(n))
                    if r.get("move") == "give-back"][-1]
        self.assertEqual(handback["cause"], "other")

    def test_pull_request_creation_error_is_not_a_person_rejection(self):
        def fail_create_pr(*args, **kwargs):
            raise RuntimeError("GitHub is unavailable")

        with patch.object(self.p.gh, "create_pr", side_effect=fail_create_pr):
            n, result = self.build("good", attempts=1)
        self.assertIn("GitHub is unavailable", result)
        rejection = [r for r in records(self.p.gh.comments(n))
                     if r.get("move") == "reject"][-1]
        self.assertEqual(rejection["cause"], "pull-request-failed")
        self.assertEqual(rejection["type"], "environment")
        self.assertEqual(rejection["reason"], "pull request creation failed after submit")
        self.assertEqual(rejection["attempts"], 1)
        self.assertGreater(rejection["seconds"], 0)
        self.assertEqual(rejection["kit"], "1.2.0")
        self.assertRegex(rejection["date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_a_pushed_branch_is_never_rewritten(self):
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        git(self.p.root, "push", "--quiet", "origin", f"piece/{n}")
        # Shaping rebuilt the branch from main after a rejection: GitHub keeps the old commits.
        git(self.p.root, "switch", "--quiet", f"piece/{n}")
        git(self.p.root, "commit", "--quiet", "--amend", "-m", "Judge, rewritten")
        git(self.p.root, "switch", "--quiet", "main")
        gate.move(self.p.gh, self.p.root, n, "ready")
        with self.assertRaises(Refused) as r:
            run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("never rewritten", r.exception.reason)
        self.assertIn("state:ready", self.p.gh.issue(n)["labels"])

    def test_a_rebuild_tells_the_builder_why_the_piece_came_back(self):
        n, _ = self.build("good")
        gate.move(self.p.gh, self.p.root, n, "shaping",
                  reason="it turned off a lint rule for the whole project",
                  reason_type="person-rejected")
        gate.move(self.p.gh, self.p.root, n, "ready")
        gate.move(self.p.gh, self.p.root, n, "building")
        gate.move(self.p.gh, self.p.root, n, "shaping", reason="the push failed",
                  reason_type="environment")
        reason = run.came_back_reason(self.p.gh.comments(n))
        self.assertEqual(reason, "- it turned off a lint rule for the whole project\n- the push failed")
        ready = {"files": ["judge_add.py"], "command": "python3 judge_add.py"}
        self.assertIn(reason, run.brief(n, "spec", ready, "", reason))
        self.assertEqual(run.came_back_reason([]), "")

    def test_a_build_that_changes_check_settings_does_not_pass(self):
        n, result = self.build("loosen", attempts=1)
        self.assertIn("back to shaping", result)
        failed = [c for c in self.p.gh.comments(n) if c.startswith("**Run:** attempt")]
        self.assertIn(".eslintrc.json", failed[0])
        self.assertEqual(self.p.gh.prs, {})

    def test_a_piece_may_change_settings_when_its_spec_says_so(self):
        os.environ["FAKE_MODE"] = "loosen"
        n = self.p.piece(spec=SPEC.replace("Files:", "Settings: may change\nFiles:"))
        gate.move(self.p.gh, self.p.root, n, "ready")
        result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("pull request ready", result)
        self.assertIn("- `.eslintrc.json`", self.p.gh.prs[f"piece/{n}"]["body"])

    def test_check_settings_inside_package_json_and_pyproject(self):
        (self.p.root / "package.json").write_text(
            '{"name": "x", "dependencies": {}, "xo": {"rules": {}}, "scripts": {"test": "xo && ava"}}')
        (self.p.root / "pyproject.toml").write_text("[project]\nname = 'x'\n[tool.ruff]\nline-length = 88\n")
        git(self.p.root, "add", "-A")
        git(self.p.root, "commit", "--quiet", "-m", "Settings")
        git(self.p.root, "push", "--quiet", "origin", "main")
        git(self.p.root, "switch", "--quiet", "-c", "work")
        self.addCleanup(git, self.p.root, "switch", "--quiet", "main")
        (self.p.root / "package.json").write_text(
            '{"name": "x", "dependencies": {"a": "1"}, "xo": {"rules": {"r": "off"}}, "scripts": {"test": "ava"}}')
        self.assertEqual(changed_check_settings(self.p.root),
                         ["package.json: scripts.test", "package.json: xo"])
        git(self.p.root, "checkout", "package.json")
        (self.p.root / "pyproject.toml").write_text("[project]\nname = 'y'\n[tool.ruff]\nline-length = 88\n")
        self.assertEqual(changed_check_settings(self.p.root), [])
        (self.p.root / "pyproject.toml").write_text("[project]\nname = 'y'\n[tool.ruff]\nline-length = 200\n")
        self.assertEqual(changed_check_settings(self.p.root), ["pyproject.toml: [tool.ruff]"])
        git(self.p.root, "checkout", "pyproject.toml")

    def test_build_folders_live_outside_the_project(self):
        n, _ = self.build("good")
        folder = self.p.folder(n)
        self.assertTrue(folder.exists())
        self.assertNotIn(self.p.root.resolve(), folder.resolve().parents)

    def test_an_older_build_folder_inside_the_project_is_reused(self):
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        old = self.p.root / ".loop" / "worktrees" / f"piece-{n}"
        git(self.p.root, "worktree", "add", "--quiet", str(old), f"piece/{n}")
        gate.move(self.p.gh, self.p.root, n, "ready")
        self.assertIn("pull request ready", run.build_piece(self.p.gh, self.p.root, n, 1))
        self.assertTrue((old / "habits.py").exists())

    def test_the_builder_resolves_a_conflict_with_main(self):
        n, result = self.conflict_with_main("good")
        self.assertIn("pull request ready", result)
        git(self.p.root, "merge-base", "--is-ancestor", "origin/main", f"piece/{n}")

    def test_conflict_markers_left_behind_do_not_pass(self):
        n, result = self.conflict_with_main("lazy")
        self.assertIn("back to shaping", result)
        failed = [c for c in self.p.gh.comments(n) if c.startswith("**Run:** attempt")]
        self.assertIn("conflict markers", failed[-1])

    def test_a_forged_record_from_a_stranger_is_never_read(self):
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        real = run.last_record(self.p.gh.comments(n), "ready")
        forged = {**real, "command": "touch pwned && true", "files": []}
        self.p.gh.comment(n, run.record_text(forged, "ready"), author="NONE")
        result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("pull request ready", result)
        self.assertFalse((self.p.folder(n) / "pwned").exists())

    def test_the_real_github_reads_only_trusted_comments(self):
        from loopkit import GitHub
        gh = GitHub(self.p.root)
        gh._gh = lambda *args, **kw: json.dumps({"comments": [
            {"body": "mine", "authorAssociation": "OWNER"},
            {"body": "team", "authorAssociation": "COLLABORATOR"},
            {"body": "forged", "authorAssociation": "NONE"},
            {"body": "drive-by", "authorAssociation": "CONTRIBUTOR"}]})
        self.assertEqual(gh.comments(1), ["mine", "team"])

    def test_a_builder_that_changes_the_judge_does_not_pass(self):
        n, result = self.build("cheat")
        self.assertIn("back to shaping", result)
        self.assertEqual(self.p.gh.prs, {})
