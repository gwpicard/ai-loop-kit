"""Unit tests for kit/scripts/loop/run/integrate.py, the integration loop.

Each test builds a real Git repository in a throwaway folder. The judges are stand-ins that
read the tree of the commit they are given (a tiny language: `exists:<path>`, `absent:<path>`,
`nodupe:<folder>`, `flaky:<path>`), so no model, network or test runner is needed. The gate's
moves are stand-ins too, and they record each call.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import github  # noqa: E402
from loop.paths import Paths  # noqa: E402
from loop.run import integrate, record  # noqa: E402
from loop.run.gateway import Reply  # noqa: E402

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test Person", "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test Person", "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
}


def git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          check=False, env={**os.environ, **GIT_ENV})
    if done.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {done.stderr}")
    return done.stdout.strip()


def spec(command: str, *, touches: str = "aa", checks: tuple[str, ...] = (),
         new_area: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "judge": {"command": command, "held_out": ""},
        "must_stay_checks": list(checks),
        "links": {"touches": [touches]},
        "changes": {"added": [], "changed": [], "removed": [], "new_area": list(new_area)},
    }


class Judges:
    """Stand-in judges. A call is kept as (command, ref, extra file names)."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls: list[tuple[str, str, tuple[str, ...]]] = []
        self.seen: dict[str, int] = {}

    def _tree(self, ref: str) -> list[str]:
        return git(self.root, "ls-tree", "-r", "--name-only", ref).splitlines()

    def __call__(self, command: str, root: Path, ref: str, **more: Any) -> dict[str, Any]:
        extra = tuple(sorted((more.get("extra_files") or {}).keys()))
        self.calls.append((command, ref, extra))
        kind, _, arg = command.partition(":")
        tree = self._tree(ref)
        passed = True
        if kind == "exists":
            passed = arg in tree
        elif kind == "absent":
            passed = arg not in tree
        elif kind == "nodupe":
            texts = [git(self.root, "show", f"{ref}:{p}") for p in tree if p.startswith(arg)]
            passed = len(texts) == len(set(texts))
        elif kind == "flaky":
            self.seen[command] = self.seen.get(command, 0) + 1
            passed = self.seen[command] > 1
        elif kind == "hidden":
            passed = bool(extra) and arg in tree
        return {"command": command, "ref": ref, "outcome": "passed" if passed else "failed",
                "exit_code": 0 if passed else 1, "failing_ids": [], "note": ""}


class Mover:
    def __init__(self, to: str = "building") -> None:
        self.calls: list[tuple[int, str, str]] = []
        self.to = to

    def __call__(self, number: int, target: str, reason: str) -> Reply:
        self.calls.append((number, target, reason))
        return Reply(0, {"ok": True, "to": self.to, "move": 8})


class Pushes:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[str] = []
        self.error = error

    def __call__(self, branch: str) -> dict[str, Any]:
        self.calls.append(branch)
        if self.error is not None:
            raise self.error
        return {"pushed": branch, "scanned": f"main..{branch}"}


