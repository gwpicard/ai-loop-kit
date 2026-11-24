import unittest

import pass_


class RubricRejectedLeaksIntoConfirmedTest(unittest.TestCase):
    def test_adjacent_rubric_blocks_keep_rejected_titles_out_of_confirmed(self):
        reply = (
            "RUBRIC CONFIRMED:\n"
            "none\n"
            "RUBRIC REJECTED:\n"
            "Wrong claim | the behaviour is allowed by PLAN.md\n"
            "CONFIRMED:\n"
            "none\n"
            "HELD:\n"
            "none\n"
            "REJECTED:\n"
            "none\n"
        )
        self.assertEqual(pass_.findings(reply, "RUBRIC REJECTED"), [
            ("Wrong claim", "the behaviour is allowed by PLAN.md", ""),
        ])
        self.assertEqual(pass_.findings(reply, "RUBRIC CONFIRMED"), [],
                         "A rejected rubric finding must not be accepted for filing.")


if __name__ == "__main__":
    unittest.main()
