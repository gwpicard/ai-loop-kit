import unittest

import merge


class AllowedDotSlashTest(unittest.TestCase):
    def test_allowed_path_written_with_leading_dot_slash_matches_the_git_path(self):
        body = "## Paths the builder may change\n\n- `./package.json`\n"
        self.assertIn("package.json", merge.allowed_paths(body))


if __name__ == "__main__":
    unittest.main()
