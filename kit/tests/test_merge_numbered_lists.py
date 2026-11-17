import unittest

import merge


class NumberedListsTest(unittest.TestCase):
    def test_numbered_allowed_paths_are_paths(self):
        body = "## Paths the builder may change\n\n1. a.py\n2. b.py\n"
        self.assertEqual(merge.allowed_paths(body), {"a.py", "b.py"})

    def test_numbered_locked_paths_are_paths(self):
        self.assertEqual(merge.locked_paths([{"body": "TESTS:\n1. tests/a.py\n"}]), ["tests/a.py"])


if __name__ == "__main__":
    unittest.main()
