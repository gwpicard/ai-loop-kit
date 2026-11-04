"""In a tiered run, ready reuses the start-of-run baseline instead of rerunning the suite."""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import GOOD_CODE, Project, git

# isort: split
import gate
from loopkit import Refused

try:
    import regression
except ImportError as error:
    if error.name != "regression":
        raise
    regression = None

TIER = "AI_LOOP_KIT_TIER"


class PieceBaselineReadyTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.marker = Path(self.p.tmp.name) / "marker.txt"
        self.prepared = Path(self.p.tmp.name) / "prepared.txt"
        gate.init(self.p.gh, self.p.root)
        self.test_command = f"echo suite >> {self.marker}"
        self.p.loop_section(self.test_command, prepare=f"echo prep >> {self.prepared}")

    def runs(self, path=None):
        path = path or self.marker
        return len(path.read_text().splitlines()) if path.exists() else 0

    def base_sha(self):
        return git(self.p.root, "rev-parse", "origin/main")

    def write_baseline(self, test=None, keep=None):
        folder = self.p.root / ".loop"
        folder.mkdir(exist_ok=True)
        test = test or self.test_command
        (folder / "baseline.json").write_text(json.dumps(
            {"commit": self.base_sha(), "test": test, "keep": keep or test}))

    def tiered(self, on=True):
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(TIER, None)
        if on:
            os.environ[TIER] = "narrow"

    def make_ready(self, n):
        gate.move(self.p.gh, self.p.root, n, "ready")
        return gate.last_record(self.p.gh.comments(n), "ready")

    def test_D1_doctor_walk_away_records_the_baseline(self):
        try:
            gate.doctor(self.p.gh, self.p.root, walk_away=True)
        except Refused:
            pass
        record = self.p.root / ".loop" / "baseline.json"
        self.assertTrue(record.is_file(), "doctor --walk-away must write .loop/baseline.json")
        self.assertEqual(json.loads(record.read_text()), {
            "commit": self.base_sha(), "test": self.test_command, "keep": self.test_command})

    def test_D1_doctor_without_walk_away_writes_no_baseline(self):
        gate.doctor(self.p.gh, self.p.root)
        self.assertFalse((self.p.root / ".loop" / "baseline.json").exists())

    def test_D1_doctor_writes_no_baseline_when_the_suite_fails(self):
        self.p.loop_section(f"echo suite >> {self.marker}; exit 1")
        gate.doctor(self.p.gh, self.p.root, walk_away=True)
        self.assertFalse((self.p.root / ".loop" / "baseline.json").exists())

    def test_D2_ready_reuses_the_baseline_and_names_its_commit(self):
        self.write_baseline()
        self.tiered()
        n = self.p.piece()
        ready = self.make_ready(n)
        self.assertEqual(self.runs(), 0)
        self.assertEqual(ready["regression_main"]["baseline"], self.base_sha())
        self.assertEqual(ready["regression_main"]["exit"], 0)
        self.assertEqual(ready["regression_main"]["reason"], "")

    def test_D2_ready_skips_a_distinct_keep_too(self):
        keep = f"echo keep >> {self.marker}"
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + f"Keep: `{keep}`\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Keep")
        git(self.p.root, "push", "--quiet", "origin", "main")
        self.write_baseline(keep=keep)
        self.tiered()
        self.make_ready(self.p.piece())
        self.assertEqual(self.runs(), 0)

    def test_D3_ready_still_runs_prepare_with_a_baseline(self):
        self.write_baseline()
        self.tiered()
        self.make_ready(self.p.piece())
        self.assertEqual(self.runs(self.prepared), 1)

    def test_D3_ready_still_refuses_a_judge_that_passes_on_base(self):
        (self.p.root / "habits.py").write_text(GOOD_CODE)
        git(self.p.root, "add", "habits.py")
        git(self.p.root, "commit", "--quiet", "-m", "Already built")
        git(self.p.root, "push", "--quiet", "origin", "main")
        self.write_baseline()
        self.tiered()
        n = self.p.piece()
        with self.assertRaises(Refused):
            gate.move(self.p.gh, self.p.root, n, "ready")
        self.assertNotIn("state:ready", self.p.gh.issue(n)["labels"])
        self.assertEqual(self.runs(), 0)

    def test_D4_no_baseline_runs_the_full_suite(self):
        self.tiered()
        ready = self.make_ready(self.p.piece())
        self.assertEqual(self.runs(), 1)
        self.assertNotIn("baseline", ready["regression_main"])

    def test_D4_a_baseline_for_other_commands_runs_the_full_suite(self):
        self.write_baseline(test="echo other")
        self.tiered()
        ready = self.make_ready(self.p.piece())
        self.assertEqual(self.runs(), 1)
        self.assertNotIn("baseline", ready["regression_main"])

    def test_D5_without_the_tier_the_full_suite_runs_despite_a_baseline(self):
        self.write_baseline()
        self.tiered(on=False)
        ready = self.make_ready(self.p.piece())
        self.assertEqual(self.runs(), 1)
        self.assertNotIn("baseline", ready["regression_main"])

    def test_D5_without_the_tier_a_failing_suite_on_base_refuses(self):
        self.p.loop_section(f"echo suite >> {self.marker}; echo broken; exit 1")
        self.write_baseline(test=f"echo suite >> {self.marker}; echo broken; exit 1")
        self.tiered(on=False)
        n = self.p.piece()
        with self.assertRaises(Refused) as caught:
            gate.move(self.p.gh, self.p.root, n, "ready")
        self.assertIn("regression", caught.exception.reason)
        self.assertEqual(self.runs(), 1)

    def test_D1_baseline_covers_needs_the_tier_the_file_and_equal_commands(self):
        self.assertIsNotNone(regression, "regression module must exist")
        self.assertTrue(hasattr(regression, "baseline_covers"),
                        "regression.baseline_covers must exist")
        root = self.p.root
        t = self.test_command
        self.tiered()
        self.assertFalse(regression.baseline_covers(root, t, t))
        regression.write_baseline(root, self.base_sha(), t, t)
        self.assertTrue(regression.baseline_covers(root, t, t))
        self.assertTrue(regression.baseline_covers(root, t, ""))
        self.assertFalse(regression.baseline_covers(root, "other", t))
        self.assertFalse(regression.baseline_covers(root, t, "other"))
        self.tiered(on=False)
        self.assertFalse(regression.baseline_covers(root, t, t))


if __name__ == "__main__":
    unittest.main()
