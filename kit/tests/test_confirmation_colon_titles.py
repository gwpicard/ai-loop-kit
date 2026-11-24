import unittest

import pass_


class ConfirmationColonTitlesTest(unittest.TestCase):
    def test_colon_titles_survive_in_either_position_before_rejected_block(self):
        colon = ("CLI: empty input", "crashes at cli.py:12", "")
        other = ("Repeated run fails", "loses state at cli.py:24", "")
        for name in ("CONFIRMED", "RUBRIC CONFIRMED"):
            rejected = "RUBRIC REJECTED" if name.startswith("RUBRIC") else "REJECTED"
            for rows in ((colon, other), (other, colon)):
                with self.subTest(name=name, rows=rows):
                    reply = name + ":\n" + "\n".join("%s | %s" % row[:2] for row in rows)
                    reply += "\n" + rejected + ":\nWrong claim | allowed behaviour\n"
                    self.assertEqual(pass_.findings(reply, name), list(rows))


if __name__ == "__main__":
    unittest.main()
