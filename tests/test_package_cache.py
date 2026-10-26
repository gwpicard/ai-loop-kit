"""Agent sessions keep the uv cache inside the build folder, which the sandbox can write."""
from __future__ import annotations

from helpers import Project, git

# isort: split

import os
import time
import unittest
from pathlib import Path
from unittest import mock

import agents
import run
import session
from loopkit import command_env, untracked_paths
from run_fixtures import RunFixture
from test_prepare_again import INSTALL


def session_env(folder, backend="codex", role="builder"):
    with mock.patch.object(agents, "subprocess") as process:
        agents.start_session(backend, "brief", folder, role=role)
    return process.Popen.call_args.kwargs["env"]


class PackageCacheTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        self.p.loop_section("printf baseline")
        self.cache = (self.p.root / ".loop" / "cache" / "uv").resolve()

    def test_package_cache_points_uv_inside_the_folder(self):
        env = command_env(self.p.root, package_cache=True)
        self.assertEqual(env["UV_CACHE_DIR"], str(self.cache))
        self.assertTrue(self.cache.is_dir())

    def test_other_commands_keep_the_person_s_cache(self):
        with mock.patch.dict(os.environ, {"UV_CACHE_DIR": "/elsewhere"}):
            self.assertEqual(command_env(self.p.root)["UV_CACHE_DIR"], "/elsewhere")

    def test_a_loop_folder_that_leaves_the_build_folder_is_refused(self):
        outside = Path(self.p.tmp.name) / "outside"
        outside.mkdir()
        (self.p.root / ".loop").symlink_to(outside)
        with self.assertRaises(ValueError):
            command_env(self.p.root, package_cache=True)

    def test_every_agent_session_uses_the_folder_cache(self):
        for backend, role in (("codex", "builder"), ("codex", "judge-writer"),
                              ("codex", "reviewer"), ("claude", "builder")):
            with self.subTest(backend=backend, role=role):
                self.assertEqual(session_env(self.p.root, backend, role)["UV_CACHE_DIR"],
                                 str(self.cache))

    def test_cache_files_are_not_untracked_project_paths(self):
        sdist = self.cache / "sdists-v9" / "pkg"
        sdist.mkdir(parents=True)
        (sdist / "pyproject.toml").write_text("[project]\n")
        (self.p.root / "new.py").write_text("")
        (self.p.root / ".loop" / "helper.py").write_text("")
        self.assertEqual(untracked_paths(self.p.root), {"new.py", ".loop/helper.py"})

    def test_a_cached_pyproject_does_not_run_prepare_again(self):
        since = git(self.p.root, "rev-parse", "HEAD")
        sdist = self.cache / "sdists-v9" / "pkg"
        sdist.mkdir(parents=True)
        (sdist / "pyproject.toml").write_text("[project]\n")
        ran, ok, _ = run.prepare_again(self.p.root, {"prepare": "true"}, since)
        self.assertEqual((ran, ok), (False, True))

    def test_cache_writes_are_not_builder_activity(self):
        self.cache.mkdir(parents=True)
        before = session._folder_activity_stamp(self.p.root)
        entry = self.cache / "entry"
        entry.write_text("x")
        future = time.time() + 10
        os.utime(entry, (future, future))
        os.utime(self.cache, (future, future))
        self.assertEqual(session._folder_activity_stamp(self.p.root), before)


class FirstPrepareTest(RunFixture, unittest.TestCase):
    def test_only_the_first_prepare_fills_the_folder_cache(self):
        self.p.loop_section("printf baseline", INSTALL)
        real = run.prepare
        with mock.patch.object(run, "prepare", side_effect=real) as prepare:
            _, result = self.build("adds-dependency", attempts=1)
        self.assertIn("pull request ready", result)
        self.assertEqual([call.kwargs.get("package_cache", False)
                          for call in prepare.call_args_list], [True, False])


if __name__ == "__main__":
    unittest.main()
