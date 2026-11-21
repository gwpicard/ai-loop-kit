import contextlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from kit.tests.helpers import FakeGh, make_repo, settings_json
from kit.tests.test_setup import rule
import setup

KIT = pathlib.Path(__file__).resolve().parents[1]
REAL = json.loads((KIT / ".claude-plugin" / "plugin.json").read_text())["version"]


def plugin_copy(parent, version):
    """A copy of the plugin that says it is `version`."""
    dest = pathlib.Path(parent, "plugin-" + version)
    dest.mkdir()
    for name in ("scripts", "bin", ".claude-plugin"):
        shutil.copytree(KIT / name, dest / name, ignore=shutil.ignore_patterns("__pycache__"))
    manifest = dest / ".claude-plugin" / "plugin.json"
    data = json.loads(manifest.read_text())
    data["version"] = version
    manifest.write_text(json.dumps(data))
    return dest


def record(project, version):
    os.makedirs(os.path.join(project, ".loop"), exist_ok=True)
    pathlib.Path(project, ".loop", "kit-version").write_text(version + "\n")


def recorded(project):
    path = pathlib.Path(project, ".loop", "kit-version")
    return path.read_text().strip() if path.exists() else None


def tree(project):
    return sorted(str(p.relative_to(project)) for p in pathlib.Path(project).rglob("*")
                  if ".git" not in p.relative_to(project).parts)


class KitVersionTest(FakeGh):
    def project(self):
        self.work, self.origin = make_repo(self.tmp, {"loop.json": settings_json("## Loop\nTest command: true\n")})
        return self.work

    def cli(self, plugin, *args):
        return subprocess.run([str(pathlib.Path(plugin, "bin", "loop")), *args], cwd=self.work,
                              capture_output=True, text=True)

    def refusal(self, old, new):
        return ["refused: this session runs kit %s, but this project was set up with kit %s" % (old, new),
                "next: restart Claude Code so it loads kit %s, then try again" % new]

    def test_check_version_refuses_an_older_kit(self):
        self.project()
        record(self.work, "99.0.0")
        before = tree(self.work)
        r = self.cli(KIT, "check-version")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual([l[20:] for l in r.stdout.splitlines()], self.refusal(REAL, "99.0.0"))
        self.assertEqual(tree(self.work), before)
        self.assertEqual(recorded(self.work), "99.0.0")

    def test_check_version_accepts_the_same_or_a_newer_kit(self):
        self.project()
        record(self.work, REAL)
        self.assertEqual(self.cli(KIT, "check-version").returncode, 0)
        record(self.work, "0.1.0")
        self.assertEqual(self.cli(KIT, "check-version").returncode, 0)

    def test_check_version_with_no_file_passes(self):
        self.project()
        r = self.cli(KIT, "check-version")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_versions_compare_as_numbers(self):
        self.project()
        record(self.work, "2.9.0")
        self.assertEqual(self.cli(plugin_copy(self.tmp, "2.10.0"), "check-version").returncode, 0)
        record(self.work, "2.10.0")
        r = self.cli(plugin_copy(self.tmp, "2.9.0"), "check-version")
        self.assertEqual(r.returncode, 1)
        self.assertEqual([l[20:] for l in r.stdout.splitlines()], self.refusal("2.9.0", "2.10.0"))

    def test_loop_run_refuses_an_older_kit_and_writes_nothing(self):
        self.project()
        record(self.work, "99.0.0")
        before = tree(self.work)
        r = self.cli(KIT, "run")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual([l[20:] for l in r.stdout.splitlines()], self.refusal(REAL, "99.0.0"))
        self.assertEqual(tree(self.work), before)
        self.assertEqual(self.calls(), [])

    def test_loop_run_records_the_version_and_raises_it(self):
        self.project()
        self.cli(KIT, "run")  # no origin loop branch: it refuses later, after the record
        self.assertEqual(recorded(self.work), REAL)
        record(self.work, "0.1.0")
        self.cli(KIT, "run")
        self.assertEqual(recorded(self.work), REAL)

    def test_setup_refuses_an_older_kit_and_changes_nothing(self):
        self.project()
        record(self.work, "99.0.0")
        self.fresh_scenario()
        before = tree(self.work)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = setup.setup(self.work)
        self.assertEqual(code, 1)
        self.assertEqual(buf.getvalue().splitlines(), self.refusal(REAL, "99.0.0"))
        self.assertEqual(tree(self.work), before)
        self.assertEqual(self.calls(), [])
        self.assertEqual(subprocess.run(["git", "ls-remote", self.origin], capture_output=True,
                                        text=True).stdout.count("loop/main"), 0)

    def fresh_scenario(self):
        self.scenario([rule("label list", "[]"), rule("label create"), rule("issue list", "[]"),
                       rule("issue create", "https://github.com/o/r/issues/7\n"), rule("issue pin")])

    def test_setup_records_the_version_when_the_file_is_missing_and_raises_it(self):
        self.project()
        self.fresh_scenario()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup.setup(self.work), 0)
        self.assertEqual(recorded(self.work), REAL)
        record(self.work, "0.1.0")
        with contextlib.redirect_stdout(io.StringIO()):
            setup.setup(self.work)
        self.assertEqual(recorded(self.work), REAL)


class SkillStepTest(unittest.TestCase):
    def check(self, name, first_marker):
        text = (KIT / "skills" / name / "SKILL.md").read_text()
        self.assertIn("<plugin>/bin/loop check-version", text)
        self.assertLess(text.index("check-version"), text.index(first_marker))

    def test_shape_checks_the_version_first(self):
        self.check("shape", "Read `AGENTS.md`")

    def test_loop_checks_the_version_first(self):
        self.check("loop", "use the setup skill")


class ReadmeTest(unittest.TestCase):
    def test_readme_says_an_update_needs_a_restart(self):
        text = (KIT / "README.md").read_text().lower()
        self.assertTrue("restart claude code" in text and "update" in text)


if __name__ == "__main__":
    unittest.main()
