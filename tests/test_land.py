"""With Base merges: run, the run merges a gated piece into the base branch, never main."""
from __future__ import annotations

from helpers import KIT, SPEC, Project, git

# isort: split

import json
import re
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import doctor
import gate
import landing
import loopkit
import run
import walkaway
from loopkit import GitHub, Refused


class LandFixture:
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.p.loop_section("printf baseline")
        self.setting("Base branch: trip\nBase merges: run\n")
        git(self.p.root, "branch", "trip")
        git(self.p.root, "push", "--quiet", "origin", "trip")
        self.p.gh.on_merge = self.merge_on_origin

    def setting(self, lines):
        agents = self.p.root / "AGENTS.md"
        text = re.sub(r"Base (branch|merges):.*\n", "", agents.read_text())
        agents.write_text(text + lines)
        git(self.p.root, "commit", "--quiet", "-am", "Loop settings")
        git(self.p.root, "push", "--quiet", "origin", "main")

    def merge_on_origin(self, branch, base):
        git(self.p.root, "fetch", "--quiet", "origin")
        git(self.p.root, "switch", "--quiet", base)
        git(self.p.root, "merge", "--quiet", "--no-ff", "-m", "Merge", f"origin/{branch}")
        git(self.p.root, "push", "--quiet", "origin", base)
        git(self.p.root, "switch", "--quiet", "main")

    def gated(self, files=None):
        """A piece built on trip, pushed, in approval with an open pull request."""
        n = self.p.gh.create_issue("A piece", SPEC, ["state:approval"])
        folder = self.p.root.parent / f"build-{n}"
        git(self.p.root, "worktree", "add", "--quiet", "-b", f"piece/{n}", str(folder), "trip")
        for name, text in (files or {"habits.py": "ADD = 1\n"}).items():
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            (folder / name).write_text(text)
        git(folder, "add", "-A")
        git(folder, "commit", "--quiet", "-m", "Build")
        git(folder, "push", "--quiet", "-u", "origin", f"piece/{n}")
        url = f"https://example.invalid/pull/{n}"
        self.p.gh.prs[f"piece/{n}"] = {"url": url, "state": "OPEN", "base": "trip"}
        return n, folder, f"piece {n}: pull request ready for you: {url}"

    def land(self, n, folder, result, review=None):
        return landing.land(self.p.gh, self.p.root, folder, n, result, review or {})


