"""Keep the split suites' original test identities and reviewable sizes."""
import json
import unittest
from collections import Counter
from pathlib import Path

TESTS = Path(__file__).resolve().parent
# Only these module moves are allowed; class and method names stay unchanged.
ORIGINAL_MODULE = {
    "test_run": "test_run",
    "test_run_processes": "test_run",
    "test_run_reviews": "test_run",
    "test_loop": "test_loop",
    "test_loop_spec": "test_loop",
    "test_loop_environment": "test_loop",
    "test_loop_guard": "test_loop",
}


def test_names(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from test_names(item)
        else:
            yield item.id()


class SplitDiscoveryTest(unittest.TestCase):
    def test_split_discovers_exactly_the_original_tests_once(self):
        expected = json.loads((TESTS / "split_test_names.json").read_text())
        suite = unittest.TestLoader().discover(str(TESTS), pattern="test_*.py")
        actual = []
        for name in test_names(suite):
            module, identity = name.split(".", 1)
            if module in ORIGINAL_MODULE:
                actual.append(f"{ORIGINAL_MODULE[module]}.{identity}")
        self.assertEqual(Counter(actual), Counter(expected))

    def test_split_modules_stay_below_eight_hundred_lines(self):
        for module in (*ORIGINAL_MODULE, "run_fixtures", "loop_fixtures"):
            path = TESTS / f"{module}.py"
            with self.subTest(module=module):
                self.assertTrue(path.is_file(), str(path))
                self.assertLess(len(path.read_text().splitlines()), 800, str(path))
