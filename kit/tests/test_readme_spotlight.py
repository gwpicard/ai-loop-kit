"""The Mac setup advice belongs beside the loop's headroom explanation."""
from pathlib import Path
import re
import unittest


README = Path(__file__).resolve().parents[1] / "README.md"


class SpotlightReadmeTest(unittest.TestCase):
    def paragraphs(self):
        return [" ".join(p.split()).replace("`", "").lower()
                for p in re.split(r"\n\s*\n", README.read_text(encoding="utf-8"))]

    def spotlight_paragraph(self):
        paragraphs = self.paragraphs()
        matches = [p for p in paragraphs if "spotlight" in p]
        self.assertTrue(matches, "The README needs a paragraph about Spotlight indexing")
        return matches[0]

    def test_mac_exclusion_instructions_are_beside_load_and_memory(self):
        paragraph = self.spotlight_paragraph()
        self.assertLessEqual(len(paragraph.split()), 110, "Keep the advice to a short paragraph")
        for pattern in (r"\bmac(?:os)?\b", r"index", r"every|each|all",
                        r"new", r"worktree", r"\blog", r"test repositor",
                        r"loop", r"creat", r"\badd\b", r"projects",
                        r"\.loop-worktrees", r"parent folder|parent directory",
                        r"default"):
            with self.subTest(content=pattern):
                self.assertRegex(paragraph, pattern)
        self.assertRegex(paragraph, r"system settings.*spotlight.*search privacy")
        paragraphs = self.paragraphs()
        advice = paragraphs.index(paragraph)
        headroom = [i for i, p in enumerate(paragraphs)
                    if "load average" in p and "memory pressure" in p]
        self.assertTrue(headroom, "Keep the existing load and memory explanation")
        self.assertTrue(any(abs(advice - i) <= 1 for i in headroom),
                        "Put the Spotlight advice next to the load and memory explanation")

    def test_advice_explains_the_visible_symptoms_and_second_build_delay(self):
        paragraph = self.spotlight_paragraph()
        for pattern in (r"\bmds_stores\b", r"\bmds\b", r"activity monitor",
                        r"(?:near|at|towards).*top", r"high.*load average|load average.*high",
                        r"(?:second|another) build",
                        r"hold.*back|held back|delay|defer|wait|prevent|block",
                        r"without|otherwise|unless"):
            with self.subTest(content=pattern):
                self.assertRegex(paragraph, pattern)


if __name__ == "__main__":
    unittest.main()
