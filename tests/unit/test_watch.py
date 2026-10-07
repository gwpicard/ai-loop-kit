"""Unit tests for kit/scripts/loop/run/watch.py: stuck detection, usage limits, real stops.

The tests feed recorded builder output, line by line and whole. A stuck attempt is the same error
three times in a row, a change undone and redone, or a test past its hard timeout. A usage-limit
message is never stuck, and it names a reset time when it holds one. The run-level real stops
notify once, and a run record that is read again does not notify twice.
"""

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import sessions  # noqa: E402
from loop.paths import Paths  # noqa: E402
from loop.run import engine, record, watch  # noqa: E402

SAME_ERROR = "AssertionError: expected 3 but got 4 in tests/test_menu.py"


def feed(lines: list[str]) -> watch.Finding | None:
    watcher = watch.Watcher()
    found = None
    for line in lines:
        found = watcher.feed(line) or found
    return found


def tool_result(text: str, *, error: bool = True) -> str:
    """A line of `claude -p --output-format stream-json`: the result of a tool the builder ran."""
    return json.dumps({"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": text, "is_error": error}]}})


def assistant(text: str) -> str:
    return json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "text", "text": text}]}})


def final(text: str, *, error: bool = False) -> str:
    return json.dumps({"type": "result", "subtype": "success", "is_error": error,
                       "result": text, "total_cost_usd": 0.1})


class StreamedOutputTest(unittest.TestCase):
    """The real `claude` prints stream-json lines, not plain text."""

    def test_the_same_error_in_three_streamed_tool_results_is_stuck(self) -> None:
        found = feed([tool_result(SAME_ERROR), assistant("let me try again"),
                      tool_result(SAME_ERROR), assistant("one more try"),
                      tool_result(SAME_ERROR)])
        assert found is not None
        self.assertEqual(found.kind, "stuck")
        self.assertIn("expected 3", found.reason)
        self.assertNotIn('"type"', found.reason, "the reason holds the JSON, not the error")

    def test_two_streamed_tool_results_are_not_stuck(self) -> None:
        self.assertIsNone(feed([tool_result(SAME_ERROR), assistant("again"),
                                tool_result(SAME_ERROR)]))

    def test_what_the_builder_says_is_not_read_as_an_error(self) -> None:
        self.assertIsNone(feed([assistant(SAME_ERROR)] * 4))

    def test_a_result_line_that_is_not_an_error_holds_no_error(self) -> None:
        watcher = watch.Watcher()
        for _ in range(3):
            watcher.feed(final("Built the menu."))
            watcher.feed(final("Built the menu.", error=False))
        self.assertIsNone(watcher.finding)
        self.assertEqual(watcher.last_error, "")

    def test_the_words_is_error_false_are_not_an_error(self) -> None:
        self.assertEqual(watch.Watcher().feed('{"is_error":false,"result":"ok"'), None)
        watcher = watch.Watcher()
        watcher.feed('{"is_error": false, "result": "ok"')  # cut short: not JSON
        self.assertEqual(watcher.last_error, "")

    def test_three_good_sessions_with_the_same_short_result_are_not_the_same_failure(self) -> None:
        for number in (1, 2, 3):
            stdout = "\n".join([assistant("working"), final("Done.")])
            watch.run_hook(self.context(), "session-ended", piece=number,
                           result=sessions.Result(exit_code=0, stdout=stdout, stderr="",
                                                  output=None, handoff=None))
        self.assertEqual(self.rec.data.get("real_stops", []), [])

    def test_a_streamed_error_result_reaches_the_run_level_check(self) -> None:
        for number in (1, 2, 3):
            stdout = "\n".join([assistant("trying"), tool_result(
                f"Error: the database is not running at port 543{number}")])
            watch.run_hook(self.context(), "session-ended", piece=number,
                           result=sessions.Result(exit_code=0, stdout=stdout, stderr="",
                                                  output=None, handoff=None))
        self.assertEqual([s["kind"] for s in self.rec.data["real_stops"]], ["same-failure"])

    def test_a_streamed_usage_limit_is_read_with_its_reset_time(self) -> None:
        found = feed([assistant("working"), final("Claude AI usage limit reached|1900000000",
                                                  error=True)])
        assert found is not None
        self.assertEqual((found.kind, found.resume_at), ("usage-limit", 1900000000.0))

    def test_a_usage_limit_named_in_a_tool_result_is_not_a_limit(self) -> None:
        self.assertIsNone(feed([tool_result("docs/limits.md: usage limit reached when ...")]))

    def setUp(self) -> None:
        self.folder = Path(tempfile.mkdtemp())
        (self.folder / ".git").mkdir()
        self.paths = Paths.for_project(self.folder, data_base=self.folder / "data",
                                       kit_folder=ROOT / "kit")
        self.rec = record.RunRecord.create(self.paths, "night-1", [1, 2, 3], attended=True,
                                           merge_pre_approved=False)
        watch.forget(self.paths, "night-1")

    def context(self) -> engine.HookContext:
        return engine.HookContext(self.paths, "night-1", self.rec, {}, lambda number: None)


