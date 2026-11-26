"""Fake projects choose their own cache without changing the enclosing loop's."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from kit.tests.fake_codex import FakeCodexGh
from kit.tests.helpers import make_repo, write_exe
import common
import session


class FakeCodexCacheEnvironmentTest(unittest.TestCase):
    def test_fake_session_uses_its_project_cache_and_cleanup_restores_the_inherited_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            inherited = Path(folder, "enclosing-cache")
            inherited.mkdir()
            marker = inherited / "compiler-output"
            marker.write_bytes(b"enclosing compiler output\n")
            with mock.patch.dict(os.environ, LOOP_CACHE_DIR=str(inherited)):
                fixture = FakeCodexGh()
                try:
                    fixture.setUp()
                    self.assertNotIn("LOOP_CACHE_DIR", os.environ)
                    write_exe(Path(fixture.tmp, "bin/ps"), "#!PYTHON\n")
                    write_exe(Path(fixture.tmp, "bin/taskpolicy"),
                              "#!PYTHON\nimport os, sys\nos.execvp(sys.argv[2], sys.argv[2:])\n")
                    work, _ = make_repo(fixture.tmp, {"loop.json": json.dumps({"Test command": "true"})})
                    with common.cache_environment(work):
                        cache = common.build_env()["LOOP_CACHE_DIR"]
                        session.run("builder", "do it", work, "gpt-6", work, 7, agent="codex")
                    call = fixture.codex_calls()[0]
                    self.assertEqual(call["env"]["LOOP_CACHE_DIR"], cache)
                    prefix = "sandbox_workspace_write.writable_roots="
                    roots = next(json.loads(value[len(prefix):]) for value in call["argv"]
                                 if value.startswith(prefix))
                    self.assertIn(str(Path(cache).resolve()), roots)
                    self.assertNotIn(str(inherited.resolve()), roots)
                finally:
                    fixture.doCleanups()
                self.assertEqual(os.environ["LOOP_CACHE_DIR"], str(inherited))
                self.assertEqual(marker.read_bytes(), b"enclosing compiler output\n")
