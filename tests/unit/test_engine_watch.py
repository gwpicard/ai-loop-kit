"""Unit tests for what the engine does for the watch and the mailbox (P22).

A stuck attempt counts, through the gate: the branch goes to move 5. A usage limit counts for
nothing, and the piece waits for the reset. A pause starts nothing new and does not end the run
as if it had finished. A stop signal is the mailbox's `stop`. Output is read while the session
runs, so a stuck builder is ended at once.
"""

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import sessions  # noqa: E402
from loop.paths import Paths  # noqa: E402
from loop.run import attempts, engine, plan, record, watch  # noqa: E402

SAME_ERROR = "AssertionError: expected 3 but got 4 in tests/test_menu.py"


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(tempfile.mkdtemp())
        (self.folder / ".git").mkdir()
        self.paths = Paths.for_project(self.folder, data_base=self.folder / "data",
                                       kit_folder=ROOT / "kit")
        self.rec = record.RunRecord.create(self.paths, "night-1", [1, 2], attended=True,
                                           merge_pre_approved=False)
        policy = json.loads((ROOT / "kit" / "templates" / "policy.json").read_text())
        infos = [plan.PieceInfo(1, "Menu"), plan.PieceInfo(2, "Paint")]
        self.engine = engine.Engine(self.paths, "night-1", self.rec, policy, infos, slot_count=2,
                                    gateway=object(), hub=object())  # type: ignore[arg-type]
        watch.forget(self.paths, "night-1")

    def result(self, text: str = "", *, handoff: dict[str, Any] | None = None,
               exit_code: int = 0) -> sessions.Result:
        return sessions.Result(exit_code=exit_code, stdout=text, stderr="", output=None,
                               handoff=handoff)

    def decisions(self) -> str:
        return " | ".join(d["text"] for d in self.rec.data["decisions"])


class VerdictTest(Base):
    def test_a_session_with_no_hand_off_and_a_repeated_error_is_stuck(self) -> None:
        text = "\n".join([SAME_ERROR, "x", SAME_ERROR, "y", SAME_ERROR])
        verdict = self.engine._verdict(1, self.result(text, exit_code=1))
        assert verdict is not None
        self.assertEqual(verdict.kind, "stuck")

    def test_a_usage_limit_message_is_a_usage_limit(self) -> None:
        verdict = self.engine._verdict(
            1, self.result("Claude AI usage limit reached|1900000000", exit_code=1))
        assert verdict is not None
        self.assertEqual((verdict.kind, verdict.resume_at), ("usage-limit", 1900000000.0))

    def test_a_session_that_left_a_hand_off_is_not_judged_by_its_talk(self) -> None:
        handoff = {"outcome": "done", "summary": "x"}
        text = "the check timed out after 10s, so I raised it. usage limit reached in the spec"
        self.assertIsNone(self.engine._verdict(1, self.result(text, handoff=handoff)))

    def test_a_session_the_watch_ended_is_stuck_whatever_it_left_behind(self) -> None:
        self.engine.stop_attempt(1, "the same error 3 times in a row")
        handoff = {"outcome": "done", "summary": "x"}
        verdict = self.engine._verdict(1, self.result("", handoff=handoff, exit_code=-15))
        assert verdict is not None
        self.assertEqual(verdict.kind, "stuck")
        self.assertIsNone(self.engine._verdict(1, self.result("")), "the stop was kept")


class StuckCountsTest(Base):
    def test_a_stuck_attempt_goes_to_the_gate_as_move_5_with_the_reason(self) -> None:
        verdict = engine.Verdict("stuck", "the same error 3 times in a row: boom")
        route = self.engine._stuck_route(1, verdict)
        self.assertEqual((route.action, route.move), ("judge", 5))
        self.assertIn("stopped as stuck", route.reason)
        self.assertEqual(self.rec.piece(1)["stuck"], 1)
        self.assertIn("counts as an attempt", self.decisions())

    def test_the_run_keeps_no_attempt_count_of_its_own(self) -> None:
        self.engine._stuck_route(1, engine.Verdict("stuck", "x"))
        self.assertNotIn("attempts", self.rec.piece(1))

    def test_a_usage_limit_is_not_an_outcome_that_counts(self) -> None:
        self.assertFalse(attempts.counts_as_attempt("usage-limit"))
        self.assertTrue(attempts.counts_as_attempt("stuck"))


class WaitForResetTest(Base):
    def test_the_piece_waits_for_the_reset_and_counts_nothing(self) -> None:
        until = time.time() + 0.4
        started = time.time()
        self.assertTrue(self.engine._wait_for_reset(
            1, engine.Verdict("usage-limit", "limit reached", until)))
        self.assertGreaterEqual(time.time() - started, 0.3)
        self.assertIsNone(self.rec.piece(1)["waiting_for_reset"])
        self.assertIn("usage limit", self.decisions())
        self.assertIn("no attempt", self.decisions())
        self.assertNotIn("attempts", self.rec.piece(1))

    def test_the_piece_says_it_waits_while_it_waits(self) -> None:
        until = time.time() + 1.0
        seen: list[Any] = []
        thread = threading.Thread(target=self.engine._wait_for_reset, args=(
            1, engine.Verdict("usage-limit", "limit reached", until)))
        thread.start()
        time.sleep(0.3)
        seen.append(self.rec.piece(1).get("waiting_for_reset"))
        thread.join()
        assert seen[0] is not None
        self.assertEqual(seen[0]["until"], until)

    def test_a_reset_time_in_the_past_waits_for_nothing(self) -> None:
        started = time.time()
        self.assertTrue(self.engine._wait_for_reset(
            1, engine.Verdict("usage-limit", "limit", time.time() - 100)))
        self.assertLess(time.time() - started, 0.5)

    def test_no_reset_time_waits_the_default_and_a_stop_ends_the_wait(self) -> None:
        old = engine.WAIT_SLICE_SECONDS
        engine.WAIT_SLICE_SECONDS = 0.05
        self.addCleanup(setattr, engine, "WAIT_SLICE_SECONDS", old)
        threading.Timer(0.2, self.engine.stop.set).start()
        started = time.time()
        self.assertFalse(self.engine._wait_for_reset(1, engine.Verdict("usage-limit", "limit")))
        self.assertLess(time.time() - started, 5)
        self.assertIsNone(self.rec.piece(1)["waiting_for_reset"])


