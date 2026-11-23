import unittest

import merge


class VerdictTruncatedFinalBlockTest(unittest.TestCase):
    def test_a_truncated_last_verdict_cannot_preserve_an_earlier_approval(self):
        head = "abcdef1234567890abcdef1234567890abcdef12"
        for ending in ("VERDICT:", "VERDICT:\nHEAD: " + head):
            with self.subTest(ending=ending):
                reply = "VERDICT: APPROVE\nHEAD: " + head + "\n\n" + ending
                verdict, _ = merge.parse_verdict(reply)
                self.assertNotEqual(verdict, "APPROVE",
                                    "Flow must not approve from a superseded VERDICT block.")


if __name__ == "__main__":
    unittest.main()
