"""Cache paths stay visible and leave leased legacy caches untouched."""
import fcntl
import os
from pathlib import Path
import unittest
from unittest import mock

from kit.tests import test_visible_build_cache


class CacheLocationContractTest(unittest.TestCase):
    def project(self, layout, name="work"):
        fixture = test_visible_build_cache.VisibleBuildCacheTest()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        return fixture, fixture.project(layout, name)

    def test_loop_run_overrides_an_inherited_hidden_cache_for_every_command_and_session(self):
        for layout, name in (("inherited cache", "app.v2"),
                             ("nested projects/cache group", "café app")):
            with self.subTest(layout=layout, project=name):
                fixture, project = self.project(layout, name)
                inherited = project.parent / "inherited" / ".compiler-cache"
                inherited.mkdir(parents=True)
                marker = inherited / "compiler-output"
                marker.write_bytes(b"inherited output\n")
                with mock.patch.dict(os.environ, LOOP_CACHE_DIR=str(inherited)):
                    rows, calls = fixture.run_command(project, 7)
                values = [row["cache"] for row in rows]
                values += [call["env"].get("LOOP_CACHE_DIR", "") for call in calls]
                self.assertEqual(marker.read_bytes(), b"inherited output\n")
                self.assertNotIn(str(inherited), values)
                self.assertNotIn("", values)
                hidden = {value: [part for part in Path(value).resolve().relative_to(project.parent.resolve()).parts
                                  if part.startswith(".")] for value in values}
                self.assertFalse(any(hidden.values()),
                                 "commands and sessions need visible cache components: %r" % hidden)

    def test_loop_run_leaves_all_legacy_slots_untouched_when_one_is_leased(self):
        fixture, project = self.project("leased old cache")
        old = project.parent / ".loop-cache" / project.name
        for slot in ("1", "2"):
            (old / slot).mkdir(parents=True)
            (old / slot / "compiler-output").write_bytes(("old slot " + slot).encode())
            (old / (slot + ".lock")).touch()

        def snapshot():
            return {str(path.relative_to(old)): (
                path.stat().st_ino, path.stat().st_mode, path.stat().st_mtime_ns,
                path.read_bytes() if path.is_file() else None)
                for path in [old, *old.rglob("*")]}

        before = snapshot()
        with (old / "1.lock").open("a") as lease:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            rows, _ = fixture.run_command(project, 7)
        with self.subTest(contract="preserve leased and available old slots"):
            self.assertEqual(snapshot(), before,
                             "starting the loop must leave every legacy cache slot untouched")
        with self.subTest(contract="start a separate cache"):
            self.assertFalse(Path(rows[0]["cache"]).is_relative_to(old))
            self.assertFalse(rows[0]["had_output"])
        with self.subTest(contract="explain manual removal"):
            log = project / ".loop/loop.out"
            lines = log.read_text().splitlines() if log.exists() else []
            notices = [line for line in lines if str(old) in line]
            self.assertEqual(len(notices), 1, lines)
            self.assertRegex(notices[0], r"(?i)remov|delet")
            self.assertRegex(notices[0], r"(?i)by hand|manually|manual removal")
