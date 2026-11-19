import unittest

import pass_


class FindingsBacktickPathTest(unittest.TestCase):
    def test_code_formatted_path_is_bare(self):
        found = pass_.findings("FINDINGS:\nA | fails | `.loop/pass/tests/test_a.py`\n")
        self.assertEqual(found, [("A", "fails", ".loop/pass/tests/test_a.py")])


if __name__ == "__main__":
    unittest.main()
