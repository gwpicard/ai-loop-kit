"""The settings template holds the merge doors shut, beside the guard hook and the gate's code.

A merge is the person's, or a pre-approved run's. The template keeps three doors out of an agent
session: `gh pr merge` (deny), the pull request script's `merge` and `gate.py move ... done`
(deny too, since the run merges in its own process and types neither command).
"""

import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "permission_matcher_door", REPO / "tests" / "lib" / "permission-matcher.py")
assert spec is not None and spec.loader is not None
matcher = importlib.util.module_from_spec(spec)
sys.modules["permission_matcher_door"] = matcher
spec.loader.exec_module(matcher)

SETTINGS = json.loads((REPO / "kit" / "templates" / "claude-settings.json").read_text())
DENY = SETTINGS["permissions"]["deny"]
ASK = SETTINGS["permissions"].get("ask", [])

MERGES = (
    "gh pr merge 5 --squash",
    "gh pr merge",
    "gh pr merge --auto 5",
    "gh api -X PUT repos/o/r/pulls/5/merge",
    "gh api repos/o/r/pulls/5/merge --method PUT -f sha=abc",
    "python3 -m loop.run.pull_request merge --run r --said merge",
    "python3 -m loop.run.pull_request merge --run r --pre-approved",
    "python3 kit/scripts/gate.py move 3 done --option merge=agent --option said=merge",
    "python3 kit/scripts/gate.py move 3 done",
)
READS = (
    "gh pr view 5",
    "gh pr checks 5",
    "python3 -m loop.run.pull_request status --run r",
    "python3 kit/scripts/gate.py move 3 review",
    "python3 kit/scripts/run.py --merge-pre-approved",
)


class MergeDoors(unittest.TestCase):
    def test_every_merge_door_is_denied_in_the_template(self) -> None:
        for command in MERGES:
            with self.subTest(command=command):
                self.assertTrue(matcher.any_match(DENY, command), f"no deny rule: {command}")

    def test_reads_and_the_pre_approved_run_are_not_denied(self) -> None:
        for command in READS:
            with self.subTest(command=command):
                self.assertFalse(matcher.any_match(DENY, command), f"denied: {command}")
                self.assertFalse(matcher.any_match(ASK, command), f"asked: {command}")


if __name__ == "__main__":
    unittest.main()
