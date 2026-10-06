"""Unit tests for kit/scripts/loop/fingerprint.py."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import fingerprint, spec  # noqa: E402

SPEC = """Some header text.

<!-- spec:start version=1 -->
## Goal
Open the menu.

## Judge
Kind: acceptance test
Command: pytest tests/test_menu.py
Proves: FL-1
<!-- spec:end -->

Text after the block.
"""


class Fingerprint(unittest.TestCase):
    def test_same_input_same_fingerprint(self) -> None:
        self.assertEqual(fingerprint.take(SPEC, "c1")["fingerprint"],
                         fingerprint.take(SPEC, "c1")["fingerprint"])

    def test_changes_with_the_spec_block(self) -> None:
        edited = SPEC.replace("Open the menu.", "Close the menu.")
        self.assertNotEqual(fingerprint.take(SPEC, "c1")["fingerprint"],
                            fingerprint.take(edited, "c1")["fingerprint"])

    def test_changes_with_the_judge_commit(self) -> None:
        self.assertNotEqual(fingerprint.take(SPEC, "c1")["fingerprint"],
                            fingerprint.take(SPEC, "c2")["fingerprint"])

    def test_not_with_text_outside_the_block(self) -> None:
        edited = SPEC.replace("Some header text.", "A new title.\nMore.")
        edited = edited.replace("Text after the block.", "Comments here.")
        self.assertEqual(fingerprint.take(SPEC, "c1")["fingerprint"],
                         fingerprint.take(edited, "c1")["fingerprint"])

    def test_not_with_spacing(self) -> None:
        edited = SPEC.replace("Open the menu.", "  Open   the menu.  \n\n")
        self.assertEqual(fingerprint.take(SPEC, "c1")["fingerprint"],
                         fingerprint.take(edited, "c1")["fingerprint"])

    def test_spaces_inside_quoted_command_text_count(self) -> None:
        one = SPEC.replace("Command: pytest tests/test_menu.py", 'Command: grep "a b" menu.txt')
        two = SPEC.replace("Command: pytest tests/test_menu.py", 'Command: grep "a  b" menu.txt')
        self.assertNotEqual(fingerprint.take(one, "c1")["fingerprint"],
                            fingerprint.take(two, "c1")["fingerprint"])
        spaced = SPEC.replace("Command: pytest tests/test_menu.py",
                              '  Command:   grep "a b"   menu.txt  ')
        self.assertEqual(fingerprint.take(one, "c1")["fingerprint"],
                         fingerprint.take(spaced, "c1")["fingerprint"])

    def test_not_with_the_line_the_gate_writes(self) -> None:
        edited = SPEC.replace("Proves: FL-1\n", "Proves: FL-1\nFails today: yes, at abc\n")
        self.assertEqual(fingerprint.take(SPEC, "c1")["fingerprint"],
                         fingerprint.take(edited, "c1")["fingerprint"])

    def test_no_block_is_refused(self) -> None:
        with self.assertRaises(fingerprint.FingerprintError) as caught:
            fingerprint.take("no spec here", "c1")
        self.assertTrue(caught.exception.next_command)

    def test_a_bad_block_raises_the_parser_error(self) -> None:
        with self.assertRaises(spec.SpecError):
            fingerprint.take(SPEC.replace("version=1", "version=9"), "c1")

    def test_result_names_its_parts(self) -> None:
        result = fingerprint.take(SPEC, "c1")
        self.assertEqual(result["judge_commit"], "c1")
        self.assertEqual(len(result["spec"]), 64)
        self.assertEqual(len(result["fingerprint"]), 64)

    def test_parser_keeps_to_dict_keys_and_holds_the_raw_block(self) -> None:
        parsed = spec.parse(SPEC)
        self.assertIn("## Goal", parsed.block)
        self.assertNotIn("block", parsed.to_dict())

    def test_judge_commit_is_the_last_commit_that_touched_the_judge(self) -> None:
        base = Path(tempfile.mkdtemp())
        env = {"GIT_CONFIG_GLOBAL": str(base / "g"), "GIT_CONFIG_SYSTEM": "/dev/null",
               "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@e.com",
               "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@e.com",
               "PATH": "/usr/bin:/bin:/usr/local/bin"}
        (base / "g").write_text("", encoding="utf-8")
        root = base / "p"
        root.mkdir()

        def git(*args: str) -> str:
            return subprocess.run(["git", "-C", str(root), *args], env=env, check=True,
                                  capture_output=True, text=True).stdout.strip()

        git("init", "-q", "-b", "main")
        (root / "t.py").write_text("a", encoding="utf-8")
        (root / "o.py").write_text("a", encoding="utf-8")
        git("add", ".")
        git("commit", "-q", "-m", "one")
        first = git("rev-parse", "HEAD")
        (root / "o.py").write_text("b", encoding="utf-8")
        git("commit", "-q", "-am", "two")
        self.assertEqual(fingerprint.judge_commit(root, "main", ["t.py"]), first)
        (root / "t.py").write_text("b", encoding="utf-8")
        git("commit", "-q", "-am", "three")
        self.assertEqual(fingerprint.judge_commit(root, "main", ["t.py"]), git("rev-parse", "HEAD"))
        with self.assertRaises(fingerprint.FingerprintError):
            fingerprint.judge_commit(root, "main", ["nothing.py"])


if __name__ == "__main__":
    unittest.main()
