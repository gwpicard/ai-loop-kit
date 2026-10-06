"""Unit tests for kit/scripts/loop/moves.py: the gate's moves and the shared rules.

The checks of each move come from stub modules here. Each later piece tests its
own checks. GitHub is an in-memory stand-in with the App, or the real wrapper
with no App credential, which must start no program at all.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import attempt_log, evidence, fingerprint, github, moves, spec, states  # noqa: E402
from loop.cli import ExitCode  # noqa: E402
from loop.gates import CheckContext, CheckResult, passed, refused  # noqa: E402
from loop.paths import Paths  # noqa: E402

BODY = (ROOT / "tests" / "fixtures" / "specs" / "full.md").read_text(encoding="utf-8")
QUESTION = "Should a rename be undoable?"
TODAY = "2026-10-06"


class Loader:
    """Stub check modules. Each passes unless its name is in `refuse`."""

    def __init__(self) -> None:
        self.refuse: set[str] = set()
        self.data: dict[str, dict[str, Any]] = {}
        self.calls: list[tuple[str, int]] = []
        self.during: dict[str, Callable[[CheckContext], None]] = {}
        self.refusal_data: dict[str, dict[str, Any]] = {}

    def __call__(self, name: str) -> Callable[[CheckContext], CheckResult]:
        def check(ctx: CheckContext) -> CheckResult:
            self.calls.append((name, ctx.move.number))
            if name in self.during:
                self.during[name](ctx)
            if name in self.refuse:
                result = refused([f"the {name} stub refused"], f"fix the {name} stub")
                return CheckResult(ok=False, failures=result.failures,
                                   next_command=result.next_command,
                                   data=self.refusal_data.get(name, {}))
            return passed(**self.data.get(name, {}))

        return check


class FakeHub:
    """An in-memory GitHub with the App. It keeps the calls it was asked to make."""

    available = True
    actor = "ai-loop-kit-stand-in[bot]"

    def __init__(self) -> None:
        self.issues: dict[int, dict[str, Any]] = {}
        self.next = 1
        self.calls: list[tuple[str, Any]] = []
        self.labels: list[str] = []
        self.on_read: Callable[[int, int], None] | None = None
        self.reads = 0

    def read_issue(self, number: int) -> dict[str, Any]:
        self.reads += 1
        if self.on_read:
            self.on_read(number, self.reads)
        issue = self.issues[number]
        return {**issue, "labels": list(issue["labels"])}

    def read_again(self, number: int, first: Mapping[str, Any]) -> dict[str, Any]:
        now = self.read_issue(number)
        if sorted(now["labels"]) != sorted(first["labels"]) or now["body"] != first["body"]:
            raise github.ReadTwiceError(number)
        return now

    def create_issue(self, title: str, body: str, labels: Sequence[str]) -> int:
        number = self.next
        self.next += 1
        self.issues[number] = {"number": number, "title": title, "body": body,
                               "labels": list(labels), "state": "open", "comments": []}
        self.calls.append(("create", number))
        return number

    def edit_labels(self, number: int, *, add: Sequence[str], remove: Sequence[str]) -> None:
        labels = self.issues[number]["labels"]
        for name in remove:
            if name in labels:
                labels.remove(name)
        for name in add:
            if name not in labels:
                labels.append(name)
        self.calls.append(("labels", (number, tuple(add), tuple(remove))))

    def set_body(self, number: int, body: str) -> None:
        self.issues[number]["body"] = body
        self.calls.append(("body", number))

    def comment(self, number: int, body: str) -> None:
        self.issues[number]["comments"].append(body)
        self.calls.append(("comment", number))

    def close(self, number: int, reason: str) -> None:
        self.issues[number]["state"] = "closed"
        self.issues[number]["reason"] = reason
        self.calls.append(("close", number))

    def reopen(self, number: int) -> None:
        self.issues[number]["state"] = "open"
        self.calls.append(("reopen", number))

    def list_labels(self) -> list[str]:
        return list(self.labels)

    def create_label(self, name: str, colour: str, description: str) -> None:
        self.labels.append(name)
        self.calls.append(("label", name))


def new_paths() -> Paths:
    base = Path(tempfile.mkdtemp())
    root = base / "project"
    root.mkdir()
    return Paths.for_project(root, data_base=base / "data", kit_folder=ROOT / "kit")


def no_app_hub(paths: Paths, spawned: list[list[str]]) -> github.GitHub:
    def runner(command: list[str], **_kwargs: Any) -> Any:
        spawned.append(list(command))
        raise AssertionError(f"a program ran with no App: {command}")

    return github.GitHub(paths, runner=runner, env={})


# The moves that lead from capture to each state, with every check passing.
ROUTE = {
    "shaping": [],
    "ready": ["ready"],
    "building": ["ready", "building"],
    "review": ["ready", "building", "review"],
    "approval": ["ready", "building", "review", "approval"],
    "done": ["ready", "building", "review", "approval", "done"],
    "dropped": ["dropped"],
}



def send(gate: moves.Gate, person: Any) -> dict[str, Any]:
    """The person's sync: the dry run first, then sync with the digest it printed."""
    digest = gate.sync(person, dry_run=True)["digest"]
    return gate.sync(person, confirm=digest)

class Base(unittest.TestCase):
    app = True

    def setUp(self) -> None:
        self.paths = new_paths()
        self.loader = Loader()
        self.spawned: list[list[str]] = []
        self.hub: Any = FakeHub() if self.app else no_app_hub(self.paths, self.spawned)
        self.gate = moves.Gate(self.paths, self.hub, loader=self.loader, today=lambda: TODAY,
                               env={}, terminal=lambda: True)
        self.reasons = 0

    def capture(self, body: str = BODY) -> int:
        result = self.gate.capture(title="Rename a report", body=body, issue_type="feature")
        return int(result["piece"])

    def reason(self) -> str:
        self.reasons += 1
        return f"reason number {self.reasons}, written for this test"

    def walk(self, number: int, state: str) -> None:
        for target in ROUTE[state]:
            move = states.find(self.gate.piece(number).state, target)
            assert move is not None
            self.gate.move(number, target, reason=self.reason() if move.back else None)
        self.assertEqual(self.gate.piece(number).state, state)

    def labels(self, number: int) -> list[str]:
        issue = self.gate.piece(number).issue
        assert issue is not None
        return sorted(self.hub.issues[issue]["labels"])


