"""Unit tests for kit/scripts/secret-scan.py.

No fixture holds a real secret. Each fake key is built at test time from
pieces, so this file does not match any scanner either.
"""

import base64
import importlib.util
import json
import os
import random
import shutil
import string
import subprocess
import sys
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
    sys.modules["secret_scan"] = module
    spec.loader.exec_module(module)
    return module


ALNUM = string.ascii_letters + string.digits


def random_text(seed: int, length: int, alphabet: str = ALNUM) -> str:
    """Random text made at test time, so no file here holds a high-entropy value."""
    rng = random.Random(seed)
    while True:
        text = "".join(rng.choice(alphabet) for _ in range(length))
        if any(c.isdigit() for c in text) and any(c.isalpha() for c in text):
            return text


def aws_secret(seed: int = 5) -> str:
    """A 40 character AWS style secret that holds a slash and a plus."""
    body = random_text(seed, 38)
    return body[:10] + "/" + body[10:25] + "+" + body[25:]


def fake_keys() -> dict[str, str]:
    """One fake key of each common kind, made at test time."""
    filler = "AbCdEf" * 6  # low entropy, so only the key shape matches
    return {
        "aws-access-key": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
        "github-token": "gh" + "p_" + filler,
        "slack-token": "xo" + "xb-" + "1234567890-" + "abcdefghijklmnop",
        "stripe-key": "sk" + "_live_" + filler[:24],
        "google-api-key": "AI" + "za" + filler[:35],
        "anthropic-key": "sk-" + "ant-" + "api03-" + filler + "-" + filler[:20],
        "private-key": "-----BEGIN " + "RSA PRIVATE" + " KEY-----",
        "aws-secret-key": "aws_secret_access_key = " + aws_secret(),
        "high-entropy-string": random_text(1, 36),
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
        sha = "0123456789abcdef" * 2 + "01234567"
        self.stage("notes.md", f"Nothing secret here.\nsha {sha}\n")
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
        self.assertEqual(
            [(f["file"], f["line"], f["kind"]) for f in found], [("b.txt", 2, "aws-access-key")]
        )

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

    def test_a_line_that_looks_like_a_header_is_still_scanned(self) -> None:
        value = fake_keys()["github-token"]
        for prefix in ("++ ", "+ ", "++ b/x ", "-- "):
            with self.subTest(prefix=prefix):
                self.stage("odd.md", f"fine\n{prefix}{value}\n")
                done = scan(self.repo, "--staged")
                self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
                found = json.loads(done.stdout)["findings"]
                self.assertEqual([(f["file"], f["line"]) for f in found], [("odd.md", 2)])

    def test_the_diff_is_read_by_hunk_not_by_prefix(self) -> None:
        module = load()
        value = fake_keys()["stripe-key"]
        diff = (
            "diff --git a/x.md b/x.md\n--- a/x.md\n+++ b/x.md\n@@ -0,0 +1,2 @@\n"
            f"+++ b/fake.txt\n+x {value}\n"
            "diff --git a/y.md b/y.md\n--- a/y.md\n+++ b/y.md\n@@ -0,0 +1 @@\n+fine\n"
        )
        found = module.scan_diff(diff)
        self.assertEqual([(f.file, f.line, f.kind) for f in found], [("x.md", 2, "stripe-key")])

    def test_lockfile_hashes_do_not_block(self) -> None:
        sri = "sha512-" + base64.b64encode(random.Random(3).randbytes(64)).decode()
        sri256 = "sha256-" + base64.b64encode(random.Random(4).randbytes(32)).decode()
        hex_hash = random_text(6, 64, "0123456789abcdef")
        lines = {
            "package-lock.json": [
                f'      "integrity": "{sri}",',
                f'      "resolved": "https://registry.npmjs.org/a/-/a-1.0.0.tgz#{hex_hash[:40]}",',
            ],
            "pnpm-lock.yaml": [
                f"    resolution: {{integrity: {sri}}}",
                f"    resolution: {{integrity: {sri256}, tarball: https://x.test/a.tgz}}",
            ],
            "uv.lock": [
                f'sdist = {{ url = "https://x.test/a.tar.gz", hash = "sha256:{hex_hash}" }}',
            ],
            "yarn.lock": [f"  integrity {sri}", f"  checksum {hex_hash}"],
        }
        for name, rows in lines.items():
            for row in rows:
                with self.subTest(file=name, row=row[:30]):
                    self.stage(name, "first\n" + row + "\n")
                    done = scan(self.repo, "--staged")
                    self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        # The same line in any other file still blocks.
        self.stage("notes.json", f'      "integrity": "{sri}",\n')
        self.assertEqual(scan(self.repo, "--staged").returncode, 3)

    def test_a_link_slug_is_not_a_secret(self) -> None:
        slug = "2026-03-24-durable-execution-background-work-ai-agent-runtimes"
        self.stage("notes.md", f"see https://example.test/research/{slug}\n")
        done = scan(self.repo, "--staged")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        # Mixed case or a missing hyphen pattern is still scanned.
        self.stage("notes.md", f"token {random_text(12, 40)}\n")
        self.assertEqual(scan(self.repo, "--staged").returncode, 3)

    def test_a_lockfile_still_blocks_a_real_secret(self) -> None:
        token = fake_keys()["github-token"]
        self.stage("package-lock.json", f'  "resolved": "https://u:{token}@host/a.tgz",\n')
        self.assertEqual(scan(self.repo, "--staged").returncode, 3)
        loose = random_text(8, 40)
        self.stage("package-lock.json", f'  "note": "{loose}",\n')
        self.assertEqual(scan(self.repo, "--staged").returncode, 3)

    def test_an_aws_secret_with_a_slash_or_a_plus_is_caught(self) -> None:
        for name, value in (
            ("bare", aws_secret(5)),
            ("slash", random_text(7, 19) + "/" + random_text(9, 20)),
            ("plus", random_text(10, 19) + "+" + random_text(11, 20)),
        ):
            with self.subTest(name=name):
                self.stage("c.env", f"x = {value}\n")
                done = scan(self.repo, "--staged")
                self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
                self.assertNotIn(value, done.stdout + done.stderr)

    def test_gitleaks_that_fails_without_a_report_fails_closed(self) -> None:
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        for name, body in (("silent", "exit 2\n"), ("junk", 'echo junk > "$4"; exit 2\n')):
            stub = bin_dir / "gitleaks"
            stub.write_text("#!/bin/sh\n" + body)
            stub.chmod(0o755)
            with self.subTest(stub=name):
                self.stage("notes.md", "fine\n")
                env = {**os.environ, "PATH": f"{bin_dir}:/usr/bin:/bin"}
                done = subprocess.run(
                    ["python3", str(SCRIPT), "--json", "--staged"],
                    cwd=self.repo, env=env, check=False, capture_output=True, text=True,
                )
                self.assertEqual(done.returncode, 4, done.stdout + done.stderr)
                self.assertIn("gitleaks", done.stderr)
                self.assertIn("next:", done.stderr)

    def commit_message(self, text: str) -> str:
        message = self.tmp / "message.txt"
        message.write_text(text)
        git(self.repo, "commit", "-q", "--allow-empty", "--file", str(message))
        return git(self.repo, "rev-parse", "HEAD")

    def test_cr21_known_message_shapes_refuse_without_gitleaks(self) -> None:
        filler = "AbCdEf" * 9
        cases = [(kind, value) for kind, value in fake_keys().items()
                 if kind != "high-entropy-string"]
        cases += [
            ("openai-key", "sk-" + filler),
            ("openai-key", "sk-" + "proj-" + filler),
            ("aws-access-key", "AS" + "IA" + "ABCDEFGHIJKLMNOP"),
            ("github-token", "github" + "_pat_" + filler),
            ("stripe-key", "rk" + "_test_" + filler),
            ("private-key", "-----BEGIN " + "PGP PRIVATE" + " KEY BLOCK-----"),
        ]
        cases += [("github-token", "gh" + variant + "_" + filler)
                  for variant in "ousr"]
        cases += [("slack-token", "xo" + "x" + variant + "-" + filler)
                  for variant in "aprs"]
        for kind, value in cases:
            for line, message in ((1, value + "\n"),
                                  (4, "Synthetic heading\n\ncontext\n" + value + "\n")):
                with self.subTest(kind=kind, line=line):
                    base = git(self.repo, "rev-parse", "HEAD")
                    head = self.commit_message(message)
                    done = scan(self.repo, f"--range={base}..{head}")
                    self.assertEqual(done.returncode, 3, "CR-21: message must refuse")
                    body = json.loads(done.stdout)
                    self.assertEqual(body["gitleaks"], "not installed")
                    self.assertEqual(body["findings"], [
                        {"file": f"commit-message:{head}", "line": line, "kind": kind}
                    ])
                    self.assertTrue(value not in done.stdout + done.stderr,
                                    "CR-21: JSON refusal must redact message values")
                    env = {**os.environ, "PATH": "/usr/bin:/bin"}
                    plain = subprocess.run(
                        ["python3", str(SCRIPT), f"--range={base}..{head}"],
                        cwd=self.repo, env=env, capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(plain.returncode, 3, "CR-21: text must refuse")
                    self.assertTrue(value not in plain.stdout + plain.stderr,
                                    "CR-21: text refusal must redact message values")

    def test_cr21_later_clean_commit_and_diff_like_message_do_not_hide_hit(self) -> None:
        base = git(self.repo, "rev-parse", "HEAD")
        value = fake_keys()["github-token"]
        message = "Synthetic heading\n\ndiff --git a/a b/a\n+++ b/package-lock.json\n" + value
        head = self.commit_message(message)
        self.commit_message("Later clean message")
        done = scan(self.repo, f"--range=HEAD --not {base}")
        self.assertEqual(done.returncode, 3, "CR-21: every selected message must be scanned")
        self.assertEqual(json.loads(done.stdout)["findings"], [
            {"file": f"commit-message:{head}", "line": 5, "kind": "github-token"}
        ])
        self.assertTrue(value not in done.stdout + done.stderr, "CR-21: redact values")

    def test_cr21_merge_commit_message_is_scanned(self) -> None:
        base = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "branch", "side")
        self.commit_message("First parent")
        first = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "checkout", "-q", "side")
        side = self.commit_message("Second parent")
        value = fake_keys()["github-token"]
        message = self.tmp / "merge-message.txt"
        message.write_text("Merge context\n\n" + value + "\n")
        merge = git(self.repo, "commit-tree", "HEAD^{tree}", "-p", first, "-p", side,
                    "-F", str(message))
        done = scan(self.repo, f"--range={base}..{merge}")
        self.assertEqual(done.returncode, 3, "CR-21: merge message must refuse")
        self.assertEqual(json.loads(done.stdout)["findings"], [
            {"file": f"commit-message:{merge}", "line": 3, "kind": "github-token"}
        ])
        self.assertTrue(value not in done.stdout + done.stderr, "CR-21: redact values")

    def test_cr21_clean_ambiguous_message_and_staged_scan_stay_clean(self) -> None:
        base = git(self.repo, "rev-parse", "HEAD")
        self.commit_message('Clean heading\n\npassword = "example"\n' + random_text(18, 48))
        self.stage("fine.txt", "clean change\n")
        for option in (f"--range={base}..HEAD", "--staged"):
            done = scan(self.repo, option)
            self.assertEqual(done.returncode, 0, "CR-21: clean messages must pass")
            self.assertEqual(json.loads(done.stdout)["findings"], [])

    def test_help_names_what_the_scan_misses(self) -> None:
        done = subprocess.run(
            ["python3", str(SCRIPT), "--help"], check=False, capture_output=True, text=True
        )
        text = " ".join(done.stdout.split())
        for phrase in ("commit message", "split across lines", "password", "64", "lockfile"):
            self.assertIn(phrase, text)
        self.assertIn("not covered yet", text)

    def test_the_scan_passes_every_file_of_this_repository(self) -> None:
        names = git(ROOT, "ls-files", "-co", "--exclude-standard", "-z").split("\0")
        copy = self.tmp / "copy"
        copy.mkdir()
        git(copy, "init", "-q", "-b", "main")
        for name in filter(None, names):
            source = ROOT / name
            if not source.is_file() and not source.is_symlink():
                continue
            target = copy / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target, follow_symlinks=False)
        git(copy, "add", "-A")
        done = scan(copy, "--staged")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
