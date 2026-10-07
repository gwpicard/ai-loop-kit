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

from loop import closing, github, pulls  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
