"""Fake-Claude rehearsals for the v1 field failure paths."""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import git
import test_run as run_test_fixture

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kit" / "scripts"))
import gate
import review
import run


class ScenarioTest(unittest.TestCase):
    def setUp(self):
        run_test_fixture.RunTest.setUp(self)

    def build(self, mode: str, attempts: int = 2):
        return run_test_fixture.RunTest.build(self, mode, attempts)

    def test_hostile_builder_changes_are_rejected(self):
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Quality: true\n")
        (self.p.root / "test_existing.py").write_text("def test_old(): assert True\n")
        (self.p.root / "conftest.py").write_text("value = 1\n")
        (self.p.root / "STANDARDS.md").write_text("Keep names clear.\n")
        git(self.p.root, "add", "AGENTS.md", "test_existing.py", "conftest.py", "STANDARDS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Add frozen checks")
        git(self.p.root, "push", "--quiet", "origin", "main")
        n, result = self.build("hostile", attempts=1)
        self.assertIn("back to shaping", result)
        self.assertEqual(self.p.gh.prs, {})
        comment = "\n".join(self.p.gh.comments(n))
        self.assertTrue(any(name in comment for name in ("AGENTS.md", "test_existing.py", "conftest.py")))

    def test_idle_events_keep_a_session_alive_and_silence_stops_it(self):
        script = self.p.tmp.name + "/stream.py"
        Path(script).write_text(
            "import time\n"
            "for _ in range(6):\n"
            " print('{\\\"type\\\":\\\"assistant\\\",\\\"message\\\":{\\\"content\\\":[{\\\"type\\\":\\\"text\\\",\\\"text\\\":\\\"working\\\"}]}}', flush=True)\n"
            " time.sleep(.08)\n")
        streamed = subprocess.Popen([sys.executable, script], stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, start_new_session=True)
        with (self.p.root / "stream.log").open("w") as output:
            status = review._pump_session(streamed, output, .2, hard_seconds=3)
        self.assertEqual(status, "")
        self.assertIn("working", (self.p.root / "stream.log").read_text())
        silent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3)"],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  start_new_session=True)
        with (self.p.root / "silent.log").open("w") as output:
            status = review._pump_session(silent, output, .2, hard_seconds=3)
        self.assertEqual(status, "idle")

    def test_bar_wrong_stops_on_attempt_one(self):
        n, result = self.build("bar-wrong", attempts=3)
        self.assertIn("back to shaping", result)
        from loopkit import records
        handbacks = [r for r in records(self.p.gh.comments(n)) if r.get("move") == "give-back"]
        self.assertEqual(handbacks[-1]["type"], "bar-wrong")
        attempts = [line for line in self.p.gh.comments(n)
                    if line.startswith("**Run:** attempt")]
        self.assertEqual(len(attempts), 1)

    def test_quality_failure_retries_and_passes_on_second_attempt(self):
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() +
            "Quality: if [ ! -f .loop/quality-once ]; then touch .loop/quality-once; exit 1; fi; exit 0\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Add retrying quality check")
        git(self.p.root, "push", "--quiet", "origin", "main")
        os.environ["FAKE_MODE"] = "good"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        with patch.object(gate, "quality_fails_on_main", return_value=False) as main_check:
            result = run.build_piece(self.p.gh, self.p.root, n, 2)
        self.assertIn("pull request ready", result)
        self.assertTrue(any("failed a Quality check; retrying" in c for c in self.p.gh.comments(n)))
        main_check.assert_called_once()
        self.assertTrue((self.p.root / ".loop" / f"main-quality-{n}.json").is_file())

    def test_node_review_fix_survives_the_recheck(self):
        source = self.p.root / "src" / "app.js"
        source.parent.mkdir()
        source.write_text("export const value = 1;\n")
        git(self.p.root, "add", "src/app.js")
        git(self.p.root, "commit", "--quiet", "-m", "Add node fixture")
        git(self.p.root, "push", "--quiet", "origin", "main")
        os.environ["FAKE_MODE"] = "good"
        os.environ["FAKE_REVIEW_MODE"] = "node-standard-fix"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("pull request ready", result)
        self.assertIn("// reviewed", git(self.p.root, "show", f"piece/{n}:src/app.js"))

    def test_kill_during_review_cleans_folder_and_branches(self):
        os.environ["FAKE_MODE"] = "good"
        os.environ["FAKE_REVIEW_MODE"] = "review-idle"
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        with patch.object(review, "idle_limit_seconds", return_value=1):
            result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("back to shaping", result)
        branches = git(self.p.root, "branch", "--list", "review/*")
        self.assertEqual(branches, "")
        self.assertFalse(self.p.folder(n).exists())
        self.assertFalse(run._ACTIVE_GROUPS)

    def test_main_merge_that_changes_the_bar_returns_before_attempt_one(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        (self.p.root / "conftest.py").write_text("value = 1\n")
        git(self.p.root, "add", "conftest.py")
        git(self.p.root, "commit", "--quiet", "-m", "Change project test bar")
        git(self.p.root, "push", "--quiet", "origin", "main")
        result = run.build_piece(self.p.gh, self.p.root, n, 1)
        self.assertIn("back to shaping", result)
        self.assertFalse(any(c.startswith("**Run:** attempt 1 of")
                             for c in self.p.gh.comments(n)))


if __name__ == "__main__":
    unittest.main()
