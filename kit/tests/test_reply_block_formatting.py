import unittest

import flow
import merge


class ReplyBlockFormattingTest(unittest.TestCase):
    def test_bold_verdict_with_colon_outside_bold_is_read(self):
        for reply in ("**VERDICT**: APPROVE\nHEAD: abc1234\n",
                      "**VERDICT**: APPROVE\n\nHEAD: def5678\n"):
            with self.subTest(reply=reply):
                head = "abc1234" if "abc1234" in reply else "def5678"
                self.assertEqual(merge.parse_verdict(reply), ("APPROVE", head))

    def test_bold_tests_with_colon_outside_bold_is_read(self):
        for items in ("a.py\nb.py\n", "- b.py\n- a.py\n"):
            with self.subTest(items=items):
                expected = ["a.py", "b.py"] if items.startswith("a") else ["b.py", "a.py"]
                self.assertEqual(flow.parse_block("**TESTS**:\n" + items), expected)

    def test_bold_backticked_paths_are_cleaned(self):
        for items in ("**`a.py`**\n- **`b.py`**\n", "- **`b.py`**\n**`a.py`**\n"):
            with self.subTest(items=items):
                expected = ["a.py", "b.py"] if items.startswith("**") else ["b.py", "a.py"]
                self.assertEqual(flow.parse_block("TESTS:\n" + items), expected)

    def test_bullet_followed_by_number_is_cleaned(self):
        for items, expected in (("- 1. a.py\n- 2. b.py\n", ["a.py", "b.py"]),
                                ("- 2. b.py\n- 1. a.py\n", ["b.py", "a.py"])):
            with self.subTest(items=items):
                self.assertEqual(flow.parse_block("TESTS:\n" + items), expected)

    def test_dash_only_items_keep_their_dashes(self):
        for items, expected in (("---\na.py\n", ["---", "a.py"]),
                                ("b.py\n----\n", ["b.py", "----"])):
            with self.subTest(items=items):
                self.assertEqual(flow.parse_block("TESTS:\n" + items), expected)

    def test_colon_in_path_is_an_item_but_built_header_ends_the_block(self):
        for items, expected in (("CLI:test_a.py\nb.py\n", ["CLI:test_a.py", "b.py"]),
                                ("b.py\nCLI:test_a.py\n", ["b.py", "CLI:test_a.py"])):
            with self.subTest(items=items):
                reply = "TESTS:\n" + items + "BUILT: added a\nDEVIATIONS:\nnone\n"
                self.assertEqual(flow.parse_block(reply), expected)


if __name__ == "__main__":
    unittest.main()