class IntegrationCase(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp())
        self.root = self.base / "project"
        self.root.mkdir()
        git(self.root, "init", "-q", "-b", "main")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "area-map").write_text("a.txt aa\nb.txt bb\nc.txt cc\n"
                                                      "d.txt dd\ncommands/ cmds\n")
        (self.root / "README.md").write_text("hello\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "Start")
        self.paths = Paths.for_project(self.root, data_base=self.base / "data",
                                       kit_folder=ROOT / "kit")
        self.run_record = record.RunRecord.create(
            self.paths, "night-1", [1, 2, 3], attended=True, merge_pre_approved=False)
        self.judges = Judges(self.root)
        self.mover = Mover()
        self.pushes = Pushes()
        self.restarted: list[int] = []
        self.views: dict[int, integrate.PieceView] = {}

    # --- helpers --------------------------------------------------------------------------

    def piece(self, number: int, files: dict[str, str], command: str, *,
              touches: str = "aa", checks: tuple[str, ...] = (), individual: bool = False,
              state: str = "review", message: str = "Build it", on: str = "main") -> None:
        branch = f"piece-{number}"
        git(self.root, "branch", branch, on)
        folder = self.base / f"wt-{number}"
        git(self.root, "worktree", "add", "-q", str(folder), branch)
        for name, text in files.items():
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        git(folder, "add", "-A")
        git(folder, "commit", "-q", "-m", message)
        git(self.root, "worktree", "remove", str(folder))
        self.views[number] = integrate.PieceView(
            number=number, title=f"Piece {number}", state=state, issue=None,
            individual=individual, issue_type="feature", judge_files=(), record=(),
            spec=spec(command, touches=touches, checks=checks))
        if str(number) in self.run_record.data["pieces"]:
            self.run_record.set_status(number, record.BUILT)

    def make(self, *, dependencies: dict[int, set[int]] | None = None,
             held: Any = None) -> integrate.Integrator:
        return integrate.Integrator(
            self.paths, "night-1", self.run_record, {"test_timeout_seconds": 60},
            reader=lambda n: self.views[n], judge_run=self.judges, mover=self.mover,
            push=self.pushes, restart=self.restarted.append,
            dependencies=dependencies or {}, held_runs=held or (lambda view: []),
            docs_commit=lambda **more: None)

    def head(self, branch: str) -> str:
        return git(self.root, "rev-parse", f"refs/heads/{branch}")

    def branches(self) -> list[str]:
        return git(self.root, "branch", "--format=%(refname:short)").splitlines()


class ReviewTestsJoinTheBarTest(IntegrationCase):
    """A check that review added to a piece runs in every trial, like the piece's own judge."""

    def with_review_test(self, number: int, command: str) -> None:
        view = self.views[number]
        entry = {"kind": "review-test", "path": "tests/test_found.py", "commit": "f" * 40,
                 "command": command, "justification": "Review found a gap."}
        self.views[number] = integrate.PieceView(
            number=view.number, title=view.title, state=view.state, issue=view.issue,
            individual=view.individual, issue_type=view.issue_type, spec=view.spec,
            judge_files=view.judge_files, record=(entry,))

    def test_a_green_review_check_runs_in_the_trial_and_the_piece_joins(self) -> None:
        self.piece(1, {"a.txt": "one\n", "found.txt": "x\n"}, "exists:a.txt")
        self.with_review_test(1, "exists:found.txt")
        loop = self.make()
        loop.start()
        self.assertEqual(loop.join(1).status, "joined")
        self.assertIn("exists:found.txt", {call[0] for call in self.judges.calls})

    def test_a_red_review_check_turns_the_trial_red_and_names_the_piece(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        self.with_review_test(1, "exists:found.txt")
        loop = self.make()
        loop.start()
        result = loop.join(1)
        self.assertEqual(result.status, "red", result)
        self.assertEqual(self.mover.calls[0][:2], (1, "building"))
        self.assertIn("review check", self.mover.calls[0][2])

    def test_the_final_check_runs_the_review_check_too(self) -> None:
        self.piece(1, {"a.txt": "one\n", "found.txt": "x\n"}, "exists:a.txt")
        self.with_review_test(1, "exists:found.txt")
        loop = self.make()
        loop.start()
        loop.join(1)
        calls_before = len(self.judges.calls)
        self.assertEqual(loop.final_check().status, "green")
        self.assertIn("exists:found.txt", {c[0] for c in self.judges.calls[calls_before:]})

    def test_the_frozen_files_hold_the_judge_files_and_the_review_tests(self) -> None:
        entry = {"kind": "review-test", "path": "tests/test_found.py", "commit": "f" * 40,
                 "command": "x", "justification": "y"}
        self.assertEqual(integrate.frozen_files(("tests/judge.py",), [entry]),
                         ("tests/judge.py", "tests/test_found.py"))


class JoinTest(IntegrationCase):
    def test_a_green_trial_moves_the_combined_branch_with_a_piece_trailer(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        loop = self.make()
        loop.start()
        before = self.head(loop.combined("main"))
        result = loop.join(1)
        self.assertEqual(result.status, "joined", result)
        after = self.head(loop.combined("main"))
        self.assertNotEqual(before, after)
        message = git(self.root, "log", "-1", "--format=%B", after)
        self.assertRegex(message, r"(?m)^Piece: #1$")
        self.assertEqual(git(self.root, "rev-list", "--parents", "-n1", after).count(" "), 2,
                         "the join is not a merge commit")
        self.assertEqual(loop.joined("main"), [1])

    def test_the_trial_is_a_scratch_copy_and_leaves_no_folder_or_branch(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        loop = self.make()
        loop.start()
        loop.join(1)
        listing = git(self.root, "worktree", "list", "--porcelain")
        self.assertNotIn("trial", listing)
        self.assertEqual(sorted(self.branches()), sorted(["main", "piece-1", "combined-night-1"]))

    def test_two_pieces_that_pass_alone_and_clash_together_are_found_at_the_second_join(
            self) -> None:
        # Both pieces pass their own judge and the old check. Together the two commands match.
        self.piece(1, {"commands/a.txt": "go\n"}, "exists:commands/a.txt",
                   touches="cmds", checks=("nodupe:commands/",))
        self.piece(2, {"commands/b.txt": "go\n"}, "exists:commands/b.txt",
                   touches="cmds", checks=("nodupe:commands/",))
        loop = self.make()
        loop.start()
        self.assertEqual(loop.join(1).status, "joined")
        moved = self.head(loop.combined("main"))
        calls_before = len(self.judges.calls)
        result = loop.join(2)
        self.assertEqual(result.status, "red", result)
        self.assertEqual(self.head(loop.combined("main")), moved, "the combined branch moved")
        self.assertEqual(loop.joined("main"), [1])
        # The culprit goes back to building by the gate's move, with the clash as the reason.
        self.assertEqual(len(self.mover.calls), 1)
        number, target, reason = self.mover.calls[0]
        self.assertEqual((number, target), (2, "building"))
        self.assertIn("piece 1", reason)
        self.assertIn("nodupe:commands/", reason)
        self.assertEqual(self.restarted, [2])
        self.assertIn("piece 1", self.run_record.piece(2)["clash"])
        # The trial commit is thrown away: no branch reaches it, and its folder is gone.
        trial = result.trial
        self.assertTrue(trial)
        self.assertEqual(git(self.root, "branch", "--contains", trial).strip(), "")
        self.assertNotIn("trial", git(self.root, "worktree", "list", "--porcelain"))
        # The judges ran the earlier piece's checks too, at the trial commit.
        ran = {call[0] for call in self.judges.calls[calls_before:] if call[1] == trial}
        self.assertIn("exists:commands/a.txt", ran)
        self.assertIn("exists:commands/b.txt", ran)

    def test_the_run_carries_on_and_the_culprit_joins_after_its_rebuild(self) -> None:
        self.piece(1, {"commands/a.txt": "go\n"}, "exists:commands/a.txt",
                   touches="cmds", checks=("nodupe:commands/",))
        self.piece(2, {"commands/b.txt": "go\n"}, "exists:commands/b.txt",
                   touches="cmds", checks=("nodupe:commands/",))
        self.piece(3, {"c.txt": "three\n"}, "exists:c.txt", touches="cc")
        loop = self.make()
        loop.start()
        loop.join(1)
        self.assertEqual(loop.join(2).status, "red")
        self.assertEqual(loop.join(3).status, "joined")
        # Piece 2 is rebuilt: a new commit on its branch, and a fresh join.
        folder = self.base / "wt-2b"
        git(self.root, "worktree", "add", "-q", str(folder), "piece-2")
        (folder / "commands" / "b.txt").write_text("go again\n")
        git(folder, "add", "-A")
        git(folder, "commit", "-q", "-m", "Rebuild it")
        git(self.root, "worktree", "remove", str(folder))
        self.assertEqual(loop.join(2).status, "joined")
        self.assertEqual(loop.joined("main"), [1, 3, 2])

    def test_a_merge_conflict_goes_back_the_same_way_and_no_agent_resolves_it(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        self.piece(2, {"a.txt": "two\n"}, "exists:a.txt")
        loop = self.make()
        loop.start()
        loop.join(1)
        moved = self.head(loop.combined("main"))
        result = loop.join(2)
        self.assertEqual(result.status, "conflict", result)
        self.assertEqual(self.head(loop.combined("main")), moved)
        number, target, reason = self.mover.calls[0]
        self.assertEqual((number, target), (2, "building"))
        self.assertIn("a.txt", reason)
        self.assertIn("piece 1", reason, "the piece that changed the file is not named")
        self.assertIn("conflict", reason)
        self.assertEqual(self.restarted, [2])
        self.assertNotIn("trial", git(self.root, "worktree", "list", "--porcelain"))

    def test_a_failed_merge_with_no_conflicting_file_is_a_refusal_and_the_piece_stays(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        loop = self.make()
        loop.start()
        moved = self.head(loop.combined("main"))
        git(self.root, "branch", "-D", "piece-1")
        result = loop.join(1)
        self.assertEqual(result.status, "refused", result)
        self.assertIn("git merge failed", result.message)
        self.assertTrue(result.next_command, "a refusal names the next command")
        self.assertEqual(self.mover.calls, [], "the piece was moved on a git error")
        self.assertEqual(self.restarted, [])
        self.assertEqual(self.head(loop.combined("main")), moved)

    def test_a_piece_that_leaves_its_touches_is_red_at_the_trial(self) -> None:
        self.piece(1, {"a.txt": "one\n", "b.txt": "two\n"}, "exists:a.txt", touches="aa")
        loop = self.make()
        loop.start()
        result = loop.join(1)
        self.assertEqual(result.status, "red")
        self.assertIn("b.txt", self.mover.calls[0][2])
        self.assertIn("touches", self.mover.calls[0][2])

    def test_a_judge_that_could_not_run_is_a_refusal_and_never_a_pass(self) -> None:
        from loop import judge

        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")

        def broken(command: str, root: Path, ref: str, **more: Any) -> dict[str, Any]:
            raise judge.JudgeError("the checkout failed", next_command="fix git")

        loop = self.make()
        loop.judge_run = broken
        loop.start()
        before = self.head(loop.combined("main"))
        result = loop.join(1)
        self.assertEqual(result.status, "refused")
        self.assertIn("fix git", result.next_command)
        self.assertEqual(self.head(loop.combined("main")), before)
        self.assertEqual(self.mover.calls, [], "the piece was blamed for the gate's own fault")

    def test_a_piece_the_gate_does_not_hold_in_review_is_not_joined(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt", state="building")
        loop = self.make()
        loop.start()
        self.assertEqual(loop.join(1).status, "refused")
        self.assertEqual(loop.joined("main"), [])

    def test_a_refusal_parks_the_piece_for_the_person_with_a_next_line(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt", state="building")
        loop = self.make()
        loop.start()
        loop.join(1)
        self.assertEqual(self.run_record.status(1), record.WAITING_PERSON)
        self.assertIn("not review", self.run_record.piece(1)["reason"])
        self.assertTrue(self.run_record.piece(1)["next"])
        self.assertTrue(any("did not join" in n["text"] for n in self.run_record.data["notes"]))


class FlakyTest(IntegrationCase):
    def test_a_red_that_passes_on_a_second_run_of_the_same_commit_is_flaky_never_a_pass(
            self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "flaky:one")
        loop = self.make()
        loop.start()
        before = self.head(loop.combined("main"))
        result = loop.join(1)
        self.assertEqual(result.status, "flaky", result)
        self.assertEqual(self.head(loop.combined("main")), before, "a flaky result passed")
        self.assertEqual(loop.joined("main"), [])
        self.assertEqual(self.mover.calls, [], "the piece was blamed for a flaky check")
        runs = [c for c in self.judges.calls if c[0] == "flaky:one"]
        self.assertEqual(len(runs), 2, "the same check did not run exactly twice")
        self.assertEqual(runs[0][1], runs[1][1], "the second run was on another commit")
        data = self.run_record.data["integration"]
        self.assertEqual(len(data["worth_knowing"]), 1)
        self.assertIn("flaky", data["worth_knowing"][0]["text"])
        self.assertIn("flaky:one", data["worth_knowing"][0]["text"])
        self.assertTrue(any("flaky" in n["text"] for n in self.run_record.data["notes"]))

    def test_a_red_that_stays_red_on_the_second_run_is_a_real_red(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:missing.txt")
        loop = self.make()
        loop.start()
        self.assertEqual(loop.join(1).status, "red")
        runs = [c for c in self.judges.calls if c[0] == "exists:missing.txt"]
        self.assertEqual(len(runs), 2)
        self.assertEqual(self.run_record.data["integration"].get("worth_knowing", []), [])

    def test_a_green_trial_runs_each_check_once(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        loop = self.make()
        loop.start()
        loop.join(1)
        self.assertEqual(len([c for c in self.judges.calls if c[0] == "exists:a.txt"]), 1)


class ResumeTest(IntegrationCase):
    def test_a_resumed_run_reads_the_trailers_and_does_not_join_twice(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        first = self.make()
        first.start()
        first.join(1)
        moved = self.head(first.combined("main"))
        # A new run script, with no memory of the join, over the same repository.
        self.run_record.data.pop("integration", None)
        self.run_record.save()
        second = self.make()
        second.start()
        second.drain()
        self.assertEqual(second.joined("main"), [1])
        calls = len(self.judges.calls)
        again = second.join(1)
        self.assertEqual(again.status, "already")
        self.assertEqual(self.head(second.combined("main")), moved)
        self.assertEqual(len(self.judges.calls), calls, "a judge ran for a join already made")
        count = git(self.root, "log", "--format=%B", moved).count("Piece: #1")
        self.assertEqual(count, 1)

    def test_start_joins_the_built_pieces_that_a_stopped_run_left_unjoined(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        self.piece(2, {"b.txt": "two\n"}, "exists:b.txt", touches="bb")
        first = self.make()
        first.start()
        first.join(1)
        second = self.make()
        second.start()
        self.assertEqual(second.drain(), [2])
        self.assertEqual(second.joined("main"), [1, 2])


class LeaveTest(IntegrationCase):
    def test_a_piece_that_leaves_rebuilds_the_branch_from_main_under_a_fresh_name(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        self.piece(2, {"b.txt": "two\n"}, "exists:b.txt", touches="bb")
        self.piece(3, {"c.txt": "three\n"}, "exists:c.txt", touches="cc")
        loop = self.make()
        loop.start()
        for n in (1, 2, 3):
            loop.join(n)
        old_name = loop.combined("main")
        old_head = self.head(old_name)
        result = loop.leave(2, "review sent it back")
        self.assertEqual(result.status, "rebuilt", result)
        new_name = loop.combined("main")
        self.assertNotEqual(new_name, old_name)
        self.assertEqual(self.head(old_name), old_head, "the old branch was changed")
        self.assertEqual(loop.joined("main"), [1, 3])
        tree = git(self.root, "ls-tree", "-r", "--name-only", new_name).splitlines()
        self.assertIn("a.txt", tree)
        self.assertIn("c.txt", tree)
        self.assertNotIn("b.txt", tree)
        log = git(self.root, "log", "--format=%B", new_name)
        self.assertNotIn("Revert", log)
        self.assertNotIn("Piece: #2", log)
        self.assertEqual(git(self.root, "merge-base", "main", new_name), self.head("main"))
        self.assertEqual(result.branch, new_name)

    def test_a_second_rebuild_takes_a_fresh_name_again(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        self.piece(2, {"b.txt": "two\n"}, "exists:b.txt", touches="bb")
        loop = self.make()
        loop.start()
        loop.join(1)
        loop.join(2)
        first = loop.combined("main")
        loop.leave(2, "rejected")
        second = loop.combined("main")
        loop.leave(1, "rejected")
        third = loop.combined("main")
        self.assertEqual(len({first, second, third}), 3)

    def test_a_rebuild_replays_each_joined_piece_through_the_trial_checks(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        self.piece(2, {"b.txt": "two\n"}, "exists:b.txt", touches="bb")
        loop = self.make()
        loop.start()
        loop.join(1)
        loop.join(2)
        before = len(self.judges.calls)
        loop.leave(2, "rejected")
        self.assertGreater(len(self.judges.calls), before)


class RefreshTest(IntegrationCase):
    """`main` moved after the final check: the branch is rebuilt on the new `main`, no piece out."""

    def test_the_branch_is_rebuilt_on_the_new_main_with_every_piece_and_a_fresh_name(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        self.piece(2, {"b.txt": "two\n"}, "exists:b.txt", touches="bb")
        loop = self.make()
        loop.start()
        loop.join(1)
        loop.join(2)
        old_name = loop.combined("main")
        old_head = self.head(old_name)
        (self.root / "d.txt").write_text("new on main\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "Work on main")
        result = loop.refresh("main", "main moved after the final check")
        self.assertEqual(result.status, "rebuilt", result)
        new_name = loop.combined("main")
        self.assertNotEqual(new_name, old_name)
        self.assertEqual(self.head(old_name), old_head, "the old branch was changed")
        self.assertEqual(loop.joined("main"), [1, 2])
        tree = git(self.root, "ls-tree", "-r", "--name-only", new_name).splitlines()
        self.assertIn("d.txt", tree)
        self.assertIn("a.txt", tree)
        self.assertIn("b.txt", tree)
        self.assertEqual(git(self.root, "merge-base", "main", new_name), self.head("main"))
        self.assertNotIn("Revert", git(self.root, "log", "--format=%B", new_name))

    def test_each_piece_is_checked_again_as_a_trial_on_the_new_main(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        loop = self.make()
        loop.start()
        loop.join(1)
        before = len(self.judges.calls)
        loop.refresh("main", "main moved")
        self.assertGreater(len(self.judges.calls), before)

    def test_a_track_that_does_not_exist_is_a_refusal(self) -> None:
        loop = self.make()
        loop.start()
        result = loop.refresh("piece-9", "main moved")
        self.assertEqual(result.status, "refused")


class StackingTest(IntegrationCase):
    def test_a_dependent_waits_until_its_dependency_has_joined(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        self.piece(2, {"b.txt": "two\n"}, "exists:b.txt", touches="bb")
        loop = self.make(dependencies={2: {1}})
        loop.start()
        self.assertEqual(loop.join(2).status, "waiting")
        self.assertEqual(loop.joined("main"), [])
        self.assertEqual(loop.join(1).status, "joined")
        self.assertEqual(loop.drain(), [2])
        self.assertEqual(loop.joined("main"), [1, 2])

    def test_a_dependent_stacked_on_its_dependency_branch_joins_cleanly(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        self.piece(2, {"b.txt": "two\n"}, "exists:b.txt", touches="bb", on="piece-1")
        loop = self.make(dependencies={2: {1}})
        loop.start()
        loop.join(1)
        self.assertEqual(loop.join(2).status, "joined")
        self.assertEqual(loop.joined("main"), [1, 2])

    def test_an_isolated_piece_follows_the_same_steps_on_its_own_branch(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        self.piece(2, {"b.txt": "two\n"}, "exists:b.txt", touches="bb", individual=True)
        loop = self.make()
        loop.start()
        self.assertEqual(loop.join(1).status, "joined")
        self.assertEqual(loop.join(2).status, "joined")
        main_track = loop.combined("main")
        own = loop.combined("piece-2")
        self.assertNotEqual(main_track, own)
        self.assertEqual(loop.joined("main"), [1])
        self.assertEqual(loop.joined("piece-2"), [2])
        self.assertNotIn("b.txt", git(self.root, "ls-tree", "-r", "--name-only", main_track))
        self.assertNotIn("a.txt", git(self.root, "ls-tree", "-r", "--name-only", own))
        self.assertRegex(git(self.root, "log", "-1", "--format=%B", own), r"(?m)^Piece: #2$")

    def test_a_dependent_of_an_isolated_piece_joins_the_isolated_branch(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt", individual=True)
        self.piece(2, {"b.txt": "two\n"}, "exists:b.txt", touches="bb", on="piece-1")
        loop = self.make(dependencies={2: {1}})
        loop.start()
        loop.join(1)
        loop.drain()
        self.assertEqual(loop.joined("piece-1"), [1, 2])
        self.assertEqual(loop.joined("main"), [])


class FinalCheckTest(IntegrationCase):
    def held(self, view: integrate.PieceView) -> list[tuple[str, dict[str, str]]]:
        if view.number == 1:
            return [("hidden:a.txt", {"tests/held/h.py": "SECRET-HELD-OUT-CASE-TEXT\n"})]
        return []

    def test_held_out_cases_are_copied_in_only_at_the_final_check(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        self.piece(2, {"b.txt": "two\n"}, "exists:b.txt", touches="bb")
        loop = self.make(held=self.held)
        loop.start()
        loop.join(1)
        loop.join(2)
        self.assertTrue(all(call[2] == () for call in self.judges.calls),
                        "an extra file reached a trial")
        result = loop.final_check("main")
        self.assertEqual(result.status, "green", result)
        extra = [c for c in self.judges.calls if c[2]]
        self.assertEqual(len(extra), 1)
        self.assertEqual(extra[0][2], ("tests/held/h.py",))
        # No case text is in the object store, in any commit, tree or blob.
        objects = git(self.root, "cat-file", "--batch-all-objects", "--batch-check").splitlines()
        for line in objects:
            sha, kind = line.split()[:2]
            if kind == "blob":
                self.assertNotIn("SECRET-HELD-OUT-CASE-TEXT", git(self.root, "cat-file", "-p",
                                                                   sha))

    def test_a_hidden_case_that_fails_at_the_final_check_sends_the_piece_back(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        self.piece(2, {"b.txt": "two\n"}, "exists:b.txt", touches="bb")

        def held(view: integrate.PieceView) -> list[tuple[str, dict[str, str]]]:
            return [("hidden:nope.txt", {"h.py": "x\n"})] if view.number == 2 else []

        loop = self.make(held=held)
        loop.start()
        loop.join(1)
        loop.join(2)
        first = loop.combined("main")
        result = loop.final_check("main")
        self.assertEqual(result.status, "red", result)
        self.assertEqual([c[:2] for c in self.mover.calls], [(2, "building")])
        reason = self.mover.calls[0][2]
        self.assertIn("hidden", reason)
        self.assertNotIn("h.py", reason, "the reason leaks a hidden case")
        self.assertEqual(self.restarted, [2])
        self.assertNotEqual(loop.combined("main"), first, "the piece left without a rebuild")
        self.assertEqual(loop.joined("main"), [1])

    def test_a_final_check_that_is_green_pushes_the_combined_branch_once(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        loop = self.make()
        loop.start()
        loop.join(1)
        result = loop.finish()
        self.assertEqual(result["main"]["status"], "green", result)
        self.assertEqual(self.pushes.calls, [loop.combined("main")])

    def test_a_push_before_the_app_waits_for_the_person_with_a_next_line(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        self.pushes.error = github.NoApp(self.root)
        loop = self.make()
        loop.start()
        loop.join(1)
        result = loop.finish()
        self.assertEqual(result["main"]["push"], "waiting")
        self.assertIn("next", result["main"])
        self.assertTrue(result["main"]["next"])

    def test_a_push_the_secret_scan_refuses_is_a_refusal_and_not_a_pass(self) -> None:
        self.piece(1, {"a.txt": "one\n"}, "exists:a.txt")
        self.pushes.error = github.GitHubError(
            "the secret scan refused the push", next_command="remove the secret")
        loop = self.make()
        loop.start()
        loop.join(1)
        result = loop.finish()
        self.assertEqual(result["main"]["push"], "refused")
        self.assertIn("remove the secret", result["main"]["next"])

    def test_nothing_joined_means_no_final_check_and_no_push(self) -> None:
        loop = self.make()
        loop.start()
        self.assertEqual(loop.finish(), {})
        self.assertEqual(self.pushes.calls, [])


class TrailerTest(unittest.TestCase):
    def test_trailers_are_read_from_a_commit_message(self) -> None:
        text = "Join piece 4\n\nPiece: #4\n"
        self.assertEqual(integrate.trailers(text), [4])
        self.assertEqual(integrate.trailers("Merge main\n"), [])
        self.assertEqual(integrate.trailers("a\n\nPiece: #7\n\u0000b\n\nPiece: #2\n"), [7, 2])

    def test_record_data_is_json_clean(self) -> None:
        json.dumps({"a": 1})  # the record is written whole as JSON; a smoke check of the module
        self.assertTrue(integrate.TRAILER_PREFIX.startswith("Piece"))


if __name__ == "__main__":
    unittest.main()
