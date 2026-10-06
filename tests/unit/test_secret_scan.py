"""Unit tests for kit/scripts/secret-scan.py.

No fixture holds a real secret. Each fake key is built at test time from
pieces, so this file does not match any scanner either.
"""

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "kit" / "scripts" / "secret-scan.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("secret_scan", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_keys() -> dict[str, str]:
    """One fake key of each common kind, joined from pieces."""
    filler = "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
    return {
        "aws-access-key": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
        "github-token": "gh" + "p_" + filler,
        "slack-token": "xo" + "xb-" + "1234567890-" + "abcdefghijklmnop",
        "stripe-key": "sk" + "_live_" + filler[:24],
        "google-api-key": "AI" + "za" + filler[:35],
        "anthropic-key": "sk-" + "ant-" + "api03-" + filler + "-" + filler[:20],
        "private-key": "-----BEGIN " + "RSA PRIVATE" + " KEY-----",
        "high-entropy-string": "q8Zk3Vb7Lp2Xw9Rt5Ym1Nc4Hd6Jf0Ga8Se",
    }


def git(cwd: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    done = subprocess.run(
        ["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def scan(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"}
    return subprocess.run(
        ["python3", str(SCRIPT), "--json", *args],
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


class SecretScanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "README.md").write_text("hello\n")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-q", "-m", "start")

    def stage(self, name: str, text: str) -> None:
        (self.repo / name).write_text(text)
        git(self.repo, "add", name)

    def test_each_kind_is_refused_by_file_line_and_kind(self) -> None:
        for kind, value in fake_keys().items():
            with self.subTest(kind=kind):
                self.stage("config.txt", f"first line\nsecond line\nvalue = {value}\n")
                done = scan(self.repo, "--staged")
                self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
                body = json.loads(done.stdout)
                self.assertFalse(body["ok"])
                found = body["findings"]
                self.assertEqual(len(found), 1, found)
                self.assertEqual(found[0]["file"], "config.txt")
                self.assertEqual(found[0]["line"], 3)
                self.assertEqual(found[0]["kind"], kind)
                self.assertIn("next:", done.stderr)

    def test_the_value_is_never_printed(self) -> None:
        for kind, value in fake_keys().items():
            with self.subTest(kind=kind):
                self.stage("config.txt", f"value = {value}\n")
                done = scan(self.repo, "--staged")
                self.assertNotIn(value, done.stdout)
                self.assertNotIn(value, done.stderr)
                body = json.loads(done.stdout)
                self.assertNotIn(value[8:], json.dumps(body))

    def test_a_clean_change_passes(self) -> None:
        self.stage("notes.md", "Nothing secret here.\nsha 0123456789abcdef0123456789abcdef01234567\n")
        done = scan(self.repo, "--staged")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        body = json.loads(done.stdout)
        self.assertTrue(body["ok"])
        self.assertEqual(body["findings"], [])

    def test_a_removed_line_is_not_a_finding(self) -> None:
        value = fake_keys()["github-token"]
        (self.repo / "old.txt").write_text(f"{value}\n")
        git(self.repo, "add", "old.txt")
        git(self.repo, "commit", "-q", "-m", "old")
        (self.repo / "old.txt").write_text("clean\n")
        git(self.repo, "add", "old.txt")
        done = scan(self.repo, "--staged")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_a_range_names_the_commit_file_and_line(self) -> None:
        base = git(self.repo, "rev-parse", "HEAD")
        self.stage("a.txt", "one\n")
        git(self.repo, "commit", "-q", "-m", "a")
        self.stage("b.txt", "x\n" + fake_keys()["aws-access-key"] + "\n")
        git(self.repo, "commit", "-q", "-m", "b")
        git(self.repo, "rm", "-q", "b.txt")
        git(self.repo, "commit", "-q", "-m", "remove b")
        head = git(self.repo, "rev-parse", "HEAD")
        done = scan(self.repo, f"--range={base}..{head}")
        self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
        found = json.loads(done.stdout)["findings"]
        self.assertEqual([(f["file"], f["line"], f["kind"]) for f in found],
                         [("b.txt", 2, "aws-access-key")])

    def test_a_clean_range_passes(self) -> None:
        base = git(self.repo, "rev-parse", "HEAD")
        self.stage("a.txt", "one\n")
        git(self.repo, "commit", "-q", "-m", "a")
        done = scan(self.repo, f"--range={base}..HEAD")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_a_range_cannot_carry_an_option(self) -> None:
        done = scan(self.repo, "--range=HEAD --output=x")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)

    def test_outside_a_repository_it_says_what_to_do(self) -> None:
        outside = Path(tempfile.mkdtemp())
        done = scan(outside)
        self.assertEqual(done.returncode, 4)
        self.assertIn("next:", done.stderr)

    def test_without_gitleaks_it_says_so(self) -> None:
        self.stage("notes.md", "fine\n")
        body = json.loads(scan(self.repo, "--staged").stdout)
        self.assertEqual(body["gitleaks"], "not installed")

    def test_with_gitleaks_its_findings_join_ours(self) -> None:
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        stub = bin_dir / "gitleaks"
        stub.write_text(
            "#!/bin/sh\n"
            'for a in "$@"; do case "$prev" in --report-path) out="$a";; esac; prev="$a"; done\n'
            'printf \'[{"File":"deep.cfg","StartLine":7,"RuleID":"stub-rule"}]\' > "$out"\n'
            "exit 1\n"
        )
        stub.chmod(0o755)
        self.stage("notes.md", "fine\n")
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PATH": f"{bin_dir}:/usr/bin:/bin"}
        done = subprocess.run(
            ["python3", str(SCRIPT), "--json", "--staged"],
            cwd=self.repo,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
        body = json.loads(done.stdout)
        self.assertEqual(body["gitleaks"], "ran")
        self.assertEqual(
            [(f["file"], f["line"], f["kind"]) for f in body["findings"]],
            [("deep.cfg", 7, "gitleaks:stub-rule")],
        )

    def test_scan_diff_reads_added_lines_only(self) -> None:
        module = load()
        value = fake_keys()["stripe-key"]
        diff = (
            "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1,2 +10,2 @@\n"
            f"-old = '{value}'\n+ok = 1\n+new = '{value}'\n"
        )
        found = module.scan_diff(diff)
        self.assertEqual([(f.file, f.line, f.kind) for f in found], [("x.py", 11, "stripe-key")])


if __name__ == "__main__":
    unittest.main()
