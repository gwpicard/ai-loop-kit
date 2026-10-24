"""Count all kit Python and guard the file and total line budgets."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOTAL_BUDGET = 7052


def python_lines(root):
    return {path.relative_to(root).as_posix(): len(path.read_text().splitlines())
            for path in sorted(root.rglob("*.py"))}


def check_sizes(counts, total_budget=TOTAL_BUDGET):
    for name, lines in counts.items():
        if lines > 800:
            raise AssertionError(f"{name}: {lines} lines exceeds file budget 800")
    total = sum(lines for name, lines in counts.items()
                if not name.startswith("extras/tests/"))
    if total > total_budget:
        raise AssertionError(f"kit Python total {total} exceeds budget {total_budget}")


class SizeInventoryTest(unittest.TestCase):
    def test_kit_python_budgets_and_install_size(self):
        counts = {f"{owner}/{name}": lines for owner in ("kit", "extras")
                  for name, lines in python_lines(ROOT / owner).items()}
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        plugin = next(p for p in marketplace["plugins"] if p["name"] == "ai-loop-kit")
        installed = python_lines(ROOT / plugin["source"])
        runtime = sum(lines for name, lines in counts.items()
                      if not name.startswith("extras/tests/"))
        print(f"Kit Python total: {runtime} lines; "
              f"default install: {sum(installed.values())} lines", flush=True)
        self.assertTrue(counts, "kit Python inventory must not be empty")
        check_sizes(counts)

    def test_nested_optional_and_quality_files_cannot_escape_the_ceiling(self):
        for name in ("scripts/new.py", "extras/nested/optional.py", "quality/new.py"):
            with self.subTest(path=name), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                path = root / name
                path.parent.mkdir(parents=True)
                path.write_text("# line\n" * 800)
                self.assertEqual(python_lines(root), {name: 800})
                check_sizes(python_lines(root))
                path.write_text("# line\n" * 800 + "# final line")
                with self.assertRaisesRegex(AssertionError, name + ".*801"):
                    check_sizes(python_lines(root))

    def test_extra_tests_keep_the_file_ceiling_outside_the_runtime_total(self):
        counts = {"scripts/runtime.py": 800, "extras/tests/test_critic.py": 800}
        check_sizes(counts, total_budget=800)
        counts["extras/tests/test_critic.py"] = 801
        with self.assertRaisesRegex(AssertionError, "801.*800"):
            check_sizes(counts, total_budget=800)

    def test_total_budget_refuses_growth_across_small_files(self):
        counts = {f"scripts/part{n}.py": 750 for n in range(TOTAL_BUDGET // 750)}
        counts["quality/tail.py"] = TOTAL_BUDGET - sum(counts.values())
        check_sizes(counts)
        counts["extras/new.py"] = 1
        with self.assertRaisesRegex(AssertionError, f"{TOTAL_BUDGET + 1}.*{TOTAL_BUDGET}"):
            check_sizes(counts)


if __name__ == "__main__":
    unittest.main()