class EveryMove(Base):
    """Each of the fourteen moves, with a passing stub and a refusing stub."""

    def test_move_1_capture(self) -> None:
        number = self.capture()
        self.assertEqual(self.gate.piece(number).state, "shaping")
        self.assertIn(("capture", 1), self.loader.calls)
        self.loader.refuse.add("capture")
        with self.assertRaises(moves.MoveError) as caught:
            self.capture()
        self.assertEqual(caught.exception.code, ExitCode.REFUSED)
        self.assertIn("fix the capture stub", caught.exception.next_command)
        self.assertEqual(len(self.hub.issues), 1, "a refused capture opens no issue")

    def check_move(self, origin: str, target: str, number_wanted: int) -> None:
        for refusing in (True, False):
            with self.subTest(origin=origin, target=target, refusing=refusing):
                piece = self.capture()
                self.walk(piece, origin)
                move = states.find(origin, target)
                assert move is not None
                self.assertEqual(move.number, number_wanted)
                before = evidence.read(self.paths, piece)
                labels_before = self.labels(piece)
                if refusing:
                    self.loader.refuse.add(move.checks)
                try:
                    if refusing:
                        with self.assertRaises(moves.MoveError) as caught:
                            self.gate.move(piece, target, reason=self.reason())
                        self.assertEqual(caught.exception.code, ExitCode.REFUSED)
                        self.assertIn(f"the {move.checks} stub refused", caught.exception.message)
                        self.assertIn(f"fix the {move.checks} stub",
                                      caught.exception.next_command)
                        self.assertEqual(self.gate.piece(piece).state, origin)
                        self.assertEqual(evidence.read(self.paths, piece), before)
                        self.assertEqual(self.labels(piece), labels_before)
                    else:
                        result = self.gate.move(piece, target, reason=self.reason())
                        self.assertEqual(result["move"], number_wanted)
                        self.assertEqual(self.gate.piece(piece).state, target)
                        self.assertIn(states.label(target), self.labels(piece))
                        self.assertNotIn(states.label(origin), self.labels(piece))
                        self.assertIn((move.checks, number_wanted), self.loader.calls)
                finally:
                    self.loader.refuse.discard(move.checks)

    def test_move_2(self) -> None:
        self.check_move("shaping", "ready", 2)

    def test_move_3(self) -> None:
        self.check_move("ready", "shaping", 3)

    def test_move_4(self) -> None:
        self.check_move("ready", "building", 4)

    def test_move_5(self) -> None:
        self.check_move("building", "review", 5)

    def test_move_6(self) -> None:
        self.check_move("building", "shaping", 6)

    def test_move_7(self) -> None:
        self.check_move("building", "ready", 7)
        self.check_move("approval", "ready", 7)

    def test_move_8(self) -> None:
        self.check_move("review", "building", 8)

    def test_move_9(self) -> None:
        self.check_move("review", "shaping", 9)

    def test_move_10(self) -> None:
        self.check_move("review", "approval", 10)

    def test_move_11(self) -> None:
        self.check_move("approval", "done", 11)

    def test_move_12(self) -> None:
        self.check_move("approval", "review", 12)

    def test_move_13(self) -> None:
        self.check_move("approval", "building", 13)
        self.check_move("approval", "shaping", 13)

    def test_move_14(self) -> None:
        self.check_move("shaping", "dropped", 14)
        self.check_move("ready", "dropped", 14)
        self.check_move("dropped", "shaping", 14)

    def test_done_closes_the_issue_and_dropped_closes_it_as_not_planned(self) -> None:
        piece = self.capture()
        self.walk(piece, "done")
        self.assertEqual(self.hub.issues[1]["reason"], "completed")
        other = self.capture()
        self.walk(other, "dropped")
        self.assertEqual(self.hub.issues[2]["reason"], "not planned")
        self.gate.move(other, "shaping", reason="the person wants it back after all")
        self.assertEqual(self.hub.issues[2]["state"], "open")


class OutsideTheTable(Base):
    def test_a_move_not_in_the_table_is_refused(self) -> None:
        piece = self.capture()
        before = evidence.read(self.paths, piece)
        for target in ("building", "review", "approval", "done", "shaping"):
            with self.assertRaises(moves.MoveError) as caught:
                self.gate.move(piece, target, reason=self.reason())
            self.assertEqual(caught.exception.code, ExitCode.REFUSED)
            self.assertIn("ready", caught.exception.next_command)
        self.assertEqual(evidence.read(self.paths, piece), before)
        self.assertEqual(self.loader.calls, [("capture", 1)], "no check ran")

    def test_a_state_that_does_not_exist_is_a_usage_fault(self) -> None:
        piece = self.capture()
        with self.assertRaises(moves.MoveError) as caught:
            self.gate.move(piece, "in-review")
        self.assertEqual(caught.exception.code, ExitCode.USAGE)

    def test_a_piece_the_gate_never_captured_is_refused(self) -> None:
        with self.assertRaises(moves.MoveError) as caught:
            self.gate.move(7, "ready")
        self.assertEqual(caught.exception.code, ExitCode.REFUSED)
        self.assertIn("gate.py capture", caught.exception.next_command)

    def test_a_check_module_not_installed_yet_refuses_with_a_next_line(self) -> None:
        # Only the capture checks are installed here, whatever later pieces have added.
        def only_capture(name: str) -> Callable[[CheckContext], CheckResult] | None:
            return moves.load_checks(name) if name == "capture" else None

        gate = moves.Gate(self.paths, self.hub, loader=only_capture, today=lambda: TODAY, env={})
        piece = int(gate.capture(title="t", body=BODY, issue_type="feature")["piece"])
        with self.assertRaises(moves.MoveError) as caught:
            gate.move(piece, "ready")
        self.assertEqual(caught.exception.code, ExitCode.REFUSED)
        self.assertIn("loop/gates/ready.py", caught.exception.message)
        self.assertIn("later piece", caught.exception.next_command)
        self.assertEqual(gate.piece(piece).state, "shaping")

    def test_the_real_capture_and_drop_checks_are_installed(self) -> None:
        gate = moves.Gate(self.paths, self.hub, today=lambda: TODAY, env={})
        piece = int(gate.capture(title="t", body=BODY, issue_type="feature")["piece"])
        gate.move(piece, "dropped", reason="not wanted any more")
        gate.move(piece, "shaping", reason="wanted again")
        self.assertEqual(gate.piece(piece).state, "shaping")

    def test_the_real_capture_check_refuses_an_empty_title(self) -> None:
        gate = moves.Gate(self.paths, self.hub, today=lambda: TODAY, env={})
        with self.assertRaises(moves.MoveError):
            gate.capture(title="  ", body=BODY, issue_type="feature")