class StuckByTheSameErrorTest(unittest.TestCase):
    def test_the_same_error_three_times_in_a_row_is_stuck(self) -> None:
        found = feed([f"run 1: {SAME_ERROR}", "editing menu.py", f"run 2: {SAME_ERROR}",
                      "editing menu.py again", f"run 3: {SAME_ERROR}"])
        assert found is not None
        self.assertEqual(found.kind, "stuck")
        self.assertIn("3 times in a row", found.reason)
        self.assertIn("expected", found.reason)

    def test_two_times_is_not_stuck(self) -> None:
        self.assertIsNone(feed([SAME_ERROR, "ok", SAME_ERROR]))

    def test_a_different_error_between_them_ends_the_run(self) -> None:
        self.assertIsNone(feed([SAME_ERROR, SAME_ERROR, "ImportError: no module named menu",
                                SAME_ERROR]))

    def test_numbers_and_line_numbers_do_not_make_an_error_new(self) -> None:
        found = feed(["Error: line 10: unexpected token at 0x7fa1c0de",
                      "Error: line 12: unexpected token at 0x7fa1c0ff",
                      "Error: line 14: unexpected token at 0x7fa1c1aa"])
        assert found is not None
        self.assertEqual(found.kind, "stuck")

    def test_one_error_printed_on_three_lines_in_one_go_counts_once(self) -> None:
        self.assertIsNone(feed([SAME_ERROR, SAME_ERROR, SAME_ERROR]))

    def test_lines_that_are_not_errors_never_count(self) -> None:
        self.assertIsNone(feed(["building the menu"] * 10))

    def test_the_last_error_is_kept_for_the_run_level_check(self) -> None:
        watcher = watch.Watcher()
        watcher.feed("Error: the registry refused the install")
        self.assertIn("registry refused", watcher.last_error)


class StuckByATimeoutTest(unittest.TestCase):
    def test_a_test_past_its_hard_timeout_is_stuck(self) -> None:
        for line in ("the check ran past the limit of 600 seconds and was stopped",
                     "Command timed out after 10m 0s",
                     "hard timeout reached for python3 -m pytest tests/slow"):
            with self.subTest(line=line):
                found = feed([line])
                assert found is not None
                self.assertEqual(found.kind, "stuck")
                self.assertIn("timeout", found.reason.lower())

    def test_the_word_timeout_in_ordinary_text_is_not_stuck(self) -> None:
        self.assertIsNone(feed(["set the request timeout to 30 seconds in config.py"]))


