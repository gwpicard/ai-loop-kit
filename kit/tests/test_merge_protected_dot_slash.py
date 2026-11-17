import unittest

import merge


class ProtectedDotSlashTest(unittest.TestCase):
    def test_protected_path_written_with_leading_dot_slash_still_protects(self):
        self.assertIsNotNone(merge.stop_reason(".claude/settings.json", ["./.claude"]))
        self.assertIsNotNone(merge.stop_reason("secrets/key.txt", ["./secrets/"]))


if __name__ == "__main__":
    unittest.main()