class ReadTwice(Base):
    def test_a_label_change_between_the_reads_is_refused(self) -> None:
        piece = self.capture()

        def race(number: int, reads: int) -> None:
            if reads == start + 2:
                self.hub.issues[number]["labels"].append("type:bug")

        start = self.hub.reads
        self.hub.on_read = race
        with self.assertRaises(moves.MoveError) as caught:
            self.gate.move(piece, "ready")
        self.assertEqual(caught.exception.code, ExitCode.REFUSED)
        self.assertIn("moved", caught.exception.message)
        self.assertEqual(self.gate.piece(piece).state, "shaping")

    def test_a_record_change_between_the_reads_is_refused(self) -> None:
        piece = self.capture()

        def another_session(ctx: CheckContext) -> None:
            evidence.append(self.paths, ctx.number, [{"kind": "note", "text": "elsewhere"}])

        self.loader.during["ready"] = another_session
        with self.assertRaises(moves.MoveError) as caught:
            self.gate.move(piece, "ready")
        self.assertEqual(caught.exception.code, ExitCode.REFUSED)
        self.assertEqual(self.gate.piece(piece).state, "shaping")


class Reasons(Base):
    def test_every_move_back_needs_a_reason(self) -> None:
        piece = self.capture()
        self.walk(piece, "ready")
        for target in ("shaping", "dropped"):
            with self.assertRaises(moves.MoveError) as caught:
                self.gate.move(piece, target)
            self.assertEqual(caught.exception.code, ExitCode.REFUSED)
            self.assertIn("--reason", caught.exception.next_command)
            with self.assertRaises(moves.MoveError):
                self.gate.move(piece, target, reason="   ")

    def test_the_reason_goes_on_the_issue_and_in_the_record(self) -> None:
        piece = self.capture()
        self.walk(piece, "building")
        self.gate.move(piece, "ready", reason="the test database was down")
        comments = self.hub.issues[1]["comments"]
        self.assertTrue(any("the test database was down" in c for c in comments))
        last = [e for e in evidence.read(self.paths, piece) if e["kind"] == "move"][-1]
        self.assertEqual(last["reason"], "the test database was down")
        self.assertEqual(last["move"], 7)

    def test_a_forward_move_needs_no_reason(self) -> None:
        piece = self.capture()
        self.gate.move(piece, "ready")
        self.assertEqual(self.gate.piece(piece).state, "ready")


class AntiCircle(Base):
    def test_a_move_back_to_shaping_adds_its_reason_as_a_new_need(self) -> None:
        piece = self.capture()
        self.walk(piece, "ready")
        self.gate.move(piece, "shaping", reason="the export format is still unclear")
        body = self.gate.piece(piece).body
        questions = spec.parse(body).open_questions
        self.assertTrue(any("the export format is still unclear" in q for q in questions))
        self.assertTrue(self.gate.piece(piece).needs_you)

    def test_a_reason_already_on_the_piece_is_refused(self) -> None:
        piece = self.capture()
        self.walk(piece, "ready")
        self.gate.move(piece, "shaping", reason="the export format is still unclear")
        self.gate.move(piece, "ready")
        with self.assertRaises(moves.MoveError) as caught:
            self.gate.move(piece, "shaping", reason="The export format is still  unclear.")
        self.assertEqual(caught.exception.code, ExitCode.REFUSED)
        self.assertIn("already", caught.exception.message)
        self.assertEqual(self.gate.piece(piece).state, "ready")

    def test_the_rule_is_for_moves_back_to_shaping_only(self) -> None:
        piece = self.capture()
        self.walk(piece, "building")
        self.gate.move(piece, "ready", reason="the runner went away")
        self.gate.move(piece, "building")
        self.gate.move(piece, "ready", reason="the runner went away")
        self.assertEqual(self.gate.piece(piece).state, "ready")
        self.gate.move(piece, "dropped", reason="no longer wanted")
        self.gate.move(piece, "shaping", reason="the runner went away")
        self.assertEqual(self.gate.piece(piece).state, "shaping")


