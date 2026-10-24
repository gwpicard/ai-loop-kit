"""The run opens one pull request from the base branch into main."""
from __future__ import annotations

from helpers import Project, git

# isort: split

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import loop_pr
import run_cli


class FinalPullRequestTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.p.loop_section("printf baseline")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Base branch: trip\nProtected paths: secret/\n")
        git(self.p.root, "commit", "--quiet", "-am", "Base branch")
        git(self.p.root, "push", "--quiet", "origin", "main")
        git(self.p.root, "branch", "trip")
        git(self.p.root, "push", "--quiet", "origin", "trip")

    def land(self, n, files, state="MERGED"):
        """Build piece n on its own branch and, when merged, merge it into trip."""
        git(self.p.root, "switch", "--quiet", "-c", f"piece/{n}", "trip")
        for name in files:
            path = self.p.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"piece {n}\n")
        git(self.p.root, "add", "-A")
        git(self.p.root, "commit", "--quiet", "-m", f"Piece {n}")
        commit = ""
        if state == "MERGED":
            git(self.p.root, "switch", "--quiet", "trip")
            git(self.p.root, "merge", "--quiet", "--no-ff", "-m", f"Merge piece {n}", f"piece/{n}")
            git(self.p.root, "push", "--quiet", "origin", "trip")
            commit = git(self.p.root, "rev-parse", "HEAD")
        git(self.p.root, "switch", "--quiet", "main")
        self.p.gh.prs[f"piece/{n}"] = {
            "url": f"https://example.invalid/pull/{n}", "state": state, "base": "trip",
            "title": f"Piece {n}", "mergeCommit": {"oid": commit} if commit else None,
            "mergedAt": f"2026-10-24T10:0{n}:00Z" if commit else None}

    def final(self, results=()):
        return loop_pr.final_pull_request(self.p.gh, self.p.root, list(results))

    def test_opens_one_pull_request_into_main_with_each_merged_piece(self):
        self.land(1, ["habits.py"])
        self.land(2, ["days.py"])
        line = self.final()
        self.assertTrue(line.startswith("Final pull request: "), line)
        final = self.p.gh.prs["trip"]
        self.assertEqual(final["base"], "main")
        self.assertEqual(final["title"], "Bring trip into main")
        body = final["body"]
        self.assertIn("piece/1: Piece 1 (https://example.invalid/pull/1)", body)
        self.assertLess(body.index("piece/1"), body.index("piece/2"))
        self.assertNotIn("Closes", body)
        self.assertNotIn("Changes check settings", body)
        self.assertNotIn("### Wave", body)

    def test_pieces_are_grouped_by_wave_when_they_depend_on_each_other(self):
        from loopkit import record_text
        for depends in ([], [1], []):
            n = self.p.gh.create_issue("A piece", "", ["state:done"])
            self.p.gh.comment(n, record_text({"move": "ready",
                                              "risks": {"depends_on": depends}}, "ready"))
        for n in (1, 3, 2):
            self.land(n, [f"piece{n}.py"])
        body = self.final() and self.p.gh.prs["trip"]["body"]
        self.assertIn("### Wave 1\n- piece/1: Piece 1", body)
        self.assertIn("- piece/3: Piece 3", body.split("### Wave 1", 1)[1].split("### Wave 2")[0])
        self.assertIn("### Wave 2\n- piece/2: Piece 2", body)

    def test_a_second_run_updates_the_same_pull_request(self):
        self.land(1, ["habits.py"])
        self.final()
        self.land(2, ["days.py"])
        line = self.final()
        self.assertTrue(line.startswith("Final pull request (updated): "), line)
        self.assertEqual([branch for branch in self.p.gh.prs if not branch.startswith("piece/")],
                         ["trip"])
        self.assertIn("piece/2", self.p.gh.prs["trip"]["body"])

    def test_names_check_settings_and_protected_paths_each_piece_changed(self):
        self.land(1, ["habits.py", ".github/workflows/ci.yml", "secret/key.txt"])
        self.final()
        self.assertIn("Changes check settings or protected paths: "
                      ".github/workflows/ci.yml, secret/key.txt", self.p.gh.prs["trip"]["body"])

    def test_waiting_and_held_pieces_make_it_incomplete(self):
        self.land(1, ["habits.py"])
        self.land(2, ["days.py"], state="OPEN")
        self.final(["piece 3: back to shaping, the judge fails", "piece 1: pull request ready"])
        final = self.p.gh.prs["trip"]
        self.assertEqual(final["title"], "Bring trip into main (incomplete: 2 not on trip)")
        self.assertIn("## Waiting to merge into `trip`\n- piece/2: Piece 2", final["body"])
        self.assertIn("## Held in this run\n- piece 3: back to shaping", final["body"])
        self.assertNotIn("pull request ready", final["body"])

    def test_nothing_new_on_the_base_opens_nothing(self):
        self.assertEqual(self.final(), "")
        self.assertNotIn("trip", self.p.gh.prs)

    def test_pieces_already_in_main_are_left_out(self):
        self.land(1, ["habits.py"])
        git(self.p.root, "merge", "--quiet", "--no-ff", "-m", "Earlier loop", "origin/trip")
        git(self.p.root, "push", "--quiet", "origin", "main")
        self.land(2, ["days.py"])
        self.final()
        body = self.p.gh.prs["trip"]["body"]
        self.assertNotIn("piece/1", body)
        self.assertIn("piece/2", body)

    def test_a_main_base_never_asks_github(self):
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text().replace("Base branch: trip\n", ""))
        git(self.p.root, "commit", "--quiet", "-am", "No base branch")
        git(self.p.root, "push", "--quiet", "origin", "main")
        gh = Mock()
        self.assertEqual(loop_pr.final_pull_request(gh, self.p.root, []), "")
        self.assertEqual(gh.mock_calls, [])

    def test_the_body_is_cut_before_the_limit(self):
        self.land(1, ["habits.py"])
        with patch.object(loop_pr, "BODY_LIMIT", 80):
            self.final()
        body = self.p.gh.prs["trip"]["body"]
        self.assertLess(len(body), 200)
        self.assertIn("The list is cut here.", body)

    def test_a_failure_is_reported_and_does_not_stop_the_run(self):
        results = ["piece 1: pull request ready"]
        api = SimpleNamespace(final_pull_request=Mock(side_effect=RuntimeError("gh is down")))
        run_cli.final_pull_request(api, self.p.gh, self.p.root, results)
        self.assertEqual(results[-1], "could not open the final pull request: gh is down")


if __name__ == "__main__":
    unittest.main()
