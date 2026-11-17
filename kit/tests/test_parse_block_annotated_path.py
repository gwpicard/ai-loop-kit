import unittest

import flow


class ParseBlockAnnotatedPathTest(unittest.TestCase):
    def test_note_after_a_backticked_path_is_dropped(self):
        self.assertEqual(flow.parse_block("TESTS:\n- `tests/test_a.py` (new)\n"), ["tests/test_a.py"])


if __name__ == "__main__":
    unittest.main()
