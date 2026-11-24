"""Select existing tests through merge and the session check command."""
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

from kit.tests import test_flow as flow_fixture
from kit.tests import test_merge_full_suite_cadence as cadence
from kit.tests.helpers import make_repo, run_git
import common
import merge


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "kit"


class ImportSelectionTest(unittest.TestCase):
    def setUp(self):
        self.fixture = cadence.FullSuiteCadenceTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.work = Path(self.fixture.work)
        self.write({
            "app.py": "value = 1\n",
            "pkg/__init__.py": "",
            "pkg/engine.py": "value = 1\n",
            "pkg/unrelated.py": "value = 1\n",
            "tests/__init__.py": "",
            "tests/test_locked.py": "# Locked acceptance test.\n",
            "tests/test_unrelated.py": "from pkg import unrelated\n",
        })
        self.save_base()

    def write(self, files):
        for name, text in files.items():
            path = self.work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def save_base(self):
        run_git(["add", "-A"], self.work)
        run_git(["commit", "-m", "Prepare import selection fixture"], self.work)
        run_git(["push", "origin", "HEAD:loop/main"], self.work)
        self.start = common.git(["rev-parse", "HEAD"], self.work)

    def exercise(self, entry):
        self.fixture.trace.write_text("")
        if entry == "merge":
            # merge_process uses the public merge gate in a fresh interpreter.
            result = self.fixture.merge_process()
            self.assertTrue(result["ok"], result["reason"])
        else:
            env = {k: v for k, v in os.environ.items() if not k.startswith("LOOP_")}
            env.update(LOOP_START=self.start, LOOP_LOCKED="tests/test_locked.py",
                       LOOP_PROJECT=str(self.work), LOOP_ROLE="builder")
            result = subprocess.run([str(KIT / "bin/loop"), "check"], cwd=self.work,
                                    env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.fixture.commands()
        self.assertEqual(calls[-1], "check", calls)
        self.assertTrue(calls[0].startswith("targeted "), calls)
        return json.loads(calls[0].removeprefix("targeted "))

    def assert_selection(self, entry, expected):
        self.assertEqual(set(self.exercise(entry)), {"tests/test_locked.py", *expected})

    def test_python_import_forms_at_merge_and_loop_check(self):
        imports = {
            "tests/test_direct.py": "import pkg.engine as subject\n",
            "tests/test_from_package.py": "from pkg import engine as subject\n",
            "tests/test_from_module.py": "from pkg.engine import (\n    value,\n)\n",
            "tests/test_comment_only.py": "# pkg.engine is mentioned, but never imported.\n",
        }
        imports["pkg/tests/test_relative.py"] = "from .. import engine\n"
        imports["pkg/tests/__init__.py"] = ""
        self.write(imports)
        self.save_base()
        self.fixture.candidate({"pkg/engine.py": "value = 2\n"})
        expected = {p for p in imports if merge.is_test_module(p)
                    and p != "tests/test_comment_only.py"}
        for entry in ("check", "merge"):
            with self.subTest(entry=entry):
                self.assert_selection(entry, expected)

    def test_fallback_for_other_languages_and_unparseable_python(self):
        self.write({
            "src/widget.ts": "export const value = 1;\n",
            "tests/widget.spec.ts": "import {value} from '../src/widget';\n",
            "tests/other.spec.ts": "// Unrelated fixture.\n",
            "tests/test_legacy.py": "import pkg.engine\nthis is invalid Python !!!\n",
        })
        self.save_base()
        self.fixture.candidate({"src/widget.ts": "export const value = 2;\n",
                                "pkg/engine.py": "value = 2\n"})
        for entry in ("merge", "check"):
            with self.subTest(entry=entry):
                self.assert_selection(entry, {"tests/widget.spec.ts", "tests/test_legacy.py"})

    def test_support_imports_and_test_importers_reach_a_fixed_point(self):
        self.write({
            "tests/helpers.py": "value = 1\n",
            "tests/test_z_fixture.py": "from .helpers import value\n",
            "tests/test_b_reuse.py": "from tests.test_z_fixture import value\n",
            "tests/test_a_reuse.py": "from tests import test_b_reuse\n",
        })
        self.save_base()
        self.fixture.candidate({"tests/helpers.py": "value = 2\n"})
        for entry in ("check", "merge"):
            with self.subTest(entry=entry):
                self.assert_selection(entry, {"tests/test_z_fixture.py", "tests/test_b_reuse.py",
                                              "tests/test_a_reuse.py"})

    def test_importers_of_a_locked_module_are_also_selected(self):
        self.write({"tests/test_reuse.py": "from tests import test_locked\n"})
        self.save_base()
        self.fixture.candidate({"app.py": "value = 2\n"})
        for entry in ("merge", "check"):
            with self.subTest(entry=entry):
                self.assert_selection(entry, {"tests/test_reuse.py"})

    def test_selection_cap_runs_full_command_and_records_a_full_merge(self):
        limits = [(name, value) for name, value in vars(merge).items()
                  if name.isupper() and type(value) is int and value > 0
                  and any(word in name for word in ("TARGET", "SELECT", "MODULE"))]
        self.assertTrue(limits, "Name the targeted module cap as a constant in merge.py")
        self.assertEqual(len(limits), 1, limits)
        _, cap = limits[0]
        modules = {"tests/test_import_%04d.py" % i for i in range(cap - 1)}
        self.write({name: "import app\n" for name in modules})
        # There is already one locked module, so this selection equals the cap.
        if modules:
            self.save_base()
        self.fixture.candidate({"app.py": "value = 2\n"})
        self.assert_selection("merge", modules)
        self.assertFalse(self.fixture.merged_events()[-1]["full_suite"])
        self.fixture.trace.write_text("")
        # One more importer exceeds the cap, including the locked module.
        self.fixture.candidate({"app.py": "value = 3\n",
                                "tests/test_over_cap.py": "import app\n"})
        result = self.fixture.merge_process()
        self.assertTrue(result["ok"], result["reason"])
        self.assertEqual(self.fixture.commands(), ["full " + self.fixture.sha, "check"])
        self.assertTrue(self.fixture.merged_events()[-1]["full_suite"])

    def test_merge_log_explains_each_extra_module(self):
        self.write({"tests/test_engine.py": "from pkg import engine\n",
                    "tests/test_reuse.py": "from tests import test_engine\n"})
        self.save_base()
        self.fixture.candidate({"pkg/engine.py": "value = 2\n"})
        outputs = []
        real_run = subprocess.run

        def record(*args, **kwargs):
            result = real_run(*args, **kwargs)
            if isinstance(result.stdout, str):
                outputs.append(result.stdout)
            return result

        with mock.patch.object(subprocess, "run", side_effect=record):
            result = self.fixture.merge_process()
        self.assertTrue(result["ok"], result["reason"])
        lines = "\n".join(outputs).splitlines()
        for module, cause in (("tests/test_engine.py", "pkg/engine.py"),
                              ("tests/test_reuse.py", "tests/test_engine.py")):
            self.assertTrue(any(module in line and cause in line and "import" in line.lower()
                                for line in lines), (module, cause, lines))


class SelectionBuildNoteTest(unittest.TestCase):
    def test_build_note_explains_each_extra_module(self):
        fixture = flow_fixture.FlowTest()
        fixture.setUpClass()
        self.addCleanup(fixture.tearDownClass)
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        work = Path(fixture.work)
        files = {"app.py": "value = 1\n",
                 "tests/test_engine.py": "import app\n",
                 "tests/test_reuse.py": "from tests import test_engine\n"}
        for name, text in files.items():
            path = work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        raw = json.loads((work / "loop.json").read_text())
        assertion = 'from pathlib import Path; assert "value = 2" in Path("app.py").read_text()'
        raw["Test files command"] = "%s -c %s {files}" % (
            shlex.quote(sys.executable), shlex.quote(assertion))
        (work / "loop.json").write_text(json.dumps(raw))
        run_git(["add", "-A"], work)
        run_git(["commit", "-m", "Prepare dependent tests"], work)
        run_git(["push", "origin", "HEAD:loop/main"], work)
        fixture.build_scenario(builder=[{"files": {"app.py": "value = 2\n"},
                                         "reply": "BUILT:\nChanged the value.\nDEVIATIONS:\nnone"}])
        sent = fixture.spy_gh()
        self.assertEqual(fixture.build().status, "merged")
        notes = [body for args, body in sent if args[:2] == ["issue", "comment"]
                 and body.startswith("## Built")]
        self.assertEqual(len(notes), 1, notes)
        for module, cause in (("tests/test_engine.py", "app.py"),
                              ("tests/test_reuse.py", "tests/test_engine.py")):
            self.assertTrue(any(module in line and cause in line and "import" in line.lower()
                                for line in notes[0].splitlines()), notes[0])


class HistoricalSelectionTest(unittest.TestCase):
    def test_both_regression_commits_select_the_tests_that_failed(self):
        cases = (
            ("6977672f0f438ce339c585620f0492a909d894c6", {"kit/tests/test_report.py"}),
            ("7d2848630dd4abc0872b5431e033463bf2f57b8c",
             {"kit/tests/test_loop_json.py", "kit/tests/test_loop_failed_crash_comment_polling.py"}),
        )
        for commit, expected in cases:
            with self.subTest(commit=commit), tempfile.TemporaryDirectory() as folder:
                for ref in (commit, commit + "^"):
                    result = subprocess.run(["git", "cat-file", "-e", ref + "^{commit}"],
                                            cwd=ROOT, capture_output=True)
                    if result.returncode:
                        self.skipTest("Historical commit unavailable: " + ref)
                # Copy historical blobs, without changing this worktree or its refs.
                archive = subprocess.check_output(["git", "archive", commit + "^"], cwd=ROOT)
                with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
                    files = {member.name: tree.extractfile(member).read().decode("utf-8")
                             for member in tree.getmembers()
                             if member.isfile() and member.name.endswith(".py")}
                files["tests/test_locked.py"] = "# Locked fixture.\n"
                work, _ = make_repo(folder, files)
                base = common.git(["rev-parse", "HEAD"], work)
                changed = common.git(["diff", "--name-only", commit + "^", commit], ROOT).splitlines()
                for name in changed:
                    if name.endswith(".py"):
                        path = Path(work, name)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(subprocess.check_output(["git", "show", commit + ":" + name], cwd=ROOT))
                settings = {"Test command": "full-suite", "Test files command": "targeted {files}"}
                command, description = merge.targeted_command(settings, work, base, ["tests/test_locked.py"])
                selected = set(shlex.split(command)[1:]) if command != "full-suite" else set()
                for module in sorted(expected):
                    with self.subTest(module=module):
                        self.assertTrue(module in selected or command == "full-suite" and module in description,
                                        (module, command, description))
