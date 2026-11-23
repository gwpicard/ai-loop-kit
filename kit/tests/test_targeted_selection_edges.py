"""Exercise selection against the reviewed tree and removed modules."""
import unittest

from kit.tests import test_targeted_import_selection as selection


class SelectionEdgesTest(unittest.TestCase):
    def setUp(self):
        self.fixture = selection.ImportSelectionTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_merge_reads_imports_from_reviewed_commit(self):
        fixture = self.fixture
        fixture.write({"tests/test_engine.py": "import app\n"})
        fixture.save_base()
        fixture.fixture.candidate({"app.py": "value = 2\n",
                                   "tests/test_added.py": "import app\n"})
        fixture.write({"tests/test_engine.py": "# Unsaved work has different imports.\n",
                       "tests/test_added.py": "# The reviewed commit still imports app.\n"})
        fixture.assert_selection("merge", {"tests/test_engine.py", "tests/test_added.py"})

    def test_deleted_modules_select_importers_without_running_deleted_tests(self):
        fixture = self.fixture
        fixture.write({"tests/test_source.py": "import app\n",
                       "tests/test_removed.py": "value = 1\n",
                       "tests/test_reuse.py": "from tests.test_removed import value\n"})
        fixture.save_base()
        (fixture.work / "app.py").unlink()
        (fixture.work / "tests/test_removed.py").unlink()
        fixture.assert_selection("check", {"tests/test_source.py", "tests/test_reuse.py"})

    def test_check_reports_import_reasons_on_one_pass_line(self):
        fixture = self.fixture
        fixture.write({"tests/test_engine.py": "import app\n"})
        fixture.save_base()
        fixture.fixture.candidate({"app.py": "value = 2\n"})
        outputs = []
        real_run = selection.subprocess.run

        def record(*args, **kwargs):
            result = real_run(*args, **kwargs)
            if isinstance(result.stdout, str):
                outputs.append(result.stdout)
            return result

        with selection.mock.patch.object(selection.subprocess, "run", side_effect=record):
            fixture.assert_selection("check", {"tests/test_engine.py"})
        output = next(text for text in outputs if text.startswith("passed:"))
        self.assertEqual(len(output.splitlines()), 1, output)
        self.assertIn("tests/test_engine.py: imports app.py", output)
