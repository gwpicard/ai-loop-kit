import json
import sys
import unittest
from pathlib import Path

PROJECT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(PROJECT))
from habits import add  # noqa: E402


class Oracle(unittest.TestCase):
    def test_approved_behaviour(self):
        self.assertEqual(add([], "read"), ["read"])
        self.assertEqual(add(["read"], "walk"), ["read", "walk"])
        self.assertEqual(add(["read"], "read"), ["read"])

    def test_no_false_block(self):
        review = json.loads((PROJECT / "review.json").read_text())
        self.assertEqual(review, {"verdict": "approve", "findings": []},
                         "unsupported finding must not block")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
