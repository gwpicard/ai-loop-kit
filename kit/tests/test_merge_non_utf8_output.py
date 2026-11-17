import tempfile
import unittest

from kit.tests.helpers import make_repo
import common
import merge


class NonUtf8OutputTest(unittest.TestCase):
    def test_passing_test_command_with_non_utf8_output_is_not_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            work, _ = make_repo(tmp, {"app.py": "x = 1\n"})
            sha = common.git(["rev-parse", "HEAD"], cwd=work)
            command = "printf 'caf\\351\\n'"
            try:
                result = merge.run_tests(work, sha, command)
            except UnicodeDecodeError as e:
                self.fail("a passing command with non-UTF-8 output raised: %s" % e)
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
