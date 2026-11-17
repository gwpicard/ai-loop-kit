import unittest

import merge


class VerdictTrailingPunctuationTest(unittest.TestCase):
    def test_verdict_word_with_a_full_stop_is_still_the_verdict(self):
        for reply in ("VERDICT: APPROVE.", "**VERDICT:** APPROVE.\nHEAD: abc1234"):
            self.assertEqual(merge.parse_verdict(reply)[0], "APPROVE", reply)


if __name__ == "__main__":
    unittest.main()
