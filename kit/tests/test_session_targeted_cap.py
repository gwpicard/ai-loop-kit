"""Exercise capped session selection through loop check and the Stop hook."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from kit.tests import test_merge_full_suite_cadence as cadence
from kit.tests.helpers import run_git
import common


KIT = Path(__file__).resolve().parents[1]
CAP = 40


class SessionFixture:
    def __init__(self, case, importers=45, mandatory=3):
        self.merge = cadence.FullSuiteCadenceTest()
        self.merge.setUp()
        case.addCleanup(self.merge.doCleanups)
        self.work = Path(self.merge.work)
        self.runtime = Path(self.merge.tmp, "build-runtime")
        self.runtime.mkdir()
        self.locked = ["tests/test_locked.py", "tests/test_z_locked.py"]
        self.changed = ["tests/test_z_changed_%02d.py" % i
                        for i in range(mandatory - len(self.locked))]
        self.importers = sorted("tests/test_import_%02d.py" % i for i in range(importers))
        # Reverse creation order to distinguish selection order from input order.
        for name in reversed(self.importers):
            (self.work / name).write_text("import app\n")
        (self.work / self.locked[1]).write_text("# Another locked test.\n")
        (self.work / "app.py").write_text("value = 1\n")
        run_git(["add", "-A"], self.work)
        run_git(["commit", "-m", "Prepare session selection fixture"], self.work)
        run_git(["push", "origin", "HEAD:loop/main"], self.work)
        self.start = common.git(["rev-parse", "HEAD"], self.work)
        changes = {name: "# Changed test.\n" for name in self.changed}
        changes["app.py"] = "value = 2\n"
        self.merge.candidate(changes)

    def env(self, locked=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("LOOP_")}
        env.update(LOOP_PROJECT=str(self.work), LOOP_START=self.start,
                   LOOP_ROLE="builder", LOOP_TMPDIR=str(self.runtime),
                   LOOP_LOCKED="\n".join(self.locked if locked is None else locked))
        return env

    def check(self, locked=None):
        return subprocess.run([str(KIT / "bin/loop"), "check"], cwd=self.work,
                              env=self.env(locked), capture_output=True, text=True, timeout=30)

    def stop(self, session="builder-session", locked=None):
        return subprocess.run([sys.executable, str(KIT / "hooks/stop.py")],
                              input=json.dumps({"session_id": session}), cwd=self.work,
                              env=self.env(locked), capture_output=True, text=True, timeout=30)

    def expected(self):
        mandatory = set(self.locked + self.changed)
        extra = self.importers[:max(0, CAP - len(mandatory))]
        return ["targeted " + json.dumps(sorted(mandatory | set(extra))), "check"]


class SessionTargetedCapTest(unittest.TestCase):
    def assert_allowed(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")

    def test_loop_check_keeps_mandatory_files_then_fills_the_cap_in_selection_order(self):
        fixture = SessionFixture(self)
        for locked in (fixture.locked, list(reversed(fixture.locked)) + fixture.locked[:1]):
            with self.subTest(locked=locked):
                fixture.merge.trace.write_text("")
                result = fixture.check(locked)
                self.assert_allowed(result)
                self.assertEqual(fixture.merge.commands(), fixture.expected())
                self.assertRegex(result.stdout.lower(), r"merge[^\n]*full suite")

    def test_stop_uses_the_same_capped_files_without_the_full_command(self):
        fixture = SessionFixture(self)
        for index, locked in enumerate((fixture.locked, list(reversed(fixture.locked)))):
            with self.subTest(locked=locked):
                fixture.merge.trace.write_text("")
                result = fixture.stop("selection-%d" % index, locked)
                self.assert_allowed(result)
                self.assertEqual(result.stdout, "")
                self.assertEqual(fixture.merge.commands(), fixture.expected())

    def test_mandatory_files_can_exceed_the_cap_in_both_session_entry_points(self):
        fixture = SessionFixture(self, mandatory=43)
        for entry in (fixture.check, fixture.stop):
            with self.subTest(entry=entry.__name__):
                fixture.merge.trace.write_text("")
                result = entry()
                self.assert_allowed(result)
                self.assertEqual(fixture.merge.commands(), fixture.expected())

    def test_merge_still_runs_the_full_command_over_the_cap(self):
        fixture = SessionFixture(self)
        result = fixture.merge.merge_process()
        self.assertTrue(result["ok"], result["reason"])
        self.assertEqual(fixture.merge.commands(), ["full " + fixture.merge.sha, "check"])
        self.assertTrue(fixture.merge.merged_events()[-1]["full_suite"])


if __name__ == "__main__":
    unittest.main()
