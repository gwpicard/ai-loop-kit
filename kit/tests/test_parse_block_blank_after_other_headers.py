import unittest

import flow


class ParseBlockBlankAfterOtherHeadersTest(unittest.TestCase):
    def test_blank_line_after_each_header_is_read(self):
        for name in ("FINDINGS", "DEVIATIONS", "FOLLOW-UPS"):
            with self.subTest(name=name):
                self.assertEqual(flow.parse_block("%s:\n\n- one\n- two\n" % name, name), ["one", "two"])

    def test_items_stop_at_the_next_blank_line(self):
        self.assertEqual(flow.parse_block("TESTS:\n\n- a.py\n\nDone.\n"), ["a.py"])


if __name__ == "__main__":
    unittest.main()
