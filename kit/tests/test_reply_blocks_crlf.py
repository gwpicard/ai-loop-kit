import unittest

import flow


class ReplyBlocksCRLFTest(unittest.TestCase):
    def test_crlf_tests_block_is_read(self):
        self.assertEqual(flow.parse_block("TESTS:\r\nkit/tests/test_flow.py\r\n"),
                         ["kit/tests/test_flow.py"])

    def test_final_crlf_block_supersedes_earlier_paths(self):
        for header in ("TESTS:", "**TESTS:**", "**TESTS**:"):
            for content, expected in (("new.py\r\n", ["new.py"]), ("", [])):
                with self.subTest(header=header, content=content):
                    reply = "TESTS:\nold.py\n\n" + header + "\r\n" + content
                    self.assertEqual(flow.parse_block(reply), expected)


if __name__ == "__main__":
    unittest.main()
