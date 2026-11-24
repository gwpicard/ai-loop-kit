import unittest

import flow
import merge


class FinalReplyBlocksTest(unittest.TestCase):
    def test_empty_last_verdict_has_no_verdict_even_after_changes(self):
        for earlier in ("APPROVE", "CHANGES"):
            for ending in ("VERDICT:", "VERDICT:\n", "VERDICT:\nHEAD: def5678",
                           "**VERDICT:**", "**VERDICT**:"):
                with self.subTest(earlier=earlier, ending=ending):
                    reply = "VERDICT: %s\nHEAD: abc1234\n\n%s" % (earlier, ending)
                    self.assertIsNone(merge.parse_verdict(reply)[0])

    def test_empty_last_tests_block_with_bold_colon_outside_is_authoritative(self):
        for ending in ("**TESTS**:", "**TESTS**:\n", "**TESTS**:\n\n"):
            with self.subTest(ending=ending):
                reply = "TESTS:\na.py\nb.py\n\n" + ending
                self.assertEqual(flow.parse_block(reply), [])


if __name__ == "__main__":
    unittest.main()