class PauseTest(Base):
    def test_a_pause_starts_nothing_and_keeps_the_run_alive_with_work_left(self) -> None:
        self.engine.set_paused(True)
        self.assertTrue(self.engine._held_by_pause())
        self.engine._launch()
        self.assertEqual(self.engine.workers, {})
        self.assertEqual(self.rec.with_status(record.PENDING), [1, 2])

    def test_an_ended_pause_lets_the_run_end_again(self) -> None:
        self.engine.set_paused(True)
        self.engine.set_paused(False)
        self.assertFalse(self.engine._held_by_pause())

    def test_a_pause_with_no_work_left_does_not_hold_the_run(self) -> None:
        self.rec.set_status(1, record.BUILT)
        self.rec.set_status(2, record.BUILT)
        self.engine.set_paused(True)
        self.assertFalse(self.engine._held_by_pause())

    def test_a_stop_ends_the_hold_of_a_pause(self) -> None:
        self.engine.set_paused(True)
        self.engine.request_stop()
        self.assertFalse(self.engine._held_by_pause())


class StreamTest(Base):
    def run_child(self, code: str, piece: int | None = 1) -> tuple[Any, float]:
        started = time.time()
        done = self.engine._run_tracked(
            [sys.executable, "-u", "-c", code], piece=piece, cwd=str(self.folder),
            env=None, stdin=None)
        return done, time.time() - started

    def test_a_builder_that_repeats_one_error_is_ended_while_it_runs(self) -> None:
        code = ("import time\n"
                f"for _ in range(3):\n    print({SAME_ERROR!r}, flush=True)\n"
                "    print('tool call', flush=True)\n"
                "time.sleep(60)\n")
        done, seconds = self.run_child(code)
        self.assertLess(seconds, 20, "the stuck builder was not ended")
        self.assertIn("expected 3", done.stdout)
        self.assertIn("same error", self.engine._attempt_stops[1])

    def test_three_same_errors_in_streamed_tool_results_end_the_builder_while_it_runs(self) -> None:
        code = ("import json, time\n"
                "def tool(text):\n"
                "    print(json.dumps({'type': 'user', 'message': {'role': 'user', 'content': [\n"
                "        {'type': 'tool_result', 'tool_use_id': 't', 'content': text,\n"
                "         'is_error': True}]}}), flush=True)\n"
                "def say(text):\n"
                "    print(json.dumps({'type': 'assistant', 'message': {'content': [\n"
                "        {'type': 'text', 'text': text}]}}), flush=True)\n"
                f"for _ in range(3):\n    tool({SAME_ERROR!r})\n    say('trying again')\n"
                "time.sleep(60)\n")
        _done, seconds = self.run_child(code)
        self.assertLess(seconds, 20, "the stuck builder was not ended")
        self.assertIn("same error", self.engine._attempt_stops[1])

    def test_a_session_that_is_not_a_builder_is_not_watched(self) -> None:
        code = f"for _ in range(3):\n    print({SAME_ERROR!r})\n    print('tool call')\n"
        done, _ = self.run_child(code, piece=None)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(self.engine._attempt_stops, {})

    def test_the_output_is_kept_whole(self) -> None:
        done, _ = self.run_child("import sys\nprint('out one')\nsys.stderr.write('err one\\n')\n")
        self.assertEqual((done.stdout, done.stderr), ("out one\n", "err one\n"))

    def test_the_pieces_with_a_session_in_flight_are_listed(self) -> None:
        seen: list[list[int]] = []
        self.engine._live.add(2)
        seen.append(self.engine.live_sessions())
        self.assertEqual(seen, [[2]])

    def test_a_label_names_the_piece_of_a_builder_session_only(self) -> None:
        self.assertIsNotNone(engine._BUILDER_LABEL.match("p12-a3"))
        for other in ("review-1", "p1-trim", "p1-a"):
            self.assertIsNone(engine._BUILDER_LABEL.match(other))


class ParkedNextLineTest(Base):
    def test_the_next_line_of_a_parked_piece_names_the_parked_form_of_the_answer(self) -> None:
        self.engine._act(1, attempts.Route("park-person", reason="Which font?"))
        self.assertIn("gate.py answer 1 --question <it> --answer <yours> --by <you> --parked",
                      self.rec.piece(1)["next"])


class AnswerInTheBriefTest(Base):
    def test_a_parked_pieces_answer_reaches_the_builder_in_the_data_block_text(self) -> None:
        self.rec.update(1, question="Which colour?",
                        answer={"text": "blue, please", "source": "a comment on #5"})
        text = self.engine._found_so_far(1, [])
        self.assertIn("Which colour?", text)
        self.assertIn("blue, please", text)
        self.assertIn("a comment on #5", text)

    def test_no_answer_adds_nothing(self) -> None:
        self.rec.update(1, question="Which colour?")
        self.assertNotIn("answered", self.engine._found_so_far(1, []))


if __name__ == "__main__":
    unittest.main()
