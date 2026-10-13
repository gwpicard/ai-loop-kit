"""Unit tests for what the integration loop needs from the run engine (P21's engine.py).

The hook context carries the gate lock, a way to start a built piece's builder again, and the
pieces' links. A dependent is stacked on its dependency's branch with merge commits, and move 5
is told where the stack ends. The clash that sent a piece back reaches its next builder's brief.
The engine is built without its threads: each test sets only the fields its method reads.
"""

import os
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import sessions  # noqa: E402
from loop.gates import CheckContext, attempt  # noqa: E402
from loop.paths import Paths  # noqa: E402
from loop.run import engine, plan, record  # noqa: E402
from loop.run.gateway import Gateway  # noqa: E402

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


class EngineCase(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp())
        self.root = self.base / "project"
        self.root.mkdir()
        git(self.root, "init", "-q", "-b", "main")
        (self.root / "README.md").write_text("hello\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "Start")
        self.paths = Paths.for_project(self.root, data_base=self.base / "data",
                                       kit_folder=ROOT / "kit")
        self.rec = record.RunRecord.create(self.paths, "night-1", [1, 2], attended=True,
                                           merge_pre_approved=False)

    def make(self, infos: list[plan.PieceInfo] | None = None) -> engine.Engine:
        made = engine.Engine.__new__(engine.Engine)
        made.paths, made.name, made.record, made.policy = self.paths, "night-1", self.rec, {}
        made.gate_lock = threading.RLock()
        made.wake = threading.Event()
        made.resume_queue = []
        made.infos = {i.number: i for i in infos or []}
        made.gateway = Gateway(self.paths)
        made._start = sessions.start
        return made


class HookContextTest(EngineCase):
    def test_the_context_carries_the_lock_the_restart_and_the_links(self) -> None:
        infos = [plan.PieceInfo(1, issue=11), plan.PieceInfo(2, issue=12,
                                                            blockers=frozenset({11}))]
        loop = self.make(infos)
        context = loop.context()
        self.assertIs(context.gate_lock, loop.gate_lock)
        self.assertEqual(context.restart_piece, loop.restart_piece)
        self.assertEqual(sorted(context.infos), [1, 2])
        self.assertEqual(context.infos[2].blockers, frozenset({11}))

    def test_a_context_made_by_hand_still_works_without_the_new_fields(self) -> None:
        context = engine.HookContext(self.paths, "night-1", self.rec, {}, lambda n: None)
        context.restart_piece(1)  # a default that does nothing
        self.assertEqual(dict(context.infos), {})


class ReviewNeedsTest(EngineCase):
    """What the review loop (P24) needs from the engine, and no more."""

    def test_the_context_carries_the_session_starter_and_the_round_request(self) -> None:
        loop = self.make()
        context = loop.context()
        self.assertEqual(context.start_session, loop._start)
        context.another_round()
        self.assertTrue(loop.another_round)

    def test_a_context_made_by_hand_starts_sessions_the_plain_way(self) -> None:
        context = engine.HookContext(self.paths, "night-1", self.rec, {}, lambda n: None)
        self.assertIs(context.start_session, sessions.start)
        context.another_round()  # a default that does nothing

    def test_the_finding_that_sent_a_piece_back_reaches_the_next_builder(self) -> None:
        loop = self.make()
        self.rec.update(1, review_finding="A blank name is not refused.")
        text = loop._found_so_far(1, [])
        self.assertIn("A blank name is not refused.", text)
        self.assertIn("review", text.lower())
        self.assertNotIn("trial join", text)


class RestartTest(EngineCase):
    def test_a_built_piece_is_built_again_by_the_next_free_slot(self) -> None:
        self.rec.set_status(1, record.BUILT)
        loop = self.make()
        loop.restart_piece(1)
        self.assertEqual(self.rec.status(1), record.BUILDING)
        self.assertEqual(loop.resume_queue, [1])
        self.assertTrue(loop.wake.is_set())

    def test_a_piece_that_is_not_built_is_left_alone(self) -> None:
        self.rec.set_status(1, record.PENDING)
        loop = self.make()
        loop.restart_piece(1)
        self.assertEqual(self.rec.status(1), record.PENDING)
        self.assertEqual(loop.resume_queue, [])

    def test_a_piece_is_not_queued_twice(self) -> None:
        self.rec.set_status(1, record.BUILT)
        loop = self.make()
        loop.restart_piece(1)
        loop.restart_piece(1)
        self.assertEqual(loop.resume_queue, [1])


class ClashTest(EngineCase):
    def test_the_clash_is_added_to_what_earlier_attempts_found(self) -> None:
        loop = self.make()
        self.assertEqual(loop._found_so_far(1, []), "No attempt has been judged yet.")
        self.rec.update(1, clash="Piece 1 clashed with piece 2.")
        text = loop._found_so_far(1, [])
        self.assertIn("No attempt has been judged yet.", text)
        self.assertIn("Piece 1 clashed with piece 2.", text)
        self.assertIn("trial join", text)


class StackTest(EngineCase):
    def piece(self, number: int, files: dict[str, str], on: str = "main") -> Path:
        git(self.root, "branch", f"piece-{number}", on)
        folder = self.base / f"wt-{number}"
        git(self.root, "worktree", "add", "-q", str(folder), f"piece-{number}")
        for name, text in files.items():
            (folder / name).write_text(text)
        git(folder, "add", "-A")
        git(folder, "commit", "-q", "-m", f"Build {number}")
        return folder

    def test_a_dependent_is_stacked_on_each_dependency_branch_with_a_merge(self) -> None:
        self.piece(1, {"a.txt": "one\n"})
        folder = self.piece(2, {"b.txt": "two\n"})
        loop = self.make()
        code, text, sha = loop.gateway.stack(folder, [1])
        self.assertEqual(code, 0, text)
        self.assertEqual(sha, git(folder, "rev-parse", "HEAD"))
        self.assertEqual(git(folder, "log", "-1", "--format=%s"), "Stack on piece 1")
        self.assertTrue((folder / "a.txt").exists(), "the dependency's work is not in the folder")
        self.assertEqual(git(folder, "rev-list", "--parents", "-n1", "HEAD").count(" "), 2)

    def test_stacking_twice_makes_no_second_merge_and_reports_no_new_base(self) -> None:
        self.piece(1, {"a.txt": "one\n"})
        folder = self.piece(2, {"b.txt": "two\n"})
        loop = self.make()
        first = loop.gateway.stack(folder, [1])
        (folder / "c.txt").write_text("three\n")
        git(folder, "add", "-A")
        git(folder, "commit", "-q", "-m", "More work")
        second = loop.gateway.stack(folder, [1])
        self.assertEqual(second[0], 0)
        self.assertEqual(second[2], "", "the gateway made no merge, so it names no base")
        self.assertTrue(first[2])

    def test_a_conflict_stops_the_stack_and_leaves_the_folder_as_it_was(self) -> None:
        self.piece(1, {"a.txt": "one\n"})
        folder = self.piece(2, {"a.txt": "two\n"})
        before = git(folder, "rev-parse", "HEAD")
        code, text, sha = self.make().gateway.stack(folder, [1])
        self.assertNotEqual(code, 0)
        self.assertIn("a.txt", text)
        self.assertEqual(sha, "")
        self.assertEqual(git(folder, "rev-parse", "HEAD"), before)
        self.assertEqual(git(folder, "status", "--porcelain"), "")

    def test_the_dependencies_of_a_piece_are_the_built_pieces_its_blockers_name(self) -> None:
        infos = [plan.PieceInfo(1, issue=11), plan.PieceInfo(2, issue=12,
                                                            blockers=frozenset({11, 99}))]
        loop = self.make(infos)
        self.rec.set_status(1, record.BUILT)
        self.assertEqual(loop._stack_pieces(2), [1])
        self.rec.set_status(1, record.PENDING)
        self.assertEqual(loop._stack_pieces(2), [], "a dependency that is not built is skipped")
        self.assertEqual(loop._stack_pieces(1), [])

    def test_move_5_is_told_where_the_stack_ends_and_what_it_was_stacked_on(self) -> None:
        loop = self.make()
        self.assertEqual(loop._move_options(1), None)
        self.rec.update(1, stack_base="abc123", stacked_on=[3, 4])
        self.assertEqual(loop._move_options(1),
                         {"stack_base": "abc123", "stacked_on": "3,4"})

    def stackable(self) -> tuple[engine.Engine, Path]:
        infos = [plan.PieceInfo(1, issue=11), plan.PieceInfo(2, issue=12,
                                                            blockers=frozenset({11}))]
        self.piece(1, {"a.txt": "one\n"})
        folder = self.piece(2, {"b.txt": "two\n"})
        self.rec.set_status(1, record.BUILT)
        return self.make(infos), folder

    def test_the_base_is_the_merge_the_gateway_just_made(self) -> None:
        loop, folder = self.stackable()
        loop._stack(2, folder)
        held = self.rec.piece(2)
        self.assertEqual(held["stack_base"], git(folder, "rev-parse", "HEAD"))
        self.assertEqual(held["stacked_on"], [1])

    def test_a_stacking_merge_the_builder_made_is_never_taken_as_the_base(self) -> None:
        """A merge with the right subject, made by the builder, after the piece's own work."""
        loop, folder = self.stackable()
        git(folder, "merge", "-q", "--no-ff", "-m", "Stack on piece 1", "piece-1")
        loop._stack(2, folder)
        self.assertNotIn("stack_base", self.rec.piece(2))

    def test_a_recorded_base_stays_when_the_gateway_made_no_merge(self) -> None:
        loop, folder = self.stackable()
        loop._stack(2, folder)
        recorded = self.rec.piece(2)["stack_base"]
        (folder / "c.txt").write_text("three\n")
        git(folder, "add", "-A")
        git(folder, "commit", "-q", "-m", "More work")
        loop._stack(2, folder)
        self.assertEqual(self.rec.piece(2)["stack_base"], recorded)

    def test_a_recorded_base_is_not_replaced_by_a_commit_that_does_not_descend_from_it(
            self) -> None:
        loop, folder = self.stackable()
        loop._stack(2, folder)
        recorded = self.rec.piece(2)["stack_base"]
        stranger = git(self.root, "rev-parse", "main")
        setattr(loop.gateway, "stack", lambda *_a, **_k: (0, "stacked", stranger))  # noqa: B010
        loop._stack(2, folder)
        self.assertEqual(self.rec.piece(2)["stack_base"], recorded)


class DependencyMovedTest(EngineCase):
    """A dependency that moves after the dependent was stacked: the dependent is given back
    (gate move 7), then built again. Its own commit sits before any new stacking merge, so the
    run cuts a fresh branch for it at the judge commit and keeps the old one under another name.
    """

    def open_worktree(self, name: str, branch: str, base: str, *, resume: bool
                      ) -> tuple[int, str]:
        folder = self.paths.worktrees_dir / name
        if not folder.exists():
            folder.parent.mkdir(parents=True, exist_ok=True)
            git(self.root, "worktree", "add", "-q", str(folder), branch)
        return 0, ""

    def commit(self, folder: Path, name: str) -> None:
        (folder / name).write_text(name + "\n")
        git(folder, "add", "-A")
        git(folder, "commit", "-q", "-m", f"Add {name}")

    def setup_pair(self) -> tuple[engine.Engine, str]:
        infos = [plan.PieceInfo(1, issue=11),
                 plan.PieceInfo(2, issue=12, blockers=frozenset({11}))]
        git(self.root, "branch", "piece-1", "main")
        self.dep = self.base / "wt-dep"
        git(self.root, "worktree", "add", "-q", str(self.dep), "piece-1")
        self.commit(self.dep, "a.txt")
        git(self.root, "branch", "piece-2", "main")
        first = self.base / "wt-first"
        git(self.root, "worktree", "add", "-q", str(first), "piece-2")
        self.commit(first, "judge.txt")
        judge = git(first, "rev-parse", "HEAD")
        git(self.root, "worktree", "remove", str(first))
        self.rec.set_status(1, record.BUILT)
        self.rec.update(2, branch="piece-2", worktree="wt-2")
        loop = self.make(infos)
        loop.gateway.open_worktree = self.open_worktree  # type: ignore[method-assign]
        setattr(loop, "_read", lambda _n: types.SimpleNamespace(  # noqa: B010
            fingerprint_data={"judge_commit": judge}))
        return loop, judge

    def test_a_rebuild_after_the_dependency_moved_passes_the_stack_check(self) -> None:
        loop, judge = self.setup_pair()
        folder = loop._worktree(2)
        old_base = self.rec.piece(2)["stack_base"]
        self.commit(folder, "own.txt")
        self.commit(self.dep, "b.txt")  # the dependency moves after the stack
        # The gate sent the piece back (move 7); the run builds it again.
        folder = loop._worktree(2)
        held = self.rec.piece(2)
        new_base = held["stack_base"]
        self.assertNotEqual(new_base, old_base)
        self.assertEqual(git(folder, "rev-parse", "HEAD"), new_base)
        self.assertEqual(git(self.root, "rev-parse", "piece-2"), new_base)
        self.assertTrue((folder / "a.txt").exists() and (folder / "b.txt").exists())
        self.assertFalse((folder / "own.txt").exists(), "the new branch starts afresh")
        # The gate's own stack check accepts the new base.
        ctx = CheckContext(number=2, move=None, origin="building",  # type: ignore[arg-type]
                           target="review", reason=None, title="", body="", spec=None,
                           record=[], paths=self.paths, options={"stacked_on": "1"})
        attempt._stack_is_clean(ctx, self.root, "again", git(self.root, "rev-parse", judge + "^"),
                                new_base, judge)

    def test_the_old_branch_and_its_own_commit_are_kept_under_another_name(self) -> None:
        loop, _judge = self.setup_pair()
        folder = loop._worktree(2)
        self.commit(folder, "own.txt")
        kept = git(self.root, "rev-parse", "piece-2")
        self.commit(self.dep, "b.txt")
        loop._worktree(2)
        names = git(self.root, "branch", "--list", "piece-2-*", "--format=%(refname:short)")
        self.assertEqual(len(names.splitlines()), 1, names)
        self.assertEqual(git(self.root, "rev-parse", names.strip()), kept)

    def test_a_dependency_that_did_not_move_leaves_the_branch_alone(self) -> None:
        loop, _judge = self.setup_pair()
        folder = loop._worktree(2)
        self.commit(folder, "own.txt")
        before = git(self.root, "rev-parse", "piece-2")
        loop._worktree(2)
        self.assertEqual(git(self.root, "rev-parse", "piece-2"), before)
        self.assertEqual(git(self.root, "branch", "--list", "piece-2-*"), "")


class BuiltAllRoundsTest(EngineCase):
    """A hook that sends a piece back at `built-all` gets another round of building."""

    def finish_with(self, queued_by_hook: list[list[int]]) -> tuple[engine.Engine, list[str]]:
        for number in (1, 2):
            self.rec.set_status(number, record.BUILT)
        loop = self.make()
        loop.stop = threading.Event()
        loop.run_parked = ""
        loop.failed = False
        loop.refused = {}
        calls: list[str] = []
        rounds: list[int] = []
        batches = list(queued_by_hook)

        def hook(event: str, **data: object) -> None:
            calls.append(event)
            if event == "built-all" and batches:
                loop.resume_queue.extend(batches.pop(0))

        def again() -> None:
            rounds.append(1)
            loop.resume_queue.clear()

        loop.hook = hook  # type: ignore[method-assign]
        loop._rounds = again  # type: ignore[method-assign]
        loop.cap_run = None
        loop._finish()
        calls.append(f"rounds={len(rounds)}")
        return loop, calls

    def test_with_nothing_sent_back_built_all_is_called_once(self) -> None:
        _, calls = self.finish_with([])
        self.assertEqual(calls, ["built-all", "run-end", "rounds=0"])

    def test_a_piece_sent_back_is_built_and_built_all_is_called_again(self) -> None:
        _, calls = self.finish_with([[2]])
        self.assertEqual(calls, ["built-all", "built-all", "run-end", "rounds=1"])

    def test_a_hook_that_asks_for_another_round_gets_one_with_nothing_queued(self) -> None:
        for number in (1, 2):
            self.rec.set_status(number, record.BUILT)
        loop = self.make()
        loop.stop = threading.Event()
        loop.run_parked = ""
        loop.failed = False
        loop.refused = {}
        loop.cap_run = None
        calls: list[str] = []
        asked = [True]

        def hook(event: str, **data: object) -> None:
            calls.append(event)
            if event == "built-all" and asked:
                asked.pop()
                loop.another_round = True

        loop.hook = hook  # type: ignore[method-assign]
        loop._rounds = lambda: calls.append("rounds")  # type: ignore[method-assign]
        loop._finish()
        self.assertEqual(calls, ["built-all", "rounds", "built-all", "run-end"])
        self.assertFalse(loop.another_round)

    def test_the_rounds_have_a_limit(self) -> None:
        _, calls = self.finish_with([[2]] * 20)
        self.assertEqual(calls.count("built-all"), engine.BUILT_ALL_ROUNDS)
        self.assertEqual(calls[-2], "run-end")

    def test_a_stopped_run_calls_no_built_all(self) -> None:
        for number in (1, 2):
            self.rec.set_status(number, record.BUILT)
        loop = self.make()
        loop.stop = threading.Event()
        loop.stop.set()
        loop.run_parked = ""
        loop.failed = False
        loop.refused = {}
        calls: list[str] = []
        loop.hook = lambda event, **data: calls.append(event)  # type: ignore[method-assign]
        loop._finish()
        self.assertEqual(calls, ["run-end"])


if __name__ == "__main__":
    unittest.main()
