"""Installed optional tooling stays local, bounded and outside founding requirements."""

import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "kit" / "scripts" / "check-tooling.sh"


class OptionalTooling(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="optional-tooling-")
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.project.mkdir()
        self.bin = self.base / "bin"
        self.bin.mkdir()
        for name in ("git", "openssl", "sh"):
            installed = shutil.which(name)
            assert installed is not None
            (self.bin / name).symlink_to(installed)
        (self.bin / "python3").symlink_to(sys.executable)
        self.env = {**os.environ, "PATH": str(self.bin),
                    "AI_LOOP_KIT_DATA": str(self.base / "data"),
                    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
        subprocess.run(["git", "init", "-q", str(self.project)], check=True, env=self.env)
        subprocess.run(["git", "-C", str(self.project), "remote", "add", "origin",
                        str(self.base / "origin.git")], check=True, env=self.env)
        self.retired_groups: set[int] = set()
        self.npx_log = self.base / "npx.log"
        self.write(self.bin / "npx", f"echo called >> '{self.npx_log}'\nexit 1\n")

    def tearDown(self) -> None:
        for name in ("parent.pid", "child.pid"):
            path = self.base / name
            if path.exists():
                identity = json.loads(path.read_text())
                pid, group = identity["pid"], identity["pgid"]
                if group in self.retired_groups:
                    continue
                status = subprocess.run(["/bin/ps", "-o", "stat=", "-p", str(pid)],
                                        capture_output=True, text=True, check=False)
                if not status.stdout.strip() or status.stdout.strip().startswith("Z"):
                    continue
                command = subprocess.run(["/bin/ps", "-o", "command=", "-p", str(pid)],
                                         capture_output=True, text=True, check=False)
                marker = str(path) if name == "child.pid" else str(self.bin / "playwright")
                self.assertIn(marker, command.stdout, "refuse cleanup of an unknown process")
                try:
                    self.assertEqual(os.getpgid(pid), group)
                    self.assertEqual(os.getsid(pid), identity["sid"])
                    self.assertEqual(group, identity["sid"], "fixture owns an isolated group")
                    os.killpg(group, signal.SIGKILL)
                    self.retired_groups.add(group)
                except ProcessLookupError:
                    pass
        self.temporary.cleanup()

    @staticmethod
    def write(path: Path, body: str, *, python: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((f"#!{sys.executable}\n" if python else "#!/bin/sh\n") + body)
        path.chmod(0o755)

    def report(self, cwd: Path | None = None) -> tuple[int, str, float]:
        started = time.monotonic()
        process = subprocess.Popen([str(CHECK), "--for-run"], cwd=cwd or self.project,
                                   env=self.env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, start_new_session=True)
        try:
            output, _ = process.communicate(timeout=6)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            self.retired_groups.add(process.pid)
            output, _ = process.communicate()
            self.fail("optional probe prevented the tooling report from returning: " + output)
        assert process.returncode is not None
        return process.returncode, output, time.monotonic() - started

    def worker(self, *, parent_exit: int | None = None) -> None:
        child = ("import json, os, signal, time\nfrom pathlib import Path\n"
                 "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                 f"Path({str(self.base / 'child.pid')!r}).write_text(json.dumps("
                 "{'pid': os.getpid(), 'pgid': os.getpgid(0), 'sid': os.getsid(0)}))\n"
                 "time.sleep(60)\n")
        body = ("import json, os, subprocess, sys, time\nfrom pathlib import Path\n"
                f"Path({str(self.base / 'parent.pid')!r}).write_text(json.dumps("
                "{'pid': os.getpid(), 'pgid': os.getpgid(0), 'sid': os.getsid(0)}))\n"
                f"subprocess.Popen([sys.executable, '-c', {child!r}])\n"
                f"while not Path({str(self.base / 'child.pid')!r}).exists(): time.sleep(.01)\n")
        body += "time.sleep(60)\n" if parent_exit is None else f"raise SystemExit({parent_exit})\n"
        self.write(self.bin / "playwright", body, python=True)
        self.write(self.bin / "npx", "exec " + shlex.quote(str(self.bin / "playwright")) + "\n")

    def assert_worker_stopped(self) -> None:
        path = self.base / "child.pid"
        self.assertTrue(path.exists(), "the controlled child never started")
        pid = json.loads(path.read_text())["pid"]
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            result = subprocess.run(["/bin/ps", "-o", "stat=", "-p", str(pid)],
                                    capture_output=True, text=True, check=False)
            if not result.stdout.strip() or result.stdout.strip().startswith("Z"):
                return
            time.sleep(.02)
        self.fail("optional probe left its TERM-ignoring child running")

    def test_missing_playwright_never_invokes_package_executor(self) -> None:
        self.write(self.bin / "npx", f"echo called >> '{self.npx_log}'\nexit 0\n")
        code, output, _ = self.report()
        self.assertEqual(code, 0)
        self.assertIn("Playwright is missing", output)
        self.assertFalse(self.npx_log.exists(), "availability discovery called npx")

    def test_installed_path_binary_is_ready_without_npx(self) -> None:
        self.write(self.bin / "playwright", "echo 'Version 1.0.0'\n")
        code, output, _ = self.report()
        self.assertEqual(code, 0)
        self.assertIn("Playwright is ready", output)
        self.assertFalse(self.npx_log.exists())

    def test_installed_ancestor_package_binary_is_ready(self) -> None:
        self.write(self.project / "node_modules" / ".bin" / "playwright",
                   "echo 'Version 1.0.0'\n")
        nested = self.project / "src" / "nested"
        nested.mkdir(parents=True)
        code, output, _ = self.report(nested)
        self.assertEqual(code, 0)
        self.assertIn("Playwright is ready", output)
        self.assertFalse(self.npx_log.exists())

    def test_failed_installed_binary_is_optional(self) -> None:
        called = self.base / "playwright.log"
        self.write(self.bin / "playwright", f"echo called > '{called}'\nexit 9\n")
        code, output, _ = self.report()
        self.assertEqual(code, 0)
        self.assertIn("Playwright is missing", output)
        self.assertTrue(called.exists())

    def test_stalled_probe_and_term_ignoring_child_are_stopped(self) -> None:
        self.worker()
        code, output, elapsed = self.report()
        self.assertEqual(code, 0)
        self.assertIn("Playwright is missing", output)
        self.assertLess(elapsed, 5)
        self.assert_worker_stopped()

    def test_child_is_stopped_even_when_parent_exits_first(self) -> None:
        self.worker(parent_exit=0)
        code, output, elapsed = self.report()
        self.assertEqual(code, 0)
        self.assertIn("Playwright is ready", output)
        self.assertLess(elapsed, 5)
        self.assert_worker_stopped()

    def test_failed_parent_leaves_no_running_child(self) -> None:
        self.worker(parent_exit=9)
        code, output, _ = self.report()
        self.assertEqual(code, 0)
        self.assertIn("Playwright is missing", output)
        self.assert_worker_stopped()

    def test_optional_success_does_not_excuse_missing_required_tool(self) -> None:
        (self.bin / "openssl").unlink()
        self.write(self.bin / "playwright", "echo 'Version 1.0.0'\n")
        code, output, _ = self.report()
        self.assertEqual(code, 1)
        self.assertIn("openssl is missing", output)


if __name__ == "__main__":
    unittest.main()
