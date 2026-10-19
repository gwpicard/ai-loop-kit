import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
from habits import add


class Oracle(unittest.TestCase):
    def test_keep_existing_items(self):
        self.assertEqual(add(["read"], "walk"), ["read", "walk"],
                         "existing items must stay")

    def test_ignore_duplicates(self):
        self.assertEqual(add(["read"], "read"), ["read"],
                         "duplicates must be ignored")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
