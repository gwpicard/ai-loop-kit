"""Judge the design through the document a reader opens and its word-count command."""
from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "docs/DESIGN.md"


class CurrentDesignTest(unittest.TestCase):
    def test_design_word_count_is_at_most_2500(self):
        result = subprocess.run(
            ["wc", "-w", "docs/DESIGN.md"], cwd=ROOT,
            capture_output=True, text=True, check=True,
        )
        self.assertLessEqual(int(result.stdout.split()[0]), 2500, result.stdout.strip())

    def test_design_describes_the_current_contract(self):
        document = DESIGN.read_text(encoding="utf-8").replace("`", "")
        text = " ".join(document.split())
        requirements = {
            "release": r"\b3\.0\.0\b",
            "committed settings": r"loop\.json",
            "local overrides": r"loop\.local\.json",
            "local concurrency": r"Parallel",
            "local idle limit": r"Idle hours",
            "plan retirement": r"PLAN\.md",
            "issue permissions heading": r"Protected paths this issue may change",
            "revert check": r"(?i)revert(?:ed)? check|check.{0,100}revert",
            "targeted checks": r"Test files command",
        }
        for meaning, pattern in requirements.items():
            with self.subTest(requirement=meaning):
                self.assertTrue(re.search(pattern, text),
                                "The current design must explain " + meaning)
        paragraphs = [" ".join(part.split()) for part in re.split(r"\n\s*\n", document)]
        with self.subTest(requirement="plan retirement"):
            self.assertTrue(any("PLAN.md" in part and re.search(
                r"(?i)no longer|does not|not read|not use|neither|without|absen", part,
            ) for part in paragraphs), "Explain that the kit does not use PLAN.md")
        restrictions = " ".join(part for part in paragraphs if re.search(
            r"(?i)full (?:Test command|suite)", part,
        ) and re.search(r"(?i)guard|refus|reserv", part))
        for role in (r"builder", r"reviewer", r"test.writer", r"\bpass\b"):
            with self.subTest(restricted_role=role):
                self.assertTrue(re.search(role + r"|all (?:roles|sessions)", restrictions, re.I),
                                "Explain the full-test restriction for " + role)

    def test_history_is_one_pointer_to_tags_and_changelog(self):
        text = DESIGN.read_text(encoding="utf-8")
        headings = re.findall(r"^#{1,6}\s+(.+)$", text, re.M)
        historical = [heading for heading in headings if re.search(
            r"(?i)\b(?:from|earlier|previous|old)\b.*\bversion\b|\bversion\s+[12]\b",
            heading,
        )]
        self.assertEqual(historical, [], "Leave earlier versions in git")
        paragraphs = re.split(r"\n\s*\n", text)
        pointers = [paragraph for paragraph in paragraphs
                    if re.search(r"(?i)\bchangelog\b", paragraph)]
        self.assertEqual(len(pointers), 1, "Point to history once")
        self.assertRegex(pointers[0], r"(?i)\bgit\b")
        self.assertRegex(pointers[0], r"(?i)\btags?\b")

    def test_backticked_static_names_have_repository_evidence(self):
        # Runtime templates and ordinary prose need a read against the code.
        # Static file names, settings and named tools can be checked directly.
        text = DESIGN.read_text(encoding="utf-8")
        sources = [path for folder in ("scripts", "hooks", "bin")
                   for path in (ROOT / "kit" / folder).rglob("*")
                   if path.is_file() and path.suffix in (".py", ".json", "")]
        evidence = "\n".join(path.read_text(encoding="utf-8") for path in sources)
        unknown = []
        for name in set(re.findall(r"`([^`\n]+)`", text)):
            if "<" in name or name.startswith(".loop/"):
                continue
            is_file = re.fullmatch(r"[\w./-]+\.(?:py|md|json)", name)
            is_tool = re.fullmatch(r"[A-Z][a-z]+(?:[A-Z][a-z]+)+", name)
            is_setting = name.endswith(" command")
            if is_file:
                candidates = [ROOT / name, ROOT / "kit" / name,
                              ROOT / "kit/scripts" / name, ROOT / "kit/hooks" / name]
                if not any(path.is_file() for path in candidates) and name not in evidence:
                    unknown.append(name)
            elif (is_tool or is_setting) and name not in evidence:
                unknown.append(name)
        self.assertEqual(sorted(unknown), [], "Backticked names need repository evidence")


if __name__ == "__main__":
    unittest.main()