class RepeatCounter(Base):
    def test_move_8_three_times_then_back_to_shaping(self) -> None:
        piece = self.capture()
        self.walk(piece, "review")
        for n in range(3):
            self.gate.move(piece, "building", reason=f"trial join {n} turned red")
            self.gate.move(piece, "review")
        result = self.gate.move(piece, "building", reason="trial join 4 turned red")
        self.assertEqual(result["move"], 9)
        self.assertEqual(result["asked"], 8)
        self.assertEqual(self.gate.piece(piece).state, "shaping")
        moved = [e for e in evidence.read(self.paths, piece) if e["kind"] == "move"][-1]
        for n in range(3):
            self.assertIn(f"trial join {n} turned red", moved["reason"])

    def test_move_7_from_building_falls_back_by_move_6(self) -> None:
        piece = self.capture()
        self.walk(piece, "building")
        for n in range(3):
            self.gate.move(piece, "ready", reason=f"environment fault {n}")
            self.gate.move(piece, "building")
        result = self.gate.move(piece, "ready", reason="environment fault 4")
        self.assertEqual((result["move"], result["asked"]), (6, 7))
        self.assertEqual(self.gate.piece(piece).state, "shaping")

    def test_move_12_falls_back_by_move_13(self) -> None:
        piece = self.capture()
        self.walk(piece, "approval")
        for n in range(3):
            self.gate.move(piece, "review", reason=f"main moved {n}")
            self.gate.move(piece, "approval")
        result = self.gate.move(piece, "review", reason="main moved again")
        self.assertEqual((result["move"], result["asked"]), (13, 12))
        self.assertEqual(self.gate.piece(piece).state, "shaping")

    def test_after_a_reshaping_move_7_works_again(self) -> None:
        piece = self.capture()
        self.walk(piece, "building")
        for n in range(3):
            self.gate.move(piece, "ready", reason=f"environment fault {n}")
            self.gate.move(piece, "building")
        result = self.gate.move(piece, "ready", reason="environment fault 3")
        self.assertEqual((result["move"], result["asked"]), (6, 7))
        # The piece is reshaped and made ready, so the counter starts again.
        self.gate.move(piece, "ready")
        self.gate.move(piece, "building")
        result = self.gate.move(piece, "ready", reason="environment fault 4")
        self.assertEqual((result["move"], result["to"]), (7, "ready"))
        self.assertEqual(self.gate.piece(piece).state, "ready")
        for n in range(5, 7):
            self.gate.move(piece, "building")
            self.gate.move(piece, "ready", reason=f"environment fault {n}")
        self.gate.move(piece, "building")
        result = self.gate.move(piece, "ready", reason="environment fault 7")
        self.assertEqual((result["move"], result["asked"]), (6, 7),
                         "the limit holds again, and the gate's own reason is new")
        moved = [e for e in evidence.read(self.paths, piece) if e["kind"] == "move"][-1]
        self.assertIn("environment fault 4", moved["reason"])
        self.assertNotIn("environment fault 0", moved["reason"],
                         "only the moves since the piece last left shaping count")

    def test_other_moves_back_have_no_counter(self) -> None:
        piece = self.capture()
        for n in range(4):
            self.gate.move(piece, "dropped", reason=f"drop {n}")
            self.gate.move(piece, "shaping", reason=f"reopen {n}")
        self.assertEqual(self.gate.piece(piece).state, "shaping")


class MustLookRecord(Base):
    """The ready gate's must-look reasons and extra entries reach the piece record."""

    def test_the_reasons_sit_on_the_move_into_ready(self) -> None:
        piece = self.capture()
        self.loader.data["ready"] = {"must_look": ["a sensitive area", "a new dependency"]}
        result = self.gate.move(piece, "ready")
        self.assertEqual(result["must_look"], ["a sensitive area", "a new dependency"])
        moved = [e for e in evidence.read(self.paths, piece) if e["kind"] == "move"][-1]
        self.assertEqual(moved["must_look"], ["a sensitive area", "a new dependency"])
        found = self.gate.piece(piece)
        self.assertEqual(found.must_look, ["a sensitive area", "a new dependency"])
        self.assertTrue(found.individual_review)

    def test_a_piece_with_no_reason_gets_no_individual_review(self) -> None:
        piece = self.capture()
        self.gate.move(piece, "ready")
        self.assertEqual(self.gate.piece(piece).must_look, [])
        self.assertFalse(self.gate.piece(piece).individual_review)

    def test_going_back_to_shaping_and_ready_again_replaces_the_reasons(self) -> None:
        piece = self.capture()
        self.loader.data["ready"] = {"must_look": ["a security change"]}
        self.gate.move(piece, "ready")
        self.gate.move(piece, "shaping", reason="the claim found something new")
        self.loader.data["ready"] = {}
        self.gate.move(piece, "ready")
        self.assertEqual(self.gate.piece(piece).must_look, [])

    def test_extra_entries_are_written_after_the_gates_own(self) -> None:
        piece = self.capture()
        entry = {"kind": "test-lists", "lists": [["FL-1"], ["FL-1"]]}
        self.loader.data["ready"] = {"entries": [entry]}
        self.gate.move(piece, "ready")
        kinds = [e["kind"] for e in evidence.read(self.paths, piece)]
        self.assertEqual(kinds[-1], "test-lists")
        self.assertLess(kinds.index("move"), kinds.index("test-lists"))

    def test_the_report_shows_the_reasons(self) -> None:
        piece = self.capture()
        self.loader.data["ready"] = {"must_look": ["the person's mark"]}
        self.gate.move(piece, "ready")
        row = self.gate.report(brief=True)["pieces"][0]
        self.assertEqual(row["must_look"], ["the person's mark"])

    def test_a_dry_run_writes_no_reason(self) -> None:
        piece = self.capture()
        self.loader.data["ready"] = {"must_look": ["a security change"]}
        result = self.gate.move(piece, "ready", dry_run=True)
        self.assertEqual(result["must_look"], ["a security change"])
        self.assertEqual(self.gate.piece(piece).must_look, [])


