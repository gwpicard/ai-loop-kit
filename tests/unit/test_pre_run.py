"""Unit tests for the two checks `run.py` added to kit/scripts/pre-run-check.py.

The `--bare` check: a session command line that carries `--bare` skips the hooks, so the run
is refused. The empty-project rule: with no test command in the policy, `main` cannot be shown
green, unless every piece in the run is the quick-path scaffold piece.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import sessions  # noqa: E402

SCRIPT = ROOT / "kit" / "scripts" / "pre-run-check.py"


def load():
    spec = importlib.util.spec_from_file_location("pre_run_check_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["pre_run_check_under_test"] = module
    spec.loader.exec_module(module)
    return module


SCAFFOLD = """Scaffold the project.

<!-- spec:start version=1 -->
Path: quick

## Goal
The project has a structure to build in and one command that runs its tests.

## Expected flow
FL-1 The person runs the test command and sees the one first test pass.

## Edge cases
EC-1 When the test command runs on a clean copy of the branch "main", then it passes.

## Must stay the same
The README stays as it is (README.md).
Check: test -f README.md

## Judge
Kind: scaffold
Command: python3 -m pytest
Proves: FL-1, EC-1

## Links
Touches: project-records
<!-- spec:end -->
"""

FEATURE = SCAFFOLD.replace("Kind: scaffold", "Kind: acceptance tests, a single test")
SLOW_SCAFFOLD = SCAFFOLD.replace("Path: quick", "Path: full")


class BareTest(unittest.TestCase):
    def setUp(self):
        self.check = load()

    def test_the_run_scripts_own_command_line_has_no_bare(self):
        command = sessions.build_command(Path("/tmp/settings.json"), max_budget_usd=2.0)
        self.assertEqual(self.check.check_bare(command, {}), [])

    def test_a_command_line_with_bare_is_refused_and_names_the_guard(self):
        command = [*sessions.build_command(Path("/tmp/settings.json")), "--bare"]
        refusals = self.check.check_bare(command, {})
        self.assertEqual([r.guard for r in refusals], ["bare"])
        self.assertIn("--bare", refusals[0].reason)
        self.assertIn("hooks", refusals[0].reason)
        self.assertTrue(refusals[0].fix)

    def test_bare_with_a_value_form_is_refused(self):
        self.assertEqual(len(self.check.check_bare(["claude", "-p", "--bare=true"], {})), 1)

    def test_the_text_form_of_a_command_line_is_read_as_words(self):
        self.assertEqual(len(self.check.check_bare_text("claude -p --bare --settings s.json", {})),
                         1)
        self.assertEqual(self.check.check_bare_text("claude -p --settings s.json", {}), [])

    def test_a_command_line_that_cannot_be_read_is_a_refusal_not_a_pass(self):
        refusals = self.check.check_bare_text("claude -p 'unclosed", {})
        self.assertEqual([r.guard for r in refusals], ["bare"])

    def test_the_environment_switch_that_means_bare_is_refused(self):
        refusals = self.check.check_bare(["claude", "-p"], {"CLAUDE_CODE_SIMPLE": "1"})
        self.assertEqual([r.guard for r in refusals], ["bare"])

    def test_an_environment_switch_set_to_nothing_is_not_bare(self):
        self.assertEqual(self.check.check_bare(["claude", "-p"], {"CLAUDE_CODE_SIMPLE": ""}), [])
        self.assertEqual(self.check.check_bare(["claude", "-p"], {"CLAUDE_CODE_SIMPLE": "0"}), [])


class ScaffoldOnlyTest(unittest.TestCase):
    def setUp(self):
        self.check = load()

    def test_one_scaffold_piece_alone_is_scaffold_only(self):
        self.assertTrue(self.check.all_scaffold([SCAFFOLD]))

    def test_a_feature_piece_is_not(self):
        self.assertFalse(self.check.all_scaffold([FEATURE]))

    def test_one_scaffold_and_one_feature_is_not(self):
        self.assertFalse(self.check.all_scaffold([SCAFFOLD, FEATURE]))

    def test_a_scaffold_that_is_not_on_the_quick_path_is_not(self):
        self.assertFalse(self.check.all_scaffold([SLOW_SCAFFOLD]))

    def test_no_piece_is_not_scaffold_only(self):
        self.assertFalse(self.check.all_scaffold([]))

    def test_a_body_that_cannot_be_read_is_not_scaffold(self):
        self.assertFalse(self.check.all_scaffold(["no spec block here"]))


if __name__ == "__main__":
    unittest.main()