class StuckByAChangeUndoneAndRedoneTest(unittest.TestCase):
    def test_a_change_undone_and_redone_is_stuck(self) -> None:
        watcher = watch.Watcher()
        self.assertIsNone(watcher.observe_state("clean"))
        self.assertIsNone(watcher.observe_state("change-x"))
        self.assertIsNone(watcher.observe_state("clean"))
        found = watcher.observe_state("change-x")
        assert found is not None
        self.assertEqual(found.kind, "stuck")
        self.assertIn("undone and redone", found.reason)

    def test_the_same_state_seen_again_changes_nothing(self) -> None:
        watcher = watch.Watcher()
        for state in ("clean", "clean", "change-x", "change-x", "change-x"):
            self.assertIsNone(watcher.observe_state(state))

    def test_steady_progress_is_never_stuck(self) -> None:
        watcher = watch.Watcher()
        for state in ("clean", "a", "ab", "abc", "abcd", "abcde"):
            self.assertIsNone(watcher.observe_state(state))

    def test_going_back_once_is_not_stuck(self) -> None:
        watcher = watch.Watcher()
        for state in ("clean", "a", "clean", "b"):
            self.assertIsNone(watcher.observe_state(state))


class UsageLimitTest(unittest.TestCase):
    def test_a_usage_limit_message_is_a_usage_limit_with_the_reset_time(self) -> None:
        reset = int(time.time()) + 3600
        found = feed([f"Claude AI usage limit reached|{reset}"])
        assert found is not None
        self.assertEqual(found.kind, "usage-limit")
        self.assertEqual(found.resume_at, float(reset))

    def test_a_limit_message_with_no_time_has_no_reset_time(self) -> None:
        found = feed(["5-hour limit reached, try again later"])
        assert found is not None
        self.assertEqual(found.kind, "usage-limit")
        self.assertIsNone(found.resume_at)

    def test_a_reset_clock_time_is_read_as_the_next_one(self) -> None:
        now = time.mktime((2026, 10, 7, 14, 0, 0, 0, 0, -1))
        found = watch.Watcher(now=lambda: now).feed("You have hit your limit. Resets 3pm")
        assert found is not None
        self.assertEqual(found.kind, "usage-limit")
        assert found.resume_at is not None
        self.assertAlmostEqual(found.resume_at - now, 3600, delta=2)

    def test_a_limit_message_repeated_is_never_stuck(self) -> None:
        found = feed(["Error: Claude AI usage limit reached|1900000000"] * 2
                     + ["Error: usage limit reached", "Error: usage limit reached"])
        assert found is not None
        self.assertEqual(found.kind, "usage-limit")

    def test_an_ordinary_line_that_says_limit_is_not_a_usage_limit(self) -> None:
        self.assertIsNone(feed(["raise the limit of rows to 50 in the menu"]))

    def test_the_json_result_of_a_limited_session_is_read(self) -> None:
        output = {"type": "result", "is_error": True,
                  "result": "Claude AI usage limit reached|1900000000"}
        found = watch.scan(json.dumps(output))
        assert found is not None
        self.assertEqual(found.kind, "usage-limit")
        self.assertEqual(found.resume_at, 1900000000.0)


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = Path(tempfile.mkdtemp())
        (self.folder / ".git").mkdir()
        self.paths = Paths.for_project(self.folder, data_base=self.folder / "data",
                                       kit_folder=ROOT / "kit")
        self.rec = record.RunRecord.create(self.paths, "night-1", [1, 2, 3, 4], attended=True,
                                           merge_pre_approved=False)
        self.stopped: list[tuple[int, str]] = []
        watch.forget(self.paths, "night-1")

    def context(self) -> engine.HookContext:
        return engine.HookContext(
            self.paths, "night-1", self.rec, {}, lambda number: None,
            stop_attempt=lambda number, why: self.stopped.append((number, why)),
            live_sessions=lambda: [1])

    def notes(self) -> str:
        return " | ".join(n["text"] for n in self.rec.data["notes"])

    def result(self, text: str = "", *, handoff: dict[str, Any] | None = None,
               exit_code: int = 0) -> sessions.Result:
        return sessions.Result(exit_code=exit_code, stdout=text, stderr="", output=None,
                               handoff=handoff)


