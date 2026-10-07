"""Unit tests for P26: closing words, the merge gate, the pull request and `check-main`.

Built in groups. The first group holds the closing-word scan, which refuses a closing word
before any number the pull request does not own. Issue numbers are written with a single digit
here, so this file passes the house rule that no tracked file cites a number by a hash and
two or more digits.
"""

import dataclasses
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_moves  # type: ignore[import-not-found, unused-ignore]  # noqa: E402
from loop import closing, github, moves, pulls, spec  # noqa: E402
from loop.gates import merge as merge_gate  # noqa: E402
from loop.gates import recheck as recheck_gate  # noqa: E402
from loop.gates import review as review_gate  # noqa: E402
from loop.run import integrate  # noqa: E402
from loop.run import pull_request as pr_loop  # noqa: E402
from loop.run import record as run_record  # noqa: E402
from loop.run.gateway import Reply  # noqa: E402


class TheClosingWords(unittest.TestCase):
    def scan(self, **more: Any) -> list[closing.Fault]:
        given: dict[str, Any] = {"title": "A title", "body": "", "commits": [],
                                    "changelog": [], "pieces": []}
        given.update(more)
        return closing.scan(**given)

    def wheres(self, faults: list[closing.Fault]) -> list[str]:
        return [f.where for f in faults]

    def test_one_closes_line_for_each_piece_is_clean(self) -> None:
        body = "Piece 1.\n\nCloses #1\nCloses #2\n"
        self.assertEqual(self.scan(body=body, pieces=[1, 2]), [])

    def test_a_piece_with_no_closes_line_is_a_fault(self) -> None:
        faults = self.scan(body="Closes #1\n", pieces=[1, 2])
        self.assertEqual(self.wheres(faults), ["body"])
        self.assertIn("2", faults[0].message)

    def test_a_closes_line_twice_is_a_fault(self) -> None:
        faults = self.scan(body="Closes #1\nCloses #1\n", pieces=[1])
        self.assertEqual(self.wheres(faults), ["body"])
        self.assertIn("twice", faults[0].message)

    def test_a_closes_line_for_a_number_that_is_not_a_piece_is_a_fault(self) -> None:
        faults = self.scan(body="Closes #1\nCloses #3\n", pieces=[1])
        self.assertEqual(self.wheres(faults), ["body"])
        self.assertIn("3", faults[0].message)

    def test_a_closing_word_in_a_sentence_is_a_fault_even_when_it_denies_it(self) -> None:
        body = "Closes #1\nThis does not close #4, we say.\n"
        faults = self.scan(body=body, pieces=[1])
        self.assertEqual(self.wheres(faults), ["body"])

    def test_every_word_and_spelling_github_reads_is_found(self) -> None:
        for word in ("close", "closes", "closed", "fix", "fixes", "fixed", "resolve",
                     "resolves", "resolved", "CLOSES", "Fixes:", "resolved:"):
            with self.subTest(word=word):
                self.assertTrue(self.scan(body=f"See {word} #4 here"), word)
        self.assertTrue(self.scan(body="fixes owner/repo#4"))
        self.assertTrue(self.scan(body="closes GH-4"))
        self.assertTrue(self.scan(body="closes https://github.com/owner/repo/issues/4"))

    def test_a_word_next_to_no_number_is_clean(self) -> None:
        self.assertEqual(self.scan(body="The fix closes the gap. It fixed nothing else."), [])

    def test_a_longer_word_is_not_a_closing_word(self) -> None:
        self.assertEqual(self.scan(body="The prefix #4 and a disclose #4 are not closers"), [])

    def test_a_closing_word_in_the_title_a_commit_or_the_changelog_is_a_fault(self) -> None:
        self.assertEqual(self.wheres(self.scan(title="Fixes #4")), ["title"])
        self.assertEqual(self.wheres(self.scan(commits=["Do a thing\n\nCloses #1"])), ["commit 1"])
        self.assertEqual(self.wheres(self.scan(changelog=["The thing works. Resolves #4"])),
                         ["changelog entry 1"])

    def test_the_closes_line_may_not_hide_in_a_commit_even_for_an_owned_piece(self) -> None:
        self.assertTrue(self.scan(body="Closes #1\n", commits=["Closes #1"], pieces=[1]))

    def test_neutralise_breaks_every_reference_in_free_text(self) -> None:
        text = "Closes #4, fixes owner/repo#5 and see https://github.com/o/r/issues/6."
        safe = closing.neutralise(text)
        self.assertEqual(self.scan(body=safe), [])
        self.assertNotIn("#4", safe)
        self.assertIn("4", safe)


