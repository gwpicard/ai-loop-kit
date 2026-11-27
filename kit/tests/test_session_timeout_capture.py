"""Session timeouts raise an error while preserving output for builder recovery."""
import json
import os
from pathlib import Path
import sys

import session
from kit.tests.helpers import FakeGh, make_repo, write_exe


REPORT = "BUILT:\nCompleted the application.\nDEVIATIONS:\nnone\n"
AGENT = '''#!PYTHON
import json, os, sys, time
sys.stdin.read()
report = %r
if os.environ.get("LOOP_AGENT") == "codex":
    print(json.dumps({"type": "thread.started", "thread_id": "timed-builder"}), flush=True)
    print(json.dumps({"type": "item.completed", "item": {
        "type": "agent_message", "text": report}}), flush=True)
else:
    print(json.dumps({"session_id": "timed-builder", "result": report}), flush=True)
print("agent diagnostic", file=sys.stderr, flush=True)
time.sleep(30)
''' % REPORT


class SessionTimeoutCaptureTest(FakeGh):
    def setUp(self):
        super().setUp()
        self.work, _ = make_repo(self.tmp, {"loop.json": json.dumps({
            "Test command": "true", "Session minutes": 0.05,
        })})

    def test_exec_raises_session_error_after_logging_both_output_streams(self):
        log = Path(self.tmp, "session.log")
        command = ("import sys, time; print('partial reply', flush=True); "
                   "print('agent diagnostic', file=sys.stderr, flush=True); time.sleep(30)")
        with self.assertRaises(session.SessionError) as caught:
            session._exec([sys.executable, "-c", command], "", self.work,
                          dict(os.environ, LOOP_PROJECT=self.work), str(log), "builder", 7, 1)
        self.assertIn("session timed out", str(caught.exception))
        self.assertIn("partial reply", caught.exception.text)
        self.assertIn("agent diagnostic", caught.exception.stderr)
        self.assertIn("partial reply", log.read_text())
        self.assertIn("agent diagnostic", log.read_text())

    def test_agent_timeouts_keep_decoded_report_and_session_id_with_stderr(self):
        for agent in ("claude", "codex"):
            with self.subTest(agent=agent):
                write_exe(str(Path(self.tmp, "bin", agent)), AGENT)
                with self.assertRaises(session.SessionTimeout) as caught:
                    session.run("builder", "Complete the application", self.work, "model",
                                self.work, 7, agent=agent)
                self.assertIn("session timed out", str(caught.exception))
                self.assertEqual(caught.exception.text, REPORT)
                self.assertEqual(caught.exception.sid, "timed-builder")