class LandTest(LandFixture, unittest.TestCase):
    def test_a_gated_piece_is_merged_into_the_base_and_done(self):
        n, folder, result = self.gated()
        line = self.land(n, folder, result)
        self.assertEqual(line, f"piece {n}: merged into trip: https://example.invalid/pull/{n}")
        self.assertEqual(self.p.gh.merges,
                         [(f"https://example.invalid/pull/{n}", "trip", git(folder, "rev-parse", "HEAD"))])
        self.assertEqual(gate.state_of(self.p.gh.issue(n)), "done")
        self.assertEqual(self.p.gh.issue(n)["state"], "CLOSED")
        self.assertIn("habits.py", git(self.p.root, "ls-tree", "--name-only", "origin/trip"))

    def test_without_the_setting_nothing_is_merged(self):
        self.setting("Base branch: trip\n")
        n, folder, result = self.gated()
        self.assertEqual(self.land(n, folder, result), result)
        self.assertEqual(self.p.gh.merges, [])

    def test_a_main_base_never_merges_even_with_the_setting(self):
        self.setting("Base merges: run\n")
        n, folder, result = self.gated()
        self.assertEqual(self.land(n, folder, result), result)
        self.assertEqual(self.p.gh.merges, [])

    def test_a_bad_setting_is_named_and_nothing_merges(self):
        self.setting("Base branch: trip\nBase merges: always\n")
        n, folder, result = self.gated()
        self.assertIn("Not merged: Base merges must be person or run", self.land(n, folder, result))
        self.assertEqual(self.p.gh.merges, [])

    def test_unresolved_contract_findings_leave_the_piece_for_the_person(self):
        n, folder, result = self.gated()
        line = self.land(n, folder, result, {"contract_findings": ["D2 is missing"]})
        self.assertIn("Not merged: the contract review left findings", line)
        self.assertEqual(self.p.gh.merges, [])
        self.assertEqual(gate.state_of(self.p.gh.issue(n)), "approval")

    def test_files_that_run_code_are_left_for_the_person_with_the_reason(self):
        for name in (".github/workflows/ci.yml", ".githooks/pre-commit", "AGENTS.md"):
            with self.subTest(name=name):
                n, folder, result = self.gated({name: "changed\n"})
                line = self.land(n, folder, result)
                self.assertIn(f"Not merged: It changes {name}.", line)
                self.assertIn("secrets", line)
                self.assertIn(f"**Run:** not merged into `trip`. It changes {name}.",
                              self.p.gh.comments(n)[-1])
        self.assertEqual(self.p.gh.merges, [])

    def test_a_base_that_moved_after_the_gate_is_not_merged(self):
        n, folder, result = self.gated()
        other = self.p.root.parent / "other"
        git(self.p.root, "worktree", "add", "--quiet", "-b", "person-edit", str(other), "origin/trip")
        (other / "notes.txt").write_text("pushed by the person\n")
        git(other, "add", "-A")
        git(other, "commit", "--quiet", "-m", "Person pushes to trip")
        git(other, "push", "--quiet", "origin", "person-edit:trip")
        self.assertIn("Not merged: trip moved after the gate passed", self.land(n, folder, result))
        self.assertEqual(self.p.gh.merges, [])

    def test_a_refused_merge_leaves_the_piece_in_approval(self):
        self.p.gh.merge_error = "is not mergeable: the merge commit cannot be cleanly created"
        n, folder, result = self.gated()
        line = self.land(n, folder, result)
        self.assertIn("Not merged: is not mergeable", line)
        self.assertEqual(gate.state_of(self.p.gh.issue(n)), "approval")

    def test_a_merge_that_errors_after_merging_still_finishes_the_piece(self):
        n, folder, result = self.gated()

        def merged_then_error(url, base, head):
            self.p.gh.prs[f"piece/{n}"]["state"] = "MERGED"
            raise RuntimeError("gh timed out")

        with patch.object(self.p.gh, "merge_pr", side_effect=merged_then_error):
            line = self.land(n, folder, result)
        self.assertTrue(line.startswith(f"piece {n}: merged into trip"), line)
        self.assertEqual(gate.state_of(self.p.gh.issue(n)), "done")

    def test_a_done_move_that_fails_after_the_merge_says_to_sync(self):
        n, folder, result = self.gated()
        with patch.object(gate, "move", side_effect=Refused("labels are wrong")):
            line = self.land(n, folder, result)
        self.assertIn("merged into trip, but the gate could not mark it done", line)
        self.assertIn("gate.py sync", line)


class MergeGuardTest(unittest.TestCase):
    """The real GitHub.merge_pr, with gh replaced."""

    def merge(self, view, base="trip", default="main"):
        github = GitHub(KIT)
        answers = [json.dumps(view), default + "\n", ""]
        with patch.object(github, "_gh", side_effect=answers) as call:
            github.merge_pr("https://example.invalid/pull/3", base, "abc123")
        return call.call_args_list

    def test_merges_only_with_the_allowed_arguments(self):
        calls = self.merge({"baseRefName": "trip", "headRefName": "piece/3", "state": "OPEN"})
        self.assertEqual(calls[-1].args, ("pr", "merge", "https://example.invalid/pull/3",
                                          "--merge", "--match-head-commit", "abc123"))

    def test_refuses_any_other_target(self):
        cases = [({"baseRefName": "main", "headRefName": "piece/3", "state": "OPEN"}, "trip", "main"),
                 ({"baseRefName": "main", "headRefName": "piece/3", "state": "OPEN"}, "main", "main"),
                 ({"baseRefName": "master", "headRefName": "piece/3", "state": "OPEN"}, "master", "main"),
                 ({"baseRefName": "trip", "headRefName": "piece/3", "state": "OPEN"}, "trip", "trip"),
                 ({"baseRefName": "trip", "headRefName": "piece/3", "state": "CLOSED"}, "trip", "main"),
                 ({"baseRefName": "trip", "headRefName": "feature", "state": "OPEN"}, "trip", "main")]
        for view, base, default in cases:
            with self.subTest(view=view, base=base, default=default):
                with self.assertRaises(Refused):
                    self.merge(view, base, default)

    def test_merge_pr_is_the_only_pull_request_merge_in_the_kit(self):
        sources = "".join(path.read_text() for path in (KIT / "scripts").glob("*.py"))
        self.assertEqual(sources.count('"pr", "merge"'), 1)