class TheClosingWordsScript(unittest.TestCase):
    SCRIPT = str(ROOT / "kit" / "scripts" / "closing-words.py")

    def setUp(self) -> None:
        self.folder = Path(tempfile.mkdtemp())
        self.env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
                    "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_AUTHOR_NAME": "T",
                    "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "T",
                    "GIT_COMMITTER_EMAIL": "t@example.com"}
        self.git("init", "-q", "-b", "main")
        (self.folder / "a.txt").write_text("a\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "Start")

    def git(self, *args: str) -> str:
        done = subprocess.run(["git", "-C", str(self.folder), *args], capture_output=True,
                              text=True, check=True, env=self.env)
        return done.stdout

    def run_script(self, *args: str) -> tuple[int, dict[str, object]]:
        done = subprocess.run([sys.executable, self.SCRIPT, "--project", str(self.folder),
                               "--json", *args], capture_output=True, text=True, check=False,
                              env=self.env, stdin=subprocess.DEVNULL)
        return done.returncode, json.loads(done.stdout.strip().splitlines()[-1])

    def test_a_clean_branch_passes_and_says_what_it_read(self) -> None:
        self.git("checkout", "-q", "-b", "topic")
        (self.folder / "CHANGELOG.md").write_text("# Changes\n\n- The thing works.\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "Add the thing")
        body = self.folder / "body.txt"
        body.write_text("Piece one.\n\nCloses #1\n")
        code, data = self.run_script("--title", "The thing", "--body-file", str(body),
                                     "--range", "main..topic", "--piece", "1")
        self.assertEqual(code, 0, data)
        self.assertEqual(data["scanned"], {"commits": 1, "changelog_lines": 2})

    def test_a_closing_word_in_a_commit_or_a_changelog_line_is_found(self) -> None:
        self.git("checkout", "-q", "-b", "topic")
        (self.folder / "CHANGELOG.md").write_text("- The thing works and fixes #4.\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "Add the thing", "-m", "Closes #3")
        code, data = self.run_script("--title", "The thing", "--range", "main..topic")
        self.assertEqual(code, 1, data)
        wheres = {f["where"] for f in data["faults"]}  # type: ignore[attr-defined]
        self.assertEqual(wheres, {"commit 1", "changelog entry 1"})
        self.assertTrue(data["next"])

    def test_a_range_git_cannot_read_is_not_a_pass(self) -> None:
        code, data = self.run_script("--title", "x", "--range", "nope..never")
        self.assertEqual(code, 4, data)
        self.assertIn("nothing was scanned", str(data["error"]))

    def test_a_run_with_nothing_to_scan_is_a_usage_error(self) -> None:
        code, _ = self.run_script()
        self.assertEqual(code, 2)


class FakeHub:
    """A hub that answers `_gh` with what the test says and keeps each call."""

    def __init__(self, *answers: object) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[list[str], str | None]] = []

    def _gh(self, args: Sequence[str], stdin: str | None = None) -> str:
        self.calls.append((list(args), stdin))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return str(answer)


VIEW = {"number": 7, "title": "T", "body": "B", "state": "OPEN",
        "url": "https://github.com/o/r/pull/7", "headRefName": "combined-r", "headRefOid": "abc",
        "baseRefName": "main", "mergedAt": None, "mergeCommit": None, "comments": []}


class ThePullRequestCalls(unittest.TestCase):
    def test_create_sends_the_body_on_standard_input_and_reads_the_number(self) -> None:
        hub = FakeHub("https://github.com/o/r/pull/7\n")
        made = pulls.Pulls(hub).create(base="main", head="combined-r", title="T", body="B")
        self.assertEqual(made, (7, "https://github.com/o/r/pull/7"))
        args, stdin = hub.calls[0]
        self.assertEqual(args[:2], ["pr", "create"])
        self.assertIn("--base", args)
        self.assertEqual(args[args.index("--head") + 1], "combined-r")
        self.assertEqual(stdin, "B")

    def test_create_with_no_address_back_is_an_error(self) -> None:
        with self.assertRaises(github.GitHubError):
            pulls.Pulls(FakeHub("nonsense")).create(base="main", head="h", title="T", body="B")

    def test_view_reads_every_field_and_the_comments(self) -> None:
        said = {"id": 5, "author": {"login": "person"}, "body": "Piece 2 is wrong"}
        shown = dict(VIEW, state="MERGED", mergedAt="2026-10-07T00:00:00Z",
                     mergeCommit={"oid": "def"}, comments=[said])
        got = pulls.Pulls(FakeHub(json.dumps(shown))).view(7)
        self.assertEqual((got.number, got.state, got.head_oid, got.merge_commit),
                         (7, "MERGED", "abc", "def"))
        self.assertEqual([(c.id, c.author, c.body) for c in got.comments],
                         [(5, "person", "Piece 2 is wrong")])

    def test_view_of_an_answer_that_is_not_a_pull_request_is_an_error(self) -> None:
        for answer in ("[]", "not json", json.dumps({"number": 7})):
            with self.subTest(answer=answer), self.assertRaises(github.GitHubError):
                pulls.Pulls(FakeHub(answer)).view(7)

    def test_merge_always_names_the_tested_commit(self) -> None:
        hub = FakeHub("")
        pulls.Pulls(hub).merge(7, head_commit="abc")
        args = hub.calls[0][0]
        self.assertEqual(args[:3], ["pr", "merge", "7"])
        self.assertEqual(args[args.index("--match-head-commit") + 1], "abc")
        self.assertIn("--merge", args)
        self.assertNotIn("--admin", args)
        self.assertNotIn("--auto", args)

    def test_merge_with_no_commit_is_refused_before_gh_starts(self) -> None:
        hub = FakeHub("")
        with self.assertRaises(ValueError):
            pulls.Pulls(hub).merge(7, head_commit="")
        self.assertEqual(hub.calls, [])

    def test_checks_that_fail_or_do_not_exist_are_never_green(self) -> None:
        def green(*answers: object) -> bool:
            return pulls.Pulls(FakeHub(*answers)).checks(7)[0]

        self.assertTrue(green("project-check\tpass\t0s\turl\n"))
        self.assertFalse(green(""))
        self.assertFalse(green(github.GitHubError("no", next_command="x")))
        self.assertFalse(green("a\tfail\t1s\tu\n"))
        self.assertFalse(green("a\tpending\t\tu\n"))

    def test_close_comment_and_set_base(self) -> None:
        hub = FakeHub("", "", "")
        api = pulls.Pulls(hub)
        api.close(7, "Replaced.")
        api.comment(7, "Hello")
        api.set_base(7, "main")
        self.assertEqual(hub.calls[0][0][:3], ["pr", "close", "7"])
        self.assertIn("Replaced.", hub.calls[0][0])
        self.assertEqual(hub.calls[1], (["pr", "comment", "7", "--body-file", "-"], "Hello"))
        self.assertEqual(hub.calls[2][0], ["pr", "edit", "7", "--base", "main"])


class TheActionOfAMove(test_moves.Base):  # type: ignore[misc, unused-ignore]
    """A check may hand the gate an action to run once, on a real move and never on a dry run."""

    def test_the_action_runs_on_a_real_move_after_the_checks_and_before_the_record(self) -> None:
        piece = self.capture()
        self.walk(piece, "approval")
        seen: list[str] = []

        def act() -> None:
            seen.append(self.gate.piece(piece).state)

        self.loader.data["merge"] = {"act": act}
        self.gate.move(piece, "done", dry_run=True)
        self.assertEqual(seen, [], "a dry run must not act")
        self.gate.move(piece, "done")
        self.assertEqual(seen, ["approval"])
        self.assertEqual(self.gate.piece(piece).state, "done")

    def test_an_action_that_fails_leaves_the_piece_where_it_was(self) -> None:
        piece = self.capture()
        self.walk(piece, "approval")
        before = self.gate.piece(piece).entries

        def act() -> None:
            raise github.GitHubError("GitHub did not merge", next_command="read the pull request")

        self.loader.data["merge"] = {"act": act}
        with self.assertRaises(moves.MoveError) as caught:
            self.gate.move(piece, "done")
        self.assertIn("GitHub did not merge", caught.exception.message)
        self.assertEqual(caught.exception.next_command, "read the pull request")
        self.assertEqual(self.gate.piece(piece).state, "approval")
        self.assertEqual(self.gate.piece(piece).entries, before)

    def test_an_action_is_not_a_record_entry(self) -> None:
        piece = self.capture()
        self.walk(piece, "approval")
        self.loader.data["merge"] = {"act": lambda: None}
        self.gate.move(piece, "done")
        kinds = {e.get("kind") for e in self.gate.piece(piece).record}
        self.assertNotIn("act", kinds)


class Repo:
    """A real Git repository with a bare origin, for the tests of the tested tree."""

    def __init__(self, root: Path | None = None) -> None:
        self.base = Path(tempfile.mkdtemp()) if root is None else root.parent
        self.root = self.base / "project" if root is None else root
        self.env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
                    "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_AUTHOR_NAME": "T",
                    "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "T",
                    "GIT_COMMITTER_EMAIL": "t@example.com"}
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.base / "o.git")],
                       check=True, env=self.env)
        self.root.mkdir(exist_ok=True)
        self.git("init", "-q", "-b", "main")
        self.git("remote", "add", "origin", str(self.base / "o.git"))
        self.write("README.md", "start\n")
        self.write(".gitignore", ".agents/\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "Start")
        self.git("push", "-q", "origin", "main")

    def git(self, *args: str) -> str:
        done = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True,
                              text=True, check=True, env=self.env)
        return done.stdout.strip()

    def write(self, name: str, text: str) -> None:
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def commit(self, name: str, text: str, message: str = "Change") -> str:
        self.write(name, text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def branch(self, name: str, start: str = "main") -> None:
        self.git("checkout", "-q", "-b", name, start)

    def join(self, branch: str, number: int) -> str:
        """Merge `branch` into the current branch with a `Piece:` trailer, as a join does."""
        self.git("merge", "--no-ff", "-q", "-m", f"Join piece {number}\n\nPiece: #{number}",
                 branch)
        return self.git("rev-parse", "HEAD")


class TheTestedTree(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repo()
        r = self.repo
        r.branch("piece-1")
        r.commit("a/one.txt", "one\n")
        r.git("checkout", "-q", "main")
        r.branch("combined", "main")
        self.join1 = r.join("piece-1", 1)
        r.git("checkout", "-q", "main")

    def test_a_main_that_has_not_moved_is_not_moved(self) -> None:
        self.assertEqual(merge_gate.moved(self.repo.root, self.join1), [])

    def test_a_commit_on_main_that_the_branch_lacks_is_moved(self) -> None:
        self.repo.commit("b/new.txt", "new\n", "Someone else's work")
        found = merge_gate.moved(self.repo.root, self.join1)
        self.assertEqual(len(found), 1)

    def test_origin_main_ahead_of_the_local_main_is_moved(self) -> None:
        r = self.repo
        r.commit("b/new.txt", "new\n", "Someone else's work")
        r.git("push", "-q", "origin", "main")
        r.git("reset", "-q", "--hard", "HEAD~1")
        r.git("fetch", "-q", "origin", "main:refs/remotes/origin/main")
        self.assertEqual(len(merge_gate.moved(r.root, self.join1)), 1)

    def test_the_merge_of_an_earlier_part_of_the_same_stack_is_not_moved(self) -> None:
        r = self.repo
        r.git("checkout", "-q", "combined")
        r.branch("piece-2")
        r.commit("a/two.txt", "two\n")
        r.git("checkout", "-q", "combined")
        head = r.join("piece-2", 2)
        # The person merged the first part into main with a merge commit.
        r.git("checkout", "-q", "main")
        r.git("merge", "--no-ff", "-q", "-m", "Merge the first part", self.join1)
        self.assertEqual(merge_gate.moved(r.root, head), [])

    def test_a_merge_of_something_the_branch_lacks_is_moved(self) -> None:
        r = self.repo
        r.branch("stray", "main")
        r.commit("c/stray.txt", "stray\n")
        r.git("checkout", "-q", "main")
        r.git("merge", "--no-ff", "-q", "-m", "Merge a stray branch", "stray")
        self.assertEqual(len(merge_gate.moved(r.root, self.join1)), 2, "the stray commit and "
                         "the merge that brings it in")

    def test_the_local_main_behind_origin_is_found(self) -> None:
        r = self.repo
        r.commit("b/new.txt", "new\n")
        r.git("push", "-q", "origin", "main")
        r.git("reset", "-q", "--hard", "HEAD~1")
        r.git("fetch", "-q", "origin", "main:refs/remotes/origin/main")
        self.assertTrue(merge_gate.main_lags(r.root))
        r.git("merge", "-q", "--ff-only", "origin/main")
        self.assertFalse(merge_gate.main_lags(r.root))

    def specs(self, *docs: str) -> dict[int, dict[str, Any]]:
        return {1: {"changes": {"docs": list(docs)}}}

    def test_a_named_doc_the_branch_changed_passes(self) -> None:
        r = self.repo
        r.git("checkout", "-q", "combined")
        head = r.commit("docs/one.md", "one\n")
        self.assertEqual(merge_gate.doc_faults(r.root, head, self.specs("docs/one.md")), [])

    def test_a_named_doc_the_branch_did_not_change_is_a_fault(self) -> None:
        r = self.repo
        r.git("checkout", "-q", "combined")
        r.write("docs/two.md", "main had it\n")
        faults = merge_gate.doc_faults(r.root, self.join1, self.specs("docs/two.md"))
        self.assertEqual(len(faults), 1)
        self.assertIn("docs/two.md", faults[0])
        self.assertIn("piece 1", faults[0])

    def test_a_piece_that_names_no_doc_needs_none(self) -> None:
        self.assertEqual(merge_gate.doc_faults(self.repo.root, self.join1, self.specs()), [])

    def test_a_named_path_outside_the_project_is_a_fault(self) -> None:
        for bad in ("/etc/hosts", "../up.md"):
            with self.subTest(bad=bad):
                faults = merge_gate.doc_faults(self.repo.root, self.join1, self.specs(bad))
                self.assertEqual(len(faults), 1)
                self.assertIn("outside the project", faults[0])

    def test_a_branch_git_cannot_read_is_never_a_pass(self) -> None:
        with self.assertRaises(merge_gate.Unreadable):
            merge_gate.doc_faults(self.repo.root, "nosuchbranch", self.specs("docs/one.md"))
        with self.assertRaises(merge_gate.Unreadable):
            merge_gate.moved(self.repo.root, "nosuchbranch")


class TheFetch(unittest.TestCase):
    def test_fetch_moves_only_the_remote_tracking_ref(self) -> None:
        from loop.paths import Paths

        r = Repo()
        other = r.base / "other"
        subprocess.run(["git", "clone", "-q", str(r.base / "o.git"), str(other)], check=True,
                       env=r.env)
        (other / "x.txt").write_text("x\n")
        for args in (["add", "-A"], ["commit", "-q", "-m", "More"],
                     ["push", "-q", "origin", "main"]):
            subprocess.run(["git", "-C", str(other), *args], check=True, env=r.env)
        paths = Paths.for_project(r.root, data_base=r.base / "data", kit_folder=ROOT / "kit")
        before = r.git("rev-parse", "main")
        done = github.fetch(paths, "main", env=r.env)
        self.assertEqual(done["fetched"], "origin/main")
        self.assertEqual(r.git("rev-parse", "main"), before, "the local main must not move")
        self.assertNotEqual(r.git("rev-parse", "refs/remotes/origin/main"), before)

    def test_fetch_refuses_a_bad_branch_name_and_an_unknown_remote(self) -> None:
        from loop.paths import Paths

        r = Repo()
        paths = Paths.for_project(r.root, data_base=r.base / "data", kit_folder=ROOT / "kit")
        with self.assertRaises(github.GitHubError):
            github.fetch(paths, "--upload-pack=x", env=r.env)
        with self.assertRaises(github.GitHubError):
            github.fetch(paths, "main", remote="nowhere", env=r.env)


class FakePulls:
    """The pull request calls, answered from a dictionary the test edits."""

    def __init__(self) -> None:
        self.view_of: dict[int, pulls.PullRequest] = {}
        self.green = True
        self.merged: list[tuple[int, str]] = []
        self.merge_error: github.GitHubError | None = None

    def view(self, ref: int | str) -> pulls.PullRequest:
        return self.view_of[int(ref)]

    def checks(self, number: int) -> tuple[bool, str]:
        return (True, "1 check(s) passed") if self.green else (False, "a check failed")

    def merge(self, number: int, *, head_commit: str) -> None:
        if self.merge_error is not None:
            raise self.merge_error
        self.merged.append((number, head_commit))


class GateWith:
    """A loader that runs the real checks of moves 10, 11 and 12 and stubs for the rest."""

    def __init__(self, stubs: Any) -> None:
        self.stubs = stubs

    def __call__(self, name: str) -> Callable[[Any], Any]:
        real = {"merge": merge_gate.check, "review": review_gate.check,
                "recheck": recheck_gate.check}
        return real[name] if name in real else self.stubs(name)


class Merging(test_moves.Base):  # type: ignore[misc, unused-ignore]
    """One piece in review, one combined branch with its join and its docs commit."""

    run_name = "r1"

    def setUp(self) -> None:
        super().setUp()
        self.gate.loader = GateWith(self.loader)
        self.repo = Repo(self.paths.root)
        r = self.repo
        self.piece = self.capture()
        self.walk(self.piece, "review")
        self.issue = self.gate.piece(self.piece).issue
        r.branch("piece-1")
        r.commit("src/report.txt", "the rename\n")
        r.git("checkout", "-q", "main")
        r.branch("combined-r1", "main")
        r.join("piece-1", self.piece)
        self.head = r.commit("docs/reports.md", "- The rename exists (piece 1)\n", "Docs")
        r.git("checkout", "-q", "main")
        self.pulls = FakePulls()
        for patch in (mock.patch.object(merge_gate, "make_pulls", lambda paths: self.pulls),
                      mock.patch.object(merge_gate, "fetch_main", lambda paths: None)):
            patch.start()
            self.addCleanup(patch.stop)
        self.write_run(merge_pre_approved=False)
        self.pulls.view_of[7] = self.pr()

    def write_run(self, *, merge_pre_approved: bool, green: bool = True, clean: bool = True,
                  verdict: str = "clean", order: Sequence[int] = (1,)) -> None:
        data = {
            "merge_pre_approved": merge_pre_approved, "order": list(order),
            "integration": {"final": {"main": {
                "status": "green" if green else "red", "head": self.head,
                "branch": "combined-r1"}}},
            "review": {"tracks": {"main": {"status": "clean" if clean else "open",
                                           "reviewed": self.head}},
                       "verdicts": {"1": {"verdict": verdict}}},
        }
        target = self.paths.run_record(self.run_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data))

    def pr(self, **more: Any) -> pulls.PullRequest:
        fields: dict[str, Any] = {
            "number": 7, "url": "https://github.com/o/r/pull/7", "state": "OPEN", "title": "A run",
            "body": f"Piece 1.\n\nCloses #{self.issue}\n", "head_branch": "combined-r1",
            "head_oid": self.head, "base": "main"}
        fields.update(more)
        return pulls.PullRequest(**fields)

    def options(self, **more: str) -> dict[str, str]:
        given = {"run": self.run_name, "track": "main", "part": "1", "parts": "1",
                 "pull_request": "7", "branch": "combined-r1", "head": self.head,
                 "base": "main", "since": "main", "stack_head": self.head, "base_pr": "",
                 "pieces": str(self.piece), "stack": str(self.piece)}
        given.update(more)
        return given

    def open_pull_request(self) -> None:
        self.gate.move(self.piece, "approval", options=self.options())

    def refusal(self, *args: Any, **kwargs: Any) -> str:
        with self.assertRaises(moves.MoveError) as caught:
            self.gate.move(*args, **kwargs)
        return str(caught.exception.message) + " | " + str(caught.exception.next_command)


class MoveTenOpensThePullRequest(Merging):
    def test_a_pull_request_that_holds_every_fact_passes_and_is_written_down(self) -> None:
        self.open_pull_request()
        self.assertEqual(self.gate.piece(self.piece).state, "approval")
        entry = merge_gate.latest_entry(self.gate.piece(self.piece).record)
        assert entry is not None
        self.assertEqual((entry["head"], entry["pull_request"], entry["pieces"]),
                         (self.head, 7, [self.piece]))
        self.assertEqual(entry["url"], "https://github.com/o/r/pull/7")

    def test_options_the_run_did_not_give_are_a_refusal(self) -> None:
        options = self.options()
        del options["head"]
        text = self.refusal(self.piece, "approval", options=options)
        self.assertIn("head", text)
        self.assertEqual(self.gate.piece(self.piece).state, "review")

    def test_a_final_check_that_was_not_green_is_a_refusal(self) -> None:
        self.write_run(merge_pre_approved=False, green=False)
        self.assertIn("final combined check", self.refusal(
            self.piece, "approval", options=self.options()))

    def test_a_review_that_was_not_clean_is_a_refusal(self) -> None:
        self.write_run(merge_pre_approved=False, clean=False)
        self.assertIn("review of main was not clean", self.refusal(
            self.piece, "approval", options=self.options()))
        self.write_run(merge_pre_approved=False, verdict="needs-work")
        self.assertIn("verdict of piece 1", self.refusal(
            self.piece, "approval", options=self.options()))

    def test_a_run_record_that_cannot_be_read_is_a_refusal_and_never_a_pass(self) -> None:
        self.paths.run_record(self.run_name).write_text("not json")
        self.assertIn("cannot be read", self.refusal(
            self.piece, "approval", options=self.options()))

    def test_a_pull_request_that_is_not_the_tested_commit_is_a_refusal(self) -> None:
        self.pulls.view_of[7] = self.pr(head_oid="0" * 40)
        self.assertIn("not the tested commit", self.refusal(
            self.piece, "approval", options=self.options()))

    def test_a_pull_request_on_the_wrong_base_or_branch_is_a_refusal(self) -> None:
        self.pulls.view_of[7] = self.pr(base="other", head_branch="elsewhere")
        text = self.refusal(self.piece, "approval", options=self.options())
        self.assertIn("based on other", text)
        self.assertIn("cut from elsewhere", text)

    def test_a_branch_that_moved_off_the_tested_commit_is_a_refusal(self) -> None:
        self.repo.git("branch", "-f", "combined-r1", "main")
        self.assertIn("does not point at the tested commit", self.refusal(
            self.piece, "approval", options=self.options()))

    def test_a_named_doc_the_pull_request_did_not_change_is_refused(self) -> None:
        r = self.repo
        r.git("checkout", "-q", "-b", "combined-nodocs", "main")
        r.join("piece-1", self.piece)
        nodocs = r.git("rev-parse", "HEAD")
        r.git("checkout", "-q", "main")
        self.write_run(merge_pre_approved=False)
        run = json.loads(self.paths.run_record(self.run_name).read_text())
        run["integration"]["final"]["main"]["head"] = nodocs
        run["review"]["tracks"]["main"]["reviewed"] = nodocs
        self.paths.run_record(self.run_name).write_text(json.dumps(run))
        self.pulls.view_of[7] = self.pr(head_oid=nodocs, head_branch="combined-nodocs")
        text = self.refusal(self.piece, "approval", options=self.options(
            branch="combined-nodocs", head=nodocs, stack_head=nodocs))
        self.assertIn("names the doc docs/reports.md", text)
        self.assertIn("did not change it", text)

    def test_a_closing_word_anywhere_else_is_refused(self) -> None:
        self.pulls.view_of[7] = self.pr(body=f"Closes #{self.issue}\nThis fixes #4 too.")
        self.assertIn("closing word", self.refusal(
            self.piece, "approval", options=self.options()))
        self.pulls.view_of[7] = self.pr(title="Closes #4")
        self.assertIn("title", self.refusal(self.piece, "approval", options=self.options()))
        self.pulls.view_of[7] = self.pr(body="Piece one without a line.")
        self.assertIn("no Closes line", self.refusal(
            self.piece, "approval", options=self.options()))

    def test_a_piece_the_pull_request_does_not_hold_is_refused(self) -> None:
        self.assertIn("not one of the pieces", self.refusal(
            self.piece, "approval", options=self.options(pieces="9", stack="9")))

    def test_a_dry_run_writes_nothing(self) -> None:
        self.gate.move(self.piece, "approval", options=self.options(), dry_run=True)
        self.assertEqual(self.gate.piece(self.piece).state, "review")
        self.assertIsNone(merge_gate.latest_entry(self.gate.piece(self.piece).record))


class MoveElevenMerges(Merging):
    def setUp(self) -> None:
        super().setUp()
        self.open_pull_request()

    def test_a_pull_request_the_person_merged_on_the_tested_commit_passes(self) -> None:
        self.pulls.view_of[7] = self.pr(state="MERGED", merge_commit="c0ffee")
        self.gate.move(self.piece, "done")
        self.assertEqual(self.gate.piece(self.piece).state, "done")
        self.assertEqual(self.pulls.merged, [], "the gate does not merge what is merged")
        kinds = [e["kind"] for e in self.gate.piece(self.piece).record]
        self.assertIn("merged", kinds)

    def test_a_merge_of_another_commit_is_a_refusal_that_names_the_check_on_main(self) -> None:
        self.pulls.view_of[7] = self.pr(state="MERGED", head_oid="0" * 40)
        text = self.refusal(self.piece, "done")
        self.assertIn("not the tested commit", text)
        self.assertIn("check-main", text)

    def test_a_closed_pull_request_points_to_move_13(self) -> None:
        self.pulls.view_of[7] = self.pr(state="CLOSED")
        self.assertIn("move 13", self.refusal(self.piece, "done"))

    def test_an_open_pull_request_waits_for_the_person(self) -> None:
        text = self.refusal(self.piece, "done")
        self.assertIn("waits for the person's merge", text)
        self.assertEqual(self.pulls.merged, [])

    def test_the_agent_merges_the_exact_tested_commit_when_the_person_says_merge(self) -> None:
        self.gate.move(self.piece, "done", options={
            "merge": "agent", "said": "Yes, merge pull request 7."})
        self.assertEqual(self.pulls.merged, [(7, self.head)])
        self.assertEqual(self.gate.piece(self.piece).state, "done")

    def test_a_yes_that_does_not_name_the_merge_is_refused(self) -> None:
        text = self.refusal(self.piece, "done", options={
            "merge": "agent", "said": "Yes, put it live."})
        self.assertIn("do not name the merge", text)
        self.assertEqual(self.pulls.merged, [])

    def test_a_dry_run_never_merges(self) -> None:
        self.gate.move(self.piece, "done", options={
            "merge": "agent", "said": "merge it"}, dry_run=True)
        self.assertEqual(self.pulls.merged, [])
        self.assertEqual(self.gate.piece(self.piece).state, "approval")

    def test_a_merge_github_refuses_leaves_the_piece_in_approval(self) -> None:
        self.pulls.merge_error = github.GitHubError(
            "Head branch was modified", next_command="read the pull request")
        text = self.refusal(self.piece, "done", options={"merge": "agent", "said": "merge"})
        self.assertIn("Head branch was modified", text)
        self.assertEqual(self.gate.piece(self.piece).state, "approval")

    def test_main_that_moved_after_the_final_check_refuses_every_merge(self) -> None:
        self.repo.commit("other/work.txt", "someone else\n", "Work that the tests never saw")
        for options in ({"merge": "agent", "said": "merge"}, {"merge": "pre-approved"}):
            with self.subTest(options=options):
                self.write_run(merge_pre_approved=True)
                text = self.refusal(self.piece, "done", options=options)
                self.assertIn("main moved after the final check", text)
                self.assertIn("move 12", text)
        self.assertEqual(self.pulls.merged, [])

    def test_a_pull_request_with_no_checks_or_red_checks_is_refused(self) -> None:
        self.pulls.green = False
        self.assertIn("checks on the pull request are not green", self.refusal(
            self.piece, "done", options={"merge": "agent", "said": "merge"}))

    def test_a_pull_request_whose_head_moved_is_refused(self) -> None:
        self.pulls.view_of[7] = self.pr(head_oid="1" * 40)
        self.assertIn("not the tested commit", self.refusal(
            self.piece, "done", options={"merge": "agent", "said": "merge"}))

    def test_an_irreversible_data_change_is_always_the_persons_merge(self) -> None:
        with mock.patch.object(merge_gate, "piece_specs", lambda paths, numbers: {
                n: {"changes": {"docs": [], "not_reversible": ["yes"]}} for n in numbers}):
            text = self.refusal(self.piece, "done", options={"merge": "agent", "said": "merge"})
        self.assertIn("irreversible", text)

    def test_a_stacked_pull_request_never_merges_before_its_base(self) -> None:
        entry = merge_gate.latest_entry(self.gate.piece(self.piece).record)
        assert entry is not None
        self.pulls.view_of[3] = self.pr(number=3, state="OPEN")
        with mock.patch.object(merge_gate, "latest_entry", lambda record: dict(
                entry, base_pr=3, part=2, parts=2)):
            text = self.refusal(self.piece, "done", options={"merge": "agent", "said": "merge"})
        self.assertIn("stacked on pull request 3", text)
        self.pulls.view_of[3] = self.pr(number=3, state="MERGED")
        self.pulls.view_of[7] = self.pr(base="part-1")
        with mock.patch.object(merge_gate, "latest_entry", lambda record: dict(
                entry, base_pr=3, part=2, parts=2, base="part-1")):
            text = self.refusal(self.piece, "done", options={"merge": "agent", "said": "merge"})
        self.assertIn("retargeted", text)

    def test_a_pre_approved_merge_needs_the_run_to_say_so(self) -> None:
        text = self.refusal(self.piece, "done", options={"merge": "pre-approved"})
        self.assertIn("was not pre-approved", text)
        self.assertEqual(self.pulls.merged, [])

    def test_a_pre_approved_merge_goes_ahead_when_every_condition_holds(self) -> None:
        self.write_run(merge_pre_approved=True)
        self.add_attempt("passed")
        self.gate.move(self.piece, "done", options={"merge": "pre-approved"})
        self.assertEqual(self.pulls.merged, [(7, self.head)])

    def add_attempt(self, result: str, gaming: bool = False) -> None:
        from loop import attempt_log, evidence

        evidence.append(self.paths, self.piece, [attempt_log.entry(
            number=1, result=result, head="h", base="b", at="2026-10-07",
            findings=[attempt_log.finding("frozen-bar", "edited", gaming=True)] if gaming else [])])

    def test_a_pre_approved_merge_waits_for_a_piece_with_a_must_look_reason(self) -> None:
        self.write_run(merge_pre_approved=True)
        self.add_attempt("passed")
        other = self.capture()
        self.loader.data["ready"] = {"must_look": ["a sensitive area"]}
        self.walk(other, "review")
        self.write_run(merge_pre_approved=True, order=(1, other))
        text = self.refusal(self.piece, "done", options={"merge": "pre-approved"})
        self.assertIn("must-look reason", text)
        self.assertEqual(self.pulls.merged, [])

    def test_a_pre_approved_merge_waits_when_the_last_attempt_is_not_a_clean_pass(self) -> None:
        self.write_run(merge_pre_approved=True)
        self.add_attempt("failed")
        self.assertIn("not a pass", self.refusal(
            self.piece, "done", options={"merge": "pre-approved"}))
        self.add_attempt("passed", gaming=True)
        self.assertIn("possible gaming", self.refusal(
            self.piece, "done", options={"merge": "pre-approved"}))


class MoveTwelveRechecks(Merging):
    def setUp(self) -> None:
        super().setUp()
        self.open_pull_request()

    def approved(self) -> int:
        """Another piece, taken to approval by stub checks (it has no pull request here)."""
        other = self.capture()
        real, self.gate.loader = self.gate.loader, self.loader
        try:
            self.walk(other, "approval")
        finally:
            self.gate.loader = real
        return int(other)

    def test_main_that_moved_sends_the_piece_back_to_review(self) -> None:
        self.repo.commit("other/work.txt", "someone else\n", "Work")
        self.gate.move(self.piece, "review", reason="main moved after the final check")
        self.assertEqual(self.gate.piece(self.piece).state, "review")
        last = [e for e in self.gate.piece(self.piece).record if e.get("kind") == "recheck"][-1]
        self.assertEqual(last["because"], "main-moved")

    def test_a_tested_tree_that_did_not_change_has_no_reason_to_go_back(self) -> None:
        text = self.refusal(self.piece, "review", reason="a feeling")
        self.assertIn("main did not move", text)
        self.assertEqual(self.gate.piece(self.piece).state, "approval")

    def test_a_rejected_piece_sends_the_others_back(self) -> None:
        other = self.approved()
        entry = merge_gate.latest_entry(self.gate.piece(self.piece).record)
        assert entry is not None
        self.gate.loader = self.loader
        self.gate.move(other, "building", reason="the person rejected piece two")
        self.gate.loader = GateWith(self.loader)
        with mock.patch.object(merge_gate, "latest_entry", lambda record: dict(
                entry, pieces=[self.piece, other], stack=[self.piece, other])):
            self.gate.move(self.piece, "review", reason="piece two was rejected",
                           options={"rejected": str(other)})
        self.assertEqual(self.gate.piece(self.piece).state, "review")

    def test_a_piece_that_is_still_in_approval_was_not_rejected(self) -> None:
        other = self.approved()
        entry = merge_gate.latest_entry(self.gate.piece(self.piece).record)
        assert entry is not None
        with mock.patch.object(merge_gate, "latest_entry", lambda record: dict(
                entry, stack=[self.piece, other])):
            text = self.refusal(self.piece, "review", reason="a feeling",
                                options={"rejected": str(other)})
        self.assertIn("was not rejected", text)


class CheckMain(Merging):
    """`gate.py check-main`: find a merge the person made, and check main when it had moved."""

    def setUp(self) -> None:
        super().setUp()
        self.open_pull_request()
        self.commands: list[tuple[str, str]] = []
        self.exit_code = 0
        self.app = True

    def settle(self, number: int) -> dict[str, Any]:
        return dict(self.gate.move(number, "done"))

    def run_check(self, ref: str) -> dict[str, Any]:
        self.commands.append(("test", ref))
        return {"exit_code": self.exit_code, "timed_out": False, "output_tail": "tail"}

    def check_main(self, *, dry_run: bool = False) -> dict[str, Any]:
        return merge_gate.check_main(
            self.paths, settle=self.settle, run_tests=self.run_check, test_command="make check",
            app=self.app, dry_run=dry_run)

    def person_merges(self, *, main_moved: bool) -> str:
        r = self.repo
        if main_moved:
            r.commit("other/work.txt", "someone else\n", "Work that was never tested together")
        r.git("merge", "--no-ff", "-q", "-m", "Merge the pull request", self.head)
        merge = r.git("rev-parse", "HEAD")
        self.pulls.view_of[7] = self.pr(state="MERGED", merge_commit=merge)
        return merge

    def test_an_open_pull_request_is_not_a_finding(self) -> None:
        found = self.check_main()
        self.assertEqual((found["merges"], found["unreadable"]), ([], []))
        self.assertEqual(self.gate.piece(self.piece).state, "approval")

    def test_a_merge_on_the_tested_commit_closes_the_piece_and_needs_no_check_on_main(self) -> None:
        self.person_merges(main_moved=False)
        found = self.check_main()
        self.assertEqual(self.gate.piece(self.piece).state, "done")
        self.assertEqual(len(found["merges"]), 1)
        item = found["merges"][0]
        self.assertFalse(item["main_moved"])
        self.assertEqual(item["main_check"], "not needed")
        self.assertEqual(self.commands, [])

    def test_a_merge_after_main_moved_runs_the_check_on_the_merge_commit(self) -> None:
        merge = self.person_merges(main_moved=True)
        found = self.check_main()
        item = found["merges"][0]
        self.assertTrue(item["main_moved"])
        self.assertEqual(item["main_check"], "green")
        self.assertEqual(self.commands, [("test", merge)])
        self.assertEqual(self.gate.piece(self.piece).state, "done")
        kinds = [e["kind"] for e in self.gate.piece(self.piece).record]
        self.assertIn("main-check", kinds)

    def test_a_red_main_names_the_next_step_and_is_not_hidden(self) -> None:
        self.exit_code = 1
        self.person_merges(main_moved=True)
        found = self.check_main()
        self.assertEqual(found["merges"][0]["main_check"], "red")
        self.assertIn("main is red", found["next"])

    def test_a_merge_with_no_test_command_is_a_visible_skip_never_green(self) -> None:
        self.person_merges(main_moved=True)
        found = merge_gate.check_main(
            self.paths, settle=self.settle, run_tests=self.run_check, test_command="",
            app=True, dry_run=False)
        self.assertEqual(found["merges"][0]["main_check"], "not run")
        self.assertIn("skipped", found["merges"][0]["why"])

    def test_a_dry_run_reports_and_changes_nothing(self) -> None:
        self.person_merges(main_moved=True)
        found = self.check_main(dry_run=True)
        self.assertEqual(len(found["merges"]), 1)
        self.assertEqual(self.gate.piece(self.piece).state, "approval")
        self.assertEqual(self.commands, [])

    def test_a_merge_of_another_commit_is_reported_and_the_piece_stays_in_approval(self) -> None:
        merge = self.person_merges(main_moved=False)
        self.pulls.view_of[7] = self.pr(state="MERGED", head_oid="0" * 40, merge_commit=merge)
        found = self.check_main()
        self.assertEqual(found["merges"][0]["settled"], False)
        self.assertEqual(found["merges"][0]["main_check"], "green", "an untested merge is checked")
        self.assertEqual(self.gate.piece(self.piece).state, "approval")

    def test_no_app_is_a_visible_skip(self) -> None:
        self.app = False
        found = self.check_main()
        self.assertIn("skipped", found["skipped"])
        self.assertEqual(found["merges"], [])

    def test_a_pull_request_that_cannot_be_read_is_listed_never_passed(self) -> None:
        def fail(ref: int | str) -> pulls.PullRequest:
            raise github.GitHubError("GitHub did not answer", next_command="try again")

        self.pulls.view = fail  # type: ignore[method-assign]
        found = self.check_main()
        self.assertEqual(len(found["unreadable"]), 1)
        self.assertIn("did not answer", found["unreadable"][0]["why"])

    def test_a_run_that_is_going_is_left_alone(self) -> None:
        lock = self.paths.lock_file("busy")
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(f"{os.getpid()}\n")
        found = self.check_main()
        self.assertIn("a run is going", found["skipped"])
        self.assertEqual(found["merges"], [])

    def test_a_lock_of_a_dead_run_does_not_count(self) -> None:
        lock = self.paths.lock_file("old")
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("999999\n")
        self.assertEqual(merge_gate.run_going(self.paths), "")

    def test_nothing_waiting_in_approval_is_a_quiet_pass(self) -> None:
        self.pulls.view_of[7] = self.pr(state="MERGED", merge_commit="x")
        self.person_merges(main_moved=False)
        self.check_main()
        again = self.check_main()
        self.assertEqual(again["merges"], [])
        self.assertEqual(again["waiting"], [])


class ThePreRunCheckOfMerges(unittest.TestCase):
    """The pre-run check asks `gate.py check-main` about a merge the person made."""

    def load(self) -> Any:
        import importlib.util

        script = ROOT / "kit" / "scripts" / "pre-run-check.py"
        spec = importlib.util.spec_from_file_location("pre_run_for_merges", script)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["pre_run_for_merges"] = module
        spec.loader.exec_module(module)
        return module

    def answer(self, code: int, data: dict[str, Any] | None = None, text: str | None = None
               ) -> Any:
        body = text if text is not None else json.dumps(data or {})

        def runner(argv: list[str], **kwargs: Any) -> Any:
            self.argv = argv
            self.cwd = kwargs.get("cwd")
            return subprocess.CompletedProcess(argv, code, stdout=body + "\n", stderr="")

        return runner

    def check(self, runner: Any) -> tuple[list[Any], list[str]]:
        module = self.load()
        folder = Path(tempfile.mkdtemp())
        return module.check_merges(folder, ROOT / "kit", runner=runner)  # type: ignore[no-any-return]

    def test_it_runs_the_gates_check_main_in_the_project(self) -> None:
        self.check(self.answer(0, {"ok": True, "merges": []}))
        self.assertEqual(self.argv[-2:], ["check-main", "--json"])
        self.assertTrue(str(self.argv[1]).endswith("gate.py"))
        self.assertIsNotNone(self.cwd)

    def test_nothing_found_passes_quietly(self) -> None:
        refusals, notices = self.check(self.answer(0, {"ok": True, "merges": [], "skipped": ""}))
        self.assertEqual((refusals, notices), ([], []))

    def test_a_run_that_is_going_is_not_a_refusal(self) -> None:
        refusals, notices = self.check(self.answer(0, {"ok": True, "merges": [],
                                                       "skipped": "skipped: a run is going (x)"}))
        self.assertEqual(refusals, [])
        self.assertTrue(any("run is going" in n for n in notices))

    def test_a_merge_found_is_told_as_a_notice_with_the_check_on_main(self) -> None:
        found = {"ok": True, "skipped": "", "merges": [
            {"pull_request": 7, "main_moved": True, "main_check": "green"}]}
        refusals, notices = self.check(self.answer(0, found))
        self.assertEqual(refusals, [])
        self.assertTrue(any("pull request 7" in n and "green" in n for n in notices), notices)

    def test_a_red_main_after_a_merge_is_a_refusal(self) -> None:
        refusals, _ = self.check(self.answer(1, {"ok": False, "error": "main is red after it",
                                                 "next": "capture a bug piece"}))
        self.assertEqual(len(refusals), 1)
        self.assertEqual(refusals[0].guard, "merge")
        self.assertIn("main is red", refusals[0].reason)
        self.assertEqual(refusals[0].fix, "capture a bug piece")

    def test_a_check_that_could_not_read_a_merge_is_a_refusal_never_a_pass(self) -> None:
        for runner in (self.answer(4, {"ok": False, "error": "GitHub did not answer",
                                       "next": "try again"}),
                       self.answer(0, text="not json"),
                       self.answer(2, text="")):
            with self.subTest():
                refusals, _ = self.check(runner)
                self.assertEqual([r.guard for r in refusals], ["merge-read"])

    def test_a_gate_that_cannot_start_is_a_refusal(self) -> None:
        def broken(argv: list[str], **kwargs: Any) -> Any:
            raise OSError("no python")

        refusals, _ = self.check(broken)
        self.assertEqual([r.guard for r in refusals], ["merge-read"])

    def test_the_unreadable_list_of_a_good_run_is_a_refusal(self) -> None:
        found = {"ok": True, "skipped": "", "merges": [], "unreadable": [
            {"pull_request": 7, "pieces": [1], "why": "GitHub did not answer"}]}
        refusals, _ = self.check(self.answer(0, found))
        self.assertEqual([r.guard for r in refusals], ["merge-read"])


class TheSplit(unittest.TestCase):
    def test_pieces_within_the_limit_stay_in_one_pull_request(self) -> None:
        self.assertEqual(pr_loop.plan_groups([(1, 300), (2, 400)], 800, one_each=False), [[1, 2]])

    def test_a_pull_request_past_the_limit_is_split_into_whole_pieces_in_order(self) -> None:
        sizes = [(1, 500), (2, 400), (3, 300), (4, 200)]
        self.assertEqual(pr_loop.plan_groups(sizes, 800, one_each=False), [[1], [2, 3], [4]])

    def test_a_piece_bigger_than_the_limit_is_a_part_of_its_own(self) -> None:
        self.assertEqual(pr_loop.plan_groups([(1, 100), (2, 5000), (3, 100)], 800,
                                             one_each=False), [[1], [2], [3]])

    def test_every_piece_appears_once_and_in_the_order_it_joined(self) -> None:
        sizes = [(5, 700), (3, 700), (9, 10), (1, 700)]
        groups = pr_loop.plan_groups(sizes, 800, one_each=False)
        self.assertEqual([n for g in groups for n in g], [5, 3, 9, 1])

    def test_an_isolated_track_gives_each_piece_its_own_pull_request(self) -> None:
        self.assertEqual(pr_loop.plan_groups([(1, 5), (2, 5)], 800, one_each=True), [[1], [2]])

    def test_no_piece_is_no_group(self) -> None:
        self.assertEqual(pr_loop.plan_groups([], 800, one_each=False), [])


def facts(number: int = 1, **more: Any) -> pr_loop.PieceFacts:
    given: dict[str, Any] = {
        "number": number, "issue": number + 10 if number > 8 else number,
        "title": "Rename a report",
        "judge": "python3 -m pytest tests/test_rename.py", "held_out": True,
        "review": "clean in round 2", "notes": [], "added": ["A Rename item exists."],
        "changed": [], "removed": [], "must_look": [], "size": 40}
    given.update(more)
    return pr_loop.PieceFacts(**given)


class TheBody(unittest.TestCase):
    def body(self, pieces: list[pr_loop.PieceFacts], **more: Any) -> str:
        given: dict[str, Any] = {
            "run": "r1", "branch": "combined-r1", "head": "a" * 40, "checks": 4, "held_runs": 2,
            "part": 1, "parts": 1, "general": []}
        given.update(more)
        return pr_loop.render_body(pieces, **given)

    def test_each_piece_is_listed_with_its_judge_held_out_review_and_notes(self) -> None:
        text = self.body([facts(1, notes=["Alpha adds a line nobody asked for."]),
                          facts(2, title="Delete a report", held_out=False)])
        self.assertIn("### Piece 1: Rename a report", text)
        self.assertIn("### Piece 2: Delete a report", text)
        self.assertIn("python3 -m pytest tests/test_rename.py", text)
        self.assertIn("green at the final combined check", text)
        self.assertIn("Held-out: the hidden cases ran at the final check and passed", text)
        self.assertIn("Held-out: none for this piece", text)
        self.assertIn("Review: clean in round 2", text)
        self.assertIn("Alpha adds a line nobody asked for.", text)
        self.assertIn("A Rename item exists.", text)

    def test_worth_knowing_notes_sit_beside_the_piece_they_belong_to(self) -> None:
        text = self.body([facts(1, notes=["note for one"]), facts(2, notes=["note for two"])])
        first, second = text.index("### Piece 1"), text.index("### Piece 2")
        self.assertTrue(first < text.index("note for one") < second < text.index("note for two"))

    def test_there_is_one_closes_line_for_each_piece_and_nothing_else_closes(self) -> None:
        pieces = [facts(1), facts(2), facts(3)]
        text = self.body(pieces, general=["A flaky check, which fixes #4 the day it goes."])
        self.assertEqual(sorted(re.findall(r"^Closes #(\d+)$", text, re.MULTILINE)),
                         ["1", "2", "3"])
        self.assertEqual(closing.scan(title="T", body=text, commits=[], changelog=[],
                                      pieces=[1, 2, 3]), [])

    def test_text_from_a_reviewer_or_a_builder_cannot_close_a_number(self) -> None:
        evil = "Resolves #5 and closes owner/repo#6 and fixes https://github.com/o/r/issues/7"
        text = self.body([facts(1, notes=[evil], title="Fixes #8"), facts(2)],
                         general=[evil])
        self.assertEqual(closing.scan(title="T", body=text, commits=[], changelog=[],
                                      pieces=[1, 2]), [])

    def test_a_piece_the_person_must_look_at_says_why(self) -> None:
        text = self.body([facts(1, must_look=["a sensitive area"])])
        self.assertIn("The person must look at this piece: a sensitive area", text)

    def test_a_stack_says_where_the_docs_commit_comes(self) -> None:
        text = self.body([facts(1)], part=1, parts=3)
        self.assertIn("part 1 of 3", text)
        self.assertIn("docs commit", text)
        self.assertNotIn("part 1 of 1", self.body([facts(1)]))

    def test_the_title_names_the_run_the_pieces_and_the_part(self) -> None:
        title = pr_loop.render_title("r1", [facts(1), facts(2, title="Delete a report")], 2, 3)
        self.assertIn("r1", title)
        self.assertIn("part 2 of 3", title)
        self.assertLessEqual(len(title), 120)
        self.assertEqual(pr_loop.render_title("r1", [facts(1)], 1, 1), "Run r1: Rename a report")

    def test_a_long_title_is_cut_and_a_closing_word_in_it_is_broken(self) -> None:
        title = pr_loop.render_title("r1", [facts(1, title="Closes #9 " + "x" * 300)], 1, 1)
        self.assertLessEqual(len(title), 120)
        self.assertEqual(closing.scan(title=title, body="", commits=[], changelog=[], pieces=[]),
                         [])


class PullPulls(FakePulls):
    """The pull request calls with a state of their own: numbers, heads, comments, closing."""

    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self.repo = repo
        self.next_number = 7
        self.created: list[dict[str, str]] = []
        self.closed: list[tuple[int, str]] = []
        self.bases: list[tuple[int, str]] = []
        self.fail_create = False

    def create(self, *, base: str, head: str, title: str, body: str) -> tuple[int, str]:
        if self.fail_create:
            raise github.GitHubError("GitHub did not answer", next_command="try again")
        number = self.next_number
        self.next_number += 1
        self.created.append({"base": base, "head": head, "title": title, "body": body})
        self.view_of[number] = pulls.PullRequest(
            number=number, url=f"https://github.com/o/r/pull/{number}", state="OPEN",
            title=title, body=body, head_branch=head,
            head_oid=self.repo.git("rev-parse", f"refs/heads/{head}"), base=base)
        return number, self.view_of[number].url

    def close(self, number: int, comment: str) -> None:
        self.closed.append((number, comment))
        self.view_of[number] = dataclasses.replace(self.view_of[number], state="CLOSED")

    def set_base(self, number: int, base: str) -> None:
        self.bases.append((number, base))
        self.view_of[number] = dataclasses.replace(self.view_of[number], base=base)

    def say(self, number: int, text: str, *, author: str = "person",
            association: str = "OWNER") -> None:
        old = self.view_of[number]
        comment = pulls.Comment(100 + len(old.comments), author, text, association)
        self.view_of[number] = dataclasses.replace(old, comments=[*old.comments, comment])

    def merge(self, number: int, *, head_commit: str) -> None:
        super().merge(number, head_commit=head_commit)
        self.view_of[number] = dataclasses.replace(self.view_of[number], state="MERGED",
                                                   merge_commit="c0ffee")


class FakeLoop:
    """What the pull request step asks of the integration loop, read from the real Git."""

    def __init__(self, case: Any) -> None:
        self.case = case
        self.left: list[tuple[int, str]] = []
        self.refreshed: list[tuple[str, str]] = []
        self.branch = "combined-r1"
        self._lock = threading.RLock()

    def tracks(self) -> list[str]:
        return list(self.case.tracks)

    def joined(self, key: str = "main") -> list[int]:
        return [j.piece for j in pr_loop.joins(self.case.paths.root, self.combined(key))]

    def combined(self, key: str = "main") -> str:
        return str(self.case.tracks[key])

    def reader(self, number: int) -> integrate.PieceView:
        piece = self.case.gate.piece(number)
        parsed = spec.parse(piece.body).to_dict()
        return integrate.PieceView(
            number=number, title=piece.title, state=piece.state, issue=piece.issue,
            individual=piece.individual_review, issue_type="feature", spec=parsed,
            record=tuple(piece.record), body=piece.body)

    def leave(self, number: int, reason: str) -> Any:
        self.left.append((number, reason))

    def refresh(self, key: str, reason: str) -> Any:
        self.refreshed.append((key, reason))


class Running(test_moves.Base):  # type: ignore[misc, unused-ignore]
    """Pieces in review, joined on a combined branch, with the pull request step on top."""

    run_name = "r1"
    app = True

    def setUp(self) -> None:
        super().setUp()
        self.gate.loader = GateWith(self.loader)
        self.repo = Repo(self.paths.root)
        self.tracks = {"main": "combined-r1"}
        self.pulls = PullPulls(self.repo)
        self.pushed: list[str] = []
        self.moves_made: list[tuple[int, str, str | None, dict[str, str]]] = []
        for patch in (mock.patch.object(merge_gate, "make_pulls", lambda paths: self.pulls),
                      mock.patch.object(merge_gate, "fetch_main", lambda paths: None)):
            patch.start()
            self.addCleanup(patch.stop)
        self.numbers: list[int] = []

    def build(self, sizes: Sequence[int], *, track: str = "main", branch: str = "combined-r1"
              ) -> list[int]:
        r = self.repo
        numbers: list[int] = []
        for size in sizes:
            number = self.capture()
            self.walk(number, "review")
            numbers.append(number)
            r.branch(f"piece-{number}")
            r.commit(f"src/piece{number}.txt", "line\n" * size)
            r.git("checkout", "-q", "main")
        r.branch(branch, "main")
        for number in numbers:
            r.join(f"piece-{number}", number)
        self.head = r.commit("docs/reports.md", "- the docs (piece 1)\n", "Docs")
        r.git("checkout", "-q", "main")
        if track != "main":
            self.tracks.pop("main", None)
        self.tracks[track] = branch
        self.numbers += numbers
        self.write_run(track, branch, numbers)
        return numbers

    def write_run(self, track: str, branch: str, numbers: Sequence[int], *,
                  pre_approved: bool = False) -> None:
        head = self.repo.git("rev-parse", f"refs/heads/{branch}")
        target = self.paths.run_record(self.run_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(target.read_text()) if target.exists() else {
            "version": 1, "run": self.run_name, "order": [], "pieces": {}, "status": "finished",
            "merge_pre_approved": pre_approved, "decisions": [], "notes": [], "problems": [],
            "integration": {"final": {}, "worth_knowing": []},
            "review": {"tracks": {}, "verdicts": {}}}
        data["merge_pre_approved"] = pre_approved or data["merge_pre_approved"]
        data["order"] = sorted({*data["order"], *numbers})
        for n in numbers:
            data["pieces"][str(n)] = {"status": "built"}
            data["review"]["verdicts"][str(n)] = {"verdict": "clean", "round": 1, "notes": [],
                                                  "findings": []}
        data["integration"]["final"][track] = {
            "status": "green", "head": head, "branch": branch, "checked": {"checks": 4,
                                                                           "held_out": 2}}
        data["review"]["tracks"][track] = {"status": "clean", "reviewed": head, "rounds": 1}
        target.write_text(json.dumps(data))

    def mover(self, number: int, target: str, reason: str | None,
              options: Mapping[str, str]) -> Reply:
        self.moves_made.append((number, target, reason, dict(options)))
        try:
            done = self.gate.move(number, target, reason=reason, options=options)
        except moves.MoveError as error:
            return Reply(3, {"ok": False, "error": error.message, "next": error.next_command})
        return Reply(0, {"ok": True, **done})

    def push(self, branch: str) -> dict[str, Any]:
        self.pushed.append(branch)
        return {}

    def step(self, *, limit: int = 800, app: bool = True) -> pr_loop.PullRequests:
        run = run_record.RunRecord.load(self.paths, self.run_name)
        self.loop = FakeLoop(self)
        made = pr_loop.PullRequests(
            self.paths, self.run_name, run, {"pull_request_size_limit": limit}, self.loop,
            api=self.pulls, mover=self.mover, push=self.push, app=app)
        return made


class OpeningPullRequests(Running):
    def test_a_clean_branch_opens_one_pull_request_with_every_piece(self) -> None:
        numbers = self.build([10, 20])
        report = self.step().open_all()
        self.assertEqual(report[0]["status"], "opened")
        created = self.pulls.created
        self.assertEqual(len(created), 1)
        self.assertEqual((created[0]["base"], created[0]["head"]), ("main", "combined-r1"))
        for number in numbers:
            self.assertEqual(self.gate.piece(number).state, "approval")
            self.assertIn(f"Closes #{self.gate.piece(number).issue}", created[0]["body"])
        self.assertEqual(self.pushed, ["combined-r1"])
        saved = json.loads(self.paths.run_record(self.run_name).read_text())
        self.assertEqual(saved["pull_requests"]["main"]["state"], "open")

    def test_asking_again_opens_nothing_new(self) -> None:
        self.build([10])
        self.step().open_all()
        again = self.step().open_all()
        self.assertEqual(again[0]["status"], "already")
        self.assertEqual(len(self.pulls.created), 1)

    def test_the_body_holds_judge_held_out_review_and_notes_beside_each_piece(self) -> None:
        numbers = self.build([10, 20])
        data = json.loads(self.paths.run_record(self.run_name).read_text())
        data["integration"]["worth_knowing"] = [
            {"text": f"Piece {numbers[0]} also fixes #4 by accident.", "piece": numbers[0],
             "source": "review"},
            {"text": "A flaky check was found, and it resolves #5 by itself.", "source": "run"}]
        data["decisions"] = [{"piece": numbers[1], "by": "builder", "text": "Used a plain file."}]
        self.paths.run_record(self.run_name).write_text(json.dumps(data))
        self.step().open_all()
        body = self.pulls.created[0]["body"]
        first, second = body.index("### Piece"), body.rindex("### Piece")
        self.assertIn("also fixes number 4 by accident", body[first:second])
        self.assertIn("Used a plain file.", body[second:])
        general = body[body.index("## Worth knowing for the whole"):]
        self.assertIn("A flaky check was found", general)
        self.assertIn("Review: clean in round 1", body)
        self.assertIn("Held-out", body)
        self.assertEqual(closing.scan(title="T", body=body, commits=[], changelog=[],
                                      pieces=[self.gate.piece(n).issue for n in numbers]), [])

    def test_a_branch_whose_review_is_not_clean_on_its_head_opens_nothing(self) -> None:
        self.build([10])
        data = json.loads(self.paths.run_record(self.run_name).read_text())
        data["review"]["tracks"]["main"]["status"] = "open"
        self.paths.run_record(self.run_name).write_text(json.dumps(data))
        report = self.step().open_all()
        self.assertEqual(report[0]["status"], "skipped")
        self.assertEqual(self.pulls.created, [])

    def test_with_no_app_nothing_is_pushed_or_opened_and_the_commands_are_named(self) -> None:
        numbers = self.build([10])
        report = self.step(app=False).open_all()
        self.assertEqual(report[0]["status"], "waiting")
        self.assertEqual((self.pushed, self.pulls.created), ([], []))
        command = report[0]["next"]
        self.assertIn("git push origin combined-r1", command)
        self.assertIn("gh pr create --base main --head combined-r1", command)
        self.assertIn("--body-file", command)
        self.assertIn("in their own terminal", command)
        body_file = Path(json.loads(self.paths.run_record(self.run_name).read_text())
                         ["pull_requests"]["main"]["body_file"])
        self.assertIn("Closes #", body_file.read_text())
        self.assertEqual(self.gate.piece(numbers[0]).state, "review", "the piece waits")
        run = json.loads(self.paths.run_record(self.run_name).read_text())
        self.assertEqual(run["pieces"][str(numbers[0])]["github_next"], command)

    def test_a_pull_request_past_the_size_limit_is_split_into_whole_pieces(self) -> None:
        numbers = self.build([30, 30, 30])
        self.step(limit=50).open_all()
        made = self.pulls.created
        self.assertGreaterEqual(len(made), 2)
        held: list[int] = []
        for item in made:
            closes = [int(n) for n in re.findall(r"^Closes #(\d+)$", item["body"], re.MULTILINE)]
            self.assertTrue(closes)
            self.assertTrue(set(closes).isdisjoint(held), "a piece is in two parts")
            held += closes
            self.assertIn("part", item["title"])
        self.assertEqual(sorted(held), sorted(self.gate.piece(n).issue for n in numbers))
        self.assertEqual(made[0]["base"], "main")
        self.assertEqual(made[1]["base"], made[0]["head"], "a part is based on the part before")
        self.assertEqual(made[-1]["head"], "combined-r1")
        first = self.repo.git("rev-parse", f"refs/heads/{made[0]['head']}")
        self.assertEqual(self.repo.git("rev-parse", "refs/heads/combined-r1"), self.head)
        self.assertNotEqual(first, self.head, "the first part is not the whole branch")
        self.assertEqual(self.pushed, [i["head"] for i in made])

    def test_an_isolated_track_gives_each_piece_its_own_pull_request_stacked_in_order(self) -> None:
        numbers = self.build([5, 5], track="piece-1", branch="combined-r1-piece-1")
        self.step().open_all()
        made = self.pulls.created
        self.assertEqual(len(made), 2)
        self.assertEqual(made[0]["base"], "main")
        self.assertEqual(made[1]["base"], made[0]["head"])
        self.assertIn(f"Closes #{self.gate.piece(numbers[0]).issue}", made[0]["body"])
        self.assertNotIn(f"Closes #{self.gate.piece(numbers[1]).issue}", made[0]["body"])

    def test_a_gate_refusal_closes_what_was_opened_and_stops(self) -> None:
        self.build([10])
        self.pulls.view_of.clear()
        run = json.loads(self.paths.run_record(self.run_name).read_text())
        run["review"]["verdicts"]["1"]["verdict"] = "needs-work"
        self.paths.run_record(self.run_name).write_text(json.dumps(run))
        with self.assertRaises(pr_loop.PullRequestRefusal) as caught:
            self.step().open_all()
        self.assertIn("verdict of piece 1", str(caught.exception))
        self.assertEqual(self.pulls.created, [], "the preflight refuses before anything opens")

    def test_the_gate_refusing_after_the_pull_request_opened_closes_it(self) -> None:
        self.build([10])
        step = self.step()
        real = step.mover

        def refuse(number: int, target: str, reason: str | None, options: Any) -> Reply:
            return Reply(3, {"ok": False, "error": "no", "next": "gate.py report"})

        step.mover = refuse
        with self.assertRaises(pr_loop.PullRequestRefusal):
            step.open_all()
        self.assertEqual(len(self.pulls.closed), 1)
        self.assertIn("refused move 10", self.pulls.closed[0][1])
        _ = real

    def test_a_pull_request_that_cannot_be_created_opens_nothing_else(self) -> None:
        self.build([10])
        self.pulls.fail_create = True
        with self.assertRaises(pr_loop.PullRequestRefusal):
            self.step().open_all()
        self.assertEqual(self.gate.piece(1).state, "review")


if __name__ == "__main__":
    unittest.main()
