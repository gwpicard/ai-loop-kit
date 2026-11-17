import unittest

import merge


class SpecAndJunitNamesTest(unittest.TestCase):
    def test_rspec_and_junit_files_are_tests(self):
        for path in ("app/user_spec.rb", "src/FooTest.java"):
            self.assertTrue(merge.is_test_file(path), path)


if __name__ == "__main__":
    unittest.main()
