import unittest

import flow


class ParseBlockHyphenatedHeaderTest(unittest.TestCase):
    def test_follow_ups_header_ends_the_block(self):
        reply = "DEVIATIONS:\n- none\nFOLLOW-UPS:\n- rename the helper"
        self.assertEqual(flow.parse_block(reply, "DEVIATIONS"), ["none"])

    def test_tests_block_stops_at_follow_ups(self):
        reply = "TESTS:\nkit/tests/test_a.py\nFOLLOW-UPS:\n- x"
        self.assertEqual(flow.parse_block(reply), ["kit/tests/test_a.py"])


if __name__ == "__main__":
    unittest.main()
