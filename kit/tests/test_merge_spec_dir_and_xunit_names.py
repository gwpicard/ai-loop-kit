import unittest

import merge


class SpecDirAndXunitNamesTest(unittest.TestCase):
    def test_files_in_a_spec_folder_are_test_files(self):
        for path in ("spec/spec_helper.rb", "spec/factories/users.rb"):
            self.assertTrue(merge.is_test_file(path), path)

    def test_test_class_files_of_other_languages_are_test_files(self):
        for path in ("src/UserTest.php", "src/UserTest.kt", "src/UserTests.cs"):
            self.assertTrue(merge.is_test_file(path), path)


if __name__ == "__main__":
    unittest.main()