class AssessASessionTest(Base):
    def test_a_finished_session_with_a_repeated_error_is_assessed_as_stuck(self) -> None:
        text = "\n".join([SAME_ERROR, "x", SAME_ERROR, "y", SAME_ERROR])
        found = watch.assess_session(self.context(), 1, self.result(text))
        assert found is not None
        self.assertEqual(found.kind, "stuck")

    def test_a_usage_limit_session_is_assessed_as_a_usage_limit(self) -> None:
        found = watch.assess_session(self.context(), 1, self.result("usage limit reached"))
        assert found is not None
        self.assertEqual(found.kind, "usage-limit")

    def test_a_clean_session_is_assessed_as_nothing(self) -> None:
        self.assertIsNone(watch.assess_session(self.context(), 1, self.result("all done")))

    def test_what_the_stream_found_is_not_lost(self) -> None:
        context = self.context()
        for _ in range(3):
            watch.on_output(context, 1, SAME_ERROR)
            watch.on_output(context, 1, "tool call")
        self.assertEqual(len(self.stopped), 1)
        self.assertEqual(self.stopped[0][0], 1)
        found = watch.assess_session(context, 1, self.result(""))
        assert found is not None
        self.assertEqual(found.kind, "stuck")

    def test_a_stream_that_found_nothing_stops_nothing(self) -> None:
        context = self.context()
        watch.on_output(context, 1, "fine")
        self.assertEqual(self.stopped, [])

    def test_a_usage_limit_in_the_stream_stops_no_attempt(self) -> None:
        context = self.context()
        watch.on_output(context, 1, "Claude AI usage limit reached|1900000000")
        self.assertEqual(self.stopped, [], "a usage limit ends the session by itself")
        found = watch.assess_session(context, 1, self.result(""))
        assert found is not None
        self.assertEqual(found.kind, "usage-limit")

    def test_a_new_session_starts_with_a_clean_watcher(self) -> None:
        context = self.context()
        for _ in range(3):
            watch.on_output(context, 1, SAME_ERROR)
            watch.on_output(context, 1, "tool call")
        self.assertIsNotNone(watch.assess_session(context, 1, self.result("")))
        self.assertIsNone(watch.assess_session(context, 1, self.result("")))


class WatchTheWorktreeTest(Base):
    def make_tree(self) -> Path:
        import subprocess

        folder = self.paths.worktrees_dir / "1-menu"
        folder.mkdir(parents=True)
        for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@example.test"],
                     ["config", "user.name", "T"], ["config", "commit.gpgsign", "false"]):
            subprocess.run(["git", "-C", str(folder), *args], check=True)
        (folder / "a.txt").write_text("one\n")
        subprocess.run(["git", "-C", str(folder), "add", "a.txt"], check=True)
        subprocess.run(["git", "-C", str(folder), "commit", "-q", "-m", "start"], check=True)
        self.rec.update(1, worktree="1-menu")
        return folder

    def test_a_change_undone_and_redone_in_the_folder_stops_the_attempt(self) -> None:
        folder = self.make_tree()
        context = self.context()
        old = watch.DIGEST_SECONDS
        watch.DIGEST_SECONDS = 0.0
        self.addCleanup(setattr, watch, "DIGEST_SECONDS", old)
        for text in ("one\n", "two\n", "one\n", "two\n"):
            (folder / "a.txt").write_text(text)
            watch.run_hook(context, "tick")
        self.assertEqual(len(self.stopped), 1, self.notes())
        self.assertIn("undone and redone", self.stopped[0][1])

    def test_a_folder_that_cannot_be_read_is_a_note_and_not_a_pass(self) -> None:
        self.rec.update(1, worktree="1-gone")
        old = watch.DIGEST_SECONDS
        watch.DIGEST_SECONDS = 0.0
        self.addCleanup(setattr, watch, "DIGEST_SECONDS", old)
        watch.run_hook(self.context(), "tick")
        watch.run_hook(self.context(), "tick")
        self.assertIn("cannot be read", self.notes())
        self.assertEqual(self.notes().count("cannot be read"), 1, "the note repeats")


