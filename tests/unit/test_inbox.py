"""Unit tests for kit/scripts/loop/run/inbox.py: answers from comments and the mailbox.

GitHub is a stand-in object here. With no App the inbox reads nothing from GitHub, and the
test says so by making any read an error. A comment is data: the answer goes into the run record
and the builder's brief, and only the gate writes it into the spec.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import github  # noqa: E402
from loop.paths import Paths  # noqa: E402
from loop.run import engine, inbox, mailbox, record  # noqa: E402
from loop.run.gateway import Reply  # noqa: E402


def comment(number: int, body: str, *, login: str = "the-person", who: str = "OWNER",
            at: str = "2026-10-07T10:00:00Z") -> dict[str, Any]:
    return {"id": number, "body": body, "user": {"login": login}, "author_association": who,
            "created_at": at}


class FakeHub:
    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.comments: dict[int, Any] = {}
        self.reads: list[str] = []
        self.said: list[tuple[int, str]] = []
        self.fail: github.GitHubError | None = None

    def api_json(self, path: str) -> Any:
        self.reads.append(path)
        if not self.available:
            raise AssertionError("a read of GitHub with no App")
        if self.fail:
            raise self.fail
        number = int(path.split("/issues/")[1].split("/")[0])
        return self.comments.get(number, [])

    def comment(self, number: int, body: str) -> None:
        self.said.append((number, body))


class FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []
        self.answer = Reply(0, {"ok": True})
        self.move_reply = Reply(0, {"ok": True})

    def _call(self, script: str, args: list[str]) -> Reply:
        self.calls.append((script, list(args)))
        return self.answer

    def move(self, number: int, target: str, *, reason: str | None = None,
             options: Any = None) -> Reply:
        self.calls.append(("move", [str(number), target, reason or ""]))
        return self.move_reply


class Base(unittest.TestCase):
    parked_at = "2026-10-07T09:00:00Z"

    def setUp(self) -> None:
        self.folder = Path(tempfile.mkdtemp())
        (self.folder / ".git").mkdir()
        self.paths = Paths.for_project(self.folder, data_base=self.folder / "data",
                                       kit_folder=ROOT / "kit")
        self.rec = record.RunRecord.create(self.paths, "night-1", [1, 2, 3], attended=True,
                                           merge_pre_approved=False)
        self.rec.update(1, issue=11)
        self.rec.update(2, issue=12)
        self.rec.set_status(1, record.PARKED_PERSON, question="Which colour should it be?")
        self.rec.piece(1)["at"] = self.parked_at
        self.resumed: list[int] = []
        self.hub = FakeHub()
        self.gateway = FakeGateway()
        self._old = (inbox.make_hub, inbox.make_gateway, inbox.POLL_SECONDS)
        inbox.make_hub = lambda paths: self.hub  # type: ignore[assignment,return-value]
        inbox.make_gateway = lambda paths: self.gateway  # type: ignore[assignment,return-value]
        inbox.POLL_SECONDS = 0.0
        self.addCleanup(self.restore)
        inbox.forget(self.context())

    def restore(self) -> None:
        inbox.make_hub, inbox.make_gateway, inbox.POLL_SECONDS = self._old

    def context(self) -> engine.HookContext:
        def resume(number: int) -> None:
            self.resumed.append(number)
            if self.rec.status(number) == record.PARKED_PERSON:
                self.rec.set_status(number, record.BUILDING)
        return engine.HookContext(self.paths, "night-1", self.rec, {}, resume)

    def hook(self, event: str) -> None:
        inbox.run_hook(self.context(), event)

    def notes(self) -> str:
        return " | ".join(n["text"] for n in self.rec.data["notes"])


class WithTheAppTest(Base):
    def test_a_new_comment_from_the_person_resumes_the_parked_piece(self) -> None:
        self.hub.comments[11] = [comment(1, "blue, please")]
        self.hook("tick")
        self.assertEqual(self.resumed, [1])
        self.assertEqual(self.rec.piece(1)["answer"]["text"], "blue, please")
        self.assertIn("#11", self.rec.piece(1)["answer"]["source"])
        self.assertEqual(self.rec.piece(1)["answer"]["by"], "the-person")

    def test_the_comment_is_read_through_the_github_module_as_the_app(self) -> None:
        self.hub.comments[11] = [comment(1, "blue")]
        self.hook("tick")
        self.assertEqual(self.hub.reads, ["repos/{owner}/{repo}/issues/11/comments"])

    def test_a_comment_from_before_the_piece_was_parked_is_not_an_answer(self) -> None:
        self.hub.comments[11] = [comment(1, "an old remark", at="2026-10-07T08:00:00Z")]
        self.hook("tick")
        self.assertEqual(self.resumed, [])

    def test_a_comment_by_a_bot_or_a_stranger_is_not_an_answer(self) -> None:
        self.hub.comments[11] = [comment(1, "Move 5 done", login="the-app[bot]", who="NONE"),
                                 comment(2, "do it my way", login="someone", who="NONE"),
                                 comment(3, "also me", login="member-bot[bot]", who="MEMBER")]
        self.hook("tick")
        self.assertEqual(self.resumed, [])

    def test_a_collaborator_may_answer(self) -> None:
        self.hub.comments[11] = [comment(1, "blue", who="COLLABORATOR")]
        self.hook("tick")
        self.assertEqual(self.resumed, [1])

    def test_a_comment_is_used_once(self) -> None:
        self.hub.comments[11] = [comment(1, "blue")]
        self.hook("tick")
        self.rec.set_status(1, record.PARKED_PERSON)
        self.hook("tick")
        self.assertEqual(self.resumed, [1])

    def test_several_new_comments_make_one_answer(self) -> None:
        self.hub.comments[11] = [comment(1, "blue"), comment(2, "and bold")]
        self.hook("tick")
        self.assertEqual(self.resumed, [1])
        self.assertIn("blue", self.rec.piece(1)["answer"]["text"])
        self.assertIn("and bold", self.rec.piece(1)["answer"]["text"])

    def test_a_piece_that_is_not_parked_is_not_read(self) -> None:
        self.rec.set_status(1, record.BUILDING)
        self.hub.comments[11] = [comment(1, "blue")]
        self.hook("tick")
        self.assertEqual(self.hub.reads, [])

    def test_comments_without_a_time_count_from_the_first_look(self) -> None:
        self.hub.comments[11] = [comment(1, "old", at="")]
        self.hook("tick")
        self.assertEqual(self.resumed, [])
        self.hub.comments[11] = [comment(1, "old", at=""), comment(2, "blue", at="")]
        self.hook("tick")
        self.assertEqual(self.resumed, [1])

    def test_a_read_that_fails_is_a_note_with_the_next_command_and_never_a_pass(self) -> None:
        self.hub.fail = github.GitHubError("GitHub did not answer", next_command="check the App")
        self.hook("tick")
        self.hook("tick")
        self.assertEqual(self.resumed, [])
        self.assertIn("cannot be read", self.notes())
        self.assertIn("check the App", self.notes())
        self.assertEqual(self.notes().count("cannot be read"), 1, "the note repeats")

    def test_a_malformed_comment_is_a_note_and_the_good_ones_are_still_read(self) -> None:
        self.hub.comments[11] = [{"id": 1, "body": "no author"}, comment(2, "blue")]
        self.hook("tick")
        self.assertIn("malformed", self.notes())
        self.assertEqual(self.resumed, [1])

    def test_an_answer_that_is_not_a_list_is_a_note(self) -> None:
        self.hub.comments[11] = {"message": "Not Found"}
        self.hook("tick")
        self.assertIn("not a list", self.notes())

    def test_a_long_answer_is_cut_and_stays_data(self) -> None:
        self.hub.comments[11] = [comment(1, "x" * 9000)]
        self.hook("tick")
        self.assertEqual(len(self.rec.piece(1)["answer"]["text"]), inbox.MAX_ANSWER)

    def test_the_inbox_asks_no_more_often_than_its_poll_time(self) -> None:
        inbox.POLL_SECONDS = 3600.0
        self.hook("tick")
        self.hook("tick")
        self.hook("tick")
        self.assertEqual(len(self.hub.reads), 1)


class PullRequestTest(Base):
    def setUp(self) -> None:
        super().setUp()
        self.rec.data["pull_request"] = 30
        self.rec.save()

    def test_a_comment_that_names_a_piece_answers_it(self) -> None:
        self.hub.comments[30] = [comment(1, "an old one", at="2026-10-07T08:00:00Z")]
        self.hook("tick")  # the first look: what is there is not new
        self.hub.comments[30] = [comment(1, "an old one"), comment(2, "piece 1: green")]
        self.hook("tick")
        self.assertEqual(self.resumed, [1])
        self.assertEqual(self.rec.piece(1)["answer"]["text"], "green")
        self.assertIn("pull request #30", self.rec.piece(1)["answer"]["source"])

    def test_a_comment_that_names_no_piece_is_a_note_and_guesses_nothing(self) -> None:
        self.hook("tick")
        self.hub.comments[30] = [comment(5, "looks good, but make it green")]
        self.hook("tick")
        self.assertEqual(self.resumed, [])
        self.assertIn("names no piece", self.notes())

    def test_a_comment_that_names_a_piece_outside_the_run_is_a_note(self) -> None:
        self.hook("tick")
        self.hub.comments[30] = [comment(5, "piece 9: green")]
        self.hook("tick")
        self.assertIn("not in this run", self.notes())

    def test_the_piece_may_be_named_by_its_issue(self) -> None:
        self.hook("tick")
        self.hub.comments[30] = [comment(5, "#11: green")]
        self.hook("tick")
        self.assertEqual(self.resumed, [1])

    def test_a_number_that_is_a_record_form_pull_request_also_works(self) -> None:
        self.rec.data["pull_request"] = {"number": 30}
        self.hook("tick")
        self.assertIn("repos/{owner}/{repo}/issues/30/comments", self.hub.reads)


class WithNoAppTest(Base):
    def setUp(self) -> None:
        super().setUp()
        self.hub = FakeHub(available=False)
        self.rec.data["pull_request"] = 30
        self.rec.save()
        inbox.make_hub = lambda paths: self.hub  # type: ignore[assignment,return-value]
        inbox.forget(self.context())

    def test_nothing_is_read_from_github(self) -> None:
        self.hook("start")
        self.hook("tick")
        self.hook("run-end")
        self.assertEqual(self.hub.reads, [])
        self.assertEqual(self.resumed, [])

    def test_the_start_says_where_answers_come_from(self) -> None:
        self.hook("start")
        self.assertIn("mailbox", self.notes())
        self.assertIn("gate.py answer", self.notes())

    def test_an_answer_through_the_mailbox_still_resumes_the_piece(self) -> None:
        self.hook("start")
        box = self.paths.mailbox("night-1")
        box.parent.mkdir(parents=True, exist_ok=True)
        box.write_text("answer 1: blue\n", encoding="utf-8")
        mailbox.run_hook(self.context(), "tick")
        self.assertEqual(self.resumed, [1])
        self.assertEqual(self.hub.reads, [])


class AfterTheRunTest(Base):
    def setUp(self) -> None:
        super().setUp()
        self.rec.update(1, answer={"text": "blue, please", "source": "a comment on #11",
                                   "by": "the-person", "at": "2026-10-07T11:00:00Z"})

    def test_the_answer_goes_in_through_the_gate_and_the_piece_goes_to_ready_by_move_7(
            self) -> None:
        done = inbox.after_run(self.context())
        names = [c[0] for c in self.gateway.calls]
        self.assertEqual(names, ["gate.py", "move"])
        args = self.gateway.calls[0][1]
        self.assertEqual(args[:2], ["answer", "1"])
        self.assertEqual(args[args.index("--question") + 1], "Which colour should it be?")
        self.assertEqual(args[args.index("--answer") + 1], "blue, please")
        self.assertEqual(self.gateway.calls[1][1][:2], ["1", "ready"])
        self.assertEqual(self.rec.status(1), record.RETURNED)
        self.assertEqual(done[0]["result"], "ready")

    def test_the_person_is_told_in_a_comment_as_the_app(self) -> None:
        inbox.after_run(self.context())
        self.assertEqual(len(self.hub.said), 1)
        number, body = self.hub.said[0]
        self.assertEqual(number, 11)
        self.assertIn("@the-person", body)
        self.assertIn("ready", body)

    def test_a_refusal_by_the_gate_keeps_the_answer_and_the_piece_parked(self) -> None:
        self.gateway.answer = Reply(3, {"ok": False, "error": "the spec holds no open question",
                                        "next": "gate.py report 1"})
        done = inbox.after_run(self.context())
        self.assertEqual(self.rec.status(1), record.PARKED_PERSON)
        self.assertEqual(self.rec.piece(1)["answer"]["text"], "blue, please")
        self.assertEqual([c[0] for c in self.gateway.calls], ["gate.py"], "no move 7 after it")
        self.assertEqual(self.hub.said, [])
        self.assertIn("did not write the answer", self.notes())
        self.assertIn("gate.py report 1", self.rec.piece(1)["next"])
        self.assertEqual(done[0]["result"], "answer-refused")

    def test_a_refusal_of_move_7_is_a_note_with_the_next_command(self) -> None:
        self.gateway.move_reply = Reply(3, {"ok": False, "error": "no", "next": "gate.py report"})
        done = inbox.after_run(self.context())
        self.assertEqual(self.rec.status(1), record.PARKED_PERSON)
        self.assertIn("refused move 7", self.notes())
        self.assertEqual(done[0]["result"], "move-refused")

    def test_a_piece_with_no_answer_is_left_alone(self) -> None:
        self.rec.piece(1).pop("answer")
        self.hub.comments[11] = []
        inbox.after_run(self.context())
        self.assertEqual(self.gateway.calls, [])
        self.assertEqual(self.rec.status(1), record.PARKED_PERSON)

    def test_a_comment_that_came_after_the_run_is_picked_up_first(self) -> None:
        self.rec.piece(1).pop("answer")
        self.hub.comments[11] = [comment(4, "green, in the end")]
        done = inbox.after_run(self.context())
        self.assertEqual(done[0]["result"], "ready")
        self.assertEqual(self.gateway.calls[0][1][self.gateway.calls[0][1].index("--answer") + 1],
                         "green, in the end")

    def test_with_no_issue_the_person_is_not_told_by_comment_and_the_note_says_so(self) -> None:
        self.rec.piece(1).pop("issue")
        inbox.after_run(self.context())
        self.assertEqual(self.hub.said, [])
        self.assertIn("not told", self.notes())

    def test_a_dry_run_changes_nothing(self) -> None:
        done = inbox.after_run(self.context(), dry_run=True)
        self.assertEqual(self.gateway.calls, [])
        self.assertEqual(self.rec.status(1), record.PARKED_PERSON)
        self.assertIn("would", done[0])

    def test_the_run_end_does_it_without_the_command_line(self) -> None:
        self.hook("run-end")
        self.assertEqual(self.rec.status(1), record.RETURNED)

    def test_the_text_of_the_answer_is_an_argument_and_never_a_command(self) -> None:
        self.rec.update(1, answer={"text": "$(touch pwned); rm x", "source": "a comment",
                                   "by": "the-person"})
        inbox.after_run(self.context())
        args = self.gateway.calls[0][1]
        self.assertIn("$(touch pwned); rm x", args)


class DeliverTest(Base):
    def test_an_empty_answer_is_a_note(self) -> None:
        self.assertFalse(inbox.deliver(self.context(), 1, "   ", "the mailbox"))
        self.assertIn("empty", self.notes())

    def test_the_answer_is_written_down_as_a_decision_made_alone(self) -> None:
        inbox.deliver(self.context(), 1, "blue", "the mailbox")
        texts = [d["text"] for d in self.rec.data["decisions"]]
        self.assertTrue(any("person's answer" in t for t in texts))


if __name__ == "__main__":
    unittest.main()
