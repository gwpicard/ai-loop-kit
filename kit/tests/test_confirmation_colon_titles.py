import unittest

import pass_


class ConfirmationColonTitlesTest(unittest.TestCase):
    def test_bare_titles_survive_in_both_confirmation_blocks(self):
        titles = ["CLI: empty input", "Repeated run fails"]
        for name in ("CONFIRMED", "RUBRIC CONFIRMED"):
            for ordered in (titles, titles[::-1]):
                for boundary in ("REJECTED:", "**RUBRIC REJECTED**:", "**HELD:**"):
                    with self.subTest(name=name, titles=ordered, boundary=boundary):
                        reply = (name + ":\n" + "\n".join(ordered) + "\n"
                                 + boundary + "\nOther finding | rejected\n")
                        self.assertEqual(pass_.findings(reply, name),
                                         [(title, "", "") for title in ordered])


if __name__ == "__main__":
    unittest.main()
