"""Keep guidance splits within explicit whole-file word budgets."""
from __future__ import annotations

import unittest

from helpers import KIT

# Unchanged guidance keeps its current ceiling until its own thinning slice.
BUDGETS = {
    "briefs/judge-writer.md": 347,
    "briefs/researcher.md": 229,
    "briefs/builder.md": 710,
    "briefs/contract-reviewer.md": 207,
    "extras/briefs/critic.md": 90,
    "briefs/standards-reviewer.md": 372,
    "skills/run/SKILL.md": 314,
    "skills/run/references/walk-away.md": 242,
    "skills/run-recovery/SKILL.md": 213,
    "skills/reject-handling/SKILL.md": 180,
    "skills/setup/SKILL.md": 1327,
    "skills/shape/SKILL.md": 1215,
    "skills/shape/references/questions.md": 244,
    "spec-format.md": 1195,
}
TOTAL_BUDGET = 6694


def check_budgets(texts, budgets=BUDGETS, total_budget=TOTAL_BUDGET):
    for name, text in texts.items():
        if name not in budgets:
            raise AssertionError("guidance files must match the word budget manifest")
        words = len(text.split())
        if words > budgets[name]:
            raise AssertionError(f"{name}: {words} words exceeds budget {budgets[name]}")
    if texts.keys() != budgets.keys():
        raise AssertionError("guidance files must match the word budget manifest")
    if sum(len(text.split()) for text in texts.values()) > total_budget:
        raise AssertionError("guidance exceeds total word budget")


class TextBudgetTest(unittest.TestCase):
    def test_guidance_word_budgets(self):
        paths = [*KIT.joinpath("skills").rglob("*.md"),
                 *KIT.joinpath("briefs").rglob("*.md"),
                 *KIT.joinpath("agents").rglob("*.md"), KIT / "spec-format.md"]
        texts = {str(path.relative_to(KIT)): path.read_text() for path in paths}
        texts["extras/briefs/critic.md"] = (KIT.parent / "extras/briefs/critic.md").read_text()
        check_budgets(texts)

    def test_one_word_overflow_is_refused_for_every_file(self):
        texts = {name: "word " * limit for name, limit in BUDGETS.items()}
        for name in BUDGETS:
            with self.subTest(name=name), self.assertRaisesRegex(AssertionError, name):
                check_budgets(dict(texts, **{name: texts[name] + "overflow"}))

    def test_total_and_unlisted_files_are_refused(self):
        with self.assertRaisesRegex(AssertionError, "total"):
            check_budgets({"a": "one two", "b": "three four"}, {"a": 2, "b": 2}, 3)
        with self.assertRaisesRegex(AssertionError, "manifest"):
            check_budgets({"unlisted.md": "one"}, {}, 3)
        with self.assertRaisesRegex(AssertionError, "manifest"):
            check_budgets({}, {"missing.md": 1}, 3)

    def test_support_skills_are_conditional_and_model_invocable(self):
        parent = (KIT / "skills/run/SKILL.md").read_text()
        for name in ("run-recovery", "reject-handling"):
            with self.subTest(name=name):
                path = KIT / "skills" / name / "SKILL.md"
                text = path.read_text()
                frontmatter = text.split("---", 2)[1]
                self.assertIn(f"name: {name}", frontmatter)
                self.assertIn("description:", frontmatter)
                self.assertIn("user-invocable: false", frontmatter)
                self.assertNotIn("disable-model-invocation: true", frontmatter)
                routes = [line for line in parent.splitlines()
                          if f"../{name}/SKILL.md" in line]
                self.assertEqual(len(routes), 1)
                self.assertTrue(routes[0].startswith("If "))

    def test_run_links_resolve_and_specialist_detail_stays_conditional(self):
        import re

        parent = KIT / "skills/run/SKILL.md"
        text = parent.read_text()
        for target in re.findall(r"\]\(([^)]+)\)", text):
            with self.subTest(target=target):
                self.assertTrue((parent.parent / target).is_file())
        self.assertNotIn("10 GB", text)
        self.assertNotIn("--type judge-gap", text)
        self.assertNotIn("--type conflict", text)
        self.assertIn("If the person will be absent", text)


if __name__ == "__main__":
    unittest.main()
