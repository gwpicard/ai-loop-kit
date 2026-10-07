"""Unit tests for P26: closing words, the merge gate, the pull request and `check-main`.

Built in groups. The first group holds the closing-word scan, which refuses a closing word
before any number the pull request does not own. Issue numbers are written with a single digit
here, so this file passes the house rule that no tracked file cites a number by a hash and
two or more digits.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_moves  # type: ignore[import-not-found, unused-ignore]  # noqa: E402
from loop import closing, github, moves, pulls  # noqa: E402
from loop.gates import merge as merge_gate  # noqa: E402
from loop.gates import recheck as recheck_gate  # noqa: E402
from loop.gates import review as review_gate  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
