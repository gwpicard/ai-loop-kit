# Intent: the walk-away check warns when core.hooksPath is absolute, as a sandboxed Claude builder cannot run it.
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

ABSOLUTE = "/elsewhere/checkout/.githooks"


class HooksPathWarningTest(unittest.TestCase):
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
        os.environ["LOOP_CLAUDE"] = str(Path(self.p.tmp.name) / "no-such-dir" / "claude")

    def hooks_checks(self, **options):
        checks = gate.doctor(self.p.gh, self.p.root, agent="claude", **options)
        return [check for check in checks if "core.hooksPath" in check[1]]

    def test_D1_absolute_hooks_path_gives_a_warning_naming_the_path(self):
        git(self.p.root, "config", "core.hooksPath", ABSOLUTE)
        found = self.hooks_checks(walk_away=True)
        self.assertEqual(1, len(found), found)
        what = found[0][1]
        self.assertEqual(
            f"warning: core.hooksPath is an absolute path ({ABSOLUTE}); "
            "sandboxed builder commits cannot run its hooks", what)

    def test_D2_the_warning_tells_the_person_to_set_a_relative_path(self):
        git(self.p.root, "config", "core.hooksPath", ABSOLUTE)
        found = self.hooks_checks(walk_away=True)
        self.assertEqual(1, len(found), found)
        self.assertEqual("the person sets a hooks path relative to the repository", found[0][2])

    def test_D3_relative_hooks_path_gives_no_warning(self):
        git(self.p.root, "config", "core.hooksPath", ".githooks")
        self.assertEqual([], self.hooks_checks(walk_away=True))

    def test_D3_unset_hooks_path_gives_no_warning(self):
        self.assertEqual([], self.hooks_checks(walk_away=True))

    def test_D4_absolute_hooks_path_gives_no_warning_without_walk_away(self):
        git(self.p.root, "config", "core.hooksPath", ABSOLUTE)
        self.assertEqual([], self.hooks_checks())


if __name__ == "__main__":
    unittest.main()