class WaitingAndReportsTest(LandFixture, unittest.TestCase):
    def test_the_waiting_limit_is_off_only_when_the_run_merges(self):
        for n in range(3):
            self.p.gh.create_issue("Waiting", SPEC, ["state:approval"])
        self.assertEqual(run.waiting_limit_note(self.p.gh, self.p.root), "")
        self.setting("Base branch: trip\n")
        self.assertIn("Run paused", run.waiting_limit_note(self.p.gh, self.p.root))

    def test_a_bad_setting_pauses_the_run(self):
        self.setting("Base branch: trip\nBase merges: always\n")
        self.assertIn("Run paused: Base merges must be person or run",
                      run.waiting_limit_note(self.p.gh, self.p.root))

    def test_the_walk_away_summary_says_what_the_run_merged(self):
        now = datetime.now(timezone.utc)
        text = walkaway.summary_text(["piece 3: merged into trip: url"], now, now)
        self.assertIn("The run merged gated pieces into the base branch", text)
        self.assertNotIn("left for the person", text)
        text = walkaway.summary_text(["piece 3: pull request ready for you: url Not merged: x"],
                                     now, now)
        self.assertIn("## Blockers\n\n- piece 3", text)

    def test_doctor_names_run_merges_and_warns_on_main(self):
        checks = doctor.doctor(self.p.gh, self.p.root)
        self.assertTrue(any(what == "the run merges gated pieces into trip" for _, what, _ in checks))
        self.setting("Base merges: run\n")
        checks = doctor.doctor(self.p.gh, self.p.root)
        self.assertTrue(any("does nothing while the base is main" in what for _, what, _ in checks))

    def test_settings_come_from_main_not_a_build_folder(self):
        n, folder, result = self.gated({"AGENTS.md": "## The loop\nBase merges: person\n"})
        self.assertTrue(loopkit.base_merges(folder))


class EndToEndTest(LandFixture, unittest.TestCase):
    def test_one_run_merges_a_piece_then_sees_it_on_the_base(self):
        import os
        import stat

        import run_cli
        from contextlib import redirect_stdout
        from io import StringIO
        from run_fixtures import FAKE_CLAUDE
        fake = self.p.root.parent / "fake-claude"
        fake.write_text(FAKE_CLAUDE)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        first, second = self.p.piece(), self.p.piece()
        for n in (first, second):
            gate.move(self.p.gh, self.p.root, n, "ready")
        out = StringIO()
        with patch.dict(os.environ, {"LOOP_CLAUDE": str(fake), "FAKE_MODE": "good"}), \
                patch.object(run_cli, "repo_root", return_value=self.p.root), \
                patch.object(run_cli, "GitHub", return_value=self.p.gh), \
                patch.object(run_cli.signal, "signal"), redirect_stdout(out):
            run.main(["--attended"])
        self.assertIn(f"piece {first}: merged into trip", out.getvalue())
        self.assertEqual(gate.state_of(self.p.gh.issue(first)), "done")
        self.assertIn(f"piece {second}: back to shaping, already satisfied", out.getvalue())
        self.assertIn("habits.py", git(self.p.root, "ls-tree", "--name-only", "origin/trip"))
        self.assertNotIn("habits.py", git(self.p.root, "ls-tree", "--name-only", "origin/main"))


if __name__ == "__main__":
    unittest.main()
