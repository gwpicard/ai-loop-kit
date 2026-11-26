"""The summary session leases its cache after the batch pass has ended."""
import json
import os
from pathlib import Path
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, write_exe
import common
import loop


class SummaryCacheTest(FakeClaudeGh):
    def test_summary_holds_its_own_cache_instead_of_inheriting_the_drains_folder(self):
        work, _ = make_repo(self.tmp, {"loop.json": json.dumps({"Test command": "true"})})
        head = common.git(["rev-parse", "HEAD"], cwd=work)
        settings = common.read_settings(work)
        self.scenario([{"match": "", "responses": [{"stdout": "[]"}]}])
        reply = "## Summary\n\nChanged.\n\n## Evidence\n\nChecked.\n\n## Merge danger\n\nReversible."
        self.claude({"pass": [{"reply": reply}]})
        write_exe(str(Path(self.tmp, "bin/ps")), "#!PYTHON\n")
        write_exe(str(Path(self.tmp, "bin/taskpolicy")),
                  "#!PYTHON\nimport os, sys\nos.execvp(sys.argv[2], sys.argv[2:])\n")
        stale = Path(self.tmp, "released-drain-cache")
        stale.mkdir()
        caches = []
        real_session = loop.session.run

        def session(*args, **kwargs):
            cache = Path(common.build_env()["LOOP_CACHE_DIR"])
            caches.append(cache)
            self.assertTrue(cache.is_dir())
            self.assertTrue(cache.is_relative_to(Path(work).parent / "loop-cache" / Path(work).name))
            with common.cache_environment(work):
                self.assertNotEqual(Path(common.build_env()["LOOP_CACHE_DIR"]), cache,
                                    "the summary must hold its cache during the session")
            return real_session(*args, **kwargs)

        with mock.patch.dict(os.environ, LOOP_CACHE_DIR=str(stale)), \
                mock.patch.object(loop.session, "run", side_effect=session):
            self.assertEqual(loop.summary(work, settings, head, "- Issue example"), reply + "\n")
            self.assertEqual(common.build_env()["LOOP_CACHE_DIR"], str(stale))
            with common.cache_environment(work):
                self.assertEqual(Path(common.build_env()["LOOP_CACHE_DIR"]), caches[0],
                                 "the summary must release its cache when it ends")
        calls = self.claude_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["env"]["LOOP_CACHE_DIR"], str(caches[0]))
