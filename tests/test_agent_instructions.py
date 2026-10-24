"""No instruction here tells an agent to run a command the settings refuse."""
from __future__ import annotations

import fnmatch
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# A sentence may name a refused command when it gives it to the person or
# says that it is refused.
EXEMPT = re.compile(r"the person|the maintainer|agents cannot|refuse|den(y|ies)|never|blocked",
                    re.IGNORECASE)


def instruction_files(root: Path) -> list[Path]:
    files = [root / "AGENTS.md", root / "CONTRIBUTING.md", *sorted((root / ".agents").rglob("*.md"))]
    return [path for path in files if path.is_file()]


def denied_patterns(settings: dict) -> list[str]:
    patterns = []
    for rule in settings.get("permissions", {}).get("deny", []):
        match = re.fullmatch(r"Bash\((.*)\)", rule)
        if match:
            body = match[1]
            patterns.append(body[:-2] + "*" if body.endswith(":*") else body)
    return patterns


def refused_instructions(text: str, patterns: list[str]) -> list[str]:
    found = []
    for paragraph in re.split(r"\n\s*\n", text):
        for sentence in re.split(r"(?<=[.!?])\s+", " ".join(paragraph.split())):
            if EXEMPT.search(sentence):
                continue
            for command in re.findall(r"`([^`]+)`", sentence):
                if any(fnmatch.fnmatchcase(command, pattern) for pattern in patterns):
                    found.append(command)
    return found


class AgentInstructionsTest(unittest.TestCase):
    def test_no_instruction_runs_a_refused_command(self):
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
        patterns = denied_patterns(settings)
        self.assertTrue(patterns, "the settings must deny some commands")
        for path in instruction_files(ROOT):
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertEqual(refused_instructions(path.read_text(), patterns), [])

    def test_the_check_catches_a_refused_instruction(self):
        patterns = denied_patterns({"permissions": {"deny": [
            "Bash(git config core.hooksPath*)", "Bash(rm -rf:*)", "Read(.env)"]}})
        self.assertEqual(patterns, ["git config core.hooksPath*", "rm -rf*"])
        text = "Run `git config core.hooksPath .githooks` once.\n\nThen `rm -rf build`."
        self.assertEqual(refused_instructions(text, patterns),
                         ["git config core.hooksPath .githooks", "rm -rf build"])

    def test_a_sentence_for_the_person_or_about_a_refusal_is_allowed(self):
        patterns = ["git config core.hooksPath*"]
        for text in ("The person runs `git config core.hooksPath .githooks` once.",
                     "The settings refuse `git config core.hooksPath x`."):
            with self.subTest(text=text):
                self.assertEqual(refused_instructions(text, patterns), [])


if __name__ == "__main__":
    unittest.main()
