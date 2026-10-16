"""Wrong-reason failures during a build return at once with their cause."""
from __future__ import annotations

import os
import stat
import unittest
from pathlib import Path
from unittest.mock import patch

import test_run
from helpers import SPEC, Project, git
from loopkit import records


class WrongReasonAttemptTests(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        fake = Path(self.p.tmp.name) / "fake-claude"
        fake.write_text(test_run.FAKE_CLAUDE)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        os.environ["LOOP_CLAUDE"] = str(fake)
        self.addCleanup(os.environ.pop, "LOOP_CLAUDE", None)
        self.addCleanup(os.environ.pop, "FAKE_MODE", None)
        self.addCleanup(os.environ.pop, "FAKE_REVIEW_MODE", None)

    def build(self, mode, attempts=2, spec=SPEC):
        os.environ["FAKE_MODE"] = mode
        n = self.p.piece(spec=spec)
        test_run.gate.move(self.p.gh, self.p.root, n, "ready")
        result = test_run.run.build_piece(self.p.gh, self.p.root, n, attempts)
        return n, result

    def assert_handback_record(self, handback, *, reason_type, cause, attempts):
        self.assertEqual(handback["move"], "give-back")
        self.assertEqual(handback["from"], "building")
        self.assertEqual(handback["to"], "shaping")
        self.assertEqual(handback["type"], reason_type)
        self.assertTrue(handback["reason"])
        self.assertEqual(handback["cause"], cause)
        self.assertEqual(handback["attempts"], attempts)

    def test_wrong_reason_import_error_returns_after_one_attempt(self):
        n, result = self.build("wrong-import", attempts=3)
        self.assertIn("back to shaping", result)
        handback = [r for r in records(self.p.gh.comments(n))
                    if r.get("move") == "give-back"][-1]
        self.assert_handback_record(handback, reason_type="environment",
                                    cause="import-error", attempts=1)
        failed = [c for c in self.p.gh.comments(n) if c.startswith("**Run:** attempt")]
        self.assertEqual(len(failed), 1)

    def test_wrong_reason_keep_import_error_returns_after_one_attempt(self):
        keep = (
            'python3 -c "import pathlib; '
            "pathlib.Path('broken_keep').exists() and "
            "__import__('missing_runtime')\""
        )
        spec = SPEC.replace("Files:", f"Keep: `{keep}`\nFiles:")
        n, result = self.build("wrong-keep-import", attempts=3, spec=spec)
        self.assertIn("back to shaping", result)
        handback = [r for r in records(self.p.gh.comments(n))
                    if r.get("move") == "give-back"][-1]
        self.assert_handback_record(handback, reason_type="environment",
                                    cause="import-error", attempts=1)
        failed = [c for c in self.p.gh.comments(n) if c.startswith("**Run:** attempt")]
        self.assertEqual(len(failed), 1)

    def test_remote_only_main_update_uses_stale_cause(self):
        os.environ["FAKE_MODE"] = "wrong-import"
        n = self.p.piece()
        test_run.gate.move(self.p.gh, self.p.root, n, "ready")
        original_build_once = test_run.run.build_once
        original_main = git(self.p.root, "rev-parse", "main")

        def build_then_advance_remote(*args, **kwargs):
            result = original_build_once(*args, **kwargs)
            git(self.p.root, "commit", "--allow-empty", "--quiet", "-m",
                "Advance remote main")
            git(self.p.root, "push", "--quiet", "origin", "main")
            git(self.p.root, "update-ref", "refs/heads/main", original_main)
            return result

        with patch("test_run.run.build_once", side_effect=build_then_advance_remote):
            test_run.run.build_piece(self.p.gh, self.p.root, n, 3)

        handback = [r for r in records(self.p.gh.comments(n))
                    if r.get("move") == "give-back"][-1]
        self.assert_handback_record(handback, reason_type="environment",
                                    cause="stale-after-main", attempts=1)
        self.assertEqual(git(self.p.root, "rev-parse", "main"), original_main)
