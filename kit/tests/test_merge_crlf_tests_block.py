import unittest

import merge


class CrlfTestsBlockTest(unittest.TestCase):
    def test_tests_block_with_windows_line_endings_still_locks_paths(self):
        body = "TESTS:\r\nkit/tests/test_a.py\r\n\r\nCommit: abc1234\r\n"
        self.assertEqual(merge.locked_paths([{"body": body}]), ["kit/tests/test_a.py"])
        self.assertEqual(merge.locked_baseline([{"body": body}]), "abc1234")


if __name__ == "__main__":
    unittest.main()
