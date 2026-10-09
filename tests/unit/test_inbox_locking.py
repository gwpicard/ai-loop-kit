"""Inbox admission must precede reading the state it will later save."""

from __future__ import annotations

import argparse
import select
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit/scripts"))

from loop import cli  # noqa: E402
from loop.paths import Paths  # noqa: E402
from loop.run import inbox, record  # noqa: E402

OWNER = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from loop.paths import Paths
from loop.run import record
paths = Paths.for_project(Path(sys.argv[2]), data_base=Path(sys.argv[2]) / 'data')
lock = record.acquire_lock(paths, 'night-1')
try:
    print('admitted', flush=True)
    sys.stdin.readline()
    run = record.RunRecord.load(paths, 'night-1')
    run.set_status(1, record.BUILT, branch='saved-work')
finally:
    lock.release()
"""


class InboxLockingTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="inbox-locking-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        (self.folder / ".git").mkdir()
        self.paths = Paths.for_project(self.folder, data_base=self.folder / "data",
                                       kit_folder=ROOT / "kit")
        run = record.RunRecord.create(self.paths, "night-1", [1, 2], attended=True,
                                      merge_pre_approved=False)
        run.set_status(2, record.PARKED_PERSON)
        self.paths.mailbox("night-1").write_text("answer 2: blue\n")
        self.args = argparse.Namespace(project=str(self.folder), run="night-1", dry_run=False)
        for substitution in (patch.object(Paths, "for_project", return_value=self.paths),
                             patch.object(inbox, "after_run", return_value=[])):
            substitution.start()
            self.addCleanup(substitution.stop)

    def test_finished_work_survives_owner_between_read_and_admission(self) -> None:
        owner = subprocess.Popen(
            [sys.executable, "-c", OWNER, str(ROOT / "kit/scripts"), str(self.folder)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            assert owner.stdout is not None and owner.stdin is not None
            self.assertTrue(select.select([owner.stdout], [], [], 10)[0], "owner never started")
            self.assertEqual(owner.stdout.readline().strip(), "admitted")
            actual_acquire = record.acquire_lock

            def finish_then_admit(paths: Paths, name: str) -> record.Lock:
                assert owner.stdin is not None
                owner.stdin.write("finish\n")
                owner.stdin.flush()
                self.assertEqual(owner.wait(timeout=10), 0)
                return actual_acquire(paths, name)

            with patch.object(record, "acquire_lock", side_effect=finish_then_admit):
                inbox.handler(self.args)
            saved = record.RunRecord.load(self.paths, "night-1")
            self.assertEqual(saved.status(1), record.BUILT,
                             "inbox overwrote finished work with its pre-admission snapshot")
            self.assertEqual(saved.piece(1)["branch"], "saved-work")
            self.assertEqual(saved.piece(2)["answer"]["text"], "blue")
            actual_acquire(self.paths, "successor").release()
        finally:
            if owner.poll() is None:
                owner.terminate()
            owner.wait(timeout=10)
            for stream in (owner.stdin, owner.stdout, owner.stderr):
                if stream is not None:
                    stream.close()

    def test_changed_record_refusal_releases_admission(self) -> None:
        actual_acquire = record.acquire_lock

        def corrupt_then_admit(paths: Paths, name: str) -> record.Lock:
            owner = actual_acquire(paths, name)
            try:
                paths.run_record(name).write_text("broken JSON")
            finally:
                owner.release()
            return actual_acquire(paths, name)

        with patch.object(record, "acquire_lock", side_effect=corrupt_then_admit), \
                self.assertRaises(cli.Failure) as caught:
            inbox.handler(self.args)
        self.assertEqual(caught.exception.code, cli.ExitCode.REFUSED)
        self.assertEqual(self.paths.run_record("night-1").read_text(), "broken JSON")
        actual_acquire(self.paths, "successor").release()


if __name__ == "__main__":
    unittest.main()
