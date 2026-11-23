import unittest

import flow


class ParseBlockHeaderWithTextTest(unittest.TestCase):
    def test_headers_end_the_block_with_or_without_inline_text(self):
        for name in ("BUILT", "DEVIATIONS", "VERDICT", "FOLLOW-UPS"):
            for template in ("{}:", "**{}:**", "**{}**:", "`{}:`", "`{}`:"):
                for text in ("", " added a"):
                    header = template.format(name) + text
                    for paths in (("tests/test_a.py",),
                                  ("tests/test_b.py", "tests/test_a.py: covers the edge case")):
                        with self.subTest(header=header, paths=paths):
                            reply = "TESTS:\n" + "\n".join("- " + path for path in paths)
                            reply += "\n" + header + "\n- belongs to the next block\n"
                            self.assertEqual(flow.parse_block(reply), list(paths))

    def test_a_colon_in_a_path_line_stays_an_item(self):
        annotated = "tests/test_a.py: covers the edge case"
        for paths in ((annotated, "tests/test_b.py"), ("tests/test_b.py", annotated)):
            with self.subTest(paths=paths):
                reply = "TESTS:\n" + "\n".join("- " + path for path in paths) + "\n"
                self.assertEqual(flow.parse_block(reply), list(paths))


if __name__ == "__main__":
    unittest.main()
