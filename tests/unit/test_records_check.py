"""Unit tests for loop/records.py: the checks that hold the records model."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

from loop import records  # noqa: E402

AREA_MAP = """# the map
docs/ project-records
src/ app
tests/ app
src/billing/ billing
"""

OVERVIEW = """# Shop

What the product is, and who it is for.

## Areas

| Area | Purpose | Sensitive | Boundary | Doc |
| --- | --- | --- | --- | --- |
| project-records | The records | no | | `docs/README.md` |
| app | The shop | no | | `docs/app.md` |
| billing | Payments | yes | Only `src/billing/` takes card data | `docs/billing.md` |
"""

AGENTS = """# AGENTS.md

## Commands

- `tests/run-all.sh`: run every check.

## Where to read next

Read `docs/overview.md`, then `docs/area-map`.
"""

PARAGRAPH = (
    "To release the tool, first make sure the environment file holds the database address "
    "and the payment key. Then run the release script from the project root, wait for the "
    "health check to pass, and tell the team in the channel that the new version is live. "
    "If the health check fails, roll back to the previous release."
)

CHANGELOG = """# Changelog

## 2026-10-06

### Added

- Refunds. ([piece 12](https://example.invalid/issues/12))
"""


def lines(count: int, prefix: str = "line") -> str:
    return "\n".join(f"{prefix} {n}" for n in range(count)) + "\n"


def good_files() -> dict[str, str]:
    return {
        "AGENTS.md": AGENTS,
        "CLAUDE.md": "@AGENTS.md\n",
        "CHANGELOG.md": CHANGELOG,
        "tests/run-all.sh": "#!/bin/sh\n",
        "docs/area-map": AREA_MAP,
        "docs/overview.md": OVERVIEW,
        "docs/README.md": "# Docs\n\n- `app.md`: the shop.\n- `billing.md`: payments.\n",
        "docs/app.md": "# App\n\n- It sells things.\n",
        "docs/billing.md": "# Billing\n\n- It takes payment.\n",
        "src/index.js": "1;\n",
        "src/billing/pay.js": "1;\n",
    }


class Project:
    """A throwaway Git project that holds `files`."""

    def __init__(self, files: dict[str, str]) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.git("init", "-q", "-b", "main")
        self.save(files)

    def git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=T", "-c", "user.email=t@example.invalid",
             "-c", "commit.gpgsign=false", *args],
            check=True,
            capture_output=True,
        )

    def save(self, files: dict[str, str]) -> None:
        for name, text in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "save", "--allow-empty")

    def rules(self, closing: tuple[int, ...] = ()) -> set[str]:
        return {fault.rule for fault in records.check(self.root, closing=closing)}

    def close(self) -> None:
        self._tmp.cleanup()


class Base(unittest.TestCase):
    def project(self, **changes: str) -> Project:
        files = good_files()
        files.update(changes)
        made = Project(files)
        self.addCleanup(made.close)
        return made


class GoodProject(Base):
    def test_a_true_project_has_no_fault(self) -> None:
        made = self.project()
        self.assertEqual(records.check(made.root), [])

    def test_a_closed_piece_with_an_entry_passes(self) -> None:
        self.assertEqual(records.check(self.project().root, closing=(12,)), [])


class AgentsMd(Base):
    def test_over_150_lines_fails(self) -> None:
        text = "# AGENTS.md\n\n" + "".join(f"## S{n}\n\n- a\n\n" for n in range(40))
        self.assertGreater(len(text.splitlines()), 150)
        self.assertIn("agents.lines", self.project(**{"AGENTS.md": text}).rules())

    def test_exactly_150_lines_passes(self) -> None:
        text = "# AGENTS.md\n\n" + "".join(f"## S{n}\n\n- a\n\n" for n in range(37))
        text = "\n".join(text.splitlines()[:150]) + "\n"
        self.assertEqual(len(text.splitlines()), 150)
        self.assertNotIn("agents.lines", self.project(**{"AGENTS.md": text}).rules())

    def test_a_section_over_12_lines_fails(self) -> None:
        text = "# AGENTS.md\n\n## Rules\n\n" + lines(13, "- rule")
        found = records.check(self.project(**{"AGENTS.md": text}).root)
        self.assertIn("agents.section", {f.rule for f in found})
        self.assertTrue(any("Rules" in f.message for f in found))

    def test_a_section_of_12_lines_passes(self) -> None:
        text = "# AGENTS.md\n\n## Rules\n\n" + lines(12, "- rule")
        self.assertNotIn("agents.section", self.project(**{"AGENTS.md": text}).rules())

    def test_blank_lines_do_not_count_toward_a_section(self) -> None:
        body = "\n\n".join(f"- rule {n}" for n in range(8))
        text = f"# AGENTS.md\n\n## Rules\n\n{body}\n"
        self.assertNotIn("agents.section", self.project(**{"AGENTS.md": text}).rules())

    def test_a_missing_file_fails(self) -> None:
        made = self.project()
        made.git("rm", "-q", "AGENTS.md")
        self.assertIn("agents.missing", made.rules())

    def test_a_path_it_names_that_does_not_exist_fails(self) -> None:
        text = AGENTS + "\nRun `scripts/deploy.sh` to ship.\n"
        found = records.check(self.project(**{"AGENTS.md": text}).root)
        self.assertIn("names", {f.rule for f in found})
        self.assertTrue(any("scripts/deploy.sh" in f.message for f in found))

    def test_a_command_it_names_that_does_not_exist_fails(self) -> None:
        text = AGENTS + "\nStart it with `npm run serve`.\n"
        made = self.project(**{"AGENTS.md": text, "package.json": '{"scripts":{"dev":"x"}}\n'})
        self.assertIn("names", made.rules())

    def test_a_placeholder_is_not_a_missing_name(self) -> None:
        text = AGENTS + "\nRun `<test command>` before a push.\n"
        self.assertNotIn("names", self.project(**{"AGENTS.md": text}).rules())

    def test_claude_md_must_only_import_agents_md(self) -> None:
        made = self.project(**{"CLAUDE.md": "@AGENTS.md\n\nAlso be kind.\n"})
        self.assertIn("claude.import", made.rules())

    def test_a_missing_claude_md_fails(self) -> None:
        made = self.project()
        made.git("rm", "-q", "CLAUDE.md")
        self.assertIn("claude.import", made.rules())


class Overview(Base):
    def test_over_100_lines_fails(self) -> None:
        text = OVERVIEW + "\n" + "".join(f"Paragraph {n}.\n\n" for n in range(50))
        self.assertGreater(len(text.splitlines()), 100)
        self.assertIn("overview.lines", self.project(**{"docs/overview.md": text}).rules())

    def test_a_missing_overview_fails(self) -> None:
        made = self.project()
        made.git("rm", "-q", "docs/overview.md")
        self.assertIn("overview.missing", made.rules())

    def test_an_area_the_map_does_not_have_fails(self) -> None:
        text = OVERVIEW + "| ghost | Nothing | no | | `docs/app.md` |\n"
        found = records.check(self.project(**{"docs/overview.md": text}).root)
        self.assertIn("overview.area", {f.rule for f in found})
        self.assertTrue(any("ghost" in f.message for f in found))

    def test_an_area_the_overview_does_not_name_fails(self) -> None:
        text = OVERVIEW.replace("| billing | Payments | yes | Only `src/billing/` takes card data "
                                "| `docs/billing.md` |\n", "")
        found = records.check(self.project(**{"docs/overview.md": text}).root)
        self.assertIn("overview.area", {f.rule for f in found})
        self.assertTrue(any("billing" in f.message for f in found))

    def test_a_flag_that_is_not_yes_or_no_fails(self) -> None:
        text = OVERVIEW.replace("| Payments | yes |", "| Payments | maybe |")
        self.assertIn("overview.sensitive", self.project(**{"docs/overview.md": text}).rules())

    def test_a_sensitive_area_with_no_boundary_fails(self) -> None:
        text = OVERVIEW.replace("Only `src/billing/` takes card data", "")
        self.assertIn("overview.sensitive", self.project(**{"docs/overview.md": text}).rules())

    def test_no_area_table_fails(self) -> None:
        self.assertIn("overview.area", self.project(**{"docs/overview.md": "# Shop\n"}).rules())

    def test_the_overview_naming_a_missing_file_fails(self) -> None:
        text = OVERVIEW + "\nSee `docs/missing-note.md` for more.\n"
        self.assertIn("names", self.project(**{"docs/overview.md": text}).rules())


class AreaDocs(Base):
    def test_an_area_doc_over_300_lines_fails(self) -> None:
        made = self.project(**{"docs/app.md": "# App\n\n" + lines(300)})
        self.assertIn("docs.lines", made.rules())

    def test_an_area_doc_of_300_lines_passes(self) -> None:
        made = self.project(**{"docs/app.md": "# App\n\n" + lines(298)})
        self.assertNotIn("docs.lines", made.rules())

    def test_an_area_doc_that_does_not_exist_fails(self) -> None:
        made = self.project()
        made.git("rm", "-q", "docs/billing.md")
        self.assertIn("docs.missing", made.rules())


class AreaMap(Base):
    def test_a_tracked_file_in_no_area_fails(self) -> None:
        made = self.project(**{"scripts/run.py": "1\n"})
        found = records.check(made.root)
        self.assertIn("areas", {f.rule for f in found})
        self.assertTrue(any("scripts/run.py" in f.message for f in found))

    def test_an_area_that_matches_nothing_fails(self) -> None:
        made = self.project(**{"docs/area-map": AREA_MAP + "lib/ library\n"})
        self.assertIn("areas", made.rules())

    def test_a_missing_map_fails(self) -> None:
        made = self.project()
        made.git("rm", "-q", "docs/area-map")
        self.assertIn("areas", made.rules())

    def test_an_untracked_file_is_not_a_fault(self) -> None:
        made = self.project()
        (made.root / "scripts").mkdir()
        (made.root / "scripts" / "run.py").write_text("1\n", encoding="utf-8")
        self.assertNotIn("areas", made.rules())


class Changelog(Base):
    def test_a_closed_piece_with_no_entry_fails(self) -> None:
        made = self.project()
        found = records.check(made.root, closing=(13,))
        self.assertIn("changelog.entry", {f.rule for f in found})
        self.assertTrue(any("13" in f.message for f in found))

    def test_a_piece_number_inside_another_number_is_no_entry(self) -> None:
        made = self.project()
        self.assertIn("changelog.entry", made.rules(closing=(1,)))

    def test_the_number_in_a_link_counts(self) -> None:
        text = CHANGELOG + "\n- Search. (https://example.invalid/issues/14)\n"
        made = self.project(**{"CHANGELOG.md": text})
        self.assertNotIn("changelog.entry", made.rules(closing=(14,)))

    def test_a_missing_changelog_fails(self) -> None:
        made = self.project()
        made.git("rm", "-q", "CHANGELOG.md")
        self.assertIn("changelog.missing", made.rules())

    def test_no_closed_piece_needs_no_entry(self) -> None:
        self.assertNotIn("changelog.entry", self.project().rules())


class Repeats(Base):
    def test_a_paragraph_repeated_across_records_fails(self) -> None:
        made = self.project(
            **{
                "AGENTS.md": AGENTS + "\n" + PARAGRAPH + "\n",
                "docs/app.md": "# App\n\n" + PARAGRAPH + "\n",
            }
        )
        found = records.check(made.root)
        self.assertIn("repeat", {f.rule for f in found})

    def test_a_note_nothing_names_is_not_a_fault_here(self) -> None:
        made = self.project(**{"docs/loose.md": "# Loose\n\nOne short note.\n"})
        self.assertNotIn("repeat", made.rules())


class Report(Base):
    def test_a_fault_says_where_and_what_to_do(self) -> None:
        text = "# AGENTS.md\n\n## Rules\n\n" + lines(13, "- rule")
        fault = records.check(self.project(**{"AGENTS.md": text}).root)[0]
        self.assertEqual(fault.where.split(":")[0], "AGENTS.md")
        self.assertTrue(fault.message)
        self.assertTrue(fault.next_step)


if __name__ == "__main__":
    unittest.main()
