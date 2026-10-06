"""Unit tests for kit/scripts/loop/bar.py: the frozen bar and its seven kinds of change.

They carry forward every case of the retired bar guard rehearsal
(`tests/bar-guard-rehearsal.sh` and the guards it drove), minus the named-change escape,
which is gone: a change to the bar is listed, and nothing names it away. The project is a
real throwaway Git repository: a base commit, a judge commit (the frozen first commit of
the piece branch) and the attempt on top.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import bar  # noqa: E402

BASE_FILES = {
    "app/orders.py": "def total():\n    return 10\n",
    "app/legacy.py": "import os  # noqa\n\n\ndef old():\n    return os.sep\n",
    "tests/test_orders.py": "def test_total():\n    assert True\n",
    "web/cart.test.js": "it('adds', () => { expect(1).toBe(1) })\n",
    "pkg/cart_test.go": "package pkg\n\nfunc TestCart(t *testing.T) {}\n",
    "tests/fixtures/orders.json": '{"orders": 1}\n',
    "jest.config.js": "module.exports = {\n  testMatch: ['**/*.test.js'],\n};\n",
    "pyproject.toml": (
        "[project]\nname = \"shop\"\ndependencies = []\n\n"
        "[tool.ruff]\nline-length = 100\nselect = ['E', 'F']\n"
    ),
    "web/__snapshots__/cart.test.js.snap": "exports[`cart 1`] = `one`;\n",
    ".github/workflows/checks.yml": "on: pull_request\njobs: {}\n",
    ".agents/tools/gate.py": "print('gate')\n",
    "README.md": "A shop.\n",
}
JUDGE_FILES = {
    "tests/acceptance/test_refund.py": "def test_refund():\n    assert refund() == 10\n",
    "tests/acceptance/test_refund_total.py": (
        "from app.orders import total  # noqa\n\n\ndef test_refund_total():\n"
        "    assert total() == 0\n"
    ),
}


class Repo:
    """A project with a base commit, a judge commit and room for an attempt."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp()) / "project"
        self.root.mkdir()
        self.git("init", "-q", "-b", "main")
        self.write(BASE_FILES)
        self.commit("Start")
        self.base = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "-b", "piece-1")
        self.write(JUDGE_FILES)
        self.commit("Judge files")
        self.judge = self.git("rev-parse", "HEAD")
        self.files = sorted(JUDGE_FILES)

    def git(self, *args: str) -> str:
        done = subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=T", "-c", "user.email=t@example.invalid",
             "-c", "commit.gpgsign=false", "-c", "core.excludesFile=/dev/null", *args],
            capture_output=True, text=True, check=True,
        )
        return done.stdout.strip()

    def write(self, files: dict[str, str]) -> None:
        for name, text in files.items():
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)

    def attempt(self, files: dict[str, str] | None = None, *, remove: tuple[str, ...] = (),
                move: tuple[tuple[str, str], ...] = ()) -> str:
        """Make the attempt's commit and return its hash."""
        self.write(files or {})
        for name in remove:
            self.git("rm", "-q", name)
        for old, new in move:
            (self.root / new).parent.mkdir(parents=True, exist_ok=True)
            self.git("mv", old, new)
        self.commit("The attempt")
        return self.git("rev-parse", "HEAD")

    def changes(self, *, scaffold: bool = False) -> list[tuple[str, str]]:
        found = bar.changes(
            self.root, self.base, self.git("rev-parse", "HEAD"),
            judge_commit=None if scaffold else self.judge,
            judge_files=[] if scaffold else self.files,
        )
        return [(c.kind, c.path) for c in found]