class RealStopsTest(Base):
    def env_failure(self, piece: int) -> None:
        handoff = {"outcome": "blocked-by-environment", "reason": "the registry is refused"}
        watch.run_hook(self.context(), "session-ended", piece=piece,
                       result=self.result("", handoff=handoff))

    def stops(self) -> list[dict[str, Any]]:
        return list(self.rec.data.get("real_stops", []))

    def test_two_environment_failures_in_a_row_on_different_pieces_notify_once(self) -> None:
        self.env_failure(1)
        self.assertEqual(self.stops(), [])
        self.env_failure(2)
        self.assertEqual(len(self.stops()), 1)
        self.assertEqual(self.stops()[0]["kind"], "environment")
        self.assertEqual(self.stops()[0]["pieces"], [1, 2])
        self.assertIn("environment", self.notes())
        self.env_failure(1)
        self.env_failure(2)
        self.assertEqual(len(self.stops()), 1, "the same stop was notified twice")

    def test_two_environment_failures_on_one_piece_are_not_a_run_level_stop(self) -> None:
        self.env_failure(1)
        self.env_failure(1)
        self.assertEqual(self.stops(), [])

    def test_a_good_session_between_them_ends_the_row(self) -> None:
        self.env_failure(1)
        watch.run_hook(self.context(), "session-ended", piece=3,
                       result=self.result("", handoff={"outcome": "done", "summary": "x"}))
        self.env_failure(2)
        self.assertEqual(self.stops(), [])

    def test_the_notice_goes_to_the_log_too(self) -> None:
        import contextlib
        import io

        caught = io.StringIO()
        with contextlib.redirect_stderr(caught):
            self.env_failure(1)
            self.env_failure(2)
        self.assertIn("real stop", caught.getvalue())

    def write_log(self, rows: list[dict[str, Any]]) -> None:
        target = self.paths.command_log("night-1")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def refusal(self, piece: int, command: str) -> dict[str, Any]:
        return {"event": "refuse", "command": command, "session": f"s{piece}",
                "cwd": str(self.paths.worktrees_dir / f"{piece}-name")}

    def test_the_same_refused_command_in_two_pieces_notifies_once(self) -> None:
        self.write_log([self.refusal(1, "npm  install left-pad"),
                        self.refusal(2, "npm install left-pad")])
        watch.run_hook(self.context(), "session-ended", piece=2, result=self.result(""))
        watch.run_hook(self.context(), "session-ended", piece=2, result=self.result(""))
        found = [s for s in self.stops() if s["kind"] == "refused-command"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["pieces"], [1, 2])
        self.assertIn("npm install left-pad", found[0]["text"])

    def test_a_link_in_the_folder_path_does_not_hide_the_piece(self) -> None:
        real = self.paths.worktrees_dir / "1-name"
        real.mkdir(parents=True)
        link = self.folder / "link-to-worktrees"
        link.symlink_to(self.paths.worktrees_dir)
        self.write_log([{"event": "refuse", "command": "npm i x", "cwd": str(link / "1-name")},
                        self.refusal(2, "npm i x")])
        watch.run_hook(self.context(), "session-ended", piece=2, result=self.result(""))
        found = [s for s in self.stops() if s["kind"] == "refused-command"]
        self.assertEqual(found[0]["pieces"], [1, 2])

    def test_the_same_refused_command_twice_in_one_piece_is_not_a_run_level_stop(self) -> None:
        self.write_log([self.refusal(1, "npm install x"), self.refusal(1, "npm install x")])
        watch.run_hook(self.context(), "session-ended", piece=1, result=self.result(""))
        self.assertEqual(self.stops(), [])

    def test_a_command_log_that_cannot_be_read_is_a_note(self) -> None:
        target = self.paths.command_log("night-1")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"\xff\xfe not text \xff")
        watch.run_hook(self.context(), "session-ended", piece=1, result=self.result(""))
        self.assertIn("command log", self.notes())

    def failing(self, piece: int,
                text: str = "Error: the database is not running at port 5431") -> None:
        watch.run_hook(self.context(), "session-ended", piece=piece, result=self.result(text))

    def test_the_same_failure_across_three_pieces_notifies_once(self) -> None:
        self.failing(1, "Error: the database is not running at port 5431")
        self.failing(2, "Error: the database is not running at port 5432")
        self.assertEqual(self.stops(), [])
        self.failing(3, "Error: the database is not running at port 5433")
        self.assertEqual([s["kind"] for s in self.stops()], ["same-failure"])
        self.assertEqual(self.stops()[0]["pieces"], [1, 2, 3])
        self.failing(4, "Error: the database is not running at port 5434")
        self.assertEqual(len(self.stops()), 1)

    def test_a_hand_off_that_says_done_gives_no_failure_of_its_own(self) -> None:
        for piece in (1, 2, 3):
            done = {"outcome": "done", "summary": f"Built piece {piece} in its own words."}
            watch.run_hook(self.context(), "session-ended", piece=piece,
                           result=self.result("Error: the database is not running", handoff=done))
        self.assertEqual([s["kind"] for s in self.stops()], ["same-failure"])
        self.assertIn("database", self.stops()[0]["text"])

    def test_gave_up_words_name_the_failure(self) -> None:
        for piece in (1, 2, 3):
            gave = {"outcome": "gave-up", "reason": f"the database at port 543{piece} is down"}
            watch.run_hook(self.context(), "session-ended", piece=piece,
                           result=self.result("", handoff=gave))
        self.assertEqual([s["kind"] for s in self.stops()], ["same-failure"])

    def stale_failure_in_the_log(self) -> None:
        from types import SimpleNamespace

        from loop import attempt_log
        found = SimpleNamespace(record=[{"kind": attempt_log.KIND, "result": "failed",
                                         "findings": [{"text": "the judge failed on fl-1"}]}])
        old = watch.moves.read_piece
        watch.moves.read_piece = lambda paths, number: found  # type: ignore[assignment]
        self.addCleanup(setattr, watch.moves, "read_piece", old)

    def test_a_good_session_does_not_repeat_the_failure_of_an_earlier_attempt(self) -> None:
        self.stale_failure_in_the_log()
        for piece in (1, 2, 3):
            done = {"outcome": "done", "summary": f"Built piece {piece}."}
            watch.run_hook(self.context(), "session-ended", piece=piece,
                           result=self.result(final("Built it."), handoff=done))
        self.assertEqual(self.stops(), [])

    def test_a_session_with_no_hand_off_names_the_failure_of_the_last_attempt(self) -> None:
        self.stale_failure_in_the_log()
        for piece in (1, 2, 3):
            watch.run_hook(self.context(), "session-ended", piece=piece,
                           result=self.result(final("I stopped.")))
        self.assertEqual([s["kind"] for s in self.stops()], ["same-failure"])

    def test_the_same_failure_on_one_piece_many_times_is_not_a_run_level_stop(self) -> None:
        for _ in range(5):
            self.failing(1)
        self.assertEqual(self.stops(), [])

    def test_a_stop_already_in_the_record_is_not_notified_again_after_a_restart(self) -> None:
        self.env_failure(1)
        self.env_failure(2)
        watch.forget(self.paths, "night-1")  # a run started again: the module forgot its state
        self.env_failure(1)
        self.env_failure(2)
        self.assertEqual(len(self.stops()), 1)

    def test_the_run_carries_on_a_real_stop_stops_no_attempt_and_no_piece(self) -> None:
        self.env_failure(1)
        self.env_failure(2)
        self.assertEqual(self.stopped, [])
        self.assertEqual(self.rec.status(3), record.PENDING)
        self.assertNotEqual(self.rec.data["status"], record.RUN_STOPPED)

    def test_a_hook_event_nobody_handles_changes_nothing(self) -> None:
        for event in ("start", "piece-built", "built-all", "run-end"):
            watch.run_hook(self.context(), event)
        self.assertEqual(self.stops(), [])


if __name__ == "__main__":
    unittest.main()
