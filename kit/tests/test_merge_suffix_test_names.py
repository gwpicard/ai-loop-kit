import unittest

import merge


class SuffixTestNamesTest(unittest.TestCase):
    def test_conventional_suffix_test_files_outside_test_folders_are_tests(self):
        for path in ("Sources/App/FooTests.swift", "src/FooSpec.scala", "src/FooSpec.hs",
                     "src/foo_tests.rs", "web/login-test.js"):
            self.assertTrue(merge.is_test_file(path), path)


if __name__ == "__main__":
    unittest.main()