class Fingerprints(Base):
    def ready_with_fingerprint(self) -> tuple[int, str]:
        piece = self.capture()
        taken = fingerprint.take(self.gate.piece(piece).body, "a1b2c3d")
        self.loader.data["ready"] = {"fingerprint": taken}
        self.gate.move(piece, "ready")
        self.assertEqual(self.gate.piece(piece).fingerprint, taken["fingerprint"])
        return piece, taken["fingerprint"]

    def test_a_gate_made_spec_change_takes_a_new_fingerprint(self) -> None:
        piece, old = self.ready_with_fingerprint()
        self.gate.move(piece, "shaping", reason="a new question came up in the claim")
        record = evidence.read(self.paths, piece)
        prints = [e for e in record if e["kind"] == "fingerprint"]
        self.assertEqual(len(prints), 2)
        self.assertEqual(prints[-1]["why"], "gate-made change")
        new = prints[-1]["fingerprint"]["fingerprint"]
        self.assertNotEqual(new, old)
        self.assertEqual(prints[-1]["fingerprint"]["judge_commit"], "a1b2c3d")
        body = self.gate.piece(piece).body
        self.assertEqual(new, fingerprint.take(body, "a1b2c3d")["fingerprint"])
        self.assertIn(f"loop:fingerprint {new}", body)
        self.assertFalse(self.gate.piece(piece).changed_outside)

    def test_an_edit_the_gate_did_not_make_shows_as_a_changed_fingerprint(self) -> None:
        piece, _old = self.ready_with_fingerprint()
        self.hub.issues[1]["body"] = self.hub.issues[1]["body"].replace("80 characters",
                                                                       "90 characters")
        self.assertTrue(self.gate.fingerprint_changed(piece))

    def test_answer_writes_a_late_answer_under_decisions_with_a_new_fingerprint(self) -> None:
        piece, old = self.ready_with_fingerprint()
        result = self.gate.answer(piece, question=QUESTION, answer="no, not in this piece",
                                  by="the person")
        body = self.gate.piece(piece).body
        parsed = spec.parse(body)
        self.assertTrue(any(QUESTION in d and "no, not in this piece" in d and TODAY in d
                            for d in parsed.decisions))
        self.assertFalse(any(QUESTION in q for q in parsed.open_questions))
        self.assertNotEqual(result["fingerprint"], old)
        self.assertEqual(self.gate.piece(piece).fingerprint, result["fingerprint"])
        self.assertFalse(self.gate.fingerprint_changed(piece))
        self.assertEqual(self.hub.issues[1]["body"], body)

    def test_answer_in_shaping_clears_the_needs_you_flag(self) -> None:
        piece = self.capture()
        self.assertIn("needs-you", self.labels(piece))
        result = self.gate.answer(piece, question=QUESTION, answer="no", by="the person")
        self.assertNotIn("fingerprint", result)
        self.assertNotIn("needs-you", self.labels(piece))
        self.assertFalse(self.gate.piece(piece).needs_you)

    def test_answer_to_a_question_the_spec_does_not_hold_is_refused(self) -> None:
        piece = self.capture()
        with self.assertRaises(moves.MoveError) as caught:
            self.gate.answer(piece, question="What colour is it?", answer="blue",
                             by="the person")
        self.assertEqual(caught.exception.code, ExitCode.REFUSED)


class SpecDoor(Base):
    """Only `answer` closes an open question. `gate.py spec` cannot remove one."""

    def without(self, body: str, words: str) -> str:
        item = next(q for q in spec.parse(body).open_questions if words in q)
        return spec.remove_list_item(body, "open_questions", item)

    def test_spec_cannot_remove_an_open_question(self) -> None:
        piece = self.capture()
        before = evidence.read(self.paths, piece)
        with self.assertRaises(moves.MoveError) as caught:
            self.gate.set_spec(piece, self.without(self.gate.piece(piece).body, QUESTION))
        self.assertEqual(caught.exception.code, ExitCode.REFUSED)
        self.assertIn("gate.py answer", caught.exception.next_command)
        self.assertEqual(evidence.read(self.paths, piece), before)
        self.assertTrue(self.gate.piece(piece).needs_you)

    def test_spec_cannot_remove_a_question_the_gate_wrote(self) -> None:
        piece = self.capture()
        self.walk(piece, "ready")
        self.gate.move(piece, "shaping", reason="the export format is still unclear")
        body = self.without(self.gate.piece(piece).body, "the export format is still unclear")
        with self.assertRaises(moves.MoveError) as caught:
            self.gate.set_spec(piece, body)
        self.assertIn("gate.py answer", caught.exception.next_command)

    def test_spec_may_keep_every_question_and_add_one(self) -> None:
        piece = self.capture()
        body = spec.add_list_item(self.gate.piece(piece).body, "open_questions",
                                  "Which months does the export cover?")
        result = self.gate.set_spec(piece, body)
        self.assertTrue(result["needs_you"])


class WhoAnswered(Base):
    def test_an_agent_session_cannot_record_the_person(self) -> None:
        gate = moves.Gate(self.paths, self.hub, loader=self.loader, today=lambda: TODAY,
                          env={"CLAUDECODE": "1"}, terminal=lambda: True)
        piece = self.capture()
        # Only "the agent" is accepted: any other name, a person's own name
        # included, is the person's to record in their own terminal.
        for who in ("the person", "The person", "person", "Guillaume", "the maintainer",
                    "the agent and the person"):
            with self.assertRaises(moves.MoveError) as caught:
                gate.answer(piece, question=QUESTION, answer="no", by=who)
            self.assertEqual(caught.exception.code, ExitCode.REFUSED)
            self.assertIn("their own terminal", caught.exception.next_command)
        gate.answer(piece, question=QUESTION, answer="no", by="the agent")
        entry = [e for e in evidence.read(self.paths, piece) if e["kind"] == "answer"][-1]
        self.assertEqual(entry["by"], "the agent")
        self.assertEqual(entry["recorded_in"], "an agent session")
        decisions = spec.parse(self.gate.piece(piece).body).decisions
        self.assertTrue(any("Decided by the agent" in d for d in decisions))

    def test_the_person_in_their_own_terminal_records_the_person(self) -> None:
        piece = self.capture()
        self.gate.answer(piece, question=QUESTION, answer="no", by="the person")
        entry = [e for e in evidence.read(self.paths, piece) if e["kind"] == "answer"][-1]
        self.assertEqual((entry["by"], entry["recorded_in"]), ("the person", "a terminal"))


