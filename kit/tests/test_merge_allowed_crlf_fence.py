import unittest

import merge


class AllowedCrlfFenceTest(unittest.TestCase):
    def test_crlf_body_with_an_earlier_closed_fence_still_lists_allowed_paths(self):
        body = ("## Why\r\n\r\n```\r\nsome output\r\n```\r\n\r\n"
                "## Protected paths this issue may change\r\n\r\n- `package.json`\r\n")
        self.assertIn("package.json", merge.allowed_paths(body))


if __name__ == "__main__":
    unittest.main()
