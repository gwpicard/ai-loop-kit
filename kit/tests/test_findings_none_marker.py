import unittest

import pass_


class FindingsNoneMarkerTest(unittest.TestCase):
    def test_decorated_none_is_no_finding(self):
        for reply in ("FINDINGS:\n**none**", "FINDINGS:\nNone.", "FINDINGS:\n- none"):
            self.assertEqual(pass_.findings(reply), [], reply)


if __name__ == "__main__":
    unittest.main()