class Labels(Base):
    def test_capture_writes_state_type_and_needs_you(self) -> None:
        piece = self.capture()
        self.assertEqual(self.labels(piece), ["needs-you", "state:shaping", "type:feature"])

    def test_the_needs_are_written_below_the_spec(self) -> None:
        piece = self.capture()
        body = self.hub.issues[1]["body"]
        below = body.split("<!-- spec:end -->", 1)[1]
        self.assertIn(moves.NEEDS_HEADING, below)
        self.assertIn(QUESTION, below)
        self.assertEqual(body.count(moves.NEEDS_HEADING), 1, "the old needs list was replaced")
        self.assertIn("loop:fingerprint none yet", below)
        self.assertEqual(self.gate.piece(piece).body, body)

    def test_a_second_state_label_is_refused(self) -> None:
        piece = self.capture()
        self.hub.issues[1]["labels"].append("state:ready")
        with self.assertRaises(moves.MoveError) as caught:
            self.gate.move(piece, "dropped", reason="not wanted")
        self.assertEqual(caught.exception.code, ExitCode.REFUSED)
        self.assertIn("two state:", caught.exception.message)
        self.assertIn("state:ready", self.hub.issues[1]["labels"])

    def test_a_hand_changed_label_is_reported_and_never_undone(self) -> None:
        piece = self.capture()
        labels = self.hub.issues[1]["labels"]
        labels.remove("state:shaping")
        labels.append("state:ready")
        report = self.gate.report()
        found = report["hand_changed"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["piece"], piece)
        self.assertEqual(found[0]["record"], "shaping")
        self.assertEqual(found[0]["labels"], ["state:ready"])
        with self.assertRaises(moves.MoveError) as caught:
            self.gate.move(piece, "dropped", reason="not wanted")
        self.assertIn("by hand", caught.exception.message)
        self.assertIn("state:ready", self.hub.issues[1]["labels"])
        self.assertNotIn("state:shaping", self.hub.issues[1]["labels"])
        self.assertEqual(self.gate.piece(piece).state, "shaping")

    def test_the_comparison_is_with_the_record_never_with_the_actor(self) -> None:
        text = (ROOT / "kit" / "scripts" / "loop" / "moves.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\bactors?\b", text.lower()))

    def test_labels_create_makes_only_the_missing_ones(self) -> None:
        self.hub.labels = ["state:shaping"]
        result = self.gate.create_labels()
        names = [name for name, _c, _t in states.LABELS]
        self.assertEqual(sorted(self.hub.labels), sorted(names))
        self.assertNotIn("state:shaping", result["created"])
        again = self.gate.create_labels()
        self.assertEqual(again["created"], [])


class WithoutTheApp(Base):
    app = False

    def test_every_move_works_in_the_record_and_the_queue_fills(self) -> None:
        result = self.gate.capture(title="Rename a report", body=BODY, issue_type="feature")
        piece = int(result["piece"])
        self.assertTrue(result["waiting"])
        self.assertIn("gate.py sync", result["next"])
        self.walk(piece, "approval")
        self.gate.move(piece, "ready", reason="the answer came after the run ended")
        record = self.gate.piece(piece)
        self.assertEqual(record.state, "ready")
        self.assertIsNone(record.issue)
        kinds = [op["op"] for op in record.queue]
        self.assertEqual(kinds[0], "issue")
        self.assertIn("labels", kinds)
        self.assertIn("comment", kinds)
        self.assertEqual(self.spawned, [], "no program ran: no gh, no keychain")

    def test_a_move_without_the_app_names_the_exact_command(self) -> None:
        piece = int(self.gate.capture(title="t", body=BODY, issue_type="chore")["piece"])
        result = self.gate.move(piece, "dropped", reason="not wanted")
        self.assertTrue(result["waiting"])
        gate_py = ROOT / "kit" / "scripts" / "gate.py"
        self.assertIn(f"python3 {gate_py} sync", result["next"])
        self.assertIn(str(self.paths.root), result["next"])

    def test_comment_and_labels_create_wait_for_the_person(self) -> None:
        piece = int(self.gate.capture(title="t", body=BODY, issue_type="bug")["piece"])
        result = self.gate.comment(piece, "a note for the person")
        self.assertTrue(result["waiting"])
        with self.assertRaises(moves.MoveError) as caught:
            self.gate.create_labels()
        self.assertEqual(caught.exception.code, ExitCode.REFUSED)
        self.assertIn("gate.py sync", caught.exception.next_command)
        self.assertEqual(self.spawned, [])

    def test_the_report_shows_the_waiting_pieces(self) -> None:
        piece = int(self.gate.capture(title="t", body=BODY, issue_type="feature")["piece"])
        report = self.gate.report(brief=True)
        self.assertEqual(report["app"], False)
        self.assertEqual(report["waiting_for_sync"], [piece])
        self.assertIn("gate.py sync", report["next"])

    def test_the_person_syncs_the_queue_with_their_own_sign_in(self) -> None:
        piece = int(self.gate.capture(title="t", body=BODY, issue_type="feature")["piece"])
        self.gate.move(piece, "ready")
        person = FakeHub()
        person.actor = "the-person"
        result = send(self.gate, person)
        self.assertEqual(result["pieces"][0]["piece"], piece)
        self.assertEqual(self.gate.piece(piece).queue, [])
        issue = self.gate.piece(piece).issue
        assert issue is not None
        self.assertEqual(sorted(person.issues[issue]["labels"]),
                         ["needs-you", "state:ready", "type:feature"])
        self.assertEqual(send(self.gate, person)["pieces"], [], "a second sync does nothing")

    def test_sync_reports_a_label_changed_by_hand_and_does_not_overwrite_it(self) -> None:
        piece = int(self.gate.capture(title="t", body=BODY, issue_type="feature")["piece"])
        person = FakeHub()
        send(self.gate, person)
        self.gate.move(piece, "ready")
        issue = self.gate.piece(piece).issue
        assert issue is not None
        person.issues[issue]["labels"].remove("state:shaping")
        person.issues[issue]["labels"].append("state:building")
        result = send(self.gate, person)
        self.assertTrue(result["refused"])
        self.assertIn("state:building", person.issues[issue]["labels"])
        self.assertNotIn("state:ready", person.issues[issue]["labels"])
        self.assertTrue(self.gate.piece(piece).queue, "the write stays queued")

    def test_the_gate_refuses_sync_in_an_agent_session(self) -> None:
        gate = moves.Gate(self.paths, self.hub, loader=self.loader, today=lambda: TODAY,
                          env={"CLAUDECODE": "1"})
        with self.assertRaises(moves.MoveError) as caught:
            gate.sync(FakeHub())
        self.assertEqual(caught.exception.code, ExitCode.REFUSED)
        self.assertIn("person", caught.exception.message)

    def test_the_guard_hook_refuses_sync_from_an_agent_session(self) -> None:
        call = {"tool_name": "Bash", "tool_input": {"command": "python3 kit/scripts/gate.py sync"},
                "cwd": str(self.paths.root)}
        done = subprocess.run(
            [sys.executable, str(ROOT / "kit" / "hooks" / "guard.py")],
            input=json.dumps(call), capture_output=True, text=True, check=False,
            env={**os.environ, "AI_LOOP_KIT_DATA": str(self.paths.data_dir)},
        )
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn("gate.py sync", done.stderr)


