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
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_moves  # type: ignore[import-not-found, unused-ignore]  # noqa: E402
from loop import closing, github, moves, pulls  # noqa: E402
from loop.gates import merge as merge_gate  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
