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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import closing  # noqa: E402


class TheClosingWords(unittest.TestCase):
    def scan(self, **more: object) -> list[closing.Fault]:
        given: dict[str, object] = {"title": "A title", "body": "", "commits": [],
                                    "changelog": [], "pieces": []}
        given.update(more)
        return closing.scan(**given)  # type: ignore[arg-type]

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


if __name__ == "__main__":
    unittest.main()
