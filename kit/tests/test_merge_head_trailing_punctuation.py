import unittest

import merge


class HeadTrailingPunctuationTest(unittest.TestCase):
    def test_head_with_a_full_stop_is_still_the_head(self):
        for reply in ("VERDICT: APPROVE\nHEAD: `abc1234`.", "VERDICT: APPROVE\nHEAD: abc1234."):
            self.assertEqual(merge.parse_verdict(reply), ("APPROVE", "abc1234"), reply)


if __name__ == "__main__":
    unittest.main()
