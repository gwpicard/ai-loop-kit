"""Unit tests for the checks that review adds to the frozen bar.

A failing-check finding from review becomes a test file. The review loop commits that file
to the piece branch and sends the piece back by move 8, with the file, the commit, the
command and a written justification as options. The gate (`loop/gates/rebuild.py`) checks
them and writes a `review-test` entry in the piece record. From then on:

- `loop.bar` lists the file as frozen, so the builder's settings deny a write to it, and the
  gate's byte-for-byte check finds an edit or a delete;
- the attempt gate runs the file's command on every attempt, so the builder must make it pass.

The project is the one `test_attempt.py` builds: a real Git repository, a claimed piece on
its branch, and the judge as a stand-in.
"""

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_attempt  # type: ignore[import-not-found, unused-ignore]  # noqa: E402
from loop import bar, states  # noqa: E402
from loop.gates import CheckContext, CheckResult, rebuild  # noqa: E402

git = test_attempt.git
PATH = "billing/test_review_found.py"
TEXT = "from src.rename import rename\n\n\ndef test_review_found():\n    assert rename(' ') is None\n"
COMMAND = f"pytest {PATH}"


class ReviewStand(test_attempt.Stand):
    """The judge stand-in, with a verdict for the review command."""

    def __init__(self) -> None:
        super().__init__()
        self.review: dict[str, Any] = test_attempt.passed_run()

    def run_judge(self, command: str, root: Path, ref: str, **more: Any) -> dict[str, Any]:
        if command == COMMAND:
            self.runs.append((command, ref))
            return {**self.review, "command": command, "ref": ref}
        return super().run_judge(command, root, ref, **more)


class ReviewCase(test_attempt.AttemptCase):
    def setUp(self) -> None:
        super().setUp()
        self.att = ReviewStand()

    def add_review_test(self, text: str = TEXT) -> str:
        """What the review loop does: commit the file to the piece branch, then move 8."""
        self.honest()
        commit: str = self.attempt({PATH: text}, message="Add a check from review")
        self.record.append(self.entry(commit))
        return commit

    @staticmethod
    def entry(commit: str, **more: Any) -> dict[str, Any]:
        found: dict[str, Any] = {
            "kind": "review-test", "path": PATH, "commit": commit, "command": COMMAND,
            "justification": "The reviewer found that a blank name is not refused.",
        }
        found.update(more)
        return found

    def move_eight(self, reason: str = "Review found a gap.", **options: str) -> CheckResult:
        ctx = CheckContext(
            number=1, move=states.by_number(8), origin="review", target="building",
            reason=reason, title="t", body=self.body, spec=self.context().spec,
            record=self.record, paths=self.paths, options=options)
        return rebuild.check(ctx)


class TheBarListsTheReviewTests(ReviewCase):
    def test_the_files_are_read_from_the_record_in_order(self) -> None:
        commit = self.add_review_test()
        self.assertEqual(bar.review_files(self.record), {PATH: commit})
        self.assertEqual([e["path"] for e in bar.review_tests(self.record)], [PATH])

    def test_no_review_test_means_no_file(self) -> None:
        self.assertEqual(bar.review_files(self.record), {})

    def test_an_edit_of_the_file_is_a_change_to_the_bar(self) -> None:
        commit = self.add_review_test()
        head = self.attempt({PATH: TEXT.replace("is None", "is not None")})
        listed = bar.changes(self.root, self.first + "^", head, judge_commit=self.first,
                             judge_files=[test_ready_file()], review_files={PATH: commit})
        self.assertEqual([(c.kind, c.path) for c in listed], [("acceptance-check", PATH)])

    def test_a_delete_of_the_file_is_a_change_to_the_bar(self) -> None:
        commit = self.add_review_test()
        head = self.attempt({}, remove=(PATH,))
        listed = bar.changes(self.root, self.first + "^", head, judge_commit=self.first,
                             judge_files=[test_ready_file()], review_files={PATH: commit})
        self.assertEqual([(c.kind, c.path) for c in listed], [("acceptance-check", PATH)])

    def test_the_file_as_review_wrote_it_is_not_a_change(self) -> None:
        commit = self.add_review_test()
        head = git(self.root, "rev-parse", "piece-1")
        listed = bar.changes(self.root, self.first + "^", head, judge_commit=self.first,
                             judge_files=[test_ready_file()], review_files={PATH: commit})
        self.assertEqual(listed, [])


def test_ready_file() -> str:
    return test_attempt.test_ready.TEST_FILE  # type: ignore[no-any-return]


