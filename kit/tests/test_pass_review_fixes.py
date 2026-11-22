"""Polling must continue through summaries, and reap must end detached pass sessions."""
import contextlib
import os
import signal
import sys
from unittest import mock

from kit.tests.helpers import write_exe
from kit.tests.test_pass_background import BackgroundPassFixture
import common
import loop

REAL_SUMMARY = loop.summary


class PassReviewFixesTest(BackgroundPassFixture):
    def agent(self, body):
        write_exe(os.path.join(self.tmp, "bin", "claude"),
                  "#!PYTHON\nimport json, os, pathlib, subprocess, sys, time\n"
                  "root = pathlib.Path(%r)\nprompt = sys.stdin.read()\n" % str(self.runtime) + body,
                  shared=False)
        self.gate.touch()

    def test_a_held_summary_does_not_hold_the_drain_or_the_next_build(self):
        mock.patch.object(loop, "summary", new=REAL_SUMMARY).start()
        self.agent(
            "if 'Merge danger' in prompt and '## Summary' in prompt:\n"
            "    (root / 'summary-started').touch()\n"
            "    until = time.monotonic() + 10\n"
            "    while not (root / 'release-summary').exists() and time.monotonic() < until:\n"
            "        time.sleep(0.02)\n"
            "    reply = '## Summary\\n\\nFresh summary.\\n\\n## Evidence\\n\\nChecked.\\n\\n## Merge danger\\n\\nSmall.'\n"
            "else:\n"
            "    reply = 'FINDINGS:\\nnone\\nLESSONS:\\nnone\\nGUARDRAILS:\\nnone\\nSIMPLIFY:\\nnone'\n"
            "print(json.dumps({'result': reply, 'session_id': 'fake'}))\n")
        self.addCleanup(lambda: (self.runtime / "release-summary").touch())
        done = self.begin_drain()
        self.wait_for(lambda: (self.runtime / "summary-started").exists(), "the summary did not start")
        self.assertTrue(done.wait(1), "drain waited for the summary agent")
        self.st["issues"] = [dict(number=2, labels={"ready"}, body="")]
        command = [sys.executable, "-c", (
            "import pathlib, sys; sys.path.insert(0, %r); import common; "
            "root = pathlib.Path(sys.argv[1]); (root / '.loop' / 'build-started').touch(); "
            "pathlib.Path(common.build_file(str(root), 2, 'result')).write_text('{\"last\": \"done\"}')"
            % loop.HERE), self.work]
        with mock.patch.object(common, "ready_is_trusted", return_value=True), \
                mock.patch.object(loop, "worker_command", return_value=command):
            loop.start_builds(self.work, self.settings, self.st)
        self.wait_for(lambda: (self.runtime / "build-started").exists(), "the next build did not start")
        self.assertFalse((self.runtime / "release-summary").exists())
        (self.runtime / "release-summary").touch()
        self.collect(lambda: any("Fresh summary." in body for body in self.bodies()))

    def detached_agent(self):
        write_exe(os.path.join(self.tmp, "bin", "ps"), '#!/bin/sh\nexec /bin/ps "$@"\n', shared=False)
        self.agent(
            "sys.path.insert(0, %r)\nimport common\n"
            "(root / 'agent-pid').write_text(str(os.getpid()))\n"
            "command = [sys.executable, '-c', \"import os, pathlib, time; pathlib.Path(%r).write_text(str(os.getpid())); time.sleep(30)\"]\n"
            "import shlex\ncommon.run_shell(shlex.join(command), os.getcwd(), 60, record=os.environ['LOOP_GROUPS'])\n"
            % (loop.HERE, str(self.runtime / "hook-pid")))
        self.addCleanup(self.end_agents)
        done = self.begin_drain()
        self.wait_for(lambda: (self.runtime / "hook-pid").exists(), "the agent's hook did not start")
        self.assertTrue(done.wait(2))
        return [int((self.runtime / name).read_text()) for name in ("agent-pid", "hook-pid")]

    def end_agents(self):
        for name in ("agent-pid", "hook-pid"):
            path = self.runtime / name
            if path.exists():
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(os.getpgid(int(path.read_text())), signal.SIGKILL)

    def assert_ended(self, pids):
        def ended():
            rows = loop.process_table()
            return all(pid not in rows or rows[pid][1].startswith("Z") for pid in pids)
        self.wait_for(ended, "reap left an agent or hook running")
        self.assertNotIn("pass", self.st)

    def test_stopped_reap_ends_detached_agent_and_hook_groups(self):
        pids = self.detached_agent()
        loop.reap(self.work, self.st, stopped=True)
        self.assert_ended(pids)

    def test_crashed_worker_collection_ends_detached_agent_and_hook_groups(self):
        pids = self.detached_agent()
        self.workers[0].kill()
        self.workers[0].wait(timeout=5)
        loop.reap(self.work, self.st)
        self.assert_ended(pids)
