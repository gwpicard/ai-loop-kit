"""The walk-away doctor runs the Test command once inside the Codex builder sandbox."""
from __future__ import annotations

from helpers import Project

# isort: split

import os
import unittest
from pathlib import Path
from unittest import mock

import sandbox
import walkaway

# Stands in for `codex sandbox`: drop the sandbox options and run the command.
FAKE_CODEX = '#!/bin/sh\nwhile [ "$1" != sh ]; do shift; done\nexec "$@"\n'


class SandboxTestCommandTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        codex = Path(self.p.tmp.name) / "codex"
        codex.write_text(FAKE_CODEX)
        codex.chmod(0o755)
        patcher = mock.patch.dict(os.environ, {"LOOP_CODEX": str(codex)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def sandbox_test(self, test, prepare=""):
        self.p.loop_section(test, prepare)
        with mock.patch.object(sandbox, "codex_builder_paths",
                               wraps=sandbox.codex_builder_paths) as paths:
            result = walkaway.codex_sandbox_test(self.p.root)
        self.paths_built = paths.call_count
        return result

    def test_a_passing_test_command_passes_inside_the_builder_boundary(self):
        self.assertEqual(self.sandbox_test("exit 0")[0], True)
        self.assertEqual(self.paths_built, 1)

    def test_a_refused_path_is_named(self):
        ok, detail = self.sandbox_test(
            "echo 'Operation not permitted at path /home/x/.cache/uv' >&2; exit 2")
        self.assertFalse(ok)
        self.assertIn("/home/x/.cache/uv", detail)

    def test_the_test_runs_with_the_build_folder_cache_after_prepare(self):
        check = ('case "$UV_CACHE_DIR" in */.loop/cache/uv) ;; *) exit 3;; esac; '
                 'test -f prepared && test "$TMPDIR" = "$(pwd -P)/.loop/tmp"')
        ok, detail = self.sandbox_test(check, prepare="touch prepared")
        self.assertTrue(ok, detail)

    def test_a_failed_prepare_is_reported(self):
        ok, detail = self.sandbox_test("exit 0", prepare="echo no network >&2; exit 1")
        self.assertFalse(ok)
        self.assertIn("Prepare failed", detail)

    def test_the_fresh_worktree_is_removed(self):
        self.sandbox_test("exit 0")
        self.assertFalse(list(self.p.root.parent.glob(".loop-sandbox-test-*")))

    def test_no_test_command_skips_the_check(self):
        self.assertEqual(walkaway.codex_sandbox_test(self.p.root)[0], True)


class PreflightTest(unittest.TestCase):
    def preflight(self, probe):
        class GitHub:
            @staticmethod
            def issues_with_label(label):
                return []

        with mock.patch.object(walkaway.agents, "selected", return_value="codex"), \
             mock.patch.object(walkaway.subprocess, "run", return_value=type(
                 "Result", (), {"returncode": 0, "stdout": "codex 1", "stderr": ""})()), \
             mock.patch.object(walkaway.shutil, "disk_usage", return_value=type(
                 "Usage", (), {"free": 11 * 1024 ** 3})()), \
             mock.patch.object(sandbox, "codex_probe", return_value=probe), \
             mock.patch.object(walkaway, "codex_sandbox_test",
                               return_value=(False, "uv panicked")) as test:
            checks = walkaway.preflight(GitHub(), Path("."), baseline_checked=True)
        return checks, test

    def test_a_failing_sandbox_test_fails_the_preflight(self):
        checks, _ = self.preflight((True, "ok"))
        ok, label, next_step = next(c for c in checks if "inside the Codex builder sandbox" in c[1])
        self.assertFalse(ok)
        self.assertIn("uv panicked", label)
        self.assertIn("doctor --walk-away", next_step)

    def test_the_sandbox_test_waits_for_a_working_probe(self):
        checks, test = self.preflight((False, "home write allowed"))
        test.assert_not_called()


if __name__ == "__main__":
    unittest.main()
