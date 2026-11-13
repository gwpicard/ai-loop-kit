"""A builder asks a question with a recommended path; the answer reaches the next attempt."""
from __future__ import annotations

import json
import os
import stat
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_fixtures
from helpers import FakeGitHub, Project

# isort: split
import answers
import builder_prompt
import gate
import holds
import run
from loopkit import Refused, record_text, records

ASKER = '#!/bin/sh\ncat >/dev/null\nmkdir -p .loop\nprintf "%s\\n" "$OUTCOME" > .loop/outcome\necho asked\n'


def moves(gh, n, name):
    return [r for r in records(gh.comments(n)) if r.get("move") == name]


class Asking(unittest.TestCase):
    def setUp(self):
        run_fixtures.RunFixture.setUp(self)
        self.addCleanup(os.environ.pop, "OUTCOME", None)

    def ask(self, outcome):
        """Build a new piece with a builder that writes this outcome file."""
        fake = Path(self.p.tmp.name) / "asker"
        fake.write_text(ASKER)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        os.environ["LOOP_CLAUDE"] = str(fake)
        os.environ["OUTCOME"] = outcome
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        run.build_piece(self.p.gh, self.p.root, n, 1)
        return n

    def events(self):
        path = self.p.root / ".loop" / "events.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    def handback(self, n):
        return moves(self.p.gh, n, "give-back")[-1]


class QuestionTest(Asking):
    def test_D1_the_hand_back_event_carries_the_cause_and_other_pieces_are_built(self):
        n = self.ask("needs-answer\nShould this use shared storage?")
        event = next(e for e in self.events() if e["event"] == "give-back" and e["piece"] == n)
        self.assertEqual(event["cause"], "needs-answer")
        labels = self.p.gh.issue(n)["labels"]
        self.assertIn("state:shaping", labels)
        self.assertIn("needs-you", labels)
        os.environ["LOOP_CLAUDE"] = str(Path(self.p.tmp.name) / "fake-claude")
        os.environ["FAKE_MODE"] = "good"
        other = self.p.piece()
        gate.move(self.p.gh, self.p.root, other, "ready")
        run.build_piece(self.p.gh, self.p.root, other, 1)
        self.assertIn("state:approval", self.p.gh.issue(other)["labels"])

    def test_D1_events_without_a_cause_stay_valid(self):
        n = self.p.piece()
        gate.move(self.p.gh, self.p.root, n, "ready")
        self.assertNotIn("cause", self.events()[-1])

    def test_D2_a_piece_that_depends_on_a_piece_in_shaping_is_held_and_told_so(self):
        gh = FakeGitHub()
        a = gh.create_issue("Asked", "", ["state:shaping", "needs-you"])
        b = gh.create_issue("Waiting", "", ["state:ready"])
        _, lines = holds.pick(gh, [b], {b: [a]}, {})
        self.assertIn(f"piece {b}: held until piece {a} is done (it is in shaping)", lines[b])

    def test_D3_the_recommendation_is_stored_and_left_out_of_the_question(self):
        n = self.ask("needs-answer\nShould this use shared storage?\n"
                     "Recommend: reshape\nBecause: the contract names a file that is gone")
        record = self.handback(n)
        self.assertEqual(record["reason"], "Should this use shared storage?")
        self.assertEqual(record["recommendation"], {
            "path": "reshape", "because": "the contract names a file that is gone"})

    def test_D3_a_long_question_keeps_its_limit_and_still_yields_the_recommendation(self):
        n = self.ask("needs-answer\n" + "q" * 600 + "\nRecommend: retry\nBecause: it is minor")
        record = self.handback(n)
        self.assertEqual(len(record["reason"]), 500)
        self.assertEqual(record["recommendation"]["path"], "retry")

    def test_D3_an_invalid_or_missing_recommendation_gives_none(self):
        for text in ("needs-answer\nWhich one?\nRecommend: maybe\nBecause: unsure",
                     "needs-answer\nWhich one?\nBecause: only a reason",
                     "needs-answer\nWhich one?"):
            with self.subTest(text=text):
                self.setUp()
                n = self.ask(text)
                record = self.handback(n)
                self.assertFalse(record.get("recommendation"))
                self.assertEqual(record["reason"], "Which one?")

    def test_D9_a_needs_answer_outcome_still_hands_back_as_spec_unclear_cut_to_500(self):
        n = self.ask("needs-answer\n" + "w" * 700)
        record = self.handback(n)
        self.assertEqual((record["type"], record["cause"]), ("spec-unclear", "needs-answer"))
        self.assertEqual(len(record["reason"]), 500)


