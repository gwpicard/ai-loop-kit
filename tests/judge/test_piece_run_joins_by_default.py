"""A run builds pieces that become ready, or come back, without any flag."""
from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
from helpers import SPEC, Project

# isort: split

import run
import run_cli
from loopkit import record_text

ROOT = Path(__file__).resolve().parents[2]


class RunJoinsByDefaultTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.gh = self.p.gh
        self.p.loop_section("true")
        self.built: list[int] = []
        self.on_build: dict[int, list] = {}
        self.stale: list[int] = []  # pieces the ready search lists whatever their label

    def piece(self, labels=("state:ready",)):
        n = self.gh.create_issue("A piece", SPEC, list(labels))
        self.gh.comment(n, record_text({"move": "ready", "risks": {"depends_on": []},
                                        "waiting_limit": "9"}, "ready"))
        return n

    def ready_pieces(self):
        live = {n for n, i in self.gh.issues.items() if "state:ready" in i["labels"]}
        return sorted(live | set(self.stale))

    def build(self, gh, root, n, *args):
        self.built.append(n)
        self.gh.set_labels(n, ["state:approval"], ["state:ready"])
        actions = self.on_build.get(n, [])
        if actions:
            actions.pop(0)()
        return f"piece {n}: built"

    def run_all(self, *argv):
        out = io.StringIO()
        with patch.object(run_cli, "repo_root", return_value=self.p.root), \
                patch.object(run_cli, "GitHub", return_value=self.gh), \
                patch.object(run_cli.signal, "signal"), \
                patch.object(run, "ready_pieces", side_effect=lambda *a: self.ready_pieces()), \
                patch.object(run, "build_piece", side_effect=self.build), \
                redirect_stdout(out):
            status = run.main(["--attended", *argv])
        return status, out.getvalue()

    def make_ready(self, n):
        self.gh.set_labels(n, ["state:ready"], ["state:shaping", "state:approval"])

    def test_D10_a_piece_ready_during_a_plain_run_is_built(self):
        first = self.piece()
        late = self.piece(["state:shaping"])
        self.on_build[first] = [lambda: self.make_ready(late)]
        status, out = self.run_all()
        self.assertEqual((status, self.built), (0, [first, late]))

    def test_D11_a_keep_going_run_still_builds_a_piece_that_becomes_ready(self):
        first = self.piece()
        late = self.piece(["state:shaping"])
        self.on_build[first] = [lambda: self.make_ready(late)]
        status, out = self.run_all("--keep-going")
        self.assertEqual((status, self.built), (0, [first, late]))

    def test_D12_a_handed_back_piece_still_listed_as_ready_is_not_built_again(self):
        a = self.piece()
        self.on_build[a] = [lambda: (
            self.gh.set_labels(a, ["state:shaping"], ["state:approval", "state:ready"]),
            self.stale.append(a))]
        status, out = self.run_all()
        self.assertEqual(self.built, [a])

    def test_D13_run_skill_and_readme_drop_keep_going_and_describe_joining(self):
        skill = (ROOT / "kit" / "skills" / "run" / "SKILL.md").read_text()
        readme = (ROOT / "README.md").read_text()
        for name, text in (("run skill", skill), ("README.md", readme)):
            self.assertNotIn("--keep-going", text, name)
            self.assertNotIn("keep going", text.lower(), name)
        self.assertRegex(skill, r"also builds pieces that become ready, or come back, while it works")

    def test_D14_a_plain_listed_run_does_not_build_an_unselected_ready_piece(self):
        a = self.piece()
        unselected = self.piece()
        late = self.piece(["state:shaping"])
        self.on_build[a] = [lambda: self.make_ready(late)]
        status, out = self.run_all(str(a))
        self.assertEqual(self.built, [a, late])
        self.assertNotIn(unselected, self.built)


if __name__ == "__main__":
    unittest.main()