class WhatSyncShows(Base):
    app = False

    def test_the_dry_run_lists_every_queued_write_in_full(self) -> None:
        piece = int(self.gate.capture(title="t", body=BODY, issue_type="feature")["piece"])
        self.gate.comment(piece, "Looks good, merge it")
        self.gate.move(piece, "dropped", reason="not wanted any more")
        result = self.gate.sync(FakeHub(), dry_run=True)
        self.assertEqual(result["pieces"][0]["piece"], piece)
        writes = result["pieces"][0]["writes"]
        kinds = [w["op"] for w in writes]
        self.assertEqual(kinds[0], "issue")
        for kind in ("comment", "labels", "close"):
            self.assertIn(kind, kinds)
        shown = json.dumps(writes)
        self.assertIn("Looks good, merge it", shown)
        self.assertIn("not wanted any more", shown)
        self.assertIn("state:dropped", shown)
        self.assertIn(QUESTION, shown, "the issue body is shown in full")
        self.assertTrue(self.gate.piece(piece).queue, "a dry run sends nothing")

    def test_sync_needs_the_digest_the_dry_run_printed(self) -> None:
        piece = int(self.gate.capture(title="t", body=BODY, issue_type="feature")["piece"])
        person = FakeHub()
        dry = self.gate.sync(person, dry_run=True)
        digest = dry["digest"]
        self.assertRegex(digest, r"^[0-9a-f]{12}$")
        self.assertIn(f"sync --confirm {digest}", dry["next"])
        with self.assertRaises(moves.MoveError) as caught:
            self.gate.sync(person)
        self.assertEqual(caught.exception.code, ExitCode.REFUSED)
        self.assertIn("sync --dry-run", caught.exception.next_command)
        self.assertEqual(person.calls, [], "nothing is sent without the digest")
        # The queue grows after the person read the dry run: the old digest is refused.
        self.gate.comment(piece, "Looks good, merge it")
        with self.assertRaises(moves.MoveError) as caught:
            self.gate.sync(person, confirm=digest)
        self.assertEqual(caught.exception.code, ExitCode.REFUSED)
        self.assertIn("changed", caught.exception.message)
        self.assertEqual(person.calls, [], "a changed queue sends nothing")
        self.assertNotEqual(self.gate.sync(person, dry_run=True)["digest"], digest)
        self.assertTrue(send(self.gate, person)["pieces"])

    def test_the_next_line_names_the_dry_run_first(self) -> None:
        result = self.gate.capture(title="t", body=BODY, issue_type="feature")
        line = result["next"]
        first = line.index("sync --dry-run")
        self.assertRegex(line[first + len("sync --dry-run"):], r"gate\.py sync(\s|$)")

    def test_sync_refuses_without_a_person_at_a_terminal(self) -> None:
        int(self.gate.capture(title="t", body=BODY, issue_type="feature")["piece"])
        gate = moves.Gate(self.paths, self.hub, loader=self.loader, today=lambda: TODAY,
                          env={}, terminal=lambda: False)
        person = FakeHub()
        digest = gate.sync(person, dry_run=True)["digest"]
        with self.assertRaises(moves.MoveError) as caught:
            gate.sync(person, confirm=digest)
        self.assertEqual(caught.exception.code, ExitCode.REFUSED)
        self.assertIn("terminal", caught.exception.message)
        self.assertEqual(person.calls, [])
        self.assertTrue(gate.sync(person, dry_run=True)["pieces"], "the dry run still shows")


class EitherNumber(Base):
    app = False

    def test_move_takes_the_local_number_or_the_synced_issue_number(self) -> None:
        piece = int(self.gate.capture(title="t", body=BODY, issue_type="feature")["piece"])
        person = FakeHub()
        person.next = 57
        send(self.gate, person)
        self.assertEqual(self.gate.piece(piece).issue, 57)
        result = self.gate.move(57, "ready")
        self.assertEqual((result["piece"], self.gate.piece(piece).state), (piece, "ready"))
        self.gate.move(piece, "shaping", reason="a new need came up")
        self.assertEqual(self.gate.piece(piece).state, "shaping")

    def test_a_number_that_is_neither_is_refused(self) -> None:
        int(self.gate.capture(title="t", body=BODY, issue_type="feature")["piece"])
        with self.assertRaises(moves.MoveError) as caught:
            self.gate.move(58, "ready")
        self.assertIn("not in the gate's record", caught.exception.message)


class WithTheAppAfterwards(Base):
    app = False

    def test_once_the_app_exists_the_queue_goes_out_as_the_app_first(self) -> None:
        piece = int(self.gate.capture(title="t", body=BODY, issue_type="feature")["piece"])
        hub = FakeHub()
        gate = moves.Gate(self.paths, hub, loader=self.loader, today=lambda: TODAY, env={})
        gate.move(piece, "ready")
        issue = gate.piece(piece).issue
        assert issue is not None
        self.assertEqual(sorted(hub.issues[issue]["labels"]),
                         ["needs-you", "state:ready", "type:feature"])
        self.assertEqual(gate.piece(piece).queue, [])


