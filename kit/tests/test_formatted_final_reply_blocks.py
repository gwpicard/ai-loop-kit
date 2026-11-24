import unittest

import flow
import merge
import pass_


class FormattedFinalReplyBlocksTest(unittest.TestCase):
    def test_empty_formatted_final_blocks_replace_earlier_results(self):
        for header in ("**%s**:", "**%s:**"):
            for ending in ("", "\n", "\n\n"):
                with self.subTest(header=header, ending=ending):
                    self.assertEqual(flow.parse_block(
                        "TESTS:\na.py\n\n" + header % "TESTS" + ending), [])
                    self.assertEqual(merge.parse_verdict(
                        "VERDICT: APPROVE\nHEAD: abc1234\n\n"
                        + header % "VERDICT" + ending), (None, None))

    def test_formatted_headers_with_inline_text_end_blocks(self):
        for header in ("**%s**:", "**%s:**"):
            with self.subTest(header=header):
                self.assertEqual(flow.parse_block(
                    "**TESTS**:\n- 1. **`CLI:test_a.py`**\n"
                    + header % "BUILT" + " added a\n"), ["CLI:test_a.py"])
                self.assertEqual(pass_.findings(
                    "RUBRIC CONFIRMED:\nCLI: empty input | crashes\n"
                    + header % "RUBRIC REJECTED" + "\nOther claim | allowed\n",
                    "RUBRIC CONFIRMED"), [("CLI: empty input", "crashes", "")])


if __name__ == "__main__":
    unittest.main()
