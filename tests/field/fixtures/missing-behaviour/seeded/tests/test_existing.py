import unittest

from habits import add


class ExistingTests(unittest.TestCase):
    def test_keep_existing_items(self):
        self.assertEqual(add(["read"], "walk"), ["read", "walk"],
                         "existing items must stay")
