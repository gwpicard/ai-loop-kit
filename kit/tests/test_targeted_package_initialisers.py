"""Exercise ancestor package initialisers through merge and loop check."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from kit.tests import test_targeted_import_selection as selection
from kit.tests.helpers import make_repo
import common


FILES = {
    "subject/__init__.py": "ROOT_VALUE = 1\n",
    "subject/nested/__init__.py": "VALUE = 1\n",
    "subject/nested/child.py": "from subject import ROOT_VALUE\nfrom . import VALUE\nTOTAL = ROOT_VALUE + VALUE\n",
    "tests/__init__.py": "",
    "tests/test_locked.py": "import unittest\n",
    "tests/test_child.py": "import subject.nested.child\nassert subject.nested.child.TOTAL == 2\n",
    "tests/test_from.py": "from subject.nested.child import TOTAL\nassert TOTAL == 2\n",
    "subject/nested/test_relative.py": "from . import child\nassert child.TOTAL == 2\n",
    "tests/test_unrelated.py": "import unittest\nassert False, 'unrelated test must not run'\n",
}
IMPORTERS = {"tests/test_child.py", "tests/test_from.py", "subject/nested/test_relative.py"}


class PackageInitialiserTest(unittest.TestCase):
    def test_check_runs_failing_importers_of_each_changed_ancestor(self):
        command = shlex.quote(sys.executable) + " -m unittest"
        for initialiser, content in (("subject/__init__.py", "ROOT_VALUE = 2\n"),
                                     ("subject/nested/__init__.py", "VALUE = 2\n")):
            with self.subTest(initialiser=initialiser), tempfile.TemporaryDirectory() as folder:
                files = dict(FILES, **{"loop.json": json.dumps({
                    "Test command": command + " discover",
                    "Test files command": command + " {files}",
                })})
                work, _ = make_repo(folder, files)
                start = common.git(["rev-parse", "HEAD"], work)
                Path(work, initialiser).write_text(content)
                env = {k: v for k, v in os.environ.items() if not k.startswith("LOOP_")}
                env.update(LOOP_START=start, LOOP_LOCKED="tests/test_locked.py",
                           LOOP_PROJECT=work, LOOP_ROLE="builder")
                result = subprocess.run([str(selection.KIT / "bin/loop"), "check"],
                                        cwd=work, env=env, capture_output=True, text=True, timeout=30)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("AssertionError", result.stdout)
                for path in IMPORTERS:
                    self.assertIn(path, result.stdout)
                self.assertNotIn("tests/test_unrelated.py", result.stdout)

    def test_merge_selects_importers_of_a_changed_ancestor(self):
        fixture = selection.ImportSelectionTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.write(FILES)
        fixture.save_base()
        fixture.fixture.candidate({"subject/__init__.py": "ROOT_VALUE = 2\n"})
        fixture.assert_selection("merge", IMPORTERS)
