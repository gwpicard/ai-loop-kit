"""No instruction tells an agent to run a command the settings refuse.

Only Bash deny rules are checked. Read and Edit rules, and ask rules, are out
of scope.
"""
from __future__ import annotations

import fnmatch
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# A sentence may name a refused command when it gives it to the person or
# says that it is refused.
EXEMPT = re.compile(r"\b(the person|the maintainer|agents cannot|refus(e|es|ed|al)|"
                    r"den(y|ies|ied)|never|blocked)\b", re.IGNORECASE)
CODE = re.compile(r"```[^\n]*\n(.*?)```|`([^`\n]+)`", re.DOTALL)


def instruction_files(root: Path) -> list[Path]:
    files = [root / "AGENTS.md", root / "CLAUDE.md", root / "CONTRIBUTING.md"]
    for folder in (".agents", "kit", "extras"):
        files += sorted((root / folder).rglob("*.md"))
    return [path for path in files if path.is_file()]


def denied_patterns(settings: dict) -> list[str]:
    patterns = []
    for rule in settings.get("permissions", {}).get("deny", []):
        match = re.fullmatch(r"Bash\((.*)\)", rule)
        if match:
            body = match[1]
            patterns.append(body[:-2] + "*" if body.endswith(":*") else body)
    return patterns


def commands(code: str) -> list[str]:
    """Split a chain into commands and drop leading variables and sudo."""
    parts = (re.sub(r"^(?:\w+=\S*\s+|sudo\s+)+", "", part.strip())
             for part in re.split(r"&&|\|\||;|\||\n", code))
    return [part for part in parts if part]


def refused_instructions(text: str, patterns: list[str]) -> list[str]:
    spans: list[str] = []

    def hold(match: re.Match) -> str:
        spans.append(match[1] if match[1] is not None else match[2])
        return f"\0{len(spans) - 1}\0"

    found = []
    for paragraph in re.split(r"\n\s*\n", CODE.sub(hold, text)):
        for sentence in re.split(r"(?<=[.!?])\s+", " ".join(paragraph.split())):
            if EXEMPT.search(sentence):
                continue
            for index in re.findall(r"\0(\d+)\0", sentence):
                found += [command for command in commands(spans[int(index)])
                          if any(fnmatch.fnmatchcase(command, p) for p in patterns)]
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
        hook = "git config core.hooksPath .githooks"
        for text in (f"Run `{hook}` once.",
                     f"Run `git add -A && {hook} && git commit -m x`.",
                     f"Run `git add . && {hook}`.",
                     f"Then run:\n\n```sh\ngit add -A\n{hook}\n```\n",
                     f"Run `X=1 sudo {hook}`.",
                     f"Whenever you start, run `{hook}`."):
            with self.subTest(text=text):
                self.assertEqual(refused_instructions(text, patterns), [hook])
        self.assertEqual(refused_instructions("Then `rm -rf build`.", patterns), ["rm -rf build"])

    def test_a_sentence_for_the_person_or_about_a_refusal_is_allowed(self):
        patterns = ["git config core.hooksPath*", "rm -rf*"]
        for text in ("The person runs `git config core.hooksPath .githooks` once.",
                     "The settings refuse `git config core.hooksPath x`.",
                     "The command was denied: `rm -rf x`."):
            with self.subTest(text=text):
                self.assertEqual(refused_instructions(text, patterns), [])


if __name__ == "__main__":
    unittest.main()

    def test_builder_stops_when_the_approach_breaks_a_test(self):
        brief = " ".join((ROOT / "kit" / "briefs" / "builder.md").read_text().split())
        self.assertIn("would break an existing test or a `(stays)` item", brief)
        self.assertIn("do not choose another rule", brief)
        self.assertIn("`spec-unclear`", brief)
        self.assertNotIn("any choice you made alone", brief)