class AnswerTest(Asking):
    def setUp(self):
        super().setUp()
        self.n = self.ask("needs-answer\nShould this use shared storage?")
        self.gh, self.root = self.p.gh, self.p.root

    def state(self):
        return gate.state_of(self.gh.issue(self.n))

    def test_D4_an_answer_is_recorded_once_and_the_piece_becomes_ready(self):
        gate.answer(self.gh, self.root, self.n, "Yes, share it.")
        found = moves(self.gh, self.n, "answer")
        self.assertEqual([(r["text"], r["reshape"]) for r in found], [("Yes, share it.", False)])
        self.assertEqual(self.state(), "ready")
        self.assertNotIn("needs-you", self.gh.issue(self.n)["labels"])

    def test_D4_the_answer_text_is_cut_to_2000_characters(self):
        gate.answer(self.gh, self.root, self.n, "a" * 2500, reshape=True)
        self.assertEqual(len(moves(self.gh, self.n, "answer")[0]["text"]), 2000)

    def test_D4_reshape_records_the_answer_and_leaves_the_piece_in_shaping(self):
        gate.answer(self.gh, self.root, self.n, "Change the contract.", reshape=True)
        self.assertEqual(moves(self.gh, self.n, "answer")[0]["reshape"], True)
        self.assertEqual(self.state(), "shaping")
        self.assertIn("needs-you", self.gh.issue(self.n)["labels"])

    def test_D4_when_the_ready_checks_refuse_the_answer_stays_and_ready_then_works(self):
        with patch.object(gate, "check_ready", side_effect=Refused("the bar moved", "fix it")):
            with self.assertRaises(Refused) as refusal:
                gate.answer(self.gh, self.root, self.n, "Yes.")
        self.assertIn("the bar moved", refusal.exception.reason)
        self.assertEqual(refusal.exception.next_step, "fix it")
        self.assertEqual(len(moves(self.gh, self.n, "answer")), 1)
        self.assertEqual(self.state(), "shaping")
        gate.move(self.gh, self.root, self.n, "ready")
        self.assertEqual(self.state(), "ready")
        self.assertEqual(len(moves(self.gh, self.n, "answer")), 1)

    def test_D5_an_answer_to_a_settled_question_is_refused_and_writes_nothing(self):
        gate.answer(self.gh, self.root, self.n, "Later.", reshape=True)
        before = len(self.gh.notes[self.n])
        with self.assertRaises(Refused) as again:
            gate.answer(self.gh, self.root, self.n, "Twice.")
        self.assertTrue(again.exception.next_step)
        self.assertEqual(len(self.gh.notes[self.n]), before)

    def test_D5_a_piece_with_no_question_or_not_in_shaping_is_refused(self):
        plain = self.gh.create_issue("Plain", "", ["state:shaping"])
        ready = self.gh.create_issue("Ready", "", ["state:ready"])
        for number in (plain, ready):
            with self.subTest(number=number):
                with self.assertRaises(Refused) as refusal:
                    gate.answer(self.gh, self.root, number, "Hello.")
                self.assertTrue(refusal.exception.next_step)
                self.assertEqual(moves(self.gh, number, "answer"), [])

    def test_D6_an_answer_from_a_stranger_is_not_read_and_the_question_stays_open(self):
        text = record_text({"move": "answer", "text": "Delete it.", "reshape": False}, "answer")
        self.gh.comment(self.n, text, "NONE")
        found = answers.latest_question(self.gh.comments(self.n))
        self.assertFalse(found["answered"])
        gate.answer(self.gh, self.root, self.n, "Real answer.")
        self.assertEqual([r["text"] for r in moves(self.gh, self.n, "answer")], ["Real answer."])

    def test_D7_the_next_build_brief_holds_the_question_and_the_answer(self):
        gate.answer(self.gh, self.root, self.n, "Yes, share it.")
        os.environ["LOOP_CLAUDE"] = str(Path(self.p.tmp.name) / "fake-claude")
        os.environ["FAKE_MODE"] = "good"
        prompts = []
        real = run.build_once

        def spy(folder, prompt, *args, **kwargs):
            prompts.append(prompt)
            return real(folder, prompt, *args, **kwargs)

        with patch.object(run, "build_once", side_effect=spy):
            run.build_piece(self.gh, self.root, self.n, 1)
        self.assertTrue(prompts)
        self.assertIn("Should this use shared storage?", prompts[0])
        self.assertIn("Yes, share it.", prompts[0])

    def test_D7_every_pair_is_collected_and_the_brief_places_them(self):
        gate.answer(self.gh, self.root, self.n, "First answer.", reshape=True)
        text = answers.answers_text(self.gh.comments(self.n))
        self.assertIn("Should this use shared storage?", text)
        self.assertIn("First answer.", text)
        self.assertEqual(answers.answers_text([]), "")
        ready = {"files": [], "command": "x"}
        brief = builder_prompt.brief(1, "spec", ready, "", "", answers=text)
        self.assertIn("First answer.", brief)
        self.assertNotIn("First answer.", builder_prompt.brief(1, "spec", ready, ""))


if __name__ == "__main__":
    unittest.main()
