import unittest

import flow
import pass_


class ParseBlockTextTest(unittest.TestCase):
    def test_deviations_keep_backticks_and_explanations(self):
        line = "`marc` uses the existing parser"
        for bullet in ("- ", "* ", "1. ", "2) "):
            with self.subTest(bullet=bullet):
                self.assertEqual(flow.parse_block("DEVIATIONS:\n" + bullet + line, "DEVIATIONS"), [line])

    def test_pass_findings_keep_the_title_detail_and_path(self):
        self.assertEqual(pass_.findings("FINDINGS:\n- `marc` drops lines | blank lines vanish | tests/test_a.py\n"),
                         [("`marc` drops lines", "blank lines vanish", "tests/test_a.py")])


if __name__ == "__main__":
    unittest.main()
