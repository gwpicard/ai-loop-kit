import json
import os
import re
import tempfile
import unittest
from unittest import mock

from kit.tests.helpers import make_repo
import common
import loop

AGENTS = "## Loop\nTest command: true\nLoop branch: loop/main\nIdle hours: 0\n"
FACTORY = {"number": 1, "title": "Factory", "body": ""}
URL = "https://github.com/o/r/milestone/3"


def out(value):
    return {"stdout": json.dumps(value)}


def issue(number, labels=("ready",), body="", milestone=None):
    return {"number": number, "title": "Piece %d" % number, "body": body, "updatedAt": "t",
            "labels": [{"name": n} for n in labels], "milestone": milestone}


def milestone(number, title, closed, opened, url=None):
    return {"number": number, "title": title, "state": "open", "closed_issues": closed,
            "open_issues": opened, "html_url": url or "https://github.com/o/r/milestone/%d" % number}


class BoardMilestones(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(mock.patch.stopall)
        self.work, _ = make_repo(self._tmp.name, {"AGENTS.md": AGENTS})
        mock.patch.object(loop, "say", return_value=None).start()
        mock.patch.object(common, "_run_gh", self.fake_gh).start()
        self.calls, self.inputs, self.rules = [], [], []
        self.world([])

    def fake_gh(self, args, input=None):
        text = " ".join(args)
        self.calls.append(text)
        self.inputs.append((text, input))
        for match, stdout in self.rules:
            if match in text:
                return 0, stdout, ""
        return 0, "", ""

    def world(self, open_issues, milestones=()):
        self.rules = [
            ("issue list --state open", json.dumps([FACTORY] + open_issues)),
            ("issue list --state closed", "[]"),
            ("pr list", "[]"),
            ("api", json.dumps(list(milestones)))]

    def board(self, **state):
        st = loop.new_state()
        loop.snapshot(st)
        st.update(state)
        loop.write_board(self.work, st)
        return [i for c, i in self.inputs if c.startswith("issue edit 1 ")][-1]

    def sections(self, body):
        return re.findall(r"^## (.*)$", body, re.M)

    def test_the_board_has_three_sections_in_order(self):
        body = self.board()
        self.assertEqual(self.sections(body), ["Building now", "Needs you", "Progress"])

    def test_an_empty_board_reads_nothing_in_each_section(self):
        body = self.board()
        self.assertEqual(body.count("Nothing."), 3)
        self.assertIn("Last event:", body)
        self.assertIn("Next check:", body)

    def test_the_removed_sections_are_gone(self):
        self.world([issue(2), issue(3, ("inbox",)), issue(4, ("shaping",))])
        pass_dir = os.path.join(self.work, ".loop")
        os.makedirs(pass_dir, exist_ok=True)
        with open(os.path.join(pass_dir, "pass.json"), "w") as f:
            json.dump({"time": "2026-11-16 10:00", "defects": 1, "inbox": 1}, f)
        body = self.board()
        for text in ("Queue", "To shape", "Landed since", "Last pass", "Pull request into", "Conflict"):
            self.assertNotIn(text, body)
        self.assertNotIn("Piece 3", body)
        self.assertNotIn("Piece 4", body)

    def test_a_ready_issue_that_is_not_building_is_not_listed(self):
        self.world([issue(2), issue(3)])
        body = self.board(building={2: ("10:00", None)})
        self.assertIn("#2", body)
        self.assertNotIn("Piece 3", body)

    def test_needs_you_holds_the_pull_request_and_the_conflict(self):
        self.world([])
        body = self.board(pr="https://example/pull/9", conflict="clash in x.txt")
        needs = body.split("## Needs you")[1].split("## Progress")[0]
        for text in ("https://example/pull/9", "clash in x.txt"):
            self.assertIn(text, needs)
        self.assertNotIn("Nothing.", needs)

    def test_needs_you_holds_parked_issues(self):
        self.world([issue(4, ("needs-user",))])
        body = self.board()
        needs = body.split("## Needs you")[1].split("## Progress")[0]
        self.assertIn("#4 Piece 4", needs)

    def test_progress_line_uses_the_milestone_counts_and_link(self):
        m = {"number": 3, "title": "Milestone A"}
        self.world([issue(2, ("ready",), milestone=m), issue(5, ("building",), milestone=m)],
                   [milestone(3, "Milestone A", 4, 2, URL)])
        body = self.board()
        self.assertIn("## Progress", body)
        progress = body.split("## Progress")[1].split("Last event")[0]
        line = [l for l in progress.splitlines() if "Milestone A" in l]
        self.assertEqual(len(line), 1)
        self.assertRegex("".join(line), r"\b4\b.*\b6\b")
        self.assertIn(URL, "".join(line))
        self.assertNotIn("Nothing.", progress)

    def test_a_milestone_without_active_issues_has_no_progress_line(self):
        m, other = {"number": 3, "title": "Milestone A"}, {"number": 4, "title": "Milestone B"}
        self.world([issue(2, ("ready",), milestone=m), issue(6, ("inbox",), milestone=other),
                    issue(7, ("ready",))],
                   [milestone(3, "Milestone A", 1, 1), milestone(4, "Milestone B", 0, 3),
                    milestone(5, "Milestone C", 2, 0)])
        body = self.board()
        self.assertIn("Milestone A", body)
        self.assertNotIn("Milestone B", body)
        self.assertNotIn("Milestone C", body)

    def test_one_milestone_call_per_board_rewrite(self):
        m = {"number": 3, "title": "Milestone A"}
        self.world([issue(2, milestone=m)], [milestone(3, "Milestone A", 1, 1)])
        self.board()
        self.assertEqual(len([c for c in self.calls if c.startswith("api") and "milestones" in c]), 1)

    def test_snapshot_lists_the_milestone_field(self):
        self.world([issue(2)])
        loop.snapshot(loop.new_state())
        listing = [c for c in self.calls if c.startswith("issue list --state open")]
        self.assertTrue(listing)
        self.assertRegex(listing[0], r"--json \S*\bmilestone\b")

    def test_writing_the_board_runs_no_git_fetch_or_log(self):
        self.world([])
        with mock.patch.object(loop, "git") as git:
            self.board()
        git.assert_not_called()


if __name__ == "__main__":
    unittest.main()
