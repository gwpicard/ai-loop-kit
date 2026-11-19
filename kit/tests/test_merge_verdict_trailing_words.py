import unittest

import merge


class VerdictTrailingWordsTest(unittest.TestCase):
    def test_a_last_verdict_with_trailing_words_does_not_fall_back_to_an_earlier_approve(self):
        text = "VERDICT: APPROVE\nHEAD: abcdef1\n\nOn a second look:\nVERDICT: CHANGES, see below\nHEAD: abcdef1\n"
        self.assertNotEqual(merge.parse_verdict(text)[0], "APPROVE")


if __name__ == "__main__":
    unittest.main()