class TheAttemptGateHoldsTheReviewTests(ReviewCase):
    def test_an_intact_file_with_a_green_command_passes(self) -> None:
        head = self.add_review_test()
        self.passes()
        self.assertIn((COMMAND, head), self.att.runs)

    def test_the_file_is_not_charged_to_the_pieces_touches(self) -> None:
        """The path sits in the billing area, which the spec does not declare."""
        self.add_review_test()
        self.passes()

    def test_an_edited_file_fails_the_attempt_as_possible_gaming(self) -> None:
        self.add_review_test()
        self.attempt({PATH: TEXT.replace("is None", "is not None")})
        item = self.fails("frozen-bar", PATH, gaming=True)
        self.assertEqual(self.att.runs, [], "no judge runs against a bar that was changed")
        self.assertIn("review", " ".join(f["text"] for f in item["findings"]))

    def test_a_deleted_file_fails_the_attempt_as_possible_gaming(self) -> None:
        self.add_review_test()
        self.attempt({}, remove=(PATH,))
        self.fails("frozen-bar", PATH, gaming=True)

    def test_a_red_command_fails_the_attempt(self) -> None:
        self.add_review_test()
        self.att.review = test_attempt.test_ready.judge_result("failed", exit_code=1)
        self.fails("review-check", COMMAND, gaming=False)

    def test_a_command_that_cannot_run_is_a_refusal_that_counts_no_attempt(self) -> None:
        self.add_review_test()
        self.att.judge_error[COMMAND] = test_attempt.judge.JudgeError(
            "no runner", next_command="install it")
        self.refuses("review check", "could not be run")


class MoveEightWithAReviewTest(ReviewCase):
    def options(self, commit: str, **more: str) -> dict[str, str]:
        found = {"review_test_path": PATH, "review_test_commit": commit,
                 "review_test_command": COMMAND,
                 "review_justification": "A blank name is not refused, and the spec asks it."}
        found.update(more)
        return found

    def committed(self) -> str:
        self.honest()
        head: str = self.attempt({PATH: TEXT}, message="Add a check from review")
        return head

    def test_no_review_options_is_a_plain_move_back(self) -> None:
        self.assertTrue(self.move_eight().ok)

    def test_the_options_make_a_review_test_entry(self) -> None:
        commit = self.committed()
        result = self.move_eight(**self.options(commit))
        self.assertTrue(result.ok, result.failures)
        entry = result.data["entries"][0]
        self.assertEqual((entry["kind"], entry["path"], entry["commit"], entry["command"]),
                         ("review-test", PATH, commit, COMMAND))
        self.assertIn("blank name", entry["justification"])

    def test_a_partial_set_of_options_is_refused(self) -> None:
        commit = self.committed()
        options = self.options(commit)
        del options["review_test_command"]
        result = self.move_eight(**options)
        self.assertFalse(result.ok)
        self.assertIn("review_test_command", " ".join(result.failures))
        self.assertTrue(result.next_command)

    def test_a_commit_that_is_not_on_the_piece_branch_is_refused(self) -> None:
        self.committed()
        other = git(self.root, "rev-parse", "main")
        result = self.move_eight(**self.options(other))
        self.assertFalse(result.ok)
        self.assertIn("not on the piece branch", " ".join(result.failures))

    def test_a_commit_that_does_not_hold_the_file_is_refused(self) -> None:
        self.committed()
        result = self.move_eight(**self.options(self.first))
        self.assertFalse(result.ok)
        self.assertIn(PATH, " ".join(result.failures))

    def test_a_path_that_is_not_a_test_is_refused(self) -> None:
        commit = self.committed()
        for bad in ("src/rename.py", "/etc/test_x.py", "../test_x.py", "tests/*.py"):
            result = self.move_eight(**self.options(commit, review_test_path=bad))
            self.assertFalse(result.ok, bad)

    def test_a_command_that_does_not_name_the_file_is_refused(self) -> None:
        commit = self.committed()
        result = self.move_eight(**self.options(commit, review_test_command="pytest tests"))
        self.assertFalse(result.ok)
        self.assertIn("names the file", " ".join(result.failures))

    def test_a_blank_justification_is_refused(self) -> None:
        commit = self.committed()
        result = self.move_eight(**self.options(commit, review_justification="  "))
        self.assertFalse(result.ok)
        self.assertIn("justification", " ".join(result.failures))

    def test_a_file_that_is_already_frozen_is_refused(self) -> None:
        commit = self.committed()
        self.record.append(self.entry(commit))
        result = self.move_eight(**self.options(commit))
        self.assertFalse(result.ok)
        self.assertIn("already", " ".join(result.failures))


if __name__ == "__main__":
    unittest.main()