class Case(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repo()

    def lists(self, kind: str, path: str, **attempt: object) -> None:
        self.repo.attempt(**attempt)  # type: ignore[arg-type]
        found = self.repo.changes()
        self.assertIn((kind, path), found, found)


class TheCleanBar(Case):
    def test_an_attempt_that_changed_nothing_guarded_lists_nothing(self) -> None:
        self.assertEqual(self.repo.changes(), [])

    def test_a_change_to_source_code_alone_lists_nothing(self) -> None:
        self.repo.attempt({"app/orders.py": "def total():\n    return 11\n"})
        self.assertEqual(self.repo.changes(), [])

    def test_a_new_test_file_changes_no_existing_test(self) -> None:
        self.repo.attempt({"tests/test_receipt.py": "def test_receipt():\n    assert True\n"})
        self.assertEqual(self.repo.changes(), [])

    def test_the_seven_kinds_are_the_old_guards_seven(self) -> None:
        self.assertEqual(
            bar.KINDS,
            ("acceptance-check", "existing-test", "skip-or-focus", "suppression",
             "tool-settings", "snapshot", "guarded-file"),
        )


class TheJudgeFiles(Case):
    def test_an_edited_judge_file_is_an_acceptance_check_change(self) -> None:
        self.lists("acceptance-check", "tests/acceptance/test_refund.py",
                   files={"tests/acceptance/test_refund.py":
                          "def test_refund():\n    assert True\n"})

    def test_a_deleted_judge_file_is_an_acceptance_check_change(self) -> None:
        self.lists("acceptance-check", "tests/acceptance/test_refund_total.py",
                   remove=("tests/acceptance/test_refund_total.py",))

    def test_a_judge_file_moved_away_is_listed_under_its_old_path(self) -> None:
        self.lists("acceptance-check", "tests/acceptance/test_refund.py",
                   move=(("tests/acceptance/test_refund.py", "app/kept.py"),))

    def test_a_judge_file_that_loses_its_executable_bit_is_a_change(self) -> None:
        (self.repo.root / "tests/acceptance/test_refund.py").chmod(0o755)
        self.repo.commit("mode")
        self.assertEqual(self.repo.changes(),
                         [("acceptance-check", "tests/acceptance/test_refund.py")])

    def test_the_suppression_a_judge_file_carries_is_the_bar_not_the_build(self) -> None:
        self.repo.attempt({"app/orders.py": "def total():\n    return 3\n"})
        self.assertNotIn("suppression", [kind for kind, _ in self.repo.changes()])

    def test_a_scaffold_piece_has_no_judge_files_and_so_no_acceptance_check(self) -> None:
        self.repo.git("checkout", "-q", "main")
        self.repo.git("checkout", "-q", "-b", "scaffold")
        self.repo.attempt(
            {"tests/acceptance/test_refund.py": "def test_refund():\n    assert True\n"})
        self.assertEqual(self.repo.changes(scaffold=True), [])


class TheExistingTests(Case):
    def test_an_existing_test_edited(self) -> None:
        self.lists("existing-test", "tests/test_orders.py",
                   files={"tests/test_orders.py": "def test_total():\n    pass\n"})

    def test_an_existing_test_deleted(self) -> None:
        self.lists("existing-test", "pkg/cart_test.go", remove=("pkg/cart_test.go",))

    def test_an_existing_test_moved_away_from_a_test_path(self) -> None:
        self.lists("existing-test", "tests/test_orders.py",
                   move=(("tests/test_orders.py", "app/kept.py"),))

    def test_an_existing_fixture_changed(self) -> None:
        self.lists("existing-test", "tests/fixtures/orders.json",
                   files={"tests/fixtures/orders.json": '{"orders": 0}\n'})

    def test_a_loosened_assertion_in_an_existing_test(self) -> None:
        self.lists("existing-test", "tests/test_orders.py",
                   files={"tests/test_orders.py": "def test_total():\n    assert total() >= 0\n"})

    def test_a_raised_timeout_in_an_existing_test(self) -> None:
        self.lists("existing-test", "web/cart.test.js",
                   files={"web/cart.test.js": "jest.setTimeout(600000)\n"
                                              "it('adds', () => { expect(1).toBe(1) })\n"})

    def test_a_retry_added_to_an_existing_test(self) -> None:
        self.lists("existing-test", "web/cart.test.js",
                   files={"web/cart.test.js": "jest.retryTimes(5)\n"
                                              "it('adds', () => { expect(1).toBe(1) })\n"})

    def test_naming_the_change_in_a_spec_names_nothing(self) -> None:
        # The old guard let a `Changes the bar:` line name a change. There is no such escape.
        self.repo.attempt({"tests/test_orders.py": "def test_total():\n    pass\n"})
        found = bar.changes(self.repo.root, self.repo.base, self.repo.git("rev-parse", "HEAD"),
                            judge_commit=self.repo.judge, judge_files=self.repo.files)
        self.assertEqual([c.kind for c in found], ["existing-test"])
        self.assertNotIn("named", " ".join(c.text() for c in found))


class TheSkipMarkers(Case):
    def test_each_skip_or_focus_marker_added_to_a_test(self) -> None:
        for marker, path, text in (
            (".only(", "web/cart.test.js", "it.only('adds', () => { expect(1).toBe(1) })\n"),
            ("xit(", "web/cart.test.js", "xit('adds', () => { expect(1).toBe(1) })\n"),
            (".skip(", "web/cart.test.js", "it.skip('adds', () => { expect(1).toBe(1) })\n"),
            ("@pytest.mark.skip", "tests/test_orders.py",
             "import pytest\n\n\n@pytest.mark.skip\ndef test_total():\n    assert True\n"),
            ("@pytest.mark.xfail", "tests/test_orders.py",
             "import pytest\n\n\n@pytest.mark.xfail\ndef test_total():\n    assert True\n"),
            ("@unittest.skip", "tests/test_orders.py",
             "import unittest\n\n\n@unittest.skip('later')\ndef test_total():\n    assert True\n"),
            ("t.Skip(", "pkg/cart_test.go",
             "package pkg\n\nfunc TestCart(t *testing.T) { t.Skip(\"later\") }\n"),
        ):
            with self.subTest(marker=marker):
                repo = Repo()
                repo.attempt({path: text})
                self.assertIn(("skip-or-focus", path), repo.changes())

    def test_a_marker_in_a_file_that_is_not_a_test_is_not_a_skip(self) -> None:
        self.repo.attempt({"app/orders.py": "# it.skip( is only text here\n"})
        self.assertEqual(self.repo.changes(), [])

    def test_a_skip_marker_taken_out_is_not_listed_as_a_skip(self) -> None:
        self.repo.attempt({"web/cart.test.js": "it('adds', () => { expect(1).toBe(2) })\n"})
        self.assertNotIn("skip-or-focus", [k for k, _ in self.repo.changes()])


class TheSuppressions(Case):
    def test_each_suppression_added(self) -> None:
        for marker, path, text in (
            ("type: ignore", "app/orders.py", "def total():  # type: ignore\n    return 10\n"),
            ("eslint-disable", "web/cart.js", "// eslint-disable-next-line\nvar a = 1\n"),
            ("@ts-ignore", "web/cart.ts", "// @ts-ignore\nconst a: number = 'x'\n"),
            ("@ts-expect-error", "web/cart.ts", "// @ts-expect-error\nconst a: number = 'x'\n"),
            ("# noqa", "app/orders.py", "import os  # noqa\n\n\ndef total():\n    return 10\n"),
            ("# pylint: disable", "app/orders.py",
             "def total():  # pylint: disable=invalid-name\n    return 10\n"),
            ("//nolint", "pkg/cart.go", "package pkg\n\nvar a = 1 //nolint\n"),
        ):
            with self.subTest(marker=marker):
                repo = Repo()
                repo.attempt({path: text})
                self.assertIn(("suppression", path), repo.changes())

    def test_a_suppression_taken_out_is_not_listed(self) -> None:
        self.repo.attempt({"app/legacy.py": "import os\n\n\ndef old():\n    return os.sep\n"})
        self.assertEqual(self.repo.changes(), [])

    def test_a_line_edited_beside_its_suppression_adds_none(self) -> None:
        self.repo.attempt({"app/legacy.py": "import os  # noqa\n\n\ndef old():\n"
                                            "    return os.sep + os.sep\n"})
        self.assertEqual(self.repo.changes(), [])


class TheToolSettings(Case):
    def test_a_line_added_to_the_jest_settings(self) -> None:
        self.lists("tool-settings", "jest.config.js",
                   files={"jest.config.js": "module.exports = {\n  testMatch: ['**/*.test.js'],\n"
                                            "  testPathIgnorePatterns: ['refund'],\n};\n"})

    def test_each_new_settings_file(self) -> None:
        for name in ("vitest.config.ts", "eslint.config.mjs", ".eslintrc.json",
                     "tsconfig.build.json", ".coveragerc", "ruff.toml", "mypy.ini", "pytest.ini"):
            with self.subTest(name=name):
                repo = Repo()
                repo.attempt({name: "ignore = everything\n"})
                self.assertIn(("tool-settings", name), repo.changes())

    def test_a_new_setup_cfg_with_a_tool_section(self) -> None:
        self.repo.attempt({"setup.cfg": "[flake8]\nignore = everything\n"})
        self.assertIn(("tool-settings", "setup.cfg"), self.repo.changes())

    def test_a_line_added_in_a_tool_section_of_pyproject(self) -> None:
        self.repo.attempt({"pyproject.toml": BASE_FILES["pyproject.toml"] + "ignore = ['F401']\n"})
        self.assertIn(("tool-settings", "pyproject.toml"), self.repo.changes())

    def test_a_settings_line_taken_out_with_nothing_added(self) -> None:
        self.repo.attempt({"pyproject.toml": BASE_FILES["pyproject.toml"].replace(
            "select = ['E', 'F']\n", "")})
        self.assertEqual(self.repo.changes(), [("tool-settings", "pyproject.toml")])

    def test_a_raised_timeout_in_the_pytest_settings(self) -> None:
        self.repo.attempt({"pyproject.toml": BASE_FILES["pyproject.toml"]
                           + "\n[tool.pytest.ini_options]\ntimeout = 600\n"})
        self.assertIn(("tool-settings", "pyproject.toml"), self.repo.changes())

    def test_a_retry_added_to_the_tox_settings(self) -> None:
        self.repo.attempt({"tox.ini": "[testenv]\ncommands = pytest --reruns 5\n"})
        self.assertIn(("tool-settings", "tox.ini"), self.repo.changes())

    def test_a_settings_file_deleted(self) -> None:
        self.lists("tool-settings", "jest.config.js", remove=("jest.config.js",))

    def test_a_new_dependency_in_pyproject_is_not_a_settings_change(self) -> None:
        self.repo.attempt({"pyproject.toml": BASE_FILES["pyproject.toml"].replace(
            "dependencies = []", "dependencies = ['left-pad']")})
        self.assertEqual(self.repo.changes(), [])

    def test_a_comment_in_a_tool_section_is_not_a_settings_change(self) -> None:
        self.repo.attempt({"pyproject.toml": BASE_FILES["pyproject.toml"].replace(
            "[tool.ruff]\n", "[tool.ruff]\n# a note\n")})
        self.assertEqual(self.repo.changes(), [])


class TheSnapshotsAndGuardedFiles(Case):
    def test_an_existing_snapshot_rewritten(self) -> None:
        self.lists("snapshot", "web/__snapshots__/cart.test.js.snap",
                   files={"web/__snapshots__/cart.test.js.snap": "exports[`cart 1`] = `two`;\n"})

    def test_a_new_snapshot_is_not_an_updated_one(self) -> None:
        self.repo.attempt({"web/__snapshots__/refund.test.js.snap": "exports[`r 1`] = `x`;\n"})
        self.assertEqual(self.repo.changes(), [])

    def test_the_gate_script_changed(self) -> None:
        self.lists("guarded-file", ".agents/tools/gate.py",
                   files={".agents/tools/gate.py": "print('gate, but kinder')\n"})

    def test_each_guarded_path(self) -> None:
        for path in (".github/workflows/checks.yml", ".agents/hooks/state-guard.sh",
                     ".githooks/pre-commit", ".husky/pre-push", ".claude/settings.json",
                     ".claude/settings.local.json", ".agents/loop/policy.json"):
            with self.subTest(path=path):
                repo = Repo()
                repo.attempt({path: "changed\n"})
                self.assertIn(("guarded-file", path), repo.changes())


class WhenTheBarCannotBeRead(Case):
    def test_a_base_that_is_no_commit_raises_with_a_next_command(self) -> None:
        with self.assertRaises(bar.BarError) as raised:
            bar.changes(self.repo.root, "no-such-base", "HEAD", judge_commit=self.repo.judge,
                        judge_files=self.repo.files)
        self.assertTrue(raised.exception.next_command)

    def test_a_head_that_is_no_commit_raises(self) -> None:
        with self.assertRaises(bar.BarError):
            bar.changes(self.repo.root, self.repo.base, "no-such-head",
                        judge_commit=self.repo.judge, judge_files=self.repo.files)

    def test_a_judge_commit_that_is_gone_raises_and_never_passes(self) -> None:
        with self.assertRaises(bar.BarError):
            bar.changes(self.repo.root, self.repo.base, "HEAD", judge_commit="0" * 40,
                        judge_files=self.repo.files)

    def test_a_folder_that_is_no_repository_raises(self) -> None:
        with self.assertRaises(bar.BarError):
            bar.paths(Path(tempfile.mkdtemp()), "HEAD", [])


class ThePathsTheFirstLayerDenies(Case):
    def listed(self) -> list[str]:
        return bar.paths(self.repo.root, self.repo.base, self.repo.files)

    def test_it_holds_the_judge_files(self) -> None:
        for name in JUDGE_FILES:
            self.assertIn(name, self.listed())

    def test_it_holds_each_existing_test_fixture_snapshot_setting_and_guarded_file(self) -> None:
        listed = self.listed()
        for name in ("tests/test_orders.py", "web/cart.test.js", "pkg/cart_test.go",
                     "tests/fixtures/orders.json", "jest.config.js",
                     "web/__snapshots__/cart.test.js.snap", ".github/workflows/checks.yml",
                     ".agents/tools/gate.py"):
            self.assertIn(name, listed)

    def test_it_leaves_out_source_files_and_the_shared_manifest(self) -> None:
        listed = self.listed()
        for name in ("app/orders.py", "README.md", "pyproject.toml"):
            self.assertNotIn(name, listed)

    def test_every_listed_path_is_a_bar_change_when_it_is_edited(self) -> None:
        """The two layers agree: what the first layer denies, the second layer lists."""
        for name in self.listed():
            with self.subTest(name=name):
                repo = Repo()
                target = repo.root / name
                target.write_text(target.read_text(encoding="utf-8") + "\n# an edit\n",
                                  encoding="utf-8")
                repo.commit("edit")
                self.assertTrue(repo.changes(), f"editing {name} was not listed")


if __name__ == "__main__":
    unittest.main()
