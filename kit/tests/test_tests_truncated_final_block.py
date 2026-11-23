import unittest

import flow


class TestsTruncatedFinalBlockTest(unittest.TestCase):
    def test_a_truncated_last_tests_block_does_not_reuse_old_paths(self):
        for ending in ("TESTS:", "**TESTS:**"):
            with self.subTest(ending=ending):
                reply = "TESTS:\nkit/tests/test_old.py\n\n" + ending
                self.assertEqual(flow.parse_block(reply), [],
                                 "The last TESTS block is empty; its earlier paths are stale.")


if __name__ == "__main__":
    unittest.main()
