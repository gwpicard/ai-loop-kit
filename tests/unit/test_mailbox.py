"""Unit tests for kit/scripts/loop/run/mailbox.py: pause, continue and stop, as lines in a file."""

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop.paths import Paths  # noqa: E402
from loop.run import engine, mailbox, record  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(tempfile.mkdtemp())
        (self.folder / ".git").mkdir()
        self.paths = Paths.for_project(self.folder, data_base=self.folder / "data",
                                       kit_folder=ROOT / "kit")
        self.rec = record.RunRecord.create(self.paths, "night-1", [1, 2], attended=True,
                                           merge_pre_approved=False)
        self.calls: list[Any] = []
        self.box = self.paths.mailbox("night-1")
        self.box.parent.mkdir(parents=True, exist_ok=True)

    def context(self) -> engine.HookContext:
        return engine.HookContext(
            self.paths, "night-1", self.rec, {},
            lambda number: self.calls.append(("resume", number)),
            set_paused=lambda paused: self.calls.append(("paused", paused)),
            request_stop=lambda: self.calls.append(("stop",)))

    def write(self, *lines: str, mode: str = "w") -> None:
        with self.box.open(mode, encoding="utf-8") as handle:
            handle.write("".join(line + "\n" for line in lines))

    def tick(self) -> None:
        mailbox.run_hook(self.context(), "tick")

    def start(self) -> None:
        mailbox.run_hook(self.context(), "start")

    def notes(self) -> str:
        return " | ".join(n["text"] for n in self.rec.data["notes"])


class CommandsTest(Base):
    def test_pause_continue_and_stop_are_obeyed_in_order(self) -> None:
        self.start()
        self.write("pause")
        self.tick()
        self.write("continue", mode="a")
        self.tick()
        self.write("stop", mode="a")
        self.tick()
        self.assertEqual(self.calls, [("paused", True), ("paused", False), ("stop",)])

    def test_a_line_is_obeyed_once(self) -> None:
        self.start()
        self.write("pause")
        for _ in range(4):
            self.tick()
        self.assertEqual(self.calls, [("paused", True)])

    def test_the_words_may_be_in_any_case_with_spaces(self) -> None:
        self.start()
        self.write("  PAUSE  ", "Continue")
        self.tick()
        self.assertEqual(self.calls, [("paused", True), ("paused", False)])

    def test_no_file_changes_nothing(self) -> None:
        self.start()
        self.tick()
        self.assertEqual(self.calls, [])

    def test_blank_lines_and_comments_are_ignored_and_other_lines_are_noted(self) -> None:
        self.start()
        self.write("", "# a note to myself", "pause it please")
        self.tick()
        self.assertEqual(self.calls, [])
        self.assertIn("pause it please", self.notes())

    def test_the_run_record_holds_each_command(self) -> None:
        self.start()
        self.write("pause", "continue", "stop")
        self.tick()
        events = self.rec.data["mailbox"]["events"]
        self.assertEqual([e["command"] for e in events], ["pause", "continue", "stop"])
        self.assertFalse(self.rec.data["mailbox"]["paused"])
        self.write("pause", mode="a")
        self.tick()
        self.assertTrue(self.rec.data["mailbox"]["paused"])


class EarlierLinesTest(Base):
    def test_a_stop_left_from_an_earlier_run_does_not_stop_this_one(self) -> None:
        self.write("stop")
        self.start()
        self.tick()
        self.assertEqual(self.calls, [])
        self.assertIn("from before the run started", self.notes())

    def test_a_replaced_file_is_read_again_from_its_first_line(self) -> None:
        self.write("pause")
        self.start()
        self.write("continue")  # replaced: the person wrote new input
        self.tick()
        self.assertEqual(self.calls, [("paused", False)])
        self.assertIn("replaced", self.notes())

    def test_a_emptied_file_then_a_new_line_is_read(self) -> None:
        self.write("pause", "continue")
        self.start()
        self.write()
        self.tick()
        self.write("stop")
        self.tick()
        self.assertEqual(self.calls, [("stop",)])


class AnswersTest(Base):
    def test_an_answer_line_goes_to_the_parked_piece(self) -> None:
        self.rec.set_status(1, record.PARKED_PERSON, question="Which colour?")
        self.start()
        self.write("answer 1: blue, please")
        self.tick()
        self.assertEqual(self.calls, [("resume", 1)])
        self.assertEqual(self.rec.piece(1)["answer"]["text"], "blue, please")
        self.assertEqual(self.rec.piece(1)["answer"]["source"], "the mailbox")

    def test_an_answer_for_a_piece_that_is_not_parked_is_a_note_and_resumes_nothing(self) -> None:
        self.start()
        self.write("answer 1: blue")
        self.tick()
        self.assertEqual(self.calls, [])
        self.assertIn("waits for no answer", self.notes())

    def test_an_answer_for_a_piece_not_in_the_run_is_a_note(self) -> None:
        self.start()
        self.write("answer 9: blue")
        self.tick()
        self.assertIn("not in this run", self.notes())


class UnreadableTest(Base):
    def test_a_mailbox_that_cannot_be_read_pauses_the_run_and_says_so(self) -> None:
        self.start()
        self.box.write_bytes(b"\xff\xfe\xff")
        self.tick()
        self.tick()
        self.assertEqual(self.calls, [("paused", True)])
        self.assertEqual(self.notes().count("cannot be read"), 1)

    def test_the_pause_for_it_ends_when_the_file_can_be_read_again(self) -> None:
        self.start()
        self.box.write_bytes(b"\xff\xfe\xff")
        self.tick()
        self.write("pause")
        self.tick()
        self.assertEqual(self.calls[0], ("paused", True))
        self.assertIn(("paused", False), self.calls)
        self.assertIn("can be read again", self.notes())

    def test_a_mailbox_that_cannot_be_read_at_the_start_pauses_the_run(self) -> None:
        self.box.write_bytes(b"\xff\xfe\xff")
        self.start()
        self.assertEqual(self.calls, [("paused", True)])


if __name__ == "__main__":
    unittest.main()
