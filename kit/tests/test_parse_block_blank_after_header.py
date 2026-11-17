import unittest

import flow


class ParseBlockBlankAfterHeaderTest(unittest.TestCase):
    def test_blank_line_after_header_is_read(self):
        self.assertEqual(flow.parse_block("TESTS:\n\n- tests/test_a.py\n- tests/test_b.py\n"),
                         ["tests/test_a.py", "tests/test_b.py"])


if __name__ == "__main__":
    unittest.main()
