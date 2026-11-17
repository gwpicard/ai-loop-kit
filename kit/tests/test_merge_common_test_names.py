import unittest

import merge


class CommonTestNamesTest(unittest.TestCase):
    def test_conventional_test_files_are_tests(self):
        for path in ("app/tests.py", "test.py", "conftest.py", "app/conftest.py"):
            self.assertTrue(merge.is_test_file(path), path)


if __name__ == "__main__":
    unittest.main()