class DryRun(Base):
    def test_a_dry_run_changes_nothing(self) -> None:
        piece = self.capture()
        before = evidence.read(self.paths, piece)
        calls = list(self.hub.calls)
        result = self.gate.move(piece, "ready", dry_run=True)
        self.assertEqual(result["to"], "ready")
        self.assertEqual(evidence.read(self.paths, piece), before)
        self.assertEqual(self.hub.calls, calls)


class FailedAttempts(Base):
    """Move 5 when the attempt gate fails an attempt: it is logged, and may send the piece back."""

    def entry(self, number: int = 1) -> dict[str, Any]:
        return attempt_log.entry(
            number=number, result="failed", head="a" * 40, base="b" * 40, at=TODAY,
            findings=[attempt_log.finding("visible-judge", f"fault {number}")])

    def building(self) -> int:
        piece = self.capture()
        self.walk(piece, "building")
        self.loader.refuse.add("attempt")
        return piece

    def refused(self, piece: int, **kwargs: Any) -> moves.MoveError:
        with self.assertRaises(moves.MoveError) as caught:
            self.gate.move(piece, "review", **kwargs)
        return caught.exception

    def test_a_failed_attempt_is_logged_and_the_piece_stays_building(self) -> None:
        piece = self.building()
        self.loader.refusal_data["attempt"] = {"attempt": self.entry()}
        error = self.refused(piece)
        self.assertEqual(error.code, ExitCode.REFUSED)
        self.assertIn("logged in the piece record", error.message)
        self.assertIn("fix the attempt stub", error.next_command)
        record = evidence.read(self.paths, piece)
        self.assertEqual(attempt_log.attempts(record), [self.entry()])
        self.assertEqual(self.gate.piece(piece).state, "building")
        self.assertIn("state:building", self.labels(piece))

    def test_each_failed_attempt_adds_one_entry(self) -> None:
        piece = self.building()
        for number in (1, 2):
            self.loader.refusal_data["attempt"] = {"attempt": self.entry(number)}
            self.refused(piece)
        self.assertEqual([a["n"] for a in attempt_log.attempts(evidence.read(self.paths, piece))],
                         [1, 2])

    def test_a_dry_run_logs_nothing(self) -> None:
        piece = self.building()
        self.loader.refusal_data["attempt"] = {"attempt": self.entry(),
                                               "send_back": "the attempts ran out"}
        before = evidence.read(self.paths, piece)
        error = self.refused(piece, dry_run=True)
        self.assertIn("move 6", error.message)
        self.assertEqual(evidence.read(self.paths, piece), before)
        self.assertEqual(self.gate.piece(piece).state, "building")

    def test_a_refusal_with_no_attempt_data_logs_nothing(self) -> None:
        piece = self.building()
        before = evidence.read(self.paths, piece)
        self.refused(piece)
        self.assertEqual(evidence.read(self.paths, piece), before)

    def test_with_no_attempt_left_the_piece_goes_back_to_shaping_by_move_6(self) -> None:
        piece = self.building()
        reason = "The attempts ran out: 3 of 3 failed. attempt 1 (fault 1) | attempt 3 (fault 3)"
        self.loader.refusal_data["attempt"] = {"attempt": self.entry(3), "send_back": reason}
        error = self.refused(piece)
        self.assertEqual(error.data, {"sent_back": True})
        self.assertIn("move 6", error.message)
        self.assertIn("gate.py move", error.next_command)
        self.assertEqual(self.gate.piece(piece).state, "shaping")
        record = evidence.read(self.paths, piece)
        move = [e for e in record if e["kind"] == "move"][-1]
        self.assertEqual((move["move"], move["from"], move["to"]), (6, "building", "shaping"))
        self.assertEqual(move["reason"], reason)
        kinds = [e["kind"] for e in record]
        self.assertLess(kinds.index("attempt"), len(kinds) - 1 - kinds[::-1].index("move"))
        issue = self.hub.issues[self.gate.piece(piece).issue]
        self.assertTrue(any(reason in c for c in issue["comments"]))
        self.assertIn(reason, issue["body"], "the reason is a new open question in the spec")

    def test_the_attempt_is_kept_when_the_send_back_is_refused(self) -> None:
        piece = self.building()
        reason = "The attempts ran out, and the findings are the same as before."
        self.loader.refusal_data["attempt"] = {"attempt": self.entry(3), "send_back": reason}
        self.refused(piece)
        self.walk(piece, "building")
        self.loader.refuse.add("attempt")
        error = self.refused(piece)  # the same reason again: the anti-circle rule says no
        self.assertIn("could not", error.message)
        self.assertEqual(self.gate.piece(piece).state, "building")
        self.assertEqual(len(attempt_log.attempts(evidence.read(self.paths, piece))), 1,
                         "the attempts of the first round do not count in the second")
        self.assertEqual(len([e for e in evidence.read(self.paths, piece)
                              if e["kind"] == "attempt"]), 2)

    def test_a_pass_records_the_attempt_and_moves_to_review(self) -> None:
        piece = self.capture()
        self.walk(piece, "building")
        passing = attempt_log.entry(number=1, result="passed", head="a" * 40, base="b" * 40,
                                    at=TODAY)
        self.loader.data["attempt"] = {"entries": [passing]}
        result = self.gate.move(piece, "review")
        self.assertEqual((result["move"], result["to"]), (5, "review"))
        self.assertEqual(attempt_log.attempts(evidence.read(self.paths, piece)), [passing])

    def test_a_record_changed_between_the_reads_logs_nothing_and_says_so(self) -> None:
        piece = self.building()
        self.loader.refusal_data["attempt"] = {"attempt": self.entry()}
        def other_session(_ctx: CheckContext) -> None:
            evidence.append(self.paths, piece, [{"kind": "answer", "text": "another session"}])

        self.loader.during["attempt"] = other_session
        error = self.refused(piece)
        self.assertIn("another session", error.message)
        self.assertEqual(attempt_log.attempts(evidence.read(self.paths, piece)), [])


if __name__ == "__main__":
    unittest.main()
