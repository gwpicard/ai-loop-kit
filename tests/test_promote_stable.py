"""Release promotion checks use a fake GitHub CLI and never write online."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "a" * 40


class PromoteStableTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.gh = self.root / "gh"
        self.log = self.root / "calls"
        self.gh.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$CALLS"
case "$*" in
  *releases/tags/*)
    [ "$SCENARIO" != missing-release ] || exit 1
    case "$SCENARIO" in
      draft|prerelease) echo false ;;
      *) echo true ;;
    esac ;;
  *commits/refs/tags/*)
    [ "$SCENARIO" != missing-tag ] || exit 1
    if [ "$SCENARIO" = mismatch ]; then echo other; else echo "$COMMIT"; fi ;;
  *--method*PATCH*) [ "$SCENARIO" != write-failed ] ;;
  *git/ref/heads/stable*)
    [ "$SCENARIO" != read-failed ] || exit 1
    if [ "$SCENARIO" = no-op ]; then echo old; else echo "$COMMIT"; fi ;;
  *) exit 2 ;;
esac
''')
        self.gh.chmod(0o755)

    def tearDown(self):
        for path in self.root.iterdir():
            path.unlink()
        self.root.rmdir()

    def promote(self, scenario="ok", tag="v1.3.0", commit=COMMIT, repo="owner/repo"):
        return subprocess.run(
            ["sh", str(ROOT / ".agents/tools/promote-stable.sh"), tag, commit],
            env={**os.environ, "PATH": f"{self.root}:{os.environ['PATH']}",
                 "CALLS": str(self.log), "COMMIT": COMMIT,
                 "SCENARIO": scenario, "GITHUB_REPOSITORY": repo},
            capture_output=True, text=True, check=False,
        )

    def test_published_release_moves_only_stable_and_reads_it_back(self):
        result = self.promote()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.log.read_text().splitlines()
        writes = [line for line in calls if "--method" in line]
        self.assertEqual(len(writes), 1)
        self.assertIn("PATCH repos/owner/repo/git/refs/heads/stable", writes[0])
        self.assertIn(f"sha={COMMIT}", writes[0])
        self.assertIn("force=false", writes[0])
        self.assertIn("git/ref/heads/stable", calls[-1])
        self.assertIn(COMMIT, result.stdout)

    def test_unpublished_or_mismatched_tag_never_writes(self):
        for scenario in ("missing-release", "draft", "prerelease", "missing-tag", "mismatch"):
            with self.subTest(scenario=scenario):
                self.log.write_text("")
                result = self.promote(scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("--method", self.log.read_text())

    def test_failed_write_or_readback_cannot_report_success(self):
        for scenario in ("write-failed", "read-failed", "no-op"):
            with self.subTest(scenario=scenario):
                result = self.promote(scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("now points", result.stdout)

    def test_invalid_arguments_never_call_github(self):
        for args in ({"tag": "v1.3.0-dev"}, {"commit": "abc"}, {"repo": ""}):
            with self.subTest(args=args):
                result = self.promote(**args)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.log.exists())
