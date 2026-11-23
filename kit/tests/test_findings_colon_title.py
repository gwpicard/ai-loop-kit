import unittest

import pass_


class FindingsColonTitleTest(unittest.TestCase):
    def test_a_colon_in_a_title_does_not_discard_the_findings(self):
        reply = (
            "FINDINGS:\n"
            "CLI: empty input | crashes on empty input | .loop/pass/kit/tests/test_empty.py\n"
            "Repeated run fails | loses the saved state | .loop/pass/kit/tests/test_repeat.py\n"
        )
        self.assertEqual(pass_.findings(reply), [
            ("CLI: empty input", "crashes on empty input", ".loop/pass/kit/tests/test_empty.py"),
            ("Repeated run fails", "loses the saved state", ".loop/pass/kit/tests/test_repeat.py"),
        ])


if __name__ == "__main__":
    unittest.main()
