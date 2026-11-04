# Intent: a missing claude executable is a failed walk-away check, not an exception.
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import Project, git

# isort: split
import gate
import walkaway

VERSION_CHECK = (False, "Claude Code version unavailable supports strict sandbox mode",
                 "install Claude Code 2.1.285 or later and check that it is on PATH")


class PieceMissingClaudeTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        gate.init(self.p.gh, self.p.root)
        self.p.loop_section("true")
        agents = self.p.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "Agent: claude\n")
        git(self.p.root, "add", "AGENTS.md")
        git(self.p.root, "commit", "--quiet", "-m", "Select claude")
        git(self.p.root, "push", "--quiet", "origin", "main")
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        self.missing = str(Path(self.p.tmp.name) / "no-such-dir" / "claude")
        os.environ["LOOP_CLAUDE"] = self.missing

    def test_D1_preflight_reports_the_missing_claude_as_a_failed_check(self):
        try:
            checks = walkaway.preflight(self.p.gh, self.p.root, baseline_checked=True)
        except OSError as error:
            self.fail(f"preflight must not raise for a missing claude: {error!r}")
        self.assertIn(VERSION_CHECK, checks)
        labels = [label for _, label, _ in checks]
        version_at = checks.index(VERSION_CHECK)
        self.assertTrue(any(label.startswith("approval queue is below its limit")
                            for label in labels[version_at + 1:]),
                        f"the approval queue check must follow the version check: {labels}")

    def test_D2_doctor_walk_away_returns_the_checks_and_the_failed_version_check(self):
        try:
            checks = gate.doctor(self.p.gh, self.p.root, walk_away=True)
        except OSError as error:
            self.fail(f"doctor must not raise for a missing claude: {error!r}")
        self.assertIn(VERSION_CHECK, checks)
        before = checks[:checks.index(VERSION_CHECK)]
        self.assertTrue(before, "doctor's own checks must precede the version check")
        self.assertTrue(all(ok for ok, _, _ in before),
                        f"the preceding doctor checks must pass: {before}")
        self.assertIn("gh is signed in", [label for _, label, _ in before])


if __name__ == "__main__":
    unittest.main()
