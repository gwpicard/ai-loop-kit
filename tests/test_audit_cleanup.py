"""The field audit checks reviewer cleanup against local processes and Git."""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import unittest
from unittest.mock import patch

from helpers import Project, git
from test_audit import audit


class AuditCleanupTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)

    def audit(self):
        output = io.StringIO()
        with patch.object(audit, "repo_root", return_value=self.p.root), \
                patch.object(audit, "load", return_value=[]), \
                contextlib.redirect_stdout(output):
            status = audit.main([])
        return status, output.getvalue()

    def test_cleanup_check_detects_a_live_reviewer_without_a_run_lock(self):
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                                start_new_session=True)

        def stop():
            if proc.poll() is None:
                proc.kill()
            proc.wait()

        self.addCleanup(stop)
        loop = self.p.root / ".loop"
        (loop / "logs").mkdir(parents=True, exist_ok=True)
        (loop / "logs" / "reviewer-processes").write_text(f"{proc.pid}\n")
        self.assertFalse((loop / "run.lock").exists())
        status, output = self.audit()
        self.assertEqual(status, 1, output)
        self.assertIn(f"BROKEN cleanup: reviewer process group {proc.pid} is alive", output)
        stop()
        status, output = self.audit()
        self.assertEqual(status, 0, output)
        self.assertIn(f"ok     cleanup: reviewer process group {proc.pid} has exited", output)

    def test_cleanup_check_detects_review_worktrees_and_branches(self):
        branch = "review/standards-1-1-abcdef12"
        folder = self.p.root.parent / "abandoned-review"
        git(self.p.root, "worktree", "add", "--quiet", "-b", branch, str(folder), "main")
        status, output = self.audit()
        self.assertEqual(status, 1, output)
        self.assertIn(f"BROKEN cleanup: review worktree remains: {folder.resolve()}", output)
        self.assertIn(f"BROKEN cleanup: review branch remains: {branch}", output)
        git(self.p.root, "worktree", "remove", str(folder))
        status, output = self.audit()
        self.assertEqual(status, 1, output)
        self.assertNotIn("review worktree remains:", output)
        self.assertIn(f"review branch remains: {branch}", output)
        git(self.p.root, "branch", "-D", branch)
        status, output = self.audit()
        self.assertEqual(status, 0, output)
        self.assertIn("cleanup: no review worktrees or branches remain", output)

    def test_old_review_logs_without_process_evidence_do_not_pass_cleanup(self):
        logs = self.p.root / ".loop" / "logs"
        logs.mkdir(parents=True)
        (logs / "piece-1-standards-review.log").write_text("old reviewer output\n")
        status, output = self.audit()
        self.assertEqual(status, 1, output)
        self.assertIn("reviewer process evidence is missing", output)


if __name__ == "__main__":
    unittest.main()
