"""The judge writer sees the Approach of the pieces a piece depends on."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))
import helpers

# isort: split

import json
import tempfile

import test_capabilities

VERDICT = '<verdict>{"judge_files":["judge.py"],"tests_per_id":true,"notes":"ok"}</verdict>'
BASE = {"Intent": "Keep a habit", "Approach": "", "Contract": "D1: keep it",
        "Files": "judge.py"}
DEPENDENCIES = "Piece 7 Approach: habits.add(items, name) returns the new list.\nNo I/O."


class DependenciesTest(unittest.TestCase):
    invoke = test_capabilities.CapabilityTest.invoke
    fake_cli = test_capabilities.CapabilityTest.fake_cli

    def run_with(self, data, backend="claude"):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            result, output = self.invoke(folder, backend, "judge-writer", data, VERDICT)
            args = folder / "args.json"
            prompt = " ".join(json.loads(args.read_text())) if args.exists() else ""
            return result, prompt

    def test_D1_dependencies_reach_the_prompt_unchanged_on_both_backends(self):
        for backend in ("claude", "codex"):
            with self.subTest(backend=backend):
                result, prompt = self.run_with({**BASE, "Dependencies": DEPENDENCIES}, backend)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(json.dumps(DEPENDENCIES), prompt)

    def test_D1_an_empty_dependencies_string_is_accepted(self):
        result, prompt = self.run_with({**BASE, "Dependencies": ""})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"Dependencies": ""', prompt)

    def test_D2_an_input_without_dependencies_is_accepted_as_before(self):
        result, prompt = self.run_with(BASE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('"Dependencies"', prompt)

    def test_D3_a_dependencies_value_that_is_not_a_string_is_refused_naming_the_key(self):
        for value in (["Piece 7"], 7, None, {"7": "x"}):
            with self.subTest(value=value):
                result, prompt = self.run_with({**BASE, "Dependencies": value})
                self.assertEqual(result.returncode, 2)
                self.assertIn("Dependencies", result.stderr)
                self.assertEqual(prompt, "", "the session must not start")

    def test_D3_an_unknown_key_is_still_refused(self):
        result, _ = self.run_with({**BASE, "Dependency": "x"})
        self.assertEqual(result.returncode, 2)
        self.assertIn("input requires only", result.stderr)

    def test_D4_the_judge_writer_brief_mentions_dependencies(self):
        brief = (helpers.KIT / "briefs" / "judge-writer.md").read_text()
        self.assertIn("Dependencies", brief)


if __name__ == "__main__":
    unittest.main()
