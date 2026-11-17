import unittest

import merge


class JunitNameCaseTest(unittest.TestCase):
    def test_source_files_ending_in_test_are_not_tests(self):
        for path in ("src/Contest.java", "src/Latest.java", "src/Foo.java"):
            self.assertFalse(merge.is_test_file(path), path)

    def test_junit_file_is_a_test(self):
        self.assertTrue(merge.is_test_file("src/FooTest.java"))


if __name__ == "__main__":
    unittest.main()
