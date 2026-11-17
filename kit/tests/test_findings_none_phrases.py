import unittest

import pass_


class FindingsNonePhrasesTest(unittest.TestCase):
    def test_none_found_is_no_finding(self):
        for reply in ("FINDINGS:\nNone found", "FINDINGS:\nNo findings.", "FINDINGS:\nnone found."):
            self.assertEqual(pass_.findings(reply), [], reply)


if __name__ == "__main__":
    unittest.main()
