import tempfile

from kit.tests.helpers import make_repo
from kit.tests.test_guard import GuardCase


class TestTestFilesIdentifiers(GuardCase):
    def test_module_identifiers_count_towards_the_complete_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            work, _ = make_repo(folder, {"kit/tests/test_one.py": "pass\n",
                                         "kit/tests/test_two.py": "pass\n"})
            for role in ("builder", "reviewer", "test-writer", "pass"):
                kw = dict(role=role, cwd=work, test="tests/run-all.sh",
                          files="python3 kit/tests/run.py {files}")
                baseline = self.bash("tests/run-all.sh", **kw)
                for selection in ("kit.tests.test_one kit.tests.test_two",
                                  "test_one test_two",
                                  "kit/tests/test_one.py kit.tests.test_two"):
                    with self.subTest(role=role, selection=selection):
                        result = self.bash("python3 kit/tests/run.py " + selection, **kw)
                        self.refused(result)
                        self.assertEqual(result.stderr, baseline.stderr)
                self.allowed(self.bash("python3 kit/tests/run.py kit.tests.test_one", **kw))
                self.allowed(self.bash("python3 kit/tests/run.py test_two", **kw))

    def test_redirection_does_not_supply_file_arguments(self):
        for role in ("builder", "reviewer", "test-writer", "pass"):
            kw = dict(role=role, test="tests/run-all.sh",
                      files="python3 kit/tests/run.py {files}")
            baseline = self.bash("tests/run-all.sh", **kw)
            for redirect in ("> /dev/null", ">/dev/null", "2>/dev/null",
                             ">> '/dev/null'", "< /dev/null > /dev/null"):
                with self.subTest(role=role, redirect=redirect):
                    result = self.bash("python3 kit/tests/run.py " + redirect, **kw)
                    self.refused(result)
                    self.assertEqual(result.stderr, baseline.stderr)
                    self.allowed(self.bash("python3 kit/tests/run.py tests/test_app.py " + redirect, **kw))
            self.allowed(self.bash("python3 kit/tests/run.py '>'", **kw))
