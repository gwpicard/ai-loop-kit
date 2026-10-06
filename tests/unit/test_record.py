"""Unit tests for kit/scripts/loop/run/record.py: the run record, the lock, the heartbeat, spend.

The run record says what is done, so a killed run started again never redoes a finished piece.
The lock file keeps two copies of a run from running at once. A record that cannot be read is a
refusal, never an empty record.
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop.paths import Paths  # noqa: E402
from loop.run import record  # noqa: E402


class RecordTestCase(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        (self.folder / ".git").mkdir()
        self.paths = Paths.for_project(self.folder, data_base=self.folder / "data",
                                       kit_folder=ROOT / "kit")

    def new(self, pieces=(1, 2, 3), **more):
        values = {"attended": True, "merge_pre_approved": False}
        values.update(more)
        return record.RunRecord.create(self.paths, "night-1", list(pieces), **values)


class RunRecordTest(RecordTestCase):
    def test_a_new_record_lists_every_piece_as_pending_in_the_given_order(self):
        run = self.new()
        self.assertEqual(run.numbers(), [1, 2, 3])
        self.assertEqual({run.status(n) for n in (1, 2, 3)}, {record.PENDING})
        self.assertTrue(self.paths.run_record("night-1").is_file())

    def test_the_record_is_read_back_from_the_file(self):
        run = self.new()
        run.set_status(2, record.BUILT, branch="piece-2")
        again = record.RunRecord.load(self.paths, "night-1")
        self.assertEqual(again.status(2), record.BUILT)
        self.assertEqual(again.piece(2)["branch"], "piece-2")

    def test_a_record_that_cannot_be_read_is_a_refusal(self):
        self.new()
        self.paths.run_record("night-1").write_text("{not json", encoding="utf-8")
        with self.assertRaises(record.RecordError) as caught:
            record.RunRecord.load(self.paths, "night-1")
        self.assertTrue(caught.exception.next_command)

    def test_a_missing_record_is_a_refusal_not_an_empty_one(self):
        with self.assertRaises(record.RecordError):
            record.RunRecord.load(self.paths, "nope")

    def test_a_record_of_the_wrong_shape_is_a_refusal(self):
        self.new()
        self.paths.run_record("night-1").write_text(json.dumps({"pieces": []}), encoding="utf-8")
        with self.assertRaises(record.RecordError):
            record.RunRecord.load(self.paths, "night-1")

    def test_exists_tells_a_resume_from_a_start(self):
        self.assertFalse(record.RunRecord.exists(self.paths, "night-1"))
        self.new()
        self.assertTrue(record.RunRecord.exists(self.paths, "night-1"))

    def test_a_status_the_run_does_not_know_is_refused(self):
        run = self.new()
        with self.assertRaises(ValueError):
            run.set_status(1, "celebrating")

    def test_a_piece_not_in_the_run_is_refused(self):
        run = self.new()
        with self.assertRaises(KeyError):
            run.set_status(9, record.BUILT)

    def test_the_file_is_always_whole_json_while_threads_write_it(self):
        run = self.new(range(1, 9))

        def work(number):
            for index in range(25):
                run.set_status(number, record.BUILDING, attempt=index)
                run.add_spend(number, 0.01)

        threads = [threading.Thread(target=work, args=(n,)) for n in range(1, 9)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        data = json.loads(self.paths.run_record("night-1").read_text(encoding="utf-8"))
        self.assertEqual(len(data["pieces"]), 8)
        self.assertAlmostEqual(run.spend_total(), 8 * 25 * 0.01, places=6)


class ResumeTest(RecordTestCase):
    def test_finished_pieces_are_never_resumed(self):
        run = self.new()
        run.set_status(1, record.BUILT)
        run.set_status(2, record.SENT_BACK)
        run.set_status(3, record.RETURNED)
        self.assertEqual(run.resumable(), [])

    def test_a_piece_parked_for_a_question_waits_for_its_answer_and_is_not_resumed(self):
        run = self.new()
        run.set_status(1, record.PARKED_PERSON, question="Which colour?")
        self.assertNotIn(1, run.resumable())

    def test_pending_building_waiting_stopped_and_spend_parked_pieces_are_resumed(self):
        run = self.new(range(1, 8))
        run.set_status(1, record.PENDING)
        run.set_status(2, record.BUILDING)
        run.set_status(3, record.WAITING)
        run.set_status(4, record.STOPPED)
        run.set_status(5, record.PARKED_SPEND)
        run.set_status(6, record.WAITING_PERSON, next="gate.py sync")
        run.set_status(7, record.BUILT)
        self.assertEqual(run.resumable(), [1, 2, 3, 4, 5, 6])

    def test_the_built_pieces_are_listed_for_the_claim(self):
        run = self.new()
        run.set_status(1, record.BUILT)
        run.set_status(3, record.BUILT)
        self.assertEqual(run.with_status(record.BUILT), [1, 3])


class SpendTest(RecordTestCase):
    def test_spend_adds_up_for_each_piece_and_for_the_run(self):
        run = self.new()
        run.add_spend(1, 0.5)
        run.add_spend(1, 0.25)
        run.add_spend(2, 1.0)
        self.assertAlmostEqual(run.spend_piece(1), 0.75)
        self.assertAlmostEqual(run.spend_piece(2), 1.0)
        self.assertAlmostEqual(run.spend_total(), 1.75)

    def test_spend_is_kept_when_the_record_is_read_again(self):
        run = self.new()
        run.add_spend(1, 0.5)
        self.assertAlmostEqual(record.RunRecord.load(self.paths, "night-1").spend_total(), 0.5)

    def test_tokens_are_added_for_the_piece(self):
        run = self.new()
        run.add_tokens(1, {"input_tokens": 10, "output_tokens": 5})
        run.add_tokens(1, {"input_tokens": 1, "output_tokens": 2})
        self.assertEqual(run.piece(1)["tokens"], {"input_tokens": 11, "output_tokens": 7})

    def test_a_negative_amount_is_refused(self):
        run = self.new()
        with self.assertRaises(ValueError):
            run.add_spend(1, -1)

    def test_a_cap_is_reached_at_the_cap_and_not_before(self):
        run = self.new()
        run.add_spend(1, 1.99)
        self.assertIsNone(run.cap_reached(per_piece=2.0, per_run=5.0, piece=1))
        run.add_spend(1, 0.01)
        reached = run.cap_reached(per_piece=2.0, per_run=5.0, piece=1)
        self.assertIsNotNone(reached)
        assert reached is not None
        self.assertIn("piece", reached.lower())

    def test_the_run_cap_counts_every_piece(self):
        run = self.new()
        run.add_spend(1, 3.0)
        run.add_spend(2, 2.0)
        reached = run.cap_reached(per_piece=10.0, per_run=5.0, piece=3)
        self.assertIsNotNone(reached)
        assert reached is not None
        self.assertIn("run", reached.lower())

    def test_no_cap_is_never_reached(self):
        run = self.new()
        run.add_spend(1, 1000.0)
        self.assertIsNone(run.cap_reached(per_piece=None, per_run=None, piece=1))


class LockTest(RecordTestCase):
    def test_a_lock_holds_the_process_number(self):
        lock = record.acquire_lock(self.paths, "night-1")
        self.assertEqual(self.paths.lock_file("night-1").read_text().split()[0], str(os.getpid()))
        lock.release()
        self.assertFalse(self.paths.lock_file("night-1").exists())

    def test_a_second_copy_of_a_live_run_is_refused(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        try:
            self.paths.run_dir("night-1").mkdir(parents=True)
            self.paths.lock_file("night-1").write_text(f"{child.pid}\n", encoding="utf-8")
            with self.assertRaises(record.LockHeld) as caught:
                record.acquire_lock(self.paths, "night-1")
            self.assertIn(str(child.pid), str(caught.exception))
            self.assertTrue(caught.exception.next_command)
            self.assertEqual(self.paths.lock_file("night-1").read_text().strip(), str(child.pid))
        finally:
            child.kill()
            child.wait()

    def test_a_lock_of_a_dead_process_is_taken_over(self):
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait()
        self.paths.run_dir("night-1").mkdir(parents=True)
        self.paths.lock_file("night-1").write_text(f"{child.pid}\n", encoding="utf-8")
        lock = record.acquire_lock(self.paths, "night-1")
        self.assertEqual(self.paths.lock_file("night-1").read_text().split()[0], str(os.getpid()))
        lock.release()

    def test_a_lock_with_no_process_number_is_refused_not_taken(self):
        self.paths.run_dir("night-1").mkdir(parents=True)
        self.paths.lock_file("night-1").write_text("???\n", encoding="utf-8")
        with self.assertRaises(record.LockHeld):
            record.acquire_lock(self.paths, "night-1")

    def test_release_leaves_a_lock_that_another_process_took(self):
        lock = record.acquire_lock(self.paths, "night-1")
        self.paths.lock_file("night-1").write_text("1\n", encoding="utf-8")
        lock.release()
        self.assertTrue(self.paths.lock_file("night-1").exists())


class HeartbeatTest(RecordTestCase):
    def test_the_heartbeat_holds_the_time_and_the_process(self):
        record.beat(self.paths, "night-1", now=1000.0)
        text = self.paths.heartbeat("night-1").read_text(encoding="utf-8")
        data = json.loads(text)
        self.assertEqual(data["pid"], os.getpid())
        self.assertEqual(data["at"], 1000.0)

    def test_an_age_is_read_from_the_heartbeat(self):
        record.beat(self.paths, "night-1", now=1000.0)
        self.assertEqual(record.heartbeat_age(self.paths, "night-1", now=1030.0), 30.0)

    def test_no_heartbeat_has_no_age(self):
        self.assertIsNone(record.heartbeat_age(self.paths, "night-1", now=5.0))


if __name__ == "__main__":
    unittest.main()
