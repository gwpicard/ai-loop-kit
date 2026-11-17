import unittest

import flow
import merge


class BoldReplyBlocksTest(unittest.TestCase):
    def test_bold_tests_header_is_read(self):
        self.assertEqual(flow.parse_block("**TESTS:**\n- tests/test_a.py\n"), ["tests/test_a.py"])

    def test_bold_verdict_is_read(self):
        self.assertEqual(merge.parse_verdict("**VERDICT:** APPROVE\nHEAD: abcdef1\n"), ("APPROVE", "abcdef1"))

    def test_decorated_head_is_read(self):
        self.assertEqual(merge.parse_verdict("VERDICT: APPROVE\nHEAD: `abcdef1`\n"), ("APPROVE", "abcdef1"))


if __name__ == "__main__":
    unittest.main()
