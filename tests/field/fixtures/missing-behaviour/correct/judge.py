import unittest

from habits import add


class PieceJudge(unittest.TestCase):
    def test_add_first_item(self):
        self.assertEqual(add([], "read"), ["read"])


if __name__ == "__main__":
    unittest.main()
