import unittest

import merge


class JunitPrefixNamesTest(unittest.TestCase):
    def test_junit_prefix_and_suffix_are_test_modules(self):
        for path in ("src/TestFoo.java", "src/FooTests.java"):
            with self.subTest(path=path):
                self.assertTrue(merge.is_test_module(path), path)
                self.assertTrue(merge.is_test_file(path), path)

    def test_junit_prefix_keeps_case_and_filename_boundaries(self):
        for path in ("src/testFoo.java", "src/ContestFoo.java", "TestFolder/Foo.java"):
            with self.subTest(path=path):
                self.assertFalse(merge.is_test_module(path), path)
                self.assertFalse(merge.is_test_file(path), path)


if __name__ == "__main__":
    unittest.main()
