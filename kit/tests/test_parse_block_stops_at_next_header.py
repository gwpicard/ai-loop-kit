import unittest

import flow


class ParseBlockStopsAtNextHeaderTest(unittest.TestCase):
    def test_next_block_header_is_not_an_item(self):
        self.assertEqual(flow.parse_block("TESTS:\n- tests/test_a.py\nBUILT: added a\n"), ["tests/test_a.py"])


if __name__ == "__main__":
    unittest.main()
