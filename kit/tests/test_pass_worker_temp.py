import json
import os
from pathlib import Path
import shlex
import sys
from unittest import mock

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git
from kit.tests.test_visible_build_temp import PROBE, TEMP_NAMES
import common
import loop


class PassWorkerTempTest(FakeClaudeGh):
    def test_real_worker_replaces_hidden_temp_for_commands_and_sessions_then_removes_it(self):
        parent = Path(self.tmp, "project parent")
        parent.mkdir()
        journal = parent / "commands.jsonl"
        command = "%s probe.py %%s %s" % (
            shlex.quote(sys.executable), shlex.quote(str(journal)))
        work, _ = make_repo(str(parent), {
            "loop.json": json.dumps({
                "Test command": "true", "Prepare command": command % "Prepare",
                "Smoke command": command % "Smoke" + " && exit 3"}),
            "probe.py": PROBE})
        run_git(["commit", "--allow-empty", "-m", "Issue fixture: exercise the summary"], work)
        run_git(["push", "origin", "HEAD:loop/main"], work)
        head = common.git(["rev-parse", "HEAD"], cwd=work)
        self.scenario([
            {"match": "issue list", "responses": [{"stdout": "[]"}]},
            {"match": "issue create", "responses": [{}]},
            {"match": "pr list", "responses": [{"stdout": "[]"}]}])
        self.claude({"pass": [{"reply": "FINDINGS:\nnone"}]})
        inherited = parent / ".hidden" / "temporary"
        inherited.mkdir(parents=True)
        state = loop.new_state()
        with mock.patch.dict(os.environ, dict.fromkeys(TEMP_NAMES, str(inherited))):
            loop.start_pass(work, common.read_settings(work), state, head, "origin/main")
            worker = state["pass"]["proc"]
            try:
                worker.wait(timeout=60)
                log = Path(work, ".loop/logs/pass-worker.log").read_text()
                self.assertEqual(worker.returncode, 0, log)
            finally:
                loop.reap_pass(work, state, stopped=True)
        saved = json.loads(Path(work, ".loop/pass.json").read_text())
        self.assertEqual(saved["head"], head, saved["text"])
        self.assertIn("Smoke command failed", saved["text"])
        records = [json.loads(line) for line in journal.read_text().splitlines()]
        self.assertEqual([r["command"] for r in records], ["Prepare", "Smoke"])
        calls = self.claude_calls()
        self.assertEqual([c["role"] for c in calls], ["pass"] * 5)
        environments = [r["env"] for r in records] + [c["env"] for c in calls]
        temp = Path(environments[0]["TMPDIR"])
        self.assertEqual(temp.parent, parent / "loop-tmp")
        for env in environments:
            self.assertEqual({name: env.get(name) for name in TEMP_NAMES},
                             dict.fromkeys(TEMP_NAMES, str(temp)))
        for path, root in ((temp, parent), (temp.resolve(), parent.resolve())):
            self.assertFalse(any(part.startswith(".") for part in path.relative_to(root).parts))
        for record in records:
            self.assertEqual(record["device"], os.stat(work).st_dev)
            self.assertEqual(Path(record["temporary"]).parent, temp)
        self.assertFalse(temp.exists(), "The worker left its temporary folder behind")
        self.assertTrue(inherited.is_dir(), "The worker removed the caller's temporary folder")
