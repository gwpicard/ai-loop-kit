"""The kit's instructions send tests through the entry point a person uses."""
import os
import unittest

import flow

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS = {"Loop branch": "loop/main", "Test command": "true", "Test files command": "",
            "Check command": ""}


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def prompt(role):
    return flow.prompt_for(role, 1, {"title": "t", "body": "b"}, "/tmp/tree", SETTINGS, [])


class EntryPointTest(unittest.TestCase):
    def test_no_brief_repeats_enforced_rules(self):
        from pathlib import Path
        for path in Path(flow.BRIEFS).glob("*.md"):
            self.assertNotIn("Hard rules", path.read_text(), path.name)

    def test_template_names_the_entry_point(self):
        text = read("kit", "templates", "issue.md").lower()
        self.assertIn("entry point", text)
        for example in ("keys pressed", "menu item", "command run", "http route"):
            self.assertIn(example, text)

    def test_shape_oracle_step_asks_for_the_entry_point(self):
        text = read("kit", "skills", "shape", "SKILL.md")
        step = text[text.index("\n5. Ask the oracle question"):]
        step = step[:step.index("\n6.")] if "\n6." in step else step
        self.assertIn("entry point", step.lower())

    def test_test_writer_prompt_drives_the_entry_point(self):
        text = " ".join(prompt("test-writer").lower().split())
        self.assertIn("entry point", text)
        self.assertIn("internal", text)
        self.assertIn("more than one example input", text)
        self.assertIn("layout", text)

    def test_reviewer_prompt_returns_changes_for_bypassed_entry_point(self):
        text = " ".join(prompt("reviewer").lower().split())
        self.assertIn("entry point", text)
        self.assertIn("internal", text)
        self.assertIn("layout", text)
        self.assertRegex(text, r"changes[^.]*(entry point|internal)|(entry point|internal)[^.]*changes")


if __name__ == "__main__":
    unittest.main()
